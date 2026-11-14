import json
import random
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mac import den as D

JS = Path(__file__).resolve().parent.parent / "templates" / "static" / "den.js"
GB, CSU, UWF, VIT = "2739", "325", "2697", "2677"  # Green Bay, Cleveland State (Horizon), West Florida (ASUN), Viterbo (not ours)


# ---------------------------------------------------------------- scoring: the same numbers den.js lists in its header

KNOWN = [
    ("fantasyPoints", [{"pts": 8, "reb": 6, "ast": 5, "blk": 2, "stl": 1}], 28.7),
    ("fantasyPoints", [[20, 7, 3, 0, 1]], 34.9),
    ("defensePoints", [{"blk": 4, "stl": 8, "pa": 46, "ofgm": 17, "ofga": 55}], 33.5),
    ("defensePoints", [{"blk": 1, "stl": 4, "pa": 67, "ofgm": 24, "ofga": 53}], 8.9),
    ("shootingPct", [{"fgm": 22, "ftm": 15, "fga": 59, "fta": 19}], 0.4744),
    ("pickWorth", [0.504, "home"], 50),
    ("pickWorth", [0.504, "away"], 50),
    ("pickWorth", [0.935, "home"], 6),
    ("pickWorth", [0.935, "away"], 94),
    ("brickWall", [["hit", "hit", "stand", "hit", "miss", "hit"]], {"wall": 1, "best": 3}),
]


def _py(name, args):
    if name == "fantasyPoints":
        a = args[0]
        return D.fantasy_points(*(a[:5] if isinstance(a, list) else [a[k] for k in ("pts", "reb", "ast", "blk", "stl")]))
    if name == "defensePoints":
        a = args[0]
        return D.defense_points(a["blk"], a["stl"], a["pa"], a["ofgm"], a["ofga"])
    if name == "shootingPct":
        a = args[0]
        return D.shooting_pct(a["fgm"], a["ftm"], a["fga"], a["fta"])
    if name == "pickWorth":
        return D.worth(*args)
    if name == "brickWall":
        return D.brick_wall(*args)
    raise KeyError(name)


@pytest.mark.parametrize("name,args,want", KNOWN)
def test_python_scoring_known_cases(name, args, want):
    assert _py(name, args) == want


def test_js_header_lists_the_same_cases():
    head = JS.read_text()
    for line in ("=== 28.7", "=== 34.9", "=== 33.5", "=== 8.9", "=== 0.4744", '"home") === 6', '"away") === 94', "{wall:1, best:3}"):
        assert line in head, line


def test_js_is_dependency_free():
    src = JS.read_text()
    assert "import " not in src.replace("//   import * as Den", "") and "require(" not in src and "document" not in src


def _node(cases):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    script = (f"import * as D from {json.dumps(JS.as_uri())};\n"
              f"const cases = {json.dumps(cases)};\n"
              "console.log(JSON.stringify(cases.map(([n, a]) => D[n](...a))));")
    out = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_js_matches_python_on_known_and_random_cases():
    rnd = random.Random(7)
    cases = [(n, a) for n, a, _ in KNOWN]
    for _ in range(300):
        cases.append(("fantasyPoints", [[rnd.randint(0, 40), rnd.randint(0, 18), rnd.randint(0, 12), rnd.randint(0, 6), rnd.randint(0, 6)]]))
        cases.append(("defensePoints", [{"blk": rnd.randint(0, 9), "stl": rnd.randint(0, 14), "pa": rnd.randint(40, 110),
                                         "ofgm": rnd.randint(12, 40), "ofga": rnd.randint(41, 75)}]))
        cases.append(("shootingPct", [{"fgm": rnd.randint(10, 40), "ftm": rnd.randint(0, 30), "fga": rnd.randint(41, 75), "fta": rnd.randint(31, 40)}]))
        cases.append(("pickWorth", [round(rnd.random(), 3), rnd.choice(["home", "away"])]))
    got = _node(cases)
    for (n, a), js in zip(cases, got):
        assert js == _py(n, a), (n, a, js)


def _results(complete=True):
    return {"complete": complete,
            "games": [{"id": "1", "home_id": "A", "away_id": "B", "winner_id": "A", "worth": {"home": 30, "away": 70}},
                      {"id": "2", "home_id": "C", "away_id": "E", "winner_id": "E", "worth": {"home": 55, "away": 45}},
                      {"id": "3", "home_id": "F", "away_id": "G", "winner_id": "F", "worth": None}],
            "players": {"p1": 20.5, "p2": 10.2}, "defenses": {"A": 12.3},
            "shooting": {"A": 0.41, "B": 0.38, "C": 0.38, "E": 0.5}}


def test_game_scoring_rules():
    res = _results()
    win, loss = {"game": "1", "side": "home"}, {"game": "2", "side": "home"}
    assert D.pick_outcome(win, res) == "win" and D.pick_outcome(loss, res) == "loss"
    assert D.pick_outcome({"game": "9", "side": "home"}, res) == "void", "postponed and the night is done"
    assert D.pick_outcome({"game": "9", "side": "home"}, _results(False)) == "pending"
    assert D.pick_outcome(win, None) == "pending"
    assert D.pick4_score([win, loss, {"game": "2", "side": "away"}, {"game": "3", "side": "home"}], res) == 30 + 45 + 0
    assert D.daily_five_score(["p1", "p2", "nobody"], "A", res) == 43.0
    assert D.bricksanity_hit(["C", "A"], res) is True, "a tie for worst counts"
    assert D.bricksanity_hit(["A", "E"], res) is False
    assert D.bricksanity_hit(["B"], _results(False)) is None
    picks4 = [win, {"game": "2", "side": "away"}, {"game": "3", "side": "home"}, {"game": "1", "side": "home"}]
    assert D.brick_day(picks4, res) == "hit"
    assert D.brick_day([win, loss], res) == "miss", "any miss knocks the wall down, even short of four"
    assert D.brick_day([win, {"game": "9", "side": "home"}, win, win], res) == "stand", "a void never lays a brick"
    assert D.brick_day([], res) == "stand"
    assert D.brick_day([win, {"game": "9", "side": "home"}], _results(False)) == "pending"


def test_js_game_rules_match_python():
    res = _results()
    win, loss = {"game": "1", "side": "home"}, {"game": "2", "side": "home"}
    picks4 = [win, {"game": "2", "side": "away"}, {"game": "3", "side": "home"}, {"game": "1", "side": "home"}]
    cases = [("pick4Score", [[win, loss, {"game": "2", "side": "away"}], res]),
             ("dailyFiveScore", [["p1", "p2", "nobody"], "A", res]),
             ("bricksanityHit", [["C", "A"], res]), ("bricksanityHit", [["A", "E"], res]),
             ("brickDay", [picks4, res]), ("brickDay", [[win, loss], res]), ("brickDay", [[], res]),
             ("isLocked", ["2026-11-13T17:00Z", datetime(2026, 11, 13, 17, 0, tzinfo=timezone.utc).timestamp() * 1000]),
             ("isLocked", ["2026-11-13T17:00Z", datetime(2026, 11, 13, 16, 59, tzinfo=timezone.utc).timestamp() * 1000])]
    assert _node(cases) == [75, 43.0, True, False, "hit", "miss", "stand", True, False]


# ---------------------------------------------------------------- win chance


def test_devig_last_capture_before_tip_average_books():
    ev = {"commence": "2026-11-13T20:00:00Z", "caps": {
        "2026-11-13T12:00:00+00:00": {"a": [-300, 250]},
        "2026-11-13T19:30:00+00:00": {"a": [-110, -110], "b": [-200, 170], "c": [None, 150]},
        "2026-11-13T20:30:00+00:00": {"a": [-5000, 2000]},  # live, after tip: ignored
    }}
    pb = (200 / 300) / (200 / 300 + 100 / 270)
    assert D.win_chance(ev) == pytest.approx((0.5 + pb) / 2)
    assert D.win_chance({"commence": "2026-11-13T20:00:00Z", "caps": {"2026-11-13T21:00:00+00:00": {"a": [-110, -110]}}}) is None


# ---------------------------------------------------------------- the build, on a small fixture


def _box(gid, home, away, hstats, astats, players):
    def team(tid, side, s):
        return {"espn_id": tid, "home_away": side, "stats": {
            "fieldGoalsMade-fieldGoalsAttempted": f"{s[0]}-{s[1]}", "freeThrowsMade-freeThrowsAttempted": f"{s[2]}-{s[3]}",
            "blocks": str(s[4]), "steals": str(s[5])}}
    return {"game_id": gid, "teams": [team(away, "away", astats), team(home, "home", hstats)], "players": players}


def _pl(pid, tid, name, pts, reb, ast, blk, stl, mins, dnp=False):
    return {"team_espn_id": tid, "espn_id": pid, "name": name, "position": "G", "dnp": dnp, "min": None if dnp else mins,
            "pts": pts, "reb": reb, "ast": ast, "blk": blk, "stl": stl}


def _game(gid, when, home, away, hs=None, as_=None, status="STATUS_FINAL"):
    done = status == "STATUS_FINAL"
    return {"game_id": gid, "date": when, "status": status, "completed": done, "time_tba": False,
            "home": {"espn_id": home, "name": "H", "abbr": "H", "score": hs, "winner": done and hs > as_},
            "away": {"espn_id": away, "name": "Viterbo V-Hawks", "abbr": "VTBO", "score": as_, "winner": done and as_ > hs}}


def _line(cap, eid, commence, home, away, hk, ak, book, hp, ap):
    base = {"captured_at": cap, "odds_event_id": eid, "commence_time": commence, "home_team": home, "away_team": away,
            "home_key": hk, "away_key": ak, "book": book, "market": "h2h", "point": None}
    return [json.dumps({**base, "outcome": home, "price": hp}), json.dumps({**base, "outcome": away, "price": ap}),
            json.dumps({**base, "market": "spreads", "outcome": home, "price": -110, "point": -3.5})]


@pytest.fixture
def fixture(tmp_path):
    hz, asun = tmp_path / "horizon", tmp_path / "asun"
    for d in (hz, asun):
        (d / "boxscores").mkdir(parents=True)
        (d / "lines").mkdir()
    games = [
        _game("10", "2026-11-12T00:00Z", GB, VIT, 80, 50),            # Nov 11 ET: day one
        _game("20", "2026-11-13T17:00Z", GB, VIT, 66, 46),            # Nov 13 ET
        _game("21", "2026-11-14T01:00Z", CSU, UWF, 69, 67),           # Nov 13 ET (8 PM)
        _game("22", "2026-11-14T00:00Z", CSU, VIT, None, None, "STATUS_POSTPONED"),
        _game("30", "2026-11-15T00:00Z", UWF, GB, None, None, "STATUS_SCHEDULED"),  # Nov 14 ET, upcoming
        _game("40", "2026-12-25T00:00Z", UWF, GB, None, None, "STATUS_SCHEDULED"),  # beyond DAYS_AHEAD
    ]
    # The ASUN copy of game 21 is the same game (two covered leagues): dedupe by id.
    (hz / "schedule.json").write_text(json.dumps({"games": games}))
    (asun / "schedule.json").write_text(json.dumps({"games": [g for g in games if g["game_id"] in ("21", "30", "40")]}))
    (hz / "boxscores" / "10.json").write_text(json.dumps(_box("10", GB, VIT, (30, 60, 10, 12, 3, 9), (20, 60, 5, 10, 1, 2), [
        _pl("p1", GB, "Ace", 20, 7, 3, 0, 1, 30), _pl("p2", GB, "Bench", 0, 0, 0, 0, 0, 0, dnp=True),
        _pl("v1", VIT, "Visitor", 30, 5, 5, 1, 1, 35)])))
    (hz / "boxscores" / "20.json").write_text(json.dumps(_box("20", GB, VIT, (22, 59, 15, 19, 4, 8), (17, 55, 4, 5, 2, 9), [
        _pl("p1", GB, "Ace", 8, 6, 5, 2, 1, 36), _pl("p2", GB, "Bench", 2, 1, 0, 0, 0, 3)])))
    box21 = _box("21", CSU, UWF, (25, 52, 16, 18, 1, 4), (24, 53, 10, 14, 0, 10), [_pl("u1", UWF, "Shine", 12, 1, 4, 0, 2, 31)])
    (hz / "boxscores" / "21.json").write_text(json.dumps(box21))
    (asun / "boxscores" / "21.json").write_text(json.dumps(box21))
    (hz / "rosters.json").write_text(json.dumps({"rosters": {"green-bay": [
        {"espn_id": "p1", "name": "Ace", "position": "G"}, {"espn_id": "p2", "name": "Bench", "position": "F"},
        {"espn_id": "p3", "name": "Redshirt", "position": "C"}], "cleveland-state": []}}))
    (asun / "rosters.json").write_text(json.dumps({"rosters": {"west-florida": [{"espn_id": "u1", "name": "Shine", "position": "G"}]}}))
    # Game 21: Horizon file names Cleveland State only, ASUN file West Florida only. Game 30 is listed flipped.
    (hz / "lines" / "2026-11-13.jsonl").write_text("\n".join(
        _line("2026-11-13T23:00:00+00:00", "e21", "2026-11-14T01:00:00Z", "Cleveland St Vikings", "West Florida Argonauts", "cleveland-state", None, "dk", -110, -110)) + "\n")
    (asun / "lines" / "2026-11-14.jsonl").write_text("\n".join(
        _line("2026-11-14T00:30:00+00:00", "e21", "2026-11-14T01:00:00Z", "Cleveland St Vikings", "West Florida Argonauts", None, "west-florida", "dk", -150, 130)
        + _line("2026-11-14T02:00:00+00:00", "e21", "2026-11-14T01:00:00Z", "Cleveland St Vikings", "West Florida Argonauts", None, "west-florida", "dk", -9000, 3000)
        + _line("2026-11-14T12:00:00+00:00", "e30", "2026-11-15T00:00:00Z", "Green Bay Phoenix", "West Florida Argonauts", None, "west-florida", "dk", 200, -250)) + "\n")
    ratings = tmp_path / "ratings.json"
    ratings.write_text(json.dumps({"teams": [{"id": VIT, "short": "Viterbo", "abbr": "VIT"}]}))
    anchors = tmp_path / "anchors.json"
    anchors.write_text(json.dumps({"anchors": {"green-bay": {"name": "Mitch Carlson"}}}))
    den = D.Den([hz, asun], ratings, anchors, now=datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc))
    return tmp_path, den


def test_build_writes_slates_results_and_index(fixture):
    tmp, den = fixture
    summary = D.build(tmp / "site", den=den)
    out = tmp / "site" / "den"
    idx = json.loads((out / "index.json").read_text())
    assert [d["date"] for d in idx["dates"]] == ["2026-11-11", "2026-11-13", "2026-11-14"], "no Dec 25: past DAYS_AHEAD"
    assert idx["dates"][2] == {"date": "2026-11-14", "slate": True, "results": False, "complete": False}
    assert summary == {"slates": 3, "results": 2}

    s = json.loads((out / "slate-2026-11-13.json").read_text())
    assert [g["id"] for g in s["games"]] == ["20", "21"], "deduped, postponed dropped, ET date (8 PM ET is Nov 13)"
    g20, g21 = s["games"]
    assert g20["home"] == {"key": "green-bay", "id": GB, "short": "Green Bay", "abbr": "GB", "edition": "Horizon", "anchor": "Mitch Carlson"}
    assert g20["away"]["key"] is None and g20["away"]["short"] == "Viterbo" and g20["away"]["edition"] is None
    assert g20["win_home"] is None and g20["worth"] is None
    pb = (150 / 250) / (150 / 250 + 100 / 230)
    assert g21["win_home"] == round(pb, 3), "last capture before tip; the in-game capture is ignored"
    assert g21["worth"] == {"home": D.worth(g21["win_home"], "home"), "away": D.worth(g21["win_home"], "away")}
    assert s["defenses"] == [GB, UWF, CSU], "away side first, by tip; Viterbo is not one of ours"
    ace = next(p for p in s["players"] if p["id"] == "p1")
    assert ace["avg"] == {"pts": 20.0, "reb": 7.0, "ast": 3.0, "blk": 0.0, "stl": 1.0, "min": 30.0, "g": 1}, "only Nov 11"
    bench = next(p for p in s["players"] if p["id"] == "p2")
    assert bench["avg"]["g"] == 0, "a DNP is not a game played"
    assert any(p["id"] == "p3" for p in s["players"]), "roster players with no games are in the pool"
    assert not any(p["team_id"] == VIT for p in s["players"])

    first = json.loads((out / "slate-2026-11-11.json").read_text())
    assert next(p for p in first["players"] if p["id"] == "p1")["avg"]["g"] == 0, "strictly before the date"

    up = json.loads((out / "slate-2026-11-14.json").read_text())
    assert up["games"][0]["win_home"] == round((250 / 350) / (250 / 350 + 100 / 300), 3), "odds event listed home/away flipped"
    assert next(p for p in up["players"] if p["id"] == "p1")["avg"]["g"] == 2

    r = json.loads((out / "results-2026-11-13.json").read_text())
    assert r["complete"] is True, "the postponed game doesn't hold the night open"
    assert [g["id"] for g in r["games"]] == ["20", "21"]
    assert r["games"][1] == {"id": "21", "final": True, "home_id": CSU, "away_id": UWF, "home_pts": 69, "away_pts": 67,
                             "winner_id": CSU, "win_home": g21["win_home"], "worth": g21["worth"]}
    assert r["players"] == {"p1": 28.7, "p2": 3.2, "u1": 23.2}
    assert r["stat"]["p1"] == [8, 6, 5, 2, 1, 36]
    assert r["defenses"][GB] == 33.5 and r["defenses"][CSU] == 8.9 and VIT not in r["defenses"]
    assert r["shooting"] == {GB: 0.4744, CSU: 0.5857, UWF: 0.5075}
    assert r["bricks"][GB] == [37, 78]
    assert r["worst_shooter"] == GB
    assert D.bricksanity_hit([CSU, GB], r) is True


def test_results_wait_for_box_scores(fixture):
    tmp, den = fixture
    del den.boxes["21"]
    r = den.results("2026-11-13")
    assert r["complete"] is False and [g["id"] for g in r["games"]] == ["20", "21"] and CSU not in r["shooting"]
    assert D.bricksanity_hit([GB], r) is None


def test_build_clears_old_files(fixture):
    tmp, den = fixture
    (tmp / "site" / "den").mkdir(parents=True)
    (tmp / "site" / "den" / "slate-2020-01-01.json").write_text("{}")
    D.build(tmp / "site", den=den)
    assert not (tmp / "site" / "den" / "slate-2020-01-01.json").exists()


def test_round_is_half_up_like_js():
    assert D.r(11.25) == 11.3 and D.r(2.25) == 2.3 and D.r(-0.25) == -0.2
