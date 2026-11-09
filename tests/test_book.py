import gzip

from mac import book


def _game():
    return {
        "game_id": "1", "date": "2026-11-05T00:00Z", "neutral_site": True,
        "teams": [{"espn_id": "h", "abbr": "HOM", "name": "Home", "home_away": "home"},
                  {"espn_id": "a", "abbr": "AWY", "name": "Away", "home_away": "away"}],
        "players": [
            {"espn_id": f"h{i}", "name": f"H{i}", "team_espn_id": "h", "position": "G", "starter": i < 5, "dnp": i == 5,
             "min": None if i == 5 else 20, "pts": 4, "fgm": 2, "fga": 4, "tpm": 0, "tpa": 1, "ftm": 0, "fta": 0,
             "reb": 3, "oreb": 1, "dreb": 2, "ast": 1, "stl": 0, "blk": 0, "to": 1, "pf": 2} for i in range(6)
        ] + [
            {"espn_id": f"a{i}", "name": f"A{i}", "team_espn_id": "a", "position": "F", "starter": True, "dnp": False,
             "min": 40, "pts": 6, "fgm": 3, "fga": 5, "tpm": 0, "tpa": 0, "ftm": 0, "fta": 0,
             "reb": 2, "oreb": 0, "dreb": 2, "ast": 0, "stl": 1, "blk": 0, "to": 0, "pf": 1} for i in range(5)
        ],
        # "ghost" is on the floor in the play-by-play but missing from the box score.
        "stints": [{"secs": 600.0, "home": ["h0", "h1", "h2", "h3", "ghost"], "away": [f"a{i}" for i in range(5)],
                    "pts_h": 10, "pts_a": 12, "poss": 18.5},
                   {"secs": 30.0, "home": ["h0", "h1"], "away": ["a0"], "pts_h": 0, "pts_a": 0, "poss": 1.0, "bad": True}],
    }


def test_game_round_trip():
    g = _game()
    back = book.decode_game("1", book.encode_game(g))
    assert back["stints"] == g["stints"]
    assert back["neutral_site"] is True and back["date"] == g["date"]
    by_id = {p["espn_id"]: p for p in back["players"]}
    for p in g["players"]:
        assert {k: by_id[p["espn_id"]][k] for k in p} == p
    assert by_id["ghost"]["min"] is None  # kept for lineups, never rated


def test_day_files_merge_and_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(book, "BOOK_DIR", tmp_path)
    book.save_games(2027, {"1": book.encode_game(_game())})
    g2 = _game() | {"date": "2026-11-05T23:00Z"}
    g2["teams"] = [dict(t, espn_id="x" if t["home_away"] == "home" else "y") for t in g2["teams"]]
    g2["players"] = [dict(p, team_espn_id="x" if p["team_espn_id"] == "h" else "y") for p in g2["players"]]
    book.save_games(2027, {"2": book.encode_game(g2)})
    files = list((tmp_path / "2027" / "games").glob("*.json.gz"))
    assert [f.name for f in files] == ["2026-11-05.json.gz"]
    assert book.stored_game_ids(2027) == {"1", "2"}
    assert [g["game_id"] for g in book.load_games(2027, {"x"})] == ["2"]
    # Rewriting the same content leaves the bytes alone (no git churn).
    before = files[0].read_bytes()
    book.save_games(2027, {"2": book.encode_game(g2)})
    assert files[0].read_bytes() == before
    assert gzip.decompress(before)


def test_compact_odds_home_view():
    ev = {"id": "e", "commence_time": "t", "home_team": "Ohio", "away_team": "Akron", "bookmakers": [
        {"key": "pinnacle", "markets": [
            {"key": "spreads", "outcomes": [{"name": "Ohio", "point": -3.5, "price": -110}, {"name": "Akron", "point": 3.5, "price": -110}]},
            {"key": "totals", "outcomes": [{"name": "Over", "point": 150.5, "price": -105}, {"name": "Under", "point": 150.5, "price": -115}]},
            {"key": "h2h", "outcomes": [{"name": "Ohio", "price": -160}, {"name": "Akron", "price": 140}]}]}]}
    assert book.compact_odds([ev]) == [["e", "t", "Ohio", "Akron", {"pinnacle": [-3.5, -110, 150.5, -105, -160, 140]}]]
