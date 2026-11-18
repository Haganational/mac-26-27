import random
from datetime import datetime, timezone

from mac import stories as s

RELS = [
    {"tag_name": "morris-promos", "published_at": "2026-11-18T18:19:59Z",
     "assets": [{"name": "morris-reel-1-crunch-time.mp4"}]},
    {"tag_name": "midmaxx60-2026-11-18", "published_at": "2026-11-18T13:36:07Z",
     "assets": [{"name": "midmaxx60-2026-11-18.mp4"}, {"name": "midmaxx60-2026-11-18-thumb.png"}]},
    {"tag_name": "cards-2026-11-18", "published_at": "2026-11-18T13:31:06Z",
     "assets": [{"name": "potn-2026-11-17-1.jpg"}, {"name": "slate-2026-11-18-1.jpg"}, {"name": "started.txt"}]},
    {"tag_name": "mac90-2026-11-13", "published_at": "2026-11-13T13:08:01Z", "assets": [{"name": "mac90-2026-11-13.mp4"}]},
    {"tag_name": "bigmid-2026-11-16", "published_at": "2026-11-16T23:33:54Z", "assets": [{"name": "bigmid-2026-11-16.mp4"}]},
]
NOW = datetime(2026, 11, 18, 21, 10, tzinfo=timezone.utc)  # 4:10 PM Eastern


def led(**kw):
    return {"since": "2026-11-18T00:00:00+00:00", "posted": {}, "slots": {}, "log": [], **kw}


def test_library_keeps_verticals_and_timeless_cards():
    keys = {i.key for i in s.items_from(RELS)}
    assert keys == {"morris-promos/morris-reel-1-crunch-time.mp4", "midmaxx60-2026-11-18/midmaxx60-2026-11-18.mp4",
                    "cards-2026-11-18/potn-2026-11-17-1.jpg"}


def test_evergreen_never_storied_goes_first():
    items = s.items_from(RELS)
    for seed in range(20):
        assert s.pick(items, led(), NOW, random.Random(seed)).tag == "morris-promos"


def test_rested_items_avoid_repeats():
    items = s.items_from(RELS)
    posted = {i.key: ["2026-11-18T12:00:00+00:00"] for i in items}
    posted.pop("cards-2026-11-18/potn-2026-11-17-1.jpg")
    assert s.pick(items, led(posted=posted), NOW, random.Random(1)).name == "potn-2026-11-17-1.jpg"


def test_new_content_after_ledger_start():
    items = s.items_from(RELS)
    assert s.pick_new(items, led(), NOW).name == "midmaxx60-2026-11-18.mp4"
    assert s.pick_new(items, led(since="2026-11-18T20:00:00+00:00"), NOW) is None


def test_slots_and_extras():
    assert s.due_slot(led(), NOW) == "2026-11-18T16"
    assert s.due_slot(led(slots={"2026-11-18T16": "x"}), NOW) is None
    six = datetime(2026, 11, 18, 23, 5, tzinfo=timezone.utc)  # 6:05 PM, an extra hour today only
    assert s.due_slot(led(), six) == "2026-11-18T18"
    assert s.due_slot(led(), datetime(2026, 11, 20, 1, 5, tzinfo=timezone.utc)) is None


def test_networks():
    env = {"FB_PAGE_ID": "1", "FB_PAGE_TOKEN": "t", "IG_USER_ID": "2"}
    assert s.networks(env) == ["facebook", "instagram"]
    assert s.networks({**env, "STORY_NETWORKS": "facebook"}) == ["facebook"]
