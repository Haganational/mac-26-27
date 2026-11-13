"""Post new recaps and previews to Bluesky and Threads, after every edition is built.

    python -m mac.collect social

Source: each edition's news-sitemap.xml, which already lists only canonical game pages
published in the last two days, with their headlines. A story is posted once (recap and
preview of the same game are separate stories), only if it was published within
FRESH_HOURS, and at most MAX_PER_RUN per run, so a backlog never floods the feed.
What was posted is kept in data/social_posted.json.

Second source: the Bricks Index. Once a week's capsules are written (data/power/capsules-<monday>.json
in each edition), each conference's ranking posts once, then the capsules go out one per run, best
rank first, in the daytime (Eastern), so 75 of them spread over a couple of days.

Every post carries the story's share card (mac/cards.py): on Bluesky as the link card's image,
on Threads through the page's og:image, or as the 4:5 portrait card for a capsule. Threads reads
from the live site, so a story waits for the run after its page deploys.

A failed post is retried quietly on the next run. When one network has failed
ALERT_AFTER_RUNS runs in a row (an expired login, say), mac.alert emails Matthew, at most
once every ALERT_EVERY_HOURS. The streaks are kept in data/social_failures.json.

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

from . import alert
from .config import LEAGUES, SHARED_DIR, SITE_BASE, SITE_ROOT

PDS = "https://bsky.social/xrpc"
POSTED = SHARED_DIR / "social_posted.json"
FRESH_HOURS = 6
MAX_PER_RUN = 8
FAILURES = SHARED_DIR / "social_failures.json"
ALERT_AFTER_RUNS = 3  # a network must fail this many runs in a row before anyone is emailed
ALERT_EVERY_HOURS = 24  # and then at most one email a day per network
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


def power_stories(now: datetime, site_root: Path = SITE_ROOT) -> list[dict[str, Any]]:
    """The Bricks Index, once a week's capsules are written: the ranking itself, then one item per capsule.

    Only the current week counts, so a late merge still posts but last week's never does."""
    from . import power
    from .cards import first_sentence
    week = power.week_of(now)
    out = []
    for lg in LEAGUES.values():
        d = lg.data_dir / "power"
        snap, caps = power.load(week, d), power.capsules(week, d)
        if not snap or not snap.get("teams") or not caps:
            continue
        wk = f"{int(week[5:7])}/{int(week[8:10])}"
        url = f"{SITE_BASE}{lg.path}power/{week}.html"
        og = site_root / lg.path / "static" / "og"
        top = snap["teams"][0]
        base = {"published": snap.get("frozen_at") or f"{week}T06:00:00-05:00", "page": site_root / lg.path / "power" / f"{week}.html",
                "league": lg.short, "tag": lg.hashtag or lg.short}
        out.append({**base, "url": url, "kind": "power", "image": og / f"power-{week}.png",
                    "title": f"{lg.short} power rankings, week of {wk}: {top['short']} is No. 1"})
        for t in snap["teams"]:
            if caps.get(t["key"]):
                out.append({**base, "url": f"{url}#{t['key']}", "kind": "capsule", "rank": t["rank"],
                            "image": og / f"power-{week}-{t['key']}.png",
                            "title": f"{lg.short} power rankings, No. {t['rank']}: {t['short']}",
                            "text": f"Bricks Index, week of {wk}. No. {t['rank']} {t['short']}: {first_sentence(caps[t['key']], 200)}"})
    return out


CAPSULES_PER_RUN = 1  # about two an hour, so a week's 75 capsules run Monday to Wednesday instead of in one burst
DAY_HOURS = range(8, 23)  # Eastern hours when capsules go out


def due_power(items: list[dict[str, Any]], posted: dict[str, str], now: datetime) -> list[dict[str, Any]]:
    """Each conference's ranking post first, then capsules best rank first, a few per run, daytime only."""
    from zoneinfo import ZoneInfo
    fresh = [{**it, "key": f"{it['url']}|{it['kind']}"} for it in items]
    fresh = [it for it in fresh if it["key"] not in posted and it.get("image") and Path(it["image"]).exists()]
    out = [it for it in fresh if it["kind"] == "power"]
    if now.astimezone(ZoneInfo("America/New_York")).hour in DAY_HOURS:
        out += sorted((it for it in fresh if it["kind"] == "capsule"), key=lambda x: (x["rank"], x["league"]))[:CAPSULES_PER_RUN]
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


def card_file(it: dict[str, Any]) -> Path | None:
    """The story's share card on disk: the item's own image, else the page's og:image."""
    if it.get("image"):
        return Path(it["image"])
    img = _meta(it.get("page"), "og:image")
    return SITE_ROOT / img[len(SITE_BASE):] if img.startswith(SITE_BASE) else None


def card_url(it: dict[str, Any]) -> str:
    f = card_file(it)
    try:
        return SITE_BASE + f.relative_to(SITE_ROOT).as_posix() if f else ""
    except ValueError:
        return ""


def _thumb(sess: dict[str, Any], it: dict[str, Any]) -> dict[str, Any] | None:
    f = card_file(it)
    if not f or not f.exists() or f.stat().st_size > 950_000:
        return None
    r = requests.post(f"{PDS}/com.atproto.repo.uploadBlob", data=f.read_bytes(), timeout=30,
                      headers={"Authorization": f"Bearer {sess['accessJwt']}", "Content-Type": "image/png"})
    return r.json().get("blob") if r.ok else None


def post(sess: dict[str, Any], it: dict[str, Any], now: datetime) -> str:
    text = text_for(it)
    card: dict[str, Any] = {"uri": it["url"], "title": it["title"][:300],
                            "description": (it.get("text") or _meta(it.get("page"), "description"))[:300]}
    thumb = _thumb(sess, it)
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


class NotLive(Exception):
    """The page or card is not on the live site yet (it deploys after this step); try next run."""


def _live(url: str) -> bool:
    try:
        return requests.head(url, timeout=15, allow_redirects=True).ok
    except requests.RequestException:
        return False


def tall_url(it: dict[str, Any]) -> str:
    """The 4:5 portrait card (static/og/ig/), for image posts."""
    u = card_url(it)
    return u.replace("/static/og/", "/static/og/ig/", 1) if "/static/og/" in u else ""


def post_threads(user_id: str, token: str, it: dict[str, Any], live=_live) -> str:
    """Create the container, then publish it. Threads reads the page (or the image) from the live
    site, and this step runs before the deploy, so a story waits until its page is up.

    Recaps, previews and the weekly ranking: a text post with a link card (Threads draws the card
    from the page's og:image). Capsules: an image post with the portrait card and the link in the text,
    since the ranking page's own card would show the whole conference."""
    if not live(it["url"].split("#")[0]):
        raise NotLive(it["url"])
    data = {"text": text_for(it), "access_token": token}
    img = tall_url(it) if it.get("kind") == "capsule" else ""
    if img and live(img):
        data.update(media_type="IMAGE", image_url=img, text=f"{text_for(it)}\n\n{it['url']}"[:500])
    else:
        data.update(media_type="TEXT", link_attachment=it["url"])
    r = requests.post(f"{THREADS}/{user_id}/threads", timeout=30, data=data)
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


def track_failures(state: dict[str, Any], name: str, failed: int, tried: int, error: str, now: datetime) -> str | None:
    """Update one network's failure streak in state; return the alert body when one is due."""
    if not tried:
        return None  # nothing to post says nothing about the network's health
    if not failed:
        state.pop(name, None)
        return None
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    s = state.setdefault(name, {"runs": 0, "since": stamp})
    s["runs"] += 1
    s["last_error"] = error[:300]
    if s["runs"] < ALERT_AFTER_RUNS:
        return None
    last = s.get("alerted")
    if last and now - datetime.fromisoformat(last.replace("Z", "+00:00")) < timedelta(hours=ALERT_EVERY_HOURS):
        return None
    s["alerted"] = stamp
    return (f"Posting to {name} has failed on {s['runs']} runs in a row, since {s['since']}.\n\n"
            f"Last error: {s['last_error']}\n\n"
            "The usual cause is an expired login: check the app password or access token in the repo secrets. "
            "Stories still inside the six-hour window post on the next good run; older ones are skipped.")


def run(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    dry = os.environ.get("SOCIAL_DRY_RUN") == "1"
    nets = _networks()
    if not dry and not nets:
        return "social: no Bluesky or Threads secrets set, skipped"
    posted = json.loads(POSTED.read_text()) if POSTED.exists() else {}
    if dry:
        todo = due(stories(), posted, now) + due_power(power_stories(now), posted, now)
        return "\n".join(f"[dry] {text_for(it)!r} -> {it['url']} [{card_url(it) or 'no card'}]" for it in todo) or "social: nothing new"
    report = []
    failures = json.loads(FAILURES.read_text()) if FAILURES.exists() else {}
    for prefix, send in nets:
        seen = seen_for(posted, prefix)
        todo = due(stories(), seen, now) + due_power(power_stories(now), seen, now)
        n, waiting, error = 0, 0, ""
        for it in todo:
            try:
                send(it, now)
            except NotLive:
                print(f"social: {prefix or 'bsky:'}{it['url']} not deployed yet, next run")
                waiting += 1  # not a failure: the page just hasn't deployed
                continue
            except (requests.RequestException, KeyError) as e:
                error = f"{type(e).__name__}: {e}"
                print(f"social: {prefix or 'bsky:'}{it['url']} failed: {e}")
                continue
            posted[prefix + it["key"]] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            n += 1
        name = (prefix or "bluesky:").rstrip(":")
        report.append(f"{name} {n}/{len(todo)}")
        body = track_failures(failures, name, len(todo) - n - waiting, len(todo) - waiting, error, now)
        if body:
            alert.send(f"Social posts to {name} keep failing", body)
    FAILURES.write_text(json.dumps(failures, indent=1, sort_keys=True) + "\n")
    cutoff = (now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    posted = {k: v for k, v in posted.items() if v >= cutoff}
    POSTED.write_text(json.dumps(dict(sorted(posted.items())), indent=0) + "\n")
    return "social: posted " + ", ".join(report)
