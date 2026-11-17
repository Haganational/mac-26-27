"""Make the byline head crops: anchors/heads/<key>.webp (96px squares) from anchors/<key>.webp.

    python tools/anchor_heads.py           # every portrait whose crop is missing or older
    python tools/anchor_heads.py --all     # redo them all

Run it after adding or replacing a portrait and commit anchors/heads/. The site build copies the crops
(mac/den_connect.publish_heads) and makes any missing one on the fly, which is slow (about 0.2s each).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mac import anchors  # noqa: E402
from mac.den_connect import head_crop  # noqa: E402


def main(argv: list[str]) -> int:
    redo = "--all" in argv
    out_dir = anchors.PORTRAITS / "heads"
    out_dir.mkdir(exist_ok=True)
    n = 0
    for p in sorted(anchors.PORTRAITS.glob("*.webp")):
        out = out_dir / p.name
        if not redo and out.exists() and out.stat().st_mtime >= p.stat().st_mtime:
            continue
        head_crop(p).save(out, "WEBP", quality=82, method=6)
        n += 1
    print(f"{n} head crops written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
