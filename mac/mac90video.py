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
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .config import SITE_DIR, TEAMS, TEMPLATES_DIR

W, H = 1080, 1920
PAD = 0.45  # seconds of air after each segment


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


def speak(text: str, out: Path) -> None:
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


def render(t: dict, out: Path) -> Path:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = out / "work"
    work.mkdir(exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    tpl = env.get_template("mac90_card.html")
    css = textures()
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

    clips, srt, clock = [], [], 0.0
    for i, seg in enumerate(t["segments"]):
        html = work / f"card{i:02d}.html"
        png = work / f"card{i:02d}.png"
        wav = work / f"seg{i:02d}.wav"
        clip = work / f"clip{i:02d}.mp4"
        html.write_text(tpl.render(seg=seg, date_label=t["date_label"], css=css, colors=colors, agenda=agenda,
                                   stripe=[tm.color for tm in TEAMS]))
        shoot(html, png)
        speak(spoken(seg["text"]), wav)
        dur = wav_seconds(wav) + PAD
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-i", str(png), "-i", str(wav),
                        "-filter_complex", f"[1:a]apad=pad_dur={PAD},aresample=44100[a]", "-map", "0:v", "-map", "[a]",
                        "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "30",
                        "-c:a", "aac", "-b:a", "128k", "-ac", "2", str(clip)], check=True)
        clips.append(clip)
        srt.append(f"{i + 1}\n{srt_time(clock)} --> {srt_time(clock + dur - PAD)}\n{seg['text']}\n")
        clock += dur

    stem = f"mac90-{t['date_iso']}"
    lst = work / "clips.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    video = out / f"{stem}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(video)], check=True)
    (out / f"{stem}.srt").write_text("\n".join(srt))
    shutil.copy(work / "card00.png", out / f"{stem}-thumb.png")
    (out / f"{stem}.txt").write_text("\n\n".join(t["paragraphs"]) + "\n\nStats: ESPN. Lines: The Odds API. https://hardwoodbricks.com/mac90.html\n")
    print(f"{video} {clock:.1f}s, {len(clips)} segments")
    return video


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--script", default=str(SITE_DIR / "mac90.json"))
    a = ap.parse_args()
    render(json.loads(Path(a.script).read_text()), Path(a.out))


if __name__ == "__main__":
    main()
