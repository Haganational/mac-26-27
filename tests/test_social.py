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


def test_seen_per_network():
    posted = {"https://x/g/1.html|recap": "t", "threads:https://x/g/2.html|recap": "t"}
    assert social.seen_for(posted, "") == {"https://x/g/1.html|recap": "t"}
    assert social.seen_for(posted, "threads:") == {"https://x/g/2.html|recap": "t"}


def test_threads_post(monkeypatch):
    calls = []

    class R:
        def __init__(self, j): self.j = j
        def raise_for_status(self): pass
        def json(self): return self.j

    def fake_post(url, data=None, **kw):
        calls.append((url, data))
        return R({"id": "c1"} if url.endswith("/threads") else {"id": "p1"})
    monkeypatch.setattr(social.requests, "post", fake_post)
    assert social.post_threads("42", "tok", it("https://x/g/1.html", "Akron beat Ohio 70-60", "x")) == "p1"
    assert calls[0][1]["link_attachment"] == "https://x/g/1.html" and calls[1][1]["creation_id"] == "c1"


def test_threads_needs_only_token(monkeypatch):
    for k in ("BSKY_HANDLE", "BSKY_APP_PASSWORD", "THREADS_USER_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
    assert [p for p, _ in social._networks()] == ["threads:"]


def test_failure_streak_alerts_once_a_day_and_clears_on_success():
    state = {}
    t0 = datetime(2026, 11, 12, 3, 0, tzinfo=timezone.utc)
    step = lambda i: t0.replace(hour=3 + i)  # noqa: E731
    assert social.track_failures(state, "bluesky", 2, 2, "HTTPError: 401", step(0)) is None
    assert social.track_failures(state, "bluesky", 0, 0, "", step(1)) is None  # nothing to post: streak untouched
    assert social.track_failures(state, "bluesky", 1, 1, "HTTPError: 401", step(1)) is None
    body = social.track_failures(state, "bluesky", 1, 3, "HTTPError: 401", step(2))
    assert body and "3 runs in a row" in body and "HTTPError: 401" in body
    assert social.track_failures(state, "bluesky", 1, 1, "HTTPError: 401", step(3)) is None  # already alerted today
    assert social.track_failures(state, "bluesky", 1, 1, "x", datetime(2026, 11, 13, 6, 0, tzinfo=timezone.utc))
    assert social.track_failures(state, "bluesky", 0, 2, "", step(5)) is None and state == {}


def test_run_emails_after_three_failed_runs(monkeypatch, tmp_path):
    import requests
    sent = []
    monkeypatch.setattr(social, "POSTED", tmp_path / "posted.json")
    monkeypatch.setattr(social, "FAILURES", tmp_path / "failures.json")
    monkeypatch.setattr(social.alert, "send", lambda subject, body: sent.append(subject) or True)
    now = datetime(2026, 11, 12, 3, 0, tzinfo=timezone.utc)
    story = {**it("u1", "Akron rolled past Kent State 80-60", "2026-11-12T02:30:00Z")}
    monkeypatch.setattr(social, "stories", lambda: [story])

    def boom(item, when):
        raise requests.HTTPError("401 Unauthorized")
    monkeypatch.setattr(social, "_networks", lambda: [("", boom)])
    monkeypatch.delenv("SOCIAL_DRY_RUN", raising=False)
    for _ in range(2):
        assert "bluesky 0/1" in social.run(now)
    assert sent == []
    social.run(now)
    assert sent == ["Social posts to bluesky keep failing"]
    monkeypatch.setattr(social, "_networks", lambda: [("", lambda item, when: "ok")])
    assert "bluesky 1/1" in social.run(now)
    assert (tmp_path / "failures.json").read_text().strip() == "{}"
