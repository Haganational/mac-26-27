from datetime import datetime, timedelta, timezone

from mac import ratings as R
from mac import three_models as T


def _row(i, day, h, a, ph, pa):
    return {"id": str(i), "date": datetime(2026, 11, day, 23, tzinfo=timezone.utc), "home": h, "away": a, "neutral": False,
            "eff_h": 100 * ph / 70, "eff_a": 100 * pa / 70, "poss": 70.0, "poss40": 70.0, "pts_h": ph, "pts_a": pa}


def test_rank_weights_newest_heaviest():
    rows = [_row(i, 3 + i, "x", "y" if i % 2 else "z", 70, 60) for i in range(6)]
    w = R._rank_weights(rows, (12.0, 9.0, 7.0, 5.0))
    # x's newest game (id 5) is x's #1 and y's #1: weight 12; id 0 is x's 6th game (1.0) and z's 3rd (7.0).
    assert w["5"] == 12.0
    assert w["0"] == (1.0 + 7.0) / 2


def test_long_game_is_flat_and_right_now_moves_with_form():
    rows = [_row(i, 1 + i, "a", "b", 60, 80) for i in range(8)] + [_row(10 + i, 12 + i, "a", "b", 85, 60) for i in range(4)]
    as_of = datetime(2026, 11, 20, tzinfo=timezone.utc)
    long_ = R.fit(rows, as_of, T.PARAMS["long"])
    now = R.fit(rows, as_of, T.PARAMS["now"])
    em = lambda r: r.teams["a"]["o"] - r.teams["a"]["d"]  # noqa: E731
    assert em(now) > em(long_)  # a's hot last four games count for more in Right Now


def test_score_grades_and_units():
    g = {"id": "1", "d": "2026-11-20", "h": "a", "a": "b", "ph": 80, "pa": 70, "sp": -5.0, "tot": 140.0,
         "m": {"ours": [-8.0, 145.0], "long": [-2.0, 135.0], "now": [-5.0, 150.0]}}
    s = T.score([g])
    assert s["models"]["ours"]["ats"]["w"] == 1  # liked home at -5, home won by 10
    assert s["models"]["long"]["ats"]["l"] == 1
    assert s["models"]["now"]["ats"]["w"] + s["models"]["now"]["ats"]["l"] == 0  # no lean on the number
    assert s["models"]["ours"]["ou"]["w"] == 1 and s["models"]["long"]["ou"]["l"] == 1
    assert s["models"]["long"]["ats"]["units"] == -1.1


def test_pack_roundtrip():
    g = {"id": "1", "d": "2026-11-20", "h": "a", "a": "b", "ph": 80, "pa": 70, "sp": -5.0, "tot": None,
         "m": {"ours": [-8.0, 145.0], "long": [-2.0, 135.0], "now": [-5.0, 150.0]}}
    assert T._unpack(T._pack(g)) == g


def test_units_chart_shapes():
    gs = [{"id": str(i), "d": (datetime(2026, 11, 5) + timedelta(days=i)).date().isoformat(), "h": "a", "a": "b", "ph": 80, "pa": 70,
           "sp": -5.0, "tot": 140.0, "m": {"ours": [-8.0, 145.0], "long": [-2.0, 135.0], "now": [-6.0, 150.0]}} for i in range(5)]
    ch = T.units_chart(gs, "ats")
    assert len(ch["lines"]) == 3 and len(ch["points"]) == 5
    assert ch["points"][-1]["v"]["ours"] == 5.0 and ch["points"][-1]["v"]["long"] == -5.5
