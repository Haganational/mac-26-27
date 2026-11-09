from mac.build import ats_board, mac_ats, school
from mac.news import headline_ok


def game(home_key, away_key, cover):
    return {"home": {"key": home_key, "abbr": "H"}, "away": {"key": away_key, "abbr": "A"}, "ats_cover": cover}


def test_mac_ats_from_each_mac_side():
    assert mac_ats(game("ohio", None, "home")) == [{"key": "ohio", "abbr": "H", "res": "y"}]
    assert [m["res"] for m in mac_ats(game("ohio", "toledo", "away"))] == ["n", "y"]
    assert mac_ats(game(None, "akron", None))[0]["res"] is None


def test_ats_board_counts_and_sorts():
    recent = [{"mac_ats": mac_ats(game("ohio", None, "home"))}, {"mac_ats": mac_ats(game("ohio", "toledo", "push"))},
              {"mac_ats": mac_ats(game(None, "akron", "home"))}]
    rows = {r["key"]: r for r in ats_board(recent)}
    assert (rows["ohio"]["w"], rows["ohio"]["l"], rows["ohio"]["p"]) == (1, 0, 1)
    assert rows["akron"]["l"] == 1 and "buffalo" not in rows
    assert ats_board(recent)[0]["key"] == "ohio"


def test_school_drops_mascot():
    assert school("Cleveland State Vikings") == "Cleveland State"
    assert school("Penn State Schuylkill Nittany Lions") == "Penn State Schuylkill"


def test_other_sports_through_google_are_dropped():
    g = "https://news.google.com/rss/articles/x"
    assert not headline_ok("Miami Beats UMass 2-1 (OT) to Win Ninth-Straight MAC Tournament", "athletics", "miami-oh", g)
    assert not headline_ok("W.Basketball | BGSU Notes | Nov. 4, 2026", "athletics", "bowling-green", g)
    assert headline_ok("Men's Basketball vs Bellarmine on 11/07/26 - Box Score", "athletics", "miami-oh", g)
