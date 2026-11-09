from datetime import datetime, timedelta, timezone

from mac.today import move_item, note_item, ou_item

NOW = datetime(2026, 11, 9, 13, tzinfo=timezone.utc)


def _game(op, now):
    return {"home": {"name": "Bowling Green Falcons", "key": "bowling-green", "abbr": "BGSU"},
            "away": {"name": "Cleveland State Vikings", "abbr": "CLEV"},
            "line": {"open_spread": op, "latest": {"spread": now}}}


def test_line_move_needs_a_real_move_and_reads_from_the_favorite():
    assert move_item([_game(-11, -12)]) is None
    m = move_item([_game(-11, -12.5)])
    assert m["text"] == "Line move of the day: Bowling Green opened as an 11-point favorite against Cleveland State and is now a 12.5-point favorite."
    flip = move_item([_game(-1, 2)])
    assert "Cleveland State opened as a 1-point underdog" in flip["text"] and "now a 2-point favorite" in flip["text"]


def test_over_under_needs_games_and_a_lean():
    ou = {"cur_season": 2027, "season_cards": [{"season": 2027, "n": 21, "o": 6, "u": 15, "p": 0, "avg_diff": -9.3}]}
    assert "15-6 to the under" in ou_item(ou)["text"]
    ou["season_cards"][0].update(n=4)
    assert ou_item(ou) is None


def test_note_only_when_fresh_and_trimmed():
    d = {"published": (NOW - timedelta(hours=7)).isoformat(), "title": "Broncos from deep",
         "text": "WMU will be a handful. " + "word " * 60}
    n = note_item([d], NOW)
    assert n["text"].startswith("From the Fieldhouse Notes: Broncos from deep. WMU will be a handful.")
    d["published"] = (NOW - timedelta(days=3)).isoformat()
    assert note_item([d], NOW) is None
