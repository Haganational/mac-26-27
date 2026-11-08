"""Build a local SQLite database from the JSON data files for ad hoc analysis.

Usage: python -m mac.collect build-db  (writes data/mac.sqlite, which is gitignored)
"""

from __future__ import annotations

import sqlite3

from .config import DATA_DIR, TEAMS
from .espn import load_schedule
from .odds import load_all_rows

DB_PATH = DATA_DIR / "mac.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
  key TEXT PRIMARY KEY, espn_id TEXT, abbr TEXT, name TEXT, short TEXT
);
CREATE TABLE IF NOT EXISTS games (
  game_id TEXT PRIMARY KEY, date TEXT, name TEXT, short_name TEXT, season_type TEXT,
  neutral_site INTEGER, conference_game INTEGER, venue TEXT,
  home_key TEXT, home_name TEXT, home_score INTEGER,
  away_key TEXT, away_name TEXT, away_score INTEGER,
  status TEXT, completed INTEGER
);
CREATE TABLE IF NOT EXISTS line_rows (
  captured_at TEXT, odds_event_id TEXT, commence_time TEXT,
  home_team TEXT, away_team TEXT, home_key TEXT, away_key TEXT,
  book TEXT, book_last_update TEXT, market TEXT, outcome TEXT, price REAL, point REAL
);
CREATE INDEX IF NOT EXISTS ix_line_rows_event ON line_rows(odds_event_id, captured_at);
"""


def build() -> str:
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    con.executemany(
        "INSERT INTO teams VALUES (?,?,?,?,?)",
        [(t.key, t.espn_id, t.abbr, t.name, t.short) for t in TEAMS],
    )
    con.executemany(
        "INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                g["game_id"], g["date"], g["name"], g["short_name"], g["season_type"],
                int(g["neutral_site"]), int(g["conference_game"]), g["venue"],
                g["home"]["key"], g["home"]["name"], g["home"]["score"],
                g["away"]["key"], g["away"]["name"], g["away"]["score"],
                g["status"], int(g["completed"]),
            )
            for g in load_schedule()["games"]
        ],
    )
    con.executemany(
        "INSERT INTO line_rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                r["captured_at"], r["odds_event_id"], r["commence_time"], r["home_team"], r["away_team"],
                r.get("home_key"), r.get("away_key"), r["book"], r.get("book_last_update"),
                r["market"], r["outcome"], r.get("price"), r.get("point"),
            )
            for r in load_all_rows()
        ],
    )
    con.commit()
    con.close()
    return str(DB_PATH)
