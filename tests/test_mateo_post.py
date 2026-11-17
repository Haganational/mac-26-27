import json

import pytest

from mac import mateo_post


def test_body_adds_disclosure_shorts_and_synthetic_flag():
    b = mateo_post.body({"title": "I'm Independent Now <boss>", "description": "Welcome to MY channel."})
    d = b["snippet"]["description"]
    assert d.startswith(mateo_post.DISCLOSURE) and d.rstrip().endswith("#Shorts")
    assert b["snippet"]["title"] == "I'm Independent Now boss"
    assert b["status"]["containsSyntheticMedia"] is True and b["status"]["privacyStatus"] == "public"
    assert mateo_post.body({"title": "x", "description": mateo_post.DISCLOSURE, "short": False})["snippet"]["description"] == mateo_post.DISCLOSURE


def test_skips_posts_not_marked_go(tmp_path, monkeypatch):
    (tmp_path / "post.json").write_text(json.dumps({"title": "x"}))
    monkeypatch.setattr(mateo_post, "_call", lambda *a, **k: pytest.fail("no API call expected"))
    assert mateo_post.post_one(tmp_path, "t") is None


def test_refuses_a_token_for_the_wrong_channel(tmp_path, monkeypatch, capsys):
    for k, v in {"YT_CLIENT_ID": "c", "YT_CLIENT_SECRET": "s", "YT_REFRESH_TOKEN_MATEO": "r"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(mateo_post, "access_token", lambda *a: "t")
    monkeypatch.setattr(mateo_post, "channel_title", lambda t: "Hardwood Bricks")
    monkeypatch.setattr(mateo_post, "post_one", lambda *a: pytest.fail("must not upload"))
    monkeypatch.setattr("sys.argv", ["mateo_post", str(tmp_path)])
    with pytest.raises(SystemExit):
        mateo_post.main()
    assert "not Mateo's channel" in capsys.readouterr().out


def test_uploads_and_records_the_id(tmp_path, monkeypatch):
    (tmp_path / "video.mp4").write_bytes(b"vid")
    (tmp_path / "post.json").write_text(json.dumps({"title": "Hi", "go": True}))

    def fake(url, token="", data=None, ctype="application/json", method=None):
        return ({}, {"Location": "https://u/s"}) if "resumable" in url else ({"id": "abc"}, {})
    monkeypatch.setattr(mateo_post, "already_up", lambda t, n: False)
    monkeypatch.setattr(mateo_post, "_call", fake)
    assert mateo_post.post_one(tmp_path, "t") == "abc"
    assert json.loads((tmp_path / "post.json").read_text())["url"] == "https://youtube.com/shorts/abc"
