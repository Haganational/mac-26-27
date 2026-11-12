"""One-off helper: stitch a small OpenStreetMap tile grid into one PNG (runs in GitHub Actions).

    python tools/osm_tiles.py <lat> <lon> <zoom> <cols> <rows> <out.png>
Map data (c) OpenStreetMap contributors; credit them wherever the image is shown.
"""
import io, math, sys, time, urllib.request
from PIL import Image

lat, lon, z, cols, rows = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
n = 2 ** z
cx = (lon + 180) / 360 * n
cy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
x0, y0 = int(cx - cols / 2), int(cy - rows / 2)
im = Image.new("RGB", (cols * 256, rows * 256))
for i in range(cols):
    for j in range(rows):
        req = urllib.request.Request(f"https://tile.openstreetmap.org/{z}/{x0 + i}/{y0 + j}.png",
                                     headers={"User-Agent": "HardwoodBricksBot/1.0 (https://hardwoodbricks.com)"})
        im.paste(Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=60).read())).convert("RGB"), (i * 256, j * 256))
        time.sleep(0.6)
im.save(sys.argv[6])
print("center px", (cx - x0) * 256, (cy - y0) * 256)
