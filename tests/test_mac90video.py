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
