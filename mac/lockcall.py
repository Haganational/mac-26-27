"""The Lock Call: the two-minute daily Tops and Bottoms podcast (Nov 23 2026).

Three small jobs, all for whoever writes the day's script:

    python -m mac.lockcall facts [YYYY-MM-DD]      the day's picks, yesterday's results and the board, as JSON
    python -m mac.lockcall check  data/podcast/DAY.json   length, cast and format check on a script
    python -m mac.lockcall render data/podcast/DAY.json out.mp3   voices from ElevenLabs, sting on both ends

Nothing here publishes. The script file is written by an editor (see data/podcast/BIBLE.md); every number in it
must come from `facts`, and the one news item must carry a source link in `notes`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from . import tops

POD_DIR = Path(__file__).resolve().parent.parent / "data" / "podcast"
VOICES = POD_DIR / "voices.json"
PARTS = ("open", "picks", "board", "close")  # Matthew's four-part format, in order
TARGET_CHARS = (1300, 1900)  # about two minutes at ~14 characters a second
API = "https://api.elevenlabs.io/v1/text-to-dialogue"


def _short(p: dict[str, Any]) -> dict[str, Any]:
    return {k: p.get(k) for k in ("label", "matchup", "kind", "why", "result", "final") if p.get(k) is not None}


def facts(day: str | None = None) -> dict[str, Any]:
    """Everything a script may state as fact for `day` (default: the newest card)."""
    cards = tops.load_cards()
    if not cards:
        return {}
    today = next((c for c in cards if c.get("date") == day), None) if day else cards[-1]
    if today is None:
        return {"date": day, "error": "no card locked for this day yet"}
    before = [c for c in cards if c["date"] < today["date"]]
    last = before[-1] if before else None
    out: dict[str, Any] = {
        "date": today["date"],
        "picks": {k: [_short(p) for p in ps] for k, ps in today.get("picks", {}).items()},
        "board": [{k: r[k] for k in ("key", "first", "record", "units", "streak", "rank")}
                  for r in tops.standings(before)],
    }
    if last:
        out["yesterday"] = {
            "date": last["date"],
            "cappers": {k: {**{f: v for f, v in tops.tally(ps).items() if f in ("record", "units")},
                            "picks": [_short(p) for p in ps]}
                        for k, ps in last.get("picks", {}).items()},
        }
    return out


def check(script: dict[str, Any]) -> list[str]:
    """Problems with a script, empty when it is ready to record."""
    cast = json.loads(VOICES.read_text())
    lines = script.get("lines", [])
    bad = []
    seen = [ln.get("part") for ln in lines]
    order = [p for i, p in enumerate(seen) if i == 0 or p != seen[i - 1]]
    if order != list(PARTS):
        bad.append(f"parts must run {' > '.join(PARTS)}; got {' > '.join(map(str, order))}")
    for ln in lines:
        if ln.get("who") not in cast:
            bad.append(f"unknown speaker: {ln.get('who')}")
    n = sum(len(ln.get("text", "")) for ln in lines)
    if not TARGET_CHARS[0] <= n <= TARGET_CHARS[1]:
        bad.append(f"{n} characters; aim for {TARGET_CHARS[0]}-{TARGET_CHARS[1]} (about two minutes)")
    talk: dict[str, int] = {}
    for ln in lines:
        talk[ln.get("who")] = talk.get(ln.get("who"), 0) + len(ln.get("text", ""))
    if lines and sorted(talk, key=talk.get, reverse=True)[:2] not in (["leslie", "brett"], ["brett", "leslie"]):
        bad.append("Leslie and Brett are the main hosts and should carry the most lines")
    news = script.get("notes", {}).get("news")
    if not news or not news.get("sources"):
        bad.append("notes.news needs the item and at least one source link")
    if "GAMBLER" not in " ".join(ln.get("text", "") for ln in lines):
        bad.append("the close must carry the 21+ / 1-800-GAMBLER line")
    return bad


def _sting(path: Path) -> None:
    """The original three-note chime. Synthesized here, so there is nothing to license."""
    notes = [(415.3, 0.0, 2.6, 0.5), (523.25, 0.18, 2.4, 0.4), (622.25, 0.36, 2.2, 0.35), (830.6, 0.54, 2.0, 0.25)]
    cmd, fc = ["ffmpeg", "-v", "error", "-y"], []
    for i, (hz, delay, dur, vol) in enumerate(notes):
        cmd += ["-f", "lavfi", "-i", f"sine=f={hz}:d={dur}"]
        ms = int(delay * 1000)
        fc.append(f"[{i}]adelay={ms}|{ms},afade=t=out:st={delay + 0.3}:d={dur - 0.3},volume={vol}[n{i}]")
    fc.append("".join(f"[n{i}]" for i in range(len(notes)))
              + f"amix=inputs={len(notes)}:normalize=0,aecho=0.8:0.6:120:0.3,apad=pad_dur=0.3,"
                "aformat=sample_rates=44100:channel_layouts=stereo,volume=0.6[s]")
    subprocess.run(cmd + ["-filter_complex", ";".join(fc), "-map", "[s]", str(path)], check=True)


def render(script: dict[str, Any], out: Path) -> None:
    cast = json.loads(VOICES.read_text())
    body = {"model_id": "eleven_v3",
            "inputs": [{"text": ln["text"], "voice_id": cast[ln["who"]]["voice_id"]} for ln in script["lines"]]}
    # In the cloud environment the network layer supplies the key; elsewhere set ELEVENLABS_API_KEY.
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "from-proxy")})
    with tempfile.TemporaryDirectory() as tmp:
        talk, sting = Path(tmp) / "talk.mp3", Path(tmp) / "sting.wav"
        with urllib.request.urlopen(req, timeout=300) as r:
            talk.write_bytes(r.read())
        _sting(sting)
        mix = ("[1]aformat=sample_rates=44100:channel_layouts=stereo,loudnorm=I=-16:TP=-1.5[v];"
               "[0]asplit[a][b];[a][v][b]concat=n=3:v=0:a=1[o]")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(sting), "-i", str(talk), "-filter_complex", mix,
                        "-map", "[o]", "-b:a", "160k", str(out)], check=True)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "facts"
    if cmd == "facts":
        print(json.dumps(facts(argv[1] if len(argv) > 1 else None), indent=1))
        return 0
    script = json.loads(Path(argv[1]).read_text())
    problems = check(script)
    for p in problems:
        print("FIX:", p)
    if cmd == "check" or problems:
        return 1 if problems else 0
    render(script, Path(argv[2]))
    print("wrote", argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
