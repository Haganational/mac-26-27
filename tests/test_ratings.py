from datetime import datetime, timedelta, timezone

from mac import ncaa, ratings as R
from mac.analysis import match_lines_to_games

T0 = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def raw(gid, day, home, away, hp, ap, neutral=False, poss=70):
    """A raw season-file game where each side used `poss` possessions (no turnovers or offensive boards)."""
    side = lambda tid, pts: {"id": tid, "name": tid, "pts": pts, "fga": poss, "fta": 0, "orb": 0, "to": 0}
    return {"id": gid, "date": (T0 + timedelta(days=day)).isoformat(), "neutral": neutral, "ot": 0,
            "home": side(home, hp), "away": side(away, ap)}


def round_robin(strength, days=12, poss=70):
    """Every pair plays home and away; points = 70 + strength gap / 2 each way, no noise."""
    games, gid = [], 0
    teams = list(strength)
    for d in range(days):
        for i, h in enumerate(teams):
            for a in teams[i + 1:]:
                hh, aa = (h, a) if d % 2 == 0 else (a, h)
                gap = strength[hh] - strength[aa]
                games.append(raw(str(gid), d, hh, aa, 70 + gap / 2, 70 - gap / 2, neutral=True, poss=poss))
                gid += 1
    return games


def test_fit_recovers_known_strengths():
    strength = {"a": 10.0, "b": 4.0, "c": 0.0, "d": -6.0}
    rows = R.game_rows(round_robin(strength), set(strength), 0.0)
    p = R.Params(prior_games=0.01, cap=1e6, half_life=1e6)
    r = R.fit(rows, T0 + timedelta(days=30), p)
    em = {t: r.teams[t]["o"] - r.teams[t]["d"] for t in strength}
    # 70 possessions, so a 10-point gap is ~14.3 per 100.
    assert abs((em["a"] - em["d"]) - 16 * 100 / 70) < 0.3
    assert em["a"] > em["b"] > em["c"] > em["d"]
    pr = R.project(r, "a", "d", neutral=True, p=p)
    assert abs(pr["margin"] - 16) < 0.3
    assert abs(pr["total"] - 140) < 0.5
    assert pr["spread"] == -pr["margin"]


def test_opponent_strength_matters():
    # x and y both win by 10 every time, but x does it against a strong team.
    games = round_robin({"s": 8.0, "m": 0.0, "w": -8.0}, days=10)
    gid = 1000
    for d in range(10):
        games.append(raw(str(gid), d, "x", "s", 80, 70, neutral=True)); gid += 1
        games.append(raw(str(gid), d, "y", "w", 80, 70, neutral=True)); gid += 1
    teams = {"s", "m", "w", "x", "y"}
    r = R.fit(R.game_rows(games, teams, 0.0), T0 + timedelta(days=30), R.Params(prior_games=0.01, cap=1e6))
    em = lambda t: r.teams[t]["o"] - r.teams[t]["d"]
    assert em("x") - em("y") > 15  # x's schedule was ~16 points harder


def test_recency_weighting_follows_form():
    # Team "f" was even early and is now 20 better; a short half-life should see more of the change.
    games = []
    for d in range(40):
        gap = 0 if d < 20 else 20
        games.append(raw(str(d), d, "f", "z", 70 + gap / 2, 70 - gap / 2, neutral=True))
    rows = R.game_rows(games, {"f", "z"}, 0.0)
    asof = T0 + timedelta(days=41)
    slow = R.fit(rows, asof, R.Params(prior_games=0.01, half_life=1e6, cap=1e6))
    fast = R.fit(rows, asof, R.Params(prior_games=0.01, half_life=7, cap=1e6))
    em = lambda r: r.teams["f"]["o"] - r.teams["f"]["d"]
    assert em(fast) > em(slow) + 3


def test_prior_fades_with_games():
    prior = R.Ratings(as_of="", mu=100, tau=70, hca=1.5,
                      teams={"p": {"o": 10, "d": -10, "t": 0, "games": 30}, "q": {"o": 0, "d": 0, "t": 0, "games": 30}})
    p = R.Params(prior_games=4, regress=0.0, half_life=1e6, cap=1e6)
    gap = lambda r: (r.teams["p"]["o"] - r.teams["p"]["d"]) - (r.teams["q"]["o"] - r.teams["q"]["d"])
    assert abs(gap(R.fit([], T0, p, prior)) - 20) < 0.5  # no games: all prior
    games = [raw(str(d), d, "p", "q", 70, 70, neutral=True) for d in range(30)]
    assert abs(gap(R.fit(R.game_rows(games, {"p", "q"}, 0.0), T0 + timedelta(days=31), p, prior))) < 4


def test_non_d1_opponents_pool():
    games = [raw("1", 0, "a", "tiny1", 90, 50), raw("2", 1, "a", "tiny2", 95, 55)]
    rows = R.game_rows(games, {"a"}, 0.0)
    assert {r["away"] for r in rows} == {R.NON_D1}


def test_possessions_formula_and_fallback():
    full = {"fga": 60, "fta": 20, "orb": 10, "to": 12}
    assert R.side_possessions(full, 1.5) == 60 - 10 + 12 + 0.475 * 20
    assert R.side_possessions({"fga": 60, "fta": 20}, 1.5) == 60 + 0.475 * 20 + 1.5


def test_enrichment_home_spread_sign():
    def summ(home_fav, away_fav, spread):
        return {"pickcenter": [{"provider": {"name": "DraftKings"}, "spread": spread, "overUnder": 150.5,
                                "homeTeamOdds": {"favorite": home_fav}, "awayTeamOdds": {"favorite": away_fav}}]}
    assert ncaa.parse_enrichment(summ(True, False, -4.5))["line"]["home_spread"] == -4.5
    assert ncaa.parse_enrichment(summ(False, True, -4.5))["line"]["home_spread"] == 4.5
    assert ncaa.parse_enrichment(summ(False, False, 0))["line"]["home_spread"] == 0.0


def test_line_matching_ignores_non_mac_sides():
    """A non-conference event must not match a different MAC team's game at the same tip."""
    def g(gid, home, away):
        return {"game_id": gid, "date": "2026-11-10T00:00Z", "home": {"key": home}, "away": {"key": away}}
    games = [g("1", "akron", None), g("2", "bowling-green", None)]
    history = {"ev": {"odds_event_id": "ev", "home_key": "bowling-green", "away_key": None,
                      "commence_time": "2026-11-10T00:00:00Z"}}
    assert match_lines_to_games(games, history) == {"2": "ev"}
