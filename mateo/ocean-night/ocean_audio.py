"""Night ocean waves, synthesized (no recordings): python ocean_audio.py SECONDS [FADE_IN] > out.s16le

48 kHz stereo s16le. Waves arrive about every 10 s (6 a minute, a slow-breathing pace), each one a
swell, a soft break and a long fizzing wash back down the sand, over a distant surf bed and a light
breeze. Wave size and timing drift so it never sounds looped. No gulls, no thunder, no peaks.
"""
import sys
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

SR = 48000
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
FADE_IN = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
CH = 60
rng = np.random.default_rng(1121)


def bw(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


class F:
    def __init__(self, sos):
        self.s, self.z = sos, [sosfilt_zi(sos) * 0, sosfilt_zi(sos) * 0]

    def __call__(self, x, i):
        y, self.z[i] = sosfilt(self.s, x, zi=self.z[i])
        return y


bed_lp, bed_hp = F(bw("low", 500)), F(bw("high", 30))
breeze = F(bw("band", [180, 1400]))
master = F(bw("low", 8500))
# filter banks for wave noise: low roar, mid break, high fizz
BANDS = [bw("low", 350), bw("band", [300, 2200]), bw("band", [1800, 7500])]


def wave(dur, size):
    """One wave as stereo noise shaped by three envelopes. dur in seconds."""
    n = int(dur * SR); t = np.arange(n) / SR
    peak = dur * rng.uniform(0.32, 0.42)
    swell = np.where(t < peak, (t / peak) ** 2.2, np.exp(-(t - peak) / (dur * 0.22)))
    brk = np.exp(-((t - peak - 0.25) / 0.9) ** 2) * 0.8 + np.where(t > peak, np.exp(-(t - peak) / 1.6), 0) * 0.6
    fizz = np.where(t > peak, (1 - np.exp(-(t - peak) / 0.6)) * np.exp(-(t - peak) / (dur * 0.35)), 0)
    env = [swell, brk, fizz]
    gains = [1.0, 0.55, 0.32]
    out = np.zeros((2, n))
    pan = rng.uniform(-0.25, 0.25)
    for i in range(2):
        acc = np.zeros(n)
        for b, e, g in zip(BANDS, env, gains):
            acc += sosfilt(b, rng.standard_normal(n)) * e * g
        out[i] = acc * size * (1 + (pan if i else -pan))
    # fade edges so overlapping waves join smoothly
    r = min(n // 10, SR)
    out[:, :r] *= np.linspace(0, 1, r); out[:, -r:] *= np.linspace(1, 0, r)
    return out


buf = np.zeros((2, SR * 40))   # carries wave tails across chunk edges
next_wave = 1.5
out = sys.stdout.buffer
for c0 in range(0, DUR, CH):
    n = SR * min(CH, DUR - c0)
    t = (c0 * SR + np.arange(n)) / SR
    mix = np.zeros((2, n + SR * 40))
    mix[:, :buf.shape[1]] += buf
    while next_wave < c0 + CH:
        size = float(np.clip(rng.lognormal(0, 0.28), 0.6, 1.5)) * 0.6
        dur = rng.uniform(11, 15)
        w = wave(dur, size)
        s = int((next_wave - c0) * SR)
        mix[:, s:s + w.shape[1]] += w
        next_wave += rng.normal(10.0, 1.2)
        if rng.random() < 0.06:   # now and then a set of bigger, closer waves eases in
            next_wave += rng.uniform(1, 4)
    for i in range(2):
        mix[i, :n] += bed_hp(bed_lp(rng.standard_normal(n), i), i) * 1.5
        b = breeze(rng.standard_normal(n), i)
        mix[i, :n] += b * 0.05 * (0.6 + 0.4 * np.sin(2 * np.pi * t / 47 + i))
    buf = mix[:, n:].copy()
    y = mix[:, :n]
    for i in range(2):
        y[i] = master(y[i], i)
    y *= np.clip(t / FADE_IN, 0, 1) * np.clip((DUR - t) / 60, 0, 1) * 0.30
    y = np.tanh(y * 1.1) / 1.1
    out.write((np.clip(y.T, -1, 1) * 32000).astype("<i2").tobytes())
    print(f"ocean {c0 + CH}s", file=sys.stderr, flush=True)
