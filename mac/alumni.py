"""Off the Court: each school's famous alumni, told by that school's anchor.

data/alumni.json holds a few researched stories per school. Every story has a checked `fact`
with its `source` (and the `evidence` sentence from that page), a `lean` (cheer, scorn or
neutral: the publisher's voice is openly progressive, so trailblazers get warmth and tycoons a
raised eyebrow, always about their public record), and the `line` the anchor says on air.

The shows take one story at a time, rotating by date, so a school's stories come round in turn.
Game stories borrow the plain `fact` as a flavor line (gamer.load_flavor).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "alumni.json"


@lru_cache(maxsize=1)
def load() -> dict[str, list[dict[str, Any]]]:
    return json.loads(PATH.read_text())["alumni"] if PATH.exists() else {}


def stories(key: str) -> list[dict[str, Any]]:
    return [s for s in load().get(key, []) if s.get("line") and s.get("fact") and s.get("source")]


def _n(seed: str) -> int:
    return int(hashlib.sha1(seed.encode()).hexdigest(), 16)


def pick(key: str, day: str) -> dict[str, Any] | None:
    """The school's story for this day: they come round in turn, from a start that differs by school."""
    pool = stories(key)
    if not pool:
        return None
    return pool[(date.fromisoformat(day).toordinal() + _n(key)) % len(pool)]


def segment(key: str, day: str, school: str, color: str | None = None) -> dict[str, Any] | None:
    """One 'Off the court' segment for a show, read by the school's anchor (anchors.team_of reads card.key)."""
    s = pick(key, day)
    if not s:
        return None
    host = s["source"].split("/")[2].removeprefix("www.").removeprefix("en.") if "//" in s["source"] else ""
    return {"kind": "offcourt", "text": f"Off the court. {s['line']}",
            "card": {"key": key, "school": school, "color": color, "name": s["name"], "known_for": s.get("known_for"),
                     "years": s.get("years"), "source": "Wikipedia" if host.startswith("wikipedia") else host}}


def choose(keys: list[str], day: str, n: int = 1) -> list[str]:
    """Which of the schools on tonight's show tell a story: up to n of those that have one, varying by day."""
    have = sorted({k for k in keys if k and stories(k)})
    have.sort(key=lambda k: _n(f"{day}:{k}"))
    return have[:n]


def flavor_lines(key: str, school: str) -> list[dict[str, str]]:
    """The same stories as flavor lines for game write-ups, in the house's plain voice."""
    return [{"text": f"Off the court, {school} claims {s['name']}: {s['fact']}", "source": s["source"], "kind": "alumni"}
            for s in stories(key)]
