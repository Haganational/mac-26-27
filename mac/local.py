"""Local flavor on each school's landing page (Matthew, Nov 17 2026: "Every school's landing page will start
to be infused with local flavor... spot for local ad text (classy), backdrop photo of town or gown").
Beta on the MAC first.

data/local_color.json
  backdrops.<key>  {"file": "<key>.jpg", "kind": "town"|"gown", "caption", "credit", "license",
                    "license_url", "source"}   a free-licensed photo (CC0, PD, CC BY, CC BY-SA) in backdrops/,
                    published to the site root's backdrops/ folder and credited on the page
  ads.<key>        {"sponsor", "text", "url"}  a local advertiser's text ad, when one signs; until then the
                    school's hometown paper runs a house ad for the slot
"""
from __future__ import annotations

import json
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import SHARED_DIR

ROOT = Path(__file__).resolve().parents[1]
BACKDROPS = ROOT / "backdrops"
PATH = SHARED_DIR / "local_color.json"
BETA = ("mac",)  # editions whose school pages carry the slots


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    try:
        d = json.loads(PATH.read_text())
    except (OSError, ValueError):
        d = {}
    d.setdefault("backdrops", {})
    d.setdefault("ads", {})
    return d


def backdrop(key: str) -> dict[str, Any] | None:
    b = load()["backdrops"].get(key)
    if not b or not (BACKDROPS / b.get("file", "")).is_file():
        return None
    return b


def ad(key: str, desk: dict[str, Any] | None, short: str) -> dict[str, Any]:
    """The school page's local ad: a signed local advertiser, else the hometown paper's house ad."""
    a = load()["ads"].get(key)
    if a and a.get("text"):
        return {"house": False, **a}
    paper = (desk or {}).get("paper") or "Hardwood Bricks"
    town = (desk or {}).get("town") or short
    return {"house": True, "sponsor": paper,
            "text": f"Reach {town} where it reads about {short}. One quiet line of type, right here, for a local business.",
            "url": "mailto:press@hardwoodbricks.com?subject=" + f"Local ad: {short}".replace(" ", "%20"),
            "cta": "Place a local line"}


def publish(site_root: Path) -> int:
    """Copy backdrops/ to the site root once (edition pages reach it through site_up)."""
    dest = Path(site_root) / "backdrops"
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in BACKDROPS.glob("*.jpg"):
        shutil.copy2(p, dest / p.name)
        n += 1
    return n
