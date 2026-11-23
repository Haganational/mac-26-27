import json

from mac import lockcall


def _script(**over):
    lines = ([{"part": "open", "who": "leslie", "text": "a" * 300}, {"part": "open", "who": "brett", "text": "b" * 300},
              {"part": "picks", "who": "merv", "text": "c" * 200}, {"part": "picks", "who": "edwin", "text": "d" * 200},
              {"part": "board", "who": "leslie", "text": "e" * 200},
              {"part": "close", "who": "brett", "text": "Call 1-800-GAMBLER. " + "f" * 200}])
    return {"lines": lines, "notes": {"news": {"item": "x", "sources": ["https://example.com"]}}, **over}


def test_good_script_passes():
    assert lockcall.check(_script()) == []


def test_needs_a_sourced_news_item():
    assert any("source" in p for p in lockcall.check(_script(notes={})))


def test_parts_must_run_in_order():
    s = _script()
    s["lines"].reverse()
    assert any("parts must run" in p for p in lockcall.check(s))


def test_pilot_script_is_ready():
    pilot = json.loads((lockcall.POD_DIR / "2026-11-22.json").read_text())
    assert lockcall.check(pilot) == []


def test_facts_come_from_the_cards():
    from mac import tops
    pick = {"label": "Under 140", "matchup": "A at B", "kind": "total", "why": "w"}
    for day, result in (("2026-11-21", "win"), ("2026-11-22", None)):
        card = {"date": day, "picks": {c["key"]: [dict(pick, result=result)] for c in tops.CAPPERS}}
        (tops.TOPS_DIR / f"{day}.json").write_text(json.dumps(card))
    f = lockcall.facts("2026-11-22")
    assert set(f["picks"]) == {c["key"] for c in tops.CAPPERS}
    assert all(r["record"] == "1-0" for r in f["board"])  # the board stops at yesterday
    assert f["yesterday"]["date"] == "2026-11-21"
    assert "error" in lockcall.facts("2026-11-23")
