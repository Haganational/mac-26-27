"""The model's projection log, one file per day.

Every run appends our number for each upcoming game. That log used to be one
model/projections.jsonl per league, rewritten every half hour, so git kept a full
copy of a 10 MB file at each snapshot (about 900 MB of repo history in one week,
Nov 2026). New rows now go to model/projections/<UTC day>.jsonl: a snapshot only
touches today's small file. The old single file stays as a frozen archive and is
still read first, so nothing is lost and no rows move.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

LEGACY = "projections.jsonl"
DAILY = "projections"


def files(model_dir: Path) -> list[Path]:
    """Every projection file in a model dir, oldest first: the frozen archive, then the daily files."""
    out = []
    legacy = model_dir / LEGACY
    if legacy.is_file():
        out.append(legacy)
    daily = model_dir / DAILY
    if daily.is_dir():
        out.extend(sorted(daily.glob("*.jsonl")))
    return out


def lines(model_dir: Path) -> Iterator[str]:
    """Raw non-blank lines across every projection file, oldest first."""
    for f in files(model_dir):
        with f.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield line


def append(model_dir: Path, rows: list[dict[str, Any]], now: datetime) -> Path:
    """Append rows to today's daily file (named by the run's UTC date)."""
    day = (now if now.tzinfo is None else now.astimezone(timezone.utc)).date().isoformat()
    path = model_dir / DAILY / f"{day}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return path

