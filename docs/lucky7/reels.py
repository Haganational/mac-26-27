"""Cut the Lucky Seven film into seven vertical reels, one per state (1080x1920, about a minute each).

    python docs/lucky7/reels.py <workdir> <outdir>

Each reel: the chapter card (the cover frame in the first second), the chapter's cold open (its first two lines),
then the state's seven-fact recap through "<State>. Keep it real." Uses <workdir>/out/lucky-seven.mp4,
out/timeline.json, out/lucky-seven-rough.srt and film/lines.json.
"""
import json, re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "templates/static/fonts"
PAGE, INK, MUTED, GOLD = (21, 17, 13), (239, 230, 214), (143, 132, 116), (240, 199, 94)
STATES = ["Connecticut", "Rhode Island", "New York", "Massachusetts", "New Hampshire", "New Jersey", "Pennsylvania"]
WORDS = ["One", "Two", "Three", "Four", "Five", "Six", "Seven"]


def font(n, s):
    return ImageFont.truetype(str(FONTS / n), s)


def frame(png, n, state, gov):
    im = Image.new("RGBA", (1080, 1920), PAGE + (255,)); d = ImageDraw.Draw(im)

    def center(y, text, f, fill):
        w = d.textlength(text, font=f); d.text(((1080 - w) / 2, y), text, font=f, fill=fill)
    center(200, "HARDWOOD BRICKS PRODUCTIONS", font("BarlowCondensed-SemiBold.ttf", 34), GOLD)
    center(250, "Lucky Seven", font("Newsreader-SemiBold.ttf", 104), INK)
    center(392, f"CHAPTER {WORDS[n - 1].upper()} · {state.upper()}", font("BarlowCondensed-SemiBold.ttf", 40), INK)
    center(448, gov.upper(), font("BarlowCondensed-SemiBold.ttf", 32), MUTED)
    d.rectangle([0, 556, 1080, 559], fill=GOLD); d.rectangle([0, 1171, 1080, 1174], fill=GOLD)
    d.rectangle([0, 560, 1080, 1170], fill=(0, 0, 0, 0))   # the film shows through here
    center(1730, "THE FULL FILM IS ON YOUTUBE", font("BarlowCondensed-SemiBold.ttf", 34), MUTED)
    center(1776, "A HARDWOOD BRICKS DOCUMENTARY", font("BarlowCondensed-SemiBold.ttf", 30), GOLD)
    im.save(png)


def srt_read(p):
    out = []
    for blk in Path(p).read_text().strip().split("\n\n"):
        ls = blk.splitlines()
        if len(ls) < 3:
            continue
        a, b = [sum(float(x) * m for x, m in zip(re.split("[:,]", t)[:3], (3600, 60, 1))) + int(t[-3:]) / 1000 for t in ls[1].split(" --> ")]
        out.append((a, b, " ".join(ls[2:])))
    return out


def ts(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):d}:{int(m):02d}:{s:05.2f}"


def main():
    work, outdir = Path(sys.argv[1]), Path(sys.argv[2]); outdir.mkdir(parents=True, exist_ok=True)
    T = json.load(open(work / "out/timeline.json")); L = json.load(open(work / "film/lines.json"))["lines"]
    st = [0.0]
    for x in T:
        st.append(st[-1] + x["dur"])
    subs = srt_read(work / "out/lucky-seven-rough.srt")
    film = work / "out/lucky-seven.mp4"
    chaps = [i for i, x in enumerate(T) if x["speaker"] == "CHAP"]
    made = []
    for n, c in enumerate(chaps, 1):
        state = STATES[n - 1]
        gov = T[c]["visual"].split("|", 1)[1].split(" · ")[0] if "|" in T[c]["visual"] else ""
        r = next(i for i in range(c, len(L)) if "one more time" in L[i].get("say", ""))
        e = next(i for i in range(r, len(L)) if L[i].get("say", "") == f"{state}. Keep it real."
                 or L[i + 1].get("say", "").startswith("Seven states. Seven governors."))   # Pennsylvania runs into the film's close
        segs = [(st[c], st[c + 3]), (st[r], st[e + 1])]
        name = f"lucky-seven-{n}-{re.sub('[^a-z]+', '-', state.lower())}"
        tmp = outdir / "tmp"; tmp.mkdir(exist_ok=True)
        png = tmp / f"{name}.png"; frame(png, n, state, gov)
        # captions for the reel's own clock
        ass = ["[Script Info]", "PlayResX: 1080", "PlayResY: 1920", "", "[V4+ Styles]",
               "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Alignment, MarginL, MarginR, MarginV, BorderStyle, Outline, Shadow",
               "Style: Cap,Barlow,50,&H00D6E6EF,&H00000000,&H00000000,0,8,70,70,1240,1,0,0",
               "Style: Who,Barlow Condensed,34,&H005EC7F0,&H00000000,&H00000000,1,8,70,70,1200,1,0,0", "",
               "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
        off = 0.0
        for a, b in segs:
            for s0, s1, txt in subs:
                if s0 >= a - 0.05 and s0 < b:
                    who, _, say = txt.partition(": ")
                    t0, t1 = s0 - a + off, min(s1, b) - a + off
                    ass.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Who,,0,0,0,,{who.upper()}")
                    ass.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Cap,,0,0,0,,{say}")
            off += b - a
        (tmp / f"{name}.ass").write_text("\n".join(ass) + "\n")
        parts = []
        for k, (a, b) in enumerate(segs):
            p = tmp / f"{name}-{k}.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-i", str(film), "-t", f"{b - a:.3f}",
                            "-af", f"afade=in:d=0.15,afade=out:st={max(b - a - 0.3, 0):.3f}:d=0.3",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(p)], check=True)
            parts.append(p)
        (tmp / f"{name}.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        joined = tmp / f"{name}-joined.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / f"{name}.txt"), "-c", "copy", str(joined)], check=True)
        out = outdir / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(joined), "-i", str(png), "-filter_complex",
                        f"[0:v]scale=1080:608,setsar=1[f];[1:v][f]overlay=0:563[c];[c]subtitles={tmp / (name + '.ass')}:fontsdir={FONTS},format=yuv420p[v]",
                        "-map", "[v]", "-map", "0:a", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
        # thumbnail: the reel's own cover (its first frame is the chapter card)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.0", "-i", str(out), "-frames:v", "1", "-q:v", "3", str(outdir / f"{name}-thumb.jpg")], check=True)
        dur = sum(b - a for a, b in segs); made.append((name, state, gov, round(dur, 1)))
        print(name, f"{dur:.1f}s", gov)
    json.dump(made, open(outdir / "reels-made.json", "w"), indent=1)


if __name__ == "__main__":
    main()
