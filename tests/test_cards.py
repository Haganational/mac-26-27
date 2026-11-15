import json

from mac import cardpost, cards
from mac.leagues import ALL


def _row(**kw):
    lg = ALL["mac"]
    t = lg.teams[0]
    r = {"gs": 20.0, "name": "Test Player", "pts": 28, "reb": 12, "ast": 3, "fgm": 9, "fga": 14, "tpm": 1, "stl": 1, "blk": 0,
         "team": t, "league": lg, "won": True, "us": 79, "them": 74, "opp": "Brown", "home": True, "neutral": False, "game_id": "1"}
    r.update(kw)
    return r


def test_game_score_rewards_efficiency():
    good = {"pts": 20, "fgm": 8, "fga": 10, "ftm": 4, "fta": 4}
    bad = {"pts": 20, "fgm": 8, "fga": 22, "ftm": 4, "fta": 8}
    assert cards.game_score(good) > cards.game_score(bad)


def test_stat_line_picks_the_double():
    assert cards.stat_line(_row()) == ("28·12", "points · rebounds")
    assert cards.stat_line(_row(reb=4, ast=8)) == ("28·8", "points · assists")
    assert cards.stat_line(_row(reb=4)) == ("28", "points")


def test_result_line_home_road_and_loss():
    assert cards.result_line(_row()) == "beat Brown 79-74"
    assert cards.result_line(_row(home=False)) == "won 79-74 at Brown"
    assert cards.result_line(_row(won=False, us=70, them=75)) == "lost to Brown 75-70"


def test_potn_card_has_a_cover_and_varied_captions():
    c = cards.potn_card("2026-11-14", [_row(), _row(name="Other Guy", pts=30, reb=4, ast=7)])
    assert len(c.slides) == 3 and len(c.alt) == 3
    heads = {cardpost.first_line(t) for t in c.captions.values()}
    assert len(heads) == len(c.captions)  # no two networks open with the same line
    assert cards.DISCLOSURE in c.captions["instagram"]
    assert len(c.captions["bluesky"]) <= 300 and len(c.captions["threads"]) <= 500
    assert cards.potn_card("2026-11-14", []) is None


def test_routes_and_secrets(tmp_path):
    man = {"captions": {"instagram": "a", "facebook": "b", "threads": "c", "bluesky": "d"}}
    env = {"FB_PAGE_ID": "1", "FB_PAGE_TOKEN": "t", "IG_USER_ID": "2", "BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "p"}
    assert cardpost.networks("potn", man, env) == ["instagram", "facebook", "bluesky"]
    assert cardpost.networks("slate", man, env) == ["bluesky"]
    assert cardpost.networks("desk", man, {}) == []


def test_dry_run_posts_nothing(tmp_path, monkeypatch, capsys):
    (tmp_path / "slate.json").write_text(json.dumps({"kind": "slate", "files": ["slate-1.jpg"], "captions": {"threads": "x", "bluesky": "y"}}))
    monkeypatch.setenv("SOCIAL_DRY_RUN", "1")
    assert cardpost.run(tmp_path, "slate", "cards-test") == 0
    assert "would post to" in capsys.readouterr().out
    assert cardpost.run(tmp_path, "desk", "cards-test") == 0  # no card, nothing to do


def test_one_failure_does_not_stop_the_rest(tmp_path, monkeypatch):
    (tmp_path / "desk.json").write_text(json.dumps({"kind": "desk", "files": ["d.jpg"], "captions": {"facebook": "f", "bluesky": "b"}}))
    for k, v in {"FB_PAGE_ID": "1", "FB_PAGE_TOKEN": "t", "BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "p"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("SOCIAL_DRY_RUN", raising=False)
    seen = []

    def fake(net, man, folder, tag):
        seen.append(net)
        if net == "facebook":
            raise RuntimeError("boom")
        return "posted"
    monkeypatch.setattr(cardpost, "post_one", fake)
    monkeypatch.setattr(cardpost.alert, "send", lambda *a, **k: None)
    assert cardpost.run(tmp_path, "desk", "cards-test") == 1
    assert seen == ["facebook", "bluesky"]


def test_marked_networks_are_skipped(tmp_path, monkeypatch):
    (tmp_path / "potn.json").write_text(json.dumps({"kind": "potn", "files": ["p.jpg"], "captions": {"threads": "t", "bluesky": "b"}}))
    for k, v in {"THREADS_ACCESS_TOKEN": "t", "BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "p"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("SOCIAL_DRY_RUN", raising=False)
    seen, marked = [], []
    monkeypatch.setattr(cardpost, "marks", lambda tag: {"posted-potn-threads.txt"})
    monkeypatch.setattr(cardpost, "mark", lambda tag, kind, net, result: marked.append(net))
    monkeypatch.setattr(cardpost, "post_one", lambda net, *a: seen.append(net) or "posted 1")
    assert cardpost.run(tmp_path, "potn", "cards-test") == 0
    assert seen == ["bluesky"] and marked == ["bluesky"]
