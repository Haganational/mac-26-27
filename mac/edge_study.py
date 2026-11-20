"""Does the model's single biggest disagreement with the book each night cover?

Analysis only: nothing here touches the site or the live picks.

Every projection comes from a walk-forward run (R.walk_forward): each morning the
model is refit on games already played, then projects that day's slate. So every
edge below was knowable before tip. The "night" is the walk-forward slate (the
10:00 UTC morning cut, so a 9 PM ET tip counts on its own date).

Edge = model spread - book spread (home perspective). We bet the side the model
likes; result is scored against the same line at -110.

    python -m mac.edge_study espn 2026 2027     # ESPN/DraftKings line at tip (in repo)
    python -m mac.edge_study cbbd 2014 2025     # CBBD closing consensus (Actions only)
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import ratings as R
from .config import DATA_DIR

OUT = DATA_DIR / "model" / "edge_study.json"
BREAKEVEN = 110 / 210  # 0.5238 at -110
THRESHOLDS = (3, 5, 7, 10)


def _slate_key(d: datetime) -> str:
    anchor = d.replace(hour=10, minute=0, second=0, microsecond=0)
    if d < anchor:
        anchor -= timedelta(days=1)
    return anchor.date().isoformat()


def bets(proj: list[dict[str, Any]], line_key: str = "home_spread") -> list[dict[str, Any]]:
    """One candidate bet per lined game: the side the model likes, with its outcome."""
    out = []
    for r in proj:
        line = (r.get("line") or {}).get(line_key)
        if line is None:
            continue
        edge = r["proj"]["spread"] - line  # negative: model likes home more than the book
        if edge == 0:
            continue
        result = (r["pts_h"] - r["pts_a"]) + line  # >0 home covered
        take_home = edge < 0
        out.append({
            "night": _slate_key(r["date"]), "id": r["id"], "edge": abs(edge),
            "home": r.get("home_name") or r["home"], "away": r.get("away_name") or r["away"],
            "side": "home" if take_home else "away", "line": line,
            "model": round(r["proj"]["spread"], 1), "margin": r["pts_h"] - r["pts_a"],
            "games_min": min(r.get("games_h", 0), r.get("games_a", 0)),
            "book": r["line"].get(f"{line_key}_book", "espn"),
            # the model sits near the line's mirror image: a sign-flipped line is likely
            "flip_suspect": abs(line) >= 3 and abs(r["proj"]["spread"] + line) <= 3,
            "line_err": abs(-line - (r["pts_h"] - r["pts_a"])),
            "model_err": abs(r["proj"]["margin"] - (r["pts_h"] - r["pts_a"])),
            "outcome": "P" if result == 0 else ("W" if (result > 0) == take_home else "L"),
        })
    return out


def top_n_per_night(b: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    nights: dict[str, list[dict[str, Any]]] = {}
    for x in b:
        nights.setdefault(x["night"], []).append(x)
    out = []
    for night in sorted(nights):
        out.extend(sorted(nights[night], key=lambda x: -x["edge"])[:n])
    return out


def _binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    lp, lq = math.log(p), math.log(1 - p)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq
             for i in range(k, n + 1)]
    m = max(terms)
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in terms))


def _wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (0.0, 1.0)
    ph = w / n
    c = (ph + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (c - h, c + h)


def record(b: list[dict[str, Any]]) -> dict[str, Any]:
    w = sum(x["outcome"] == "W" for x in b)
    l = sum(x["outcome"] == "L" for x in b)
    p = sum(x["outcome"] == "P" for x in b)
    n = w + l
    lo, hi = _wilson(w, n)
    return {
        "bets": n, "w": w, "l": l, "push": p,
        "pct": round(w / n, 4) if n else None,
        "ci95": [round(lo, 3), round(hi, 3)],
        # one-sided: chance of doing at least this well if the true rate were breakeven
        "p_vs_breakeven": round(_binom_sf(w, n, BREAKEVEN), 4) if n else None,
        "roi": round((w * (100 / 110) - l) / (n + p), 4) if n + p else None,
        "units": round(w * (100 / 110) - l, 2),
        "avg_edge": round(sum(x["edge"] for x in b) / len(b), 2) if b else None,
    }


def strategies(b: list[dict[str, Any]]) -> dict[str, Any]:
    s: dict[str, Callable[[], list[dict[str, Any]]]] = {
        "all_lined_games": lambda: b,
        "top1_per_night": lambda: top_n_per_night(b, 1),
        "top3_per_night": lambda: top_n_per_night(b, 3),
        "top1_both_teams_5plus_games": lambda: top_n_per_night([x for x in b if x["games_min"] >= 5], 1),
    }
    for t in THRESHOLDS:
        s[f"edge_{t}plus"] = (lambda t=t: [x for x in b if x["edge"] >= t])
    out = {k: record(f()) for k, f in s.items()}
    # data-quality checks: are the big edges real disagreements or bad lines?
    clean = [x for x in b if not x["flip_suspect"]]
    out["top1_per_night_no_flip_suspects"] = record(top_n_per_night(clean, 1))
    for t in (7, 10):
        big = [x for x in b if x["edge"] >= t]
        out[f"edge_{t}plus_no_flip_suspects"] = record([x for x in big if not x["flip_suspect"]])
        out[f"edge_{t}plus_flip_suspects"] = record([x for x in big if x["flip_suspect"]])
        out[f"edge_{t}plus_by_book"] = {bk: record([x for x in big if x["book"] == bk])
                                        for bk in sorted({x["book"] for x in big})}
        if big:
            out[f"edge_{t}plus_mae"] = {"line": round(sum(x["line_err"] for x in big) / len(big), 2),
                                        "model": round(sum(x["model_err"] for x in big) / len(big), 2)}
    out["books_all_games"] = {bk: sum(x["book"] == bk for x in b) for bk in sorted({x["book"] for x in b})}
    return out


def run(proj_by_season: dict[int, list[dict[str, Any]]], source: str) -> dict[str, Any]:
    per = {}
    pooled: list[dict[str, Any]] = []
    picks = {}
    for season, proj in proj_by_season.items():
        b = bets(proj)
        pooled.extend(b)
        per[season] = strategies(b)
        picks[season] = top_n_per_night(b, 1)
        print(season, json.dumps(per[season]["top1_per_night"]), flush=True)
    # top-N selection is per night, so pooling across seasons is just concatenation
    return {"source": source, "breakeven": round(BREAKEVEN, 4), "by_season": per,
            "pooled": strategies(pooled), "top1_picks": picks}


def _espn(seasons: list[int]) -> dict[int, list[dict[str, Any]]]:
    from . import backtest as B
    from . import ncaa
    d1 = set(ncaa.load_d1_teams())
    p = R.Params()
    out = {}
    for s in seasons:
        prior = B.season_end_prior(s - 1, d1, p)
        rows, _ = B.season_rows(s, d1)
        out[s] = R.walk_forward(rows, p, prior)
    return out


def _cbbd(seasons: list[int]) -> dict[int, list[dict[str, Any]]]:
    from . import cbbd_study as C
    p = R.Params()
    out = {}
    for s in seasons:
        prev, _ = C.season_rows(s - 1)
        rows, _ = C.season_rows(s)
        if not prev or not rows:
            continue
        end = max(r["date"] for r in prev)
        out[s] = R.walk_forward(rows, p, R.fit(prev, end.replace(hour=23, minute=59), p))
    return out


def main(source: str, lo: int, hi: int, write: bool = True) -> dict[str, Any]:
    seasons = list(range(lo, hi + 1))
    proj = _espn(seasons) if source == "espn" else _cbbd(seasons)
    res = run(proj, source)
    res["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res["params"] = R.Params().__dict__
    if write:
        path = OUT.with_name(f"edge_study_{source}.json")
        if source == "cbbd":  # CBBD terms: summary numbers only, no per-game rows
            res.pop("top1_picks")
            res["attribution"] = "Data provided by CollegeBasketballData.com"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(res, indent=1, default=str))
        print("saved:", path)
    return res


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
