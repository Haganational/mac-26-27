"""Render 'Lost in Athens, part three' (1080x1920): noir apartment, TV static and test pattern,
a sitcom couch watching part two, then an anthem fade-out and a to-be-continued card.

python athens3.py <voices_dir> <out.mp4> [--frame T,..]
Needs beside it: dialogue.json, raw/athens/NN_*.jpg, ep2/%04d.jpg (part two from 60 s, 30 fps, 360x640),
ep2.wav, outro.json ([[image path, slug], ...]) and optional room.jpg, laugh.wav.
"""
import glob, json, math, subprocess, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
import audio3 as A

W, H, FPS, SR = 1080, 1920, 30, A.SR
HERE = Path(__file__).parent
SET = Path("/mnt/project-files/video/studio-set")
DLG = json.load(open(HERE / "dialogue.json")); OUTRO = json.load(open(HERE / "outro.json"))
VOX = Path(sys.argv[1]); OUT = Path(sys.argv[2])
rng = np.random.default_rng(5)
def inter(w, s, disp=False): return ImageFont.truetype(f"/usr/share/fonts/opentype/inter/Inter{'Display' if disp else ''}-{w}.otf", s)
MONO = subprocess.run(["fc-match", "-f", "%{file}", "JetBrains Mono:bold"], capture_output=True, text=True).stdout
CHARTER = subprocess.run(["fc-match", "-f", "%{file}", "Bitstream Charter:bold:italic"], capture_output=True, text=True).stdout
NAMES = {"matthew": "MATTHEW HAGAN", "bumrod": "PASTOR RODNEY BUMROD", "cynthia": "CYNTHIA SIAKAM", "kennedy": "T. KENNEDY"}

# ---------- timeline + audio ----------
wavs = sorted(VOX.glob("*.wav")); L = DLG["lines"]; assert len(wavs) == len(L)
V = [A.load(p, A.SPEED if L[i][0] != "kennedy" else 1.0) for i, p in enumerate(wavs)]
voice = np.zeros(200 * SR, np.float32); segs = []
def say(i, t, fx=None, g=1.0):
    a = V[i] if fx is None else fx(V[i]); a = a * g
    voice[int(t * SR): int(t * SR) + len(a)] += a
    s = dict(i=i, spk=L[i][0], text=L[i][1], t0=t, t1=t + len(V[i]) / SR); segs.append(s); return s["t1"]
t = say(0, 2.6); t = say(1, t + .35); t = say(2, t + .45)
CLICK = t + .55                       # the set clunks on
STATIC0 = CLICK + .12; BARS0 = STATIC0 + .8; STATIC1 = BARS0 + 1.5
C0 = STATIC1 + .55                    # cut to the couch
EP2_OFF = 4.3                         # where part two is when we join it (its phone rings at 6.5, Craig at 8.5)
BELL0 = C0 + 8.6                      # the Kennedys' own phone
PICK = BELL0 + 2.7
t = say(3, PICK + .35); CALL0 = t + .25
t = say(4, CALL0, A.phone_fx, 1.5); CALL1 = t
t = say(5, t + .45)
D0 = t + 1.5                          # anthem; fade begins
an, BEAT = A.anthem(); an = an / np.abs(an).max()
NIMG = len(OUTRO); IMG_LEN = 24 * BEAT / NIMG
CARD0 = D0 + 26 * BEAT                # to be continued, on the last chord
TOTAL = D0 + 34 * BEAT + 2.2
print(f"total {TOTAL:.1f}s click {CLICK:.1f} couch {C0:.1f} bell {BELL0:.1f} call {CALL0:.1f} anthem {D0:.1f} card {CARD0:.1f}", file=sys.stderr)

def laughs():
    """(start, length, gain) laugh cues in couch time."""
    return [(C0 + (8.5 - EP2_OFF) + .9, 2.6, 1.0), (CALL1 + .1, 1.3, .55), (segs[5]["t1"] + .05, 3.0, 1.0)]
def synth_laugh(d, seed):
    r = np.random.default_rng(seed); n = int(d * SR); tt = np.arange(n) / SR; out = np.zeros(n, np.float32)
    for _ in range(46):
        f0 = r.uniform(140, 330); rate = r.uniform(4.2, 6.4); ph = r.uniform(0, 6.28); st = r.uniform(0, .35); ln = r.uniform(.5, 1) * d
        f = f0 * (1 + .12 * np.sin(2 * np.pi * rate * tt + ph)) * (1 - .15 * tt / d)
        p = 2 * np.pi * np.cumsum(f) / SR; s = sum(np.sin(k * p) * g for k, g in ((1, .5), (2, .8), (3, 1), (4, .7), (5, .5), (7, .3)))
        ha = np.clip(np.sin(2 * np.pi * rate * tt + ph), 0, 1) ** 1.5
        env = np.clip((tt - st) * 9, 0, 1) * np.clip((st + ln - tt) * 3, 0, 1)
        out += (s * ha * env * r.uniform(.4, 1)).astype(np.float32)
        out += (r.normal(0, .5, n) * ha * env).astype(np.float32) * .6
    out = A.box(out, 3) - A.box(out, 90); return out / (np.abs(out).max() or 1)
def build_audio():
    n = int(TOTAL * SR); mix = np.zeros(n + SR * 8, np.float32)
    def add(s, t0, g=1.0):
        i = int(t0 * SR); m = min(len(s), len(mix) - i); mix[i:i + m] += s[:m] * g
    import importlib.util
    spec = importlib.util.spec_from_file_location("a2music", HERE / "noir.py"); nm = importlib.util.module_from_spec(spec); spec.loader.exec_module(nm)
    noir = nm.noir_music(int(CLICK * SR)); add(noir, 0, .9)
    # TV: a hum that rises as Bumrod reaches for it, clunk, static, test tone
    add(A.click(), CLICK, .7); add(A.static(STATIC1 + .5 - STATIC0), STATIC0, .13)
    tn = A.tone(STATIC1 - BARS0); add(tn, BARS0, .11); add(A.click(), C0 - .03, .4)
    # couch: sting, part two through the TV speaker, bell, laughs
    add(A.sitcom_sting(), C0 + .05, .9)
    e = A.load(HERE / "ep2.wav", 1.0, trim=False, norm=None); e = e[int(EP2_OFF * SR):]
    tv = A.tv_fx(e); tt = np.arange(len(tv)) / SR
    duck = np.where(tt + C0 > BELL0 - .3, .28, 1.0) * np.clip((D0 + .8 - C0 - tt) / 1.2, 0, 1); duck = A.box(duck.astype(np.float32), 2400)
    add(tv * duck, C0, .5)
    add(A.bell(PICK - BELL0), BELL0, 1.5); add(A.click(), PICK, .35)
    srcs = [HERE / "src_laugh-2.wav", HERE / "src_laugh-2.wav", HERE / "src_laugh-1.wav"]      # real audience (lonemonk, CC BY 3.0) when fetched
    for k, (t0, d, g) in enumerate(laughs()):
        if srcs[k].exists():
            s = A.load(srcs[k], 1.0, trim=False)[: int((d + 1.2) * SR)].copy(); tt = np.arange(len(s)) / SR
            s *= np.clip(tt * 10, 0, 1) * np.clip((d + 1.2 - tt) / 1.4, 0, 1)
        else: s = synth_laugh(d, 40 + k)
        add(s, t0, .34 * g)
    add(an, D0, .62)
    mix[:n] += voice[:n]
    mix = mix[:n]; tt = np.arange(n) / SR; mix *= np.clip((TOTAL - tt) / 1.6, 0, 1)
    pk = np.abs(mix).max(); mix = mix / pk * .97 if pk > .97 else mix
    ap = HERE / "_mix.wav"
    with wave.open(str(ap), "w") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    return ap

# ---------- shared drawing ----------
PH = {}
def photo(n):
    if n not in PH:
        im = ImageOps.exif_transpose(Image.open(glob.glob(str(HERE / f"raw/athens/{n}_*.jpg"))[0])).convert("RGB")
        s = max(W / im.width, H / im.height) * 1.3
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
# cramped: everybody bigger, shoulder to shoulder
NCAST = {"matthew": noirize(cut("matthew", 980, .62)), "bumrod": noirize(cut("bumrod", 1560, .62)), "cynthia": noirize(cut("cynthia", 1040, .78))}
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
CAPN = ImageFont.truetype(MONO, 52); CAPS = ImageFont.truetype(CHARTER, 60)
REPL = (("T V", "TV"), ("Mister", "Mr."), ("Atlantic Ten", "Atlantic 10"))
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
def typed(d, y, text, f, tt, t0, cps=24):
    n = int(max(0, tt - t0) * cps)
    if n <= 0: return
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text[:n] + ("█" if n < len(text) and int(tt * 4) % 2 else ""), font=f, fill=(255, 255, 255, 255), anchor="lm", stroke_width=5, stroke_fill=(0, 0, 0, 255))
def grain(a, amp=26):
    n = rng.integers(-amp, amp, (H // 2, W // 2)).astype(np.float32); return a + np.kron(n, np.ones((2, 2), np.float32))[..., None] if a.ndim == 3 else a + np.kron(n, np.ones((2, 2), np.float32))

# ---------- A: the apartment ----------
INT0 = 2.3    # exterior establishing shot, then inside
def noir_frame(tt):
    if tt < INT0: g = kbim(photo("03"), tt / INT0, .42, .42, .50, .40, 1.0, 1.10).convert("L"); lamp = None
    else: g = kbim(photo("16"), (tt - INT0) / (CLICK - INT0), .5, .5, .45, .5, 1.25, 1.42).convert("L"); lamp = (.80, .22)
    g = ImageOps.autocontrast(g, cutoff=1); g = ImageEnhance.Contrast(g).enhance(1.7); g = ImageEnhance.Brightness(g).enhance(0.40 if tt < INT0 else .34)
    a = np.asarray(g).astype(np.float32)
    if lamp:
        yy, xx = np.mgrid[0:H:8, 0:W:8]; fl = 0.85 + 0.15 * math.sin(tt * 23) * math.sin(tt * 7.3)
        gl = np.exp(-(((xx - lamp[0] * W) ** 2 + (yy - lamp[1] * H) ** 2) / (2 * 260 * 260))) * 120 * fl
        a += np.asarray(Image.fromarray(gl.astype(np.float32)).resize((W, H), Image.BILINEAR))
    a = grain(a)
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")
    cur = next((s for s in segs if s["t0"] <= tt <= s["t1"] + 0.2 and s["i"] < 3), None)
    if tt < INT0:
        rl = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(rl)
        for _ in range(230):
            x = rng.integers(-100, W + 100); y = rng.integers(-100, H); Ln = rng.integers(40, 110)
            rd.line([(x, y), (x - Ln * .22, y + Ln)], fill=int(rng.integers(60, 150)), width=2)
        ov = Image.new("RGBA", (W, H), (255, 255, 255, 0)); ov.putalpha(rl.point(lambda v: int(v * .55))); im.alpha_composite(ov)
    else:
        for spk, x, yb in (("bumrod", 250, 80), ("matthew", -150, 40), ("cynthia", 500, 40)):
            c = NCAST[spk] if (cur and cur["spk"] == spk) else DIM[spk]
            shadowed(im, c, x, H - c.height + yb)
    im.alpha_composite(FOG)
    o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); o.putalpha(BLINDS); im.alpha_composite(o)
    im = Image.composite(im.convert("RGB"), Image.new("RGB", (W, H), (0, 0, 0)), VIG).convert("RGBA")
    # the tube warming up: a cold blue flicker from below, the only color in the room
    wu = (tt - (segs[2]["t1"] - .3)) / (CLICK - segs[2]["t1"] + .3)
    if wu > 0:
        fl = min(1, wu) ** 2 * (.6 + .4 * rng.random())
        gl = Image.new("L", (W, H), 0); ImageDraw.Draw(gl).ellipse((-200, 1150, W + 200, 2500), fill=int(200 * fl)); gl = gl.filter(ImageFilter.GaussianBlur(160))
        o = Image.new("RGBA", (W, H), (150, 190, 255, 0)); o.putalpha(gl); im.alpha_composite(o)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 96), fill=(0, 0, 0, 255)); d.rectangle((0, H - 96, W, H), fill=(0, 0, 0, 255))
    if tt < INT0:
        typed(d, 300, "LOST IN ATHENS", ImageFont.truetype(MONO, 64), tt, 0.3)
        typed(d, 380, "PART THREE", ImageFont.truetype(MONO, 44), tt, 1.1)
    chips = [(INT0 + .1, segs[0]["t1"] + .2, "COURT STREET  ·  2:47 AM  ·  ONE ROOM, ONE COUCH"),
             (segs[1]["t0"], segs[1]["t1"] + .3, "CYNTHIA: CHARGING (LAMP)  ·  4%")]
    for t0, t1, text in chips:
        if t0 <= tt <= t1:
            f = inter("Bold", 28); tw = d.textlength(text, font=f)
            d.rectangle(((W - tw) / 2 - 20, 1690, (W + tw) / 2 + 20, 1750), fill=(0, 0, 0, 220), outline=(230, 230, 230, 255), width=2)
            d.text((W / 2, 1720), text, font=f, fill=(240, 240, 240, 255), anchor="mm")
    if cur:
        draw_caption(im, cur, tt, 470)
        d.text((W / 2, 350), NAMES[cur["spk"]], font=inter("Bold", 30), fill=(200, 200, 200, 255), anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0, 255))
    if 0 <= tt - INT0 < 0.1: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - (tt - INT0) / 0.1)))))
    if tt < 0.6: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - tt / 0.6)))))
    return im.convert("RGB")

# ---------- B: the tube ----------
def crt(arr, tt, roll=0.0):
    """Scanlines, bloom, bowed vignette on a full-frame picture (float array HxWx3)."""
    if roll: arr = np.roll(arr, int(roll * H), axis=0)
    arr = arr * (0.80 + 0.20 * (np.arange(H) % 6 < 4))[:, None, None]
    band = np.exp(-(((np.arange(H) - ((tt * 420) % (H + 500) - 250)) / 110.0) ** 2)) * 30; arr = arr + band[:, None, None]
    im = Image.fromarray(arr.clip(0, 255).astype(np.uint8)); bl = im.filter(ImageFilter.GaussianBlur(14))
    im = Image.blend(im, Image.fromarray(np.maximum(np.asarray(im), np.asarray(bl))), .5)
    return Image.composite(im, Image.new("RGB", (W, H), (0, 0, 0)), VIG)
def static_arr(amp=1.0):
    n = rng.integers(0, 256, (H // 6, W // 3)).astype(np.float32); a = np.kron(n, np.ones((6, 3), np.float32))
    a *= (0.55 + 0.45 * rng.random((H // 6, 1)).repeat(6, 0))
    return np.repeat(a[..., None], 3, 2) * amp
_BARS = None
def bars():
    global _BARS
    if _BARS is None:
        im = Image.new("RGB", (W, H), (16, 16, 16)); d = ImageDraw.Draw(im)
        cols = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]
        bw = W / 7
        for i, c in enumerate(cols): d.rectangle((i * bw, 0, (i + 1) * bw + 1, 1260), fill=c)
        for i, c in enumerate([(0, 0, 192), (16, 16, 16), (192, 0, 192), (16, 16, 16), (0, 192, 192), (16, 16, 16), (192, 192, 192)]): d.rectangle((i * bw, 1260, (i + 1) * bw + 1, 1400), fill=c)
        for i, c in enumerate([(0, 33, 76), (255, 255, 255), (50, 0, 106), (16, 16, 16), (8, 8, 8), (24, 24, 24)]): d.rectangle((i * W / 6, 1400, (i + 1) * W / 6 + 1, H), fill=c)
        d.ellipse((W / 2 - 330, 420, W / 2 + 330, 1080), outline=(255, 255, 255), width=8)
        d.rectangle((W / 2 - 300, 668, W / 2 + 300, 832), fill=(0, 0, 0))
        d.text((W / 2, 720), "HARDWOOD BRICKS", font=inter("Black", 54), fill=(255, 255, 255), anchor="mm")
        d.text((W / 2, 786), "PLEASE STAND BY", font=ImageFont.truetype(MONO, 40), fill=(255, 220, 90), anchor="mm")
        _BARS = np.asarray(im.filter(ImageFilter.GaussianBlur(1.6))).astype(np.float32)
    return _BARS
def tube_frame(tt):
    if tt < STATIC0:      # a white line blooms open
        k = (tt - CLICK) / (STATIC0 - CLICK); a = np.zeros((H, W, 3), np.float32); hh = int(4 + k ** 2 * H / 2)
        a[H // 2 - hh: H // 2 + hh] = 235; return crt(a, tt)
    if tt < BARS0: return osd(crt(static_arr(), tt), "CH 03", tt)
    if tt < STATIC1:
        k = (tt - BARS0) / (STATIC1 - BARS0); a = bars().copy()
        roll = max(0, .5 - k * 2.2) ; a = a * .86 + static_arr(.14)
        if k > .86: a = a * .5 + static_arr(.5)
        sh = int(8 * math.sin(tt * 40)) if k < .25 else 0
        return osd(crt(np.roll(a, sh, 1), tt, roll), "CH 03", tt)
    return osd(crt(static_arr(), tt), "CH 04", tt)
def osd(im, text, tt):
    d = ImageDraw.Draw(im); d.text((W - 110, 180), text, font=ImageFont.truetype(MONO, 64), fill=(60, 255, 90), anchor="rm", stroke_width=3, stroke_fill=(0, 60, 10)); return im

# ---------- C: the couch ----------
TVX, TVY, TVW, TVH = 220, 400, 640, 480      # the screen
_ROOM = None
def room():
    global _ROOM
    if _ROOM is None:
        rp = HERE / "room.jpg"
        if rp.exists():
            im = ImageOps.fit(Image.open(rp).convert("RGB"), (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(5))
            im = ImageEnhance.Brightness(im).enhance(.62)
        else:
            im = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(im)
            for x in range(0, W, 90):      # wood paneling
                sh = int(rng.integers(-8, 8)); d.rectangle((x, 0, x + 90, 1420), fill=(118 + sh, 74 + sh, 40 + sh // 2)); d.line([(x, 0), (x, 1420)], fill=(60, 36, 18), width=4)
            a = np.asarray(im).astype(np.float32); gr = np.kron(rng.normal(0, 7, (H // 2, 1)), np.ones((2, W))) + np.kron(rng.normal(0, 5, (H // 4, W // 2)), np.ones((4, 2)))
            im = Image.fromarray((a + gr[..., None]).clip(0, 255).astype(np.uint8)); d = ImageDraw.Draw(im)
            d.rectangle((0, 1420, W, H), fill=(92, 58, 30))                                      # shag carpet, burnt orange-brown
            d.rectangle((0, 1400, W, 1424), fill=(54, 32, 16))
            # framed landscape, a little crooked
            fr = Image.new("RGBA", (300, 220), (0, 0, 0, 0)); fd = ImageDraw.Draw(fr); fd.rectangle((0, 0, 299, 219), fill=(150, 112, 50)); fd.rectangle((16, 16, 283, 203), fill=(196, 178, 130))
            fd.rectangle((16, 120, 283, 203), fill=(96, 120, 70)); fd.polygon([(16, 120), (110, 60), (180, 120)], fill=(120, 130, 120)); fd.ellipse((210, 40, 250, 80), fill=(240, 190, 110))
            im.paste(fr.rotate(-2.5, expand=True, resample=Image.BICUBIC), (70, 90), fr.rotate(-2.5, expand=True, resample=Image.BICUBIC))
            # sunburst clock
            cx, cy = 880, 190
            for k in range(24): ang = k * math.pi / 12; r = 110 if k % 2 else 80; d.line([(cx, cy), (cx + r * math.cos(ang), cy + r * math.sin(ang))], fill=(210, 160, 60), width=5)
            d.ellipse((cx - 44, cy - 44, cx + 44, cy + 44), fill=(60, 40, 22), outline=(220, 170, 70), width=5); d.line([(cx, cy), (cx + 20, cy - 22)], fill=(240, 220, 170), width=4); d.line([(cx, cy), (cx - 6, cy + 32)], fill=(240, 220, 170), width=3)
            # lamp on a side table, right
            d.rectangle((900, 1130, 1080, 1420), fill=(70, 42, 20)); d.rectangle((962, 960, 978, 1130), fill=(170, 130, 60)); d.polygon([(900, 960), (1040, 960), (1010, 800), (930, 800)], fill=(250, 214, 150))
            # fern, left
            for k in range(11):
                ang = -math.pi / 2 + (k - 5) * .22; d.line([(110, 1180), (110 + 240 * math.cos(ang), 1180 + 300 * math.sin(ang))], fill=(44, 92, 40), width=14)
            d.polygon([(60, 1180), (160, 1180), (146, 1330), (74, 1330)], fill=(150, 80, 44)); d.rectangle((40, 1330, 180, 1420), fill=(70, 42, 20))
            im = im.filter(ImageFilter.GaussianBlur(3))
            gl = Image.new("L", (W, H), 0); ImageDraw.Draw(gl).ellipse((640, 520, 1320, 1240), fill=200); gl = gl.filter(ImageFilter.GaussianBlur(150))
            im = Image.composite(Image.new("RGB", (W, H), (255, 214, 150)), im, gl.point(lambda v: int(v * .55)))
            im = ImageEnhance.Brightness(im).enhance(.78)
        d = ImageDraw.Draw(im)
        # the console set: walnut cabinet, speaker cloth, brass knobs, rabbit ears, doily
        x0, y0, x1, y1 = TVX - 60, TVY - 50, TVX + TVW + 190, TVY + TVH + 60
        d.line([(x0 + 300, y0), (x0 + 170, y0 - 210)], fill=(190, 190, 196), width=7); d.line([(x0 + 330, y0), (x0 + 500, y0 - 230)], fill=(190, 190, 196), width=7); d.ellipse((x0 + 285, y0 - 30, x0 + 345, y0 + 10), fill=(40, 40, 44))
        d.rounded_rectangle((x0, y0, x1, y1), 26, fill=(86, 50, 24), outline=(48, 26, 10), width=8)
        for yy in range(y0 + 14, y1 - 10, 9): d.line([(x0 + 12, yy), (x1 - 12, yy + int(rng.integers(-2, 3)))], fill=(96 + int(rng.integers(-10, 10)), 56, 27), width=3)
        d.rounded_rectangle((TVX - 22, TVY - 22, TVX + TVW + 22, TVY + TVH + 22), 44, fill=(26, 22, 20), outline=(150, 120, 70), width=5)
        cx = TVX + TVW + 105
        d.rounded_rectangle((cx - 62, TVY - 14, cx + 62, TVY + TVH + 14), 12, fill=(60, 36, 18), outline=(150, 120, 70), width=3)
        for k, yy in enumerate((TVY + 60, TVY + 180)):
            d.ellipse((cx - 44, yy - 44, cx + 44, yy + 44), fill=(196, 160, 90), outline=(70, 50, 20), width=4); d.ellipse((cx - 22, yy - 22, cx + 22, yy + 22), fill=(60, 44, 24)); d.line([(cx, yy), (cx + 14, yy - 30)], fill=(240, 220, 170), width=5)
        for yy in range(TVY + 260, TVY + TVH, 14): d.line([(cx - 44, yy), (cx + 44, yy)], fill=(160, 128, 76), width=6)
        for lx in (x0 + 50, x1 - 80): d.polygon([(lx, y1), (lx + 30, y1), (lx + 22, y1 + 120), (lx + 8, y1 + 120)], fill=(48, 26, 10))
        _ROOM = im.convert("RGBA")
    return _ROOM
_SCRMASK = Image.new("L", (TVW, TVH), 0); ImageDraw.Draw(_SCRMASK).rounded_rectangle((0, 0, TVW - 1, TVH - 1), 40, fill=255)
_SCRVIG = Image.new("L", (TVW, TVH), 0); ImageDraw.Draw(_SCRVIG).ellipse((-90, -70, TVW + 90, TVH + 70), fill=255); _SCRVIG = _SCRVIG.filter(ImageFilter.GaussianBlur(40))
EPF = sorted(glob.glob(str(HERE / "ep2/*.jpg")))
def screen(tt):
    e = (tt - C0) + EP2_OFF; n = int(e * FPS)
    if n >= len(EPF): n = int(11.6 * FPS) + (n - int(11.6 * FPS)) % (len(EPF) - int(11.6 * FPS) - 12)      # keep the Miami finale looping
    f = Image.open(EPF[n]).convert("RGB")                       # 360x640
    f = f.crop((0, 120, 360, 390)).resize((TVW, TVH), Image.BILINEAR)
    a = np.asarray(f).astype(np.float32) * 1.08 + 10
    a *= (0.84 + 0.16 * (np.arange(TVH) % 4 < 3))[:, None, None]
    a += rng.integers(-10, 10, (TVH, TVW, 1))
    k = tt - C0
    if k < .35: a = np.roll(a, int((1 - k / .35) * TVH * .8), 0) * .6 + static_arr()[:TVH, :TVW] * .4          # vertical hold settles
    f = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    return Image.composite(f, Image.new("RGB", (TVW, TVH), (0, 0, 0)), _SCRVIG), a.reshape(-1, 3).mean(0)
def person(kind, lean=0.0, bob=0.0, phone=0.0):
    """Back-of-head silhouette on a transparent 620x900 tile. kind: 'k' (him) or 'l' (her)."""
    im = Image.new("RGBA", (620, 900), (0, 0, 0, 0)); d = ImageDraw.Draw(im); cx = 310 + lean; y = 40 + bob
    if kind == "k":
        sk, hair, shirt = (120, 84, 62), (38, 28, 22), (52, 74, 104)
        d.rounded_rectangle((cx - 280, y + 330, cx + 280, 900), 120, fill=shirt)                       # shoulders, cardigan
        d.polygon([(cx - 90, y + 300), (cx + 90, y + 300), (cx + 130, y + 380), (cx - 130, y + 380)], fill=(236, 232, 220))   # collar
        d.rounded_rectangle((cx - 62, y + 230, cx + 62, y + 350), 30, fill=sk)                         # neck
        d.ellipse((cx - 150, y + 110, cx - 106, y + 210), fill=sk); d.ellipse((cx + 106, y + 110, cx + 150, y + 210), fill=sk)   # ears
        d.ellipse((cx - 128, y, cx + 128, y + 290), fill=sk)
        d.pieslice((cx - 132, y - 8, cx + 132, y + 300), 180, 360, fill=hair); d.rounded_rectangle((cx - 132, y + 130, cx + 132, y + 216), 40, fill=hair)
        d.ellipse((cx - 50, y + 20, cx + 50, y + 100), fill=(128, 92, 70))                              # the thinning spot
        if phone > 0:   # handset comes up to his right ear
            px, py = cx + 150, y + 150 + (1 - phone) * 520
            d.line([(cx + 250, 900), (px + 40, py + 190)], fill=shirt, width=120)
            d.ellipse((px - 10, py + 120, px + 90, py + 220), fill=sk)
            d.rounded_rectangle((px, py - 30, px + 64, py + 250), 30, fill=(214, 204, 176), outline=(120, 110, 90), width=4)
    else:
        sk, hair, dress = (150, 104, 82), (74, 40, 22), (176, 70, 86)
        d.rounded_rectangle((cx - 240, y + 350, cx + 240, 900), 120, fill=dress)
        d.rounded_rectangle((cx - 50, y + 250, cx + 50, y + 370), 26, fill=sk)
        d.ellipse((cx - 170, y - 30, cx + 170, y + 300), fill=hair)                                     # big set-and-sprayed hair
        d.ellipse((cx - 190, y + 60, cx - 40, y + 330), fill=hair); d.ellipse((cx + 40, y + 60, cx + 190, y + 330), fill=hair)
        d.ellipse((cx - 110, y - 50, cx + 110, y + 120), fill=hair)
        d.arc((cx - 120, y + 10, cx + 60, y + 200), 190, 300, fill=(120, 74, 44), width=10)
    return im
_PCACHE = {}
def couch_layer(tt, glow):
    """Couch back and two heads, soft focus, rim-lit by the screen."""
    def amt(t0, d): return max(0.0, min(1.0, (tt - t0) * 6, (t0 + d - tt) * 2))
    lg = max([amt(t0, d) for t0, d, g in laughs()] + [0])
    kb_ = lg * 14 * math.sin(tt * 26); lb = lg * 16 * math.sin(tt * 22 + 1.3)
    ph = max(0.0, min(1.0, (tt - PICK + .25) / .5))
    turn = max(0.0, min(1.0, (tt - BELL0 - .5) / .4)) * (1 - ph)          # he glances toward the ringing
    key = (round(kb_), round(lb), round(ph * 12), round(turn * 6))
    if key not in _PCACHE:
        if len(_PCACHE) > 400: _PCACHE.clear()
        ly = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ly.alpha_composite(person("k", lean=turn * 26, bob=kb_ - lg * 10, phone=ph), (10, 1040))
        ly.alpha_composite(person("l", lean=-lg * 12, bob=lb - lg * 8), (470, 1100))
        d = ImageDraw.Draw(ly)
        d.rounded_rectangle((-60, 1560, W + 60, H + 200), 110, fill=(150, 92, 34))        # harvest-gold couch back
        for x in range(40, W, 150): d.line([(x, 1600), (x - 30, H)], fill=(128, 76, 26), width=6)
        d.rounded_rectangle((-60, 1560, W + 60, 1620), 30, fill=(176, 112, 46))
        # crocheted afghan over the back, zigzag
        for k, c in enumerate(((190, 60, 40), (236, 200, 90), (60, 110, 90), (236, 226, 200))):
            pts = [(640 + i * 40, 1560 + k * 34 + (0 if i % 2 else 34)) for i in range(12)]; d.line(pts, fill=c, width=22, joint="curve")
        _PCACHE[key] = ly.filter(ImageFilter.GaussianBlur(5))
    ly = _PCACHE[key]
    a = np.asarray(ly).astype(np.float32); rgb = a[..., :3] * .34       # backs are in shadow...
    al = ly.getchannel("A"); edge = np.asarray(al).astype(np.float32) - np.asarray(al.filter(ImageFilter.GaussianBlur(9))).astype(np.float32)
    rim = np.clip(edge, 0, 255) / 255 * np.linspace(1.3, .25, H)[:, None]                       # ...with the tube's light on their edges
    rgb = rgb + rim[..., None] * np.asarray(glow, np.float32)[None, None, :] * 1.5
    return Image.fromarray(np.dstack([rgb.clip(0, 255), a[..., 3]]).astype(np.uint8), "RGBA")
_MCUT = None
def call_inset(im, tt):
    """Split-screen: the caller, still in black and white."""
    global _MCUT
    k = min(1, (tt - CALL0 + .15) / .25); 
    if k <= 0 or tt > CALL1 + .5: return
    if _MCUT is None:
        bg = kbim(photo("16"), .5, .5, .5, .45, .5, 1.3, 1.3).convert("L"); bg = ImageEnhance.Brightness(ImageEnhance.Contrast(bg).enhance(1.6)).enhance(.4).resize((430, 764)).crop((0, 100, 430, 620)).convert("RGBA")
        c = noirize(cut("matthew", 620, .62)); bg.alpha_composite(c, ((430 - c.width) // 2, 520 - c.height + 40))
        o = Image.new("RGBA", bg.size, (0, 0, 0, 0)); o.putalpha(BLINDS.crop((0, 0, 430, 520)).point(lambda v: int(v * 1.2))); bg.alpha_composite(o)
        _MCUT = bg.convert("RGB")
    g = np.asarray(_MCUT).astype(np.float32) + rng.integers(-18, 18, (520, 430, 1))
    tile = Image.fromarray(g.clip(0, 255).astype(np.uint8)); x = int(W - 40 - 430 * k) ; y = 150
    d = ImageDraw.Draw(im); d.rectangle((x - 8, y - 8, x + 438, y + 528 + 56), fill=(245, 240, 225, 255)); im.paste(tile, (x, y))
    d.text((x + 215, y + 552), "ATHENS, OHIO  ·  2:51 AM", font=inter("Bold", 24), fill=(20, 20, 20, 255), anchor="mm")
def couch_frame(tt):
    im = room().copy(); scr, glow = screen(tt)
    gl = Image.new("L", (W, H), 0); ImageDraw.Draw(gl).ellipse((TVX - 260, TVY - 200, TVX + TVW + 260, TVY + TVH + 420), fill=150); gl = gl.filter(ImageFilter.GaussianBlur(130))
    o = Image.new("RGBA", (W, H), tuple(int(v) for v in np.clip(glow * 1.3, 0, 255)) + (0,)); o.putalpha(gl.point(lambda v: int(v * .5))); im.alpha_composite(o)   # screen light spills on the room
    im.paste(scr, (TVX, TVY), _SCRMASK)
    hl = Image.new("RGBA", (TVW, TVH), (0, 0, 0, 0)); ImageDraw.Draw(hl).ellipse((40, 20, 330, 150), fill=(255, 255, 255, 26)); im.alpha_composite(hl.filter(ImageFilter.GaussianBlur(24)), (TVX, TVY))
    # slow push-in toward the set
    k = (tt - C0) / (D0 + 2 - C0); z = 1.0 + .07 * k
    im.alpha_composite(couch_layer(tt, np.clip(glow * 1.2 + 40, 0, 255)))
    if z > 1.001:
        cw, ch = W / z, H / z; x = (W - cw) / 2; y = (H - ch) * .38
        im = im.crop((int(x), int(y), int(x + cw), int(y + ch))).resize((W, H), Image.BILINEAR)
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    a = a * np.array([1.06, 1.0, .88]) + np.array([10, 4, -4]); a = grain(a, 9)        # warm three-camera glow
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8)); bl = im.filter(ImageFilter.GaussianBlur(18)); im = Image.blend(im, Image.fromarray(np.maximum(np.asarray(im), np.asarray(bl))), .35).convert("RGBA")
    d = ImageDraw.Draw(im); k = tt - C0
    if .25 < k < 3.6:      # sitcom title super
        f = ImageFont.truetype(CHARTER, 92); al = int(255 * min(1, (k - .25) / .3, (3.6 - k) / .4))
        o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(o)
        for txt, yy, ff in (("Meanwhile,", 1130, f), ("in the suburbs", 1230, f)):
            od.text((W / 2 + 5, yy + 6), txt, font=ff, fill=(60, 20, 10, al), anchor="mm"); od.text((W / 2, yy), txt, font=ff, fill=(255, 214, 70, al), anchor="mm", stroke_width=3, stroke_fill=(120, 50, 10, al))
        od.text((W / 2, 1320), "FILMED BEFORE A LIVE STUDIO AUDIENCE", font=inter("Bold", 26), fill=(255, 240, 210, al), anchor="mm", stroke_width=3, stroke_fill=(40, 20, 10, al))
        im.alpha_composite(o)
    call_inset(im, tt); d = ImageDraw.Draw(im)
    if BELL0 <= tt < PICK and ((tt - BELL0) % 2.2) < 1.25:
        j = int(6 * math.sin(tt * 70)); d.text((W / 2 + j, 1180), "RRRING!", font=ImageFont.truetype(CHARTER, 96), fill=(255, 214, 70, 255), anchor="mm", stroke_width=6, stroke_fill=(120, 40, 10, 255))
    cur = next((s for s in segs if s["t0"] <= tt <= s["t1"] + 0.25 and s["i"] >= 3), None)
    if cur:
        d.text((W / 2, 1090), NAMES[cur["spk"]] + ("  ·  ON THE LINE" if cur["spk"] == "matthew" else ""), font=inter("Bold", 30), fill=(255, 240, 210, 255), anchor="mm", stroke_width=4, stroke_fill=(40, 20, 10, 255))
        draw_caption(im, cur, tt, 1190, CAPS, (255, 226, 110), (60, 24, 8))
    for t0, dd, g in laughs():
        if t0 <= tt <= t0 + dd - .3 and not cur and int(tt * 3) % 2 == 0:
            d.rounded_rectangle((W / 2 - 150, 150, W / 2 + 150, 226), 12, fill=(30, 10, 6, 255), outline=(255, 80, 60, 255), width=4); d.text((W / 2, 188), "LAUGHTER", font=inter("Black", 40), fill=(255, 90, 70, 255), anchor="mm")
    return im.convert("RGB")

# ---------- D: the anthem ----------
_OIM = {}
def outro_im(i):
    if i not in _OIM:
        im = ImageOps.exif_transpose(Image.open(HERE / OUTRO[i][0])).convert("RGB"); s = max(W / im.width, H / im.height) * 1.3
        im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
        im = ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.12)).enhance(1.22); _OIM[i] = im
    return _OIM[i]
def outro_shot(i, k):
    dirn = 1 if i % 2 == 0 else -1
    return kbim(outro_im(i), k, .5 - .10 * dirn, .5 + .10 * dirn, .5, .5, 1.0, 1.10)
def outro_frame(tt):
    e = tt - D0; i = min(NIMG - 1, int(e / IMG_LEN)); k = e / IMG_LEN - i if i < NIMG - 1 else (e - (NIMG - 1) * IMG_LEN) / (TOTAL - D0 - (NIMG - 1) * IMG_LEN)
    im = outro_shot(i, min(1, k * .8 + .1))
    xf = (e - i * IMG_LEN) / 1.1
    if i > 0 and xf < 1: im = Image.blend(outro_shot(i - 1, min(1, .9 + xf * 1.1 / IMG_LEN * .8)), im, xf)
    a = np.asarray(im).astype(np.float32); a = a * np.array([1.04, 1.0, .94]) + rng.integers(-6, 6, (H, W, 1))
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8)); bl = im.filter(ImageFilter.GaussianBlur(22)); im = Image.blend(im, Image.fromarray(np.maximum(np.asarray(im), np.asarray(bl))), .3)
    im = Image.composite(im, ImageEnhance.Brightness(im).enhance(.35), VIG).convert("RGBA"); d = ImageDraw.Draw(im)
    if tt < CARD0:
        slug = OUTRO[i][1]; al = int(255 * max(0, min(1, (e - i * IMG_LEN - .5) / .5, ((i + 1) * IMG_LEN - e) / .4)))
        if al > 0:
            o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(o); f = ImageFont.truetype(CHARTER, 58)
            od.text((W / 2, 1560), slug, font=f, fill=(255, 250, 235, al), anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0, al)); im.alpha_composite(o)
    else:
        k = min(1, (tt - CARD0) / .9)
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(150 * k)))); o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(o); al = int(255 * k)
        od.text((W / 2, 800), "To be continued...", font=ImageFont.truetype(CHARTER, 104), fill=(255, 214, 70, al), anchor="mm", stroke_width=4, stroke_fill=(60, 24, 8, al))
        k2 = max(0, min(1, (tt - CARD0 - 1.0) / .7)); al2 = int(255 * k2)
        od.text((W / 2, 940), "FROM YPSILANTI", font=inter("Black", 76, True), fill=(255, 255, 255, al2), anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0, al2))
        od.text((W / 2, 1030), "LOST IN ATHENS  ·  PART FOUR", font=ImageFont.truetype(MONO, 34), fill=(235, 235, 235, al2), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, al2))
        od.text((W / 2, 1700), "Voices are AI-generated.  hardwoodbricks.com", font=inter("Medium", 28), fill=(235, 235, 235, al2), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, al2))
        im.alpha_composite(o)
    fo = (TOTAL - tt) / 1.2
    if fo < 1: im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - max(0, fo))))))
    return im.convert("RGB")

def frame(n):
    tt = n / FPS
    if tt < CLICK: return noir_frame(tt)
    if tt < C0: return tube_frame(tt)
    if tt < D0: return couch_frame(tt)
    if tt < D0 + 1.6: return Image.blend(couch_frame(tt), outro_frame(tt), (tt - D0) / 1.6)     # the suburbs dissolve into the old country
    return outro_frame(tt)

if "--frame" in sys.argv:
    for t in sys.argv[sys.argv.index("--frame") + 1].split(","):
        t = {"C": C0, "D": D0, "K": CLICK, "B": BELL0}.get(t[0], 0) + float(t[1:]) if t[0] in "CDKB" else float(t)
        frame(int(t * FPS)).resize((540, 960)).save(OUT.with_suffix(f".{t:.1f}.png"))
    sys.exit()
apath = build_audio()
if "--audio" in sys.argv: sys.exit()
N = int(TOTAL * FPS)
p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                      "-i", str(apath), "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-maxrate", "3000k", "-bufsize", "6000k", "-pix_fmt", "yuv420p",
                      "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
for n in range(N):
    p.stdin.write(frame(n).tobytes())
    if n % 300 == 0: print(n, "/", N, file=sys.stderr, flush=True)
p.stdin.close(); p.wait(); print("wrote", OUT, file=sys.stderr)
