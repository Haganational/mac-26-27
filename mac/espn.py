"""Pull schedules and results for the MAC from ESPN's public site API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests

from .config import BY_ESPN_ID, DATA_DIR, ESPN_BASE, SEASON, TEAMS

SCHEDULE_PATH = DATA_DIR / "schedule.json"
TIMEOUT = 30


def fetch_team_schedule(espn_id: str, season: int = SEASON) -> dict[str, Any]:
    url = f"{ESPN_BASE}/teams/{espn_id}/schedule"
    resp = requests.get(url, params={"season": season}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("value")
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_broadcasts(comp: dict[str, Any]) -> list[dict[str, Any]]:
    """ESPN's broadcast list, flattened: network name, TV/Streaming/Radio, National/Home/Away."""
    out = []
    for b in comp.get("broadcasts") or []:
        name = (b.get("media") or {}).get("shortName") or ((b.get("names") or [None])[0])
        if not name:
            continue
        kind = (b.get("type") or {}).get("shortName") or ""
        if kind.lower() == "radio":
            continue
        market = (b.get("market") or {}).get("type") if isinstance(b.get("market"), dict) else b.get("market")
        out.append({"name": name, "kind": kind, "market": market or ""})
    return out


def parse_event(event: dict[str, Any]) -> dict[str, Any]:
    """Flatten one ESPN event into our game record."""
    comp = event["competitions"][0]
    home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
    away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
    status = comp.get("status", {}).get("type", {})
    home_team = BY_ESPN_ID.get(home["team"]["id"])
    away_team = BY_ESPN_ID.get(away["team"]["id"])
    venue = comp.get("venue") or {}
    return {
        "game_id": event["id"],
        "date": event["date"],  # ISO UTC, e.g. 2026-11-11T00:00Z
        "name": event.get("name"),
        "short_name": event.get("shortName"),
        "season_type": event.get("seasonType", {}).get("abbreviation"),
        "neutral_site": bool(comp.get("neutralSite")),
        "conference_game": home_team is not None and away_team is not None,
        "time_tba": comp.get("timeValid") is False,
        "broadcasts": parse_broadcasts(comp),
        "venue": venue.get("fullName"),
        "venue_city": (venue.get("address") or {}).get("city"),
        "venue_state": (venue.get("address") or {}).get("state"),
        "home": {
            "espn_id": home["team"]["id"],
            "key": home_team.key if home_team else None,
            "name": home["team"].get("displayName"),
            "abbr": home["team"].get("abbreviation"),
            "score": _int_or_none(home.get("score")),
            "winner": home.get("winner"),
        },
        "away": {
            "espn_id": away["team"]["id"],
            "key": away_team.key if away_team else None,
            "name": away["team"].get("displayName"),
            "abbr": away["team"].get("abbreviation"),
            "score": _int_or_none(away.get("score")),
            "winner": away.get("winner"),
        },
        "status": status.get("name"),
        "completed": bool(status.get("completed")),
    }


def refresh_schedule() -> dict[str, Any]:
    """Fetch every MAC team's schedule, dedupe by game id, write data/schedule.json."""
    games: dict[str, dict[str, Any]] = {}
    for team in TEAMS:
        payload = fetch_team_schedule(team.espn_id)
        for event in payload.get("events", []):
            parsed = parse_event(event)
            games[parsed["game_id"]] = parsed
    ordered = sorted(games.values(), key=lambda g: g["date"])
    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": SEASON,
        "games": ordered,
    }
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_PATH.write_text(json.dumps(out, indent=1))
    return out


def load_schedule() -> dict[str, Any]:
    if not SCHEDULE_PATH.exists():
        return {"fetched_at": None, "season": SEASON, "games": []}
    return json.loads(SCHEDULE_PATH.read_text())
