"""Render the MAC90 video: one vertical card per script segment, voiced and stitched.

    python -m mac.mac90video --out out/

Needs site/mac90.json (written by `python -m mac.collect site`), a headless Chrome
and ffmpeg. The voice is Piper when PIPER_VOICE points at a .onnx voice, else
espeak-ng, else silence timed to the words (for layout checks only).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import alert
from .config import SITE_DIR, TEAMS, TEMPLATES_DIR

STALE_HOURS = 6  # data older than this at render time means the collector has stopped

W, H = 1080, 1920
PAD = 0.45  # seconds of air after each segment
FPS = 30
COUNT_STEPS = 10  # frames in a score count-up
COUNT_SECS = 0.8  # how long the count-up takes
GOLD, CREAM = "f0c75e", "f6efe3"
BAR_Y, BAR_H = 342, 10  # progress bar, just under the team-color stripe


def spoken(text: str) -> str:
    """Script text as it should be read aloud."""
    t = text.replace("Miami (OH)", "Miami of Ohio").replace("MAC90", "MAC Ninety").replace("ESPN+", "ESPN Plus")
    t = re.sub(r"\b(\d{2,3})-(\d{2,3})\b", r"\1 to \2", t)  # scores, not "4.5-point"
    t = t.replace("p.m.", "P M").replace("a.m.", "A M").replace("Hardwood Bricks dot com", "Hardwood Bricks dot com")
    return t


def textures() -> str:
    """Just the brick and parquet textures from the site stylesheet (the rest would clash with the card)."""
    src = (TEMPLATES_DIR / "static" / "site.css").read_text()
    out = []
    for var in ("--bricks", "--wood-parquet"):
        m = re.search(re.escape(var) + r":\s*(url\(\"data:[^\"]+\"\))", src)
        if m:
            out.append(f"{var}: {m.group(1)};")
    return ":root { " + " ".join(out) + " }"


FONT_DIR = TEMPLATES_DIR / "static" / "fonts"


def font_faces() -> str:
    """@font-face rules for the house faces, read from the vendored files so headless Chrome needs no network."""
    faces = (("Newsreader", 400, "normal", "Newsreader-Regular.ttf"), ("Newsreader", 600, "normal", "Newsreader-SemiBold.ttf"),
             ("Newsreader", 600, "italic", "Newsreader-SemiBoldItalic.ttf"), ("Newsreader", 400, "italic", "Newsreader-SemiBoldItalic.ttf"),
             ("Barlow Condensed", 500, "normal", "BarlowCondensed-SemiBold.ttf"), ("Barlow Condensed", 600, "normal", "BarlowCondensed-SemiBold.ttf"),
             ("Barlow Condensed", 700, "normal", "BarlowCondensed-Bold.ttf"), ("Barlow", 400, "normal", "Barlow-Regular.ttf"),
             ("Barlow", 600, "normal", "Barlow-SemiBold.ttf"))
    return "\n".join(f'@font-face {{ font-family: "{fam}"; font-weight: {w}; font-style: {st}; src: url("{(FONT_DIR / f).resolve().as_uri()}"); }}'
                     for fam, w, st, f in faces if (FONT_DIR / f).exists())


def chrome() -> str:
    for c in (os.environ.get("CHROME_BIN"), shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser"),
              "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"):
        if c and Path(c).exists():
            return c
    raise SystemExit("no headless Chrome found; set CHROME_BIN")


def shoot(html: Path, png: Path) -> None:
    subprocess.run([chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    f"--window-size={W},{H}", "--virtual-time-budget=8000", f"--screenshot={png}", html.as_uri()],
                   check=True, capture_output=True, timeout=120)


def wav_seconds(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / float(w.getframerate())


def clone_all(texts: list[str], wavs: list[Path], work: Path) -> bool:
    """Voice every segment in the cloned voice in one go (the model is slow to load).

    Needs VOICE_CLONE_PY (a Python with Chatterbox installed) and VOICE_REF (the reference clip).
    Returns False, and the video falls back to Piper, if either is missing or the clone fails.
    """
    py, ref = os.environ.get("VOICE_CLONE_PY"), os.environ.get("VOICE_REF")
    if not (py and ref and Path(py).exists() and Path(ref).exists()):
        return False
    jobs = work / "voice-jobs.json"
    jobs.write_text(json.dumps([{"text": t, "out": str(w.resolve())} for t, w in zip(texts, wavs)]))
    tool = Path(__file__).resolve().parent.parent / "tools" / "clone_voice.py"
    r = subprocess.run([py, str(tool), "--ref", ref, "--jobs", str(jobs)], timeout=3000)
    if r.returncode != 0 or not all(w.exists() and w.stat().st_size > 1000 for w in wavs):
        print("voice clone failed; falling back to Piper", file=sys.stderr)
        for w in wavs:
            w.unlink(missing_ok=True)
        return False
    return True


def speak(text: str, out: Path) -> None:
    if out.exists():  # already voiced by clone_all()
        return
    voice = os.environ.get("PIPER_VOICE")
    if voice and Path(voice).exists():
        subprocess.run([sys.executable, "-m", "piper", "-m", voice, "-f", str(out), "--length-scale", os.environ.get("PIPER_SPEED", "0.95"), "--sentence-silence", "0.2"],
                       input=text.encode(), check=True, capture_output=True)
    elif shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-s", "165", "-w", str(out), text], check=True, capture_output=True)
    else:  # silence, about 2.6 words a second, so the timing is still realistic
        secs = max(1.5, len(text.split()) / 2.6)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", f"{secs:.2f}", str(out)], check=True)


def srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def chunks(text: str, most: int = 5) -> list[list[str]]:
    """Caption-sized groups of words: at most `most`, breaking after punctuation when we can."""
    out, cur = [], []
    for w in text.split():
        cur.append(w)
        if len(cur) >= most or (len(cur) >= 2 and w[-1] in ".,;:!?"):
            out.append(cur)
            cur = []
    if cur:
        if out and len(cur) == 1 and len(out[-1]) < most + 1:
            out[-1].extend(cur)
        else:
            out.append(cur)
    return out


def _weight(w: str) -> float:
    """Rough speaking time of a word: its letters, plus a beat for punctuation."""
    return len(w) + 1.5 + (3.0 if w[-1] in ",;:" else 6.0 if w[-1] in ".!?" else 0.0)


def _ass_time(s: float) -> str:
    cs = int(round(s * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _ass_color(hex6: str) -> str:
    r, g, b = hex6[0:2], hex6[2:4], hex6[4:6]
    return f"&H00{b}{g}{r}".upper()


def _ass_escape(w: str) -> str:
    return w.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def ass_events(text: str, start: float, speech: float) -> list[str]:
    """Karaoke caption lines for one segment: each chunk on screen while it is spoken, words filling gold as they are read."""
    groups = chunks(text)
    total = sum(_weight(w) for g in groups for w in g) or 1.0
    lead = min(0.12, speech * 0.05)  # Piper starts with a breath of silence
    per = (speech - lead) / total
    t, lines = start + lead, []
    for g in groups:
        ks = [max(1, round(_weight(w) * per * 100)) for w in g]
        end = t + sum(ks) / 100
        body = " ".join(f"{{\\kf{k}}}{_ass_escape(w)}" for w, k in zip(g, ks))
        lines.append(f"Dialogue: 0,{_ass_time(t)},{_ass_time(end)},Cap,,0,0,0,,{body}")
        t = end
    return lines


def ass_file(events: list[str]) -> str:
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # Primary is the "already said" color, secondary the "coming up" color. Bottom-center, clear of the Shorts buttons.
        f"Style: Cap,Barlow Condensed,86,{_ass_color(GOLD)},{_ass_color(CREAM)},&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,6,3,2,90,150,430,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text", *events, ""])


def _counted(seg: dict, frac: float) -> dict:
    """A copy of a result segment with both scores scaled down, for the count-up frames."""
    card = dict(seg["card"])
    for side in ("away", "home"):
        s = dict(card[side])
        if isinstance(s.get("score"), (int, float)) or str(s.get("score", "")).isdigit():
            s["score"] = round(int(s["score"]) * frac)
        card[side] = s
    return {**seg, "card": card}


def render(t: dict, out: Path) -> Path:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = out / "work"
    work.mkdir(exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    tpl = env.get_template("mac90_card.html")
    css = textures() + "\n" + font_faces()
    colors = {tm.short: tm.color for tm in TEAMS}
    agenda = []
    n_res = sum(1 for s in t["segments"] if s["kind"] == "result")
    n_tune = sum(len(s.get("cards", [])) for s in t["segments"] if s["kind"] == "tuneups")
    if n_res or n_tune:
        agenda.append(f"{t['results_label']}: {n_res + n_tune} final{'s' if n_res + n_tune != 1 else ''}")
    n_prev = sum(1 for s in t["segments"] if s["kind"] == "preview") + sum(len(s.get("cards", [])) for s in t["segments"] if s["kind"] == "tuneups_next")
    if n_prev:
        agenda.append(f"{t['slate_label']}: {n_prev} game{'s' if n_prev != 1 else ''}")
    agenda.append("The unbeaten and the winless")

    cloned = clone_all([spoken(seg["text"]) for seg in t["segments"]], [work / f"seg{i:02d}.wav" for i in range(len(t["segments"]))], work)
    common = dict(date_label=t["date_label"], css=css, colors=colors, agenda=agenda, stripe=[tm.color for tm in TEAMS])
    clips, srt, events, clock = [], [], [], 0.0
    for i, seg in enumerate(t["segments"]):
        png = work / f"card{i:02d}.png"
        wav = work / f"seg{i:02d}.wav"
        clip = work / f"clip{i:02d}.mp4"
        frames: list[tuple[Path, float | None]] = []
        if seg["kind"] == "result" and seg.get("card"):  # scores count up from zero
            for k in range(1, COUNT_STEPS):
                f = work / f"card{i:02d}-{k:02d}.png"
                h = work / f"card{i:02d}-{k:02d}.html"
                h.write_text(tpl.render(seg=_counted(seg, k / COUNT_STEPS), live_caps=True, **common))
                shoot(h, f)
                frames.append((f, COUNT_SECS / COUNT_STEPS))
        html = work / f"card{i:02d}.html"
        html.write_text(tpl.render(seg=seg, live_caps=True, **common))
        shoot(html, png)
        frames.append((png, None))
        speak(spoken(seg["text"]), wav)
        speech = wav_seconds(wav)
        dur = speech + PAD
        imgs = work / f"imgs{i:02d}.txt"
        lines, used = [], 0.0
        for f, d in frames:
            d = d if d is not None else max(dur - used, 0.1)
            used += d
            lines += [f"file '{f.resolve()}'", f"duration {d:.3f}"]
        lines.append(f"file '{frames[-1][0].resolve()}'")  # concat demuxer needs the last image twice
        imgs.write_text("\n".join(lines) + "\n")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(imgs), "-i", str(wav),
                        "-filter_complex", f"[0:v]fps={FPS},format=yuv420p[v];[1:a]apad=pad_dur={PAD},aresample=44100[a]", "-map", "[v]", "-map", "[a]",
                        "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-r", str(FPS),
                        "-c:a", "aac", "-b:a", "128k", "-ac", "2", str(clip)], check=True)
        clips.append(clip)
        srt.append(f"{i + 1}\n{srt_time(clock)} --> {srt_time(clock + speech)}\n{seg['text']}\n")
        events += ass_events(seg["text"], clock, speech)
        clock += dur

    stem = f"mac90-{t['date_iso']}"
    lst = work / "clips.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    joined = work / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)], check=True)
    # Burn in the karaoke captions (most Shorts are watched muted) and a gold progress bar that fills as it plays.
    ass = work / "captions.ass"
    ass.write_text(ass_file(events))
    fc = (f"[0:v]ass={ass.name}:fontsdir={FONT_DIR.resolve()},drawbox=x=0:y={BAR_Y}:w=iw:h={BAR_H}:color=black@0.55:t=fill[base];"
          f"[base][1:v]overlay=x='-w+W*t/{clock:.3f}':y={BAR_Y}:eval=frame:shortest=1[v]")
    video = out / f"{stem}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined.name, "-f", "lavfi", "-i", f"color=c=0x{GOLD}:s={W}x{BAR_H}:r={FPS}",
                    "-filter_complex", fc, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(video)], check=True, cwd=work)
    (out / f"{stem}.srt").write_text("\n".join(srt))
    shutil.copy(work / "card00.png", out / f"{stem}-thumb.png")
    voiced = "Voiced by an AI model of Matthew Hagan's voice. " if cloned else ""
    (out / f"{stem}.txt").write_text("\n\n".join(t["paragraphs"]) + f"\n\n{voiced}Stats: ESPN. Lines: The Odds API. https://hardwoodbricks.com/mac90.html\n")
    print(f"{video} {clock:.1f}s, {len(clips)} segments, voice: {'clone' if cloned else 'piper'}")
    return video


def skip_reason(t: dict, data_time: datetime | None, now: datetime, stale_hours: float = STALE_HOURS) -> str | None:
    """Why today's video should not be made, or None when the script is fit to publish."""
    if data_time and now - data_time > timedelta(hours=stale_hours):
        hours = (now - data_time).total_seconds() / 3600
        return f"the data was last updated {hours:.0f} hours ago (limit {stale_hours:g}), so the script would repeat old news"
    if not t.get("results") and not t.get("previews"):
        return "the script has no results and no games coming up, only an intro and outro"
    return None


def check(t: dict, data_time: str, now: datetime | None = None) -> str | None:
    """Skip-and-alert gate for the daily workflow: emails Matthew and returns the reason when the video is skipped."""
    now = now or datetime.now(timezone.utc)
    when = datetime.fromisoformat(data_time.replace("Z", "+00:00")) if data_time else None
    reason = skip_reason(t, when, now)
    if reason:
        alert.send(f"MAC90 skipped for {t.get('date_label') or 'today'}",
                   f"No MAC90 video was made this morning because {reason}.\n\n"
                   "Check the latest Collect run on GitHub Actions. Once data is flowing again, "
                   "run the MAC90 video workflow by hand to publish today's episode.")
    return reason


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--script", default=str(SITE_DIR / "mac90.json"))
    ap.add_argument("--check", action="store_true", help="only decide whether to skip today's video; writes skip=<reason> to $GITHUB_OUTPUT")
    ap.add_argument("--data-time", default="", help="ISO time of the last data commit, for --check")
    a = ap.parse_args()
    if a.check:
        reason = check(json.loads(Path(a.script).read_text()), a.data_time)
        print(f"mac90: skipped, {reason}" if reason else "mac90: script is fresh")
        if reason and os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("skip=yes\n")
        return
    render(json.loads(Path(a.script).read_text()), Path(a.out))


if __name__ == "__main__":
    main()
