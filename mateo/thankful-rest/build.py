"""Thankful Rest: python mateo/thankful-rest/build.py [HOURS] [OUT]

Picture: Matthew's fall foliage photos (Niagara gorge in red and gold, river paths, sumac and sycamores, misty
gorge to finish), each slowly zooming with crossfades, the cover (title, Mateo upper right, REST · DIGEST) fading
out at 9-15 s. A few autumn leaves drift down through the frame on the breeze, the light warms toward late
afternoon, and the whole picture dims to pure black by 20:00. After that the screen stays black.
Sound: fall_audio.py (synthesized breeze, slow gusts, rustling leaves, a rare skitter), the whole length, no loops.
Run by .github/workflows/mateo.yml before upload. Needs numpy, scipy, pillow, ffmpeg.
"""
import subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 8
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "video.mp4"
W, H, FPS = 1280, 720, 24
INTRO = int(sys.argv[3]) if len(sys.argv) > 3 else 1200  # seconds until fully black
PHOTOS = ["red-whirlpool", "rapids-leaves", "gorge-bend", "whirlpool", "golden-river", "sycamores", "sumac-woods",
          "river-flats", "bridge-road", "red-sumac", "lone-tree-mist", "misty-saplings"]
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


LEAF_COLS = np.array([[0.86, 0.36, 0.10], [0.78, 0.18, 0.08], [0.93, 0.62, 0.16], [0.62, 0.30, 0.10], [0.90, 0.48, 0.12]],
                     np.float32)


class Leaves:
    """A few autumn leaves drifting down at half resolution: soft colored flecks that flutter and sway."""
    def __init__(self, n=55, seed=11262026):
        self.r = np.random.default_rng(seed)
        self.x = self.r.uniform(0, 1, n); self.y = self.r.uniform(0, 1, n)
        self.z = self.r.choice([0, 1, 2], n, p=[0.5, 0.35, 0.15])
        self.ph = self.r.uniform(0, 2 * np.pi, n); self.sp = self.r.uniform(0.5, 1.2, n)
        self.col = LEAF_COLS[self.r.integers(0, len(LEAF_COLS), n)]

    def frame(self, t):
        dt = 1 / FPS
        fall = np.array([0.025, 0.04, 0.065])[self.z] * self.sp
        self.y += fall * dt * (1 + 0.5 * np.sin(2.1 * t * self.sp + self.ph))
        self.x += (0.012 + 0.03 * np.sin(t / 9.0) + 0.02 * np.sin(1.3 * t * self.sp + self.ph) * (1 + self.z)) * dt
        self.y %= 1.0; self.x %= 1.0
        w, h = W // 2, H // 2
        alpha = np.zeros((h, w), np.float32); rgb = np.zeros((h, w, 3), np.float32)
        for layer, (sig, amp) in enumerate([(1.6, 0.85), (2.6, 0.95), (4.2, 1.0)]):
            sel = np.nonzero(self.z == layer)[0]
            a = np.zeros((h, w), np.float32); c = np.zeros((h, w, 3), np.float32)
            iy = (self.y[sel] * (h - 1)).astype(int); ix = (self.x[sel] * (w - 1)).astype(int)
            flick = 0.55 + 0.45 * np.abs(np.sin(3.0 * t * self.sp[sel] + self.ph[sel]))   # leaves turning in the air
            np.add.at(a, (iy, ix), amp * flick)
            for ch in range(3):
                np.add.at(c[..., ch], (iy, ix), amp * flick * self.col[sel, ch])
            k = 2 * np.pi * sig * sig
            alpha += gaussian_filter(a, (sig, sig * 1.5)) * k
            rgb += np.stack([gaussian_filter(c[..., ch], (sig, sig * 1.5)) * k for ch in range(3)], -1)
        col = rgb / np.maximum(alpha[..., None], 1e-4)
        al = np.clip(alpha, 0, 1)
        im = lambda x: np.asarray(Image.fromarray(np.clip(x * 255, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)).astype(np.float32) / 255
        return im(col), im(al)[..., None]


def warm(f, s):
    """s 0..1: soft late-afternoon warmth, a touch of amber and lower contrast as the light goes."""
    if s <= 0:
        return f
    f = f * np.array([1 + 0.05 * s, 1 - 0.01 * s, 1 - 0.12 * s], np.float32)
    return f * (1 - 0.1 * s) + 0.1 * s * f.mean(axis=2, keepdims=True)


def frames(overlay):
    ps = [prep(n) for n in PHOTOS]
    oa = overlay[..., 3:4].astype(np.float32) / 255
    oc = overlay[..., :3].astype(np.float32) / 255
    step = SLIDE - XF
    leaves = Leaves()
    for i in range(INTRO * FPS):
        t = i / FPS
        j = min(int(t // step), len(ps) - 1); u0 = t - j * step
        f = slide_frame(ps[j], min(u0 / SLIDE, 1.0), j)
        if u0 < XF and j > 0:
            g = slide_frame(ps[j - 1], (u0 + step) / SLIDE, j - 1)
            f = g * (1 - smooth(u0 / XF)) + f * smooth(u0 / XF)
        f = warm(f, smooth((t - 30) / 700))
        lc, la = leaves.frame(t)
        f = f * (1 - la * 0.9) + lc * la * 0.9
        a = 1 - smooth((t - 9) / 6)  # title, Mateo and REST · DIGEST fade together, 9-15 s
        if a > 0:
            f = f * (1 - oa * a) + oc * oa * a
        dim = 1 - smooth((t - 45) / (INTRO - 45))
        f = f * dim ** 1.6
        yield (np.clip(f, 0, 1) * 255).astype(np.uint8).tobytes()


if __name__ == "__main__":
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
        audio = subprocess.Popen([sys.executable, HERE / "fall_audio.py", str(dur), "3"], stdout=subprocess.PIPE)
        subprocess.run(FF + ["-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "-", "-i", t / "picture.mp4", "-map", "1:v", "-map", "0:a",
                             "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-shortest", OUT],
                       stdin=audio.stdout, check=True)
        audio.stdout.close()
        if audio.wait():
            sys.exit("fall_audio.py failed")
    print(f"built {OUT} ({OUT.stat().st_size / 1e6:.0f} MB, {dur / 3600:.2f} h)")
