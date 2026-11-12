"""Original classic-rock outro: crunchy power-chord riff in A, bass, drums, organ, pentatonic lead."""
import numpy as np, wave, sys
SR = 24000; rng = np.random.default_rng(11)
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def box(x, n): return np.convolve(x, np.ones(n, np.float32) / n, "same")
def ks(m, d, damp=.996, bright=.5):
    n = int(d * SR); N = int(SR / hz(m)); buf = rng.uniform(-1, 1, N).astype(np.float32); buf = box(buf, 3) * bright + buf * (1 - bright)
    out = np.empty(n, np.float32)
    reps = n // N + 1; cur = buf
    chunks = []
    for _ in range(reps):
        chunks.append(cur); cur = (cur + np.roll(cur, 1)) * .5 * damp
    return np.concatenate(chunks)[:n]
def amp(x, gain=9.0):
    x = x - box(x, 400); y = np.tanh(x * gain); y = np.tanh(y * 1.6 + .15 * y * y)
    y = box(y, 5) * .7 + box(y, 11) * .3; return y - box(y, 300)
def rock(bars=8, bpm=126, lead=True):
    beat = 60 / bpm; n = int((bars * 4 * beat + 4) * SR); gtrL = np.zeros(n, np.float32); bass = np.zeros(n, np.float32); drums = np.zeros(n, np.float32); org = np.zeros(n, np.float32); ld = np.zeros(n, np.float32)
    def put(buf, s, t0, g=1.0):
        i = int(t0 * SR); m = min(len(s), n - i)
        if m > 0: buf[i:i + m] += s[:m] * g
    def chord(root, d, mute=False):
        s = sum(ks(root + k, d, .9975 if not mute else .96) for k in (0, 7, 12)) / 3
        tt = np.arange(len(s)) / SR; return s * np.minimum(1, (d - tt) * 40)
    def kick():
        tt = np.arange(int(.22 * SR)) / SR; return (np.sin(2 * np.pi * (48 * tt + 60 * (1 - np.exp(-tt * 30)) / 30)) * np.exp(-tt * 16) + rng.normal(0, .3, len(tt)) * np.exp(-tt * 300)).astype(np.float32)
    def snare():
        tt = np.arange(int(.26 * SR)) / SR; x = rng.normal(0, 1, len(tt)); x = x - box(x, 8)
        return (x * np.exp(-tt * 15) * .8 + np.sin(2 * np.pi * 190 * tt) * np.exp(-tt * 26) * .7).astype(np.float32)
    def hat(d=.05):
        tt = np.arange(int(d * SR)) / SR; x = rng.normal(0, 1, len(tt)); x = x - box(x, 3); return (x * np.exp(-tt / d * 4)).astype(np.float32)
    def crash():
        tt = np.arange(int(1.8 * SR)) / SR; x = rng.normal(0, 1, len(tt)); x = x - box(x, 4); return (x * np.exp(-tt * 2.4)).astype(np.float32)
    def bnote(m, d):
        tt = np.arange(int(d * SR)) / SR; p = 2 * np.pi * hz(m) * tt
        return ((np.sin(p) + .5 * np.sin(2 * p) + .25 * np.sin(3 * p)) * np.exp(-tt * 2.5) * np.minimum(1, tt * 300) * np.minimum(1, (d - tt) * 60)).astype(np.float32)
    def organ(ms, d):
        tt = np.arange(int(d * SR)) / SR; s = 0
        for m in ms:
            p = 2 * np.pi * hz(m) * tt * (1 + .003 * np.sin(2 * np.pi * 6.5 * tt)); s = s + np.sin(p) + .6 * np.sin(2 * p) + .4 * np.sin(3 * p) + .2 * np.sin(4 * p)
        return (s / len(ms) * np.minimum(1, tt * 20) * np.minimum(1, (d - tt) * 12)).astype(np.float32)
    A, G, D, C, E = 45, 43, 50, 48, 40
    # two-bar riff in eighths: (eighth index, root, length in eighths)
    riff = [(0, A, 1.5), (2, A, 1), (3, A, 1.5), (5, G, 1), (6, D, 2),   (8, A, 1.5), (10, A, 1), (11, A, 1), (12, C, 1.5), (14, D, 1), (15, D, 1)]
    e = beat / 2
    for b in range(0, bars, 2):
        last = b + 2 >= bars
        for i, r, ln in riff:
            if last and i >= 12: continue
            put(gtrL, chord(r, ln * e * .96), (b * 8 + i) * e); put(bass, bnote(r - 12, ln * e * .95), (b * 8 + i) * e)
        if last:  # big finish: E ... A, let it ring
            put(gtrL, chord(E, 1.9 * e), (b * 8 + 12) * e); put(bass, bnote(E - 12, 1.9 * e), (b * 8 + 12) * e)
        for i in range(0, 16, 2):   # chug between hits
            put(gtrL, chord(A, e * .5, True), (b * 8 + i + 1) * e, .25)
        chords = [(0, [57, 61, 64]), (5, [55, 59, 62]), (6, [57, 62, 66]), (8, [57, 61, 64]), (12, [55, 60, 64]), (14, [57, 62, 66])]
        for k, (i, ms) in enumerate(chords):
            j = chords[k + 1][0] if k + 1 < len(chords) else 16; put(org, organ(ms, (j - i) * e), (b * 8 + i) * e)
    endt = bars * 4 * beat
    put(gtrL, chord(A, 3.6), endt); put(gtrL, chord(A + 12, 3.6), endt, .5); put(bass, bnote(A - 12, 3.0), endt); put(org, organ([57, 61, 64, 69], 3.4), endt)
    for b in range(bars):
        for q in range(4):
            t0 = (b * 4 + q) * beat
            if q in (0, 2): put(drums, kick(), t0, 1.0)
            if q == 2 and b % 2: put(drums, kick(), t0 + e, .8)
            if q in (1, 3): put(drums, snare(), t0, .8)
            put(drums, hat(), t0, .22); put(drums, hat(), t0 + e, .14)
        if b % 4 == 0: put(drums, crash(), b * 4 * beat, .3)
    for k in range(6): put(drums, snare(), endt - (6 - k) * e / 2 * 1.0, .45 + k * .08)     # fill into the last chord
    put(drums, crash(), endt, .45); put(drums, kick(), endt, 1.0)
    if lead:   # A minor pentatonic, starts at bar 5
        lic = [(0, 69, 1), (1, 72, 1), (2, 74, 2), (4, 76, 1.5), (5.5, 74, .5), (6, 72, 1), (7, 69, 1), (8, 72, 1), (9, 74, 1), (10, 76, 1), (11, 79, 3), (14, 81, 2),
               (16, 84, 1.5), (17.5, 81, .5), (18, 79, 1), (19, 76, 1), (20, 79, 1), (21, 81, 3), (24, 84, 1), (25, 86, 1), (26, 88, 2), (28, 81, 4)]
        t0 = (bars - 4) * 4 * beat
        for i, m, ln in lic:
            d = ln * e; tt = np.arange(int(d * SR)) / SR
            bend = 1 - .03 * np.exp(-tt * 14); vib = 1 + .008 * np.sin(2 * np.pi * 5.8 * tt) * np.minimum(1, tt * 4)
            p = 2 * np.pi * np.cumsum(hz(m) * bend * vib) / SR; s = sum(np.sin(k * p) / k for k in range(1, 6))
            put(ld, (s * np.minimum(1, tt * 80) * np.minimum(1, (d - tt) * 30)).astype(np.float32), t0 + i * e)
        put(ld, (lambda tt: (sum(np.sin(k * 2 * np.pi * np.cumsum(hz(81) * (1 + .01 * np.sin(2 * np.pi * 6 * tt))) / SR) / k for k in range(1, 6)) * np.exp(-tt * .9)).astype(np.float32))(np.arange(int(3.2 * SR)) / SR), endt)
    g = amp(gtrL, 7) ; l = amp(ld, 5)
    d2 = np.zeros(n, np.float32); k = int(.33 * SR); d2[k:] = l[:-k] * .35
    mix = g * .34 + bass * .5 + np.tanh(drums * 1.4) * .5 + org * .05 + (l + d2) * .2
    wet = np.zeros(n, np.float32)
    for dl, gg in ((.029, .3), (.053, .25), (.089, .2), (.141, .15)):
        kk = int(dl * SR); wet[kk:] += mix[:-kk] * gg
    mix = mix + box(wet, 5) * .5
    return mix / np.abs(mix).max(), beat
if __name__ == "__main__":
    a, b = rock(); print(len(a) / SR, b)
    with wave.open("_rock.wav", "w") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * .9 * 32767).astype(np.int16).tobytes())
