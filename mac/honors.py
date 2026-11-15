"""What the social cards said about each school, kept on its team page (Matthew, Nov 15 2026).

Two kinds of post land on a team page, newest first, for the whole season:

  potn     the school's player was its edition's Player of the Night (the potn card's slide)
  upset    the school won outright as an underdog of MIN_BRICK+ points (the loser's page gets it
           as "bricked", the name of the card)

Both come from the same functions the cards use (mac.cards), run over this edition's games, so a
team page and the night's card always agree. Feature films pinned to the top of a team's
multimedia section live in data/films.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import cards
from .den import ET, load_boxes, load_games
from .leagues import ROOT, League

FILMS = ROOT / "data" / "films.json"


def films() -> dict[str, list[dict[str, Any]]]:
    """team key -> its feature films, pinned first."""
    if not FILMS.exists():
        return {}
    return {k: v for k, v in json.loads(FILMS.read_text()).get("films", {}).items() if v}


def _line(r: dict[str, Any]) -> str:
    bits = [f"{r['pts']} points"]
    if r["reb"] >= 5:
        bits.append(f"{r['reb']} rebounds")
    if r["ast"] >= 5:
        bits.append(f"{r['ast']} assists")
    return ", ".join(bits)


def season(lg: League, now: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
    """team key -> honors, newest first."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ET).date().isoformat()
    games = load_games([lg.data_dir])
    ours = {t.key for t in lg.teams}
    finals = [g for g in games.values() if g.get("completed")]
    days = sorted({cards.et_day(g["date"]) for g in finals if cards.et_day(g["date"]) <= today})
    boxes = load_boxes([lg.data_dir], {g["game_id"] for g in finals})
    out: dict[str, list[dict[str, Any]]] = {}
    for day in days:
        when = cards.pretty_day(day)
        for r in cards.players_of_the_night(day, games, boxes):
            if r["league"].key != lg.key:
                continue
            res = f"{'W' if r['won'] else 'L'} {r['us']}-{r['them']} {'vs.' if r['home'] or r['neutral'] else 'at'} {r['opp']}"
            out.setdefault(r["team"].key, []).append({
                "day": day, "when": when, "kind": "potn", "label": "Player of the Night",
                "text": f"{r['name']}: {_line(r)} ({res})", "game_id": r["game_id"]})
        for b in cards.bricks(day, games):
            g, pts = b["game"], b["points"]
            score = f"{b['dog'].get('score')}-{b['fav'].get('score')}"
            pts_s = f"{pts:g}"
            if b["dog_key"] in ours:
                out.setdefault(b["dog_key"], []).append({
                    "day": day, "when": when, "kind": "upset", "label": "Upset",
                    "text": f"Beat {cards.nick(b['fav'])} {score} as a {pts_s}-point underdog", "game_id": g["game_id"]})
            if b["fav_key"] in ours:
                out.setdefault(b["fav_key"], []).append({
                    "day": day, "when": when, "kind": "bricked", "label": "Bricked",
                    "text": f"Lost to {cards.nick(b['dog'])} {b['fav'].get('score')}-{b['dog'].get('score')} as a {pts_s}-point favorite",
                    "game_id": g["game_id"]})
    for v in out.values():
        v.sort(key=lambda h: h["day"], reverse=True)
    return out
