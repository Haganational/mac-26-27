from mac import lockcall
from mac import midboard as M

BASE = {"median_em": 0.0, "sd_em": 10.0, "avg_total": 150.0, "teams": 365}


def test_dead_center_is_zero():
    assert M.distance(0.0, 0.0, 0.0, 150.0, BASE)["d"] == 0


def test_spread_and_total_push_off_center():
    near = M.distance(1.0, -1.0, -1.5, 148.0, BASE)["d"]
    far = M.distance(1.0, -1.0, -12.5, 165.0, BASE)["d"]
    assert near < far


def test_board_ranks_the_mid_game_first():
    teams = [{"id": i, "adj_em": em, "adj_o": 107 + em / 2, "adj_d": 107 - em / 2, "adj_t": 69.0, "rk_adj_em": rk}
             for i, em, rk in (("a", 0.5, 180), ("b", -0.5, 185), ("c", 30.0, 2), ("d", -20.0, 350))]
    r = {"teams": teams, "mu": 107.0, "tau": 69.0, "hca": 2.7}

    def game(gid, h, a, spread, total):
        side = lambda t: {"id": t, "name": t.upper(), "conf": "14", "pts": None}
        return {"id": gid, "tip": "2026-11-28T00:00Z", "neutral": False, "home": side(h), "away": side(a),
                "line": {"home_spread": spread, "total": total}}
    rows = M.board([game("1", "c", "d", -45.5, 150.0), game("2", "a", "b", -1.5, 150.5)], r, BASE)
    assert [x["game_id"] for x in rows] == ["2", "1"]
    assert rows[0]["mid_rank"] == 1


def test_line_sign_follows_the_favorite():
    away_fav = [{"spread": 3.5, "overUnder": 141.5, "homeTeamOdds": {"favorite": False}, "awayTeamOdds": {"favorite": True}}]
    home_fav = [{"spread": -3.5, "overUnder": 141.5, "homeTeamOdds": {"favorite": True}, "awayTeamOdds": {"favorite": False}}]
    assert M._line_from_odds(away_fav)["home_spread"] == 3.5
    assert M._line_from_odds(home_fav)["home_spread"] == -3.5
    assert M._line_from_odds([]) is None


def _final(h_pts, a_pts, spread, h_conf="14", a_conf="14"):
    return {"id": "g", "final": True, "neutral": False, "line": {"home_spread": spread, "total": 140.0},
            "home": {"id": "h", "name": "Home", "conf": h_conf, "pts": h_pts},
            "away": {"id": "a", "name": "Away", "conf": a_conf, "pts": a_pts}}


def test_big_upset_and_mid_over_power():
    big = M.upsets([_final(60, 70, -9.5)])  # the away team was a 9.5-point dog and won
    assert big and big[0]["kinds"] == ["big upset"] and big[0]["dog_by"] == 9.5
    mop = M.upsets([_final(70, 72, -2.5, h_conf="23", a_conf="14")])  # MAC team wins at an SEC team
    assert mop and mop[0]["kinds"] == ["mid over power"] and mop[0]["power_loser"] == "SEC"
    assert M.upsets([_final(80, 60, -9.5)]) == []  # the favorite won: nothing to see


def _lines(parts, n=200):
    out = [{"part": "hook", "who": "leslie", "text": "Best line first!"}]
    for p in parts:
        out += [{"part": p, "who": "leslie", "text": "a" * n}, {"part": p, "who": "brett", "text": "b" * n}]
    out[-1]["text"] += " Call 1-800-GAMBLER."
    return out


NEWS = {"news": {"item": "x", "sources": ["https://example.com"]}}


def test_big_mid_is_required_from_nov_28():
    s = {"date": "2026-11-28", "lines": _lines(["open", "picks", "board", "close"], 260), "notes": NEWS}
    assert any("bigmid" in p for p in lockcall.check(s))
    s["lines"] = _lines(["open", "picks", "bigmid", "board", "close"], 220)
    assert lockcall.check(s) == []


def test_big_mid_can_sit_out_a_day():
    s = {"date": "2026-11-29", "lines": _lines(["open", "picks", "board", "close"], 200), "notes": {**NEWS, "bigmid": "none"}}
    assert lockcall.check(s) == []
