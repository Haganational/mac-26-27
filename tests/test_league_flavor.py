"""Every edition's local color file parses, and each researched note carries its source."""
import json

from mac.config import ROOT
from mac.leagues import ALL

KINDS = {"town", "arena", "program-history", "campus-tradition", "rivalry", "coach", "current", "alumni"}


def _notes(f):
    for t in f["teams"].values():
        yield from t.get("home_lines", [])
        yield from t.get("lines", [])
    for r in f.get("rivalries", {}).values():
        yield from r.get("lines", [])


def test_league_flavor_files_are_sourced():
    for key, lg in ALL.items():
        path = ROOT / "data" / ("flavor.json" if key == "mac" else f"leagues/{key}/flavor.json")
        if not path.exists():
            continue
        f = json.loads(path.read_text())
        team_keys = {t.key for t in lg.teams}
        assert set(f["teams"]) <= team_keys, f"{key}: unknown team keys {set(f['teams']) - team_keys}"
        for pair in f.get("rivalries", {}):
            assert set(pair.split("|")) <= team_keys and pair == "|".join(sorted(pair.split("|"))), (key, pair)
        for n in _notes(f):
            if isinstance(n, str):
                continue  # hand-written house lines
            assert n["source"].startswith("http"), (key, n["text"])
            assert n["kind"] in KINDS, (key, n["kind"])
            assert "{" not in n["text"] and "}" not in n["text"], (key, n["text"])
