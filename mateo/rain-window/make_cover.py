"""One-time: draws cover-overlay.png (committed), so the workflow needs no fonts."""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W, H = 1280, 720
S = '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf'
SI = '/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf'
SA = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
band = Image.new('L', (W, H), 0); ImageDraw.Draw(band).rectangle([0, 0, W, 175], fill=185)
ov.putalpha(band.filter(ImageFilter.GaussianBlur(30)))
d = ImageDraw.Draw(ov)
m = Image.open('/mnt/project-files/mid-mateo/test-scene/stills/mateo-still.jpg').convert('RGB')
face = m.crop((330, 40, 750, 460)).resize((112, 112), Image.LANCZOS)
mask = Image.new('L', (112, 112), 0); ImageDraw.Draw(mask).ellipse([0, 0, 111, 111], fill=255)
cx, cy = 150, 86
for k in range(36):
    a = 2 * math.pi * k / 36; x = cx + 64 * math.cos(a); y = cy + 64 * math.sin(a)
    d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(205, 25, 45, 255) if k % 2 else (225, 225, 232, 255))
    d.ellipse([x - 1.5, y - 2.5, x + .5, y - .5], fill=(255, 255, 255, 230))
ov.paste(face, (cx - 56, cy - 56), mask)
d.text((236, 30), "Rain on Mateo's Window", font=ImageFont.truetype(S, 62), fill=(220, 232, 255, 255))
d.text((240, 104), "8 hours of soft rain + deep brown noise for sleep", font=ImageFont.truetype(SI, 29), fill=(160, 190, 235, 255))
t = "SANDOVAL STUDIOS  ·  @MidMateoSandoval96"; f3 = ImageFont.truetype(SA, 17)
d.text(((W - d.textlength(t, font=f3)) / 2, 690), t, font=f3, fill=(190, 200, 225, 220))
ov.save('cover-overlay.png')
