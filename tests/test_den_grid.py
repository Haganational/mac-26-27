import json

from mac import den_grid


def _data():
    """Six made-up schools; franchises A..E. Enough overlap for several grids."""
    schools = {}
    for s in range(6):
        alumni = []
        for k, codes in enumerate([["A", "B"], ["B", "C"], ["C", "D"], ["A", "D"], ["E", "A"], ["B", "E"], ["C", "E"], ["D", "B"]]):
            alumni.append({"name": f"P{s}-{k}", "qid": f"Q{s}{k}", "teams": codes})
        schools[str(100 + s)] = {"name": f"School {s}", "short": f"S{s}", "edition": "MAC", "alumni": alumni}
    return {"franchises": {c: f"Team {c}" for c in "ABCDE"}, "schools": schools}


def test_grid_is_deterministic_and_solvable():
    d = _data()
    g1, g2 = den_grid.make_grid(d, "2026-11-20"), den_grid.make_grid(d, "2026-11-20")
    assert g1 == g2 and len(g1["rows"]) == 3 and len(g1["cols"]) == 3
    assert set(g1["cells"]) == {f"{i},{j}" for i in range(3) for j in range(3)}
    for k, ids in g1["cells"].items():
        i, j = map(int, k.split(","))
        code, sid = g1["cols"][j]["code"], g1["rows"][i]["id"]
        assert ids, k
        for p in ids:
            name = g1["players"][p]
            alum = next(a for a in d["schools"][sid]["alumni"] if a["name"] == name)
            assert code in alum["teams"]
    assert den_grid._distinct_solution({k: set(v) for k, v in g1["cells"].items()})


def test_search_list_covers_all_alumni_of_the_three_schools():
    d = _data()
    g = den_grid.make_grid(d, "2026-11-21")
    want = {a["name"] for r in g["rows"] for a in d["schools"][r["id"]]["alumni"]}
    assert set(g["players"]) == want


def test_no_grid_when_data_is_too_thin():
    d = {"franchises": {}, "schools": {"1": {"name": "x", "short": "x", "alumni": [{"name": "a", "teams": ["A"]}]}}}
    assert den_grid.make_grid(d, "2026-11-20") is None


def test_distinct_solution_rejects_one_player_for_two_squares():
    assert not den_grid._distinct_solution({(0, 0): {"x"}, (0, 1): {"x"}})
    assert den_grid._distinct_solution({(0, 0): {"x", "y"}, (0, 1): {"x"}})


def test_check_counts_a_player_once():
    g = {"cells": {"0,0": [1, 2], "0,1": [1]}}
    assert den_grid.check(g, {"0,0": 1, "0,1": 1}) == {"0,0": True, "0,1": False}


def test_build_writes_three_days(tmp_path):
    src = tmp_path / "alumni.json"
    src.write_text(json.dumps(_data()))
    from datetime import datetime, timezone
    n = den_grid.build(tmp_path / "site", datetime(2026, 11, 14, 15, tzinfo=timezone.utc), path=src)
    assert n == 3
    assert sorted(p.name for p in (tmp_path / "site" / "den").glob("grid-*.json")) == [
        "grid-2026-11-14.json", "grid-2026-11-15.json", "grid-2026-11-16.json"]


def test_build_without_data_is_quiet(tmp_path):
    assert den_grid.build(tmp_path, path=tmp_path / "missing.json") == 0


def test_unnamed_players_are_left_out():
    d = _data()
    for s in d["schools"].values():
        s["alumni"].append({"name": "", "qid": "Q1", "teams": ["A", "B", "C", "D", "E"]})
        s["alumni"].append({"name": "Q123", "qid": "Q123", "teams": ["A"]})
    g = den_grid.make_grid(d, "2026-11-20")
    assert "" not in g["players"] and "Q123" not in g["players"]
