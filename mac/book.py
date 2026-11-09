"""The book: lean, D-I-wide storage so every conference can be rated like the MAC.

The MAC keeps its rich, readable files (data/lines/*.jsonl, data/boxscores/). Everything
D-I-wide lives under data/book/<season>/ in compact, gzipped, write-once files so the
repo stays light (a full season of every game is a few MB, not hundreds):

  conferences.json                 32 conferences and their team ids (ESPN standings)
  <season>/games/YYYY-MM-DD.json.gz   per game: player lines + lineup stints, as arrays
  <season>/odds/YYYYMMDDTHHMM.json.gz one file per odds snapshot, every D-I game, every book

Game files are keyed by the game's UTC date and only rewritten while that date is
inside the collector's refresh window. gzip is written with a fixed timestamp so an
unchanged file never shows up as a git change.

Nothing here makes extra requests: games come from the summary call ncaa.py already
makes for every D-I game, and odds from the single Odds API call we already make.
"""

from __future__ import annotations

import gzip
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from .config import SEASON, SHARED_DIR

BOOK_DIR = SHARED_DIR / "book"
CONF_PATH = BOOK_DIR / "conferences.json"
TIMEOUT = 30

# Player line columns, in order. Stints reference players by row index.
P_COLS = ("id", "name", "side", "pos", "starter", "min", "pts", "fgm", "fga", "tpm", "tpa",
          "ftm", "fta", "oreb", "dreb", "ast", "stl", "blk", "to", "pf")
SIDES = ("home", "away")


# ---------------------------------------------------------------- gzip json, deterministic


def write_gz(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(raw)
    data = buf.getvalue()
    if path.exists() and path.read_bytes() == data:
        return
    path.write_bytes(data)


def read_gz(path: Path) -> Any:
    with gzip.open(path, "rb") as fh:
        return json.loads(fh.read())


# ---------------------------------------------------------------- conferences


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch_conferences(season: int = SEASON) -> dict[str, Any]:
    resp = requests.get("https://site.api.espn.com/apis/v2/sports/basketball/mens-college-basketball/standings",
                        params={"season": season}, timeout=TIMEOUT)
    resp.raise_for_status()
    confs = []
    for c in resp.json().get("children", []):
        teams = [e["team"]["id"] for e in (c.get("standings") or {}).get("entries", []) if e.get("team")]
        confs.append({"id": str(c["id"]), "name": c.get("name"), "short": c.get("shortName") or c.get("abbreviation"),
                      "slug": _slug(c.get("shortName") or c.get("abbreviation") or str(c["id"])), "teams": teams})
    out = {"season": season, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "conferences": confs}
    BOOK_DIR.mkdir(parents=True, exist_ok=True)
    CONF_PATH.write_text(json.dumps(out, indent=0))
    return out


def conferences_stale(days: int = 7) -> bool:
    if not CONF_PATH.exists():
        return True
    fetched = datetime.fromisoformat(json.loads(CONF_PATH.read_text())["fetched_at"])
    return (datetime.now(timezone.utc) - fetched).days >= days


def load_conferences() -> list[dict[str, Any]]:
    if not CONF_PATH.exists():
        return []
    return json.loads(CONF_PATH.read_text())["conferences"]


def conference_of() -> dict[str, dict[str, Any]]:
    """team id -> conference"""
    return {tid: c for c in load_conferences() for tid in c["teams"]}


# ---------------------------------------------------------------- games: encode / decode


def encode_game(game: dict[str, Any]) -> dict[str, Any]:
    """Compact form of a game (pbp.game_from_summary shape): player lines and lineup stints."""
    side_of = {t["espn_id"]: t["home_away"] for t in game["teams"]}
    players = [p for p in game["players"] if side_of.get(p["team_espn_id"]) in SIDES]
    idx = {p["espn_id"]: i for i, p in enumerate(players)}
    rows = []
    for p in players:
        row = []
        for c in P_COLS:
            if c == "id":
                row.append(p["espn_id"])
            elif c == "side":
                row.append(SIDES.index(side_of[p["team_espn_id"]]))
            elif c == "pos":
                row.append(p.get("position"))
            elif c == "starter":  # bit 0 starter, bit 1 did not play
                row.append((1 if p.get("starter") else 0) | (2 if p.get("dnp") else 0))
            else:
                row.append(p.get(c))
        rows.append(row)
    # A player the play-by-play puts on the floor but the box score omits gets a blank row.
    for s in game["stints"]:
        for side in SIDES:
            for x in s[side]:
                if x not in idx:
                    idx[x] = len(rows)
                    rows.append([x, None, SIDES.index(side), None, 0] + [None] * (len(P_COLS) - 5))
    st = [[s["secs"], [idx[x] for x in s["home"]], [idx[x] for x in s["away"]], s["pts_h"], s["pts_a"], s["poss"],
           1 if s.get("bad") else 0] for s in game["stints"]]
    teams = {t["home_away"]: [t["espn_id"], t.get("abbr")] for t in game["teams"] if t["home_away"] in SIDES}
    return {"d": game.get("date"), "n": 1 if game.get("neutral_site") else 0,
            "t": [teams.get("home"), teams.get("away")], "p": rows, "s": st}


def decode_game(game_id: str, g: dict[str, Any]) -> dict[str, Any]:
    """Back to the shape pbp.py and player_ratings.py use."""
    teams = [{"espn_id": t[0], "abbr": t[1], "name": t[1], "home_away": SIDES[i]} for i, t in enumerate(g["t"]) if t]
    tid = [t[0] if t else None for t in g["t"]]
    players = []
    for r in g["p"]:
        p = dict(zip(P_COLS, r))
        players.append({"espn_id": p["id"], "name": p["name"], "team_espn_id": tid[p["side"]], "position": p["pos"],
                        "starter": bool(p["starter"] & 1), "dnp": bool(p["starter"] & 2),
                        **{k: p[k] for k in P_COLS[5:]},
                        "reb": None if p["oreb"] is None or p["dreb"] is None else p["oreb"] + p["dreb"]})
    ids = [r[0] for r in g["p"]]
    stints = [{"secs": s[0], "home": [ids[i] for i in s[1]], "away": [ids[i] for i in s[2]],
               "pts_h": s[3], "pts_a": s[4], "poss": s[5], **({"bad": True} if s[6] else {})} for s in g["s"]]
    return {"game_id": game_id, "date": g["d"], "neutral_site": bool(g["n"]), "teams": teams,
            "players": players, "stints": stints}


def _day(date_str: str | None) -> str:
    return (date_str or "unknown")[:10]


def games_dir(season: int) -> Path:
    return BOOK_DIR / str(season) / "games"


def save_games(season: int, games: dict[str, dict[str, Any]]) -> int:
    """Merge encoded games ({game_id: encoded}) into their day files."""
    by_day: dict[str, dict[str, Any]] = {}
    for gid, g in games.items():
        by_day.setdefault(_day(g.get("d")), {})[gid] = g
    for day, new in by_day.items():
        path = games_dir(season) / f"{day}.json.gz"
        cur = read_gz(path) if path.exists() else {}
        cur.update(new)
        write_gz(path, cur)
    return len(games)


def load_games(season: int, team_ids: set[str] | None = None) -> list[dict[str, Any]]:
    """Decoded games, optionally only those involving one of `team_ids`."""
    d = games_dir(season)
    if not d.exists():
        return []
    out = []
    for path in sorted(d.glob("*.json.gz")):
        for gid, g in read_gz(path).items():
            if team_ids is not None and not any(t and t[0] in team_ids for t in g["t"]):
                continue
            out.append(decode_game(gid, g))
    return out


def stored_game_ids(season: int) -> set[str]:
    d = games_dir(season)
    if not d.exists():
        return set()
    return {gid for p in d.glob("*.json.gz") for gid in read_gz(p)}


# ---------------------------------------------------------------- odds snapshots


def compact_odds(events: Iterable[dict[str, Any]]) -> list[list[Any]]:
    """[[event_id, commence, home, away, {book: [spread_home, price, total, over_price, ml_home, ml_away]}], ...]"""
    out = []
    for e in events:
        home = e["home_team"]
        books = {}
        for b in e.get("bookmakers", []):
            v = [None] * 6
            for m in b.get("markets", []):
                for o in m.get("outcomes", []):
                    if m["key"] == "spreads" and o["name"] == home:
                        v[0], v[1] = o.get("point"), o.get("price")
                    elif m["key"] == "totals" and o["name"] == "Over":
                        v[2], v[3] = o.get("point"), o.get("price")
                    elif m["key"] == "h2h":
                        v[4 if o["name"] == home else 5] = o.get("price")
            books[b["key"]] = v
        out.append([e["id"], e["commence_time"], home, e["away_team"], books])
    return out


def save_odds_snapshot(events: list[dict[str, Any]], captured_at: datetime, season: int = SEASON) -> str:
    path = BOOK_DIR / str(season) / "odds" / f"{captured_at.strftime('%Y%m%dT%H%M')}.json.gz"
    write_gz(path, {"captured_at": captured_at.isoformat(timespec="seconds"), "events": compact_odds(events)})
    return str(path)


def load_odds(season: int = SEASON) -> list[dict[str, Any]]:
    d = BOOK_DIR / str(season) / "odds"
    return [read_gz(p) for p in sorted(d.glob("*.json.gz"))] if d.exists() else []


# ---------------------------------------------------------------- conference tables (derived, never committed)


TEAM_KEYS = ("id", "name", "short", "abbr", "games", "adj_o", "adj_d", "adj_em", "adj_t", "net_pts", "sos",
             "raw_margin", "raw_total", "rk_adj_em", "rk_adj_o", "rk_adj_d", "rk_adj_t", "rk_sos")
PLAYER_KEYS = ("id", "name", "team_id", "abbr", "pos", "gp", "mpg", "min_pct", "ppg", "usage", "ts",
               "off", "def", "net", "prior_share", "returning")


def _round(v: Any) -> Any:
    return round(v, 2) if isinstance(v, float) else v


def conference_tables(games: list[dict[str, Any]], players: dict[str, dict[str, Any]], team_ratings: Any,
                      team_rows: list[dict[str, Any]], names: dict[str, dict[str, Any]], now: datetime,
                      weights: dict[str, Any]) -> dict[str, Any]:
    """Team and player tables for every conference, from one pass over the D-I book.

    These are rebuilt every run from the committed raw data and published with the site
    (site/book/<slug>.json), so they cost nothing in the repo.
    """
    from . import player_ratings as PR

    rows_by_id = {t["id"]: t for t in team_rows}
    index = []
    out: dict[str, Any] = {}
    for c in load_conferences():
        ids = set(c["teams"])
        teams = sorted((rows_by_id[t] for t in ids if t in rows_by_id), key=lambda t: -t["adj_em"])
        tbl = PR.table(games, players, team_ratings, now, weights, ids, names, with_onoff=False)
        team_rows_out = []
        for i, t in enumerate(teams, 1):
            team_rows_out.append({**{k: _round(t.get(k)) for k in TEAM_KEYS}, "rk_conf": i})
        plist = [{k: _round(p.get(k)) for k in PLAYER_KEYS} for p in tbl["players"]]
        avg = sum(t["adj_em"] for t in teams) / len(teams) if teams else None
        out[c["slug"]] = {"id": c["id"], "slug": c["slug"], "name": c["name"], "short": c["short"],
                          "as_of": tbl["as_of"], "games": tbl["games"], "teams": team_rows_out, "players": plist}
        index.append({"id": c["id"], "slug": c["slug"], "name": c["name"], "short": c["short"],
                      "teams": len(teams), "players": len(plist), "games": tbl["games"],
                      "avg_em": _round(avg), "top": teams[0]["short"] if teams else None})
    index.sort(key=lambda c: -(c["avg_em"] if c["avg_em"] is not None else -99))
    for i, c in enumerate(index, 1):
        c["rk"] = i
    return {"as_of": now.isoformat(timespec="seconds"), "conferences": index, "tables": out}
