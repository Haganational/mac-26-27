"""Render 'Lost in Athens, part two' (1080x1920): noir panels, then a full-color Miami finale.

python athens2.py <voices_dir> <out.mp4> [--frame T,..]
Finale footage: finale.json = {"craig": {...}, "cuts": [{"dir": frames_dir, "beats": n}, ...]}
(frames pre-extracted at 30 fps, 1080x1920 JPEGs named %04d.jpg).
"""
import glob, json, math, subprocess, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H, FPS, SR = 1080, 1920, 30, 24000
HERE = Path(__file__).parent
SET = Path("/mnt/project-files/video/studio-set")
DLG = json.load(open(HERE / "dialogue.json"))
FIN = json.load(open(HERE / "finale.json"))
VOX = Path(sys.argv[1]); OUT = Path(sys.argv[2])
SPEED = 1.17
rng = np.random.default_rng(5)

def inter(w, s, disp=False): return ImageFont.truetype(f"/usr/share/fonts/opentype/inter/Inter{'Display' if disp else ''}-{w}.otf", s)
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
MONO = subprocess.run(["fc-match", "-f", "%{file}", "JetBrains Mono:bold"], capture_output=True, text=True).stdout
GOLD = (236, 196, 106)
NAMES = {"matthew": "MATTHEW HAGAN", "bumrod": "PASTOR RODNEY BUMROD", "cynthia": "CYNTHIA SIAKAM", "craig": "CRAIG SHORES"}

# ---------- audio ----------
def read(p, speed):
    tmp = HERE / "_t.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(p), "-af", f"atempo={speed}", "-ac", "1", "-ar", str(SR), str(tmp)], check=True)
    with wave.open(str(tmp)) as w: a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    idx = np.nonzero(np.abs(a) > 0.012)[0]
    if len(idx): a = a[max(0, idx[0] - 1000): idx[-1] + 2000]
    return (a * (0.89 / (np.abs(a).max() or 1))).astype(np.float32)

wavs = sorted(VOX.glob("*.wav")); assert len(wavs) == len(DLG["lines"]), len(wavs)
INTRO = 2.2
GAP = {i: 0.22 for i in range(1, 14)}; GAP.update({1: .35, 4: .12, 6: .1, 7: .3, 8: .15, 9: .3, 10: .35, 11: .3, 13: .15})
segs, t = [], INTRO
voice = np.zeros(int(400 * SR), np.float32)
for i, (p, (spk, text)) in enumerate(zip(wavs[:-1], DLG["lines"][:-1])):
    t += GAP.get(i, 0)
    a = read(p, SPEED); voice[int(t * SR): int(t * SR) + len(a)] += a
    segs.append(dict(i=i, spk=spk, text=text, t0=t, t1=t + len(a) / SR, a=a)); t += len(a) / SR
RING0 = t + 0.5                 # black: phone rings
T0 = RING0 + 2.3                # smash cut to Miami
BEAT = 60 / 124
CRAIG_LEN = BEAT * 6
ca = read(wavs[-1], 1.0); CR0 = T0 + 1.15
voice[int(CR0 * SR): int(CR0 * SR) + len(ca)] += ca * 1.0
craig = dict(i=14, spk="craig", text="Hello?", t0=CR0, t1=CR0 + len(ca) / SR, a=ca)
M0 = T0 + CRAIG_LEN             # the drop: panels slam in
TITLE0 = M0 + FIN["title_beat"] * BEAT
TOTAL = M0 + FIN["total_beats"] * BEAT + 0.5
voice = voice[: int(TOTAL * SR)]
print(f"duration {TOTAL:.1f}s ring {RING0:.1f} miami {T0:.1f} drop {M0:.1f} finale {TOTAL - T0:.1f}s", file=sys.stderr)

def hz(m): return 440 * 2 ** ((m - 69) / 12)
def noir_music(n):
    out = np.zeros(n + SR * 6, np.float32); beat = 60 / 66
    def add(sig, t0, g):
        i = int(t0 * SR)
        if 0 <= i < n: out[i: i + len(sig)] += sig[: len(out) - i] * g
    def pluck(m, d=0.9):
        tt = np.arange(int(d * SR)) / SR; f = hz(m)
        return ((np.sin(2 * np.pi * f * tt) + 0.45 * np.sin(4 * np.pi * f * tt) + 0.18 * np.sin(6 * np.pi * f * tt)) * np.exp(-tt * 4.2) * np.minimum(1, tt * 200)).astype(np.float32)
    def keys(ms, d=3.4):
        tt = np.arange(int(d * SR)) / SR; s = 0
        for m in ms: s = s + np.sin(2 * np.pi * hz(m) * tt)
        return (s / len(ms) * np.exp(-tt * 1.1) * (1 + 0.25 * np.sin(2 * np.pi * 4.6 * tt)) * np.minimum(1, tt * 60)).astype(np.float32)
    def horn(m, d):
        tt = np.arange(int(d * SR)) / SR; f = hz(m) * (1 + 0.006 * np.sin(2 * np.pi * 5.2 * tt) * np.minimum(1, tt * 2))
        ph = 2 * np.pi * np.cumsum(f) / SR; s = sum(np.sin(k * ph) / k ** 1.5 for k in range(1, 7))
        return (s * np.minimum(1, tt * 9) * np.minimum(1, (d - tt) * 5)).astype(np.float32)
    def brush(d=0.22):
        x = rng.normal(0, 1, int(d * SR)).astype(np.float32); x = x - np.convolve(x, np.ones(6) / 6, "same")
        tt = np.arange(len(x)) / SR; return x * np.sin(np.pi * tt / d) ** 2
    bars = [([38, 41, 45, 48], [50, 53, 57, 60, 64]), ([34, 38, 41, 45], [46, 50, 53, 57]), ([31, 34, 38, 41], [43, 46, 50, 53]), ([33, 37, 40, 45], [45, 49, 52, 55, 58])]
    b = 0
    while b * beat < n / SR:
        tm = b * beat; bar = bars[(b // 4) % 4]
        add(pluck(bar[0][b % 4]), tm, 0.11)
        if b % 4 == 0: add(keys(bar[1]), tm + 0.02, 0.06)
        add(brush(), tm + (beat * 0.5 if b % 2 else 0), 0.02)
        b += 1
    mel = [(69, 2.5), (65, 1), (62, 2.5), (None, 2), (64, 1.5), (65, .5), (64, 1), (57, 3), (None, 3), (62, 1), (65, 1), (69, 1.5), (72, .5), (70, 3), (None, 3)]
    tm, k = 0.5, 0
    while tm < n / SR - 2:
        m, d = mel[k % len(mel)]; d *= beat
        if m: add(horn(m, d * 0.96), tm, 0.03)
        tm += d; k += 1
    r = rng.normal(0, 1, n).astype(np.float32); r = np.convolve(r, np.ones(5) / 5, "same") - np.convolve(r, np.ones(80) / 80, "same")
    out = out[:n] + r * 0.07
    tt = np.arange(n) / SR
    return out * np.clip(tt / 1.0, 0, 1) * np.clip((n / SR - tt) / 0.25, 0, 1)

def ring(d=2.2):
    tt = np.arange(int(d * SR)) / SR
    s = (np.sin(2 * np.pi * 440 * tt) + np.sin(2 * np.pi * 480 * tt)) * 0.5
    env = ((tt % 1.1) < 0.75).astype(np.float32); env = np.convolve(env, np.ones(200) / 200, "same")
    s = s * env; s = s - np.convolve(s, np.ones(12) / 12, "same") * 0.6      # thin, telephone-ish
    return (s * 0.22).astype(np.float32)

def miami_music(d):
    """Original 80s Miami freestyle: gated drums, congas, clave, synth brass, piano montuno."""
    n = int(d * SR); out = np.zeros(n + SR * 4, np.float32)
    def add(sig, t0, g):
        i = int(t0 * SR)
        if 0 <= i < n: out[i: i + len(sig)] += sig[: len(out) - i] * g
    def saw(f, tt, h=10): return sum(np.sin(2 * np.pi * f * k * tt) / k for k in range(1, h + 1))
    def kick():
        tt = np.arange(int(.3 * SR)) / SR; f = 45 + 110 * np.exp(-tt * 28)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9)).astype(np.float32)
    def snare():
        tt = np.arange(int(.34 * SR)) / SR; x = rng.normal(0, 1, len(tt)).astype(np.float32)
        x = x - np.convolve(x, np.ones(10) / 10, "same")
        gate = np.where(tt < .26, 1.0, 0.0) * (0.35 + 0.65 * np.exp(-tt * 14))
        return (x * gate + np.sin(2 * np.pi * 190 * tt) * np.exp(-tt * 22) * 1.2).astype(np.float32)
    def hat():
        x = rng.normal(0, 1, int(.05 * SR)).astype(np.float32); x = np.diff(x, prepend=0)
        return x * np.exp(-np.arange(len(x)) / SR * 90)
    def conga(f, dd=.16):
        tt = np.arange(int(dd * SR)) / SR; ff = f * (1 + 0.25 * np.exp(-tt * 60))
        return (np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-tt * 26) * np.minimum(1, tt * 900)).astype(np.float32)
    def clave():
        tt = np.arange(int(.06 * SR)) / SR; return (np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 70)).astype(np.float32)
    def bell():
        tt = np.arange(int(.12 * SR)) / SR; return ((np.sign(np.sin(2 * np.pi * 810 * tt)) + np.sign(np.sin(2 * np.pi * 545 * tt))) * np.exp(-tt * 30) * .5).astype(np.float32)
    def bass(m, dd):
        tt = np.arange(int(dd * SR)) / SR; return (saw(hz(m), tt, 6) * np.exp(-tt * 6) * np.minimum(1, tt * 300)).astype(np.float32)
    def brass(ms, dd):
        tt = np.arange(int(dd * SR)) / SR; s_ = 0
        for m in ms: s_ = s_ + saw(hz(m) * 1.004, tt, 8) + saw(hz(m) * 0.996, tt, 8)
        return (s_ / len(ms) * np.minimum(1, tt * 40) * np.minimum(1, (dd - tt) * 30) * (0.75 + 0.25 * np.exp(-tt * 8))).astype(np.float32)
    def piano(m, dd=.22):
        tt = np.arange(int(dd * SR)) / SR; f = hz(m)
        return ((np.sin(2 * np.pi * f * tt) + .5 * np.sin(4 * np.pi * f * tt) + .25 * np.sin(6 * np.pi * f * tt)) * np.exp(-tt * 11) * np.minimum(1, tt * 500)).astype(np.float32)
    def pad(ms, dd):
        tt = np.arange(int(dd * SR)) / SR; s_ = 0
        for m in ms: s_ = s_ + saw(hz(m) * 1.003, tt, 5) + saw(hz(m) * 0.997, tt, 5)
        return (s_ / len(ms) * np.minimum(1, tt / (dd * .5)) * np.minimum(1, (dd - tt) * 6)).astype(np.float32)
    chords = [(45, [57, 60, 64]), (43, [55, 59, 62]), (41, [53, 57, 60]), (40, [56, 59, 64])]      # Am G F E
    # Craig's moment: surf and a rising pad, no drums
    tt = np.arange(int(CRAIG_LEN * SR)) / SR
    sea = rng.normal(0, 1, len(tt)).astype(np.float32); sea = np.convolve(sea, np.ones(40) / 40, "same")
    add(sea * (0.5 + 0.5 * np.sin(2 * np.pi * tt / 2.8 - 1)) * 1.6, 0, 0.5)
    add(pad([57, 64, 69, 72], CRAIG_LEN), 0, 0.05)
    for k in range(8):                                                    # timbale fill into the drop
        add(conga(330 - k * 18, .12), CRAIG_LEN - BEAT * 2 + k * BEAT / 4, 0.16 + k * 0.02); add(hat(), CRAIG_LEN - BEAT * 2 + k * BEAT / 4, 0.12)
    d0 = CRAIG_LEN; nb = int((d - d0) / BEAT) + 1; s16 = BEAT / 4
    tumbao = [(2, 300), (3, 300), (6, 210), (7, 210), (10, 300), (11, 300), (14, 250), (15, 210)]
    clv = [0, 3, 6, 10, 12]                                               # 3-2 son clave, in 16ths over two beats x2
    mont = [0, 2, 3, 5, 6, 8, 10, 11, 13, 14]
    for bar in range(nb // 4 + 1):
        tb = d0 + bar * 4 * BEAT; root, ch = chords[bar % 4]
        for b in range(4):
            tm = tb + b * BEAT
            add(kick(), tm, 0.55)
            if b % 2 == 1: add(snare(), tm, 0.30)
            add(hat(), tm + BEAT / 2, 0.10); add(bell(), tm, 0.05)
            add(bass(root - 12, BEAT * .45), tm, 0.17); add(bass(root, BEAT * .3), tm + BEAT * .75, 0.13)
        for st, f in tumbao: add(conga(f), tb + st * s16, 0.13)
        for st in clv: add(clave(), tb + st * s16 * (16 / 16), 0.07)
        for j, st in enumerate(mont): add(piano(ch[j % 3] + 12 + (12 if j % 4 == 3 else 0)), tb + st * s16, 0.06)
        for st, dd in ((0, 1.2), (6, .8), (11, 1.6)): add(brass([m + 12 for m in ch] + [ch[0] + 24], s16 * dd * 1.6), tb + st * s16, 0.035)
        add(pad(ch, BEAT * 4), tb, 0.025)
    out = out[:n]; tt = np.arange(n) / SR
    return out * np.clip((d - tt) / 0.5, 0, 1)

mix = voice.copy()
nm = noir_music(int((RING0 + 0.15) * SR)); mix[: len(nm)] += nm
rg = ring(); mix[int((RING0 + 0.1) * SR): int((RING0 + 0.1) * SR) + len(rg)] += rg
mm = miami_music(TOTAL - T0); i0 = int(T0 * SR); mix[i0: i0 + len(mm)] += mm[: len(mix) - i0]
mix = np.tanh(mix * 1.05) / 1.05
apath = OUT.with_suffix(".wav")
with wave.open(str(apath), "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())

# ---------- noir body ----------
PH = {}
def photo(n):
    if n not in PH:
        im = ImageOps.exif_transpose(Image.open(glob.glob(str(HERE / f"raw/athens/{n}_*.jpg"))[0])).convert("RGB")
        s = max(W / im.width, H / im.height) * 1.3
        PH[n] = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    return PH[n]
def kb(n, k, cx0, cx1, cy0=.5, cy1=.5, z0=1.0, z1=1.12):
    im = photo(n); z = z0 + (z1 - z0) * k; cw, ch = W * 1.3 / z, H * 1.3 / z
    cx = (cx0 + (cx1 - cx0) * k) * im.width; cy = (cy0 + (cy1 - cy0) * k) * im.height
    x = min(max(cx - cw / 2, 0), im.width - cw); y = min(max(cy - ch / 2, 0), im.height - ch)
    return im.crop((int(x), int(y), int(x + cw), int(y + ch))).resize((W, H), Image.BILINEAR)

S = segs
PANELS = [  # (start, photo, kb args, lamp (x, y) or None, chapter card)
    (0, "19", (.14, .30, .5, .5, 1.0, 1.10), (.44, .40)),
    (S[3]["t0"] - .12, "11", (.5, .5, .62, .48, 1.0, 1.10), None),
    (S[7]["t0"] - .12, "13", (.30, .50, .5, .5, 1.0, 1.10), (.62, .30)),
    (S[11]["t0"] - .12, "03", (.42, .52, .42, .36, 1.0, 1.12), None),
]
CHIPS = [
    (S[0]["t0"] + (S[0]["t1"] - S[0]["t0"]) * .45, S[0]["t1"] + .2, "WED 6:30 PM  ·  GREAT LAKES CHRISTIAN at EASTERN MICHIGAN  ·  YPSILANTI"),
    (S[4]["t0"], S[4]["t1"] + .3, "VIEWERS: 0"),
    (S[7]["t0"] + .8, S[10]["t1"] + .2, "1989 NISSAN SENTRA  ·  CIGARETTE LIGHTER: YES  ·  USB-C: NO"),
    (S[11]["t0"] + 1.0, S[13]["t1"] + .2, "COURT STREET APARTMENTS  ·  LAST KNOWN TENANT: CRAIG, c. 1996"),
]
def cut(name, h, crop=None):
    c = Image.open(SET / f"cutout-{name}.png"); c = c.crop(c.getbbox())
    if crop: c = c.crop((0, 0, c.width, int(c.height * crop)))
    return c.resize((int(c.width * h / c.height), h), Image.LANCZOS)
def noirize(c):
    a = c.getchannel("A"); g = ImageOps.autocontrast(c.convert("L"), cutoff=2)
    g = ImageEnhance.Contrast(g).enhance(1.5); g = ImageEnhance.Brightness(g).enhance(.8)
    return Image.merge("RGBA", (g, g, g, a))
NCAST = {"matthew": noirize(cut("matthew", 760, .62)), "bumrod": noirize(cut("bumrod", 1300, .62)), "cynthia": noirize(cut("cynthia", 840, .78))}
DIM = {k: ImageEnhance.Brightness(v).enhance(.5) for k, v in NCAST.items()}
def shadowed(im, c, x, y):
    sh = Image.new("RGBA", c.size, (0, 0, 0, 0)); sh.putalpha(c.getchannel("A").point(lambda v: int(v * .6)))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)), (x + 16, y + 10)); im.alpha_composite(c, (x, y))
VIG = Image.new("L", (W, H), 0); ImageDraw.Draw(VIG).ellipse((-W * .35, -H * .2, W * 1.35, H * 1.2), fill=255); VIG = VIG.filter(ImageFilter.GaussianBlur(220))
BLINDS = Image.new("L", (W, H), 0); _d = ImageDraw.Draw(BLINDS)
for i in range(-6, 30): _d.polygon([(0, i * 96 + 30), (W, i * 96 - 110), (W, i * 96 - 66), (0, i * 96 + 74)], fill=66)
BLINDS = BLINDS.filter(ImageFilter.GaussianBlur(5))
FOG = Image.new("RGBA", (W, H), (0, 0, 0, 0)); _d = ImageDraw.Draw(FOG)
for y in range(1500, H): _d.line([(0, y), (W, y)], fill=(0, 0, 0, int(230 * ((y - 1500) / 420) ** 1.4)))
CAPN = ImageFont.truetype(MONO, 52)

def caption_chunks(seg):
    txt = seg["text"].replace("A Sun", "ASUN").replace("U S B C", "USB-C").replace("nineteen eighty nine", "1989").replace("six thirty", "6:30").replace("Mister", "Mr.")
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
def draw_caption(im, seg, tt):
    d = ImageDraw.Draw(im); chunk = None
    for c in seg["caps"]:
        if c[0][1] <= tt: chunk = c
    if not chunk: return
    lines, cur = [], []
    for w_ in chunk:
        if cur and d.textlength(" ".join(x[0] for x in cur + [w_]), font=CAPN) > W - 120: lines.append(cur); cur = [w_]
        else: cur.append(w_)
    if cur: lines.append(cur)
    y0 = 560 - (len(lines) - 1) * 40
    for ln in lines:
        x = (W - d.textlength(" ".join(x[0] for x in ln), font=CAPN)) / 2
        for w_, a, b in ln:
            if a > tt: break
            d.text((x, y0), w_, font=CAPN, fill=(255, 255, 255), anchor="lm", stroke_width=7, stroke_fill=(0, 0, 0)); x += d.textlength(w_ + " ", font=CAPN)
        y0 += 80

def typed(d, y, text, f, tt, t0, cps=24):
    n = int(max(0, tt - t0) * cps)
    if n <= 0: return
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text[:n] + ("█" if n < len(text) and int(tt * 4) % 2 else ""), font=f, fill=(255, 255, 255, 255), anchor="lm", stroke_width=5, stroke_fill=(0, 0, 0, 255))

def noir_frame(tt):
    pi = max(i for i, p in enumerate(PANELS) if p[0] <= tt); p = PANELS[pi]
    nxt = PANELS[pi + 1][0] if pi + 1 < len(PANELS) else RING0
    k = (tt - p[0]) / max(.1, nxt - p[0])
    g = kb(p[1], k, *p[2]).convert("L")
    g = ImageOps.autocontrast(g, cutoff=1); g = ImageEnhance.Contrast(g).enhance(1.7); g = ImageEnhance.Brightness(g).enhance(0.40)
    a = np.asarray(g).astype(np.float32)
    if p[3]:
        yy, xx = np.mgrid[0:H:8, 0:W:8]; fl = 0.85 + 0.15 * math.sin(tt * 23) * math.sin(tt * 7.3)
        gl = np.exp(-(((xx - p[3][0] * W) ** 2 + (yy - p[3][1] * H) ** 2) / (2 * 300 * 300))) * 110 * fl
        a += np.asarray(Image.fromarray(gl.astype(np.float32)).resize((W, H), Image.BILINEAR))
    n = rng.integers(-26, 26, (H // 2, W // 2)).astype(np.float32); a += np.kron(n, np.ones((2, 2), np.float32))
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")
    rl = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(rl)
    for _ in range(230):
        x = rng.integers(-100, W + 100); y = rng.integers(-100, H); L = rng.integers(40, 110)
        rd.line([(x, y), (x - L * .22, y + L)], fill=int(rng.integers(60, 150)), width=2)
    ov = Image.new("RGBA", (W, H), (255, 255, 255, 0)); ov.putalpha(rl.point(lambda v: int(v * .55))); im.alpha_composite(ov)
    cur = next((s for s in segs if s["t0"] <= tt <= s["t1"] + 0.2), None)
    for spk, x, yb in (("bumrod", 330, 60), ("matthew", -40, 30), ("cynthia", 560, 30)):
        c = NCAST[spk] if (cur and cur["spk"] == spk) else DIM[spk]
        shadowed(im, c, x, H - c.height + yb)
    im.alpha_composite(FOG)
    o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); o.putalpha(BLINDS); im.alpha_composite(o)
    im = Image.composite(im.convert("RGB"), Image.new("RGB", (W, H), (0, 0, 0)), VIG).convert("RGBA"); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 96), fill=(0, 0, 0, 255)); d.rectangle((0, H - 96, W, H), fill=(0, 0, 0, 255))
    if tt < segs[0]["t0"] + 0.4:
        typed(d, 300, "LOST IN ATHENS", ImageFont.truetype(MONO, 64), tt, 0.3)
        typed(d, 380, "PART TWO", ImageFont.truetype(MONO, 44), tt, 1.1)
    # low battery: the only color in the noir
    if S[7]["t0"] <= tt <= S[10]["t1"] + .3 and int(tt * 2.5) % 2 == 0:
        d.rounded_rectangle((W - 250, 130, W - 70, 200), 10, outline=(255, 40, 40, 255), width=5); d.rectangle((W - 68, 150, W - 58, 180), fill=(255, 40, 40, 255))
        d.rectangle((W - 240, 140, W - 222, 190), fill=(255, 40, 40, 255)); d.text((W - 160, 232), "CYNTHIA 2%", font=inter("Bold", 26), fill=(255, 60, 60, 255), anchor="mm")
    for t0, t1, text in CHIPS:
        if t0 <= tt <= t1:
            f = inter("Bold", 28)
            while d.textlength(text, font=f) > W - 110: f = inter("Bold", f.size - 1)
            tw = d.textlength(text, font=f); d.rectangle(((W - tw) / 2 - 20, 1690, (W + tw) / 2 + 20, 1750), fill=(0, 0, 0, 220), outline=(230, 230, 230, 255), width=2)
            d.text((W / 2, 1720), text, font=f, fill=(240, 240, 240, 255), anchor="mm")
    if cur:
        draw_caption(im, cur, tt)
        d.text((W / 2, 440), NAMES[cur["spk"]], font=inter("Bold", 30), fill=(200, 200, 200, 255), anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0, 255))
    if pi and tt - p[0] < 0.1: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - (tt - p[0]) / 0.1)))))   # hard panel cut with a blink
    if tt < 0.6: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - tt / 0.6)))))
    return im.convert("RGB")

def ring_frame(tt):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    typed(d, 860, "CALLING CRAIG...", ImageFont.truetype(MONO, 60), tt, RING0 + 0.15)
    typed(d, 950, "MIAMI, FLA.", ImageFont.truetype(MONO, 44), tt, RING0 + 1.0)
    n = rng.integers(0, 16, (H // 4, W // 4)).astype(np.uint8)
    g = Image.fromarray(np.kron(n, np.ones((4, 4), np.uint8))).convert("RGB")
    return Image.fromarray(np.clip(np.asarray(im.convert("RGB")).astype(np.int16) + np.asarray(g), 0, 255).astype(np.uint8))

# ---------- Miami ----------
RAMP = np.array([[30, 14, 84], [112, 56, 170], [226, 72, 150], [255, 118, 104], [255, 178, 98], [255, 238, 206]], np.float32)   # indigo, lavender, pink, coral, orange, cream
def miami_grade(arr, amt=.34, sat=1.4, bloom=.5, tint=None):
    a = arr.astype(np.float32); h, w = a.shape[:2]; lum = (a @ np.array([.3, .59, .11], np.float32))[..., None]
    a = lum + (a - lum) * sat
    x = np.clip(lum[..., 0] / 255, 0, 1) * (len(RAMP) - 1); i = np.clip(x.astype(int), 0, len(RAMP) - 2); f = (x - i)[..., None]
    a = a * (1 - amt) + (RAMP[i] * (1 - f) + RAMP[i + 1] * f) * amt
    if tint is not None: a = a * (1 - .12) + np.array(tint, np.float32) * .12
    a = (a - 128) * 1.14 + 134
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    if bloom:
        sm = im.resize((w // 8, h // 8), Image.BILINEAR); b_ = np.clip(np.asarray(sm).astype(np.float32) - 165, 0, 255) * 2.2
        bl = Image.fromarray(b_.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)).resize((w, h), Image.BILINEAR)
        im = Image.fromarray((np.asarray(im).astype(np.float32) + np.asarray(bl).astype(np.float32) * bloom).clip(0, 255).astype(np.uint8))
    return im

FRAMES = {}
def clip_frame(name, t, rate=1.0):
    fs = FRAMES.setdefault(name, sorted(glob.glob(str(HERE / "cuts" / name / "*.jpg"))))
    return Image.open(fs[min(len(fs) - 1, int(t * FPS * rate))]).convert("RGB")

def letterspaced(d, xy, text, f, fill, sp):
    tw = sum(d.textlength(ch, font=f) for ch in text) + sp * (len(text) - 1); x = xy[0] - tw / 2
    for ch in text: d.text((x, xy[1]), ch, font=f, fill=fill, anchor="lm", stroke_width=3, stroke_fill=(30, 8, 60, 255)); x += d.textlength(ch, font=f) + sp

def neon(im, text, y, size, col, glowcol):
    f = inter("BlackItalic", size, disp=True); L = Image.new("L", (W, 400), 0); d = ImageDraw.Draw(L)
    d.text((W / 2, 200), text, font=f, fill=255, anchor="mm")
    for r, a in ((30, .95), (10, .9)):
        g = Image.new("RGBA", (W, 400), glowcol + (0,)); g.putalpha(L.filter(ImageFilter.GaussianBlur(r)).point(lambda v: int(min(255, v * 1.7) * a))); im.alpha_composite(g, (0, y - 200))
    out = Image.new("RGBA", (W, 400), (0, 0, 0, 0)); od = ImageDraw.Draw(out)
    od.text((W / 2 + 6, 208), text, font=f, fill=(40, 10, 70, 255), anchor="mm")
    od.text((W / 2, 200), text, font=f, fill=col + (255,), anchor="mm", stroke_width=3, stroke_fill=(255, 255, 255, 255))
    im.alpha_composite(out, (0, y - 200))

_SIL = None
def craig_sil(sway, yo=0):
    """A long-haired figure with a phone to his ear, cut from a real body outline."""
    global _SIL
    if _SIL is None:
        c = Image.open(SET / "cutout-bumrod.png"); c = c.crop(c.getbbox()).getchannel("A")
        c = c.resize((int(c.width * .6), int(c.height * .6)), Image.LANCZOS)
        im = Image.new("L", (W, H + 300), 0); im.paste(c, (222, 616))
        d = ImageDraw.Draw(im)
        d.ellipse((530, 560, 730, 700), fill=0)                                  # lose the sunglasses bump
        d.ellipse((498, 628, 760, 900), fill=255)
        d.polygon([(858, 1500), (948, 1470), (800, 850), (730, 880)], fill=255)  # forearm up to the ear
        d.ellipse((716, 800, 822, 930), fill=255)                                # hand
        d.polygon([(742, 742), (780, 736), (806, 900), (768, 908)], fill=255)    # phone
        _SIL = im.filter(ImageFilter.GaussianBlur(1.5))
    out = Image.new("L", (W, H), 0); out.paste(_SIL, (sway, 0)); return out

SKY = None; HORIZ = 763; SUN = (526, 600)
def craig_frame(t):
    global SKY
    if SKY is None:
        b = Image.open(HERE / "miami/bay-3.jpg").convert("RGB"); b = b.resize((1425, 2150), Image.LANCZOS)
        SKY = b.crop((172, 0, 172 + W, HORIZ + 60))
    im = Image.new("RGB", (W, H)); im.paste(SKY, (0, 0))
    oc = clip_frame("ocean", t)
    mask = Image.new("L", (W, 1160), 255); md = ImageDraw.Draw(mask)
    for y in range(50): md.line([(0, y), (W, y)], fill=int(255 * y / 50))
    im.paste(oc, (0, HORIZ), mask)
    a = np.asarray(im).astype(np.float32)
    # the sun's road on the water, broken up by the real waves
    yy = np.arange(HORIZ, H)[:, None]; xx = np.arange(W)[None, :]; dep = (yy - HORIZ) / (H - HORIZ)
    road = np.exp(-((xx - SUN[0]) ** 2) / (2 * (50 + 190 * dep) ** 2)) * (1 - dep * .45)
    lum = a[HORIZ:].mean(2, keepdims=True) / 255
    a[HORIZ:] += road[..., None] * (lum ** 1.5) * np.array([900, 420, 150], np.float32)
    a[HORIZ:] = a[HORIZ:] * (0.55 + 0.45 * road[..., None]) + np.array([40, 6, 30], np.float32) * (1 - road[..., None])
    z = 1 + 0.05 * t / CRAIG_LEN
    im = miami_grade(a.clip(0, 255), amt=.30, sat=1.35, bloom=.9).convert("RGBA")
    fl = Image.new("RGB", (W // 4, H // 4), (0, 0, 0)); fd = ImageDraw.Draw(fl); pul = 1 + 0.06 * math.sin(t * 6); sx, sy = SUN[0] / 4, SUN[1] / 4
    for r, col in ((170, (50, 14, 40)), (105, (110, 40, 50)), (60, (215, 110, 64)), (27, (255, 228, 188))):
        r *= pul; fd.ellipse((sx - r, sy - r, sx + r, sy + r), fill=col)
    fd.rectangle((0, sy - 2, W // 4, sy + 2), fill=(170, 80, 100))
    fl = fl.filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    a = np.asarray(im.convert("RGB")).astype(np.float32) + np.asarray(fl).astype(np.float32) * 0.95
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")
    sil = craig_sil(int(5 * math.sin(t * 1.3)))
    im.paste(Image.new("RGBA", (W, H), (10, 3, 14, 255)), (0, 0), sil)
    a = np.asarray(im.convert("RGB")).astype(np.float32) + np.asarray(fl).astype(np.float32) * 0.16     # a little light wrap
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    cw, ch = W / z, H / z; im = im.crop((int((W - cw) / 2), int((H - ch) * .35), int((W + cw) / 2), int((H - ch) * .35 + ch))).resize((W, H), Image.BILINEAR).convert("RGBA")
    d = ImageDraw.Draw(im); k = min(1, t / .4)
    d.rectangle((0, 1590, W, 1740), fill=(20, 6, 40, int(190 * k)))
    letterspaced(d, (W / 2, 1640), "CRAIG SHORES", inter("ExtraBold", 52), (255, 236, 200, int(255 * k)), 10)
    letterspaced(d, (W / 2, 1700), "BISCAYNE BAY  ·  MIAMI", inter("Medium", 28), (255, 150, 190, int(255 * k)), 6)
    if craig["t0"] - .05 <= T0 + t <= craig["t1"] + 1.2:
        d.text((W / 2, 330), "“Hello?”", font=inter("BlackItalic", 140, disp=True), fill=(255, 255, 255, 255), anchor="mm", stroke_width=8, stroke_fill=(60, 10, 80, 255))
    return im

ROWY = (36, 656, 1276); TINTS = ((255, 120, 170), (255, 150, 100), (180, 140, 255))
BACK = None
def backdrop():
    global BACK
    if BACK is None:
        b = Image.new("RGB", (W, H)); d = ImageDraw.Draw(b)
        for y in range(H):
            k = y / H; d.line([(0, y), (W, y)], fill=tuple(int(a + (c - a) * k) for a, c in zip((36, 12, 80), (236, 72, 150))))
        for i in range(-12, 13):
            ang = math.radians(-90 + i * 8); d.line([(W / 2, H + 200), (W / 2 + math.cos(ang) * 3000, H + 200 + math.sin(ang) * 3000)], fill=(255, 170, 120), width=6)
        BACK = b.filter(ImageFilter.GaussianBlur(1))
    return BACK.copy().convert("RGBA")

def title_overlay(im, t):
    k = min(1, t / .2); d = ImageDraw.Draw(im)
    im.alpha_composite(Image.new("RGBA", (W, 640), (26, 8, 58, int(205 * k))), (0, 640)); d = ImageDraw.Draw(im)
    for j, col in enumerate(((255, 110, 170), (255, 170, 110), (190, 150, 255))):
        d.rectangle((24 + j * 12, 646 + j * 12, W - 24 - j * 12, 1274 - j * 12), outline=col + (int(255 * k),), width=4)
    s = 1.3 - 0.3 * min(1, t / .16)
    neon(im, "MIAMI", 800, int(250 * s), (255, 96, 170), (255, 60, 150)); d = ImageDraw.Draw(im)
    if t > BEAT: letterspaced(d, (W / 2, 985), "THE ASUN DESK", inter("ExtraBold", 66), (255, 240, 214, 255), 12)
    if t > BEAT * 2: letterspaced(d, (W / 2, 1066), "WITH CRAIG SHORES", inter("SemiBold", 38), (120, 240, 235, 255), 9)
    if t > BEAT * 3:
        letterspaced(d, (W / 2, 1150), "COMING SOON", inter("Bold", 36), (255, 176, 96, 255), 14)
        d.text((W / 2, 1212), "hardwoodbricks.com/asun", font=inter("SemiBold", 32), fill=(255, 255, 255, 255), anchor="mm")
        d.text((W / 2, 1898), "All voices are AI. Pastor Bumrod and Craig Shores are fictional.", font=inter("Medium", 22), fill=(255, 235, 225, 255), anchor="mm", stroke_width=3, stroke_fill=(30, 8, 60, 255))

def miami_frame(tt):
    t = tt - T0
    if t < CRAIG_LEN:
        im = craig_frame(t)
        if t < 0.14: im.alpha_composite(Image.new("RGBA", (W, H), (255, 240, 230, int(255 * (1 - t / 0.14)))))
        return im.convert("RGB")
    mb = (tt - M0) / BEAT; im = backdrop(); d = ImageDraw.Draw(im)
    for r, row in enumerate(FIN["rows"]):
        for name, b0, nb in row:
            if b0 <= mb < b0 + nb or (mb >= b0 + nb and (name, b0, nb) == tuple(row[-1])):
                ct = (mb - b0) * BEAT; base = clip_frame(name, ct)
                g = miami_grade(np.asarray(base), amt=.32, sat=1.45, bloom=.55, tint=TINTS[r])
                sc = 1 + 0.22 * max(0, 1 - ct / .14)                               # slam in
                if sc > 1.001: g2 = g.resize((int(W * sc), int(608 * sc)), Image.BILINEAR); g = g2.crop(((g2.width - W) // 2, (g2.height - 608) // 2, (g2.width - W) // 2 + W, (g2.height - 608) // 2 + 608))
                im.paste(g, (0, ROWY[r]))
                if ct < 0.12: im.alpha_composite(Image.new("RGBA", (W, 608), (255, 230, 240, int(230 * (1 - ct / 0.12)))), (0, ROWY[r]))
                d = ImageDraw.Draw(im); d.rectangle((0, ROWY[r], W - 1, ROWY[r] + 607), outline=TINTS[r] + (255,), width=6)
                break
    sl = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(sl)
    for _ in range(22):
        y = int(rng.integers(0, H)); x = int(rng.integers(-200, W)); L = int(rng.integers(160, 520))
        sd.line([(x, y), (x + L, y)], fill=int(rng.integers(40, 120)), width=int(rng.integers(2, 5)))
    o = Image.new("RGBA", (W, H), (255, 225, 238, 0)); o.putalpha(sl.filter(ImageFilter.GaussianBlur(2))); im.alpha_composite(o)
    if tt >= TITLE0: title_overlay(im, tt - TITLE0)
    fo = (TOTAL - tt) / 0.3
    if fo < 1: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - max(0, fo))))))
    return im.convert("RGB")

def frame(n):
    tt = n / FPS
    if tt < RING0: return noir_frame(tt)
    if tt < T0: return ring_frame(tt)
    return miami_frame(tt)

if "--frame" in sys.argv:
    for t in sys.argv[sys.argv.index("--frame") + 1].split(","):
        t = {"T": T0, "M": M0, "E": TITLE0}.get(t[0], 0) + float(t[1:]) if t[0] in "TME" else float(t)
        frame(int(t * FPS)).resize((540, 960)).save(OUT.with_suffix(f".{t:.1f}.png"))
    sys.exit()
N = int(TOTAL * FPS)
p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                      "-i", str(apath), "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-maxrate", "3000k", "-bufsize", "6000k", "-pix_fmt", "yuv420p",
                      "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
for n in range(N):
    p.stdin.write(frame(n).tobytes())
    if n % 300 == 0: print(n, "/", N, file=sys.stderr, flush=True)
p.stdin.close(); p.wait(); print("wrote", OUT, file=sys.stderr)
