"""Builds video.mp4 for this folder: python mateo/rain-window/build.py [HOURS] [OUT]

Run by .github/workflows/mateo.yml before upload, so the long file never sits in the repo.
Picture: 60 s cover intro, bright scene to 5:00, a 60 s dim-down, then the dark night scene.
Sound: rain_audio.py, generated fresh for the whole length (never loops). Needs numpy, scipy,
pillow and ffmpeg.
"""
import subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 8
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "video.mp4"
TOTAL = int(HOURS * 3600)
LOOP, BRIGHT_UNTIL, DIM = 30, 300, "0.16"
ENC = ["-c:v", "libx264", "-preset", "veryslow", "-crf", "34", "-g", "360", "-bf", "4", "-pix_fmt", "yuv420p", "-r", "12"]
RAW = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1280x720", "-r", "12"]
FF = ["ffmpeg", "-v", "error", "-y"]


def sh(cmd, **kw):
    print("+", " ".join(map(str, cmd))[:160], flush=True)
    subprocess.run(cmd, check=True, **kw)


with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    for name, dim in (("bright", "1.0"), ("dim", DIM)):
        with open(t / f"{name}.rgb", "wb") as f:
            sh([sys.executable, HERE / "rain_video.py", dim], stdout=f)
    sh(FF + RAW + ["-i", t / "bright.rgb"] + ENC + [t / "bright.mp4"])
    sh(FF + RAW + ["-i", t / "dim.rgb"] + ENC + [t / "dim.mp4"])
    # cover intro: two loops with the title card, card fades out 8-10.5 s
    sh(FF + RAW + ["-stream_loop", "1", "-i", t / "bright.rgb", "-loop", "1", "-r", "12", "-i", HERE / "cover-overlay.png",
                   "-filter_complex", "[1]format=rgba,fade=t=out:st=8:d=2.5:alpha=1[o];[0][o]overlay=shortest=1"] + ENC + [t / "intro.mp4"])
    # dim-down: two loops blending bright -> night over 60 s
    sh(FF + RAW + ["-stream_loop", "1", "-i", t / "bright.rgb"] + RAW + ["-stream_loop", "1", "-i", t / "dim.rgb",
                   "-filter_complex", "[0][1]blend=all_expr='A*(1-min(T/60\\,1))+B*min(T/60\\,1)'"] + ENC + [t / "fade.mp4"])
    n_bright = (BRIGHT_UNTIL - 60) // LOOP
    n_dim = (TOTAL - BRIGHT_UNTIL - 60) // LOOP
    lines = ["file 'intro.mp4'"] + ["file 'bright.mp4'"] * n_bright + ["file 'fade.mp4'"] + ["file 'dim.mp4'"] * n_dim
    (t / "list.txt").write_text("\n".join(lines) + "\n")
    sh(FF + ["-f", "concat", "-safe", "0", "-i", t / "list.txt", "-c", "copy", t / "picture.mp4"])
    dur = 60 + n_bright * LOOP + 60 + n_dim * LOOP
    audio = subprocess.Popen([sys.executable, HERE / "rain_audio.py", str(dur)], stdout=subprocess.PIPE)
    sh(FF + ["-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "-", "-i", t / "picture.mp4", "-map", "1:v", "-map", "0:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-shortest", OUT], stdin=audio.stdout)
    audio.stdout.close()
    if audio.wait():
        sys.exit("rain_audio.py failed")
print(f"built {OUT} ({OUT.stat().st_size / 1e6:.0f} MB, {dur / 3600:.2f} h)")
