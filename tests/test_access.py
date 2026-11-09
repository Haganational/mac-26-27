import json

from mac import access

PAGE = """<html><body><header>top</header><main id="main"><h1>Odds</h1><table id="t">secret line -3.5</table></main>
<footer>foot</footer><script>window.x = 1;</script><script src="static/nav.js" defer></script></body></html>"""

HOME = """<main id="main"><details class="bestplay">
  <summary><span class="bp-tease">KENT at AKR · <b>3 pts</b></span></summary>
  <div class="bp-body">
    <span class="bp-pick"><b>KENT +4.5</b></span>
  </div>
</details><script id="data" type="application/json">{"best_play": {"matchup": "KENT at AKR", "edge": 3, "pick": "KENT +4.5", "price": -110, "books": ["DK"], "model": 1.5, "odds_event_id": "x"}}</script></main>"""


def test_lock_page_hides_body_and_scripts():
    s = access.Sealer("bricks", salt=b"0" * 16)
    out = access.lock_page(PAGE, s)
    assert "secret line" not in out and "window.x" not in out
    assert "Enter your access code" in out and access.REQUEST_EMAIL in out
    assert 'src="static/nav.js"' in out and "<footer>foot</footer>" in out
    blob = out.split('class="hb-sealed">')[1].split("</script>")[0]
    p = json.loads(s.open(blob))
    assert "secret line -3.5" in p["html"] and p["scripts"] == ["window.x = 1;"]


def test_wrong_code_cannot_open():
    blob = access.Sealer("bricks", salt=b"1" * 16).seal("hi")
    try:
        access.Sealer("nope", salt=b"1" * 16).open(blob)
    except Exception:
        return
    raise AssertionError("opened with the wrong code")


def test_best_play_sealed_teaser_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("ACCESS_CODE", "bricks")
    (tmp_path / "index.html").write_text(HOME)
    (tmp_path / "odds.html").write_text(PAGE)
    (tmp_path / "data.json").write_text(json.dumps({"best_play": {"matchup": "KENT at AKR", "pick": "KENT +4.5", "edge": 3}}))
    assert access.lock_site(tmp_path) == 2
    home = (tmp_path / "index.html").read_text()
    assert "KENT +4.5" not in home and "KENT at AKR" in home and "-110" not in home
    assert "KENT +4.5" not in (tmp_path / "data.json").read_text()


def test_no_code_no_change(tmp_path, monkeypatch):
    monkeypatch.delenv("ACCESS_CODE", raising=False)
    (tmp_path / "odds.html").write_text(PAGE)
    assert access.lock_site(tmp_path) == 0
    assert (tmp_path / "odds.html").read_text() == PAGE
