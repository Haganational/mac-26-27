"""Every Division I result, so the rating model can rate MAC opponents too.

The MAC schedule only covers games a MAC team played. To weight an opponent by
strength we need that opponent's own results, and its opponents' results, and so
on, which means the whole D-I graph. ESPN's scoreboard (groups=50 is Division I)
returns every game on a date in one request, with points, field goal attempts and
free throw attempts per team.

Stored compactly, one file per season: data/ncaa/games-<season>.json.

- `season` is ESPN's season id: 2027 is 2026-27, 2026 is 2025-26.
- The previous season is fetched once and only feeds the preseason prior.
- The current season is refreshed every run, re-reading the last few days so late
  finals and stat corrections land.

The scoreboard has no turnovers or offensive rebounds, so possessions are
estimated as FGA + 0.475*FTA + c, where c (turnovers minus offensive rebounds,
about +1.5 a game) is calibrated against the full box scores we hold for MAC games.
Where a full box score exists, the exact count is used instead (see ratings.py).
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from .config import DATA_DIR, ESPN_BASE, SEASON

NCAA_DIR = DATA_DIR / "ncaa"
TEAMS_PATH = NCAA_DIR / "teams.json"
TIMEOUT = 30
REFRESH_DAYS = 4  # re-read this many past days each run


def season_path(season: int):
    return NCAA_DIR / f"games-{season}.json"


def season_window(season: int) -> tuple[date, date]:
    """Opening night is early November; the title game is early April."""
    return date(season - 1, 11, 1), date(season, 4, 10)


def _stat(comp: dict[str, Any], name: str) -> int | None:
    for s in comp.get("statistics") or []:
        if s.get("name") == name:
            try:
                return int(float(s.get("displayValue")))
            except (TypeError, ValueError):
                return None
    return None


def parse_scoreboard_event(event: dict[str, Any]) -> dict[str, Any] | None:
    comp = event["competitions"][0]
    status = comp.get("status", {}).get("type", {})
    if not status.get("completed"):
        return None
    sides: dict[str, dict[str, Any]] = {}
    for c in comp.get("competitors", []):
        try:
            score = int(c.get("score"))
        except (TypeError, ValueError):
            return None
        sides[c["homeAway"]] = {
            "id": c["team"]["id"],
            "name": c["team"].get("displayName") or c["team"].get("name"),
            "conf": c["team"].get("conferenceId"),
            "pts": score,
            "fga": _stat(c, "fieldGoalsAttempted"),
            "fta": _stat(c, "freeThrowsAttempted"),
        }
    if set(sides) != {"home", "away"}:
        return None
    periods = max((len(c.get("linescores") or []) for c in comp.get("competitors", [])), default=2)
    return {
        "id": event["id"],
        "date": event["date"],
        "neutral": bool(comp.get("neutralSite")),
        "ot": max(0, periods - 2),
        "season_type": (event.get("season") or {}).get("type"),
        "home": sides["home"],
        "away": sides["away"],
    }


def fetch_scoreboard(day: date) -> list[dict[str, Any]]:
    resp = requests.get(
        f"{ESPN_BASE}/scoreboard",
        params={"dates": day.strftime("%Y%m%d"), "groups": 50, "limit": 500},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    out = []
    for ev in resp.json().get("events", []):
        g = parse_scoreboard_event(ev)
        if g:
            out.append(g)
    return out


def load_season(season: int) -> dict[str, Any]:
    path = season_path(season)
    if not path.exists():
        return {"season": season, "fetched_through": None, "games": []}
    return json.loads(path.read_text())


def save_season(data: dict[str, Any]) -> None:
    NCAA_DIR.mkdir(parents=True, exist_ok=True)
    data["games"].sort(key=lambda g: (g["date"], g["id"]))
    # One game per line: small diffs, still valid JSON.
    body = ",\n".join(json.dumps(g, separators=(",", ":")) for g in data["games"])
    head = {k: v for k, v in data.items() if k != "games"}
    text = json.dumps(head)[:-1] + ', "games": [\n' + body + "\n]}\n"
    season_path(data["season"]).write_text(text)


def refresh_season(season: int = SEASON, today: date | None = None, full: bool = False, pause: float = 0.15) -> dict[str, Any]:
    """Fetch completed D-I games for a season. Incremental unless `full` or no file yet."""
    today = today or datetime.now(timezone.utc).date()
    start, end = season_window(season)
    end = min(end, today)
    data = load_season(season)
    have = {g["id"]: g for g in data["games"]}
    if not full and data.get("fetched_through"):
        start = max(start, date.fromisoformat(data["fetched_through"]) - timedelta(days=REFRESH_DAYS))
    days = fetched = 0
    d = start
    while d <= end:
        try:
            for g in fetch_scoreboard(d):
                have[g["id"]] = g
                fetched += 1
        except requests.RequestException as exc:
            print(f"scoreboard {d}: {exc}")
            end = d - timedelta(days=1)  # stop here; resume from this day next run
            break
        days += 1
        d += timedelta(days=1)
        if pause:
            time.sleep(pause)
    data["games"] = list(have.values())
    data["fetched_through"] = end.isoformat()
    data["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_season(data)
    return {"season": season, "days": days, "games_seen": fetched, "games_total": len(data["games"])}


# ---------------------------------------------------------------- box enrichment


def _box_int(stats: dict[str, Any], key: str) -> int | None:
    try:
        return int(float(stats.get(key)))
    except (TypeError, ValueError):
        return None


BOX_VERSION = 3  # 1: orb/to/fga/fta only; 2: full team box (for player-rating weights); 3: + player lines and stints in the book
BOX_KEYS = ("orb", "to", "fga", "fta", "fgm", "ftm", "tpm", "tpa", "drb", "ast", "stl", "blk", "pf")


def parse_enrichment(summary: dict[str, Any]) -> dict[str, Any]:
    """The few summary fields the model wants: offensive rebounds, turnovers, and the closing line.

    ESPN's pickcenter carries the DraftKings number it showed at tip (close-ish).
    Its `spread` is the favourite's number; we store it from the home side.
    """
    out: dict[str, Any] = {"box": BOX_VERSION}
    for t in summary.get("boxscore", {}).get("teams", []):
        stats = {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}
        side = t.get("homeAway")
        if side in ("home", "away"):
            out[f"{side}_orb"] = _box_int(stats, "offensiveRebounds")
            out[f"{side}_to"] = _box_int(stats, "totalTurnovers")
            fg = (stats.get("fieldGoalsMade-fieldGoalsAttempted") or "").split("-")
            ft = (stats.get("freeThrowsMade-freeThrowsAttempted") or "").split("-")
            out[f"{side}_fga"] = int(fg[1]) if len(fg) == 2 and fg[1].isdigit() else None
            out[f"{side}_fta"] = int(ft[1]) if len(ft) == 2 and ft[1].isdigit() else None
            tp = (stats.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted") or "").split("-")
            out[f"{side}_fgm"] = int(fg[0]) if len(fg) == 2 and fg[0].isdigit() else None
            out[f"{side}_ftm"] = int(ft[0]) if len(ft) == 2 and ft[0].isdigit() else None
            out[f"{side}_tpm"] = int(tp[0]) if len(tp) == 2 and tp[0].isdigit() else None
            out[f"{side}_tpa"] = int(tp[1]) if len(tp) == 2 and tp[1].isdigit() else None
            for key, name in (("drb", "defensiveRebounds"), ("ast", "assists"), ("stl", "steals"),
                              ("blk", "blocks"), ("pf", "fouls")):
                out[f"{side}_{key}"] = _box_int(stats, name)
    for pc in summary.get("pickcenter", []) or []:
        spread, total = pc.get("spread"), pc.get("overUnder")
        if spread is None and total is None:
            continue
        home_fav = (pc.get("homeTeamOdds") or {}).get("favorite")
        away_fav = (pc.get("awayTeamOdds") or {}).get("favorite")
        if spread is not None:
            mag = abs(float(spread))
            spread = -mag if home_fav else (mag if away_fav else (0.0 if mag == 0 else None))
        out["line"] = {"book": (pc.get("provider") or {}).get("name"), "home_spread": spread, "total": total}
        break
    return out


def fetch_enrichment(game_id: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """One summary request: the team box extras, plus the game's compact book entry."""
    from . import book, pbp

    resp = requests.get(f"{ESPN_BASE}/summary", params={"event": game_id}, timeout=TIMEOUT)
    resp.raise_for_status()
    summary = resp.json()
    try:
        entry = book.encode_game(pbp.game_from_summary(game_id, summary))
    except (KeyError, ValueError, TypeError, IndexError):
        entry = None
    return parse_enrichment(summary), entry


def enrich_season(season: int = SEASON, limit: int | None = None, workers: int = 4) -> dict[str, int]:
    """Add box score extras to games that lack them. Saves as it goes so a stop loses little."""
    from concurrent.futures import ThreadPoolExecutor

    data = load_season(season)
    todo = [g for g in data["games"] if (g.get("box") or 0) < BOX_VERSION]
    if limit is not None:
        todo = todo[:limit]
    done = failed = 0
    entries: dict[str, Any] = {}

    def flush() -> None:
        from . import book

        save_season(data)
        book.save_games(season, entries)
        entries.clear()

    def one(g: dict[str, Any]) -> bool:
        try:
            extra, entry = fetch_enrichment(g["id"])
        except (requests.RequestException, ValueError):
            return False
        if entry is not None:
            entries[g["id"]] = entry
        for side in ("home", "away"):
            for k in BOX_KEYS:
                v = extra.pop(f"{side}_{k}", None)
                if v is not None:
                    g[side][k] = v
        g.update(extra)
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, ok in enumerate(pool.map(one, todo), 1):
            done += ok
            failed += not ok
            if i % 500 == 0:
                flush()
    flush()
    return {"season": season, "enriched": done, "failed": failed, "remaining": len(todo) - done}


def fetch_d1_teams() -> dict[str, Any]:
    resp = requests.get(f"{ESPN_BASE}/teams", params={"groups": 50, "limit": 500}, timeout=TIMEOUT)
    resp.raise_for_status()
    teams = {}
    for t in resp.json()["sports"][0]["leagues"][0]["teams"]:
        t = t["team"]
        teams[t["id"]] = {"name": t.get("displayName"), "short": t.get("shortDisplayName") or t.get("location"),
                          "abbr": t.get("abbreviation")}
    out = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "teams": teams}
    NCAA_DIR.mkdir(parents=True, exist_ok=True)
    TEAMS_PATH.write_text(json.dumps(out, indent=0))
    return out


def load_d1_teams() -> dict[str, dict[str, Any]]:
    if not TEAMS_PATH.exists():
        return {}
    return json.loads(TEAMS_PATH.read_text())["teams"]
