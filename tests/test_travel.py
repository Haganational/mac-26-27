from mac import travel

V = {
    "Toledo|OH": {"lat": 41.6528, "lon": -83.5379, "tz": "America/New_York"},
    "Chicago|IL": {"lat": 41.8781, "lon": -87.6298, "tz": "America/Chicago"},
    "Milwaukee|WI": {"lat": 43.0389, "lon": -87.9065, "tz": "America/Chicago"},
    "Detroit|MI": {"lat": 42.3314, "lon": -83.0458, "tz": "America/Detroit"},
}


def game(gid, date, home_key, away_key, city, state, neutral=False):
    side = lambda k: {"key": k, "name": k or "Opp", "espn_id": "1", "abbr": "X", "score": None, "winner": None}
    return {"game_id": gid, "date": date, "home": side(home_key), "away": side(away_key), "neutral_site": neutral,
            "venue": f"{city} Arena", "venue_city": city, "venue_state": state, "conference_game": False, "completed": False}


def test_miles_known_distance():
    # Toledo to Chicago is about 213 great-circle miles.
    assert 205 < travel.miles(V["Toledo|OH"], V["Chicago|IL"]) < 220


def test_road_trip_stays_out_and_counts_way_home():
    games = [
        game("1", "2026-11-01T23:00Z", "toledo", None, "Toledo", "OH"),
        game("2", "2026-11-04T23:00Z", None, "toledo", "Chicago", "IL"),
        game("3", "2026-11-06T23:00Z", None, "toledo", "Milwaukee", "WI"),
        game("4", "2026-11-09T23:00Z", "toledo", None, "Toledo", "OH"),
    ]
    it = travel.itinerary("toledo", games, V)
    legs = it["legs"]
    assert [l["site"] for l in legs] == ["home", "away", "away", "home"]
    assert legs[2]["via_home"] is False and legs[2]["road_streak"] == 2
    assert legs[1]["tz_shift"] == -1
    assert len(it["trips"]) == 1 and it["trips"][0]["games"] == 2
    expected = travel.miles(V["Toledo|OH"], V["Chicago|IL"]) + travel.miles(V["Chicago|IL"], V["Milwaukee|WI"]) + travel.miles(V["Milwaukee|WI"], V["Toledo|OH"])
    assert abs(it["totals"]["miles"] - expected) < 3


def test_goes_home_between_when_on_the_way():
    # Detroit then Chicago: Toledo is almost on the way, so the team goes home in between.
    games = [
        game("1", "2026-11-01T23:00Z", "toledo", None, "Toledo", "OH"),
        game("2", "2026-11-03T23:00Z", None, "toledo", "Detroit", "MI"),
        game("3", "2026-11-10T23:00Z", None, "toledo", "Chicago", "IL"),
    ]
    legs = travel.itinerary("toledo", games, V)["legs"]
    assert legs[2]["via_home"] is True and legs[2]["road_streak"] == 1


def test_rest_days_use_local_calendar():
    # 7pm ET Saturday is 00:00Z Sunday; a Sunday 2pm ET game is a back-to-back (0 days off).
    games = [
        game("1", "2026-11-08T00:00Z", "toledo", None, "Toledo", "OH"),
        game("2", "2026-11-08T19:00Z", "toledo", None, "Toledo", "OH"),
    ]
    legs = travel.itinerary("toledo", games, V)["legs"]
    assert legs[1]["rest_days"] == 0
