"""Post vertical promo reels: YouTube Shorts first, then Facebook, Instagram, Threads and Bluesky.

    PYTHONPATH=<checkout of main> python promos/post.py promos/<name>/promo.json

Trimmed copy of the film promo poster (branch claude/project-thread-vgi1wa) for a stand-alone teaser:
every post carries "link_label: main_url" (default "Watch the full film"), and "blurb" replaces the
film line in the YouTube description. "stage": "done" skips, "dry" prints the plan, "youtube" uploads
the Shorts only, "all" uploads and cross-posts. Each network is checked for the reel's title first,
so a re-run only fills gaps and never posts twice.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mac import reels as R
from mac import youtube as Y


def yt_short(token: str, mp4: Path, thumb: Path, title: str, text: str, m: dict) -> str:
    if Y.already_up(token, title):
        return "already on the channel"
    desc = f"{text}\n\n{m['link_label']}: {m['main_url']}\n\n{m['blurb']}\n\n{m['disclosure']}\n\n#Shorts {m['tags']}"
    meta = {"snippet": {"title": title[:100], "categoryId": "17", "defaultLanguage": "en", "defaultAudioLanguage": "en",
                        "description": desc, "tags": m.get("yt_tags", [])},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    _, head = Y._call(f"{Y.UPLOAD}/videos?uploadType=resumable&part=snippet,status", token, json.dumps(meta).encode())
    vid = Y._call(head.get("Location") or head.get("location"), token, mp4.read_bytes(), "video/mp4", "PUT")[0]["id"]
    try:
        Y._call(f"{Y.UPLOAD}/thumbnails/set?videoId={vid}&uploadType=media", token, thumb.read_bytes(), "image/jpeg")
    except Exception as ex:  # noqa: BLE001 - a Short keeps its own first frame if the thumbnail is refused
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
    if stage == "done":
        print(f"{path.parent.name}: released, nothing to do"); return
    cid, secret, refresh = (os.environ.get(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    token = Y.access_token(cid, secret, refresh) if cid and secret and refresh else ""
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip() or R.REPO
    link = f"{m['link_label']}: {m['main_url']}"
    failed = 0
    for r in m["reels"]:
        mp4 = path.parent / r["file"]
        long_text = f"{r['title']}\n\n{r['text']}\n\n{link}\n\n{m['tags']}\n\n{m['disclosure']}"
        short_tags = m["tags"]
        short_text = f"{r['title']}\n\n{r['text']}{m.get('short_note', '')}\n\n{link}\n\n{short_tags}"
        while len(short_text) > 300 and " " in short_tags:  # Bluesky's limit: drop tags from the end, never the link
            short_tags = short_tags.rsplit(" ", 1)[0]
            short_text = f"{r['title']}\n\n{r['text']}{m.get('short_note', '')}\n\n{link}\n\n{short_tags}"
        assert len(short_text) <= 300, len(short_text)
        url = f"https://github.com/{repo}/releases/download/{m['release']}/{r['file']}"
        nets = R.networks("midmaxx60")
        if stage == "dry":
            print(f"--- {r['file']}\n[long]\n{long_text}\n[short]\n{short_text}\n[would post to] youtube, {', '.join(nets)}")
            continue
        try:
            print(f"youtube: {r['title']}: {yt_short(token, mp4, path.parent / r['thumb'], r['title'], r['text'], m)}")
        except Exception as ex:  # noqa: BLE001
            failed += 1
            body = ex.read().decode(errors="replace")[:400] if hasattr(ex, "read") else ""
            print(f"youtube failed: {ex} {body}")
            if "quota" not in body.lower():
                continue  # YouTube goes first; do not cross-post a reel that is not on YouTube
            print("youtube: out of daily upload quota; cross-posting anyway, the Short goes up on a later re-run")
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
