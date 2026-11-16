"""The Bricks Score that orders the cover and edition fronts (Matthew, Nov 16 2026: "blend")."""
from mac import frontscore
from mac.leagues import ALL


def _t(conf, key):
    return next(t for t in ALL[conf].teams if t.key == key)


def _side(team, score, won, conf=True):
    return {"espn_id": team.espn_id if conf else team, "key": team.key if conf else None,
            "name": team.short if conf else "Outsider", "score": score, "winner": won}


def _game(gid, home, away, day="2026-11-15", detail="Final"):
    return {"game_id": gid, "date": f"{day}T23:00Z", "home": home, "away": away, "completed": True, "detail": detail,
            "neutral_site": False}


def _scorer(games, spreads=(), ranks=None):
    ratings = {"teams": [{"id": k, "rk_adj_em": v} for k, v in (ranks or {}).items()]}
    return frontscore.Scorer(games={g["game_id"]: g for g in games}, ratings=ratings, spreads=lambda day: list(spreads))


def _stories(*gids):
    return [{"href": f"games/{g}.html", "kind": "recap", "id": g} for g in gids]


def test_an_upset_outscores_a_routine_win_and_a_rout_sinks():
    bradley, mason, drake, siu = _t("mvc", "bradley"), _t("a10", "george-mason"), _t("mvc", "drake"), _t("mvc", "southern-illinois")
    games = [_game("1", _side(bradley, 62, True), _side(mason, 61, False)),
             _game("2", _side(drake, 80, True), _side(siu, 70, False)),
             _game("3", _side(drake, 101, True), _side("999999", 50, False, conf=False))]
    spreads = [{"points": 12.0, "fav_key": "george-mason", "dog_key": "bradley"},
               {"points": 4.0, "fav_key": "drake", "dog_key": "southern-illinois"}]
    sc = _scorer(games, spreads)
    one = sc.score("1")
    assert one["upset"] == 40 and one["drama"] == 15 and one["why"] == "12-point underdog"
    assert sc.score("3")["rout"] == -25
    assert [s["id"] for s in frontscore.rank(_stories("3", "2", "1"), sc)] == ["1", "2", "3"]


def test_home_weights_and_the_ohio_floor():
    ohio, toledo = _t("mac", "ohio"), _t("mac", "toledo")
    akron = _t("mac", "akron")
    csu, oak = _t("horizon", "cleveland-state"), _t("horizon", "oakland")
    sc = _scorer([_game("9", _side(ohio, 60, False), _side(toledo, 80, True))])
    assert sc.score("9")["home"] == 20
    assert sc.home_weight(_game("x", _side(akron, 1, True), _side(toledo, 0, False))) == 15
    assert sc.home_weight(_game("x", _side(csu, 1, True), _side(oak, 0, False))) == 12
    assert sc.home_weight(_game("x", _side(oak, 1, True), _side("999", 0, False, conf=False))) == 4
    # On the Horizon front only Cleveland State carries weight; on another edition's front nobody does.
    assert sc.home_weight(_game("x", _side(csu, 1, True), _side(oak, 0, False)), edition="horizon") == 12
    assert sc.home_weight(_game("x", _side(ohio, 1, True), _side(toledo, 0, False)), edition="horizon") == 0
    # Five upsets outscore an Ohio blowout loss, but Ohio stays in the top three.
    teams = [t for t in ALL["mvc"].teams][:10]
    games = [_game(str(i), _side(teams[2 * i], 70, True), _side(teams[2 * i + 1], 69, False)) for i in range(5)]
    spreads = [{"points": 10.0, "fav_key": teams[2 * i + 1].key, "dog_key": teams[2 * i].key} for i in range(5)]
    games.append(_game("9", _side(ohio, 60, False), _side(toledo, 80, True)))
    order = [s["id"] for s in frontscore.rank(_stories("0", "1", "2", "3", "4", "9"), _scorer(games, spreads))]
    assert order.index("9") == 2


def test_floors_keep_the_score_order_otherwise():
    pool = [{"n": i} for i in range(8)]
    due = {id(pool[7]): 2, id(pool[6]): 5}
    assert [s["n"] for s in frontscore.floors(pool, due)] == [0, 1, 7, 2, 3, 6, 4, 5]


def test_unscored_and_older_stories_fall_back_to_newest_first():
    bradley, mason = _t("mvc", "bradley"), _t("a10", "george-mason")
    sc = _scorer([_game("1", _side(bradley, 62, True), _side(mason, 61, False), day="2026-11-15")])
    st = [{"href": "games/77.html", "kind": "recap", "id": "77"}, {"href": "games/5.html", "kind": "preview", "id": "p"}] + _stories("1")
    assert [s["id"] for s in frontscore.rank(st, sc)] == ["1", "77", "p"]
    assert frontscore.rank(st, None) == st
