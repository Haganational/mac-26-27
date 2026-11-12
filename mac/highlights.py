"""Official game highlights: ESPN's "Game Highlights" clips, embedded on our recap pages.

ESPN cuts a highlight package for most D-I games, ESPN+ games included, usually within a
couple of hours of the final. Each clip shows up in ESPN's per-team news feed as a "Media"
item whose categories carry the ESPN event (game) id, so matching a clip to our game page
is exact, with no guessing from titles. We embed ESPN's own syndicated player
(https://www.espn.com/core/video/iframe/...), the same thing ESPN's "Embed" button gives,
so the video plays from ESPN with their ads and rights intact. We never copy the video.

Cost: one request per team that played in the last LOOKBACK_HOURS and has no clip yet,
so a typical 30-minute run makes zero to a handful of requests. Never fails the run.

    python -m mac.collect highlights     # this edition's teams (LEAGUE env picks the edition)

Found clips are kept in data/highlights.json (shared by every edition): event id -> clip.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from .config import ESPN_BASE, SHARED_DIR

FILE = SHARED_DIR / "highlights.json"
LOOKBACK_HOURS = 36
TIMEOUT = 20
EMBED = "https://www.espn.com/core/video/iframe/_/id/{id}/endcard/false"
_HIGHLIGHT = re.compile(r"\bhighlights?\b", re.I)


def load(path: Path = FILE) -> dict[str, dict[str, Any]]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save(clips: dict[str, dict[str, Any]], path: Path = FILE) -> None:
    path.write_text(json.dumps(dict(sorted(clips.items())), indent=1) + "\n")


def parse(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """ESPN news items -> {event id: clip} for highlight videos tied to one game."""
    out: dict[str, dict[str, Any]] = {}
    for it in items:
        if it.get("type") != "Media" or not _HIGHLIGHT.search(it.get("headline") or ""):
            continue
        cats = it.get("categories") or []
        events = {str(c.get("eventId") or (c.get("event") or {}).get("id") or "") for c in cats if c.get("type") == "event"}
        events.discard("")
        if len(events) != 1 or not it.get("id"):
            continue
        eid = events.pop()
        clip = {"id": str(it["id"]), "title": it.get("headline", ""), "published": it.get("published", ""),
                "full": any("full highlight" in (c.get("description") or "").lower() for c in cats)}
        # Prefer ESPN's full highlight package over a single-play clip of the same game.
        have = out.get(eid)
        if have is None or (clip["full"] and not have["full"]):
            out[eid] = clip
    return out


def due_teams(games: Iterable[dict[str, Any]], clips: dict[str, Any], now: datetime,
              lookback_hours: float = LOOKBACK_HOURS) -> list[str]:
    """ESPN team ids worth asking about: a side of a recent final with no clip yet."""
    cut = now - timedelta(hours=lookback_hours)
    out: list[str] = []
    for g in games:
        if not g.get("completed") or str(g.get("game_id")) in clips:
            continue
        try:
            tip = datetime.fromisoformat((g.get("date") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if tip < cut:
            continue
        # Our own team first: its feed is the one we know ESPN files the clip under.
        for side in ("home", "away"):
            t = g.get(side) or {}
            if t.get("key") and t.get("espn_id") and str(t["espn_id"]) not in out:
                out.append(str(t["espn_id"]))
    return out


def fetch_team(espn_id: str, session: Any = requests) -> list[dict[str, Any]]:
    r = session.get(f"{ESPN_BASE}/news", params={"team": espn_id, "limit": 25}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json().get("articles") or []


def refresh(games: list[dict[str, Any]], now: datetime | None = None, path: Path = FILE,
            fetch: Any = fetch_team) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    clips = load(path)
    teams = due_teams(games, clips, now)
    found = 0
    for tid in teams:
        try:
            got = parse(fetch(tid))
        except Exception:  # noqa: BLE001 - one team's feed failing must not stop the rest
            continue
        for eid, clip in got.items():
            if eid not in clips or (clip["full"] and not clips[eid].get("full")):
                found += eid not in clips
                clips[eid] = clip
    if found or teams:
        save(clips, path)
    return {"asked": len(teams), "new": found, "total": len(clips)}


def for_game(game_id: str, clips: dict[str, Any] | None = None) -> dict[str, Any] | None:
    c = (clips if clips is not None else load()).get(str(game_id))
    return {**c, "embed": EMBED.format(id=c["id"]), "watch": f"https://www.espn.com/video/clip/_/id/{c['id']}"} if c else None
