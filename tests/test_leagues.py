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


def test_mountain_west_names():
    lg = leagues.MW
    assert lg.path == "mw/" and len(lg.teams) == 10
    assert lg.team_for_odds_name("Hawaii Rainbow Warriors") == "hawaii"
    assert lg.team_for_odds_name("San Jose St Spartans") == "san-jose-state"
    assert lg.team_for_odds_name("Grand Canyon Antelopes") == "grand-canyon"


def test_metro_conference_names_and_tag():
    from mac import social
    lg = leagues.METRO
    assert lg.path == "metro/" and len(lg.teams) == 13 and lg.short == "Metro"
    assert lg.team_for_odds_name("Mt. St. Mary's Mountaineers") == "mount-st-marys"
    assert lg.team_for_odds_name("St. Peter's Peacocks") == "saint-peters"
    assert lg.team_for_odds_name("Marist Red Foxes") == "marist"
    assert lg.team_for_odds_name("Ohio Bobcats") is None  # Quinnipiac are Bobcats too; no mix-up
    assert social.text_for({"title": "Marist at Quinnipiac", "league": "Metro", "tag": "MetroConference"}).endswith(
        "#MetroConference #CollegeBasketball")
    assert social.text_for({"title": "x", "league": "MAC"}).endswith("#MAC #CollegeBasketball")


def test_big_west_names():
    lg = leagues.BIGWEST
    assert lg.path == "bigwest/" and len(lg.teams) == 12 and lg.theme == "coast"
    assert lg.team_for_odds_name("Long Beach St 49ers") == "long-beach-state"
    assert lg.team_for_odds_name("CSU Bakersfield Roadrunners") == "csu-bakersfield"
    assert lg.team_for_odds_name("Cal Baptist Lancers") == "cal-baptist"
    assert lg.team_for_odds_name("San Diego St Aztecs") is None  # San Diego State is not UC San Diego
    assert lg.team_for_odds_name("Hawaii Rainbow Warriors") is None  # Hawai'i moved to the Mountain West


def test_social_tags_are_single_words_and_league_feeds_are_hosts():
    import re
    tags = {lg.key: re.sub(r"\W", "", lg.hashtag or lg.short) for lg in leagues.ALL.values()}
    assert tags == {"mac": "MAC", "asun": "ASUN", "horizon": "HorizonLeague", "mw": "MountainWest",
                    "metro": "MetroConference", "bigwest": "BigWest"}
    for lg in leagues.ALL.values():
        if lg.league_feed:
            assert re.fullmatch(r"[a-z0-9.-]+\.[a-z]+", lg.league_feed[0]) and lg.league_feed[0] in lg.league_feed[1]
