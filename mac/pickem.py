"""Anchor Pick'em on air: the Den's Beat the Desk ledger, read on the shows.

The ledger (data/den/desk/<date>.json, written by mac/den_connect.py) holds the night's desk
anchor and their Pick 4, frozen at tip, plus every anchor's homer pick. This module only reads
it: MidMaxx60 gets the desk anchor calling tonight's four (and how last night's desk did), and
The Big Mid gets the season board. No ledger for the day, no segment.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from . import anchors, den_connect
from .config import SITE_ROOT

NUM = ["zero", "one", "two", "three", "four"]
BOARD_TOP = 5


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def ledger(day: str, ledger_dir: Path | None = None) -> dict[str, Any] | None:
    return _load((ledger_dir or den_connect.LEDGER_DIR) / f"{day}.json")


def results(day: str, site: Path | None = None) -> dict[str, Any] | None:
    return _load((site or SITE_ROOT) / "den" / f"results-{day}.json")


def _list(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


def _said(short: str) -> str:
    """'Sacramento St' is read 'Sacramento State', never 'Saint'."""
    return short[:-3] + " State" if short.endswith(" St") else short


def last_night(day: str, ledger_dir: Path | None = None, site: Path | None = None) -> dict[str, Any] | None:
    """How the previous day's desk did, once all four of its games are final."""
    prev = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    desk = (ledger(prev, ledger_dir) or {}).get("desk")
    if not desk or not desk.get("anchor"):
        return None
    sc = den_connect.score_picks(desk["picks"], results(prev, site))
    if sc["graded"] != len(desk["picks"]):
        return None
    return {"key": desk["anchor"]["key"], "name": desk["anchor"]["name"], "hits": sc["hits"], "of": sc["graded"], "points": sc["points"]}


def segment(day: str, ledger_dir: Path | None = None, site: Path | None = None) -> dict[str, Any] | None:
    """Tonight's desk for MidMaxx60, read by the anchor who has it (anchors.team_of reads card.key)."""
    desk = (ledger(day, ledger_dir) or {}).get("desk")
    if not desk or not desk.get("anchor") or not desk.get("picks"):
        return None
    a = desk["anchor"]
    text = f"Anchor Pick'em. I have the desk tonight, and I'm taking {_list([_said(p['short']) for p in desk['picks']])}."
    was = last_night(day, ledger_dir, site)
    if was:
        who = "I" if was["key"] == a["key"] else anchors.first_name(was["name"])
        text += f" Last night {who} went {NUM[was['hits']]} for {NUM[was['of']]}."
    return {"kind": "pickem", "text": text,
            "card": {"key": a["key"], "school": a["school"], "color": a.get("color"), "name": a["name"], "max": desk.get("max"),
                     "picks": [{"short": p["short"], "worth": p["worth"], "homer": p.get("kind") == "homer"} for p in desk["picks"]],
                     "last": was}}


def board(ledger_dir: Path | None = None, site: Path | None = None) -> dict[str, Any] | None:
    """The season board for The Big Mid: desk points and the Homer Ledger, from every graded night."""
    d = ledger_dir or den_connect.LEDGER_DIR
    ledgers = [x for p in sorted(d.glob("*.json")) if (x := _load(p))]
    st = den_connect.standings(ledgers, {x["date"]: r for x in ledgers if (r := results(x["date"], site))})
    desk, homer = st["desk"][:BOARD_TOP], [r for r in st["homer"] if r["games"] >= 2][:BOARD_TOP]
    if not desk:
        return None
    top = desk[0]
    text = (f"Anchor Pick'em. {top['anchor']['name']} of the {top['anchor']['school']} desk leads the board with {top['points']} points"
            + ("" if top["nights"] == 1 else f" over {top['nights']} nights") + ".")
    if homer:
        h = homer[0]
        text += f" The best homer so far is {h['anchor']['name']}: {h['anchor']['school']} is {h['wins']} and {h['games'] - h['wins']} when picked."
    text += " Make your own four at the Den."

    def row(r: dict[str, Any]) -> dict[str, Any]:
        return {"name": r["anchor"]["name"], "school": r["anchor"]["school"], "color": r["anchor"]["color"]}

    return {"kind": "pickem", "text": text,
            "card": {"key": top["key"], "desk": [{**row(r), "points": r["points"], "nights": r["nights"]} for r in desk],
                     "homer": [{**row(r), "wins": r["wins"], "losses": r["games"] - r["wins"], "points": r["points"]} for r in homer]}}
