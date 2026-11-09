"""Voice every MAC90 segment in Matthew's cloned voice with Chatterbox Turbo (MIT, runs on CPU).

    python tools/clone_voice.py --ref voices/matthew.wav --jobs work/voice-jobs.json

Runs in its own virtualenv (torch and Chatterbox pin versions the site doesn't use),
so it takes a JSON list of {"text", "out"} and writes one WAV per item, loading the
model once. The reference clip must be over 5 seconds; 10 to 20 seconds of clean,
dry speech works best. Chatterbox adds an inaudible Perth watermark to everything
it makes, which marks the audio as AI-generated.
"""
import argparse
import json
import sys
import time

import torch
import torchaudio
from chatterbox.tts_turbo import ChatterboxTurboTTS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--jobs", required=True)
    a = ap.parse_args()
    jobs = json.load(open(a.jobs))
    torch.set_num_threads(max(1, torch.get_num_threads()))
    t0 = time.time()
    model = ChatterboxTurboTTS.from_pretrained(device="cpu")
    model.prepare_conditionals(a.ref)
    print(f"model ready in {time.time() - t0:.0f}s", file=sys.stderr)
    for j in jobs:
        t1 = time.time()
        wav = model.generate(j["text"])
        torchaudio.save(j["out"], wav, model.sr)
        print(f"{j['out']}: {wav.shape[-1] / model.sr:.1f}s audio in {time.time() - t1:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
