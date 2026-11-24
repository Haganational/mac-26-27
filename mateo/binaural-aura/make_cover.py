"""One-time: draws overlay.png (video intro, fades out) and thumb.jpg. Committed, so the runner needs no fonts."""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
W, H = 1280, 720
S = '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf'
SI = '/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf'
SA = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
MATEO = Image.open('/mnt/project-files/mid-mateo/test-scene/stills/mateo-still.jpg').convert('RGB')


def medallion(d, base, cx, cy, r):
    face = MATEO.crop((330, 40, 750, 460)).resize((2 * r, 2 * r), Image.LANCZOS)
    mask = Image.new('L', (2 * r, 2 * r), 0); ImageDraw.Draw(mask).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
    n, R, s = 40, r + 9, max(3, r // 14)
    for k in range(n):
        a = 2 * math.pi * k / n; x = cx + R * math.cos(a); y = cy + R * math.sin(a)
        d.ellipse([x - s, y - s, x + s, y + s], fill=(205, 25, 45, 255) if k % 2 else (225, 225, 232, 255))
        d.ellipse([x - s * .4, y - s * .7, x + s * .1, y - s * .2], fill=(255, 255, 255, 230))
    base.paste(face, (cx - r, cy - r), mask)


def layer(title_size, sub_size, rd_size, r):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh = Image.new('L', (W, H), 0); sd = ImageDraw.Draw(sh)
    sd.rectangle([0, 0, W, 225], fill=175); sd.rectangle([0, H - 200, W, H], fill=150)
    ov.putalpha(sh.filter(ImageFilter.GaussianBlur(35)))
    d = ImageDraw.Draw(ov)
    d.text((48, 34), "Binaural Aura", font=ImageFont.truetype(S, title_size), fill=(255, 236, 214, 255))
    d.text((52, 40 + title_size * 1.12), "Come to bed with me?", font=ImageFont.truetype(SI, sub_size), fill=(255, 168, 200, 255))
    y3 = 40 + title_size * 1.12 + sub_size * 1.25
    f3 = ImageFont.truetype(SI, int(sub_size * 0.72)); fo = ImageFont.truetype(S, int(sub_size * 0.72))
    d.text((54, y3), "SLEEP PLUS", font=fo, fill=(72, 214, 168, 255))
    d.text((54 + d.textlength("SLEEP PLUS ", font=fo), y3), "75 Hz · 6 Hz theta", font=f3, fill=(255, 236, 214, 255))
    medallion(d, ov, W - r - 46, r + 36, r)
    f = ImageFont.truetype(S, rd_size); t = "REST   ·   DIGEST"
    yr = H - rd_size - 34
    d.text(((W - d.textlength(t, font=f)) / 2, yr), t, font=f, fill=(255, 222, 170, 255))
    # translucent lines above REST · DIGEST (50%), composited so the photo shows through
    tl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); td = ImageDraw.Draw(tl)
    f1 = ImageFont.truetype(S, int(rd_size * 0.62)); f2 = ImageFont.truetype(S, int(rd_size * 0.46))
    l1, l2 = "H E A D P H O N E S   O N", "E I G H T   H O U R S   O F   T H E T A"
    y2 = yr - int(rd_size * 0.46) - 18; y1 = y2 - int(rd_size * 0.62) - 12
    td.text(((W - td.textlength(l1, font=f1)) / 2, y1), l1, font=f1, fill=(255, 255, 255, 128))
    td.text(((W - td.textlength(l2, font=f2)) / 2, y2), l2, font=f2, fill=(255, 255, 255, 128))
    ov.alpha_composite(tl)
    return ov

layer(70, 40, 48, 72).save('overlay.png')
import sys, numpy as np; sys.argv = ["x"]; sys.path.insert(0, ".")
import build  # thumbnail = the moment the galaxy blooms out of the Pacific sun
crop = Image.fromarray((np.clip(build.Scene().frame(208), 0, 1) * 255).astype(np.uint8))
th = Image.alpha_composite(crop.convert('RGBA'), layer(92, 50, 56, 96)).convert('RGB')
th.save('thumb.jpg', quality=90)
