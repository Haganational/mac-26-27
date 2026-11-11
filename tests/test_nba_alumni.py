from datetime import date

from mac import nba_alumni


def _summary():
    names = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST"]
    def a(i, n, mins, pts, reb, ast, dnp=False):
        return {"athlete": {"id": i, "displayName": n}, "didNotPlay": dnp, "stats": [] if dnp else [mins, pts, "1-2", "0-0", "0-0", reb, ast]}
    return {"boxscore": {"players": [{"team": {"name": "Rockets"}, "statistics": [{"names": names, "athletes": [
        a("1", "Zip One", "30", "14", "6", "2"), a("2", "Bench Guy", "0", "0", "0", "0"), a("3", "Hurt Guy", "", "", "", "", dnp=True)]}]}]}}


def test_parse_summary_keeps_players_who_got_in():
    ps = nba_alumni.parse_summary(_summary())
    assert ps == [{"id": "1", "name": "Zip One", "team": "Rockets", "pts": 14, "reb": 6, "ast": 2}]


def test_paragraph_same_night_and_night_before_only():
    nights = {"2026-11-10": [{"id": "1", "name": "Zip One", "team": "Rockets", "pts": 14, "reb": 6, "ast": 2}],
              "2026-11-09": [{"id": "2", "name": "Old Zip", "team": "Bucks", "pts": 9, "reb": 1, "ast": 5}],
              "2026-11-08": [{"id": "3", "name": "Too Early", "team": "Nets", "pts": 30, "reb": 0, "ast": 0}]}
    colleges = {"1": {"college_id": "2006"}, "2": {"college_id": "2006"}, "3": {"college_id": "2006"}, "4": {"college_id": "195"}}
    para = nba_alumni.paragraph([("2006", "Akron"), ("195", "Ohio")], date(2026, 11, 10), nights, colleges)
    assert para == ("In the NBA, former Akron player Zip One had 14 points and 6 rebounds for the Rockets on Tuesday; "
                    "former Akron player Old Zip had 9 points and 5 assists for the Bucks the night before.")
    assert nba_alumni.paragraph([("195", "Ohio")], date(2026, 11, 10), nights, colleges) is None
