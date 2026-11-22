"""Bay breezes, synthesized (no recordings): python bay_audio.py SECONDS [FADE_IN] > out.s16le

48 kHz stereo s16le. A soft onshore wind that rises and falls in long gusts (20-60 s) through dry grass and
cypress, small bay water lapping at a seawall every few seconds, a low bed under it, and once in a long
while a far-off two-tone foghorn, very faint, out past the bridge. No gulls, no traffic, no music.
Gust timing, lap timing and the horn drift, so it never loops.
"""
import sys
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

SR = 48000
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
FADE_IN = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
CH = 60
rng = np.random.default_rng(910)


def bw(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


class F:
    def __init__(self, sos):
        self.s, self.z = sos, [sosfilt_zi(sos) * 0, sosfilt_zi(sos) * 0]

    def __call__(self, x, i):
        y, self.z[i] = sosfilt(self.s, x, zi=self.z[i])
        return y


bed_lp, bed_hp = F(bw("low", 220)), F(bw("high", 22))
wind_lo = F(bw("band", [90, 600]))
wind_mid = F(bw("band", [400, 2400]))
grass = F(bw("band", [2500, 7000]))
master = F(bw("low", 9000))
LAP = [bw("band", [150, 900]), bw("band", [900, 3500]), bw("low", 120, 4)]
HORN = bw("low", 700, 2)


class Gust:
    """Slow wind envelope: smooth random walk between targets, 20-60 s per move."""
    def __init__(self, lo, hi):
        self.lo, self.hi, self.v, self.tgt, self.left = lo, hi, (lo + hi) / 2, hi, 0.0

    def run(self, n):
        out = np.empty(n); k = 0
        while k < n:
            if self.left <= 0:
                self.start, self.tgt = self.v, rng.uniform(self.lo, self.hi)
                self.total = self.left = int(rng.uniform(20, 60) * SR)
            m = int(min(n - k, self.left))
            p = 1 - (self.left - np.arange(1, m + 1)) / self.total
            out[k:k + m] = self.start + (self.tgt - self.start) * (p * p * (3 - 2 * p))
            self.v = out[k + m - 1]; self.left -= m; k += m
        return out


def lap(size):
    """One small bay wave against the wall: soft slap then a short trickle back."""
    dur = rng.uniform(2.2, 3.6); n = int(dur * SR); t = np.arange(n) / SR
    pk = rng.uniform(0.35, 0.6)
    body = np.where(t < pk, (t / pk) ** 1.6, np.exp(-(t - pk) / 0.55))
    trickle = np.where(t > pk, (1 - np.exp(-(t - pk) / 0.15)) * np.exp(-(t - pk) / 0.9), 0)
    thump = np.exp(-((t - pk) / 0.18) ** 2)
    out = np.zeros((2, n)); pan = rng.uniform(-0.5, 0.5)
    for i in range(2):
        a = sosfilt(LAP[0], rng.standard_normal(n)) * body
        a += sosfilt(LAP[1], rng.standard_normal(n)) * trickle * 0.35
        a += sosfilt(LAP[2], rng.standard_normal(n)) * thump * 1.6
        out[i] = a * size * (1 + (pan if i else -pan))
    r = n // 12
    out[:, :r] *= np.linspace(0, 1, r); out[:, -r:] *= np.linspace(1, 0, r)
    return out


def horn():
    """Distant diaphone: two long low tones (high then low), soft attack, heavy air loss."""
    seg = []
    for f0, d in ((182.0, 2.2), (148.0, 2.6)):
        n = int(d * SR); t = np.arange(n) / SR
        ph = 2 * np.pi * f0 * t + 0.4 * np.sin(2 * np.pi * 0.7 * t)
        s = sum(np.sin(ph * h) / h ** 1.3 for h in range(1, 7))
        env = np.clip(t / 0.5, 0, 1) * np.clip((d - t) / 0.7, 0, 1)
        seg.append(s * env)
    x = np.concatenate([seg[0], np.zeros(int(0.15 * SR)), seg[1]])
    x = sosfilt(HORN, x)
    tail = np.zeros(int(3 * SR))  # crude echo off the water
    x = np.concatenate([x, tail]); e = int(0.9 * SR)
    x[e:] += x[:-e] * 0.35
    return np.vstack([x * 0.95, x * 1.05])


g_wind, g_grass = Gust(0.25, 1.0), Gust(0.1, 0.8)
buf = np.zeros((2, SR * 30))
next_lap, next_horn = 2.0, rng.uniform(150, 300)
out = sys.stdout.buffer
for c0 in range(0, DUR, CH):
    n = SR * min(CH, DUR - c0)
    t = (c0 * SR + np.arange(n)) / SR
    mix = np.zeros((2, n + SR * 30))
    mix[:, :buf.shape[1]] += buf
    while next_lap < c0 + CH:
        w = lap(float(np.clip(rng.lognormal(0, 0.25), 0.6, 1.5)) * 0.32)
        s = int((next_lap - c0) * SR); mix[:, s:s + w.shape[1]] += w
        next_lap += rng.uniform(3.5, 7.5)
    while next_horn < c0 + CH:
        h = horn(); s = int((next_horn - c0) * SR)
        lvl = 0.05 if next_horn < 3600 else 0.03   # fainter still after the first hour
        mix[:, s:s + h.shape[1]] += h * lvl
        next_horn += rng.uniform(360, 720)
    gw, gg = g_wind.run(n), g_grass.run(n)
    for i in range(2):
        mix[i, :n] += bed_hp(bed_lp(rng.standard_normal(n), i), i) * 1.1
        mix[i, :n] += wind_lo(rng.standard_normal(n), i) * gw * 0.55
        mix[i, :n] += wind_mid(rng.standard_normal(n), i) * gw ** 1.5 * 0.22
        mix[i, :n] += grass(rng.standard_normal(n), i) * (gg * gw) * 0.07
    buf = mix[:, n:].copy()
    y = mix[:, :n]
    for i in range(2):
        y[i] = master(y[i], i)
    y *= np.clip(t / FADE_IN, 0, 1) * np.clip((DUR - t) / 60, 0, 1) * 0.53
    y = np.tanh(y * 1.1) / 1.1
    out.write((np.clip(y.T, -1, 1) * 32000).astype("<i2").tobytes())
    print(f"bay {c0 + CH}s", file=sys.stderr, flush=True)
