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


def test_horizon_odds_names_and_no_overlap():
    lg = leagues.HORIZON
    assert lg.path == "horizon/" and len(lg.teams) == 12
    assert lg.team_for_odds_name("Cleveland St Vikings") == "cleveland-state"
    assert lg.team_for_odds_name("IUPUI Jaguars") == "iu-indy"
    assert lg.team_for_odds_name("Ohio Bobcats") is None
    ids = [t.espn_id for l in leagues.ALL.values() for t in l.teams]
    assert len(ids) == len(set(ids))  # no school sits in two editions


def test_notes_stay_in_their_own_edition(tmp_path, monkeypatch):
    from mac import notes
    (tmp_path / "a.md").write_text("---\ntitle: Ohio\ndate: 2026-11-09\n---\nMAC note\n")
    (tmp_path / "b.md").write_text("---\ntitle: Eagles\ndate: 2026-11-09\nleague: asun\nauthor: Craig\n---\nASUN note\n")
    monkeypatch.setattr(notes, "NOTES_DIR", tmp_path)
    monkeypatch.setattr(notes, "LEAGUE", leagues.ASUN)
    got = notes.load()
    assert [n["title"] for n in got] == ["Eagles"] and got[0]["author"] == "Craig"
