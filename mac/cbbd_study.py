"""Multi-season backtest on CollegeBasketballData.com box scores and lines.

For each season, the prior is the season before (fit from CBBD boxes too), every slate
sees only earlier games, and projections are scored against the result, the closing
line and the OPENING line. Two model settings run side by side: the one live before
Nov 2026 ("v1.0") and the current one ("v1.1": opening-fortnight home bump, lighter
regression of the prior). The v1.1 knobs were picked on 2025-26 ESPN data, so every
other season here is out-of-sample for them.

Writes data/model/cbbd_study.json: summary numbers only (no CBBD rows; see cbbd.py).
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from . import cbbd
from . import ratings as R
from .config import DATA_DIR

OUT = DATA_DIR / "model" / "cbbd_study.json"
SETTINGS = {
    "v1.0": replace(R.Params(), regress=0.2, open_home_wk1=0.0, open_home_wk2=0.0),
    "v1.1": R.Params(),
}
PHASES = {"first_14_days": lambda d: d < 14, "rest_of_nov": lambda d: 14 <= d < 30,
          "dec": lambda d: 30 <= d < 61, "jan_on": lambda d: d >= 61}


def _games(season: int) -> list[dict[str, Any]]:
    return cbbd.games_from_team_boxes(cbbd.cached("teams", season) or [])


def season_rows(season: int) -> tuple[list[dict[str, Any]], set[str]]:
    games = _games(season)
    # A team is D-I if it played a full schedule this season or last (so a partial season still works).
    d1 = cbbd.d1_ids(games + _games(season - 1))
    rows = R.game_rows(games, d1, R.calibrate_to_minus_orb(games))
    lines = cbbd.lines_by_game(cbbd.cached("lines", season) or [])
    for r in rows:
        r["line"] = lines.get(r["id"])
    return rows, d1


def _mae(xs: list[float]) -> float | None:
    return round(mean(xs), 3) if xs else None


def score(proj: list[dict[str, Any]]) -> dict[str, Any]:
    act = lambda r: r["pts_h"] - r["pts_a"]  # noqa: E731
    close = [r for r in proj if (r.get("line") or {}).get("home_spread") is not None]
    opn = [r for r in proj if (r.get("line") or {}).get("open_spread") is not None]
    tot = [r for r in proj if (r.get("line") or {}).get("total") is not None]
    return {
        "games": len(proj),
        "model_mae": _mae([abs(r["proj"]["margin"] - act(r)) for r in proj]),
        "lined_close": len(close),
        "model_mae_vs_close_games": _mae([abs(r["proj"]["margin"] - act(r)) for r in close]),
        "close_mae": _mae([abs(-r["line"]["home_spread"] - act(r)) for r in close]),
        "lined_open": len(opn),
        "model_mae_vs_open_games": _mae([abs(r["proj"]["margin"] - act(r)) for r in opn]),
        "open_mae": _mae([abs(-r["line"]["open_spread"] - act(r)) for r in opn]),
        "model_total_mae": _mae([abs(r["proj"]["total"] - r["pts_h"] - r["pts_a"]) for r in tot]),
        "close_total_mae": _mae([abs(r["line"]["total"] - r["pts_h"] - r["pts_a"]) for r in tot]),
    }


def run_season(season: int) -> dict[str, Any] | None:
    prev, prev_d1 = season_rows(season - 1)
    rows, d1 = season_rows(season)
    if not prev or not rows:
        return None
    start = min(r["date"] for r in rows)
    out: dict[str, Any] = {"season": season}
    for name, p in SETTINGS.items():
        end = max(r["date"] for r in prev)
        prior = R.fit(prev, end.replace(hour=23, minute=59), p)
        proj = R.walk_forward(rows, p, prior)
        res = {"all": score(proj)}
        for ph, keep in PHASES.items():
            res[ph] = score([r for r in proj if keep(R.days_since(start, r["date"]))])
        out[name] = res
        print(season, name, json.dumps(res["all"]), flush=True)
    return out


def main(lo: int, hi: int) -> dict[str, Any]:
    seasons = [s for s in (run_season(s) for s in range(lo, hi + 1)) if s]
    result = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "source": cbbd.ATTRIBUTION, "settings": {k: asdict(v) for k, v in SETTINGS.items()},
              "seasons": seasons}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1))
    print("saved:", OUT)
    return result
