from mac import player_pages


def prof(**kw):
    p = {"espn_id": "5105569", "name": "Evan Mahaffey", "team_key": "akron", "position": "F", "jersey": "12",
         "hometown": "Cincinnati, OH", "height": "6' 6\"", "espn_url": "https://espn.example/p",
         "season": {"gp": 2, "per_game": {"pts": 11.5, "reb": 6.0, "ast": 3.0, "min": 30.0}},
         "game_log": [
             {"game_id": "1", "date": "2026-11-03T23:00Z", "dnp": False, "min": 30, "pts": 9, "reb": 7, "ast": 2,
              "home": True, "opponent": "Louisiana Ragin' Cajuns", "opponent_abbr": "UL"},
             {"game_id": "2", "date": "2026-11-08T23:00Z", "dnp": False, "min": 31, "pts": 14, "reb": 5, "ast": 4,
              "home": False, "opponent": "Kent State Golden Flashes", "opponent_abbr": "KENT"}]}
    p.update(kw)
    return p


def test_path_has_name_and_id():
    assert player_pages.path(prof()) == "players/evan-mahaffey-5105569.html"


def test_title_and_description_lead_with_points_and_hometown():
    c = player_pages.context(prof(), "2026-27")
    assert c["page_title"] == "Evan Mahaffey stats: 11.5 points per game, 2026-27 · Akron"
    assert c["page_desc"].startswith("Evan Mahaffey, Akron forward from Cincinnati, Ohio.")
    assert "Last game: 14 points, 5 rebounds and 4 assists at Kent State." in c["page_desc"]
    assert c["highs"]["pts"]["pts"] == 14


def test_json_ld_person_with_team_and_hometown():
    c = player_pages.context(prof(), "2026-27")
    ld = player_pages.json_ld(c, "Hardwood Bricks", "https://hardwoodbricks.com/")
    person = ld["mainEntity"]
    assert ld["@type"] == "ProfilePage" and person["@type"] == "Person"
    assert person["homeLocation"]["name"] == "Cincinnati, Ohio"
    assert person["affiliation"]["url"] == "https://hardwoodbricks.com/teams/akron.html"


def test_player_who_has_not_played():
    c = player_pages.context(prof(season={"gp": 0, "per_game": {}}, game_log=[], hometown=None), "2026-27")
    assert c["page_title"] == "Evan Mahaffey stats, 2026-27 · Akron"
    assert c["last"] is None and "homeLocation" not in player_pages.json_ld(c, "HB")["mainEntity"]
