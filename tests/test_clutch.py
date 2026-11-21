from mac import book, clutch


def _play(h, a, per=2, clock="5:00", kind="JumpShot", pid=None, text="", team="x", scoring=None):
    p = {"type": {"text": kind}, "text": text, "team": {"id": team}, "period": {"number": per},
         "clock": {"displayValue": clock}, "homeScore": h, "awayScore": a,
         "participants": [{"athlete": {"id": pid}}] if pid else []}
    if scoring is not None:
        p["scoringPlay"] = scoring
    return p


def test_ft_halves_counts_made_and_missed_by_half():
    roster = {"h1": "home", "a1": "away"}
    summary = {"plays": [
        _play(1, 0, per=1, clock="15:00", kind="MadeFreeThrow", pid="h1", text="made free throw", scoring=True),
        _play(1, 0, per=1, clock="15:00", kind="MadeFreeThrow", pid="h1", text="missed free throw", scoring=False),
        _play(1, 1, per=2, clock="0:30", kind="MadeFreeThrow", pid="a1", text="made free throw", scoring=True, team="h"),  # wrong team tag
        _play(1, 1, per=3, clock="0:10", kind="MadeFreeThrow", pid="a1", text="missed free throw", scoring=False),
    ]}
    f = clutch.ft_halves(summary, roster, {"h": "home", "a": "away"})
    assert f == {"home": [1, 2, 0, 0], "away": [0, 0, 1, 2]}
    assert clutch.ft_halves({"plays": [_play(2, 0)]}, roster, {}) is None


def _game(events, t=(["1", "H"], ["2", "A"])):
    return {"teams": [{"espn_id": "1", "home_away": "home"}, {"espn_id": "2", "home_away": "away"}],
            "events": [{"t": e[0], "per": e[1], "h": e[2], "a": e[3]} for e in events]}


def test_late_comeback_only_counts_last_ten_minutes():
    # away led by 15 at the half, home cut it to 4 by 10:00 left, trailed by 7 at 6:00 left, won
    ev = [(1100, 1, 20, 35), (1790, 2, 40, 44), (1850, 2, 40, 47), (2160, 2, 52, 50), (2390, 2, 60, 55)]
    c = clutch.late_comeback(_game(ev))
    assert c["side"] == "home" and c["deficit"] == 7 and c["secs_left"] == 550
    # a lead never lost after 10:00 left is no comeback
    assert clutch.late_comeback(_game([(1000, 1, 0, 20), (1700, 2, 50, 40), (2400, 2, 70, 60)])) is None


def test_late_comeback_counts_the_score_at_the_ten_minute_mark():
    ev = [(1700, 2, 30, 42), (2000, 2, 40, 42), (2400, 2, 50, 44)]
    c = clutch.late_comeback(_game(ev))
    assert c["deficit"] == 12 and c["secs_left"] == 600


def _raw(gid, home, away, events, ft=None, box_ft=None):
    rows = []
    for side, (m, a) in enumerate(box_ft or [(0, 0), (0, 0)]):
        r = [f"p{side}", "x", side, "G", 1] + [None] * (len(book.P_COLS) - 5)
        r[book.P_COLS.index("ftm")], r[book.P_COLS.index("fta")] = m, a
        rows.append(r)
    g = {"d": "2026-11-10T00:00Z", "n": 0, "t": [[home, "H"], [away, "A"]], "p": rows, "s": [],
         "e": [[e[0], e[1], e[2], e[3], -1, "fg", None, None] for e in events]}
    if ft is not None:
        g["f"] = ft
    return gid, g


def test_rankings_rank_kings_and_free_throws():
    teams = {str(i): {"key": f"t{i}", "short": f"T{i}", "color": "#000", "conf_short": "C", "href": f"teams/t{i}.html"} for i in range(1, 13)}
    games = [
        _raw("g1", "1", "2", [(1850, 2, 40, 50), (2400, 2, 60, 58)]),  # T1 back from 10
        _raw("g2", "3", "4", [(1850, 2, 40, 50), (2380, 2, 50, 58), (2400, 2, 50, 60)]),  # T4 led all the way late
        _raw("g3", "4", "5", [(2350, 2, 40, 50), (2700, 3, 61, 60)]),  # T4 back from 10 with 0:50 left, in OT
    ]
    # T1..T12 each shoot second-half free throws; one game whose log doesn't match the box is ignored
    for i in range(1, 12, 2):
        games.append(_raw(f"f{i}", str(i), str(i + 1), [(2400, 2, 1, 0)],
                          ft=[[0, 0, 10 + i, 30], [0, 0, 30 - i, 30]], box_ft=[(10 + i, 30), (30 - i, 30)]))
    games.append(_raw("bad", "1", "2", [(2400, 2, 1, 0)], ft=[[0, 0, 0, 30], [0, 0, 0, 30]], box_ft=[(20, 30), (20, 30)]))
    r = clutch.rankings(2027, teams=teams, games=games)
    assert [k["short"] for k in r["kings"]] == ["T4", "T1"]  # same 10, T4's came with less time left
    assert r["kings"][0]["when"] == "0:50" and r["kings"][0]["score"] == "61-60" and r["kings"][0]["home"]
    assert r["n_ft"] == 7 and r["n_ft_ok"] == 6
    assert [x["short"] for x in r["dont_foul"]] == ["T2", "T4", "T6", "T8", "T10"]
    assert [x["short"] for x in r["foul"]] == ["T1", "T3", "T5", "T7", "T9"]
    assert r["dont_foul"][0]["pct_label"] == "96.7%"


def test_book_keeps_free_throws_by_half():
    from tests.test_book import _game as bg
    g = bg()
    g["ft"] = {"home": [1, 2, 3, 4], "away": [5, 6, 7, 8]}
    enc = book.encode_game(g)
    assert enc["f"] == [[1, 2, 3, 4], [5, 6, 7, 8]]
    assert book.decode_game("1", enc)["ft"] == g["ft"]


def test_clutch_baskets_tie_and_go_ahead_late_only():
    g = {"events": [{"t": 1000, "per": 1, "h": 2, "a": 0, "pid": "x"},  # early: no
                    {"t": 1900, "per": 2, "h": 2, "a": 2, "pid": "y"},  # tie: yes, away
                    {"t": 1950, "per": 2, "h": 5, "a": 2, "pid": "x"},  # go-ahead three: yes
                    {"t": 2000, "per": 2, "h": 7, "a": 2, "pid": "x"},  # extends a lead: no
                    {"t": 2100, "per": 2, "h": 7, "a": 4, "pid": "y"}]}  # still behind: no
    b = clutch.clutch_baskets(g)
    assert [(x["pid"], x["pts"], x["ahead"]) for x in b] == [("y", 2, False), ("x", 3, True)]


def test_heart_rate_counts_lead_changes():
    ev = [{"t": 100 * i, "per": 1 if i < 12 else 2, "h": 2 * i if i % 2 else 2 * i - 3, "a": 2 * i - 1 if i % 2 else 2 * i} for i in range(1, 24)]
    sw, ch = clutch.heart_rate({"events": ev})
    assert ch >= 20 and sw > 0
    assert clutch.heart_rate({"events": ev[:5]}) is None
