"""Front Range blizzard, synthesized (no recordings): python blizzard_audio.py SECONDS [FADE_IN] > out.s16le

48 kHz stereo s16le. Heard from inside a warm cabin: a deep steady wind bed, long gusts that swell over
5-12 s and sigh away (the wind's pitch rises a little as each gust builds), a soft low howl around the
eaves that glides with the gusts, and fine snow ticking and hissing on the glass. Everything is a touch
muffled, like through a wall. No creaks, no thunder, nothing sudden. Timing drifts, so it never loops.
"""
import sys
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

SR = 48000
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
FADE_IN = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
CH = 60
CR = 100                      # control rate for gust envelopes (Hz)
rng = np.random.default_rng(3172019)


def bw(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


class F:
    def __init__(self, sos):
        self.s, self.z = sos, [sosfilt_zi(sos) * 0, sosfilt_zi(sos) * 0]

    def __call__(self, x, i):
        y, self.z[i] = sosfilt(self.s, x, zi=self.z[i])
        return y


# wind body: bands from low roar to airy, mixed by gust strength so the spectrum lifts as a gust builds
WIND = [F(bw("band", f)) for f in ([60, 160], [140, 320], [280, 600], [520, 1100], [950, 2200])]
HOWL = [F(bw("band", [f * 0.94, f * 1.06], 2)) for f in (330, 440, 560, 700)]   # soft eave tones
rumble = F(bw("low", 70, 4))
hiss = F(bw("band", [3500, 9000]))
tick = F(bw("band", [2500, 7000]))
master = F(bw("low", 6000, 2))
house = F(bw("high", 22))


class Gusts:
    """Sum of gust events at control rate; each rises smoothly and decays slowly. Carries over chunk edges."""
    def __init__(self):
        self.events, self.next = [], 2.0

    def env(self, c0, n):
        t = c0 + np.arange(int(n * CR / SR)) / CR
        while self.next < c0 + CH + 30:
            rise, fall = rng.uniform(4, 9), rng.uniform(6, 14)
            self.events.append((self.next, rise, fall, float(np.clip(rng.lognormal(0, 0.35), 0.4, 1.8))))
            self.next += rng.uniform(9, 30) if rng.random() > 0.2 else rng.uniform(35, 70)   # some calm spells
        e = np.zeros_like(t)
        for s, r, f, a in self.events:
            x = t - s
            up = np.clip(x / r, 0, 1); up = up * up * (3 - 2 * up)
            e += a * np.where(x < r, up, np.exp(-(x - r) / f)) * (x > 0)
        self.events = [ev for ev in self.events if ev[0] + ev[1] + 8 * ev[2] > c0]
        return t, e


def up(ctrl, n):
    return np.interp(np.arange(n), np.linspace(0, n - 1, len(ctrl)), ctrl)


gusts = [Gusts(), Gusts()]       # left/right gusts mostly shared, slightly offset by a second gust layer
out = sys.stdout.buffer
for c0 in range(0, DUR, CH):
    n = SR * min(CH, DUR - c0)
    t = (c0 * SR + np.arange(n)) / SR
    tc, g = gusts[0].env(c0, n)
    _, g2 = gusts[1].env(c0, n)
    storm = 0.85 + 0.15 * np.sin(2 * np.pi * tc / 1460 + 1.3) * np.sin(2 * np.pi * tc / 577)   # slow storm breathing
    y = np.zeros((2, n))
    for i in range(2):
        gi = up(storm * (0.6 + g * 0.32 + g2 * 0.1 * (1 if i else 0.6)), n)
        lift = np.clip(gi / 1.3, 0, 1.2)        # how far the gust brightens the wind
        w = np.zeros(n)
        for k, band in enumerate(WIND):
            weight = (1.0, 0.8, 0.55, 0.32, 0.16)[k] * (0.35 + lift) ** (k * 0.7)
            w += band(rng.standard_normal(n), i) * weight
        y[i] += w * gi * 1.4
        # eave howl: each tone fades in with the gust, pitch drifts with slow vibrato
        h = np.zeros(n)
        for k, band in enumerate(HOWL):
            v = band(rng.standard_normal(n), i)
            h += v * (0.5 + 0.5 * np.sin(2 * np.pi * t / (23 + 7 * k) + k + i))
        y[i] += h * np.clip(gi - 0.45, 0, None) ** 1.5 * 0.55
        y[i] += rumble(rng.standard_normal(n), i) * (0.9 + 0.4 * gi)
        # snow on glass: hiss rides the gusts, plus sparse tiny ticks
        y[i] += hiss(rng.standard_normal(n), i) * gi * 0.07
        clicks = (rng.random(n) < (25 + 90 * gi) / SR) * rng.standard_normal(n)
        y[i] += tick(clicks, i) * 0.35
    for i in range(2):
        y[i] = house(master(y[i], i), i)
    y *= np.clip(t / FADE_IN, 0, 1) * np.clip((DUR - t) / 60, 0, 1) * 0.40
    y = np.tanh(y * 1.1) / 1.1
    out.write((np.clip(y.T, -1, 1) * 32000).astype("<i2").tobytes())
    print(f"blizzard {c0 + CH}s", file=sys.stderr, flush=True)
