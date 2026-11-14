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
