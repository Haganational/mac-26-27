from datetime import datetime, timedelta, timezone

from mac import analysis, espn


def _event(state, home=0, away=0, detail=""):
    return {"id": "1", "date": "2026-11-10T00:00Z", "competitions": [{
        "status": {"type": {"name": {"pre": "STATUS_SCHEDULED", "in": "STATUS_IN_PROGRESS", "post": "STATUS_FINAL"}[state],
                            "state": state, "completed": state == "post", "shortDetail": detail}},
        "competitors": [
            {"homeAway": "home", "team": {"id": "2006", "displayName": "Akron Zips", "abbreviation": "AKR"}, "score": str(home), "winner": state == "post" and home > away},
            {"homeAway": "away", "team": {"id": "999", "displayName": "Muskingum", "abbreviation": "MSK"}, "score": str(away), "winner": state == "post" and away > home},
        ]}]}


def test_parse_event_live_fields():
    g = espn.parse_event(_event("in", 41, 19, "2:58 - 1st"))
    assert g["live"] and not g["completed"] and g["detail"] == "2:58 - 1st"
    assert (g["home"]["score"], g["away"]["score"]) == (41, 19)
    pre = espn.parse_event(_event("pre", detail="11/9 - 7:00 PM EST"))
    assert not pre["live"] and pre["detail"] == "" and pre["home"]["score"] is None


def test_apply_live_then_final():
    g = espn.parse_event(_event("pre"))
    assert espn.apply_live(g, espn.parse_event(_event("in", 41, 19, "2:58 - 1st")))
    assert not espn.apply_live(g, espn.parse_event(_event("in", 41, 19, "2:58 - 1st")))
    espn.apply_live(g, espn.parse_event(_event("post", 90, 50, "Final")))
    assert g["completed"] and not g["live"] and g["home"]["winner"]


def test_live_candidates_window():
    now = datetime(2026, 11, 10, 1, 0, tzinfo=timezone.utc)
    mk = lambda h, **kw: {"date": (now + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%MZ"), "completed": False, **kw}
    games = [mk(-1), mk(0.25), mk(2), mk(-7), mk(-1, completed=True), mk(-1, time_tba=True)]
    assert espn.live_candidates(games, now) == [games[0], games[1]]


def test_upcoming_keeps_live_game_past_three_hours():
    now = datetime(2026, 11, 10, 4, 0, tzinfo=timezone.utc)
    g = espn.parse_event(_event("in", 70, 60, "0:30 - 2OT"))
    g["date"] = "2026-11-10T00:30Z"
    assert [x["game_id"] for x in analysis.upcoming([g], {}, now)] == ["1"]
    g["live"] = False
    assert analysis.upcoming([g], {}, now) == []


def test_parse_tickets_takes_event_link_and_low_price():
    ev = _event("pre")
    ev["competitions"][0]["ticketsAvailable"] = True
    ev["competitions"][0]["tickets"] = [{"summary": "Tickets as low as $14", "startingPrice": 14.0, "links": [
        {"rel": ["tickets", "desktop", "venue"], "href": "https://tix.example/venue"},
        {"rel": ["tickets", "desktop", "event"], "href": "https://tix.example/event"}]}]
    assert espn.parse_event(ev)["tickets"] == {"url": "https://tix.example/event", "low": 14.0}
    ev["competitions"][0]["ticketsAvailable"] = False
    assert espn.parse_event(ev)["tickets"] is None
    assert espn.parse_event(_event("pre"))["tickets"] is None
