"""One-off helper for the MAC After Dark Short (runs in GitHub Actions, where Commons is reachable).

    python tools/afterdark_fetch.py afterdark/photos.json afterdark/photos/

Searches Wikimedia Commons for each query, keeps freely licensed photos, downloads a
1600px version of the top few, and writes credits.json (title, author, license, page URL).
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "HardwoodBricksBot/1.0 (https://hardwoodbricks.com)"}
FREE = re.compile(r"^(CC0|CC BY(-SA)? ?[0-9.]*|Public domain|PD.*)$", re.I)


def get(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


def search(q: str) -> list[dict]:
    params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": "6", "gsrsearch": q,
              "gsrlimit": "12", "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": "1600"}
    d = json.loads(get(API + "?" + urllib.parse.urlencode(params)))
    pages = sorted((d.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    return pages


def strip(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


def main() -> None:
    queries, out = json.load(open(sys.argv[1])), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    credits, seen = [], set()
    for key, qs in queries.items():
        n = 0
        for q in qs:
            for p in search(q):
                ii = (p.get("imageinfo") or [{}])[0]
                m = ii.get("extmetadata", {})
                lic = strip(m.get("LicenseShortName", {}).get("value", ""))
                if p["title"] in seen or ii.get("mime") != "image/jpeg" or not FREE.match(lic) or ii.get("width", 0) < 1200:
                    continue
                seen.add(p["title"])
                n += 1
                name = f"{key}-{n}.jpg"
                (out / name).write_bytes(get(ii["thumburl"]))
                credits.append({"file": name, "title": p["title"], "author": strip(m.get("Artist", {}).get("value", "")),
                                "license": lic, "url": ii.get("descriptionurl"), "query": q})
                print(name, p["title"], lic)
                if n >= 5:
                    break
            if n >= 5:
                break
    (out / "credits.json").write_text(json.dumps(credits, indent=1))


if __name__ == "__main__":
    main()
