"""Tops and Bottoms: the JuiceBox Nation wagering board on Hardwood Bricks (Matthew, Nov 18 2026).

Part ledger, part column. Four fictional handicappers make rule-based picks off our model and the
night's board, the picks lock at 8:15 AM Eastern, and the ledger keeps every one's record and units.

The four and their rules (Matthew's words, made exact here):

  Brett Busberger, Mr. JuiceBox   The model's two biggest gaps from the spread, taking the model's side.
  Merv Crutch, Hall of Famer      Defense. One under (the model's biggest gap under the posted total), and
                                  the team with the night's third-lowest points allowed per game, against the spread.
  Leslie Phyllis, Tunica's own    Offense. One over (the model's biggest gap over the posted total), and the
                                  team with the night's second-highest points per game, against the spread.
  Edwin "The Shark" Sinclair,     One home dog getting 3 to 10 points, and the same game's total, over or under
  Atlantic City                   on "inside information": always shady, never about the game, and never about a
                                  real person or business (house rule). Which dog and which way are a coin
                                  seeded by the date, so a rerun on the same morning picks the same thing.

Every handicapper makes two picks a night (Matthew, Nov 19 2026). When a rule comes up short, the pick moves to the
next one up or down the same list (the closest under, the nearest home dog to the window, the next team on the
points list), and only when the list is empty does a coin seeded by the date choose.

"The board" is every game on our 27 editions' schedules tipping that Eastern day with a pre-game spread and total
(our model logs both, data/**/model/projections.jsonl), neither side non-D-I. Points per game and allowed are this
season's D-I results before that day (data/ncaa/games-<season>.json), two games minimum.

Files: data/tops/YYYY-MM-DD.json, one per day, written once at lock and never re-picked. Grades are added to the
same file as games go final. Every pick is 1 unit at -110: a win pays +0.91, a loss costs 1, a push or a postponed
game is 0. The column is written at lock and kept with the picks, so it reads the same all day.

Entertainment only. The model has not beaten closing lines out of sample (see the ratings page), the handicappers are
fictional AI personas, and the page says both.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date as Date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from zoneinfo import ZoneInfo

from .leagues import ALL, ROOT

ET = ZoneInfo("America/New_York")
TOPS_DIR = ROOT / "data" / "tops"
NCAA_DIR = ROOT / "data" / "ncaa"
# Picks lock in the first collect run from 7:30 AM Eastern, so the page is published by 8:15 (Matthew's deadline).
# A full collect run takes ~25 minutes and the site only deploys at its end; locking at 8:15 put the page up ~8:27
# (Nov 21 2026). collect.yml locks in an early step, before the slow edition loop; the hub step is the backup.
LOCK_AT = time(7, 30)
WIN, LOSS = 0.91, -1.0  # 1 unit at -110
MIN_GAMES = 2  # a team needs this many D-I games for points per game to count
DOG_MIN, DOG_MAX = 3.0, 10.0  # the Shark's home dog window, inclusive
MAX_GAP = 20.0  # a model-vs-market gap past this is a data problem, not a lean
OFF = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED", "STATUS_FORFEIT"}

DISCLOSURE = ("Tops and Bottoms is entertainment from JuiceBox Nation. Merv, Leslie, Brett and the Shark are fictional "
              "AI personas, not real people. Their picks follow fixed rules off our ratings model, which has not beaten "
              "the betting market in testing. Nothing here is betting advice.")
HELPLINE = "If you or someone you know has a gambling problem, call 1-800-GAMBLER."

CAPPERS: list[dict[str, Any]] = [
    {"key": "merv", "name": "Merv Crutch", "first": "Merv", "title": "Hall of Famer", "from": "Hall of Fame handicapper",
     "lean": "Defense wins. One under, plus the night's third-stingiest defense against the spread.", "color": "#2f5d8a"},
    {"key": "leslie", "name": "Leslie Phyllis", "first": "Leslie", "title": "Tunica's own", "from": "Tunica, Mississippi",
     "lean": "Buckets. One over, plus the night's second-highest-scoring team against the spread.", "color": "#d4146f"},
    {"key": "brett", "name": "Brett Busberger", "first": "Brett", "title": "Mr. JuiceBox", "from": "JuiceBox Nation",
     "lean": "Trusts the machine. The model's two biggest gaps from the spread.", "color": "#e8731c"},
    {"key": "shark", "name": "Edwin “The Shark” Sinclair", "first": "The Shark", "title": "Atlantic City",
     "from": "Atlantic City, New Jersey",
     "lean": "One home dog getting 3 to 10, and a total off inside information. Do not ask him where it comes from.",
     "color": "#1f8a7a"},
]
BY_KEY = {c["key"]: c for c in CAPPERS}

# The Shark's inside information. Shady, a non sequitur, and about nobody real: invented people, no real
# businesses, nothing a reader could pin on an actual person. Add freely, keep to those three rules.
INSIDE = [
    "A fella named Dutch, who I will not describe, says the shrimp at the Neptune Lounge came in on the wrong truck.",
    "Somebody left a duffel bag by the claw machine on the boardwalk. Nobody's touched it. Nobody.",
    "My guy at the car wash says they've been running the rinse cycle backwards since Tuesday.",
    "There's a parrot at a pawn shop I know that can recite three phone numbers. I have two of them.",
    "My cousin Sal has been moving refrigerators that don't get cold. Eleven of them. Ask me why.",
    "A man in a wet trench coat slipped me a napkin with a goat drawn on it. I've seen that goat before.",
    "The night manager at a motel I won't name just bought a jet ski. In November.",
    "Three crates of lemons fell off a bakery truck. The lemons will turn up. The truck will not.",
    "The ice machine on the fourth floor has been humming in Morse code. I don't know Morse code. My associate does.",
    "Big Tino's nephew paid cash for a boat and named it Plausible Deniability.",
    "A guy at the track with one eyebrow tells me the moon's been coming up early.",
    "My bookkeeper Lorraine went to Delaware for the weekend and came back with a different accent.",
    "There's a tuxedo rental that's been closed six years and still does a lot of business.",
    "A mime on the boardwalk broke character and said one word to me. The word was Thursday.",
    "The kid who refills the mints at the hotel bar is wearing a much nicer watch than last week.",
    "A pigeon with a Newark leg band has been circling the same parking garage since Sunday.",
    "Two men in matching windbreakers asked my barber if he still had the thing. He said he did.",
    "My dry cleaner sent my shirt back with somebody else's receipt in the pocket. Forty pounds of anchovies.",
    "The bingo hall switched callers. New guy has a cousin in the commissary.",
    "Somebody's been buying every rubber duck in South Jersey. Every single one.",
    "A limo with out-of-state plates has idled outside the clam bar for nine hours. Engine's still warm.",
    "My accountant told me to stop asking about the freezer. So I stopped asking about the freezer.",
    "A florist I know got an order for four hundred carnations and no card. No card, Jerry.",
    "Fat Louie's brother-in-law is suddenly an expert on Portuguese tile.",
    "The fortune cookies at a place on Pacific Avenue started coming back empty. All of them.",
    "My guy in shipping says a crate marked 'BOWLING BALLS' is way too light to be bowling balls.",
    "The organ player at the ice rink hasn't missed a note in nine years. Tonight he's out sick.",
    "Somebody painted over the 7 on the elevator in my building. Now it goes from 6 to 8.",
]
SHARK_SIGNOFF = {"over": ["Over. Don't ask.", "I'm on the over. You didn't hear it from me.", "Over. That's all I can say."],
                 "under": ["Under. Don't ask.", "I'm on the under. You didn't hear it from me.", "Under. That's all I can say."]}

# ---------------------------------------------------------------- small helpers


def _iso(v: str) -> datetime:
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


def et_day(v: str) -> str:
    return _iso(v).astimezone(ET).date().isoformat()


def _seed(*parts: Any) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def _choose(options: list[Any], *seed: Any) -> Any:
    return options[_seed(*seed) % len(options)]


def _num(v: float) -> str:
    """+3.5, -7, PK."""
    if v == 0:
        return "PK"
    return f"{v:+g}"


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def data_dirs() -> list[Path]:
    return [lg.data_dir for lg in ALL.values()]


# ---------------------------------------------------------------- the board


def load_games(dirs: Iterable[Path], day: str | None = None) -> dict[str, dict[str, Any]]:
    """Every game on our schedules (optionally one Eastern day), deduped by id; a final copy wins."""
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        for g in (_load(d / "schedule.json") or {}).get("games", []):
            if day and et_day(g["date"]) != day:
                continue
            old = out.get(g["game_id"])
            if old is None or (g.get("completed") and not old.get("completed")):
                out[g["game_id"]] = g
    return out


def load_projections(dirs: Iterable[Path], day: str, now: datetime) -> dict[str, dict[str, Any]]:
    """The newest model row per game for games tipping on `day`, logged no later than `now`.
    The logs are big (every run appends), so lines are filtered on the tip date as text before parsing."""
    d0 = Date.fromisoformat(day)
    keys = [d0.isoformat(), (d0 + timedelta(days=1)).isoformat()]  # late tips are tomorrow in UTC
    stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        f = d / "model" / "projections.jsonl"
        if not f.exists():
            continue
        with f.open() as fh:
            for line in fh:
                if not any(k in line for k in keys):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if et_day(r["tip"]) != day or r["generated_at"][:19] > stamp[:19]:
                    continue
                old = out.get(r["game_id"])
                if old is None or r["generated_at"] >= old["generated_at"]:
                    out[r["game_id"]] = r
    return out


def ncaa_games(path: Path | None = None) -> list[dict[str, Any]]:
    if path is None:
        files = sorted(NCAA_DIR.glob("games-*.json"))
        if not files:
            return []
        path = files[-1]
    return (_load(path) or {}).get("games", [])


def team_scoring(games: Iterable[dict[str, Any]], before: str) -> dict[str, dict[str, float]]:
    """Points per game and allowed per game for every D-I team, from finals before `before` (an Eastern date)."""
    acc: dict[str, list[float]] = {}
    for g in games:
        if et_day(g["date"]) >= before:
            continue
        h, a = g.get("home") or {}, g.get("away") or {}
        if h.get("pts") is None or a.get("pts") is None:
            continue
        for me, them in ((h, a), (a, h)):
            t = acc.setdefault(str(me["id"]), [0, 0.0, 0.0])
            t[0] += 1
            t[1] += me["pts"]
            t[2] += them["pts"]
    return {k: {"g": v[0], "ppg": round(v[1] / v[0], 1), "papg": round(v[2] / v[0], 1)} for k, v in acc.items() if v[0]}


def _side(s: dict[str, Any]) -> dict[str, Any]:
    name = s.get("name") or ""
    return {"id": str(s.get("espn_id")), "key": s.get("key"), "name": name, "abbr": s.get("abbr") or name[:4].upper()}


def board(day: str, now: datetime, dirs: list[Path] | None = None, scoring: dict[str, dict[str, float]] | None = None) -> list[dict[str, Any]]:
    """The night's board: games tipping on `day`, not yet tipped at `now`, with a pre-game spread and total."""
    dirs = dirs if dirs is not None else data_dirs()
    games = load_games(dirs, day)
    if not games:
        return []
    proj = load_projections(dirs, day, now)
    if scoring is None:
        scoring = team_scoring(ncaa_games(), day)
    out = []
    for gid, g in games.items():
        p = proj.get(gid)
        if not p or g.get("completed") or g.get("status") in OFF or p.get("non_d1"):
            continue
        tip = _iso(g["date"])
        if tip <= now or p.get("mkt_spread") is None or p.get("mkt_total") is None:
            continue
        if p.get("mkt_captured_at") and _iso(p["mkt_captured_at"]) >= tip:  # an in-game number, not a pre-game line
            continue
        home, away = _side(g["home"]), _side(g["away"])
        for s in (home, away):
            s.update(scoring.get(s["id"]) or {"g": 0, "ppg": None, "papg": None})
        spread, model_spread = float(p["mkt_spread"]), float(p["model_spread"])
        # The odds feed names its own home team. On a neutral floor that can be ESPN's away team, which flips the
        # sign; when the model and the market disagree on the favorite at a neutral site we can't tell, so no side.
        flip_risk = bool(g.get("neutral_site")) and spread * model_spread < 0
        out.append({
            "id": gid, "tip": g["date"], "neutral": bool(g.get("neutral_site")), "home": home, "away": away,
            "spread": spread, "total": float(p["mkt_total"]), "model_spread": model_spread, "model_total": float(p["model_total"]),
            "captured_at": p.get("mkt_captured_at"), "sides_ok": not flip_risk and abs(model_spread - spread) <= MAX_GAP,
            "totals_ok": abs(float(p["model_total"]) - float(p["mkt_total"])) <= MAX_GAP,
        })
    out.sort(key=lambda b: (b["tip"], b["id"]))
    return out


# ---------------------------------------------------------------- the four rules


def _matchup(b: dict[str, Any]) -> str:
    return f"{b['away']['name']} {'vs.' if b['neutral'] else 'at'} {b['home']['name']}"


def side_pick(b: dict[str, Any], side: str, why: str) -> dict[str, Any]:
    """A pick against the spread. line is the number on the side taken (home spread, or minus it for the away side)."""
    line = b["spread"] if side == "home" else -b["spread"]
    t = b[side]
    return {"kind": "side", "game": b["id"], "tip": b["tip"], "matchup": _matchup(b), "side": side, "team": t["name"],
            "abbr": t["abbr"], "line": line, "label": f"{t['name']} {_num(line)}", "why": why}


def total_pick(b: dict[str, Any], way: str, why: str) -> dict[str, Any]:
    return {"kind": "total", "game": b["id"], "tip": b["tip"], "matchup": _matchup(b), "side": way, "line": b["total"],
            "label": f"{'Over' if way == 'over' else 'Under'} {b['total']:g}", "why": why}


def model_side(b: dict[str, Any]) -> str:
    """Negative gap: the model likes the home team more than the market does."""
    return "home" if b["model_spread"] - b["spread"] < 0 else "away"


PICKS_EACH = 2  # Matthew, Nov 19 2026: every handicapper makes two picks a night, rules or no rules


def _gap_rank(bd: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Games by the model's distance from the spread, biggest first; games we can't orient go last."""
    return sorted(bd, key=lambda b: (not b["sides_ok"], -abs(b["model_spread"] - b["spread"]), b["id"]))


def _random_pick(bd: list[dict[str, Any]], day: str, who: str, n: int, taken: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Last resort when a rule comes up empty: a seeded coin picks a game and a side or total."""
    used = {(p["game"], p["kind"]) for p in taken}
    opts = [(b, k) for b in sorted(bd, key=lambda b: b["id"]) for k in ("side", "total") if (b["id"], k) not in used]
    if not opts:
        return None
    b, k = _choose(opts, who, "random", day, n)
    if k == "side":
        side = _choose(["home", "away"], who, "random-side", day, n)
        return side_pick(b, side, "Nothing on the board fit the rule tonight, so this one's a coin flip.")
    way = _choose(["over", "under"], who, "random-way", day, n)
    return total_pick(b, way, "Nothing on the board fit the rule tonight, so this one's a coin flip.")


def _fill(out: list[dict[str, Any]], bd: list[dict[str, Any]], day: str, who: str) -> list[dict[str, Any]]:
    while len(out) < PICKS_EACH:
        p = _random_pick(bd, day, who, len(out), out)
        if not p:
            break
        out.append(p)
    return out


def brett(bd: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    out = []
    for b in _gap_rank(bd)[:PICKS_EACH]:
        gap = abs(b["model_spread"] - b["spread"])
        out.append(side_pick(b, model_side(b), f"Model is {gap:.1f} points off the number."))
    return _fill(out, bd, day, "brett")


def _best_total(bd: list[dict[str, Any]], way: str) -> dict[str, Any] | None:
    """The game where the model leans hardest `way`; if none leans that way, the one closest to it."""
    sign = 1 if way == "over" else -1
    ok = sorted(bd, key=lambda b: (not b["totals_ok"], -sign * (b["model_total"] - b["total"]), b["id"]))
    return ok[0] if ok else None


def _total_why(b: dict[str, Any], way: str) -> str:
    gap = (b["model_total"] - b["total"]) * (1 if way == "over" else -1)
    if gap > 0:
        return f"Model has it {gap:.1f} {way} the total."
    return f"Closest thing to an {way} on the board tonight."


def _ranked_teams(bd: list[dict[str, Any]], stat: str, reverse: bool) -> list[tuple[dict[str, Any], str]]:
    """(board game, side) for every team on the board with a number, best first on `stat`.
    Teams with enough games come first; short samples and games we can't orient fill in behind them."""
    rows = [(b, s) for b in bd for s in ("home", "away") if b[s].get(stat) is not None]
    rows.sort(key=lambda x: (not x[0]["sides_ok"], x[0][x[1]].get("g", 0) < MIN_GAMES,
                             -x[0][x[1]][stat] if reverse else x[0][x[1]][stat], x[0][x[1]]["id"]))
    return rows


def _nth(rows: list[Any], n: int) -> Any:
    """The nth (0-based) if it's there, else the nearest one up the list."""
    return rows[min(n, len(rows) - 1)] if rows else None


STINGY = {1: "Stingiest", 2: "Second-stingiest", 3: "Third-stingiest"}


def merv(bd: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    out = []
    u = _best_total(bd, "under")
    if u:
        out.append(total_pick(u, "under", _total_why(u, "under")))
    ranked = _ranked_teams(bd, "papg", reverse=False)
    hit = _nth(ranked, 2)
    if hit:
        b, s = hit
        i = ranked.index(hit) + 1
        out.append(side_pick(b, s, f"{STINGY[i]} defense on the board: {b[s]['papg']:.1f} allowed a game."))
    return _fill(out, bd, day, "merv")


def leslie(bd: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    out = []
    o = _best_total(bd, "over")
    if o:
        out.append(total_pick(o, "over", _total_why(o, "over")))
    ranked = _ranked_teams(bd, "ppg", reverse=True)
    hit = _nth(ranked, 1)
    if hit:
        b, s = hit
        i = ranked.index(hit) + 1
        out.append(side_pick(b, s, f"{'Second-highest' if i == 2 else 'Highest'} scoring team on the board: {b[s]['ppg']:.1f} a game."))
    return _fill(out, bd, day, "leslie")


def _dog_distance(b: dict[str, Any]) -> float:
    """How far a home team's number sits outside the 3-to-10 window (0 inside it)."""
    return max(DOG_MIN - b["spread"], b["spread"] - DOG_MAX, 0.0)


def shark(bd: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    way = _choose(["over", "under"], "shark-way", day)
    info = _choose(INSIDE, "shark-info", day)
    total_why = info + " " + _choose(SHARK_SIGNOFF[way], "shark-sign", day)
    dogs = sorted([b for b in bd if not b["neutral"] and DOG_MIN <= b["spread"] <= DOG_MAX], key=lambda b: b["id"])
    if dogs:
        b = _choose(dogs, "shark-dog", day)
        why = "Home dog in the window. I like a building that owes me money."
    else:
        # Nothing in the window: the home team nearest it, up or down the list. Then any game at all.
        homes = sorted([b for b in bd if not b["neutral"]], key=lambda b: (_dog_distance(b), b["id"]))
        if homes:
            b = homes[0]
            why = "Closest thing to a home dog in my window tonight. A building that owes me money is a building that owes me money."
        elif bd:
            b = _choose(sorted(bd, key=lambda b: b["id"]), "shark-any", day)
            why = "No home dogs tonight. I'm taking the home team anyway. Call it loyalty."
        else:
            return []
    return [side_pick(b, "home", why), total_pick(b, way, total_why)]


RULES = {"merv": merv, "leslie": leslie, "brett": brett, "shark": shark}


def make_picks(bd: list[dict[str, Any]], day: str) -> dict[str, list[dict[str, Any]]]:
    return {k: RULES[k](bd, day) for k in RULES}


# ---------------------------------------------------------------- grading


def final_scores(dirs: list[Path] | None = None, games: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """game id -> {home, away, status}: finals from our schedules, then the D-I results file for anything else."""
    out: dict[str, dict[str, Any]] = {}
    for gid, g in load_games(dirs if dirs is not None else data_dirs()).items():
        if g.get("status") in OFF:
            out[gid] = {"status": "off"}
        elif g.get("completed") and g["home"].get("score") is not None and g["away"].get("score") is not None:
            out[gid] = {"status": "final", "home": float(g["home"]["score"]), "away": float(g["away"]["score"])}
    for g in games if games is not None else ncaa_games():
        if g["id"] not in out and (g.get("home") or {}).get("pts") is not None and (g.get("away") or {}).get("pts") is not None:
            out[g["id"]] = {"status": "final", "home": float(g["home"]["pts"]), "away": float(g["away"]["pts"])}
    return out


def grade_pick(p: dict[str, Any], score: dict[str, Any] | None) -> str | None:
    """win / loss / push / void, or None while the game is unplayed."""
    if not score:
        return None
    if score["status"] == "off":
        return "void"
    if p["kind"] == "side":
        mine, theirs = (score["home"], score["away"]) if p["side"] == "home" else (score["away"], score["home"])
        diff = mine + p["line"] - theirs
    else:
        diff = (score["home"] + score["away"] - p["line"]) * (1 if p["side"] == "over" else -1)
    return "win" if diff > 0 else "loss" if diff < 0 else "push"


def units(result: str | None) -> float:
    return WIN if result == "win" else LOSS if result == "loss" else 0.0


def grade_card(card: dict[str, Any], scores: dict[str, dict[str, Any]]) -> bool:
    """Fill in results for ungraded picks. True when anything changed."""
    changed = False
    for picks in card.get("picks", {}).values():
        for p in picks:
            if p.get("result"):
                continue
            r = grade_pick(p, scores.get(p["game"]))
            if r:
                p["result"] = r
                sc = scores[p["game"]]
                if sc["status"] == "final":
                    p["final"] = f"{sc['away']:g}-{sc['home']:g}"
                changed = True
    return changed


# ---------------------------------------------------------------- the ledger


def tally(picks: Iterable[dict[str, Any]]) -> dict[str, Any]:
    t = {"w": 0, "l": 0, "p": 0, "units": 0.0, "pending": 0}
    for p in picks:
        r = p.get("result")
        if r == "win":
            t["w"] += 1
        elif r == "loss":
            t["l"] += 1
        elif r == "push":
            t["p"] += 1
        elif r is None:
            t["pending"] += 1
        t["units"] += units(r)
    t["units"] = round(t["units"], 2)
    t["record"] = f"{t['w']}-{t['l']}" + (f"-{t['p']}" if t["p"] else "")
    return t


def load_cards(tops_dir: Path | None = None) -> list[dict[str, Any]]:
    d = tops_dir or TOPS_DIR
    return [c for f in sorted(d.glob("????-??-??.json")) if (c := _load(f))]


def standings(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for c in CAPPERS:
        mine = [p for card in cards for p in card.get("picks", {}).get(c["key"], [])]
        t = tally(mine)
        streak, run = "", 0
        for p in reversed([p for p in mine if p.get("result") in ("win", "loss")]):
            s = "W" if p["result"] == "win" else "L"
            if streak and s != streak:
                break
            streak, run = s, run + 1
        risked = t["w"] + t["l"]
        rows.append({**c, **t, "streak": f"{streak}{run}" if run else "",
                     "roi": round(100 * t["units"] / risked, 1) if risked else None})
    rows.sort(key=lambda r: (-r["units"], -r["w"], r["key"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def window(cards: list[dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
    """The Window (Nov 21 2026): game id -> every Tops and Bottoms pick on that game, for game cards and recaps.
    Each row carries the capper (key, name, first, color), the pick label and kind, and its grade if it has one."""
    out: dict[str, list[dict[str, Any]]] = {}
    for card in load_cards() if cards is None else cards:
        for key, picks in (card.get("picks") or {}).items():
            c = BY_KEY.get(key)
            if not c:
                continue
            for p in picks:
                if not p.get("game"):
                    continue
                out.setdefault(str(p["game"]), []).append({
                    "key": key, "name": c["name"], "first": c["first"], "color": c["color"], "day": card.get("date"),
                    "kind": p["kind"], "side": p.get("side"), "line": p.get("line"), "label": p["label"],
                    "result": p.get("result")})
    order = {c["key"]: i for i, c in enumerate(CAPPERS)}
    for rows in out.values():
        rows.sort(key=lambda r: (order[r["key"]], r["kind"] != "side"))
    return out


def graded(rows: list[dict[str, Any]], home: Any, away: Any) -> list[dict[str, Any]]:
    """Window rows for a finished game, graded off its final score where the ledger hasn't caught up yet."""
    score = {"status": "final", "home": float(home), "away": float(away)} if home is not None and away is not None else None
    out = []
    for r in rows:
        res = r.get("result") or grade_pick(r, score)
        out.append({**r, "result": res, "units": units(res) if res else None})
    return out


def night_of(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Each handicapper's line for one day, best units first."""
    rows = [{**BY_KEY[k], **tally(ps)} for k, ps in card.get("picks", {}).items() if k in BY_KEY]
    rows.sort(key=lambda r: (-r["units"], -r["w"], r["key"]))
    return rows


# ---------------------------------------------------------------- the column

OPEN = {
    "merv": ["Sixty-one years at this and I still read the board with a pencil.",
             "They put me in the Hall of Fame for knowing when to shut up and take the under.",
             "My doctor says no more excitement. I told him I only bet defense."],
    "leslie": ["Good morning from the Delta, where the buffet opens at seven and so do I.",
               "Tunica taught me two things: never fear a fast team, and always tip the shuttle driver.",
               "Mama said points are the only thing nobody can take back."],
    "brett": ["The machine ran all night and so did the hair dryer.",
              "Mr. JuiceBox here, fully hydrated and fully modeled.",
              "I don't have feelings about games. I have deltas."],
    "shark": ["I'm writing this from a booth with my back to the wall, like always.",
              "Morning. Don't use my name on the phone.",
              "The sun's up over the boardwalk and so are my associates."],
}
TOP_LINE = ["{who} took the top of the board last night at {rec}, {u}.",
            "Top of the night: {who}, {rec}, {u}. Somebody frame it.",
            "{who} owned last night: {rec}, {u}."]
BOTTOM_LINE = ["Bottom of the barrel: {who}, {rec}, {u}.",
               "{who} brought up the rear at {rec}, {u}. It happens. It happens to {who} a lot.",
               "And at the bottom, {who}: {rec}, {u}. Somebody check on them."]
SWEEP_LINE = "{who} went {rec}. A clean sweep."
SELF_TOP = ["Yes, that was me on top. I'd like the record to show it.", "I'll be brief about my own night. I was great."]
SELF_BOTTOM = ["Yes, that was me at the bottom. We move.", "I'm not going to talk about my night. I'm going to talk about tonight."]
NO_NIGHT = ["No graded games from last night, so nobody gets to brag yet.", "Nothing graded from last night. Clean slate."]
PICK_VOICE = {
    "merv": {"side": ["{label}. {why} Defense travels.", "{label}. {why} I've seen that team guard a man into retirement."],
             "under": ["{label}. {why} Nobody's scoring on anybody in my world."]},
    "leslie": {"side": ["{label}. {why} Let 'em cook.", "{label}. {why} I want the team that brings the buckets."],
               "over": ["{label}. {why} Turn the scoreboard up, honey."]},
    "brett": {"side": ["{label}. {why} I don't make the rules. The machine does.", "{label}. {why} Big number, big hair, big night.",
                       "{label}. {why} The spreadsheet has spoken."]},
    "shark": {"side": ["{label}. {why}"], "over": ["{label}. {why}"], "under": ["{label}. {why}"]},
}
PASS = {"merv": "Merv found nothing he trusts tonight. He's going to bed at seven.",
        "leslie": "Leslie's sitting this one out. Not enough points on the board for her taste.",
        "brett": "Brett's board is empty. The machine says nothing, so Brett says nothing.",
        "shark": "No home dog in the Shark's window tonight. He says he's 'visiting a friend.'"}


BAD_BEAT = ["{who}'s {label} died {when}, on {scorer}'s {shot}.",
            "Bad beat for {who}: {label} was cashing until {scorer}'s {shot} {when}.",
            "{who} had {label} in the bag until {when}. Then {scorer} hit a {shot}."]
GOOD_BEAT = ["{who} got {label} home {when}, on {scorer}'s {shot}.",
             "{label} was dead for {who} until {scorer}'s {shot} {when}. Back door, front door, still a door."]
MY_BAD_BEAT = {"merv": "My {label} died {when} on a {shot}. Sixty-one years and it still stings.",
               "leslie": "My {label} went down {when} on a {shot}. Honey, I felt that one in my rings.",
               "brett": "{label} lost {when} on a {shot}. The machine calls that variance. I call it rude.",
               "shark": "{label} went sideways {when} on a {shot}. My associates are looking into it."}
MY_GOOD_BEAT = {"merv": "{label} came home {when} on a {shot}. You wait long enough, the game pays you.",
                "leslie": "{label} cashed {when} on a {shot}. Mama didn't raise a quitter.",
                "brett": "{label} flipped to a win {when} on a {shot}. Deltas, baby.",
                "shark": "{label} came through {when} on a {shot}. Like I said, I heard things."}


def beats(card: dict[str, Any] | None, book: Any = None, most: int = 2) -> list[dict[str, Any]]:
    """Last night's picks the play-by-play says were decided late (mac/moments.py), bad beats first."""
    from . import moments

    if not card:
        return []
    bk = book or moments.shared()
    out = []
    for key, ps in (card.get("picks") or {}).items():
        for p in ps:
            if p.get("result") not in ("win", "loss"):
                continue
            try:
                g = bk.game(p["game"], et_day(p["tip"]) if p.get("tip") else None)
            except (KeyError, ValueError):
                g = None
            ev = (g or {}).get("events") or []
            f = moments.flip(ev, p["kind"], p["side"], float(p["line"])) if ev else None
            if not f or f["left"] > moments.LATE or f["result"] != p["result"]:
                continue
            e = ev[f["i"]]
            names = {str(x["espn_id"]): x.get("name") for x in g.get("players", [])}
            scorer = names.get(str(e.get("pid")))
            if not scorer:
                continue
            last_per = max(x["per"] for x in ev)
            out.append({"key": key, "label": p["label"], "result": p["result"], "scorer": scorer,
                        "shot": moments.KINDS.get(e["kind"], "basket"), "when": moments.when(e, last_per), "left": f["left"]})
    out.sort(key=lambda b: (b["result"] != "loss", b["left"], b["key"]))
    return out[:most]


def beat_line(b: dict[str, Any], by: str, day: str) -> str:
    who = BY_KEY[b["key"]]["first"]
    if b["key"] == by:
        bank = MY_BAD_BEAT if b["result"] == "loss" else MY_GOOD_BEAT
        text = bank[by]
    else:
        text = _choose(BAD_BEAT if b["result"] == "loss" else GOOD_BEAT, "beat", day, b["key"])
    text = text.format(who=who, label=b["label"], when=b["when"], scorer=b["scorer"], shot=b["shot"])
    return text[0].upper() + text[1:]


def _u(v: float) -> str:
    return f"{v:+.2f} units".replace("+0.00", "even")


def _byline(day: str) -> str:
    return CAPPERS[Date.fromisoformat(day).toordinal() % len(CAPPERS)]["key"]


def column(day: str, picks: dict[str, list[dict[str, Any]]], last: dict[str, Any] | None, season: list[dict[str, Any]],
           late: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The 8:15 column: one handicapper's byline, last night's tops and bottoms, tonight's card in four voices."""
    by = _byline(day)
    me = BY_KEY[by]
    paras: list[str] = [_choose(OPEN[by], "open", day)]
    head = f"Picks are in for {Date.fromisoformat(day):%A}"
    night = [r for r in night_of(last) if r["w"] + r["l"] + r["p"]] if last else []
    if night:
        top, bottom = night[0], night[-1]
        if len(night) > 1 and top["units"] != bottom["units"]:
            paras.append(_choose(TOP_LINE, "top", day).format(who=top["first"], rec=top["record"], u=_u(top["units"])))
            paras.append(_choose(BOTTOM_LINE, "bottom", day).format(who=bottom["first"], rec=bottom["record"], u=_u(bottom["units"])))
            if top["key"] == by:
                paras.append(_choose(SELF_TOP, "self", day))
            elif bottom["key"] == by:
                paras.append(_choose(SELF_BOTTOM, "self", day))
            head = f"Tops: {top['first']}. Bottoms: {bottom['first']}."
        else:
            paras.append(f"Everybody broke about even last night. {top['first']} and the rest, {top['record']}.")
        for r in night:
            if r["l"] == 0 and r["w"] >= 2 and r["p"] == 0:
                paras.append(SWEEP_LINE.format(who=r["first"], rec=r["record"]))
        for b in late or []:  # the play-by-play's late flips: bad beats and back doors
            paras.append(beat_line(b, by, day))
    else:
        paras.append(_choose(NO_NIGHT, "none", day))
    lines = []
    for c in CAPPERS:
        ps = picks.get(c["key"]) or []
        if not ps:
            lines.append({"key": c["key"], "who": c["first"], "text": PASS[c["key"]]})
            continue
        bits = []
        for i, p in enumerate(ps):
            kind = "side" if p["kind"] == "side" else p["side"]
            bank = PICK_VOICE[c["key"]].get(kind) or PICK_VOICE[c["key"]]["side"]
            bits.append(_choose(bank, c["key"], day, i).format(label=p["label"], why=p["why"]))
        lines.append({"key": c["key"], "who": c["first"], "text": " ".join(bits)})
    lead = season[0] if season and (season[0]["w"] + season[0]["l"]) else None
    close = (f"Season ledger: {lead['first']} leads at {lead['record']}, {_u(lead['units'])}." if lead
             else "Season ledger starts tonight. Everybody's even.")
    return {"byline": by, "by": me["name"], "head": head, "paras": paras, "lines": lines, "close": close}


# ---------------------------------------------------------------- lock, grade, save


def lock_due(now: datetime) -> bool:
    return now.astimezone(ET).time() >= LOCK_AT


def lock(now: datetime, tops_dir: Path | None = None, dirs: list[Path] | None = None,
         scoring: dict[str, dict[str, float]] | None = None, force: bool = False) -> dict[str, Any] | None:
    """Make and save today's card once, at or after 8:15 AM Eastern. An existing card is never re-picked."""
    d = tops_dir or TOPS_DIR
    day = now.astimezone(ET).date().isoformat()
    f = d / f"{day}.json"
    if f.exists() or not (force or lock_due(now)):
        return None
    bd = board(day, now, dirs, scoring)
    picks = make_picks(bd, day)
    cards = load_cards(d)
    prev = (Date.fromisoformat(day) - timedelta(days=1)).isoformat()
    last = next((c for c in cards if c.get("date") == prev), None)
    card = {"date": day, "locked_at": now.astimezone(timezone.utc).isoformat(timespec="minutes"),
            "board": len(bd), "picks": picks, "column": column(day, picks, last, standings(cards), late=_safe_beats(last))}
    d.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(card, indent=1) + "\n")
    return card


def _safe_beats(card: dict[str, Any] | None) -> list[dict[str, Any]]:
    try:
        return beats(card)
    except Exception:  # noqa: BLE001 - the column never waits on the book
        return []


def grade_all(tops_dir: Path | None = None, scores: dict[str, dict[str, Any]] | None = None) -> int:
    """Grade every card with open picks. Returns how many cards changed."""
    d = tops_dir or TOPS_DIR
    files = sorted(d.glob("????-??-??.json"))
    open_files = [(f, c) for f in files if (c := _load(f)) and any(not p.get("result") for ps in c.get("picks", {}).values() for p in ps)]
    if not open_files:
        return 0
    scores = scores if scores is not None else final_scores()
    n = 0
    for f, c in open_files:
        if grade_card(c, scores):
            f.write_text(json.dumps(c, indent=1) + "\n")
            n += 1
    return n


def page_context(now: datetime, tops_dir: Path | None = None) -> dict[str, Any]:
    """Everything tops.html needs: today's card (or the latest), the season ledger, recent nights."""
    cards = load_cards(tops_dir)
    today = now.astimezone(ET).date().isoformat()
    card = next((c for c in reversed(cards) if c["date"] <= today), None)
    for c in cards:
        for ps in c.get("picks", {}).values():
            for p in ps:
                p["tip_et"] = _iso(p["tip"]).astimezone(ET).strftime("%-I:%M %p").replace(":00 ", " ")
    recent = [{"date": c["date"], "label": Date.fromisoformat(c["date"]).strftime("%a %b %-d"),
               "rows": night_of(c), "card": c} for c in reversed(cards) if c is not card][:7]
    return {"card": card, "is_today": bool(card and card["date"] == today), "today": today,
            "card_label": Date.fromisoformat(card["date"]).strftime("%A, %B %-d") if card else None,
            "ledger": standings(cards), "recent": recent, "cappers": CAPPERS, "by_key": BY_KEY,
            "disclosure": DISCLOSURE, "helpline": HELPLINE, "lock_label": "8:15 AM Eastern"}


def teaser(now: datetime, tops_dir: Path | None = None) -> dict[str, Any] | None:
    """One line for the front page rail."""
    cards = load_cards(tops_dir)
    today = now.astimezone(ET).date().isoformat()
    c = next((c for c in reversed(cards) if c["date"] == today), None)
    if c:
        n = sum(len(v) for v in c["picks"].values())
        if not n:
            return {"text": "No board today. The four are off"}
        return {"text": c["column"]["head"]}
    return {"text": "Picks in by 8:15 AM Eastern"}


def run(now: datetime | None = None) -> dict[str, Any]:
    """Called on every hub build: grade what's final, lock today's card if it's time."""
    now = now or datetime.now(timezone.utc)
    graded = grade_all()
    card = lock(now)
    return {"graded": graded, "locked": card["date"] if card else None,
            "picks": sum(len(v) for v in card["picks"].values()) if card else 0}


if __name__ == "__main__":
    import sys
    now = datetime.now(timezone.utc)
    if len(sys.argv) > 1 and sys.argv[1] == "preview":  # print today's card without saving it
        day = now.astimezone(ET).date().isoformat()
        bd = board(day, now)
        print(f"board: {len(bd)} games")
        print(json.dumps(make_picks(bd, day), indent=1))
    else:
        print(json.dumps(run(now)))
