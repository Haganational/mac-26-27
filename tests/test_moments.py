from mac import book, moments as M


def _p(pid, name, side):
    return {"espn_id": pid, "name": name, "team_espn_id": side}


def _game(events, players=None):
    players = players or [_p("h1", "Hal Home", "h"), _p("a1", "Al Away", "a"), _p("a2", "Ace Away", "a")]
    return {"game_id": "9", "date": "2026-11-18T23:00Z", "players": players, "events": events}


def _ev(t, per, h, a, pid=None, kind="fg"):
    return {"t": t, "per": per, "h": h, "a": a, "pid": pid, "kind": kind, "wb": None, "wa": None}


def _close_game():
    """Home leads most of the way, away goes on a 12-0 run late, home wins on a jumper with 4 seconds left."""
    ev, h, a, t = [], 0, 0, 0.0
    for i in range(20):  # home builds a lead: 2 for home, then 1 for away... home 40-20 by halftime
        t += 55
        if i % 2 == 0:
            h += 3; ev.append(_ev(t, 1, h, a, "h1", "3"))
        else:
            a += 2; ev.append(_ev(t, 1, h, a, "a1"))
    # second half: trade baskets, then the away run
    t = 1300.0
    for _ in range(6):
        t += 60; h += 2; ev.append(_ev(t, 2, h, a, "h1"))
        t += 60; a += 2; ev.append(_ev(t, 2, h, a, "a1"))
    t = 2000.0
    for _ in range(6):
        t += 40; a += 2; ev.append(_ev(t, 2, h, a, "a2", "layup"))
    # now h=42+... compute: tie it and go ahead for away, then home wins late
    while a <= h:
        t += 20; a += 2; ev.append(_ev(t, 2, h, a, "a2", "dunk"))
    t = 2396.0
    need = a - h + 1
    h += need if need <= 3 else 3
    ev.append(_ev(t, 2, h, a, "h1", "jumper" if need == 2 else "3" if need == 3 else "ft"))
    return ev


def test_events_from_summary_reads_scoring_plays_and_espn_win_probability():
    def play(pid, h, a, per=1, clock="19:00", kind="JumpShot", id_=None):
        return {"id": id_, "type": {"text": kind}, "text": "", "team": {"id": "x"}, "participants": [{"athlete": {"id": pid}}],
                "period": {"number": per}, "clock": {"displayValue": clock}, "homeScore": h, "awayScore": a}
    summary = {"plays": [play("h1", 0, 0, id_="1", kind="Substitution"), play("h1", 3, 0, id_="2"), play("a1", 3, 1, id_="3", kind="MadeFreeThrow"),
                         play("a1", 3, 3, per=2, clock="0:04", id_="4", kind="DunkShot")],
               "winprobability": [{"playId": "1", "homeWinPercentage": 0.6}, {"playId": "2", "homeWinPercentage": 0.7},
                                  {"playId": "3", "homeWinPercentage": 0.68}, {"playId": "4", "homeWinPercentage": 0.5}]}
    ev = M.events_from_summary(summary)
    assert [(e["h"], e["a"], e["kind"]) for e in ev] == [(3, 0, "3"), (3, 1, "ft"), (3, 3, "dunk")]
    assert ev[0]["wb"] == 600 and ev[0]["wa"] == 700 and ev[2]["t"] == 2396.0


def test_book_keeps_scoring_plays():
    g = {"game_id": "1", "date": "2026-11-05T00:00Z", "neutral_site": False,
         "teams": [{"espn_id": "h", "abbr": "H", "name": "H", "home_away": "home"}, {"espn_id": "a", "abbr": "A", "name": "A", "home_away": "away"}],
         "players": [{"espn_id": "h1", "name": "Hal", "team_espn_id": "h", "starter": True, "dnp": False, "pts": 3}],
         "stints": [], "events": [_ev(30.0, 1, 3, 0, "h1", "3"), _ev(60.0, 1, 3, 2, "zz")]}
    back = book.decode_game("1", book.encode_game(g))
    assert back["events"][0]["pid"] == "h1" and back["events"][1]["pid"] is None and back["events"][0]["kind"] == "3"


def test_moments_find_the_winner_the_run_and_the_late_basket():
    m = M.analyze(_game(_close_game()), home_spread=-5.0, total=120.5)
    assert m["winner"] == "home"
    fg = m["for_good"]
    assert fg["who"] == "Hal Home" and fg["crunch"] and fg["when"] == "with 4 seconds left"
    assert m["run"]["side"] == "away" and m["run"]["pts"] >= 12
    assert m["swing"]["i"] == fg["i"]  # the late winner is the biggest swing
    lines = M.recap_lines(m, {"home": "Toledo", "away": "Akron"}, seed="9")
    assert any("ahead for good" in s or "won it" in s for s in lines)
    assert any("Akron made a" in s and "could not hold it" in s for s in lines)
    assert M.short_line(m, "home", {"home": "Toledo", "away": "Akron"}).endswith("with 4 seconds left won it.")


def test_flip_finds_the_play_that_decided_a_bet():
    ev = [_ev(100, 1, 2, 0), _ev(2300, 2, 70, 66), _ev(2390, 2, 70, 68, "a1"), _ev(2398, 2, 70, 69, "a1", "ft")]
    # home -3.5: covering at 70-66, then the away basket with 10 seconds left flips it
    f = M.flip(ev, "side", "home", -3.5)
    assert f["i"] == 2 and f["result"] == "loss" and f["left"] == 10
    # the over 138.5 crossed on the last free throw
    o = M.flip(ev, "total", "over", 138.5)
    assert o["i"] == 3 and o["result"] == "win"
    # an under that never crossed: no flip to talk about
    assert M.flip(ev, "total", "under", 150.5) is None


def test_when_reads_like_a_broadcaster():
    assert M.when({"t": 1200 - 75, "per": 1}) == "with 1:15 left in the first half"
    assert M.when({"t": 2400 - 41, "per": 2}) == "with 41 seconds left"
    assert M.when({"t": 2400, "per": 2}) == "at the buzzer"
    assert M.when({"t": 2400 - 70, "per": 2}, last_per=3) == "with 1:10 left in regulation"
    assert M.when({"t": 2700 - 65, "per": 3}) == "with 1:05 left in overtime"


def test_no_play_by_play_no_moments():
    assert M.analyze(_game([])) is None
    assert M.recap_lines(None, {}) == []


def test_season_high_needs_three_earlier_games():
    games = [{"date": f"2026-11-0{i}", "players": [{"espn_id": "p", "pts": 10 + i}]} for i in range(1, 5)]
    highs = M.season_highs(games)
    assert M.high_note("p", 20, "2026-11-09", highs) == "season high"
    assert M.high_note("p", 14, "2026-11-09", highs) is None
    assert M.high_note("p", 20, "2026-11-03", highs) is None  # only two earlier games


class _FakeBook:
    def __init__(self, game):
        self.g = game

    def game(self, gid, date):
        return self.g


def test_tops_bad_beat_from_the_play_by_play():
    from mac import tops
    ev = [_ev(100, 1, 2, 0), _ev(2300, 2, 70, 66), _ev(2390, 2, 70, 68, "a1"), _ev(2398, 2, 70, 69, "a1", "ft")]
    card = {"picks": {"merv": [{"kind": "side", "game": "9", "tip": "2026-11-18T23:00Z", "side": "home", "line": -3.5,
                                "label": "Toledo -3.5", "result": "loss"}],
                      "leslie": [{"kind": "total", "game": "9", "tip": "2026-11-18T23:00Z", "side": "over", "line": 138.5,
                                  "label": "Over 138.5", "result": "win"}]}}
    bs = tops.beats(card, book=_FakeBook(_game(ev)))
    assert [b["key"] for b in bs] == ["merv", "leslie"]
    assert bs[0]["scorer"] == "Al Away" and bs[0]["when"] == "with 10 seconds left"
    line = tops.beat_line(bs[0], "brett", "2026-11-19")
    assert "Toledo -3.5" in line and "Al Away" in line
    mine = tops.beat_line(bs[0], "merv", "2026-11-19")
    assert mine.startswith("My Toledo -3.5 died with 10 seconds left")
    col = tops.column("2026-11-19", {}, None, [], late=bs)
    assert col["paras"]


def test_anchor_moment_lines_never_name_players():
    from mac import press
    for lines in press.MOMENT_ASIDES.values():
        for t in lines:
            assert "{" not in t.format(us="Toledo", them="Akron", when="at the buzzer", deficit=12, run="14-0", town="", margin=3, rival="")
    m = M.analyze(_game(_close_game()), home_spread=-5.0)
    assert M.anchor_moment(m, "home")[0] == "late_win" and M.anchor_moment(m, "away")[0] == "late_loss"


def test_articles_read_right_aloud():
    assert [M.an(n) for n in (8, 11, 18, 84, 12, 1)] == ["an", "an", "an", "an", "a", "a"]
    run = {"before": [30, 22], "after": [41, 22]}
    assert M._run_phrase(run, "X") == "stretching an 8-point lead to 19"


def test_run_phrase_from_behind():
    assert M._run_phrase({"before": [10, 16], "after": [24, 16]}, "X") == "turning a 6-point deficit into an 8-point lead"
