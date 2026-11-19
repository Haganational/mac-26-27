"""Temp narration and crowd chants for the "Spring Forward" film via Gemini TTS (same API as tools/audition.py).
Reads spring/vo.json, writes spring/out/<id>.wav. Skips files that already exist."""
import base64, json, os, sys, time, urllib.error, urllib.request, wave
from pathlib import Path
MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
KEY = os.environ["GEMINI_API_KEY"].strip()
OUT = Path("spring/out"); OUT.mkdir(parents=True, exist_ok=True)
cfg = json.load(open("spring/vo.json"))
def say(text, voice, out):
    if out.exists(): return
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": KEY})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r: data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:300]
            if e.code in (429, 500, 503) and attempt < 4:
                print(f"{out.name}: {e.code}, retrying"); time.sleep(25 * (attempt + 1)); continue
            print(f"{out.name}: FAILED {e.code} {msg}"); return
    part = data["candidates"][0]["content"]["parts"][0]["inlineData"]
    rate = int(part.get("mimeType", "rate=24000").split("rate=")[-1].split(";")[0] or 24000)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(base64.b64decode(part["data"]))
    print(out, out.stat().st_size // 1024, "KB"); time.sleep(7)
for k, line in cfg["lines"].items():
    say(f"{cfg['direction']}\n\n{line}", cfg["voice"], OUT / f"{k}.wav")
ch = cfg["chants"]
for i, v in enumerate(ch["voices"]):
    for k, line in ch["lines"].items():
        say(f"{ch['direction']}\n\n{line}", v, OUT / f"chant-{k}-{i}.wav")
