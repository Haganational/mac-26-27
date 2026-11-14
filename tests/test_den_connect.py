import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from mac import den_connect as dc

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
EARLY = datetime(2026, 11, 22, 17, tzinfo=timezone.utc)  # before every tip
LATE = datetime(2026, 11, 23, 6, tzinfo=timezone.utc)  # after every tip


def _side(tid, short, abbr, key=None):
    return {"id": tid, "short": short, "abbr": abbr, "key": key, "edition": None, "anchor": None}


def _game(gid, home, away, win_home, tip="2026-11-23T00:00Z"):
    worth = None if win_home is None else {"home": round(100 * (1 - win_home)), "away": round(100 * win_home)}
    return {"id": gid, "tip": tip, "home": home, "away": away, "win_home": win_home, "worth": worth}


def slate(date="2026-11-22"):
    return {"date": date, "games": [
        _game("1", _side("2006", "Akron", "AKR", "akron"), _side("2309", "Kent State", "KENT", "kent-state"), 0.6),
        _game("2", _side("2509", "Purdue", "PUR"), _side("195", "Ohio", "OHIO", "ohio"), 0.9, tip="2026-11-22T23:00Z"),
        _game("3", _side("2099", "Canisius", "CAN", "canisius"), _side("9001", "Visitor", "VIS"), 0.55),
        _game("4", _side("2649", "Toledo", "TOL", "toledo"), _side("9002", "Guest", "GST"), 0.5),
        _game("5", _side("9003", "Big", "BIG"), _side("9004", "Small", "SML"), 0.3),
        _game("6", _side("314", "Iona", "IONA", "iona"), _side("9005", "Other", "OTH"), None),
    ]}


def _team(tid, o, d, t=68.0):
    return {"id": tid, "adj_o": o, "adj_d": d, "adj_t": t}


RATINGS = {"mu": 100.0, "tau": 68.0, "hca": 3.0, "params": {"sigma_margin": 12.0}, "teams": [
    _team("2006", 105, 100), _team("2309", 108, 95),  # Kent better than Akron: ratings ~43% home vs market 60%
    _team("2099", 100, 100), _team("9001", 100, 100),  # even teams, home edge: ~60% vs market 55%
    _team("9003", 112, 92), _team("9004", 96, 104),  # ratings love Big at home: ~98% vs market 30%
    _team("2509", 115, 92), _team("195", 104, 101),
]}


# ---------------------------------------------------------------- tickets

def test_clean_ticket_url_strips_espn_code_and_rejects_other_hosts():
    raw = "https://www.vividseats.com/akron-zips-tickets/production/7630642?wsUser=717"
    assert dc.clean_ticket_url(raw) == "https://www.vividseats.com/akron-zips-tickets/production/7630642"
    assert dc.clean_ticket_url("http://vividseats.com/x?a=1&WSUSER=717&b=2#frag") == "https://vividseats.com/x?a=1&b=2"
    assert dc.clean_ticket_url("https://evil.example/vividseats.com?wsUser=717") is None
    assert dc.clean_ticket_url("https://notvividseats.com/x") is None
    assert dc.clean_ticket_url(None) is None


def test_affiliate_is_off_until_matthew_sets_the_template():
    raw = "https://www.vividseats.com/x/production/1?wsUser=717"
    assert dc.AFFILIATE_TEMPLATE is None, "ship with ticket links off"
    assert dc.affiliate_url(raw) is None
    wrapped = dc.affiliate_url(raw, "https://vivid-seats.pxf.io/c/1/2/3")
    assert wrapped == "https://vivid-seats.pxf.io/c/1/2/3?u=https%3A%2F%2Fwww.vividseats.com%2Fx%2Fproduction%2F1"
    assert "717" not in wrapped
    assert dc.affiliate_url(raw, "https://t.example/c?u={url}&s=den") == "https://t.example/c?u=https%3A%2F%2Fwww.vividseats.com%2Fx%2Fproduction%2F1&s=den"


def test_ticket_only_before_tip_and_only_with_template():
    g = slate()["games"][0]
    tix = {"1": {"url": "https://www.vividseats.com/a/production/9?wsUser=717", "low": 13.4}}
    assert dc.ticket_for(g, tix, EARLY) is None, "no Impact link yet"
    t = dc.ticket_for(g, tix, EARLY, "https://vivid-seats.pxf.io/c/1/2/3")
    assert t["low"] == 13 and t["matchup"] == "Kent State at Akron" and "wsUser" not in t["href"]
    assert dc.ticket_for(g, tix, LATE, "https://vivid-seats.pxf.io/c/1/2/3") is None, "tipped games lose the link"
    assert dc.ticket_for(slate()["games"][1], tix, EARLY, "https://vivid-seats.pxf.io/c/1/2/3") is None


def test_ticket_index_dedupes_across_editions(tmp_path):
    g = {"game_id": "7", "tickets": {"url": "https://www.vividseats.com/a?wsUser=717", "low": 5}}
    (tmp_path / "a.json").write_text(json.dumps({"games": [g, {"game_id": "8", "tickets": None}]}))
    (tmp_path / "b.json").write_text(json.dumps({"games": [{**g, "tickets": {"url": "https://www.vividseats.com/b", "low": 9}}]}))
    assert dc.ticket_index([tmp_path / "a.json", tmp_path / "b.json"]) == {"7": {"url": "https://www.vividseats.com/a?wsUser=717", "low": 5}}


def test_real_schedule_tickets_all_clean():
    for t in dc.ticket_index().values():
        clean = dc.clean_ticket_url(t["url"])
        assert clean and "wsuser" not in clean.lower()


# ---------------------------------------------------------------- anchors

def test_anchor_card_keeps_name_and_falls_back_to_monogram():
    a = dc.anchor_card("akron")
    assert a["name"] == "Marcus Vance" and a["school"] == "Akron" and a["tag"] == "AI anchor"
    assert a["portrait"] == "den/anchors/akron.webp"
    c = dc.anchor_card("canisius")  # Metro portrait not made yet
    assert c["portrait"] is None and c["initials"] == "PB" and "portrait coming" in c["alt"]
    assert c["color"].startswith("#") and c["ink"] in ("#ffffff", "#111111")
    assert dc.anchor_card("purdue") is None


def test_host_is_our_school_home_side_first():
    g = slate()["games"]
    assert dc.host_side(g[0]) == "home"  # both ours: home anchor hosts
    assert dc.host_side(g[1]) == "away"
    assert dc.host_side(g[4]) is None


def test_homer_lines_are_stable_and_in_voice():
    g = slate()["games"]
    fav = dc.homer_line(g[0], "home")
    assert fav == dc.homer_line(g[0], "home") and "Akron" in fav
    dog = dc.homer_line(g[1], "away")
    assert "Ohio" in dog
    final = dc.homer_line(g[1], "away", {"final": True, "winner_id": "195"})
    assert final in [s.format(me="Ohio", opp="Purdue", worth=90) for s in dc.RESULT_WIN]
    every = dc.HOMER_FAV + dc.HOMER_DOG + dc.HOMER_FLAT + dc.RESULT_WIN + dc.RESULT_LOSS + dc.BRICKS
    banned = ("bet", "wager", "$", "odds", "real person", "our gym", "sources")
    assert not [s for s in every if any(b in s.lower() for b in banned)]


def test_bricksanity_call_goes_to_worst_shooters_anchor():
    c = dc.bricksanity_call(slate(), {"worst_shooter": "195", "shooting": {"195": 0.314}})
    assert c["anchor"]["key"] == "ohio" and "31.4%" in c["line"] and "Ohio" in c["line"]
    assert dc.bricksanity_call(slate(), None) is None
    assert dc.bricksanity_call(slate(), {"worst_shooter": "9003"}) is None, "only our schools have anchors"


# ---------------------------------------------------------------- beat the desk

def test_ratings_win_home_matches_model_shape():
    p = dc.ratings_win_home(RATINGS, "2099", "9001")
    assert 0.55 < p < 0.65
    assert abs(dc.ratings_win_home(RATINGS, "2099", "9001", neutral=True) - 0.5) < 1e-9
    assert dc.ratings_win_home(RATINGS, "2099", "nope") is None and dc.ratings_win_home(None, "1", "2") is None


def test_real_ratings_file_loads():
    r = dc.load_ratings()
    assert r and r["teams"]
    t = r["teams"]
    assert 0 <= dc.ratings_win_home(r, t[0]["id"], t[-1]["id"]) <= 1


def test_desk_rotates_over_anchors_playing_pickable_games():
    keys = [dc.desk_anchor(slate(d))[0] for d in ("2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25")]
    assert keys == ["akron", "kent-state", "ohio", "toledo", "canisius", "akron"], "roster order, Iona has no win chance"
    assert dc.desk_anchor({"date": "2026-11-22", "games": [slate()["games"][4]]}) is None


def test_desk_pick4_homer_first_then_biggest_ratings_gaps():
    d = dc.desk_pick4(slate(), RATINGS)
    assert d["anchor"]["key"] == "ohio"
    p = d["picks"]
    assert [x["game_id"] for x in p] == ["2", "5", "1", "3"]
    assert p[0] == {**p[0], "side": "away", "team_id": "195", "kind": "homer", "worth": 90}
    assert p[1]["side"] == "home" and p[1]["kind"] == "ratings" and "market 30%" in p[1]["why"]
    assert p[2]["side"] == "away" and p[2]["abbr"] == "KENT", "ratings side, not the market favorite"
    assert d["max"] == sum(x["worth"] for x in p)
    assert dc.desk_pick4(slate(), RATINGS) == d, "deterministic"


def test_desk_fills_with_closest_market_games_without_ratings():
    p = dc.desk_pick4(slate(), None)["picks"]
    assert [x["game_id"] for x in p] == ["2", "4", "3", "1"]
    assert [x["kind"] for x in p] == ["homer", "market", "market", "market"]
    assert p[1]["side"] == "home" and p[3]["side"] == "home"


def test_homer_picks_cover_every_anchor_in_a_pickable_game():
    h = dc.homer_picks(slate())
    assert sorted(x["key"] for x in h) == ["akron", "canisius", "kent-state", "ohio", "toledo"]
    assert next(x for x in h if x["key"] == "kent-state")["side"] == "away"


def test_score_picks():
    p = dc.desk_pick4(slate(), RATINGS)["picks"]
    res = {"games": [{"id": "2", "final": True, "winner_id": "195"}, {"id": "5", "final": True, "winner_id": "9004"}]}
    s = dc.score_picks(p, res)
    assert s == {"points": 90, "hits": 1, "graded": 2, "marks": [True, False, None, None]}


def test_ledger_freezes_after_first_desk_tip(tmp_path):
    sl = slate()
    first = dc.update_ledger(sl, RATINGS, EARLY, tmp_path)
    assert (tmp_path / "2026-11-22.json").exists() and first["desk"]["anchor"]["key"] == "ohio"
    # Before tip a ratings change can move picks.
    again = dc.update_ledger(sl, None, EARLY, tmp_path)
    assert [x["kind"] for x in again["desk"]["picks"]][1:] == ["market"] * 3
    # Ohio's game tips at 23:00Z: from then on the stored desk stands, whatever the ratings say.
    mid = datetime(2026, 11, 22, 23, 30, tzinfo=timezone.utc)
    locked = dc.update_ledger(sl, RATINGS, mid, tmp_path)
    assert locked["desk"] == again["desk"]
    # Homer picks freeze game by game: game 2 tipped, so a changed line does not move its worth.
    sl["games"][1]["worth"] = {"home": 20, "away": 80}
    sl["games"][1]["win_home"] = 0.8
    h = dc.update_ledger(sl, RATINGS, mid, tmp_path)["homer"]
    assert next(x for x in h if x["key"] == "ohio")["worth"] == 90
    assert next(x for x in h if x["key"] == "akron")["worth"] == 40


def test_standings_from_ledgers():
    led = {"date": "2026-11-22", "desk": dc.desk_pick4(slate(), RATINGS), "homer": dc.homer_picks(slate())}
    res = {"games": [{"id": g, "final": True, "winner_id": w} for g, w in
                     [("1", "2309"), ("2", "195"), ("3", "2099"), ("4", "9002"), ("5", "9003")]]}
    s = dc.standings([led], {"2026-11-22": res})
    assert s["desk"][0]["key"] == "ohio" and s["desk"][0]["points"] == 90 + 70 + 60 + 45 and s["desk"][0]["hits"] == 4
    top = s["homer"][0]
    assert top["key"] == "ohio" and top["points"] == 90
    assert {r["key"]: r["wins"] for r in s["homer"]} == {"ohio": 1, "kent-state": 1, "canisius": 1, "akron": 0, "toledo": 0}
    assert dc.standings([led], {})["desk"] == [], "ungraded nights do not count"
    assert "fictional AI personas" in s["disclosure"]


# ---------------------------------------------------------------- the page

def test_connect_and_build(tmp_path):
    tix = {"1": {"url": "https://www.vividseats.com/a/production/9?wsUser=717", "low": 22}}
    c = dc.connect(slate(), ratings=RATINGS, tickets=tix, now=EARLY)
    assert c["cards"]["1"]["host"]["key"] == "akron" and c["cards"]["5"]["host"] is None
    assert c["cards"]["1"]["tickets"] is None and c["going"] == [] and c["tickets_on"] is False
    on = dc.connect(slate(), ratings=RATINGS, tickets=tix, now=EARLY, template="https://vivid-seats.pxf.io/c/1/2/3")
    assert on["going"][0]["game_id"] == "1" and on["tickets_on"] is True
    assert c["desk"]["locked"] is False and c["desk"]["score"] is None

    site, ledger = tmp_path / "site", tmp_path / "ledger"
    out = dc.build(site, slate(), {"games": [{"id": "2", "final": True, "winner_id": "195"}]}, now=LATE, ledger_dir=ledger)
    assert out["desk"]["locked"] is True and out["desk"]["score"]["points"] == 90
    assert json.loads((site / "den" / "connect-2026-11-22.json").read_text())["date"] == "2026-11-22"
    assert (site / "den" / "anchors" / "akron.webp").exists() and not (site / "den" / "anchors" / "canisius.webp").exists()
    assert "homer" in json.loads((site / "den" / "desk-standings.json").read_text())


def _env():
    return Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))


def test_partial_renders_everything():
    from mac.site_chrome import AD
    tix = {"1": {"url": "https://www.vividseats.com/a/production/9?wsUser=717", "low": 22}}
    c = dc.connect(slate(), ratings=RATINGS, tickets=tix, now=EARLY, template="https://vivid-seats.pxf.io/c/1/2/3")
    c["bricksanity"] = dc.bricksanity_call(slate(), {"worst_shooter": "2099", "shooting": {"2099": 28.0}})
    led = {"date": "2026-11-22", "desk": c["desk"], "homer": dc.homer_picks(slate())}
    st = dc.standings([led], {"2026-11-22": {"games": [{"id": "2", "final": True, "winner_id": "195"}]}})
    tpl = _env().from_string(
        '{% import "_den_connect.html" as dc %}{{ dc.styles() }}{{ dc.host(c.cards["1"]) }}{{ dc.host(c.cards["3"]) }}'
        '{{ dc.ticket_link(c.cards["1"].tickets) }}{{ dc.desk(c.desk) }}{{ dc.bricks_call(c.bricksanity) }}'
        '{{ dc.partners(c.going, ad) }}{{ dc.board(st) }}{{ dc.disclosure(c.disclosure) }}')
    html = tpl.render(c=c, ad=AD, st=st)
    assert "Marcus Vance" in html and "AI anchor" in html and 'src="den/anchors/akron.webp"' in html
    assert 'class="dc-face mono"' in html and ">PB<" in html, "Canisius gets the monogram"
    assert html.count('rel="sponsored noopener"') == 3 and "717" not in html
    assert "Going to the game" in html and "JuiceBox Nation" in html and "Beat the Desk" in html
    assert "#d4146f" in html and "#ff5fa2" in html
    assert "28.0%" in html and "Homer Ledger" in html and "fictional AI personas" in html


def test_partial_quiet_when_off():
    c = dc.connect(slate(), ratings=RATINGS, tickets={}, now=EARLY)
    html = _env().from_string('{% import "_den_connect.html" as dc %}{{ dc.ticket_link(c.cards["1"].tickets) }}{{ dc.partners(c.going, none) }}{{ dc.board(none) }}').render(c=c)
    assert html.strip() == ""
