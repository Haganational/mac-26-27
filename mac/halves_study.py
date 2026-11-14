"""First half vs second half: what a halftime score does and doesn't tell you.

Built from CollegeBasketballData.com game scores by period (homePeriodPoints /
awayPeriodPoints) and closing lines, every season in the cache. Seasons up to SPLIT
are used to fit; later seasons only to check. Four questions:

1. Halftime projection. How much of a halftime lead carries into the second half,
   once you know the pregame line? Fit  H2 = a + b*expected + c*H1  on the early
   seasons, score it on the late ones against two simple rules.
2. Totals the same way: second-half points from the closing total and first-half points.
3. "Second-half teams". Is a team's habit of playing better (or worse) after the break
   real? If it is, a team's H2-minus-H1 margin in its odd-numbered games predicts the
   same number in its even-numbered games, and carries over to next season.
4. Halftime leads. How often a lead of each size holds, for the content desk.

Writes data/model/halves_study.json: summary numbers only (no CBBD rows; see cbbd.py).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

from . import cbbd
from .config import DATA_DIR

OUT = DATA_DIR / "model" / "halves_study.json"
SPLIT = 2021  # fit on seasons <= SPLIT, check on later ones


def game_halves(season: int) -> list[dict[str, Any]]:
    """One row per finished game with both halves and (if any) the closing line."""
    lines = cbbd.lines_by_game(cbbd.cached("lines", season) or [])
    out = []
    for g in cbbd.cached("games", season) or []:
        hp, ap = g.get("homePeriodPoints"), g.get("awayPeriodPoints")
        if not isinstance(hp, list) or not isinstance(ap, list) or len(hp) < 2 or len(ap) < 2:
            continue
        if any(not isinstance(x, (int, float)) for x in hp[:2] + ap[:2]):
            continue
        ln = lines.get(str(g.get("id"))) or {}
        out.append({
            "season": season, "id": str(g.get("id")), "date": g.get("startDate") or "",
            "home": str(g.get("homeTeamId")), "away": str(g.get("awayTeamId")),
            "h1": hp[0] - ap[0], "h2": hp[1] - ap[1], "t1": hp[0] + ap[0], "t2": hp[1] + ap[1],
            "ot": len(hp) > 2,
            "tot_ot": sum(x for x in hp[2:] + ap[2:] if isinstance(x, (int, float))),
            "final": (g.get("homePoints") or sum(hp)) - (g.get("awayPoints") or sum(ap)),
            "exp": -ln["home_spread"] if ln.get("home_spread") is not None else None,
            "exp_total": ln.get("total"),
        })
    return out


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


def projection(rows: list[dict[str, Any]], y_key: str, exp_key: str, h1_key: str) -> dict[str, Any]:
    lined = [r for r in rows if r[exp_key] is not None]
    tr = [r for r in lined if r["season"] <= SPLIT]
    te = [r for r in lined if r["season"] > SPLIT]
    if len(tr) < 200 or len(te) < 200:
        return {"skipped": "not enough lined games", "train": len(tr), "test": len(te)}

    def mat(rs):
        return (np.array([[1.0, r[exp_key], r[h1_key]] for r in rs]), np.array([r[y_key] for r in rs], float))

    Xtr, ytr = mat(tr)
    Xte, yte = mat(te)
    a, b, c = _ols(Xtr, ytr)
    # Rules to beat: the line split evenly; the line split by the training share plus nothing from H1;
    # "the first half repeats" (H2 = H1).
    share = float(np.sum(ytr) / np.sum(Xtr[:, 1])) if np.sum(Xtr[:, 1]) else 0.5
    preds = {
        "fitted": Xte @ np.array([a, b, c]),
        "half_the_line": Xte[:, 1] / 2,
        "line_share_only": Xte[:, 1] * share,
        "first_half_repeats": Xte[:, 2],
    }
    return {
        "train_games": len(tr), "test_games": len(te),
        "coef": {"intercept": round(float(a), 3), "pregame": round(float(b), 3), "first_half": round(float(c), 3)},
        "test_mae": {k: round(float(np.mean(np.abs(v - yte))), 3) for k, v in preds.items()},
        "test_rmse": {k: round(float(np.sqrt(np.mean((v - yte) ** 2))), 3) for k, v in preds.items()},
        "test_resid_sd_fitted": round(float(np.std(preds["fitted"] - yte)), 3),
    }


def _corr(x: list[float], y: list[float]) -> float | None:
    if len(x) < 30:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 3)


def second_half_teams(rows: list[dict[str, Any]], min_games: int = 16) -> dict[str, Any]:
    """Split-half and year-to-year reliability of a team's (H2 margin - H1 margin)."""
    per: dict[tuple[int, str], list[tuple[str, float, float]]] = defaultdict(list)
    for r in rows:
        for team, sign in ((r["home"], 1), (r["away"], -1)):
            # margin swing after the break, and the same for points scored (pace/fouling habits)
            per[(r["season"], team)].append((r["date"], sign * (r["h2"] - r["h1"]), 0.0))
    odd, even, by_ts = [], [], {}
    for key, gs in per.items():
        if len(gs) < min_games:
            continue
        gs.sort()
        vals = [v for _, v, _ in gs]
        odd.append(float(np.mean(vals[0::2])))
        even.append(float(np.mean(vals[1::2])))
        by_ts[key] = float(np.mean(vals))
    yy_x, yy_y = [], []
    for (season, team), v in by_ts.items():
        nxt = by_ts.get((season + 1, team))
        if nxt is not None:
            yy_x.append(v)
            yy_y.append(nxt)
    spread = float(np.std(list(by_ts.values()))) if by_ts else None
    # How big would the spread of team averages be from luck alone? Per-game SD / sqrt(games).
    all_vals = [v for gs in per.values() for _, v, _ in gs]
    avg_n = float(np.mean([len(gs) for k, gs in per.items() if k in by_ts])) if by_ts else None
    luck = float(np.std(all_vals)) / math.sqrt(avg_n) if all_vals and avg_n else None
    return {
        "team_seasons": len(by_ts),
        "split_half_corr": _corr(odd, even),
        "year_to_year_corr": _corr(yy_x, yy_y), "year_pairs": len(yy_x),
        "sd_of_team_averages": round(spread, 3) if spread is not None else None,
        "sd_expected_from_luck_alone": round(luck, 3) if luck is not None else None,
    }


def lead_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = [(1, 3), (4, 6), (7, 9), (10, 12), (13, 15), (16, 20), (21, 99)]
    out = []
    for lo, hi in buckets:
        held = n = 0
        fav_held = fav_n = dog_held = dog_n = 0
        for r in rows:
            lead = abs(r["h1"])
            if not lo <= lead <= hi or r["final"] == 0:
                continue
            leader_home = r["h1"] > 0
            won = (r["final"] > 0) == leader_home
            n += 1
            held += won
            if r["exp"] is not None and r["exp"] != 0:
                leader_fav = (r["exp"] > 0) == leader_home
                if leader_fav:
                    fav_n += 1
                    fav_held += won
                else:
                    dog_n += 1
                    dog_held += won
        out.append({"lead": f"{lo}-{hi}" if hi < 99 else f"{lo}+", "games": n,
                    "leader_won": round(held / n, 3) if n else None,
                    "favorite_leading_won": round(fav_held / fav_n, 3) if fav_n else None, "fav_games": fav_n,
                    "underdog_leading_won": round(dog_held / dog_n, 3) if dog_n else None, "dog_games": dog_n})
    return out


def totals_shape(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reg = [r for r in rows if not r["ot"]]
    close = [r for r in reg if abs(r["final"]) <= 5]
    blow = [r for r in reg if abs(r["final"]) >= 20]

    def share(rs):
        t1, t2 = sum(r["t1"] for r in rs), sum(r["t2"] for r in rs)
        return round(t2 / (t1 + t2), 4) if rs else None

    return {"games": len(reg), "second_half_share_of_points": share(reg),
            "share_in_games_decided_by_5_or_less": share(close), "share_in_blowouts_20_plus": share(blow),
            "avg_first_half_points": round(float(np.mean([r["t1"] for r in reg])), 2) if reg else None,
            "avg_second_half_points": round(float(np.mean([r["t2"] for r in reg])), 2) if reg else None}


def _ou_rate(rs: list[dict[str, Any]]) -> dict[str, Any]:
    o = sum(1 for r in rs if r["t1"] + r["t2"] + r.get("tot_ot", 0) > r["exp_total"])
    u = sum(1 for r in rs if r["t1"] + r["t2"] + r.get("tot_ot", 0) < r["exp_total"])
    n = o + u
    return {"over": o, "under": u, "over_pct": round(o / n, 3) if n else None}


def overs_unders(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Full-game over/under against the closing total, sliced by things known before tip
    (spread size, total size) and by the first half (known only at halftime)."""
    lined = [r for r in rows if r["exp_total"] is not None and r["exp"] is not None]
    fit = [r for r in lined if r["season"] <= SPLIT]
    chk = [r for r in lined if r["season"] > SPLIT]

    def both(pred):
        return {"fit": _ou_rate([r for r in fit if pred(r)]), "check": _ou_rate([r for r in chk if pred(r)])}

    out: dict[str, Any] = {"all": both(lambda r: True)}
    out["by_spread"] = {f"{lo}-{hi}": both(lambda r, lo=lo, hi=hi: lo <= abs(r["exp"]) < hi)
                        for lo, hi in ((0, 3), (3, 7), (7, 12), (12, 18), (18, 99))}
    totals = sorted(r["exp_total"] for r in fit)
    q = [totals[int(len(totals) * f)] for f in (0.2, 0.4, 0.6, 0.8)] if totals else []
    edges = [0.0] + q + [999.0]
    out["by_total_quintile"] = {f"{edges[i]:.1f}-{edges[i + 1]:.1f}": both(lambda r, a=edges[i], b=edges[i + 1]: a <= r["exp_total"] < b)
                                for i in range(len(edges) - 1)}
    out["november_only"] = both(lambda r: r["date"][5:7] == "11")
    # Halftime: first-half points vs the share of the total a first half usually gets.
    share1 = sum(r["t1"] for r in fit) / sum(r["exp_total"] for r in fit) if fit else 0.473
    out["first_half_share_of_total"] = round(share1, 4)
    for r in lined:
        r["_dev1"] = r["t1"] - share1 * r["exp_total"]
    out["by_first_half_vs_pace"] = {f"{lo}..{hi}": both(lambda r, lo=lo, hi=hi: lo <= r["_dev1"] < hi)
                                    for lo, hi in ((-99, -10), (-10, -5), (-5, 0), (0, 5), (5, 10), (10, 99))}
    # Does the second half give back a hot/cold first half? Slope of H2 deviation on H1 deviation.
    share2 = 1 - share1
    x = np.array([r["_dev1"] for r in fit])
    y = np.array([r["t2"] - share2 * r["exp_total"] for r in fit])
    xc = np.array([r["_dev1"] for r in chk])
    yc = np.array([r["t2"] - share2 * r["exp_total"] for r in chk])
    if len(x) > 100 and len(xc) > 100:
        out["second_half_carryover_slope"] = {"fit": round(float(np.polyfit(x, y, 1)[0]), 3), "check": round(float(np.polyfit(xc, yc, 1)[0]), 3)}
        out["second_half_bias_vs_share"] = {"fit": round(float(y.mean()), 2), "check": round(float(yc.mean()), 2)}
    for r in lined:
        r.pop("_dev1", None)
    return out


def main(lo: int, hi: int) -> dict[str, Any]:
    rows = [r for s in range(lo, hi + 1) for r in game_halves(s)]
    by_season = defaultdict(int)
    for r in rows:
        by_season[r["season"]] += 1
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": cbbd.ATTRIBUTION, "fit_seasons": f"<= {SPLIT}", "check_seasons": f"> {SPLIT}",
        "games_by_season": dict(sorted(by_season.items())),
        "margin_projection": projection(rows, "h2", "exp", "h1"),
        "total_projection": projection(rows, "t2", "exp_total", "t1"),
        "second_half_teams": second_half_teams(rows),
        "second_half_teams_check_seasons_only": second_half_teams([r for r in rows if r["season"] > SPLIT]),
        "halftime_leads": lead_table(rows),
        "totals_shape": totals_shape(rows),
        "overs_unders": overs_unders(rows),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))
    print("saved:", OUT)
    return result
