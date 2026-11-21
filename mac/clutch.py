"""Crunch-time rankings from the play-by-play (Matthew, Nov 20 2026).

Two team rankings across every edition's schools, read from the scoring plays and free throws the
book keeps for each D-I game (book.py keys "e" and "f", both from the ESPN summary call that
ncaa.enrich_season already makes). Nothing here makes a request.

Comeback Kings
    The biggest deficit a team came back from to win, counting only the last ten minutes of the
    second half and any overtime. A team trailing by 9 with 6:40 left that wins has a 9-point late
    comeback; a 15-point first-half hole erased by the under-12 timeout doesn't count. Each team is
    ranked by its best late comeback of the season, then by how little time was left when it trailed
    by the most, then by how many late comebacks it has.

Foul Him / Don't Foul Him
    Free-throw shooting after halftime (second half plus overtime), when fouling is a strategy.
    "Don't Foul Him" is the top five, "Foul Him" the bottom five, among teams with at least
    MIN_FTA second-half attempts. A game counts only when its free-throw log matches the box score's
    made and attempted totals for both teams, so a garbled feed never moves a team's number.

Final Exams (Matthew, Nov 20 2026)
    Players ranked by points on go-ahead and tying baskets in the last ten minutes of the second
    half and overtime: a basket that takes a team from behind or level to level or ahead.

The Cardiologists
    The teams whose games are hardest on the heart: the average total swing in win probability per
    game, summed over every scoring play and shown in full swings (100 points of win probability:
    one sure loss turned into one sure win). One formula for every game (score margin and time left,
    no spread), so a game with ESPN's numbers and one without are measured the same way. Lead
    changes per game ride along.

Dunking and Donuts
    How teams score: the share of points from threes, dunks, layups and other rim shots, other twos
    and free throws. "Dunking" is the five teams with the most dunks per game; "Donuts" the five with
    the fewest, the jump-shooting teams that rarely see the rim from above.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from .moments import HALF, period_end

LATE = 600  # the last ten minutes of the second half
MIN_FTA = 20  # second-half free throws a team needs to make Foul Him
TOP = 10  # Comeback Kings shown
FIVE = 5


# ---------------------------------------------------------------- reading the feed: free throws by half


def ft_halves(summary: dict[str, Any], side_of_player: dict[str, str], side_of_team: dict[str, str]) -> dict[str, list[int]] | None:
    """Free throws made and attempted by half: {"home": [h1 made, h1 att, h2+OT made, h2+OT att], "away": [...]}.
    The shooter's side comes from the box score roster (ESPN's team tag is sometimes the other bench),
    then the team tag. A made free throw is one the running score moved by a point for; a play with no
    score on it falls back to ESPN's scoringPlay flag."""
    out = {"home": [0, 0, 0, 0], "away": [0, 0, 0, 0]}
    hs = as_ = 0
    seen = False
    for play in summary.get("plays") or []:
        h, a = play.get("homeScore"), play.get("awayScore")
        h = hs if h is None else int(h)
        a = as_ if a is None else int(a)
        t = ((play.get("type") or {}).get("text") or "").lower().replace(" ", "")
        text = (play.get("text") or "").lower()
        if "freethrow" in t or "free throw" in text:
            seen = True
            pids = [str(p["athlete"]["id"]) for p in play.get("participants") or [] if (p.get("athlete") or {}).get("id")]
            side = next((side_of_player[p] for p in pids if p in side_of_player), None) or side_of_team.get(str((play.get("team") or {}).get("id")))
            dh, da = h - hs, a - as_
            if dh == 1 and da == 0:
                side, made = "home", True
            elif da == 1 and dh == 0:
                side, made = "away", True
            elif dh == 0 and da == 0:
                made = bool(play.get("scoringPlay")) and "miss" not in text
            else:
                made = None  # a score correction riding on the play; can't tell
            if side in out and made is not None:
                per = int((play.get("period") or {}).get("number") or 1)
                i = 0 if per <= 1 else 2
                out[side][i] += 1 if made else 0
                out[side][i + 1] += 1
        hs, as_ = h, a
    return out if seen else None


# ---------------------------------------------------------------- Comeback Kings


def late_comeback(g: dict[str, Any]) -> dict[str, Any] | None:
    """The winner's biggest deficit from 10:00 left in the second half on, or None if it never trailed then.
    g is a decoded book game (book.decode_game) with scoring plays."""
    ev = g.get("events") or []
    if not ev or len(g.get("teams") or []) != 2:
        return None
    fh, fa = ev[-1]["h"], ev[-1]["a"]
    if fh == fa:
        return None
    win = "home" if fh > fa else "away"
    start = 2 * HALF - LATE
    last_per = max(e["per"] for e in ev)
    h = a = 0
    best, at = 0, None
    marked = False
    for e in ev:
        if e["t"] >= start and not marked:  # the score at the 10:00 mark counts too
            marked = True
            d = (a - h) if win == "home" else (h - a)
            if d > 0:
                best, at = d, {"t": start, "per": 2, "h": h, "a": a}
        if e["t"] >= start:
            d = (e["a"] - e["h"]) if win == "home" else (e["h"] - e["a"])
            if d > best:
                best, at = d, e
        h, a = e["h"], e["a"]
    if at is None:
        return None
    secs = int(round(max(0.0, period_end(at["per"]) - at["t"])))
    return {"side": win, "deficit": best, "secs_left": secs, "ot": at["per"] >= 3, "periods": last_per,
            "score_then": [at["h"], at["a"]], "final": [fh, fa]}


def clock(secs: int, ot: bool = False) -> str:
    return f"{secs // 60}:{secs % 60:02d}" + (" in OT" if ot else "")


# ---------------------------------------------------------------- the rankings


def _teams() -> dict[str, dict[str, Any]]:
    """espn id -> our team (every edition's schools), with its page link and conference."""
    from .leagues import ALL as LEAGUES

    out = {}
    for lg in LEAGUES.values():
        for t in lg.teams:
            out[str(t.espn_id)] = {"key": t.key, "short": t.short, "color": t.color, "conf_short": lg.short,
                                   "href": f"{lg.path}teams/{t.key}.html"}
    return out


def _games(season: int) -> Iterable[tuple[str, dict[str, Any]]]:
    from . import book

    d = book.games_dir(season)
    if not d.exists():
        return
    for path in sorted(d.glob("*.json.gz")):
        try:
            day = book.read_gz(path)
        except (OSError, ValueError):
            continue
        yield from day.items()


def _box_ft(g: dict[str, Any]) -> list[list[int]] | None:
    """Box-score free throws made/attempted per side, from the book's raw player rows."""
    from .book import P_COLS

    s, ftm, fta = P_COLS.index("side"), P_COLS.index("ftm"), P_COLS.index("fta")
    tot = [[0, 0], [0, 0]]
    any_row = False
    for r in g.get("p") or []:
        if r[ftm] is None or r[fta] is None:
            continue
        any_row = True
        tot[r[s]][0] += r[ftm]
        tot[r[s]][1] += r[fta]
    return tot if any_row else None


def rankings(season: int | None = None, teams: dict[str, dict[str, Any]] | None = None,
             games: Iterable[tuple[str, dict[str, Any]]] | None = None) -> dict[str, Any]:
    from . import book
    from .config import SEASON

    season = season or SEASON
    teams = teams if teams is not None else _teams()
    games = games if games is not None else _games(season)
    kings: dict[str, dict[str, Any]] = {}
    ft: dict[str, list[int]] = {}
    n_games = n_pbp = n_ft = n_ft_ok = 0
    last = ""
    for gid, raw in games:
        n_games += 1
        last = max(last, str(raw.get("d") or "")[:10])
        ids = [t[0] if t else None for t in raw.get("t") or [None, None]]
        if raw.get("e"):
            n_pbp += 1
            g = book.decode_game(gid, raw)
            c = late_comeback(g)
            if c:
                me = ids[0 if c["side"] == "home" else 1]
                opp = ids[1 if c["side"] == "home" else 0]
                if str(me) in teams:
                    i = 0 if c["side"] == "home" else 1
                    k = kings.setdefault(str(me), {"n": 0, "best": None})
                    k["n"] += 1
                    row = {**c, "game_id": gid, "date": raw.get("d"), "home": c["side"] == "home",
                           "opp_id": str(opp), "opp": (teams.get(str(opp)) or {}).get("short") or _abbr(raw, 1 - i),
                           "score": f"{c['final'][i]}-{c['final'][1 - i]}",
                           "then": f"{c['score_then'][1 - i]}-{c['score_then'][i]}"}  # trailing score, theirs first
                    if k["best"] is None or _comeback_key(row) > _comeback_key(k["best"]):
                        k["best"] = row
        f = raw.get("f")
        if f:
            n_ft += 1
            box = _box_ft(raw)
            ok = box is not None and all(f[i][0] + f[i][2] == box[i][0] and f[i][1] + f[i][3] == box[i][1] for i in (0, 1))
            if ok:
                n_ft_ok += 1
                for i in (0, 1):
                    if ids[i] and str(ids[i]) in teams:
                        cur = ft.setdefault(str(ids[i]), [0, 0, 0])
                        cur[0] += f[i][2]
                        cur[1] += f[i][3]
                        cur[2] += 1
    ck = []
    for tid, k in kings.items():
        ck.append({**teams[tid], "count": k["n"], **k["best"]})
    ck.sort(key=lambda r: (-r["deficit"], r["secs_left"], -r["count"], r["short"]))
    for i, r in enumerate(ck, 1):
        r["rank"] = i
        r["when"] = clock(r["secs_left"], r["ot"])
    fts = []
    for tid, (m, a, n) in ft.items():
        if a >= MIN_FTA:
            fts.append({**teams[tid], "ftm": m, "fta": a, "games": n, "pct": m / a})
    fts.sort(key=lambda r: (-r["pct"], -r["fta"], r["short"]))
    for i, r in enumerate(fts, 1):
        r["rank"] = i
        r["pct_label"] = f"{100 * r['pct']:.1f}%"
    tot_m = sum(r["ftm"] for r in fts)
    tot_a = sum(r["fta"] for r in fts)
    return {"kings": ck, "dont_foul": fts[:FIVE], "foul": list(reversed(fts[-FIVE:])) if len(fts) >= 2 * FIVE else [],
            "n_ft_teams": len(fts), "avg_pct": f"{100 * tot_m / tot_a:.1f}%" if tot_a else None,
            "n_games": n_games, "n_pbp": n_pbp, "n_ft": n_ft, "n_ft_ok": n_ft_ok, "min_fta": MIN_FTA,
            "n_teams": len(teams), "last_day": _label(last)}


# ---------------------------------------------------------------- Final Exams, The Cardiologists, Dunking and Donuts

MIN_GAMES = 3  # games a team needs for the Cardiologists and Dunking and Donuts
MIX = (("3", "Threes"), ("dunk", "Dunks"), ("rim", "Layups and rim"), ("two", "Other twos"), ("ft", "Free throws"))
MIX_OF = {"3": "3", "dunk": "dunk", "layup": "rim", "tip": "rim", "hook": "two", "jumper": "two", "fg": "two", "ft": "ft"}


def _scorer_side(prev: tuple[int, int], e: dict[str, Any]) -> str | None:
    dh, da = e["h"] - prev[0], e["a"] - prev[1]
    if dh > 0 and da == 0:
        return "home"
    if da > 0 and dh == 0:
        return "away"
    return None


def clutch_baskets(g: dict[str, Any]) -> list[dict[str, Any]]:
    """Go-ahead and tying baskets in the last ten minutes of the second half and overtime."""
    out = []
    prev = (0, 0)
    start = 2 * HALF - LATE
    for e in g.get("events") or []:
        side = _scorer_side(prev, e)
        if side and e["t"] >= start and e.get("pid"):
            mine0, opp0 = (prev[0], prev[1]) if side == "home" else (prev[1], prev[0])
            mine1, opp1 = (e["h"], e["a"]) if side == "home" else (e["a"], e["h"])
            if mine0 <= opp0 and mine1 >= opp1:
                out.append({"pid": e["pid"], "side": side, "pts": mine1 - mine0, "ahead": mine1 > opp1})
        prev = (e["h"], e["a"])
    return out


def heart_rate(g: dict[str, Any]) -> tuple[float, int] | None:
    """(total win-probability swing in percentage points, lead changes) for one game."""
    from .moments import home_wp

    ev = g.get("events") or []
    if len(ev) < 10:
        return None
    end = period_end(max(e["per"] for e in ev))
    wp, swing, changes, leader = 0.5, 0.0, 0, 0
    for e in ev:
        w = home_wp(e["h"] - e["a"], e["t"], end, None)
        swing += abs(w - wp)
        wp = w
        now = (e["h"] > e["a"]) - (e["h"] < e["a"])
        if now and leader and now != leader:
            changes += 1
        if now:
            leader = now
    return 100 * swing, changes


def extras(teams: dict[str, dict[str, Any]], games: Iterable[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    from . import book

    exams: dict[str, dict[str, Any]] = {}
    heart: dict[str, list[float]] = {}
    mix: dict[str, dict[str, float]] = {}
    for gid, raw in games:
        if not raw.get("e"):
            continue
        g = book.decode_game(gid, raw)
        ids = {"home": str((raw.get("t") or [None, None])[0][0]) if raw["t"][0] else None,
               "away": str(raw["t"][1][0]) if raw["t"][1] else None}
        names = {str(p["espn_id"]): p.get("name") for p in g["players"]}
        for b in clutch_baskets(g):
            tid = ids[b["side"]]
            if tid not in teams:
                continue
            x = exams.setdefault(b["pid"], {"pid": b["pid"], "tid": tid, "name": names.get(str(b["pid"])), "pts": 0, "n": 0, "ahead": 0})
            x["pts"] += b["pts"]
            x["n"] += 1
            x["ahead"] += 1 if b["ahead"] else 0
        hr = heart_rate(g)
        ev = g["events"]
        fh, fa = ev[-1]["h"], ev[-1]["a"]
        if hr:
            for side, won in (("home", fh > fa), ("away", fa > fh)):
                if ids[side] in teams:
                    h = heart.setdefault(ids[side], [0.0, 0, 0, 0, 0])
                    h[0] += hr[0]
                    h[1] += hr[1]
                    h[2] += 1
                    h[3 if won else 4] += 1
        prev = (0, 0)
        tally = {"home": {}, "away": {}}
        for e in ev:
            side = _scorer_side(prev, e)
            if side:
                pts = (e["h"] - prev[0]) if side == "home" else (e["a"] - prev[1])
                k = MIX_OF.get(e["kind"], "two")
                tally[side][k] = tally[side].get(k, 0) + pts
                if e["kind"] == "dunk":
                    tally[side]["n_dunk"] = tally[side].get("n_dunk", 0) + 1
            prev = (e["h"], e["a"])
        for side in ("home", "away"):
            if ids[side] in teams:
                m = mix.setdefault(ids[side], {"games": 0})
                m["games"] += 1
                for k, v in tally[side].items():
                    m[k] = m.get(k, 0) + v
    fe = sorted((x for x in exams.values() if x["name"]), key=lambda x: (-x["pts"], -x["ahead"], x["name"] or ""))
    for i, x in enumerate(fe, 1):
        t = teams[x["tid"]]
        x.update(rank=i, short=t["short"], color=t["color"], conf_short=t["conf_short"], href=t["href"])
    cards = []
    for tid, (sw, ch, n, w, l) in heart.items():
        if n >= MIN_GAMES:
            cards.append({**teams[tid], "swings": round(sw / n / 100, 1), "changes": round(ch / n, 1), "games": n, "record": f"{w}-{l}"})
    cards.sort(key=lambda r: (-r["swings"], -r["changes"], r["short"]))
    for i, r in enumerate(cards, 1):
        r["rank"] = i
    mixes = []
    for tid, m in mix.items():
        tot = sum(m.get(k, 0) for k, _ in MIX)
        if m["games"] >= MIN_GAMES and tot:
            mixes.append({**teams[tid], "games": m["games"], "dpg": round(m.get("n_dunk", 0) / m["games"], 1),
                          "dunks": m.get("n_dunk", 0),
                          "mix": [{"k": k, "label": lab, "pct": round(100 * m.get(k, 0) / tot, 1)} for k, lab in MIX]})
    dunking = sorted(mixes, key=lambda r: (-r["dunks"] / r["games"], r["short"]))
    donuts = sorted(mixes, key=lambda r: (r["dunks"] / r["games"], r["short"]))
    for lst in (dunking, donuts):
        lst[:] = [dict(r, rank=i) for i, r in enumerate(lst, 1)]
    return {"exams": fe[:TOP], "n_exams": len(fe), "cardio": cards[:TOP], "n_cardio": len(cards),
            "dunking": dunking[:FIVE], "donuts": donuts[:FIVE] if len(mixes) >= 2 * FIVE else [], "n_mix": len(mixes),
            "mix_keys": MIX, "min_games": MIN_GAMES}


def _label(day: str) -> str:
    try:
        return datetime.fromisoformat(day).strftime("%b %-d, %Y")
    except ValueError:
        return ""


def _abbr(raw: dict[str, Any], i: int) -> str:
    t = (raw.get("t") or [None, None])[i]
    return (t[1] if t and len(t) > 1 else None) or "?"


def _comeback_key(r: dict[str, Any]) -> tuple:
    return (r["deficit"], -r["secs_left"])


def page_context(season: int | None = None) -> dict[str, Any] | None:
    from .config import SEASON

    teams = _teams()
    games = list(_games(season or SEASON))
    r = rankings(season, teams=teams, games=games)
    r.update(extras(teams, games))
    if not r["kings"] and not r["dont_foul"]:
        return None
    for row in r["kings"]:
        try:
            row["day"] = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00")).strftime("%b %-d")
        except ValueError:
            row["day"] = ""
    r["kings_top"] = r["kings"][:TOP]
    r["through"] = r.pop("last_day", "") or ""
    r["n_kings"] = len(r["kings"])
    return r


if __name__ == "__main__":  # python -m mac.clutch : print the rankings
    import json

    out = rankings()
    print(json.dumps({k: (v[:TOP] if isinstance(v, list) else v) for k, v in out.items()}, indent=1, default=str))
