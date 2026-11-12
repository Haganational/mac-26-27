from mac import prep


def g(gid, date, home, away, hs=None, as_=None, done=True, hk=None, ak=None, conf=False):
    return {"game_id": gid, "date": date, "completed": done, "conference_game": conf, "neutral_site": False,
            "venue_city": "Akron",
            "home": {"espn_id": home, "key": hk, "name": home.title(), "score": hs},
            "away": {"espn_id": away, "key": ak, "name": away.title(), "score": as_}}


GAMES = [g("1", "2026-11-03T00:00Z", "akron", "kent", 70, 60, hk="akron", ak="kent-state", conf=True),
         g("2", "2026-11-06T00:00Z", "ohio", "akron", 80, 75, hk="ohio", ak="akron"),
         g("3", "2026-11-20T00:00Z", "kent", "akron", done=False, hk="kent-state", ak="akron", conf=True)]


def test_last_games_newest_first_and_before_tip():
    from datetime import datetime, timezone
    out = prep.last_games("akron", GAMES, datetime(2026, 11, 19, tzinfo=timezone.utc))
    assert [(x["site"], x["wl"], x["score"]) for x in out] == [("at", "L", "75-80"), ("vs", "W", "70-60")]
    assert out[1]["conf"] is True


def test_meetings_finds_earlier_game():
    m = prep.meetings(GAMES[2], GAMES)
    assert m == [{"date": "11/2", "winner": "Akron", "score": "70-60", "where": "Akron"}]


def test_roster_skips_unplayed_and_sorts_by_minutes():
    pl = [{"name": "A", "season": {"gp": 2, "per_game": {"min": 10, "pts": 4}}},
          {"name": "B", "season": {"gp": 2, "per_game": {"min": 30, "pts": 20}}, "game_log": [{"pts": 22, "opponent_abbr": "KENT"}]},
          {"name": "C", "season": {"gp": 0}}]
    r = prep.roster(pl)
    assert [x["name"] for x in r] == ["B", "A"] and r[0]["last"] == "22 pts vs KENT"


def test_non_league_side_uses_opp_form():
    up = g("9", "2026-11-20T00:00Z", "akron", "niagara", done=False, hk="akron")
    opp = {"niagara": {"record": "0-2", "ppg": 56.5, "opp_ppg": 82.0,
                       "last": [{"date": "2026-11-07", "site": "vs", "opp": "Morgan State", "wl": "L", "score": "67-73"}]}}
    s = prep.side(up, "away", GAMES, {}, {}, lambda k: {}, opp)
    assert s["record"] == "0-2" and s["last5"][0]["date"] == "11/7" and not s["ours"]
