import json
from pathlib import Path

from mac import towns


def test_every_school_has_a_town_page(tmp_path: Path):
    ts = towns.build(tmp_path, eds=[])
    assert sum(len(t["schools"]) for t in ts) == 286
    slugs = {t["slug"] for t in ts}
    assert len(slugs) == len(ts)
    for t in ts:
        page = (tmp_path / "towns" / f"{t['slug']}.html").read_text()
        assert t["label"] in page and '<base href="../">' in page
        ld = json.loads(page.split('<script type="application/ld+json">', 1)[1].split("</script>", 1)[0])
        assert any(x["@type"] == "SportsTeam" for x in ld["@graph"])
    sm = (tmp_path / "towns" / "sitemap.xml").read_text()
    assert sm.count("<loc>") == len(ts) + 1


def test_labels_and_team_link():
    assert towns.town_label("the Bronx", "New York") == "The Bronx, New York"
    assert towns.town_label("Washington", "District of Columbia") == "Washington, D.C."
    assert towns.team_link("akron") == {"label": "Akron, Ohio", "href": "towns/akron-oh.html", "town": "Akron", "state": "Ohio"}


def test_robots_lists_towns_sitemap():
    from mac import hub
    assert "towns/sitemap.xml" in hub.robots("https://x/", noindex=False)
