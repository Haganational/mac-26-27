from datetime import datetime
from zoneinfo import ZoneInfo

from mac import brick, social
from mac.leagues import Team

ET = ZoneInfo("America/New_York")
TEAMS = [Team("aa", "1", "AA", "Alpha Aardvarks", "Alpha"), Team("bb", "2", "BB", "Beta Bears", "Beta")]


def _game(gid, date, home, away, hs, as_, neutral=False):
    return {"game_id": gid, "date": date, "completed": True, "neutral_site": neutral,
            "home": {"espn_id": home, "name": f"T{home} Team", "score": hs},
            "away": {"espn_id": away, "name": f"T{away} Team", "score": as_}}


def _box(gid, rows, players=()):
    return {"game_id": gid, "teams": [{"espn_id": tid, "stats": {
        "fieldGoalsMade-fieldGoalsAttempted": fg, "threePointFieldGoalsMade-threePointFieldGoalsAttempted": tp,
        "freeThrowsMade-freeThrowsAttempted": ft}} for tid, fg, tp, ft in rows], "players": list(players)}


def test_week_and_window():
    assert brick.week_of(datetime(2026, 11, 13, 12, tzinfo=ET)) == "2026-11-16"
    assert brick.week_of(datetime(2026, 11, 16, 5, tzinfo=ET)) == "2026-11-16"  # before the freeze hour
    assert brick.week_of(datetime(2026, 11, 16, 7, tzinfo=ET)) == "2026-11-23"
    start, end = brick.window("2026-11-16")
    assert (start.day, end.day, end.hour) == (9, 16, 6)
    assert brick.span_label("2026-11-16") == "Nov. 9-15"
    assert brick.span_label("2026-12-07") == "Nov. 30 - Dec. 6"


def test_rule_min_attempts_power_skip_and_tiebreak():
    games = [_game("g1", "2026-11-10T00:00Z", "1", "99999", 50, 70),   # Alpha: 18-60, cold
             _game("g2", "2026-11-11T00:00Z", "2", "88888", 30, 80),   # Beta: only 35 FGA -> not eligible
             _game("g3", "2026-11-12T00:00Z", "7", "2", 90, 40),   # Beta at a power team -> skipped
             _game("g4", "2026-11-20T00:00Z", "1", "99999", 10, 90)]   # outside the week
    boxes = {"g1": _box("g1", [("1", "18-60", "4-25", "10-20")], [
                 {"team_espn_id": "1", "name": "Sharp Shooter", "fgm": 6, "fga": 9, "pts": 15},
                 {"team_espn_id": "1", "name": "Cold Hands", "fgm": 1, "fga": 12, "pts": 2}]),
             "g2": _box("g2", [("2", "10-35", "2-10", "8-10")]),
             "g3": _box("g3", [("2", "14-60", "2-20", "10-20")]),
             "g4": _box("g4", [("1", "3-50", "0-20", "4-10")])}
    a = brick.award("2026-11-16", boxes, games, TEAMS, skip_opp={"7"})
    assert a["winner"]["team"] == "Alpha" and a["candidates"] == 1
    assert a["line"] == "18-60 FG (30.0%), 4-25 3PT, 10-20 FT"
    text = " ".join(a["paragraphs"])
    assert "Sharp Shooter went 6 for 9" in text and "Cold Hands" not in text  # bright spot only, never the cold shooter
    # Same true shooting: more misses wins the tie.
    c = [{"ts": .4, "misses": 40, "date": "b", "game_id": "x"}, {"ts": .4, "misses": 45, "date": "c", "game_id": "y"}]
    assert brick.ranked(c)[0]["game_id"] == "y"


def test_write_up_is_stable_and_social_fits():
    games = [_game("g1", "2026-11-10T00:00Z", "1", "99999", 50, 70)]
    boxes = {"g1": _box("g1", [("1", "18-60", "4-25", "10-20")])}
    a = brick.award("2026-11-16", boxes, games, TEAMS, skip_opp=set())
    assert a == brick.award("2026-11-16", boxes, games, TEAMS, skip_opp=set())
    t = social.text_for({"text": brick.social_text(a, "Mountain West"), "title": "x", "league": "MW", "tag": "Mountain West"})
    assert len(t) <= 290 and t.endswith("#MountainWest #CollegeBasketball") and "Alpha went 18-60" in t


def test_freeze_once(tmp_path):
    games = [_game("g1", "2026-11-10T00:00Z", "1", "99999", 50, 70)]
    boxes = {"g1": _box("g1", [("1", "18-60", "4-25", "10-20")])}
    assert brick.freeze(boxes, games, TEAMS, datetime(2026, 11, 15, 12, tzinfo=ET), d=tmp_path) == []
    assert brick.freeze(boxes, games, TEAMS, datetime(2026, 11, 16, 7, tzinfo=ET), d=tmp_path) == ["2026-11-16"]
    assert brick.freeze(boxes, games, TEAMS, datetime(2026, 11, 16, 9, tzinfo=ET), d=tmp_path) == []
    assert brick.for_issue("2026-11-17", d=tmp_path)["winner"]["team"] == "Alpha"


def test_social_paces_brick_posts():
    now = datetime(2026, 11, 16, 8, tzinfo=ET)
    items = [{"kind": "brick", "url": f"u{i}", "published": "2026-11-16T07:00-05:00"} for i in range(6)]
    first = social.due_brick(items, {}, now)
    assert len(first) == 2
    posted = {it["key"]: "x" for it in first}
    assert len(social.due_brick(items, posted, now)) == 2 and social.due_brick(items, posted, now)[0]["url"] == "u2"
