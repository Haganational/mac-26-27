"""Find free-license B-roll for a documentary and record its credits.

    python tools/broll_scout.py docs/athens/broll_queries.json docs/athens/broll

Wikimedia Commons: searches the File namespace and keeps only public domain, CC0, CC BY
and CC BY-SA files, with author and license from the file's own metadata. Library of
Congress (photos and Chronicling America): keeps items, with their rights text recorded
for review. Writes <out>/<key>-<n>.jpg, <out>/credits.json and <out>/contact.jpg.
"""
import json, re, sys, time, html
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageOps

UA = {"User-Agent": "HardwoodBricksDocs/1.0 (https://hardwoodbricks.com)"}
FREE = re.compile(r"public domain|^pd|cc0|cc[ -]by(-sa)?[ -]\d|cc[ -]by(-sa)?$", re.I)
API = "https://commons.wikimedia.org/w/api.php"


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def commons(key, q, out, n=6):
    r = requests.get(API, headers=UA, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": q, "gsrnamespace": 6,
        "gsrlimit": 15, "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiurlwidth": 1600})
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    got = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii.get("mime", "").startswith("image/") or ii.get("mime") == "image/svg+xml" and False:
            continue
        md = ii.get("extmetadata", {})
        lic = clean(md.get("LicenseShortName", {}).get("value"))
        if not FREE.search(lic):
            continue
        got.append({"key": key, "source": "Wikimedia Commons", "title": p["title"], "page": ii.get("descriptionurl"),
                    "image": ii.get("thumburl") or ii.get("url"), "author": clean(md.get("Artist", {}).get("value")),
                    "date": clean(md.get("DateTimeOriginal", {}).get("value")), "license": lic,
                    "license_url": clean(md.get("LicenseUrl", {}).get("value")),
                    "description": clean(md.get("ImageDescription", {}).get("value"))[:300]})
        if len(got) >= n:
            break
    return got


def loc(key, url, out, n=6):
    r = requests.get(url, headers=UA, timeout=60)
    got = []
    for it in r.json().get("results", []):
        imgs = [u for u in it.get("image_url", []) if u.endswith((".jpg", ".jpeg")) or ".jpg#" in u]
        if not imgs:
            continue
        big = sorted(imgs, key=lambda u: int(re.search(r"#h=(\d+)", u).group(1)) if "#h=" in u else 0)[-1].split("#")[0]
        got.append({"key": key, "source": "Library of Congress", "title": clean(it.get("title")), "page": it.get("url") or it.get("id"),
                    "image": big, "author": clean(", ".join(it.get("contributor", []) or [])), "date": it.get("date", ""),
                    "license": clean(" ".join(it.get("rights", []) if isinstance(it.get("rights"), list) else [it.get("rights") or ""]))[:300] or "see item page",
                    "description": clean(" ".join(it.get("description", []) or []))[:300]})
        if len(got) >= n:
            break
    return got


def main():
    q = json.load(open(sys.argv[1])); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    old = json.load(open(out / "credits.json")) if (out / "credits.json").exists() else []
    have = {it["key"] for it in old}
    items = []
    for key, s in q.get("commons", []):
        if key in have:
            continue
        try:
            items += commons(key, s, out)
        except Exception as e:
            print("commons", key, e)
        time.sleep(1)
    for key, u in q.get("loc", []):
        if key in have:
            continue
        try:
            items += loc(key, u, out)
        except Exception as e:
            print("loc", key, e)
        time.sleep(3)
    kept, thumbs, count = list(old), [], {}
    for it in old:
        try:
            thumbs.append((it["file"], Image.open(out / it["file"]).convert("RGB")))
        except Exception:
            pass
    for it in items:
        count[it["key"]] = count.get(it["key"], 0) + 1
        name = f"{it['key']}-{count[it['key']]}.jpg"
        try:
            b = requests.get(it["image"], headers=UA, timeout=60); b.raise_for_status()
            p = out / name; p.write_bytes(b.content)
            im = Image.open(p).convert("RGB"); im.thumbnail((1920, 1920)); im.save(p, quality=86)
        except Exception as e:
            print("download", name, e); continue
        it["file"] = name; kept.append(it); thumbs.append((name, im))
        time.sleep(0.5)
    json.dump(kept, open(out / "credits.json", "w"), indent=1)
    W, H, cols = 320, 240, 6
    rows = (len(thumbs) + cols - 1) // cols or 1
    sheet = Image.new("RGB", (cols * W, rows * (H + 22)), "white"); d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(thumbs):
        t = im.copy(); t.thumbnail((W, H)); x, y = (i % cols) * W, (i // cols) * (H + 22)
        sheet.paste(t, (x, y)); d.text((x + 4, y + H + 4), name, fill="black")
    sheet.save(out / "contact.jpg", quality=80)
    print(len(kept), "items kept")


if __name__ == "__main__":
    main()
