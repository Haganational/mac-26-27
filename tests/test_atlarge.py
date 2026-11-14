import json

from mac import atlarge as A
from mac.leagues import ALL


def _bids():
    return A.load_bids()


def test_history_matches_the_brackets():
    h = {c["key"]: c for c in A.history(_bids(), now=2027)}
    assert h["mw"]["total"] == 32 and h["mw"]["multi"] == 13
    assert h["mac"]["total"] == 1 and h["mac"]["last"]["year"] == 2026 and h["mac"]["last"]["at_large"] == ["Miami (OH)"]
    assert h["metro"]["total"] == 1 and h["metro"]["last"]["at_large"] == ["Iona"]
    assert h["horizon"]["total"] == h["asun"]["total"] == h["bigwest"]["total"] == 0
    assert [c["key"] for c in A.history(_bids(), now=2027)][0] == "mw", "the Mountain West carries the most weight"
    assert len(h["mw"]["seasons"]) == 16, "2010-2026 without 2020"


def test_recency_weighting():
    bids = {"2025": {"x": {"auto": "", "at_large": ["a", "b"]}}, "2021": {"x": {"auto": "", "at_large": []}}}
    # 2025 has weight 0.5^(2/4), 2021 has 0.5^(6/4): the recent two-bid year dominates
    w = A.conference_weight(bids, "x", now=2027)
    assert abs(w - 4 / 3) < 1e-9  # 2 x 0.707 / (0.707 + 0.354)
    assert A.conference_weight(bids, "x", now=2025) == 0.0, "the current season never counts"
    assert A.conference_weight(bids, "nope", now=2027) == 0.0


def _ratings(ranks):
    return {"as_of": "2026-11-14T01:00:00+00:00", "teams": [{"id": eid, "rk_adj_em": rk, "net_pts": 0, "games": 3} for eid, rk in ranks.items()]}


def test_watch_formula_and_order():
    unm = next(t for t in ALL["mw"].teams if t.key == "new-mexico")
    wsu = next(t for t in ALL["horizon"].teams if t.key == "wright-state")
    rows = A.watch(_ratings({unm.espn_id: 50, wsu.espn_id: 40}), _bids(), now=2027)
    by = {r["key"]: r for r in rows}
    c = A.conference_weight(_bids(), "mw", now=2027)
    assert by["new-mexico"]["watch"] == round(50 - A.BOOST * c, 1)
    assert by["wright-state"]["watch"] == 40.0 and by["wright-state"]["boost"] == 0
    assert rows[0]["key"] == "new-mexico", "the league boost lifts a Mountain West team past a better-rated Horizon team"
    assert by["wright-state"]["zone"] == "bubble"


def test_net_is_averaged_only_for_this_season():
    unm = next(t for t in ALL["mw"].teams if t.key == "new-mexico")
    html = ("<p>Through Games 12/01/2026</p><table><thead><tr><th>Rank</th><th>School</th><th>Record</th><th>Conf</th></tr></thead>"
            "<tbody><tr><td>20</td><td>New Mexico</td><td>7-1</td><td>Mountain West</td></tr>"
            "<tr><td>88</td><td>Miami (OH)</td><td>6-1</td><td>MAC</td></tr>"
            "<tr><td>140</td><td>Saint Peter's</td><td>3-4</td><td>MAAC</td></tr></tbody></table>")
    net = A.parse_net(html)
    assert net["through"] == "2026-12-01" and net["teams"][0] == {"rank": 20, "school": "New Mexico", "record": "7-1", "conf": "Mountain West"}
    assert A.net_ranks({**net, "season": 2027}, now=2027) == {"new-mexico": 20, "miami-oh": 88, "saint-peters": 140}
    assert A.net_ranks({**net, "season": 2026}, now=2027) == {}, "last March's NET is ignored"
    rows = A.watch(_ratings({unm.espn_id: 40}), _bids(), {"new-mexico": 20}, now=2027)
    assert rows[0]["strength"] == 30.0 and rows[0]["net"] == 20


def test_page_renders(tmp_path):
    root = tmp_path / "data"
    (root / "atlarge").mkdir(parents=True)
    (root / "atlarge" / "bids.json").write_text(A.BIDS.read_text())
    (root / "model").mkdir()
    unm = next(t for t in ALL["mw"].teams if t.key == "new-mexico")
    (root / "model" / "ratings.json").write_text(json.dumps(_ratings({unm.espn_id: 28})))
    ctx = A.page_context(root, now=2027)
    assert ctx["rows"][0]["short"] == "New Mexico" and not ctx["net_on"]
    from jinja2 import Environment, FileSystemLoader
    from mac.config import TEMPLATES_DIR
    html = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True).get_template("atlarge.html").render(
        eds=[], names="x", base="https://x.com/", season="2026-27", noindex=False, built="now", **ctx)
    assert "Watch rank = <b>S</b> − 10 × <b>C</b>" in html and "Miami (OH)" in html and "Iona" in html
