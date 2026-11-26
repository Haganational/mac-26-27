from pathlib import Path

from mac import indexnow

NEWS = ('<urlset><url><loc>https://hardwoodbricks.com/games/1.html</loc><news:news><news:title>{t}</news:title></news:news></url>'
        '<url><loc>https://elsewhere.com/x.html</loc></url></urlset>')


def test_queue_then_send_next_run(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(indexnow, "STATE", tmp_path / "state")
    monkeypatch.setattr(indexnow, "SITE_NOINDEX", False)
    site = tmp_path / "site"
    site.mkdir()
    (site / "news-sitemap.xml").write_text(NEWS.format(t="A vs. B prediction"))
    (site / "sitemap.xml").write_text("<urlset><url><loc>https://hardwoodbricks.com/towns/akron-oh.html</loc></url></urlset>")
    calls = []
    send = lambda urls, base: calls.append(urls) or [200]
    r1 = indexnow.run(site, "https://hardwoodbricks.com/", send)
    assert r1["queued"] == 2 and not calls  # first run only queues
    r2 = indexnow.run(site, "https://hardwoodbricks.com/", send)
    assert r2["sent"] == 2 and r2["queued"] == 0
    assert calls[0] == ["https://hardwoodbricks.com/games/1.html", "https://hardwoodbricks.com/towns/akron-oh.html"]
    (site / "news-sitemap.xml").write_text(NEWS.format(t="A 70, B 60"))  # the preview became a recap
    assert indexnow.run(site, "https://hardwoodbricks.com/", send)["queued"] == 1


def test_failed_send_keeps_queue(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(indexnow, "SITE_NOINDEX", False)
    monkeypatch.setattr(indexnow, "STATE", tmp_path / "s")
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitemap.xml").write_text("<urlset><url><loc>https://hardwoodbricks.com/a.html</loc></url></urlset>")
    indexnow.run(site, "https://hardwoodbricks.com/", lambda u, b: [200])
    assert indexnow.run(site, "https://hardwoodbricks.com/", lambda u, b: [429])["sent"] == 0
    assert indexnow.run(site, "https://hardwoodbricks.com/", lambda u, b: [200])["sent"] == 1


def test_key_file(tmp_path: Path):
    f = indexnow.key_file(tmp_path)
    assert f.name == indexnow.KEY + ".txt" and f.read_text() == indexnow.KEY
