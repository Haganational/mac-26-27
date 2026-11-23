"""Bay Breezes: python mateo/bay-breezes/build.py [HOURS] [OUT]

Picture: Matthew's Golden Gate cover shot, then his Big Sur afternoon (Sep 6 2018) and Marin Headlands sunset (Sep 10 2018), each slowly zooming
with crossfades, the cover (title, Mateo upper right, REST · DIGEST) fading out at 9-15 s, while the
whole picture dims to pure black by 20:00. After that the screen stays black, the kindest dark for eyes.
Sound: bay_audio.py (synthesized gusting bay breeze, lapping water, a rare faint foghorn), the whole length, no loops.
Run by .github/workflows/mateo.yml before upload. Needs numpy, scipy, pillow, ffmpeg.
"""
import subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 8
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "video.mp4"
W, H, FPS = 1280, 720, 24
INTRO = int(sys.argv[3]) if len(sys.argv) > 3 else 1200  # seconds until fully black
PHOTOS = ["golden-gate-wide", "bigsur-cove", "bigsur-cypress-cove", "bigsur-cypress", "bigsur-headland", "bigsur-cove-wide",
          "bigsur-blue", "bigsur-blue-brush", "headlands-first-light", "golden-gate-gold", "headlands-sunburst",
          "headlands-ridge", "headlands-sea", "golden-gate-path", "golden-gate-dusk", "golden-gate-last",
          "headlands-last-light"]
XF = 6.0
SLIDE = INTRO / len(PHOTOS) + XF  # the last photo ends as the screen reaches black
ENC = ["-c:v", "libx264", "-preset", "slow", "-crf", "30", "-g", "240", "-pix_fmt", "yuv420p", "-r", str(FPS)]
FF = ["ffmpeg", "-v", "error", "-y"]


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def prep(name):
    im = Image.open(HERE / "assets" / f"{name}.jpg").convert("RGB")
    s = max(W / im.width, H / im.height) * 1.12
    return im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)


def slide_frame(big, u, k):
    """Photo at progress u (0..1): slow zoom out 1.12 -> 1.0 with a gentle drift; returns float RGB."""
    z = 1.12 - 0.12 * u
    a = big.width / (W * 1.12) * (1.12 / z)
    sw, sh = W * a, H * a
    x0 = (0.5 + 0.35 * np.sin(np.pi * u + k)) * (big.width - sw)
    y0 = (big.height - sh) * 0.5
    img = big.transform((W, H), Image.AFFINE, (a, 0, x0, 0, a, y0), resample=Image.BICUBIC)
    return np.asarray(img).astype(np.float32) / 255


def frames(overlay):
    ps = [prep(n) for n in PHOTOS]
    oa = overlay[..., 3:4].astype(np.float32) / 255
    oc = overlay[..., :3].astype(np.float32) / 255
    step = SLIDE - XF
    for i in range(INTRO * FPS):
        t = i / FPS
        j = min(int(t // step), len(ps) - 1); u0 = t - j * step
        f = slide_frame(ps[j], min(u0 / SLIDE, 1.0), j)
        if u0 < XF and j > 0:
            g = slide_frame(ps[j - 1], (u0 + step) / SLIDE, j - 1)
            f = g * (1 - smooth(u0 / XF)) + f * smooth(u0 / XF)
        a = 1 - smooth((t - 9) / 6)  # title, Mateo and REST · DIGEST fade together, 9-15 s
        if a > 0:
            f = f * (1 - oa * a) + oc * oa * a
        dim = 1 - smooth((t - 45) / (INTRO - 45))
        f = f * dim ** 1.6
        yield (np.clip(f, 0, 1) * 255).astype(np.uint8).tobytes()


with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    overlay = np.asarray(Image.open(HERE / "overlay.png").convert("RGBA"))
    enc = subprocess.Popen(FF + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"] + ENC + [t / "intro.mp4"],
                           stdin=subprocess.PIPE)
    for k, fr in enumerate(frames(overlay)):
        enc.stdin.write(fr)
        if k % (FPS * 60) == 0:
            print(f"picture {k // FPS}s", flush=True)
    enc.stdin.close()
    if enc.wait():
        sys.exit("intro encode failed")
    subprocess.run(FF + ["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d=60"] + ENC + [t / "black.mp4"], check=True)
    total = int(HOURS * 3600)
    n_black = max(0, (total - INTRO) // 60)
    (t / "list.txt").write_text("file 'intro.mp4'\n" + "file 'black.mp4'\n" * n_black)
    subprocess.run(FF + ["-f", "concat", "-safe", "0", "-i", t / "list.txt", "-c", "copy", t / "picture.mp4"], check=True)
    dur = INTRO + n_black * 60
    audio = subprocess.Popen([sys.executable, HERE / "bay_audio.py", str(dur), "3"], stdout=subprocess.PIPE)
    subprocess.run(FF + ["-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "-", "-i", t / "picture.mp4", "-map", "1:v", "-map", "0:a",
                         "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-shortest", OUT],
                   stdin=audio.stdout, check=True)
    audio.stdout.close()
    if audio.wait():
        sys.exit("bay_audio.py failed")
print(f"built {OUT} ({OUT.stat().st_size / 1e6:.0f} MB, {dur / 3600:.2f} h)")
