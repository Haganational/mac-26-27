"""The Watch page shows the shows, every anchor, and only what the shows themselves use."""
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader

from mac import anchors, watch
from mac.config import TEMPLATES_DIR


def test_every_anchor_is_on_the_desk_once():
    keys = [a["key"] for c in watch.desk() for a in c["anchors"]]
    assert sorted(keys) == sorted(anchors.roster()) and len(set(keys)) == len(keys)


def test_playlists_are_the_channels_own_upload_lists():
    p = watch.playlists()
    assert p["midmaxx60"].startswith("UUSH") and p["bigmid"].startswith("UULF") and p["midmaxx60"][4:] == p["bigmid"][4:]


def test_todays_story_is_a_checked_one():
    s = watch.story("2026-11-14")
    assert s and s["checked"] and s["source"].startswith("https://") and s["anchor"]["name"]


def test_page_renders_with_and_without_a_desk_tonight():
    ctx = watch.page_context(datetime(2026, 11, 14, 18, tzinfo=timezone.utc))
    tpl = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True).get_template("watch.html")
    for tonight in (ctx["tonight"], None):
        html = tpl.render(eds=[], names="MAC", base="https://x/", season="2026-27", noindex=True, today="Saturday", built="now", **{**ctx, "tonight": tonight})
        assert "The Big Mid" in html and "AI personas" in html and html.count('class="an"') == len(anchors.roster())


def test_every_anchor_gets_a_page_with_their_stories(tmp_path):
    from mac import alumni
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    n = watch.build_profiles(env, tmp_path, eds=[], base="https://x/", season="2026-27", noindex=True, built="now")
    assert n == len(anchors.roster())
    key = next(k for k in anchors.roster() if alumni.stories(k))
    html = (tmp_path / "anchors" / f"{key}.html").read_text()
    assert alumni.stories(key)[0]["name"] in html and anchors.roster()[key]["name"] in html and '<base href="../">' in html
    p = watch.profile(key)
    assert p["rival"]["href"].startswith("anchors/") and p["team_href"].endswith(f"teams/{key}.html")
    with_bio = next(k for k in anchors.roster() if anchors.bio(k))
    page = (tmp_path / "anchors" / f"{with_bio}.html").read_text()
    assert "Who they are" in page and anchors.bio(with_bio)[:40].replace("'", "&#39;").replace('"', "&#34;") in page


def test_latest_upload_comes_from_the_feed_and_survives_an_outage(tmp_path, monkeypatch):
    from mac import watch
    monkeypatch.setattr(watch, "LATEST", tmp_path / "yl.json")
    xml = ("<feed><entry><id>yt:video:abcDEF12345</id><yt:videoId>abcDEF12345</yt:videoId><yt:channelId>UC1</yt:channelId>"
           "<title>MidMaxx60 &amp; friends</title><published>2026-11-14T12:00:00+00:00</published></entry></feed>")
    got = watch.latest(fetch=lambda url: xml)
    assert got["midmaxx60"] == {"id": "abcDEF12345", "title": "MidMaxx60 & friends", "published": "Sat, Nov 14"}

    def down(url):
        raise OSError("feed down")
    assert watch.latest(fetch=down)["midmaxx60"]["id"] == "abcDEF12345"  # last good poster kept
