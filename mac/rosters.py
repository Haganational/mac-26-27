"""Rosters and box scores from ESPN's public site API.

- data/rosters.json: every MAC team's roster with bio fields.
- data/boxscores/<game_id>.json: one compact file per completed game with team
  totals, every player's line, and the DraftKings line ESPN carried (closing-ish
  spread, total and moneylines), which doubles as line history for games played
  before our collector existed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests

from .config import DATA_DIR, ESPN_BASE, SEASON, TEAMS
from .espn import load_schedule

ROSTERS_PATH = DATA_DIR / "rosters.json"
BOX_DIR = DATA_DIR / "boxscores"
TIMEOUT = 30

STAT_KEYS = ["min", "pts", "fg", "3pt", "ft", "reb", "ast", "to", "stl", "blk", "oreb", "dreb", "pf"]


def fetch_roster(espn_id: str) -> list[dict[str, Any]]:
    resp = requests.get(f"{ESPN_BASE}/teams/{espn_id}/roster", params={"season": SEASON}, timeout=TIMEOUT)
    resp.raise_for_status()
    out = []
    for a in resp.json().get("athletes", []):
        out.append({
            "espn_id": a["id"],
            "name": a.get("displayName"),
            "first_name": a.get("firstName"),
            "last_name": a.get("lastName"),
            "jersey": a.get("jersey"),
            "position": (a.get("position") or {}).get("abbreviation"),
            "height": a.get("displayHeight"),
            "height_in": a.get("height"),
            "weight": a.get("displayWeight"),
            "class": (a.get("experience") or {}).get("abbreviation"),
            "class_name": (a.get("experience") or {}).get("displayValue"),
            "hometown": (a.get("birthPlace") or {}).get("displayText"),
            "headshot": f"https://a.espncdn.com/i/headshots/mens-college-basketball/players/full/{a['id']}.png",
            "espn_url": next((l["href"] for l in a.get("links", []) if "playercard" in l.get("rel", [])), None),
            "injuries": [{"status": i.get("status"), "detail": i.get("details", {}).get("detail") if isinstance(i.get("details"), dict) else None} for i in a.get("injuries", [])],
        })
    return out


def refresh_rosters() -> dict[str, Any]:
    rosters = {t.key: fetch_roster(t.espn_id) for t in TEAMS}
    out = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "season": SEASON, "rosters": rosters}
    ROSTERS_PATH.write_text(json.dumps(out, indent=1))
    return out


def load_rosters() -> dict[str, Any]:
    if not ROSTERS_PATH.exists():
        return {"fetched_at": None, "rosters": {t.key: [] for t in TEAMS}}
    return json.loads(ROSTERS_PATH.read_text())


# ---------------------------------------------------------------- box scores


def _split(value: str) -> tuple[int | None, int | None]:
    try:
        made, att = value.split("-")
        return int(made), int(att)
    except (ValueError, AttributeError):
        return None, None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_summary(game_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    box = summary.get("boxscore", {})
    teams_out = []
    for team in box.get("teams", []):
        stats = {s["name"]: s.get("displayValue") for s in team.get("statistics", [])}
        teams_out.append({
            "espn_id": team["team"]["id"],
            "abbr": team["team"].get("abbreviation"),
            "name": team["team"].get("displayName"),
            "home_away": team.get("homeAway"),
            "stats": stats,
        })
    players_out = []
    for team in box.get("players", []):
        tid = team["team"]["id"]
        for group in team.get("statistics", []):
            names = [n.lower() for n in group.get("names", [])]
            for a in group.get("athletes", []):
                row = dict(zip(names, a.get("stats", [])))
                fgm, fga = _split(row.get("fg", ""))
                tpm, tpa = _split(row.get("3pt", ""))
                ftm, fta = _split(row.get("ft", ""))
                players_out.append({
                    "team_espn_id": tid,
                    "espn_id": a["athlete"]["id"],
                    "name": a["athlete"].get("displayName"),
                    "position": (a["athlete"].get("position") or {}).get("abbreviation"),
                    "starter": bool(a.get("starter")),
                    "dnp": bool(a.get("didNotPlay")),
                    "min": _int(row.get("min")),
                    "pts": _int(row.get("pts")),
                    "fgm": fgm, "fga": fga, "tpm": tpm, "tpa": tpa, "ftm": ftm, "fta": fta,
                    "reb": _int(row.get("reb")), "oreb": _int(row.get("oreb")), "dreb": _int(row.get("dreb")),
                    "ast": _int(row.get("ast")), "to": _int(row.get("to")), "stl": _int(row.get("stl")),
                    "blk": _int(row.get("blk")), "pf": _int(row.get("pf")),
                })
    line = None
    for pc in summary.get("pickcenter", []) or []:
        home = pc.get("homeTeamOdds", {})
        away = pc.get("awayTeamOdds", {})
        # pickcenter "spread" is from the favourite's view; normalise to the home team.
        spread = pc.get("spread")
        if spread is not None and not home.get("favorite"):
            spread = -spread
        line = {
            "provider": pc.get("provider", {}).get("name"),
            "details": pc.get("details"),
            "home_spread": spread,
            "total": pc.get("overUnder"),
            "ml_home": home.get("moneyLine"),
            "ml_away": away.get("moneyLine"),
        }
        break
    header = summary.get("header", {}).get("competitions", [{}])[0]
    return {
        "game_id": game_id,
        "date": header.get("date"),
        "neutral_site": header.get("neutralSite"),
        "attendance": summary.get("gameInfo", {}).get("attendance"),
        "teams": teams_out,
        "players": players_out,
        "espn_line": line,
    }


def fetch_summary(game_id: str) -> dict[str, Any]:
    resp = requests.get(f"{ESPN_BASE}/summary", params={"event": game_id}, timeout=TIMEOUT)
    resp.raise_for_status()
    return parse_summary(game_id, resp.json())


def refresh_boxscores(force: bool = False) -> dict[str, int]:
    """Fetch box scores for completed games we have not stored yet."""
    BOX_DIR.mkdir(parents=True, exist_ok=True)
    fetched = skipped = 0
    for g in load_schedule()["games"]:
        if not g["completed"]:
            continue
        path = BOX_DIR / f"{g['game_id']}.json"
        if path.exists() and not force:
            skipped += 1
            continue
        try:
            path.write_text(json.dumps(fetch_summary(g["game_id"]), separators=(",", ":")))
            fetched += 1
        except requests.RequestException as exc:  # keep going; retry next run
            print(f"boxscore {g['game_id']}: {exc}")
    return {"fetched": fetched, "already_had": skipped}


def load_boxscores() -> list[dict[str, Any]]:
    if not BOX_DIR.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(BOX_DIR.glob("*.json"))]
