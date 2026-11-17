"""Hometown papers and their anchors (Matthew, Nov 17 2026).

Every school has its own newspaper, with a town-based title that clashes with no current or former paper of
that town (data/papers.json, researched and checked by the desk), and the school's AI anchor edits it. The
anchor is the lead writer of the town's coverage: game stories and previews run under the home anchor's
byline and paper, and the anchor's leans (data/anchor_leans.json) color some of them with a one-line aside.
The visiting anchor sometimes gets a rejoinder.

papers.json   {"papers": {key: {"title", "town", "state", "status", "existing": [...], "checks": [...]}}}
anchor_leans  {"settings": {"aside_rate", "rejoinder_rate"}, "leans": {key: {"homer", "lean", "pet", "rival",
               "asides": {"win", "loss", "road_win", "road_loss", "rival_win", "rival_loss", "upset", "preview"}}}}

Asides may use {us}, {them}, {town}, {margin} and {rival}. They target anchors, towns and teams, and (Matthew,
Nov 17 2026) the Trump administration, its officials and fascist groups, for their public conduct; never
players, coaches, students, fans or other private people, and never a made-up quote. The house stance is
logic and empathy, not power and cruelty. Anchors are fictional AI personas, and every page that shows one says so.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import anchors
from .config import SHARED_DIR

PAPERS = SHARED_DIR / "papers.json"
LEANS = SHARED_DIR / "anchor_leans.json"
SITUATIONS = ("win", "loss", "road_win", "road_loss", "rival_win", "rival_loss", "upset", "preview")
PLACEHOLDERS = ("us", "them", "town", "margin", "rival")


@lru_cache(maxsize=1)
def papers() -> dict[str, dict[str, Any]]:
    return json.loads(PAPERS.read_text()).get("papers", {}) if PAPERS.exists() else {}


@lru_cache(maxsize=1)
def _leans_file() -> dict[str, Any]:
    return json.loads(LEANS.read_text()) if LEANS.exists() else {}


def leans() -> dict[str, dict[str, Any]]:
    return _leans_file().get("leans", {})


def settings() -> dict[str, Any]:
    return {"aside_rate": 0.6, "rejoinder_rate": 0.35, **_leans_file().get("settings", {})}


def paper(key: str | None) -> str | None:
    return (papers().get(key or "") or {}).get("title") or None


def desk(key: str | None, depth: int = 0) -> dict[str, Any] | None:
    """Who files for this school: the anchor (when Matthew's roster has them), the paper and the town.
    depth = how many folders below the site root the page's edition sits (0 for the MAC, 1 for the rest)."""
    if not key:
        return None
    a, title = anchors.roster().get(key), paper(key)
    if not a and not title:
        return None
    p = papers().get(key) or {}
    return {"key": key, "name": a["name"] if a else None, "paper": title, "town": p.get("town") or "",
            "portrait": bool(a and anchors.portrait(key)),
            "href": ("../" * depth) + f"anchors/{key}.html" if a else None}


def lead_key(home_key: str | None, away_key: str | None) -> str | None:
    """The home anchor leads a story; when the home school isn't one of ours, the visitors' anchor does."""
    return home_key if desk(home_key) else (away_key if desk(away_key) else None)


def byline(key: str | None) -> str | None:
    """'Ray Abernathy, The Athens Clarion'; 'The Athens Clarion' while the anchor is still a draft; None."""
    d = desk(key)
    if not d:
        return None
    if d["name"] and d["paper"]:
        return f"{d['name']}, {d['paper']}"
    return d["name"] or d["paper"]


def _roll(seed: str) -> float:
    return int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def aside(key: str | None, situation: str, seed: str, fill: dict[str, Any], rate: float | None = None,
          avoid: tuple[str, ...] = (), before: str | None = None) -> dict[str, str] | None:
    """One of the anchor's lines for this situation, or None (no lean, no line, or this story isn't one
    the anchor editorializes: `rate` of stories get one, picked by the seed so a page never flips).
    before = the game's tip time: the anchor's barometer going into it (mac/notebook.py) raises the rate
    when the team is on a tear or in a slump. It is worked out as of the tip, so the page still never flips."""
    ln = leans().get(key or "")
    if not ln:
        return None
    rate = settings()["aside_rate"] if rate is None else rate
    if before:
        from . import notebook
        rate = min(1.0, rate * notebook.mood_rate(key, before))
    if _roll(seed + "|gate") >= rate:
        return None
    pool = [s for s in (ln.get("asides") or {}).get(situation, []) if isinstance(s, str) and s.strip()
            and not any("{" + a + "}" in s for a in avoid)]
    if not pool:
        return None
    text = pool[int(_roll(seed + "|" + situation) * len(pool)) % len(pool)]
    vals = {k: "" for k in PLACEHOLDERS}
    vals.update({k: v for k, v in fill.items() if v is not None})
    try:
        text = text.format(**vals)
    except (KeyError, IndexError, ValueError):
        return None
    if "{" in text or "}" in text:
        return None
    a = anchors.roster().get(key or "")
    return {"key": key or "", "text": text.strip(), "name": a["name"] if a else "", "paper": paper(key) or ""}


def _school(key: str | None) -> str:
    from .leagues import ALL
    return next((t.short for lg in ALL.values() for t in lg.teams if t.key == key), "") if key else ""


def rival(key: str | None) -> str | None:
    return (leans().get(key or "") or {}).get("rival") or anchors.color().get(key or "", {}).get("rival")


def game_situation(us_won: bool, at_home: bool, rival_game: bool, underdog: bool) -> str:
    if rival_game:
        return "rival_win" if us_won else "rival_loss"
    if us_won and underdog:
        return "upset"
    if at_home:
        return "win" if us_won else "loss"
    return "road_win" if us_won else "road_loss"


def game_asides(home_key: str | None, away_key: str | None, home_won: bool, home_spread: float | None,
                names: dict[str, str], towns: dict[str, str], margin: int, seed: str, neutral: bool = False,
                before: str | None = None) -> list[dict[str, str]]:
    """The lead (home) anchor's aside on a finished game, then sometimes the visiting anchor's rejoinder."""
    out = []
    rv = bool(home_key and away_key and (rival(home_key) == away_key or rival(away_key) == home_key))
    for k, us, them, won, at_home, dog, rate in (
            (home_key, "home", "away", home_won, not neutral, home_spread is not None and home_spread > 0, None),
            (away_key, "away", "home", not home_won, False, home_spread is not None and home_spread < 0,
             settings()["rejoinder_rate"] if home_key in leans() else None)):
        if not k:
            continue
        sit = game_situation(won, at_home, rv, dog)
        fill = {"us": names.get(us, ""), "them": names.get(them, ""), "town": towns.get(k, ""),
                "margin": margin, "rival": _school(rival(k))}
        a = aside(k, sit, f"{seed}|{k}", fill, rate, before=before)
        if a:
            out.append(a)
    return out


def preview_aside(home_key: str | None, away_key: str | None, names: dict[str, str], towns: dict[str, str], seed: str,
                  before: str | None = None) -> list[dict[str, str]]:
    out = []
    for k, us, them, rate in ((home_key, "home", "away", None), (away_key, "away", "home", settings()["rejoinder_rate"] if home_key in leans() else None)):
        if not k:
            continue
        fill = {"us": names.get(us, ""), "them": names.get(them, ""), "town": towns.get(k, ""), "margin": "",
                "rival": _school(rival(k))}
        # the visitors' anchor isn't in their own town for this one, so skip their lines that name it
        a = aside(k, "preview", f"{seed}|pre|{k}", fill, rate, avoid=("town",) if k == away_key else (), before=before)
        if a:
            out.append(a)
    return out
