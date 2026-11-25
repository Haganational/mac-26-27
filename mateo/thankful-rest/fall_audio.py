"""Thankful Rest, fall rustling winds, synthesized (no recordings): python fall_audio.py SECONDS [FADE_IN] > out.s16le

48 kHz stereo s16le. A mild autumn afternoon in the trees: a soft low breeze always moving, slow gusts
that swell for a few seconds and let go, and with each gust the dry leaves overhead rustle (thousands of
tiny crisp clicks, brighter as the gust peaks) and settle back to a whisper. Now and then a few leaves
skitter across the ground. No birds, no voices, no music, nothing sudden. Timing drifts, so it never loops.
"""
import sys
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

SR = 48000
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
FADE_IN = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
CH = 60
CR = 100
rng = np.random.default_rng(11262026)


def bw(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


class F:
    def __init__(self, sos):
        self.s, self.z = sos, [sosfilt_zi(sos) * 0, sosfilt_zi(sos) * 0]

    def __call__(self, x, i):
        y, self.z[i] = sosfilt(self.s, x, zi=self.z[i])
        return y


AIR = [F(bw("band", f)) for f in ([70, 220], [200, 520], [480, 1200])]
LEAF = [F(bw("band", [1800, 4200])), F(bw("band", [3800, 9000]))]
leaf_body = [F(bw("band", [700, 1800]))]
skit = F(bw("band", [1500, 6000]))
master = F(bw("low", 11000, 2))
house = F(bw("high", 30))


class Gusts:
    def __init__(self, lo, hi):
        self.events, self.next, self.lo, self.hi = [], 1.0, lo, hi

    def env(self, c0, n):
        t = c0 + np.arange(int(n * CR / SR)) / CR
        while self.next < c0 + CH + 30:
            rise, fall = rng.uniform(2.5, 6), rng.uniform(4, 9)
            self.events.append((self.next, rise, fall, float(np.clip(rng.lognormal(0, 0.35), 0.4, 1.6))))
            self.next += rng.uniform(self.lo, self.hi) if rng.random() > 0.15 else rng.uniform(25, 50)
        e = np.zeros_like(t)
        for s, r, f, a in self.events:
            x = t - s
            u = np.clip(x / r, 0, 1); u = u * u * (3 - 2 * u)
            e += a * np.where(x < r, u, np.exp(-(x - r) / f)) * (x > 0)
        self.events = [ev for ev in self.events if ev[0] + ev[1] + 8 * ev[2] > c0]
        return t, e


def up(ctrl, n):
    return np.interp(np.arange(n), np.linspace(0, n - 1, len(ctrl)), ctrl)


gl, gr = Gusts(7, 20), Gusts(7, 20)    # the trees left and right catch the wind at slightly different times
shared = Gusts(10, 26)
skitter_next = 20.0
out = sys.stdout.buffer
for c0 in range(0, DUR, CH):
    n = SR * min(CH, DUR - c0)
    t = (c0 * SR + np.arange(n)) / SR
    _, gs = shared.env(c0, n)
    side = [gl.env(c0, n)[1], gr.env(c0, n)[1]]
    y = np.zeros((2, n))
    for i in range(2):
        g = up(0.35 + gs * 0.45 + side[i] * 0.3, n)
        a = np.zeros(n)
        for k, band in enumerate(AIR):
            a += band(rng.standard_normal(n), i) * (1.0, 0.55, 0.22)[k] * (0.4 + 0.6 * g) ** k
        y[i] += a * g * 0.9
        # leaf rustle: sparse crisp clicks, their rate and brightness ride the gust
        rate = 400 + 5200 * np.clip(g - 0.3, 0, None) ** 1.4
        clicks = (rng.random(n) < rate / SR) * rng.standard_normal(n)
        r1 = LEAF[0](clicks, i); r2 = LEAF[1](clicks, i)
        y[i] += (r1 * 1.1 + r2 * 0.55 * np.clip(g, 0, 1.3)) * 0.55
        y[i] += leaf_body[0](clicks, i) * 0.25
    # now and then a few leaves skitter across the ground, panned to one side
    while skitter_next < c0 + CH:
        s = int((skitter_next - c0) * SR); L = int(rng.uniform(0.8, 2.2) * SR)
        if s + L < n:
            e = np.sin(np.linspace(0, np.pi, L)) ** 2
            burst = (rng.random(L) < 900 / SR) * rng.standard_normal(L) * e * rng.uniform(0.25, 0.5)
            p = rng.uniform(0.2, 0.8)
            for i in range(2):
                y[i, s:s + L] += skit(burst, i) * (p if i else 1 - p)
        skitter_next += rng.uniform(25, 90)
    for i in range(2):
        y[i] = house(master(y[i], i), i)
    y *= np.clip(t / FADE_IN, 0, 1) * np.clip((DUR - t) / 60, 0, 1) * 0.74
    y = np.tanh(y * 1.1) / 1.1
    out.write((np.clip(y.T, -1, 1) * 32000).astype("<i2").tobytes())
    print(f"fall {c0 + CH}s", file=sys.stderr, flush=True)
