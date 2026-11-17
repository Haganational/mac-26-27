from mac import honors


def test_ohio_film_is_pinned():
    f = honors.films()
    assert f["ohio"][0]["youtube"] == "H6GUKT38RN0" and f["ohio"][0]["title"]
    assert f["toledo"][0]["youtube"] == "S7vx_vBG8qk"


def test_line_reads_like_a_box_score():
    r = {"pts": 31, "reb": 9, "ast": 2}
    assert honors._line(r) == "31 points, 9 rebounds"


def test_fight_songs_only_show_rows_with_a_video(tmp_path, monkeypatch):
    import json
    from mac import honors
    f = tmp_path / "fight_songs.json"
    f.write_text(json.dumps({"songs": {"ohio": {"title": "Stand Up and Cheer", "youtube": "abc"}, "toledo": {"title": "U of Toledo"}}}))
    monkeypatch.setattr(honors, "FIGHT_SONGS", f)
    assert list(honors.fight_songs()) == ["ohio"]
