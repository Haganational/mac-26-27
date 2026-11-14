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
COLOR = ROOT / "data" / "anchor_color.json"  # voice brief, catchphrase, sign-off and rival per anchor
PORTRAITS = ROOT / "anchors"
SETS = ROOT / "sets"  # backdrops behind the anchor: <school>.jpg (Matthew's arena photos), <edition>.jpg, then studio.jpg

# Piper voices (rhasspy/piper-voices, en_US). Name -> download path under the repo's "en/en_US/".
VOICE_POOL = {
    "Man": ["en_US-ryan-high", "en_US-joe-medium", "en_US-john-medium", "en_US-norman-medium", "en_US-bryce-medium",
            "en_US-hfc_male-medium", "en_US-kusal-medium"],
    "Woman": ["en_US-lessac-high", "en_US-amy-medium", "en_US-kristin-medium", "en_US-hfc_female-medium",
              "en_US-ljspeech-high", "en_US-kathleen-low"],
}
PACE = {"Early 20s": 0.84, "Late 20s": 0.86, "Mid-30s": 0.87, "40s": 0.89, "50s": 0.91, "Late 50s": 0.93, "Early 60s": 0.95}  # Piper length-scale: lower is quicker (sped up Nov 14)


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
            out[k]["pace"] = PACE.get(out[k]["age"], 0.88)
    return out


@lru_cache(maxsize=1)
def color() -> dict[str, dict[str, str]]:
    return json.loads(COLOR.read_text())["color"] if COLOR.exists() else {}


def first_name(name: str) -> str:
    """'Col. Hank Sterling' -> 'Hank', 'Father Dante Russo' -> 'Dante'."""
    words = [w for w in name.split() if w.rstrip(".") not in {"Col", "Capt", "Father", "Lord", "Dr"}]
    return words[0] if words else name


OPENERS = 2  # how many anchors open with their catchphrase; the rest go straight to the news, so a game is never cut for a bit


def mood(card: dict, key: str) -> str:
    """One line that follows the anchor's team: a run of wins, a skid, or a win as the underdog.
    Read from the result card (its sides' streaks and the closing-line sentence), so it is always true."""
    me = next((s for s in (card.get("away") or {}, card.get("home") or {}) if s.get("key") == key), None)
    if not me:
        return ""
    st = str(me.get("streak") or "")
    n = int(st[1:]) if st[1:].isdigit() else 0
    if st.startswith("W") and n >= 3:
        return f"That's {n} straight."
    if st.startswith("L") and n >= 3:
        return f"That's {n} in a row the wrong way. We'll get the next one."
    ats = card.get("ats") or ""
    if me.get("winner") and me.get("name") and ats.startswith(me["name"]) and "underdog" in ats:  # the line is about us, not them
        return "Underdogs, folks."
    return ""


def dress(segs: list[dict], desk: list[dict | None]) -> None:
    """Put the anchors' color into the script before it is voiced: the first anchors on air open with
    their catchphrase, an anchor whose team beat their rival's says so, and the last anchor signs off.
    The facts are untouched; color only adds a line before or after them."""
    seen: set[str] = set()
    last = max((i for i, a in enumerate(desk) if a), default=None)
    for i, (sg, a) in enumerate(zip(segs, desk)):
        c = color().get(a["key"]) if a else None
        if not c:
            continue
        text = sg["text"]
        if a["key"] not in seen and len(seen) < OPENERS:
            text = f"{c['catch']} {text}"
        seen.add(a["key"])
        card = sg.get("card") or {}
        loser = next((s for s in (card.get("away") or {}, card.get("home") or {}) if s.get("mac") and s.get("winner") is False), None)
        if sg.get("kind") == "result" and loser and loser.get("key") == c.get("rival") and roster().get(c["rival"]):
            text = f"{text} {first_name(roster()[c['rival']]['name'])}, that one's for you."
        if sg.get("kind") == "result":
            text = f"{text} {mood(card, a['key'])}".rstrip()
        if i == last:
            text = f"{text} {c['signoff']}"
        sg["text"] = text


AUDITIONS = ROOT / "voices" / "anchors"  # each anchor's audition, <key>.ogg (tools/audition.py), which Chatterbox clones


def audition(key: str) -> Path | None:
    """The anchor's audition as a WAV for Chatterbox. The workflow decodes voices/anchors/*.ogg into
    ANCHOR_AUDITIONS before rendering; without that, nobody is cloned and the desk reads in Piper."""
    import os
    d = os.environ.get("ANCHOR_AUDITIONS")
    p = Path(d) / f"{key}.wav" if d else None
    return p if p and p.exists() and p.stat().st_size > 1000 else None


def portrait(key: str) -> Path | None:
    p = PORTRAITS / f"{key}.webp"
    return p if p.exists() else None


def edition_of(key: str) -> str | None:
    from .leagues import ALL  # late: leagues imports config, which reads LEAGUE
    return next((lg.key for lg in ALL.values() if any(t.key == key for t in lg.teams)), None)


def backdrop(key: str) -> Path | None:
    """The set behind an anchor: a photo of their own arena, else their edition's backdrop, else the home studio."""
    for name in (key, edition_of(key), "studio"):
        for ext in ("jpg", "webp", "png"):
            p = SETS / f"{name}.{ext}"
            if name and p.exists():
                return p
    return None


def team_of(seg: dict) -> str | None:
    """Which of our schools a segment is about, from its card."""
    card = seg.get("card") or {}
    if seg.get("kind") in ("star", "offcourt", "pickem"):
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
    return {"key": key, "name": a["name"], "voice_brief": color().get(key, {}).get("voice"), "school": a.get("school", key), "voice": a["voice"], "pace": a["pace"],
            "portrait": pic.as_uri() if pic else None, "set": (b.as_uri() if (b := backdrop(key)) else None)}
