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
        "blend": {"spread": blend_study(proj, "spread"), "total": blend_study(proj, "total")},
    }


# --- Model-to-market blend -------------------------------------------------------
# The raw model trails the closing number, and raw gaps to it barely predict covers.
# So treat the market as the base forecast and ask how much of the model's
# disagreement to keep: blended = market + w * (model - market). w is fit walk-forward
# (only games from earlier dates), shrunk toward 0, and an edge is only published when
# the blended edge clears a gate chosen on the first half of the season and checked on
# the second half.

BLEND_MIN_GAMES = 300   # no blending until this many lined games have been seen
BLEND_SHRINK = 200.0    # pseudo-games pulling w toward 0
BLEND_GATES = (0.5, 0.75, 1.0, 1.5, 2.0)


def _blend_w(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope through the origin of (actual - market) on (model - market), shrunk to 0."""
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    if not xs or sxx == 0:
        return 0.0
    n = len(xs)
    w = sxy / sxx
    return max(0.0, min(1.0, w * n / (n + BLEND_SHRINK)))


def _wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if not n:
        return None
    ph = w / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** 0.5) / d
    return round(c - h, 3), round(c + h, 3)


def _record(picks: list[tuple[float, float]]) -> dict[str, Any]:
    """picks: (signed blended edge, signed result vs line). Win when signs agree; 0 result is a push."""
    w = sum(1 for e, r in picks if r != 0 and (r > 0) == (e > 0))
    l = sum(1 for e, r in picks if r != 0 and (r > 0) != (e > 0))
    n = w + l
    return {"w": w, "l": l, "pct": round(w / n, 3) if n else None, "ci95": _wilson(w, n),
            "beats_juice": bool(n and _wilson(w, n)[0] > JUICE_BREAKEVEN)}


def blend_study(proj: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    """kind 'spread' (home margin) or 'total'. Walk-forward w, blended MAE, and gated pick record."""
    def parts(r: dict[str, Any]) -> tuple[float, float, float] | None:
        line = r.get("line") or {}
        if kind == "spread":
            if line.get("home_spread") is None:
                return None
            return r["proj"]["margin"], -line["home_spread"], float(r["pts_h"] - r["pts_a"])
        if line.get("total") is None:
            return None
        return r["proj"]["total"], float(line["total"]), float(r["pts_h"] + r["pts_a"])

    games = sorted((r["date"], p) for r in proj if (p := parts(r)))
    xs: list[float] = []
    ys: list[float] = []
    out_rows = []
    i = 0
    while i < len(games):
        day = games[i][0]
        w = _blend_w(xs, ys) if len(xs) >= BLEND_MIN_GAMES else 0.0
        while i < len(games) and games[i][0] == day:
            model, mkt, actual = games[i][1]
            out_rows.append({"date": day, "w": w, "model": model, "mkt": mkt, "actual": actual,
                             "blend": mkt + w * (model - mkt)})
            i += 1
        for o in out_rows[len(xs):]:
            xs.append(o["model"] - o["mkt"])
            ys.append(o["actual"] - o["mkt"])
    if not out_rows:
        return {"games": 0}
    half = len(out_rows) // 2
    first, second = out_rows[:half], out_rows[half:]

    def picks(rows: list[dict[str, Any]], gate: float) -> list[tuple[float, float]]:
        return [(o["blend"] - o["mkt"], o["actual"] - o["mkt"]) for o in rows
                if abs(o["blend"] - o["mkt"]) >= gate]

    # Gate chosen on the first half only: the smallest gate whose record is best, needing 50+ picks.
    scored = [(g, _record(picks(first, g))) for g in BLEND_GATES]
    eligible = [(g, s) for g, s in scored if s["w"] + s["l"] >= 50]
    gate = max(eligible, key=lambda gs: (gs[1]["pct"] or 0, -gs[0]))[0] if eligible else BLEND_GATES[-1]
    holdout = _record(picks(second, gate))
    final_w = _blend_w(xs, ys)
    return {
        "games": len(out_rows),
        "w_final": round(final_w, 3),
        "w_path": [round(out_rows[int(len(out_rows) * q) - 1]["w"], 3) for q in (0.25, 0.5, 0.75, 1.0)],
        "model_mae": round(mean(abs(o["model"] - o["actual"]) for o in out_rows), 2),
        "market_mae": round(mean(abs(o["mkt"] - o["actual"]) for o in out_rows), 2),
        "blend_mae": round(mean(abs(o["blend"] - o["actual"]) for o in out_rows), 2),
        "raw_edge_3plus": _record([(o["model"] - o["mkt"], o["actual"] - o["mkt"]) for o in out_rows
                                   if abs(o["model"] - o["mkt"]) >= 3]),
        "gate_tuning_first_half": [{"gate": g, **s} for g, s in scored],
        "gate": gate,
        "holdout_second_half": holdout,
        "publish_edges": holdout["beats_juice"],
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
