import json
import re

from mac.build import follow_context
from mac.config import DATA_DIR, TEAMS

HANDLE = re.compile(r"^[A-Za-z0-9_]{1,15}$")


def test_every_handle_is_well_formed():
    x = json.loads((DATA_DIR / "x_follow.json").read_text())
    for t in x["teams"].values():
        for h in t["team_accounts"] + [c["handle"] for c in t["coaches"]] + [p["handle"] for p in t["players"] if p["handle"]]:
            assert HANDLE.match(h), h


def test_follow_context_covers_all_teams():
    ctx = follow_context()
    assert [t["key"] for t in ctx["teams"]] == [t.key for t in TEAMS]
    assert ctx["counts"]["players"] <= ctx["counts"]["roster"]
    assert ctx["counts"]["handles"] >= ctx["counts"]["players"]
