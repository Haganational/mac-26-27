from datetime import datetime, timezone

from mac import social


def it(url, title, when):
    return {"url": url, "title": title, "published": when, "kind": social.kind(title), "page": None, "league": "MAC"}


def test_due_fresh_unposted_capped():
    now = datetime(2026, 11, 12, 3, 0, tzinfo=timezone.utc)
    items = [it("u1", "Akron rolled past Kent State 80-60", "2026-11-12T02:30:00Z"),
             it("u1", "Kent State vs. Akron prediction: model has Akron by 7", "2026-11-11T22:00:00Z"),
             it("u2", "Ohio beat Toledo 70-66", "2026-11-11T12:00:00Z"),  # too old
             it("u3", "Buffalo edged Ball State 61-60", "2026-11-12T01:00:00Z")]
    out = social.due(items, {"u3|recap": "x"}, now)
    assert [(o["url"], o["kind"]) for o in out] == [("u1", "preview"), ("u1", "recap")]
    assert len(social.due(items, {}, now, most=1)) == 1


def test_text_and_tag_facets():
    t = social.text_for(it("u", "Akron rolled past Kent State 80-60", "x"))
    assert t.startswith("Akron rolled past Kent State 80-60") and "#MAC" in t
    f = social._facets(t)
    assert {x["features"][0]["tag"] for x in f} == {"MAC", "CollegeBasketball"}
    b = t.encode()
    assert all(b[x["index"]["byteStart"]:x["index"]["byteEnd"]].startswith(b"#") for x in f)


def test_skips_without_secrets(monkeypatch):
    monkeypatch.delenv("BSKY_HANDLE", raising=False)
    monkeypatch.delenv("SOCIAL_DRY_RUN", raising=False)
    assert "skipped" in social.run()
