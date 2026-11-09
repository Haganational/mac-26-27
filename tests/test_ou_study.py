from mac import ou_study


def g(gid, home_id, away_id, hp, ap, total, ot=0, date="2025-11-10T23:00Z"):
    return {"id": gid, "date": date, "neutral": False, "ot": ot, "season_type": 2,
            "home": {"id": home_id, "name": "H", "pts": hp}, "away": {"id": away_id, "name": "A", "pts": ap},
            "line": {"book": "DraftKings", "total": total}}


def test_rows_mac_only_and_results():
    ohio, toledo = "195", "2649"
    games = [g("1", ohio, "999", 80, 70, 140.5), g("2", ohio, toledo, 60, 60, 130.5), g("3", "998", "997", 90, 90, 150),
             {**g("4", ohio, "999", 70, 70, 140), "line": {}}]
    rs = ou_study.rows(games, 2026)
    assert {r["id"] for r in rs} == {"1", "2"}
    assert len([r for r in rs if r["id"] == "2"]) == 2  # MAC vs MAC: one row per team
    assert len(ou_study.games_only(rs)) == 2
    s = ou_study.summarize(ou_study.games_only(rs))
    assert (s["o"], s["u"], s["p"]) == (1, 1, 0) and s["avg_diff"] == 0.0


def test_lean_needs_sample_and_direction():
    under = [{"res": "u", "diff": -5.0, "close": 150, "actual": 145}] * 12 + [{"res": "o", "diff": 2.0, "close": 150, "actual": 152}] * 4
    assert ou_study.summarize(under)["lean"] == "under"
    assert ou_study.summarize(under[:10])["lean"] is None  # too few games
    even = [{"res": "u", "diff": -1.0, "close": 150, "actual": 149}] * 8 + [{"res": "o", "diff": 9.0, "close": 150, "actual": 159}] * 8
    assert ou_study.summarize(even)["lean"] is None  # big average miss but a 50/50 split


def test_build_runs_on_repo_data():
    o = ou_study.build()
    assert o["seasons"] and o["all"]["n"] > 0 and o["scatter"]["dots"]
