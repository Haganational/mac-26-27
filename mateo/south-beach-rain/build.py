"""South Beach Rain: python mateo/south-beach-rain/build.py [HOURS] [OUT]

Picture: Matthew's rain clip on Ocean Drive with the cover (title, Mateo upper right, REST · DIGEST)
fading out, then his four South Beach photos slowly cycling (soft zoom, crossfades) while the whole
picture dims to pure black by 20:00. After that the screen stays black, the kindest dark for eyes.
Sound: ../rain-window/rain_audio.py (synthesized rain + brown noise), the whole length, no loops.
Run by .github/workflows/mateo.yml before upload. Needs numpy, scipy, pillow, ffmpeg.
"""
import subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 8
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "video.mp4"
W, H, FPS = 1280, 720, 24
INTRO = int(sys.argv[3]) if len(sys.argv) > 3 else 1200  # seconds until fully black
SLIDE, XF = 75.0, 6.0
PHOTOS = ["ocean-drive", "breakwater", "palms", "clevelander"]
ENC = ["-c:v", "libx264", "-preset", "slow", "-crf", "30", "-g", "240", "-pix_fmt", "yuv420p", "-r", str(FPS)]
FF = ["ffmpeg", "-v", "error", "-y"]


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def prep(name):
    im = Image.open(HERE / "assets" / f"{name}.jpg").convert("RGB")
    bg = im.resize((W, int(W * im.height / im.width))).crop((0, 0, W, H)) if False else None
    s = max(W / im.width, H / im.height)
    bg = im.resize((int(im.width * s) + 1, int(im.height * s) + 1)).crop((0, 0, W, H)).filter(ImageFilter.GaussianBlur(28))
    bg = np.asarray(bg).astype(np.float32) / 255 * 0.45
    fh = H; fw = int(im.width * fh / im.height)
    big = im.resize((int(fw * 1.12), int(fh * 1.12)), Image.LANCZOS)
    return bg, big, fw, fh


def slide_frame(p, u, k):
    """Photo p at progress u (0..1): slow zoom out 1.12 -> 1.0, gentle drift; returns float RGB."""
    bg, big, fw, fh = p
    z = 1.12 - 0.12 * u
    cw, ch = fw * z / 1.12 * 1.12 / z, fh  # display size stays fw x fh
    sw, sh_ = big.width / z, big.height / z  # source window size in big's pixels
    drift = (0.5 + 0.35 * np.sin(np.pi * u + k)) * (big.width - sw)
    x0, y0 = drift, (big.height - sh_) * 0.5
    a = sw / fw
    img = big.transform((fw, fh), Image.AFFINE, (a, 0, x0, 0, a, y0), resample=Image.BICUBIC)
    out = bg.copy()
    x = (W - fw) // 2
    out[:, x:x + fw] = np.asarray(img).astype(np.float32) / 255
    # soft shadow edges
    return out


def frames(clip_raw, overlay):
    clip = np.frombuffer(clip_raw, np.uint8).reshape(-1, H, W, 3)
    nclip = len(clip)
    ps = [prep(n) for n in PHOTOS]
    oa = overlay[..., 3:4].astype(np.float32) / 255
    oc = overlay[..., :3].astype(np.float32) / 255
    t0 = nclip / FPS - 2.5  # photos start under the last 2.5 s of the clip
    for i in range(INTRO * FPS):
        t = i / FPS
        if t >= t0:
            s = t - t0
            j = int(s // (SLIDE - XF)); u0 = s - j * (SLIDE - XF)
            f = slide_frame(ps[j % 4], u0 / SLIDE, j)
            if u0 < XF and j > 0:
                g = slide_frame(ps[(j - 1) % 4], (u0 + SLIDE - XF) / SLIDE, j - 1)
                f = g * (1 - smooth(u0 / XF)) + f * smooth(u0 / XF)
            if i < nclip:
                c = clip[i].astype(np.float32) / 255
                m = smooth(s / 2.5)
                f = c * (1 - m) + f * m
        else:
            f = clip[min(i, nclip - 1)].astype(np.float32) / 255
        a = 1 - smooth((t - 9) / 6)  # title, Mateo and REST · DIGEST fade together, 9-15 s
        if a > 0:
            f = f * (1 - oa * a) + oc * oa * a
        dim = 1 - smooth((t - 45) / (INTRO - 45))
        f = f * dim ** 1.6
        yield (np.clip(f, 0, 1) * 255).astype(np.uint8).tobytes()


with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    clip_raw = subprocess.run(FF + ["-i", HERE / "assets" / "clip.mp4", "-vf", f"scale={W}:{H},fps={FPS}", "-f", "rawvideo",
                                    "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    overlay = np.asarray(Image.open(HERE / "overlay.png").convert("RGBA"))
    enc = subprocess.Popen(FF + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"] + ENC + [t / "intro.mp4"],
                           stdin=subprocess.PIPE)
    for k, fr in enumerate(frames(clip_raw, overlay)):
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
    audio = subprocess.Popen([sys.executable, HERE.parent / "rain-window" / "rain_audio.py", str(dur), "3"], stdout=subprocess.PIPE)
    subprocess.run(FF + ["-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "-", "-i", t / "picture.mp4", "-map", "1:v", "-map", "0:a",
                         "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-shortest", OUT],
                   stdin=audio.stdout, check=True)
    audio.stdout.close()
    if audio.wait():
        sys.exit("rain_audio.py failed")
print(f"built {OUT} ({OUT.stat().st_size / 1e6:.0f} MB, {dur / 3600:.2f} h)")
