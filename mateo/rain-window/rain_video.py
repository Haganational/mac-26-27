"""Rain on Mateo's window: a seamless 30 s loop drawn from scratch. Raw RGB24 frames to stdout.

python rain_video.py [dim]   dim = 1.0 full scene, smaller = darker (the night version uses ~0.16)
Seamless by construction: every drop's path wraps a whole number of times per loop.
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS, LOOP = 1280, 720, 12, 30
T = FPS * LOOP
DIM = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
rng = np.random.default_rng(7)

# window opening (glass area) and the room around it
gx0, gy0, gx1, gy1 = 420, 60, 1080, 560
room = Image.new("RGB", (W, H), (14, 10, 12))
d = ImageDraw.Draw(room)
# warm lamp light on the wall, lower left
yy, xx = np.mgrid[0:H, 0:W]
lamp = np.exp(-(((xx - 170) / 380) ** 2 + ((yy - 380) / 300) ** 2))
roomA = np.asarray(room).astype(float) / 255 + lamp[..., None] * np.array([0.33, 0.2, 0.09])
# outside: deep blue night, soft city bokeh far away
sky = np.zeros((gy1 - gy0, gx1 - gx0, 3))
v = np.linspace(0, 1, gy1 - gy0)[:, None, None]
sky += (1 - v) * np.array([0.03, 0.06, 0.13]) + v * np.array([0.05, 0.08, 0.16])
bok = Image.new("RGB", (gx1 - gx0, gy1 - gy0), (0, 0, 0))
bd = ImageDraw.Draw(bok)
for _ in range(38):
    x, y, r = rng.uniform(0, gx1 - gx0), rng.uniform(250, gy1 - gy0), rng.uniform(5, 16)
    c = [(255, 190, 110), (120, 170, 255), (255, 140, 90), (200, 210, 255)][rng.integers(4)]
    k = rng.uniform(0.25, 0.6)
    bd.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(q * k) for q in c))
bokA = np.asarray(bok.filter(ImageFilter.GaussianBlur(9))).astype(float) / 255
outside = np.clip(sky + bokA, 0, 1)
# blurred copy of outside, used for what you see through a drop (refraction-ish)
outsideB = np.asarray(Image.fromarray((outside * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))).astype(float) / 255

# frame + mullions, lamp-lit wood
frame = Image.new("L", (W, H), 0)
fd = ImageDraw.Draw(frame)
fd.rectangle([gx0 - 26, gy0 - 26, gx1 + 26, gy1 + 34], fill=255)
fd.rectangle([gx0, gy0, gx1, gy1], fill=0)
fd.rectangle([(gx0 + gx1) // 2 - 9, gy0, (gx0 + gx1) // 2 + 9, gy1], fill=255)
fd.rectangle([gx0, (gy0 + gy1) // 2 - 9, gx1, (gy0 + gy1) // 2 + 9], fill=255)
frameM = np.asarray(frame.filter(ImageFilter.GaussianBlur(1))).astype(float)[..., None] / 255
wood = np.array([0.17, 0.11, 0.08]) * (0.6 + 0.9 * lamp[..., None])

# table lamp (left) and a red/silver sequin throw folded over the window sill
lampM = Image.new("L", (W, H), 0); ld = ImageDraw.Draw(lampM)
ld.polygon([(120, 330), (220, 330), (245, 415), (95, 415)], fill=255)          # shade
shadeM = np.asarray(lampM.filter(ImageFilter.GaussianBlur(1.5))).astype(float)[..., None] / 255
stand = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(stand)
sd.rectangle([165, 415, 175, 560], fill=255); sd.ellipse([125, 550, 215, 575], fill=255)
sd.rectangle([40, 572, 300, 590], fill=255); sd.rectangle([60, 590, 76, 720], fill=255); sd.rectangle([264, 590, 280, 720], fill=255)
standM = np.asarray(stand.filter(ImageFilter.GaussianBlur(1))).astype(float)[..., None] / 255
sill = Image.new("L", (W, H), 0); ImageDraw.Draw(sill).rectangle([gx0 - 60, gy1 + 30, gx1 + 60, gy1 + 56], fill=255)
sillM = np.asarray(sill.filter(ImageFilter.GaussianBlur(1))).astype(float)[..., None] / 255
pts = [(400, gy1 + 26), (600, gy1 + 26), (606, gy1 + 60)]
for k in range(13):
    x = 606 - k * 17; pts.append((x, 700 + 14 * np.sin(k * 1.3) + (8 if k % 2 else 0)))
pts += [(396, gy1 + 60)]
throw = Image.new("L", (W, H), 0); ImageDraw.Draw(throw).polygon(pts, fill=255)
throwM = np.asarray(throw.filter(ImageFilter.GaussianBlur(2))).astype(float)[..., None] / 255
fold = np.clip(np.sin((xx - 400) / 11.0), 0, 1)[..., None] * 0.35 + 0.65  # vertical folds
sx, sy = rng.integers(396, 608, 1400), rng.integers(gy1 + 26, 715, 1400)
keep = throwM[sy, sx, 0] > 0.6
sx, sy = sx[keep], sy[keep]
scol = np.where(rng.random(len(sx))[:, None] < 0.55, np.array([[0.95, 0.15, 0.2]]), np.array([[0.9, 0.9, 0.95]]))
sph = rng.uniform(0, 2 * np.pi, len(sx)); sfr = rng.integers(1, 4, len(sx))
lamp2 = np.exp(-(((xx - 170) / 520) ** 2 + ((yy - 400) / 420) ** 2))[..., None]

# drops on the glass
GW, GH = gx1 - gx0, gy1 - gy0
beads = [(rng.uniform(0, GW), rng.uniform(0, GH), rng.uniform(1.0, 4.2)) for _ in range(260)]
runners = []
for _ in range(26):
    wraps = int(rng.integers(1, 4))
    runners.append(dict(x=rng.uniform(10, GW - 10), y0=rng.uniform(0, GH), wraps=wraps, r=rng.uniform(2.5, 4.5),
                        wob=rng.uniform(2, 7), wf=rng.uniform(0.5, 1.6), ph=rng.uniform(0, 6.28)))

def glass_frame(ti):
    """Alpha mask of water on the glass for frame ti, plus streak trails."""
    m = Image.new("L", (GW, GH), 0)
    g = ImageDraw.Draw(m)
    for x, y, r in beads:
        g.ellipse([x - r, y - r, x + r, y + r], fill=200)
    u = ti / T
    for R in runners:
        y = (R["y0"] + u * R["wraps"] * (GH + 80)) % (GH + 80) - 40
        x = R["x"] + R["wob"] * np.sin(2 * np.pi * R["wf"] * R["wraps"] * u + R["ph"])
        g.line([(x, y - 70), (x + R["wob"] * 0.3, y)], fill=90, width=max(1, int(R["r"] * 0.6)))
        g.ellipse([x - R["r"], y - R["r"] * 1.3, x + R["r"], y + R["r"] * 1.3], fill=255)
    return np.asarray(m.filter(ImageFilter.GaussianBlur(0.8))).astype(float)[..., None] / 255

# falling rain outside the glass (faint diagonal streaks)
falls = [(rng.uniform(-100, GW), rng.uniform(0, GH), int(rng.integers(4, 9))) for _ in range(160)]

base = roomA.copy()
base = base * (1 - frameM) + wood * frameM
for ti in range(T):
    img = base.copy()
    out = outside.copy()
    u = ti / T
    fl = Image.new("L", (GW, GH), 0); fdw = ImageDraw.Draw(fl)
    for x, y, w in falls:
        yy_ = (y + u * w * (GH + 60)) % (GH + 60) - 30
        xx_ = x + (yy_ - y) * 0.18
        fdw.line([(xx_, yy_), (xx_ + 4, yy_ + 22)], fill=60, width=1)
    out = np.clip(out + np.asarray(fl).astype(float)[..., None] / 255 * 0.22, 0, 1)
    wet = glass_frame(ti)
    glass = out * (1 - wet) + (outsideB * 1.6 + 0.05) * wet  # drops catch light
    img[gy0:gy1, gx0:gx1] = glass * (1 - frameM[gy0:gy1, gx0:gx1]) + img[gy0:gy1, gx0:gx1] * frameM[gy0:gy1, gx0:gx1]
    img = img * (1 - sillM) + wood * 1.2 * sillM
    img = img * (1 - standM) + np.array([0.04, 0.03, 0.03]) * standM
    img = img * (1 - shadeM) + np.array([0.98, 0.72, 0.42]) * shadeM
    img = img * (1 - throwM) + np.array([0.42, 0.05, 0.08]) * (0.45 + 0.8 * lamp2) * fold * throwM
    tw = 0.5 + 0.5 * np.sin(2 * np.pi * sfr * u + sph)
    img[sy, sx] = np.clip(img[sy, sx] + scol * (0.15 + 0.85 * tw[:, None] ** 6) * 0.7, 0, 1)
    img = img * DIM
    sys.stdout.buffer.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
