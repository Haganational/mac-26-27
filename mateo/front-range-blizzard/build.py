"""Front Range Blizzard: python mateo/front-range-blizzard/build.py [HOURS] [OUT]

Picture: Matthew's March 2019 Front Range hike photos (snowy ridges and canyon), each slowly zooming with
crossfades, the cover (title, Mateo upper right, REST · DIGEST) fading out at 9-15 s. A blizzard rolls in:
falling snow thickens, wind drifts it sideways, the blue sky goes grey-white and the colour drains, while the
whole picture dims to pure black by 20:00. After that the screen stays black, the kindest dark for eyes.
Sound: blizzard_audio.py (synthesized wind, gusts, eave howl, snow on the glass), the whole length, no loops.
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
PHOTOS = ["wide-ridge", "ridge-pines", "canyon-view", "two-hikers", "canyon-peaks", "cottonwood-bridge",
          "canyon-trail", "bare-trees"]
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


class Snow:
    """Falling snow at half resolution: far, mid and near flakes, pushed sideways by a gusting wind."""
    def __init__(self, n=2600, seed=3172019):
        self.r = np.random.default_rng(seed)
        self.x = self.r.uniform(0, 1, n); self.y = self.r.uniform(0, 1, n)
        self.z = self.r.choice([0, 1, 2], n, p=[0.55, 0.32, 0.13])        # depth layer
        self.ph = self.r.uniform(0, 2 * np.pi, n)
        self.order = self.r.permutation(n)                                 # who shows first as it thickens

    def wind(self, t):
        return 0.10 + 0.07 * np.sin(t / 7.3) + 0.05 * np.sin(t / 2.9 + 1) + 0.04 * np.sin(t / 17.0 + 2)

    def frame(self, t, density):
        dt = 1 / FPS
        fall = np.array([0.055, 0.10, 0.17])[self.z]
        self.y += fall * dt * (1 + 0.15 * np.sin(self.ph + t))
        self.x += (self.wind(t) * (0.6 + 0.35 * self.z) + 0.01 * np.sin(t * 1.3 + self.ph)) * dt
        self.y %= 1.0; self.x %= 1.0
        k = int(len(self.x) * min(max(density, 0), 1))
        w, h = W // 2, H // 2
        out = np.zeros((h, w), np.float32)
        for layer, (sig, amp) in enumerate([(0.5, 0.55), (1.0, 0.9), (1.9, 1.6)]):
            sel = self.order[:k][self.z[self.order[:k]] == layer]
            if len(sel) == 0:
                continue
            acc = np.zeros((h, w), np.float32)
            np.add.at(acc, ((self.y[sel] * (h - 1)).astype(int), (self.x[sel] * (w - 1)).astype(int)), amp)
            out += gaussian_filter(acc, sig) * (2 * np.pi * sig * sig)
        img = Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
        return np.asarray(img).astype(np.float32)[..., None] / 255


def storm_grade(f, s):
    """s 0..1: blue sky to grey-white whiteout. Desaturate, cool, lift into haze, soften contrast."""
    if s <= 0:
        return f
    g = f.mean(axis=2, keepdims=True)
    f = f * (1 - 0.7 * s) + g * 0.7 * s
    f = f * (1 - 0.18 * s) + np.array([0.80, 0.84, 0.90], np.float32) * 0.18 * s
    return f * np.array([1 - 0.06 * s, 1 - 0.02 * s, 1.0], np.float32)


def frames(overlay):
    ps = [prep(n) for n in PHOTOS]
    oa = overlay[..., 3:4].astype(np.float32) / 255
    oc = overlay[..., :3].astype(np.float32) / 255
    step = SLIDE - XF
    snow = Snow()
    for i in range(INTRO * FPS):
        t = i / FPS
        j = min(int(t // step), len(ps) - 1); u0 = t - j * step
        f = slide_frame(ps[j], min(u0 / SLIDE, 1.0), j)
        if u0 < XF and j > 0:
            g = slide_frame(ps[j - 1], (u0 + step) / SLIDE, j - 1)
            f = g * (1 - smooth(u0 / XF)) + f * smooth(u0 / XF)
        s = smooth((t - 20) / 520)                       # the blizzard rolls in over the first ~9 minutes
        f = storm_grade(f, s)
        fl = snow.frame(t, 0.12 + 0.88 * s)
        f = f + (np.array([0.96, 0.97, 1.0], np.float32) - f) * np.clip(fl, 0, 1) * (0.75 + 0.2 * s)
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
        audio = subprocess.Popen([sys.executable, HERE / "blizzard_audio.py", str(dur), "3"], stdout=subprocess.PIPE)
        subprocess.run(FF + ["-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "-", "-i", t / "picture.mp4", "-map", "1:v", "-map", "0:a",
                             "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-shortest", OUT],
                       stdin=audio.stdout, check=True)
        audio.stdout.close()
        if audio.wait():
            sys.exit("blizzard_audio.py failed")
    print(f"built {OUT} ({OUT.stat().st_size / 1e6:.0f} MB, {dur / 3600:.2f} h)")
