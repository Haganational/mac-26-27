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


def test_the_desk_installs_as_its_own_home_screen_app():
    import json
    from mac import site_chrome
    m = json.loads(site_chrome.desk_manifest())
    assert m["start_url"] == "./desk.html" and m["short_name"] == "HB Desk" and m["icons"]


def test_the_desk_has_dictation_camera_and_one_tap_games():
    from mac.config import TEMPLATES_DIR
    page = (TEMPLATES_DIR / "desk.html").read_text()
    for needle in ('id="dictate"', 'capture="environment"', 'id="gamechips"', "desk.webmanifest", "indexedDB.open('btb-desk'"):
        assert needle in page


def test_contributors_send_photos_and_the_editor_fills_them_from_the_email():
    from mac.config import TEMPLATES_DIR
    page = (TEMPLATES_DIR / "desk.html").read_text()
    assert "navigator.share(" in page and "navigator.canShare" in page  # dispatch + photos in one share sheet
    assert "ph.need" in page  # a pasted dispatch's photos wait for the emailed files before Publish


def test_a_masthead_byline_gets_a_face_and_a_masthead_link():
    from jinja2 import Environment, FileSystemLoader
    from mac.config import TEMPLATES_DIR
    from mac import hub
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    env.globals.update(nav_teams=[], feat=[], site_up="../", notes_kinds={"arena": ("Arena", "")}, notes_color={"arena": "#000"},
                       bylines={s["name"]: s for s in hub.staff({"staff": [
                           {"name": "Pat Writer", "title": "Contributor, Athens", "photo": "static/staff/pat-writer.jpg"}]})})
    tpl = env.from_string('{% import "_layout.html" as L %}{{ L.dispatches(items, root="../") }}')
    base = {"kind": "arena", "kind_label": "Arena", "slug": "s", "file": "s.md", "date": "2026-11-19", "teams": [], "html": "", "photos": [], "title": ""}
    html = tpl.render(items=[dict(base, author="Pat Writer"), dict(base, author="Someone Else", slug="t")])
    assert 'href="../../masthead.html#pat-writer"' in html and 'src="../../static/staff/pat-writer.jpg"' in html
    assert ", Contributor, Athens" in html and "By Someone Else</span></div>" in html


def test_articles_videos_and_conference_notes(tmp_path):
    _write(tmp_path, "2026-11-19-metro-1400.md", "---\nkind: arena\ntitle: Long read\nformat: article\nabout: conference\n"
           "video: dQw4w9WgXcQ | The Big Mid: Week 3\n---\nFirst graf.")
    _write(tmp_path, "2026-11-19-bad-1500.md", "---\nkind: tv\nvideo: not-a-video-id-at-all\n---\nNote.")
    art, note = notes.load(tmp_path)[1], notes.load(tmp_path)[0]
    assert art["article"] and art["href"] == "articles/2026-11-19-metro-1400.html" and art["about"] == "conference"
    assert art["video"] == {"id": "dQw4w9WgXcQ", "title": "The Big Mid: Week 3", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    assert note["video"] is None and note["href"] == "notes.html#n-2026-11-19-bad-1500"
    assert notes.feed_items([art])[0]["url"] == "articles/2026-11-19-metro-1400.html"


def test_the_plus_sign_files_to_the_conference_a_video_or_an_article():
    from jinja2 import Environment, FileSystemLoader
    from mac.config import TEMPLATES_DIR
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    env.globals.update(feat=["notes"])
    t = env.from_string('{% import "_layout.html" as L %}{{ L.add_dispatch("", "x", conf=True) }}|{{ L.add_dispatch("", "v", video="dQw4w9WgXcQ", vtitle="Big Mid: 3") }}|{{ L.add_dispatch("", "", article=True) }}')
    conf, vid, art = t.render().split("|")
    assert 'href="desk.html?conf=1"' in conf and "+</span>" in conf
    assert "video=dQw4w9WgXcQ&amp;vt=Big%20Mid%3A%203" in vid
    assert 'href="desk.html?article=1"' in art and "+ Article" in art


def test_a_dispatch_about_any_page_of_the_site():
    assert notes.ref_of("/tops.html | JuiceBox pick: Merv, UTEP -3") == {"url": "/tops.html", "title": "JuiceBox pick: Merv, UTEP -3"}
    assert notes.ref_of("/metro/power.html%23w3 | Power") == {"url": "/metro/power.html#w3", "title": "Power"}
    assert notes.ref_of("https://evil.example/x | nope") is None and notes.ref_of("//evil.example | nope") is None
    assert notes.ref_of("javascript:alert(1)") is None


def test_pin_until_absolute_and_relative():
    from datetime import datetime
    from mac import notes
    assert notes.pin_until({"pin_until": "2026-11-22T16:20Z"}, "2026-11-21-1120") == "2026-11-22T16:20:00+00:00"
    # pin: 12 counts from the dispatch's own time (11:20 AM ET on Nov 21 = 16:20 UTC)
    assert notes.pin_until({"pin": "12", "date": "2026-11-21"}, "2026-11-21-1120") == "2026-11-22T04:20:00+00:00"
    assert notes.pin_until({"pin": "500"}, "2026-11-21-1120") is None
    assert notes.pin_until({}, "2026-11-21-1120") is None and notes.pin_until({"pin_until": "soon"}, "x") is None


def test_a_dispatch_push_renders_only_its_own_editions(tmp_path):
    _write(tmp_path, "2026-11-27-1-1850.md", "---\nleague: ivy\n---\nFrom the Cathedral.")
    _write(tmp_path, "2026-11-27-1-1901.md", "---\nleague: CAA\n---\nPhilly specials.")
    _write(tmp_path, "2026-11-27-2-2000.md", "---\ntitle: MAC note\n---\nNo league means the MAC.")
    d = "notes/dispatches/"
    assert notes.editions_for([d + "2026-11-27-1-1850.md", d + "2026-11-27-1-1901.md", "notes/photos/a.jpg"], tmp_path) == {"ivy", "caa"}
    assert notes.editions_for([d + "2026-11-27-2-2000.md"], tmp_path) == {"mac"}
    # A deleted dispatch, or only photos changed: can't tell, so every edition.
    assert notes.editions_for([d + "gone.md"], tmp_path) is None
    assert notes.editions_for(["notes/photos/a.jpg"], tmp_path) is None


def test_dispatch_runs_have_their_own_lane_and_never_post_or_commit():
    import re
    from pathlib import Path
    wf = (Path(__file__).resolve().parents[1] / ".github/workflows/collect.yml").read_text()
    assert "'collect-notes'" in wf
    for name in ("Commit new data", "Post new recaps and previews to Bluesky and Threads"):
        step = re.search(r"- name: " + re.escape(name) + r"\n(.*?)\n      - ", wf, re.S).group(1)
        assert "if: github.event_name != 'push'" in step
    assert "- name: Dispatches that landed mid-run" in wf
