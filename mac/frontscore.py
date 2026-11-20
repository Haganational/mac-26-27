"""The Bricks Score: which final leads the cover and each edition's front page (Matthew, Nov 16 2026: "blend").

A final's score is the sum of four parts, plus the home weight:

  upset   0-40  4 per point of closing spread the underdog won by; with no line, the rating gap
                when the lower-rated team won (1 per 8 places, at most 25)
  stakes  0-40  our team's rating rank (25 for No. 1, 0 past 175), +15 when one of ours beats a
                top-60 team from outside our editions
  drama   0-20  15 for a one-possession game, 10 within 6, 5 within 10; +5 for overtime
  home    0-20  Ohio 20, Akron and Kent State 15, Cleveland State 12, the rest of the MAC 8,
                the rest of the Horizon 4 (the larger side counts)
  rout    -25   for a 30-point win, so exhibitions against non-D-I teams don't lead

Floors on the newest night: Ohio is in the top three whenever it played, Akron, Kent State and
Cleveland State in the top six, and the cover keeps at least one MAC game in its top six.

On an edition's own front the home weights count only for that edition's teams (Ohio, Akron and
Kent on the MAC front, Cleveland State on the Horizon front); the other 25 fronts are neutral.
"""
from __future__ import annotations

import re
from datetime import date as Date, timedelta
from typing import Any, Callable

from . import atlarge, cards
from .den import load_games

HOME_TEAM = {"ohio": 20, "akron": 15, "kent-state": 15, "cleveland-state": 12}
HOME_CONF = {"mac": 8, "horizon": 4}
TOP3 = ("ohio",)
TOP6 = ("akron", "kent-state", "cleveland-state")
ROUT = 30
POOL_DAYS = 2  # finals from the newest night and the one before are scored; older ones fall back to newest-first

_GAME = re.compile(r"games/(\d+)\.html")


def game_id(href: str) -> str | None:
    m = _GAME.search(href or "")
    return m.group(1) if m else None


class Scorer:
    """Scores finals from the collector's schedule files, closing spreads and model ratings."""

    def __init__(self, games: dict[str, dict[str, Any]] | None = None, ratings: dict[str, Any] | None = None,
                 spreads: Callable[[str], list[dict[str, Any]]] | None = None) -> None:
        self.games = games if games is not None else load_games(cards.data_dirs())
        r = ratings if ratings is not None else (atlarge.load_ratings() or {})
        self.rank = {str(t["id"]): t.get("rk_adj_em") for t in r.get("teams", []) if t.get("rk_adj_em")}
        self._spreads = spreads or cards.closing_spreads
        self._by_day: dict[str, list[dict[str, Any]]] = {}

    def _rk(self, espn_id: Any) -> int:
        return int(self.rank.get(str(espn_id)) or 365)

    def spreads(self, day: str) -> list[dict[str, Any]]:
        if day not in self._by_day:
            try:
                self._by_day[day] = self._spreads(day)
            except (OSError, ValueError):
                self._by_day[day] = []
        return self._by_day[day]

    def line(self, g: dict[str, Any], day: str) -> dict[str, Any] | None:
        keys = {g["home"].get("key"), g["away"].get("key")} - {None}
        if not keys:
            return None
        for s in self.spreads(day):
            ks = {s.get("fav_key"), s.get("dog_key")} - {None}
            if ks and ks <= keys:
                return s
        return None

    def home_weight(self, g: dict[str, Any], edition: str | None = None) -> int:
        best = 0
        for side in ("home", "away"):
            tl = cards.team_of(g[side].get("espn_id"))
            if not tl:
                continue
            t, lg = tl
            if edition is None:
                w = max(HOME_TEAM.get(t.key, 0), HOME_CONF.get(lg.key, 0))
            else:
                w = HOME_TEAM.get(t.key, 0) if lg.key == edition else 0
            best = max(best, w)
        return best

    def score(self, gid: str, edition: str | None = None) -> dict[str, Any] | None:
        g = self.games.get(str(gid))
        if not g or not g.get("completed"):
            return None
        h, a = g["home"], g["away"]
        if h.get("score") is None or a.get("score") is None:
            return None
        day = cards.et_day(g["date"])
        win, los = (h, a) if (h.get("winner") or (h["score"] or 0) > (a["score"] or 0)) else (a, h)
        margin = abs((h["score"] or 0) - (a["score"] or 0))
        ln = self.line(g, day)
        pts = 0.0
        if ln:
            if win.get("key") and win["key"] == ln.get("dog_key"):
                pts = float(ln["points"])
            elif not win.get("key") and los.get("key") and los["key"] == ln.get("fav_key"):
                pts = float(ln["points"])
        rw, rl = self._rk(win.get("espn_id")), self._rk(los.get("espn_id"))
        upset = min(40.0, pts * 4) if ln else min(25.0, max(0, rw - rl) / 8)
        ours_w, ours_l = cards.team_of(win.get("espn_id")), cards.team_of(los.get("espn_id"))
        our_rk = min([self._rk(s.get("espn_id")) for s in (h, a) if cards.team_of(s.get("espn_id"))] or [365])
        giant = 15 if ours_w and not ours_l and rl <= 60 else 0
        stakes = max(0.0, 25 * (1 - (our_rk - 1) / 175)) + giant
        ot = "OT" in (g.get("detail") or "")
        drama = (15 if margin <= 3 else 10 if margin <= 6 else 5 if margin <= 10 else 0) + (5 if ot else 0)
        home = self.home_weight(g, edition)
        rout = -25 if margin >= ROUT else 0
        total = upset + stakes + drama + home + rout
        keys = {s.get("key") for s in (h, a)} - {None}
        return {"score": round(total, 1), "day": day, "keys": keys, "margin": margin, "ot": ot,
                "upset": round(upset, 1), "stakes": round(stakes, 1), "drama": drama, "home": home, "rout": rout,
                "dog_pts": pts, "mac": any((cards.team_of(s.get("espn_id")) or (None, None))[1] is not None
                                          and cards.team_of(s.get("espn_id"))[1].key == "mac" for s in (h, a)),
                "why": why(pts, margin, ot, giant)}


def why(dog_pts: float, margin: int, ot: bool, giant: int) -> str:
    """The short reason chip beside the kicker."""
    if dog_pts >= 3:
        return f"{dog_pts:g}-point underdog"
    if giant:
        return "Beat a top-60 team"
    if ot:
        return "Overtime"
    if margin <= 3:
        return "One-possession game"
    return ""


def rank(stories: list[dict[str, Any]], scorer: Scorer | None, edition: str | None = None,
         href: str = "href") -> list[dict[str, Any]]:
    """Stories in front-page order: the scored finals of the newest two nights, best first with the floors
    applied, then everything else newest first (the order they came in). Adds "fs" (the score dict) to each."""
    if scorer is None:
        return list(stories)
    # Only the newest two nights are scored (reading closing lines is the slow part); find them from game dates first.
    day_of: dict[int, str] = {}
    for s in stories:
        s["fs"] = None
        gid = game_id(s.get(href, ""))
        g = scorer.games.get(gid) if gid and s.get("kind", "recap") == "recap" else None
        if g and g.get("completed"):
            day_of[id(s)] = cards.et_day(g["date"])
    if not day_of:
        return list(stories)
    newest = max(day_of.values())
    cutoff = (Date.fromisoformat(newest) - timedelta(days=POOL_DAYS - 1)).isoformat()
    pool, rest = [], []
    for s in stories:
        if day_of.get(id(s), "") >= cutoff:
            s["fs"] = scorer.score(game_id(s.get(href, "")), edition)
        (pool if s["fs"] else rest).append(s)
    if not pool:
        return list(stories)
    newest = max(s["fs"]["day"] for s in pool)
    late: list[dict[str, Any]] = []
    # The newest slate always leads: every final from the newest night ranks ahead of the night before, which
    # follows in its own score order (Matthew, Nov 20 2026: "A game from Wednesday shouldn't be leading off our
    # page on Friday morning. We are timely"). A 10-point handicap let a Wednesday thriller top Thursday's finals.
    pool.sort(key=lambda s: (s["fs"]["day"] != newest, -s["fs"]["score"]))
    tonight = [s for s in pool if s["fs"]["day"] == newest]
    due: dict[int, int] = {}  # id(story) -> the last index it may sit at
    for st in tonight:
        if _home_counts(st, edition):
            if st["fs"]["keys"] & set(TOP3):
                due[id(st)] = 2
            elif st["fs"]["keys"] & set(TOP6):
                due[id(st)] = min(due.get(id(st), 5), 5)
    if edition is None and not any(st["fs"]["mac"] for st in pool[:6]) and not any(
            st["fs"]["mac"] for st in tonight if id(st) in due):
        mac = next((st for st in tonight if st["fs"]["mac"]), None)
        if mac is not None:
            due[id(mac)] = 5
    pool = floors(pool, due)
    late_and_rest = sorted(late + rest, key=lambda s: stories.index(s))
    return pool + late_and_rest


def floors(pool: list[dict[str, Any]], due: dict[int, int]) -> list[dict[str, Any]]:
    """Keep the score order, except that each story in `due` sits no lower than its index there: at each
    place take the next story by score unless a floored story would otherwise run out of room."""
    rem, out = list(pool), []
    while rem:
        p = len(out)
        req = sorted((s for s in rem if id(s) in due), key=lambda s: (due[id(s)], rem.index(s)))
        tight = any(i + 1 >= due[id(r)] - p + 1 for i, r in enumerate(req))
        pick = req[0] if tight else rem[0]
        rem.remove(pick)
        out.append(pick)
    return out


def _home_counts(s: dict[str, Any], edition: str | None) -> bool:
    """Floors follow the weights: on an edition front they only apply to that edition's own home teams."""
    return edition is None or s["fs"]["home"] > 0


def home_desk(scorer: Scorer, today: str) -> list[dict[str, Any]]:
    """The cover's home desk, Ohio first, then Akron, Kent State and Cleveland State: each team's
    result from the last three days (or None) and its next game (or None)."""
    rows = []
    for key in list(TOP3) + list(TOP6):
        mine = sorted((g for g in scorer.games.values() if key in (g["home"].get("key"), g["away"].get("key"))),
                      key=lambda g: g["date"])
        past = [g for g in mine if g.get("completed")]
        nxt = next((g for g in mine if not g.get("completed") and g.get("status") not in ("STATUS_POSTPONED", "STATUS_CANCELED")), None)
        last = past[-1] if past and cards.et_day(past[-1]["date"]) >= (Date.fromisoformat(today) - timedelta(days=3)).isoformat() else None
        rows.append({"key": key, "last": last, "next": nxt})
    return rows


def around(scorer: Scorer, exclude: str, today: str, most: int = 3) -> list[dict[str, Any]]:
    """The national top finals from the newest night (up to today), leaving out games with an `exclude`
    team, for the "Around the mid-majors" strip on an edition front. Only games whose box score is in,
    so the link lands on a recap. href is relative to the site root."""
    from .hub import game_owner
    finals = [g for g in scorer.games.values() if g.get("completed") and cards.et_day(g["date"]) <= today]
    if not finals:
        return []
    newest = max(cards.et_day(g["date"]) for g in finals)
    out = []
    for g in finals:
        if cards.et_day(g["date"]) != newest:
            continue
        sides = [cards.team_of(g[s].get("espn_id")) for s in ("home", "away")]
        if any(tl and tl[1].key == exclude for tl in sides):
            continue
        owner = game_owner(g["home"].get("espn_id"), g["away"].get("espn_id"))
        if owner is None or not (owner.data_dir / "boxscores" / f"{g['game_id']}.json").exists():
            continue
        fs = scorer.score(g["game_id"])
        if not fs:
            continue
        h, a = g["home"], g["away"]
        win, los = (h, a) if (h["score"] or 0) > (a["score"] or 0) else (a, h)
        out.append({"href": f"{owner.path}games/{g['game_id']}.html", "league": owner.short, "key": owner.key,
                    "text": f"{_name(win)} {win['score']}, {_name(los)} {los['score']}{' (OT)' if fs['ot'] else ''}",
                    "why": fs["why"], "score": fs["score"]})
    out.sort(key=lambda x: -x["score"])
    return out[:most]


def _name(side: dict[str, Any]) -> str:
    tl = cards.team_of(side.get("espn_id"))
    if tl:
        return tl[0].short
    from .today import school
    return school(side.get("name") or "") or side.get("abbr") or ""
