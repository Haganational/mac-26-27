from datetime import datetime, timezone

from mac import analysis
from mac.config import team_key_for_odds_name


def game(gid, date, home, away, hs=None, as_=None, conf=True):
    return {
        "game_id": gid, "date": date, "name": "", "short_name": "", "season_type": "reg",
        "neutral_site": False, "conference_game": conf, "venue": None, "venue_city": None, "venue_state": None,
        "home": {"espn_id": "", "key": home, "name": home, "abbr": "", "score": hs, "winner": None},
        "away": {"espn_id": "", "key": away, "name": away, "abbr": "", "score": as_, "winner": None},
        "status": "STATUS_FINAL" if hs is not None else "STATUS_SCHEDULED",
        "completed": hs is not None,
    }


def row(captured, book, market, outcome, price, point=None, event="ev1", home="Toledo Rockets", away="Akron Zips"):
    return {
        "captured_at": captured, "odds_event_id": event, "commence_time": "2026-12-05T19:00:00Z",
        "home_team": home, "away_team": away, "home_key": team_key_for_odds_name(home),
        "away_key": team_key_for_odds_name(away), "book": book, "book_last_update": captured,
        "market": market, "outcome": outcome, "price": price, "point": point,
    }


def test_odds_name_mapping():
    assert team_key_for_odds_name("Toledo Rockets") == "toledo"
    assert team_key_for_odds_name("Miami (OH) RedHawks") == "miami-oh"
    assert team_key_for_odds_name("Michigan Wolverines") is None


def test_standings_counts_conference_and_overall():
    games = [
        game("1", "2026-11-05T00:00Z", "toledo", None, 80, 70, conf=False),
        game("2", "2026-12-05T00:00Z", "toledo", "akron", 75, 70),
        game("3", "2026-12-08T00:00Z", "akron", "toledo", 90, 60),
    ]
    rows = {r["key"]: r for r in analysis.standings(games)}
    assert (rows["toledo"]["w"], rows["toledo"]["l"]) == (2, 1)
    assert (rows["toledo"]["cw"], rows["toledo"]["cl"]) == (1, 1)
    assert rows["akron"]["streak"] == "W1"
    assert rows["toledo"]["streak"] == "L1"


def test_line_history_prefers_pinnacle_and_tracks_movement():
    rows = [
        row("2026-12-01T12:00:00+00:00", "pinnacle", "spreads", "Toledo Rockets", -110, -3.5),
        row("2026-12-01T12:00:00+00:00", "draftkings", "spreads", "Toledo Rockets", -110, -4.0),
        row("2026-12-01T12:00:00+00:00", "pinnacle", "totals", "Over", -108, 145.5),
        row("2026-12-02T12:00:00+00:00", "pinnacle", "spreads", "Toledo Rockets", -110, -5.0),
        row("2026-12-02T12:00:00+00:00", "pinnacle", "totals", "Over", -108, 147.0),
    ]
    hist = analysis.line_history(rows)
    ev = hist["ev1"]
    assert ev["open_spread"] == -3.5
    assert ev["latest"]["spread"] == -5.0
    assert ev["spread_move"] == -1.5
    assert ev["total_move"] == 1.5
    assert ev["snapshots"][0]["books"] == 2


def test_consensus_is_median_without_pinnacle():
    rows = [
        row("t", "draftkings", "spreads", "Toledo Rockets", -110, -4.0),
        row("t", "fanduel", "spreads", "Toledo Rockets", -110, -3.0),
        row("t", "betmgm", "spreads", "Toledo Rockets", -110, -3.5),
    ]
    assert analysis.line_history(rows)["ev1"]["latest"]["spread"] == -3.5


def test_match_lines_to_games_and_ats():
    games = [game("g1", "2026-12-05T19:00Z", "toledo", "akron", 70, 68)]
    rows = [row("2026-12-05T12:00:00+00:00", "pinnacle", "spreads", "Toledo Rockets", -110, -3.5)]
    hist = analysis.line_history(rows)
    assert analysis.match_lines_to_games(games, hist) == {"g1": "ev1"}
    now = datetime(2026, 12, 6, tzinfo=timezone.utc)
    recent = analysis.recent_results(games, hist, now)
    assert recent[0]["ats_cover"] == "away"  # Toledo won by 2, needed 3.5
