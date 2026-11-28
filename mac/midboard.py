"""The Big Mid: the most middling game on the D-I slate, for the Lock Call (Matthew, Nov 27 2026).

Matthew asked whether Towson at Penn was "center of the road mid". Then he named the answer: every day the
Tops and Bottoms crew previews tonight's Big Mid and recaps last night's, plus any big upsets and any
mid-major that beat a power-conference team.

    python -m mac.midboard [YYYY-MM-DD]     the facts for that day's Lock Call (default: today, Eastern), as JSON

How mid a game is: its distance from dead center, made of four parts, each scaled so one unit is a
fair step off the middle:

    each team's rating (adj_em) minus the D-I median, in standard deviations   (two parts)
    the spread, in 5-point steps                                               (a pick'em is zero)
    the total minus the national average D-I vs D-I total, in 10-point steps

The game with the smallest distance is the Big Mid. Lines are ESPN's (scoreboard odds, else the summary
feed's pickcenter); a game without a line uses our model's spread and total, and says so. Ratings are
data/model/ratings.json, the same ones the site runs on.

Tonight's pick is saved to data/midboard/DAY.json the first time it is made, so tomorrow's recap covers the
game we actually previewed, even if the lines moved. Every number is arithmetic on the feeds; a sentence
whose number is missing is left out.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .config import ESPN_BASE

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RATINGS = DATA / "model" / "ratings.json"
GAMES = DATA / "ncaa" / "games-2027.json"
MID_DIR = DATA / "midboard"
ET = ZoneInfo("America/New_York")
TIMEOUT = 30

SPREAD_STEP, TOTAL_STEP = 5.0, 10.0
POWER = {"2": "ACC", "4": "Big East", "7": "Big Ten", "8": "Big 12", "23": "SEC"}  # ESPN conference ids; everyone else is a mid-major
UPSET_DOG = 7.0  # a closing underdog of this many points or more that wins is a big upset
MOST_UPSETS = 4  # upsets and mid-over-power wins read on the show, biggest first
BOARD = 5  # the top of tonight's Mid Board in the facts


# ---------------------------------------------------------------- scoring

def baseline(teams: list[dict[str, Any]], games: list[dict[str, Any]]) -> dict[str, float]:
    """The middle of D-I: median rating and its spread, and the average D-I vs D-I total this season."""
    ems = [t["adj_em"] for t in teams]
    ids = {t["id"] for t in teams}
    totals = [g["home"]["pts"] + g["away"]["pts"] for g in games
              if g["home"].get("pts") is not None and g["away"].get("pts") is not None
              and g["home"]["id"] in ids and g["away"]["id"] in ids]
    return {"median_em": statistics.median(ems), "sd_em": statistics.pstdev(ems) or 1.0,
            "avg_total": statistics.mean(totals) if totals else 145.0, "teams": len(teams)}


def distance(em_home: float, em_away: float, spread: float, total: float, base: dict[str, float]) -> dict[str, float]:
    """How far a game sits from dead center; 0 is perfectly mid."""
    parts = {"home": (em_home - base["median_em"]) / base["sd_em"],
             "away": (em_away - base["median_em"]) / base["sd_em"],
             "spread": abs(spread) / SPREAD_STEP,
             "total": (total - base["avg_total"]) / TOTAL_STEP}
    return {"d": math.sqrt(sum(v * v for v in parts.values())), **{k: round(v, 2) for k, v in parts.items()}}


def project(th: dict[str, Any], ta: dict[str, Any], r: dict[str, Any], neutral: bool) -> tuple[float, float]:
    """Our model's home margin and total, from the published ratings table (mac/ratings.py project())."""
    loc = 0.0 if neutral else 1.0
    poss = th["adj_t"] + ta["adj_t"] - r["tau"]
    eh = th["adj_o"] + ta["adj_d"] - r["mu"] + r["hca"] * loc
    ea = ta["adj_o"] + th["adj_d"] - r["mu"] - r["hca"] * loc
    return (eh - ea) * poss / 100, (eh + ea) * poss / 100


# ---------------------------------------------------------------- feeds

def scoreboard(day: date) -> list[dict[str, Any]]:
    resp = requests.get(f"{ESPN_BASE}/scoreboard", params={"dates": day.strftime("%Y%m%d"), "groups": "50", "limit": "500"},
                        timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("events", [])


def summary(game_id: str) -> dict[str, Any] | None:
    try:
        resp = requests.get(f"{ESPN_BASE}/summary", params={"event": game_id}, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def _line_from_odds(odds: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """ESPN odds (scoreboard `odds` or summary `pickcenter`) as {home_spread, total}; home_spread < 0 = home favored."""
    for o in odds or []:
        spread, total = o.get("spread"), o.get("overUnder")
        if spread is None and total is None:
            continue
        hs = None
        if spread is not None:
            mag = abs(float(spread))
            home_fav = (o.get("homeTeamOdds") or {}).get("favorite")
            away_fav = (o.get("awayTeamOdds") or {}).get("favorite")
            hs = -mag if home_fav else (mag if away_fav else (float(spread) if mag else 0.0))
        return {"home_spread": hs, "total": float(total) if total is not None else None,
                "book": (o.get("provider") or {}).get("name")}
    return None


def slate(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scoreboard events as plain games: ids, names, conference, status, score, and ESPN's line when it has one."""
    out = []
    for e in events:
        c = e["competitions"][0]
        sides = {x["homeAway"]: x for x in c.get("competitors", [])}
        if set(sides) != {"home", "away"}:
            continue

        def side(x: dict[str, Any]) -> dict[str, Any]:
            t = x["team"]
            try:
                pts = int(x.get("score"))
            except (TypeError, ValueError):
                pts = None
            return {"id": t["id"], "name": t.get("shortDisplayName") or t.get("location") or t.get("displayName"),
                    "full": t.get("displayName"), "conf": str(t.get("conferenceId") or ""), "pts": pts}

        st = (c.get("status") or e.get("status") or {}).get("type", {})
        out.append({"id": e["id"], "tip": e["date"], "neutral": bool(c.get("neutralSite")),
                    "state": st.get("state"), "final": bool(st.get("completed")),
                    "home": side(sides["home"]), "away": side(sides["away"]), "line": _line_from_odds(c.get("odds"))})
    return out


def fill_lines(games: list[dict[str, Any]], known: dict[str, dict[str, Any]]) -> None:
    """Games without a scoreboard line: the season file's closing line, else one summary call each."""
    need = []
    for g in games:
        if g["line"] is None and known.get(g["id"]):
            g["line"] = dict(known[g["id"]])
        if g["line"] is None:
            need.append(g)

    def one(g: dict[str, Any]) -> None:
        s = summary(g["id"])
        g["line"] = _line_from_odds((s or {}).get("pickcenter"))
        g["_summary"] = s

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one, need))


# ---------------------------------------------------------------- the board

def board(games: list[dict[str, Any]], r: dict[str, Any], base: dict[str, float]) -> list[dict[str, Any]]:
    """Every D-I vs D-I game, most mid first."""
    teams = {t["id"]: t for t in r["teams"]}
    rows = []
    for g in games:
        th, ta = teams.get(g["home"]["id"]), teams.get(g["away"]["id"])
        if not th or not ta:
            continue
        margin, total = project(th, ta, r, g["neutral"])
        ln = g.get("line") or {}
        spread = ln.get("home_spread")
        line_total = ln.get("total")
        src = "line" if spread is not None and line_total is not None else ("model" if spread is None and line_total is None else "mixed")
        sp = spread if spread is not None else -margin
        tot = line_total if line_total is not None else total
        d = distance(th["adj_em"], ta["adj_em"], sp, tot, base)
        rows.append({
            "game_id": g["id"], "tip": g["tip"], "neutral": g["neutral"],
            "matchup": f"{g['away']['name']} {'vs' if g['neutral'] else 'at'} {g['home']['name']}",
            "home": {"name": g["home"]["name"], "rank": th["rk_adj_em"], "adj_em": th["adj_em"], "conf": g["home"]["conf"]},
            "away": {"name": g["away"]["name"], "rank": ta["rk_adj_em"], "adj_em": ta["adj_em"], "conf": g["away"]["conf"]},
            "home_spread": sp, "total": tot, "from": src,
            "model": {"home_margin": round(margin, 1), "total": round(total, 1)},
            "mid": round(d["d"], 2), "parts": {k: d[k] for k in ("home", "away", "spread", "total")},
        })
    rows.sort(key=lambda x: x["mid"])
    for i, x in enumerate(rows, 1):
        x["mid_rank"] = i
    return rows


def why(row: dict[str, Any], base: dict[str, float]) -> str:
    """One plain sentence on what keeps a game off dead center: its biggest part."""
    p = row["parts"]
    worst = max(p, key=lambda k: abs(p[k]))
    if worst == "spread":
        return f"the spread ({abs(row['home_spread']):g}) is the only thing keeping it off dead center"
    if worst == "total":
        gap = row["total"] - base["avg_total"]
        return f"the total ({row['total']:g}) runs {abs(gap):.1f} {'over' if gap > 0 else 'under'} the national average"
    side = row[worst]
    return f"{side['name']} ({side['rank']} of {base['teams']}) sits furthest from the median team"


def _et(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(ET).strftime("%-I:%M %p ET")


# ---------------------------------------------------------------- last night

def _top_scorers(s: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """{'home': {name, pts}, 'away': {...}} from a summary's box score."""
    out: dict[str, dict[str, Any]] = {}
    for team in (s.get("boxscore") or {}).get("players", []) or []:
        side = team.get("homeAway") or ("home" if team.get("displayOrder") == 2 else "away")
        best = None
        for block in team.get("statistics", []) or []:
            keys = block.get("keys") or block.get("names") or []
            if "points" not in keys:
                continue
            i = keys.index("points")
            for a in block.get("athletes", []) or []:
                try:
                    pts = int((a.get("stats") or [])[i])
                except (ValueError, IndexError, TypeError):
                    continue
                if best is None or pts > best["pts"]:
                    best = {"name": (a.get("athlete") or {}).get("displayName"), "pts": pts}
        if best and best["name"]:
            out[side] = best
    return out


def _moments(game_id: str, s: dict[str, Any], line: dict[str, Any] | None, names: dict[str, str], most: int) -> list[str]:
    """Up to `most` sentences on how the game turned (mac/moments.py), from the play-by-play."""
    from . import book, moments, pbp
    try:
        g = book.decode_game(game_id, book.encode_game(pbp.game_from_summary(game_id, s)))
        m = moments.analyze(g, (line or {}).get("home_spread"), (line or {}).get("total"))
    except (KeyError, ValueError, TypeError, IndexError):
        return []
    return moments.recap_lines(m, names, seed=game_id, most=most)


def result(g: dict[str, Any], line: dict[str, Any] | None, most: int = 2) -> dict[str, Any]:
    """The final of one game: score, the line's verdict, top scorer on each side, and the runs."""
    h, a = g["home"], g["away"]
    win, lose = (h, a) if h["pts"] > a["pts"] else (a, h)
    out: dict[str, Any] = {"game_id": g["id"], "final": f"{win['name']} {win['pts']}, {lose['name']} {lose['pts']}",
                           "winner": win["name"], "margin": win["pts"] - lose["pts"]}
    hs = (line or {}).get("home_spread")
    if hs is not None:
        cover = h["pts"] - a["pts"] + hs
        fav = h["name"] if hs < 0 else (a["name"] if hs > 0 else None)
        out["line"] = f"{fav} by {abs(hs):g}" if fav else "pick'em"
        out["covered"] = "push" if cover == 0 else (h["name"] if cover > 0 else a["name"])
        out["missed_line_by"] = abs(abs(h["pts"] - a["pts"]) - abs(hs)) if fav else None
    tot = (line or {}).get("total")
    if tot is not None:
        pts = h["pts"] + a["pts"]
        out["total"] = {"line": tot, "scored": pts, "went": "push" if pts == tot else ("over" if pts > tot else "under")}
    s = g.get("_summary") or summary(g["id"])
    if s:
        tops = _top_scorers(s)
        if tops:
            out["top_scorers"] = [{"team": g[k]["name"], **v} for k, v in tops.items()]
        lines = _moments(g["id"], s, line, {"home": h["name"], "away": a["name"]}, most)
        if lines:
            out["how"] = lines
    return out


def upsets(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Last night's big upsets (a winner that closed a 7-point dog or more) and every mid-major win over a power team."""
    out = []
    for g in games:
        if not g["final"] or g["home"]["pts"] is None or g["away"]["pts"] is None or g["home"]["pts"] == g["away"]["pts"]:
            continue
        win, lose = ("home", "away") if g["home"]["pts"] > g["away"]["pts"] else ("away", "home")
        hs = (g.get("line") or {}).get("home_spread")
        dog_by = None if hs is None else (hs if win == "home" else -hs)  # positive: the winner was the underdog
        mid_over_power = g[lose]["conf"] in POWER and g[win]["conf"] not in POWER and bool(g[win]["conf"])
        big = dog_by is not None and dog_by >= UPSET_DOG
        if not (big or mid_over_power):
            continue
        out.append({"g": g, "dog_by": dog_by, "kinds": [k for k, on in (("big upset", big), ("mid over power", mid_over_power)) if on],
                    "power_loser": POWER.get(g[lose]["conf"])})
    out.sort(key=lambda x: -(x["dog_by"] if x["dog_by"] is not None else 0))
    return out


# ---------------------------------------------------------------- the day

def pick_path(day: str) -> Path:
    return MID_DIR / f"{day}.json"


def tonight(day: date, r: dict[str, Any], base: dict[str, float], known: dict[str, dict[str, Any]], save: bool = True) -> dict[str, Any]:
    """Tonight's Mid Board. The first run of the day freezes the Big Mid pick in data/midboard/DAY.json."""
    games = slate(scoreboard(day))
    fill_lines(games, known)
    rows = board(games, r, base)
    if not rows:
        return {"date": day.isoformat(), "games": 0}
    saved = pick_path(day.isoformat())
    frozen = json.loads(saved.read_text()) if saved.exists() else None
    if frozen is None and save:
        MID_DIR.mkdir(parents=True, exist_ok=True)
        frozen = {"date": day.isoformat(), "picked_at": datetime.now(ET).isoformat(timespec="minutes"),
                  "ratings_as_of": r.get("as_of"), "base": base, "bigmid": rows[0], "board": rows[:BOARD]}
        saved.write_text(json.dumps(frozen, indent=1) + "\n")
    pick = (frozen or {}).get("bigmid") or rows[0]
    return {"date": day.isoformat(), "games": len(rows), "bigmid": {**pick, "tip_et": _et(pick["tip"]), "why_not_zero": why(pick, base)},
            "board": [{k: x[k] for k in ("mid_rank", "matchup", "mid", "home_spread", "total", "from")} | {"tip_et": _et(x["tip"])}
                      for x in rows[:BOARD]]}


def last_night(day: date, r: dict[str, Any], base: dict[str, float], known: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Recap of `day`'s Big Mid, plus the night's upsets."""
    games = slate(scoreboard(day))
    for g in games:  # completed games lose ESPN's scoreboard odds; the season file has the closing line
        if g["line"] is None and known.get(g["id"]):
            g["line"] = dict(known[g["id"]])
    out: dict[str, Any] = {"date": day.isoformat()}
    saved = pick_path(day.isoformat())
    if saved.exists():
        pick = json.loads(saved.read_text())["bigmid"]
    else:  # no pick was frozen that day: rank it now from closing lines (ratings are today's, so say so)
        fill_lines(games, known)
        rows = board(games, r, base)
        pick = rows[0] if rows else None
        out["picked_after_the_fact"] = True
    if pick:
        g = next((x for x in games if x["id"] == pick["game_id"]), None)
        out["bigmid"] = {"matchup": pick["matchup"], "mid": pick["mid"], "line_was": pick["home_spread"], "total_was": pick["total"]}
        if g and g["final"]:
            out["bigmid"]["result"] = result(g, {"home_spread": pick["home_spread"], "total": pick["total"]}, most=3)
        elif g:
            out["bigmid"]["result"] = None
            out["bigmid"]["status"] = "not final (postponed or still going)"
    ups = upsets([g for g in games if g["id"] != (pick or {}).get("game_id")])
    out["upsets"] = []
    for u in ups[:MOST_UPSETS]:
        g = u["g"]
        res = result(g, g.get("line"), most=1)
        out["upsets"].append({"matchup": f"{g['away']['name']} {'vs' if g['neutral'] else 'at'} {g['home']['name']}",
                              "kinds": u["kinds"], "winner_was_dog_by": u["dog_by"], "power_loser": u["power_loser"], **res})
    if len(ups) > MOST_UPSETS:
        out["more_upsets"] = len(ups) - MOST_UPSETS
    return out


def facts(day: str | None = None, save: bool = True) -> dict[str, Any]:
    """Everything the Lock Call's Big Mid segment may say for `day` (the card's date, Eastern)."""
    d = date.fromisoformat(day) if day else datetime.now(ET).date()
    r = json.loads(RATINGS.read_text())
    games = json.loads(GAMES.read_text())["games"] if GAMES.exists() else []
    base = baseline(r["teams"], games)
    known = {g["id"]: g["line"] for g in games if g.get("line")}
    out: dict[str, Any] = {"how": ("distance from dead center: both teams' rating vs the D-I median, the spread, and the total "
                                   "vs the national average; 0 is perfectly mid"),
                           "middle": {"median_team_em": round(base["median_em"], 2), "avg_total": round(base["avg_total"], 1)}}
    try:
        out["tonight"] = tonight(d, r, base, known, save=save)
    except requests.RequestException as e:
        out["tonight"] = {"error": f"ESPN scoreboard: {e}"}
    try:
        out["last_night"] = last_night(d - timedelta(days=1), r, base, known)
    except requests.RequestException as e:
        out["last_night"] = {"error": f"ESPN scoreboard: {e}"}
    return out


def main(argv: list[str]) -> int:
    print(json.dumps(facts(argv[0] if argv else None), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
