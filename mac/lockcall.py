"""The Lock Call: the two-minute daily Tops and Bottoms podcast (Nov 23 2026).

Three small jobs, all for whoever writes the day's script:

    python -m mac.lockcall facts [YYYY-MM-DD]      the day's picks, yesterday's results and the board, as JSON
    python -m mac.lockcall check  data/podcast/DAY.json   length, cast and format check on a script
    python -m mac.lockcall render data/podcast/DAY.json out.mp3   voices from ElevenLabs, bumper music on both ends

    python -m mac.lockcall bluesky [episode id]   post a posted episode's video to Bluesky (the lockcall workflow)

Only `bluesky` publishes, and only when run by hand. The script file is written by an editor (see data/podcast/BIBLE.md); every number in it
must come from `facts`, and the one news item must carry a source link in `notes`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from . import tops

POD_DIR = Path(__file__).resolve().parent.parent / "data" / "podcast"
VOICES = POD_DIR / "voices.json"
PARTS = ("hook", "open", "picks", "board", "close")  # the cold-open hook, then Matthew's four-part format, in order
TARGET_CHARS = (1300, 2000)  # about two minutes at ~14 characters a second
API = "https://api.elevenlabs.io/v1/text-to-dialogue"
EPISODES = POD_DIR / "episodes.json"  # what has been posted, newest last; the page and the feed both read this
FEED_PATH = "podcast/feed.xml"  # the RSS feed every podcast app reads (live Nov 23 2026)
FEED_LIVE = True
SHOW = {
    "title": "Tops and Bottoms: The Lock Call",
    "author": "Hardwood Bricks",
    "email": "press@hardwoodbricks.com",  # directories send their ownership check here
    "summary": ("Two minutes, every morning, from The Window at Hardwood Bricks. Leslie Phyllis and Brett Busberger "
                "read the day's eight picks with Merv Crutch and Edwin \"The Shark\" Sinclair, check the board, and "
                "take one swing at the news. The hosts are fictional AI personas. Picks are entertainment, not advice. "
                "21+. If gambling is a problem, call 1-800-GAMBLER."),
    "cover": "static/podcast/cover.jpg",
    "page": "tops.html",
    "category": ("Sports", "Basketball"),
}


def _short(p: dict[str, Any]) -> dict[str, Any]:
    return {k: p.get(k) for k in ("label", "matchup", "kind", "why", "result", "final") if p.get(k) is not None}


def facts(day: str | None = None) -> dict[str, Any]:
    """Everything a script may state as fact for `day` (default: the newest card)."""
    cards = tops.load_cards()
    if not cards:
        return {}
    today = next((c for c in cards if c.get("date") == day), None) if day else cards[-1]
    if today is None:
        return {"date": day, "error": "no card locked for this day yet"}
    before = [c for c in cards if c["date"] < today["date"]]
    last = before[-1] if before else None
    out: dict[str, Any] = {
        "date": today["date"],
        "picks": {k: [_short(p) for p in ps] for k, ps in today.get("picks", {}).items()},
        "board": [{k: r[k] for k in ("key", "first", "record", "units", "streak", "rank")}
                  for r in tops.standings(before)],
    }
    if last:
        out["yesterday"] = {
            "date": last["date"],
            "cappers": {k: {**{f: v for f, v in tops.tally(ps).items() if f in ("record", "units")},
                            "picks": [_short(p) for p in ps]}
                        for k, ps in last.get("picks", {}).items()},
        }
    return out


def episodes() -> list[dict[str, Any]]:
    """Posted episodes, newest first, each with its show notes attached."""
    if not EPISODES.exists():
        return []
    out = []
    for e in json.loads(EPISODES.read_text()):
        f = POD_DIR.parent.parent / e.get("script", "")
        notes = json.loads(f.read_text()).get("notes", {}) if e.get("script") and f.exists() else {}
        out.append({**e, "news": notes.get("news"), "length": f"{e['seconds'] // 60}:{e['seconds'] % 60:02d}"})
    return out[::-1]


def page_context() -> dict[str, Any]:
    """For tops.html: the newest episode and where the feed will live."""
    eps = episodes()
    return {"lockcall": eps[0] if eps else None, "lockcall_feed": FEED_PATH if FEED_LIVE else None}


def feed_xml(base: str) -> str:
    """The podcast feed: RSS 2.0 with the iTunes tags Apple and Spotify ask for. `base` ends in a slash."""
    eps = episodes()
    items = []
    for e in eps:
        when = datetime.fromisoformat(e["published"])
        notes = e["blurb"] + (" Show notes: " + " ".join(e["news"]["sources"]) if e.get("news") else "")
        items.append(
            f"<item><title>{escape(e['title'])}</title><description>{escape(notes)}</description>"
            f"<link>{escape(base + SHOW['page'])}</link><guid isPermaLink=\"false\">hardwoodbricks-lockcall-{escape(e['id'])}</guid>"
            f"<pubDate>{format_datetime(when)}</pubDate>"
            f"<enclosure url={quoteattr(base + e['audio'])} length=\"{e['bytes']}\" type=\"audio/mpeg\"/>"
            f"<itunes:duration>{e['seconds']}</itunes:duration><itunes:explicit>false</itunes:explicit>"
            "<itunes:episodeType>full</itunes:episodeType></item>")
    cat, sub = SHOW["category"]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
        'xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>{escape(SHOW['title'])}</title><link>{escape(base + SHOW['page'])}</link>"
        f"<atom:link href={quoteattr(base + FEED_PATH)} rel=\"self\" type=\"application/rss+xml\"/>"
        f"<language>en-us</language><description>{escape(SHOW['summary'])}</description>"
        f"<itunes:author>{escape(SHOW['author'])}</itunes:author><itunes:type>episodic</itunes:type>"
        f"<itunes:owner><itunes:name>{escape(SHOW['author'])}</itunes:name><itunes:email>{SHOW['email']}</itunes:email></itunes:owner>"
        f"<itunes:image href={quoteattr(base + SHOW['cover'])}/><image><url>{escape(base + SHOW['cover'])}</url>"
        f"<title>{escape(SHOW['title'])}</title><link>{escape(base + SHOW['page'])}</link></image>"
        f"<itunes:category text={quoteattr(cat)}><itunes:category text={quoteattr(sub)}/></itunes:category>"
        "<itunes:explicit>false</itunes:explicit>" + "".join(items) + "</channel></rss>\n")


def write_feed(site_root: Path, base: str) -> Path | None:
    if not FEED_LIVE:
        return None
    out = site_root / FEED_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(feed_xml(base))
    return out


def check(script: dict[str, Any]) -> list[str]:
    """Problems with a script, empty when it is ready to record."""
    cast = json.loads(VOICES.read_text())
    lines = script.get("lines", [])
    bad = []
    seen = [ln.get("part") for ln in lines]
    order = [p for i, p in enumerate(seen) if i == 0 or p != seen[i - 1]]
    if order != list(PARTS):
        bad.append(f"parts must run {' > '.join(PARTS)}; got {' > '.join(map(str, order))}")
    for ln in lines:
        if ln.get("who") not in cast:
            bad.append(f"unknown speaker: {ln.get('who')}")
    n = sum(len(ln.get("text", "")) for ln in lines)
    if not TARGET_CHARS[0] <= n <= TARGET_CHARS[1]:
        bad.append(f"{n} characters; aim for {TARGET_CHARS[0]}-{TARGET_CHARS[1]} (about two minutes)")
    talk: dict[str, int] = {}
    for ln in lines:
        talk[ln.get("who")] = talk.get(ln.get("who"), 0) + len(ln.get("text", ""))
    if lines and sorted(talk, key=talk.get, reverse=True)[:2] not in (["leslie", "brett"], ["brett", "leslie"]):
        bad.append("Leslie and Brett are the main hosts and should carry the most lines")
    hook = sum(len(ln.get("text", "")) for ln in lines if ln.get("part") == "hook")
    if not 0 < hook <= 170:
        bad.append(f"the hook is {hook} characters; it is the first thing heard, one or two short lines (170 at most)")
    news = script.get("notes", {}).get("news")
    if not news or not news.get("sources"):
        bad.append("notes.news needs the item and at least one source link")
    if "GAMBLER" not in " ".join(ln.get("text", "") for ln in lines):
        bad.append("the close must carry the 21+ / 1-800-GAMBLER line")
    return bad


THEME = POD_DIR / "theme.mp3"  # original bumper theme, made for the show Nov 23 2026: 16.7 s at 120 bpm, clean button ending
INTRO, LEAD_IN, OUTRO_FROM, UNDER = 7.5, 3.5, 8.7, 3.0  # seconds: intro length, music alone, outro cue, outro under the goodbye


def _seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def _tight(src: Path) -> Path:
    """Trim the dead air a voice render leaves at its ends, so music cues land on words."""
    dst = src.with_name(src.stem + "-tight.wav")
    cut = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", f"{cut},areverse,{cut},areverse", str(dst)],
                   check=True)
    return dst


def mix(hook: Path, talk: Path, out: Path, theme: Path = THEME) -> None:
    """Hook cold, bumper in, voices, bumper out. The theme lands on the hook's last word, plays alone,
    ducks under the hello, and returns under the goodbye to finish on its button."""
    hook, talk = _tight(hook), _tight(talk)
    start = _seconds(hook) + 0.1  # the theme hits right after the hook's last word
    hello = start + LEAD_IN
    back = hello + _seconds(talk) - UNDER
    fmt = "aformat=sample_rates=44100:channel_layouts=stereo"
    ms = lambda t: int(t * 1000)
    graph = (
        f"[0]atrim=0:{INTRO},{fmt},volume=0.55,afade=t=out:st={LEAD_IN - 0.5}:d={INTRO - LEAD_IN + 0.5},"
        f"adelay={ms(start)}:all=1[in];"
        f"[0]atrim={OUTRO_FROM},asetpts=PTS-STARTPTS,{fmt},"
        f"volume='if(lt(t,{UNDER}),0.16,min(0.6,0.16+(t-{UNDER})*0.9))':eval=frame,adelay={ms(back)}:all=1[outro];"
        # loudnorm swallows the last ~3 s of a clip unless it is padded first; the trim puts the length back
        f"[1]apad=pad_dur=4,loudnorm=I=-16:TP=-1.5,atrim=0:{_seconds(hook):.3f},{fmt}[h];"
        f"[2]apad=pad_dur=4,loudnorm=I=-16:TP=-1.5,atrim=0:{_seconds(talk):.3f},{fmt},adelay={ms(hello)}:all=1[v];"
        "[h][in][v][outro]amix=inputs=4:normalize=0:duration=longest,alimiter=limit=0.95[o]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(theme), "-i", str(hook), "-i", str(talk),
                    "-filter_complex", graph, "-map", "[o]", "-t", f"{back + 17.2 - OUTRO_FROM:.2f}", "-b:a", "160k", str(out)], check=True)


def _speak(lines: list[dict[str, Any]], cast: dict[str, Any], out: Path) -> None:
    body = {"model_id": "eleven_v3", "inputs": [{"text": ln["text"], "voice_id": cast[ln["who"]]["voice_id"]} for ln in lines]}
    # In the cloud environment the network layer supplies the key; elsewhere set ELEVENLABS_API_KEY.
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "from-proxy")})
    with urllib.request.urlopen(req, timeout=300) as r:
        out.write_bytes(r.read())


def render(script: dict[str, Any], out: Path) -> None:
    cast = json.loads(VOICES.read_text())
    keep = os.environ.get("LOCKCALL_KEEP")  # a folder to keep the raw voice renders in, for checking or remixing
    with tempfile.TemporaryDirectory() as tmp:
        hook, talk = Path(keep or tmp) / "hook.mp3", Path(keep or tmp) / "talk.mp3"
        _speak([ln for ln in script["lines"] if ln["part"] == "hook"], cast, hook)
        _speak([ln for ln in script["lines"] if ln["part"] != "hook"], cast, talk)
        mix(hook, talk, out)


def video(ep: dict[str, Any], out: Path) -> tuple[int, int]:
    """A square video of an episode for the social networks: the cover, held from the first frame."""
    static = POD_DIR.parent.parent / "templates"
    still = out.with_suffix(".cover.png")  # scale the cover once; looping the 3000 px original is very slow
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(static / SHOW["cover"]), "-vf", "scale=1080:1080", str(still)],
                   check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "15", "-i", str(still),
                    "-i", str(static / ep["audio"]), "-shortest", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)], check=True)
    still.unlink()
    return 1080, 1080


def bluesky_text(ep: dict[str, Any], base: str = "https://hardwoodbricks.com/") -> str:
    return f"{ep['title']}\n\n{ep['blurb']} Two minutes, with the picks.\n\n{base}{SHOW['page']}\n\n#Midmaxxing"


def bluesky(ep_id: str | None = None) -> str:
    """Post one episode's video to Bluesky. Skips an episode already posted; needs BSKY_HANDLE and BSKY_APP_PASSWORD."""
    from . import reels
    eps = episodes()
    ep = next((e for e in eps if e["id"] == ep_id), None) if ep_id else (eps[0] if eps else None)
    if not ep:
        return "no such episode"
    text = bluesky_text(ep)
    if len(text) > 300:
        return f"caption is {len(text)} characters; Bluesky takes 300"
    sess = reels.bsky_session(os.environ["BSKY_HANDLE"].strip(), os.environ["BSKY_APP_PASSWORD"].strip())
    if reels.bsky_already(sess, text.split("\n")[0]):
        return "already posted"
    with tempfile.TemporaryDirectory() as tmp:
        mp4 = Path(tmp) / f"lock-call-{ep['id']}.mp4"
        return "posted " + reels.bsky_video(sess, mp4, text, video(ep, mp4))


def publish(script_path: Path, mp3: Path, now: datetime | None = None) -> dict[str, Any]:
    """Put a recorded episode on the site and in the feed: copy the audio in and add its row to episodes.json.

    The script carries `title` and `blurb`. Running it twice for the same day replaces that day's row."""
    script = json.loads(script_path.read_text())
    day = script["date"]
    audio = f"static/podcast/lock-call-{day}.mp3"
    dest = POD_DIR.parent.parent / "templates" / audio
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(mp3.read_bytes())
    secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(dest)],
                                check=True, capture_output=True, text=True).stdout)
    row = {"id": day, "date": day, "published": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
           "title": script["title"], "blurb": script["blurb"], "audio": audio, "bytes": dest.stat().st_size,
           "seconds": round(secs), "script": f"data/podcast/{script_path.name}"}
    if len(bluesky_text(row)) > 300:
        raise ValueError(f"blurb too long: the Bluesky caption is {len(bluesky_text(row))} characters; it takes 300")
    rows = [r for r in (json.loads(EPISODES.read_text()) if EPISODES.exists() else []) if r["id"] != day]
    EPISODES.write_text(json.dumps([*rows, row], indent=1) + "\n")
    return row


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "facts"
    if cmd == "facts":
        print(json.dumps(facts(argv[1] if len(argv) > 1 else None), indent=1))
        return 0
    if cmd == "bluesky":
        print("bluesky:", bluesky(argv[1] if len(argv) > 1 else None))
        return 0
    if cmd == "publish":
        print(json.dumps(publish(Path(argv[1]), Path(argv[2])), indent=1))
        return 0
    script = json.loads(Path(argv[1]).read_text())
    problems = check(script)
    for p in problems:
        print("FIX:", p)
    if cmd == "check" or problems:
        return 1 if problems else 0
    render(script, Path(argv[2]))
    print("wrote", argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
