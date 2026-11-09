from datetime import datetime, timezone

from mac import notes


def _write(d, name, text):
    (d / name).write_text(text)


def test_filing_kinds_and_feed(tmp_path):
    _write(tmp_path, "README.md", "# not a dispatch")
    _write(tmp_path, "2026-11-08-401-2130.md", "---\nkind: tv   # phone, paper, tv or arena\ngame: 401\ntitle: Game note\n---\nHello **there**.")
    _write(tmp_path, "2026-11-08-ohio-2200.md", "---\nkind: Newspaper\nteam: ohio\n---\nTeam note with no title.")
    _write(tmp_path, "2026-11-08-77-0900.md", "---\nkind: telephone\nplayer: 77   # Some Player\n---\nPlayer note.")
    _write(tmp_path, "2026-11-09-draft.md", "---\ndraft: true\n---\nNot yet.")
    ds = notes.load(tmp_path, game_teams={"401": ["ohio", "akron"]})
    assert [d["slug"] for d in ds] == ["2026-11-08-ohio-2200", "2026-11-08-401-2130", "2026-11-08-77-0900"]
    game = ds[1]
    assert game["kind"] == "tv" and game["teams"] == ["ohio", "akron"] and "<strong>there</strong>" in game["html"]
    assert ds[0]["kind"] == "paper" and ds[2]["kind"] == "phone" and ds[2]["player"] == "77"
    assert [d["slug"] for d in notes.for_team(ds, "akron")] == ["2026-11-08-401-2130"]
    assert set(notes.by_player(ds)) == {"77"}
    # 21:30 Eastern on Nov 8 is 02:30 UTC on Nov 9.
    assert game["published"] == "2026-11-09T02:30:00+00:00"
    view = {"headlines": [{"title": "x", "published": "2026-11-09T01:00:00+00:00", "teams": []}], "total": 1}
    merged = notes.merge_feed(view, ds, datetime(2026, 11, 9, 5, tzinfo=timezone.utc))
    assert merged["headlines"][0]["mine"] and merged["headlines"][0]["title"] == "Team note with no title."
    team_only = notes.merge_feed({"headlines": []}, ds, datetime(2026, 11, 9, 5, tzinfo=timezone.utc), team_key="akron")
    assert [h["title"] for h in team_only["headlines"]] == ["Game note"]


def test_markdown_escapes_html():
    out = notes.render_markdown("Hi <script>alert(1)</script> [x](javascript:alert(1)) [ok](https://a.b)")
    assert "<script>" not in out
    assert 'href="https://a.b"' in out and 'href="javascript' not in out
