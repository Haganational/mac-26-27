"""An original salsa run-up for a film's opening plates (Matthew, Nov 16 2026: "a salsa jam crescendo
run up... ode to Calle Ocho"). Everything is synthesized here, so there is nothing to license.

    python tools/doc_salsa.py <seconds> <out.wav>

Layers come in one at a time (clave, congas, bass, piano montuno, cowbell, horns) and it ends on a hit.
"""
import sys
import wave

import numpy as np

SR = 48000
BPM = 188
BEAT = 60 / BPM
EIGHTH = BEAT / 2
rng = np.random.default_rng(8)


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def env(n, a=0.002, d=0.2):
    t = np.arange(n) / SR
    return np.minimum(t / a, 1) * np.exp(-t / d)


def put(buf, t, snd, g=1.0):
    i = int(t * SR)
    if i >= len(buf) or i < 0:
        return
    snd = snd[: len(buf) - i]
    buf[i:i + len(snd)] += g * snd


def clave():
    n = int(0.09 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 2450 * t) + 0.4 * np.sin(2 * np.pi * 3700 * t)) * env(n, 0.0005, 0.018)


def conga(f=210, slap=False):
    n = int(0.22 * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (f * (1 + 0.25 * np.exp(-t / 0.012))) * t) * env(n, 0.001, 0.07 if not slap else 0.03)
    noise = rng.standard_normal(n) * env(n, 0.0005, 0.008 if not slap else 0.02) * (0.25 if not slap else 0.7)
    return body + noise


def bell():
    n = int(0.16 * SR); t = np.arange(n) / SR
    s = np.sign(np.sin(2 * np.pi * 562 * t)) + np.sign(np.sin(2 * np.pi * 845 * t))
    return s * env(n, 0.0005, 0.05) * 0.35


def piano(m, dur=0.22):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m)
    s = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.4 for k in range(1, 7))
    return s * env(n, 0.002, 0.16)


def bass(m, dur):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m)
    s = np.sin(2 * np.pi * f * t) + 0.45 * np.sin(2 * np.pi * 2 * f * t) + 0.15 * np.sin(2 * np.pi * 3 * f * t)
    return s * np.minimum(t / 0.004, 1) * np.exp(-t / (dur * 0.9))


def horn(ms, dur):
    n = int(dur * SR); t = np.arange(n) / SR; out = np.zeros(n)
    for m in ms:
        f = hz(m) * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * t))
        ph = 2 * np.pi * np.cumsum(f) / SR
        out += sum(np.sin(k * ph) / k for k in range(1, 9))
    e = np.minimum(t / 0.02, 1) * np.minimum((dur - t) / 0.04, 1).clip(0, 1)
    return out * e / len(ms)


def timbal(f=330):
    n = int(0.25 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.59 * t)) * env(n, 0.0005, 0.06) + rng.standard_normal(n) * env(n, 0.0005, 0.012) * 0.5


def build(seconds):
    n = int(seconds * SR); mix = np.zeros(n)
    bar = 4 * BEAT
    hit_t = seconds - 0.9                      # the final hit
    bars = int(hit_t // bar)
    start = hit_t - bars * bar                 # so the hit lands on a downbeat
    # A minor: Am | Dm | E7 | Am  (roots and chord tones, MIDI)
    chords = [(45, [57, 60, 64]), (50, [57, 62, 65]), (52, [56, 59, 62]), (45, [57, 60, 64])]
    clave_beats = [1, 2, 4, 5.5, 7]
    for b in range(bars):
        t0 = start + b * bar
        prog = b / max(1, bars - 1)            # 0..1 across the build
        g = 0.55 + 0.45 * prog
        root, tones = chords[b % 4]
        # clave from the first bar
        for cb in clave_beats:
            if int(cb // 4) == b % 2:
                put(mix, t0 + (cb % 4) * BEAT, clave(), 0.5 * g)
        if prog >= 0.12:                       # congas: tumbao
            for e8, (f, sl) in enumerate([(210, False), (210, False), (260, True), (210, False), (210, False), (210, False), (300, False), (300, False)]):
                put(mix, t0 + e8 * EIGHTH, conga(f, sl), (0.42 if e8 in (2, 6, 7) else 0.2) * g)
        if prog >= 0.28:                       # bass: anticipated tumbao (and of 2, 4)
            nxt = chords[(b + 1) % 4][0]
            put(mix, t0 + 1.5 * BEAT, bass(root + 7, BEAT * 1.4), 0.55 * g)
            put(mix, t0 + 3 * BEAT, bass(nxt, BEAT * 1.9), 0.65 * g)
        if prog >= 0.42:                       # piano montuno in octaves
            pat = [0, 1, 2, 1, 0, 1, 2, 1]
            for e8, k in enumerate(pat):
                if e8 in (0, 3):               # leave air on the downbeat and the and-of-2
                    continue
                m = tones[k]
                put(mix, t0 + e8 * EIGHTH, piano(m + 12) + piano(m + 24) * 0.7, 0.2 * g)
        if prog >= 0.58:                       # cowbell on the beat, louder on 1 and 3
            for q in range(4):
                put(mix, t0 + q * BEAT, bell(), (0.5 if q % 2 == 0 else 0.3) * g)
        if prog >= 0.72:                       # horns: off-beat stabs, climbing
            lift = 12 if prog > 0.88 else 0
            for q in (0.5, 2, 3.5):
                put(mix, t0 + q * BEAT, horn([t + 12 + lift for t in tones], BEAT * 0.42), 0.34 * g)
    # timbale roll into the hit, last bar
    roll0 = hit_t - bar
    k = 0; t = roll0 + 2 * BEAT
    while t < hit_t - 0.02:
        put(mix, t, timbal(300 + 12 * k), 0.25 + 0.5 * (t - roll0) / bar)
        t += EIGHTH / 2; k += 1
    # the hit: full band on A minor, long horn, low drum
    put(mix, hit_t, horn([57, 64, 69, 72, 76], 0.8), 0.9)
    put(mix, hit_t, bass(33, 0.9), 1.0)
    put(mix, hit_t, timbal(220), 0.9); put(mix, hit_t, bell(), 0.8); put(mix, hit_t, conga(180), 0.8)
    # overall swell, soft start, clean tail
    tt = np.arange(n) / SR
    mix *= 0.6 + 0.4 * np.clip(tt / hit_t, 0, 1) ** 1.3
    mix *= np.clip(tt / 0.4, 0, 1) * np.clip((seconds - tt) / 0.25, 0, 1)
    mix = np.tanh(mix * 1.1)
    return mix / (np.abs(mix).max() + 1e-9) * 0.85


if __name__ == "__main__":
    secs, out = float(sys.argv[1]), sys.argv[2]
    x = (build(secs) * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(x.tobytes())
