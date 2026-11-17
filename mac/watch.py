"""The Watch page: where the video lives on the site.

One site-wide page (site/watch.html) with the two shows' players, what runs on them, tonight's
Anchor Pick'em desk, today's Off the Court story, and the whole anchor desk by conference.
Everything on it comes from files the shows already use, so the page can't drift from the air.
"""
from __future__ import annotations

import json
import re
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import alumni, anchors, den_connect, pickem, press, site_chrome
from .config import SHARED_DIR
from .leagues import ALL as LEAGUES

ET = ZoneInfo("America/New_York")
SHOWS = [
    {"key": "midmaxx60", "name": "MidMaxx60", "when": "Every morning", "length": "60 seconds",
     "what": "Last night's results, tonight's lines and our model, read by the anchors of the schools that played."},
    {"key": "bigmid", "name": "The Big Mid", "when": "Every week", "length": "About five minutes",
     "what": "The week in every conference we cover: the upset, the player of the week, the game to circle, and the At-Large Watch."},
]
SEGMENTS = [
    {"name": "Anchor Pick'em", "what": "One anchor has the desk each night and calls four winners. Their own school is always the first pick.", "href": "den.html", "link": "Beat the desk at the Den"},
    {"name": "Off the Court", "what": "Famous alumni, told by the school's own anchor. Every story is checked against its source."},
    {"name": "Rivalry Desk", "what": "When rivals meet, their anchors say so across the desk."},
    {"name": "At-Large Watch", "what": "Who could reach the NCAA tournament without the automatic bid.", "href": "at-large.html", "link": "See the ranking"},
]


def playlists() -> dict[str, str]:
    """YouTube's own upload playlists for the channel: Shorts (UUSH...) and long videos (UULF...)."""
    cid = site_chrome.YOUTUBE_CHANNEL_ID
    return {"midmaxx60": "UUSH" + cid[2:], "bigmid": "UULF" + cid[2:]} if cid else {}


LATEST = SHARED_DIR / "youtube_latest.json"
FEED = "https://www.youtube.com/feeds/videos.xml?playlist_id={}"
_ENTRY = re.compile(r"<entry>.*?<yt:videoId>([\w-]{6,})</yt:videoId>.*?<title>([^<]*)</title>.*?<published>([^<]+)</published>", re.S)


def latest(fetch: Any = None) -> dict[str, dict[str, str]]:
    """Each show's newest upload (video id, title, date), from YouTube's public playlist feed (no API key).
    The last good answer is kept in data/youtube_latest.json, so a feed outage or an offline build keeps the poster."""
    try:
        known = json.loads(LATEST.read_text())
    except (OSError, ValueError):
        known = {}
    out = dict(known)
    for key, pl in playlists().items():
        try:
            xml = fetch(FEED.format(pl)) if fetch else urllib.request.urlopen(FEED.format(pl), timeout=8).read().decode()
        except Exception:  # noqa: BLE001 - a feed hiccup keeps the last poster
            continue
        if m := _ENTRY.search(xml):
            d = datetime.fromisoformat(m.group(3)).astimezone(ET)
            out[key] = {"id": m.group(1), "title": m.group(2).replace("&amp;", "&"), "published": f"{d:%a, %b} {d.day}"}
    if out != known:
        try:
            LATEST.write_text(json.dumps(out, indent=1) + "\n")
        except OSError:
            pass
    return out


def desk() -> list[dict[str, Any]]:
    """Every anchor, grouped by conference in the order the editions run."""
    color = anchors.color()
    out = []
    for lg in LEAGUES.values():
        rows = [{**card, "catch": color.get(tm.key, {}).get("catch", ""), "href": f"anchors/{tm.key}.html"}
                for tm in lg.teams if (card := den_connect.anchor_card(tm.key))]
        if rows:
            out.append({"key": lg.key, "short": lg.short, "name": lg.name, "anchors": rows})
    return out


def story(day: str) -> dict[str, Any] | None:
    """Today's Off the Court story for the page: one school a day, in turn."""
    have = sorted(k for k in anchors.roster() if alumni.stories(k))
    if not have:
        return None
    key = have[datetime.fromisoformat(day).toordinal() % len(have)]
    s = alumni.pick(key, day)
    return {**s, "anchor": den_connect.anchor_card(key)} if s else None


def page_context(now: datetime) -> dict[str, Any]:
    day = now.astimezone(ET).date().isoformat()
    tonight = pickem.segment(day)
    up = latest()
    return {"shows": [{**s, "list": playlists().get(s["key"], ""), "latest": up.get(s["key"])} for s in SHOWS], "segments": SEGMENTS, "desk": desk(),
            "handle": site_chrome.YOUTUBE_CHANNEL, "story": story(day),
            "tonight": {**tonight["card"], "anchor": den_connect.anchor_card(tonight["card"]["key"])} if tonight else None,
            "count": sum(len(c["anchors"]) for c in desk()), "disclosure": den_connect.DISCLOSURE}


def profile(key: str, homer: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """One anchor's page: who they are on air, their rival, their school's stories and their homer record.
    Paths are from the site root; the page sets <base href="../">."""
    a, card = anchors.roster().get(key), den_connect.anchor_card(key)
    if not a or not card:
        return None
    c = anchors.color().get(key, {})
    lg, tm = next(((lg, tm) for lg in LEAGUES.values() for tm in lg.teams if tm.key == key), (None, None))
    rival = den_connect.anchor_card(c.get("rival")) if c.get("rival") else None
    return {**card, "catch": c.get("catch", ""), "signoff": c.get("signoff", ""), "brief": c.get("voice", ""),
            "conf": lg.short if lg else "", "team_href": f"{lg.path}teams/{key}.html" if lg else None,
            "rival": {**rival, "href": f"anchors/{rival['key']}.html"} if rival else None,
            "stories": alumni.stories(key), "homer": (homer or {}).get(key),
            "paper": press.paper(key), "town": (press.papers().get(key) or {}).get("town", ""),
            "lean": (press.leans().get(key) or {}).get("lean", ""),
            "audio": f"anchors/audio/{key}.ogg" if (anchors.AUDITIONS / f"{key}.ogg").exists() else None}


def build_profiles(env: Any, site_root: Path, **common: Any) -> int:
    """Write site/anchors/<key>.html for every anchor, with their audition where one is recorded."""
    out = site_root / "anchors"
    (out / "audio").mkdir(parents=True, exist_ok=True)
    ledgers = [x for p in sorted(den_connect.LEDGER_DIR.glob("*.json")) for x in [pickem._load(p)] if x]
    results = {p.stem.removeprefix("results-"): r for p in (site_root / "den").glob("results-*.json") for r in [pickem._load(p)] if r}
    homer = {r["key"]: r for r in den_connect.standings(ledgers, results)["homer"]}
    tpl, n = env.get_template("anchor.html"), 0
    for key in anchors.roster():
        p = profile(key, homer)
        if not p:
            continue
        if p["audio"]:
            shutil.copyfile(anchors.AUDITIONS / f"{key}.ogg", site_root / p["audio"])
        (out / f"{key}.html").write_text(tpl.render(a=p, disclosure=den_connect.DISCLOSURE, **common))
        n += 1
    return n
