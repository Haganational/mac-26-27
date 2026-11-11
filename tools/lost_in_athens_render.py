"""Render 'Lost in Athens' (1080x1920): Ken Burns over Matthew's photos, cast cutouts, noir outro.

python lost.py <voices_dir> <out.mp4> [--frame T]
"""
import glob, json, math, subprocess, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H, FPS, SR = 1080, 1920, 30, 24000
HERE = Path(__file__).parent
SET = Path("/mnt/project-files/video/studio-set")
DLG = json.load(open(HERE / "dialogue.json"))
VOX = Path(sys.argv[1]); OUT = Path(sys.argv[2])
rng = np.random.default_rng(3)

def inter(w, s): return ImageFont.truetype(f"/usr/share/fonts/opentype/inter/Inter-{w}.otf", s)
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
MONO = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf"
if not Path(MONO).exists(): MONO = subprocess.run(["fc-match", "-f", "%{file}", "JetBrains Mono:bold"], capture_output=True, text=True).stdout
GOLD = (236, 196, 106)
SPK = {"matthew": dict(name="Matthew Hagan", sub="Editor · lived in the Convo, '98", col=(240, 150, 80)),
       "bumrod": dict(name="Pastor Rodney Bumrod", sub="Ball State, class of way back", col=(238, 52, 68)),
       "cynthia": dict(name="Cynthia Siakam", sub="Data desk · AI · needs broadband", col=(84, 222, 244))}

# ---------- audio ----------
def read(p):
    with wave.open(str(p)) as w:
        sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2: a = a.reshape(-1, 2).mean(1)
    if sr != SR: a = np.interp(np.linspace(0, len(a) - 1, int(len(a) * SR / sr)), np.arange(len(a)), a)
    idx = np.nonzero(np.abs(a) > 0.012)[0]
    if len(idx): a = a[max(0, idx[0] - 1200): idx[-1] + 2400]
    return (a * (0.89 / (np.abs(a).max() or 1))).astype(np.float32)

wavs = sorted(VOX.glob("*.wav")); assert len(wavs) == len(DLG["lines"])
INTRO = 3.0
GAP = {1: 0.25, 2: 0.3, 3: 0.4, 4: 0.3, 5: 0.45, 6: 0.5, 7: 3.2, 8: 0.9, 9: 0.5}
segs, t = [], INTRO
voice = np.zeros(int(400 * SR), np.float32)
for i, (p, (spk, text)) in enumerate(zip(wavs, DLG["lines"])):
    t += GAP.get(i, 0)
    a = read(p); voice[int(t * SR): int(t * SR) + len(a)] += a
    segs.append(dict(i=i, spk=spk, text=text, t0=t, t1=t + len(a) / SR, a=a)); t += len(a) / SR
NOIR0 = segs[7]["t0"] - 2.6          # noir section starts (fade through black)
END0 = segs[-1]["t1"] + 1.0          # end title
TOTAL = END0 + 6.5
voice = voice[: int(TOTAL * SR)]
print(f"duration {TOTAL:.1f}s noir at {NOIR0:.1f}", file=sys.stderr)

def music():
    n = int(TOTAL * SR); out = np.zeros(n + SR * 6, np.float32); bpm = 63; beat = 60 / bpm
    def hz(m): return 440 * 2 ** ((m - 69) / 12)
    def add(sig, t0, g):
        i = int(t0 * SR)
        if i < n: out[i: i + len(sig)] += sig[: len(out) - i] * g
    def pluck(m, d=0.9):
        tt = np.arange(int(d * SR)) / SR; f = hz(m)
        s = np.sin(2 * np.pi * f * tt) + 0.45 * np.sin(4 * np.pi * f * tt) + 0.18 * np.sin(6 * np.pi * f * tt)
        return (s * np.exp(-tt * 4.2) * np.minimum(1, tt * 200)).astype(np.float32)
    def keys(ms, d=3.4):
        tt = np.arange(int(d * SR)) / SR; s = 0
        for m in ms: f = hz(m); s = s + np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt) * np.exp(-tt * 6)
        return (s / len(ms) * np.exp(-tt * 1.1) * (1 + 0.25 * np.sin(2 * np.pi * 4.6 * tt)) * np.minimum(1, tt * 60)).astype(np.float32)
    def horn(m, d):
        tt = np.arange(int(d * SR)) / SR; f = hz(m) * (1 + 0.006 * np.sin(2 * np.pi * 5.2 * tt) * np.minimum(1, tt * 2))
        ph = 2 * np.pi * np.cumsum(f) / SR; s = sum(np.sin(k * ph) / k ** 1.5 for k in range(1, 7))
        env = np.minimum(1, tt * 9) * np.minimum(1, (d - tt) * 5)
        return (s * env).astype(np.float32)
    def brush(d=0.22):
        x = rng.normal(0, 1, int(d * SR)).astype(np.float32); x = x - np.convolve(x, np.ones(6) / 6, "same")
        tt = np.arange(len(x)) / SR; return x * np.sin(np.pi * tt / d) ** 2
    bars = [([38, 41, 45, 48], [50, 53, 57, 60, 64]), ([34, 38, 41, 45], [46, 50, 53, 57]),
            ([31, 34, 38, 41], [43, 46, 50, 53]), ([33, 37, 40, 45], [45, 49, 52, 55, 58])]
    def lvl(tm): return 0.35 if tm < NOIR0 else (1.0 if tm < END0 else 1.5)
    b = 0
    while b * beat < TOTAL + 2:
        tm = b * beat; bar = bars[(b // 4) % 4]; g = lvl(tm)
        add(pluck(bar[0][b % 4]), tm, 0.20 * g)
        if b % 4 == 0: add(keys(bar[1]), tm + 0.02, 0.10 * g)
        add(brush(), tm + (beat * 0.5 if b % 2 else 0), 0.035 * g)
        add(brush(0.12), tm + beat * 0.66, 0.02 * g)
        b += 1
    # lonely horn in the noir section
    mel = [(69, 2.5), (65, 1), (62, 2.5), (None, 1), (64, 1.5), (65, .5), (64, 1), (57, 3), (None, 1.5),
           (62, 1), (65, 1), (69, 1.5), (72, .5), (70, 3), (None, 1), (69, 1), (65, 1), (64, 1), (62, 4)]
    tm = math.ceil(NOIR0 / (4 * beat)) * 4 * beat
    k = 0
    while tm < TOTAL - 1:
        m, d = mel[k % len(mel)]; d *= beat
        if m: add(horn(m, d * 0.96), tm, 0.045 if tm < END0 else 0.075)
        tm += d; k += 1
    # rain
    r = rng.normal(0, 1, n).astype(np.float32); r = np.convolve(r, np.ones(5) / 5, "same") - np.convolve(r, np.ones(80) / 80, "same")
    tt = np.arange(n) / SR; renv = np.clip((tt - NOIR0) / 2.0, 0, 1) * 0.10
    out[:n] += r * renv
    out = out[:n]; fade = np.clip((TOTAL - tt) / 2.5, 0, 1) * np.clip(tt / 1.0, 0, 1)
    return out * fade
mix = voice + music()
mix = np.tanh(mix * 1.05) / 1.05
apath = OUT.with_suffix(".wav")
with wave.open(str(apath), "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())

# ---------- photos ----------
PH = {}
def photo(n):
    if n not in PH:
        im = ImageOps.exif_transpose(Image.open(glob.glob(str(HERE / f"raw/athens/{n}_*.jpg"))[0])).convert("RGB")
        s = max(W / im.width, H / im.height) * 1.3
        PH[n] = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    return PH[n]
def kb(n, k, cx0, cx1, cy0=.5, cy1=.5, z0=1.0, z1=1.12):
    im = photo(n); k = k * k * (3 - 2 * k) * 0.6 + k * 0.4
    z = (z0 + (z1 - z0) * k); cw, ch = W * 1.3 / z, H * 1.3 / z
    cx = (cx0 + (cx1 - cx0) * k) * im.width; cy = (cy0 + (cy1 - cy0) * k) * im.height
    x = min(max(cx - cw / 2, 0), im.width - cw); y = min(max(cy - ch / 2, 0), im.height - ch)
    return im.crop((int(x), int(y), int(x + cw), int(y + ch))).resize((W, H), Image.BILINEAR)

# shots: (start_time, photo, cx0, cx1, cy0, cy1, z0, z1)
S = segs
def mid(s, f): return s["t0"] + (s["t1"] - s["t0"]) * f
SHOTS = [
    (0, "01", .5, .5, .62, .40, 1.0, 1.22),
    (S[0]["t0"] - .2, "03", .35, .6, .6, .45, 1.0, 1.1),
    (mid(S[0], .40), "18", .3, .62, .5, .5, 1.0, 1.08),
    (mid(S[0], .68), "02", .33, .40, .5, .56, 1.0, 1.14),
    (S[1]["t0"] - .15, "13", .25, .6, .5, .5, 1.05, 1.12),
    (S[2]["t0"] - .15, "05", .3, .7, .5, .5, 1.0, 1.1),
    (mid(S[2], .45), "17", .3, .55, .5, .5, 1.05, 1.15),
    (S[3]["t0"] - .15, "20", .17, .40, .5, .5, 1.0, 1.0),
    (mid(S[3], .42), "11", .5, .5, .65, .40, 1.0, 1.15),
    (S[4]["t0"] - .15, "06", .5, .5, .7, .35, 1.0, 1.12),
    (S[5]["t0"] - .15, "08", .5, .5, .6, .45, 1.0, 1.15),
    (S[6]["t0"] - .15, "15", .2, .7, .5, .5, 1.0, 1.1),
    (mid(S[6], .5), "14", .25, .6, .5, .5, 1.0, 1.12),
]
NOIRSHOT = ("19", .14, .40, .5, .5, 1.0, 1.16)
CHIPS = [  # (t0, t1, text, color)
    (mid(S[0], .70), S[0]["t1"] + .2, "NO GAME TONIGHT  ·  NO OUTLET", (238, 52, 68)),
    (mid(S[2], .50), S[2]["t1"] + .2, "ATHENS MIDDLE SCHOOL  ·  1998", (90, 150, 255)),
    (S[3]["t0"] + .3, mid(S[3], .40), "BAGEL STREET DELI  ·  PASS #3", (84, 222, 244)),
    (mid(S[3], .45), S[3]["t1"] + .2, "MOTEL 6, NELSONVILLE (DRAMATIZATION)  ·  WI-FI: NONE", (84, 222, 244)),
    (S[4]["t0"] + .3, S[4]["t1"] + .3, "TRAVEL BUDGET: $0.00", (240, 150, 80)),
    (mid(S[5], .35), S[5]["t1"] + .2, "\"SOMEWHERE NEAR THIS RIVER\"  ·  199?", (238, 52, 68)),
    (mid(S[6], .40), S[6]["t1"] + .3, "BUMROD COAL-BASE INFANT FORMULA  ·  1994–1994", (238, 52, 68)),
]

# ---------- cast ----------
def cut(name, h, crop=None):
    c = Image.open(SET / f"cutout-{name}.png"); c = c.crop(c.getbbox())
    if crop: c = c.crop((0, 0, c.width, int(c.height * crop)))
    return c.resize((int(c.width * h / c.height), h), Image.LANCZOS)
CAST = {"matthew": cut("matthew", 900, .62), "bumrod": cut("bumrod", 1180, .62), "cynthia": cut("cynthia", 980, .78)}
def noirize(c, dark=.8):
    a = c.getchannel("A"); g = ImageOps.autocontrast(c.convert("L"), cutoff=2)
    g = ImageEnhance.Contrast(g).enhance(1.5); g = ImageEnhance.Brightness(g).enhance(dark)
    o = Image.merge("RGBA", (g, g, g, a)); return o
NCAST = {"matthew": noirize(cut("matthew", 760, .62)), "bumrod": noirize(cut("bumrod", 1300, .62)), "cynthia": noirize(cut("cynthia", 840, .78))}
def shadowed(im, c, x, y):
    sh = Image.new("RGBA", c.size, (0, 0, 0, 0)); sh.putalpha(c.getchannel("A").point(lambda v: int(v * .6)))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)), (x + 16, y + 10)); im.alpha_composite(c, (x, y))

def nameplate(im, spk, k, noir=False):
    s = SPK[spk]; d = ImageDraw.Draw(im); col = (235, 235, 235) if noir else s["col"]
    y = 1716; a = int(235 * k)
    d.rounded_rectangle((40, y, W - 40, y + 130), 26, fill=(10, 8, 8, a), outline=col + (int(255 * k),), width=4)
    d.text((76, y + 44), s["name"], font=inter("ExtraBold", 46), fill=col + (int(255 * k),), anchor="lm")
    d.text((76, y + 96), s["sub"], font=inter("Medium", 27), fill=(228, 222, 212, int(255 * k)), anchor="lm")

CAPF = inter("ExtraBold", 66); CAPN = ImageFont.truetype(MONO, 52)
def caption_chunks(seg):
    words = seg["text"].split(); chunks, cur = [], []
    for w_ in words:
        cur.append(w_)
        if len(" ".join(cur)) > 24 or (w_.endswith((".", "?", "!")) and len(cur) > 1): chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    tot = sum(len(w_) + 1 for w_ in words); dur = seg["t1"] - seg["t0"]; t = seg["t0"]; out = []
    for c in chunks:
        wt = []
        for w_ in c: d_ = dur * (len(w_) + 1) / tot; wt.append((w_, t, t + d_)); t += d_
        out.append(wt)
    return out
for s in segs: s["caps"] = caption_chunks(s)
def wrap(words, f, maxw, d):
    lines, cur = [], []
    for w_ in words:
        if cur and d.textlength(" ".join(x[0] for x in cur + [w_]), font=f) > maxw: lines.append(cur); cur = [w_]
        else: cur.append(w_)
    if cur: lines.append(cur)
    return lines
def draw_caption(im, seg, tt, noir):
    d = ImageDraw.Draw(im); chunk = None
    for c in seg["caps"]:
        if c[0][1] <= tt: chunk = c
    if not chunk: return
    f = CAPN if noir else CAPF; col = (255, 255, 255) if noir else SPK[seg["spk"]]["col"]
    lines = wrap(chunk, f, W - 120, d); y0 = (560 if noir else 520) - (len(lines) - 1) * 42
    for ln in lines:
        full = " ".join(x[0] for x in ln); x = (W - d.textlength(full, font=f)) / 2
        for w_, a, b in ln:
            if noir and a > tt: break
            fill = col if a <= tt else (255, 255, 255)
            d.text((x, y0), w_, font=f, fill=fill, anchor="lm", stroke_width=7, stroke_fill=(0, 0, 0))
            x += d.textlength(w_ + " ", font=f)
        y0 += 84

def chip(im, text, col, k):
    d = ImageDraw.Draw(im); f = inter("ExtraBold", 34)
    while d.textlength(text, font=f) > W - 150: f = inter("ExtraBold", f.size - 2)
    tw = d.textlength(text, font=f); a = int(255 * min(1, k * 6)); y = 250
    d.rounded_rectangle(((W - tw) / 2 - 30, y, (W + tw) / 2 + 30, y + 74), 37, fill=(8, 6, 6, int(a * .88)), outline=col + (a,), width=3)
    d.text((W / 2, y + 37), text, font=f, fill=(255, 255, 255, a), anchor="mm")

def topbar(im, noir):
    d = ImageDraw.Draw(im); f = ImageFont.truetype(SERIF, 30); s = "HARDWOOD BRICKS"
    tw = d.textlength(s, font=f); x0, x1 = (W - tw) / 2 - 26, (W + tw) / 2 + 26
    for y in range(120, 172):
        k = (y - 120) / 52; c = tuple(int(a + (b - a) * k) for a, b in zip((246, 214, 140), (176, 128, 52)))
        if noir: g = int(sum(c) / 3); c = (g, g, g)
        d.line([(x0, y), (x1, y)], fill=c + (255,))
    d.text((W / 2, 146), s, font=f, fill=(40, 22, 10, 255), anchor="mm")
    d.text((W / 2, 200), "L O S T   I N   A T H E N S", font=inter("ExtraBold", 28), fill=((230, 230, 230) if noir else GOLD) + (255,), anchor="mm")

VIG = Image.new("L", (W, H), 0); ImageDraw.Draw(VIG).ellipse((-W * .35, -H * .2, W * 1.35, H * 1.2), fill=255)
VIG = VIG.filter(ImageFilter.GaussianBlur(220))
BOTTOM = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(BOTTOM)
for y in range(1150, H): bd.line([(0, y), (W, y)], fill=(0, 0, 0, int(150 * ((y - 1150) / 770) ** 1.3)))
for y in range(0, 330): bd.line([(0, y), (W, y)], fill=(0, 0, 0, int(170 * (1 - y / 330) ** 1.2)))

def noir_bg(tt):
    k = min(1, max(0, (tt - NOIR0) / (TOTAL - NOIR0)))
    g = kb(NOIRSHOT[0], k, *NOIRSHOT[1:]).convert("L")
    g = ImageOps.autocontrast(g, cutoff=1); g = ImageEnhance.Contrast(g).enhance(1.7); g = ImageEnhance.Brightness(g).enhance(0.42)
    a = np.asarray(g).astype(np.float32)
    # lamp glow, flickering
    yy, xx = np.mgrid[0:H:8, 0:W:8]; fl = 0.85 + 0.15 * math.sin(tt * 23) * math.sin(tt * 7.3)
    for lx, ly, r, s in ((0.44 - 0.5 * k * .3, 0.40, 300, 110), (0.9, 0.47, 160, 50)):
        gl = np.exp(-(((xx - lx * W) ** 2 + (yy - ly * H) ** 2) / (2 * r * r))) * s * fl
        a += np.asarray(Image.fromarray(gl.astype(np.float32)).resize((W, H), Image.BILINEAR))
    # grain
    n = rng.integers(-22, 22, (H // 2, W // 2)).astype(np.float32); a += np.kron(n, np.ones((2, 2), np.float32))
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")
    # rain
    rl = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(rl)
    for _ in range(230):
        x = rng.integers(-100, W + 100); y = rng.integers(-100, H); L = rng.integers(40, 110)
        rd.line([(x, y), (x - L * .22, y + L)], fill=int(rng.integers(60, 150)), width=2)
    ov = Image.new("RGBA", (W, H), (255, 255, 255, 0)); ov.putalpha(rl.point(lambda v: int(v * .55))); im.alpha_composite(ov)
    return im

def blinds(im, k):
    ov = Image.new("L", (W, H), 0); d = ImageDraw.Draw(ov)
    for i in range(-6, 30):
        y = i * 96 + 30; d.polygon([(0, y), (W, y - 140), (W, y - 140 + 44), (0, y + 44)], fill=int(120 * k))
    o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); o.putalpha(ov.filter(ImageFilter.GaussianBlur(5))); im.alpha_composite(o)

def typed(d, xy, text, f, tt, t0, cps=22, fill=(255, 255, 255, 255), anchor="mm"):
    n = int(max(0, tt - t0) * cps)
    if n <= 0: return
    full = d.textlength(text, font=f); x = xy[0] - full / 2
    d.text((x, xy[1]), text[:n] + ("█" if n < len(text) and int(tt * 4) % 2 else ""), font=f, fill=fill, anchor="lm", stroke_width=5, stroke_fill=(0, 0, 0, 255))

def frame(n):
    tt = n / FPS
    cur = next((s for s in segs if s["t0"] <= tt <= s["t1"] + 0.3), None)
    if tt < NOIR0:
        sh = [s for s in SHOTS if s[0] <= tt][-1]; nxt = next((s[0] for s in SHOTS if s[0] > tt), NOIR0)
        k = (tt - sh[0]) / max(0.1, nxt - sh[0])
        im = kb(sh[1], k, *sh[2:])
        im = ImageEnhance.Color(im).enhance(1.12)
        # crossfade from previous shot
        if tt - sh[0] < 0.3 and sh is not SHOTS[0]:
            pv = SHOTS[SHOTS.index(sh) - 1]; pim = kb(pv[1], 1.0, *pv[2:]); im = Image.blend(pim, im, (tt - sh[0]) / 0.3)
        im = Image.composite(im, Image.new("RGB", (W, H), (6, 4, 3)), VIG).convert("RGBA")
        im.alpha_composite(BOTTOM)
        if tt < INTRO:
            d = ImageDraw.Draw(im); a = int(255 * min(1, tt / .5) * min(1, (INTRO - tt) / .4))
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
            od.rectangle((0, 760, W, 1180), fill=(8, 5, 3, int(a * .72)))
            f = ImageFont.truetype(SERIF, 124)
            od.text((W / 2, 880), "LOST IN", font=f, fill=GOLD + (a,), anchor="mm"); od.text((W / 2, 1020), "ATHENS", font=f, fill=GOLD + (a,), anchor="mm")
            od.text((W / 2, 1126), "a Hardwood Bricks road picture", font=inter("SemiBold", 36), fill=(240, 232, 215, a), anchor="mm")
            im.alpha_composite(ov)
        else:
            topbar(im, False)
        if cur and not (cur["i"] == 0 and tt >= SHOTS[3][0]):   # shot 02 is the real Matthew: no cutout
            c = CAST[cur["spk"]]; k = min(1, (tt - cur["t0"] + .15) / .35); e = 1 - (1 - k) ** 3
            side = {"matthew": 0, "bumrod": 1, "cynthia": 1}[cur["spk"]]
            x = int(-c.width + (c.width + 10) * e) if side == 0 else int(W - (c.width + 10) * e)
            bob = int(4 * math.sin(tt * 2.2))
            shadowed(im, c, x, H - c.height + 40 + bob)
        if cur: nameplate(im, cur["spk"], min(1, (tt - cur["t0"] + .15) / .3))
        for t0, t1, text, col in CHIPS:
            if t0 <= tt <= t1: chip(im, text, col, tt - t0)
        if cur: draw_caption(im, cur, tt, False)
        fo = (tt - (NOIR0 - 0.7)) / 0.7
        if fo > 0: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * min(1, fo)))))
        return im.convert("RGB")
    # ---------- noir ----------
    im = noir_bg(tt); d = ImageDraw.Draw(im)
    # the three of them under the lamp
    kin = min(1, (tt - NOIR0) / 1.2)
    for spk, x, yb, in (("bumrod", 330, 60), ("matthew", -40, 30), ("cynthia", 560, 30)):
        c = NCAST[spk]
        if cur and cur["spk"] != spk: c = ImageEnhance.Brightness(c).enhance(.55)
        elif not cur: c = ImageEnhance.Brightness(c).enhance(.7)
        shadowed(im, c, x, H - c.height + yb)
    fog = Image.new("RGBA", (W, H), (0, 0, 0, 0)); fd = ImageDraw.Draw(fog)
    for y in range(1500, H): fd.line([(0, y), (W, y)], fill=(0, 0, 0, int(230 * ((y - 1500) / 420) ** 1.4)))
    im.alpha_composite(fog)
    blinds(im, 0.55)
    im2 = Image.composite(im.convert("RGB"), Image.new("RGB", (W, H), (0, 0, 0)), VIG).convert("RGBA"); im = im2; d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 96), fill=(0, 0, 0, 255)); d.rectangle((0, H - 96, W, H), fill=(0, 0, 0, 255))
    if tt < segs[7]["t0"] - 0.1:
        typed(d, (W / 2, 420), "COURT STREET. 11:47 P.M.", ImageFont.truetype(MONO, 50), tt, NOIR0 + 0.5)
        typed(d, (W / 2, 500), "NO GAME. NO LEADS.", ImageFont.truetype(MONO, 50), tt, NOIR0 + 1.6)
    if cur and tt < END0:
        draw_caption(im, cur, tt, True)
        d.text((W / 2, 400), SPK[cur["spk"]]["name"].upper(), font=inter("Bold", 30), fill=(200, 200, 200, 255), anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0, 255))
    if tt >= END0:
        k = min(1, (tt - END0) / 0.8); ov = Image.new("RGBA", (W, H), (0, 0, 0, int(150 * k))); od = ImageDraw.Draw(ov); a = int(255 * k)
        f = ImageFont.truetype(SERIF, 120)
        od.text((W / 2, 520), "LOST IN", font=f, fill=(245, 245, 245, a), anchor="mm"); od.text((W / 2, 660), "ATHENS", font=f, fill=(245, 245, 245, a), anchor="mm")
        od.text((W / 2, 780), "f i n", font=ImageFont.truetype(MONO, 44), fill=(220, 220, 220, a), anchor="mm")
        for j, ln in enumerate(["Photos: Matthew Hagan, Athens, Ohio", "Matthew and Pastor Bumrod: AI models of Matthew's voice",
                                "Cynthia: a synthetic voice. Pastor Bumrod is fictional.", "No coal-based baby formula was ever sold. We think."]):
            od.text((W / 2, 900 + j * 46), ln, font=inter("Medium", 28), fill=(215, 215, 215, a), anchor="mm")
        od.text((W / 2, 1120), "hardwoodbricks.com", font=inter("ExtraBold", 44), fill=GOLD + (a,), anchor="mm")
        im.alpha_composite(ov)
    fi = (tt - NOIR0) / 0.8
    if fi < 1: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - max(0, fi))))))
    fo = (TOTAL - tt) / 1.2
    if fo < 1: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - max(0, fo))))))
    return im.convert("RGB")

if "--frame" in sys.argv:
    for t in sys.argv[sys.argv.index("--frame") + 1].split(","):
        t = float(t) if not t.startswith("s") else mid(segs[int(t[1])], float(t.split(":")[1]))
        frame(int(t * FPS)).resize((540, 960)).save(OUT.with_suffix(f".{t:.1f}.png"))
    sys.exit()
if "--still" in sys.argv:
    t = sys.argv[sys.argv.index("--still") + 1]; t = mid(segs[int(t[1])], float(t.split(":")[1])); frame(int(t * FPS)).save(OUT.with_suffix(".still.png")); sys.exit()

N = int(TOTAL * FPS)
p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                      "-i", str(apath), "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
                      "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
for n in range(N):
    p.stdin.write(frame(n).tobytes())
    if n % 300 == 0: print(n, "/", N, file=sys.stderr, flush=True)
p.stdin.close(); p.wait(); print("wrote", OUT, file=sys.stderr)
