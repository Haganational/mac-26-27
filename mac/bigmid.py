"""The Big Mid: a weekly five-minute recap of every conference we cover, for YouTube (16:9).

Two halves:

    edition(...)   runs inside each edition's build and writes site/<edition>/bigmid.json:
                   the week's record, the upset (or best win), the player of the week,
                   the standings leaders and the game to circle next week.
    python -m mac.bigmid --out out/
                   reads every edition's bigmid.json plus the At-Large Watch, writes the
                   episode script, voices it like MidMaxx60 and renders 1920x1080 cards.

Every fact comes from our own data (schedule, box scores, closing lines, the model).
If a number is missing, its sentence is left out.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

ORDER = ["mac", "horizon", "asun", "mw", "metro", "bigwest"]  # the order the editions run in the show
WEEK = timedelta(days=7)
VW, VH = 1920, 1080
MAX_SECS = 6 * 60 + 30  # "five-ish minutes": trim past six and a half
DROP_FIRST = ("star", "next")  # what goes first, from the last edition back, when the show runs long
WATCH_TOP = 6
SAID = {"horizon": "Horizon League"}  # how an edition's name is read aloud, where the short name doesn't work
NUM = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}


def _when(g: dict) -> datetime:
    return datetime.fromisoformat(g["date"].replace("Z", "+00:00"))


# ------------------------------------------------------------------ one edition's week (runs in build.py)

def edition(now: datetime, recent: list[dict], upcoming: list[dict], boxes: dict[str, dict], standings: list[dict]) -> dict[str, Any]:
    """This edition's week, told from its own teams' side. Uses the current LEAGUE (mac.config)."""
    from . import today
    from .config import BY_KEY, LEAGUE

    week = [g for g in recent if now - WEEK <= _when(g) <= now and g["home"].get("score") is not None]
    w = l = 0
    for g in week:
        for side, other in (("home", "away"), ("away", "home")):
            if g[side].get("key") in BY_KEY:
                won = (g[side]["score"] or 0) > (g[other]["score"] or 0)
                w, l = w + won, l + (not won)

    # The upset: our biggest closing underdog that won. Failing that, the most lopsided win over a D-I team.
    def dog(g: dict) -> float:
        h = g["home"].get("key") in BY_KEY
        sp = g.get("closing_spread")
        return (sp if h else -sp) if sp is not None else -99.0

    def won(g: dict) -> bool:
        ours = g["home"] if g["home"].get("key") in BY_KEY else g["away"]
        opp = g["away"] if ours is g["home"] else g["home"]
        return (ours["score"] or 0) > (opp["score"] or 0)

    lined_wins = [g for g in week if g.get("closing_spread") is not None and won(g)]
    upset, label = None, ""
    if lined_wins:
        g = max(lined_wins, key=dog)
        if dog(g) > 0:
            upset, label = g, "Upset of the week"
        else:
            upset = max(lined_wins, key=lambda g: abs(g["home"]["score"] - g["away"]["score"]))
            label = "Statement win of the week"
    upset_item = None
    if upset:
        it = today.result_item(upset, boxes.get(upset["game_id"]))
        upset_item = {"label": label, "text": f"{label}: {it['text']}", "card": it["card"]}

    # Player of the week: the most points by one of our players in a single game this week.
    ids = {t.espn_id: t for t in BY_KEY.values()}
    best = None
    for g in week:
        if upset and g["game_id"] == upset["game_id"]:
            continue  # the upset already names its top scorer
        for p in (boxes.get(g["game_id"]) or {}).get("players", []):
            if p.get("team_espn_id") in ids and not p.get("dnp") and p.get("pts") is not None:
                if not best or (p["pts"], p.get("reb") or 0) > (best[0]["pts"], best[0].get("reb") or 0):
                    best = (p, g)
    star = None
    if best and best[0]["pts"] >= 15:
        p, g = best
        team = ids[p["team_espn_id"]]
        ours = g["home"] if g["home"].get("espn_id") == team.espn_id else g["away"]
        opp = g["away"] if ours is g["home"] else g["home"]
        res = "win over" if (ours["score"] or 0) > (opp["score"] or 0) else "loss to"
        hi, lo = sorted((ours["score"] or 0, opp["score"] or 0), reverse=True)
        parts = [f"{p['pts']} points"] + ([f"{p['reb']} rebounds"] if (p.get("reb") or 0) >= 8 else []) \
            + ([f"{p['ast']} assists"] if (p.get("ast") or 0) >= 6 else [])
        star = {"name": p["name"], "key": team.key, "team": team.short, "abbr": team.abbr, "color": team.color, "espn_id": team.espn_id,
                "pts": p["pts"], "reb": p.get("reb"), "ast": p.get("ast"), "opp": today.school(opp.get("name"), opp.get("key")),
                "text": f"Player of the week: {p['name']} had {_list(parts)} in {team.short}'s "
                        f"{hi}-{lo} {res} {today.school(opp.get('name'), opp.get('key'))}."}

    # Circle it: next week's best game. Conference games first, then the tightest line.
    nxt = [g for g in upcoming if now <= _when(g) <= now + WEEK]

    def rank(g: dict) -> tuple:
        sp = ((g.get("line") or {}).get("latest") or {}).get("spread")
        both = g["home"].get("key") in BY_KEY and g["away"].get("key") in BY_KEY
        return (not both, sp is None, abs(sp) if sp is not None else 0, g["date"])

    circle = None
    if nxt:
        g = min(nxt, key=rank)
        it = today.preview_item(g)
        day = _when(g).astimezone(today.schedule_view.ET).strftime("%A")
        circle = {"text": f"Circle it: {day}, {it['text']}", "card": {**it["card"], "day": day}}

    leaders = [{"team": r["team"], "abbr": r["abbr"], "w": r["w"], "l": r["l"], "cw": r["cw"], "cl": r["cl"],
                "color": BY_KEY[r["key"]].color} for r in standings[:3] if r.get("games")]
    return {"key": LEAGUE.key, "name": LEAGUE.short, "full": LEAGUE.name, "built": now.isoformat(),
            "colors": [t.color for t in BY_KEY.values()], "w": w, "l": l, "games": len(week),
            "leaders": leaders, "upset": upset_item, "star": star, "next": circle}


# ------------------------------------------------------------------ the episode script (all editions)

def _list(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


def _leaders_line(e: dict) -> str:
    rows = e.get("leaders") or []
    if not rows:
        return ""
    conf = any(r["cw"] or r["cl"] for r in rows)
    top = [f"{r['team']} at {r['cw']}-{r['cl']}" if conf else f"{r['team']} at {r['w']}-{r['l']}" for r in rows[:2]]
    return f"{'Atop the league standings' if conf else 'Best records so far'}: {_list(top)}."


def episode(blocks: list[dict], watch: list[dict] | None, now: datetime) -> dict[str, Any]:
    """The show as segments, one card each: intro, then each edition's block, the At-Large Watch, outro."""
    blocks = sorted(blocks, key=lambda b: ORDER.index(b["key"]) if b["key"] in ORDER else 99)
    start, end = now - timedelta(days=7), now - timedelta(days=1)
    span = f"{start.strftime('%B %-d')} to {end.strftime('%B %-d')}" if start.month != end.month else f"{start.strftime('%B %-d')} to {end.day}"
    games = sum(b["games"] for b in blocks)
    segs: list[dict] = [{"kind": "intro", "text": f"This is The Big Mid, the week in mid-major basketball, {span}. "
                         f"{NUM.get(len(blocks), len(blocks))} conferences, {games} games.",
                         "editions": [b["name"] for b in blocks], "games": games, "span": span}]
    for b in blocks:
        rec = f"{SAID.get(b['key'], b['name'])} teams went {b['w']}-{b['l']} this week." if b["w"] + b["l"] else f"A quiet week for the {b['name']}."
        said = SAID.get(b["key"], b["name"])
        segs.append({"kind": "edition", "edition": b["key"], "name": b["name"], "full": b["full"], "colors": b["colors"],
                     "leaders": b["leaders"], "w": b["w"], "l": b["l"],
                     "text": f"The {said}. {rec} {_leaders_line(b)}".strip()})
        if b.get("upset"):
            segs.append({"kind": "result", "edition": b["key"], "colors": b["colors"], "name": b["name"], "label": b["upset"]["label"],
                         "text": b["upset"]["text"], "card": b["upset"]["card"]})
        if b.get("star"):
            segs.append({"kind": "star", "edition": b["key"], "colors": b["colors"], "name": b["name"], "text": b["star"]["text"], "card": b["star"]})
        if b.get("next"):
            segs.append({"kind": "next", "edition": b["key"], "colors": b["colors"], "name": b["name"], "text": b["next"]["text"], "card": b["next"]["card"]})
    rows = [r for r in (watch or []) if r.get("games")][:WATCH_TOP]
    if rows:
        names = [f"{r['short']} of the {r['conf_short']}" for r in rows[:4]]
        segs.append({"kind": "atlarge", "rows": rows,
                     "text": f"The At-Large Watch, our read on who could earn a bid without the auto bid: {_list(names)} lead the line."})
    segs.append({"kind": "outro", "text": "That's The Big Mid. MidMaxx60 runs every morning, and every line, box score and rating "
                 "is at Hardwood Bricks dot com. Keep it mid. Keep it real."})
    return {"date_iso": now.date().isoformat(), "span": span, "segments": segs,
            "words": sum(len(s["text"].split()) for s in segs)}


def trim(segments: list[dict], secs: list[float], budget: float = MAX_SECS) -> list[int]:
    """Indexes to keep so the show runs `budget` seconds or less: player-of-the-week segments go
    first (last edition back), then next-week games; each edition's header and upset always stay."""
    keep = list(range(len(segments)))
    for kind in DROP_FIRST:
        for i in reversed(range(len(segments))):
            if sum(secs[j] for j in keep) <= budget:
                return keep
            if segments[i]["kind"] == kind:
                keep.remove(i)
    return keep


# ------------------------------------------------------------------ render (python -m mac.bigmid)

def load_blocks(site: Path, now: datetime) -> list[dict]:
    """Every edition's bigmid.json under the built site, if it was built in the last two days."""
    out = []
    for p in sorted(site.glob("**/bigmid.json")):
        b = json.loads(p.read_text())
        if now - datetime.fromisoformat(b["built"]) <= timedelta(days=2):
            out.append(b)
    return out


def render(ep: dict, out: Path) -> Path:
    from . import midmaxx60 as mm
    from .config import TEMPLATES_DIR

    out = out.resolve()
    work = out / "bigmid-work"
    work.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    tpl = env.get_template("bigmid_card.html")
    css = mm.textures() + "\n" + mm.font_faces()
    segs = ep["segments"]
    wavs = [work / f"seg{i:02d}.wav" for i in range(len(segs))]
    desk = mm.voice_all(segs, wavs, work)
    cloned = desk["cloned"]
    keep = trim(segs, [mm.wav_seconds(w) + mm.PAD for w in wavs])
    segs, wavs = [segs[i] for i in keep], [wavs[i] for i in keep]

    clips, srt, events, clock = [], [], [], 0.0
    for i, (seg, wav) in enumerate(zip(segs, wavs)):
        html, png, clip = work / f"card{i:02d}.html", work / f"card{i:02d}.png", work / f"clip{i:02d}.mp4"
        html.write_text(tpl.render(seg=seg, span=ep["span"], css=css))
        mm.shoot(html, png, VW, VH)
        speech = mm.wav_seconds(wav)
        dur = speech + mm.PAD
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(png), "-i", str(wav),
                        "-filter_complex", f"[0:v]fps={mm.FPS},format=yuv420p[v];[1:a]apad=pad_dur={mm.PAD},aresample=44100[a]",
                        "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                        "-r", str(mm.FPS), "-c:a", "aac", "-b:a", "128k", "-ac", "2", str(clip)], check=True)
        clips.append(clip)
        srt.append(f"{i + 1}\n{mm.srt_time(clock)} --> {mm.srt_time(clock + speech)}\n{seg['text']}\n")
        pic = (seg.get("anchor") or {}).get("portrait")
        events += mm.ass_events(seg["text"], clock, speech, margin_r=560 if pic else 0)
        clock += dur

    stem = f"bigmid-{ep['date_iso']}"
    lst = work / "clips.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    joined = work / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)], check=True)
    ass = work / "captions.ass"
    ass.write_text(mm.ass_file(events, VW, VH, size=64, margin_v=60))
    video = out / f"{stem}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined.name, "-vf", f"ass={ass.name}:fontsdir={mm.FONT_DIR.resolve()}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    "-movflags", "+faststart", str(video)], check=True, cwd=work)
    (out / f"{stem}.srt").write_text("\n".join(srt))
    shutil.copy(work / "card00.png", out / f"{stem}-thumb.png")
    chapters, t = [], 0.0
    for seg, wav in zip(segs, wavs):
        if seg["kind"] in ("intro", "edition", "atlarge", "outro"):
            name = {"intro": "This week", "atlarge": "At-Large Watch", "outro": "Sign-off"}.get(seg["kind"]) or seg["full"]
            chapters.append(f"{int(t // 60)}:{int(t % 60):02d} {name}")
        t += mm.wav_seconds(wav) + mm.PAD
    voiced = mm.disclosure(cloned, desk["anchors"])
    (out / f"{stem}.txt").write_text(
        f"The Big Mid: every mid-major conference we cover, {ep['span']}.\n\n" + "\n".join(chapters) + "\n\n"
        + "\n\n".join(s["text"] for s in segs) + f"\n\n{voiced}Stats: ESPN. Lines: The Odds API. https://hardwoodbricks.com/\n")
    print(f"{video} {clock:.1f}s, {len(clips)} segments, voice: {'clone' if cloned else 'piper'}")
    return video


def main() -> None:
    from . import atlarge
    from .config import SITE_ROOT

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--site", default=str(SITE_ROOT))
    ap.add_argument("--script-only", action="store_true", help="write bigmid.json and stop")
    a = ap.parse_args()
    now = datetime.now().astimezone()
    blocks = load_blocks(Path(a.site), now)
    if not blocks:
        raise SystemExit("bigmid: no edition has a fresh bigmid.json; build the editions first")
    ctx = atlarge.page_context()
    ep = episode(blocks, (ctx or {}).get("rows"), now)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "bigmid.json").write_text(json.dumps(ep, indent=1))
    print(f"bigmid: {len(blocks)} editions, {len(ep['segments'])} segments, {ep['words']} words")
    if not a.script_only:
        render(ep, Path(a.out))


if __name__ == "__main__":
    main()
