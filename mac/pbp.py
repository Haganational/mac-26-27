"""Play-by-play for MAC games: who was on the floor, and what happened while they were.

ESPN's summary feed logs every substitution with player ids. Starting from the box
score starters, we replay the game and cut it into *stints*: stretches with the same
ten players on the floor. Each stint records points, possessions and seconds for
both sides, which is what on/off and adjusted plus-minus need.

ESPN occasionally misses a substitution. Two repairs keep lineups honest:
- a player who records an event (shot, rebound, foul...) while marked off the floor
  is put on it;
- if that leaves six, the player idle the longest comes off.
Stints that still don't have exactly five a side are kept but flagged `bad`, and
the rating code skips them.

Files: data/pbp/<season>/<game_id>.json, one per MAC game, holding the player box
lines and the stints. Fetched once per finished game.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

from .config import DATA_DIR, ESPN_BASE, SEASON, TEAMS
from .rosters import parse_summary

PBP_DIR = DATA_DIR / "pbp"
TIMEOUT = 30
FT_WEIGHT = 0.475
MAC_IDS = {t.espn_id for t in TEAMS}


def _secs(period: int, clock: str) -> float:
    """Seconds elapsed since tip. Halves are 20:00, overtimes 5:00."""
    try:
        m, s = clock.split(":")
        left = int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        left = 0.0
    if period <= 2:
        return (period - 1) * 1200 + (1200 - left)
    return 2400 + (period - 3) * 300 + (300 - left)


def _kind(play: dict[str, Any]) -> str:
    t = (play.get("type") or {}).get("text") or ""
    if t == "Substitution":
        return "sub"
    if "FreeThrow" in t:
        return "ft"
    if play.get("shootingPlay"):
        return "fga"
    if "Turnover" in t:
        return "to"
    if t == "Offensive Rebound":
        return "orb"
    return "other"


def build_stints(summary: dict[str, Any]) -> dict[str, Any]:
    box = parse_summary("", summary)
    teams = {t["home_away"]: t["espn_id"] for t in box["teams"]}
    if set(teams) != {"home", "away"}:
        return {"stints": [], "error": "no teams"}
    side_of = {teams["home"]: "home", teams["away"]: "away"}
    roster = {p["espn_id"]: side_of.get(p["team_espn_id"]) for p in box["players"]}
    floor = {s: {p["espn_id"] for p in box["players"] if p["starter"] and side_of.get(p["team_espn_id"]) == s} for s in ("home", "away")}
    last_seen: dict[str, float] = {pid: 0.0 for s in floor.values() for pid in s}

    stints: list[dict[str, Any]] = []

    def new_stint(t0: float, hs: int, as_: int) -> dict[str, Any]:
        return {"t0": t0, "t1": t0, "home": sorted(floor["home"]), "away": sorted(floor["away"]),
                "hs0": hs, "as0": as_, "hs1": hs, "as1": as_,
                "fga": {"home": 0, "away": 0}, "fta": {"home": 0, "away": 0},
                "to": {"home": 0, "away": 0}, "orb": {"home": 0, "away": 0}}

    cur = new_stint(0.0, 0, 0)
    pending_change = False
    hs = as_ = 0
    for play in summary.get("plays") or []:
        kind = _kind(play)
        t = _secs((play.get("period") or {}).get("number") or 1, (play.get("clock") or {}).get("displayValue") or "0:00")
        tid = (play.get("team") or {}).get("id")
        side = side_of.get(tid)
        pids = [a["athlete"]["id"] for a in play.get("participants") or [] if a.get("athlete")]
        text = (play.get("text") or "").lower()
        if kind == "sub":
            if not pids or side is None:
                continue
            pid = pids[0]
            if "subbing in" in text or " enters" in text:
                floor[side].add(pid)
                last_seen[pid] = t
            elif "subbing out" in text or " goes to the bench" in text:
                floor[side].discard(pid)
            pending_change = True
            continue
        # First real event after a batch of substitutions closes the old stint.
        if pending_change:
            cur["t1"] = t
            stints.append(cur)
            cur = new_stint(t, hs, as_)
            pending_change = False
        # Repair: an active player must be on the floor.
        for pid in pids:
            s2 = roster.get(pid)
            if s2 is None:
                continue
            if pid not in floor[s2]:
                floor[s2].add(pid)
                if len(floor[s2]) > 5:
                    idle = min((p for p in floor[s2] if p != pid), key=lambda p: last_seen.get(p, -1))
                    floor[s2].discard(idle)
                cur[s2] = sorted(floor[s2])
            last_seen[pid] = t
        if side:
            if kind == "fga":
                cur["fga"][side] += 1
            elif kind == "ft":
                cur["fta"][side] += 1
            elif kind == "to":
                cur["to"][side] += 1
            elif kind == "orb":
                cur["orb"][side] += 1
        hs = play.get("homeScore", hs) or hs
        as_ = play.get("awayScore", as_) or as_
        cur["hs1"], cur["as1"], cur["t1"] = hs, as_, t
    stints.append(cur)

    out = []
    for s in stints:
        poss = {}
        for sd in ("home", "away"):
            poss[sd] = s["fga"][sd] - s["orb"][sd] + s["to"][sd] + FT_WEIGHT * s["fta"][sd]
        row = {
            "secs": round(s["t1"] - s["t0"], 1),
            "home": s["home"], "away": s["away"],
            "pts_h": s["hs1"] - s["hs0"], "pts_a": s["as1"] - s["as0"],
            "poss": round(max(0.0, (poss["home"] + poss["away"]) / 2), 2),
        }
        if len(s["home"]) != 5 or len(s["away"]) != 5:
            row["bad"] = True
        if row["secs"] > 0 or row["pts_h"] or row["pts_a"]:
            out.append(row)
    return {"stints": out}


def fetch_game(game_id: str) -> dict[str, Any]:
    resp = requests.get(f"{ESPN_BASE}/summary", params={"event": game_id}, timeout=TIMEOUT)
    resp.raise_for_status()
    summary = resp.json()
    box = parse_summary(game_id, summary)
    st = build_stints(summary)
    header = (summary.get("header") or {}).get("competitions", [{}])[0]
    return {
        "game_id": game_id,
        "date": header.get("date"),
        "neutral_site": header.get("neutralSite"),
        "teams": [{k: t[k] for k in ("espn_id", "abbr", "name", "home_away")} for t in box["teams"]],
        "players": box["players"],
        "stints": st["stints"],
    }


def game_path(season: int, game_id: str):
    return PBP_DIR / str(season) / f"{game_id}.json"


def refresh(season: int = SEASON, game_ids: list[str] | None = None, workers: int = 4, force: bool = False) -> dict[str, int]:
    """Fetch every finished MAC game of a season that we don't have yet."""
    from . import ncaa

    if game_ids is None:
        games = ncaa.load_season(season)["games"]
        game_ids = [g["id"] for g in games if g["home"]["id"] in MAC_IDS or g["away"]["id"] in MAC_IDS]
    (PBP_DIR / str(season)).mkdir(parents=True, exist_ok=True)
    todo = [gid for gid in game_ids if force or not game_path(season, gid).exists()]

    def one(gid: str) -> bool:
        try:
            data = fetch_game(gid)
        except (requests.RequestException, ValueError, KeyError):
            return False
        game_path(season, gid).write_text(json.dumps(data, separators=(",", ":")))
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        ok = sum(pool.map(one, todo))
    return {"season": season, "fetched": ok, "failed": len(todo) - ok, "had": len(game_ids) - len(todo)}


def load_games(season: int) -> list[dict[str, Any]]:
    d = PBP_DIR / str(season)
    if not d.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]
