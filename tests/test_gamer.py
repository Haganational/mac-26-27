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
    assert ev["organizer"]["name"] == "Akron Zips"
    assert len(ev["performer"]) == 2 and ev["performer"][1]["name"] == "Akron Zips"
    assert ev["image"] and all(isinstance(u, str) and u.startswith("https://") for u in ev["image"])
    assert ev["description"]
    json.dumps(ld)


def test_seed_flavor_file_parses():
    f = gamer.load_flavor()
    assert f["settings"]["byline"]
    for key in f["rivalries"]:
        assert key == "|".join(sorted(key.split("|")))


def test_scoring_line_lists_every_scorer_winner_first():
    gm = gamer.write(ctx(), None, FLAVOR)
    assert gm["scoring"] == "Akron: A One 22, A Two 10. Kent State: K One 18."
    gm = gamer.write(ctx(home_score=70, away_score=72), None, FLAVOR)
    assert gm["scoring"].startswith("Kent State: K One 18.")


def test_town_spells_out_states():
    assert gamer.town("Westerville, OH") == "Westerville, Ohio"
    assert gamer.town("Cotonou, Benin") == "Cotonou, Benin"
    assert gamer.town("") is None and gamer.town(None) is None


def test_hometowns_for_top_scorer_and_leading_rebounder():
    c = ctx()
    for i, pl in enumerate(c["home"]["players"] + c["away"]["players"]):
        pl["espn_id"] = str(i)
    c["away"]["players"][0]["reb"] = 12  # K One out-rebounds everyone
    bios = {"0": {"hometown": "Westerville, OH"}, "3": {"hometown": "Cleveland, OH"}}
    s = gamer.write(c, None, FLAVOR, bios)["paragraphs"][1]
    assert s.startswith("Westerville, Ohio, native A One led Akron with 22 points")
    assert "Cleveland, Ohio, native K One had 18 points and 12 rebounds for Kent State, a game high on the boards." in s


def test_top_scorer_who_also_leads_the_glass_is_named_once():
    s = gamer.write(ctx(), None, FLAVOR)["paragraphs"][1]
    assert s.count("A One") == 1 and "rebounds for" not in s


def test_linkify_escapes_and_links_longest_name_first():
    out = gamer.linkify("Jalen Smith Jr. had 9 & Jalen Smith 4.", {"Jalen Smith": "a.html", "Jalen Smith Jr.": "b.html"})
    assert '<a href="b.html">Jalen Smith Jr.</a>' in out
    assert '<a href="a.html">Jalen Smith</a> 4' in out
    assert "&amp;" in out


def test_losers_top_scorer_who_led_the_glass_is_named_once_with_hometown():
    c = ctx()
    for i, pl in enumerate(c["home"]["players"] + c["away"]["players"]):
        pl["espn_id"] = str(i)
    c["home"]["players"][0]["reb"] = 3
    c["away"]["players"][0]["reb"] = 7
    s = gamer.write(c, None, FLAVOR, {"3": {"hometown": "Irmo, SC"}})["paragraphs"][1]
    assert "Irmo, South Carolina, native K One had 18 points for Kent State and a game-high 7 rebounds." in s
    assert s.count("K One") == 1


def test_photo_ld():
    o = gamer.photo_ld({"src": "photos/a.jpg", "caption": "Tip", "credit": "Pat"}, "https://x.com/")
    assert o["contentUrl"] == "https://x.com/photos/a.jpg" and o["caption"] == "Tip"
    assert o["creator"] == {"@type": "Person", "name": "Pat"} and o["creditText"] == "Pat"
    assert "creator" not in gamer.photo_ld({"src": "photos/b.jpg"}, "https://x.com/")


def test_event_offers_only_for_upcoming_games_with_tickets():
    c = ctx()
    gm = gamer.write(c, None, FLAVOR)
    ld = gamer.json_ld(c, gm, "2026-11-04T01:05:00Z", "2026-11-04T02:00:00Z", "Hardwood Bricks", "https://hardwoodbricks.com/")
    assert "offers" not in ld["@graph"][1]
    c["g"]["tickets"] = {"url": "https://tix.example/event", "low": 14.0}
    c["g"]["completed"] = False
    ev = gamer.json_ld(c, gm, "2026-11-04T01:05:00Z", "2026-11-04T02:00:00Z", "Hardwood Bricks", "https://hardwoodbricks.com/")["@graph"][1]
    assert ev["offers"] == {"@type": "Offer", "url": "https://tix.example/event", "availability": "https://schema.org/InStock",
                            "priceCurrency": "USD", "price": "14.00"}
    c["g"]["completed"] = True
    assert "offers" not in gamer.json_ld(c, gm, "2026-11-04T01:05:00Z", "2026-11-04T02:00:00Z", "Hardwood Bricks")["@graph"][1]
