"""Post a video to Mateo Sandoval's own YouTube channel (@MidMateoSandoval96), only when asked.

Hardwood Bricks stays the default channel for everything automatic: MidMaxx60, The Big Mid and the
promos read YT_REFRESH_TOKEN and never this one. This script reads YT_REFRESH_TOKEN_MATEO, a token
Matthew granted once with Mateo's channel picked on Google's consent screen. Nothing schedules it:
a post goes up only when a mateo/<slug>/post.json with "go": true is pushed, which happens on
Matthew's say-so.

post.json: {"title", "description", "go": true, "privacy": "public|unlisted|private",
            "video": "video.mp4", "thumbnail": "thumb.jpg" (optional), "short": true}

Safety: before uploading, the token's channel must look like Mateo's (MATEO_CHANNEL_MATCH, default
"Mateo"), so a Bricks token pasted into the wrong secret can never post Mateo videos to Bricks.
Every upload declares synthetic content and opens its description with the AI-persona line.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
from pathlib import Path

from . import alert
from .youtube import API, UPLOAD, SPORTS, _call, access_token, already_up

DISCLOSURE = ("Mateo Sandoval is a fictional AI persona created by Hardwood Bricks. "
              "Not affiliated with the University of New Mexico.")
TAGS = ["Mateo Sandoval", "MidMateoSandoval", "Sandoval Studios", "New Mexico Lobos", "mid-major basketball", "Hardwood Bricks"]


def body(post: dict) -> dict:
    text = post.get("description", "").replace("<", "").replace(">", "").strip()
    if DISCLOSURE not in text:
        text = DISCLOSURE + "\n\n" + text
    title = post["title"].replace("<", "").replace(">", "").strip()
    if post.get("short", True) and "#shorts" not in (title + text).lower():
        text += "\n\n#Shorts"
    privacy = post.get("privacy", "public")
    return {"snippet": {"title": title[:100], "description": text[:5000], "tags": TAGS + post.get("tags", []),
                        "categoryId": SPORTS, "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": privacy if privacy in ("public", "unlisted", "private") else "public",
                       "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}


def channel_title(token: str) -> str:
    items = _call(f"{API}/channels?part=snippet&mine=true", token)[0].get("items", [])
    return items[0]["snippet"]["title"] if items else ""


def post_one(folder: Path, token: str) -> str | None:
    post = json.loads((folder / "post.json").read_text())
    if not post.get("go") or post.get("youtube_id"):
        print(f"mateo: {folder.name} skipped ({'already posted' if post.get('youtube_id') else 'not marked go'})")
        return None
    meta = body(post)
    if already_up(token, meta["snippet"]["title"]):
        print(f"mateo: {meta['snippet']['title']!r} is already on the channel, not uploading again")
        return None
    _, head = _call(f"{UPLOAD}/videos?uploadType=resumable&part=snippet,status", token, json.dumps(meta).encode())
    session = head.get("Location") or head.get("location")
    vid = _call(session, token, (folder / post.get("video", "video.mp4")).read_bytes(), "video/mp4", "PUT")[0]["id"]
    thumb = folder / post.get("thumbnail", "thumb.jpg")
    if thumb.exists():
        try:
            _call(f"{UPLOAD}/thumbnails/set?videoId={vid}&uploadType=media", token, thumb.read_bytes(), "image/jpeg")
        except Exception as e:  # noqa: BLE001
            print(f"mateo: thumbnail not set ({e})")
    url = f"https://youtube.com/{'shorts/' if post.get('short', True) else 'watch?v='}{vid}"
    post["youtube_id"] = vid
    post["url"] = url
    (folder / "post.json").write_text(json.dumps(post, indent=2) + "\n")
    print(f"mateo: uploaded {url}")
    return vid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="*", help="mateo/<slug> folders; default: every folder under mateo/")
    a = ap.parse_args()
    folders = [Path(f) for f in a.folders] or sorted(p.parent for p in Path("mateo").glob("*/post.json"))
    cid, secret, refresh = (os.environ.get(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN_MATEO"))
    if not (cid and secret and refresh):
        print("::warning::Mateo upload skipped: YT_REFRESH_TOKEN_MATEO (or the client secrets) is not set")
        return
    try:
        token = access_token(cid, secret, refresh)
        name = channel_title(token)
        want = os.environ.get("MATEO_CHANNEL_MATCH", "Mateo")
        if want.lower() not in name.lower():
            print(f"::error::YT_REFRESH_TOKEN_MATEO belongs to {name!r}, not Mateo's channel; nothing uploaded")
            sys.exit(1)
        for f in folders:
            post_one(f, token)
    except urllib.error.HTTPError as e:
        alert.send("Mateo video did not upload", f"YouTube answered {e.code}: {e.read().decode(errors='replace')[:600]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
