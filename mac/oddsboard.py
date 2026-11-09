"""Per-book odds screen for MAC games, built from the line snapshots in data/lines.

Everything is computed from rows the collector already saved, so the odds page costs
no extra Odds API requests. For each game it works out, per book:

- the current number and price on both sides of the spread, total and moneyline,
- the number that book opened at (the first snapshot we saw it in) and its move since,
- that book's hold (vig) on each market,
- whether the book is off the market (its number away from the median of US books),

and across books: the best available price on every side, the median ("sharp number"
for now, since the US region has no Pinnacle), the no-vig fair win probability, which
book posted first, and the consensus path over time for the movement chart.

When data/model/projections.jsonl exists, each game also gets the model's spread and
total with the gap to the median and to the best number on the board.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

from .analysis import parse_iso
from .config import DATA_DIR, SHARED_DIR

MODEL_PATH = DATA_DIR / "model" / "projections.jsonl"
RUNS_PATH = SHARED_DIR / "odds_runs.jsonl"
# Monthly request allowance on the Odds API plan. Set to the plan's number when it changes.
MONTHLY_REQUESTS = 20000
# The collector snapshots every 30 minutes: 48 runs a day.
RUNS_PER_DAY = 48

BOOK_NAMES = {
    "draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM", "williamhill_us": "Caesars",
    "betrivers": "BetRivers", "espnbet": "theScore Bet", "fanatics": "Fanatics", "hardrockbet": "Hard Rock",
    "ballybet": "Bally Bet", "betparx": "betPARX", "fliff": "Fliff", "bovada": "Bovada",
    "betonlineag": "BetOnline", "novig": "Novig", "prophetx": "ProphetX", "kalshi": "Kalshi", "polymarket": "Polymarket", "lowvig": "LowVig", "betus": "BetUS", "mybookieag": "MyBookie",
    "pinnacle": "Pinnacle", "unibet_us": "Unibet", "superbook": "SuperBook", "wynnbet": "WynnBET",
    "betanysports": "BetAnySports", "rebet": "ReBet", "windcreek": "Wind Creek",
}

# A book this far from the median is flagged as off-market: worth a look either way.
OFF_MARKET = {"spread": 1.0, "total": 1.5}


# A quote is left out of "best available" and the market number when it can't be a real
# pre-game bet: juice past these limits on a spread or total (an exchange's stale or
# in-play leftovers, e.g. -1.5 at -1150 when every book has -12.5 at -110), a number too
# far from the other books, or a moneyline far from the other books' win probability.
SANE_PRICE = (-250, 250)
SANE_POINTS = {"spread": 3.0, "total": 5.0}
SANE_ML_PROB = 0.12


# ---------------------------------------------------------------- price math


def decimal_odds(american: float | None) -> float | None:
    if american is None:
        return None
    return 1 + american / 100 if american > 0 else 1 + 100 / -american


def implied_prob(american: float | None) -> float | None:
    d = decimal_odds(american)
    return 1 / d if d else None


def prob_to_american(p: float) -> int:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def hold(a: float | None, b: float | None) -> float | None:
    """Book's margin on a two-way market, e.g. 0.045 for -110/-110."""
    pa, pb = implied_prob(a), implied_prob(b)
    if pa is None or pb is None:
        return None
    return round(pa + pb - 1, 4)


def book_name(key: str) -> str:
    return BOOK_NAMES.get(key, key.replace("_", " ").title())


# ---------------------------------------------------------------- per-book lines


SIDES = ("away_spread", "home_spread", "over", "under", "away_ml", "home_ml")


def book_quotes(rows: list[dict[str, Any]], home: str, away: str) -> dict[str, dict[str, Any]]:
    """{book: {side: {"point", "price"}, "updated": iso}} for one game at one capture time."""
    out: dict[str, dict[str, Any]] = defaultdict(dict)
    for r in rows:
        b = out[r["book"]]
        if r.get("book_last_update"):
            b["updated"] = max(b.get("updated", ""), r["book_last_update"])
        side = None
        if r["market"] == "spreads":
            side = "home_spread" if r["outcome"] == home else ("away_spread" if r["outcome"] == away else None)
        elif r["market"] == "totals":
            side = {"Over": "over", "Under": "under"}.get(r["outcome"])
        elif r["market"] == "h2h":
            side = "home_ml" if r["outcome"] == home else ("away_ml" if r["outcome"] == away else None)
        if side is None or r.get("price") is None:
            continue
        if side in ("away_ml", "home_ml"):
            b[side] = {"point": None, "price": r["price"]}
        elif r.get("point") is not None:
            b[side] = {"point": r["point"], "price": r["price"]}
    return dict(out)


def _kind(side: str) -> str:
    return "spread" if side.endswith("spread") else ("ml" if side.endswith("ml") else "total")


def suspect_quotes(books: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    """{book: {side, ...}} for quotes that don't look like a real pre-game price."""
    out: dict[str, set[str]] = defaultdict(set)
    for side in SIDES:
        kind = _kind(side)
        offers = {k: b[side] for k, b in books.items() if side in b}
        if kind == "ml":
            probs = {k: implied_prob(q["price"]) for k, q in offers.items()}
            if len(probs) >= 3:
                mid = median(probs.values())
                for k, pr in probs.items():
                    if abs(pr - mid) > SANE_ML_PROB:
                        out[k].add(side)
            continue
        for k, q in offers.items():
            if not SANE_PRICE[0] <= q["price"] <= SANE_PRICE[1] or -100 < q["price"] < 100:
                out[k].add(side)
        pts = [q["point"] for k, q in offers.items() if side not in out[k]]
        if len(pts) >= 3:
            mid = median(pts)
            for k, q in offers.items():
                if abs(q["point"] - mid) > SANE_POINTS[kind]:
                    out[k].add(side)
    return {k: v for k, v in out.items() if v}


def drop_quotes(books: dict[str, dict[str, Any]], bad: dict[str, set[str]]) -> dict[str, dict[str, Any]]:
    clean = {k: {s: q for s, q in b.items() if s not in bad.get(k, ())} for k, b in books.items()}
    return {k: b for k, b in clean.items() if any(s in b for s in SIDES)}


def _better(side: str, q: dict[str, Any]) -> tuple:
    """Sort key: bigger is better for the bettor on that side."""
    price = decimal_odds(q["price"]) or 0
    if side in ("away_spread", "home_spread", "under"):
        return (q["point"], price)  # more points / higher under
    if side == "over":
        return (-q["point"], price)  # lower over
    return (price,)


def best_by_side(books: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """For each side, the best quote and every book offering it."""
    out = {}
    for side in SIDES:
        offers = [(k, b[side]) for k, b in books.items() if side in b]
        if not offers:
            continue
        top = max(_better(side, q) for _, q in offers)
        winners = sorted(k for k, q in offers if _better(side, q) == top)
        q = next(q for k, q in offers if k == winners[0])
        out[side] = {"point": q["point"], "price": q["price"], "books": winners}
    return out


SHARP_BOOK = "pinnacle"


def consensus(books: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The market number: Pinnacle when it is posted, otherwise the median across books.

    The median is always kept too (median_spread, median_total) and is what off-market
    flags are measured against. Moneyline median is taken in probability space; the fair
    win probability strips the vig (Pinnacle's own two prices when it is there).
    """
    def med(side: str) -> float | None:
        vals = [b[side]["point"] for b in books.values() if side in b]
        return round(median(vals) * 2) / 2 if vals else None

    def med_prob(side: str) -> float | None:
        vals = [implied_prob(b[side]["price"]) for b in books.values() if side in b]
        return median(vals) if vals else None

    ph, pa = med_prob("home_ml"), med_prob("away_ml")
    fair_home = ph / (ph + pa) if ph and pa else None
    holds = [h for h in (hold(b.get("home_spread", {}).get("price"), b.get("away_spread", {}).get("price")) for b in books.values()) if h is not None]
    m_spread, m_total = med("home_spread"), med("over")
    spread, total, source = m_spread, m_total, "median"
    sharp = books.get(SHARP_BOOK)
    if sharp:
        if "home_spread" in sharp:
            spread, source = sharp["home_spread"]["point"], SHARP_BOOK
        if "over" in sharp:
            total, source = sharp["over"]["point"], SHARP_BOOK
        sh, sa = implied_prob(sharp.get("home_ml", {}).get("price")), implied_prob(sharp.get("away_ml", {}).get("price"))
        if sh and sa:
            fair_home = sh / (sh + sa)
    return {
        "spread": spread,  # home view, negative = home favored
        "total": total,
        "source": source,
        "median_spread": m_spread,
        "median_total": m_total,
        "ml_home": prob_to_american(ph) if ph else None,
        "ml_away": prob_to_american(pa) if pa else None,
        "fair_home": round(fair_home, 3) if fair_home is not None else None,
        "fair_ml_home": prob_to_american(fair_home) if fair_home is not None else None,
        "fair_ml_away": prob_to_american(1 - fair_home) if fair_home is not None else None,
        "median_spread_hold": round(median(holds), 4) if holds else None,
        "books": len(books),
    }


# ---------------------------------------------------------------- one game


def _point_move(now: dict[str, Any] | None, then: dict[str, Any] | None) -> float | None:
    if not now or not then or now.get("point") is None or then.get("point") is None:
        return None
    return round(now["point"] - then["point"], 1)


def build_event(event_rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = event_rows[0]
    home, away = first["home_team"], first["away_team"]
    by_capture: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in event_rows:
        by_capture[r["captured_at"]].append(r)
    captures = sorted(by_capture)
    snaps = [(t, book_quotes(by_capture[t], home, away)) for t in captures]

    latest_t, latest = snaps[-1]
    opening: dict[str, dict[str, Any]] = {}
    first_seen: dict[str, str] = {}
    last_seen: dict[str, str] = {}
    for t, books in snaps:
        for k, b in books.items():
            first_seen.setdefault(k, t)
            last_seen[k] = t
            ob = opening.setdefault(k, {})
            for side in SIDES:
                if side in b and side not in ob:
                    ob[side] = b[side]

    suspect = suspect_quotes(latest)
    clean = drop_quotes(latest, suspect)
    cons = consensus(clean)
    best = best_by_side(clean)
    rows = []
    for k in sorted(latest, key=lambda k: book_name(k).lower()):
        b = latest[k]
        cells = {}
        for side in SIDES:
            q = b.get(side)
            if not q:
                continue
            cell = {**q, "best": k in best.get(side, {}).get("books", []), "suspect": side in suspect.get(k, ()),
                    "open": opening[k].get(side), "move": _point_move(q, opening[k].get(side))}
            if side in ("away_ml", "home_ml"):
                o = opening[k].get(side)
                cell["move"] = None if not o or o["price"] == q["price"] else q["price"] - o["price"]
            cells[side] = cell
        off = {}
        cb = clean.get(k, {})  # suspect quotes are flagged as stale, not as off the market
        if "home_spread" in cb and cons["median_spread"] is not None:
            off["spread"] = round(cb["home_spread"]["point"] - cons["median_spread"], 1)
        if "over" in cb and cons["median_total"] is not None:
            off["total"] = round(cb["over"]["point"] - cons["median_total"], 1)
        rows.append({
            "book": k, "name": book_name(k), "cells": cells,
            "hold": {
                "spread": hold(cb.get("home_spread", {}).get("price"), cb.get("away_spread", {}).get("price")),
                "total": hold(cb.get("over", {}).get("price"), cb.get("under", {}).get("price")),
                "ml": hold(cb.get("home_ml", {}).get("price"), cb.get("away_ml", {}).get("price")),
            },
            "suspect": sorted(suspect.get(k, ())),
            "off": off,
            "off_market": any(abs(v) >= OFF_MARKET[m] for m, v in off.items()),
            "first_seen": first_seen[k],
            "updated": b.get("updated"),
        })
    pulled = [{"book": k, "name": book_name(k), "last_seen": last_seen[k]} for k in sorted(first_seen) if k not in latest]

    # Consensus path, for the movement chart and open vs now.
    path = []
    for t, books in snaps:
        c = consensus(drop_quotes(books, suspect_quotes(books)))
        path.append({"t": t, "spread": c["spread"], "total": c["total"], "fair_home": c["fair_home"], "books": c["books"]})
    book_paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t, books in snaps:
        for k, b in books.items():
            book_paths[k].append({"t": t, "spread": b.get("home_spread", {}).get("point"), "total": b.get("over", {}).get("point")})

    open_c = next((p for p in path if p["spread"] is not None), path[0])
    open_t = next((p for p in path if p["total"] is not None), path[0])
    opener = min(first_seen.items(), key=lambda kv: (kv[1], kv[0]))
    tip = parse_iso(first["commence_time"])
    return {
        "odds_event_id": first["odds_event_id"],
        "commence_time": first["commence_time"],
        "home_team": home, "away_team": away,
        "home_key": first.get("home_key"), "away_key": first.get("away_key"),
        "captured_at": latest_t,
        "snapshots": len(snaps),
        "consensus": cons,
        "open": {"spread": open_c["spread"], "total": open_t["total"], "t": path[0]["t"]},
        "move": {
            "spread": round(cons["spread"] - open_c["spread"], 1) if cons["spread"] is not None and open_c["spread"] is not None else None,
            "total": round(cons["total"] - open_t["total"], 1) if cons["total"] is not None and open_t["total"] is not None else None,
        },
        "best": best,
        "rows": rows,
        "pulled": pulled,
        "path": path,
        "book_paths": dict(book_paths),
        "opener": {"book": opener[0], "name": book_name(opener[0]), "t": opener[1],
                   "lead_hours": round((tip - parse_iso(opener[1])).total_seconds() / 3600, 1)},
        "spread_range": _range(latest, "home_spread"),
        "total_range": _range(latest, "over"),
    }


def _range(books: dict[str, dict[str, Any]], side: str) -> list[float] | None:
    pts = [b[side]["point"] for b in books.values() if side in b]
    return [min(pts), max(pts)] if pts else None


def build_events(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_event[r["odds_event_id"]].append(r)
    return {eid: build_event(evr) for eid, evr in by_event.items()}


# ---------------------------------------------------------------- model


def load_projections(path: Path = MODEL_PATH) -> dict[str, dict[str, Any]]:
    """Latest projection per ESPN game id. Missing file means no model yet."""
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            gid = str(p.get("game_id") or "")
            if not gid:
                continue
            if gid not in out or str(p.get("generated_at", "")) >= str(out[gid].get("generated_at", "")):
                out[gid] = p
    return out


def model_edge(proj: dict[str, Any], ev: dict[str, Any]) -> dict[str, Any]:
    """Model vs market, in points, from the bettor's side of each gap.

    proj_margin is home points minus away points, so the model's home spread is
    -proj_margin. A model spread below the market spread means the model likes the
    home team more than the market does.
    """
    out: dict[str, Any] = {"model_version": proj.get("model_version"), "generated_at": proj.get("generated_at"),
                           # One side is non-D-I: the model's number is rough, so don't call it an edge.
                           "rough": bool(proj.get("non_d1"))}
    margin = proj.get("proj_margin")
    if margin is not None:
        model_spread = round(-float(margin), 1)
        out["spread"] = model_spread
        mkt = ev["consensus"]["spread"]
        if mkt is not None:
            gap = round(mkt - model_spread, 1)  # >0: model likes home more than market
            side = "home_spread" if gap > 0 else "away_spread"
            out["spread_gap"] = abs(gap)
            out["spread_side"] = "home" if gap > 0 else ("away" if gap < 0 else None)
            best = ev["best"].get(side)
            if best and gap != 0:
                # Edge at the best number: points of daylight between model and that line.
                model_side = model_spread if side == "home_spread" else -model_spread
                out["spread_best"] = {**best, "edge": round(best["point"] - model_side, 1)}
    total = proj.get("proj_total")
    if total is not None:
        out["total"] = round(float(total), 1)
        mkt = ev["consensus"]["total"]
        if mkt is not None:
            gap = round(out["total"] - mkt, 1)  # >0: model says over
            out["total_gap"] = abs(gap)
            out["total_side"] = "over" if gap > 0 else ("under" if gap < 0 else None)
            side = "over" if gap > 0 else "under"
            best = ev["best"].get(side)
            if best and gap != 0:
                edge = out["total"] - best["point"] if side == "over" else best["point"] - out["total"]
                out["total_best"] = {**best, "edge": round(edge, 1)}
    if proj.get("win_prob_home") is not None:
        out["win_prob_home"] = round(float(proj["win_prob_home"]), 3)
        fair = ev["consensus"]["fair_home"]
        if fair is not None:
            out["win_prob_gap"] = round(out["win_prob_home"] - fair, 3)
    return out


# ---------------------------------------------------------------- API budget


def record_run(summary: dict[str, Any], path: Path = RUNS_PATH) -> None:
    """Append one line per collector run: when, how many MAC games, quota left."""
    q = summary.get("quota") or {}
    row = {
        "captured_at": summary["captured_at"],
        "mac_events": summary.get("mac_events"),
        "rows": summary.get("rows"),
        "requests_used": _int(q.get("requests_used")),
        "requests_remaining": _int(q.get("requests_remaining")),
        "requests_last": _int(q.get("requests_last")),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def _int(v: Any) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def budget(now: datetime, line_rows: list[dict[str, Any]], path: Path = RUNS_PATH, runs_per_day: int = RUNS_PER_DAY, cost_per_run: int = 3) -> dict[str, Any]:
    """Quota picture. Uses the API's own counters when we have them, else counts snapshots."""
    runs = []
    if path.exists():
        runs = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    month = now.strftime("%Y-%m")
    captures = sorted({r["captured_at"] for r in line_rows})
    month_captures = [c for c in captures if c[:7] == month]
    latest = runs[-1] if runs else None
    days_in_month = ((now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
    days_left = days_in_month - now.day + 1
    used = latest["requests_used"] if latest and latest.get("requests_used") is not None and latest["captured_at"][:7] == month else None
    remaining = latest["requests_remaining"] if latest and latest.get("requests_remaining") is not None and latest["captured_at"][:7] == month else None
    est_used = used if used is not None else len(month_captures) * cost_per_run
    projected = est_used + days_left * runs_per_day * cost_per_run
    return {
        "month": month,
        "used": used,
        "remaining": remaining,
        "estimated_used": est_used,
        "snapshots_this_month": len(month_captures),
        "projected_month_end": projected,
        "limit": MONTHLY_REQUESTS,
        "headroom": MONTHLY_REQUESTS - projected,
        "from_api": used is not None,
        "last_run": latest["captured_at"] if latest else (captures[-1] if captures else None),
    }


# ---------------------------------------------------------------- charts


def sparkline(points: list[tuple[str, float]], width: int = 220, height: int = 46, pad: int = 4) -> dict[str, Any] | None:
    """Pre-computed SVG path for a small step chart of one series."""
    pts = [(parse_iso(t).timestamp(), v) for t, v in points if v is not None]
    if not pts:
        return None
    x0, x1 = pts[0][0], pts[-1][0]
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    if hi - lo < 1:
        lo, hi = lo - 0.5, hi + 0.5

    def X(t: float) -> float:
        return pad + (0.5 if x1 == x0 else (t - x0) / (x1 - x0)) * (width - 2 * pad)

    def Y(v: float) -> float:
        return pad + (1 - (v - lo) / (hi - lo)) * (height - 2 * pad)

    d = f"M{X(pts[0][0]):.1f},{Y(pts[0][1]):.1f}"
    for (t, v), (_, pv) in zip(pts[1:], pts[:-1]):
        d += f" L{X(t):.1f},{Y(pv):.1f} L{X(t):.1f},{Y(v):.1f}"
    if len(pts) == 1:
        d += f" L{width - pad:.1f},{Y(pts[0][1]):.1f}"
    return {"d": d, "w": width, "h": height, "lo": lo, "hi": hi,
            "dots": [{"x": round(X(t), 1), "y": round(Y(v), 1), "v": v} for t, v in pts],
            "first": pts[0][1], "last": pts[-1][1]}


# ---------------------------------------------------------------- book scorecard


def book_scorecard(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Across every game we have: how often each book was best, its hold, first to post, distance from median."""
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"games": 0, "best": 0, "quotes": 0, "holds": [], "first": 0, "dist": []})
    for ev in events:
        openers = {ev["opener"]["book"]}
        for r in ev["rows"]:
            s = stats[r["book"]]
            s["games"] += 1
            for side, c in r["cells"].items():
                s["quotes"] += 1
                s["best"] += 1 if c["best"] else 0
            if r["hold"]["spread"] is not None:
                s["holds"].append(r["hold"]["spread"])
            if "spread" in r["off"]:
                s["dist"].append(abs(r["off"]["spread"]))
            if r["book"] in openers:
                s["first"] += 1
    out = []
    for k, s in stats.items():
        out.append({
            "book": k, "name": book_name(k), "games": s["games"],
            "best_pct": round(100 * s["best"] / s["quotes"]) if s["quotes"] else None,
            "hold": round(100 * median(s["holds"]), 1) if s["holds"] else None,
            "first": s["first"],
            "avg_off": round(sum(s["dist"]) / len(s["dist"]), 2) if s["dist"] else None,
        })
    out.sort(key=lambda r: (-(r["best_pct"] or 0), r["hold"] or 99))
    return out


# ---------------------------------------------------------------- page


# The day's featured number: the single biggest gap between the model and the best price
# on the board, spread or total, among games tipping in the next 30 hours.
BEST_PLAY_MIN_EDGE = 1.5
BEST_PLAY_WINDOW_H = 30


def best_play(board: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    cands = []
    for ev in board:
        m = ev.get("model")
        if not m or m.get("rough"):
            continue
        hours = (parse_iso(ev["commence_time"]) - now).total_seconds() / 3600
        if not 0 < hours <= BEST_PLAY_WINDOW_H:
            continue
        for kind in ("spread", "total"):
            b = m.get(f"{kind}_best")
            if b and b["edge"] >= BEST_PLAY_MIN_EDGE:
                cands.append((b["edge"], kind, ev, m, b))
    if not cands:
        return None
    edge, kind, ev, m, b = max(cands, key=lambda c: (c[0], c[1] == "spread"))
    away, home = ev.get("away") or {}, ev.get("home") or {}
    if kind == "spread":
        team = home if m["spread_side"] == "home" else away
        pick = f"{team.get('abbr') or team.get('name')} {'+' if b['point'] > 0 else ''}{b['point']:g}"
        model = m["spread"] if m["spread_side"] == "home" else -m["spread"]
    else:
        pick = f"{'Over' if m['total_side'] == 'over' else 'Under'} {b['point']:g}"
        model = m["total"]
    return {"odds_event_id": ev["odds_event_id"], "commence_time": ev["commence_time"],
            "matchup": f"{away.get('abbr') or away.get('name')} at {home.get('abbr') or home.get('name')}",
            "kind": kind, "pick": pick, "price": b["price"], "books": [book_name(k) for k in b["books"]],
            "model": model, "edge": edge}


def page_context(now: datetime, games: list[dict[str, Any]], rows: list[dict[str, Any]],
                 mapping: dict[str, str], projections: dict[str, dict[str, Any]] | None = None,
                 decorate=lambda g: g) -> dict[str, Any]:
    """Everything odds.html needs. `mapping` is ESPN game id -> odds event id."""
    projections = projections or {}
    events = build_events(rows)
    ev_to_game = {eid: gid for gid, eid in mapping.items()}
    by_gid = {g["game_id"]: g for g in games}

    board, closed = [], []
    for eid, ev in events.items():
        g = by_gid.get(ev_to_game.get(eid, ""))
        ev["game"] = decorate(dict(g)) if g else None
        for side in ("home", "away"):
            name = ev[f"{side}_team"]
            ev[side] = {
                "name": g[side]["name"] if g else name,
                "abbr": g[side]["abbr"] if g else name.split(" ")[0][:4].upper(),
                "espn_id": g[side]["espn_id"] if g else None,
                "key": ev[f"{side}_key"],
            }
        proj = projections.get(g["game_id"]) if g else None
        ev["model"] = model_edge(proj, ev) if proj else None
        ev["spark"] = {
            "spread": sparkline([(p["t"], p["spread"]) for p in ev["path"]]),
            "total": sparkline([(p["t"], p["total"]) for p in ev["path"]]),
        }
        tip = parse_iso(ev["commence_time"])
        if g and g.get("completed") or tip < now - timedelta(hours=3):
            if g and g.get("completed") and g["home"]["score"] is not None:
                margin = g["home"]["score"] - g["away"]["score"]
                pts = g["home"]["score"] + g["away"]["score"]
                sp, tot = ev["consensus"]["spread"], ev["consensus"]["total"]
                ev["result"] = {
                    "margin": margin, "points": pts,
                    "ats": None if sp is None else ("push" if margin + sp == 0 else ("home" if margin + sp > 0 else "away")),
                    "ou": None if tot is None else ("push" if pts == tot else ("over" if pts > tot else "under")),
                    # Did the move from open to close go the way the game went?
                    "move_right": None if not ev["move"]["spread"] else (ev["move"]["spread"] < 0) == (margin + (ev["open"]["spread"] or 0) > 0),
                }
            closed.append(ev)
        else:
            board.append(ev)
    board.sort(key=lambda e: e["commence_time"])
    closed.sort(key=lambda e: e["commence_time"], reverse=True)

    # MAC games coming up that no US book has posted yet.
    on_board = {ev_to_game.get(e["odds_event_id"]) for e in board}
    waiting = []
    for g in games:
        tip = parse_iso(g["date"])
        if g["completed"] or tip < now or tip > now + timedelta(days=8) or g["game_id"] in on_board:
            continue
        waiting.append({**decorate(dict(g)), "hours_out": round((tip - now).total_seconds() / 3600)})
    waiting.sort(key=lambda g: g["date"])

    books = sorted({r["book"] for ev in board for r in ev["rows"]}, key=lambda k: book_name(k).lower())
    leads = [ev["opener"]["lead_hours"] for ev in events.values()]
    play = best_play(board, now)
    edges = [ev for ev in board if ev["model"] and not ev["model"]["rough"]
             and max(ev["model"].get("spread_gap") or 0, ev["model"].get("total_gap") or 0) >= 1.5]
    return {
        "board": board,
        "closed": closed[:30],
        "waiting": waiting,
        "books": [{"key": k, "name": book_name(k)} for k in books],
        "scorecard": book_scorecard(list(events.values())),
        "has_model": bool(projections),
        "edges": len(edges),
        "best_play": play,
        "median_lead": round(median(leads), 1) if leads else None,
        "last_capture": max((ev["captured_at"] for ev in events.values()), default=None),
    }
