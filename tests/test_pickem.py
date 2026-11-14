"""Anchor Pick'em on air reads the Den's desk ledger and never invents a pick."""
import json

from mac import anchors, bigmid, midmaxx60, pickem


def _pick(gid, tid, short, worth, kind="ratings"):
    return {"game_id": gid, "team_id": tid, "short": short, "abbr": short[:3].upper(), "side": "home", "worth": worth, "kind": kind, "why": "", "tip": None}


def _desk(key, name, school, picks):
    return {"anchor": {"key": key, "name": name, "school": school, "color": "#123456"}, "picks": picks, "max": sum(p["worth"] for p in picks)}


def _write(tmp_path):
    led, site = tmp_path / "desk", tmp_path / "site"
    led.mkdir(), (site / "den").mkdir(parents=True)
    y = [_pick("1", "10", "Akron", 20, "homer"), _pick("2", "20", "Toledo", 40), _pick("3", "30", "Ohio", 60), _pick("4", "40", "Sacramento St", 50)]
    (led / "2026-11-13.json").write_text(json.dumps({"date": "2026-11-13", "desk": _desk("akron", "Nick Example", "Akron", y),
                                                      "homer": [{"key": "akron", **y[0]}]}))
    (led / "2026-11-14.json").write_text(json.dumps({"date": "2026-11-14", "desk": _desk("toledo", "Rosa Example", "Toledo", y[1:] + y[:1]), "homer": []}))
    wins = {"1": "10", "2": "20", "3": "99", "4": "40"}
    (site / "den" / "results-2026-11-13.json").write_text(json.dumps(
        {"date": "2026-11-13", "games": [{"id": g, "final": True, "winner_id": w} for g, w in wins.items()]}))
    return led, site


def test_tonights_desk_is_read_by_its_anchor_with_last_nights_score(tmp_path):
    led, site = _write(tmp_path)
    sg = pickem.segment("2026-11-14", led, site)
    assert sg["kind"] == "pickem" and anchors.team_of(sg) == "toledo"
    assert "Toledo, Ohio, Sacramento State and Akron" in sg["text"] and "Last night Nick went three for four." in sg["text"]
    assert sg["card"]["last"]["points"] == 110 and [p["homer"] for p in sg["card"]["picks"]] == [False, False, False, True]


def test_no_ledger_no_segment_and_ungraded_nights_stay_quiet(tmp_path):
    led, site = _write(tmp_path)
    assert pickem.segment("2026-11-20", led, site) is None
    assert pickem.last_night("2026-11-15", led, site) is None  # the 14th has no results yet
    assert "Last night" not in pickem.segment("2026-11-13", led, site)["text"]


def test_board_counts_only_graded_nights(tmp_path):
    led, site = _write(tmp_path)
    b = pickem.board(led, site)
    assert [r["points"] for r in b["card"]["desk"]] == [110] and "Marcus Vance of the Akron desk leads the board with 110 points." in b["text"]
    assert b["card"]["homer"] == []  # one game is not a ledger yet
    assert pickem.board(tmp_path / "nowhere", site) is None


def test_a_game_is_never_cut_for_the_desk():
    assert "pickem" in midmaxx60.DROP_FIRST and "pickem" in bigmid.DROP_FIRST
