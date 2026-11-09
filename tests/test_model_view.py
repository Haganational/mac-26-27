from mac import model_view as mv


def _u(spread=-5.0, total=150.0, se=None, te=None, non_d1=False):
    return {"game_id": "1", "home": {"abbr": "OHIO", "key": "ohio", "non_d1": non_d1}, "away": {"abbr": "KENT", "key": "kent-state", "non_d1": False},
            "model": {"spread": spread, "total": total, "home_pts": 77.5, "away_pts": 72.5, "poss": 69, "home_win": 0.68},
            "market": {"spread": -3.0, "total": 146.0}, "spread_edge": se, "total_edge": te}


def test_leans_and_colors():
    v = mv.view(_u(se={"abs": 2.0, "take": "OHIO -3.0", "abbr": "OHIO"}, te={"gap": 4.0, "abs": 4.0, "take": "Over 146"}))
    assert v["side"]["kind"] == "fav" and v["ou"]["kind"] == "over"
    assert v["ou"]["pct"] > v["side"]["pct"]  # bigger gap, deeper shade
    assert v["fav_line"] == "OHIO -5.0" and v["home_win"] == 68 and v["max_gap"] == 4.0
    dog = mv.view(_u(se={"abs": 1.0, "take": "KENT +3.0", "abbr": "KENT"}, te={"gap": -1.0, "abs": 1.0, "take": "Under 146"}))
    assert dog["side"]["kind"] == "dog" and dog["ou"]["kind"] == "under"
    assert mv.lean_pct(0) == 18 and mv.lean_pct(99) == 90


def test_non_d1_has_no_lean():
    v = mv.view(_u(se={"abs": 9.0, "take": "OHIO -3.0", "abbr": "OHIO"}, non_d1=True))
    assert v["side"] is None and v["ou"] is None


def test_players_to_watch_unique_regulars():
    prate = {
        "a": {"id": "a", "name": "A", "team_key": "ohio", "abbr": "OHIO", "net": 5, "off": 4, "def": 1, "min_pct": 80, "rk": 1, "off_rk": 1, "def_rk": 9},
        "b": {"id": "b", "name": "B", "team_key": "ohio", "abbr": "OHIO", "net": 3, "off": 3, "def": 0, "min_pct": 70, "rk": 2, "off_rk": 2, "def_rk": 10},
        "c": {"id": "c", "name": "C", "team_key": "kent-state", "abbr": "KENT", "net": 2, "off": -1, "def": 3, "min_pct": 60, "rk": 3, "off_rk": 5, "def_rk": 1},
        "d": {"id": "d", "name": "D", "team_key": "kent-state", "abbr": "KENT", "net": 9, "off": 9, "def": 9, "min_pct": 5, "rk": 0, "off_rk": 0, "def_rk": 0},
    }
    out = mv.players_to_watch(["ohio", "kent-state"], prate, 4)
    assert [p["id"] for p in out] == ["a", "b", "c"]  # cameo player d skipped, nobody twice
    assert out[2]["role"] == "Defensive anchor" and out[0]["href"] == "teams/ohio.html#pa"
