from mac import players, rosters


def test_parse_summary_normalises_spread_to_home_team():
    summary = {
        "boxscore": {"teams": [], "players": []},
        "pickcenter": [{
            "provider": {"name": "DraftKings"}, "details": "TOL -3.5", "spread": -3.5, "overUnder": 140.5,
            "homeTeamOdds": {"favorite": False, "moneyLine": 150},
            "awayTeamOdds": {"favorite": True, "moneyLine": -180},
        }],
        "header": {"competitions": [{"date": "2026-11-11T00:00Z"}]},
        "gameInfo": {},
    }
    out = rosters.parse_summary("1", summary)
    assert out["espn_line"]["home_spread"] == 3.5  # away team favoured by 3.5
    assert out["espn_line"]["total"] == 140.5


def test_season_line_averages_and_shooting():
    games = [
        {"starter": True, "dnp": False, "min": 30, "pts": 20, "fgm": 7, "fga": 14, "tpm": 2, "tpa": 5, "ftm": 4, "fta": 4,
         "reb": 5, "oreb": 1, "dreb": 4, "ast": 3, "to": 2, "stl": 1, "blk": 0, "pf": 2},
        {"starter": False, "dnp": False, "min": 20, "pts": 10, "fgm": 3, "fga": 6, "tpm": 0, "tpa": 1, "ftm": 4, "fta": 6,
         "reb": 3, "oreb": 0, "dreb": 3, "ast": 1, "to": 0, "stl": 0, "blk": 1, "pf": 3},
        {"starter": False, "dnp": True, "min": None, "pts": None, "fgm": None, "fga": None, "tpm": None, "tpa": None,
         "ftm": None, "fta": None, "reb": None, "oreb": None, "dreb": None, "ast": None, "to": None, "stl": None, "blk": None, "pf": None},
    ]
    s = players.season_line(games)
    assert (s["gp"], s["gs"]) == (2, 1)
    assert s["per_game"]["pts"] == 15.0
    assert s["fg_pct"] == 50.0
    assert s["efg_pct"] == 55.0  # (10 + 0.5*2) / 20


def test_norm_name_ignores_suffix_and_punctuation():
    assert players.norm_name("Jaylan Ouwinga Jr.") == players.norm_name("jaylan ouwinga")
    assert players.norm_name("D'Andre O'Neal") == "dandreoneal"
