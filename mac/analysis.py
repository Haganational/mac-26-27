"""Turn raw schedule and line snapshots into the shapes the dashboard needs.

Everything here is pure Python over the JSON files in data/, so it runs the same
in GitHub Actions, locally, and in tests. A SQLite export is in db.py for ad hoc
queries.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

from .config import TEAMS, team_key_for_odds_name

SHARP_BOOK = "pinnacle"  # preferred reference book when present
STALE_SNAPSHOT_GAP = timedelta(minutes=5)  # rows within this window belong to one snapshot


def parse_iso(value: str) -> datetime:
    """Parse ESPN ('2026-11-11T00:00Z') and Odds API ('2026-11-11T00:00:00Z') timestamps."""
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------- standings


def standings(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rec: dict[str, dict[str, Any]] = {
        t.key: {"key": t.key, "team": t.short, "abbr": t.abbr, "w": 0, "l": 0, "cw": 0, "cl": 0,
                "pf": 0, "pa": 0, "games": 0, "streak": []}
        for t in TEAMS
    }
    for g in sorted(games, key=lambda g: g["date"]):
        if not g["completed"] or g["home"]["score"] is None or g["away"]["score"] is None:
            continue
        for side, other in (("home", "away"), ("away", "home")):
            key = g[side]["key"]
            if key is None:
                continue
            r = rec[key]
            won = g[side]["score"] > g[other]["score"]
            r["games"] += 1
            r["pf"] += g[side]["score"]
            r["pa"] += g[other]["score"]
            r["w" if won else "l"] += 1
            if g["conference_game"]:
                r["cw" if won else "cl"] += 1
            r["streak"].append("W" if won else "L")
    out = []
    for r in rec.values():
        streak = r.pop("streak")
        run = 0
        for s in reversed(streak):
            if not streak or s != streak[-1]:
                break
            run += 1
        r["streak"] = f"{streak[-1]}{run}" if streak else "-"
        r["margin"] = round((r["pf"] - r["pa"]) / r["games"], 1) if r["games"] else 0.0
        out.append(r)
    out.sort(key=lambda r: (-(r["cw"] - r["cl"]), -(r["w"] - r["l"]), -r["margin"]))
    return out


# ---------------------------------------------------------------- lines


def _consensus(values: list[float]) -> float | None:
    return round(median(values), 1) if values else None


def summarize_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse the rows of one game at one capture time into spread/total/moneyline.

    Spread and total are the sharp book's number when present, otherwise the median
    across books. Spread is always from the home team's perspective (negative = home
    favored).
    """
    home = rows[0]["home_team"]
    by_book: dict[str, dict[str, Any]] = defaultdict(dict)
    for r in rows:
        b = by_book[r["book"]]
        if r["market"] == "spreads" and r["outcome"] == home and r["point"] is not None:
            b["spread"] = r["point"]
            b["spread_price"] = r["price"]
        elif r["market"] == "totals" and r["outcome"] == "Over" and r["point"] is not None:
            b["total"] = r["point"]
            b["total_price"] = r["price"]
        elif r["market"] == "h2h":
            if r["outcome"] == home:
                b["ml_home"] = r["price"]
            else:
                b["ml_away"] = r["price"]

    def pick(field: str) -> float | None:
        if SHARP_BOOK in by_book and field in by_book[SHARP_BOOK]:
            return by_book[SHARP_BOOK][field]
        return _consensus([b[field] for b in by_book.values() if field in b])

    return {
        "captured_at": rows[0]["captured_at"],
        "spread": pick("spread"),
        "total": pick("total"),
        "ml_home": pick("ml_home"),
        "ml_away": pick("ml_away"),
        "books": len(by_book),
        "has_sharp": SHARP_BOOK in by_book,
        "by_book": by_book,
    }


def line_history(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group raw rows by odds event, then by capture time, and summarize each snapshot."""
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_event[r["odds_event_id"]].append(r)

    out: dict[str, dict[str, Any]] = {}
    for event_id, event_rows in by_event.items():
        by_capture: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in event_rows:
            by_capture[r["captured_at"]].append(r)
        snaps = [summarize_snapshot(by_capture[k]) for k in sorted(by_capture)]
        first = event_rows[0]
        out[event_id] = {
            "odds_event_id": event_id,
            "commence_time": first["commence_time"],
            "home_team": first["home_team"],
            "away_team": first["away_team"],
            "home_key": first.get("home_key") or team_key_for_odds_name(first["home_team"]),
            "away_key": first.get("away_key") or team_key_for_odds_name(first["away_team"]),
            "first_seen": snaps[0]["captured_at"],
            "latest": {k: v for k, v in snaps[-1].items() if k != "by_book"},
            "latest_by_book": snaps[-1]["by_book"],
            "snapshots": [{k: v for k, v in s.items() if k != "by_book"} for s in snaps],
            "open_spread": snaps[0]["spread"],
            "open_total": snaps[0]["total"],
            "spread_move": (round(snaps[-1]["spread"] - snaps[0]["spread"], 1)
                            if snaps[0]["spread"] is not None and snaps[-1]["spread"] is not None else None),
            "total_move": (round(snaps[-1]["total"] - snaps[0]["total"], 1)
                           if snaps[0]["total"] is not None and snaps[-1]["total"] is not None else None),
        }
    return out


# ---------------------------------------------------------------- joining


def match_lines_to_games(games: list[dict[str, Any]], history: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Map ESPN game_id -> odds event id by team keys and tip time within 36 hours."""
    mapping: dict[str, str] = {}
    for ev in history.values():
        if not ev["home_key"] and not ev["away_key"]:
            continue
        tip = parse_iso(ev["commence_time"])
        best: tuple[float, str] | None = None
        ev_keys = {k for k in (ev["home_key"], ev["away_key"]) if k}
        for g in games:
            keys = {k for k in (g["home"]["key"], g["away"]["key"]) if k}
            # Every MAC team named on the event must be in the game (and vice versa),
            # so a non-conference opponent's missing key can never match another game's.
            if ev_keys != keys:
                continue
            gap = abs((parse_iso(g["date"]) - tip).total_seconds())
            if gap <= 36 * 3600 and (best is None or gap < best[0]):
                best = (gap, g["game_id"])
        if best:
            mapping[best[1]] = ev["odds_event_id"]
    return mapping


def upcoming(games: list[dict[str, Any]], history: dict[str, dict[str, Any]], now: datetime, days: int = 8) -> list[dict[str, Any]]:
    mapping = match_lines_to_games(games, history)
    horizon = now + timedelta(days=days)
    out = []
    for g in games:
        tip = parse_iso(g["date"])
        if g["completed"] or tip < now - timedelta(hours=3) or tip > horizon:
            continue
        ev = history.get(mapping.get(g["game_id"], ""))
        out.append({**g, "tip": tip.isoformat(), "line": ev})
    return out


def recent_results(games: list[dict[str, Any]], history: dict[str, dict[str, Any]], now: datetime, days: int = 7) -> list[dict[str, Any]]:
    mapping = match_lines_to_games(games, history)
    out = []
    for g in games:
        tip = parse_iso(g["date"])
        if not g["completed"] or tip < now - timedelta(days=days):
            continue
        ev = history.get(mapping.get(g["game_id"], ""))
        margin = (g["home"]["score"] or 0) - (g["away"]["score"] or 0)
        closing = ev["latest"]["spread"] if ev else None
        ats = None
        if closing is not None:
            diff = margin + closing
            ats = "push" if diff == 0 else ("home" if diff > 0 else "away")
        out.append({**g, "margin": margin, "closing_spread": closing, "ats_cover": ats, "line": ev})
    out.sort(key=lambda g: g["date"], reverse=True)
    return out


def posting_stats(history: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """How far before tip did we first see a line, and how much did it move? Grows as data grows."""
    leads = []
    moves = []
    for ev in history.values():
        lead_h = (parse_iso(ev["commence_time"]) - parse_iso(ev["first_seen"])).total_seconds() / 3600
        leads.append(lead_h)
        if ev["spread_move"] is not None:
            moves.append(abs(ev["spread_move"]))
    return {
        "events": len(history),
        "median_lead_hours": round(median(leads), 1) if leads else None,
        "median_abs_spread_move": round(median(moves), 2) if moves else None,
        "note": "Lines are checked every 15 minutes, so a posting time here is accurate to within 15 minutes of when the book put it up.",
    }


def book_posting(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per book: how many games we saw it price, how far before tip we first saw its spread, and how often it was first.

    Precision is one snapshot interval (15 minutes), so ties within a snapshot all count as first."""
    first: dict[tuple[str, str], str] = {}
    tip: dict[str, str] = {}
    for r in rows:
        if r.get("market") != "spreads":
            continue
        key = (r["odds_event_id"], r["book"])
        if key not in first or r["captured_at"] < first[key]:
            first[key] = r["captured_at"]
        tip[r["odds_event_id"]] = r["commence_time"]
    earliest: dict[str, str] = {}
    for (ev, _), t in first.items():
        if ev not in earliest or t < earliest[ev]:
            earliest[ev] = t
    by: dict[str, dict[str, Any]] = {}
    for (ev, book), t in first.items():
        b = by.setdefault(book, {"book": book, "games": 0, "first": 0, "leads": []})
        b["games"] += 1
        b["first"] += t == earliest[ev]
        b["leads"].append((parse_iso(tip[ev]) - parse_iso(t)).total_seconds() / 3600)
    out = []
    for b in by.values():
        leads = b.pop("leads")
        out.append({**b, "median_lead_hours": round(median(leads), 1)})
    out.sort(key=lambda b: (-b["first"], -b["median_lead_hours"]))
    return out


def posting_clocks(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """One clock per game: when we first saw each book price it (any market), measured back from tip."""
    first: dict[tuple[str, str], str] = {}
    meta: dict[str, dict[str, Any]] = {}
    for r in rows:
        ev = r["odds_event_id"]
        key = (ev, r["book"])
        if key not in first or r["captured_at"] < first[key]:
            first[key] = r["captured_at"]
        meta.setdefault(ev, {"id": ev, "tip": r["commence_time"], "home": r["home_team"], "away": r["away_team"],
                             "home_key": r.get("home_key"), "away_key": r.get("away_key")})
    out = []
    for ev, m in meta.items():
        tip = parse_iso(m["tip"])
        books = sorted(({"book": b, "t": t, "lead_h": round((tip - parse_iso(t)).total_seconds() / 3600, 2)}
                        for (e, b), t in first.items() if e == ev), key=lambda x: -x["lead_h"])
        books = [b for b in books if b["lead_h"] > 0]  # quotes first seen after tip are in-play, not openers
        if not books:
            continue
        lead = books[0]["lead_h"]
        span = 12 if lead <= 12 else 24 if lead <= 24 else 48 if lead <= 48 else 72
        to_tip = (tip - now).total_seconds() / 3600
        out.append({**m, "books": books, "span_h": span, "lead_h": lead,
                    "gap_h": round(books[0]["lead_h"] - books[-1]["lead_h"], 2),
                    "now_h": round(to_tip, 2) if 0 < to_tip <= span else None,
                    "final": to_tip <= 0})
    out.sort(key=lambda e: e["tip"], reverse=True)
    return out

