"""Render a long-form documentary rough cut from a script JSON.

    python tools/docs_render.py docs/athens --out docs/athens/out [--no-voice]

<dir>/lines.json lists lines (speaker, say, caption, visual). A visual is a photo stem
(looked up in <dir>/photos, then <dir>/broll), "card:Title|Subtitle", or null (keep the
last picture). Voices: each speaker's reference clip is cloned with Chatterbox
(tools/clone_voice.py, run by $VOICE_CLONE_PY); a speaker whose clip is missing reads
with Piper ($PIPER_DIR/<voice>.onnx). Writes <name>.mp4 (720p) and <name>.srt.
"""
import argparse, json, os, re, subprocess, sys, textwrap, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
F = ROOT / "templates/static/fonts"
W, H, FPS, SR = 1280, 720, 25, 24000
PAGE, INK, MUTED, GOLD = (21, 17, 13), (239, 230, 214), (143, 132, 116), (240, 199, 94)
GAP, TAIL, CARD = 0.22, 0.55, 4.0
CLIPDIR = Path(".")


def font(n, s):
    return ImageFont.truetype(str(F / n), s)


def ff(*a):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *a], check=True)


def card(title, sub, path):
    im = Image.new("RGB", (W, H), PAGE); d = ImageDraw.Draw(im)
    big = len(title) < 40; t = font("Newsreader-SemiBold.ttf", 58 if big else 40)
    lines = textwrap.wrap(title, 34 if big else 52); y = H // 2 - 40 * len(lines) - 10
    for ln in lines:
        d.text(((W - d.textlength(ln, font=t)) / 2, y), ln, font=t, fill=INK); y += t.size + 14
    d.line([(W / 2 - 60, y + 12), (W / 2 + 60, y + 12)], fill=GOLD, width=3)
    s = font("BarlowCondensed-SemiBold.ttf", 30); sub = sub.upper()
    d.text(((W - d.textlength(sub, font=s)) / 2, y + 34), sub, font=s, fill=MUTED)
    im.save(path)


def photo(src, path):
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    CW, CH = int(W * 1.25), int(H * 1.25)
    bg = ImageOps.fit(im, (CW, CH))
    if im.width / im.height < 1.2:
        bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(30))).enhance(0.45)
        fg = ImageOps.contain(im, (CW, CH)); bg.paste(fg, ((CW - fg.width) // 2, (CH - fg.height) // 2))
    bg.save(path, quality=92)


def caption(name, text, path):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    body, nm = font("Barlow-Regular.ttf", 27), font("BarlowCondensed-Bold.ttf", 24)
    lines = textwrap.wrap(text, 78)
    if len(lines) > 4:
        lines = lines[:4]; lines[-1] += " …"
    h = 46 + 36 * len(lines)
    d.rectangle([0, H - h - 24, W, H], fill=(15, 12, 9, 200)); d.text((60, H - h - 12), name, font=nm, fill=GOLD)
    y = H - h + 20
    for ln in lines:
        d.text((60, y), ln, font=body, fill=INK); y += 36
    im.save(path)


def read_wav(p):
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def sentences(t):
    parts = re.split(r"(?<=[.?!])\s+", t.strip())
    out, cur = [], ""
    for p in parts:  # keep chunks between ~6 and ~40 words
        if cur and len((cur + " " + p).split()) > 40:
            out.append(cur); cur = p
        else:
            cur = (cur + " " + p).strip()
    return out + ([cur] if cur else [])


def voice(lines, voices, work, use_voice):
    """One 24 kHz mono int16 array per line (silence for cards)."""
    work.mkdir(parents=True, exist_ok=True)
    jobs, piper, plan = [], [], []
    for i, ln in enumerate(lines):
        v = voices.get(ln["speaker"])
        if not v or not use_voice:
            plan.append([]); continue
        chunks = []
        for k, s in enumerate(sentences(ln["say"])):
            raw = work / f"l{i:03d}_{k}.raw.wav"; chunks.append(raw)
            ref = v.get("ref_path")
            if ref and os.environ.get("VOICE_CLONE_PY"):
                jobs.append({"text": s, "out": str(raw), "ref": ref})
            else:
                piper.append((s, raw, v.get("piper", "en_US-ryan-high")))
        plan.append(chunks)
    if jobs:
        jf = work / "jobs.json"; json.dump(jobs, open(jf, "w"))
        subprocess.run([os.environ["VOICE_CLONE_PY"], str(ROOT / "tools/clone_voice.py"), "--jobs", str(jf)], check=True)
    for s, raw, pv in piper:
        model = Path(os.environ.get("PIPER_DIR", "voices")) / f"{pv}.onnx"
        subprocess.run([sys.executable, "-m", "piper", "-m", str(model), "-f", str(raw)], input=s.encode(), check=True)
    out = []
    for i, chunks in enumerate(plan):
        vis = lines[i].get("visual") or ""
        if lines[i]["speaker"] == "CLIP" and vis.startswith("clip:"):
            src = CLIPDIR / f"{vis[5:]}.mp4"
            if src.exists():
                wav = work / f"clip{i:03d}.wav"
                ff("-i", str(src), "-vn", "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", "-af", "volume=0.8", str(wav))
                out.append(read_wav(wav)); continue
        if not chunks:
            n = len(lines[i]["say"].split())
            secs = CARD if lines[i]["speaker"] in ("TITLE", "CHAP") else max(2.2, n / 2.4 + TAIL)
            out.append(np.zeros(int(secs * SR), np.int16)); continue
        parts = []
        for c in chunks:
            norm = c.with_suffix(".24k.wav"); ff("-i", str(c), "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", str(norm))
            parts += [read_wav(norm), np.zeros(int(GAP * SR), np.int16)]
        parts[-1] = np.zeros(int(TAIL * SR), np.int16)
        out.append(np.concatenate(parts))
    return out


def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("--out", required=True)
    ap.add_argument("--no-voice", action="store_true"); a = ap.parse_args()
    global CLIPDIR
    d, out = Path(a.dir), Path(a.out); CLIPDIR = d / "clips"; out.mkdir(parents=True, exist_ok=True); work = Path("/tmp/docwork"); work.mkdir(exist_ok=True)
    spec = json.load(open(d / "lines.json")); lines = spec["lines"]; voices = spec["voices"]
    for v in voices.values():
        r = v.get("ref")
        if r == "matthew":
            r = os.environ.get("MATTHEW_REF")
        if r and Path(r).exists():
            wav = work / (Path(r).stem + ".ref.wav"); ff("-i", r, "-ac", "1", "-ar", str(SR), str(wav)); v["ref_path"] = str(wav)
    # closing credits for every Commons/LOC picture and fair-use clip used
    cred = {c["file"][:-4]: c for c in json.load(open(d / "broll/credits.json"))} if (d / "broll/credits.json").exists() else {}
    rows = []
    for ln in lines:
        v = ln.get("visual") or ""
        if v in cred and not any(r[0] == v for r in rows):
            c = cred[v]; ttl = re.sub(r"\s*-\s*DPLA\s*-\s*[0-9a-f]+|\.(jpe?g|png|tif)$", "", c["title"].replace("File:", ""), flags=re.I)
            rows.append((v, f"{ttl[:80]} · {c['author'][:60] or 'author unknown'} · {c['license']} · {c['source']}"))
        if v.startswith("clip:") and not any(r[0] == v for r in rows):
            rows.append((v, ln["caption"]))
    rows.append(("own", "Athens photographs by Matthew Hagan, 2017 to 2025"))
    for k in range(0, len(rows), 7):
        lines.append({"speaker": "TITLE", "say": "", "caption": "", "visual": "credits:" + "\n".join(r[1] for r in rows[k:k + 7])})
    audio = voice(lines, voices, work / "vo", not a.no_voice)
    durs = [len(x) / SR for x in audio]
    # shots: runs of lines that share a picture
    shots = []
    for i, ln in enumerate(lines):
        if ln["visual"] is not None or not shots:
            shots.append({"visual": ln["visual"], "idx": []})
        shots[-1]["idx"].append(i)
    clips, t_abs, srt = [], 0.0, []
    for n, sh in enumerate(shots):
        vis = sh["visual"]
        clip_src = d / "clips" / f"{vis[5:]}.mp4" if vis.startswith("clip:") else None
        if clip_src is not None:
            if clip_src.exists():
                D = sum(durs[i] for i in sh["idx"]); cp = work / f"c{n:03d}_clip.png"
                credit = lines[sh["idx"][0]]["caption"]
                im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(im); fnt = font("Barlow-Regular.ttf", 20)
                dd.rectangle([0, H - 44, W, H], fill=(15, 12, 9, 170)); dd.text((24, H - 34), credit, font=fnt, fill=INK); im.save(cp)
                clip = work / f"s{n:03d}.mp4"
                ff("-i", str(clip_src), "-i", str(cp), "-filter_complex",
                   f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p[v];[v][1:v]overlay=0:0[out]",
                   "-map", "[out]", "-t", f"{D:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", str(clip))
                clips.append(clip); t_abs += D; print(f"shot {n}: {vis} {D:.1f}s", flush=True); continue
            vis = "card:Clip missing|" + vis[5:]
        if vis.startswith("credits:"):
            img = work / f"v{n:03d}.png"; im = Image.new("RGB", (W, H), PAGE); dd = ImageDraw.Draw(im)
            dd.text((80, 70), "PICTURE CREDITS", font=font("BarlowCondensed-Bold.ttf", 34), fill=GOLD); y = 140
            for row in vis[8:].split("\n"):
                for ln2 in textwrap.wrap(row, 96):
                    dd.text((80, y), ln2, font=font("Barlow-Regular.ttf", 22), fill=INK); y += 30
                y += 16
            im.save(img)
        elif vis.startswith("card:"):
            img = work / f"v{n:03d}.png"; t, s = vis[5:].split("|", 1); card(t, s, img)
        else:
            src = next((p for p in (d / "photos" / f"{vis}.jpg", d / "broll" / f"{vis}.jpg") if p.exists()), None)
            if not src:
                img = work / f"v{n:03d}.png"; card(vis, "picture missing", img)
            else:
                img = work / f"v{n:03d}.jpg"; photo(src, img)
        D = sum(durs[i] for i in sh["idx"]); fr = int(round(D * FPS)) + 2
        args, caps, t0 = ["-loop", "1", "-i", str(img)], [], 0.0
        for k, i in enumerate(sh["idx"]):
            ln = lines[i]; v = voices.get(ln["speaker"])
            if v:
                cp = work / f"c{n:03d}_{k}.png"; caption(v["name"], ln["caption"], cp); args += ["-i", str(cp)]
                caps.append((t0, t0 + durs[i]))
                srt.append((t_abs + t0, t_abs + t0 + durs[i] - TAIL + 0.1, f"{v['name']}: {ln['caption']}"))
            t0 += durs[i]
        if vis.startswith(("card:", "credits:")) or not img.suffix == ".jpg":
            f = f"[0:v]scale={W}:{H},format=yuv420p[b0]"
        else:
            z = "'min(1+0.00035*on,1.2)'" if n % 2 == 0 else "'max(1.2-0.00035*on,1)'"
            f = (f"[0:v]scale={W*2}:-2,zoompan=z={z}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                 f":d={fr}:s={W}x{H}:fps={FPS},format=yuv420p[b0]")
        last = "b0"
        for j, (s0, s1) in enumerate(caps):
            f += f";[{last}][{j+1}:v]overlay=0:0:enable='between(t,{s0:.3f},{s1:.3f})'[b{j+1}]"; last = f"b{j+1}"
        f += f";[{last}]fade=in:st=0:d=0.4,fade=out:st={max(D-0.4,0):.3f}:d=0.4[out]"
        clip = work / f"s{n:03d}.mp4"
        ff(*args, "-filter_complex", f, "-map", "[out]", "-t", f"{D:.3f}", "-r", str(FPS),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", str(clip))
        clips.append(clip); t_abs += D; print(f"shot {n}: {vis[:40]} {D:.1f}s", flush=True)
    (work / "list.txt").write_text("".join(f"file '{c}'\n" for c in clips))
    track = work / "voice.wav"
    with wave.open(str(track), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(np.concatenate(audio).tobytes())
    name = re.sub(r"[^a-z0-9]+", "-", spec["title"].lower()).strip("-") + "-rough"
    ff("-f", "concat", "-safe", "0", "-i", str(work / "list.txt"), "-i", str(track), "-map", "0:v", "-map", "1:a",
       "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "loudnorm=I=-16:TP=-1.5", "-shortest", "-movflags", "+faststart", str(out / f"{name}.mp4"))
    (out / f"{name}.srt").write_text("\n".join(f"{k+1}\n{srt_time(a)} --> {srt_time(b)}\n{t}\n" for k, (a, b, t) in enumerate(srt)))
    print("wrote", out / f"{name}.mp4", f"{t_abs/60:.1f} min")


if __name__ == "__main__":
    main()
