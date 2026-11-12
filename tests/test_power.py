from datetime import datetime, timezone

from mac import power
from mac import ratings as R


def row(i, day, home, away, ph, pa, neutral=False):
    return {"id": str(i), "date": datetime(2026, 11, day, 23, tzinfo=timezone.utc), "home": home, "away": away,
            "neutral": neutral, "eff_h": ph * 100 / 70, "eff_a": pa * 100 / 70, "poss": 70.0, "poss40": 70.0,
            "pts_h": ph, "pts_a": pa, "home_name": home.upper(), "away_name": away.upper()}


def test_week_turns_over_monday_6am_et():
    assert power.week_of(datetime(2026, 11, 16, 10, 59, tzinfo=timezone.utc)) == "2026-11-09"  # 5:59 ET
    assert power.week_of(datetime(2026, 11, 16, 11, 0, tzinfo=timezone.utc)) == "2026-11-16"
    assert power.week_of(datetime(2026, 11, 22, 23, 0, tzinfo=timezone.utc)) == "2026-11-16"


def test_road_win_beats_same_home_win():
    # a and b each beat c by 10 once; a did it on the road, b at home.
    rows = [row(1, 10, "c", "a", 60, 70), row(2, 10, "b", "c", 70, 60),
            row(3, 5, "c", "d", 65, 65 - 1), row(4, 6, "d", "c", 65, 64)]
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    season = R.fit(rows, now)
    idx = power.index(rows, season, None, now, [("a", "a", "A"), ("b", "b", "B")])
    by = {t["key"]: t for t in idx}
    assert by["a"]["road"] > 0 and by["b"]["road"] == 0
    assert by["a"]["road_wins"][0]["site"] == "road"
    assert idx[0]["rank"] == 1 and idx[0]["score"] >= idx[1]["score"]


def test_quality_bounds():
    assert power.quality(-100) == power.Q_MIN and power.quality(100) == power.Q_MAX and power.quality(0) == 1


def test_freeze_once_and_not_before_launch(tmp_path):
    idx = [{"key": "akron", "short": "Akron", "rank": 1, "score": 5.0, "form": 4.0, "road": 1.0, "road_wins": [], "scale": 0.7}]
    early = datetime(2026, 11, 12, tzinfo=timezone.utc)
    power.freeze(idx, [], {}, {}, early, tmp_path)
    assert power.weeks(tmp_path) == []
    mon = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
    assert power.freeze(idx, [], {"akron": {"w": 2, "l": 0, "cw": 0, "cl": 0, "streak": "W2"}}, {}, mon, tmp_path) == "2026-11-16"
    snap = power.load("2026-11-16", tmp_path)
    assert snap["teams"][0]["record"] == "2-0" and snap["teams"][0]["prev_rank"] is None
    idx[0]["score"] = 99
    power.freeze(idx, [], {}, {}, mon, tmp_path)
    assert power.load("2026-11-16", tmp_path)["teams"][0]["score"] == 5.0
    (tmp_path / "capsules-2026-11-16.json").write_text('{"_note": "x", "akron": "Words."}')
    assert power.capsules("2026-11-16", tmp_path) == {"akron": "Words."}
