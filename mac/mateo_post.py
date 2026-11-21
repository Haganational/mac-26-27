"""Post a video to Mateo Sandoval's own YouTube channel (@MidMateoSandoval96), only when asked.

Hardwood Bricks stays the default channel for everything automatic: MidMaxx60, The Big Mid and the
promos read YT_REFRESH_TOKEN and never this one. This script reads YT_REFRESH_TOKEN_MATEO, a token
Matthew granted once with Mateo's channel picked on Google's consent screen. Nothing schedules it:
a post goes up only when a mateo/<slug>/post.json with "go": true is pushed, which happens on
Matthew's say-so.

post.json: {"title", "description", "go": true, "privacy": "public|unlisted|private",
            "video": "video.mp4", "thumbnail": "thumb.jpg" (optional), "short": true}
A folder may hold build.py instead of video.mp4 (long sleep videos, hours long): mateo.yml runs it
to make video.mp4 on the runner just before upload, so the big file never sits in the repo.

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

CHUNK = 32 * 1024 * 1024  # long videos (the 8-hour sleep ones) upload in pieces, never read whole


def send_video(session: str, token: str, path: Path) -> str:
    """Upload to a resumable session; returns the video id. Small files go in one request."""
    size = path.stat().st_size
    if size <= CHUNK:
        return _call(session, token, path.read_bytes(), "video/mp4", "PUT")[0]["id"]
    import requests
    with path.open("rb") as f:
        start = 0
        while start < size:
            f.seek(start)
            piece = f.read(CHUNK)
            end = start + len(piece) - 1
            for attempt in range(5):
                try:
                    r = requests.put(session, data=piece, timeout=600, headers={
                        "Authorization": f"Bearer {token}", "Content-Type": "video/mp4",
                        "Content-Range": f"bytes {start}-{end}/{size}"})
                    break
                except requests.RequestException as e:
                    print(f"mateo: chunk at {start} failed ({e}), retrying")
            else:
                raise RuntimeError("upload kept failing")
            if r.status_code in (200, 201):
                return r.json()["id"]
            if r.status_code != 308:
                raise RuntimeError(f"YouTube answered {r.status_code}: {r.text[:300]}")
            got = r.headers.get("Range", "")
            start = int(got.split("-")[1]) + 1 if got else start
            print(f"mateo: {start / size:.0%} uploaded", flush=True)
    raise RuntimeError("upload ended without a video id")

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
    vid = send_video(session, token, folder / post.get("video", "video.mp4"))
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
