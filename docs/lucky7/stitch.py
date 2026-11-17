"""Stitch the seven rendered Lucky Seven episodes into one film.

    python docs/lucky7/stitch.py <workdir>

Uses each episode's out/vo/<speaker>-NN.ogg (every voiced line, saved by save_all_vo), its Commons
B-roll and credits, and the house plates and outros from docs/akron. Writes <workdir>/film/lines.json,
photos/, broll/, clips/ and takes/, then renders with tools/docs_render.py (voices taken from takes/).
"""
import json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPS = sorted((ROOT / "docs").glob("lucky7-[1-7]-*"))


def main():
    work = Path(sys.argv[1]); film = work / "film"
    if film.exists():
        shutil.rmtree(film)
    for sub in ("photos", "broll", "clips", "takes"):
        (film / sub).mkdir(parents=True)
    for p in (ROOT / "docs/akron/photos").glob("logo-*.jpg"):
        shutil.copy(p, film / "photos")
    for c in ("hardwood-outro", "juicebox-outro"):
        shutil.copy(ROOT / f"docs/akron/clips/{c}.mp4", film / "clips")
    voices, lines, credits, picks = {}, [], [], json.load(open(work / "picks.json")) if (work / "picks.json").exists() else {}
    lines += [{"speaker": "TITLE", "say": "", "caption": "", "visual": f"still:logo-{k}"} for k in ("hardwood-bricks", "juicebox", "19-north", "hocking-miami")]
    lines.append({"speaker": "TITLE", "say": "", "caption": "", "visual": "card:Lucky Seven|The seventh governors of the Ivy League states"})
    merged_n, missing = {}, []
    for ep in EPS:
        spec = json.load(open(ep / "lines.json")); voices.update(spec["voices"])
        for c in json.load(open(ep / "broll/credits.json")) if (ep / "broll/credits.json").exists() else []:
            credits.append(c); src = ep / "broll" / c["file"]
            if src.exists():
                shutil.copy(src, film / "broll" / c["file"])
        local_n = {}
        for ln in spec["lines"]:
            ln = dict(ln)
            if ln.get("visual") in picks:          # a hand-picked picture swap after looking at the contact sheets
                ln["visual"] = picks[ln["visual"]]
            sp = ln["speaker"]
            if sp in spec["voices"]:
                local_n[sp] = local_n.get(sp, 0) + 1; merged_n[sp] = merged_n.get(sp, 0) + 1
                src = ep / "out/vo" / f"{sp}-{local_n[sp]:02d}.ogg"
                if src.exists():
                    shutil.copy(src, film / "takes" / f"{sp}-{merged_n[sp]:02d}.ogg")
                else:
                    missing.append(f"{ep.name} {sp}-{local_n[sp]:02d}")
            lines.append(ln)
    names = ", ".join(v["name"].title() for k, v in voices.items() if k != "M")
    lines.append({"speaker": "TITLE", "say": "", "caption": "",
                  "visual": f"card:A Hardwood Bricks film|{names} are fictional AI anchors with AI voices"})
    lines += [{"speaker": "OUTRO", "say": "", "caption": "", "visual": v} for v in ("clip:hardwood-outro", "clip:juicebox-outro", "still:logo-19-north")]
    json.dump(credits, open(film / "broll/credits.json", "w"), indent=1)
    json.dump({"title": "Lucky Seven", "own_credit": "Pictures from Wikimedia Commons under the licenses listed",
               "voices": voices, "lines": lines}, open(film / "lines.json", "w"), indent=1, ensure_ascii=False)
    print(len(lines), "lines;", sum(merged_n.values()), "voiced;", len(missing), "missing takes", missing[:10])
    if "--render" in sys.argv:
        env = {**__import__("os").environ, "DOC_TAKES": str(film / "takes")}
        subprocess.run([sys.executable, str(ROOT / "tools/docs_render.py"), str(film), "--out", str(work / "out"), "--no-voice"], check=True, env=env)


if __name__ == "__main__":
    main()
