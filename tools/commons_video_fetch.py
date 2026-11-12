"""One-off helper: fetch freely licensed video clips from Wikimedia Commons (runs in GitHub Actions).

    python tools/commons_video_fetch.py miami/videos.json miami/videos/

For each query keeps free-licensed videos, downloads a 720p-or-smaller WebM transcode
(under 40 MB) of the top few and writes credits.json.
"""
import json, re, sys, urllib.parse, urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "HardwoodBricksBot/1.0 (https://hardwoodbricks.com)"}
FREE = re.compile(r"^(CC0|CC BY(-SA)? ?[0-9.]*|Public domain|PD.*)$", re.I)


def get(url):
    import time
    for wait in (2, 20, 60, 120):
        time.sleep(wait)
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read()
        except Exception as e:  # rate limits: back off and retry
            print("retry", e)
    raise RuntimeError("gave up on " + url)


def strip(h):
    return re.sub(r"<[^>]+>", "", h or "").strip()


def main():
    queries, out = json.load(open(sys.argv[1])), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    credits, seen = [], set()
    for key, qs in queries.items():
        n = 0
        for q in qs:
            params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": "6",
                      "gsrsearch": q + " filetype:video", "gsrlimit": "20", "prop": "videoinfo",
                      "viprop": "url|size|mime|extmetadata|derivatives"}
            d = json.loads(get(API + "?" + urllib.parse.urlencode(params)))
            pages = sorted((d.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
            for p in pages:
                vi = (p.get("videoinfo") or [{}])[0]
                m = vi.get("extmetadata", {})
                lic = strip(m.get("LicenseShortName", {}).get("value", ""))
                if p["title"] in seen or not FREE.match(lic) or vi.get("width", 0) < 640:
                    continue
                ders = [x for x in vi.get("derivatives", []) if "webm" in x.get("type", "") and 360 <= (x.get("height") or 0) <= 1080]
                ders.sort(key=lambda x: -(x.get("height") or 0))
                data = None
                for x in ders:
                    try:
                        data = get(x["src"])
                    except Exception as e:  # transcode missing
                        print("skip", x.get("src"), e)
                        continue
                    if len(data) < 40_000_000:
                        break
                    data = None
                if not data:
                    continue
                seen.add(p["title"]); n += 1
                name = f"{key}-{n}.webm"
                (out / name).write_bytes(data)
                credits.append({"file": name, "title": p["title"], "author": strip(m.get("Artist", {}).get("value", "")),
                                "license": lic, "url": vi.get("descriptionurl"), "query": q})
                print(name, p["title"], lic, len(data))
                if n >= 4:
                    break
            if n >= 4:
                break
    (out / "credits.json").write_text(json.dumps(credits, indent=1))


if __name__ == "__main__":
    main()
