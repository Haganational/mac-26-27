from datetime import datetime, timezone

from mac import today


def game(gid, date, home, away, hs, as_, spread=None, cover=None):
    return {"game_id": gid, "date": date, "neutral_site": False, "conference_game": False,
            "home": {**home, "score": hs, "winner": hs > as_}, "away": {**away, "score": as_, "winner": as_ > hs},
            "closing_spread": spread, "ats_cover": cover}


WMU = {"key": "western-michigan", "name": "Western Michigan Broncos", "espn_id": "2711", "abbr": "WMU"}
CAM = {"key": None, "name": "Campbell Fighting Camels", "espn_id": "2097", "abbr": "CAM"}
MIA = {"key": "miami-oh", "name": "Miami (OH) RedHawks", "espn_id": "193", "abbr": "M-OH"}
BELL = {"key": None, "name": "Bellarmine Knights", "espn_id": "91", "abbr": "BELL"}


def test_school_names():
    assert today.school("Campbell Fighting Camels") == "Campbell"
    assert today.school("Muskingum Fighting Muskies") == "Muskingum"
    assert today.school("Bellarmine Knights") == "Bellarmine"
    assert today.school("x", "western-michigan") == "Western Michigan"


def test_results_tell_score_scorer_and_cover():
    box = {"players": [{"team_espn_id": "2711", "name": "Jaylen Washington Jr.", "pts": 27, "reb": 4},
                       {"team_espn_id": "2711", "name": "Bench Guy", "pts": 3}]}
    r = today.result_item(game("1", "2026-11-08T19:00Z", WMU, CAM, 87, 71, -4.5, "home"), box)
    assert r["text"] == ("Western Michigan beat Campbell 87-71. Jaylen Washington Jr. led the Broncos with 27 points. "
                         "Western Michigan covered as a 4.5-point favorite.")
    r = today.result_item(game("2", "2026-11-07T22:00Z", MIA, BELL, 80, 73, -18.5, "away"), None)
    assert r["text"].endswith("won but didn't cover as an 18.5-point favorite.")


def test_build_groups_tune_ups_and_labels_days():
    now = datetime(2026, 11, 9, 14, tzinfo=timezone.utc)  # Monday morning ET
    recent = [game("1", "2026-11-08T23:00Z", WMU, CAM, 87, 71, -4.5, "home")]
    upcoming = [
        {"game_id": "3", "neutral_site": False, "home": {**WMU, "score": None}, "away": {"key": None, "name": "Kalamazoo Hornets", "abbr": "KALC"},
         "et": {"day_key": "2026-11-09", "time": "7:00 PM"}, "watch": {"nets": [{"name": "ESPN+"}]}, "line": None,
         "model": {"model": {"spread": -30.0}, "home": {"non_d1": False}, "away": {"non_d1": True}}},
    ]
    standings = [{"team": "Western Michigan", "w": 2, "l": 0}, {"team": "Buffalo", "w": 0, "l": 2}]
    t = today.build(now, recent, upcoming, {}, standings)
    assert t["results_label"] == "Last night"
    assert "Western Michigan plays a non-Division I opponent, so no line." in t["paragraphs"][2]
    assert t["paragraphs"][3] == "Still unbeaten: Western Michigan. Still looking for a first win: Buffalo."
    assert 0 < t["seconds"] < 90
