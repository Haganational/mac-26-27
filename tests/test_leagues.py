from datetime import datetime, timezone

from mac import leagues, odds


def test_every_league_has_unique_keys_and_its_own_folder():
    for lg in leagues.ALL.values():
        keys = [t.key for t in lg.teams]
        assert len(keys) == len(set(keys))
        assert set(lg.news_names) <= set(keys)
    assert leagues.MAC.path == "" and leagues.ASUN.path == "asun/"
    assert leagues.ASUN.data_dir.as_posix().endswith("data/leagues/asun")


def test_asun_odds_names_and_rows():
    lg = leagues.ASUN
    assert lg.team_for_odds_name("Florida Gulf Coast Eagles") == "fgcu"
    assert lg.team_for_odds_name("Queens Royals") == "queens"
    assert lg.team_for_odds_name("Toledo Rockets") is None
    ev = {"id": "e1", "commence_time": "2026-11-10T00:00:00Z", "home_team": "Georgia Bulldogs",
          "away_team": "Florida Gulf Coast Eagles",
          "bookmakers": [{"key": "draftkings", "last_update": "x", "markets": [
              {"key": "spreads", "outcomes": [{"name": "Georgia Bulldogs", "point": -22.5, "price": -110},
                                              {"name": "Florida Gulf Coast Eagles", "point": 22.5, "price": -110}]}]}]}
    other = dict(ev, id="e2", home_team="Toledo Rockets", away_team="Ohio Bobcats")
    rows = odds.league_rows(lg, [ev, other], datetime(2026, 11, 9, tzinfo=timezone.utc).isoformat())
    assert len(rows) == 2 and {r["away_key"] for r in rows} == {"fgcu"} and {r["home_key"] for r in rows} == {None}
