"""Rain on a window over deep brown noise. Every sound is synthesized here: no recordings.

python rain_audio.py SECONDS > out.s16le   (48 kHz stereo, signed 16-bit little-endian)
Steady by design for sleep: no thunder, no music, no sudden peaks. Never loops: each minute is new.
"""
import sys
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi, oaconvolve

SR = 48000
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
CH = 60
FADE_IN = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
rng = np.random.default_rng(2026_11_20)


class F:
    """Stateful stereo filter so 60 s chunks join without clicks."""
    def __init__(self, sos):
        self.s, self.z = sos, [sosfilt_zi(sos) * 0, sosfilt_zi(sos) * 0]

    def __call__(self, x, i):
        y, self.z[i] = sosfilt(self.s, x, zi=self.z[i])
        return y


def bw(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


brown_lp, brown_hp = F(bw("low", 180)), F(bw("high", 22))
hiss_bp, hiss_tilt = F(bw("band", [350, 7000])), F(bw("low", 3200, 1))
master = F(bw("low", 9000))
slow = F(butter(1, 0.02, fs=SR, output="sos"))

# droplet grains: kernels of short filtered noise, several timbres
def grains(n, lo, hi, dlo, dhi):
    out = []
    for _ in range(n):
        L = int(SR * rng.uniform(dlo, dhi)) + 1
        g = sosfilt(bw("band", [lo * rng.uniform(.8, 1.2), hi * rng.uniform(.8, 1.2)]), rng.standard_normal(L + 96))[96:]
        g *= np.exp(-np.arange(L) / (L * 0.3))
        out.append(g / (np.abs(g).max() + 1e-9))
    return out

fine = grains(8, 2500, 9000, 0.0004, 0.002)     # the patter on glass
tick = grains(6, 900, 3500, 0.002, 0.008)       # bigger drops
plinks = []                                      # gutter drip: soft pitched plink
for f0 in (620, 700, 760, 840, 910):
    L = int(SR * 0.09); t = np.arange(L) / SR
    plinks.append(np.sin(2 * np.pi * f0 * t * (1 + 0.15 * np.exp(-t * 60))) * np.exp(-t * 38) * (1 - np.exp(-t * 3000)))

carry = np.zeros((2, SR))
drip_phase, drip_on, drip_next = 0.0, True, 0.0
out = sys.stdout.buffer
for c0 in range(0, DUR, CH):
    n = SR * min(CH, DUR - c0)
    t = (c0 * SR + np.arange(n)) / SR
    # very slow, small intensity drift (about +-1.5 dB over minutes)
    drift = 1 + 0.18 * np.tanh(3 * slow(np.repeat(rng.standard_normal(n // SR + 2), SR)[:n] * 6, 0))
    mix = np.zeros((2, n + SR))
    for i in range(2):
        b = brown_hp(brown_lp(rng.standard_normal(n), i), i)
        mix[i, :n] += b * 2.2
        h = hiss_bp(rng.standard_normal(n), i)
        mix[i, :n] += (0.55 * h + 0.45 * hiss_tilt(h, i)) * 0.16 * drift
    # patter: dense impulses convolved with grain kernels (fast, never repeats)
    for kern, rate, amp in ((fine, 260, 0.05), (tick, 9, 0.11)):
        for k, g in enumerate(kern):
            for i in range(2):
                imp = np.zeros(n)
                m = rng.poisson(rate / len(kern) * n / SR * drift.mean())
                pos = rng.integers(0, n, m)
                np.add.at(imp, pos, np.exp(rng.normal(-1.0, 0.5, m)))
                mix[i, :n + len(g) - 1] += oaconvolve(imp, g)[: n + len(g) - 1] * amp
    # gutter drip: comes and goes in phases of a few minutes, one side, soft
    s = 0.0
    while s < CH and c0 + s < DUR:
        if drip_on:
            p = int(s * SR)
            g = plinks[rng.integers(len(plinks))] * rng.uniform(0.025, 0.045)
            mix[0, p:p + len(g)] += g * 0.75; mix[1, p:p + len(g)] += g * 0.35
        s += rng.uniform(2.6, 4.2)
        if rng.random() < 0.012:
            drip_on = not drip_on
    mix[:, :SR] += carry
    carry = mix[:, n:n + SR].copy()
    y = mix[:, :n]
    for i in range(2):
        y[i] = master(y[i], i)
    y *= np.clip(t / FADE_IN, 0, 1) * np.clip((DUR - t) / 60, 0, 1) * 0.35
    y = np.tanh(y * 1.1) / 1.1
    out.write((np.clip(y.T, -1, 1) * 32000).astype("<i2").tobytes())
    print(f"rain {c0 + CH}s", file=sys.stderr, flush=True)
