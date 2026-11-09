"""Over/under study: closing total vs what was actually scored, for games involving MAC teams.

Closing totals are the DraftKings number ESPN carries on each finished game
(data/ncaa/games-<season>.json, `line.total`). Every game with a closing total
and a final score counts; overtime games are kept but can be split out.

Trends are only called out when a split has enough games and leans hard
enough that it is worth a look. With samples this small most "trends" are
noise, and the page says so.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable

from .config import LEAGUE, SHARED_DIR, TEAMS
from .schedule_view import ET

NCAA_DIR = SHARED_DIR / "ncaa"
MAC_IDS = {t.espn_id: t for t in TEAMS}
BUCKETS = ((0, 140, "Under 140"), (140, 150, "140–149.5"), (150, 160, "150–159.5"), (160, 999, "160 and up"))
MIN_TREND_N = 15  # fewest games before a split can be called a trend
TREND_SHARE = 0.60  # over or under rate that makes a split worth flagging
TREND_POINTS = 3.0  # or an average miss this big


def season_label(season: int) -> str:
    return f"{season - 1}-{str(season)[2:]}"


def load_games(season: int) -> list[dict[str, Any]]:
    path = NCAA_DIR / f"games-{season}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("games", [])


def rows(games: Iterable[dict[str, Any]], season: int) -> list[dict[str, Any]]:
    """One row per MAC team appearance in a finished game with a closing total."""
    out = []
    for g in games:
        line = g.get("line") or {}
        close = line.get("total")
        hp, ap = g["home"].get("pts"), g["away"].get("pts")
        if close is None or hp is None or ap is None:
            continue
        mac_sides = [s for s in ("home", "away") if g[s]["id"] in MAC_IDS]
        if not mac_sides:
            continue
        actual = hp + ap
        when = datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(ET)
        both = len(mac_sides) == 2
        base = {
            "id": g["id"], "season": season, "date": when.strftime("%Y-%m-%d"), "md": when.strftime("%b %-d"), "month": when.strftime("%b"),
            "month_n": (when.month - 10) % 12, "close": float(close), "actual": actual, "diff": round(actual - float(close), 1),
            "ot": bool(g.get("ot")), "conf": both, "post": g.get("season_type") == 3, "neutral": bool(g.get("neutral")),
            "away": g["away"]["name"], "home": g["home"]["name"], "away_pts": ap, "home_pts": hp,
        }
        base["res"] = "o" if actual > close else ("u" if actual < close else "p")
        base["kind"] = "Conference tournament / postseason" if base["post"] else ("Conference" if both else "Non-conference")
        for side in mac_sides:
            out.append({**base, "team": MAC_IDS[g[side]["id"]].key, "side": side})
    return out


def games_only(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each game once (a MAC-vs-MAC game appears twice in rows())."""
    seen, out = set(), []
    for r in rs:
        if r["id"] not in seen:
            seen.add(r["id"])
            out.append(r)
    return out


def summarize(rs: list[dict[str, Any]], label: str = "") -> dict[str, Any]:
    n = len(rs)
    o = sum(r["res"] == "o" for r in rs)
    u = sum(r["res"] == "u" for r in rs)
    p = n - o - u
    decided = o + u
    diff = sum(r["diff"] for r in rs) / n if n else None
    s = {"label": label, "n": n, "o": o, "u": u, "p": p,
         "over_pct": round(100 * o / decided) if decided else None,
         "avg_diff": round(diff, 1) if diff is not None else None,
         "avg_close": round(sum(r["close"] for r in rs) / n, 1) if n else None,
         "avg_actual": round(sum(r["actual"] for r in rs) / n, 1) if n else None,
         "mae": round(sum(abs(r["diff"]) for r in rs) / n, 1) if n else None}
    # Two-sided p-value for the over/under split against a coin flip (normal approximation).
    if decided:
        z = (o - decided / 2) / math.sqrt(decided / 4)
        s["p_value"] = round(math.erfc(abs(z) / math.sqrt(2)), 3)
    else:
        s["p_value"] = None
    s["lean"] = None
    if decided and n >= MIN_TREND_N:
        share = max(o, u) / decided
        side = "over" if o > u else "under"
        agrees = (diff or 0) > 0 if side == "over" else (diff or 0) < 0
        if o != u and agrees and (share >= TREND_SHARE or (abs(diff) >= TREND_POINTS and share >= 0.55)):
            s["lean"] = side
    return s


def split(rs: list[dict[str, Any]], key, order=None) -> list[dict[str, Any]]:
    groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in rs:
        groups[key(r)].append(r)
    keys = order if order else sorted(groups)
    return [summarize(groups[k], k) for k in keys if groups.get(k)]


def bucket(close: float) -> str:
    for lo, hi, name in BUCKETS:
        if lo <= close < hi:
            return name
    return BUCKETS[-1][2]


def scatter(gs: list[dict[str, Any]], w: int = 560, h: int = 360, pad: int = 40) -> dict[str, Any] | None:
    """Close (x) vs actual (y), one dot per game, plus the y = x line where the total landed exactly."""
    if not gs:
        return None
    vals = [r["close"] for r in gs] + [r["actual"] for r in gs]
    lo, hi = math.floor(min(vals) / 10) * 10, math.ceil(max(vals) / 10) * 10
    X = lambda v: round(pad + (v - lo) / (hi - lo) * (w - pad - 12), 1)  # noqa: E731
    Y = lambda v: round(h - pad + 4 - (v - lo) / (hi - lo) * (h - pad - 16), 1)  # noqa: E731
    ticks = list(range(lo, hi + 1, 10 if hi - lo <= 120 else 20))
    return {"w": w, "h": h, "pad": pad, "diag": (X(lo), Y(lo), X(hi), Y(hi)),
            "xt": [(X(t), t) for t in ticks], "yt": [(Y(t), t) for t in ticks], "x0": X(lo), "x1": X(hi), "y0": Y(lo), "y1": Y(hi),
            "dots": [{"x": X(r["close"]), "y": Y(r["actual"]), "res": r["res"], "cur": r.get("cur", False),
                      "t": f"{r['md']} {r['season'] - 1 if r['month_n'] < 3 else r['season']}: {r['away']} {r['away_pts']}, {r['home']} {r['home_pts']} · close {r['close']:g}, scored {r['actual']} ({r['diff']:+g})"} for r in gs]}


def histogram(gs: list[dict[str, Any]], width: int = 5, lo: int = -40, hi: int = 40) -> list[dict[str, Any]]:
    """How far the score landed from the close, in 5-point bins; ends catch everything beyond."""
    bins = []
    for start in range(lo, hi, width):
        bins.append({"lo": start, "hi": start + width, "n": 0, "label": f"{start:+d} to {start + width:+d}"})
    for r in gs:
        i = min(max(int((r["diff"] - lo) // width), 0), len(bins) - 1)
        bins[i]["n"] += 1
    top = max((b["n"] for b in bins), default=1) or 1
    for b in bins:
        b["pct"] = round(100 * b["n"] / top)
        b["side"] = "o" if b["lo"] >= 0 else "u"
    return bins


def trends(sections: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Splits that lean hard on enough games, strongest first. Not advice: most will regress."""
    out = []
    for name, splits in sections.items():
        for s in splits:
            if s["lean"]:
                out.append({**s, "where": name})
    out.sort(key=lambda s: (s["p_value"] if s["p_value"] is not None else 1, -abs(s["avg_diff"] or 0)))
    return out[:8]


def build(seasons: tuple[int, ...] | None = None) -> dict[str, Any]:
    seasons = seasons or tuple(sorted(int(p.stem.split("-")[1]) for p in NCAA_DIR.glob("games-*.json")))
    seasons = tuple(s for s in seasons if load_games(s))
    if not seasons:
        return {"seasons": []}
    cur = max(seasons)
    by_season: dict[int, list[dict[str, Any]]] = {s: rows(load_games(s), s) for s in seasons}
    by_season = {s: r for s, r in by_season.items() if r}
    if not by_season:
        return {"seasons": []}
    all_rows = [r for s in sorted(by_season) for r in by_season[s]]
    for r in all_rows:
        r["cur"] = r["season"] == cur
    games = games_only(all_rows)
    team_name = {t.key: t.short for t in TEAMS}

    season_cards = []
    for s in sorted(by_season, reverse=True):
        g = games_only(by_season[s])
        season_cards.append({**summarize(g, season_label(s)), "season": s,
                             "conf": summarize([r for r in g if r["conf"]], f"{LEAGUE.short} vs {LEAGUE.short}"),
                             "nonconf": summarize([r for r in g if not r["conf"] and not r["post"]], "Non-conference")})
    # D-I baseline for the most recent full season with lines: is the MAC any different from everyone?
    base = None
    for s in sorted(by_season, reverse=True):
        allg = [g for g in load_games(s) if (g.get("line") or {}).get("total") is not None and g["home"].get("pts") is not None]
        if len(allg) > 500:
            fake = [{"res": "o" if g["home"]["pts"] + g["away"]["pts"] > g["line"]["total"] else ("u" if g["home"]["pts"] + g["away"]["pts"] < g["line"]["total"] else "p"),
                     "diff": g["home"]["pts"] + g["away"]["pts"] - g["line"]["total"], "close": g["line"]["total"], "actual": g["home"]["pts"] + g["away"]["pts"]} for g in allg]
            base = {**summarize(fake, f"All D-I {season_label(s)}"), "season": s}
            break

    sections = {
        "Team": sorted(split(all_rows, lambda r: team_name[r["team"]]), key=lambda s: -(s["avg_diff"] or 0)),
        "Game type": split(games, lambda r: r["kind"], ["Non-conference", "Conference", "Conference tournament / postseason"]),
        "Closing total": split(games, lambda r: bucket(r["close"]), [b[2] for b in BUCKETS]),
        "Month": split(games, lambda r: (r["month_n"], r["month"])),
        "Overtime": split(games, lambda r: "Went to OT" if r["ot"] else "Regulation", ["Regulation", "Went to OT"]),
        "Site": split(games, lambda r: "Neutral court" if r["neutral"] else "Campus", ["Campus", "Neutral court"]),
    }
    for s in sections["Month"]:
        s["label"] = s["label"][1]
    # Per team, this season vs last.
    team_seasons = {}
    for key, name in team_name.items():
        team_seasons[name] = {s: summarize([r for r in by_season[s] if r["team"] == key]) for s in by_season}

    recent = sorted([r for r in games if r["cur"]], key=lambda r: r["date"], reverse=True)
    return {
        "seasons": [season_label(s) for s in sorted(by_season)], "current": season_label(cur), "cur_season": cur,
        "season_cards": season_cards, "baseline": base, "all": summarize(games, f"All {LEAGUE.short} games"),
        "sections": sections, "team_seasons": team_seasons, "season_keys": sorted(by_season, reverse=True),
        "trends": trends({k: v for k, v in sections.items() if k != "Overtime"}),
        "scatter": scatter(games), "hist": histogram(games), "recent": recent[:20],
        "min_n": MIN_TREND_N, "share": round(TREND_SHARE * 100), "points": TREND_POINTS,
    }
