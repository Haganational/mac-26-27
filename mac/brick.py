"""Brick of the Week: the ugliest shooting night in each conference, every week, with love.

The rule
--------
Every game a conference team finished in the award week (Monday 6 a.m. Eastern to the next
Monday 6 a.m., the same week as the Bricks Index) is a candidate, if the team took at least
MIN_FGA field goal attempts. The award goes to the lowest true shooting percentage:

    TS% = points / (2 * (FGA + 0.44 * FTA))

True shooting counts every way a team tried to score, twos, threes and free throws, so a team
can't hide a bad night behind the foul line or a few lucky threes. Ties go to the team with
more missed shots (field goals plus free throws), then to the earlier game.

Guarantee games don't count: a night against an ACC, Big Ten, Big 12, SEC or Big East team is
left out. Everybody shoots poorly at a top-50 defense on its home floor, and an award for that
would just be a list of who took the biggest check.

We name teams, never players. The write-up pokes at the rim, the ball and the box score, not at
anyone who shot it, and it always names the bright spot: the teammate who shot best that night.

Each Monday the award is frozen into <league data>/brick/<monday>.json, named for the Monday it
is announced and covering the seven days before it. During the week the page shows "Brick
watch", the leader so far, which can change any night.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .config import DATA_DIR, SHARED_DIR

ET = ZoneInfo("America/New_York")
MIN_FGA = 40
FREEZE_HOUR = 6  # Monday, Eastern: the same turnover as the Bricks Index
LATE_HOUR = 12  # freeze by Monday noon even if a box score is still missing
FIRST_WEEK = "2026-11-16"  # the first award, announced with BricksIt Weekly Edition 1
BRICK_DIR = DATA_DIR / "brick"
NAME = "Brick of the Week"
POWER = ("ACC", "Big Ten", "Big 12", "SEC", "Big East")  # opponents whose games don't count
CONF_PATH = SHARED_DIR / "book" / "conferences.json"


def power_ids(path: Path = CONF_PATH) -> set[str]:
    """ESPN ids of every team in a power conference, from the Almanac's conference list."""
    try:
        confs = json.loads(path.read_text())["conferences"]
    except (OSError, ValueError, KeyError):
        return set()
    return {str(t) for c in confs if c.get("short") in POWER for t in c.get("teams") or []}


# ---------------------------------------------------------------- weeks

def week_of(now: datetime) -> str:
    """The Monday that names the award being decided right now (it turns over Monday at FREEZE_HOUR ET).
    The award named for Monday M covers the seven days before M, so while M's week is in progress,
    the award in progress is the one named M + 7 days."""
    et = now.astimezone(ET) - timedelta(hours=FREEZE_HOUR)
    monday = et - timedelta(days=et.weekday())
    return (monday + timedelta(days=7)).strftime("%Y-%m-%d")


def window(week: str) -> tuple[datetime, datetime]:
    """[start, end) of the games an award covers: the seven days before its Monday, 6 a.m. to 6 a.m. ET."""
    end = datetime.fromisoformat(week).replace(hour=FREEZE_HOUR, tzinfo=ET)
    return end - timedelta(days=7), end


def span_label(week: str) -> str:
    """'Nov. 9-15' (the Monday to the Sunday of the award week)."""
    start, end = window(week)
    last = end - timedelta(days=1)

    def mon(d: datetime) -> str:
        m = d.strftime("%b")
        return m if m in ("May", "June", "July") else m + "."
    if start.month == last.month:
        return f"{mon(start)} {start.day}-{last.day}"
    return f"{mon(start)} {start.day} - {mon(last)} {last.day}"


# ---------------------------------------------------------------- the numbers

def _pair(stats: dict[str, Any], key: str) -> tuple[int, int]:
    try:
        made, att = str(stats.get(key) or "").split("-")
        return int(made), int(att)
    except ValueError:
        return 0, 0


def ts_pct(pts: int, fga: int, fta: int) -> float:
    shots = 2 * (fga + 0.44 * fta)
    return pts / shots if shots else 0.0


def _when(g: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(g["date"].replace("Z", "+00:00"))


def _short(side: dict[str, Any], teams: dict[str, Any]) -> str:
    from .today import school
    t = teams.get(str(side.get("espn_id") or ""))
    return t.short if t else school(side.get("name"))


def nights(boxes: dict[str, dict[str, Any]], games: Iterable[dict[str, Any]], teams: Iterable[Any],
           start: datetime, end: datetime, skip_opp: set[str] = frozenset()) -> list[dict[str, Any]]:
    """Every qualifying shooting night by one of `teams` in [start, end), with the line the award prints.
    Nights against an opponent in `skip_opp` (the power conferences) don't count."""
    ours = {t.espn_id: t for t in teams}
    out = []
    for g in games:
        if not g.get("completed") or not (start <= _when(g) < end):
            continue
        box = boxes.get(g["game_id"])
        if not box:
            continue
        for side, other in (("home", "away"), ("away", "home")):
            me, op = g[side], g[other]
            tid = str(me.get("espn_id") or "")
            if tid not in ours or me.get("score") is None or op.get("score") is None or str(op.get("espn_id") or "") in skip_opp:
                continue
            row = next((t for t in box.get("teams") or [] if str(t.get("espn_id")) == tid), None)
            if not row:
                continue
            st = row.get("stats") or {}
            fgm, fga = _pair(st, "fieldGoalsMade-fieldGoalsAttempted")
            tpm, tpa = _pair(st, "threePointFieldGoalsMade-threePointFieldGoalsAttempted")
            ftm, fta = _pair(st, "freeThrowsMade-freeThrowsAttempted")
            if fga < MIN_FGA:
                continue
            pts = int(me["score"])
            site = "neutral" if g.get("neutral_site") else side
            mates = [p for p in box.get("players") or [] if str(p.get("team_espn_id")) == tid and not p.get("dnp")]
            bright = max((p for p in mates if (p.get("fga") or 0) >= 4 and p["fgm"] * 2 >= p["fga"]),
                         key=lambda p: (p["fgm"] / p["fga"], p["fgm"], p.get("pts") or 0), default=None)
            out.append({
                "game_id": g["game_id"], "date": g["date"], "team_id": tid, "key": ours[tid].key, "team": ours[tid].short,
                "opp": _short(op, ours), "opp_key": opp_t.key if (opp_t := ours.get(str(op.get("espn_id") or ""))) else None,
                "site": site, "pts": pts, "opp_pts": int(op["score"]), "won": pts > int(op["score"]),
                "fgm": fgm, "fga": fga, "tpm": tpm, "tpa": tpa, "ftm": ftm, "fta": fta,
                "misses": (fga - fgm) + (fta - ftm), "ts": round(ts_pct(pts, fga, fta), 4),
                "fg_pct": round(100 * fgm / fga, 1) if fga else 0.0,
                "bright": {"name": bright["name"], "espn_id": str(bright.get("espn_id") or ""), "fgm": bright["fgm"],
                           "fga": bright["fga"], "pts": bright.get("pts") or 0} if bright else None,
            })
    return out


def ranked(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Worst first: lowest true shooting, then most misses, then the earlier game."""
    return sorted(cands, key=lambda c: (c["ts"], -c["misses"], c["date"], c["game_id"]))


# ---------------------------------------------------------------- the write-up

def _pick(options: list[str], seed: str, salt: str) -> str:
    h = int(hashlib.sha1(f"{seed}|{salt}".encode()).hexdigest(), 16)
    return options[h % len(options)]


def _where(c: dict[str, Any]) -> str:
    return {"home": f"at home against {c['opp']}", "away": f"at {c['opp']}", "neutral": f"against {c['opp']} on a neutral floor"}[c["site"]]


def _score(c: dict[str, Any]) -> str:
    hi, lo = max(c["pts"], c["opp_pts"]), min(c["pts"], c["opp_pts"])
    return f"{hi}-{lo}"


def line(c: dict[str, Any]) -> str:
    """The box score line: '16-58 FG (27.6%), 6-23 3PT, 15-18 FT'."""
    return f"{c['fgm']}-{c['fga']} FG ({c['fg_pct']:.1f}%), {c['tpm']}-{c['tpa']} 3PT, {c['ftm']}-{c['fta']} FT"


def worst_part(c: dict[str, Any]) -> str:
    """Which part of the night the write-up dwells on."""
    if c["tpa"] >= 15 and c["tpm"] / c["tpa"] < 0.22:
        return "three"
    if c["fta"] >= 12 and c["ftm"] / c["fta"] < 0.6:
        return "line"
    return "floor"


HEADLINES = {
    "three": ["The three-point line was more of a suggestion", "Long-range forecast: cloudy", "From deep, mostly echoes"],
    "line": ["Free throws, in name only", "The charity stripe kept the change", "Fifteen feet, no waiting"],
    "floor": ["The rim had other plans", "Iron, mostly", "A long night for the nets"],
}

LEDES_LOSS = [
    "{team} took {fga} shots {where} and made {fgm} of them. The scoreboard operator handled it with real professionalism. {opp} won {score}.",
    "Somewhere a rim is still humming. {team} shot {fg_pct}% {where}, {fgm} for {fga}, in a {score} loss.",
    "{team} went {fgm} for {fga} {where}. The ball saw a lot of iron, a little net and, by the end, a {score} final in {opp}'s favor.",
]
LEDES_WIN = [
    "{team} went {fgm} for {fga} {where} and won anyway, {score}. Style points are not on the standings page, and nobody in that locker room is asking for them.",
    "A win is a win. {team} beat {opp} {score} while shooting {fg_pct}% from the floor, proof that defense travels even when the jumper stays home.",
    "{team} shot {fg_pct}% {where} and still walked out with a {score} win, which is the most basketball sentence we will write all week.",
]
PARTS = {
    "three": ["From three it was {tpm} for {tpa}. The nets on that end got the night off and did not complain.",
              "From beyond the arc: {tpm} for {tpa}. Every one of the misses was a good look somewhere in the multiverse."],
    "line": ["At the line, {ftm} for {fta}. Free throws are free in name only.",
             "Free throws: {ftm} for {fta}. Fifteen feet, no defense, and still the rim said no thank you."],
    "floor": ["{misses} missed shots in all, free throws included. That is a lot of bricks for one night, and we would know.",
              "Counting free throws, {misses} shots did not go in. The building's maintenance crew has been notified, as a courtesy."],
}
CLOSERS = [
    "Every team has a night like this. The good ones shrug and get the next one.",
    "Shooters shoot. This group will be back in the gym before the trophy is cold.",
    "Hold the trophy loosely. It is made of brick, and it moves on next Monday.",
]


def write_up(c: dict[str, Any]) -> dict[str, Any]:
    """Headline and paragraphs, deadpan and kind: about the shooting, never the shooters."""
    seed = c["game_id"] + c["team_id"]
    part = worst_part(c)
    vals = {**c, "where": _where(c), "score": _score(c), "fg_pct": f"{c['fg_pct']:.1f}"}
    lede = _pick(LEDES_WIN if c["won"] else LEDES_LOSS, seed, "lede").format(**vals)
    middle = _pick(PARTS[part], seed, "part").format(**vals)
    paras = [lede, middle]
    b = c.get("bright")
    if b:
        paras.append(f"Bright spot: {b['name']} went {b['fgm']} for {b['fga']} and scored {b['pts']}. Somebody brought the touch.")
    paras.append(_pick(CLOSERS, seed, "close"))
    return {"headline": _pick(HEADLINES[part], seed, "head"), "paragraphs": paras, "part": part}


def social_text(a: dict[str, Any], league_short: str) -> str:
    """One post per conference: who, the line, a deadpan sign-off. The poster adds the hashtags."""
    w = a["winner"]
    res = f"{'won' if w['won'] else 'lost'} {_score(w)} {_where(w).replace('at home against', 'vs.')}"
    also = f"{w['ftm']}-{w['fta']} at the line" if worst_part(w) == "line" else f"{w['tpm']}-{w['tpa']} from three"
    return (f"\U0001F9F1 {league_short} Brick of the Week, {span_label(a['week'])}: {w['team']} "
            f"went {w['fgm']}-{w['fga']} from the floor and {also}, and {res}. {a['headline']}.")


# ---------------------------------------------------------------- the award

def award(week: str, boxes: dict[str, dict[str, Any]], games: list[dict[str, Any]], teams: Iterable[Any],
          skip_opp: set[str] | None = None) -> dict[str, Any] | None:
    start, end = window(week)
    order = ranked(nights(boxes, games, teams, start, end, power_ids() if skip_opp is None else skip_opp))
    if not order:
        return None
    w = order[0]
    wu = write_up(w)
    return {"week": week, "span": span_label(week), "winner": w, "line": line(w), "headline": wu["headline"],
            "paragraphs": wu["paragraphs"], "runners_up": [{**r, "line": line(r)} for r in order[1:3]],
            "candidates": len(order), "rule": {"min_fga": MIN_FGA, "stat": "true shooting", "skips": list(POWER)}}


def ready(week: str, games: list[dict[str, Any]], boxes: dict[str, Any], teams: Iterable[Any], now: datetime) -> bool:
    """Freeze once the week is over and every finished game has its box score (or by Monday noon regardless)."""
    start, end = window(week)
    if now < end:
        return False
    if now >= end.replace(hour=LATE_HOUR):
        return True
    ids = {t.espn_id for t in teams}
    return all(g["game_id"] in boxes for g in games if g.get("completed") and start <= _when(g) < end
               and ids & {str(g["home"].get("espn_id")), str(g["away"].get("espn_id"))})


def weeks(d: Path = BRICK_DIR) -> list[str]:
    return sorted(f.stem for f in d.glob("20??-??-??.json")) if d.exists() else []


def load(week: str, d: Path = BRICK_DIR) -> dict[str, Any] | None:
    f = d / f"{week}.json"
    return json.loads(f.read_text()) if f.exists() else None


def for_issue(day: str, d: Path = BRICK_DIR) -> dict[str, Any] | None:
    """The award announced in the week of a newsletter dated `day` (the latest Monday on or before it)."""
    try:
        when = datetime.fromisoformat(day)
    except ValueError:
        return None
    monday = (when - timedelta(days=when.weekday())).strftime("%Y-%m-%d")
    return load(monday, d)


def freeze(boxes: dict[str, dict[str, Any]], games: list[dict[str, Any]], teams: Iterable[Any], now: datetime,
           d: Path = BRICK_DIR) -> list[str]:
    """Write every finished award week not yet on disk (from FIRST_WEEK on). Frozen files are never rewritten,
    so a late stat correction can't take a trophy back. Returns the weeks written."""
    teams = list(teams)
    done = set(weeks(d))
    wrote = []
    wk = FIRST_WEEK
    current = week_of(now)
    while wk < current:
        if wk not in done and ready(wk, games, boxes, teams, now):
            a = award(wk, boxes, games, teams)
            if a:
                a["frozen_at"] = now.astimezone(ET).isoformat(timespec="minutes")
                d.mkdir(parents=True, exist_ok=True)
                (d / f"{wk}.json").write_text(json.dumps(a, indent=1) + "\n")
                wrote.append(wk)
        wk = (datetime.fromisoformat(wk) + timedelta(days=7)).strftime("%Y-%m-%d")
    return wrote


def watch(boxes: dict[str, dict[str, Any]], games: list[dict[str, Any]], teams: Iterable[Any], now: datetime) -> dict[str, Any] | None:
    """Brick watch: the leader of the week in progress, games so far. Not an award until Monday."""
    wk = week_of(now)
    a = award(wk, boxes, games, teams)
    if a:
        a["live"] = True
    return a
