from mac.midmaxx60 import _counted, ass_events, ass_file, chunks


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

    from mac import midmaxx60
    sent = []
    monkeypatch.setattr(midmaxx60.alert, "send", lambda subject, body: sent.append((subject, body)) or True)
    now = datetime(2026, 11, 12, 13, 0, tzinfo=timezone.utc)
    t = {"date_label": "Thursday, November 12", "results": [{}], "previews": []}
    assert midmaxx60.check(t, "2026-11-12T12:31:00+00:00", now) is None and sent == []
    assert "11 hours ago" in midmaxx60.check(t, "2026-11-12T02:00:00Z", now)
    assert sent[0][0] == "MidMaxx60 skipped for Thursday, November 12"
    assert "no results" in midmaxx60.check({**t, "results": []}, "2026-11-12T12:31:00+00:00", now)
    assert midmaxx60.check(t, "", now) is None  # no commit time to go on: trust the script


def test_fit_keeps_the_short_under_sixty_seconds():
    from mac.midmaxx60 import fit
    kinds = ["intro", "result", "result", "tuneups", "preview", "preview", "move", "standings", "note", "outro"]
    segs = [{"kind": k} for k in kinds]
    secs = [3.0, 8.0, 8.0, 5.0, 7.0, 7.0, 6.0, 5.0, 6.0, 5.0]  # 60 seconds in all
    keep = fit(segs, secs)
    assert sum(secs[i] for i in keep) <= 59.0
    assert [kinds[i] for i in keep] == ["intro", "result", "result", "preview", "preview", "move", "standings", "note", "outro"]
    # A long night: extras go, then the last of the longer list; one result and one preview survive.
    long = fit(segs, [3.0, 20.0, 20.0, 5.0, 12.0, 12.0, 6.0, 5.0, 6.0, 5.0])
    assert [kinds[i] for i in long] == ["intro", "result", "preview", "outro"]
    assert fit(segs, [1.0] * 10) == list(range(10))


def test_combine_dedupes_a_game_two_editions_share():
    from mac import midmaxx60 as mm
    game = {"kind": "result", "game_id": "g1", "label": "Since Thursday", "text": "Bowling Green beat Niagara 88-76.", "card": {}}
    base = {"date_label": "Saturday, November 14", "date_iso": "2026-11-14", "results_label": "Since Thursday", "slate_label": "Tonight"}
    a = {**base, "league": "mac", "league_short": "MAC", "segments": [{"kind": "intro", "text": "x"}, dict(game)]}
    b = {**base, "league": "metro", "league_short": "Metro", "segments": [{"kind": "intro", "text": "x"}, dict(game)]}
    segs = mm.combine([a, b])["segments"]
    assert [s["kind"] for s in segs].count("result") == 1


def test_anchor_reads_our_side():
    from mac import anchors
    seg = {"kind": "result", "card": {"away": {"mac": True, "key": "niagara", "winner": False},
                                      "home": {"mac": True, "key": "siena", "winner": True}}}
    assert anchors.team_of(seg) == "siena"
    seg["card"]["home"]["mac"] = False
    assert anchors.team_of(seg) == "niagara"
    assert anchors.team_of({"kind": "intro"}) is None
    a = anchors.for_segment(seg)
    assert a["school"] and a["voice"] in anchors.VOICE_POOL[anchors.roster()["niagara"]["gender"]]
