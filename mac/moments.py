"""Moments: what mattered in a game, read from the play-by-play (Matthew, Nov 19 2026).

A box score says who scored. The play-by-play says *when*, and that is where the story is. ESPN's
summary feed (the one call per D-I game ncaa.enrich_season already makes) logs every scoring play with
the running score, the clock and the scorer, and for most games ESPN's own win probability after each
play. We keep the scoring plays in the book (book.py, key "e") and work out, per game:

  for_good   the basket that put the winner ahead for good, and whether it came in crunch time
  swing      the single scoring play that moved win probability the most (ESPN's numbers when the feed
             has them, else our own: score margin, time left and the closing spread)
  run        the longest unanswered run, with the score before and after
  comeback   the winner's biggest deficit, and the loser's blown lead
  drought    each side's longest stretch without a field goal
  hot_half   a player who scored most of his points in one half
  flips      for any spread or total: the play that last flipped it, e.g. the late free throws that
             covered, or the three that pushed a game over (Tops and Bottoms' bad beats)

Season highs come from the book's player lines, so they cost nothing either.

Coverage, checked Nov 19 2026 against the book: 958 of the season's first 963 D-I games had a full
play-by-play, and every conference was at 95% or better (SWAC 60 of 60, MEAC 42 of 42). A game without
one simply has no moments, and every writer falls back to the box score the way it always has.

Everything here is arithmetic on the feed. Nothing is generated, and a sentence whose number is
missing is left out.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date as date_cls, timedelta
from typing import Any, Iterable

HALF = 1200
OT = 300
SIGMA = 11.5  # final-margin spread (points) for a full game, for our own win probability
CRUNCH = 300  # last five minutes of the final period
LATE = 180  # a flip in the last three minutes is a late flip
KINDS = {"3": "three-pointer", "dunk": "dunk", "layup": "layup", "tip": "tip-in", "hook": "hook shot",
         "jumper": "jumper", "fg": "basket", "ft": "free throw"}


# ---------------------------------------------------------------- reading the feed


def _secs(period: int, clock: str) -> float:
    try:
        m, s = str(clock).split(":")
        left = int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        left = 0.0
    if period <= 2:
        return (period - 1) * HALF + (HALF - left)
    return 2 * HALF + (period - 3) * OT + (OT - left)


def period_end(per: int) -> float:
    return per * HALF if per <= 2 else 2 * HALF + (per - 2) * OT


def _kind(play: dict[str, Any], pts: int) -> str:
    if pts == 3:
        return "3"
    if pts == 1:
        return "ft"
    t = ((play.get("type") or {}).get("text") or "").lower() + " " + (play.get("text") or "").lower()
    for word, k in (("dunk", "dunk"), ("layup", "layup"), ("lay up", "layup"), ("tip", "tip"), ("hook", "hook"),
                    ("jump", "jumper")):
        if word in t:
            return k
    return "fg"


def events_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Every scoring play: time, period, running score, scorer, shot kind, and ESPN's home win
    probability (per mille) just before and just after it when the feed has one."""
    wp = {}
    for w in summary.get("winprobability") or []:
        if w.get("playId") is not None and w.get("homeWinPercentage") is not None:
            wp[str(w["playId"])] = round(1000 * float(w["homeWinPercentage"]))
    out: list[dict[str, Any]] = []
    hs = as_ = 0
    last_wp = None
    for play in summary.get("plays") or []:
        h = play.get("homeScore")
        a = play.get("awayScore")
        h = hs if h is None else int(h)
        a = as_ if a is None else int(a)
        w = wp.get(str(play.get("id"))) if wp else None
        dh, da = h - hs, a - as_
        if (dh > 0) != (da > 0) and max(dh, da) in (1, 2, 3) and min(dh, da) == 0:
            pts = dh or da  # the running score says who scored; ESPN's team tag is sometimes the other bench
            per = int((play.get("period") or {}).get("number") or 1)
            pids = [p["athlete"]["id"] for p in play.get("participants") or [] if (p.get("athlete") or {}).get("id")]
            out.append({"t": round(_secs(per, (play.get("clock") or {}).get("displayValue") or "0:00"), 1), "per": per,
                        "h": h, "a": a, "pid": str(pids[0]) if pids else None, "kind": _kind(play, pts),
                        "wb": last_wp if last_wp is not None else w, "wa": w})
        hs, as_ = h, a  # a corrected (lowered) score resets the count instead of scoring a play
        if w is not None:
            last_wp = w
    if wp and not all(e["wa"] is not None and e["wb"] is not None for e in out):
        for e in out:  # a partial win-probability feed is worse than none: use ours for the whole game
            e["wb"] = e["wa"] = None
    return out


# ---------------------------------------------------------------- our own win probability


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def home_wp(margin: float, t: float, end: float, home_spread: float | None) -> float:
    """Chance the home team wins from a home `margin` at time t of a game ending at `end`."""
    left = max(0.0, end - t)
    frac = left / (2 * HALF)
    mu = margin + (-(home_spread or 0.0)) * frac
    sd = SIGMA * math.sqrt(frac)
    if sd < 0.3:
        return 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
    return _phi(mu / sd)


# ---------------------------------------------------------------- the moments


def _left_in_game(e: dict[str, Any], last_per: int) -> float:
    return period_end(last_per) - e["t"]


def when(e: dict[str, Any], last_per: int | None = None) -> str:
    """'with 41 seconds left', 'with 3:12 left in the first half', 'with 1:05 left in overtime'."""
    per = e["per"]
    left = max(0.0, period_end(per) - e["t"])
    secs = int(round(left))
    clock = f"{secs // 60}:{secs % 60:02d}"
    if per >= 3:
        ot = "overtime" if per == 3 else ("double overtime" if per == 4 else "triple overtime" if per == 5 else f"the {per - 2}th overtime")
        if secs <= 1:
            return f"at the end of {ot}"
        return f"with {secs} seconds left in {ot}" if secs < 60 else f"with {clock} left in {ot}"
    if per == 1:
        if secs <= 1:
            return "at the halftime buzzer"
        return f"with {clock} left in the first half" if secs >= 60 else f"with {secs} seconds left in the first half"
    if secs <= 1:
        return "at the buzzer" if last_per in (None, 2) else "at the end of regulation"
    if secs < 60:
        return f"with {secs} {'second' if secs == 1 else 'seconds'} left" + ("" if last_per in (None, 2) else " in regulation")
    return f"with {clock} left" + ("" if last_per in (None, 2) else " in regulation")


def window(t: float, per: int) -> str:
    """Where in the game a stretch sat, in words."""
    if per >= 3:
        return "in overtime"
    into = t - (per - 1) * HALF
    half = "first half" if per == 1 else "second half"
    if into < 400:
        return f"early in the {half}"
    if into < 800:
        return f"midway through the {half}"
    return f"late in the {half}"


def analyze(game: dict[str, Any], home_spread: float | None = None, total: float | None = None) -> dict[str, Any] | None:
    """The moments of one decoded book game (book.decode_game), or None without a play-by-play."""
    ev = game.get("events") or []
    if len(ev) < 10:
        return None
    names = {str(p["espn_id"]): p.get("name") for p in game.get("players", []) if p.get("name")}
    last_per = max(e["per"] for e in ev)
    end = period_end(last_per)
    fh, fa = ev[-1]["h"], ev[-1]["a"]
    if fh == fa:
        return None
    win = "home" if fh > fa else "away"
    lose = "away" if win == "home" else "home"

    def mine(e: dict[str, Any], side: str) -> tuple[int, int]:
        return (e["h"], e["a"]) if side == "home" else (e["a"], e["h"])

    def scorer(e: dict[str, Any]) -> str | None:
        return names.get(str(e.get("pid"))) if e.get("pid") else None

    def side_of(i: int) -> str:
        prev = ev[i - 1] if i else {"h": 0, "a": 0}
        return "home" if ev[i]["h"] > prev["h"] else "away"

    def play(i: int) -> dict[str, Any]:
        e = ev[i]
        return {"i": i, "t": e["t"], "per": e["per"], "side": side_of(i), "who": scorer(e), "pid": e.get("pid"),
                "shot": KINDS.get(e["kind"], "basket"), "kind": e["kind"], "h": e["h"], "a": e["a"],
                "when": when(e, last_per), "left": round(end - e["t"], 1)}

    out: dict[str, Any] = {"winner": win, "final": [fh, fa], "periods": last_per}

    # Ahead for good: the last play after which the winner led and before which it did not.
    for_good = None
    for i, e in enumerate(ev):
        us, them = mine(e, win)
        pu, pt = mine(ev[i - 1], win) if i else (0, 0)
        if us > them and pu <= pt:
            for_good = i
    if for_good is not None:
        p = play(for_good)
        pu, pt = mine(ev[for_good - 1], win) if for_good else (0, 0)
        p["was"] = "tied" if pu == pt else "behind"
        p["crunch"] = p["left"] <= CRUNCH
        out["for_good"] = p

    # Lead changes and ties.
    changes = ties = 0
    leader = None
    for e in ev:
        d = e["h"] - e["a"]
        now = "home" if d > 0 else "away" if d < 0 else None
        if now is None:
            ties += 1
        elif leader is not None and now != leader:
            changes += 1
        if now:
            leader = now
    out["lead_changes"], out["ties"] = changes, ties

    # Biggest leads, so the winner's deficit (a comeback) and the loser's blown lead.
    best = {"home": (0, None), "away": (0, None)}
    for i, e in enumerate(ev):
        for s in ("home", "away"):
            us, them = mine(e, s)
            if us - them > best[s][0]:
                best[s] = (us - them, i)
    out["max_lead"] = {s: best[s][0] for s in best}
    if best[lose][0] >= 10:
        out["comeback"] = {"deficit": best[lose][0], **play(best[lose][1])}

    # The longest unanswered run.
    run = None
    i = 0
    while i < len(ev):
        s = side_of(i)
        j = i
        while j + 1 < len(ev) and side_of(j + 1) == s:
            j += 1
        before = mine(ev[i - 1], s) if i else (0, 0)
        after = mine(ev[j], s)
        pts = after[0] - before[0]
        if run is None or pts > run["pts"] or (pts == run["pts"] and ev[j]["t"] > run["t1"]):
            run = {"side": s, "pts": pts, "before": list(before), "after": list(after), "t0": ev[i]["t"], "t1": ev[j]["t"],
                   "per": ev[i]["per"], "per1": ev[j]["per"], "where": window((ev[i]["t"] + ev[j]["t"]) / 2, ev[i]["per"])}
        i = j + 1
    if run and run["pts"] >= 8:
        out["run"] = run

    # Field-goal droughts, from tip or a basket to the next basket (or the horn).
    dr = {}
    for s in ("home", "away"):
        fgs = [ev[k]["t"] for k in range(len(ev)) if side_of(k) == s and ev[k]["kind"] != "ft"]
        marks = [0.0] + fgs + [end]
        gaps = [(marks[k + 1] - marks[k], marks[k]) for k in range(len(marks) - 1)]
        if gaps:
            g, t0 = max(gaps)
            per0 = 1 if t0 < HALF else 2 if t0 < 2 * HALF else 3 + int((t0 - 2 * HALF) // OT)
            dr[s] = {"secs": round(g), "t0": t0, "where": window(t0 + g / 2, per0 if t0 + g <= period_end(per0) else per0)}
    out["drought"] = dr

    # Points by half, per player.
    halves: dict[str, list[int]] = {}
    for k, e in enumerate(ev):
        pid = e.get("pid")
        if not pid:
            continue
        prev = ev[k - 1] if k else {"h": 0, "a": 0}
        pts = (e["h"] - prev["h"]) + (e["a"] - prev["a"])
        halves.setdefault(str(pid), [0, 0])[0 if e["per"] == 1 else 1] += pts
    hot = None
    for pid, (a, b) in halves.items():
        tot = a + b
        big = max(a, b)
        if big >= 15 and big >= 0.7 * tot and pid in names and (hot is None or big > hot["pts"]):
            hot = {"pid": pid, "who": names[pid], "pts": big, "of": tot, "half": "first" if a >= b else "second",
                   "ot": last_per > 2}
    if hot:
        out["hot_half"] = hot

    # The swing: ESPN's win probability if the feed had it, else ours.
    espn = all(e.get("wa") is not None and e.get("wb") is not None for e in ev)
    swing = None
    for k, e in enumerate(ev):
        prev = ev[k - 1] if k else {"h": 0, "a": 0}
        if espn:
            before, after = e["wb"] / 1000, e["wa"] / 1000
        else:
            before = home_wp(prev["h"] - prev["a"], e["t"], end, home_spread)
            after = home_wp(e["h"] - e["a"], e["t"], end, home_spread)
        s = side_of(k)
        gain = (after - before) if s == "home" else (before - after)
        if swing is None or gain > swing["gain"]:
            swing = {"gain": round(gain, 3), **play(k)}
    if swing and swing["gain"] >= 0.08:
        swing["source"] = "espn" if espn else "model"
        out["swing"] = swing

    if home_spread is not None:
        f = flip(ev, "side", "home", float(home_spread))
        if f:
            out["cover_flip"] = {**play(f["i"]), "result": f["result"], "late": f["left"] <= LATE}
    if total is not None:
        f = flip(ev, "total", "over", float(total))
        if f and f["result"] == "win":
            out["over_cross"] = {**play(f["i"]), "late": f["left"] <= LATE, "total": total}
    return out


def flip(ev: list[dict[str, Any]], kind: str, side: str, line: float) -> dict[str, Any] | None:
    """The play that last flipped a bet to how it finished: kind 'side' (side home/away, line on that side)
    or 'total' (side over/under). None if it never changed, or the game had no scoring plays."""
    if not ev:
        return None

    def status(h: int, a: int) -> int:
        if kind == "side":
            mine, theirs = (h, a) if side == "home" else (a, h)
            d = mine + line - theirs
        else:
            d = (h + a - line) * (1 if side == "over" else -1)
        return (d > 0) - (d < 0)

    final = status(ev[-1]["h"], ev[-1]["a"])
    cur = status(0, 0)
    last = None
    for i, e in enumerate(ev):
        s = status(e["h"], e["a"])
        if s != cur and s == final:
            last = i
        cur = s
    if last is None:
        return None
    end = period_end(max(e["per"] for e in ev))
    return {"i": last, "left": end - ev[last]["t"], "result": "win" if final > 0 else "loss" if final < 0 else "push"}


# ---------------------------------------------------------------- season highs


def season_highs(games: Iterable[dict[str, Any]]) -> dict[str, list[tuple[str, int]]]:
    """pid -> [(date, points)] from decoded book games, oldest first."""
    out: dict[str, list[tuple[str, int]]] = {}
    for g in sorted(games, key=lambda g: g.get("date") or ""):
        for p in g.get("players", []):
            if p.get("pts") is not None and not p.get("dnp"):
                out.setdefault(str(p["espn_id"]), []).append((g.get("date") or "", int(p["pts"])))
    return out


def high_note(pid: str, pts: int, date: str, highs: dict[str, list[tuple[str, int]]], min_games: int = 3) -> str | None:
    """'season high' when the points beat every earlier game this season (three or more of them)."""
    prior = [p for d, p in highs.get(str(pid), []) if d < date]
    if len(prior) >= min_games and pts > max(prior) and pts >= 12:
        return "season high"
    return None


# ---------------------------------------------------------------- the words


def _pick(options: list[str], seed: str) -> str:
    return options[int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16) % len(options)]


def _poss(name: str) -> str:
    return name + ("'" if name.endswith("s") else "'s")


def _score(us: int, them: int) -> str:
    return f"{us}-{them}"


def _pts(n: int) -> str:
    return f"{n}-point"


def _run_phrase(run: dict[str, Any], team: str) -> str:
    """The run's effect from the running team's side, in margins so nobody has to read a score backwards."""
    b, a = run["before"], run["after"]
    d0, d1 = b[0] - b[1], a[0] - a[1]
    if d0 == 0:
        return f"from {b[0]}-all to a {_pts(d1)} lead" if b[0] else f"to open the game"
    if d0 < 0:
        if d1 > 0:
            return f"turning a {_pts(-d0)} deficit into a {_pts(d1)} lead"
        if d1 == 0:
            return f"erasing a {_pts(-d0)} deficit to tie it at {a[0]}"
        return f"cutting a {_pts(-d0)} deficit to {-d1}"
    return f"stretching a {_pts(d0)} lead to {d1}"


def recap_lines(m: dict[str, Any] | None, names: dict[str, str], seed: str = "", most: int = 3) -> list[str]:
    """Up to `most` sentences on how the game turned, most telling first. names: {'home': .., 'away': ..}."""
    if not m:
        return []
    win, lose = m["winner"], ("away" if m["winner"] == "home" else "home")
    wn, ln = names.get(win, ""), names.get(lose, "")
    fw, fl = (m["final"][0], m["final"][1]) if win == "home" else (m["final"][1], m["final"][0])
    margin = fw - fl
    out: list[str] = []
    fg = m.get("for_good")
    if fg and fg.get("who") and fg["crunch"]:
        score = _score(*((fg["h"], fg["a"]) if win == "home" else (fg["a"], fg["h"])))
        if fg["left"] <= 1:
            out.append(f"{fg['who']} won it with a {fg['shot']} {fg['when']}, {score}.")
        else:
            verb = "put" if fg["was"] == "behind" else "broke the tie and put"
            lead = _pick([f"{_poss(fg['who'])} {fg['shot']} {fg['when']} {verb} {wn} ahead for good, {score}.",
                          f"{wn} went ahead for good on {_poss(fg['who'])} {fg['shot']} {fg['when']}, {score}."], seed + "fg")
            out.append(lead)
    elif m.get("swing") and m["swing"].get("who") and margin <= 10 and m["swing"]["left"] <= 600:
        sw = m["swing"]
        us = names.get(sw["side"], "")
        score = _score(*((sw["h"], sw["a"]) if sw["side"] == "home" else (sw["a"], sw["h"])))
        out.append(f"The biggest swing was {_poss(sw['who'])} {sw['shot']} {sw['when']}, which made it {score} {us}.")
    run = m.get("run")
    if run and (run["pts"] >= 10 or (run["pts"] >= 8 and margin <= 10)):
        team = names.get(run["side"], "")
        phrase = _run_phrase(run, team)
        if run["side"] == win:
            out.append(_pick([f"{team} took control with a {run['pts']}-0 run {run['where']}, {phrase}.",
                              f"The game turned on a {run['pts']}-0 {team} run {run['where']}, {phrase}."], seed + "run"))
        else:
            out.append(f"{team} made a {run['pts']}-0 run {run['where']}, {phrase}, but could not hold it.")
    cb = m.get("comeback")
    if cb:
        out.append(f"{wn} trailed by {cb['deficit']} {cb['when']} and came all the way back." if cb["per"] >= 2
                   else f"{wn} fell behind by {cb['deficit']} in the first half and came all the way back.")
    if m.get("lead_changes", 0) >= 10:
        t = m.get("ties", 0)
        out.append(f"The lead changed hands {m['lead_changes']} times" + (f", and the game was tied {t} times." if t >= 3 else "."))
    dr = (m.get("drought") or {}).get(lose)
    if dr and dr["secs"] >= 360:
        mm, ss = divmod(dr["secs"], 60)
        out.append(f"{ln} went {mm}:{ss:02d} without a field goal {dr['where']}.")
    hot = m.get("hot_half")
    if hot:
        part = "in the first half" if hot["half"] == "first" else ("after halftime" if not hot["ot"] else "after halftime, overtime included")
        if hot["pts"] == hot["of"]:
            out.append(f"{hot['who']} scored all {hot['of']} of his points {part}.")
        else:
            out.append(f"{hot['who']} scored {hot['pts']} of his {hot['of']} points {part}.")
    return out[:most]


def cover_line(m: dict[str, Any] | None, names: dict[str, str], covered: str | None) -> str | None:
    """'Toledo covered the closing spread on Jane Doe's free throw with 8 seconds left.' Late flips only."""
    cf = (m or {}).get("cover_flip")
    if not cf or not cf["late"] or not cf.get("who") or cf["result"] == "push" or not covered:
        return None
    side = "home" if cf["result"] == "win" else "away"
    if names.get(side) != covered:
        return None
    return f"{covered} covered the closing spread on {_poss(cf['who'])} {cf['shot']} {cf['when']}."


def over_line(m: dict[str, Any] | None) -> str | None:
    oc = (m or {}).get("over_cross")
    if not oc or not oc["late"] or not oc.get("who"):
        return None
    return f"{_poss(oc['who'])} {oc['shot']} {oc['when']} pushed the game over the {oc['total']:g} total."


def short_line(m: dict[str, Any] | None, side: str, names: dict[str, str]) -> str | None:
    """One short spoken sentence for MidMaxx60, told from `side`'s view."""
    if not m:
        return None
    fg = m.get("for_good")
    won = m["winner"] == side
    if fg and fg["crunch"] and fg.get("who"):
        secs = int(round(fg["left"]))
        clock = "at the buzzer" if secs <= 1 else (f"with {secs} seconds left" if secs < 60 else f"with {secs // 60}:{secs % 60:02d} left")
        if fg["per"] >= 3:
            clock += " in overtime"
        if won:
            return f"{_poss(fg['who'])} {fg['shot']} {clock} won it."
        return f"{_poss(fg['who'])} {fg['shot']} {clock} beat them."
    run = m.get("run")
    if run and run["pts"] >= 12:
        team = names.get(run["side"], "")
        when_ = run["where"].replace("midway through", "in the middle of")
        if run["side"] == side and won:
            return f"A {run['pts']}-0 run {when_} did it."
        if run["side"] != side and not won:
            return f"{team} ran off {run['pts']} straight {when_}."
    cb = m.get("comeback")
    if cb and won and m["winner"] == side:
        return f"They came back from {cb['deficit']} down."
    return None


def anchor_moment(m: dict[str, Any] | None, side: str) -> tuple[str, dict[str, Any]] | None:
    """(situation, fill) for an anchor's moment aside, from `side`'s view. Team-level only, never a player."""
    if not m:
        return None
    won = m["winner"] == side
    fg = m.get("for_good")
    if fg and fg["crunch"]:
        return ("late_win" if won else "late_loss"), {"when": "at the buzzer" if fg["left"] <= 1 else "in the last five minutes"}
    cb = m.get("comeback")
    if cb:
        return ("comeback" if won else "collapse"), {"deficit": cb["deficit"]}
    run = m.get("run")
    if run and run["pts"] >= 12 and (run["side"] == side) == won:
        return ("run_win" if won else "run_loss"), {"run": f"{run['pts']}-0"}
    return None


# ---------------------------------------------------------------- loading from the book


class Book:
    """Lazy reader of the book's day files, so a page build only opens the days it needs."""

    def __init__(self, season: int | None = None):
        from .config import SEASON

        self.season = season or SEASON
        self._days: dict[str, dict[str, Any]] = {}
        self._highs: dict[str, list[tuple[str, int]]] | None = None

    def highs(self) -> dict[str, list[tuple[str, int]]]:
        """Every D-I player's points by game this season, read once per process."""
        if self._highs is None:
            from . import book

            try:
                self._highs = season_highs(book.load_games(self.season))
            except (OSError, ValueError):
                self._highs = {}
        return self._highs

    def _day(self, day: str) -> dict[str, Any]:
        if day not in self._days:
            from . import book

            path = book.games_dir(self.season) / f"{day}.json.gz"
            try:
                self._days[day] = book.read_gz(path) if path.exists() else {}
            except (OSError, ValueError):
                self._days[day] = {}
        return self._days[day]

    def game(self, gid: str, date: str | None) -> dict[str, Any] | None:
        from . import book

        if not date:
            return None
        day = str(date)[:10]
        try:  # the book keys days by the game's UTC date; look one day either side in case a caller used local time
            d0 = date_cls.fromisoformat(day)
            days = [day, (d0 + timedelta(days=1)).isoformat(), (d0 - timedelta(days=1)).isoformat()]
        except ValueError:
            days = [day]
        for d in days:
            g = self._day(d).get(str(gid))
            if g:
                return book.decode_game(str(gid), g)
        return None

    def moments(self, gid: str, date: str | None, home_spread: float | None = None, total: float | None = None) -> dict[str, Any] | None:
        g = self.game(gid, date)
        return analyze(g, home_spread, total) if g else None


_BOOK: Book | None = None


def shared() -> Book:
    global _BOOK
    if _BOOK is None:
        _BOOK = Book()
    return _BOOK


# ---------------------------------------------------------------- backfill


def backfill(season: int | None = None, limit: int = 200, workers: int = 4) -> dict[str, int]:
    """Games the book stored before scoring plays were kept get one more summary call, newest first,
    `limit` per run, so the backlog clears in a few collector runs and then this costs nothing."""
    from concurrent.futures import ThreadPoolExecutor

    import requests

    from . import book, pbp
    from .config import SEASON

    season = season or SEASON
    d = book.games_dir(season)
    if not d.exists():
        return {"fetched": 0, "missing": 0}
    todo = []
    for path in sorted(d.glob("*.json.gz"), reverse=True):
        for gid, g in book.read_gz(path).items():
            if "e" not in g:
                todo.append(gid)
    missing = len(todo)
    todo = todo[:limit]

    def one(gid: str):
        try:
            return gid, book.encode_game(pbp.fetch_game(gid))
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
            return gid, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        got = {gid: g for gid, g in pool.map(one, todo) if g is not None}
    book.save_games(season, got)
    return {"fetched": len(got), "missing": missing - len(got)}
