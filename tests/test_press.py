import json
import re

from mac import anchors, press
from mac.leagues import ALL

LEAN = {"homer": 2, "lean": "Roots out loud.", "pet": "free throws", "rival": "kent-state",
        "asides": {s: [f"{s}: {{us}} vs {{them}} in {{town}} by {{margin}}"] for s in press.SITUATIONS}}


def _fake(monkeypatch, leans, papers, settings=None):
    monkeypatch.setattr(press, "_leans_file", lambda: {"settings": settings or {"aside_rate": 1, "rejoinder_rate": 1}, "leans": leans})
    monkeypatch.setattr(press, "papers", lambda: papers)


def test_situations():
    assert press.game_situation(True, True, False, False) == "win"
    assert press.game_situation(False, False, False, False) == "road_loss"
    assert press.game_situation(True, False, True, True) == "rival_win"  # the rivalry beats the upset
    assert press.game_situation(True, False, False, True) == "upset"


def test_game_asides_lead_then_rejoinder(monkeypatch):
    _fake(monkeypatch, {"akron": LEAN, "kent-state": {**LEAN, "rival": "akron"}},
          {"akron": {"title": "The Akron Test", "town": "Akron"}})
    out = press.game_asides("akron", "kent-state", True, 3.5, {"home": "Akron", "away": "Kent State"},
                            {"akron": "Akron", "kent-state": "Kent"}, 6, "401")
    assert [a["key"] for a in out] == ["akron", "kent-state"]
    assert out[0]["text"] == "rival_win: Akron vs Kent State in Akron by 6"
    assert out[1]["text"].startswith("rival_loss: Kent State vs Akron")
    assert press.byline("akron") == f"{anchors.roster()['akron']['name']}, The Akron Test"


def test_rate_zero_means_no_asides(monkeypatch):
    _fake(monkeypatch, {"akron": LEAN}, {}, {"aside_rate": 0, "rejoinder_rate": 0})
    assert press.game_asides("akron", "toledo", True, None, {}, {}, 1, "x") == []


def test_bad_placeholder_is_dropped(monkeypatch):
    _fake(monkeypatch, {"akron": {**LEAN, "asides": {"win": ["{coach} again"]}}}, {})
    assert press.aside("akron", "win", "s", {"us": "Akron"}) is None


def test_shipped_files_are_clean():
    keys = {t.key for lg in ALL.values() for t in lg.teams}
    if press.PAPERS.exists():
        ps = json.loads(press.PAPERS.read_text())["papers"]
        assert set(ps) <= keys
        titles = [p["title"] for p in ps.values()]
        assert len(titles) == len(set(titles)), "two schools share a paper"
        for p in ps.values():
            assert p["title"] and p["town"]
            assert p["title"] not in [e["name"] for e in p.get("existing", [])]
    if press.LEANS.exists():
        ls = json.loads(press.LEANS.read_text())["leans"]
        assert set(ls) <= keys
        ok = re.compile(r"\{(\w+)\}")
        for k, ln in ls.items():
            assert ln.get("rival") in keys, k
            for sit, lines in ln["asides"].items():
                assert sit in press.SITUATIONS, (k, sit)
                for s in lines:
                    assert set(ok.findall(s)) <= set(press.PLACEHOLDERS), (k, s)
                    assert s.count("{") == s.count("}") == len(ok.findall(s)), (k, s)
                    assert "—" not in s, (k, s)
