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
    assert player["u"] == "teams/akron.html#p9" and "jose perez" in player.get("h", "jose perez")
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
