"""Record each anchor's audition: a short in-character read by Gemini's text-to-speech, saved as
voices/anchors/<key>.ogg. Chatterbox clones it for every line the anchor reads (mac/midmaxx60.py).

    GEMINI_API_KEY=... python tools/audition.py              # every anchor still missing one, up to --most
    GEMINI_API_KEY=... python tools/audition.py akron toledo  # these anchors, redone
    python tools/audition.py --show akron                    # print the prompt only, no API call

The direction comes from data/anchor_color.json (the anchor's voice brief) and data/anchors.json
(gender, age). Each anchor gets one of Gemini's prebuilt voices, dealt by gender so neighbors on the
desk differ. Matthew can also record an audition by hand in AI Studio and drop it in as <key>.ogg.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mac import anchors  # noqa: E402

MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Gemini's prebuilt voices, split by how they read; each anchor gets one, and the voice brief does the rest.
VOICES = {
    "Man": ["Charon", "Puck", "Fenrir", "Orus", "Enceladus", "Iapetus", "Umbriel", "Algieba", "Algenib",
            "Rasalgethi", "Alnilam", "Schedar", "Achird", "Zubenelgenubi", "Sadachbia", "Sadaltager"],
    "Woman": ["Kore", "Zephyr", "Leda", "Aoede", "Callirrhoe", "Autonoe", "Despina", "Erinome", "Laomedeia",
              "Achernar", "Gacrux", "Pulcherrima", "Vindemiatrix", "Sulafat"],
}


def gemini_voice(key: str) -> str:
    roster = anchors.roster()
    g = roster[key]["gender"]
    pool = VOICES.get(g, VOICES["Man"])
    mine = sorted((a["id"], k) for k, a in roster.items() if a["gender"] == g)
    start = int(hashlib.sha1(f"gemini-{g}".encode()).hexdigest(), 16) % len(pool)
    return pool[(start + [k for _, k in mine].index(key)) % len(pool)]


def script(key: str) -> str:
    a, c = anchors.roster()[key], anchors.color()[key]
    who = f"{'man in his' if a['gender'] == 'Man' else 'woman in her'} {a['age'].lower()}"
    lines = (f"{c['catch']} Here's where it stands. A road win, a cover, and a crowd that never sat down. "
             f"The numbers say one thing, my gut says another, and tonight my gut wins. {c['signoff']}")
    return f"Read this as a college basketball TV anchor, a {who}. Voice and delivery: {c['voice']}\n\n{lines}"


def record(key: str, out: Path, api_key: str) -> None:
    body = {"contents": [{"parts": [{"text": script(key)}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": gemini_voice(key)}}}}}
    req = urllib.request.Request(URL.format(model=MODEL), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            raise SystemExit(f"{key}: Gemini said {e.code}: {e.read().decode()[:400]}")
    part = data["candidates"][0]["content"]["parts"][0]["inlineData"]
    pcm = base64.b64decode(part["data"])  # 16-bit mono PCM, 24 kHz unless the mime type says otherwise
    rate = int(part.get("mimeType", "rate=24000").split("rate=")[-1].split(";")[0] or 24000)
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        with wave.open(tmp.name, "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate), w.writeframes(pcm)
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp.name, "-c:a", "libopus", "-b:a", "48k", str(out)], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--most", type=int, default=10, help="most auditions per run (free-tier limits)")
    ap.add_argument("--show", action="store_true", help="print the prompt and voice, no API call")
    a = ap.parse_args()
    todo = a.keys or [k for k in anchors.roster() if not (anchors.AUDITIONS / f"{k}.ogg").exists()]
    if a.show:
        for k in todo:
            print(f"--- {k} ({gemini_voice(k)})\n{script(k)}\n")
        return
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set")
    for k in todo[: a.most]:
        out = anchors.AUDITIONS / f"{k}.ogg"
        record(k, out, api_key)
        print(f"{out} ({gemini_voice(k)}) {out.stat().st_size // 1024} KB")
        time.sleep(7)  # stay under the free tier's requests per minute
    print(f"{max(0, len(todo) - a.most)} still to record")


if __name__ == "__main__":
    main()
