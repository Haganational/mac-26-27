from datetime import datetime, timezone

from mac import preview_story as ps


def game(**kw):
    g = {"game_id": "1", "date": "2026-11-12T00:00Z", "completed": False, "neutral_site": False, "conference_game": True,
         "venue": "James A. Rhodes Arena", "venue_city": "Akron", "broadcasts": [{"name": "ESPN+"}],
         "et": {"weekday": "Wed", "time": "7 PM", "tba": False},
         "home": {"key": "akron", "name": "Akron Zips", "abbr": "AKR"},
         "away": {"key": "kent-state", "name": "Kent State Golden Flashes", "abbr": "KENT"},
         "mv": {"home_pts": 80, "away_pts": 73, "spread": -7.2, "home_win": 74, "away_win": 26, "fav_abbr": "AKR",
                "dog_abbr": "KENT", "non_d1": False, "market": {"spread": -6.5, "total": 152.5},
                "side": {"take": "KENT +6.5"}, "ou": None},
         "ptw": [{"name": "A Guard", "abbr": "AKR", "ppg": 15.2}, {"name": "B Forward", "abbr": "KENT", "ppg": 18.0}],
         "travel_away": {"rest_days": 0, "miles_in": 12, "road_streak": 3, "tz_shift": 0},
         "travel_home": {"rest_days": 3, "miles_in": 0, "road_streak": 0}}
    g.update(kw)
    return g


STAND = [{"key": "akron", "w": 2, "l": 0, "cw": 1, "cl": 0}, {"key": "kent-state", "w": 1, "l": 1, "cw": 0, "cl": 1}]
FLAVOR = {"settings": {"max_lines": 2}, "teams": {"akron": {"home_lines": ["{home} at home.", "{winner} wins."]}}}


def test_preview_story_facts():
    s = ps.write(game(), STAND, FLAVOR)
    assert s["headline"] == "Kent State at Akron preview: model has Akron by 7"
    p = s["paragraphs"]
    assert p[0].startswith("Kent State (1-1, 0-1 in conference) visits Akron (2-0, 1-0 in conference) at James A. Rhodes Arena")
    assert "Wednesday at 7 PM ET on ESPN+, a conference game." in p[0]
    assert "projecting an 80-73 final" in p[1] and "74% chance" in p[1]
    assert "Akron favored by 6.5 with a total of 152.5" in p[1] and "leans Kent State +6.5" in p[1]
    assert p[2].startswith("Players to watch: B Forward of Kent State, 18 points a game")
    assert p[3] == "Kent State played yesterday and is playing its third straight road game."
    assert all("{" not in f for f in s["flavor"])


def test_due_and_freeze():
    g = game()
    assert ps.due(g, datetime(2026, 11, 11, 6, tzinfo=timezone.utc))
    assert not ps.due(g, datetime(2026, 11, 9, 6, tzinfo=timezone.utc))
    saved = {}
    first = ps.remember(saved, g, {"headline": "v1", "paragraphs": []}, datetime(2026, 11, 11, 6, tzinfo=timezone.utc))
    ps.remember(saved, g, {"headline": "v2", "paragraphs": []}, datetime(2026, 11, 11, 20, tzinfo=timezone.utc))
    assert saved["1"]["headline"] == "v2" and saved["1"]["published"] == first["published"]
    ps.remember(saved, g, {"headline": "v3", "paragraphs": []}, datetime(2026, 11, 12, 3, tzinfo=timezone.utc))
    assert saved["1"]["headline"] == "v2"  # frozen at tip
