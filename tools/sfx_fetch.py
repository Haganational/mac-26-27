"""Find free-license sound effects on Wikimedia Commons and download the best few, with credits.

    python tools/sfx_fetch.py docs/<doc>/sfx_queries.json docs/<doc>/sfx

sfx_queries.json: {"queries": ["crowd cheering basketball", ...], "per_query": 4}
Keeps public domain, CC0, CC BY and CC BY-SA only; writes <slug>.<ext> plus credits.json.
"""
import json, re, sys, time
from pathlib import Path
import requests

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "HardwoodBricksDocs/1.0 (sound effects for a documentary; https://hardwoodbricks.com)"}
OK = re.compile(r"^(public domain|pd|cc0|cc by(-sa)? [0-9.]+)", re.I)
spec, out = json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
credits, seen = [], set()
jobs = [("search", q) for q in spec.get("queries", [])] + [("cat", c) for c in spec.get("categories", [])]
for kind, q in jobs:
    base = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata"}
    if kind == "search":
        base.update({"generator": "search", "gsrnamespace": 6, "gsrsearch": f"{q} filemime:audio", "gsrlimit": 20})
    else:
        base.update({"generator": "categorymembers", "gcmtitle": q, "gcmtype": "file", "gcmlimit": 30})
    r = requests.get(API, params=base, headers=UA, timeout=60).json()
    print(kind, q, "->", len(r.get("query", {}).get("pages", {})), r.get("error", ""))
    pages = sorted(r.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    n = 0
    for p in pages:
        if n >= spec.get("per_query", 4) or p["title"] in seen:
            continue
        ii = (p.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
        lic = re.sub("<[^>]+>", "", md.get("LicenseShortName", {}).get("value", "")).strip()
        dur = ii.get("duration") or 0
        if not OK.match(lic):
            print("skip license", lic, p["title"]); continue
        url = ii.get("url", "")
        ext = url.rsplit(".", 1)[-1].lower()
        if ext not in ("ogg", "oga", "wav", "flac", "mp3", "opus"):
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", p["title"][5:].rsplit(".", 1)[0].lower()).strip("-")[:60]
        data = requests.get(url, headers=UA, timeout=120).content
        if len(data) > 40_000_000:
            continue
        (out / f"{slug}.{ext}").write_bytes(data)
        seen.add(p["title"]); n += 1
        credits.append({"file": f"{slug}.{ext}", "query": q, "title": p["title"], "page": ii.get("descriptionurl", ""),
                        "author": re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "")).strip()[:200],
                        "license": lic, "bytes": len(data)})
        print("got", slug, lic)
        time.sleep(1)
(out / "credits.json").write_text(json.dumps(credits, indent=1))
