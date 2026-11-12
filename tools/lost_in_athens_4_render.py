"""Render 'Lost in Athens, part four' (1080x1920): noir I-75 lament (Matthew + Cynthia), a hard cut
to Pastor Bumrod lost on a map near Quinnipiac, then a classic-rock outro.

python athens4.py <voices_dir> <out.mp4> [--frame T,..]
Needs beside it: dialogue.json, keep/photos/*.jpg, keep/map13.png, keep/map15.png, v/ct/%04d.jpg (540x960 night dashcam).
"""
import glob, json, math, subprocess, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
import audio3 as A, rock as R, noir as NZ

W, H, FPS, SR = 1080, 1920, 30, A.SR
HERE = Path(__file__).parent; SET = Path("/mnt/project-files/video/studio-set"); PHO = HERE / "keep/photos"
DLG = json.load(open(HERE / "dialogue.json")); L = DLG["lines"]
VOX = Path(sys.argv[1]); OUT = Path(sys.argv[2])
rng = np.random.default_rng(5)
def inter(w, s, disp=False): return ImageFont.truetype(f"/usr/share/fonts/opentype/inter/Inter{'Display' if disp else ''}-{w}.otf", s)
MONO = subprocess.run(["fc-match", "-f", "%{file}", "JetBrains Mono:bold"], capture_output=True, text=True).stdout
CHARTER = subprocess.run(["fc-match", "-f", "%{file}", "Bitstream Charter:bold:italic"], capture_output=True, text=True).stdout
NAMES = {"matthew": "MATTHEW HAGAN", "bumrod": "PASTOR RODNEY BUMROD", "cynthia": "CYNTHIA SIAKAM"}

# ---------- timeline ----------
wavs = sorted(VOX.glob("*.wav")); assert len(wavs) == len(L)
V = [A.load(p, A.SPEED) for p in wavs]
voice = np.zeros(200 * SR, np.float32); segs = []
def say(i, t, g=1.0):
    voice[int(t * SR): int(t * SR) + len(V[i])] += V[i] * g
    segs.append(dict(i=i, spk=L[i][0], text=L[i][1], t0=t, t1=t + len(V[i]) / SR)); return segs[-1]["t1"]
t = say(0, 2.5); t = say(1, t + .4); t = say(2, t + .4)
BOOT = t + .5                       # Cynthia powers up
t = say(3, BOOT + .9); DIE = t + .25
t = say(4, DIE + .7)
CUT = t + .55                       # smash to black
B0 = CUT + .9                       # the map
t = say(5, B0 + 1.0); t = say(6, t + .45)
R0 = t + .15                        # the riff kicks in
rk, BEAT = R.rock(); BAR = 4 * BEAT
t = say(7, R0 + BAR * 1.0, 1.15)
D7 = t
END_CHORD = R0 + 8 * BAR
CARD0 = R0 + 6 * BAR
TOTAL = END_CHORD + 3.4
S = segs
print(f"total {TOTAL:.1f}s boot {BOOT:.1f} cut {CUT:.1f} map {B0:.1f} rock {R0:.1f} card {CARD0:.1f}", file=sys.stderr)

def build_audio():
    n = int(TOTAL * SR); mix = np.zeros(n + SR * 8, np.float32)
    def add(s, t0, g=1.0):
        i = int(t0 * SR); m = min(len(s), len(mix) - i); mix[i:i + m] += s[:m] * g
    add(NZ.noir_music(int(CUT * SR)), 0, .9)
    def beep(f, d, g=.12):
        tt = np.arange(int(d * SR)) / SR; return (np.sin(2 * np.pi * f * tt) * np.minimum(1, tt * 200) * np.minimum(1, (d - tt) * 60) * g).astype(np.float32)
    for k, f in enumerate((660, 880, 1320)): add(beep(f, .11), BOOT + k * .13)                    # power-up chime
    tt = np.arange(int(.7 * SR)) / SR; add((np.sin(2 * np.pi * np.cumsum(700 * np.exp(-tt * 4.5)) / SR) * np.exp(-tt * 3) * .14).astype(np.float32), DIE)   # power-down sigh
    tt = np.arange(int(.5 * SR)) / SR; add((np.sin(2 * np.pi * 52 * tt) * np.exp(-tt * 9) + rng.normal(0, .4, len(tt)) * np.exp(-tt * 40)).astype(np.float32), CUT, .8)   # the cut lands
    # lost in Connecticut: turn signal, night air
    tk = A.click() * .5
    q = B0 + .2
    while q < R0 - .2: add(tk, q, .22); add(tk, q + .38, .14); q += .76
    air = rng.normal(0, 1, int((R0 - B0) * SR)).astype(np.float32); air = A.box(air, 60) * 1.2; add(air, B0, .05)
    duck = np.ones(len(rk), np.float32); a0 = int((S[7]["t0"] - R0 - .1) * SR); a1 = int((S[7]["t1"] - R0 + .1) * SR); duck[a0:a1] = .42; duck = A.box(duck, 3000)
    add(rk * duck, R0, .62)
    mix[:n] += voice[:n]; mix = mix[:n]; tt = np.arange(n) / SR; mix *= np.clip((TOTAL - tt) / .8, 0, 1)
    pk = np.abs(mix).max(); mix = mix / pk * .97 if pk > .97 else mix
    ap = HERE / "_mix.wav"
    with wave.open(str(ap), "w") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    return ap

# ---------- shared drawing ----------
PH = {}
def photo(n):
    if n not in PH:
        im = ImageOps.exif_transpose(Image.open(PHO / f"{n}.jpg")).convert("RGB"); s = max(W / im.width, H / im.height) * 1.3
        PH[n] = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    return PH[n]
def kbim(im, k, cx0, cx1, cy0=.5, cy1=.5, z0=1.0, z1=1.12):
    z = z0 + (z1 - z0) * k; cw, ch = W * 1.3 / z, H * 1.3 / z
    cx = (cx0 + (cx1 - cx0) * k) * im.width; cy = (cy0 + (cy1 - cy0) * k) * im.height
    x = min(max(cx - cw / 2, 0), im.width - cw); y = min(max(cy - ch / 2, 0), im.height - ch)
    return im.crop((int(x), int(y), int(x + cw), int(y + ch))).resize((W, H), Image.BILINEAR)
def cut(name, h, crop=None):
    c = Image.open(SET / f"cutout-{name}.png"); c = c.crop(c.getbbox())
    if crop: c = c.crop((0, 0, c.width, int(c.height * crop)))
    return c.resize((int(c.width * h / c.height), h), Image.LANCZOS)
def noirize(c):
    a = c.getchannel("A"); g = ImageOps.autocontrast(c.convert("L"), cutoff=2)
    g = ImageEnhance.Contrast(g).enhance(1.5); g = ImageEnhance.Brightness(g).enhance(.8)
    return Image.merge("RGBA", (g, g, g, a))
MAT = noirize(cut("matthew", 900, .62)); MATD = ImageEnhance.Brightness(MAT).enhance(.5)
CYNC = cut("cynthia", 960, .78); CYN = noirize(CYNC); CYNOFF = ImageEnhance.Brightness(CYN).enhance(.16)
BUM = cut("bumrod", 1060, .62)
def shadowed(im, c, x, y):
    sh = Image.new("RGBA", c.size, (0, 0, 0, 0)); sh.putalpha(c.getchannel("A").point(lambda v: int(v * .6)))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)), (x + 16, y + 10)); im.alpha_composite(c, (x, y))
VIG = Image.new("L", (W, H), 0); ImageDraw.Draw(VIG).ellipse((-W * .35, -H * .2, W * 1.35, H * 1.2), fill=255); VIG = VIG.filter(ImageFilter.GaussianBlur(220))
BLINDS = Image.new("L", (W, H), 0); _d = ImageDraw.Draw(BLINDS)
for i in range(-6, 30): _d.polygon([(0, i * 96 + 30), (W, i * 96 - 110), (W, i * 96 - 66), (0, i * 96 + 74)], fill=66)
BLINDS = BLINDS.filter(ImageFilter.GaussianBlur(5))
FOG = Image.new("RGBA", (W, H), (0, 0, 0, 0)); _d = ImageDraw.Draw(FOG)
for y in range(1500, H): _d.line([(0, y), (W, y)], fill=(0, 0, 0, int(230 * ((y - 1500) / 420) ** 1.4)))
CAPN = ImageFont.truetype(MONO, 52); CAPB = inter("Black", 60, True)
REPL = (("T Kennedy", "T. Kennedy"), ("Interstate 75", "I-75"))
def caption_chunks(seg):
    txt = seg["text"]
    for a, b in REPL: txt = txt.replace(a, b)
    words = txt.split(); chunks, cur = [], []
    for w_ in words:
        cur.append(w_)
        if len(" ".join(cur)) > 22 or (w_.endswith((".", "?", "!")) and len(cur) > 1): chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    tot = sum(len(w_) + 1 for w_ in words); dur = seg["t1"] - seg["t0"]; t = seg["t0"]; out = []
    for c in chunks:
        wt = []
        for w_ in c: d_ = dur * (len(w_) + 1) / tot; wt.append((w_, t, t + d_)); t += d_
        out.append(wt)
    return out
for s in segs: s["caps"] = caption_chunks(s)
def draw_caption(im, seg, tt, yc=560, font=None, fill=(255, 255, 255), stroke=(0, 0, 0)):
    font = font or CAPN; d = ImageDraw.Draw(im); chunk = None
    for c in seg["caps"]:
        if c[0][1] <= tt: chunk = c
    if not chunk: return
    lines, cur = [], []
    for w_ in chunk:
        if cur and d.textlength(" ".join(x[0] for x in cur + [w_]), font=font) > W - 120: lines.append(cur); cur = [w_]
        else: cur.append(w_)
    if cur: lines.append(cur)
    y0 = yc - (len(lines) - 1) * 40
    for ln in lines:
        x = (W - d.textlength(" ".join(x[0] for x in ln), font=font)) / 2
        for w_, a, b in ln:
            if a > tt: break
            d.text((x, y0), w_, font=font, fill=fill, anchor="lm", stroke_width=7, stroke_fill=stroke); x += d.textlength(w_ + " ", font=font)
        y0 += 80
def typed(d, y, text, f, tt, t0, cps=24, fill=(255, 255, 255, 255)):
    n = int(max(0, tt - t0) * cps)
    if n <= 0: return
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text[:n] + ("█" if n < len(text) and int(tt * 4) % 2 else ""), font=f, fill=fill, anchor="lm", stroke_width=5, stroke_fill=(0, 0, 0, 255))
def chip(d, text, y=1720, fill=(0, 0, 0, 220), ink=(240, 240, 240, 255), line=(230, 230, 230, 255)):
    f = inter("Bold", 28)
    while d.textlength(text, font=f) > W - 110: f = inter("Bold", f.size - 1)
    tw = d.textlength(text, font=f); d.rectangle(((W - tw) / 2 - 20, y - 30, (W + tw) / 2 + 20, y + 30), fill=fill, outline=line, width=2)
    d.text((W / 2, y), text, font=f, fill=ink, anchor="mm")

# ---------- A: I-75 ----------
c0 = S[0]; f0 = lambda k: c0["t0"] + (c0["t1"] - c0["t0"]) * k
PANELS = [  # start, photo, kb, lamp
    (0, "ypsi-8", (.50, .50, .52, .44, 1.0, 1.12), None),
    (S[0]["t0"] - .12, "motel-6", (.52, .52, .30, .36, 1.25, 1.4), (.5, .3)),
    (f0(.68), "bg-7", (.40, .56, .5, .5, 1.0, 1.1), None),
    (S[1]["t0"] - .12, "i75-9", (.44, .56, .5, .5, 1.0, 1.14), (.2, .42)),
    (S[1]["t0"] + (S[1]["t1"] - S[1]["t0"]) * .5, "i75-3", (.40, .60, .5, .5, 1.0, 1.1), None),
    (S[2]["t0"] - .12, "i75-8", (.5, .5, .56, .46, 1.0, 1.16), None),
]
CHIPS = [(S[0]["t0"] + .2, f0(.30), "PHONE: 0%  ·  WILL NOT CHARGE"),
         (f0(.32), f0(.66), "MOTEL 28  ·  OUTSIDE YPSILANTI  ·  CORPORATE CARD: DECLINED"),
         (f0(.70), S[0]["t1"] + .3, "BOWLING GREEN  ·  PRESS PASS: DENIED"),
         (S[1]["t0"] + .2, S[1]["t1"] + .3, "I-75 SOUTH  ·  CHECK ENGINE  ·  REAR TIRES: BALD"),
         (S[2]["t0"] + 1.4, S[2]["t1"] + .3, "CRAIG: NO ANSWER  ·  T. KENNEDY: NO ANSWER")]
def stamp(im, text, k):
    f = inter("Black", 120, True); tile = Image.new("RGBA", (900, 260), (0, 0, 0, 0)); td = ImageDraw.Draw(tile)
    td.rounded_rectangle((10, 10, 890, 250), 20, outline=(225, 40, 40, 255), width=12); td.text((450, 128), text, font=f, fill=(225, 40, 40, 255), anchor="mm")
    z = 1 + 1.2 * max(0, 1 - k / .12); tile = tile.resize((int(900 * z * .8), int(260 * z * .8))).rotate(-9, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(tile, ((W - tile.width) // 2, 960 - tile.height // 2))
def noir_frame(tt):
    pi = max(i for i, p in enumerate(PANELS) if p[0] <= tt); p = PANELS[pi]; nxt = PANELS[pi + 1][0] if pi + 1 < len(PANELS) else CUT
    k = (tt - p[0]) / max(.1, nxt - p[0])
    g = ImageOps.autocontrast(kbim(photo(p[1]), k, *p[2]).convert("L"), cutoff=1); g = ImageEnhance.Contrast(g).enhance(1.7); g = ImageEnhance.Brightness(g).enhance(.42 if not p[1].startswith("motel") else .8)
    a = np.asarray(g).astype(np.float32)
    if p[3]:
        yy, xx = np.mgrid[0:H:8, 0:W:8]; fl = 0.85 + 0.15 * math.sin(tt * 23) * math.sin(tt * 7.3)
        gl = np.exp(-(((xx - p[3][0] * W) ** 2 + (yy - p[3][1] * H) ** 2) / (2 * 300 * 300))) * 90 * fl
        a += np.asarray(Image.fromarray(gl.astype(np.float32)).resize((W, H), Image.BILINEAR))
    n = rng.integers(-26, 26, (H // 2, W // 2)).astype(np.float32); a += np.kron(n, np.ones((2, 2), np.float32))
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")
    rl = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(rl)
    for _ in range(230):
        x = rng.integers(-100, W + 100); y = rng.integers(-100, H); Ln = rng.integers(40, 110)
        rd.line([(x, y), (x - Ln * .22, y + Ln)], fill=int(rng.integers(60, 150)), width=2)
    ov = Image.new("RGBA", (W, H), (255, 255, 255, 0)); ov.putalpha(rl.point(lambda v: int(v * .55))); im.alpha_composite(ov)
    cur = next((s for s in segs if s["t0"] <= tt <= s["t1"] + 0.2 and s["i"] < 5), None)
    if pi > 0:
        on = BOOT <= tt < DIE
        cy = CYNOFF
        if on:      # she comes back in full color, the only color on the road
            fl = 1.0 if tt - BOOT > .35 else (.4 + .6 * (int((tt - BOOT) * 30) % 2))
            cy = ImageEnhance.Brightness(CYNC).enhance(fl)
            gl = Image.new("L", (W, H), 0); ImageDraw.Draw(gl).ellipse((420, 900, 1200, 1900), fill=int(120 * fl)); o = Image.new("RGBA", (W, H), (60, 230, 255, 0)); o.putalpha(gl.filter(ImageFilter.GaussianBlur(120))); im.alpha_composite(o)
        elif DIE <= tt < DIE + .3:
            k2 = (tt - DIE) / .3; cy = Image.blend(CYNC, CYNOFF, k2)
        shadowed(im, cy, 520, H - cy.height + 30)
        m = MAT if (cur and cur["spk"] == "matthew") else MATD
        shadowed(im, m, -60, H - m.height + 30)
    im.alpha_composite(FOG)
    o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); o.putalpha(BLINDS); im.alpha_composite(o)
    im = Image.composite(im.convert("RGB"), Image.new("RGB", (W, H), (0, 0, 0)), VIG).convert("RGBA"); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 96), fill=(0, 0, 0, 255)); d.rectangle((0, H - 96, W, H), fill=(0, 0, 0, 255))
    if tt < S[0]["t0"] - .1:
        typed(d, 300, "LOST IN ATHENS", ImageFont.truetype(MONO, 64), tt, 0.3); typed(d, 380, "PART FOUR", ImageFont.truetype(MONO, 44), tt, 1.1)
        if tt > 1.5: chip(d, "YPSILANTI, MICHIGAN")
    if f0(.74) <= tt <= S[0]["t1"] + .3: stamp(im, "DENIED", tt - f0(.74)); d = ImageDraw.Draw(im)
    if S[1]["t0"] <= tt <= S[2]["t1"] and int(tt * 2.2) % 2 == 0:        # check engine light, amber
        x, y = W - 170, 170; am = (255, 170, 20, 255)
        d.rounded_rectangle((x - 60, y - 34, x + 60, y + 40), 10, outline=am, width=7); d.rectangle((x - 30, y - 54, x + 30, y - 34), outline=am, width=7)
        d.rectangle((x - 84, y - 12, x - 60, y + 18), fill=am); d.rectangle((x + 60, y - 12, x + 84, y + 18), fill=am); d.text((x, y + 80), "CHECK ENGINE", font=inter("Bold", 24), fill=am, anchor="mm")
    if BOOT <= tt < DIE + .3:
        col = (60, 230, 255, 255) if tt < DIE else (255, 60, 60, 255)
        d.text((W - 60, 1010), "CYNTHIA  ·  POWER " + ("ON" if tt < DIE else "LOST"), font=inter("Bold", 26), fill=col, anchor="rm", stroke_width=4, stroke_fill=(0, 0, 0, 255))
    for t0, t1, text in CHIPS:
        if t0 <= tt <= t1: chip(d, text)
    if S[3]["t0"] + .9 <= tt <= DIE + .2: chip(d, "MISSED CALLS: 0", ink=(60, 230, 255, 255), line=(60, 230, 255, 255))
    if cur:
        draw_caption(im, cur, tt, 560, None, (140, 240, 255) if cur["spk"] == "cynthia" else (255, 255, 255))
        d.text((W / 2, 440), NAMES[cur["spk"]], font=inter("Bold", 30), fill=(200, 200, 200, 255), anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0, 255))
    if pi and tt - p[0] < 0.1: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - (tt - p[0]) / 0.1)))))
    if tt < 0.6: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - tt / 0.6)))))
    return im.convert("RGB")
def black_frame(tt):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    typed(d, 900, "MEANWHILE...", ImageFont.truetype(MONO, 60), tt, CUT + .1, 30); typed(d, 990, "SOMEWHERE IN CONNECTICUT", ImageFont.truetype(MONO, 40), tt, CUT + .4, 40)
    return im.convert("RGB")

# ---------- B: the map ----------
M13 = Image.open(HERE / "keep/map13.png").convert("RGB"); M15 = Image.open(HERE / "keep/map15.png").convert("RGB")
def paper(im):
    a = np.asarray(im).astype(np.float32); g = a.mean(2, keepdims=True); a = a * .75 + g * .25
    a = a * np.array([1.0, .95, .80]) - 14; return Image.fromarray(a.clip(0, 255).astype(np.uint8))
M13 = paper(M13.resize((2048, 3584), Image.LANCZOS)); M15 = paper(M15.resize((2048, 3584), Image.LANCZOS))
Q13 = (1090 / 1024 * 2048 * .5 + 0, 0)   # placeholder, set below
# Quinnipiac label on map13 (px in 1024x1792): about (570, 935); on map15: about (527, 993)
Q13 = (570 * 2, 935 * 2); Q15 = (527 * 2, 993 * 2)
ROUTE = [(545, 1790), (548, 1560), (520, 1420), (430, 1330), (330, 1345), (400, 1260), (520, 1200), (620, 1170), (760, 1040), (700, 960), (760, 1040), (640, 1110), (530, 1010), (500, 900), (470, 700), (490, 600), (470, 700), (500, 860), (560, 925)]
ROUTE = [(x * 2, y * 2) for x, y in ROUTE]
_rl = [0]
for a, b in zip(ROUTE, ROUTE[1:]): _rl.append(_rl[-1] + math.dist(a, b))
def route_pt(k):
    dd = k * _rl[-1]
    for i in range(len(ROUTE) - 1):
        if dd <= _rl[i + 1]:
            u = (dd - _rl[i]) / (_rl[i + 1] - _rl[i]); return (ROUTE[i][0] + (ROUTE[i + 1][0] - ROUTE[i][0]) * u, ROUTE[i][1] + (ROUTE[i + 1][1] - ROUTE[i][1]) * u), i
    return ROUTE[-1], len(ROUTE) - 2
def view(m, cx, cy, z):
    cw, ch = W / z, H / z; x = min(max(cx - cw / 2, 0), m.width - cw); y = min(max(cy - ch * .42, 0), m.height - ch)
    return m.crop((int(x), int(y), int(x + cw), int(y + ch))).resize((W, H), Image.BILINEAR), (x, y)
ZOOM0 = S[5]["t0"] + (S[5]["t1"] - S[5]["t0"]) * .40      # "like a church camp": punch in to the campus map
def polaroid(name, w, rot, box=None):
    im = ImageOps.exif_transpose(Image.open(PHO / f"{name}.jpg")).convert("RGB")
    if box: im = im.crop(box)
    im = ImageOps.fit(im, (w, int(w * .8)), Image.LANCZOS); t = Image.new("RGBA", (w + 36, int(w * .8) + 110), (248, 244, 232, 255)); t.paste(im, (18, 18))
    return t.rotate(rot, expand=True, resample=Image.BICUBIC)
_POL = {}
def map_frame(tt):
    e = tt - B0; rk_ = min(1, e / (ZOOM0 - B0 - .2)); (px, py), seg = route_pt(rk_ ** .9)
    if tt < ZOOM0:
        im, (ox, oy) = view(M13, px, py + 250, 1.35); z = 1.35
        o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(o)
        pts = [((x - ox) * z, (y - oy) * z) for x, y in ROUTE[:seg + 1]] + [((px - ox) * z, (py - oy) * z)]
        for a, b in zip(pts, pts[1:]):          # dashed red wander
            n = max(1, int(math.dist(a, b) / 26))
            for j in range(n):
                if j % 2 == 0: d.line([(a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n), (a[0] + (b[0] - a[0]) * (j + 1) / n, a[1] + (b[1] - a[1]) * (j + 1) / n)], fill=(200, 30, 30, 255), width=9)
        x, y = pts[-1]; d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=(200, 30, 30, 255), outline=(255, 255, 255, 255), width=5)
        for (qx, qy), txt in ((ROUTE[4], "?"), (ROUTE[9], "??"), (ROUTE[15], "NOPE")):
            if _rl[ROUTE.index((qx, qy))] <= rk_ ** .9 * _rl[-1]: d.text(((qx - ox) * z + 40, (qy - oy) * z - 40), txt, font=inter("Black", 64, True), fill=(200, 30, 30, 255), anchor="mm", stroke_width=5, stroke_fill=(255, 250, 235, 255))
        im = im.convert("RGBA"); im.alpha_composite(o)
    else:
        k = min(1, (tt - ZOOM0) / 6); z = 1.0 + .16 * k
        im, (ox, oy) = view(M15, Q15[0] + 60, Q15[1] + 330, z); im = im.convert("RGBA"); d = ImageDraw.Draw(im)
        x, y = (Q15[0] - ox) * z, (Q15[1] - oy) * z; pu = (tt * 1.6) % 1
        for r, al in ((150 + pu * 120, int(255 * (1 - pu))), (150, 255)): d.ellipse((x - r * 1.5, y - r * .7, x + r * 1.5, y + r * .7), outline=(200, 30, 30, al), width=10)
        d.text((x, y - 160), "FOUND IT (PROBABLY)", font=inter("Black", 46, True), fill=(200, 30, 30, 255), anchor="mm", stroke_width=6, stroke_fill=(255, 250, 235, 255))
        for nm, t0, pos, rot, box in (("quin-6", ZOOM0 + .5, (20, 960), -6, None), ("quin-4", ZOOM0 + 1.3, (50, 1400), 5, None)):
            if tt >= t0:
                if nm not in _POL: _POL[nm] = polaroid(nm, 400, rot, box)
                pk = min(1, (tt - t0) / .15); p_ = _POL[nm]; sh = Image.new("RGBA", p_.size, (0, 0, 0, 0)); sh.putalpha(p_.getchannel("A").point(lambda v: int(v * .5)))
                im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (pos[0] + 12, pos[1] + 16 - int((1 - pk) * 60))); im.alpha_composite(p_, (pos[0], pos[1] - int((1 - pk) * 60)))
        d = ImageDraw.Draw(im)
        if tt >= ZOOM0 + .5: d.text((230, 1330), "CHURCH CAMP?", font=inter("Black", 34), fill=(40, 30, 20, 255), anchor="mm")
    a = np.asarray(im.convert("RGB")).astype(np.float32) + rng.integers(-8, 8, (H, W, 1))
    im = Image.composite(Image.fromarray(a.clip(0, 255).astype(np.uint8)), Image.new("RGB", (W, H), (30, 18, 8)), VIG.point(lambda v: 90 + v * 165 // 255)).convert("RGBA")
    cur = next((s for s in segs if s["t0"] <= tt <= s["t1"] + 0.2 and s["i"] >= 5), None)
    bob = int(6 * math.sin(tt * 9)) if cur else 0
    shadowed(im, BUM, 470, H - BUM.height + 90 + bob + int(max(0, 1 - e / .35) * 500))
    im.alpha_composite(FOG); d = ImageDraw.Draw(im)
    d.text((W - 24, H - 24), "Map © OpenStreetMap contributors", font=inter("Medium", 22), fill=(255, 255, 255, 220), anchor="rb", stroke_width=3, stroke_fill=(0, 0, 0, 255))
    if cur:
        draw_caption(im, cur, tt, 800, CAPB, (255, 232, 120), (30, 14, 4))
        d.text((W / 2, 700), NAMES[cur["spk"]], font=inter("Bold", 30), fill=(255, 250, 235, 255), anchor="mm", stroke_width=5, stroke_fill=(30, 14, 4, 255))
    if e < .12: im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * (1 - e / .12)))))
    return im.convert("RGB")

# ---------- C: rock outro ----------
CT = sorted(glob.glob(str(HERE / "v/ct/*.jpg")))
def ct_frame(e):
    n = int(e * FPS * 1.6); m = len(CT) - 1; n = n % (2 * m); n = n if n <= m else 2 * m - n
    return Image.open(CT[n]).convert("RGB").resize((W, H), Image.BILINEAR)
SHOTS = [("ct", None), ("quin-1", (.5, .5, .62, .58)), ("ct", None), ("quin-7", (.40, .60, .5, .5)), ("quin-6", (.36, .5, .5, .5)), ("ct", None)]
def rock_grade(im, pulse):
    a = np.asarray(im).astype(np.float32); a = (a - 110) * 1.35 + 118; a = a * np.array([1.12, .98, .80]) * (1 + .12 * pulse) + rng.integers(-12, 12, (H, W, 1))
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8)); bl = im.filter(ImageFilter.GaussianBlur(20)); im = Image.blend(im, Image.fromarray(np.maximum(np.asarray(im), np.asarray(bl))), .4)
    return Image.composite(im, ImageEnhance.Brightness(im).enhance(.3), VIG)
BUMR = cut("bumrod", 1700, .56)
def phone_card(im, tt):
    e = tt - R0; k = min(1, e / .25); x0, y0 = 150, 150 - int((1 - k) * 500); d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, W - 150, y0 + 330), 44, fill=(16, 16, 20, 240), outline=(255, 200, 60, 255), width=5)
    d.ellipse((x0 + 40, y0 + 60, x0 + 200, y0 + 220), fill=(200, 60, 40, 255)); d.text((x0 + 120, y0 + 140), "D", font=inter("Black", 96, True), fill=(255, 240, 220, 255), anchor="mm")
    d.text((x0 + 240, y0 + 100), "DERRICK", font=inter("Black", 76, True), fill=(255, 255, 255, 255), anchor="lm")
    dots = "." * (1 + int(e * 2.5) % 3)
    d.text((x0 + 240, y0 + 180), "church camps  ·  calling" + dots, font=inter("Medium", 32), fill=(200, 200, 205, 255), anchor="lm")
    ring = int(e / BEAT) % 2 == 0
    d.text((x0 + 240, y0 + 260), "RINGING" if ring else "", font=inter("Bold", 30), fill=(120, 255, 140, 255), anchor="lm")
def rock_frame(tt):
    e = tt - R0; bi = int(e / BAR); pulse = math.exp(-((e % BEAT) / BEAT) * 4)
    si = min(len(SHOTS) - 1, int(e / (BAR * 8 / len(SHOTS)))) if tt < END_CHORD else len(SHOTS) - 1
    nm, kbp = SHOTS[si]; k = (e - si * BAR * 8 / len(SHOTS)) / (BAR * 8 / len(SHOTS))
    base = ct_frame(e) if nm == "ct" else kbim(photo(nm), min(1, k), kbp[0], kbp[1], kbp[2], kbp[3], 1.0, 1.14)
    im = rock_grade(base, pulse).convert("RGBA")
    if tt < CARD0:
        if tt < D7 + .6:
            bob = int(10 * pulse); shadowed(im, BUMR, 140, H - BUMR.height + 200 - bob); im.alpha_composite(FOG)
        phone_card(im, tt); d = ImageDraw.Draw(im)
        cur = next((s for s in segs if s["t0"] <= tt <= s["t1"] + 0.2 and s["i"] == 7), None)
        if cur:
            draw_caption(im, cur, tt, 700, CAPB, (255, 232, 120), (30, 14, 4)); d.text((W / 2, 600), NAMES["bumrod"], font=inter("Bold", 30), fill=(255, 250, 235, 255), anchor="mm", stroke_width=5, stroke_fill=(30, 14, 4, 255))
        elif tt > D7 + .6:
            f = inter("Black", 150, True); o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(o); z = 1 + .04 * pulse
            for txt, yy in (("WILL", 900), ("DERRICK", 1060), ("PICK UP?", 1220)):
                od.text((W / 2 + 8, yy + 8), txt, font=f, fill=(0, 0, 0, 200), anchor="mm"); od.text((W / 2, yy), txt, font=f, fill=(255, 210, 60, 255), anchor="mm", stroke_width=6, stroke_fill=(120, 30, 10, 255))
            o = o.resize((int(W * z), int(H * z))); im.alpha_composite(o.crop(((o.width - W) // 2, (o.height - H) // 2, (o.width - W) // 2 + W, (o.height - H) // 2 + H)))
    else:
        k = min(1, (tt - CARD0) / .6); im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(140 * k)))); o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(o); al = int(255 * k)
        od.text((W / 2, 800), "To be continued...", font=ImageFont.truetype(CHARTER, 104), fill=(255, 214, 70, al), anchor="mm", stroke_width=4, stroke_fill=(60, 24, 8, al))
        od.text((W / 2, 940), "IF DERRICK PICKS UP", font=inter("Black", 70, True), fill=(255, 255, 255, al), anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0, al))
        od.text((W / 2, 1030), "LOST IN ATHENS  ·  PART FIVE", font=ImageFont.truetype(MONO, 34), fill=(235, 235, 235, al), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, al))
        od.text((W / 2, 1700), "Voices are AI-generated.  hardwoodbricks.com", font=inter("Medium", 28), fill=(235, 235, 235, al), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, al))
        im.alpha_composite(o)
    if e < .1: im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * (1 - e / .1)))))
    fo = (TOTAL - tt) / 1.0
    if fo < 1: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - max(0, fo))))))
    return im.convert("RGB")

def frame(n):
    tt = n / FPS
    if tt < CUT: return noir_frame(tt)
    if tt < B0: return black_frame(tt)
    if tt < R0: return map_frame(tt)
    return rock_frame(tt)
if "--frame" in sys.argv:
    for t in sys.argv[sys.argv.index("--frame") + 1].split(","):
        t = {"C": CUT, "B": B0, "R": R0, "O": BOOT}.get(t[0], 0) + float(t[1:]) if t[0] in "CBRO" else float(t)
        frame(int(t * FPS)).resize((540, 960)).save(OUT.with_suffix(f".{t:.1f}.png"))
    sys.exit()
apath = build_audio()
N = int(TOTAL * FPS)
p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                      "-i", str(apath), "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-maxrate", "3000k", "-bufsize", "6000k", "-pix_fmt", "yuv420p",
                      "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
for n in range(N):
    p.stdin.write(frame(n).tobytes())
    if n % 300 == 0: print(n, "/", N, file=sys.stderr, flush=True)
p.stdin.close(); p.wait(); print("wrote", OUT, file=sys.stderr)
