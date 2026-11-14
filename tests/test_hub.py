import json
from unittest.mock import patch

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


def test_media_page_for_sids(tmp_path):
    (tmp_path / "data.json").write_text(json.dumps({"recent": [], "upcoming": [], "tonight": []}))
    mh = {"editor": "Pat Editor", "email": "press@x.com", "staff": [{"name": "Pat Editor", "title": "Editor and publisher"}],
          "media": {"in_person": "Home games in Northeast Ohio.", "samples": [{"title": "A good recap", "href": "games/9.html", "kind": "Recap"}]}}
    with patch.object(hub, "load_masthead", return_value=mh):
        hub.build(tmp_path, "https://x.com/")
    html = (tmp_path / "media.html").read_text()
    assert '<link rel="canonical" href="https://x.com/media.html">' in html
    assert "Pat Editor" in html and 'mailto:press@x.com' in html and "Home games in Northeast Ohio." in html
    assert 'href="games/9.html">A good recap' in html, "hand-picked samples win"
    assert 'notes.html">MAC</a>' in html, "editions with Fieldhouse Notes are linked"
    assert 'href="media.html"' in (tmp_path / "masthead.html").read_text()


def test_media_samples_fall_back_to_newest_stories():
    sts = [{"title": f"R{i}", "href": f"games/{i}.html", "kind": "recap", "league": "MAC"} for i in range(5)]
    sts.append({"title": "A at B prediction", "href": "games/p.html", "kind": "preview", "league": "MAC"})
    got = hub.media_samples({}, sts)
    assert [s["title"] for s in got] == ["R0", "R1", "R2", "A at B prediction"]


def test_build_writes_privacy_page_for_google_oauth(tmp_path):
    hub.build(tmp_path, "https://x.com/")
    html = (tmp_path / "privacy.html").read_text()
    assert '<link rel="canonical" href="https://x.com/privacy.html">' in html
    assert "YouTube API Services" in html and "policies.google.com/privacy" in html
    assert 'href="privacy.html"' in (tmp_path / "index.html").read_text()


def test_den_page_and_its_quiet_front_page_line(tmp_path):
    from datetime import datetime, timezone
    hub.build(tmp_path, "https://x.com/")
    front = (tmp_path / "index.html").read_text()
    assert 'href="den.html">The Den</a>' in front and 'class="den-tz"' not in front, "no slate, no teaser line"
    den = (tmp_path / "den.html").read_text()
    assert '<link rel="canonical" href="https://x.com/den.html">' in den and 'aria-current="page">The Den' in den
    today = datetime.now(timezone.utc).astimezone(hub.ET).strftime("%Y-%m-%d")
    (tmp_path / "den").mkdir()

    def side(i, ed):
        return {"key": f"t{i}", "id": str(i), "short": f"T{i}", "abbr": f"T{i}", "edition": ed}
    (tmp_path / "den" / f"slate-{today}.json").write_text(json.dumps({"date": today, "games": [
        {"id": "g1", "home": side(1, "mac"), "away": side(2, None)}, {"id": "g2", "home": side(3, "horizon"), "away": side(1, "mac")}]}))
    hub.build(tmp_path, "https://x.com/")
    assert "Tonight's Bricksanity: 2 teams eligible" in (tmp_path / "index.html").read_text()
