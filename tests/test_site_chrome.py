from mac import site_chrome
from mac.config import TEAMS


def test_slug_matches_heading_rules():
    assert site_chrome.slug("This week: when and where to watch") == "this-week-when-and-where-to-watch"
    assert site_chrome.slug("Who covers Miami (OH)") == "who-covers-miami-oh"
    assert site_chrome.slug("!!!") == "section"


def test_anchor_sections_adds_unique_ids_and_keeps_existing():
    page = ('<section><h2>Schedule</h2></section><section id="news"><h2>Latest <a>x</a></h2></section>'
            '<section><h2>Schedule</h2></section><section><p>no heading</p></section>')
    out, found = site_chrome.anchor_sections(page)
    assert found == [("schedule", "Schedule"), ("news", "Latest x"), ("schedule-2", "Schedule")]
    assert '<section id="schedule">' in out and '<section id="schedule-2">' in out
    assert "<section><p>no heading</p>" in out


def test_team_css_has_every_team_and_readable_ink():
    css = site_chrome.teams_css()
    for t in TEAMS:
        assert f".t-{t.key}," in css
        assert site_chrome.contrast(t.color, site_chrome.ink_on(t.color)) >= 3


def test_search_index_covers_teams_players_games_sections():
    games = [{"game_id": "1", "completed": True, "date": "2026-11-03T23:00Z", "neutral_site": False, "venue": "JAR",
              "home": {"key": "akron", "abbr": "AKR", "name": "Akron Zips", "score": 80},
              "away": {"key": None, "abbr": "UL", "name": "Louisiana", "score": 70}},
             {"game_id": "2", "completed": False, "date": "2026-11-20T00:00Z", "neutral_site": False,
              "watch": {"nets": [{"name": "ESPN+"}]},
              "home": {"key": "ohio", "abbr": "OHIO", "name": "Ohio Bobcats", "score": None},
              "away": {"key": "akron", "abbr": "AKR", "name": "Akron Zips", "score": None}}]
    profiles = {"akron": [{"name": "José Pérez", "espn_id": "9", "jersey": "5", "position": "G", "season": {}}]}
    idx = site_chrome.build_search_index({"teams/akron.html": [("schedule", "Schedule")]}, games, {"1"}, profiles,
                                         {"akron": "Coach A"}, {}, lambda g: g["date"][:10])
    by_kind = {}
    for e in idx:
        by_kind.setdefault(e["k"], []).append(e)
    assert len(by_kind["Team"]) == len(TEAMS)
    player = by_kind["Player"][0]
    assert player["u"] == "players/jose-perez-9.html" and "jose perez" in player.get("h", "jose perez")
    urls = [g["u"] for g in by_kind["Game"]]
    assert urls == ["tv.html#g2", "games/1.html"]  # upcoming first; finished links to its box score
    assert "espn+" in by_kind["Game"][0]["h"]
    assert by_kind["Section"][0]["u"] == "teams/akron.html#schedule"


def test_share_card_renders(tmp_path):
    if not site_chrome.pillow_ok():
        return
    from PIL import Image
    p = tmp_path / "card.png"
    site_chrome.share_card(p, "Toledo Rockets", "Roster and schedule", bg=TEAMS[9].color, lines=["1-2 overall"])
    assert Image.open(p).size == (1200, 630)


def test_news_sitemap_keeps_last_two_days():
    from datetime import datetime, timezone
    xml = site_chrome.news_sitemap([("games/1.html", "A beat B 70-60", "2026-11-10T04:00:00Z"),
                                    ("games/2.html", "Old & gone", "2026-11-01T04:00:00Z")],
                                   datetime(2026, 11, 11, 5, tzinfo=timezone.utc))
    assert "games/1.html" in xml and "games/2.html" not in xml and "<news:title>A beat B 70-60</news:title>" in xml
    assert site_chrome.sitemap(["index.html", "mac/index.html", "teams/a.html"]).count("index.html") == 0


def test_game_card_renders_in_house_fonts(tmp_path):
    if not site_chrome.pillow_ok():
        return
    from PIL import Image
    assert (site_chrome.FONT_DIR / "Newsreader-SemiBold.ttf").exists()
    g = {"date": "2026-11-12T23:00Z", "venue": "Rhodes Arena",
         "away": {"key": TEAMS[1].key, "abbr": "KENT", "name": TEAMS[1].name, "score": 71},
         "home": {"key": TEAMS[0].key, "abbr": "AKR", "name": TEAMS[0].name, "score": 78}}
    p = tmp_path / "game.png"
    site_chrome.game_card(p, g, {t.key: t.color for t in TEAMS})
    assert Image.open(p).size == (1200, 630)


def test_top_performer_picks_leading_scorer_and_notable_lines():
    from mac.site_chrome import top_performer
    box = {"players": [
        {"team_espn_id": "5", "name": "Al Smith Jr.", "pts": 22, "reb": 3, "ast": 1, "blk": 4, "stl": 0, "dnp": False},
        {"team_espn_id": "5", "name": "Bo Lee", "pts": 22, "reb": 1, "ast": 0, "blk": 0, "stl": 0, "dnp": False},
        {"team_espn_id": "9", "name": "Cy Day", "pts": 30, "reb": 9, "ast": 5, "blk": 0, "stl": 0, "dnp": False},
    ]}
    tp = top_performer(box, 5)
    assert (tp["last"], tp["pts"], tp["extra"]) == ("Smith", 22, ["4 BLK"])
    assert top_performer(box, 9)["extra"] == ["9 REB", "5 AST"]
    assert top_performer(None, 5) is None


def test_game_card_draws_with_box(tmp_path):
    from mac.site_chrome import game_card, pillow_ok
    if not pillow_ok():
        return
    g = {"date": "2026-11-20T19:00Z", "venue": "Colonial Hall",
         "away": {"espn_id": "5", "key": None, "abbr": "UAB", "name": "UAB Blazers", "score": 101},
         "home": {"espn_id": "9", "key": None, "abbr": "GW", "name": "GW", "score": 76}}
    box = {"players": [{"team_espn_id": "5", "name": "Al Smith", "pts": 22, "reb": 7}, {"team_espn_id": "9", "name": "Cy Day", "pts": 9}]}
    game_card(tmp_path / "c.png", g, {}, box)
    assert (tmp_path / "c.png").stat().st_size > 1000
