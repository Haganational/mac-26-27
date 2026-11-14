from datetime import date

from mac import cbbd
from mac import ratings as R


def _team_row(gid, tid, name, home, pts, neutral=False):
    return {"gameId": gid, "startDate": "2025-11-05T00:00:00.000Z", "neutralSite": neutral, "isHome": home,
            "teamId": tid, "team": name, "conference": "MAC", "gameMinutes": 45,
            "teamStats": {"points": {"total": pts}, "fieldGoals": {"made": 25, "attempted": 60},
                          "freeThrows": {"made": 10, "attempted": 15}, "threePointFieldGoals": {"made": 7, "attempted": 22},
                          "rebounds": {"offensive": 9, "defensive": 25, "total": 34}, "turnovers": {"total": 12}}}


def test_games_from_team_boxes_pairs_sides_and_counts_overtime():
    games = cbbd.games_from_team_boxes([_team_row(1, 10, "Kent State", True, 80), _team_row(1, 20, "Akron", False, 75)])
    assert len(games) == 1
    g = games[0]
    assert g["home"]["id"] == "10" and g["away"]["id"] == "20"
    assert g["home"]["pts"] == 80 and g["away"]["fga"] == 60 and g["home"]["orb"] == 9 and g["home"]["to"] == 12
    assert g["ot"] == 1
    rows = R.game_rows(games, {"10", "20"}, 1.5)
    assert rows and rows[0]["pts_h"] == 80


def test_neutral_game_with_no_home_flag_still_pairs():
    games = cbbd.games_from_team_boxes([_team_row(2, 10, "A", False, 70, True), _team_row(2, 20, "B", False, 60, True)])
    assert len(games) == 1 and {games[0]["home"]["id"], games[0]["away"]["id"]} == {"10", "20"}


def test_lines_prefer_listed_provider_and_keep_openers():
    rows = [{"gameId": 5, "lines": [
        {"provider": "Bovada", "spread": -3.0, "spreadOpen": -2.5, "overUnder": 140.0, "overUnderOpen": 141.0},
        {"provider": "ESPN BET", "spread": -4.0, "spreadOpen": None, "overUnder": 139.5, "overUnderOpen": 138.0},
    ]}]
    got = cbbd.lines_by_game(rows)["5"]
    assert got["home_spread"] == -4.0 and got["home_spread_book"] == "ESPN BET"
    assert got["open_spread"] == -2.5 and got["open_spread_book"] == "Bovada"  # falls through to the next book
    assert got["total"] == 139.5 and got["open_total"] == 138.0


def test_full_window_is_split():
    calls = []

    def getter(path, params):
        calls.append(params["startDateRange"][:10])
        return [{}] * (3000 if len(calls) == 1 else 10)

    rows = cbbd.fetch_window("/games/teams", 2026, date(2025, 11, 1), date(2025, 11, 30), getter)
    assert len(calls) == 3 and len(rows) == 20


def test_season_windows_cover_the_season():
    w = cbbd.season_windows(2026)
    assert w[0][0] == date(2025, 11, 1) and w[-1][1] == date(2026, 4, 15)
    assert all(b[0] > a[1] for a, b in zip(w, w[1:]))


def test_opening_bump_only_on_home_floors_early():
    p = R.Params()
    assert R.opening_bump(p, 2, False) == p.open_home_wk1
    assert R.opening_bump(p, 10, False) == p.open_home_wk2
    assert R.opening_bump(p, 20, False) == 0.0
    assert R.opening_bump(p, 2, True) == 0.0
    assert R.opening_bump(p, None, False) == 0.0


def test_halves_rows_and_lead_table(tmp_path, monkeypatch):
    from mac import halves_study as H
    monkeypatch.setattr(cbbd, "CACHE_DIR", tmp_path)
    cbbd.store("games", 2026, [
        {"id": 1, "startDate": "2025-11-05", "homeTeamId": 10, "awayTeamId": 20, "homePoints": 70, "awayPoints": 60,
         "homePeriodPoints": [40, 30], "awayPeriodPoints": [30, 30]},
        {"id": 2, "startDate": "2025-11-06", "homeTeamId": 10, "awayTeamId": 30, "homePoints": 60, "awayPoints": 65,
         "homePeriodPoints": [35, 25], "awayPeriodPoints": [30, 35]},
        {"id": 3, "startDate": "2025-11-07", "homeTeamId": 10, "awayTeamId": 30, "homePeriodPoints": None},
    ])
    cbbd.store("lines", 2026, [{"gameId": 1, "lines": [{"provider": "DraftKings", "spread": -6.5, "overUnder": 140.5}]}])
    rows = H.game_halves(2026)
    assert len(rows) == 2
    r = rows[0]
    assert (r["h1"], r["h2"], r["t1"], r["exp"], r["exp_total"]) == (10, 0, 70, 6.5, 140.5)
    table = {b["lead"]: b for b in H.lead_table(rows)}
    assert table["10-12"]["leader_won"] == 1.0 and table["4-6"]["leader_won"] == 0.0
