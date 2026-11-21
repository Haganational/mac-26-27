"""Three models against the number, for Data Visualized.

Same ratings engine, same preseason prior, same home edge and opening-fortnight bump.
Only the way past games are weighted changes:

- Our line (v1.1): each game's weight halves every 90 days. This is the site's model.
- The Long Game: every game this season counts the same. No recency at all.
- Right Now: each team's last four games count heavily, newest heaviest
  (12, 9, 7, 5), and every older game counts 1.

Each one is walked forward a day at a time (refit every morning on earlier games only)
and scored against the DraftKings spread and total ESPN carried at tip. The live slate
puts each model's number next to the latest Odds API line.

    python -m mac.three_models          # refresh data/model/three_models.json
    python -m mac.three_models --full   # recompute last season too
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Iterable

from . import backtest, ncaa
from . import ratings as R
from .config import SEASON, SHARED_DIR

DIR = SHARED_DIR / "model"
BASE = R.Params()
RIGHT_NOW_WEIGHTS = (12.0, 9.0, 7.0, 5.0)
MODELS = [
    {"key": "ours", "name": "Our line", "color": 1,
     "blurb": "The site's model (v1.1). A game's weight halves every 90 days, so recent form counts a bit more."},
    {"key": "long", "name": "The Long Game", "color": 2,
     "blurb": "Every game counts the same, November or March. No recency weight."},
    {"key": "now", "name": "Right Now", "color": 3,
     "blurb": "Each team's last four games weigh 12, 9, 7 and 5 (newest first). Every older game weighs 1."},
]
PARAMS = {
    "ours": BASE,
    "long": replace(BASE, half_life=1e9, min_weight=1.0),
    "now": replace(BASE, rank_weights=RIGHT_NOW_WEIGHTS),
}
WIN, LOSS = 1.0, -1.1  # units at -110
EDGE = 3.0


def _r1(v: float | None) -> float | None:
    return None if v is None else round(v, 1)


# ---------------------------------------------------------------- backtest


def backtest_season(season: int, d1: set[str]) -> list[dict[str, Any]]:
    """One compact row per lined game: the close, the result and each model's walk-forward number."""
    prior = backtest.season_end_prior(season - 1, d1, BASE)
    rows, _ = backtest.season_rows(season, d1)
    by_model = {k: {g["id"]: g["proj"] for g in R.walk_forward(rows, p, prior)} for k, p in PARAMS.items()}
    out = []
    for g in sorted(rows, key=lambda r: r["date"]):
        line = g.get("line") or {}
        if line.get("home_spread") is None and line.get("total") is None:
            continue
        if any(g["id"] not in by_model[k] for k in PARAMS):
            continue
        out.append({
            "id": g["id"], "d": g["date"].date().isoformat(), "h": g["home"], "a": g["away"],
            "ph": g["pts_h"], "pa": g["pts_a"], "sp": line.get("home_spread"), "tot": line.get("total"),
            "m": {k: [_r1(by_model[k][g["id"]]["spread"]), _r1(by_model[k][g["id"]]["total"])] for k in PARAMS},
        })
    return out


def _latest_final(season: int) -> str | None:
    games = ncaa.load_season(season)["games"]
    done = [g["date"] for g in games if g["home"].get("pts") is not None]
    return max(done) if done else None


def _path(season: int):
    return DIR / f"three_models-{season}.json"


# Stored compact, one list per game, to keep the committed file small.
FIELDS = ("id", "d", "h", "a", "ph", "pa", "sp", "tot")


def _pack(g: dict[str, Any]) -> list[Any]:
    return [g[f] for f in FIELDS] + [v for k in PARAMS for v in g["m"][k]]


def _unpack(row: list[Any]) -> dict[str, Any]:
    g = dict(zip(FIELDS, row))
    rest = row[len(FIELDS):]
    g["m"] = {k: rest[2 * i:2 * i + 2] for i, k in enumerate(PARAMS)}
    return g


def refresh(full: bool = False) -> None:
    """Recompute this season when new finals have landed; last season once (or with full=True)."""
    d1: set[str] | None = None
    for season in (SEASON - 1, SEASON):
        path = _path(season)
        old = json.loads(path.read_text()) if path.exists() else {}
        through = _latest_final(season)
        stamp = {"through": through, "weights": list(RIGHT_NOW_WEIGHTS), "models": list(PARAMS)}
        if not full and all(old.get(k) == v for k, v in stamp.items()):
            continue
        d1 = d1 or set(ncaa.load_d1_teams())
        games = backtest_season(season, d1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**stamp, "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "fields": list(FIELDS) + [f"{k}_{x}" for k in PARAMS for x in ("spread", "total")],
                                    "games": [_pack(g) for g in games]}, separators=(",", ":")))


def load() -> dict[str, Any] | None:
    seasons = {}
    updated = None
    for season in (SEASON - 1, SEASON):
        path = _path(season)
        if path.exists():
            raw = json.loads(path.read_text())
            seasons[str(season)] = {"games": [_unpack(r) for r in raw["games"]]}
            updated = max(updated or "", raw.get("updated") or "") or None
    return {"seasons": seasons, "updated": updated} if seasons else None


# ---------------------------------------------------------------- scoring


def _grade_side(g: dict[str, Any], k: str) -> str | None:
    """W/L/P for the model's side against the close, None when no line or no lean."""
    if g["sp"] is None:
        return None
    gap = g["m"][k][0] - g["sp"]  # negative: the model likes the home side more than the book
    if gap == 0:
        return None
    cover = (g["ph"] - g["pa"]) + g["sp"]
    if cover == 0:
        return "P"
    return "W" if (cover > 0) == (gap < 0) else "L"


def _grade_total(g: dict[str, Any], k: str) -> str | None:
    if g["tot"] is None:
        return None
    gap = g["m"][k][1] - g["tot"]
    if gap == 0:
        return None
    pts = g["ph"] + g["pa"]
    if pts == g["tot"]:
        return "P"
    return "W" if (pts > g["tot"]) == (gap > 0) else "L"


def _rec(grades: Iterable[str | None]) -> dict[str, Any]:
    w = l = p = 0
    for x in grades:
        if x == "W":
            w += 1
        elif x == "L":
            l += 1
        elif x == "P":
            p += 1
    n = w + l
    units = w * WIN + l * LOSS
    return {"w": w, "l": l, "p": p, "pct": round(100 * w / n, 1) if n else None,
            "units": round(units, 1), "roi": round(100 * units / (1.1 * n), 1) if n else None}


def _mae(vals: list[float]) -> float | None:
    return round(sum(vals) / len(vals), 2) if vals else None


def score(games: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"n": len(games), "models": {}}
    sp = [g for g in games if g["sp"] is not None]
    tot = [g for g in games if g["tot"] is not None]
    out["book_mae"] = _mae([abs(-g["sp"] - (g["ph"] - g["pa"])) for g in sp])
    out["book_total_mae"] = _mae([abs(g["tot"] - (g["ph"] + g["pa"])) for g in tot])
    for m in MODELS:
        k = m["key"]
        big_sp = [g for g in sp if abs(g["m"][k][0] - g["sp"]) >= EDGE]
        big_tot = [g for g in tot if abs(g["m"][k][1] - g["tot"]) >= EDGE]
        out["models"][k] = {
            "ats": _rec(_grade_side(g, k) for g in sp),
            "ou": _rec(_grade_total(g, k) for g in tot),
            "ats3": _rec(_grade_side(g, k) for g in big_sp),
            "ou3": _rec(_grade_total(g, k) for g in big_tot),
            "mae": _mae([abs(-g["m"][k][0] - (g["ph"] - g["pa"])) for g in sp]),
            "total_mae": _mae([abs(g["m"][k][1] - (g["ph"] + g["pa"])) for g in tot]),
            "gap": _mae([abs(g["m"][k][0] - g["sp"]) for g in sp]),
        }
    # When all three take the same side of the spread.
    agree = [g for g in sp if len({_grade_side(g, m["key"]) for m in MODELS}) == 1]
    out["agree_ats"] = _rec(_grade_side(g, "ours") for g in agree)
    agree_t = [g for g in tot if len({_grade_total(g, m["key"]) for m in MODELS}) == 1]
    out["agree_ou"] = _rec(_grade_total(g, "ours") for g in agree_t)
    return out


# ---------------------------------------------------------------- the chart

W, H, PAD_L, PAD_R, PAD_T, PAD_B = 860, 300, 44, 140, 14, 28


def units_chart(games: list[dict[str, Any]], kind: str = "ats") -> dict[str, Any] | None:
    """Running units at -110 for each model, one point per day, ATS or O/U."""
    grade = _grade_side if kind == "ats" else _grade_total
    days = sorted({g["d"] for g in games})
    if len(days) < 2:
        return None
    by_day: dict[str, list[dict[str, Any]]] = {}
    for g in games:
        by_day.setdefault(g["d"], []).append(g)
    series = {}
    for m in MODELS:
        run, pts = 0.0, []
        for d in days:
            for g in by_day[d]:
                x = grade(g, m["key"])
                run += WIN if x == "W" else LOSS if x == "L" else 0.0
            pts.append(round(run, 1))
        series[m["key"]] = pts
    lo = min(min(v) for v in series.values())
    hi = max(max(v) for v in series.values())
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    step = next(s for s in (2, 5, 10, 20, 25, 50, 100, 200, 250, 500) if (hi - lo) / s <= 5)
    lo_t, hi_t = step * (lo // step), step * -(-hi // step)
    if hi_t == lo_t:
        hi_t = lo_t + step
    x = lambda i: round(PAD_L + (W - PAD_L - PAD_R) * i / (len(days) - 1), 1)  # noqa: E731
    y = lambda v: round(PAD_T + (H - PAD_T - PAD_B) * (hi_t - v) / (hi_t - lo_t), 1)  # noqa: E731
    lines = []
    ends = []
    for m in MODELS:
        pts = series[m["key"]]
        d = "M" + " L".join(f"{x(i)} {y(v)}" for i, v in enumerate(pts))
        lines.append({"key": m["key"], "name": m["name"], "color": m["color"], "d": d})
        ends.append({"key": m["key"], "name": m["name"], "v": pts[-1], "y": y(pts[-1])})
    # Keep end labels from colliding: spread them at least 14px apart.
    ends.sort(key=lambda e: e["y"])
    for i in range(1, len(ends)):
        if ends[i]["y"] - ends[i - 1]["y"] < 14:
            ends[i]["y"] = round(ends[i - 1]["y"] + 14, 1)
    yticks = []
    v = lo_t
    while v <= hi_t + 1e-9:
        yticks.append({"y": y(v), "t": f"{v:+g}" if v else "0", "zero": v == 0})
        v += step
    months, seen = [], set()
    for i, d in enumerate(days):
        mo = datetime.fromisoformat(d).strftime("%b")
        if mo not in seen:
            seen.add(mo)
            months.append({"x": x(i), "t": mo})
    pts_js = [{"d": datetime.fromisoformat(d).strftime("%b %-d"), "x": x(i),
               "v": {k: series[k][i] for k in series}} for i, d in enumerate(days)]
    return {"w": W, "h": H, "x0": PAD_L, "x1": W - PAD_R, "y0": PAD_T, "y1": H - PAD_B,
            "lines": lines, "ends": ends, "yticks": yticks, "months": months, "points": pts_js, "kind": kind}


# ---------------------------------------------------------------- the live slate


def slate(now: datetime, games: list[dict[str, Any]], days: int = 3) -> list[dict[str, Any]]:
    """Each model's spread and total for the next few days of this edition's games, next to the line."""
    from . import model

    names = ncaa.load_d1_teams()
    d1 = set(names)
    prior = backtest.season_end_prior(SEASON - 1, d1, BASE)
    rows, _ = backtest.season_rows(SEASON, d1)
    start = min((x["date"] for x in rows), default=None)
    merged: dict[str, dict[str, Any]] = {}
    for k, p in PARAMS.items():
        r = R.fit(rows, now, p, prior)
        for u in model.project_upcoming(r, games, now, days=days, p=p, season_start=start):
            row = merged.setdefault(u["game_id"], {
                "game_id": u["game_id"], "date": u["date"], "home": u["home"]["short"] if "short" in u["home"] else u["home"].get("name"),
                "away": u["away"]["short"] if "short" in u["away"] else u["away"].get("name"),
                "home_abbr": u["home"].get("abbr"), "away_abbr": u["away"].get("abbr"),
                "spread": (u["market"] or {}).get("spread"), "total": (u["market"] or {}).get("total"), "m": {}})
            row["m"][k] = {"spread": u["model"]["spread"], "total": u["model"]["total"],
                           "side": u["spread_edge"], "ou": u["total_edge"]}
    out = sorted(merged.values(), key=lambda r: r["date"])
    for r in out:
        sides = {(r["m"][k]["side"] or {}).get("abbr") for k in r["m"]}
        ous = {((r["m"][k]["ou"] or {}).get("take") or "").split(" ")[0] for k in r["m"]}
        r["split_side"] = len(sides) > 1
        r["split_ou"] = len(ous) > 1
    return out


def _team_ids_ok(g: dict[str, Any], ids: set[str] | None) -> bool:
    return ids is None or g["h"] in ids or g["a"] in ids


def page_context(now: datetime, games: list[dict[str, Any]], team_ids: set[str] | None,
                 league_label: str) -> dict[str, Any] | None:
    data = load()
    if not data:
        return None
    cards = []
    for season in sorted(data["seasons"], reverse=True):
        allg = data["seasons"][season]["games"]
        mine = [g for g in allg if _team_ids_ok(g, team_ids)]
        cards.append({"season": int(season), "label": f"{int(season) - 1}-{season[2:]}",
                      "current": int(season) == SEASON, "d1": score(allg), "lg": score(mine) if team_ids else None})
    cur = data["seasons"].get(str(SEASON), {}).get("games", [])
    prev = data["seasons"].get(str(SEASON - 1), {}).get("games", [])
    try:
        live = slate(now, games)
    except Exception as exc:  # noqa: BLE001 - the page must still publish
        print(f"three models slate: skipped ({exc!r})")
        live = []
    return {
        "models": MODELS, "cards": cards, "league": league_label, "edge": EDGE,
        "chart_cur": units_chart(cur, "ats"), "chart_cur_ou": units_chart(cur, "ou"),
        "chart_prev": units_chart(prev, "ats"), "chart_prev_ou": units_chart(prev, "ou"),
        "slate": live, "updated": data.get("updated"),
    }


if __name__ == "__main__":
    refresh(full="--full" in sys.argv)
    for s, v in sorted((load() or {"seasons": {}})["seasons"].items()):
        sc = score(v["games"])
        print(s, sc["n"], "games; book MAE", sc["book_mae"])
        for m in MODELS:
            x = sc["models"][m["key"]]
            print(f"  {m['name']:14} ATS {x['ats']['w']}-{x['ats']['l']} ({x['ats']['pct']}%) {x['ats']['units']:+}u "
                  f"| O/U {x['ou']['w']}-{x['ou']['l']} ({x['ou']['pct']}%) | 3+ ATS {x['ats3']['w']}-{x['ats3']['l']} "
                  f"| 3+ O/U {x['ou3']['w']}-{x['ou3']['l']} | MAE {x['mae']} total MAE {x['total_mae']}")
        print("  all three agree ATS", sc["agree_ats"], "O/U", sc["agree_ou"])
