"""Download full-resolution files listed in docs/<doc>/fetch_list.json into docs/<doc>/full/ (long side capped at 3000px)."""
import json, sys, time
from io import BytesIO
from pathlib import Path
import requests
from PIL import Image
UA = {"User-Agent": "HardwoodBricksDocs/1.0 (https://hardwoodbricks.com)"}
lst, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
for it in json.loads(lst.read_text()):
    dst = out / f"{it['name']}.jpg"
    if dst.exists(): continue
    for a in range(3):
        try:
            r = requests.get(it["url"], headers=UA, timeout=90); r.raise_for_status()
            im = Image.open(BytesIO(r.content)).convert("RGB"); im.thumbnail((3000, 3000))
            im.save(dst, quality=92); print("ok", dst, im.size); break
        except Exception as e:
            print("retry", it["name"], e); time.sleep(5)
    time.sleep(1)
