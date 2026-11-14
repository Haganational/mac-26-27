"""The Watch page: where the video lives on the site.

One site-wide page (site/watch.html) with the two shows' players, what runs on them, tonight's
Anchor Pick'em desk, today's Off the Court story, and the whole anchor desk by conference.
Everything on it comes from files the shows already use, so the page can't drift from the air.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import alumni, anchors, den_connect, pickem, site_chrome
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


def desk() -> list[dict[str, Any]]:
    """Every anchor, grouped by conference in the order the editions run."""
    color = anchors.color()
    out = []
    for lg in LEAGUES.values():
        rows = [{**card, "catch": color.get(tm.key, {}).get("catch", "")} for tm in lg.teams if (card := den_connect.anchor_card(tm.key))]
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
    return {"shows": [{**s, "list": playlists().get(s["key"], "")} for s in SHOWS], "segments": SEGMENTS, "desk": desk(),
            "handle": site_chrome.YOUTUBE_CHANNEL, "story": story(day),
            "tonight": {**tonight["card"], "anchor": den_connect.anchor_card(tonight["card"]["key"])} if tonight else None,
            "count": sum(len(c["anchors"]) for c in desk()), "disclosure": den_connect.DISCLOSURE}
