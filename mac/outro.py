"""Brand outros tacked onto the end of every auto-produced video (MidMaxx60 and The Big Mid).

Two vertical clips in outros/ take turns: MidMaxx60 swaps daily, The Big Mid weekly. Both are
1080x1920 with their own audio (made by Matthew, cleared to use). On a 16:9 video the clip sits
in the middle over a blurred, darkened copy of itself.
"""
from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from .config import ROOT

OUTRO_DIR = ROOT / "outros"
OUTROS = ("hardwood-bricks.mp4", "juicebox-nation.mp4")  # rotation order


def pick(n: int) -> Path:
    """The outro for slot n (a day or week number): alternates through OUTROS."""
    return OUTRO_DIR / OUTROS[n % len(OUTROS)]


def for_day(d: date) -> Path:
    return pick(d.toordinal())


def for_week(d: date) -> Path:
    return pick(d.isocalendar()[1])


def seconds(clip: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(clip)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def video_filter(w: int, h: int, fps: int) -> str:
    """Fit the 9:16 outro into a w x h frame; when the shapes differ, fill the sides with a blurred copy."""
    if w * 16 == h * 9:
        return f"[1:v]scale={w}:{h},setsar=1,fps={fps},format=yuv420p[ov]"
    return (f"[1:v]split[o1][o2];"
            f"[o1]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=40:2,eq=brightness=-0.25[bg];"
            f"[o2]scale=-2:{h}[fg];[bg][fg]overlay=(W-w)/2:0,setsar=1,fps={fps},format=yuv420p[ov]")


def append(video: Path, clip: Path, w: int, h: int, fps: int) -> Path:
    """Re-encode video with clip on the end, in place. Returns video."""
    tmp = video.with_name(video.stem + "-outro" + video.suffix)
    fc = (video_filter(w, h, fps) + ";"
          f"[0:v]setsar=1,fps={fps},format=yuv420p[mv];"
          "[0:a]aresample=44100,aformat=channel_layouts=stereo[ma];"
          "[1:a]aresample=44100,aformat=channel_layouts=stereo[oa];"
          "[mv][ma][ov][oa]concat=n=2:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(clip), "-filter_complex", fc,
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(video)
    return video
