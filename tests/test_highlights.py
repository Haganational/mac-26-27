from datetime import datetime, timezone

from mac import highlights as H


def _item(cid, headline, event, full=True, kind="Media"):
    cats = [{"type": "team", "teamId": 2717, "description": "Western Carolina Catamounts"},
            {"type": "league", "leagueId": 41}]
    if full:
        cats.append({"type": "editorialindicator", "description": "SC4U - Full Highlight"})
    if event:
        cats.append({"type": "event", "eventId": event, "description": "Away @ Home"})
    return {"id": cid, "type": kind, "headline": headline, "published": "2026-11-12T01:07:23Z", "categories": cats}


def test_parse_keeps_highlights_tied_to_one_game():
    got = H.parse([
        _item(50456883, "VU of Lynchburg Dragons vs. Western Carolina Catamounts: Game Highlights", 401926206),
        _item(1, "Coach on the win", 401926206),                  # not a highlight
        _item(2, "Game Highlights", None),                        # no game attached
        _item(3, "Recap: Game Highlights", 5, kind="Recap"),      # not a video
    ])
    assert list(got) == ["401926206"]
    assert got["401926206"]["id"] == "50456883" and got["401926206"]["full"]


def test_full_package_beats_a_single_play_clip():
    got = H.parse([_item(10, "Big dunk highlight", 7, full=False), _item(11, "A vs. B: Game Highlights", 7)])
    assert got["7"]["id"] == "11"


def test_only_recent_finals_without_a_clip_are_asked_about():
    now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
    g = lambda gid, date, done=True: {"game_id": gid, "date": date, "completed": done,
                                       "home": {"espn_id": "1", "key": "akron"}, "away": {"espn_id": "9", "key": None}}
    games = [g("a", "2026-11-12T00:00Z"), g("b", "2026-11-09T00:00Z"), g("c", "2026-11-12T00:00Z", False), g("d", "2026-11-11T23:00Z")]
    assert H.due_teams(games, {"d": {}}, now) == ["1"], "only our team's feed, once, for the recent final with no clip"


def test_refresh_stores_new_clips_and_embed_url(tmp_path):
    f = tmp_path / "hl.json"
    games = [{"game_id": "401926206", "date": "2026-11-12T00:00Z", "completed": True,
              "home": {"espn_id": "2717", "key": "wcu"}, "away": {"espn_id": "5", "key": None}}]
    out = H.refresh(games, datetime(2026, 11, 12, 3, tzinfo=timezone.utc), f,
                    fetch=lambda tid: [_item(50456883, "A vs. B: Game Highlights", 401926206)])
    assert out == {"asked": 1, "new": 1, "total": 1}
    hl = H.for_game("401926206", H.load(f))
    assert hl["embed"] == "https://www.espn.com/core/video/iframe/_/id/50456883/endcard/false"
    assert H.for_game("nope", H.load(f)) is None
    # a failing feed never raises
    assert H.refresh(games, datetime(2026, 11, 12, 3, tzinfo=timezone.utc), tmp_path / "x.json", fetch=lambda t: 1 / 0)["new"] == 0
