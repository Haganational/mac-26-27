"""Post the image cards from mac.cards to Instagram, Facebook, Threads and Bluesky.

    python -m mac.cardpost --dir out/cards --kind potn --tag cards-2026-11-15

The images must already be attached to the GitHub release `--tag` (the workflow uploads them),
because Instagram and Threads fetch images from a public URL. Facebook gets the same URLs;
Bluesky gets the bytes.

Where each kind goes (Matthew's caps, Nov 15 2026: Instagram 2-3 feed posts a day counting the
MidMaxx60 Reel, Facebook 3-4, Threads 4-6, Bluesky more):

  potn     Instagram carousel (10 slides max), Facebook album, Threads carousel, Bluesky (4 images)
  bricked  Facebook, Threads, Bluesky
  slate    Threads, Bluesky
  desk     Instagram, Facebook, Threads, Bluesky

Same secrets and the same never-twice rule as mac.reels: before posting, the network's recent
posts are checked for the first line of the caption this card would post there. A failure on one
network does not stop the others; each emails Matthew and the step fails at the end.
SOCIAL_DRY_RUN=1 prints the plan instead.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from . import alert
from .reels import (GRAPH, PDS, REPO, THREADS, _facets, _ok, _wait, bsky_session, ig_auth, page_token, resolve)

ROUTES = {
    "potn": ("instagram", "facebook", "threads", "bluesky"),
    "bricked": ("facebook", "threads", "bluesky"),
    "slate": ("threads", "bluesky"),
    "desk": ("instagram", "facebook", "threads", "bluesky"),
}
NAMES = {"potn": "Players of the Night", "bricked": "Bricked", "slate": "Tonight's Four", "desk": "Beat the Desk"}
IG_MAX, TH_MAX, BSKY_MAX = 10, 20, 4


def first_line(text: str) -> str:
    return text.strip().split("\n", 1)[0].strip()


def asset_url(tag: str, name: str, repo: str = REPO) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{name}"


def has_secrets(net: str, e: dict[str, str]) -> bool:
    if net == "facebook":
        return bool(e.get("FB_PAGE_ID") and e.get("FB_PAGE_TOKEN"))
    if net == "instagram":
        return bool(e.get("IG_ACCESS_TOKEN") or (e.get("IG_USER_ID") and e.get("FB_PAGE_TOKEN")))
    if net == "threads":
        return bool(e.get("THREADS_ACCESS_TOKEN"))
    if net == "bluesky":
        return bool(e.get("BSKY_HANDLE") and e.get("BSKY_APP_PASSWORD"))
    return False


def networks(kind: str, man: dict[str, Any], env: dict[str, str] | None = None) -> list[str]:
    """The networks this card goes to: routed for its kind, with a caption, and with secrets set."""
    e = {k: v.strip() for k, v in (env if env is not None else os.environ).items()}
    return [n for n in ROUTES.get(kind, ()) if man.get("captions", {}).get(n) and has_secrets(n, e)]


# ---------- Facebook ----------

def fb_posted(page: str, token: str, head: str) -> bool:
    data = _ok(requests.get(f"{GRAPH}/{page}/posts", timeout=30,
                            params={"fields": "message", "limit": 20, "access_token": token})).get("data", [])
    return any((p.get("message") or "").startswith(head) for p in data)


def fb_photos(page: str, token: str, urls: list[str], text: str) -> str:
    if len(urls) == 1:
        return _ok(requests.post(f"{GRAPH}/{page}/photos", timeout=120, data={
            "url": urls[0], "caption": text, "published": "true", "access_token": token})).get("post_id", "")
    ids = [_ok(requests.post(f"{GRAPH}/{page}/photos", timeout=120, data={
        "url": u, "published": "false", "access_token": token}))["id"] for u in urls]
    data = {"message": text, "access_token": token}
    for i, pid in enumerate(ids):
        data[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
    return _ok(requests.post(f"{GRAPH}/{page}/feed", timeout=60, data=data)).get("id", "")


# ---------- Instagram ----------

def ig_posted(user: str, token: str, head: str, host: str) -> bool:
    data = _ok(requests.get(f"{host}/{user}/media", timeout=30,
                            params={"fields": "caption", "limit": 20, "access_token": token})).get("data", [])
    return any((m.get("caption") or "").startswith(head) for m in data)


def _ig_ready(host: str, cid: str, token: str) -> None:
    _wait(lambda: _ok(requests.get(f"{host}/{cid}", timeout=30, params={"fields": "status_code", "access_token": token})).get("status_code", ""),
          {"FINISHED"}, {"ERROR", "EXPIRED"}, "Instagram")


def ig_images(user: str, token: str, urls: list[str], text: str, host: str) -> str:
    if len(urls) == 1:
        cid = _ok(requests.post(f"{host}/{user}/media", timeout=120, data={
            "image_url": urls[0], "caption": text, "access_token": token}))["id"]
    else:
        kids = [_ok(requests.post(f"{host}/{user}/media", timeout=120, data={
            "image_url": u, "is_carousel_item": "true", "access_token": token}))["id"] for u in urls]
        for k in kids:
            _ig_ready(host, k, token)
        cid = _ok(requests.post(f"{host}/{user}/media", timeout=120, data={
            "media_type": "CAROUSEL", "children": ",".join(kids), "caption": text, "access_token": token}))["id"]
    _ig_ready(host, cid, token)
    return _ok(requests.post(f"{host}/{user}/media_publish", timeout=60, data={"creation_id": cid, "access_token": token})).get("id", "")


# ---------- Threads ----------

def th_posted(user: str, token: str, head: str) -> bool:
    data = _ok(requests.get(f"{THREADS}/{user}/threads", timeout=30,
                            params={"fields": "text", "limit": 25, "access_token": token})).get("data", [])
    return any((t.get("text") or "").startswith(head) for t in data)


def _th_ready(cid: str, token: str) -> None:
    _wait(lambda: _ok(requests.get(f"{THREADS}/{cid}", timeout=30, params={"fields": "status", "access_token": token})).get("status", ""),
          {"FINISHED"}, {"ERROR", "EXPIRED"}, "Threads")


def th_images(user: str, token: str, urls: list[str], text: str, alts: list[str]) -> str:
    def item(u: str, alt: str, child: bool) -> dict[str, str]:
        d = {"media_type": "IMAGE", "image_url": u, "access_token": token}
        if alt:
            d["alt_text"] = alt[:1000]
        if child:
            d["is_carousel_item"] = "true"
        return d
    if len(urls) == 1:
        cid = _ok(requests.post(f"{THREADS}/{user}/threads", timeout=120, data={**item(urls[0], alts[0] if alts else "", False), "text": text}))["id"]
    else:
        kids = [_ok(requests.post(f"{THREADS}/{user}/threads", timeout=120, data=item(u, alts[i] if i < len(alts) else "", True)))["id"]
                for i, u in enumerate(urls)]
        for k in kids:
            _th_ready(k, token)
        cid = _ok(requests.post(f"{THREADS}/{user}/threads", timeout=120, data={
            "media_type": "CAROUSEL", "children": ",".join(kids), "text": text, "access_token": token}))["id"]
    _th_ready(cid, token)
    return _ok(requests.post(f"{THREADS}/{user}/threads_publish", timeout=60, data={"creation_id": cid, "access_token": token})).get("id", "")


# ---------- Bluesky ----------

def bsky_posted(sess: dict[str, Any], head: str) -> bool:
    feed = _ok(requests.get(f"{PDS}/app.bsky.feed.getAuthorFeed", timeout=30,
                            headers={"Authorization": f"Bearer {sess['accessJwt']}"},
                            params={"actor": sess["did"], "limit": 50, "filter": "posts_no_replies"})).get("feed", [])
    return any((f.get("post", {}).get("record", {}).get("text") or "").startswith(head) for f in feed)


def bsky_images(sess: dict[str, Any], files: list[Path], text: str, alts: list[str]) -> str:
    auth = {"Authorization": f"Bearer {sess['accessJwt']}"}
    images = []
    for i, f in enumerate(files):
        blob = _ok(requests.post(f"{PDS}/com.atproto.repo.uploadBlob", timeout=120, data=f.read_bytes(),
                                 headers={**auth, "Content-Type": "image/jpeg"}))["blob"]
        images.append({"image": blob, "alt": (alts[i] if i < len(alts) else "")[:2000], "aspectRatio": {"width": 1080, "height": 1350}})
    text = text[:300]
    record = {"$type": "app.bsky.feed.post", "text": text, "facets": _facets(text), "langs": ["en"],
              "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
              "embed": {"$type": "app.bsky.embed.images", "images": images}}
    return _ok(requests.post(f"{PDS}/com.atproto.repo.createRecord", timeout=30, headers=auth,
                             json={"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record})).get("uri", "")


# ---------- the run ----------

def post_one(net: str, man: dict[str, Any], folder: Path, tag: str) -> str:
    e = os.environ
    text = man["captions"][net]
    head = first_line(text)
    files = man["files"]
    alts = man.get("alt", [])
    repo = e.get("GITHUB_REPOSITORY", "").strip() or REPO

    def urls(n: int) -> list[str]:
        return [resolve(asset_url(tag, f, repo)) for f in files[:n]]
    if net == "facebook":
        page = e["FB_PAGE_ID"].strip()
        token = page_token(page, e["FB_PAGE_TOKEN"].strip())
        if fb_posted(page, token, head):
            return "already posted"
        return f"posted {fb_photos(page, token, urls(len(files)), text)}"
    if net == "instagram":
        token, user, host = ig_auth(e)
        if ig_posted(user, token, head, host):
            return "already posted"
        return f"posted {ig_images(user, token, urls(IG_MAX), text, host)}"
    if net == "threads":
        token = e["THREADS_ACCESS_TOKEN"].strip()
        user = e.get("THREADS_USER_ID", "").strip() or "me"
        if th_posted(user, token, head):
            return "already posted"
        return f"posted {th_images(user, token, urls(TH_MAX), text[:500], alts)}"
    if net == "bluesky":
        sess = bsky_session(e["BSKY_HANDLE"].strip(), e["BSKY_APP_PASSWORD"].strip())
        if bsky_posted(sess, head):
            return "already posted"
        return f"posted {bsky_images(sess, [folder / f for f in files[:BSKY_MAX]], text, alts)}"
    raise ValueError(net)


def run(folder: Path, kind: str, tag: str) -> int:
    f = folder / f"{kind}.json"
    if not f.exists():
        print(f"cardpost: no {kind} card in {folder}, nothing to post")
        return 0
    man = json.loads(f.read_text())
    nets = networks(kind, man)
    if os.environ.get("SOCIAL_DRY_RUN") == "1":
        for n in ROUTES.get(kind, ()):
            if man["captions"].get(n):
                print(f"[dry] {kind} -> {n}:\n{man['captions'][n]}\n")
        print(f"[dry] images: {', '.join(man['files'])}\n[dry] would post to: {', '.join(nets) or 'nothing (no secrets set)'}")
        return 0
    failed = 0
    for net in nets:
        try:
            print(f"cardpost: {kind} {net}: {post_one(net, man, folder, tag)}")
        except Exception as ex:  # noqa: BLE001 - one network's trouble must not stop the others
            failed += 1
            print(f"cardpost: {kind} {net} failed: {ex}")
            alert.send(f"{NAMES.get(kind, kind)} card did not post to {net.title()}",
                       f"{type(ex).__name__}: {ex}\n\nRe-running the social cards workflow retries it; networks that "
                       f"already have the card are skipped.")
    return failed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="out/cards")
    ap.add_argument("--kind", required=True)
    ap.add_argument("--tag", required=True, help="the GitHub release holding the images")
    a = ap.parse_args()
    sys.exit(1 if run(Path(a.dir), a.kind, a.tag) else 0)


if __name__ == "__main__":
    main()
