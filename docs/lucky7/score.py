"""Lucky Seven score, all synthesized here so there is nothing to license.

    python docs/lucky7/score.py <outdir>

Writes four cues (48 kHz mono wav):
  bugle.wav     an original bugle call on the natural notes of a B-flat bugle (about 4 s)
  fife.wav      "Yankee Doodle" (18th-century tune, public domain) on fife with snare and bass drum, played twice
  strut.wav     "Yankee Doodle" as a Philadelphia Mummers-style string band strut: banjos, saxes, glockenspiel,
                bass drum and cymbal, played three times
  strutbed.wav  the strut's rhythm section alone (banjo, bass drum, glockenspiel taps), a light bed for under talk
"""
import sys, wave
from pathlib import Path
import numpy as np

SR = 48000
rng = np.random.default_rng(1776)
NOTE = {n: i for i, n in enumerate("C C# D D# E F F# G G# A A# B".split())}


def hz(name):  # "D5", "F#4"
    p, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[p] + 12 * (o + 1) - 69) / 12)


def env(L, a=0.01, r=0.05, sus=1.0):
    t = np.arange(L) / SR; e = np.minimum(1, t / a) * sus
    rr = int(r * SR)
    if rr and rr < L:
        e[-rr:] *= np.linspace(1, 0, rr)
    return e


def lowpass(x, k=8):
    return np.convolve(x, np.ones(k) / k, "same")


def highpass(x, k=8):
    return x - lowpass(x, k)


def place(buf, x, t):
    i = int(t * SR)
    if i < 0:
        x, i = x[-i:], 0
    j = min(len(buf), i + len(x))
    if j > i:
        buf[i:j] += x[:j - i]


# ---------- instruments ----------
def fife(f, d):
    L = int(d * SR); t = np.arange(L) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.6 * t) * np.minimum(1, t / 0.15)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    x = np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph) + 0.05 * np.sin(4 * ph)
    breath = highpass(rng.standard_normal(L), 6) * 0.05
    return (x + breath) * env(L, 0.018, min(0.04, d / 3), 0.9)


def brass(f, d, bright=1.0):
    L = int(d * SR); t = np.arange(L) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.clip((t - 0.2) / 0.3, 0, 1)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    swell = np.minimum(1, t / 0.06)
    x = sum((1 / k ** 1.1) * np.clip(bright * swell * 10 - k + 1, 0, 1) * np.sin(k * ph) for k in range(1, 11))
    return x * env(L, 0.03, min(0.08, d / 3))


def sax(f, d):
    L = int(d * SR); t = np.arange(L) / SR
    vib = 1 + 0.008 * np.sin(2 * np.pi * 5.0 * t) * np.clip((t - 0.12) / 0.2, 0, 1)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    x = sum((0.85 ** k) * np.sin(k * ph + k) for k in range(1, 9)) + 0.03 * rng.standard_normal(L)
    return np.tanh(1.6 * x) * env(L, 0.025, min(0.06, d / 3))


def banjo(f, d=0.5):
    L = int(d * SR); t = np.arange(L) / SR
    x = sum(np.exp(-t * (6 + 9 * k)) / k * np.sin(2 * np.pi * f * k * t) for k in range(1, 9))
    return x * np.minimum(1, t / 0.002)


def glock(f, d=0.9):
    L = int(d * SR); t = np.arange(L) / SR
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 3.5) + 0.25 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 9)) * np.minimum(1, t / 0.001)


def snare(v=1.0, d=0.18):
    L = int(d * SR); t = np.arange(L) / SR
    n = highpass(rng.standard_normal(L), 4)
    return v * (0.8 * n * np.exp(-t * 26) + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 40))


def bass_drum(v=1.0, d=0.45):
    L = int(d * SR); t = np.arange(L) / SR
    return v * np.sin(2 * np.pi * np.cumsum(np.linspace(78, 44, L)) / SR) * np.exp(-t * 7)


def cymbal(v=1.0, d=1.2):
    L = int(d * SR); t = np.arange(L) / SR
    return v * highpass(rng.standard_normal(L), 3) * np.exp(-t * 3.2) * 0.35


# ---------- tunes ----------
# Yankee Doodle in D, one entry per eighth note; "-" holds the previous note.
YD_VERSE = ("D5 D5 E5 F#5 | D5 F#5 E5 A4 | D5 D5 E5 F#5 | D5 - C#5 - | "
            "D5 D5 E5 F#5 | G5 F#5 E5 D5 | C#5 A4 B4 C#5 | D5 - D5 -")
YD_CHORUS = ("B4 C#5 B4 A4 | B4 C#5 D5 - | A4 B4 A4 G4 | F#4 - A4 - | "
             "B4 C#5 B4 A4 | B4 C#5 D5 B4 | A4 D5 C#5 E5 | D5 - D5 -")


def notes(s):
    out = []
    for tok in s.replace("|", " ").split():
        if tok == "-":
            out[-1][1] += 1
        else:
            out.append([tok, 1])
    return out


TUNE = notes(YD_VERSE) + notes(YD_CHORUS)   # 32 eighth-note slots, 16 bars of 2/4
CHORDS = ["D", "D", "D", "A", "D", "G", "A", "D", "G", "D", "A", "D", "G", "D", "A", "D"]   # one per bar
TRIAD = {"D": ("D4", "F#4", "A4"), "G": ("G3", "B3", "D4"), "A": ("A3", "C#4", "E4")}
ROOT = {"D": "D3", "G": "G2", "A": "A2"}


def bugle_call():
    # original call on B-flat bugle harmonics (F4, Bb4, D5, F5), up a fourth here so it sits with the D-major tune
    seq = [("C5", .13), ("F5", .13), ("A5", .13), ("C6", .55), ("A5", .2), ("C6", .2), ("F5", .55), ("A5", .13), ("C6", .13), ("F6", 1.4)]
    L = int((sum(d for _, d in seq) + 0.8) * SR); buf = np.zeros(L); t = 0
    for n, d in seq:
        place(buf, brass(hz(n), d + 0.05, 1.0), t); t += d
    place(buf, snare(0.5, 0.9) * np.linspace(0.3, 1, int(0.9 * SR)), t - 1.4)
    place(buf, bass_drum(1.0, 1.2) + cymbal(0.8, 1.6)[:int(1.2 * SR)], t - 1.4)
    return buf


def fife_and_drum(times=2, bpm=118):
    e = 60 / bpm / 2; bar = 4 * e; total = times * 16 * bar
    buf = np.zeros(int((total + 1.5) * SR))
    for r in range(times):
        t0 = r * 16 * bar; t = t0
        for n, k in TUNE:
            place(buf, 0.8 * fife(hz(n), k * e * 0.95), t)
            place(buf, 0.35 * fife(hz(n) / 2 * 1.0, k * e * 0.95), t)   # second fife an octave down
            t += k * e
        for b in range(16):
            tb = t0 + b * bar
            place(buf, bass_drum(0.9), tb); place(buf, bass_drum(0.6), tb + 2 * e)
            # snare: a short roll into each bar's first beat, taps on the eighths
            for j in range(6):
                place(buf, snare(0.18 + 0.05 * j, 0.08), tb - e + j * e / 6)
            for j in (0, 1, 3):
                place(buf, snare(0.55 if j == 0 else 0.35), tb + j * e)
    return buf


def strut(times=3, bpm=112, melody=True):
    e = 60 / bpm / 2; bar = 4 * e; total = times * 16 * bar
    buf = np.zeros(int((total + 2.0) * SR))
    for r in range(times):
        t0 = r * 16 * bar
        if melody:
            t = t0
            for n, k in TUNE:
                d = k * e
                place(buf, 0.55 * sax(hz(n), d * 0.9), t)
                place(buf, 0.35 * sax(hz(n) * 2 ** (-4 / 12), d * 0.9), t)   # second sax a third below
                place(buf, 0.22 * glock(hz(n) * 2), t)
                t += d
        for b, c in enumerate(CHORDS):
            tb = t0 + b * bar
            place(buf, bass_drum(1.0 if melody else 0.7), tb); place(buf, bass_drum(0.8 if melody else 0.55), tb + 2 * e)
            for j in range(4):   # banjo: steady eighth-note strums, accents on the off-beats
                acc = 1.0 if j % 2 else 0.6
                for s, nn in enumerate(TRIAD[c]):
                    place(buf, 0.22 * acc * banjo(hz(nn) * 2), tb + j * e + s * 0.008)
            place(buf, 0.35 * banjo(hz(ROOT[c]), 0.6), tb)
            if melody:
                place(buf, cymbal(0.5 if b % 4 else 1.0), tb + e)
            else:
                place(buf, 0.12 * glock(hz(TRIAD[c][2]) * 2), tb + e)
    return buf


def save(x, p):
    x = x / (np.abs(x).max() + 1e-9) * 10 ** (-3 / 20)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    save(bugle_call(), out / "bugle.wav")
    save(fife_and_drum(), out / "fife.wav")
    save(strut(), out / "strut.wav")
    save(strut(times=2, melody=False), out / "strutbed.wav")
    for f in sorted(out.glob("*.wav")):
        with wave.open(str(f)) as w:
            print(f.name, round(w.getnframes() / SR, 1), "s")
