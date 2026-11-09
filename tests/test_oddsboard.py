import json
from datetime import datetime, timezone

from mac import oddsboard

HOME, AWAY = "Toledo Rockets", "Akron Zips"
T1, T2 = "2026-12-04T12:00:00+00:00", "2026-12-05T12:00:00+00:00"


def quote(t, book, spread=None, sp_price=(-110, -110), total=None, tot_price=(-110, -110), ml=None):
    """Rows for one book at one capture. spread is the home number."""
    base = {"captured_at": t, "odds_event_id": "ev1", "commence_time": "2026-12-05T19:00:00Z",
            "home_team": HOME, "away_team": AWAY, "home_key": "toledo", "away_key": "akron",
            "book": book, "book_last_update": t}
    out = []
    if spread is not None:
        out.append({**base, "market": "spreads", "outcome": HOME, "point": spread, "price": sp_price[0]})
        out.append({**base, "market": "spreads", "outcome": AWAY, "point": -spread, "price": sp_price[1]})
    if total is not None:
        out.append({**base, "market": "totals", "outcome": "Over", "point": total, "price": tot_price[0]})
        out.append({**base, "market": "totals", "outcome": "Under", "point": total, "price": tot_price[1]})
    if ml:
        out.append({**base, "market": "h2h", "outcome": HOME, "point": None, "price": ml[0]})
        out.append({**base, "market": "h2h", "outcome": AWAY, "point": None, "price": ml[1]})
    return out


def board_rows():
    return (
        quote(T1, "draftkings", -3.5, total=145.5, ml=(-170, 145))
        + quote(T2, "draftkings", -4.5, total=146.5, ml=(-190, 160))
        + quote(T2, "fanduel", -4.5, (-105, -115), 147.0, ml=(-180, 155))
        + quote(T2, "betmgm", -6.0, total=146.5, tot_price=(-105, -115))
        + quote(T2, "bovada", -4.0, total=146.0)
        + quote(T1, "lowvig", -3.5, total=145.5)  # pulled before T2
    )


def test_price_math():
    assert round(oddsboard.hold(-110, -110), 4) == 0.0476
    assert oddsboard.prob_to_american(0.6) == -150
    assert oddsboard.prob_to_american(0.4) == 150
    assert round(oddsboard.decimal_odds(150), 2) == 2.5


def test_best_prices_pick_points_then_price():
    ev = oddsboard.build_event(board_rows())
    best = ev["best"]
    # Away side: most points wins (+6 at BetMGM).
    assert best["away_spread"]["point"] == 6.0 and best["away_spread"]["books"] == ["betmgm"]
    # Home side: -4.0 beats -4.5 and -6.
    assert best["home_spread"]["books"] == ["bovada"]
    # Over: lowest number; Under: highest number, ties broken by price.
    assert best["over"]["point"] == 146.0
    assert best["under"]["point"] == 147.0 and best["under"]["books"] == ["fanduel"]
    # Moneyline: highest payout.
    assert best["away_ml"]["price"] == 160 and best["home_ml"]["price"] == -180


def test_open_vs_now_pulled_and_off_market():
    ev = oddsboard.build_event(board_rows())
    rows = {r["book"]: r for r in ev["rows"]}
    dk = rows["draftkings"]["cells"]["home_spread"]
    assert dk["open"]["point"] == -3.5 and dk["move"] == -1.0
    assert rows["draftkings"]["cells"]["away_ml"]["move"] == 15
    assert [p["book"] for p in ev["pulled"]] == ["lowvig"]
    assert rows["betmgm"]["off_market"] and rows["betmgm"]["off"]["spread"] == -1.5
    assert not rows["fanduel"]["off_market"]
    assert ev["opener"]["book"] in ("draftkings", "lowvig") and ev["opener"]["lead_hours"] == 31.0
    assert ev["open"]["spread"] == -3.5 and ev["move"]["spread"] == -1.0


def test_pinnacle_is_market_number_when_posted():
    rows = board_rows() + quote(T2, "pinnacle", -5.0, (-104, -106), 146.5, ml=(-200, 175))
    c = oddsboard.build_event(rows)["consensus"]
    assert c["source"] == "pinnacle" and c["spread"] == -5.0
    assert c["median_spread"] == -4.5
    assert 0.6 < c["fair_home"] < 0.7


def test_model_edge_sides():
    ev = oddsboard.build_event(board_rows())
    # Model has Toledo by 7: likes the home side by 2.5 against the -4.5 market.
    m = oddsboard.model_edge({"proj_margin": 7.0, "proj_total": 150.0, "win_prob_home": 0.72}, ev)
    assert m["spread"] == -7.0 and m["spread_side"] == "home" and m["spread_gap"] == 2.5
    assert m["spread_best"]["books"] == ["bovada"] and m["spread_best"]["edge"] == 3.0
    assert m["total_side"] == "over" and m["total_best"]["edge"] == 4.0
    assert not m["rough"]
    # Model has Toledo by 2: likes Akron; best Akron number is +6 at BetMGM.
    m = oddsboard.model_edge({"proj_margin": 2.0, "proj_total": 140.0, "non_d1": True}, ev)
    assert m["spread_side"] == "away" and m["spread_best"]["edge"] == 4.0
    assert m["total_side"] == "under" and m["rough"]


def test_load_projections_latest_wins(tmp_path):
    p = tmp_path / "projections.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in [
        {"game_id": "1", "generated_at": "2026-12-01T12:00:00Z", "proj_margin": 3},
        {"game_id": "1", "generated_at": "2026-12-02T12:00:00Z", "proj_margin": 5},
        {"game_id": "2", "generated_at": "2026-12-01T12:00:00Z", "proj_margin": 1},
    ]))
    out = oddsboard.load_projections(p)
    assert out["1"]["proj_margin"] == 5 and len(out) == 2
    assert oddsboard.load_projections(tmp_path / "missing.jsonl") == {}


def test_budget_uses_api_counters(tmp_path):
    runs = tmp_path / "runs.jsonl"
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    rows = [{"captured_at": "2026-11-19T12:00:00+00:00"}]
    b = oddsboard.budget(now, rows, runs)
    assert not b["from_api"] and b["estimated_used"] == 3
    oddsboard.record_run({"captured_at": "2026-11-19T12:00:00+00:00", "mac_events": 2, "rows": 40,
                          "quota": {"requests_used": "60", "requests_remaining": "440", "requests_last": "3"}}, runs)
    b = oddsboard.budget(now, rows, runs)
    assert b["from_api"] and b["used"] == 60 and b["remaining"] == 440
    assert b["projected_month_end"] == 60 + 11 * 9


def test_page_context_splits_board_and_closed():
    games = [{
        "game_id": "g1", "date": "2026-12-05T19:00Z", "completed": False, "conference_game": True,
        "neutral_site": False, "broadcasts": [],
        "home": {"key": "toledo", "name": HOME, "abbr": "TOL", "espn_id": "2649", "score": None},
        "away": {"key": "akron", "name": AWAY, "abbr": "AKR", "espn_id": "2006", "score": None},
    }]
    now = datetime(2026, 12, 5, 13, tzinfo=timezone.utc)
    ctx = oddsboard.page_context(now, games, board_rows(), {"g1": "ev1"}, {"g1": {"proj_margin": 8, "proj_total": 140}})
    assert len(ctx["board"]) == 1 and not ctx["closed"]
    ev = ctx["board"][0]
    assert ev["home"]["abbr"] == "TOL" and ev["model"]["spread_side"] == "home"
    assert ctx["edges"] == 1 and ctx["has_model"]
    later = datetime(2026, 12, 6, 13, tzinfo=timezone.utc)
    games[0].update(completed=True)
    games[0]["home"]["score"], games[0]["away"]["score"] = 75, 70
    ctx = oddsboard.page_context(later, games, board_rows(), {"g1": "ev1"})
    r = ctx["closed"][0]["result"]
    assert r["ats"] == "home" and r["ou"] == "under"  # TOL -4.5 won by 5; 145 points vs 146.5


def test_stale_exchange_quote_is_not_best():
    # Every book is -12.5 at about -110; one exchange still shows a stale -1.5 at -1150 / 136.5.
    rows = []
    for bk in ("draftkings", "fanduel", "betmgm", "bovada"):
        rows += quote(T2, bk, -12.5, total=157.0, ml=(-900, 600))
    rows += quote(T2, "pinnacle", -13.0, (-101, -116), 157.0, ml=(-850, 620))
    rows += quote(T2, "novig", -1.5, (-1150, -4900), 136.5, ml=(-120, 100))
    ev = oddsboard.build_event(rows)
    assert "novig" not in ev["best"]["home_spread"]["books"]
    assert ev["best"]["home_spread"]["point"] == -12.5
    assert ev["best"]["away_spread"]["books"] == ["pinnacle"]
    assert ev["best"]["over"]["point"] == 157.0 and "novig" not in ev["best"]["under"]["books"]
    assert "novig" not in ev["best"]["away_ml"]["books"]
    nov = next(r for r in ev["rows"] if r["book"] == "novig")
    assert nov["cells"]["home_spread"]["suspect"] and nov["cells"]["over"]["suspect"]
    assert not next(r for r in ev["rows"] if r["book"] == "draftkings")["cells"]["home_spread"]["suspect"]
    assert ev["consensus"]["median_total"] == 157.0


def test_best_play_picks_biggest_edge_in_window():
    now = datetime(2026, 12, 5, 0, 0, tzinfo=timezone.utc)
    def ev(eid, tip, sp_edge=None, tot_edge=None, rough=False):
        m = {"rough": rough, "spread": -5.0, "spread_side": "home", "total": 150.0, "total_side": "over"}
        if sp_edge is not None:
            m["spread_best"] = {"point": -3.5, "price": -110, "books": ["draftkings"], "edge": sp_edge}
        if tot_edge is not None:
            m["total_best"] = {"point": 147.5, "price": -105, "books": ["fanduel", "betmgm"], "edge": tot_edge}
        return {"odds_event_id": eid, "commence_time": tip, "model": m,
                "away": {"abbr": "AKR"}, "home": {"abbr": "TOL"}}
    board = [ev("a", "2026-12-05T19:00:00Z", sp_edge=1.5, tot_edge=2.5),
             ev("b", "2026-12-08T19:00:00Z", sp_edge=6.0),            # outside 30h
             ev("c", "2026-12-05T20:00:00Z", sp_edge=4.0, rough=True)]  # non-D-I
    bp = oddsboard.best_play(board, now)
    assert bp["odds_event_id"] == "a" and bp["kind"] == "total" and bp["pick"] == "Over 147.5" and bp["edge"] == 2.5
    assert oddsboard.best_play([ev("a", "2026-12-05T19:00:00Z", sp_edge=1.0)], now) is None
