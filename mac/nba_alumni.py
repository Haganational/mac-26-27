"""NBA alumni in the recap: "In the NBA, former Toledo player X had 14 points for the Bucks on Tuesday."

ESPN's NBA rosters carry each player's college as an ESPN college team id, which is the same id
our teams use. Each run caches the 30 rosters (refreshed weekly) and every finished NBA night
(data/nba/box/YYYYMMDD.json, kept once final). A recap mentions a school's former players who
played in the NBA the same night or the night before; when nobody did, there is no line.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .config import SHARED_DIR

NBA = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
DIR = SHARED_DIR / "nba"
ROSTERS = DIR / "rosters.json"
ET = ZoneInfo("America/New_York")
TIMEOUT = 30
WINDOW_DAYS = 1  # same night, or the night before


def _get(path: str, **params: str) -> dict[str, Any]:
    r = requests.get(f"{NBA}/{path}", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def refresh_rosters(now: datetime | None = None, max_age_days: int = 7, path: Path = ROSTERS) -> int:
    """{athlete id: {name, college_id, college}} for every NBA roster. Returns players with a college."""
    now = now or datetime.now(timezone.utc)
    if path.exists():
        old = json.loads(path.read_text())
        if (now - datetime.fromisoformat(old["fetched_at"])).days < max_age_days:
            return len(old["players"])
    players: dict[str, dict[str, str]] = {}
    teams = _get("teams")["sports"][0]["leagues"][0]["teams"]
    for t in teams:
        for a in _get(f"teams/{t['team']['id']}/roster").get("athletes", []):
            col = a.get("college") or {}
            if col.get("id"):
                players[str(a["id"])] = {"name": a.get("displayName", ""), "college_id": str(col["id"]), "college": col.get("name", "")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": now.isoformat(timespec="seconds"), "players": players}, indent=0, sort_keys=True))
    return len(players)


def parse_summary(s: dict[str, Any]) -> list[dict[str, Any]]:
    """Every player who got in, from an NBA game summary."""
    out = []
    for side in (s.get("boxscore") or {}).get("players", []):
        team = side.get("team") or {}
        for st in side.get("statistics", [])[:1]:
            names = st.get("names") or st.get("labels") or []
            for a in st.get("athletes", []):
                stats = a.get("stats") or []
                if a.get("didNotPlay") or not stats:
                    continue
                row = dict(zip(names, stats))
                try:
                    mins = int(row.get("MIN") or 0)
                except ValueError:
                    mins = 0
                if mins <= 0:
                    continue
                out.append({"id": str(a["athlete"]["id"]), "name": a["athlete"].get("displayName", ""),
                            "team": team.get("name") or team.get("displayName", ""),
                            "pts": int(row.get("PTS") or 0), "reb": int(row.get("REB") or 0), "ast": int(row.get("AST") or 0)})
    return out


def refresh_nights(today: date | None = None, days: int = 2, box_dir: Path = DIR / "box") -> int:
    """Cache finished NBA nights (ET dates), today and the days before. A night is final once all its games are."""
    today = today or datetime.now(ET).date()
    box_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for k in range(days + 1):
        d = today - timedelta(days=k)
        f = box_dir / f"{d:%Y%m%d}.json"
        if f.exists() and json.loads(f.read_text()).get("final"):
            continue
        events = _get("scoreboard", dates=f"{d:%Y%m%d}").get("events", [])
        players, final = [], bool(events)
        for ev in events:
            if not ev["status"]["type"].get("completed"):
                final = False
                continue
            players += parse_summary(_get("summary", event=ev["id"]))
        f.write_text(json.dumps({"date": d.isoformat(), "final": final, "players": players}))
        n += len(players)
    return n


def load_nights(box_dir: Path = DIR / "box") -> dict[str, list[dict[str, Any]]]:
    if not box_dir.exists():
        return {}
    return {(j := json.loads(f.read_text()))["date"]: j["players"] for f in sorted(box_dir.glob("*.json"))}


def load_colleges(path: Path = ROSTERS) -> dict[str, dict[str, str]]:
    return json.loads(path.read_text())["players"] if path.exists() else {}


def _line(p: dict[str, Any]) -> str:
    bits = [f"{p['pts']} points"]
    if p["reb"] >= 5:
        bits.append(f"{p['reb']} rebounds")
    if p["ast"] >= 5:
        bits.append(f"{p['ast']} assists")
    return bits[0] if len(bits) == 1 else ", ".join(bits[:-1]) + " and " + bits[-1]


def lines_for(college_id: str, school_name: str, game_day: date, nights: dict[str, list[dict[str, Any]]],
              colleges: dict[str, dict[str, str]], limit: int = 2) -> list[str]:
    """Sentences about a school's former players who played in the NBA on game day or the day before."""
    seen, found = set(), []
    for k in range(WINDOW_DAYS + 1):
        d = game_day - timedelta(days=k)
        for p in nights.get(d.isoformat(), []):
            c = colleges.get(p["id"])
            if c and c["college_id"] == str(college_id) and p["id"] not in seen:
                seen.add(p["id"])
                found.append((p["pts"], d, p))
    found.sort(key=lambda x: -x[0])
    out = []
    for _, d, p in found[:limit]:
        when = "the night before" if d < game_day else f"on {d:%A}"
        out.append(f"former {school_name} player {p['name']} had {_line(p)} for the {p['team']} {when}")
    return out


def paragraph(teams: list[tuple[str, str]], game_day: date, nights: dict[str, list[dict[str, Any]]],
              colleges: dict[str, dict[str, str]]) -> str | None:
    """'In the NBA, ...' for both teams in a game, or None."""
    bits = [s for cid, name in teams if cid for s in lines_for(cid, name, game_day, nights, colleges)]
    if not bits:
        return None
    return "In the NBA, " + "; ".join(bits) + "."
