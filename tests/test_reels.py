from pathlib import Path

from mac import reels

DESC = "This is MidMaxx60 for Saturday, November 14. 8 conferences, sixty seconds.\n\nLast night. MAC: Purdue beat Ohio 80-62.\n"


def test_caption_leads_with_the_title_and_discloses():
    c = reels.caption("midmaxx60-2026-11-14", DESC, "midmaxx60")
    assert c.startswith("MidMaxx60: the mid-majors in 60 seconds, Nov. 14\n\nThis is MidMaxx60 for Saturday")
    assert "Purdue" not in c  # only the opening line, not the whole script
    assert "https://hardwoodbricks.com/midmaxx60.html" in c and "#Midmaxxing" in c and reels.DISCLOSURE in c
    long = reels.caption("midmaxx60-2026-11-14", "x" * 5000, "midmaxx60")
    assert len(long) <= 2200 and long.startswith("MidMaxx60")


def test_short_caption_fits_bluesky():
    s = reels.short_caption("bigmid-2026-11-16", "bigmid")
    assert s.startswith("The Big Mid") and len(s) <= 300 and "watch.html" in s


def test_bluesky_link_facet_covers_the_url():
    s = reels.short_caption("midmaxx60-2026-11-14", "midmaxx60")
    b = s.encode()
    links = [f for f in reels._facets(s) if f["features"][0]["$type"].endswith("#link")]
    assert len(links) == 1
    i = links[0]["index"]
    assert b[i["byteStart"]:i["byteEnd"]] == b"https://hardwoodbricks.com/midmaxx60.html"


def test_networks_follow_secrets_and_show():
    env = {"FB_PAGE_ID": "1", "FB_PAGE_TOKEN": "t", "IG_ACCESS_TOKEN": "i", "THREADS_ACCESS_TOKEN": "th",
           "BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": " "}
    assert reels.networks("midmaxx60", env) == ["facebook", "instagram", "threads"]
    assert reels.networks("bigmid", env) == ["facebook"]  # 16:9 and five minutes: no Reel, no Threads video
    assert reels.networks("bigmid", {**env, "BSKY_APP_PASSWORD": "p"}) == ["facebook", "bluesky"]
    assert reels.networks("midmaxx60", {}) == []


def test_release_url():
    assert reels.release_url("midmaxx60-2026-11-14") == \
        "https://github.com/Haganational/mac-26-27/releases/download/midmaxx60-2026-11-14/midmaxx60-2026-11-14.mp4"


def test_no_secrets_is_a_clean_skip(tmp_path, monkeypatch, capsys):
    for k in ("FB_PAGE_ID", "IG_ACCESS_TOKEN", "THREADS_ACCESS_TOKEN", "BSKY_HANDLE", "SOCIAL_DRY_RUN"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "midmaxx60-2026-11-14.mp4").write_bytes(b"x")
    assert reels.run(tmp_path, "midmaxx60") == 0
    assert "skipped" in capsys.readouterr().out


def test_one_failure_does_not_stop_the_rest(tmp_path, monkeypatch):
    (tmp_path / "midmaxx60-2026-11-14.mp4").write_bytes(b"x")
    monkeypatch.delenv("SOCIAL_DRY_RUN", raising=False)
    monkeypatch.setattr(reels, "networks", lambda show: ["facebook", "bluesky"])
    tried, alerts = [], []

    def post_one(net, show, mp4, desc):
        tried.append(net)
        if net == "facebook":
            raise RuntimeError("token expired")
        return "posted"
    monkeypatch.setattr(reels, "post_one", post_one)
    monkeypatch.setattr(reels.alert, "send", lambda subject, body: alerts.append(subject))
    assert reels.run(tmp_path, "midmaxx60") == 1
    assert tried == ["facebook", "bluesky"] and alerts == ["MidMaxx60 did not post to Facebook"]


def test_facebook_skips_a_day_already_posted(tmp_path, monkeypatch):
    mp4 = tmp_path / "midmaxx60-2026-11-14.mp4"
    mp4.write_bytes(b"x")
    monkeypatch.setenv("FB_PAGE_ID", "1")
    monkeypatch.setenv("FB_PAGE_TOKEN", "t")
    monkeypatch.setattr(reels, "fb_already", lambda page, token, head: head.endswith("Nov. 14"))
    monkeypatch.setattr(reels, "fb_reel", lambda *a: (_ for _ in ()).throw(AssertionError("posted twice")))
    assert reels.post_one("facebook", "midmaxx60", mp4, DESC) == "already posted"


def test_instagram_through_the_page_token():
    env = {"FB_PAGE_ID": "1", "FB_PAGE_TOKEN": "pt", "IG_USER_ID": "1784"}
    assert reels.networks("midmaxx60", env) == ["facebook", "instagram"]
    assert reels.ig_auth(env) == ("pt", "1784", reels.GRAPH)
    assert reels.ig_auth({**env, "IG_ACCESS_TOKEN": "it"}) == ("it", "1784", reels.IG)
    assert reels.ig_auth({"IG_ACCESS_TOKEN": "it"}) == ("it", "me", reels.IG)


def test_page_token_swaps_a_user_token(monkeypatch):
    class R:
        def __init__(self, ok, body): self.ok, self._b = ok, body
        def json(self): return self._b
    monkeypatch.setattr(reels.requests, "get", lambda *a, **k: R(True, {"access_token": "page", "id": "1"}))
    assert reels.page_token("1", "user") == "page"
    monkeypatch.setattr(reels.requests, "get", lambda *a, **k: R(False, {"error": {}}))
    assert reels.page_token("1", "page") == "page"
