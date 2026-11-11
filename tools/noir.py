import numpy as np
SR=24000
rng=np.random.default_rng(5)
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def noir_music(n):
    out = np.zeros(n + SR * 6, np.float32); beat = 60 / 66
    def add(sig, t0, g):
        i = int(t0 * SR)
        if 0 <= i < n: out[i: i + len(sig)] += sig[: len(out) - i] * g
    def pluck(m, d=0.9):
        tt = np.arange(int(d * SR)) / SR; f = hz(m)
        return ((np.sin(2 * np.pi * f * tt) + 0.45 * np.sin(4 * np.pi * f * tt) + 0.18 * np.sin(6 * np.pi * f * tt)) * np.exp(-tt * 4.2) * np.minimum(1, tt * 200)).astype(np.float32)
    def keys(ms, d=3.4):
        tt = np.arange(int(d * SR)) / SR; s = 0
        for m in ms: s = s + np.sin(2 * np.pi * hz(m) * tt)
        return (s / len(ms) * np.exp(-tt * 1.1) * (1 + 0.25 * np.sin(2 * np.pi * 4.6 * tt)) * np.minimum(1, tt * 60)).astype(np.float32)
    def horn(m, d):
        tt = np.arange(int(d * SR)) / SR; f = hz(m) * (1 + 0.006 * np.sin(2 * np.pi * 5.2 * tt) * np.minimum(1, tt * 2))
        ph = 2 * np.pi * np.cumsum(f) / SR; s = sum(np.sin(k * ph) / k ** 1.5 for k in range(1, 7))
        return (s * np.minimum(1, tt * 9) * np.minimum(1, (d - tt) * 5)).astype(np.float32)
    def brush(d=0.22):
        x = rng.normal(0, 1, int(d * SR)).astype(np.float32); x = x - np.convolve(x, np.ones(6) / 6, "same")
        tt = np.arange(len(x)) / SR; return x * np.sin(np.pi * tt / d) ** 2
    bars = [([38, 41, 45, 48], [50, 53, 57, 60, 64]), ([34, 38, 41, 45], [46, 50, 53, 57]), ([31, 34, 38, 41], [43, 46, 50, 53]), ([33, 37, 40, 45], [45, 49, 52, 55, 58])]
    b = 0
    while b * beat < n / SR:
        tm = b * beat; bar = bars[(b // 4) % 4]
        add(pluck(bar[0][b % 4]), tm, 0.11)
        if b % 4 == 0: add(keys(bar[1]), tm + 0.02, 0.06)
        add(brush(), tm + (beat * 0.5 if b % 2 else 0), 0.02)
        b += 1
    mel = [(69, 2.5), (65, 1), (62, 2.5), (None, 2), (64, 1.5), (65, .5), (64, 1), (57, 3), (None, 3), (62, 1), (65, 1), (69, 1.5), (72, .5), (70, 3), (None, 3)]
    tm, k = 0.5, 0
    while tm < n / SR - 2:
        m, d = mel[k % len(mel)]; d *= beat
        if m: add(horn(m, d * 0.96), tm, 0.03)
        tm += d; k += 1
    r = rng.normal(0, 1, n).astype(np.float32); r = np.convolve(r, np.ones(5) / 5, "same") - np.convolve(r, np.ones(80) / 80, "same")
    out = out[:n] + r * 0.07
    tt = np.arange(n) / SR
    return out * np.clip(tt / 1.0, 0, 1) * np.clip((n / SR - tt) / 0.25, 0, 1)

