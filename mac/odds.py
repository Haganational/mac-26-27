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
from .config import LEAGUE, LEAGUES, LINES_DIR, ODDS_BASE, ODDS_BOOKMAKERS, ODDS_MARKETS, ODDS_REGIONS, ODDS_SPORT, team_key_for_odds_name

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
    """Fetch, append MAC rows to today's JSONL file, and keep every game in the book."""
    captured_at = datetime.now(timezone.utc).replace(microsecond=0)
    events, quota = fetch_ncaab_odds()
    mac_events = [e for e in events if is_mac_event(e)]
    rows = [row for e in mac_events for row in flatten_event(e, captured_at.isoformat())]

    LINES_DIR.mkdir(parents=True, exist_ok=True)
    path = LINES_DIR / f"{captured_at.date().isoformat()}.jsonl"
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    # The other editions' games ride on the same pull: no extra API requests.
    other = {lg.key: write_league_rows(lg, events, captured_at) for lg in LEAGUES.values() if lg.key != LEAGUE.key}

    # Every D-I game, every book, for the book on other conferences. Compact and gzipped.
    from . import book
    book_file = book.save_odds_snapshot(events, captured_at) if events else None

    summary = {
        "captured_at": captured_at.isoformat(),
        "ncaab_events": len(events),
        "book_file": book_file,
        "mac_events": len(mac_events),
        "other_leagues": other,
        "rows": len(rows),
        "file": str(path),
        "quota": quota,
    }
    record_run(summary)
    return summary


def league_rows(lg: Any, events: list[dict[str, Any]], captured_at: str) -> list[dict[str, Any]]:
    """Line rows for one league's games, team keys from that league."""
    rows = []
    for e in events:
        hk, ak = lg.team_for_odds_name(e["home_team"]), lg.team_for_odds_name(e["away_team"])
        if hk or ak:
            for row in flatten_event(e, captured_at):
                rows.append({**row, "home_key": hk, "away_key": ak})
    return rows


def write_league_rows(lg: Any, events: list[dict[str, Any]], captured_at: datetime) -> int:
    rows = league_rows(lg, events, captured_at.isoformat())
    d = lg.data_dir / "lines"
    d.mkdir(parents=True, exist_ok=True)
    with (d / f"{captured_at.date().isoformat()}.jsonl").open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return len(rows)


def backfill_from_book(lg: Any) -> dict[str, Any]:
    """Rebuild a league's line rows from the Almanac's compact snapshots of every D-I game.

    Used once when an edition launches, so its line history starts when the Almanac's did.
    The compact snapshots keep each book's price but not its own update time, so
    book_last_update is the capture time.
    """
    from . import book
    d = lg.data_dir / "lines"
    if d.exists() and any(d.glob("*.jsonl")):
        return {"skipped": "lines already exist"}
    d.mkdir(parents=True, exist_ok=True)
    n = 0
    for snap in book.load_odds():
        cap = snap["captured_at"]
        events = []
        for eid, commence, home, away, books in snap["events"]:
            if not (lg.team_for_odds_name(home) or lg.team_for_odds_name(away)):
                continue
            bms = []
            for bk, v in books.items():
                mk = []
                if v[0] is not None:
                    mk.append({"key": "spreads", "outcomes": [{"name": home, "point": v[0], "price": v[1]}]})
                if v[2] is not None:
                    mk.append({"key": "totals", "outcomes": [{"name": "Over", "point": v[2], "price": v[3]}]})
                if v[4] is not None or v[5] is not None:
                    mk.append({"key": "h2h", "outcomes": [o for o in ({"name": home, "price": v[4]}, {"name": away, "price": v[5]}) if o["price"] is not None]})
                if mk:
                    bms.append({"key": bk, "last_update": cap, "markets": mk})
            events.append({"id": eid, "commence_time": commence, "home_team": home, "away_team": away, "bookmakers": bms})
        rows = league_rows(lg, events, cap)
        if rows:
            with (d / f"{cap[:10]}.jsonl").open("a") as fh:
                for row in rows:
                    fh.write(json.dumps(row, separators=(",", ":")) + "\n")
            n += len(rows)
    return {"rows": n}


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
