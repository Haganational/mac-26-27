"""Pull schedules and results for the MAC from ESPN's public site API."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

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
    st = comp.get("status") or event.get("status") or {}
    status = st.get("type", {})
    state = status.get("state") or ""
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
            "score": None if state == "pre" else _int_or_none(home.get("score")),
            "winner": home.get("winner"),
        },
        "away": {
            "espn_id": away["team"]["id"],
            "key": away_team.key if away_team else None,
            "name": away["team"].get("displayName"),
            "abbr": away["team"].get("abbreviation"),
            "score": None if state == "pre" else _int_or_none(away.get("score")),
            "winner": away.get("winner"),
        },
        "status": status.get("name"),
        "completed": bool(status.get("completed")),
        # In progress: ESPN's state "in" covers live play, halftime and breaks between periods.
        "live": state == "in",
        "detail": (status.get("shortDetail") or status.get("detail") or "") if state in ("in", "post") else "",
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


ET = ZoneInfo("America/New_York")
# A game is worth a live check from 20 minutes before tip until it is final (or 6 hours on).
LIVE_BEFORE = timedelta(minutes=20)
LIVE_AFTER = timedelta(hours=6)
LIVE_FIELDS = ("status", "completed", "live", "detail")


def _tip(g: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(g["date"].replace("Z", "+00:00"))


def live_candidates(games: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Games that have tipped, or are about to, and are not final yet."""
    return [g for g in games if not g.get("completed") and not g.get("time_tba")
            and now - LIVE_AFTER <= _tip(g) <= now + LIVE_BEFORE]


def fetch_scoreboard(day: str) -> list[dict[str, Any]]:
    """Every Division I game on one date (YYYYMMDD), with live scores and clocks: one request."""
    resp = requests.get(f"{ESPN_BASE}/scoreboard", params={"dates": day, "groups": "50", "limit": "500"}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("events", [])


def fetch_event(game_id: str) -> dict[str, Any] | None:
    """One game's header from the summary feed, shaped like a scoreboard event (fallback only)."""
    resp = requests.get(f"{ESPN_BASE}/summary", params={"event": game_id}, timeout=TIMEOUT)
    resp.raise_for_status()
    header = resp.json().get("header") or {}
    return {"id": header.get("id") or game_id, "date": header.get("competitions", [{}])[0].get("date"),
            "competitions": header.get("competitions") or []} if header.get("competitions") else None


def apply_live(game: dict[str, Any], fresh: dict[str, Any]) -> bool:
    """Copy score, status and clock from a freshly parsed event onto our game. True if anything changed."""
    before = json.dumps({k: game.get(k) for k in (*LIVE_FIELDS, "home", "away")}, sort_keys=True)
    for k in LIVE_FIELDS:
        game[k] = fresh.get(k)
    for side in ("home", "away"):
        game[side]["score"] = fresh[side]["score"]
        game[side]["winner"] = fresh[side]["winner"]
    return json.dumps({k: game.get(k) for k in (*LIVE_FIELDS, "home", "away")}, sort_keys=True) != before


def refresh_live(now: datetime | None = None) -> dict[str, Any]:
    """Score, clock and status for games in progress, from ESPN's scoreboard (one request per game day).

    Costs nothing when no game is near tip: no request at all. Rewrites data/schedule.json only on change.
    """
    now = now or datetime.now(timezone.utc)
    sched = load_schedule()
    cands = live_candidates(sched["games"], now)
    out = {"checked": len(cands), "live": 0, "finished": [], "changed": 0}
    if not cands:
        return out
    events: dict[str, dict[str, Any]] = {}
    for day in sorted({_tip(g).astimezone(ET).strftime("%Y%m%d") for g in cands}):
        for ev in fetch_scoreboard(day):
            events[str(ev.get("id"))] = ev
    for g in cands:
        ev = events.get(g["game_id"])
        if ev is None:  # not on the D-I board (rare): ask for the game itself
            try:
                ev = fetch_event(g["game_id"])
            except requests.RequestException as exc:
                print(f"live {g['game_id']}: {exc}")
                continue
        if not ev or not ev.get("competitions"):
            continue
        try:
            fresh = parse_event(ev)
        except (KeyError, StopIteration):
            continue
        if apply_live(g, fresh):
            out["changed"] += 1
        out["live"] += bool(g.get("live"))
        if g.get("completed"):
            out["finished"].append(g["game_id"])
    if out["changed"]:
        sched["live_at"] = now.isoformat(timespec="seconds")
        SCHEDULE_PATH.write_text(json.dumps(sched, indent=1))
    return out


def load_schedule() -> dict[str, Any]:
    if not SCHEDULE_PATH.exists():
        return {"fetched_at": None, "season": SEASON, "games": []}
    return json.loads(SCHEDULE_PATH.read_text())
