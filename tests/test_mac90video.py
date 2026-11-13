from mac.mac90video import _counted, ass_events, ass_file, chunks


def test_chunks_break_on_punctuation_and_size():
    groups = chunks("Last night: Western Michigan beat Campbell 87-71. Done.")
    assert groups[0] == ["Last", "night:"]
    assert all(len(g) <= 6 for g in groups)
    assert sum(len(g) for g in groups) == 8


def test_captions_cover_the_speech():
    ev = ass_events("Tonight: Cleveland State visits Bowling Green, 7 p.m. on ESPN+.", start=10.0, speech=4.0)
    assert ev[0].startswith("Dialogue: 0,0:00:10.")
    assert "{\\kf" in ev[0]
    last_end = ev[-1].split(",")[2]
    assert last_end.startswith("0:00:13.9") or last_end.startswith("0:00:14.0")
    assert "[Events]" in ass_file(ev)


def test_count_up_scales_scores_without_touching_the_original():
    seg = {"kind": "result", "card": {"away": {"score": 71}, "home": {"score": 87}}}
    half = _counted(seg, 0.5)
    assert half["card"]["away"]["score"] == 36 and half["card"]["home"]["score"] == 44
    assert seg["card"]["home"]["score"] == 87


def test_stale_or_empty_script_is_skipped_with_an_alert(monkeypatch):
    from datetime import datetime, timezone

    from mac import mac90video
    sent = []
    monkeypatch.setattr(mac90video.alert, "send", lambda subject, body: sent.append((subject, body)) or True)
    now = datetime(2026, 11, 12, 13, 0, tzinfo=timezone.utc)
    t = {"date_label": "Thursday, November 12", "results": [{}], "previews": []}
    assert mac90video.check(t, "2026-11-12T12:31:00+00:00", now) is None and sent == []
    assert "11 hours ago" in mac90video.check(t, "2026-11-12T02:00:00Z", now)
    assert sent[0][0] == "MAC90 skipped for Thursday, November 12"
    assert "no results" in mac90video.check({**t, "results": []}, "2026-11-12T12:31:00+00:00", now)
    assert mac90video.check(t, "", now) is None  # no commit time to go on: trust the script
