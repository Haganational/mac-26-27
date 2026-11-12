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
