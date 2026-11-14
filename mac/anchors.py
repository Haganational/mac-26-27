"""The anchor desk: one AI anchor per school (data/anchors.json), who reads that school's segments.

A segment about a game is read by the anchor of our team in it (the winner if both are ours,
the home side for a preview). Intros, outros and league-wide segments are read by the host
voice (Matthew's clone when it is set up, else the default Piper voice), with no portrait.

Each anchor's voice is a free Piper voice picked by gender, spread so neighbors on the desk
sound different, with a pace by age. VOICE_POOL lists every voice the workflows download.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ROSTER = ROOT / "data" / "anchors.json"
PORTRAITS = ROOT / "anchors"

# Piper voices (rhasspy/piper-voices, en_US). Name -> download path under the repo's "en/en_US/".
VOICE_POOL = {
    "Man": ["en_US-ryan-high", "en_US-joe-medium", "en_US-john-medium", "en_US-norman-medium", "en_US-bryce-medium",
            "en_US-hfc_male-medium", "en_US-kusal-medium"],
    "Woman": ["en_US-lessac-high", "en_US-amy-medium", "en_US-kristin-medium", "en_US-hfc_female-medium",
              "en_US-ljspeech-high", "en_US-kathleen-low"],
}
PACE = {"Early 20s": 0.9, "Late 20s": 0.92, "Mid-30s": 0.94, "40s": 0.96, "50s": 0.98, "Late 50s": 1.0, "Early 60s": 1.02}


def voice_path(name: str) -> str:
    """'en_US-ryan-high' -> 'en/en_US/ryan/high/en_US-ryan-high' (no extension)."""
    lang, speaker, quality = name.split("-")
    return f"{lang[:2]}/{lang}/{speaker}/{quality}/{name}"


@lru_cache(maxsize=1)
def roster() -> dict[str, dict[str, Any]]:
    if not ROSTER.exists():
        return {}
    out = json.loads(ROSTER.read_text())["anchors"]
    for gender, pool in VOICE_POOL.items():
        # Deal the pool out in roster order, so schools next to each other in a conference differ.
        mine = sorted((a["id"], k) for k, a in out.items() if a["gender"] == gender)
        start = int(hashlib.sha1(gender.encode()).hexdigest(), 16) % len(pool)
        for n, (_, k) in enumerate(mine):
            out[k]["voice"] = pool[(start + n) % len(pool)]
            out[k]["pace"] = PACE.get(out[k]["age"], 0.95)
    return out


def portrait(key: str) -> Path | None:
    p = PORTRAITS / f"{key}.webp"
    return p if p.exists() else None


def team_of(seg: dict) -> str | None:
    """Which of our schools a segment is about, from its card."""
    card = seg.get("card") or {}
    if seg.get("kind") == "star":
        return card.get("key")
    sides = [card.get(s) or {} for s in ("away", "home")]
    ours = [s for s in sides if s.get("mac") and s.get("key")]
    if not ours:
        return None
    if len(ours) == 2:
        win = [s for s in ours if s.get("winner")]
        return (win or [ours[1]])[0]["key"]  # the winner, else the home side
    return ours[0]["key"]


def for_segment(seg: dict) -> dict[str, Any] | None:
    """The anchor who reads this segment: name, school key, voice, pace and portrait (or None for the host)."""
    key = team_of(seg)
    a = roster().get(key or "")
    if not a:
        return None
    pic = portrait(key)
    return {"key": key, "name": a["name"], "school": a.get("school", key), "voice": a["voice"], "pace": a["pace"],
            "portrait": pic.as_uri() if pic else None}
