"""The Den: data for the games section (Daily Five, Pick 4, Bricksanity, Brick by Brick).

Built with the hub (mac/hub.py). Writes, into site/den/:

  slate-YYYY-MM-DD.json    one per ET date with a game involving our 67 schools, from the
                           season's first such date through today + DAYS_AHEAD
  results-YYYY-MM-DD.json  one per ET date with at least one final
  index.json               which dates have what

Past slates are rebuilt each run (averages strictly before the date, last line before tip),
so a visitor's old picks always have names to show.

Shapes (short keys only where noted)
------------------------------------
slate:   {date, generated_at,
          games: [{id, tip (ISO UTC, "2026-11-13T17:00Z"), tba (only when the tip time is TBA),
                   home: {key, id, short, abbr, edition, anchor}, away: {...},
                   win_home (0-1, 3 decimals, or null), worth: {home, away} or null}],
          players: [{id, name, team_id, pos, avg: {pts, reb, ast, blk, stl, min, g}}],
          defenses: [team_id, ...]}
         key/edition/anchor are null for a school we don't cover. anchor is the fictional
         AI anchor persona's name for that school (portrait: anchors/<key>.webp, Agent 3's call).
         players are everyone on our rosters in tonight's games plus anyone who has appeared
         in a box score for them; g = games played (not DNP); avg 1 decimal, 0s when g = 0.
results: {date, generated_at, complete,
          games: [{id, final: true, home_id, away_id, home_pts, away_pts, winner_id, win_home, worth}],
          players: {id: fantasy_pts}, stat: {id: [pts, reb, ast, blk, stl, min]},
          defenses: {team_id: pts}, shooting: {team_id: pct (0-1, 4 decimals)},
          bricks: {team_id: [makes, attempts]}, worst_shooter: team_id or null}
         complete = every game that day is final (or postponed/canceled) and every final
         involving our schools has a box score. Only finals are in games; only players on our
         67 who played are in players/stat; defenses/shooting cover our 67 with a box score.
index:   {generated_at, today, dates: [{date, slate: bool, results: bool, complete: bool}]}

Scoring (templates/static/den.js mirrors every function marked "JS"; keep them in sync,
tests/test_den.py checks both against the same numbers):
  fantasy    pts + 1.2 reb + 1.5 ast + 2 blk + 2 stl, to 0.1
  team D     blk + stl + 0.5 (75 - points allowed) + 0.5 (45 - opponent FG%), to 0.1
  Pick 4     a right pick earns round(100 (1 - win chance of the side picked)); wrong 0
  Bricksanity  (FGM+FTM)/(FGA+FTA) among our 67; hit if either guess ties the lowest
  Brick by Brick  4 picks a day; 4 right lays a brick; any wrong pick knocks the wall to 0;
             no picks, or a voided (postponed) pick with no misses, leaves the wall standing
Rounding is half-up (JS Math.round), not Python's banker's rounding.

Win chance: for each h2h odds event, the last capture before commence_time; each book in
that capture de-vigged (home implied / (home + away implied)); the books averaged.

Locks are client side only (the page refuses edits after tip). A static site cannot
enforce them; see the report. Results only ever score finals.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date as Date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from zoneinfo import ZoneInfo

from .leagues import ALL, ROOT

ET = ZoneInfo("America/New_York")
DAYS_AHEAD = 3
MATCH_HOURS = 6  # an odds event and an ESPN game are the same game if they tip this close
OFF = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED", "STATUS_FORFEIT"}
TEAM: dict[str, tuple[Any, Any]] = {t.espn_id: (t, lg) for lg in ALL.values() for t in lg.teams}


# ---------------------------------------------------------------- scoring (JS: den.js)


def r(x: float, places: int = 1) -> float:
    """Round half up, exactly as JS Math.round(x * 10**places) / 10**places."""
    k = 10 ** places
    return math.floor(x * k + 0.5) / k


def fantasy_points(pts: float, reb: float, ast: float, blk: float, stl: float) -> float:
    """JS fantasyPoints."""
    return r(pts + 1.2 * reb + 1.5 * ast + 2 * blk + 2 * stl)


def defense_points(blk: float, stl: float, pa: float, ofgm: float, ofga: float) -> float:
    """JS defensePoints. Opponent FG% as a percentage (30.9, not 0.309)."""
    return r(blk + stl + 0.5 * (75 - pa) + 0.5 * (45 - 100 * ofgm / ofga)) if ofga else r(blk + stl + 0.5 * (75 - pa))


def shooting_pct(fgm: float, ftm: float, fga: float, fta: float) -> float | None:
    """JS shootingPct."""
    a = fga + fta
    return r((fgm + ftm) / a, 4) if a else None


def worth(win_home: float | None, side: str) -> int | None:
    """JS pickWorth. Pick 4 points for a right pick on `side` ("home" or "away")."""
    if win_home is None:
        return None
    p = win_home if side == "home" else 1 - win_home
    return math.floor(100 * (1 - p) + 0.5)


def pick_outcome(pick: dict[str, str], results: dict[str, Any] | None) -> str:
    """JS pickOutcome. pick = {game, side}. "win", "loss", "void" (never went final) or "pending"."""
    if not results:
        return "pending"
    g = next((x for x in results["games"] if x["id"] == pick["game"]), None)
    if g is None:
        return "void" if results.get("complete") else "pending"
    if g["winner_id"] is None:
        return "void"
    side_id = g["home_id"] if pick["side"] == "home" else g["away_id"]
    return "win" if side_id == g["winner_id"] else "loss"


def pick4_score(picks: list[dict[str, str]], results: dict[str, Any] | None) -> int:
    """JS pick4Score. The first 4 picks count."""
    total = 0
    for p in picks[:4]:
        if pick_outcome(p, results) == "win":
            g = next(x for x in results["games"] if x["id"] == p["game"])
            total += (g.get("worth") or {}).get(p["side"]) or 0
    return total


def daily_five_score(players: list[str], defense: str | None, results: dict[str, Any] | None) -> float:
    """JS dailyFiveScore. A player who didn't play scores 0."""
    if not results:
        return 0.0
    s = sum(results["players"].get(str(p), 0) for p in players[:5])
    if defense is not None:
        s += results["defenses"].get(str(defense), 0)
    return r(s)


def bricksanity_hit(guesses: list[str], results: dict[str, Any] | None) -> bool | None:
    """JS bricksanityHit. None until the night is complete."""
    if not results or not results.get("complete") or not results["shooting"]:
        return None
    low = min(results["shooting"].values())
    return any(results["shooting"].get(str(g)) == low for g in guesses[:2])


def brick_day(picks: list[dict[str, str]], results: dict[str, Any] | None) -> str:
    """JS brickDay. "hit", "miss", "pending" or "stand" (skip, or a void with no misses)."""
    outs = [pick_outcome(p, results) for p in picks[:4]]
    if "loss" in outs:
        return "miss"
    if "pending" in outs:
        return "pending"
    return "hit" if len(outs) == 4 and all(o == "win" for o in outs) else "stand"


def brick_wall(days: Iterable[str]) -> dict[str, int]:
    """JS brickWall. days = brick_day outcomes in date order -> {wall, best}."""
    wall = best = 0
    for d in days:
        if d == "hit":
            wall += 1
            best = max(best, wall)
        elif d == "miss":
            wall = 0
    return {"wall": wall, "best": best}


# ---------------------------------------------------------------- loading


def parse_iso(v: str) -> datetime:
    dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def et_date(v: str) -> str:
    return parse_iso(v).astimezone(ET).date().isoformat()


def data_dirs() -> list[Path]:
    return [lg.data_dir for lg in ALL.values()]


def ours(g: dict[str, Any]) -> bool:
    return str(g["home"].get("espn_id")) in TEAM or str(g["away"].get("espn_id")) in TEAM


def load_games(dirs: list[Path]) -> dict[str, dict[str, Any]]:
    """Every game involving our schools, deduped by game_id (a final copy wins)."""
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        f = d / "schedule.json"
        if not f.exists():
            continue
        for g in json.loads(f.read_text()).get("games", []):
            if not ours(g):
                continue
            old = out.get(g["game_id"])
            if old is None or (g.get("completed") and not old.get("completed")):
                out[g["game_id"]] = g
    return out


def load_boxes(dirs: list[Path], ids: set[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        bd = d / "boxscores"
        if not bd.exists():
            continue
        for f in bd.glob("*.json"):
            if f.stem in ids and f.stem not in out:
                try:
                    out[f.stem] = json.loads(f.read_text())
                except ValueError:
                    pass
    return out


def load_rosters(dirs: list[Path]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for d in dirs:
        f = d / "rosters.json"
        if f.exists():
            for k, v in (json.loads(f.read_text()).get("rosters") or {}).items():
                out.setdefault(k, v)
    return out


def load_names(path: Path) -> dict[str, dict[str, str]]:
    """espn id -> {short, abbr} for every D-I team."""
    if not path.exists():
        return {}
    return {str(t["id"]): {"short": t.get("short"), "abbr": t.get("abbr")} for t in json.loads(path.read_text()).get("teams", [])}


def load_anchors(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {k: a.get("name") for k, a in json.loads(path.read_text()).get("anchors", {}).items()}


def _field(line: str, key: str) -> str | None:
    """A string field from a compact JSON line without parsing it ('"key":"value"')."""
    for pat in (f'"{key}":"', f'"{key}": "'):
        i = line.find(pat)
        if i >= 0:
            i += len(pat)
            break
    else:
        return None
    j = line.find('"', i)
    return line[i:j] if j > 0 else None


def load_h2h(dirs: list[Path], days: set[str]) -> dict[str, dict[str, Any]]:
    """The last pre-tip h2h capture of every odds event in the line files of the given UTC capture dates.

    event -> {commence, home_key, away_key, caps: {captured_at: {book: [home_price, away_price]}}}
    Lines are a full season of captures, so they are scanned as text: only the rows of each
    event's last capture before commence_time are JSON-parsed. Each file is read once.
    """
    keep: dict[str, tuple[str, list[str]]] = {}
    for d in dirs:
        for day in sorted(days):
            f = d / "lines" / f"{day}.jsonl"
            if not f.exists():
                continue
            with f.open() as fh:
                for line in fh:
                    if '"h2h"' not in line:
                        continue
                    eid, cap, com = _field(line, "odds_event_id"), _field(line, "captured_at"), _field(line, "commence_time")
                    if not (eid and cap and com):
                        continue
                    cap, com = cap[:19], com[:19]
                    if cap >= com:
                        continue  # in-game capture
                    best = keep.get(eid)
                    if best is None or cap > best[0]:
                        keep[eid] = (cap, [line])
                    elif cap == best[0]:
                        best[1].append(line)
    ev: dict[str, dict[str, Any]] = {}
    for _, lines in keep.values():
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("market") != "h2h" or row.get("price") is None:
                continue
            e = ev.setdefault(row["odds_event_id"], {"commence": row["commence_time"], "home": row["home_team"],
                                                     "away": row["away_team"], "home_key": None, "away_key": None,
                                                     "caps": defaultdict(dict)})
            e["home_key"] = e["home_key"] or row.get("home_key")
            e["away_key"] = e["away_key"] or row.get("away_key")
            q = e["caps"][row["captured_at"]].setdefault(row["book"], [None, None])
            if row["outcome"] == row["home_team"]:
                q[0] = row["price"]
            elif row["outcome"] == row["away_team"]:
                q[1] = row["price"]
    return ev


# ---------------------------------------------------------------- win chance


def implied(american: float) -> float:
    return -american / (-american + 100) if american < 0 else 100 / (american + 100)


def win_chance(event: dict[str, Any]) -> float | None:
    """P(event home wins): last capture before commence, de-vig per book, average the books."""
    tip = parse_iso(event["commence"])
    caps = sorted((c for c in event["caps"] if parse_iso(c) < tip), reverse=True)
    for c in caps:
        ps = []
        for h, a in event["caps"][c].values():
            if h and a:
                ih, ia = implied(h), implied(a)
                ps.append(ih / (ih + ia))
        if ps:
            return sum(ps) / len(ps)
    return None


def match_events(games: dict[str, dict[str, Any]], events: dict[str, dict[str, Any]]) -> dict[str, float]:
    """game_id -> P(ESPN home wins). An event matches a game when every one of our team keys
    it names is in the game and it tips within MATCH_HOURS; the closest tip wins."""
    by_key: dict[str, list[tuple[datetime, dict[str, Any]]]] = defaultdict(list)
    for g in games.values():
        for s in ("home", "away"):
            t = TEAM.get(str(g[s].get("espn_id")))
            if t:
                by_key[t[0].key].append((parse_iso(g["date"]), g))
    out: dict[str, float] = {}
    best: dict[str, float] = {}
    for e in events.values():
        keys = [k for k in (e["home_key"], e["away_key"]) if k]
        if not keys:
            continue
        tip = parse_iso(e["commence"])
        cands = []
        for when, g in by_key.get(keys[0], []):
            gk = {TEAM[str(g[s].get("espn_id"))][0].key for s in ("home", "away") if str(g[s].get("espn_id")) in TEAM}
            gap = abs((when - tip).total_seconds())
            if set(keys) <= gk and gap <= MATCH_HOURS * 3600:
                cands.append((gap, g))
        if not cands:
            continue
        gap, g = min(cands, key=lambda x: x[0])
        p = win_chance(e)
        if p is None or best.get(g["game_id"], 1e18) <= gap:
            continue
        home_key = TEAM.get(str(g["home"].get("espn_id")), (None,))[0]
        home_key = home_key.key if home_key else None
        away_key = TEAM.get(str(g["away"].get("espn_id")), (None,))[0]
        away_key = away_key.key if away_key else None
        flipped = (e["home_key"] and e["home_key"] == away_key) or (e["away_key"] and e["away_key"] == home_key)
        out[g["game_id"]] = 1 - p if flipped else p
        best[g["game_id"]] = gap
    return out


# ---------------------------------------------------------------- box scores


def _pair(s: str | None) -> tuple[int, int]:
    try:
        a, b = (s or "").split("-")
        return int(a), int(b)
    except ValueError:
        return 0, 0


def _n(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def team_lines(box: dict[str, Any], game: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """espn id -> {pts, pa, blk, stl, fgm, fga, ftm, fta, ofgm, ofga} from a box score."""
    teams = box.get("teams") or []
    if len(teams) != 2:
        return {}
    score = {str(game[s].get("espn_id")): game[s].get("score") for s in ("home", "away")}
    raw = {}
    for t in teams:
        st = t.get("stats") or {}
        fgm, fga = _pair(st.get("fieldGoalsMade-fieldGoalsAttempted"))
        ftm, fta = _pair(st.get("freeThrowsMade-freeThrowsAttempted"))
        tid = str(t["espn_id"])
        pts = score.get(tid)
        if pts is None:
            pts = sum(int(_n(p.get("pts"))) for p in box.get("players", []) if str(p.get("team_espn_id")) == tid)
        raw[tid] = {"pts": int(pts), "blk": int(_n(st.get("blocks"))), "stl": int(_n(st.get("steals"))),
                    "fgm": fgm, "fga": fga, "ftm": ftm, "fta": fta}
    a, b = list(raw)
    for me, op in ((a, b), (b, a)):
        raw[me].update(pa=raw[op]["pts"], ofgm=raw[op]["fgm"], ofga=raw[op]["fga"])
    return raw


# ---------------------------------------------------------------- building


class Den:
    """Everything loaded once per run, then sliced per date."""

    def __init__(self, dirs: list[Path] | None = None, ratings: Path | None = None, anchors: Path | None = None,
                 now: datetime | None = None):
        dirs = dirs or data_dirs()
        self.now = now or datetime.now(timezone.utc)
        self.today = self.now.astimezone(ET).date()
        self.games = {gid: g for gid, g in load_games(dirs).items() if g.get("date")}
        self.by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for g in self.games.values():
            self.by_date[et_date(g["date"])].append(g)
        for gs in self.by_date.values():
            gs.sort(key=lambda g: (g["date"], g["game_id"]))
        final_ids = {gid for gid, g in self.games.items() if is_final(g)}
        self.boxes = load_boxes(dirs, final_ids)
        self.rosters = load_rosters(dirs)
        self.names = load_names(ratings or ROOT / "data" / "model" / "ratings.json")
        self.anchors = load_anchors(anchors or ROOT / "data" / "anchors.json")
        last = (self.today + timedelta(days=DAYS_AHEAD)).isoformat()
        self.slate_dates = sorted(d for d in self.by_date if d <= last)
        # UTC capture dates that can hold the last line before each needed tip: the tip's UTC day and the one before.
        cap_days = set()
        for d in self.slate_dates:
            for g in self.by_date[d]:
                t = parse_iso(g["date"]).date()
                cap_days |= {t.isoformat(), (t - timedelta(days=1)).isoformat()}
        self.win = match_events({g["game_id"]: g for d in self.slate_dates for g in self.by_date[d]}, load_h2h(dirs, cap_days))
        self._stats = self._player_lines()

    # one pass over the box scores: per player per game
    def _player_lines(self) -> list[tuple[str, dict[str, Any]]]:
        rows = []
        for gid, box in self.boxes.items():
            d = et_date(self.games[gid]["date"])
            for p in box.get("players", []):
                if str(p.get("team_espn_id")) in TEAM:
                    rows.append((d, p))
        rows.sort(key=lambda x: x[0])
        return rows

    def averages(self) -> Iterable[tuple[str, dict[str, dict[str, Any]]]]:
        """Yield (date, totals) for each slate date in order: totals from box scores strictly before it."""
        tot: dict[str, dict[str, Any]] = {}
        i = 0
        for d in self.slate_dates:
            while i < len(self._stats) and self._stats[i][0] < d:
                p = self._stats[i][1]
                i += 1
                pid = str(p.get("espn_id"))
                t = tot.setdefault(pid, {"name": p.get("name"), "pos": p.get("position"), "team_id": str(p.get("team_espn_id")),
                                         "pts": 0.0, "reb": 0.0, "ast": 0.0, "blk": 0.0, "stl": 0.0, "min": 0.0, "g": 0})
                if p.get("dnp") or (p.get("min") is None and not p.get("pts")):
                    continue
                for k in ("pts", "reb", "ast", "blk", "stl", "min"):
                    t[k] += _n(p.get(k))
                t["g"] += 1
                t["team_id"] = str(p.get("team_espn_id"))
            yield d, tot

    def side(self, s: dict[str, Any]) -> dict[str, Any]:
        tid = str(s.get("espn_id"))
        t = TEAM.get(tid)
        if t:
            team, lg = t
            return {"key": team.key, "id": tid, "short": team.short, "abbr": team.abbr, "edition": lg.short,
                    "anchor": self.anchors.get(team.key)}
        nm = self.names.get(tid, {})
        return {"key": None, "id": tid, "short": nm.get("short") or s.get("name"), "abbr": nm.get("abbr") or s.get("abbr"),
                "edition": None, "anchor": None}

    def slate(self, d: str, totals: dict[str, dict[str, Any]]) -> dict[str, Any]:
        games, defenses, players, seen = [], [], [], set()
        for g in self.by_date[d]:
            if g.get("status") in OFF:
                continue
            p = self.win.get(g["game_id"])
            p = r(p, 3) if p is not None else None
            row = {"id": g["game_id"], "tip": g["date"], "home": self.side(g["home"]), "away": self.side(g["away"]),
                   "win_home": p, "worth": {"home": worth(p, "home"), "away": worth(p, "away")} if p is not None else None}
            if g.get("time_tba"):
                row["tba"] = True
            games.append(row)
            for s in ("away", "home"):
                tid = str(g[s].get("espn_id"))
                if tid in TEAM and tid not in defenses:
                    defenses.append(tid)
        for tid in defenses:
            team = TEAM[tid][0]
            pool = {}
            for rp in self.rosters.get(team.key, []):
                pid = str(rp.get("espn_id"))
                pool[pid] = {"name": rp.get("name"), "pos": rp.get("position")}
            for pid, t in totals.items():
                if t["team_id"] == tid and pid not in pool:
                    pool[pid] = {"name": t["name"], "pos": t["pos"]}
            team_players = []
            for pid, info in pool.items():
                if pid in seen:
                    continue
                seen.add(pid)
                t = totals.get(pid)
                g = t["g"] if t else 0
                avg = {k: (r(t[k] / g) if g else 0) for k in ("pts", "reb", "ast", "blk", "stl", "min")}
                avg["g"] = g
                team_players.append({"id": pid, "name": info["name"], "team_id": tid, "pos": info["pos"] or "", "avg": avg})
            team_players.sort(key=lambda x: (-x["avg"]["pts"], -x["avg"]["min"], x["name"] or ""))
            players += team_players
        return {"date": d, "generated_at": self.now.isoformat(timespec="minutes"), "games": games,
                "players": players, "defenses": defenses}

    def results(self, d: str) -> dict[str, Any] | None:
        gs = [g for g in self.by_date[d] if g.get("status") not in OFF]
        finals = [g for g in gs if is_final(g)]
        if not finals:
            return None
        games, players, stat, defenses, shooting, bricks = [], {}, {}, {}, {}, {}
        complete = len(finals) == len(gs)
        for g in finals:
            p = self.win.get(g["game_id"])
            p = r(p, 3) if p is not None else None
            hp, ap = g["home"].get("score"), g["away"].get("score")
            hid, aid = str(g["home"].get("espn_id")), str(g["away"].get("espn_id"))
            winner = hid if g["home"].get("winner") or (hp or 0) > (ap or 0) else aid if g["away"].get("winner") or (ap or 0) > (hp or 0) else None
            games.append({"id": g["game_id"], "final": True, "home_id": hid, "away_id": aid, "home_pts": hp, "away_pts": ap,
                          "winner_id": winner, "win_home": p,
                          "worth": {"home": worth(p, "home"), "away": worth(p, "away")} if p is not None else None})
            box = self.boxes.get(g["game_id"])
            if not box:
                complete = False
                continue
            for tid, t in team_lines(box, g).items():
                if tid not in TEAM:
                    continue
                defenses[tid] = defense_points(t["blk"], t["stl"], t["pa"], t["ofgm"], t["ofga"])
                pct = shooting_pct(t["fgm"], t["ftm"], t["fga"], t["fta"])
                if pct is not None:
                    shooting[tid] = pct
                    bricks[tid] = [t["fgm"] + t["ftm"], t["fga"] + t["fta"]]
            for pl in box.get("players", []):
                if str(pl.get("team_espn_id")) not in TEAM or pl.get("dnp"):
                    continue
                v = [int(_n(pl.get(k))) for k in ("pts", "reb", "ast", "blk", "stl", "min")]
                pid = str(pl.get("espn_id"))
                players[pid] = fantasy_points(*v[:5])
                stat[pid] = v
        worst = min(shooting, key=lambda k: (shooting[k], bricks[k][0]), default=None)
        return {"date": d, "generated_at": self.now.isoformat(timespec="minutes"), "complete": complete,
                "games": games, "players": players, "stat": stat, "defenses": defenses, "shooting": shooting,
                "bricks": bricks, "worst_shooter": worst}


def is_final(g: dict[str, Any]) -> bool:
    return bool(g.get("completed")) and g.get("status") not in OFF


def _dump(path: Path, obj: Any) -> int:
    s = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    path.write_text(s)
    return len(s)


def build(site_root: Path, now: datetime | None = None, den: Den | None = None) -> dict[str, Any]:
    """Write site/den/*.json. Returns a small summary for the build log."""
    den = den or Den(now=now)
    out = site_root / "den"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()
    index: dict[str, dict[str, Any]] = {}
    for d, totals in den.averages():
        _dump(out / f"slate-{d}.json", den.slate(d, totals))
        index[d] = {"date": d, "slate": True, "results": False, "complete": False}
    for d in sorted(den.by_date):
        res = den.results(d)
        if res:
            _dump(out / f"results-{d}.json", res)
            index.setdefault(d, {"date": d, "slate": False, "results": False, "complete": False})
            index[d].update(results=True, complete=res["complete"])
    _dump(out / "index.json", {"generated_at": den.now.isoformat(timespec="minutes"), "today": den.today.isoformat(),
                                "dates": [index[d] for d in sorted(index)]})
    return {"slates": sum(1 for v in index.values() if v["slate"]), "results": sum(1 for v in index.values() if v["results"])}


if __name__ == "__main__":
    import sys
    import time
    t0 = time.perf_counter()
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    print(build(root), f"{time.perf_counter() - t0:.2f}s")
