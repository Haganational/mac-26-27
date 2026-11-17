import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = {"backstory", "beat", "look", "favorite", "hot_takes", "off_air", "gags", "temperament", "disposition",
          "appropriateness", "compassion", "humor", "worldview", "rube", "status", "tape"}


def test_every_dossier_is_a_known_anchor_with_every_category():
    anchors = json.loads((ROOT / "data" / "anchors.json").read_text())["anchors"]
    for key, d in json.loads((ROOT / "data" / "anchor_dossiers.json").read_text())["dossiers"].items():
        assert key in anchors, key
        assert FIELDS <= set(d), (key, FIELDS - set(d))


def test_roster_tool_covers_every_school():
    spec = importlib.util.spec_from_file_location("anchor_roster", ROOT / "tools" / "anchor_roster.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rs = mod.rows({})
    assert len({r["key"] for r in rs}) == len(rs)
    assert {r["next"] for r in rs} <= {"name", "headshot", "wire", "dossier", "ok"}
