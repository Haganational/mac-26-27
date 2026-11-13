"""Post new recaps and previews to Bluesky and Threads, after every edition is built.

    python -m mac.collect social

Source: each edition's news-sitemap.xml, which already lists only canonical game pages
published in the last two days, with their headlines. A story is posted once (recap and
preview of the same game are separate stories), only if it was published within
FRESH_HOURS, and at most MAX_PER_RUN per run, so a backlog never floods the feed.
What was posted is kept in data/social_posted.json. Brick of the Week (mac/brick.py) adds one post per
conference on Monday morning, at most BRICK_PER_RUN a run so the six awards are spread out.

Needs two repo secrets, set by the account owner: BSKY_HANDLE (e.g. hardwoodbricks.bsky.social)
and BSKY_APP_PASSWORD (an app password from Bluesky settings, never the account password).
Threads needs THREADS_ACCESS_TOKEN (from a Meta developer app with threads_basic and
threads_content_publish; the token lasts about 60 days). THREADS_USER_ID is optional and
defaults to "me", the account the token belongs to. Each network
posts on its own once its secrets are set; with none, this does nothing. SOCIAL_DRY_RUN=1 prints the posts instead of sending them.
"""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from .config import LEAGUES, SHARED_DIR, SITE_BASE, SITE_ROOT

PDS = "https://bsky.social/xrpc"
POSTED = SHARED_DIR / "social_posted.json"
FRESH_HOURS = 6
MAX_PER_RUN = 8
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "n": "http://www.google.com/schemas/sitemap-news/0.9"}


def kind(title: str) -> str:
    return "preview" if " prediction" in title else "recap"


def stories(site_root: Path = SITE_ROOT) -> list[dict[str, Any]]:
    """Every story in every edition's news sitemap: url, title, published, kind, local page path."""
    out = []
    for lg in LEAGUES.values():
        f = site_root / lg.path / "news-sitemap.xml"
        if not f.exists():
            continue
        try:
            root = ET.fromstring(f.read_text())
        except ET.ParseError:
            continue
        for u in root.findall("s:url", NS):
            loc, title, when = (u.findtext(p, default="", namespaces=NS) for p in
                                ("s:loc", "n:news/n:title", "n:news/n:publication_date"))
            if not (loc and title and when):
                continue
            rel = loc[len(SITE_BASE):] if loc.startswith(SITE_BASE) else ""
            out.append({"url": loc, "title": title, "published": when, "kind": kind(title),
                        "page": site_root / rel if rel else None, "league": lg.short, "tag": lg.hashtag or lg.short})
    return out


def brick_items(site_root: Path = SITE_ROOT) -> list[dict[str, Any]]:
    """This week's Brick of the Week for every edition, one post each, from the edition's brick.json.
    The award is frozen Monday morning, so it is "published" at its freeze time and goes out once."""
    out = []
    for lg in LEAGUES.values():
        f = site_root / lg.path / "brick.json"
        try:
            a = (json.loads(f.read_text()) or {}).get("award")
        except (OSError, ValueError):
            continue
        if not a or not a.get("frozen_at"):
            continue
        from .brick import social_text
        rel = f"{lg.path}brick/{a['week']}.html"
        out.append({"url": SITE_BASE + rel, "title": f"{lg.short} Brick of the Week: {a['winner']['team']}",
                    "published": a["frozen_at"], "kind": "brick", "page": site_root / rel, "league": lg.short,
                    "tag": lg.hashtag or lg.short, "text": social_text(a, lg.short)})
    return out


BRICK_PER_RUN = 2  # six conferences' awards land at once on Monday; spread them over the morning's runs
BRICK_FRESH_HOURS = 24


def due_brick(items: list[dict[str, Any]], posted: dict[str, str], now: datetime, most: int = BRICK_PER_RUN) -> list[dict[str, Any]]:
    """Unposted Brick of the Week awards frozen in the last day, at most `most` a run; the rest wait for the next run."""
    return due(items, posted, now, fresh_hours=BRICK_FRESH_HOURS, most=most)


def due(items: list[dict[str, Any]], posted: dict[str, str], now: datetime,
        fresh_hours: float = FRESH_HOURS, most: int = MAX_PER_RUN) -> list[dict[str, Any]]:
    """Unposted stories published in the last fresh_hours, oldest first."""
    seen, out = set(), []
    for it in items:
        key = f"{it['url']}|{it['kind']}"
        if key in posted or key in seen:
            continue
        try:
            when = datetime.fromisoformat(it["published"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if now - when > timedelta(hours=fresh_hours) or when > now + timedelta(minutes=5):
            continue
        seen.add(key)
        out.append({**it, "key": key, "when": when})
    return sorted(out, key=lambda x: x["when"])[:most]


def _meta(page: Path | None, prop: str) -> str:
    if not page or not page.exists():
        return ""
    m = re.search(rf'<meta (?:name|property)="{re.escape(prop)}" content="([^"]*)"', page.read_text())
    return (m.group(1).replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"').replace("&#34;", '"') if m else "")


def text_for(it: dict[str, Any]) -> str:
    """The post body: the headline (or an item's own text, like Brick of the Week) and a tag for the
    conference. The link rides in the card."""
    tag = "#" + re.sub(r"\W", "", it.get("tag") or it["league"])
    tail = f"\n\n{tag} #CollegeBasketball"
    body = it.get("text") or it["title"]
    return (body if len(body) + len(tail) <= 290 else body[:289 - len(tail)].rsplit(" ", 1)[0] + "…") + tail


def _facets(text: str) -> list[dict[str, Any]]:
    out = []
    b = text.encode()
    for m in re.finditer(rb"#(\w+)", b):
        out.append({"index": {"byteStart": m.start(), "byteEnd": m.end()},
                    "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1).decode()}]})
    return out


def _session(handle: str, password: str) -> dict[str, Any]:
    r = requests.post(f"{PDS}/com.atproto.server.createSession", json={"identifier": handle, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()


def _thumb(sess: dict[str, Any], page: Path | None) -> dict[str, Any] | None:
    img = _meta(page, "og:image")
    if not img.startswith(SITE_BASE):
        return None
    f = SITE_ROOT / img[len(SITE_BASE):]
    if not f.exists() or f.stat().st_size > 950_000:
        return None
    r = requests.post(f"{PDS}/com.atproto.repo.uploadBlob", data=f.read_bytes(), timeout=30,
                      headers={"Authorization": f"Bearer {sess['accessJwt']}", "Content-Type": "image/png"})
    return r.json().get("blob") if r.ok else None


def post(sess: dict[str, Any], it: dict[str, Any], now: datetime) -> str:
    text = text_for(it)
    card: dict[str, Any] = {"uri": it["url"], "title": it["title"][:300],
                            "description": _meta(it.get("page"), "description")[:300]}
    thumb = _thumb(sess, it.get("page"))
    if thumb:
        card["thumb"] = thumb
    record = {"$type": "app.bsky.feed.post", "text": text, "facets": _facets(text), "langs": ["en"],
              "createdAt": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
              "embed": {"$type": "app.bsky.embed.external", "external": card}}
    r = requests.post(f"{PDS}/com.atproto.repo.createRecord", timeout=30,
                      headers={"Authorization": f"Bearer {sess['accessJwt']}"},
                      json={"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record})
    r.raise_for_status()
    return r.json().get("uri", "")


THREADS = "https://graph.threads.net/v1.0"


def post_threads(user_id: str, token: str, it: dict[str, Any]) -> str:
    """A text post with a link card: create the container, then publish it."""
    r = requests.post(f"{THREADS}/{user_id}/threads", timeout=30, data={
        "media_type": "TEXT", "text": text_for(it), "link_attachment": it["url"], "access_token": token})
    r.raise_for_status()
    r2 = requests.post(f"{THREADS}/{user_id}/threads_publish", timeout=30,
                       data={"creation_id": r.json()["id"], "access_token": token})
    r2.raise_for_status()
    return r2.json().get("id", "")


OTHER = ("threads:",)  # prefixes of networks after Bluesky; Bluesky keys carry none


def seen_for(posted: dict[str, str], prefix: str) -> dict[str, str]:
    """The posted keys for one network, without its prefix."""
    if prefix:
        return {k[len(prefix):]: v for k, v in posted.items() if k.startswith(prefix)}
    return {k: v for k, v in posted.items() if not k.startswith(OTHER)}


def _networks() -> list[tuple[str, Any]]:
    """(key prefix, poster) for every network whose secrets are set."""
    nets: list[tuple[str, Any]] = []
    handle, password = os.environ.get("BSKY_HANDLE", "").strip(), os.environ.get("BSKY_APP_PASSWORD", "").strip()
    if handle and password:
        box: dict[str, Any] = {}

        def bsky(it: dict[str, Any], now: datetime) -> str:
            if "s" not in box:
                box["s"] = _session(handle, password)
            return post(box["s"], it, now)
        nets.append(("", bsky))
    uid = os.environ.get("THREADS_USER_ID", "").strip() or "me"
    token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    if token:
        nets.append(("threads:", lambda it, now: post_threads(uid, token, it)))
    return nets


def run(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    dry = os.environ.get("SOCIAL_DRY_RUN") == "1"
    nets = _networks()
    if not dry and not nets:
        return "social: no Bluesky or Threads secrets set, skipped"
    posted = json.loads(POSTED.read_text()) if POSTED.exists() else {}
    if dry:
        todo = due(stories(), posted, now) + due_brick(brick_items(), posted, now)
        return "\n".join(f"[dry] {text_for(it)!r} -> {it['url']}" for it in todo) or "social: nothing new"
    report = []
    for prefix, send in nets:
        seen = seen_for(posted, prefix)
        todo = due(stories(), seen, now) + due_brick(brick_items(), seen, now)
        n = 0
        for it in todo:
            try:
                send(it, now)
            except (requests.RequestException, KeyError) as e:
                print(f"social: {prefix or 'bsky:'}{it['url']} failed: {e}")
                continue
            posted[prefix + it["key"]] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            n += 1
        report.append(f"{(prefix or 'bluesky:').rstrip(':')} {n}/{len(todo)}")
    cutoff = (now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    posted = {k: v for k, v in posted.items() if v >= cutoff}
    POSTED.write_text(json.dumps(dict(sorted(posted.items())), indent=0) + "\n")
    return "social: posted " + ", ".join(report)
