import json

import pytest

from mac import lockcall


def _script(**over):
    lines = ([{"part": "hook", "who": "leslie", "text": "Best line first!"}, {"part": "open", "who": "leslie", "text": "a" * 300}, {"part": "open", "who": "brett", "text": "b" * 300},
              {"part": "picks", "who": "merv", "text": "c" * 200}, {"part": "picks", "who": "edwin", "text": "d" * 200},
              {"part": "board", "who": "leslie", "text": "e" * 200},
              {"part": "close", "who": "brett", "text": "Call 1-800-GAMBLER. " + "f" * 200}])
    return {"lines": lines, "notes": {"news": {"item": "x", "sources": ["https://example.com"]}}, **over}


def test_good_script_passes():
    assert lockcall.check(_script()) == []


def test_needs_a_sourced_news_item():
    assert any("source" in p for p in lockcall.check(_script(notes={})))


def test_parts_must_run_in_order():
    s = _script()
    s["lines"].reverse()
    assert any("parts must run" in p for p in lockcall.check(s))


def test_pilot_script_is_ready():
    pilot = json.loads((lockcall.POD_DIR / "2026-11-22.json").read_text())
    assert lockcall.check(pilot) == []


def test_facts_come_from_the_cards():
    from mac import tops
    pick = {"label": "Under 140", "matchup": "A at B", "kind": "total", "why": "w"}
    for day, result in (("2026-11-21", "win"), ("2026-11-22", None)):
        card = {"date": day, "picks": {c["key"]: [dict(pick, result=result)] for c in tops.CAPPERS}}
        (tops.TOPS_DIR / f"{day}.json").write_text(json.dumps(card))
    f = lockcall.facts("2026-11-22")
    assert set(f["picks"]) == {c["key"] for c in tops.CAPPERS}
    assert all(r["record"] == "1-0" for r in f["board"])  # the board stops at yesterday
    assert f["yesterday"]["date"] == "2026-11-21"
    assert "error" in lockcall.facts("2026-11-23")


def test_posted_episode_has_its_audio_and_notes():
    ctx = lockcall.page_context()
    ep = ctx["lockcall"]
    assert ":" in ep["length"]
    daily = next(e for e in lockcall.episodes() if not e.get("bonus") and not e.get("pilot"))
    assert daily["news"]["sources"]  # a daily show carries its news source; a bonus skit may have none
    pilot = lockcall.episodes()[-1]
    assert pilot["pilot"] and pilot["length"] == "2:10"
    assert (lockcall.POD_DIR.parent.parent / "templates" / ep["audio"]).exists()
    assert ctx["lockcall_feed"] == "podcast/feed.xml"


def test_feed_is_valid_rss_with_what_the_directories_need(tmp_path):
    import xml.etree.ElementTree as ET
    out = lockcall.write_feed(tmp_path, "https://hardwoodbricks.com/")
    ch = ET.parse(out).getroot().find("channel")
    it = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
    assert ch.findtext("title") == "Tops and Bottoms: The Lock Call"
    assert ch.find(f"{it}owner/{it}email").text and ch.find(f"{it}image").get("href").endswith("cover.jpg")
    enc = ch.find("item/enclosure")
    assert enc.get("url").startswith("https://hardwoodbricks.com/static/podcast/") and int(enc.get("length")) > 0
    assert ch.findtext("item/pubDate") and ch.findtext("item/guid")


def test_every_episode_opens_on_a_hook():
    s = _script()
    s["lines"] = s["lines"][1:]
    assert any("hook" in p for p in lockcall.check(s))


def test_publish_adds_a_row_and_replaces_the_same_day(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(lockcall, "POD_DIR", tmp_path / "data" / "podcast")
    monkeypatch.setattr(lockcall, "EPISODES", tmp_path / "data" / "podcast" / "episodes.json")
    lockcall.POD_DIR.mkdir(parents=True)
    script = lockcall.POD_DIR / "2026-11-23.json"
    script.write_text(json.dumps({"date": "2026-11-23", "title": "The Lock Call: Monday, November 23", "blurb": "A blurb."}))
    mp3 = tmp_path / "ep.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=d=2", str(mp3)], check=True)
    for _ in range(2):
        row = lockcall.publish(script, mp3)
    rows = json.loads(lockcall.EPISODES.read_text())
    assert [r["id"] for r in rows] == ["2026-11-23"] and row["seconds"] == 2
    assert (tmp_path / "templates" / row["audio"]).exists()
    script.write_text(json.dumps({"date": "2026-11-23", "title": "T", "blurb": "x" * 300}))
    with pytest.raises(ValueError):
        lockcall.publish(script, mp3)
