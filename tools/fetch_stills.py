"""Download exact Wikimedia Commons files listed in <doc>/stills.json, re-checking each license.

    python tools/fetch_stills.py docs/falcons45

Writes <doc>/stills/<key>.jpg (longest side 2000 px), <doc>/stills/credits.json and
<doc>/stills/contact.jpg. Files whose license is not public domain, CC0, CC BY or CC BY-SA
are skipped and listed in credits.json under "skipped".
"""
import html, io, json, re, sys, time
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageOps

UA = {"User-Agent": "HardwoodBricksDocs/1.0 (https://hardwoodbricks.com)"}
FREE = re.compile(r"public domain|^pd|cc0|cc[ -]by(-sa)?[ -]\d|cc[ -]by(-sa)?$", re.I)


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def main():
    doc = Path(sys.argv[1]); spec = json.load(open(doc / "stills.json"))["files"]
    out = doc / "stills"; out.mkdir(parents=True, exist_ok=True)
    credits, skipped, thumbs = [], [], []
    for key, title in spec.items():
        try:
            r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
                "action": "query", "format": "json", "titles": title, "prop": "imageinfo",
                "iiprop": "url|extmetadata", "iiurlwidth": 2000})
            p = next(iter(r.json()["query"]["pages"].values()))
            ii = p["imageinfo"][0]; md = ii.get("extmetadata", {})
            lic = clean(md.get("LicenseShortName", {}).get("value"))
            if not FREE.search(lic):
                skipped.append({"key": key, "title": title, "license": lic}); continue
            img = Image.open(io.BytesIO(requests.get(ii.get("thumburl") or ii["url"], headers=UA, timeout=60).content))
            img = ImageOps.exif_transpose(img).convert("RGB"); img.thumbnail((2000, 2000))
            img.save(out / f"{key}.jpg", quality=90)
            thumbs.append((key, img.copy()))
            credits.append({"key": key, "title": title, "page": ii.get("descriptionurl"), "license": lic,
                            "license_url": clean(md.get("LicenseUrl", {}).get("value")),
                            "author": clean(md.get("Artist", {}).get("value"))[:200],
                            "date": clean(md.get("DateTimeOriginal", {}).get("value"))[:40],
                            "credit": clean(md.get("Credit", {}).get("value"))[:200],
                            "description": clean(md.get("ImageDescription", {}).get("value"))[:300]})
            print("ok", key, lic)
        except Exception as e:
            skipped.append({"key": key, "title": title, "error": str(e)[:200]}); print("FAIL", key, e)
        time.sleep(1)
    json.dump({"credits": credits, "skipped": skipped}, open(out / "credits.json", "w"), indent=1, ensure_ascii=False)
    cols, cw, ch = 6, 320, 260
    sheet = Image.new("RGB", (cols * cw, ((len(thumbs) + cols - 1) // cols) * ch), "white"); d = ImageDraw.Draw(sheet)
    for i, (k, im) in enumerate(thumbs):
        im.thumbnail((cw - 10, ch - 30)); x, y = (i % cols) * cw, (i // cols) * ch
        sheet.paste(im, (x + 5, y + 5)); d.text((x + 5, y + ch - 22), k, fill="black")
    sheet.save(out / "contact.jpg", quality=85)


if __name__ == "__main__":
    main()
