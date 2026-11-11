import json
from datetime import datetime, timezone

from mac import gamer


def ctx(home_score=80, away_score=70, neutral=False):
    def p(name, team, pts, reb=3, ast=1, tpm=0, dnp=False):
        return {"name": name, "team_espn_id": team, "pts": pts, "reb": reb, "ast": ast, "tpm": tpm, "dnp": dnp}
    g = {"game_id": "401", "date": "2026-11-03T23:00Z", "neutral_site": neutral, "venue": "James A. Rhodes Arena",
         "venue_city": "Akron", "venue_state": "OH",
         "home": {"key": "akron", "name": "Akron Zips", "abbr": "AKR", "score": home_score, "espn_id": "2006"},
         "away": {"key": "kent-state", "name": "Kent State Golden Flashes", "abbr": "KENT", "score": away_score, "espn_id": "2309"}}
    home = {**g["home"], "stats": {"offensiveRebounds": "15", "totalTurnovers": "8"},
            "players": [p("A One", "2006", 22, reb=9), p("A Two", "2006", 10), p("A Bench", "2006", None, dnp=True)]}
    away = {**g["away"], "stats": {"offensiveRebounds": "6", "totalTurnovers": "9"}, "players": [p("K One", "2309", 18)]}
    return {"g": g, "home": home, "away": away, "box": {}, "result": {"ats": "AKR covered"}}


FLAVOR = {"settings": {"max_lines": 1, "byline": "Desk"},
          "teams": {"akron": {"town": "Akron", "home_floor": "the JAR", "home_lines": ["Loud night at {floor} in {town}."]}},
          "rivalries": {"akron|kent-state": {"lines": ["{winner} keeps the bragging rights."]}}}


def test_gamer_uses_only_box_facts():
    gm = gamer.write(ctx(), {"model_err": 4.25}, FLAVOR)
    assert gm["headline"] == "Akron beat Kent State 80-70"
    assert gm["paragraphs"][0] == "Akron beat Kent State 80-70 at James A. Rhodes Arena."
    assert "A One led Akron with 22 points and 9 rebounds." in gm["paragraphs"][1]
    assert "Akron had 15 offensive rebounds to Kent State's 6." in gm["paragraphs"][2]
    assert "Akron covered the closing spread." in gm["paragraphs"][2]
    assert "4.2 points" in gm["paragraphs"][2] or "4.3 points" in gm["paragraphs"][2]
    assert gm["byline"] == "Desk"


def test_rivalry_line_wins_and_fills_knobs():
    assert gamer.write(ctx(), None, FLAVOR)["flavor"] == ["Akron keeps the bragging rights."]
    two = {**FLAVOR, "settings": {"max_lines": 2}}
    assert gamer.write(ctx(), None, two)["flavor"][1] == "Loud night at the JAR in Akron."
    off = {**FLAVOR, "settings": {"enabled": False}}
    assert gamer.write(ctx(), None, off)["flavor"] == []


def test_home_lines_never_appear_on_the_road():
    c = ctx()
    c["g"]["home"]["key"], c["home"]["key"] = None, None
    c["g"]["away"]["key"] = "akron"
    f = {"settings": {"max_lines": 2}, "teams": {"akron": {"home_lines": ["At the JAR."], "lines": ["Rubber City."]}}, "rivalries": {}}
    assert gamer.write(c, None, f)["flavor"] == ["Rubber City."]


def test_road_win_and_close_game_wording():
    gm = gamer.write(ctx(home_score=70, away_score=72), None, {"settings": {}, "teams": {}, "rivalries": {}})
    assert gm["paragraphs"][0] == "Kent State edged Akron 72-70 on the road in Akron."


def test_published_time_is_sticky(tmp_path):
    pub = {}
    first = gamer.stamp(pub, "401", datetime(2026, 11, 4, 1, 5, tzinfo=timezone.utc))
    again = gamer.stamp(pub, "401", datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc))
    assert first == again == "2026-11-04T01:05:00Z"
    path = tmp_path / "published.json"
    gamer.save_published(pub, path)
    assert gamer.load_published(path) == pub
    late = gamer.stamp(pub, "402", datetime(2026, 11, 9, tzinfo=timezone.utc), "2026-11-03T23:00Z")
    assert late == "2026-11-04T01:00:00Z"


def test_json_ld_is_news_article_about_sports_event():
    c = ctx()
    gm = gamer.write(c, None, FLAVOR)
    ld = gamer.json_ld(c, gm, "2026-11-04T01:05:00Z", "2026-11-04T02:00:00Z", "Hardwood Bricks", "https://hardwoodbricks.com/")
    art, ev = ld["@graph"]
    assert art["@type"] == "NewsArticle" and ev["@type"] == "SportsEvent"
    assert art["datePublished"] == "2026-11-04T01:05:00Z"
    assert art["mainEntityOfPage"] == "https://hardwoodbricks.com/games/401.html"
    assert art["about"]["@id"] == ev["@id"]
    assert ev["startDate"] == "2026-11-03T23:00:00Z"
    assert ev["location"]["address"]["addressLocality"] == "Akron"
    assert ev["homeTeam"]["name"] == "Akron Zips"
    json.dumps(ld)


def test_seed_flavor_file_parses():
    f = gamer.load_flavor()
    assert f["settings"]["byline"]
    for key in f["rivalries"]:
        assert key == "|".join(sorted(key.split("|")))
