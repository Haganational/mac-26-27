import json
from datetime import date

from mac import flavor_queue as fq
from mac.leagues import ALL


def test_parse_marks_and_parts():
    items = fq.parse("x 1: Town line. | Second line. home: Home only.\n~ 2: half\n- 3\nx 4: \n5: no mark floor: the Barn")
    by = {i["n"]: i for i in items}
    assert by[1]["kind"] == "done" and by[1]["lines"] == ["Town line.", "Second line."]
    assert by[1]["home_lines"] == ["Home only."]
    assert by[2]["kind"] == "started" and by[2]["raw"] == "half"
    assert by[3]["kind"] == "skip"
    assert 4 not in by  # untouched template line
    assert by[5]["kind"] == "done" and by[5]["floor"] == "the Barn" and by[5]["lines"] == ["no mark"]


def test_pick_and_apply(tmp_path, monkeypatch):
    lg = ALL["horizon"]
    monkeypatch.setattr(fq, "flavor_path", lambda l: tmp_path / l.key / "flavor.json")
    prog = tmp_path / "progress.json"
    p = fq.load_progress(prog)
    rows = fq.pick(date(2026, 11, 13), 67, p)
    assert len(rows) == 67  # nothing written yet in the temp flavor files
    first = [r["id"] for r in rows[:3]]
    p["days"]["2026-11-13"] = first
    fq.save_json(prog, p)
    rep = fq.apply("x 1: A line. home: At home.\n~ 2: draft\n- 3", progress_path=prog)
    assert len(rep) == 3
    lk, tk = first[0].split("/")
    f = json.loads((tmp_path / lk / "flavor.json").read_text())
    assert f["teams"][tk]["lines"] == ["A line."] and f["teams"][tk]["home_lines"] == ["At home."]
    p = fq.load_progress(prog)
    assert p["partial"][first[1]] == "draft" and first[2] in p["skipped"]
    nxt = [r["id"] for r in fq.pick(date(2026, 11, 14), 67, p)]
    assert first[0] not in nxt
    assert nxt[0] == first[1]  # started ones come back first
    assert nxt[-1] == first[2]  # skipped ones go last
