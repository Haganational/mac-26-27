from pathlib import Path

import pytest

from mac import cards
from mac.config import BY_KEY

PIL = pytest.importorskip("PIL")


def ctx():
    pl = lambda n, pts, reb=0, ast=0: {"name": n, "pts": pts, "reb": reb, "ast": ast}
    return {"g": {"date": "2026-11-07T00:00Z", "venue": "Worthen Arena"},
            "home": {"name": "Ball State Cardinals", "key": "ball-state", "abbr": "BALL", "score": 66,
                     "players": [pl("Sean Blake", 20, 6), pl("A", 9)]},
            "away": {"name": "Indiana State Sycamores", "key": None, "abbr": "INST", "score": 69,
                     "players": [pl("B", 18, 10), {"name": "C", "dnp": True, "pts": None}]}}


def test_recap_card_facts():
    c = cards.recap("MAC", ctx(), {"headline": "Indiana State edged Ball State 69-66"}, {"ball-state": "#BA0C2F"})
    assert c["kicker"] == "FINAL · MAC" and c["date"] == "Fri, Nov 6"  # Eastern, not UTC
    assert [r["right"] for r in c["rows"]] == [69, 66] and c["rows"][1]["dim"] and not c["rows"][0]["dim"]
    assert c["rows"][1]["color"] == "#BA0C2F" and c["rows"][0]["color"] is None
    assert c["stat"] == "Sean Blake, 20 points, 6 rebounds (Ball State Cardinals)"


def test_capsule_card_and_first_sentence():
    t = {"key": "akron", "short": "Akron", "rank": 2, "prev_rank": 5, "score": 9.04, "form": 7.0, "road": 2.0,
         "record": "3-1", "conf_record": "0-0"}
    c = cards.capsule("MAC", "2026-11-16", t, "<p>The Zips went to Ann Arbor and won. Then more.</p>", BY_KEY["akron"])
    assert c["headline"] == "The Zips went to Ann Arbor and won."
    assert c["rows"][0]["pre"] == "2" and c["rows"][0]["right"] == "+9.0" and "Up 3" in c["rows"][0]["sub"]
    assert c["date"] == "Week of 11/16"


@pytest.mark.parametrize("rows", [1, 2, 5])
def test_both_sizes_render(tmp_path, rows):
    card = {"kicker": "FINAL · MAC", "date": "Fri, Nov 6", "headline": "A very long headline " * 6,
            "label": "Top scorer", "stat": "Someone, 30 points " * 5,
            "rows": [{"abbr": "AKR", "name": "Akron", "color": "#041E42", "right": 80, "pre": str(i + 1)} for i in range(rows)]}
    cards.render(tmp_path, "x", card)
    from PIL import Image
    assert Image.open(tmp_path / "x.png").size == (1200, 630)
    assert Image.open(tmp_path / "ig" / "x.png").size == (1080, 1350)
