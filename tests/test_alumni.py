"""Off the Court: alumni stories rotate by day, ride with the school's anchor, and are cut before any game."""
import json

import pytest

from mac import alumni, anchors, gamer, midmaxx60

STORY = {"name": "Ada Example", "years": "class of 1970", "known_for": "first woman to do a thing", "lean": "cheer",
         "fact": "Ada Example was the first woman to do a thing.", "evidence": "She was the first woman to do a thing.",
         "source": "https://en.wikipedia.org/wiki/Ada_Example", "line": "Ada Example went first. Akron remembers."}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    p = tmp_path / "alumni.json"
    p.write_text(json.dumps({"alumni": {"akron": [STORY, {**STORY, "name": "Bo Sample", "line": "Bo Sample, class act."}],
                                        "toledo": [{**STORY, "source": ""}]}}))
    monkeypatch.setattr(alumni, "PATH", p)
    alumni.load.cache_clear()
    yield
    alumni.load.cache_clear()


def test_stories_need_a_line_a_fact_and_a_source(desk):
    assert len(alumni.stories("akron")) == 2
    assert alumni.stories("toledo") == [] and alumni.pick("toledo", "2026-11-14") is None


def test_stories_come_round_in_turn(desk):
    a, b = alumni.pick("akron", "2026-11-14"), alumni.pick("akron", "2026-11-15")
    assert a["name"] != b["name"] and alumni.pick("akron", "2026-11-16") == a


def test_segment_is_read_by_the_schools_anchor(desk):
    sg = alumni.segment("akron", "2026-11-14", "Akron", "#041e42")
    assert sg["kind"] == "offcourt" and sg["text"].startswith("Off the court. ")
    assert sg["card"]["source"] == "Wikipedia" and anchors.team_of(sg) == "akron"


def test_choose_skips_schools_without_stories(desk):
    assert alumni.choose(["toledo", "akron", None, "akron"], "2026-11-14") == ["akron"]


def test_the_story_goes_before_any_game_when_the_short_runs_long():
    assert midmaxx60.DROP_FIRST[0] == "offcourt"


def test_game_stories_get_the_plain_fact_with_its_source(desk):
    line = alumni.flavor_lines("akron", "Akron")[0]
    assert line["kind"] == "alumni" and line["source"].startswith("https://") and "first woman" in line["text"]
    assert any(isinstance(x, dict) and x.get("kind") == "alumni" for x in gamer.load_flavor()["teams"]["akron"]["lines"])


def test_every_shipped_story_is_sourced_and_short():
    alumni.load.cache_clear()
    for key, rows in alumni.load().items():
        assert key in anchors.roster(), key
        for s in rows:
            assert s["source"].startswith("https://") and s["evidence"] and s["fact"], (key, s["name"])
            assert s["lean"] in ("cheer", "scorn", "neutral") and len(s["line"].split()) <= 50, (key, s["name"])
