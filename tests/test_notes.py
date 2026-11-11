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


def test_photos_parse_credit_and_copy(tmp_path):
    notes_dir = tmp_path / "dispatches"; notes_dir.mkdir()
    photos_dir = tmp_path / "photos"; photos_dir.mkdir()
    (photos_dir / "2026-11-08-ab12cd.jpg").write_bytes(b"jpg")
    (photos_dir / "unused.jpg").write_bytes(b"jpg")
    _write(notes_dir, "2026-11-08-401-2130.md",
           "---\ngame: 401\nauthor: Pat\nphoto: 2026-11-08-ab12cd.jpg | Tip-off at the JAR\n"
           "photo: ../../etc/passwd | nope\nphoto: missing.jpg\n---\n")
    ds = notes.load(notes_dir)
    assert len(ds) == 1, "a photo-only dispatch still publishes"
    ph = ds[0]["photos"]
    assert [p["file"] for p in ph] == ["2026-11-08-ab12cd.jpg", "missing.jpg"]
    assert ph[0] == {"file": "2026-11-08-ab12cd.jpg", "src": "photos/2026-11-08-ab12cd.jpg",
                     "caption": "Tip-off at the JAR", "credit": "Pat"}
    assert ds[0]["text"] == "Tip-off at the JAR"
    site = tmp_path / "site"
    assert notes.copy_photos(ds, site, photos_dir) == 1
    assert sorted(p.name for p in (site / "photos").iterdir()) == ["2026-11-08-ab12cd.jpg"]


def test_photo_credit_line_wins(tmp_path):
    _write(tmp_path, "2026-11-08-x.md", "---\nauthor: Pat\ncredit: Sam Lee\nphoto: a.jpg\n---\nBody.")
    assert notes.load(tmp_path)[0]["photos"][0]["credit"] == "Sam Lee"
