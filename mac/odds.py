"""Snapshot MAC lines from The Odds API.

One call to /sports/basketball_ncaab/odds with three markets costs 3 requests
against the monthly quota (cost = markets x regions, where a named list of up to
10 bookmakers counts as one region; see config.ODDS_BOOKMAKERS). Three runs a day is about
270 requests a month, inside the 500-request free tier.

Snapshots are appended to data/lines/YYYY-MM-DD.jsonl, one flattened row per
(game, bookmaker, market, outcome), so git diffs stay small and append-only.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from .oddsboard import record_run
from .config import LINES_DIR, ODDS_BASE, ODDS_BOOKMAKERS, ODDS_MARKETS, ODDS_REGIONS, ODDS_SPORT, team_key_for_odds_name

TIMEOUT = 30


class OddsApiError(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise OddsApiError("ODDS_API_KEY is not set")
    return key


def fetch_ncaab_odds() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return (events, quota headers) for all upcoming NCAAB games with lines."""
    resp = requests.get(
        f"{ODDS_BASE}/sports/{ODDS_SPORT}/odds",
        params={
            "apiKey": api_key(),
            **({"bookmakers": ",".join(ODDS_BOOKMAKERS)} if ODDS_BOOKMAKERS else {"regions": ",".join(ODDS_REGIONS)}),
            "markets": ",".join(ODDS_MARKETS),
            "oddsFormat": "american",
            "dateFormat": "iso",
        },
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise OddsApiError(f"Odds API returned {resp.status_code}: {resp.text[:300]}")
    quota = {
        "requests_used": resp.headers.get("x-requests-used", ""),
        "requests_remaining": resp.headers.get("x-requests-remaining", ""),
        "requests_last": resp.headers.get("x-requests-last", ""),
    }
    return resp.json(), quota


def is_mac_event(event: dict[str, Any]) -> bool:
    return bool(team_key_for_odds_name(event["home_team"]) or team_key_for_odds_name(event["away_team"]))


def flatten_event(event: dict[str, Any], captured_at: str) -> Iterable[dict[str, Any]]:
    home, away = event["home_team"], event["away_team"]
    base = {
        "captured_at": captured_at,
        "odds_event_id": event["id"],
        "commence_time": event["commence_time"],
        "home_team": home,
        "away_team": away,
        "home_key": team_key_for_odds_name(home),
        "away_key": team_key_for_odds_name(away),
    }
    for book in event.get("bookmakers", []):
        for market in book.get("markets", []):
            for outcome in market.get("outcomes", []):
                yield {
                    **base,
                    "book": book["key"],
                    "book_last_update": market.get("last_update") or book.get("last_update"),
                    "market": market["key"],
                    "outcome": outcome["name"],  # team name, or Over/Under
                    "price": outcome.get("price"),
                    "point": outcome.get("point"),
                }


def snapshot_lines() -> dict[str, Any]:
    """Fetch, filter to MAC games, append rows to today's JSONL file."""
    captured_at = datetime.now(timezone.utc).replace(microsecond=0)
    events, quota = fetch_ncaab_odds()
    mac_events = [e for e in events if is_mac_event(e)]
    rows = [row for e in mac_events for row in flatten_event(e, captured_at.isoformat())]

    LINES_DIR.mkdir(parents=True, exist_ok=True)
    path = LINES_DIR / f"{captured_at.date().isoformat()}.jsonl"
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    summary = {
        "captured_at": captured_at.isoformat(),
        "ncaab_events": len(events),
        "mac_events": len(mac_events),
        "rows": len(rows),
        "file": str(path),
        "quota": quota,
    }
    record_run(summary)
    return summary


def load_all_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not LINES_DIR.exists():
        return rows
    for path in sorted(LINES_DIR.glob("*.jsonl")):
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows
