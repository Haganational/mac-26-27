from mac import pbp, player_ratings as P
from mac import ratings as R

WEIGHTS = {
    "net": {"const": -20.0, "tpm": 1.3, "twom": 0.4, "ftm": 0.45, "fgx": -1.0, "ftx": -0.6, "orb": 0.9,
            "drb": 1.0, "ast": 0.0, "stl": 0.8, "blk": 0.4, "to": -1.06, "pf": 0.0},
    "off": {"const": 25.0, "tpm": 1.5, "twom": 0.55, "ftm": 0.43, "fgx": -1.0, "ftx": -0.6, "orb": 0.95,
            "drb": -0.3, "ast": 0.0, "stl": -0.4, "blk": 0.05, "to": -1.06, "pf": 0.0},
    "assist_share": 1 / 3,
}


def player(pid, team, minutes, **stats):
    base = {k: 0 for k in ("pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "ast", "stl", "blk", "to", "pf")}
    base.update(stats)
    return {"espn_id": pid, "name": pid, "team_espn_id": team, "position": "G", "starter": True, "dnp": False, "min": minutes, **base}


def game(players):
    stint = {"secs": 2400, "home": [], "away": [], "pts_h": 0, "pts_a": 0, "poss": 70}
    return {"game_id": "g", "date": "2026-11-05T00:00Z", "teams": [], "players": players, "stints": [stint]}


def test_team_adjustment_matches_team_rating():
    toledo, akron = "2649", "2006"
    ps = [player(f"t{i}", toledo, 40, fgm=4, fga=9, tpm=1, pts=10, dreb=3, to=2) for i in range(5)]
    ps[0].update(fgm=9, fga=14, pts=22, tpm=3, ast=6)
    ps += [player(f"a{i}", akron, 40, fgm=3, fga=10, pts=7, to=3) for i in range(5)]
    team = R.Ratings(as_of="", mu=105, tau=68, hca=1.5,
                     teams={toledo: {"o": 4.0, "d": -2.0, "t": 0, "games": 1}, akron: {"o": -1.0, "d": 3.0, "t": 0, "games": 1}})
    rated = P.rate_players([game(ps)], team, weights=WEIGHTS)
    for tid, tr in ((toledo, team.teams[toledo]), (akron, team.teams[akron])):
        mine = [p for p in rated.values() if p["team"] == tid]
        mins = sum(p["min"] for p in mine)
        five_x = 5 * sum(p["net"] * p["min"] for p in mine) / mins
        assert abs(five_x - (tr["o"] - tr["d"])) < 1e-6
        off5 = 5 * sum(p["off"] * p["min"] for p in mine) / mins
        assert abs(off5 - tr["o"]) < 1e-6
    # The productive, passing scorer rates above his teammates.
    tol = sorted((p for p in rated.values() if p["team"] == toledo), key=lambda p: -p["net"])
    assert tol[0]["id"] == "t0"


def test_assist_split_is_zero_sum_for_the_team():
    t = {"poss": 100.0, "tpm": 2, "fgm": 8, "fga": 15, "ftm": 2, "fta": 3, "oreb": 1, "dreb": 4, "ast": 0, "stl": 1, "blk": 0, "to": 2, "pf": 2}
    passer = {**t, "fgm": 2, "fga": 5, "tpm": 0, "ast": 8}
    off_s, net_s = P.box_rating(t, WEIGHTS, team_ast_per_fgm=0.8)
    off_s0, net_s0 = P.box_rating({**t}, {**WEIGHTS, "assist_share": 0}, team_ast_per_fgm=0.8)
    assert net_s < net_s0  # scorer gives some value back
    _, net_p = P.box_rating(passer, WEIGHTS, team_ast_per_fgm=0.8)
    _, net_p0 = P.box_rating(passer, {**WEIGHTS, "assist_share": 0}, team_ast_per_fgm=0.8)
    assert net_p > net_p0  # passer gains


def test_absence_adjustment_sign():
    players = [{"id": "x", "name": "Star", "team_key": "toledo", "net": 6.0, "min_pct": 80.0}]
    adj = P.team_adjustment(players, "toledo", {"x"})
    assert adj["delta_net"] < 0 and abs(adj["delta_net"] - 0.8 * (-2.0 - 6.0)) < 1e-9


def _play(kind, text, team, pid, period=1, clock="19:00", hs=0, as_=0, shooting=False):
    return {"type": {"text": kind}, "text": text, "team": {"id": team}, "participants": [{"athlete": {"id": pid}}] if pid else [],
            "period": {"number": period}, "clock": {"displayValue": clock}, "homeScore": hs, "awayScore": as_, "shootingPlay": shooting}


def test_stints_follow_substitutions_and_repair_missing_ones():
    def box_team(tid, side):
        return {"team": {"id": tid, "abbreviation": tid, "displayName": tid}, "homeAway": side, "statistics": []}

    def box_players(tid, ids, starters):
        return {"team": {"id": tid}, "statistics": [{"names": ["MIN"], "athletes": [
            {"athlete": {"id": i, "displayName": i}, "starter": i in starters, "stats": ["20"]} for i in ids]}]}

    H, A = "h", "a"
    hs = [f"h{i}" for i in range(7)]
    as_ = [f"a{i}" for i in range(6)]
    summary = {
        "boxscore": {"teams": [box_team(H, "home"), box_team(A, "away")],
                     "players": [box_players(H, hs, hs[:5]), box_players(A, as_, as_[:5])]},
        "plays": [
            _play("JumpShot", "h0 makes jumper", H, "h0", clock="19:00", hs=2, shooting=True),
            _play("Substitution", "h0 subbing out for H", H, "h0", clock="15:00", hs=2),
            _play("Substitution", "h5 subbing in for H", H, "h5", clock="15:00", hs=2),
            _play("JumpShot", "a0 makes three", A, "a0", clock="14:00", hs=2, as_=3, shooting=True),
            # a5 never subbed in, but scores: repair puts him on, idle a4 comes off
            _play("LayUpShot", "a5 makes layup", A, "a5", clock="10:00", hs=2, as_=5, shooting=True),
        ],
    }
    st = pbp.build_stints(summary)["stints"]
    assert st[0]["home"] == sorted(hs[:5]) and st[0]["pts_h"] == 2
    assert "h5" in st[1]["home"] and "h0" not in st[1]["home"]
    assert all(len(s["home"]) == 5 and len(s["away"]) == 5 for s in st)
    assert "a5" in st[-1]["away"]
    assert sum(s["pts_a"] for s in st) == 5
