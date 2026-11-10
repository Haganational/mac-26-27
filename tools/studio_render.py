"""Render the 'Tonight in the MAC' studio Short (1080x1920) from voiced lines.

python render.py <voices_dir> <out.mp4> [--thumb thumb.png]
voices_dir holds NN-<speaker>.wav in dialogue order.
"""
import json, math, subprocess, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
SR = 24000
HERE = Path(__file__).parent
DLG = json.load(open(sys.argv[3] if len(sys.argv) > 3 and sys.argv[3].endswith('.json') else HERE / "dialogue.json"))
VOX = Path(sys.argv[1]); OUT = Path(sys.argv[2])

F = "/usr/share/fonts/opentype/inter/"
def font(w, s): return ImageFont.truetype(F + f"Inter-{w}.otf", s)
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
EMOJI = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)

GOLD = (236, 196, 106)
SPK = {
    "matthew": dict(name="Matthew Hagan", sub="Editor, Hardwood Bricks", ini="MH", col=(232, 120, 64), grad=((150, 60, 30), (232, 120, 64))),
    "bumrod": dict(name="Pastor Rodney Bumrod", sub="Ball State, class of way back", ini="PB", col=(226, 32, 52), grad=((120, 10, 20), (226, 32, 52))),
    "cynthia": dict(name="Cynthia Siakam", sub="Data desk · AI", ini="CS", col=(64, 214, 240), grad=((60, 90, 230), (64, 214, 240))),
}
GAMES = [
    dict(away=("Youngstown St.", "YSU", (210, 16, 52)), home=("Central Michigan", "CMU", (106, 0, 50), (255, 200, 46)),
         rec="CMU 2-0", where="McGuirk Arena · Mount Pleasant, Mich.",
         line="CMU -3.5", total="151.5", model="Pick'em", mtotal="148.5"),
    dict(away=("Wright St.", "WSU", (0, 105, 62)), home=("Toledo", "TOL", (21, 57, 127), (255, 206, 0)),
         rec="Toledo 1-2", where="Savage Arena · Toledo, Ohio",
         line="WSU -1.5", total="158.5", model="WSU -2.3", mtotal="160.0"),
]
# which game card each line shows, and on-screen gags per line index
GAME_FOR_LINE = [0, 0, 0, 0, 0, 0, 0, 1, 1, 1]
STAMP = {2: ("NOT IN YOUNGSTOWN", (226, 32, 52)), 5: ("FOUL: MATTHEW", (64, 214, 240))}
EMOJI_FOR = {8: "\U0001F6A4", 9: "\U0001F30A"}

# ---------- audio ----------
def read(p):
    with wave.open(str(p)) as w:
        sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2: a = a.reshape(-1, 2).mean(1)
    if sr != SR:
        x = np.linspace(0, len(a) - 1, int(len(a) * SR / sr)); a = np.interp(x, np.arange(len(a)), a)
    # trim silence
    env = np.abs(a) > 0.012
    idx = np.nonzero(env)[0]
    if len(idx): a = a[max(0, idx[0] - 1200): idx[-1] + 2400]
    pk = np.abs(a).max() or 1
    return a * (0.89 / pk)

wavs = sorted(VOX.glob("*.wav"))
assert len(wavs) == len(DLG["lines"]), (len(wavs), len(DLG["lines"]))
GAP_BEFORE = {1: 0.02, 3: 0.15, 4: 0.05, 5: 0.15, 8: 0.35, 9: 0.15}
INTRO = 1.2
segs, t, chunks = [], INTRO, [np.zeros(int(INTRO * SR), np.float32)]
for i, (p, (spk, text)) in enumerate(zip(wavs, DLG["lines"])):
    if i: gap = GAP_BEFORE.get(i, 0.3); chunks.append(np.zeros(int(gap * SR), np.float32)); t += gap
    a = read(p); chunks.append(a)
    segs.append(dict(i=i, spk=spk, text=text, t0=t, t1=t + len(a) / SR, a=a)); t += len(a) / SR
OUTRO = 3.6
chunks.append(np.zeros(int(OUTRO * SR), np.float32)); TOTAL = t + OUTRO
audio = np.concatenate(chunks)
apath = OUT.with_suffix(".wav")
with wave.open(str(apath), "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
print(f"duration {TOTAL:.1f}s", file=sys.stderr)

# ---------- static layers ----------
bg0 = Image.open("/mnt/project-files/art/mac-in-motion-phone-bare.png").convert("RGB")
bg0 = bg0.resize((int(W * 1.12), int(H * 1.12)), Image.LANCZOS)
dark = Image.new("RGB", bg0.size, (0, 0, 0))
bg0 = Image.blend(bg0, dark, 0.45)

def text_w(d, s, f): return d.textlength(s, font=f)

def plaque():
    im = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(SERIF, 40); s = "HARDWOOD BRICKS"; tw = text_w(d, s, f)
    x0, y0, x1, y1 = (W - tw) / 2 - 34, 40, (W + tw) / 2 + 34, 108
    for y in range(int(y0), int(y1)):
        k = (y - y0) / (y1 - y0); c = tuple(int(a + (b - a) * k) for a, b in zip((246, 214, 140), (176, 128, 52)))
        d.line([(x0, y), (x1, y)], fill=c)
    d.text((W / 2, 74), s, font=f, fill=(60, 30, 10), anchor="mm")
    f2 = font("ExtraBold", 54); s2 = "TONIGHT IN THE MAC"
    sp = 9; total = sum(text_w(d, ch, f2) for ch in s2) + sp * (len(s2) - 1); x = (W - total) / 2
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    for ch in s2:
        gd.text((x, 150), ch, font=f2, fill=GOLD + (255,)); x += text_w(d, ch, f2) + sp
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
    im.alpha_composite(glow)
    d.text((W / 2, 238), "TUESDAY, NOV. 10  ·  AFTER DARK STUDIO", font=font("SemiBold", 28), fill=(235, 225, 205), anchor="mm")
    return im
PLAQUE = plaque()

def rr(d, box, r, **kw): d.rounded_rectangle(box, r, **kw)

def game_card(g):
    im = Image.new("RGBA", (W, 560), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rr(d, (48, 10, W - 48, 550), 34, fill=(14, 10, 8, 214), outline=(236, 196, 106, 140), width=3)
    # team rows
    def row(y, team, tag):
        name, ab, col = team[0], team[1], team[2]
        rr(d, (84, y, 84 + 14, y + 100), 7, fill=col)
        d.text((122, y + 2), tag, font=font("Bold", 24), fill=(200, 190, 175))
        d.text((120, y + 30), name, font=font("ExtraBold", 60), fill=(255, 255, 255))
    row(34, g["away"], "AWAY")
    row(150, g["home"], "HOME  \u00b7  " + g["rec"])
    d.text((W / 2, 298), "7:00 PM ET  ·  ESPN+", font=font("Bold", 40), fill=GOLD, anchor="mm")
    d.text((W / 2, 346), g["where"], font=font("Medium", 30), fill=(225, 218, 205), anchor="mm")
    # chips
    chips = [("LINE", g["line"]), ("TOTAL", g["total"]), ("MODEL", g["model"]), ("MODEL TOTAL", g["mtotal"])]
    cw = (W - 96 - 30 * 3 - 60) / 4; x = 78
    for lab, val in chips:
        model = lab.startswith("MODEL")
        rr(d, (x, 392, x + cw, 512), 20, fill=(42, 26, 16, 235) if not model else (60, 30, 90, 235),
           outline=(236, 196, 106, 180) if not model else (180, 140, 255, 200), width=2)
        d.text((x + cw / 2, 426), lab, font=font("Bold", 21), fill=(220, 205, 180), anchor="mm")
        d.text((x + cw / 2, 474), val, font=font("ExtraBold", 38), fill=(255, 255, 255), anchor="mm")
        x += cw + 30
    d.text((W / 2, 534), "Lines: Pinnacle, 10:30 a.m. ET. Model: hardwoodbricks.com", font=font("Medium", 20), fill=(170, 160, 150), anchor="mm")
    return im
CARDS = [game_card(g) for g in GAMES]

def avatar(spk, size=150):
    s = SPK[spk]; im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    g = Image.new("RGBA", (size, size)); gd = ImageDraw.Draw(g)
    for y in range(size):
        k = y / size; gd.line([(0, y), (size, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(s["grad"][1], s["grad"][0])) + (255,))
    m = Image.new("L", (size, size), 0); ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
    im.paste(g, (0, 0), m)
    ImageDraw.Draw(im).text((size / 2, size / 2), s["ini"], font=font("ExtraBold", int(size * 0.36)), fill=(255, 255, 255), anchor="mm")
    return im
AV = {k: avatar(k) for k in SPK}

ROWY = {"matthew": 900, "bumrod": 1060, "cynthia": 1220}

def speaker_rows(active, level, tt):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for spk, y in ROWY.items():
        s = SPK[spk]
        if spk == active:
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
            rr(gd, (36, y - 8, W - 36, y + 148), 30, outline=s["col"] + (255,), width=10)
            im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
            rr(d, (36, y - 8, W - 36, y + 148), 30, fill=(10, 8, 8, 230), outline=s["col"] + (255,), width=4)
            im.alpha_composite(AV[spk], (62, y))
            d.text((240, y + 40), s["name"], font=font("ExtraBold", 50), fill=s["col"], anchor="lm")
            d.text((240, y + 98), s["sub"], font=font("Medium", 30), fill=(225, 220, 210), anchor="lm")
            # waveform bars
            for k in range(9):
                ph = math.sin(tt * 19 + k * 1.7) * 0.5 + 0.5
                h = 10 + 70 * min(1, level * 3.2) * (0.35 + 0.65 * ph) * (1 - abs(k - 4) / 6)
                x = 838 + k * 18
                rr(d, (x, y + 70 - h / 2, x + 9, y + 70 + h / 2), 4, fill=s["col"])
        else:
            a = AV[spk].copy(); a.putalpha(a.getchannel("A").point(lambda v: int(v * 0.5)))
            im.alpha_composite(a, (62, y))
            d.text((240, y + 40), s["name"], font=font("ExtraBold", 50), fill=(255, 255, 255, 120), anchor="lm")
            d.text((240, y + 98), s["sub"], font=font("Medium", 30), fill=(255, 255, 255, 95), anchor="lm")
    return im

# captions: split each line into chunks of <= ~6 words, timed by characters
CAPF = font("ExtraBold", 64)
def caption_chunks(seg):
    words = seg["text"].split(); chunks, cur = [], []
    for w_ in words:
        cur.append(w_)
        if len(" ".join(cur)) > 26 or w_.endswith((".", "?", "!")) and len(cur) > 2:
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    tot = sum(len(w_) + 1 for w_ in words); dur = seg["t1"] - seg["t0"]; t = seg["t0"]; out = []
    for c in chunks:
        wt = []
        for w_ in c:
            d_ = dur * (len(w_) + 1) / tot; wt.append((w_, t, t + d_)); t += d_
        out.append(wt)
    return out
for s in segs: s["caps"] = caption_chunks(s)

def wrap(words, f, maxw, d):
    lines, cur = [], []
    for w_ in words:
        test = " ".join(x[0] for x in cur + [w_])
        if cur and d.textlength(test, font=f) > maxw: lines.append(cur); cur = [w_]
        else: cur.append(w_)
    if cur: lines.append(cur)
    return lines

def draw_caption(im, seg, tt):
    d = ImageDraw.Draw(im)
    chunk = None
    for c in seg["caps"]:
        if c[0][1] <= tt: chunk = c
    if not chunk: return
    col = SPK[seg["spk"]]["col"]
    lines = wrap(chunk, CAPF, W - 140, d); y = 1500 - (len(lines) - 1) * 40
    for ln in lines:
        full = " ".join(x[0] for x in ln); x = (W - d.textlength(full, font=CAPF)) / 2
        for w_, a, b in ln:
            fill = col if a <= tt else (255, 255, 255)
            d.text((x, y), w_, font=CAPF, fill=fill, anchor="lm", stroke_width=6, stroke_fill=(0, 0, 0))
            x += d.textlength(w_ + " ", font=CAPF)
        y += 80

def stamp(im, text, col, k):
    f = font("Black", 64); tmp = Image.new("RGBA", (900, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(tmp)
    tw = d.textlength(text, font=f)
    rr(d, ((900 - tw) / 2 - 30, 50, (900 + tw) / 2 + 30, 150), 16, outline=col + (255,), width=8)
    d.text((450, 100), text, font=f, fill=col + (255,), anchor="mm")
    sc = 1.6 - 0.6 * min(1, k * 5)
    tmp = tmp.rotate(-8, resample=Image.BICUBIC, expand=True)
    tmp = tmp.resize((int(tmp.width * sc), int(tmp.height * sc)), Image.BICUBIC)
    a = tmp.getchannel("A").point(lambda v: int(v * min(1, k * 5)))
    tmp.putalpha(a)
    im.alpha_composite(tmp, (int(W / 2 - tmp.width / 2), int(560 - tmp.height / 2)))

def emoji(ch):
    tmp = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((10, 10), ch, font=EMOJI, embedded_color=True)
    return tmp
EMO = {i: emoji(c) for i, c in EMOJI_FOR.items()}

FOOT = Image.new("RGBA", (W, 200), (0, 0, 0, 0)); fd = ImageDraw.Draw(FOOT)
fd.text((W / 2, 70), "hardwoodbricks.com", font=font("ExtraBold", 40), fill=GOLD, anchor="mm")
fd.text((W / 2, 120), "All three voices are AI. Lines change; not betting advice.", font=font("Medium", 26), fill=(200, 192, 180), anchor="mm")

def level_at(seg, tt):
    a = seg["a"]; c = int((tt - seg["t0"]) * SR); w = 900
    if c < 0 or c >= len(a): return 0
    return float(np.sqrt(np.mean(a[max(0, c - w): c + w] ** 2)))

def card_for(tt):
    for s in reversed(segs):
        if s["t0"] - 0.2 <= tt: return GAME_FOR_LINE[s["i"]]
    return 0

def frame(n):
    tt = n / FPS
    z = 1 + 0.0016 * tt; cw, ch = int(W / z * 1.0), int(H / z * 1.0)
    ox = (bg0.width - cw) / 2 + 30 * math.sin(tt / 9); oy = (bg0.height - ch) / 2 + 20 * math.cos(tt / 11)
    im = bg0.crop((int(ox), int(oy), int(ox) + cw, int(oy) + ch)).resize((W, H), Image.BILINEAR).convert("RGBA")
    im.alpha_composite(PLAQUE, (0, 0))
    gi = card_for(tt)
    # crossfade card on switch
    sw = next((s["t0"] for s in segs if GAME_FOR_LINE[s["i"]] == 1), 1e9) - 0.2
    if abs(tt - sw) < 0.35 and tt > sw:
        k = (tt - sw) / 0.35; c = CARDS[1].copy(); c.putalpha(c.getchannel("A").point(lambda v: int(v * k)))
        c0 = CARDS[0].copy(); c0.putalpha(c0.getchannel("A").point(lambda v: int(v * (1 - k))))
        im.alpha_composite(c0, (0, 290)); im.alpha_composite(c, (0, 290))
    else:
        card = CARDS[gi]
        if tt < INTRO:
            k = tt / INTRO; card = card.copy(); card.putalpha(card.getchannel("A").point(lambda v: int(v * k)))
        im.alpha_composite(card, (0, 290))
    cur = next((s for s in segs if s["t0"] <= tt <= s["t1"] + 0.25), None)
    prev = None
    for s in segs:
        if s["t0"] <= tt: prev = s
    active = cur["spk"] if cur else None
    im.alpha_composite(speaker_rows(active, level_at(cur, tt) if cur else 0, tt))
    if cur: draw_caption(im, cur, tt)
    # gags
    for i, (txt, col) in STAMP.items():
        s = segs[i]
        if s["t0"] + 0.3 <= tt <= s["t1"] + 0.6: stamp(im, txt, col, tt - s["t0"] - 0.3)
    for i, e in EMO.items():
        s = segs[i]
        if s["t0"] <= tt <= s["t1"] + 0.9:
            k = tt - s["t0"]; x = int(-160 + (W + 160) * ((k / 2.2) % 1)) if i == 8 else 900
            y = 760 + int(10 * math.sin(k * 8))
            im.alpha_composite(e, (x, y))
    im.alpha_composite(FOOT, (0, H - 230))
    if tt > TOTAL - OUTRO + 0.6:
        k = min(1, (tt - (TOTAL - OUTRO + 0.6)) / 0.5)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, int(200 * k))); od = ImageDraw.Draw(ov)
        a = int(255 * k)
        od.text((W / 2, 760), "TIP-OFF 7 PM ET", font=font("Black", 86), fill=GOLD + (a,), anchor="mm")
        od.text((W / 2, 860), "YSU at Central Michigan", font=font("Bold", 52), fill=(255, 255, 255, a), anchor="mm")
        od.text((W / 2, 930), "Wright St. at Toledo", font=font("Bold", 52), fill=(255, 255, 255, a), anchor="mm")
        od.text((W / 2, 1000), "Both on ESPN+", font=font("SemiBold", 40), fill=(220, 210, 195, a), anchor="mm")
        od.text((W / 2, 1120), "Every line and our model: hardwoodbricks.com", font=font("SemiBold", 34), fill=GOLD + (a,), anchor="mm")
        od.text((W / 2, 1200), "Matthew and Pastor Bumrod: AI models of Matthew Hagan's voice.", font=font("Medium", 26), fill=(210, 200, 190, a), anchor="mm")
        od.text((W / 2, 1240), "Cynthia: a synthetic voice. Pastor Bumrod is a fictional character.", font=font("Medium", 26), fill=(210, 200, 190, a), anchor="mm")
        im.alpha_composite(ov)
    return im.convert("RGB")

if "--frame" in sys.argv:
    t = float(sys.argv[sys.argv.index("--frame") + 1]); frame(int(t * FPS)).save(OUT.with_suffix(f".{t}.png")); sys.exit()

N = int(TOTAL * FPS)
p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                      "-i", str(apath), "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                      "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-14:TP=-1.5", "-shortest", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
for n in range(N):
    p.stdin.write(frame(n).tobytes())
    if n % 300 == 0: print(n, "/", N, file=sys.stderr)
p.stdin.close(); p.wait()
print("wrote", OUT, file=sys.stderr)
