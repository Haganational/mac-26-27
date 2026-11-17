from mac import anchors


def test_every_anchor_has_color_and_a_real_rival():
    roster, color = anchors.roster(), anchors.color()
    assert set(color) == set(roster)
    for key, c in color.items():
        assert c["voice"] and c["catch"] and c["signoff"], key
        assert c["rival"] in roster and c["rival"] != key, key
        assert len(c["catch"].split()) <= 8, key  # openers stay short so they never push a game out of the Short


def test_first_name_skips_titles():
    assert anchors.first_name("Col. Hank Sterling") == "Hank"
    assert anchors.first_name("Father Dante Russo") == "Dante"
    assert anchors.first_name("Lord Percival Finch") == "Percival"


def _result(winner, loser):
    side = lambda k, w: {"key": k, "mac": True, "winner": w}
    return {"kind": "result", "text": "Final.", "card": {"away": side(loser, False), "home": side(winner, True)}}


def test_dress_opens_needles_and_signs_off():
    segs = [{"kind": "intro", "text": "Good morning."}, _result("akron", "kent-state"), _result("toledo", "ohio")]
    desk = [anchors.for_segment(s) for s in segs]
    anchors.dress(segs, desk)
    akron, toledo = anchors.color()["akron"], anchors.color()["toledo"]
    assert segs[0]["text"] == "Good morning."  # the host is not dressed
    assert segs[1]["text"].startswith(akron["catch"]) and "Nick, that one's for you." in segs[1]["text"]
    assert segs[2]["text"].startswith(toledo["catch"]) and segs[2]["text"].endswith(toledo["signoff"])
    assert "for you" not in segs[2]["text"]  # Ohio is not Toledo's rival


def test_only_the_first_anchors_get_openers():
    keys = ["akron", "toledo", "buffalo"]
    segs = [_result(k, "nobody") for k in keys]
    anchors.dress(segs, [anchors.for_segment(s) for s in segs])
    assert segs[2]["text"].startswith("Final.")


def test_backdrop_prefers_the_school_then_the_edition_then_the_studio(tmp_path, monkeypatch):
    monkeypatch.setattr(anchors, "SETS", tmp_path)
    assert anchors.backdrop("akron") is None
    (tmp_path / "studio.jpg").write_bytes(b"x")
    assert anchors.backdrop("akron").name == "studio.jpg"
    (tmp_path / "mac.webp").write_bytes(b"x")
    assert anchors.backdrop("akron").name == "mac.webp"
    (tmp_path / "akron.jpg").write_bytes(b"x")
    assert anchors.backdrop("akron").name == "akron.jpg"
    assert anchors.backdrop("toledo").name == "mac.webp"


def test_clone_jobs_route_auditions_host_and_piper(tmp_path, monkeypatch):
    import json
    from mac import midmaxx60 as mm
    py, host = tmp_path / "py", tmp_path / "matthew.wav"
    py.write_text(""), host.write_bytes(b"x")
    monkeypatch.setenv("VOICE_CLONE_PY", str(py))
    seen = {}

    def fake_run(cmd, timeout=None):
        jobs = json.loads(open(cmd[cmd.index("--jobs") + 1]).read())
        seen["jobs"], seen["cmd"] = jobs, cmd
        for j in jobs:
            open(j["out"], "wb").write(b"0" * 2000)
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(mm.subprocess, "run", fake_run)
    wavs = [tmp_path / f"{i}.wav" for i in range(3)]
    refs = [mm.HOST, "/tmp/auditions/akron.wav", None]  # host, an anchor with an audition, an anchor without
    monkeypatch.delenv("VOICE_REF", raising=False)
    assert mm.clone_all(["a", "b", "c"], wavs, tmp_path, refs) is False  # no host clip: only the audition is cloned
    assert [j.get("ref") for j in seen["jobs"]] == ["/tmp/auditions/akron.wav"] and "--ref" not in seen["cmd"]
    for w in wavs:
        w.unlink(missing_ok=True)
    monkeypatch.setenv("VOICE_REF", str(host))
    assert mm.clone_all(["a", "b", "c"], wavs, tmp_path, refs) is True
    assert [j.get("ref") for j in seen["jobs"]] == [None, "/tmp/auditions/akron.wav"]
    assert not wavs[2].exists()  # left to the anchor's Piper voice


def test_mood_follows_the_team():
    side = lambda k, w, st: {"key": k, "name": k.replace("-", " ").title(), "mac": True, "winner": w, "streak": st}
    card = {"away": side("kent-state", False, "L3"), "home": side("akron", True, "W4"), "ats": "Akron covered as a 3-point favorite."}
    assert anchors.mood(card, "akron") == "That's 4 straight."
    assert anchors.mood(card, "kent-state").startswith("That's 3 in a row the wrong way.")
    card = {"away": side("ohio", True, "W1"), "home": side("toledo", False, "L1"), "ats": "Ohio covered as a 6-point underdog."}
    assert anchors.mood(card, "ohio") == "Underdogs, folks."
    assert anchors.mood(card, "toledo") == ""
    card["ats"] = "Toledo lost but covered as a 6-point underdog."  # told from the loser's side: no underdog line for Ohio
    assert anchors.mood(card, "ohio") == ""


def test_rivalry_desk_speaks_up_only_when_rivals_meet():
    from mac import anchors
    col, roster = anchors.color(), anchors.roster()
    key = next(k for k in roster if col[k]["rival"] in roster)
    rival = col[key]["rival"]
    other = next(k for k in roster if k not in (key, rival))

    def seg(away):
        return {"kind": "preview", "text": "Tonight.", "card": {"away": {"key": away, "mac": True}, "home": {"key": key, "mac": True}}}

    segs = [seg(rival), seg(other)]
    anchors.dress(segs, [{"key": key}, {"key": key}])
    assert f"Rivalry Desk: {anchors.first_name(roster[rival]['name'])}, bring your best." in segs[0]["text"]
    assert "Rivalry Desk" not in segs[1]["text"]
