"""Who has an anchor, a portrait and a dossier, and what's still missing (Matthew, Nov 16 2026).

    python tools/anchor_roster.py [--drafts DIR] [--out FILE.csv]

One row per school across every edition. Name comes from data/anchors.json; when a school has
no row there, a draft name from the project's roster TSVs (--drafts, columns School and
Anchor_Name) is shown as 'draft'. next = what Matthew or the desk does next:
  name     no anchor name yet (pick one)
  headshot has a name, no anchors/<key>.webp (make the green-screen portrait)
  wire     has a draft name and maybe a portrait but no data/anchors.json row
  dossier  has name and portrait, no data/anchor_dossiers.json entry
  ok       all three
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mac.leagues import ALL  # noqa: E402


def drafts(folder: Path | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if folder and folder.is_dir():
        for f in sorted(folder.glob("*.tsv")):
            for r in csv.DictReader(f.open(), delimiter="\t"):
                if r.get("School") and r.get("Anchor_Name"):
                    out[r["School"].strip().lower()] = r["Anchor_Name"].strip()
    return out


def rows(draft_names: dict[str, str]) -> list[dict[str, str]]:
    anchors = json.loads((ROOT / "data" / "anchors.json").read_text())["anchors"]
    dpath = ROOT / "data" / "anchor_dossiers.json"
    dossiers = json.loads(dpath.read_text())["dossiers"] if dpath.exists() else {}
    out = []
    for lg in ALL.values():
        for t in lg.teams:
            a = anchors.get(t.key)
            name, src = (a["name"], "roster") if a else (draft_names.get(t.short.lower()) or draft_names.get(t.name.lower()) or "", "draft")
            if not name:
                src = ""
            pic = (ROOT / "anchors" / f"{t.key}.webp").exists()
            dos = dossiers.get(t.key, {})
            if not name:
                nxt = "name"
            elif not pic:
                nxt = "headshot"
            elif not a:
                nxt = "wire"
            elif not dos:
                nxt = "dossier"
            else:
                nxt = "ok"
            out.append({"edition": lg.short, "key": t.key, "school": t.short, "anchor": name, "name_source": src,
                        "portrait": "yes" if pic else "no", "dossier": dos.get("status", "no"), "tape": dos.get("tape", ""), "next": nxt})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", type=Path, default=Path("/mnt/project-files/anchors-roster"))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rs = rows(drafts(args.drafts))
    if args.out:
        with args.out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rs[0]))
            w.writeheader()
            w.writerows(rs)
    print(f"{len(rs)} schools: " + ", ".join(f"{k} {v}" for k, v in Counter(r["next"] for r in rs).most_common()))


if __name__ == "__main__":
    main()
