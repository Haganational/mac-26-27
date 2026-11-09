"""Walk-forward backtest of the rating model against results and closing lines.

For each day of a past season, refit on everything before that morning, project the
day's games, then score the projections against what happened and against the
DraftKings number ESPN recorded at tip. No look-ahead: the prior is the season
before, and each slate only sees earlier games.

    python -m mac.backtest            # 2025-26, prior from 2024-25, default params
    python -m mac.backtest tune       # small grid over the knobs
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from . import ncaa
from . import ratings as R
from .config import DATA_DIR, TEAMS

MAC_IDS = {t.espn_id for t in TEAMS}
BACKTEST_PATH = DATA_DIR / "model" / "backtest.json"
EDGE_BUCKETS = (0, 1, 2, 3, 4, 5, 7)
JUICE_BREAKEVEN = 0.5238  # -110 both ways


def season_rows(season: int, d1: set[str]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    games = ncaa.load_season(season)["games"]
    c = R.calibrate_to_minus_orb(games)
    rows = R.game_rows(games, d1, c)
    lines = {g["id"]: g.get("line") for g in games if g.get("line")}
    mac = {g["id"] for g in games if g["home"]["id"] in MAC_IDS or g["away"]["id"] in MAC_IDS}
    for r in rows:
        r["line"] = lines.get(r["id"])
        r["mac"] = r["id"] in mac
    return rows, lines


def season_end_prior(season: int, d1: set[str], p: R.Params) -> R.Ratings:
    """Final ratings of a finished season, fit with the same recency weighting."""
    games = ncaa.load_season(season)["games"]
    rows = R.game_rows(games, d1, R.calibrate_to_minus_orb(games))
    end = max(r["date"] for r in rows)
    return R.fit(rows, end.replace(hour=23, minute=59), p)


def _ats(rows: list[dict[str, Any]], edge_min: float, edge_max: float | None = None) -> dict[str, Any]:
    w = l = push = 0
    for r in rows:
        line = (r.get("line") or {}).get("home_spread")
        if line is None:
            continue
        edge = r["proj"]["spread"] - line  # negative: model likes home more than the market
        if abs(edge) < edge_min or (edge_max is not None and abs(edge) >= edge_max):
            continue
        result = (r["pts_h"] - r["pts_a"]) + line  # >0 home covered
        if result == 0:
            push += 1
            continue
        took_home = edge < 0
        if (result > 0) == took_home:
            w += 1
        else:
            l += 1
    n = w + l
    return {"w": w, "l": l, "push": push, "pct": round(w / n, 3) if n else None}


def _ou(rows: list[dict[str, Any]], edge_min: float, edge_max: float | None = None) -> dict[str, Any]:
    w = l = push = 0
    for r in rows:
        line = (r.get("line") or {}).get("total")
        if line is None:
            continue
        edge = r["proj"]["total"] - line
        if abs(edge) < edge_min or (edge_max is not None and abs(edge) >= edge_max):
            continue
        pts = r["pts_h"] + r["pts_a"]
        if pts == line:
            push += 1
            continue
        if (pts > line) == (edge > 0):
            w += 1
        else:
            l += 1
    n = w + l
    return {"w": w, "l": l, "push": push, "pct": round(w / n, 3) if n else None}


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"games": 0}
    margin_err = [abs(r["proj"]["margin"] - (r["pts_h"] - r["pts_a"])) for r in rows]
    total_err = [abs(r["proj"]["total"] - (r["pts_h"] + r["pts_a"])) for r in rows]
    with_spread = [r for r in rows if (r.get("line") or {}).get("home_spread") is not None]
    with_total = [r for r in rows if (r.get("line") or {}).get("total") is not None]
    out: dict[str, Any] = {
        "games": len(rows),
        "margin_mae": round(mean(margin_err), 2),
        "total_mae": round(mean(total_err), 2),
        "winner_pct": round(mean(1.0 if (r["proj"]["margin"] > 0) == (r["pts_h"] > r["pts_a"]) else 0.0 for r in rows), 3),
        "lined_games": len(with_spread),
    }
    if with_spread:
        out["model_margin_mae_lined"] = round(mean(abs(r["proj"]["margin"] - (r["pts_h"] - r["pts_a"])) for r in with_spread), 2)
        out["market_margin_mae"] = round(mean(abs(-r["line"]["home_spread"] - (r["pts_h"] - r["pts_a"])) for r in with_spread), 2)
        out["spread_gap_mae"] = round(mean(abs(r["proj"]["spread"] - r["line"]["home_spread"]) for r in with_spread), 2)
    if with_total:
        out["model_total_mae_lined"] = round(mean(abs(r["proj"]["total"] - (r["pts_h"] + r["pts_a"])) for r in with_total), 2)
        out["market_total_mae"] = round(mean(abs(r["line"]["total"] - (r["pts_h"] + r["pts_a"])) for r in with_total), 2)
        out["total_gap_mae"] = round(mean(abs(r["proj"]["total"] - r["line"]["total"]) for r in with_total), 2)
    buckets = list(EDGE_BUCKETS) + [None]
    out["ats_by_edge"] = [{"edge": f"{lo}-{hi}" if hi is not None else f"{lo}+", **_ats(rows, lo, hi)}
                          for lo, hi in zip(buckets[:-1], buckets[1:])]
    out["ou_by_edge"] = [{"edge": f"{lo}-{hi}" if hi is not None else f"{lo}+", **_ou(rows, lo, hi)}
                         for lo, hi in zip(buckets[:-1], buckets[1:])]
    out["ats_edge_3plus"] = _ats(rows, 3)
    out["ou_edge_3plus"] = _ou(rows, 3)
    return out


def run(season: int = 2026, p: R.Params = R.Params(), d1: set[str] | None = None) -> dict[str, Any]:
    d1 = d1 or set(ncaa.load_d1_teams())
    prior = season_end_prior(season - 1, d1, p)
    rows, _ = season_rows(season, d1)
    proj = R.walk_forward(rows, p, prior)
    # Calibrate the win-probability spread from residuals.
    resid = [r["proj"]["margin"] - (r["pts_h"] - r["pts_a"]) for r in proj]
    sd = (sum(x * x for x in resid) / len(resid)) ** 0.5 if resid else None
    tresid = [r["proj"]["total"] - (r["pts_h"] + r["pts_a"]) for r in proj]
    tsd = (sum(x * x for x in tresid) / len(tresid)) ** 0.5 if tresid else None
    phases = {
        "nov": [r for r in proj if r["date"].month == 11],
        "dec": [r for r in proj if r["date"].month == 12],
        "jan_on": [r for r in proj if r["date"].month in (1, 2, 3, 4)],
    }
    return {
        "season": season,
        "params": asdict(p),
        "residual_sd_margin": round(sd, 2) if sd else None,
        "residual_sd_total": round(tsd, 2) if tsd else None,
        "bias_margin": round(mean(resid), 2) if resid else None,
        "bias_total": round(mean(tresid), 2) if tresid else None,
        "all": score(proj),
        "mac": score([r for r in proj if r["mac"]]),
        "mac_conf": score([r for r in proj if r["home"] in MAC_IDS and r["away"] in MAC_IDS]),
        "by_phase": {k: score(v) for k, v in phases.items()},
        "mac_by_phase": {k: score([r for r in v if r["mac"]]) for k, v in phases.items()},
    }


GRID = {
    "half_life": [30.0, 60.0, 120.0, 1e6],
    "prior_games": [2.0, 4.0, 8.0],
    "regress": [0.2, 0.35, 0.5],
    "cap": [20.0, 30.0, 1e6],
    "hca_prior_games": [300.0, 3000.0, 30000.0],
    "non_d1_weight": [0.25, 0.5, 1.0],
    "tempo_prior_games": [1.0, 3.0, 8.0],
}


def tune(season: int = 2026) -> list[dict[str, Any]]:
    """One knob at a time around the defaults; scored on margin MAE across all D-I games."""
    d1 = set(ncaa.load_d1_teams())
    base = R.Params()
    results = []
    for knob, values in GRID.items():
        for v in values:
            p = replace(base, **{knob: v})
            res = run(season, p, d1)
            results.append({"knob": knob, "value": v, "margin_mae": res["all"]["margin_mae"],
                            "lined_mae": res["all"].get("model_margin_mae_lined"),
                            "lined_total_mae": res["all"].get("model_total_mae_lined"),
                            "dec_mae": res["by_phase"]["dec"]["margin_mae"], "jan_mae": res["by_phase"]["jan_on"]["margin_mae"],
                            "bias": res["bias_margin"],
                            "total_mae": res["all"]["total_mae"],
                            "spread_gap_mae": res["all"].get("spread_gap_mae"),
                            "mac_margin_mae": res["mac"]["margin_mae"],
                            "nov_margin_mae": res["by_phase"]["nov"]["margin_mae"],
                            "ats3": res["all"]["ats_edge_3plus"]["pct"]})
            print(json.dumps(results[-1]))
    return results


def save(result: dict[str, Any]) -> str:
    BACKTEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = {**result, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    BACKTEST_PATH.write_text(json.dumps(result, indent=1))
    return str(BACKTEST_PATH)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "tune":
        tune()
    else:
        res = run()
        print(json.dumps({k: v for k, v in res.items() if k not in ("by_phase", "mac_by_phase")}, indent=1))
        print("saved:", save(res))
