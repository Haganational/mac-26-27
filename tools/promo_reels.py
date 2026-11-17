"""Cut vertical promo reels (1080x1920) from a finished film and its captions.

    python tools/promo_reels.py <film.mp4> <film.srt> <spec.json> <outdir>

spec.json: {"place": "Toledo, Ohio", "subtitle": "A HUNDRED DOLLARS TO FUMBLE", "film_title": "...",
"wide": [caption numbers shown on a title card], "reels": [{"name", "ids": [[caption numbers]...],
"thumb_t": seconds, "head": [lines], "sub": "...", "wide_thumb": false}]}.
Each reel OPENS on its own thumbnail for COVER seconds (Matthew, Nov 15 2026: Threads, Bluesky and
others use the first frame as the cover), then the cut, then the end card.
Optional brand plates (Matthew, Nov 17 2026: "19 North name plate only way in, all on way out"):
"plates_dir": folder of 16:9 logo plates, "open_plates": ["logo-19-north.jpg"] replaces the thumbnail
cover (the plate is then the first frame), "close_plates": [...] play after the end card.
"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

F = Path(__file__).resolve().parent.parent / "templates/static/fonts"
V, SRT, SPEC, R = Path(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text()), Path(sys.argv[4])
R.mkdir(parents=True, exist_ok=True)
PAGE, INK, MUTED, GOLD = (21, 17, 13), (239, 230, 214), (143, 132, 116), (240, 199, 94)
W, H = 1080, 1920
PY, PH = 430, 810  # picture box
WIDE = set(SPEC.get("wide", []))
COVER = 0.8
PLATE_IN, PLATE_OUT = 1.6, 1.4
PLATES = Path(sys.argv[3]).parent / SPEC['plates_dir'] if SPEC.get('plates_dir') else None


def plate(src, path):
    """A 16:9 logo plate set on a 9:16 frame: its centre (wide enough for the logo's wordmark), sharp, over a blurred fill of itself."""
    im = Image.open(src).convert('RGB')
    w, h = im.size
    bg = im.resize((round(w * H / h), H), Image.LANCZOS)
    bg = bg.crop(((bg.width - W) // 2, 0, (bg.width - W) // 2 + W, H)).filter(ImageFilter.GaussianBlur(40))
    cw = round(h * 1.2)
    sq = im.crop(((w - cw) // 2, 0, (w + cw) // 2, h)).resize((W, round(W / 1.2)), Image.LANCZOS)
    bg.paste(sq, (0, (H - sq.height) // 2))
    bg.save(path, quality=94)


def font(n, s):
    return ImageFont.truetype(str(F / n), s)


def ctext(d, y, text, f, fill):
    d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)


def tsec(t):
    h, m, s = t.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


cues = {}
for b in SRT.read_text().strip().split('\n\n'):
    l = b.split('\n')
    a, z = l[1].split(' --> ')
    who, _, txt = ' '.join(l[2:]).partition(': ')
    cues[int(l[0])] = (tsec(a), tsec(z), who, txt)


def canvas(path):
    im = Image.new('RGB', (W, H), PAGE)
    d = ImageDraw.Draw(im)
    ctext(d, 150, 'HARDWOOD BRICKS PRODUCTIONS', font('BarlowCondensed-SemiBold.ttf', 34), GOLD)
    ctext(d, 205, SPEC['place'], font('Newsreader-SemiBold.ttf', 96), INK)
    ctext(d, 325, SPEC['subtitle'], font('BarlowCondensed-SemiBold.ttf', 40), MUTED)
    d.rectangle([0, PY - 3, W, PY - 1], fill=GOLD)
    d.rectangle([0, PY + PH + 1, W, PY + PH + 3], fill=GOLD)
    ctext(d, 1650, 'A HARDWOOD BRICKS DOCUMENTARY', font('BarlowCondensed-SemiBold.ttf', 32), MUTED)
    im.save(path)


def endcard(path):
    im = Image.new('RGB', (W, H), PAGE)
    d = ImageDraw.Draw(im)
    ctext(d, 560, 'Local history...', font('Newsreader-SemiBold.ttf', 104), INK)
    ctext(d, 700, 'and college basketball.', font('Newsreader-SemiBoldItalic.ttf', 84), INK)
    d.rectangle([390, 870, 690, 873], fill=GOLD)
    ctext(d, 930, 'SEE MORE AT', font('BarlowCondensed-SemiBold.ttf', 46), GOLD)
    ctext(d, 1000, 'hardwoodbricks.com', font('Newsreader-SemiBold.ttf', 92), INK)
    ctext(d, 1180, 'FULL FILM: ' + SPEC['film_title'].upper(), font('BarlowCondensed-SemiBold.ttf', 34), MUTED)
    im.save(path)


def at(t):
    cs = round(t * 100)
    return '%d:%02d:%02d.%02d' % (cs // 360000, cs % 360000 // 6000, cs % 6000 // 100, cs % 100)


def chunks(txt, maxc=26):
    out, cur = [], ''
    for w in txt.split():
        if cur and len(cur) + 1 + len(w) > maxc:
            out.append(cur); cur = w
        else:
            cur = (cur + ' ' + w).strip()
        if cur and cur[-1] in '.?!' and len(cur) > 10:
            out.append(cur); cur = ''
    if cur:
        out.append(cur)
    return out


def build(name, ids, thumb_t, head, sub, wide_thumb=False):
    segs, ass, t = [], [], 0.0
    for grp in ids:  # each group is a run of consecutive cues cut as one piece
        a = cues[grp[0]][0] - 0.12
        z = cues[grp[-1]][1] + 0.16
        segs.append((a, z - a))
        for i in grp:
            ca, cz, who, txt = cues[i]
            ra, rz = t + ca - a, t + cz - a
            ass.append(f"Dialogue: 0,{at(ra)},{at(rz)},Name,,0,0,0,,{who}")
            ch = chunks(txt)
            tot = sum(len(c) for c in ch)
            x = ra
            for c in ch:
                dur = (rz - ra) * len(c) / tot
                ass.append(f"Dialogue: 0,{at(x)},{at(x + dur)},Cap,,0,0,0,,{c}")
                x += dur
        t += z - a
    body = t
    (R / f'{name}.ass').write_text(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Barlow SemiBold,74,&H00D6E6EF,&H00D6E6EF,&H000D1115,&H000D1115,0,0,0,0,100,100,0,0,1,0,0,8,70,70,1385,1
Style: Name,Barlow Condensed SemiBold,40,&H005EC7F0,&H005EC7F0,&H000D1115,&H000D1115,0,0,0,0,100,100,2,0,1,0,0,8,70,70,1305,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + '\n'.join(ass) + '\n')
    # thumbnail
    fr = R / f'{name}-frame.png'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(thumb_t), '-i', str(V), '-frames:v', '1', '-vf', ('crop=1280:560:0:0,scale=800:-2,pad=800:600:0:(oh-ih)/2:color=0x15110D' if wide_thumb else 'crop=720:540:280:0,scale=800:600'), str(fr)], check=True)
    pic = Image.open(fr).convert('RGB')
    bg = pic.resize((2560, 1920), Image.LANCZOS).crop((740, 0, 1820, 1920)).filter(ImageFilter.GaussianBlur(30))
    bg = Image.blend(bg, Image.new('RGB', (W, H), PAGE), 0.62)
    bg.paste(pic.resize((W, PH), Image.LANCZOS), (0, 360))
    d = ImageDraw.Draw(bg)
    d.rectangle([0, 357, W, 359], fill=GOLD); d.rectangle([0, 360 + PH, W, 362 + PH], fill=GOLD)
    ctext(d, 200, 'HARDWOOD BRICKS PRODUCTIONS', font('BarlowCondensed-SemiBold.ttf', 40), GOLD)
    y = 1250
    for ln in head:
        ctext(d, y, ln, font('Newsreader-SemiBold.ttf', 124), INK); y += 136
    ctext(d, y + 30, sub, font('BarlowCondensed-SemiBold.ttf', 50), GOLD)
    bg.save(R / f'{name}-thumb.jpg', quality=92)
    canvas(R / 'canvas.png'); endcard(R / 'end.png')
    END = 4.0
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-threads', '2', '-loop', '1', '-framerate', '25', '-t', f'{body:.3f}', '-i', str(R / 'canvas.png')]
    for a, d in segs:
        cmd += ['-ss', f'{a:.3f}', '-t', f'{d:.3f}', '-i', str(V)]
    cmd += ['-loop', '1', '-framerate', '25', '-t', str(END), '-i', str(R / 'end.png'), '-f', 'lavfi', '-t', str(END), '-i', 'anullsrc=r=48000:cl=mono']
    n = len(segs)
    opens = [(R / f'{name}-thumb.jpg', COVER)]
    closes = []
    if PLATES and SPEC.get('open_plates'):
        opens = []
        for i, f in enumerate(SPEC['open_plates']):
            plate(PLATES / f, R / f'plate-in-{i}.jpg'); opens.append((R / f'plate-in-{i}.jpg', PLATE_IN))
    if PLATES:
        for i, f in enumerate(SPEC.get('close_plates', [])):
            plate(PLATES / f, R / f'plate-out-{i}.jpg'); closes.append((R / f'plate-out-{i}.jpg', PLATE_OUT))
    k = n + 3  # next input index
    pre, post = [], []
    for lst, out, fin in ((opens, pre, False), (closes, post, True)):
        for j, (img, d) in enumerate(lst):
            cmd += ['-loop', '1', '-framerate', '25', '-t', str(d), '-i', str(img), '-f', 'lavfi', '-t', str(d), '-i', 'anullsrc=r=48000:cl=mono']
            fade = (f',fade=t=in:d=0.25' if fin or j else '') + (f',fade=t=out:st={d - 0.25:.2f}:d=0.25' if fin and j == len(lst) - 1 else '')
            out.append((f'[{k}:v]format=yuv420p,setsar=1{fade}[p{k}];', f'[p{k}][{k + 1}:a]'))
            k += 2
    fc = ''
    for i, (a, d) in enumerate(segs):
        if ids[i][0] in WIDE:
            fc += f"[{i+1}:v]crop=960:400:160:140,scale={W}:-2:flags=lanczos,pad={W}:{PH}:0:(oh-ih)/2:color=0x15110D,fps=25,format=yuv420p,setsar=1[v{i}];"
        else:
            fc += f"[{i+1}:v]crop=720:540:280:0,scale={W}:{PH}:flags=lanczos,fps=25,format=yuv420p,setsar=1[v{i}];"
        fc += f"[{i+1}:a]aresample=48000,afade=t=in:d=0.06,afade=t=out:st={d-0.08:.3f}:d=0.08[a{i}];"
    fc += ''.join(f'[v{i}][a{i}]' for i in range(n)) + f"concat=n={n}:v=1:a=1[pv][pa];"
    fc += f"[0:v]format=yuv420p[bg];[bg][pv]overlay=0:{PY}:shortest=1,ass={R / (name + '.ass')}:fontsdir={F}[body];"
    fc += f"[{n+1}:v]format=yuv420p,setsar=1,fade=t=in:d=0.4[ev];" + ''.join(a for a, _ in pre + post)
    parts = [b for _, b in pre] + ['[body][pa]', f'[ev][{n+2}:a]'] + [b for _, b in post]
    fc += ''.join(parts) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
    out = R / f'{name}.mp4'
    cmd += ['-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(out)]
    subprocess.run(cmd, check=True)
    print(name, round(sum(d for _, d in opens + closes) + body + END, 2), 's')


for r in SPEC['reels']:
    build(r['name'], r['ids'], r['thumb_t'], r['head'], r['sub'], r.get('wide_thumb', False))
