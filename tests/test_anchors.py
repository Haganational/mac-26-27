import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from mac import anchors
from mac.leagues import MAC

CAST = [
    {"key": "sully", "name": "Sully Brennan", "tag": "The Homer", "bias": "home", "color": "#900"},
    {"key": "dee", "name": "Dee Marchetti", "tag": "The Dog", "bias": "underdog", "color": "#090"},
    {"key": "ivy", "name": "Ivy Calloway", "tag": "The Number", "bias": "model", "color": "#009"},
]


def _game(gid, tip, conf=False, home_key="akron", away_key=None, completed=False, hs=None, as_=None):
    return {"game_id": gid, "date": tip, "conference_game": conf, "neutral_site": False, "completed": completed,
            "venue": "JAR", "venue_city": "Akron", "broadcasts": [{"name": "ESPN+"}],
            "home": {"espn_id": "2006", "key": home_key, "name": "Akron Zips", "abbr": "AKR", "score": hs},
            "away": {"espn_id": "2199", "key": away_key, "name": "Eastern Michigan Eagles", "abbr": "EMU", "score": as_}}


def _league(tmp_path, monkeypatch, games, proj):
    import mac.leagues as leagues
    monkeypatch.setattr(leagues, "ROOT", tmp_path)
    lg = replace(MAC, key="tst", path="t/")
    d = lg.data_dir
    (d / "model").mkdir(parents=True)
    (d / "schedule.json").write_text(json.dumps({"games": games}))
    (d / "model" / "projections.jsonl").write_text("\n".join(json.dumps(p) for p in proj) + "\n")
    monkeypatch.setattr(anchors, "ALL", {"tst": lg})
    return lg, d


def test_pick_prefers_conference_then_closest():
    rows = [
        {"g": {"conference_game": False, "date": "2026-11-13T23:00Z"}, "p": {"proj_margin": 0.5}},
        {"g": {"conference_game": True, "date": "2026-11-14T00:00Z"}, "p": {"proj_margin": -6.0}},
        {"g": {"conference_game": True, "date": "2026-11-13T23:30Z"}, "p": {"proj_margin": 3.0}},
    ]
    assert anchors.pick(rows) is rows[2]
    assert anchors.pick([]) is None


def test_late_tip_belongs_to_the_night_before():
    assert anchors.et_date(datetime(2026, 11, 14, 5, 30, tzinfo=timezone.utc)) == "2026-11-13"  # 12:30 a.m. ET


def test_review_gate():
    night = {"date": "2026-11-13", "game": {"game_id": "1"}, "comments": [
        {"id": "sully-pre", "who": "sully", "phase": "pre", "text": "a", "written_at": "2026-11-13T20:00:00Z"},
        {"id": "dee-pre", "who": "dee", "phase": "pre", "text": "b", "written_at": "2026-11-13T20:00:00Z"},
        {"id": "ivy-pre", "who": "ivy", "phase": "pre", "text": "c", "written_at": "2026-11-13T20:00:00Z"}]}
    cfg = {**anchors.DEFAULT_CONFIG}
    review = {"approve": ["sully-pre", "dee-pre"], "hold": ["dee-pre"], "edit": {"sully-pre": "edited"},
              "matthew": [{"id": "m1", "at": "2026-11-13T21:00:00Z", "text": "Real me here."}]}
    t = anchors.thread(night, CAST, cfg, review)
    assert [(x["kind"], x["text"]) for x in t["posts"]] == [("anchor", "edited"), ("human", "Real me here.")]
    assert t["pending"] == 1  # ivy-pre is waiting
    # auto-publish from a date lets unreviewed drafts through, but never a held one
    t = anchors.thread(night, CAST, {**cfg, "auto_publish_from": "2026-11-13"}, {**review, "approve": []})
    assert {x["id"] for x in t["posts"] if x["kind"] == "anchor"} == {"sully-pre", "ivy-pre"}


def test_advance_picks_writes_and_never_rewrites(tmp_path, monkeypatch):
    tip = "2026-11-13T23:00Z"
    games = [_game("g1", tip, conf=True), _game("g2", "2026-11-14T00:00Z")]
    proj = [{"game_id": "g1", "proj_margin": 2.0, "proj_total": 140, "win_prob_home": 0.6, "mkt_spread": -1.5},
            {"game_id": "g2", "proj_margin": 0.1, "proj_total": 150, "win_prob_home": 0.5, "mkt_spread": None}]
    lg, d = _league(tmp_path, monkeypatch, games, proj)
    nights = tmp_path / "nights"
    early = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)  # 7 a.m. ET: too early to pick
    assert anchors.advance(early, CAST, nights, [lg]) is None
    morning = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)
    n = anchors.advance(morning, CAST, nights, [lg])
    assert n["game"]["game_id"] == "g1" and n["comments"] == []  # conference game first; takes wait for tip - 4h
    n = anchors.advance(datetime(2026, 11, 13, 20, 0, tzinfo=timezone.utc), CAST, nights, [lg])
    assert [c["id"] for c in n["comments"]] == ["sully-pre", "dee-pre", "ivy-pre"]
    assert "Akron" in n["comments"][0]["text"]  # the homer takes the home team
    first = json.loads((nights / "2026-11-13.json").read_text())
    # the schedule changes later in the day; the pick and the takes stay put
    (d / "schedule.json").write_text(json.dumps({"games": [_game("g1", tip, completed=True, hs=70, as_=68)]}))
    box = {"teams": [{"espn_id": "2006", "stats": {"totalRebounds": "40", "totalTurnovers": "9", "fieldGoalPct": "47"}},
                     {"espn_id": "2199", "stats": {"totalRebounds": "31", "totalTurnovers": "14", "fieldGoalPct": "39"}}],
           "players": [{"team_espn_id": "2006", "name": "A Player", "pts": 21, "dnp": False}]}
    (d / "boxscores").mkdir()
    (d / "boxscores" / "g1.json").write_text(json.dumps(box))
    n = anchors.advance(datetime(2026, 11, 14, 2, 0, tzinfo=timezone.utc), CAST, nights, [lg])
    assert n["comments"][:3] == first["comments"]
    assert [c["id"] for c in n["comments"][3:]] == ["sully-post", "dee-post", "ivy-post"]
    assert n["final"]["winner"] == "Akron" and n["final"]["cover"] == "Akron"
    again = anchors.advance(datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc), CAST, nights, [lg])
    assert again["comments"] == n["comments"]


def test_every_anchor_comment_renders_with_ai_badge():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(anchors.ROOT / "templates")), autoescape=True)
    night = {"date": "2026-11-13", "why": "Close one.", "game": {"game_id": "1", "tip_et": "7:00 p.m. ET", "path": "games/1.html",
             "home": "Akron", "away": "Kent State"},
             "comments": [{"id": "ivy-pre", "who": "ivy", "phase": "pre", "text": "Numbers.", "written_at": "2026-11-13T20:00:00Z"}]}
    t = anchors.thread(night, CAST, {**anchors.DEFAULT_CONFIG}, {"approve": ["ivy-pre"], "hold": [], "edit": {}, "matthew": []})
    html = env.from_string('{% import "_courtside.html" as C %}{{ C.panel(t) }}').render(t=t, site_url="")
    assert html.count('cs-item anchor') == 1 and "AI anchor</span>" in html and "Hide AI anchors" in html
