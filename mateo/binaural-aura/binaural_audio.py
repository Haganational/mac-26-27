"""Binaural Aura sound: python binaural_audio.py SECONDS [FADE_IN] > out.s16le

48 kHz stereo s16le. The Sunset Cliffs Pacific swell (../sunset-cliffs/pacific_audio.py, synthesized)
with a soft binaural theta bed under it: 75 Hz in the left ear, 81 Hz in the right, so headphones
hear a slow 6 Hz beat. The tones breathe very gently (a 0.1 Hz swell) and fade in over the first
minute. Everything is generated; nothing is sampled.
"""
import subprocess, sys
from pathlib import Path
import numpy as np

SR = 48000
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
FADE_IN = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
LEFT, RIGHT, LEVEL = 75.0, 81.0, 0.075
HERE = Path(__file__).resolve().parent
sea = subprocess.Popen([sys.executable, HERE.parent / "sunset-cliffs" / "pacific_audio.py", str(DUR), str(FADE_IN)],
                       stdout=subprocess.PIPE)
out = sys.stdout.buffer
n0 = 0
CH = SR * 60
while True:
    raw = sea.stdout.read(CH * 4)
    if not raw:
        break
    x = np.frombuffer(raw, "<i2").reshape(-1, 2).astype(np.float64) / 32000
    t = (n0 + np.arange(len(x))) / SR
    amp = LEVEL * np.clip(t / 60, 0, 1) * np.clip((DUR - t) / 60, 0, 1) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.1 * t))
    x[:, 0] += amp * np.sin(2 * np.pi * LEFT * t)
    x[:, 1] += amp * np.sin(2 * np.pi * RIGHT * t)
    out.write((np.clip(x, -1, 1) * 32000).astype("<i2").tobytes())
    n0 += len(x)
if sea.wait():
    sys.exit("pacific_audio.py failed")
