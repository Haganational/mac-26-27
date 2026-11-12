import json

from mac import hub
from mac.leagues import ALL


def _g(gid, home, away, done, **kw):
    return {"game_id": gid, "home": {"espn_id": home, "abbr": "H" + gid, "score": 70, "winner": True},
            "away": {"espn_id": away, "abbr": "A" + gid, "score": 60}, "completed": done,
            "et": {"weekday": "Wed", "time": "7 PM"}, "broadcasts": [{"name": "ESPN+"}], **kw}


def test_owner_is_first_edition_with_a_team():
    akron, ysu = ALL["mac"].teams[0].espn_id, next(t.espn_id for t in ALL["horizon"].teams if t.key == "youngstown-state")
    assert hub.game_owner(akron, ysu).key == "mac"
    assert hub.game_owner(ysu, "99999").key == "horizon"
    assert hub.game_owner("99999") is None


def test_build_links_canonical_copy_and_writes_robots(tmp_path):
    akron, ysu = ALL["mac"].teams[0].espn_id, next(t.espn_id for t in ALL["horizon"].teams if t.key == "youngstown-state")
    (tmp_path / "games").mkdir(); (tmp_path / "horizon" / "games").mkdir(parents=True)
    (tmp_path / "games" / "1.html").write_text("x"); (tmp_path / "horizon" / "games" / "1.html").write_text("x")
    (tmp_path / "data.json").write_text(json.dumps({"recent": [_g("1", akron, ysu, True)], "upcoming": [_g("2", akron, "5", False)], "tonight": []}))
    (tmp_path / "horizon" / "data.json").write_text(json.dumps({"recent": [_g("1", akron, ysu, True)], "tonight": [_g("1", akron, ysu, True), _g("3", ysu, "5", False)]}))
    hub.build(tmp_path, "https://x.com/")
    html = (tmp_path / "index.html").read_text()
    assert '<link rel="canonical" href="https://x.com/">' in html and 'href="mac/index.html"' in html
    assert html.count('href="games/1.html"') == 2, "the Horizon card links the MAC copy Google indexes"
    assert "A2 at Akron" in html and "A3 at Youngstown State" in html and "A1 at Akron" not in html, "finished games are not 'next up'"
    robots = (tmp_path / "robots.txt").read_text()
    assert "Sitemap: https://x.com/horizon/sitemap.xml" in robots and "Sitemap: https://x.com/news-sitemap.xml" in robots


def test_age_labels():
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 11, 12, 17, tzinfo=timezone.utc)
    assert hub._age(now - timedelta(minutes=5), now) == "5m ago"
    assert hub._age(now - timedelta(hours=3), now) == "3h ago"
    assert hub._age(now - timedelta(hours=30), now) == "yesterday"


def test_front_page_leads_with_our_newest_recap(tmp_path):
    akron = ALL["mac"].teams[0].espn_id
    (tmp_path / "games").mkdir()
    (tmp_path / "data.json").write_text(json.dumps({"recent": [], "upcoming": [_g("2", akron, "5", False)], "tonight": []}))
    page = '<meta property="og:description" content="{d}">\n<meta property="og:image" content="https://x.com/static/og/game-{i}.png">'
    (tmp_path / "games" / "7.html").write_text(page.format(d="Akron won going away.", i=7))
    (tmp_path / "games" / "8.html").write_text(page.format(d="Older one.", i=8))
    news = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
<url><loc>https://x.com/games/8.html</loc><news:news><news:publication_date>2026-11-11T02:00:00Z</news:publication_date><news:title>Ohio beat Kent State 70-60</news:title></news:news></url>
<url><loc>https://x.com/games/7.html</loc><news:news><news:publication_date>2026-11-12T02:00:00Z</news:publication_date><news:title>Akron rolled past Toledo 90-70</news:title></news:news></url>
</urlset>"""
    (tmp_path / "news-sitemap.xml").write_text(news)
    import mac.social as social
    old = social.SITE_BASE
    social.SITE_BASE = "https://x.com/"
    try:
        hub.build(tmp_path, "https://x.com/")
    finally:
        social.SITE_BASE = old
    html = (tmp_path / "index.html").read_text()
    lead = html.index('class="lead')
    assert html.index("Akron rolled past Toledo 90-70") > lead and "Akron won going away." in html
    assert 'src="static/og/game-7.png"' in html, "card images are site-relative"
    assert html.index("Akron rolled past Toledo") < html.index("Ohio beat Kent State"), "newest first"
