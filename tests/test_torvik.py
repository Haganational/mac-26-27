from mac import torvik

TEAMS = {
    "1": {"name": "Kent State Golden Flashes", "short": "Kent State"},
    "2": {"name": "UConn Huskies", "short": "UConn"},
    "3": {"name": "Mississippi State Bulldogs", "short": "Mississippi St"},
    "4": {"name": "Ole Miss Rebels", "short": "Ole Miss"},
    "5": {"name": "Saint Mary's Gaels", "short": "Saint Mary's"},
}


def test_name_map_exact_and_aliases():
    m, missing = torvik.name_map({"Kent St.", "Connecticut", "Mississippi", "Mississippi St.", "Saint Mary's", "Nowhere"}, TEAMS)
    assert m == {"Kent St.": "1", "Connecticut": "2", "Mississippi": "4", "Mississippi St.": "3", "Saint Mary's": "5"}
    assert missing == ["Nowhere"]


def test_html_responses_are_not_saved(monkeypatch):
    class Resp:
        status_code = 200
        content = b"<!DOCTYPE html><html>challenge</html>"

    class S:
        def get(self, *a, **k):
            return Resp()

    assert torvik._get(S(), "2027_team_results.csv") is None
