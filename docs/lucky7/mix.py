"""Lay the Lucky Seven score under the stitched film.

    python docs/lucky7/mix.py <film.mp4> <timeline.json> <scoredir> <out.mp4>

Heaviest at the open (bugle call, then fife and drum under the company plates and title) and the close
(the Mummers strut under the last words, the disclosure card and the credits). Elsewhere: a bugle call
and a short fife phrase on each chapter card, and the strut's rhythm bed low under each seven-fact recap.
"""
import json, subprocess, sys, wave
import numpy as np

SR = 48000


def load(p):
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def ramp(L, a, b):
    return np.linspace(a, b, max(L, 1))[:L]


def main():
    film, tl, sd, out = sys.argv[1:5]
    T = json.load(open(tl))
    starts = np.concatenate([[0], np.cumsum([x["dur"] for x in T])]); total = starts[-1]
    cue = {k: load(f"{sd}/{k}.wav") for k in ("bugle", "fife", "strut", "strutbed")}
    music = np.zeros(int((total + 1) * SR), np.float32)

    def lay(x, t, gains):
        """gains: list of (time from cue start, gain) points, linear in between; zero after the last point."""
        i = int(t * SR); x = x[:max(0, min(len(x), len(music) - i))]
        g = np.zeros(len(x), np.float32); pts = [(int(a * SR), b) for a, b in gains]
        for (a0, g0), (a1, g1) in zip(pts, pts[1:]):
            a1 = min(a1, len(x))
            if a1 > a0:
                g[a0:a1] = ramp(a1 - a0, g0, g1)
        music[i:i + len(x)] += x * g

    def loop(x, secs):
        n = int(secs * SR); return np.tile(x, n // len(x) + 1)[:n]

    # open: lines before the first voiced line are the plates and title
    first_voice = next(i for i, x in enumerate(T) if x["speaker"] not in ("TITLE", "CHAP", "OUTRO", "CLIP"))
    t_open = starts[first_voice]
    lay(cue["bugle"], 0, [(0, .9), (4.3, .9)])
    lay(cue["fife"], 4.0, [(0, .85), (t_open - 4.0, .85), (t_open - 3.0, .16), (30.0 - 4.0, .1), (34.0 - 4.0, 0)])

    # chapter cards
    for i, x in enumerate(T):
        if x["speaker"] == "CHAP":
            t0 = starts[i]; t1 = starts[i + 1]
            lay(cue["bugle"], t0, [(0, .7), (4.3, .7)])
            lay(cue["fife"], t0 + 3.6, [(0, .55), (t1 - t0 - 3.6, .5), (t1 - t0 - 3.0, .12), (8.0, .1), (10.0, 0)])

    # seven-fact recaps: from the line before "card:One|" through the "card:Seven|" line
    for i, x in enumerate(T):
        if (x["visual"] or "").startswith("card:One|"):
            j = next(k for k in range(i, len(T)) if (T[k]["visual"] or "").startswith("card:Seven|"))
            t0, t1 = starts[i - 1], starts[j + 1]; D = t1 - t0
            lay(loop(cue["strutbed"], D + 1.5), t0, [(0, 0), (1.0, .14), (D, .14), (D + 1.5, 0)])

    # close: rise under the last two spoken lines, full under the disclosure card and credits, out before the stings
    disc = next(i for i, x in enumerate(T) if (x["visual"] or "").startswith("card:A Hardwood Bricks film"))
    end = next((i for i, x in enumerate(T) if x["speaker"] == "OUTRO"), len(T))
    t0 = starts[max(disc - 2, 0)]; tf = starts[disc]; te = starts[end]; D = te - t0
    lay(loop(cue["strut"], D + 0.5), t0, [(0, .0), (1.5, .2), (tf - t0, .25), (tf - t0 + 1.0, .9), (D - 2.0, .9), (D, 0)])

    tmp = out + ".music.wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(music, -1, 1) * 32767 * 0.5).astype(np.int16).tobytes())   # about -6 dB under the voice track
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", film, "-i", tmp, "-filter_complex",
                    "[0:a]aresample=48000[v];[1:a]volume=1.0[m];[v][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], check=True)
    print("wrote", out, f"{total/60:.1f} min")


if __name__ == "__main__":
    main()
