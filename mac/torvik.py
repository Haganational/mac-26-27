"""Bart Torvik's T-Rank numbers (barttorvik.com), fetched from his published exports.

Only the plain CSV exports are used, never the HTML pages:

    {year}_team_results.csv     current season-to-date ratings
    {year}_super_sked.csv       schedule with T-Rank's game projections

barttorvik.com/robots.txt (checked Nov 14, 2026) asks every client to wait 10 seconds between
requests and disallows /*.json, which covers the time-machine snapshots. Those are not fetched.
It also fully disallows named AI crawlers (ClaudeBot, GPTBot, ...). Fetching runs only on
Matthew's say-so; see the PR that added this file.

"year" is the season's ending year (2026 = 2025-26). Raw files are saved untouched under
data/torvik/raw/ so the backtest can be rerun without fetching again.

Torvik data is NOT published on the site. It feeds the backtest only, until Matthew decides
on attribution (see the PR that added this file).

    python -m mac.torvik fetch 2027      # season CSVs for 2026-27 (2 requests)
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import requests

BASE = "https://barttorvik.com"
ROOT = Path(__file__).resolve().parents[1] / "data" / "torvik"
RAW = ROOT / "raw"
USER_AGENT = "hardwoodbricks-research/1.0 (+https://hardwoodbricks.com)"
PAUSE = 10.0  # robots.txt Crawl-Delay
TIMEOUT = 30


# ---------------------------------------------------------------- fetching


def _get(session: requests.Session, path: str) -> bytes | None:
    url = f"{BASE}/{path}"
    try:
        resp = session.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as exc:
        print(f"  {path}: {exc}")
        return None
    body = resp.content
    looks_html = body[:200].lstrip().lower().startswith((b"<!doctype", b"<html"))
    print(f"  {path}: {resp.status_code} {len(body)} bytes{' (html, skipped)' if looks_html else ''}")
    if resp.status_code != 200 or looks_html or not body:
        return None
    return body


def _save(path: str, body: bytes) -> Path:
    out = RAW / path.replace("/", "__")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(body)
    return out


def fetch_season(year: int, session: requests.Session | None = None) -> list[Path]:
    session = session or requests.Session()
    saved = []
    for path in (f"{year}_team_results.csv", f"{year}_super_sked.csv"):
        body = _get(session, path)
        if body:
            saved.append(_save(path, body))
        time.sleep(PAUSE)
    return saved


# ---------------------------------------------------------------- parsing

def load_team_results(year: int) -> list[dict[str, str]]:
    path = RAW / f"{year}_team_results.csv"
    if not path.exists():
        return []
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8", errors="replace"))))


# ---------------------------------------------------------------- names

# Torvik's spelling -> ESPN short name, where the plain match below misses. Extend from the
# "unmatched" list that `python -m mac.torvik names` prints after a fetch.
ALIASES: dict[str, str] = {
    "Connecticut": "UConn",
    "Mississippi": "Ole Miss",
    "Penn": "Pennsylvania",
    "Miami FL": "Miami",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("'", "").replace(".", " ")
    s = re.sub(r"\bst\b", "state", s)
    s = re.sub(r"\bsaint\b", "st", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def name_map(torvik_names: set[str], teams: dict[str, dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    """Match Torvik team names to ESPN ids. Returns (map, unmatched Torvik names).

    Exact matches only (after normalizing "St." and punctuation): a wrong match silently
    corrupts the blend, a miss just drops that team until an alias is added.
    """
    index: dict[str, str | None] = {}
    for tid, t in teams.items():
        key = _norm(t.get("short", ""))
        if key:
            index[key] = tid if key not in index else None  # ambiguous -> unusable
    out, missing = {}, []
    for name in sorted(torvik_names):
        tid = index.get(_norm(ALIASES.get(name, name)))
        if tid:
            out[name] = tid
        else:
            missing.append(name)
    return out, missing


# ---------------------------------------------------------------- cli


def main(argv: list[str]) -> None:
    if len(argv) >= 2 and argv[0] == "fetch":
        for y in argv[1:]:
            print(f"season {y}")
            fetch_season(int(y))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
