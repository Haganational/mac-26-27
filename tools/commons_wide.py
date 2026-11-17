"""Wide free-license image sweep for a doc: many candidates per query, contact sheets to pick from.

    python tools/commons_wide.py docs/thurmond/scout_queries.json docs/thurmond/scout

Queries file: {"search": [[key, query], ...], "category": [[key, "Category:Name"], ...], "loc": [[key, query], ...]}.
Keeps Wikimedia Commons files that are public domain, CC0, CC BY or CC BY-SA (license from the file's
own metadata) and Library of Congress items (rights text recorded for review). Writes 640px thumbs
<out>/<key>-<n>.jpg, <out>/candidates.json and numbered contact sheets <out>/sheet-<key>.jpg.
"""
import json, re, sys, html, time
from pathlib import Path
from io import BytesIO
import requests
from PIL import Image, ImageDraw, ImageOps

UA = {"User-Agent": "HardwoodBricksDocs/1.0 (https://hardwoodbricks.com)"}
FREE = re.compile(r"public domain|^pd|cc0|cc[ -]by(-sa)?[ -]\d|cc[ -]by(-sa)?$", re.I)
API = "https://commons.wikimedia.org/w/api.php"
clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def info(params):
    base = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size", "iiurlwidth": 1600}
    r = requests.get(API, headers=UA, timeout=40, params={**base, **params})
    return sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))


def keep(key, pages, n):
    got = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png", "image/tiff", "image/webp"):
            continue
        md = ii.get("extmetadata", {})
        lic = clean(md.get("LicenseShortName", {}).get("value"))
        if not FREE.search(lic):
            continue
        got.append({"key": key, "source": "Wikimedia Commons", "title": p["title"], "page": ii.get("descriptionurl"),
                    "image": ii.get("thumburl") or ii.get("url"), "full": ii.get("url"), "w": ii.get("width"), "h": ii.get("height"),
                    "author": clean(md.get("Artist", {}).get("value"))[:200], "date": clean(md.get("DateTimeOriginal", {}).get("value"))[:60],
                    "license": lic, "license_url": clean(md.get("LicenseUrl", {}).get("value")),
                    "description": clean(md.get("ImageDescription", {}).get("value"))[:400]})
        if len(got) >= n:
            break
    return got


def loc(key, q, n):
    r = requests.get("https://www.loc.gov/pictures/search/", headers=UA, timeout=60, params={"q": q, "fo": "json", "c": 40})
    got = []
    for it in r.json().get("results", []):
        im = (it.get("image") or {}).get("full") or (it.get("image") or {}).get("medium")
        if not im:
            continue
        im = im if im.startswith("http") else "https:" + im
        got.append({"key": key, "source": "Library of Congress", "title": clean(it.get("title")), "page": it.get("links", {}).get("item"),
                    "image": im, "full": im, "author": clean(it.get("creator")), "date": it.get("created_published_date", ""),
                    "license": "see item page (rights advisory)", "license_url": "", "description": clean(it.get("subjects") and ", ".join(it["subjects"]) or "")[:300]})
        if len(got) >= n:
            break
    return got


def sheet(items, path):
    cols, tw, th = 5, 300, 220
    rows = (len(items) + cols - 1) // cols
    S = Image.new("RGB", (cols * tw, rows * (th + 40)), "white")
    d = ImageDraw.Draw(S)
    for i, it in enumerate(items):
        x, y = (i % cols) * tw, (i // cols) * (th + 40)
        try:
            im = Image.open(it["_local"]).convert("RGB"); im = ImageOps.contain(im, (tw - 8, th - 8)); S.paste(im, (x + 4, y + 4))
        except Exception:
            pass
        d.text((x + 4, y + th), f"{it['file']}  {it['license'][:18]}", fill="black")
        d.text((x + 4, y + th + 14), (it["date"] or "")[:30], fill="gray")
    S.save(path, quality=80)


def main(qfile, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    Q = json.load(open(qfile)); allc = []; seen = set()
    jobs = [("search", k, q) for k, q in Q.get("search", [])] + [("category", k, q) for k, q in Q.get("category", [])] + [("loc", k, q) for k, q in Q.get("loc", [])]
    for kind, key, q in jobs:
        try:
            if kind == "search":
                got = keep(key, info({"generator": "search", "gsrsearch": q, "gsrnamespace": 6, "gsrlimit": 40}), 20)
            elif kind == "category":
                got = keep(key, info({"generator": "categorymembers", "gcmtitle": q, "gcmtype": "file", "gcmlimit": 60}), 30)
            else:
                got = loc(key, q, 15)
        except Exception as e:
            print(key, "ERR", e); continue
        items = []
        for c in got:
            if c["image"] in seen:
                continue
            seen.add(c["image"])
            c["file"] = f"{key}-{len(items) + 1}.jpg"
            try:
                r = requests.get(c["image"], headers=UA, timeout=60); r.raise_for_status()
                im = Image.open(BytesIO(r.content)).convert("RGB"); im.thumbnail((640, 640)); im.save(out / c["file"], quality=82)
                c["_local"] = str(out / c["file"]); items.append(c)
            except Exception as e:
                print("  skip", c["title"], e)
            time.sleep(0.3)
        if items:
            sheet(items, out / f"sheet-{key}.jpg")
        print(f"{kind:8} {key:28} {len(items)}")
        allc += items
    for c in allc:
        c.pop("_local", None)
    json.dump(allc, open(out / "candidates.json", "w"), indent=1)
    print("total", len(allc))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
