"""Pacific swell at Sunset Cliffs, synthesized (no recordings): python pacific_audio.py SECONDS [FADE_IN] > out.s16le

48 kHz stereo s16le. Long-period groundswell: waves about every 15 s (4 a minute, a very slow breath),
arriving in sets of a few bigger waves then a lull. Each one is a long swell, a deep low boom as it
breaks on the reef, and a slow wash back over the cobbles with a faint stone rattle. Deep bed under it.
No gulls, no sea lions, no thunder. Timing and size drift, so it never loops.
"""
import sys
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

SR = 48000
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
FADE_IN = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
CH = 60
rng = np.random.default_rng(1017)


def bw(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


class F:
    def __init__(self, sos):
        self.s, self.z = sos, [sosfilt_zi(sos) * 0, sosfilt_zi(sos) * 0]

    def __call__(self, x, i):
        y, self.z[i] = sosfilt(self.s, x, zi=self.z[i])
        return y


bed_lp, bed_hp = F(bw("low", 320)), F(bw("high", 25))
breeze = F(bw("band", [180, 1400]))
master = F(bw("low", 8500))
# filter banks for wave noise: low roar, mid break, high fizz
BANDS = [bw("low", 260), bw("band", [260, 1800]), bw("band", [1600, 6500]), bw("low", 95, 4)]
RATTLE = bw("band", [1200, 4200])


def wave(dur, size):
    """One wave as stereo noise shaped by three envelopes. dur in seconds."""
    n = int(dur * SR); t = np.arange(n) / SR
    peak = dur * rng.uniform(0.32, 0.42)
    swell = np.where(t < peak, (t / peak) ** 2.2, np.exp(-(t - peak) / (dur * 0.22)))
    brk = np.exp(-((t - peak - 0.25) / 0.9) ** 2) * 0.8 + np.where(t > peak, np.exp(-(t - peak) / 1.6), 0) * 0.6
    fizz = np.where(t > peak, (1 - np.exp(-(t - peak) / 0.6)) * np.exp(-(t - peak) / (dur * 0.35)), 0)
    boom = np.where(t > peak - 0.2, np.exp(-np.maximum(t - peak + 0.2, 0) / 1.4), 0) * np.clip((t - peak + 0.6) / 0.4, 0, 1)
    env = [swell, brk, fizz, boom]
    gains = [1.0, 0.45, 0.26, 2.2]
    out = np.zeros((2, n))
    pan = rng.uniform(-0.3, 0.3)
    # cobble rattle on the backwash: sparse soft clicks
    clicks = (rng.random(n) < 90 / SR) * rng.standard_normal(n)
    clicks = sosfilt(RATTLE, np.convolve(clicks, np.hanning(48), "same")) * fizz * 0.5
    for i in range(2):
        acc = np.zeros(n)
        for b, e, g in zip(BANDS, env, gains):
            acc += sosfilt(b, rng.standard_normal(n)) * e * g
        acc += np.roll(clicks, i * 37)
        out[i] = acc * size * (1 + (pan if i else -pan))
    # fade edges so overlapping waves join smoothly
    r = min(n // 10, SR)
    out[:, :r] *= np.linspace(0, 1, r); out[:, -r:] *= np.linspace(1, 0, r)
    return out


buf = np.zeros((2, SR * 60))   # carries wave tails across chunk edges
next_wave = 1.5
set_left, set_size = 4, 1.0
out = sys.stdout.buffer
for c0 in range(0, DUR, CH):
    n = SR * min(CH, DUR - c0)
    t = (c0 * SR + np.arange(n)) / SR
    mix = np.zeros((2, n + SR * 60))
    mix[:, :buf.shape[1]] += buf
    while next_wave < c0 + CH:
        if set_left <= 0:                      # lull between sets, then a new set of 3-5
            next_wave += rng.uniform(8, 18)
            set_left = int(rng.integers(3, 6)); set_size = float(np.clip(rng.lognormal(0, 0.2), 0.8, 1.3))
        size = set_size * float(np.clip(rng.lognormal(0, 0.18), 0.75, 1.25)) * 0.55
        dur = rng.uniform(15, 20)
        w = wave(dur, size)
        s = int((next_wave - c0) * SR)
        mix[:, s:s + w.shape[1]] += w
        next_wave += rng.normal(15.0, 1.4); set_left -= 1
    for i in range(2):
        mix[i, :n] += bed_hp(bed_lp(rng.standard_normal(n), i), i) * 1.5
        b = breeze(rng.standard_normal(n), i)
        mix[i, :n] += b * 0.05 * (0.6 + 0.4 * np.sin(2 * np.pi * t / 47 + i))
    buf = mix[:, n:].copy()
    y = mix[:, :n]
    for i in range(2):
        y[i] = master(y[i], i)
    y *= np.clip(t / FADE_IN, 0, 1) * np.clip((DUR - t) / 60, 0, 1) * 0.39
    y = np.tanh(y * 1.1) / 1.1
    out.write((np.clip(y.T, -1, 1) * 32000).astype("<i2").tobytes())
    print(f"pacific {c0 + CH}s", file=sys.stderr, flush=True)
