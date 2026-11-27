"""Upload a show to the YouTube channel: the daily MidMaxx60 Short, or the weekly Big Mid.

Needs three repo secrets, set by the channel owner: YT_CLIENT_ID and YT_CLIENT_SECRET (an OAuth
client from a Google Cloud project with the YouTube Data API turned on) and YT_REFRESH_TOKEN
(granted once by the channel's Google account with the youtube.upload and youtube.force-ssl
scopes). The repo variable YT_PRIVACY is optional: public (default), unlisted or private.
Without the secrets this prints a warning and exits cleanly, so the release still publishes.
A day that already uploaded is skipped, so a re-run never posts a duplicate. Every upload declares
altered or synthetic content, because the anchors' faces and voices are AI-generated.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from . import alert
from . import tags as hashtags

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"
SPORTS = "17"  # YouTube category id
TAGS = ["MidMaxx60", "Midmaxxing", "mid-major basketball", "college basketball", "Hardwood Bricks"]
SHOWS = {"midmaxx60": ("MidMaxx60: the mid-majors in 60 seconds", ("#Shorts",)),
         "bigmid": ("The Big Mid: the week in mid-majors", ()),
         "lockclip": ("The Lock Call: the day's picks", ("#Shorts",))}
VERTICAL = {"midmaxx60", "lockclip"}  # Shorts


def show_of(stem: str) -> str:
    """midmaxx60-2026-11-12 -> midmaxx60, lockclip-2026-11-27 -> lockclip."""
    return next((s for s in SHOWS if stem.startswith(s + "-")), "midmaxx60")


def title(stem: str) -> str:
    """midmaxx60-2026-11-12 -> 'MidMaxx60: the mid-majors in 60 seconds, Nov. 12'."""
    show = SHOWS[show_of(stem)][0]
    try:
        d = date.fromisoformat(stem[-10:])
        return f"{show}, {d.strftime('%b')}. {d.day}".replace("May.", "May")
    except ValueError:
        return show


def body(stem: str, description: str, privacy: str, specific: list[str] | None = None) -> dict:
    """The video resource. YouTube allows 100 characters of title and 5,000 of description, no angle brackets.
    The description ends on five hashtags at most (YouTube shows the first three above the title); the
    day's schools and conferences also go in the search tags, as plain words."""
    text = description.replace("<", "").replace(">", "").strip()
    first = SHOWS[show_of(stem)][1]
    specific = specific or []
    tags = hashtags.line(first=[*first, *specific[:2]])  # school and conference among the three shown
    words = [re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t.lstrip("#")) for t in specific]
    return {"snippet": {"title": title(stem)[:100], "description": (text + "\n\n" + tags)[:5000],
                        "tags": TAGS + [w for w in words if w not in TAGS], "categoryId": SPORTS, "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": privacy if privacy in ("public", "unlisted", "private") else "public",
                       "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}


def _call(url: str, token: str = "", data: bytes | None = None, ctype: str = "application/json", method: str | None = None) -> tuple[dict, dict]:
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data is not None else "GET"))
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", ctype)
    with urllib.request.urlopen(req, timeout=300) as r:
        raw = r.read()
        return (json.loads(raw) if raw.strip() else {}), dict(r.headers)


def access_token(cid: str, secret: str, refresh: str) -> str:
    form = urllib.parse.urlencode({"client_id": cid, "client_secret": secret, "refresh_token": refresh, "grant_type": "refresh_token"}).encode()
    return _call(TOKEN_URL, data=form, ctype="application/x-www-form-urlencoded")[0]["access_token"]


def already_up(token: str, name: str) -> bool:
    """True when the channel's recent uploads already carry this title."""
    ch = _call(f"{API}/channels?part=contentDetails&mine=true", token)[0]
    lists = [c["contentDetails"]["relatedPlaylists"]["uploads"] for c in ch.get("items", [])]
    if not lists:
        return False
    items = _call(f"{API}/playlistItems?part=snippet&maxResults=15&playlistId={lists[0]}", token)[0].get("items", [])
    return any(i["snippet"]["title"] == name for i in items)


def upload(out: Path, token: str, privacy: str, show: str = "midmaxx60") -> str | None:
    mp4 = sorted(out.glob(f"{show}-*.mp4"))[-1]
    stem = mp4.stem
    meta = body(stem, (out / f"{stem}.txt").read_text() if (out / f"{stem}.txt").exists() else "", privacy,
                hashtags.from_file(out / f"{stem}.tags"))
    if already_up(token, meta["snippet"]["title"]):
        print(f"youtube: {meta['snippet']['title']!r} is already on the channel, not uploading again")
        return None
    _, head = _call(f"{UPLOAD}/videos?uploadType=resumable&part=snippet,status", token, json.dumps(meta).encode())
    session = head.get("Location") or head.get("location")
    video = _call(session, token, mp4.read_bytes(), "video/mp4", "PUT")[0]
    vid = video["id"]
    print(f"youtube: uploaded https://youtube.com/{'shorts/' if show in VERTICAL else 'watch?v='}{vid} ({video.get('status', {}).get('privacyStatus')})")
    # Thumbnail and captions are extras: a failure there must not fail the upload.
    for label, path, url, ctype in (
        ("thumbnail", out / f"{stem}-thumb.png", f"{UPLOAD}/thumbnails/set?videoId={vid}&uploadType=media", "image/png"),):
        try:
            if path.exists():
                _call(url, token, path.read_bytes(), ctype)
        except Exception as e:  # noqa: BLE001
            print(f"youtube: {label} not set ({e})")
    return vid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--show", default="midmaxx60", choices=sorted(SHOWS))
    a = ap.parse_args()
    name = {"bigmid": "The Big Mid", "lockclip": "The Lock Call clip"}.get(a.show, "MidMaxx60")
    cid, secret, refresh = (os.environ.get(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    if not (cid and secret and refresh):
        print("::warning::YouTube upload skipped: the YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN secrets are not set")
        return
    try:
        upload(Path(a.out), access_token(cid, secret, refresh), os.environ.get("YT_PRIVACY", "").strip() or "public", a.show)
    except urllib.error.HTTPError as e:
        alert.send(f"{name} did not upload to YouTube", f"YouTube answered {e.code}: {e.read().decode(errors='replace')[:600]}")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        alert.send(f"{name} did not upload to YouTube", repr(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
