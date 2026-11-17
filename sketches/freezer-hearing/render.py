"""The Freezer Hearing: stick-figure animatic with anchor headshots, crude drawings and the studio set.

python render.py [--audio DIR] [--test SECONDS] [--out FILE]
"""
from __future__ import annotations

import argparse, json, math, os, random, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

REPO = Path("/home/claude/mac-26-27")
HERE = Path(__file__).resolve().parent
W, H, FPS, SR = 1920, 1080, 12, 48000
FONT = str(REPO / "templates/static/fonts/BarlowCondensed-Bold.ttf")
FONT2 = str(REPO / "templates/static/fonts/Newsreader-SemiBoldItalic.ttf")
CHALK = (246, 240, 228)
INK = (28, 24, 22)
RED = (196, 30, 58)
GOLD = (214, 178, 94)

LINES = json.loads((REPO / "sketches/freezer-hearing/lines.json").read_text())
TAKES = {t["id"]: t for t in LINES["takes"]}

# headshot crop box in the 720x1290 portraits, and the mouth line inside that crop
CROP = (190, 110, 530, 590)
HEADS = {
    "claire": ("miami-oh", 400), "gary": ("bowling-green", 379), "simone": ("buffalo", 339),
    "trevor": ("central-michigan", 357), "marcus": ("akron", 367), "diane": ("eastern-michigan", 401),
    "patty": ("western-michigan", 396), "ray": ("ohio", 343),
}
NAMES = {"claire": "CLAIRE BEAUMONT · MIAMI", "gary": "GARY MERCER · BOWLING GREEN", "simone": "SIMONE BAPTISTE · COMPLIANCE",
         "trevor": "TREVOR HOLLOWAY · WALK-ON", "marcus": "MARCUS VANCE · COMMITTEE", "diane": "DIANE OKAFOR · COMMITTEE",
         "patty": "PATTY GALLAGHER", "ray": "RAY ABERNATHY"}


def font(size, f=FONT):
    return _font(f, int(size))


@lru_cache(None)
def _font(f, size):
    return ImageFont.truetype(f, size)


# ---------------------------------------------------------------- wobbly marker drawing
class Pen:
    def __init__(self, d: ImageDraw.ImageDraw, seed: int, wob: float = 2.5):
        self.d, self.r, self.wob = d, random.Random(seed), wob

    def j(self, p, k=1.0):
        return (p[0] + self.r.uniform(-self.wob, self.wob) * k, p[1] + self.r.uniform(-self.wob, self.wob) * k)

    def line(self, pts, fill=CHALK, width=6, k=1.0):
        out = []
        for a, b in zip(pts, pts[1:]):
            n = max(2, int(math.dist(a, b) / 40))
            for i in range(n):
                t = i / n
                out.append(self.j((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), k))
        out.append(self.j(pts[-1], k))
        self.d.line(out, fill=fill, width=int(width), joint="curve")
        r = width / 2
        for p in (out[0], out[-1]):
            self.d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=fill)

    def poly(self, pts, fill=None, outline=CHALK, width=6):
        jp = [self.j(p) for p in pts]
        if fill:
            self.d.polygon(jp, fill=fill)
        if outline:
            self.line(jp + [jp[0]], fill=outline, width=width, k=0.4)

    def rect(self, x0, y0, x1, y1, **kw):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **kw)

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=CHALK, width=6, n=28):
        pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
        self.poly(pts, fill=fill, outline=outline, width=width)

    def text(self, xy, s, size, fill=CHALK, f=FONT, anchor="mm", rot=0.0):
        if not rot:
            self.d.text(self.j(xy), s, font=font(size, f), fill=fill, anchor=anchor)
            return
        fnt = font(size, f)
        bb = self.d.textbbox((0, 0), s, font=fnt)
        tile = Image.new("RGBA", (bb[2] + 20, bb[3] + 20), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((10, 10), s, font=fnt, fill=fill)
        tile = tile.rotate(rot, expand=True, resample=Image.BICUBIC)
        self.d._image.paste(tile, (int(xy[0] - tile.width / 2), int(xy[1] - tile.height / 2)), tile)


# ---------------------------------------------------------------- headshots with a jaw that drops
@lru_cache(None)
def head_parts(who: str, h: int, shades: bool):
    key, mouth = HEADS[who]
    im = Image.open(REPO / f"anchors/{key}.webp").convert("RGBA").crop(CROP)
    cw, ch = im.size
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).ellipse([6, 4, cw - 6, ch - 4], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(2))
    a = Image.composite(im, Image.new("RGBA", im.size, (0, 0, 0, 0)), mask)
    if shades:
        d = ImageDraw.Draw(a)
        d.polygon([(52, 228), (290, 228), (282, 292), (196, 300), (170, 268), (146, 300), (62, 292)], fill=(14, 14, 16, 255))
        d.line([(80, 244), (130, 238)], fill=(150, 160, 175, 255), width=6)
        d.line([(205, 238), (255, 244)], fill=(150, 160, 175, 255), width=6)
    s = h / ch
    a = a.resize((max(1, int(cw * s)), h), Image.LANCZOS)
    m = int((mouth - 2) * s)
    top, jaw = a.crop((0, 0, a.width, m)), a.crop((0, m, a.width, a.height))
    return top, jaw, m, a


def paste_head(img, who, cx, cy, h, amp=0.0, shades=False, tilt=0.0):
    """cx, cy = center of head; amp 0..1 opens the jaw."""
    top, jaw, m, full = head_parts(who, int(h), shades)
    hw = full.width
    drop = int(min(amp, 1.1) * h * 0.13)
    canvas = Image.new("RGBA", (hw, full.height + drop), (0, 0, 0, 0))
    if drop > 1:
        d = ImageDraw.Draw(canvas)
        mw = hw * 0.26
        d.ellipse([hw / 2 - mw / 2, m - drop * 0.4, hw / 2 + mw / 2, m + drop * 1.4], fill=(52, 16, 18, 255))
    canvas.paste(jaw, (0, m + drop), jaw)
    canvas.paste(top, (0, 0), top)
    if tilt:
        canvas = canvas.rotate(tilt, expand=True, resample=Image.BICUBIC)
    img.paste(canvas, (int(cx - canvas.width / 2), int(cy - h / 2)), canvas)


# ---------------------------------------------------------------- stick figures
def limb(p, ang, ln):
    return (p[0] + ln * math.cos(ang), p[1] + ln * math.sin(ang))


def figure(img, pen, who, x, y, h, pose="stand", amp=0.0, t=0.0, color=CHALK, cut=None, arms=None,
           shades=False, props=(), walk=0.0, face=0.0, tilt=0.0):
    """x = body center, y = feet (stand/sit) or the cut line (behind a desk). h = head height."""
    lw = max(4, h * 0.05)
    torso = h * 1.05
    if pose == "stand":
        hip = (x, y - h * 1.25)
    elif pose == "sit":
        hip = (x, y - h * 0.62)
    else:  # behind desk: hips hidden below the cut line
        hip = (x, y + h * 0.15)
    neck = (hip[0] + face * h * 0.05, hip[1] - torso)
    head_c = (neck[0], neck[1] - h * 0.47)
    # legs
    if pose == "stand":
        sw = math.sin(walk * math.pi * 2) * 0.45 if walk else 0
        for s in (-1, 1):
            a = math.pi / 2 + s * 0.18 + s * sw
            knee = limb(hip, a, h * 0.65)
            foot = limb(knee, math.pi / 2 + s * 0.08 + s * sw * 0.6, h * 0.62)
            pen.line([hip, knee, foot, (foot[0] + s * h * 0.12 + face * h * 0.1, foot[1])], fill=color, width=lw)
    elif pose == "sit":
        for s in (-1, 1):
            knee = (hip[0] + s * h * 0.22 + face * h * 0.4, hip[1] - h * 0.02)
            foot = (knee[0] + s * h * 0.05, y)
            pen.line([hip, knee, foot, (foot[0] + h * 0.1 * (1 if face >= 0 else -1), foot[1])], fill=color, width=lw)
    # singlet for Trevor
    if "singlet" in props:
        sh = h * 0.28
        pen.poly([(neck[0] - sh * 0.55, neck[1] + h * 0.08), (neck[0] + sh * 0.55, neck[1] + h * 0.08),
                  (hip[0] + sh * 0.65, hip[1] + h * 0.1), (hip[0] - sh * 0.65, hip[1] + h * 0.1)],
                 fill=(120, 26, 40), outline=GOLD, width=lw * 0.6)
    # torso
    pts = [neck, hip]
    if cut is not None:
        pts = [neck, (hip[0], min(hip[1], cut))]
    pen.line(pts, fill=color, width=lw)
    # arms: arms = (left shoulder angle, left elbow bend, right shoulder angle, right elbow bend) in degrees, 0 = down
    sh_pt = (neck[0], neck[1] + h * 0.18)
    if arms is None:
        g = amp * 30 * math.sin(t * 7.0)
        arms = (25 + g, 20 + g * 0.5, 25 - g * 0.6, 20)
    hands = []
    for s, (sa, eb) in zip((-1, 1), ((arms[0], arms[1]), (arms[2], arms[3]))):
        a1 = math.pi / 2 + s * math.radians(sa)
        el = limb(sh_pt, a1, h * 0.5)
        a2 = a1 + s * math.radians(eb)
        hd = limb(el, a2, h * 0.48)
        seg = [sh_pt, el, hd]
        if cut is not None and hd[1] > cut:
            hd = (hd[0], cut)
            seg = [sh_pt, el if el[1] < cut else (el[0], cut), hd]
        pen.line(seg, fill=color, width=lw)
        hands.append(hd)
    # props in hands
    if "cane" in props:
        hd = hands[1]
        pen.line([(hd[0], hd[1] - h * 0.1), (hd[0] + h * 0.08, y if pose != "desk" else hd[1] + h)], fill=(150, 98, 52), width=lw * 1.1)
        pen.line([(hd[0] - h * 0.12, hd[1] - h * 0.1), (hd[0], hd[1] - h * 0.1)], fill=(150, 98, 52), width=lw * 1.1)
    if "pen" in props:
        hd = hands[1]
        pen.line([hd, (hd[0] + h * 0.05, hd[1] - h * 0.25)], fill=(30, 60, 160), width=lw * 0.8)
    if "clipboard" in props:
        hd = hands[0]
        pen.rect(hd[0] - h * 0.25, hd[1] - h * 0.35, hd[0] + h * 0.15, hd[1] + h * 0.15, fill=(170, 130, 80), outline=color, width=lw * 0.6)
        pen.rect(hd[0] - h * 0.2, hd[1] - h * 0.28, hd[0] + h * 0.1, hd[1] + h * 0.1, fill=(250, 248, 240), outline=None)
    if "lid" in props:
        hd = hands[0]
        pen.ellipse(hd[0], hd[1] - h * 0.08, h * 0.2, h * 0.07, fill=(248, 244, 236), outline=RED, width=lw * 0.6)
    if "paddle" in props:
        hd = hands[1]
        pen.line([hd, (hd[0] + h * 0.1, hd[1] - h * 0.35)], fill=(222, 190, 140), width=lw * 1.4)
    paste_head(img, who, head_c[0], head_c[1], h, amp=amp, shades=shades, tilt=tilt)
    return {"head": head_c, "hands": hands, "neck": neck}


# ---------------------------------------------------------------- backgrounds
@lru_cache(None)
def photo(name, box):
    im = Image.open(f"/mnt/project-files/sets/{name}.jpg").convert("RGB").crop(box)
    return im


@lru_cache(None)
def bg_main():
    return photo("studio-main", (0, 1250, 1536, 2114)).resize((W, H), Image.LANCZOS)


@lru_cache(None)
def bg_alt():
    return photo("studio-alt", (0, 1050, 1536, 1914)).resize((W, H), Image.LANCZOS)


@lru_cache(None)
def paper(seed=1, tint=(244, 238, 222)):
    rng = np.random.default_rng(seed)
    a = np.ones((H, W, 3), np.float32) * np.array(tint, np.float32)
    a += rng.normal(0, 6, (H, W, 1))
    yy, xx = np.mgrid[0:H, 0:W]
    v = 1 - 0.18 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a *= v[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


BOXES = {"l": (100, 230, 620, 880), "c": (690, 150, 1230, 960), "r": (1300, 230, 1820, 880)}
BOX_SRC = {"l": (0, 1350, 640, 2150), "c": (560, 1000, 1160, 1900), "r": (900, 1350, 1536, 2150)}


@lru_cache(None)
def bg_weave():
    img = Image.new("RGB", (W, H), (31, 26, 23))
    d = ImageDraw.Draw(img)
    for k, b in BOXES.items():
        src = photo("studio-main", BOX_SRC[k]).resize((b[2] - b[0], b[3] - b[1]), Image.LANCZOS)
        img.paste(src, b[:2])
        d.rectangle(b, outline=GOLD if k == "c" else (90, 78, 66), width=4 if k == "c" else 2)
    d.text((100, 70), "MID", font=font(64, FONT2), fill=(240, 232, 218), anchor="ls")
    x = 100 + d.textlength("MID", font=font(64, FONT2))
    d.text((x, 70), "night", font=font(64, FONT2), fill=GOLD, anchor="ls")
    x += d.textlength("night", font=font(64, FONT2))
    d.text((x + 14, 70), "Weave", font=font(64, FONT2), fill=(240, 232, 218), anchor="ls")
    d.text((102, 104), "THE MID-MAJORS TONIGHT  ·  SPECIAL HEARING COVERAGE", font=font(26), fill=(170, 156, 140), anchor="ls")
    d.rectangle([0, H - 14, W, H], fill=(120, 60, 40))
    return img


def tag(img, x, y, text, size=30):
    d = ImageDraw.Draw(img)
    w = d.textlength(text, font=font(size))
    d.rectangle([x, y, x + w + 28, y + size + 16], fill=(18, 16, 14))
    d.rectangle([x, y, x + 6, y + size + 16], fill=RED)
    d.text((x + 16, y + 8), text, font=font(size), fill=(240, 234, 222))


# ---------------------------------------------------------------- crude props on top of the set
def fluorescents(pen, flick):
    for x in (420, 960, 1500):
        pen.line([(x - 10, 0), (x - 10, 46)], width=3)
        pen.line([(x + 170, 0), (x + 170, 46)], width=3)
        c = (250, 252, 230) if not flick or x != 960 else (120, 120, 110)
        pen.rect(x - 60, 46, x + 240, 74, fill=c, outline=CHALK, width=4)


def sign(pen):
    pen.rect(1390, 110, 1740, 230, fill=(250, 246, 236), outline=INK, width=4)
    pen.text((1565, 146), "COMPLIANCE HEARING", 40, fill=INK)
    pen.text((1565, 194), "(the studio was the only room open)", 26, fill=(90, 80, 70))
    pen.line([(1400, 106), (1440, 120)], fill=(230, 220, 180), width=10)
    pen.line([(1730, 106), (1690, 120)], fill=(230, 220, 180), width=10)


def pint(pen, x, y, s=1.0, empty=True, color=CHALK, label=True):
    pen.poly([(x - 60 * s, y - 90 * s), (x + 60 * s, y - 90 * s), (x + 48 * s, y + 40 * s), (x - 48 * s, y + 40 * s)],
             fill=(250, 248, 244), outline=INK, width=5 * s)
    pen.ellipse(x, y - 90 * s, 60 * s, 14 * s, fill=(236, 230, 222), outline=INK, width=4 * s)
    if label:
        pen.rect(x - 52 * s, y - 40 * s, x + 50 * s, y - 14 * s, fill=RED, outline=None)
        pen.text((x, y - 27 * s), "CLAIRE", 22 * s, fill=(255, 255, 255))


def whiteboard(pen, x, y, ang=0.0):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))

    def r(px, py):
        return (x + px * c - py * s, y + px * s + py * c)
    pen.poly([r(-140, -260), r(140, -260), r(140, -40), r(-140, -40)], fill=(250, 250, 250), outline=(150, 150, 160), width=8)
    pen.line([r(-100, -200), r(60, -210)], fill=(40, 80, 200), width=5)
    pen.line([r(-100, -160), r(20, -150)], fill=(40, 80, 200), width=5)
    pen.text(r(0, -105), "SYNERGY?", 34, fill=(200, 40, 40), rot=-ang)
    pen.line([r(-110, -40), r(-110, 60)], fill=(150, 150, 160), width=7)
    pen.line([r(110, -40), r(110, 60)], fill=(150, 150, 160), width=7)
    for wx in (-110, 110):
        p = r(wx, 70)
        pen.ellipse(p[0], p[1], 12, 12, fill=(40, 40, 40), outline=None)


def folding_chair(pen, x, y, h):
    pen.line([(x - h * 0.3, y - h * 0.6), (x + h * 0.32, y - h * 0.6)], fill=(170, 170, 176), width=h * 0.05)
    pen.line([(x - h * 0.3, y), (x + h * 0.25, y - h * 0.6)], fill=(170, 170, 176), width=h * 0.035)
    pen.line([(x + h * 0.3, y), (x - h * 0.25, y - h * 0.6)], fill=(170, 170, 176), width=h * 0.035)


def glass_door(pen, x0, y0, x1, y1, open_frac=0.0):
    w = (x1 - x0) * (1 - open_frac * 0.85)
    pen.rect(x0, y0, x0 + w, y1, fill=None, outline=(200, 230, 245), width=8)
    pen.line([(x0 + w * 0.2, y0 + 80), (x0 + w * 0.45, y0 + 30)], fill=(220, 240, 250), width=5)
    pen.line([(x0 + w * 0.25, y0 + 150), (x0 + w * 0.6, y0 + 70)], fill=(220, 240, 250), width=5)
    pen.line([(x0 + w * 0.85, (y0 + y1) / 2 - 40), (x0 + w * 0.85, (y0 + y1) / 2 + 40)], fill=(200, 200, 200), width=10)
    pen.text((x0 + w / 2, y0 + 220), "PULL", 40, fill=(200, 230, 245))


# ---------------------------------------------------------------- timeline
def word_dur(text):
    return max(1.0, len(text.split()) / 2.6)


def load_take(audio_dir, tid):
    p = Path(audio_dir) / f"{tid}.wav" if audio_dir else None
    if p and p.exists():
        y = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                           capture_output=True, check=True).stdout
        a = np.frombuffer(y, np.float32).copy()
        nz = np.where(np.abs(a) > 0.01)[0]
        if len(nz):
            a = a[max(0, nz[0] - 1200): nz[-1] + 2400]
        return a
    return np.zeros(int(word_dur(TAKES[tid]["text"]) * SR), np.float32)


def envelope(a):
    n = int(math.ceil(len(a) / SR * FPS))
    hop = SR // FPS
    e = np.array([np.sqrt(np.mean(a[i * hop:(i + 1) * hop] ** 2)) if len(a[i * hop:(i + 1) * hop]) else 0 for i in range(n)])
    if e.max() > 0:
        e = np.clip(e / (np.percentile(e, 90) + 1e-6), 0, 1.2)
    return e


def build(audio_dir):
    """Returns (events, takes) where each event has start, dur, scene, speaker/take and extras."""
    takes = {tid: load_take(audio_dir, tid) for tid in TAKES}
    ev, t = [], 0.0

    def add(scene, dur=None, take=None, gap=0.35, **kw):
        nonlocal t
        if take:
            dur = len(takes[take]) / SR
        ev.append(dict(start=t, dur=dur, scene=scene, take=take, who=TAKES[take]["who"] if take else None, **kw))
        t += dur + gap
        return ev[-1]

    add("cover", 1.6, gap=0, sfx=[(0, "sting")])
    add("claire_open", take="01_claire", gap=0.6)
    add("hearing", 2.2, gap=0, sfx=[(0.1, "taps")], shot="establish")
    add("hearing", take="02_simone", shot="simone", gap=0.3)
    add("hearing", 2.0, shot="claire_lid", gap=0)
    add("weave", take="03_trevor", gap=0.05, sfx=[(0, "whoosh")])
    add("weave", take="04_gary", gap=0.6)
    for tid in ("05_simone", "06_gary", "07_simone", "08_gary", "09_diane", "10_simone"):
        add("weave", take=tid, gap=0.4)
    add("hearing", 3.0, shot="gary_rises", gap=0, sfx=[(0.0, "squeak"), (0.5, "taps"), (1.7, "clang")])
    for tid, shot in (("11_gary", "gary_mid"), ("12_simone", "simone"), ("13_trevor", "front"), ("14_gary", "front")):
        add("hearing", take=tid, shot=shot, gap=0.4)
    add("hearing", take="15_gary", shot="pace", gap=0.4)
    add("hearing", take="16_simone", shot="simone", gap=0.25)
    add("hearing", take="17_gary", shot="pace", gap=0.2)
    add("hearing", 2.2, shot="stapler", gap=0, sfx=[(0.1, "slam"), (0.35, "clatter")])
    add("speech", take="18_gary", gap=0.2, sfx=[("end", "gasp")])
    add("hearing", 1.6, shot="gasp", gap=0)
    add("hearing", take="19_simone", shot="simone", gap=0.35)
    add("flashback", take="20_gary", gap=0.6, sfx=[(0, "whoosh")])
    add("hearing", take="21_claire", shot="claire_close", gap=0.3)
    add("weave_clap", 4.6, gap=0, sfx=[(0.3, "tile"), (1.6, "clap1"), (2.5, "applause")])
    add("weave_clap", take="22_patty", gap=0.2)
    add("hearing", take="23_marcus", shot="marcus", gap=0.2)
    add("hearing", 2.0, shot="salute", gap=0)
    add("exit", take="24_gary", gap=0, sfx=[(0, "whoosh")])
    add("exit", 3.4, shot="bonk", gap=0, sfx=[(0.75, "thud"), (2.1, "door")])
    add("door", take="25_trevor", gap=0.2, sfx=[("end", "scratch")])
    add("button", take="26_claire", gap=0.6, sfx=[(0, "whoosh")])
    add("endcard", 3.0, gap=0, sfx=[(0, "sting")])
    return ev, takes, t


# ---------------------------------------------------------------- SFX (synthesized, original)
def sfx(name):
    rng = np.random.default_rng(abs(hash(name)) % 2**32)
    def tt(d): return np.arange(int(d * SR)) / SR
    if name == "sting":
        out = np.zeros(int(1.6 * SR))
        for i, (f, st) in enumerate(((146.8, 0), (146.8, 0.18), (174.6, 0.36), (220, 0.62))):
            x = tt(0.5 if i < 3 else 0.9)
            s = sum(np.sin(2 * np.pi * f * k * x) / k for k in range(1, 7)) * np.exp(-x * 4) * 0.25
            o = int(st * SR); out[o:o + len(s)] += s
        return out
    if name == "whoosh":
        x = tt(0.45); n = rng.normal(0, 1, len(x))
        k = np.convolve(n, np.ones(40) / 40, "same")
        return k * np.sin(np.pi * x / 0.45) ** 2 * 0.5
    if name == "taps":
        out = np.zeros(int(1.2 * SR))
        for i in range(4):
            x = tt(0.06); s = np.sin(2 * np.pi * 1800 * x) * np.exp(-x * 120) * 0.3
            o = int(i * 0.28 * SR); out[o:o + len(s)] += s
        return out
    if name == "squeak":
        x = tt(0.5); f = 900 + 500 * np.sin(np.pi * x / 0.5)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * x / 0.5) * 0.12
    if name == "clang":
        x = tt(1.4)
        return sum(np.sin(2 * np.pi * f * x) * a for f, a in ((523, .3), (1187, .25), (1761, .2), (2690, .15))) * np.exp(-x * 3.5) \
            + rng.normal(0, 1, len(x)) * np.exp(-x * 40) * 0.4
    if name in ("thud", "slam"):
        x = tt(0.5); f = 110 * np.exp(-x * 4)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.8 + rng.normal(0, 1, len(x)) * 0.3 * np.exp(-x * 30)) * np.exp(-x * 9)
    if name == "clatter":
        out = np.zeros(int(0.8 * SR))
        for i in range(5):
            x = tt(0.08); s = rng.normal(0, 1, len(x)) * np.exp(-x * 60) * 0.35
            o = int((0.05 + i * 0.13 + rng.uniform(0, .04)) * SR); out[o:o + len(s)] += s
        return out
    if name == "gasp":
        out = np.zeros(int(1.2 * SR))
        for i in range(9):
            x = tt(0.5); n = np.convolve(rng.normal(0, 1, len(x)), np.ones(12) / 12, "same")
            s = n * np.sin(np.pi * x / 0.5) ** 3 * 0.18
            o = int(rng.uniform(0, .35) * SR); out[o:o + len(s)] += s
        return out
    if name == "tile":
        out = np.zeros(int(0.9 * SR))
        for i in range(10):
            x = tt(0.04); s = np.sin(2 * np.pi * 300 * x) * np.exp(-x * 90) * 0.15 + rng.normal(0, .05, len(x))
            o = int(i * 0.07 * SR); out[o:o + len(s)] += s * np.exp(-i / 5)
        return out
    if name in ("clap1", "applause"):
        d = 0.9 if name == "clap1" else 10.0
        out = np.zeros(int(d * SR))
        n = 2 if name == "clap1" else 900
        for i in range(n):
            x = tt(0.03); s = np.convolve(rng.normal(0, 1, len(x)), [1, -1], "same") * np.exp(-x * 160)
            o = int((i * 0.5 if name == "clap1" else rng.uniform(0, d - 0.05) ** 1.0) * SR)
            if name == "applause":
                s *= min(1, (o / SR) / 2.5) * 0.22
            else:
                s *= 0.4
            out[o:o + len(s)] += s
        return out
    if name == "scratch":
        x = tt(0.5); f = 600 + 1800 * np.abs(np.sin(2 * np.pi * x * 3))
        return np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.08 * (1 - x / 0.5) + rng.normal(0, .05, len(x))
    if name == "door":
        x = tt(0.7); f = 300 + 200 * x
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.06 * np.sin(np.pi * x / 0.7)
    return np.zeros(10)


def mix(ev, takes, total):
    out = np.zeros(int((total + 1) * SR), np.float32)
    def put(a, t, g=1.0):
        o = int(t * SR); a = a[: len(out) - o]; out[o:o + len(a)] += a * g
    # room tone under the hearing
    hum_t = np.arange(len(out)) / SR
    hum = (np.sin(2 * np.pi * 120 * hum_t) * 0.006 + np.sin(2 * np.pi * 240 * hum_t) * 0.003).astype(np.float32)
    gate = np.zeros(len(out), np.float32)
    applause_end = None
    for e in ev:
        if e["scene"] in ("hearing", "weave", "speech", "weave_clap"):
            gate[int(e["start"] * SR): int((e["start"] + e["dur"] + 0.4) * SR)] = 1
        if e["take"]:
            put(takes[e["take"]], e["start"], 1.0)
        for off, name in e.get("sfx", []):
            at = e["start"] + (e["dur"] if off == "end" else off)
            s = sfx(name).astype(np.float32)
            if name == "applause":
                applause_at = at
            if name == "scratch":
                applause_end = at
            put(s, at, 0.9)
    # applause bed runs from the clap until the record scratch
    if applause_end:
        a0 = [e for e in ev if e["scene"] == "weave_clap"][0]["start"] + 2.5
        bed = np.concatenate([sfx("applause")] * 4).astype(np.float32)
        n = int((applause_end - a0) * SR)
        bed = bed[:n]
        fade = np.ones(n, np.float32); fade[:int(SR * 2)] = np.linspace(0, 1, int(SR * 2))
        idx = np.arange(n) / SR
        duck = np.ones(n, np.float32)
        for e in ev:
            if e["take"] and e["start"] >= a0:
                s0, s1 = int((e["start"] - a0) * SR), int((e["start"] + e["dur"] - a0) * SR)
                duck[max(0, s0):max(0, s1)] = 0.35
        put(bed * fade * duck, a0, 0.8)
    out += hum * gate
    peak = np.max(np.abs(out)) or 1
    return (out / peak * 0.89).astype(np.float32)


# ---------------------------------------------------------------- scenes
def caption(img, e, lt):
    if not e["take"]:
        return
    text = TAKES[e["take"]]["text"].replace("...", "…")
    words = text.split()
    chunks, cur = [], []
    for w_ in words:
        cur.append(w_)
        if len(" ".join(cur)) > 44 or w_.endswith((".", "?", "!", "—", "…")) and len(" ".join(cur)) > 18:
            chunks.append(" ".join(cur)); cur = []
    if cur:
        chunks.append(" ".join(cur))
    tot = sum(len(c) for c in chunks)
    frac, acc = lt / max(e["dur"], .01), 0
    for c in chunks:
        acc += len(c) / tot
        if frac <= acc + 1e-6:
            break
    d = ImageDraw.Draw(img)
    f = font(46)
    w = d.textlength(c, font=f)
    x, y = W / 2, H - 70
    d.rectangle([x - w / 2 - 22, y - 34, x + w / 2 + 22, y + 30], fill=(14, 12, 11))
    d.text((x, y), c, font=f, fill=(250, 244, 230), anchor="mm")


def amp_at(e, envs, lt):
    if not e["take"]:
        return 0.0
    en = envs[e["take"]]
    i = int(lt * FPS)
    return float(en[i]) if i < len(en) else 0.0


def camera(img, cx, cy, z, shake=0.0, seed=0):
    if z <= 1.001 and not shake:
        return img
    r = random.Random(seed)
    w, h = W / z, H / z
    x0 = min(max(cx - w / 2 + r.uniform(-shake, shake), 0), W - w)
    y0 = min(max(cy - h / 2 + r.uniform(-shake, shake), 0), H - h)
    return img.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.LANCZOS)


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def hearing_frame(fi, gt, e, lt, envs, state):
    img = bg_main().copy()
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.blend(img, dark, 0.15)
    d = ImageDraw.Draw(img)
    pen = Pen(d, fi // 2)
    shot = e.get("shot")
    sp = e["who"]
    a = amp_at(e, envs, lt)
    fluorescents(pen, flick=(fi % 37 < 2))
    sign(pen)
    # exhibit A on the desk
    pint(pen, 1125, 412, s=0.45, label=True)
    pen.text((1125, 450), "EXHIBIT A", 20)
    # whiteboard: center until Gary hits it, then knocked aside
    wb_x, wb_ang = 1000, 0
    if state["wb_hit"] is not None:
        k = ease((gt - state["wb_hit"]) / 0.4)
        wb_x, wb_ang = lerp(1000, 1130, k), lerp(0, 14, k)
    elif shot == "gary_rises" and lt > 1.7:
        wb_x, wb_ang = lerp(1000, 1130, ease((lt - 1.7) / 0.4)), lerp(0, 14, ease((lt - 1.7) / 0.4))
    if shot not in ("simone", "marcus"):
        whiteboard(pen, wb_x, 900, wb_ang)
    # committee behind the desk (cut line = desk top)
    cut = 440
    simone_pen_down = shot in ("salute", "marcus") or state.get("pen_down")
    for who, x, props in (("marcus", 780, ("clipboard",)), ("simone", 1010, ("pen",)), ("diane", 1240, ())):
        arms = None
        if who == "simone" and simone_pen_down:
            arms = (25, 20, 15, 60)
        if who == "marcus" and shot == "stapler" and lt > 0.5:
            arms = (25, 20, -60 + 40 * ease((lt - 0.5) / 0.5), 30)
        if shot in ("salute", "marcus") and who == "marcus":
            arms = (25, 20, 70 + 20 * math.sin(gt * 18), 80)
        figure(img, pen, who, x, cut, 150, pose="desk", amp=a if sp == who else 0, t=gt, cut=cut + 4, props=props, arms=arms)
    if shot == "stapler":
        k = ease(lt / 0.5)
        sx, sy = lerp(900, 830, k), lerp(425, 360 + 60 * (1 - math.sin(math.pi * k)), k) if lt < 1.0 else 330
        pen.rect(sx - 30, sy - 10, sx + 30, sy + 10, fill=(60, 60, 64), outline=CHALK, width=3)
    # back row
    applause = state["applause"]
    for who, x in (("patty", 1600), ("ray", 1750)):
        arms = None
        if applause:
            c = math.sin(gt * 16 + (0 if who == "patty" else 1))
            arms = (80 + 8 * c, 95 + 10 * c, 80 - 8 * c, 95 - 10 * c)
        nod = 6 * math.sin(gt * 9) if (who == "ray" and shot in ("speech_back", "gasp")) else 0
        figure(img, pen, who, x, 660, 105, pose="stand", t=gt, arms=arms, tilt=nod)
    fg = shot not in ("simone", "marcus")
    # Claire, front left, holding the lid
    c_arms = (10, 150, 20, 20)
    if shot == "gasp" or e["take"] == "21_claire":
        c_arms = (10, 150, 40, 130)
    if applause:
        c_arms = (80 + 8 * math.sin(gt * 16), 95, 80, 95)
    if fg: figure(img, pen, "claire", 250, 1050, 190, pose="sit", amp=a if sp == "claire" else 0, t=gt, props=("lid",), arms=c_arms, face=0.6)
    if fg: folding_chair(pen, 250, 1052, 190)
    # Gary + Trevor
    gx, gpose, gwalk, gface = 640, "sit", 0.0, 0.5
    if shot == "gary_rises":
        if lt > 0.4:
            gpose = "stand"
            k = (lt - 0.6) / 2.2
            gx = lerp(640, 900, ease(k))
            gwalk = lt * 1.6 if 0.6 < lt < 2.8 else 0
            if 1.7 < lt < 2.0:
                gx += 30 * math.sin((lt - 1.7) * 60)
    elif state["gary_up"]:
        gpose = "stand"
        gx = 900
        if shot == "pace":
            gx = 900 + 240 * math.sin(lt * 0.7)
            gwalk = lt * 1.4
            gface = math.cos(lt * 0.7)
    g_arms = None
    if shot == "salute":
        g_arms = (25, 20, 150, 60)
    if gpose == "sit" and fg:
        folding_chair(pen, gx, 1052, 210)
    if fg: figure(img, pen, "gary", gx, 1050, 210, pose=gpose, amp=a if sp == "gary" else 0, t=gt, shades=True, props=("cane",),
           walk=gwalk, face=gface, arms=g_arms)
    if fg: folding_chair(pen, 1430, 1052, 210)
    t_arms = (15, 25, 15, 25)
    if fg: figure(img, pen, "trevor", 1430, 1050, 200, pose="sit", amp=a if sp == "trevor" else 0, t=gt, props=("singlet",),
           arms=t_arms if sp != "trevor" else None, face=-0.4)
    if shot == "establish":
        tag(img, 70, 120, "MEANWHILE, IN OUR STUDIO", 34)
    # cameras
    z, cx, cy, sh = 1.0, W / 2, H / 2, 0
    if shot == "simone":
        z, cx, cy = 1.7, 1010, 360
    elif shot == "claire_lid" or shot == "claire_close":
        z, cx, cy = 2.1, 300, 740
    elif shot == "front":
        z, cx, cy = 1.35, 960, 720
        if e["take"] == "14_gary" and lt < 0.6:
            sh = 18
    elif shot == "gary_mid":
        z, cx, cy = 1.45, 900, 560
    elif shot == "pace":
        z, cx, cy = lerp(1.15, 1.45, lt / max(e["dur"], 1)), 900, 560
    elif shot == "marcus":
        z, cx, cy = 1.9, 780, 360
    elif shot == "gary_rises" and 1.7 < lt < 2.1:
        sh = 22
    elif shot == "stapler" and lt < 0.4:
        sh = 16
    elif shot == "gasp":
        z, cx, cy = 1.3, 700, 650
    img = camera(img, cx, cy, z, sh, fi)
    if shot in ("simone", "front", "pace", "gary_mid", "marcus", "claire_close") and sp:
        tag(img, 70, H - 190, NAMES[sp], 30)
    return img


def weave_frame(fi, gt, e, lt, envs, state, clap=False):
    img = bg_weave().copy()
    d = ImageDraw.Draw(img)
    pen = Pen(d, fi // 2)
    sp = e["who"]
    a = amp_at(e, envs, lt)
    cast = {"l": "gary", "c": "simone", "r": "trevor"}
    if e["take"] == "09_diane":
        cast["r"] = "diane"
    if clap:
        cast = {"l": "patty", "c": "diane", "r": "ray"}
    for k, who in cast.items():
        b = BOXES[k]
        tile = img.crop(b)
        td = ImageDraw.Draw(tile)
        tp = Pen(td, fi // 2 + hash(k) % 97)
        bw, bh = b[2] - b[0], b[3] - b[1]
        hh = int(bh * 0.42)
        arms = None
        if clap and who in ("patty", "ray"):
            on = (who == "patty" and (e["take"] or lt > 1.6)) or (who == "ray" and (e["take"] or lt > 2.5))
            if on:
                c = math.sin(gt * 16 + (0 if who == "patty" else 1.3))
                arms = (80 + 8 * c, 95 + 10 * c, 80 - 8 * c, 95 - 10 * c)
        props = ("cane",) if who == "gary" else ("singlet",) if who == "trevor" else ("pen",) if who == "simone" else ()
        figure(tile, tp, who, bw / 2, bh - 10, hh, pose="desk", amp=a if sp == who else 0, t=gt, cut=bh,
               shades=(who == "gary"), props=props, arms=arms)
        img.paste(tile, b[:2])
        name = NAMES[who].split(" · ")[0]
        tag(img, b[0] + 10, b[3] - 62, name, 26)
        if sp == who:
            d.rectangle([b[0] - 6, b[1] - 6, b[2] + 6, b[3] + 6], outline=RED, width=5)
    if clap and lt > 0.3 and lt < 1.2 and not e["take"]:
        tp = Pen(d, fi)
        tp.text((W / 2, 1010), "*ceiling tile rattles*", 34, fill=(200, 190, 175))
    if clap and not e["take"] and lt > 3.4:
        Pen(d, fi).text((960, 1010), "(Diane is not clapping.)", 34, fill=(200, 190, 175))
    return img


def paper_scene(fi, gt, e, lt, envs, kind):
    img = paper(3 if kind != "cctv" else 4).copy()
    d = ImageDraw.Draw(img)
    pen = Pen(d, fi // 2, wob=3.5)
    a = amp_at(e, envs, lt)
    frac = lt / max(e["dur"], .01)
    if kind == "cover":
        pint(pen, 960, 520, s=2.4)
        pen.line([(700, 650), (1220, 650)], fill=INK, width=6)
        pen.text((960, 160), "THE FREEZER HEARING", 110, fill=INK)
        pen.text((960, 830), "A HOCKING MIAMI EXCLUSIVE", 64, fill=RED)
        return img
    if kind == "endcard":
        pen.text((960, 380), "THE FREEZER HEARING", 110, fill=INK)
        pen.text((960, 500), "A Hocking Miami Exclusive", 60, fill=RED, f=FONT2)
        pen.text((960, 640), "hardwoodbricks.com", 54, fill=INK)
        pen.text((960, 900), "A sketch. Every character is a fictional AI anchor. No real Miami staff, players or freezers were harmed.", 28, fill=(90, 80, 70))
        return img
    if kind == "pint":
        pint(pen, 960, 600, s=3.0)
        for x, y, r in ((560, 380, -12), (1360, 420, 10)):
            pen.text((x, y), "MY NAME. THREE SIDES.", 44, fill=RED, rot=r)
        pen.text((960, 940), "Exhibit A (artist's rendering)", 40, fill=INK)
        return img
    if kind == "cctv":
        g = img.convert("L").convert("RGB")
        d = ImageDraw.Draw(g)
        pen = Pen(d, fi // 2, wob=3.5)
        pen.rect(1100, 260, 1460, 900, fill=(225, 225, 225), outline=INK, width=8)
        pen.line([(1130, 520), (1430, 520)], fill=INK, width=6)
        pen.line([(1140, 400), (1140, 470)], fill=INK, width=10)
        pen.text((1280, 220), "MEDIA ROOM FREEZER", 40, fill=INK)
        tx = 620 + 40 * math.sin(lt * 2)
        figure(g, pen, "trevor", tx, 900, 170, pose="stand", t=gt, color=INK, props=("singlet",), face=0.6 * math.sin(lt * 3),
               arms=(20, 30, 20, 30))
        for y in range(0, H, 6):
            d.line([(0, y), (W, y)], fill=(150, 150, 150), width=1)
        d.text((60, 60), "ARENA CAM 3   7:12:0%d PM" % (int(lt) % 10), font=font(48), fill=(20, 20, 20))
        d.ellipse([W - 120, 60, W - 80, 100], fill=(200, 20, 20) if fi % 12 < 6 else (120, 120, 120))
        return g
    if kind == "speech":
        cards = [("A grown point guard crying over a flat ball", "pg"), ("An AD hiding in a mop closet", "ad"),
                 ("The bus leaving Buffalo without the radio crew. Twice.", "bus")]
        tx = TAKES[e["take"]]["text"]
        b1, b2 = tx.index("hold air.") / len(tx), tx.index("coaching search.") / len(tx) + 0.03
        i = 0 if frac < b1 + 0.02 else 1 if frac < b2 else 2
        cap, k = cards[i]
        pen.text((960, 110), cap, 58, fill=INK)
        if k == "pg":
            figure(img, pen, "gary", 560, 920, 0 or 1, pose="stand") if False else None
            pen.ellipse(1150, 820, 110, 60, fill=(220, 120, 50), outline=INK)
            pen.text((1150, 820), "pfff", 40, fill=INK)
            # stick point guard, ink, generic round head
            hx = 760
            pen.ellipse(hx, 420, 70, 80, fill=(250, 246, 236), outline=INK)
            for dx in (-25, 25):
                pen.line([(hx + dx, 410), (hx + dx, 440 + 30 * ((fi % 6) / 6))], fill=(60, 120, 220), width=6)
            pen.line([(hx, 500), (hx, 720)], fill=INK)
            pen.line([(hx, 560), (hx - 80, 640)], fill=INK); pen.line([(hx, 560), (hx + 90, 620)], fill=INK)
            pen.line([(hx, 720), (hx - 60, 900)], fill=INK); pen.line([(hx, 720), (hx + 60, 900)], fill=INK)
            pen.text((hx, 340), "23", 40, fill=RED)
        elif k == "ad":
            pen.rect(700, 250, 1220, 950, fill=(205, 180, 140), outline=INK, width=8)
            pen.text((960, 310), "MOP CLOSET", 48, fill=INK)
            pen.ellipse(1150, 620, 14, 14, fill=INK, outline=None)
            peek = 40 * math.sin(lt * 3)
            pen.ellipse(760 + peek, 600, 50, 60, fill=(250, 246, 236), outline=INK)
            pen.text((760 + peek, 600), "AD", 32, fill=INK)
            pen.line([(980, 950), (1020, 500)], fill=(150, 98, 52), width=10)
        else:
            bx = 300 + (frac - b2) * e["dur"] * 260
            pen.rect(bx, 500, bx + 620, 820, fill=(240, 190, 40), outline=INK, width=8)
            for wx in (bx + 60, bx + 200, bx + 340, bx + 480):
                pen.rect(wx, 540, wx + 100, 640, fill=(200, 230, 245), outline=INK, width=4)
            for wx in (bx + 120, bx + 500):
                pen.ellipse(wx, 830, 50, 50, fill=(40, 40, 40), outline=INK)
            pen.text((bx + 310, 730), "MAC TEAM BUS", 44, fill=INK)
            for i_, x in enumerate((180, 300)):
                pen.ellipse(x, 640, 36, 40, fill=(250, 246, 236), outline=INK)
                pen.line([(x, 680), (x, 820)], fill=INK); pen.line([(x, 720), (x + 40 * (1 if fi % 4 < 2 else -1), 660)], fill=INK)
                pen.line([(x, 820), (x - 30, 920)], fill=INK); pen.line([(x, 820), (x + 30, 920)], fill=INK)
            pen.text((240, 560), "RADIO CREW", 30, fill=RED)
            pen.text((240, 980), "(left in Buffalo)", 30, fill=INK)
        return img
    if kind == "flashback":
        pen.text((960, 70), "THE CONFESSION (dramatization)", 44, fill=INK)
        if frac < 0.22:  # behind the tuba
            x = -200 + frac / 0.22 * 1500
            for i_, bx in enumerate((x, x - 260, x - 520)):
                pen.ellipse(bx, 520, 40, 46, fill=(250, 246, 236), outline=INK)
                pen.line([(bx, 566), (bx, 760)], fill=INK)
                pen.line([(bx, 760), (bx - 40 + 30 * math.sin(gt * 9 + i_), 920)], fill=INK)
                pen.line([(bx, 760), (bx + 40 - 30 * math.sin(gt * 9 + i_), 920)], fill=INK)
            pen.ellipse(x + 40, 520, 120, 120, fill=(230, 190, 60), outline=INK, width=8)
            pen.line([(x + 10, 600), (x + 30, 760)], fill=(200, 160, 40), width=24)
            pen.text((x + 40, 380), "TUBA", 40, fill=INK)
            figure(img, pen, "gary", x - 120, 920, 150, pose="stand", t=gt, color=INK, shades=True, walk=gt * 1.6, face=1)
            pen.text((x - 120, 360), "(nobody stops a tuba)", 34, fill=RED)
        elif frac < 0.72:
            pen.rect(1150, 230, 1520, 930, fill=(230, 230, 232), outline=INK, width=8)
            ang = min(1, (frac - 0.22) / 0.1)
            pen.poly([(1150, 230), (1150 - 260 * ang, 260), (1150 - 260 * ang, 900), (1150, 930)], fill=(205, 205, 210), outline=INK)
            pen.text((1335, 200), "MEDIA ROOM", 40, fill=INK)
            pint(pen, 1330, 470, s=0.9, color=INK)
            pen.rect(1250, 420, 1420, 440, fill=RED, outline=None)
            hold = ("paddle",) if frac > 0.45 else ()
            figure(img, pen, "gary", 780, 930, 170, pose="stand", amp=a, t=gt, color=INK, shades=True, props=hold, face=1)
            if frac > 0.45:
                pen.text((560, 330), "corn dog paddle", 40, fill=RED, rot=8)
        else:
            figure(img, pen, "gary", 900, 930, 220, pose="stand", amp=a, t=gt, color=INK, shades=True, arms=(20, 20, 120, 110))
            pen.ellipse(1040, 380, 70, 24, fill=(248, 244, 236), outline=INK)
            if frac > 0.88:
                pen.poly([(990, 420), (1010, 470), (1030, 420)], fill=(220, 90, 110), outline=INK, width=4)
                pen.text((1250, 300), "*lick*", 60, fill=RED, rot=-10)
        return img
    return img


def claire_desk(fi, gt, e, lt, envs, look):
    a = amp_at(e, envs, lt)
    if look == "main":
        img = bg_main().copy()
        d = ImageDraw.Draw(img)
        pen = Pen(d, fi // 2)
        figure(img, pen, "claire", 1010, 440, 190, pose="desk", amp=a, t=gt, cut=444, props=("lid",), arms=(10, 150, 25, 30))
        img = camera(img, 1010, 420, 1.55)
        frac = lt / max(e["dur"], .01)
        if 0.40 < frac < 0.74:
            ins = paper_scene(fi, gt, e, lt, envs, "pint").resize((760, 428))
            img.paste(ins, (1100, 100))
            ImageDraw.Draw(img).rectangle([1100, 100, 1860, 528], outline=CHALK, width=6)
        tag(img, 70, H - 190, "CLAIRE BEAUMONT · MIAMI DESK", 30)
        if lt < 4:
            tag(img, 70, 80, "A HOCKING MIAMI EXCLUSIVE", 36)
        return img
    img = bg_alt().copy()
    d = ImageDraw.Draw(img)
    pen = Pen(d, fi // 2)
    figure(img, pen, "claire", 1430, 520, 200, pose="desk", amp=a, t=gt, cut=530, props=("lid",), arms=(10, 150, 25, 30))
    img = camera(img, 1300, 420, 1.35)
    tag(img, 70, H - 190, "CLAIRE BEAUMONT · MIAMI DESK", 30)
    return img


def exit_frame(fi, gt, e, lt, envs, state, kind):
    img = bg_alt().copy()
    d = ImageDraw.Draw(img)
    pen = Pen(d, fi // 2)
    a = amp_at(e, envs, lt)
    door = (1560, 140, 1840, 1000)
    open_f = 0.0
    gx, gwalk, sh = 300, 0, 0
    tx, twalk, tvis = 120, 0, False
    if kind == "talk":
        gx = 340 + lt * 60
        gwalk = lt * 1.5
    elif kind == "bonk":
        gx = lerp(340 + e.get("prev", 0), 1560 - 60, ease(lt / 0.75))
        gwalk = lt * 1.8 if lt < 0.75 else 0
        if 0.75 < lt < 1.1:
            gx = 1500 - 80 * math.sin((lt - 0.75) / 0.35 * math.pi)
            sh = 20
        if lt > 1.1:
            gx = 1470
        tvis = lt > 1.2
        tx = lerp(300, 1600, ease((lt - 1.2) / 0.9))
        twalk = lt * 1.6
        if lt > 2.1:
            open_f = ease((lt - 2.1) / 0.4)
        if lt > 2.5:
            gx = lerp(1470, 2100, ease((lt - 2.5) / 0.9))
            tx = lerp(1600, 2150, ease((lt - 2.5) / 0.9))
    glass_door(pen, *door, open_frac=open_f)
    stars = kind == "bonk" and 0.8 < lt < 2.3
    figure(img, pen, "gary", gx, 1040, 190, pose="stand", amp=a, t=gt, shades=True, props=("cane",), walk=gwalk, face=1,
           tilt=(-8 if stars else 0))
    if stars:
        for i in range(4):
            ang = gt * 6 + i * math.pi / 2
            pen.text((gx + 120 * math.cos(ang), 300 + 30 * math.sin(ang)), "*", 70, fill=GOLD)
    if tvis:
        figure(img, pen, "trevor", tx, 1040, 180, pose="stand", t=gt, props=("singlet",), walk=twalk, face=1)
    if kind == "door":
        figure(img, pen, "trevor", 1700, 1040, 240, pose="stand", amp=a, t=gt, props=("singlet",), arms=(10, 10, 10, 10))
        img = camera(img, 1500, 600, 1.6)
        tag(img, 70, H - 190, "TREVOR HOLLOWAY · WALK-ON", 30)
    return camera(img, W / 2, H / 2, 1.0, sh, fi)


def frame(args):
    fi, ev, envs, out_dir = args
    gt = fi / FPS
    e = ev[0]
    for x in ev:
        if x["start"] <= gt:
            e = x
    lt = gt - e["start"]
    state = {
        "wb_hit": next((x["start"] + 1.7 for x in ev if x.get("shot") == "gary_rises"), None),
        "gary_up": gt >= next((x["start"] + 0.5 for x in ev if x.get("shot") == "gary_rises"), 1e9),
        "applause": next((x["start"] + 2.5 for x in ev if x["scene"] == "weave_clap"), 1e9) <= gt,
        "pen_down": gt >= next((x["start"] for x in ev if x["scene"] == "weave_clap"), 1e9),
    }
    if state["wb_hit"] is not None and gt < state["wb_hit"]:
        state["wb_hit"] = None
    sc = e["scene"]
    if sc == "cover":
        img = paper_scene(fi, gt, e, lt, envs, "cover")
    elif sc == "endcard":
        img = paper_scene(fi, gt, e, lt, envs, "endcard")
    elif sc == "claire_open":
        img = claire_desk(fi, gt, e, lt, envs, "main")
    elif sc == "button":
        img = claire_desk(fi, gt, e, lt, envs, "alt")
    elif sc == "hearing":
        if e.get("take") == "02_simone" and 0.42 < lt / e["dur"] < 0.68:
            img = paper_scene(fi, gt, e, lt, envs, "cctv")
        else:
            img = hearing_frame(fi, gt, e, lt, envs, state)
    elif sc == "weave":
        img = weave_frame(fi, gt, e, lt, envs, state)
    elif sc == "weave_clap":
        img = weave_frame(fi, gt, e, lt, envs, state, clap=True)
    elif sc == "speech":
        frac = lt / e["dur"]
        tx = TAKES[e["take"]]["text"]
        if frac < tx.index("Twice.") / len(tx) + 0.04:
            img = paper_scene(fi, gt, e, lt, envs, "speech")
        else:
            e2 = dict(e, shot="pace" if frac < 0.9 else "front")
            img = hearing_frame(fi, gt, e2, lt, envs, state)
    elif sc == "flashback":
        img = paper_scene(fi, gt, e, lt, envs, "flashback")
    elif sc == "exit":
        img = exit_frame(fi, gt, e, lt, envs, state, "bonk" if e.get("shot") == "bonk" else "talk")
    elif sc == "door":
        img = exit_frame(fi, gt, e, lt, envs, state, "door")
    else:
        img = Image.new("RGB", (W, H))
    caption(img, e, lt)
    img.save(f"{out_dir}/f{fi:05d}.jpg", quality=90)
    return fi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default=str(REPO / "sketches/freezer-hearing/audio"))
    ap.add_argument("--test", type=float, nargs="*")
    ap.add_argument("--out", default=str(HERE / "freezer-hearing.mp4"))
    a = ap.parse_args()
    ev, takes, total = build(a.audio)
    envs = {k: envelope(v) for k, v in takes.items()}
    out_dir = HERE / "frames"
    out_dir.mkdir(exist_ok=True)
    if a.test is not None:
        for s in a.test:
            frame((int(s * FPS), ev, envs, str(out_dir)))
            print(out_dir / f"f{int(s * FPS):05d}.jpg")
        for e in ev:
            print(f"{e['start']:6.1f} {e['dur']:5.1f} {e['scene']:10s} {e.get('shot') or ''} {e['take'] or ''}")
        return
    for f in out_dir.glob("*.jpg"):
        f.unlink()
    n = int(total * FPS)
    with Pool(os.cpu_count()) as p:
        for i, _ in enumerate(p.imap_unordered(frame, [(fi, ev, envs, str(out_dir)) for fi in range(n)], chunksize=8)):
            if i % 300 == 0:
                print(f"{i}/{n}", flush=True)
    audio = mix(ev, takes, total)
    wav = HERE / "mix.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", f"{out_dir}/f%05d.jpg", "-i", str(wav),
                    "-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                    "-af", "loudnorm=I=-15:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", a.out], check=True)
    print(a.out, f"{total:.1f}s")


if __name__ == "__main__":
    main()
