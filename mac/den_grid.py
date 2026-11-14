"""Called Up: the Den's daily 3x3 grid. Rows are three of our schools, columns three NBA franchises.
Fill a square with a former player from that school who played for that franchise.

Input:  data/den/nba_alumni.json (tools/wikidata_nba_alumni.py, from Wikidata)
Output: site/den/grid-YYYY-MM-DD.json for today and the next two ET dates:
  {date, rows:[{id, short, edition}], cols:[{code, name}],
   cells:{"r,c": [player index, ...]},   every square has at least MIN_ANSWERS answers
   players:[name, ...],                  every alumnus of the three schools (the search list),
                                         so the list itself doesn't give the answers away
   source}
A player can be used once per grid. The same date always gives the same grid.
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
ALUMNI = ROOT / "data" / "den" / "nba_alumni.json"
ET = ZoneInfo("America/New_York")
MIN_ANSWERS = 1
DAYS_AHEAD = 2
TRIES = 4000


def load(path: Path = ALUMNI) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def _named(a: dict[str, Any]) -> bool:
    """Wikidata has a few players with no English label; leave them out rather than show a blank or a Q-id."""
    n = (a.get("name") or "").strip()
    return bool(n) and not (n[0] == "Q" and n[1:].isdigit())


def _index(data: dict[str, Any]) -> dict[str, dict[str, set[str]]]:
    """school id -> franchise code -> player names."""
    out: dict[str, dict[str, set[str]]] = {}
    for sid, s in (data.get("schools") or {}).items():
        for a in s.get("alumni") or []:
            if not _named(a):
                continue
            for code in a.get("teams") or []:
                out.setdefault(sid, {}).setdefault(code, set()).add(a["name"])
    return out


def make_grid(data: dict[str, Any], day: str, min_answers: int = MIN_ANSWERS) -> dict[str, Any] | None:
    """A solvable grid for one date, or None when the data can't support one."""
    idx = _index(data)
    schools = [s for s in idx if len(idx[s]) >= 3]
    if len(schools) < 3:
        return None
    rng = random.Random(int(hashlib.sha256(f"called-up:{day}".encode()).hexdigest()[:12], 16))
    for _ in range(TRIES):
        rows = rng.sample(sorted(schools), 3)
        common = [c for c in sorted(set.union(*(set(idx[r]) for r in rows)))
                  if all(len(idx[r].get(c, ())) >= min_answers for r in rows)]
        if len(common) < 3:
            continue
        cols = rng.sample(common, 3)
        cells = {(i, j): idx[r][c] for i, r in enumerate(rows) for j, c in enumerate(cols)}
        if not _distinct_solution(cells):
            continue
        return _shape(data, day, rows, cols, cells)
    return None


def _distinct_solution(cells: dict[tuple[int, int], set[str]]) -> bool:
    """True when the nine squares can be filled with nine different players (players are used once)."""
    order = sorted(cells, key=lambda k: len(cells[k]))
    used: set[str] = set()

    def go(i: int) -> bool:
        if i == len(order):
            return True
        for name in sorted(cells[order[i]]):
            if name not in used:
                used.add(name)
                if go(i + 1):
                    return True
                used.discard(name)
        return False
    return go(0)


def _shape(data: dict[str, Any], day: str, rows: list[str], cols: list[str],
           cells: dict[tuple[int, int], set[str]]) -> dict[str, Any]:
    schools, nick = data["schools"], data.get("franchises") or {}
    pool = sorted({a["name"] for r in rows for a in schools[r].get("alumni") or [] if _named(a)})
    at = {n: i for i, n in enumerate(pool)}
    return {
        "date": day,
        "rows": [{"id": r, "short": schools[r].get("short", r), "edition": schools[r].get("edition")} for r in rows],
        "cols": [{"code": c, "name": nick.get(c, c)} for c in cols],
        "cells": {f"{i},{j}": sorted(at[n] for n in v) for (i, j), v in sorted(cells.items())},
        "players": pool,
        "source": "Wikidata (CC0)",
    }


def check(grid: dict[str, Any], picks: dict[str, int]) -> dict[str, bool]:
    """Score a finished grid: {"r,c": player index} -> {"r,c": right?}. A player counts once, first square wins."""
    seen: set[int] = set()
    out = {}
    for k in sorted(picks):
        p = picks[k]
        ok = p in set(grid["cells"].get(k, [])) and p not in seen
        if ok:
            seen.add(p)
        out[k] = ok
    return out


def build(site_root: Path, now: datetime | None = None, path: Path = ALUMNI) -> int:
    """Write the grids for today and the next DAYS_AHEAD dates. Returns how many were written."""
    data = load(path)
    if not data:
        return 0
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ET).date()
    out = Path(site_root) / "den"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for k in range(DAYS_AHEAD + 1):
        day = (today + timedelta(days=k)).isoformat()
        g = make_grid(data, day)
        if g:
            (out / f"grid-{day}.json").write_text(json.dumps(g, separators=(",", ":"), ensure_ascii=False))
            n += 1
    return n
