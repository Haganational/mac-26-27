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
    assert "A2 at H2" in html and "A3 at H3" in html and "A1 at H1" not in html, "finished games are not 'next up'"
    robots = (tmp_path / "robots.txt").read_text()
    assert "Sitemap: https://x.com/horizon/sitemap.xml" in robots and "Sitemap: https://x.com/news-sitemap.xml" in robots
