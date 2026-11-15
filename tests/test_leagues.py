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


def test_missouri_valley_names():
    lg = leagues.MVC
    assert lg.path == "mvc/" and len(lg.teams) == 11 and lg.theme == "arch"
    assert lg.team_for_odds_name("Murray St Racers") == "murray-state"
    assert lg.team_for_odds_name("Illinois St Redbirds") == "illinois-state"
    assert lg.team_for_odds_name("UIC Flames") == "uic"
    assert lg.team_for_odds_name("Illinois Fighting Illini") is None
    assert lg.team_for_odds_name("SIU-Edwardsville Cougars") is None  # SIUE is not Southern Illinois


def test_atlantic_10_names():
    lg = leagues.A10
    assert lg.path == "a10/" and len(lg.teams) == 14 and lg.theme == "ironbridge"
    assert lg.team_for_odds_name("GW Revolutionaries") == "george-washington"
    assert lg.team_for_odds_name("Loyola (Chi) Ramblers") == "loyola-chicago"
    assert lg.team_for_odds_name("Loyola (MD) Greyhounds") is None
    assert lg.team_for_odds_name("St. Bonaventure Bonnies") == "st-bonaventure"
    # Three schools called the Rams: two are ours, one is not.
    assert lg.team_for_odds_name("VCU Rams") == "vcu" and lg.team_for_odds_name("Fordham Rams") == "fordham"
    assert lg.team_for_odds_name("Colorado St Rams") is None


def test_pac_12_names():
    lg = leagues.PAC12
    assert lg.path == "pac12/" and len(lg.teams) == 9 and lg.theme == "timber"
    assert lg.team_for_odds_name("San Diego St Aztecs") == "san-diego-state"
    assert lg.team_for_odds_name("Colorado St Rams") == "colorado-state"
    assert lg.team_for_odds_name("Washington St Cougars") == "washington-state"
    assert lg.team_for_odds_name("Gonzaga Bulldogs") == "gonzaga"
    assert lg.team_for_odds_name("San Diego Toreros") is None  # WCC
    # The five schools that left are gone from the Mountain West edition.
    assert not {t.key for t in lg.teams} & {t.key for t in leagues.MW.teams}


def test_wcc_names():
    lg = leagues.WCC
    assert lg.path == "wcc/" and len(lg.teams) == 10 and lg.theme == "mission"
    assert lg.team_for_odds_name("San Diego Toreros") == "san-diego"
    assert lg.team_for_odds_name("Seattle Redhawks") == "seattle"
    assert lg.team_for_odds_name("Saint Mary's Gaels") == "saint-marys"
    assert lg.team_for_odds_name("Mt. St. Mary's Mountaineers") is None  # Metro
    assert lg.team_for_odds_name("Portland St Vikings") is None
    assert lg.team_for_odds_name("UC San Diego Tritons") is None  # Big West until 2027-28


def test_american_names():
    lg = leagues.AMERICAN
    assert lg.path == "american/" and len(lg.teams) == 13 and lg.theme == "levee"
    assert lg.team_for_odds_name("Wichita St Shockers") == "wichita-state"
    assert lg.team_for_odds_name("Florida Atlantic Owls") == "fau"
    assert lg.team_for_odds_name("Memphis Tigers") == "memphis"
    assert lg.team_for_odds_name("Rice Owls") == "rice"
    assert lg.team_for_odds_name("Kennesaw St Owls") is None  # CUSA


def test_sun_belt_names():
    lg = leagues.SUNBELT
    assert lg.path == "sunbelt/" and len(lg.teams) == 14 and lg.theme == "liveoak"
    assert lg.team_for_odds_name("Appalachian St Mountaineers") == "app-state"
    assert lg.team_for_odds_name("Arkansas St Red Wolves") == "arkansas-state"
    assert lg.team_for_odds_name("Georgia St Panthers") == "georgia-state"
    assert lg.team_for_odds_name("Louisiana Ragin' Cajuns") == "louisiana"
    assert lg.team_for_odds_name("Louisiana Tech Bulldogs") == "louisiana-tech"
    assert lg.team_for_odds_name("SE Louisiana Lions") is None  # Southland
    assert lg.team_for_odds_name("Texas St Bobcats") is None  # Pac-12 now


def test_ivy_and_caa_names():
    assert leagues.IVY.path == "ivy/" and len(leagues.IVY.teams) == 8 and leagues.IVY.theme == "quad"
    assert leagues.CAA.path == "caa/" and len(leagues.CAA.teams) == 13 and leagues.CAA.theme == "harbor"
    assert leagues.IVY.team_for_odds_name("Pennsylvania Quakers") == "penn"
    assert leagues.IVY.team_for_odds_name("Penn State Nittany Lions") is None
    assert leagues.CAA.team_for_odds_name("Charleston Cougars") == "charleston"
    assert leagues.CAA.team_for_odds_name("Charleston Southern Buccaneers") is None  # Big South
    assert leagues.CAA.team_for_odds_name("UNC Wilmington Seahawks") == "uncw"


def test_every_school_is_in_one_edition_and_editions_match_the_registry():
    import json
    seen = {}
    for lg in leagues.ALL.values():
        for t in lg.teams:
            assert t.key not in seen, f"{t.key} is in {seen[t.key]} and {lg.key}"
            seen[t.key] = lg.key
    reg = {c["id"]: set(c["teams"]) for c in json.loads((leagues.ROOT / "data/book/conferences.json").read_text())["conferences"]}
    groups = {"ivy": "12", "caa": "10", "american": "62", "sunbelt": "27", "pac12": "21", "wcc": "29", "a10": "3", "mvc": "18"}
    for key, gid in groups.items():
        assert {t.espn_id for t in leagues.ALL[key].teams} == reg[gid], key


def test_no_odds_name_belongs_to_two_editions():
    from mac import book
    names = {n for s in book.load_odds() for e in s["events"] for n in (e[2], e[3])}
    for n in names:
        owners = [lg.key for lg in leagues.ALL.values() if lg.team_for_odds_name(n)]
        assert len(owners) <= 1, (n, owners)


def test_social_tags_are_single_words_and_league_feeds_are_hosts():
    import re
    tags = {lg.key: re.sub(r"\W", "", lg.hashtag or lg.short) for lg in leagues.ALL.values()}
    assert tags == {"mac": "MAC", "asun": "ASUN", "horizon": "HorizonLeague", "mw": "MountainWest",
                    "metro": "MetroConference", "bigwest": "BigWest",
                    "mvc": "MVCHoops", "a10": "A10MBB",
                    "pac12": "Pac12MBB", "wcc": "WCCHoops",
                    "american": "AmericanMBB", "sunbelt": "SunBeltMBB",
                    "ivy": "IvyMBB", "caa": "CAAHoops"}
    for lg in leagues.ALL.values():
        if lg.league_feed:
            assert re.fullmatch(r"[a-z0-9.-]+\.[a-z]+", lg.league_feed[0]) and lg.league_feed[0] in lg.league_feed[1]


def test_two_word_mascots_come_off_school_names():
    from mac.build import school
    assert school("Southern Indiana Screaming Eagles") == "Southern Indiana"
    assert school("Nevada Wolf Pack") == "Nevada"
    assert school("DePaul Blue Demons") == "DePaul"
    assert school("UMass Lowell River Hawks") == "UMass Lowell"
    assert school("Louisiana Ragin' Cajuns") == "Louisiana"
    assert school("Gardner-Webb Runnin' Bulldogs") == "Gardner-Webb"
    assert school("Akron Zips") == "Akron"
