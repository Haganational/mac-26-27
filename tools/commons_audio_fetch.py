"""One-off helper: fetch freely licensed audio from Wikimedia Commons (runs in GitHub Actions).

    python tools/commons_audio_fetch.py ep3/audio.json ep3/audio/
"""
import json, re, sys, urllib.parse, urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "HardwoodBricksBot/1.0 (https://hardwoodbricks.com)"}
FREE = re.compile(r"^(CC0|CC BY(-SA)? ?[0-9.]*|Public domain|PD.*)$", re.I)


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()


def strip(h):
    return re.sub(r"<[^>]+>", "", h or "").strip()


queries, out = json.load(open(sys.argv[1])), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
credits, seen = [], set()
for key, qs in queries.items():
    n = 0
    for q in qs:
        params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": "6",
                  "gsrsearch": q + " filetype:audio", "gsrlimit": "15", "prop": "imageinfo",
                  "iiprop": "url|size|mime|extmetadata"}
        d = json.loads(get(API + "?" + urllib.parse.urlencode(params)))
        for p in sorted((d.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99)):
            ii = (p.get("imageinfo") or [{}])[0]
            m = ii.get("extmetadata", {})
            lic = strip(m.get("LicenseShortName", {}).get("value", ""))
            if p["title"] in seen or not FREE.match(lic) or ii.get("size", 0) > 12_000_000 or not ii.get("url"):
                continue
            seen.add(p["title"]); n += 1
            ext = ii["url"].rsplit(".", 1)[-1].lower()
            name = f"{key}-{n}.{ext}"
            (out / name).write_bytes(get(ii["url"]))
            credits.append({"file": name, "title": p["title"], "author": strip(m.get("Artist", {}).get("value", "")),
                            "license": lic, "url": ii.get("descriptionurl"), "query": q})
            print(name, p["title"], lic)
            if n >= 5:
                break
        if n >= 5:
            break
(out / "credits.json").write_text(json.dumps(credits, indent=1))
