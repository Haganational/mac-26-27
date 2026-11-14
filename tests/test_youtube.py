from mac import youtube


def test_title_and_body():
    assert youtube.title("midmaxx60-2026-11-12") == "MidMaxx60: the mid-majors in 60 seconds, Nov. 12"
    assert youtube.title("midmaxx60-2027-05-03") == "MidMaxx60: the mid-majors in 60 seconds, May 3"
    assert youtube.title("midmaxx60") == "MidMaxx60: the mid-majors in 60 seconds"
    b = youtube.body("midmaxx60-2026-11-12", "Akron <won>.\n", "nonsense")
    assert b["status"] == {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}
    assert b["snippet"]["description"].startswith("Akron won.") and "#Shorts" in b["snippet"]["description"]
    assert youtube.body("midmaxx60-2026-11-12", "x", "private")["status"]["privacyStatus"] == "private"


def test_no_secrets_is_a_clean_skip(monkeypatch, capsys):
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("sys.argv", ["youtube"])
    youtube.main()
    assert "YouTube upload skipped" in capsys.readouterr().out


def test_upload_skips_a_day_already_on_the_channel(tmp_path, monkeypatch):
    (tmp_path / "midmaxx60-2026-11-12.mp4").write_bytes(b"x")
    calls = []
    monkeypatch.setattr(youtube, "already_up", lambda token, name: True)
    monkeypatch.setattr(youtube, "_call", lambda *a, **k: calls.append(a) or ({}, {}))
    assert youtube.upload(tmp_path, "t", "public") is None and calls == []


def test_upload_sends_video_then_thumbnail(tmp_path, monkeypatch):
    (tmp_path / "midmaxx60-2026-11-12.mp4").write_bytes(b"vid")
    (tmp_path / "midmaxx60-2026-11-12-thumb.png").write_bytes(b"png")
    seen = []

    def fake(url, token="", data=None, ctype="application/json", method=None):
        seen.append((url, ctype, method))
        if "uploadType=resumable" in url:
            return {}, {"Location": "https://upload.example/session"}
        return {"id": "abc123", "status": {"privacyStatus": "public"}}, {}
    monkeypatch.setattr(youtube, "already_up", lambda token, name: False)
    monkeypatch.setattr(youtube, "_call", fake)
    assert youtube.upload(tmp_path, "t", "public") == "abc123"
    assert seen[1] == ("https://upload.example/session", "video/mp4", "PUT")
    assert "thumbnails/set?videoId=abc123" in seen[2][0]


def test_big_mid_is_a_regular_upload():
    assert youtube.title("bigmid-2026-11-16") == "The Big Mid: the week in mid-majors, Nov. 16"
    d = youtube.body("bigmid-2026-11-16", "x", "public")["snippet"]["description"]
    assert "#Shorts" not in d and "#Midmaxxing" in d
