"""CollegeBasketballData.com (CBBD): a decade of box scores and opening + closing lines.

Why we want it
--------------
ESPN gives us every D-I game since 2024-25, but only the DraftKings number at tip, and
in 2025-26 no lines at all for the first three weeks. CBBD has team box scores back to
2003 and lines (several books, with opening AND closing spread/total) back to 2013, so
the model can be backtested across ten-plus seasons instead of one, scored against the
opener as well as the close, and tuned on early-season games we have never had lines for.

Terms (collegebasketballdata.com/terms, read Nov 14, 2026)
----------------------------------------------------------
- Commercial use is allowed; attribution is appreciated, not required. We credit
  "Data provided by CollegeBasketballData.com" wherever a number derived from it shows.
- No raw mirror: the API's responses must not be republished as a dataset, feed or bulk
  download. This repo is public, so raw responses live ONLY in data/cache/cbbd/ (git-
  ignored; a GitHub Actions cache on CI). What gets committed is our own derived output
  (backtest summaries), never the rows themselves.
- The key must stay server-side: it is read from the CBBD_API_KEY secret.
- Free tier: 1,000 calls a month, shared with CollegeFootballData. Every call is logged to
  data/cbbd_calls.jsonl (date and path only) and we stop at CALL_BUDGET for the month.

    CBBD_API_KEY=... python -m mac.cbbd backfill 2014 2026   # ~15 calls a season, cached
    python -m mac.cbbd study 2015 2026                       # backtest from the cache, no calls
"""

from __future__ import annotations

import gzip
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

import requests

from .config import SHARED_DIR

BASE = "https://api.collegebasketballdata.com"
TIMEOUT = 60
CACHE_DIR = SHARED_DIR / "cache" / "cbbd"
CALL_LOG = SHARED_DIR / "cbbd_calls.jsonl"
CALL_BUDGET = int(os.environ.get("CBBD_MONTHLY_BUDGET", "800"))  # of the free tier's 1,000; leaves room for one-offs
ATTRIBUTION = "Data provided by CollegeBasketballData.com"

# Per-request record caps from the API docs; a full window means "split it and ask again".
CAPS = {"/games/teams": 3000, "/games/players": 1000, "/games": 3000, "/lines": 3000}


class CbbdError(RuntimeError):
    pass


# ---------------------------------------------------------------- calls and budget


def api_key() -> str:
    key = os.environ.get("CBBD_API_KEY")
    if not key:
        raise CbbdError("CBBD_API_KEY is not set (free key: https://collegebasketballdata.com/key)")
    return key


def calls_this_month(today: date | None = None) -> int:
    today = today or datetime.now(timezone.utc).date()
    if not CALL_LOG.exists():
        return 0
    month = today.strftime("%Y-%m")
    return sum(1 for line in CALL_LOG.read_text().splitlines() if line.startswith(f'{{"at": "{month}'))


def _log_call(path: str, status: int) -> None:
    CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CALL_LOG.open("a") as f:
        f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "path": path, "status": status}) + "\n")


def get(path: str, params: dict[str, Any], session: requests.Session | None = None) -> list[dict[str, Any]]:
    if calls_this_month() >= CALL_BUDGET:
        raise CbbdError(f"monthly CBBD budget of {CALL_BUDGET} calls reached; resets on the 1st")
    s = session or requests
    resp = s.get(BASE + path, params=params, headers={"Authorization": f"Bearer {api_key()}"}, timeout=TIMEOUT)
    _log_call(path, resp.status_code)
    if resp.status_code == 429:
        raise CbbdError("CBBD says the monthly quota is used up (429)")
    if resp.status_code != 200:
        raise CbbdError(f"CBBD {path} {params} returned {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return data if isinstance(data, list) else [data]


def season_windows(season: int, days: int = 30) -> list[tuple[date, date]]:
    """Nov 1 through mid-April of the season ending in `season`, in `days`-day windows."""
    start, end = date(season - 1, 11, 1), date(season, 4, 15)
    out, d = [], start
    while d <= end:
        e = min(d + timedelta(days=days - 1), end)
        out.append((d, e))
        d = e + timedelta(days=1)
    return out


def fetch_window(path: str, season: int, lo: date, hi: date,
                 getter: Callable[[str, dict[str, Any]], list[dict[str, Any]]] = get) -> list[dict[str, Any]]:
    """One date window; halves it whenever the response comes back full."""
    params = {"season": season, "startDateRange": f"{lo.isoformat()}T00:00:00Z", "endDateRange": f"{hi.isoformat()}T23:59:59Z"}
    rows = getter(path, params)
    cap = CAPS.get(path)
    if cap and len(rows) >= cap and lo < hi:
        mid = lo + (hi - lo) // 2
        return fetch_window(path, season, lo, mid, getter) + fetch_window(path, season, mid + timedelta(days=1), hi, getter)
    return rows


# ---------------------------------------------------------------- cache (git-ignored)


def cache_path(kind: str, season: int):
    return CACHE_DIR / f"{kind}-{season}.json.gz"


def cached(kind: str, season: int) -> list[dict[str, Any]] | None:
    p = cache_path(kind, season)
    if not p.exists():
        return None
    with gzip.open(p, "rt") as f:
        return json.load(f)


def store(kind: str, season: int, rows: list[dict[str, Any]]) -> None:
    p = cache_path(kind, season)
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt") as f:
        json.dump(rows, f, separators=(",", ":"))


KINDS = {"teams": "/games/teams", "lines": "/lines", "players": "/games/players"}


def backfill(seasons: list[int], kinds: tuple[str, ...] = ("teams", "lines"), refresh: bool = False) -> dict[str, int]:
    """Pull whole seasons into the cache. A finished season is fetched once, ever."""
    out = {}
    with requests.Session() as s:
        getter = lambda path, params: get(path, params, s)  # noqa: E731
        for season in seasons:
            for kind in kinds:
                if not refresh and cached(kind, season) is not None:
                    continue
                rows: list[dict[str, Any]] = []
                seen: set[Any] = set()
                for lo, hi in season_windows(season):
                    for r in fetch_window(KINDS[kind], season, lo, hi, getter):
                        key = (r.get("gameId"), r.get("teamId")) if kind != "lines" else r.get("gameId")
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append(r)
                store(kind, season, rows)
                out[f"{kind}-{season}"] = len(rows)
                print(f"cbbd {kind} {season}: {len(rows)} rows ({calls_this_month()} calls this month)", flush=True)
    return out


# ---------------------------------------------------------------- into the model's shape


def _num(x: Any, *keys: str) -> float | None:
    """Dig a number out of CBBD's nested stat objects ({"made": .., "attempted": ..} or a bare number)."""
    for k in keys:
        if isinstance(x, dict):
            x = x.get(k)
        else:
            return None
    if isinstance(x, dict):
        x = x.get("total", x.get("value"))
    return float(x) if isinstance(x, (int, float)) else None


def _side(team_id: Any, name: str | None, conf: str | None, st: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(team_id), "name": name, "conf": conf,
        "pts": _num(st, "points", "total") if isinstance(st.get("points"), dict) else _num(st, "points"),
        "fga": _num(st, "fieldGoals", "attempted"), "fgm": _num(st, "fieldGoals", "made"),
        "fta": _num(st, "freeThrows", "attempted"), "ftm": _num(st, "freeThrows", "made"),
        "tpa": _num(st, "threePointFieldGoals", "attempted"), "tpm": _num(st, "threePointFieldGoals", "made"),
        "orb": _num(st, "rebounds", "offensive"), "drb": _num(st, "rebounds", "defensive"),
        "to": _num(st, "turnovers", "total") if isinstance(st.get("turnovers"), dict) else _num(st, "turnovers"),
    }


def games_from_team_boxes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """CBBD /games/teams (one row per team-game) -> the game dicts ratings.game_rows reads."""
    by_game: dict[Any, dict[str, Any]] = {}
    for r in rows:
        g = by_game.setdefault(r["gameId"], {"id": str(r["gameId"]), "date": r.get("startDate"),
                                             "neutral": bool(r.get("neutralSite")), "season_type": r.get("seasonType"),
                                             "conference_game": bool(r.get("conferenceGame"))})
        side = "home" if r.get("isHome") else "away"
        if side in g:  # neutral-site games can arrive with isHome false on both rows
            side = "away" if side == "home" else "home"
        g[side] = _side(r.get("teamId"), r.get("team"), r.get("conference"), r.get("teamStats") or {})
        minutes = r.get("gameMinutes")
        g["ot"] = max(0, round(((minutes or 40) - 40) / 5))
    out = []
    for g in by_game.values():
        if "home" in g and "away" in g and g["home"]["pts"] is not None and g["away"]["pts"] is not None:
            out.append(g)
    out.sort(key=lambda g: g["date"] or "")
    return out


PROVIDER_ORDER = ("ESPN BET", "DraftKings", "Bovada", "William Hill (New Jersey)", "consensus")


def lines_by_game(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """gameId -> {close/open spread and total from the first provider that has them}."""
    out = {}
    for g in rows:
        books = {b.get("provider"): b for b in g.get("lines") or []}
        order = [p for p in PROVIDER_ORDER if p in books] + [p for p in books if p not in PROVIDER_ORDER]
        pick: dict[str, Any] = {}
        for p in order:
            b = books[p]
            for src, dst in (("spread", "home_spread"), ("spreadOpen", "open_spread"),
                             ("overUnder", "total"), ("overUnderOpen", "open_total")):
                if pick.get(dst) is None and isinstance(b.get(src), (int, float)):
                    pick[dst] = float(b[src])
                    pick.setdefault(f"{dst}_book", p)
        if pick:
            out[str(g.get("gameId"))] = pick
    return out


def d1_ids(games: list[dict[str, Any]], min_games: int = 15) -> set[str]:
    """Teams with a full schedule; one-off non-D-I visitors fall into ratings.NON_D1."""
    n: dict[str, int] = defaultdict(int)
    for g in games:
        n[g["home"]["id"]] += 1
        n[g["away"]["id"]] += 1
    return {t for t, k in n.items() if k >= min_games}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "backfill":
        lo, hi = int(sys.argv[2]), int(sys.argv[3] if len(sys.argv) > 3 else sys.argv[2])
        kinds = tuple(sys.argv[4].split(",")) if len(sys.argv) > 4 else ("teams", "lines")
        print(json.dumps(backfill(list(range(lo, hi + 1)), kinds)))
    elif cmd == "study":
        from .cbbd_study import main
        main(int(sys.argv[2]), int(sys.argv[3] if len(sys.argv) > 3 else sys.argv[2]))
    else:
        print(__doc__)
