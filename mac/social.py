"""Post new recaps and previews to Bluesky, after every edition is built.

    python -m mac.collect social

Source: each edition's news-sitemap.xml, which already lists only canonical game pages
published in the last two days, with their headlines. A story is posted once (recap and
preview of the same game are separate stories), only if it was published within
FRESH_HOURS, and at most MAX_PER_RUN per run, so a backlog never floods the feed.
What was posted is kept in data/social_posted.json.

Needs two repo secrets, set by the account owner: BSKY_HANDLE (e.g. hardwoodbricks.bsky.social)
and BSKY_APP_PASSWORD (an app password from Bluesky settings, never the account password).
Without them this does nothing. SOCIAL_DRY_RUN=1 prints the posts instead of sending them.
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
                        "page": site_root / rel if rel else None, "league": lg.short})
    return out


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
    """The post body: the headline and a tag for the conference. The link rides in the card."""
    tag = "#" + re.sub(r"\W", "", it["league"])
    return f"{it['title']}\n\n{tag} #CollegeBasketball"[:290]


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


def run(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    handle, password = os.environ.get("BSKY_HANDLE", "").strip(), os.environ.get("BSKY_APP_PASSWORD", "").strip()
    dry = os.environ.get("SOCIAL_DRY_RUN") == "1"
    if not dry and not (handle and password):
        return "social: no Bluesky secrets set, skipped"
    posted = json.loads(POSTED.read_text()) if POSTED.exists() else {}
    todo = due(stories(), posted, now)
    if dry:
        return "\n".join(f"[dry] {text_for(it)!r} -> {it['url']}" for it in todo) or "social: nothing new"
    sess = _session(handle, password)
    n = 0
    for it in todo:
        try:
            post(sess, it, now)
        except requests.RequestException as e:
            print(f"social: {it['url']} failed: {e}")
            continue
        posted[it["key"]] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        n += 1
    cutoff = (now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    posted = {k: v for k, v in posted.items() if v >= cutoff}
    POSTED.write_text(json.dumps(dict(sorted(posted.items())), indent=0) + "\n")
    return f"social: posted {n} of {len(todo)}"
