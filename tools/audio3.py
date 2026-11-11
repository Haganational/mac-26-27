"""Audio for 'Lost in Athens, part three'. Imported by athens3.py."""
import subprocess, sys, wave, json
from pathlib import Path
import numpy as np
SR = 24000; HERE = Path(__file__).parent; SPEED = 1.17
rng = np.random.default_rng(7)
def load(p, speed=1.0, trim=True, norm=.89):
    tmp = HERE / "_t.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(p), "-af", f"atempo={speed}", "-ac", "1", "-ar", str(SR), str(tmp)], check=True)
    with wave.open(str(tmp)) as w: a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if trim:
        idx = np.nonzero(np.abs(a) > 0.012)[0]
        if len(idx): a = a[max(0, idx[0] - 1000): idx[-1] + 2000]
    return (a * (norm / (np.abs(a).max() or 1))).astype(np.float32) if norm else a
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def box(x, n): return np.convolve(x, np.ones(n, np.float32) / n, "same")
def phone_fx(a):      # band-limited, a little crunchy: the voice on the other end of the line
    b = box(a, 5) - box(a, 70); b = np.tanh(b * 3.2) * .6
    return b.astype(np.float32)
def tv_fx(a):         # small TV speaker in the room
    b = box(a, 4) - box(a, 50); echo = np.zeros_like(b); d = int(.045 * SR); echo[d:] = b[:-d] * .35
    return (b + echo).astype(np.float32)
def static(d):
    x = rng.normal(0, 1, int(d * SR)).astype(np.float32); x = x - box(x, 4) * .5
    return x * (.8 + .2 * np.sin(2 * np.pi * 60 * np.arange(len(x)) / SR))
def tone(d, f=1000):
    tt = np.arange(int(d * SR)) / SR; return np.sin(2 * np.pi * f * tt).astype(np.float32)
def click():
    tt = np.arange(int(.09 * SR)) / SR; return (np.sin(2 * np.pi * 180 * tt) * np.exp(-tt * 60) + rng.normal(0, .5, len(tt)) * np.exp(-tt * 220)).astype(np.float32)
def bell(d=3.6):      # mechanical two-gong telephone bell: 2s on, 4s off cadence shortened
    tt = np.arange(int(d * SR)) / SR; s = np.zeros_like(tt)
    for f, g in ((1210, 1), (1510, .8), (2390, .5), (3170, .35), (4630, .2)): s += g * np.sin(2 * np.pi * f * tt + 3 * np.sin(2 * np.pi * 20 * tt))
    clap = (.5 + .5 * np.sign(np.sin(2 * np.pi * 21 * tt)))
    env = ((tt % 2.2) < 1.25).astype(np.float32); env = box(env, 300)
    return (s * (.55 + .45 * clap) * env * .09).astype(np.float32)
def sitcom_sting(d=2.6):   # warm little major-seventh vamp for the cut to the couch
    out = np.zeros(int(d * SR) + SR, np.float32)
    def ep(m, t0, dur=.9, g=.1):
        tt = np.arange(int(dur * SR)) / SR; f = hz(m)
        s = (np.sin(2 * np.pi * f * tt + 1.6 * np.exp(-tt * 6) * np.sin(2 * np.pi * f * 2 * tt))) * np.exp(-tt * 3.2) * np.minimum(1, tt * 300)
        i = int(t0 * SR); out[i:i + len(s)] += s.astype(np.float32) * g
    for k, ch in enumerate(([53, 60, 64, 69], [55, 62, 65, 71], [57, 64, 67, 72], [60, 67, 71, 76])):
        for j, m in enumerate(ch): ep(m, k * .42 + j * .035, 1.4 if k == 3 else .6)
    for k, m in enumerate((41, 43, 45, 48)): ep(m, k * .42, .5, .16)
    return out[:int(d * SR)]
def anthem(beats_per_min=100):
    """Original stately hymn in E-flat: brass choir, strings, timpani. 8 bars of 4."""
    beat = 60 / beats_per_min; n = int((34 * beat + 4) * SR); out = np.zeros(n, np.float32)
    def add(s, t0, g):
        i = int(t0 * SR); out[i:i + len(s)] += s[:n - i] * g
    def brass(m, d, bright=1.6):
        tt = np.arange(int(d * SR)) / SR; f = hz(m) * (1 + .004 * np.sin(2 * np.pi * 5 * tt) * np.minimum(1, tt * 1.5))
        ph = 2 * np.pi * np.cumsum(f) / SR; s = sum(np.sin(k * ph) / k ** bright for k in range(1, 9))
        return (s * np.minimum(1, tt * 14) * np.minimum(1, (d - tt) * 9) * (.8 + .2 * np.exp(-tt * 5))).astype(np.float32)
    def strings(m, d):
        tt = np.arange(int(d * SR)) / SR; s = 0
        for det in (-.07, 0, .06):
            ph = 2 * np.pi * hz(m + det) * tt; s = s + sum(np.sin(k * ph) / k for k in range(1, 7))
        return (s / 3 * np.minimum(1, tt * 3.5) * np.minimum(1, (d - tt) * 3)).astype(np.float32)
    def timp(m, g=1.0):
        tt = np.arange(int(1.3 * SR)) / SR; f = hz(m) * (1 + .25 * np.exp(-tt * 30))
        return ((np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3.5) + rng.normal(0, .25, len(tt)) * np.exp(-tt * 40)) * g).astype(np.float32)
    def cym(d=2.5):
        x = rng.normal(0, 1, int(d * SR)).astype(np.float32); x = x - box(x, 3); tt = np.arange(len(x)) / SR
        return x * np.minimum(1, tt * 2.2) ** 2 * np.exp(-np.maximum(0, tt - .45) * 2.2)
    E = 63  # E-flat 4
    # melody (semitones above Eb4, beats)
    mel = [(7, 1.5), (7, .5), (9, 1), (7, 1),  (12, 2), (11, 1), (9, 1),  (7, 1.5), (4, .5), (5, 1), (7, 1),  (4, 3), (None, 1),
           (9, 1.5), (9, .5), (11, 1), (12, 1),  (14, 2), (16, 1), (14, 1),  (12, 1.5), (9, .5), (11, 1), (14, 1),  (12, 6)]
    chords = [(0, [0, 4, 7]), (4, [5, 9, 12]), (6, [7, 11, 14]), (8, [0, 4, 7]), (10, [5, 9, 12]), (12, [0, 4, 7]),
              (16, [5, 9, 12]), (20, [7, 11, 14]), (22, [9, 12, 16]), (24, [5, 9, 12]), (26, [7, 11, 14]), (28, [0, 4, 7])]
    t = 0
    for m, d in mel:
        if m is not None:
            add(brass(E + m, d * beat * .97), t * beat, .075); add(brass(E + m - 12, d * beat * .97, 1.9), t * beat, .05)
            add(strings(E + m + 12, d * beat), t * beat, .016)
        t += d
    for k, (b0, ch) in enumerate(chords):
        b1 = chords[k + 1][0] if k + 1 < len(chords) else 34
        d = (b1 - b0) * beat
        for m in ch: add(strings(E + m - 12, d + .15), b0 * beat, .02); add(brass(E + m - 12, d * .98, 2.2), b0 * beat, .022)
        add(brass(E + ch[0] - 24, d * .98, 1.4), b0 * beat, .07)
        add(timp(E + ch[0] - 24, 1.0 if b0 % 4 == 0 else .6), b0 * beat, .16)
    for b in (15, 15.5, 27, 27.33, 27.66): add(timp(E + 7 - 24, .7), b * beat, .12)
    add(cym(), 15 * beat - .6, .05); add(cym(3.2), 28 * beat - 1.0, .09)
    # hall
    wet = np.zeros_like(out)
    for dl, g in ((.031, .5), (.047, .42), (.071, .36), (.113, .3), (.171, .24), (.263, .18), (.397, .12)):
        k = int(dl * SR); wet[k:] += out[:-k] * g
    out = out * .8 + box(wet, 6) * .5
    return out, beat
if __name__ == "__main__":
    a, _ = anthem(); a = a / np.abs(a).max() * .8
    for nm, x in (("anthem", a), ("bell", bell() * 4), ("sting", sitcom_sting() * 3)):
        with wave.open(str(HERE / f"_{nm}.wav"), "w") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
        print(nm, len(x) / SR)
