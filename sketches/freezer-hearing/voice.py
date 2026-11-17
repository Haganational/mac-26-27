"""Voice The Freezer Hearing with Gemini TTS, one file per take, in each anchor's audition voice.

    GEMINI_API_KEY=... python sketches/freezer-hearing/voice.py    # renders takes still missing in audio/
Resumable: a take already in audio/ is skipped, so a quota stop just means run it again later.
"""
from __future__ import annotations

import base64, json, os, sys, time, urllib.error, urllib.request, wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from tools.audition import gemini_voice  # noqa: E402

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS = [os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"), "gemini-2.5-pro-preview-tts"]


def call(model: str, prompt: str, voice: str, key: str) -> bytes:
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    req = urllib.request.Request(URL.format(model=model), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    try:
        return base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    except (KeyError, IndexError):
        print("  no audio:", json.dumps(data)[:300])
        return b""


def main() -> None:
    key = os.environ["GEMINI_API_KEY"].strip()
    spec = json.loads((HERE / "lines.json").read_text())
    out = HERE / "audio"
    out.mkdir(exist_ok=True)
    models = list(MODELS)
    for t in spec["takes"]:
        dest = out / f"{t['id']}.wav"
        if dest.exists():
            continue
        c = spec["cast"][t["who"]]
        prompts = [f"Read this aloud as {c['who']}. Delivery: {t['how']}\n\n{t['text']}",
                   f"Read this aloud as {c['who']}.\n\n{t['text']}",
                   f"Say: {t['text']}"]
        pcm = None
        while models and pcm is None:
            for attempt in range(3):
                try:
                    got = call(models[0], prompts[min(attempt, 2)], gemini_voice(c["key"]), key)
                    if got:
                        pcm = got
                        break
                    continue
                except urllib.error.HTTPError as e:
                    msg = e.read().decode()[:300]
                    print(f"{t['id']} {models[0]}: {e.code} {msg}")
                    if e.code in (500, 503) or (e.code == 429 and "PerMinute" in msg):
                        time.sleep(25 * (attempt + 1)); continue
                    break
            if pcm is None:
                print(f"dropping {models.pop(0)}")
        if pcm is None:
            print("out of models/quota; stopping, run again later")
            break
        with wave.open(str(dest), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
        print(f"{dest.name} {len(pcm) / 48000:.1f}s")
        time.sleep(7)
    have = len(list(out.glob("*.wav")))
    print(f"{have}/{len(spec['takes'])} takes voiced")


if __name__ == "__main__":
    main()
