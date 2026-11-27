"""The Lock Call clip: the daily vertical video (Matthew, Nov 26 2026, option A after MidMaxx60 ended).

    python -m mac.lockclip --out out [--episode 2026-11-26]

Takes the newest regular (non-bonus) Lock Call episode from data/podcast/episodes.json and cuts its
opening (the cold-open hook, the theme and the news bit) into a 1080x1920 Short under 60 seconds:
the show's cover on a blurred copy of itself, the date and the episode blurb above, a gold waveform
below, then the day's brand outro. The first frame is the full designed card, so first-frame
previews on Threads and Bluesky read as a cover.

Writes out/lockclip-<date>.mp4, -thumb.png and .txt (the description that youtube.py and reels.py use).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import textwrap
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import outro
from .config import ROOT
from .lockcall import EPISODES, SHOW

W, H, FPS = 1080, 1920, 30
MAX_SECONDS = 59.0  # a Short, outro included
FADE = 1.5
STATIC = ROOT / "templates" / "static"
FONTS = STATIC / "fonts"
GOLD, CREAM, MUTED = (232, 182, 74), (247, 239, 224), (205, 192, 170)
PAGE = "hardwoodbricks.com/" + SHOW["page"]
GAMBLING = "Picks are entertainment, not advice. 21+. If gambling is a problem, call 1-800-GAMBLER."
DISCLOSURE = "The hosts are fictional AI personas."
COVER_TOP, COVER = 560, 960
WAVE_TOP, WAVE_H = COVER_TOP + COVER + 40, 150


def episode(ep_id: str | None = None) -> dict:
    """The episode to clip: the one named, else the newest regular show (bonus episodes are skipped)."""
    eps = json.loads(EPISODES.read_text())
    if ep_id:
        return next(e for e in eps if e["id"] == ep_id)
    return [e for e in eps if not e.get("bonus")][-1]


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _center(d: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.FreeTypeFont, fill, spacing: int = 0) -> int:
    """Draw one centered line at y (with optional letter spacing); returns the line's bottom."""
    if spacing:
        widths = [d.textlength(c, font=font) for c in text]
        x = (W - (sum(widths) + spacing * (len(text) - 1))) / 2
        for c, w in zip(text, widths):
            d.text((x, y), c, font=font, fill=fill)
            x += w + spacing
    else:
        d.text(((W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)
    box = d.textbbox((0, y), text, font=font)
    return box[3]


def balanced(text: str, width: int) -> list[str]:
    """Wrap into as few lines as width allows, as evenly as possible (no one-word last line)."""
    n = len(textwrap.wrap(text, width, break_on_hyphens=False))
    return next(ln for w in range(12, width + 1) if len(ln := textwrap.wrap(text, w, break_on_hyphens=False)) == n)


def card(ep: dict) -> Image.Image:
    """The still every frame sits on: blurred cover, kicker, date, blurb, cover, footer."""
    cover = Image.open(ROOT / "templates" / SHOW["cover"]).convert("RGB")
    bg = cover.resize((H, H)).crop(((H - W) // 2, 0, (H - W) // 2 + W, H)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (14, 10, 8)), 0.62)
    d = ImageDraw.Draw(bg)
    day = date.fromisoformat(ep["date"])
    y = _center(d, 96, "TODAY'S LOCK CALL", _font("BarlowCondensed-SemiBold.ttf", 46), GOLD, spacing=6) + 22
    y = _center(d, y, f"{day:%A}, {day:%B} {day.day}", _font("Newsreader-SemiBold.ttf", 74), CREAM) + 30
    blurb = _font("Barlow-Regular.ttf", 38)
    for line in balanced(ep["blurb"], 46)[:4]:
        y = _center(d, y, line, blurb, MUTED) + 12
    bg.paste(cover.resize((COVER, COVER), Image.LANCZOS), ((W - COVER) // 2, COVER_TOP))
    foot = WAVE_TOP + WAVE_H + 34
    foot = _center(d, foot, "FULL EPISODE  ·  " + PAGE.upper(), _font("BarlowCondensed-SemiBold.ttf", 36), GOLD, spacing=2) + 18
    small = _font("Barlow-Regular.ttf", 24)
    _center(d, foot, GAMBLING, small, MUTED)
    return bg


def clip_seconds(outro_clip: Path) -> float:
    return round(MAX_SECONDS - outro.seconds(outro_clip), 2)


def description(ep: dict) -> str:
    """Blurb first: reels.py uses the first paragraph as the post's lead line."""
    return (f"{ep['blurb']}\n\n{ep['title']}. The whole episode, with all eight picks: https://{PAGE}\n\n"
            f"{DISCLOSURE} {GAMBLING}")


def render(ep: dict, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    stem = f"lockclip-{ep['date']}"
    mp4, still = out / f"{stem}.mp4", out / f"{stem}-thumb.png"
    card(ep).save(still)
    end = outro.for_day(date.fromisoformat(ep["date"]))
    secs = clip_seconds(end)
    audio = ROOT / "templates" / ep["audio"]
    fc = (f"[1:a]atrim=0:{secs},asetpts=PTS-STARTPTS,afade=t=out:st={secs - FADE}:d={FADE},asplit[a][w0];[w0]volume=2.5[w];"
          f"[w]showwaves=s={COVER}x{WAVE_H}:mode=cline:draw=full:rate={FPS}:colors=#E8B64A:scale=cbrt,format=rgba,"
          f"colorchannelmixer=aa=0.9[wave];"
          f"[0:v][wave]overlay=(W-w)/2:{WAVE_TOP}:shortest=1,format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(still), "-i", str(audio),
                    "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(secs),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(mp4)], check=True)
    outro.append(mp4, end, W, H, FPS)
    (out / f"{stem}.txt").write_text(description(ep) + "\n")
    (out / f"{stem}.tags").write_text("")
    return mp4


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--episode", default="", help="episode id from data/podcast/episodes.json (blank = newest regular show)")
    a = ap.parse_args()
    print(f"lockclip: {render(episode(a.episode or None), Path(a.out))}")


if __name__ == "__main__":
    main()
