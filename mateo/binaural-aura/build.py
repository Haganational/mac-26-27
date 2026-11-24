"""Binaural Aura: python mateo/binaural-aura/build.py [HOURS] [OUT]

Picture: Matthew's Pacific sunset at Sunset Cliffs, with the cover (title, Mateo upper right, REST · DIGEST)
fading at 9-15 s. The photo drifts toward the sun, then blurs while a spiral galaxy blooms out of the sun
and takes the screen. The galaxy turns slowly as you fall into it, dimming to pure black by 20:00. After that
the screen stays black. Sound: binaural_audio.py (Pacific swell + 75/81 Hz binaural, a 6 Hz theta beat).
Run by .github/workflows/mateo.yml before upload. Needs numpy, scipy, pillow, ffmpeg.
"""
import subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageOps

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from galaxy import galaxy  # noqa: E402

W, H, FPS = 1280, 720, 24
INTRO = 1200            # seconds until fully black
SUN = (616.0, 226.0)    # where the sun sits in the photo frame
T_BLUR, T_GAL, T_FULL = 100.0, 115.0, 240.0
ENC = ["-c:v", "libx264", "-preset", "slow", "-crf", "30", "-g", "240", "-pix_fmt", "yuv420p", "-r", str(FPS)]
FF = ["ffmpeg", "-v", "error", "-y"]
GN = 1500


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Scene:
    def __init__(self):
        im = ImageOps.fit(Image.open(HERE / "assets" / "sun-on-water.jpg").convert("RGB"), (W, H), Image.LANCZOS)
        self.photo = im.resize((int(W * 1.6), int(H * 1.6)), Image.LANCZOS)  # headroom for the drift zoom
        self.gal = Image.fromarray((galaxy(GN) * 255).astype(np.uint8))

    def view(self, t):
        z = 1.0 + 0.10 * smooth(t / 200)                     # slow push toward the sun
        cx = W / 2 + (SUN[0] - W / 2) * smooth(t / 200) * 0.6
        cy = H / 2 + (SUN[1] - H / 2) * smooth(t / 200) * 0.6
        a = 1.6 / z                                           # source px per output px
        x0 = cx * 1.6 - W / 2 * a; y0 = cy * 1.6 - H / 2 * a
        x0 = min(max(x0, 0), self.photo.width - W * a); y0 = min(max(y0, 0), self.photo.height - H * a)
        return a, x0, y0

    def sun_on_screen(self, t):
        a, x0, y0 = self.view(t)
        return (SUN[0] * 1.6 - x0) / a, (SUN[1] * 1.6 - y0) / a

    def photo_at(self, t):
        a, x0, y0 = self.view(t)
        img = self.photo.transform((W, H), Image.AFFINE, (a, 0, x0, 0, a, y0), resample=Image.BILINEAR)
        r = 34 * smooth((t - T_BLUR) / (T_FULL - T_BLUR - 40))
        if r > 0.3:
            img = img.filter(ImageFilter.GaussianBlur(r))
        return np.asarray(img).astype(np.float32) / 255

    def galaxy_at(self, t):
        u = smooth((t - T_GAL) / (T_FULL - T_GAL))
        sx, sy = self.sun_on_screen(min(t, 200.0))
        cx = sx + (W / 2 - sx) * u; cy = sy + (H / 2 - sy) * u
        # texture px per output px: starts small at the sun (radius ~180 px), fills the frame, then keeps falling in
        s = (GN / 2) / (180 + 520 * u) * (1 - 0.25 * smooth((t - T_FULL) / (INTRO - T_FULL)))
        ang = -2 * np.pi * (t - T_GAL) / 420.0               # one slow turn every 7 minutes
        c, sn = np.cos(ang) * s, np.sin(ang) * s
        # output (x, y) -> texture: R*s*(p - centre) + texture centre
        a, b, d, e = c, -sn, sn, c
        x0 = GN / 2 - (a * cx + b * cy); y0 = GN / 2 - (d * cx + e * cy)
        img = self.gal.transform((W, H), Image.AFFINE, (a, b, x0, d, e, y0), resample=Image.BILINEAR)
        return np.asarray(img).astype(np.float32) / 255

    def frame(self, t):
        g_a = smooth((t - T_GAL) / 110)
        p_w = 1 - smooth((t - 160) / (T_FULL - 160))
        f = self.photo_at(t) if p_w > 0 else None
        if g_a > 0:
            g = self.galaxy_at(t) * g_a
            f = g if f is None else 1 - (1 - f * p_w) * (1 - g)   # screen blend: the galaxy glows out of the blur
        return f


def frames(overlay):
    sc = Scene()
    oa = overlay[..., 3:4].astype(np.float32) / 255
    oc = overlay[..., :3].astype(np.float32) / 255
    for i in range(INTRO * FPS):
        t = i / FPS
        f = sc.frame(t)
        a = 1 - smooth((t - 9) / 6)  # title, Mateo and REST · DIGEST fade together, 9-15 s
        if a > 0:
            f = f * (1 - oa * a) + oc * oa * a
        f = f * (1 - smooth((t - T_FULL) / (INTRO - T_FULL))) ** 1.6
        yield (np.clip(f, 0, 1) * 255).astype(np.uint8).tobytes()


if __name__ == "__main__":
    HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 8
    OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "video.mp4"
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
        audio = subprocess.Popen([sys.executable, HERE / "binaural_audio.py", str(dur), "3"], stdout=subprocess.PIPE)
        subprocess.run(FF + ["-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "-", "-i", t / "picture.mp4", "-map", "1:v", "-map", "0:a",
                             "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", OUT],
                       stdin=audio.stdout, check=True)
        audio.stdout.close()
        if audio.wait():
            sys.exit("binaural_audio.py failed")
    print(f"built {OUT} ({OUT.stat().st_size / 1e6:.0f} MB, {dur / 3600:.2f} h)")
