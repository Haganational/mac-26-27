from mac import notebook, press


def _fake(monkeypatch, games):
    monkeypatch.setattr(notebook, "_schedule", lambda d: games)


def _g(i, date, us, them, home=True):
    me = {"key": "akron", "score": us, "name": "Akron"}
    op = {"key": "kent-state", "score": them, "name": "Kent State"}
    return {"game_id": str(i), "date": date, "completed": True, "neutral_site": False, "conference_game": True,
            "home": me if home else op, "away": op if home else me}


def test_barometer_moves_with_results(monkeypatch):
    _fake(monkeypatch, [])
    assert notebook.barometer("akron")["score"] == 50
    _fake(monkeypatch, [_g(i, f"2026-11-0{i}T23:00Z", 80, 60) for i in range(1, 6)])
    hot = notebook.barometer("akron")
    assert hot["score"] > 65 and hot["streak"] == "W5" and hot["record"] == "5-0" and hot["conf"] == "5-0"
    _fake(monkeypatch, [_g(i, f"2026-11-0{i}T23:00Z", 60, 80, home=False) for i in range(1, 6)])
    assert notebook.barometer("akron")["score"] < 35
    # as of a tip time, later games don't count
    assert notebook.barometer("akron", before="2026-11-02T00:00Z")["games"] == 1
    assert notebook.mood_rate("akron", "2026-11-09") > 1


def test_log_only_grows(monkeypatch, tmp_path):
    monkeypatch.setattr(notebook, "OUT", tmp_path)
    _fake(monkeypatch, [_g(1, "2026-11-01T23:00Z", 70, 60)])
    notebook.write_all(["akron"])
    first = (tmp_path / "akron.md").read_text()
    assert first.count("<!-- g:1 -->") == 1
    _fake(monkeypatch, [_g(1, "2026-11-01T23:00Z", 70, 60), _g(2, "2026-11-03T23:00Z", 50, 70)])
    notebook.write_all(["akron"])
    second = (tmp_path / "akron.md").read_text()
    assert second.count("<!-- g:1 -->") == 1 and second.count("<!-- g:2 -->") == 1
    assert "fictional AI" in second


def test_mood_raises_aside_rate(monkeypatch):
    monkeypatch.setattr(press, "_leans_file", lambda: {"settings": {"aside_rate": 0.5}, "leans": {
        "akron": {"rival": "kent-state", "asides": {"win": ["{us} again"]}}}})
    monkeypatch.setattr(notebook, "mood_rate", lambda k, b=None: 2.0)
    hits = sum(bool(press.aside("akron", "win", str(i), {"us": "Akron"}, before="2026-11-20")) for i in range(200))
    assert hits == 200
