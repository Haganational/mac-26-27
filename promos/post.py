"""Post a film's vertical promo reels: YouTube Shorts first, then Facebook, Instagram, Threads and Bluesky.

    PYTHONPATH=<checkout of main> python promos/post.py promos/athens/promo.json

Every post links to the full film on YouTube. The film's link comes from "main_url" in the
manifest or, when that is empty, from the channel's own uploads (the newest title containing
"main_title_contains"). No link, no posts. "stage" in the manifest: "done" skips a released film, "dry" prints the plan,
"youtube" uploads the Shorts only, "all" uploads the Shorts and cross-posts. Each network is
checked for the reel's title first, so a re-run only fills gaps and never posts twice.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mac import reels as R
from mac import youtube as Y

try:  # the tag rule lives on main (mac/tags.py); an older checkout falls back to the manifest's own tag text
    from mac import tags as T
except ImportError:  # pragma: no cover
    T = None

TAGS = "#Athens #Ohio #History #Documentary #HardwoodBricks"
DISCLOSURE = "Ray, Marcus and Simone are fictional AI anchors. The narrator is real."


def tag_line(m: dict, first: tuple[str, ...] = ()) -> str:
    """Town film tags (Matthew, Nov 15 2026): the house line from mac.tags (#Midmaxxing, #CollegeBasketball) plus
    the film's city tags ("city_tags", e.g. ["#ToledoOhio"]) and then its school or conference tags
    ("specific_tags"), five at most. No @-mentions. A manifest without "city_tags" keeps its old "tags" text."""
    if not m.get("city_tags") or T is None:
        return " ".join([*first, m.get("tags", TAGS)])
    return T.line(extra=[*m["city_tags"], *m.get("specific_tags", [])], first=first)


def place(m: dict) -> dict:
    """The video location from the manifest: "location": {"name": "Toledo, Ohio", "lat": 41.65, "lng": -83.54}."""
    loc = m.get("location")
    if not loc:
        return {}
    return {"recordingDetails": {"locationDescription": loc["name"], "location": {"latitude": loc["lat"], "longitude": loc["lng"]}}}


def parts(m: dict) -> str:
    return "snippet,status,recordingDetails" if m.get("location") else "snippet,status"


def find_film(token: str, needle: str) -> str:
    ch = Y._call(f"{Y.API}/channels?part=contentDetails&mine=true", token)[0]
    pl = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    items = Y._call(f"{Y.API}/playlistItems?part=snippet,status&maxResults=50&playlistId={pl}", token)[0].get("items", [])
    for i in items:
        s = i["snippet"]
        if needle.lower() in s["title"].lower() and "#shorts" not in s.get("description", "").lower():
            print(f"film: found {s['title']!r} ({i.get('status', {}).get('privacyStatus')})")
            if i.get("status", {}).get("privacyStatus") != "public":
                raise SystemExit("film: the full film is on the channel but not public yet; make it public, then re-run")
            return f"https://youtu.be/{s['resourceId']['videoId']}"
    return ""


def yt_film(token: str, d: Path, f: dict, m: dict) -> str:
    """Upload the full film itself (public) when the manifest carries a "film" block and it is not on the channel yet."""
    meta = {"snippet": {"title": f["title"][:100], "categoryId": "27", "defaultLanguage": "en", "defaultAudioLanguage": "en",
                        "description": f["description"] + (f"\n\n{tag_line(m)}" if m.get("city_tags") else ""), "tags": m.get("yt_tags", [])},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}, **place(m)}
    _, head = Y._call(f"{Y.UPLOAD}/videos?uploadType=resumable&part={parts(m)}", token, json.dumps(meta).encode())
    vid = Y._call(head.get("Location") or head.get("location"), token, (d / f["file"]).read_bytes(), "video/mp4", "PUT")[0]["id"]
    print(f"film: uploaded https://youtu.be/{vid}")
    try:
        Y._call(f"{Y.UPLOAD}/thumbnails/set?videoId={vid}&uploadType=media", token, (d / f["thumb"]).read_bytes(), "image/jpeg")
        print("film: thumbnail set")
    except Exception as ex:  # noqa: BLE001 - the film stays up; the thumbnail can be set by hand
        print(f"film: thumbnail not set ({ex})")
    return f"https://youtu.be/{vid}"


def rethumb(token: str, title: str, thumb: Path, m: dict) -> str:
    """With "rethumb" set in the manifest, set the thumbnail again on a video that is already up."""
    if not m.get("rethumb"):
        return ""
    ch = Y._call(f"{Y.API}/channels?part=contentDetails&mine=true", token)[0]
    pl = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    for i in Y._call(f"{Y.API}/playlistItems?part=snippet&maxResults=50&playlistId={pl}", token)[0].get("items", []):
        if i["snippet"]["title"] == title:
            try:
                Y._call(f"{Y.UPLOAD}/thumbnails/set?videoId={i['snippet']['resourceId']['videoId']}&uploadType=media", token, thumb.read_bytes(), "image/jpeg")
                return ", thumbnail set"
            except Exception as ex:  # noqa: BLE001
                return f", thumbnail not set ({ex})"
    return ", not found for a thumbnail"


def yt_short(token: str, mp4: Path, thumb: Path, title: str, text: str, film: str, m: dict) -> str:
    if Y.already_up(token, title):
        return "already on the channel" + rethumb(token, title, thumb, m)
    meta = {"snippet": {"title": title[:100], "categoryId": "27", "defaultLanguage": "en", "defaultAudioLanguage": "en",
                        "description": f"{text}\n\nWatch the full film: {film}\n\nLocal history... and college basketball. See more at {R.SITE}\n\n{m.get('disclosure', DISCLOSURE)}\n\n{tag_line(m, ('#Shorts',))}",
                        "tags": m.get("yt_tags", ["Athens Ohio", "Ohio University", "history", "documentary", "Hardwood Bricks"])},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}, **place(m)}
    _, head = Y._call(f"{Y.UPLOAD}/videos?uploadType=resumable&part={parts(m)}", token, json.dumps(meta).encode())
    vid = Y._call(head.get("Location") or head.get("location"), token, mp4.read_bytes(), "video/mp4", "PUT")[0]["id"]
    try:
        Y._call(f"{Y.UPLOAD}/thumbnails/set?videoId={vid}&uploadType=media", token, thumb.read_bytes(), "image/jpeg")
    except Exception as ex:  # noqa: BLE001 - a Short keeps its own frame if the thumbnail is refused
        print(f"youtube: thumbnail not set ({ex})")
    return f"uploaded https://youtube.com/shorts/{vid}"


def cross(net: str, mp4: Path, title: str, long_text: str, short_text: str, url: str) -> str:
    e = os.environ
    if net == "facebook":
        page = e["FB_PAGE_ID"].strip()
        tok = R.page_token(page, e["FB_PAGE_TOKEN"].strip())
        return "already posted" if R.fb_already(page, tok, title) else f"posted {R.fb_reel(page, tok, mp4, long_text)}"
    if net == "instagram":
        tok, user, host = R.ig_auth(e)
        return "already posted" if R.ig_already(user, tok, title, host) else f"posted {R.ig_reel(user, tok, R.resolve(url), long_text, host)}"
    if net == "threads":
        tok, user = e["THREADS_ACCESS_TOKEN"].strip(), e.get("THREADS_USER_ID", "").strip() or "me"
        return "already posted" if R.th_already(user, tok, title) else f"posted {R.th_video(user, tok, R.resolve(url), short_text)}"
    sess = R.bsky_session(e["BSKY_HANDLE"].strip(), e["BSKY_APP_PASSWORD"].strip())
    return "already posted" if R.bsky_already(sess, title) else f"posted {R.bsky_video(sess, mp4, short_text, (1080, 1920))}"


def main() -> None:
    path = Path(sys.argv[1])
    m = json.loads(path.read_text())
    stage = m.get("stage", "dry")
    if stage == "done":   # a released film: never touched again, so a later film's run cannot repost it
        print(f"{path.parent.name}: released, nothing to do"); return
    cid, secret, refresh = (os.environ.get(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    token = Y.access_token(cid, secret, refresh) if cid and secret and refresh else ""
    film = m.get("main_url", "").strip() or (find_film(token, m["main_title_contains"]) if token else "")
    if film and token and m.get("film") and stage != "dry":
        print(f"film: already on the channel{rethumb(token, m['film']['title'], path.parent / m['film']['thumb'], m)}")
    if not film and token and m.get("film") and stage != "dry":
        film = yt_film(token, path.parent, m["film"], m)
    if not film and stage == "dry" and m.get("film"):
        film = "https://youtu.be/(the film, uploaded on the live run)"
    if not film:
        raise SystemExit("film: the full film is not on the channel yet and no main_url is set; nothing posted")
    print(f"film link: {film}")
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip() or R.REPO
    failed = 0
    for r in m["reels"]:
        mp4 = path.parent / r["file"]
        long_text = f"{r['title']}\n\n{r['text']}\n\nWatch the full film: {film}\n\n{tag_line(m)}\n\n{m.get('disclosure', DISCLOSURE)}"
        short_tags = tag_line(m) if m.get("city_tags") and T else m.get("short_tags", "#Athens #Ohio #History")
        short_text = f"{r['title']}\n\nFull film: {film}\n\n{short_tags}"
        while len(short_text) > 300 and " " in short_tags:  # Bluesky's limit: drop tags from the end, never the link
            short_tags = short_tags.rsplit(" ", 1)[0]
            short_text = f"{r['title']}\n\nFull film: {film}\n\n{short_tags}"
        assert len(short_text) <= 300, len(short_text)
        url = f"https://github.com/{repo}/releases/download/{m['release']}/{r['file']}"
        nets = R.networks("midmaxx60")
        if stage == "dry":
            print(f"--- {r['file']}\n[long]\n{long_text}\n[short]\n{short_text}\n[would post to] youtube, {', '.join(nets)}")
            continue
        try:
            print(f"youtube: {r['title']}: {yt_short(token, mp4, path.parent / r['thumb'], r['title'], r['text'], film, m)}")
        except Exception as ex:  # noqa: BLE001
            failed += 1
            body = ex.read().decode(errors="replace")[:400] if hasattr(ex, "read") else ""
            print(f"youtube failed: {ex} {body}")
            continue  # YouTube goes first; do not cross-post a reel that is not on YouTube
        if stage != "all":
            continue
        for net in nets:
            try:
                print(f"{net}: {r['title']}: {cross(net, mp4, r['title'], long_text, short_text, url)}")
            except Exception as ex:  # noqa: BLE001 - one network's trouble must not stop the others
                failed += 1
                print(f"{net} failed: {ex}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
