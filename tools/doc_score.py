"""An original rising score for a film's opening plates: python tools/doc_score.py <seconds> <out.wav>

Synthesized here (drone, tremolo strings in D minor, air, an accelerating drum roll, one hit as the
film starts), so there is nothing to license. The build lasts <seconds>; the hit's tail runs 2.6 s past it.
"""
import sys, wave
import numpy as np

T, out = float(sys.argv[1]), sys.argv[2]
sr, tail = 48000, 2.6
n = int((T + tail) * sr); t = np.arange(n) / sr; rng = np.random.default_rng(7); u = np.clip(t / T, 0, 1)


def saw(f, h=8, bright=None):
    x = np.zeros(n)
    for k in range(1, h + 1):
        w = 1 / k if bright is None else (1 / k) * np.clip(bright * h - (k - 1), 0, 1)
        x += w * np.sin(2 * np.pi * f * k * t + rng.uniform(0, 6.28))
    return x


drone = (saw(73.42, 6, u * 0.8 + 0.2) + 0.7 * saw(110.0, 5, u * 0.8 + 0.2) + 0.5 * np.sin(2 * np.pi * 36.71 * t)) * (0.25 + 0.75 * u ** 1.5)
trem = 0.5 * (1 + np.sin(2 * np.pi * (5 + 7 * u) * t))
strings = sum(saw(f * d, 7, u) for f in (293.66, 349.23, 440.0) for d in (0.997, 1.003)) * trem * u ** 2.4
high = sum(saw(f, 5, u) for f in (587.33, 880.0)) * trem * np.clip((u - 0.55) / 0.45, 0, 1) ** 2
noise = rng.standard_normal(n); noise = noise - np.convolve(noise, np.ones(64) / 64, "same")
riser = noise * u ** 4 * 0.5
drum = np.zeros(n); tt = T - 7.0; step = 0.55
while tt < T - 0.05:
    i = int(tt * sr); L = int(0.35 * sr); e = np.exp(-np.arange(L) / sr * 14)
    drum[i:i + L] += np.sin(2 * np.pi * np.cumsum(np.linspace(95, 55, L)) / sr) * e * (0.35 + 0.65 * (tt - (T - 7)) / 7)
    step = max(0.09, step * 0.9); tt += step
i = int(T * sr); L = n - i; tl = np.arange(L) / sr; hit = np.zeros(n)
hit[i:] = (np.sin(2 * np.pi * np.cumsum(np.linspace(70, 42, L)) / sr) * np.exp(-tl * 2.2) * 1.6 + rng.standard_normal(L) * np.exp(-tl * 9) * 0.5
           + (saw(146.83, 6)[i:] + saw(220, 5)[i:]) * np.exp(-tl * 1.6) * 0.35)
build = 0.9 * drone + 0.22 * strings + 0.12 * high + riser + 0.9 * drum
build[i:] *= np.exp(-tl * 6)
x = (build + hit) * np.minimum(1, t / 1.5); x = x / np.abs(x).max() * 10 ** (-5 / 20)
with wave.open(out, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((x * 32767).astype(np.int16).tobytes())
