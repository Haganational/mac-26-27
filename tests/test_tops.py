import json
from datetime import datetime, timezone

from mac import tops

DAY = "2026-11-19"
LOCK = datetime(2026, 11, 19, 13, 15, tzinfo=timezone.utc)  # 8:15 AM Eastern


def _team(i, ppg=None, papg=None, g=5):
    return {"id": str(i), "key": None, "name": f"Team {i}", "abbr": f"T{i}", "g": g, "ppg": ppg, "papg": papg}


def _b(gid, spread, model_spread, total, model_total, home, away, neutral=False):
    return {"id": gid, "tip": "2026-11-20T00:00Z", "neutral": neutral, "home": home, "away": away, "spread": spread,
            "total": total, "model_spread": model_spread, "model_total": model_total, "captured_at": None,
            "sides_ok": True, "totals_ok": True}


def _board():
    return [
        _b("1", -5.0, -12.0, 140.0, 131.0, _team(1, 80, 60), _team(2, 70, 75)),   # model 7 on home; 9 under
        _b("2", 4.5, 4.0, 150.0, 158.0, _team(3, 90, 62), _team(4, 85, 70)),      # home dog +4.5; 8 over
        _b("3", -2.0, 3.0, 145.0, 146.0, _team(5, 75, 61), _team(6, 95, 80)),     # model 5 on away
        _b("4", 12.0, 11.0, 135.0, 133.0, _team(7, 66, 58), _team(8, 72, 64)),    # home dog +12: outside the window
    ]


def test_brett_takes_the_two_biggest_spread_gaps_on_the_models_side():
    ps = tops.brett(_board(), DAY)
    assert [(p["game"], p["side"], p["line"]) for p in ps] == [("1", "home", -5.0), ("3", "away", 2.0)]
    assert ps[1]["label"] == "Team 6 +2"


def test_merv_takes_the_best_under_and_the_third_stingiest_defense():
    ps = tops.merv(_board(), DAY)
    assert ps[0]["kind"] == "total" and ps[0]["side"] == "under" and ps[0]["game"] == "1"
    # points allowed: 58 (T7), 60 (T1), 61 (T5) -> third is Team 5, home in game 3
    assert ps[1]["team"] == "Team 5" and ps[1]["line"] == -2.0


def test_leslie_takes_the_best_over_and_the_second_highest_scorer():
    ps = tops.leslie(_board(), DAY)
    assert ps[0]["side"] == "over" and ps[0]["game"] == "2"
    # scoring: 95 (T6), 90 (T3) -> Team 3, home +4.5
    assert ps[1]["team"] == "Team 3" and ps[1]["line"] == 4.5


def test_shark_only_takes_a_home_dog_from_3_to_10_and_that_games_total():
    ps = tops.shark(_board(), DAY)
    assert ps[0]["game"] == "2" and ps[0]["side"] == "home" and ps[0]["line"] == 4.5
    assert ps[1]["kind"] == "total" and ps[1]["game"] == "2" and ps[1]["side"] in ("over", "under")
    assert any(i in ps[1]["why"] for i in tops.INSIDE)
    assert tops.shark(_board(), DAY) == ps, "same morning, same pick"
    neutral = [dict(b, neutral=True) for b in _board()]
    assert tops.shark(neutral, DAY) == [], "a neutral floor has no home dog"


def test_min_games_keeps_one_game_teams_off_the_points_rankings():
    bd = _board()
    bd[3]["home"]["g"] = 1  # Team 7, the stingiest, has one game: drops out
    ps = tops.merv(bd, DAY)
    assert ps[1]["team"] == "Team 3"  # 60 (T1), 61 (T5), 62 (T3)


def test_grading_sides_totals_pushes_and_voids():
    side = {"kind": "side", "side": "away", "line": 2.0}
    assert tops.grade_pick(side, {"status": "final", "home": 70, "away": 69}) == "win"
    assert tops.grade_pick(side, {"status": "final", "home": 72, "away": 70}) == "push"
    assert tops.grade_pick(side, {"status": "final", "home": 80, "away": 70}) == "loss"
    under = {"kind": "total", "side": "under", "line": 140.5}
    assert tops.grade_pick(under, {"status": "final", "home": 70, "away": 70}) == "win"
    assert tops.grade_pick(under, {"status": "off"}) == "void"
    assert tops.grade_pick(under, None) is None
    t = tops.tally([{"result": "win"}, {"result": "loss"}, {"result": "push"}, {"result": None}])
    assert t["record"] == "1-1-1" and t["units"] == -0.09 and t["pending"] == 1


def _write_day(d, schedule_games, proj_rows):
    d.mkdir(parents=True, exist_ok=True)
    (d / "schedule.json").write_text(json.dumps({"games": schedule_games}))
    (d / "model").mkdir(exist_ok=True)
    (d / "model" / "projections.jsonl").write_text("".join(json.dumps(r) + "\n" for r in proj_rows))


def _sg(gid, home, away, tip="2026-11-20T00:00Z", **kw):
    return {"game_id": gid, "date": tip, "neutral_site": False, "status": "STATUS_SCHEDULED", "completed": False,
            "home": {"espn_id": home, "key": None, "name": f"Team {home}", "abbr": f"T{home}"},
            "away": {"espn_id": away, "key": None, "name": f"Team {away}", "abbr": f"T{away}"}, **kw}


def _pr(gid, spread, model_spread, total, model_total, at="2026-11-19T13:00:00+00:00", tip="2026-11-20T00:00Z"):
    return {"generated_at": at, "game_id": gid, "tip": tip, "non_d1": False, "model_spread": model_spread, "model_total": model_total,
            "mkt_spread": spread, "mkt_total": total, "mkt_captured_at": "2026-11-19T12:30:00+00:00"}


def test_board_reads_the_newest_pregame_row_and_skips_unlined_or_tipped_games(tmp_path):
    d = tmp_path / "lg"
    _write_day(d, [_sg("1", "1", "2"), _sg("2", "3", "4"), _sg("3", "5", "6", tip="2026-11-19T12:00Z"), _sg("4", "7", "8", tip="2026-11-21T00:00Z")],
               [_pr("1", -3.0, -4.0, 140, 139, at="2026-11-19T10:00:00+00:00"), _pr("1", -5.0, -6.0, 141, 138),
                _pr("1", -9.0, -9.0, 150, 150, at="2026-11-19T14:00:00+00:00"),  # logged after the lock: ignored
                _pr("2", None, -2.0, None, 140), _pr("3", -1.0, -1.0, 140, 140, tip="2026-11-19T12:00Z")])
    bd = tops.board(DAY, LOCK, [d], scoring={})
    assert [b["id"] for b in bd] == ["1"] and bd[0]["spread"] == -5.0 and bd[0]["model_spread"] == -6.0


def test_neutral_site_with_disagreeing_favorites_gets_no_side(tmp_path):
    d = tmp_path / "lg"
    _write_day(d, [_sg("1", "1", "2", neutral_site=True)], [_pr("1", 6.0, -6.0, 140, 139)])
    bd = tops.board(DAY, LOCK, [d], scoring={})
    assert bd[0]["sides_ok"] is False and tops.brett(bd, DAY) == []


def test_lock_once_at_815_then_grade_and_rank(tmp_path):
    d, out = tmp_path / "lg", tmp_path / "tops"
    _write_day(d, [_sg("1", "1", "2"), _sg("2", "3", "4")], [_pr("1", -5.0, -12.0, 140, 131), _pr("2", 4.5, 4.0, 150, 158)])
    early = datetime(2026, 11, 19, 13, 0, tzinfo=timezone.utc)
    assert tops.lock(early, out, [d], scoring={}) is None, "nothing before 8:15"
    card = tops.lock(LOCK, out, [d], scoring={})
    assert card and card["board"] == 2 and card["picks"]["brett"][0]["game"] == "1"
    assert card["picks"]["shark"][0]["label"] == "Team 3 +4.5"
    assert card["column"]["byline"] in tops.BY_KEY and card["column"]["lines"]
    assert tops.lock(LOCK, out, [d], scoring={}) is None, "a locked card is never re-picked"
    scores = {"1": {"status": "final", "home": 80.0, "away": 60.0}, "2": {"status": "final", "home": 70.0, "away": 72.0}}
    assert tops.grade_all(out, scores) == 1
    graded = json.loads((out / f"{DAY}.json").read_text())
    assert graded["picks"]["brett"][0]["result"] == "win" and graded["picks"]["brett"][0]["final"] == "60-80"
    assert graded["picks"]["shark"][0]["result"] == "win"  # home +4.5, lost by 2
    table = tops.standings(tops.load_cards(out))
    assert [r["rank"] for r in table] == [1, 2, 3, 4] and table[0]["units"] >= table[-1]["units"]
    nxt = tops.column("2026-11-20", {}, graded, table)
    assert nxt["head"].startswith("Tops: ") and "Bottoms: " in nxt["head"]


def test_page_renders_with_a_card_and_without(tmp_path):
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from mac.config import TEMPLATES_DIR
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    kw = dict(eds=[], names="", base="https://x.com/", season="2026-27", noindex=True, today_label="Thursday", built="now", n_conf=27)
    html = env.get_template("tops.html").render(**kw, **tops.page_context(LOCK, tmp_path))
    assert "Tops and Bottoms" in html and "The first card" in html and "1-800-GAMBLER" in html
    d = tmp_path / "lg"
    _write_day(d, [_sg("1", "1", "2"), _sg("2", "3", "4")], [_pr("1", -5.0, -12.0, 140, 131), _pr("2", 4.5, 4.0, 150, 158)])
    tops.lock(LOCK, tmp_path, [d], scoring={})
    html = env.get_template("tops.html").render(**kw, **tops.page_context(LOCK, tmp_path))
    assert "Today's card" in html and "Team 3 +4.5" in html and "fictional AI" in html
    assert tops.teaser(LOCK, tmp_path)["text"]


def test_inside_information_names_no_real_people():
    # House rule: the Shark's sources are invented. Keep real names out of the bank.
    for line in tops.INSIDE:
        assert "Trump" not in line and "Bellini" not in line
