from datetime import datetime, timezone

import requests

from mac import news

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)

GOOGLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>"Kent State" basketball - Google News</title>
<item><title>Kent State basketball beats Toledo in overtime - Record-Courier</title>
<link>https://news.google.com/rss/articles/abc</link><pubDate>Sun, 08 Nov 2026 22:10:00 GMT</pubDate>
<description>&lt;a href="x"&gt;Kent State basketball beats Toledo&lt;/a&gt;</description>
<source url="https://www.record-courier.com">Record-Courier</source></item>
<item><title>Kent State football falls at Buffalo - Akron Beacon Journal</title>
<link>https://news.google.com/rss/articles/def</link><pubDate>Sun, 08 Nov 2026 20:00:00 GMT</pubDate>
<source url="https://www.beaconjournal.com">Akron Beacon Journal</source></item>
<item><title>Kent State women's basketball opens with win - KentWired</title>
<link>https://news.google.com/rss/articles/ghi</link><pubDate>Sat, 07 Nov 2026 20:00:00 GMT</pubDate>
<source url="https://kentwired.com">KentWired</source></item>
</channel></rss>"""

SIDEARM = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>Men's Basketball</title>
<item><title>Kent State Basketball Beats Toledo in Overtime</title>
<link>https://kentstatesports.com/news/2026/11/8/mbb-recap.aspx</link>
<pubDate>Sun, 08 Nov 2026 23:00:00 GMT</pubDate><description>Recap</description></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>sMACk Talk</title>
<entry><title>Week 1 MAC hoops power rankings: Miami (OH) stays on top</title>
<link rel="alternate" href="https://smacktalk.substack.com/p/week-1"/>
<published>2026-11-08T15:00:00Z</published><summary>Akron and Toledo move up.</summary></entry>
<entry><title>Podcast: grocery store tier list</title>
<link rel="alternate" href="https://smacktalk.substack.com/p/tier"/>
<published>2026-11-07T15:00:00Z</published></entry>
</feed>"""


def feed(key):
    return next(f for f in news.all_feeds() if f.key == key)


def test_feed_list_covers_every_team():
    feeds = news.all_feeds()
    teams = {f.team for f in feeds if f.kind == "google"}
    assert len(teams) == 12
    assert all(f.url.startswith("https://") for f in feeds)
    assert not any("reddit.com" in f.url for f in feeds)


def test_parse_rss_and_atom():
    rss = news.parse_feed(GOOGLE)
    assert len(rss) == 3 and rss[0]["publisher"] == "Record-Courier"
    assert rss[0]["published"] == datetime(2026, 11, 8, 22, 10, tzinfo=timezone.utc)
    atom = news.parse_feed(ATOM)
    assert atom[0]["url"] == "https://smacktalk.substack.com/p/week-1"
    assert atom[0]["published"].hour == 15


def test_google_filters_to_mens_hoops_and_strips_publisher():
    f = feed("google:kent-state")
    items = [x for x in (news.normalize(f, r, NOW) for r in news.parse_feed(GOOGLE)) if x]
    assert [i["title"] for i in items] == ["Kent State basketball beats Toledo in overtime"]
    assert items[0]["source"] == "Record-Courier"
    assert items[0]["teams"] == ["kent-state", "toledo"]


def test_substack_keeps_hoops_and_tags_teams():
    f = feed("substack:smacktalk")
    items = [x for x in (news.normalize(f, r, NOW) for r in news.parse_feed(ATOM)) if x]
    assert len(items) == 1
    assert items[0]["teams"] == ["miami-oh"]


def test_merge_dedupes_and_prefers_school_link():
    g = [news.normalize(feed("google:kent-state"), r, NOW) for r in news.parse_feed(GOOGLE)][0]
    s = news.normalize(feed("athletics:kent-state"), news.parse_feed(SIDEARM)[0], NOW)
    assert g["id"] == s["id"]
    merged = news.merge([g], [s], NOW)
    assert len(merged) == 1
    assert merged[0]["url"].startswith("https://kentstatesports.com/")
    assert set(merged[0]["teams"]) == {"kent-state", "toledo"}


def test_merge_drops_old_items():
    old = {"id": "x", "title": "t", "url": "u", "source": "s", "kind": "google", "feed": "f", "teams": [],
           "published": "2026-08-01T00:00:00+00:00", "first_seen": "2026-08-01T00:00:00+00:00"}
    assert news.merge([old], [], NOW) == []


class FakeResp:
    def __init__(self, body, status=200):
        self.content, self.status = body.encode(), status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status}")


class FakeSession:
    def get(self, url, **_):
        if "kentstatesports" in url:
            return FakeResp(SIDEARM)
        if "smacktalk" in url:
            return FakeResp(ATOM)
        if "google" in url and "Kent" in url:
            return FakeResp(GOOGLE)
        if "gozips" in url:
            return FakeResp("nope", 404)
        return FakeResp("<rss><channel></channel></rss>")


def test_refresh_writes_items_and_feed_status(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "NEWS_DIR", tmp_path)
    monkeypatch.setattr(news, "ITEMS_PATH", tmp_path / "items.json")
    monkeypatch.setattr(news, "FEEDS_PATH", tmp_path / "feeds.json")
    out = news.refresh(NOW, FakeSession())
    assert out["feeds"] == len(news.all_feeds())
    assert out["feeds_ok"] == out["feeds"] - 1
    status = news.load_feed_status()
    assert status["athletics:akron"]["ok"] is False
    v = news.view(NOW, "kent-state")
    assert v["total"] == 1 and v["headlines"][0]["fresh"]
    assert any("CollegeBasketball" in r["url"] for r in v["reddit"])
