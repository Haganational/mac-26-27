"""The Den's connectors: anchors in the games, the house ad, and ticket links.

Two pieces, both built on Agent 2's slate and results files (mac/den.py):

1. Beat the Desk. Each night one anchor "has the desk" and makes a public Pick 4.
   - Who: the anchors whose school plays tonight in a pickable game, rotating by date
     (sorted by roster number, position = date ordinal mod count).
   - Picks: their own school first (a homer pick, always), then the three games where our
     ratings and the market disagree most, taking our ratings' side. Too few rated games:
     fill with the closest games by the market, taking the favorite.
   - Locks: the desk is kept in data/den/desk/YYYY-MM-DD.json. Once any desk game tips the
     night's desk is frozen, so a ratings refit can never change a pick after tip.
   - The ledger also keeps every anchor's homer pick (their own school, every game), so a
     season board of all 67 anchors needs no accounts and no server.

2. The game card host and the partner rail. Each game gets the anchor of our school in it
   (the home side when both are ours) with a one-line homer call, and after finals the
   anchor of the worst-shooting team gets the Bricksanity call. Ticket links ("Going to the
   game", marked Ad) appear only when the game has a Vivid Seats URL, has not tipped, and
   AFFILIATE_TEMPLATE is set. ESPN's wsUser code is always stripped first.

Anchors are fictional AI personas, one per school, not affiliated with any school. Every
output carries that disclosure. Nothing here touches money: desk picks score Pick 4 points,
the same as a visitor's, and the ads sit beside the games, never in the scoring.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date as Date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from . import anchors as anchor_desk
from .leagues import ALL as LEAGUES

ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = ROOT / "data" / "den" / "desk"
RATINGS = ROOT / "data" / "model" / "ratings.json"

# ---------------------------------------------------------------- the one affiliate switch
# None = no ticket links anywhere. When the Vivid Seats program on Impact is approved, paste
# the Impact tracking link here. Two shapes work:
#   "https://vivid-seats.pxf.io/c/1234567/123456/12345"         -> we add ?u=<ticket url>
#   "https://vivid-seats.pxf.io/c/1234567/123456/12345?u={url}" -> {url} is filled in
# The ticket URL is percent-encoded and has ESPN's wsUser code removed before it goes in.
AFFILIATE_TEMPLATE: str | None = None

TICKET_HOSTS = ("vividseats.com",)
STRIP_PARAMS = {"wsuser"}  # ESPN's Vivid Seats partner code (wsUser=717), matched case-insensitively
PINK = {"light": "#d4146f", "dark": "#ff5fa2"}  # Miami pink: ticket links only
TICKETS_SHOWN = 3  # games in the night-level "Going to the game" box

DISCLOSURE = "Our anchors are fictional AI personas, one per school. They are not real people and are not affiliated with any school."
TAG = "AI anchor"

_UNSET: Any = object()


# ---------------------------------------------------------------- tickets

def clean_ticket_url(url: str | None) -> str | None:
    """A Vivid Seats URL with ESPN's wsUser code (and any fragment) removed; None for anything else."""
    if not url or not isinstance(url, str):
        return None
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not any(host == h or host.endswith("." + h) for h in TICKET_HOSTS):
        return None
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in STRIP_PARAMS]
    return urlunsplit(("https", parts.netloc, parts.path, urlencode(query), ""))


def affiliate_url(url: str | None, template: str | None = _UNSET) -> str | None:
    """The ticket URL wrapped in Matthew's Impact link, or None while there is no link (or no ticket URL)."""
    template = AFFILIATE_TEMPLATE if template is _UNSET else template
    clean = clean_ticket_url(url)
    if not template or not clean:
        return None
    if "{url}" in template:
        return template.replace("{url}", quote(clean, safe=""))
    parts = urlsplit(template)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "u"] + [("u", clean)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def ticket_index(paths: Iterable[Path] | None = None) -> dict[str, dict[str, Any]]:
    """game_id -> {"url", "low"} from every edition's schedule.json (raw ESPN URLs; cleaned later)."""
    if paths is None:
        paths = [ROOT / "data" / "schedule.json", *sorted((ROOT / "data" / "leagues").glob("*/schedule.json"))]
    out: dict[str, dict[str, Any]] = {}
    for p in paths:
        try:
            games = json.loads(Path(p).read_text()).get("games") or []
        except (OSError, ValueError):
            continue
        for g in games:
            t = g.get("tickets") or {}
            if t.get("url") and str(g.get("game_id")) not in out:
                out[str(g["game_id"])] = {"url": t["url"], "low": t.get("low")}
    return out


def ticket_for(game: dict[str, Any], tickets: dict[str, dict[str, Any]], now: datetime,
               template: str | None = _UNSET) -> dict[str, Any] | None:
    """The "Going to the game" link for one slate game, or None (no URL, already tipped, or no affiliate link yet)."""
    t = tickets.get(str(game.get("id")))
    if not t or _tipped(game, now):
        return None
    href = affiliate_url(t.get("url"), template)
    if not href:
        return None
    low = t.get("low")
    home, away = game.get("home") or {}, game.get("away") or {}
    return {"game_id": str(game["id"]), "href": href, "low": round(low) if isinstance(low, (int, float)) and low > 0 else None,
            "matchup": f"{away.get('short') or away.get('abbr', '')} at {home.get('short') or home.get('abbr', '')}",
            "tip": game.get("tip"), "label": "Going to the game", "partner": "Vivid Seats"}


# ---------------------------------------------------------------- anchors

def _team_colors() -> dict[str, tuple[str, str]]:
    return {t.key: (t.color, t.color2) for lg in LEAGUES.values() for t in lg.teams}


def _ink(bg: str) -> str:
    from .site_chrome import ink_on
    try:
        return ink_on(bg)
    except (ValueError, IndexError):
        return "#ffffff"


def anchor_card(key: str | None, portrait_prefix: str = "den/anchors/") -> dict[str, Any] | None:
    """Everything a page needs to show one anchor, with a monogram fallback when the portrait is missing."""
    a = anchor_desk.roster().get(key or "")
    if not a:
        return None
    color, color2 = _team_colors().get(key, ("#2a1a10", "#f0c75e"))
    initials = "".join(w[0] for w in a["name"].replace("-", " ").split() if w[:1].isalpha())[:2].upper()
    has = anchor_desk.portrait(key) is not None
    return {"key": key, "name": a["name"], "school": a.get("school", key), "tag": TAG,
            "portrait": f"{portrait_prefix}{key}.webp" if has else None,
            "initials": initials, "color": color, "color2": color2, "ink": _ink(color),
            "alt": f"{a['name']}, the {a.get('school', key)} AI anchor" + ("" if has else " (portrait coming)")}


def publish_portraits(site_root: Path, sub: str = "den/anchors") -> int:
    """Copy anchors/*.webp into the site (they are not published anywhere else yet). Returns the count."""
    dest = Path(site_root) / sub
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(anchor_desk.PORTRAITS.glob("*.webp")):
        shutil.copy2(p, dest / p.name)
        n += 1
    return n


def _side_key(side: dict[str, Any]) -> str | None:
    key = side.get("key")
    if not key and isinstance(side.get("anchor"), str):
        key = side["anchor"]
    if not key and isinstance(side.get("anchor"), dict):
        key = side["anchor"].get("key")
    return key if key in anchor_desk.roster() else None


def host_side(game: dict[str, Any]) -> str | None:
    """'home' or 'away': whose anchor hosts this game card (the home side when both are ours)."""
    for s in ("home", "away"):
        if _side_key(game.get(s) or {}):
            return s
    return None


def _other(side: str) -> str:
    return "away" if side == "home" else "home"


def _choose(options: list[str], *seed: Any) -> str:
    h = int(hashlib.sha1("|".join(map(str, seed)).encode()).hexdigest(), 16)
    return options[h % len(options)]


HOMER_FAV = [
    "{me} by our numbers and by my heart. Easy call.",
    "Our ratings like {me}. So do I. Shocking, I know.",
    "{me}. I'd take them anyway, but the numbers agree tonight.",
]
HOMER_DOG = [
    "Our numbers say {opp}. My desk says {me}. Worth {worth} if I'm right.",
    "{me} as the underdog, {worth} points if it lands. Yes, I'm a homer.",
    "I'm the {me} anchor. You knew where this was going.",
]
HOMER_FLAT = [
    "{me}. I'm the {me} anchor. That's the whole analysis.",
    "No line yet, no doubt here: {me}.",
]
RESULT_WIN = ["{me} gets it done. Told you.", "{me} wins. The homer pick cashes {worth} points."]
RESULT_LOSS = ["{opp} wins this one. I'll be back at the desk tomorrow.", "Not {me}'s night. {opp} takes it."]
BRICKS = [
    "{me} shot {pct} tonight. I'm the {me} anchor, so I'll say it: bricks.",
    "{me} built tonight's wall: {pct} from the field and the line.",
    "{me} at {pct}. Somebody check the rims. Then check the shooters.",
]


def homer_line(game: dict[str, Any], side: str, result: dict[str, Any] | None = None) -> str:
    """The host anchor's one line for this game, in their own homer voice (same game, same line)."""
    me, opp = (game.get(side) or {}), (game.get(_other(side)) or {})
    worth = (game.get("worth") or {}).get(side)
    fmt = {"me": me.get("short") or me.get("abbr", ""), "opp": opp.get("short") or opp.get("abbr", ""), "worth": worth}
    gid, key = game.get("id"), _side_key(me)
    if result and result.get("final") and result.get("winner_id") is not None:
        won = str(result["winner_id"]) == str(me.get("id"))
        return _choose(RESULT_WIN if won else RESULT_LOSS, key, gid, "final").format(**fmt)
    if worth is None:
        return _choose(HOMER_FLAT, key, gid).format(**fmt)
    return _choose(HOMER_FAV if worth < 50 else HOMER_DOG, key, gid).format(**fmt)


def bricksanity_call(slate: dict[str, Any], results: dict[str, Any] | None) -> dict[str, Any] | None:
    """After finals: the worst-shooting team's anchor owns it, in one line."""
    if not results or results.get("worst_shooter") in (None, ""):
        return None
    tid = str(results["worst_shooter"])
    for g in slate.get("games") or []:
        for s in ("home", "away"):
            side = g.get(s) or {}
            if str(side.get("id")) == tid and _side_key(side):
                a = anchor_card(_side_key(side))
                pct = (results.get("shooting") or {}).get(tid)
                pct_txt = "" if pct is None else f"{pct * 100 if pct <= 1 else pct:.1f}%"
                line = _choose(BRICKS if pct_txt else ["{me} wins Bricksanity tonight. Not the trophy we wanted."],
                               a["key"], slate.get("date")).format(me=side.get("short") or side.get("abbr", ""), pct=pct_txt)
                return {"anchor": a, "team_id": tid, "pct": pct, "line": line}
    return None


# ---------------------------------------------------------------- our ratings

def load_ratings(path: Path = RATINGS) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def ratings_win_home(ratings: dict[str, Any] | None, home_id: Any, away_id: Any, neutral: bool = False) -> float | None:
    """Home win chance from data/model/ratings.json, same formula as mac.ratings.project (no opening-week bump)."""
    if not ratings:
        return None
    by = {str(t["id"]): t for t in ratings.get("teams") or []}
    h, a = by.get(str(home_id)), by.get(str(away_id))
    if not h or not a:
        return None
    from .ratings import norm_cdf
    mu, tau, hca = ratings["mu"], ratings["tau"], (0.0 if neutral else ratings.get("hca", 0.0))
    sigma = (ratings.get("params") or {}).get("sigma_margin", 12.0)
    poss = h["adj_t"] + a["adj_t"] - tau
    eh = h["adj_o"] + a["adj_d"] - mu + hca
    ea = a["adj_o"] + h["adj_d"] - mu - hca
    return norm_cdf((eh - ea) * poss / 100 / sigma)


# ---------------------------------------------------------------- beat the desk

def _tip(game: dict[str, Any]) -> datetime | None:
    t = game.get("tip")
    if not t:
        return None
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def _tipped(game: dict[str, Any], now: datetime) -> bool:
    t = _tip(game)
    return t is not None and now >= t


def _pickable(game: dict[str, Any]) -> bool:
    w = game.get("worth") or {}
    return game.get("win_home") is not None and w.get("home") is not None and w.get("away") is not None


def _pick(game: dict[str, Any], side: str, why: str, kind: str) -> dict[str, Any]:
    s = game[side]
    return {"game_id": str(game["id"]), "side": side, "team_id": str(s.get("id")), "abbr": s.get("abbr"),
            "short": s.get("short"), "worth": game["worth"][side], "tip": game.get("tip"), "kind": kind, "why": why}


def desk_anchor(slate: dict[str, Any]) -> tuple[str, dict[str, Any], str] | None:
    """(anchor key, their game, their side): the rotation over anchors whose school plays a pickable game tonight."""
    roster = anchor_desk.roster()
    seen: dict[str, tuple[dict[str, Any], str]] = {}
    for g in sorted(slate.get("games") or [], key=lambda g: (g.get("tip") or "", str(g.get("id")))):
        if not _pickable(g):
            continue
        for s in ("home", "away"):
            k = _side_key(g.get(s) or {})
            if k and k not in seen:
                seen[k] = (g, s)
    if not seen:
        return None
    order = sorted(seen, key=lambda k: (roster[k]["id"], k))
    key = order[Date.fromisoformat(slate["date"]).toordinal() % len(order)]
    return key, seen[key][0], seen[key][1]


def desk_pick4(slate: dict[str, Any], ratings: dict[str, Any] | None) -> dict[str, Any] | None:
    """Tonight's desk: anchor card, four picks with a reason each, and the most it can score."""
    found = desk_anchor(slate)
    if not found:
        return None
    key, own, side = found
    picks = [_pick(own, side, "Homer pick: the anchor's own school, always.", "homer")]
    rest = [g for g in slate.get("games") or [] if _pickable(g) and str(g["id"]) != str(own["id"])]
    rated = []
    for g in rest:
        rh = ratings_win_home(ratings, (g.get("home") or {}).get("id"), (g.get("away") or {}).get("id"), bool(g.get("neutral")))
        if rh is not None:
            rated.append((-abs(rh - g["win_home"]), g.get("tip") or "", str(g["id"]), g, rh))
    rated.sort(key=lambda r: r[:3])
    for _, _, _, g, rh in rated[:3]:
        s = "home" if rh >= 0.5 else "away"
        ours, market = (rh if s == "home" else 1 - rh), (g["win_home"] if s == "home" else 1 - g["win_home"])
        picks.append(_pick(g, s, f"Our ratings {ours:.0%}, pregame win chance {market:.0%}.", "ratings"))
    used = {p["game_id"] for p in picks}
    close = sorted((g for g in rest if str(g["id"]) not in used), key=lambda g: (abs(g["win_home"] - 0.5), g.get("tip") or "", str(g["id"])))
    for g in close[: 4 - len(picks)]:
        s = "home" if g["win_home"] >= 0.5 else "away"
        picks.append(_pick(g, s, f"Closest game on the board; takes the favorite ({max(g['win_home'], 1 - g['win_home']):.0%} win chance).", "market"))
    return {"anchor": anchor_card(key), "picks": picks, "max": sum(p["worth"] for p in picks),
            "rule": "Pick 1 is the anchor's own school. Picks 2 to 4 are where our ratings disagree most with the pregame win chance, on our ratings' side."}


def homer_picks(slate: dict[str, Any]) -> list[dict[str, Any]]:
    """Every anchor's homer pick on this slate: their own school, every pickable game (both anchors when both are ours)."""
    out = []
    for g in slate.get("games") or []:
        if not _pickable(g):
            continue
        for s in ("home", "away"):
            k = _side_key(g.get(s) or {})
            if k:
                out.append({"key": k, **_pick(g, s, "Homer pick.", "homer")})
    return out


def score_picks(picks: list[dict[str, Any]], results: dict[str, Any] | None) -> dict[str, Any]:
    """Pick 4 points for picks against a results file: worth if right, 0 if wrong, ungraded until final."""
    finals = {str(r["id"]): r for r in (results or {}).get("games") or [] if r.get("final") and r.get("winner_id") is not None}
    pts = hits = graded = 0
    marks = []
    for p in picks:
        r = finals.get(p["game_id"])
        if r is None:
            marks.append(None)
            continue
        graded += 1
        ok = str(r["winner_id"]) == p["team_id"]
        hits += ok
        pts += p["worth"] if ok else 0
        marks.append(ok)
    return {"points": pts, "hits": hits, "graded": graded, "marks": marks}


def freeze(prev: dict[str, Any] | None, fresh: dict[str, Any], slate: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Merge a new ledger entry into the stored one so nothing changes after its game tips.

    The desk is all-or-nothing: once any of its four games tips, the stored desk stands.
    Homer picks freeze game by game."""
    if not prev:
        return fresh
    tips = {str(g["id"]): g for g in slate.get("games") or []}

    def tipped(gid: str) -> bool:
        g = tips.get(gid)
        return g is not None and _tipped(g, now)

    out = dict(fresh)
    pd = prev.get("desk")
    if pd and any(tipped(p["game_id"]) for p in pd.get("picks") or []):
        out["desk"] = pd
    old = {(h["key"], h["game_id"]): h for h in prev.get("homer") or [] if tipped(h["game_id"])}
    new = [old.get((h["key"], h["game_id"]), h) for h in fresh.get("homer") or []]
    have = {(h["key"], h["game_id"]) for h in new}
    out["homer"] = new + [h for k, h in old.items() if k not in have]  # a game that fell off the slate after tip stays
    return out


def update_ledger(slate: dict[str, Any], ratings: dict[str, Any] | None = _UNSET, now: datetime | None = None,
                  ledger_dir: Path = LEDGER_DIR) -> dict[str, Any]:
    """Write (or freeze-merge) data/den/desk/<date>.json for this slate and return it. Call once per build."""
    now = now or datetime.now(timezone.utc)
    ratings = load_ratings() if ratings is _UNSET else ratings
    path = Path(ledger_dir) / f"{slate['date']}.json"
    try:
        prev = json.loads(path.read_text())
    except (OSError, ValueError):
        prev = None
    fresh = {"date": slate["date"], "desk": desk_pick4(slate, ratings), "homer": homer_picks(slate)}
    entry = freeze(prev, fresh, slate, now)
    if entry != prev:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entry, indent=1, sort_keys=True) + "\n")
    return entry


def standings(ledgers: Iterable[dict[str, Any]], results_by_date: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Season board from the ledger: desk nights (Pick 4 points) and the Homer Ledger for every anchor."""
    desk: dict[str, dict[str, Any]] = {}
    homer: dict[str, dict[str, Any]] = {}
    for led in sorted(ledgers, key=lambda d: d.get("date", "")):
        res = results_by_date.get(led.get("date", ""))
        d = led.get("desk")
        if d and d.get("anchor"):
            sc = score_picks(d["picks"], res)
            if sc["graded"] == len(d["picks"]):
                row = desk.setdefault(d["anchor"]["key"], {"key": d["anchor"]["key"], "nights": 0, "points": 0, "hits": 0, "best": 0})
                row["nights"] += 1
                row["points"] += sc["points"]
                row["hits"] += sc["hits"]
                row["best"] = max(row["best"], sc["points"])
        for h in led.get("homer") or []:
            sc = score_picks([h], res)
            if not sc["graded"]:
                continue
            row = homer.setdefault(h["key"], {"key": h["key"], "games": 0, "wins": 0, "points": 0})
            row["games"] += 1
            row["wins"] += sc["hits"]
            row["points"] += sc["points"]

    def card(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**r, "anchor": anchor_card(r["key"])} for r in rows.values()]

    return {"desk": sorted(card(desk), key=lambda r: (-r["points"], -r["hits"], r["key"])),
            "homer": sorted(card(homer), key=lambda r: (-r["points"], -r["wins"], r["key"])),
            "disclosure": DISCLOSURE}


# ---------------------------------------------------------------- one call per build

def connect(slate: dict[str, Any], results: dict[str, Any] | None = None, ledger: dict[str, Any] | None = None,
            ratings: dict[str, Any] | None = _UNSET, tickets: dict[str, dict[str, Any]] | None = None,
            now: datetime | None = None, template: str | None = _UNSET) -> dict[str, Any]:
    """Everything the Den page needs from Agent 3 for one date: desk, per-game hosts and tickets, Bricksanity call."""
    now = now or datetime.now(timezone.utc)
    if ledger is None:
        ratings = load_ratings() if ratings is _UNSET else ratings
        ledger = {"desk": desk_pick4(slate, ratings), "homer": homer_picks(slate)}
    tickets = ticket_index() if tickets is None else tickets
    finals = {str(r["id"]): r for r in (results or {}).get("games") or []}
    cards: dict[str, dict[str, Any]] = {}
    for g in slate.get("games") or []:
        gid, side = str(g["id"]), host_side(g)
        cards[gid] = {"host": anchor_card(_side_key(g[side])) if side else None, "side": side,
                      "line": homer_line(g, side, finals.get(gid)) if side else None,
                      "tickets": ticket_for(g, tickets, now, template)}
    desk = ledger.get("desk")
    if desk:
        desk = {**desk, "locked": any(_tipped(g, now) for g in slate.get("games") or []
                                      if str(g["id"]) in {p["game_id"] for p in desk["picks"]}),
                "score": score_picks(desk["picks"], results) if results else None}
    going = sorted((c["tickets"] for c in cards.values() if c["tickets"]), key=lambda t: (t.get("tip") or "", t["game_id"]))
    return {"date": slate.get("date"), "disclosure": DISCLOSURE, "desk": desk, "cards": cards,
            "bricksanity": bricksanity_call(slate, results), "going": going[:TICKETS_SHOWN],
            "tickets_on": bool(AFFILIATE_TEMPLATE if template is _UNSET else template), "pink": PINK}


def build(site_root: Path, slate: dict[str, Any], results: dict[str, Any] | None = None,
          now: datetime | None = None, ledger_dir: Path = LEDGER_DIR) -> dict[str, Any]:
    """The hook for mac/den.py: update the ledger, write site/den/connect-<date>.json and desk-standings.json,
    copy the portraits once. Returns the connect dict (also what the Jinja partial takes)."""
    now = now or datetime.now(timezone.utc)
    ratings = load_ratings()
    ledger = update_ledger(slate, ratings, now, ledger_dir)
    out = connect(slate, results, ledger, ratings, now=now)
    den = Path(site_root) / "den"
    den.mkdir(parents=True, exist_ok=True)
    (den / f"connect-{slate['date']}.json").write_text(json.dumps(out, separators=(",", ":")))
    if not (den / "anchors").exists():
        publish_portraits(site_root)
    ledgers, res = [], {}
    for p in sorted(Path(ledger_dir).glob("*.json")):
        try:
            ledgers.append(json.loads(p.read_text()))
        except ValueError:
            continue
        rp = den / f"results-{p.stem}.json"
        if rp.exists():
            res[p.stem] = json.loads(rp.read_text())
    if results:
        res[slate["date"]] = results
    (den / "desk-standings.json").write_text(json.dumps(standings(ledgers, res), separators=(",", ":")))
    return out
