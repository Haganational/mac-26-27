import json

from mac import weekly
from mac.config import LEAGUES


def test_every_conference_has_a_complete_issue():
    for key in LEAGUES:
        issue = weekly.latest(key)
        assert issue, key
        assert issue["lead"]["headline"] and issue["lead"]["body"]
        assert issue["notes"]
        col = issue["column"]
        assert col.get("dispatch") or (col.get("title") and col.get("body"))


def test_issues_sort_and_latest(tmp_path):
    d = tmp_path / "mac"
    d.mkdir()
    for n in (0, 1):
        (d / f"{n:03d}.json").write_text(json.dumps({"edition": n}))
    assert [f.stem for f in weekly.issues("mac", tmp_path)] == ["000", "001"]
    assert weekly.latest("mac", tmp_path)["edition"] == 1
    assert weekly.latest("asun", tmp_path) is None


def test_inline_escapes_and_bolds():
    assert weekly._inline("**A 70, B 60.** x < y") == "<b>A 70, B 60.</b> x &lt; y"


def test_chart_orders_by_rating_and_skips_unrated():
    st = [{"key": "a", "team": "A", "w": 1, "l": 2}, {"key": "b", "team": "B", "w": 3, "l": 0}, {"key": "c", "team": "C", "w": 0, "l": 0}]
    ch = weekly.chart(st, {"a": {"adj_em": -4.0}, "b": {"adj_em": 8.04}})
    assert [(r["team"], r["rec"], r["em"], r["pos"]) for r in ch["rows"]] == [("B", "3-0", 8.0, True), ("A", "1-2", -4.0, False)]
    assert ch["rows"][0]["x"] == ch["zero"]
    assert weekly.chart([], {})["rows"] == []


def test_context_uses_a_dispatch_as_the_column():
    issue = {"edition": 0, "date": "2026-11-12", "lead": {"headline": "H", "body": ["p"]},
             "column": {"dispatch": "s1"}, "notes": [{"headline": "N", "body": "b"}]}
    ctx = weekly.context(issue, {}, [{"slug": "s1", "title": "T", "author": "", "html": "<p>x</p>"}])
    assert ctx["column"]["title"] == "T" and ctx["column"]["byline"] == "Matthew Hagan"
    assert ctx["column"]["href"] == "notes.html#n-s1"
    assert ctx["dateline"] == "Thursday, November 12, 2026" and ctx["number"] == "000"
    look = weekly.context({**issue, "column": {"title": "Picks", "body": ["**A.** yes"]}}, {}, [])
    assert look["column"]["html"] == "<p><b>A.</b> yes</p>"


def test_rotation_covers_every_conference_once():
    keys = [k for day in weekly.ROTATION.values() for k in day]
    assert sorted(keys) == sorted(LEAGUES) and len(keys) == len(set(keys))
    from datetime import date
    assert weekly.due(date(2026, 11, 30)) == weekly.ROTATION["Mon"]


def test_check_wants_the_next_edition_and_a_full_issue(tmp_path):
    (tmp_path / "mac").mkdir()
    (tmp_path / "mac" / "000.json").write_text(json.dumps({"edition": 0}))
    good = {"edition": 1, "date": "2026-11-30",
            "lead": {"kicker": "k", "headline": "h", "deck": "d", "body": ["a", "b", "c"]},
            "column": {"label": "By the Numbers", "title": "t", "byline": "Hardwood Bricks staff", "body": ["x"]},
            "notes": [{"headline": "n", "body": "b"}] * 4}
    assert weekly.check(good, "mac", tmp_path) == []
    bad = {**good, "edition": 0, "notes": [], "column": {**good["column"], "byline": "Matthew Hagan"}}
    assert len(weekly.check(bad, "mac", tmp_path)) == 3


def test_check_skips_the_issue_own_file(tmp_path):
    (tmp_path / "mac").mkdir()
    (tmp_path / "mac" / "000.json").write_text(json.dumps({"edition": 0}))
    f = tmp_path / "mac" / "001.json"
    f.write_text(json.dumps({"edition": 1}))
    assert "edition should be 2" in weekly.check({"edition": 1}, "mac", tmp_path)
    assert not any("edition" in p for p in weekly.check({"edition": 1}, "mac", tmp_path, path=f))


def test_papers_layout_is_stable_and_photo_prefers_the_lead_school():
    a, b = weekly.paper("mac"), weekly.paper("mac")
    assert a["sidebar"] == b["sidebar"] and a["tone"] in weekly.TONES
    lay = weekly._layout("nosuch", {})
    assert lay == weekly._layout("nosuch", {}) and lay["sidebar"] in ("left", "right")

    class T:
        def __init__(self, key, short):
            self.key, self.short = key, short
    teams = [T("ohio", "Ohio"), T("toledo", "Toledo")]
    bd = {"ohio": {"file": "ohio.jpg"}, "toledo": {"file": "toledo.jpg"}}
    assert weekly.photo({"edition": 0, "lead": {"headline": "Toledo wins"}}, teams, bd)["file"] == "toledo.jpg"
    assert weekly.photo({"edition": 1, "lead": {"headline": "x"}}, teams, bd)["file"] == "toledo.jpg"
    assert weekly.photo({"edition": 1}, [T("akron", "Akron")], bd) is None
