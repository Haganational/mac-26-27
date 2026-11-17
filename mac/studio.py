"""The studio set: the anchor seated behind the desk, for the daily Short and the image posts.

    python -m mac.studio kent-state out.png --w 1080 --h 860 --x 0.24

The set is the MIDnight Weave studio (Matthew's ImagineArt plates, Nov 2026), committed small in sets/:

  desk-center.jpg  the center chair: bookshelves, brass lamps, the curved walnut desk across the bottom
  desk-wide.jpg    the three-chair desk, 16:9
  studio.jpg       the whole room, vertical (the cover and the room behind the board)
  studio-alt.jpg   the side desk, vertical (the sign-off)

desk_shot() puts an anchor's keyed portrait (anchors/<key>.webp) behind the center desk, so the
desk's front edge crosses their chest the way a real anchor sits, with the room's warm light on them.
"""
from __future__ import annotations

import argparse
import hashlib
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SETS = ROOT / "sets"
DESK = SETS / "desk-center.jpg"  # 1440x1928
WIDE = SETS / "desk-wide.jpg"
ROOM = SETS / "studio.jpg"
SIDE = SETS / "studio-alt.jpg"

# The desk's back edge on desk-center.jpg, measured on the full plate (3584 wide): row 2934 at the
# middle, curving down about 45 rows toward the sides. Scaled to the committed 1440-wide plate.
_PLATE_W = 3584


def desk_edge(x: np.ndarray, plate_w: int) -> np.ndarray:
    """Row of the desk's back edge at column x of a desk-center plate plate_w wide."""
    s = plate_w / _PLATE_W
    xf = x / s
    return (2934 + 45 * ((xf - 1800) / 1600) ** 2) * s


@lru_cache(None)
def plate(path: Path = DESK) -> Image.Image:
    return Image.open(path).convert("RGB")


def _cut(portrait: Path) -> Image.Image:
    im = Image.open(portrait).convert("RGBA")
    box = im.getchannel("A").getbbox() or (0, 0, im.width, im.height)
    return im.crop((0, box[1], im.width, im.height))  # trim the empty space above the hair


def _warm(im: Image.Image) -> Image.Image:
    """Bring a green-screen portrait into the set's light: a touch darker and warmer, softer contrast."""
    a = np.asarray(im).astype(np.float32)
    rgb = a[..., :3]
    rgb = 0.9 * rgb + 6  # lift the blacks, lower the whites
    rgb *= np.array([1.0, 0.95, 0.86], np.float32)  # tungsten
    # Light falls from the lamps above: a gentle top-to-bottom falloff.
    h = rgb.shape[0]
    rgb *= np.linspace(1.0, 0.82, h, dtype=np.float32)[:, None, None]
    a[..., :3] = np.clip(rgb, 0, 255)
    # Most portraits are cropped at the shoulders; fade the outer edges so no hard vertical line shows.
    w = a.shape[1]
    side = max(1, int(w * 0.07))
    ramp = np.ones(w, np.float32)
    ramp[:side] = np.linspace(0, 1, side) ** 0.8
    ramp[-side:] = np.linspace(1, 0, side) ** 0.8
    a[..., 3] *= ramp[None, :]
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def desk_shot(portrait: Path | None, w: int, h: int, x: float = 0.5, head: float = 0.07, edge: float = 0.70,
              chest: float = 0.78, fade_top: int = 0, fade_left: int = 0) -> Image.Image:
    """An anchor seated behind the center desk, w by h.

    x      where the anchor's center sits, as a share of the width
    head   where the top of their hair sits, as a share of the height
    edge   where the desk's back edge crosses the middle of the frame, as a share of the height
    chest  how much of the trimmed portrait shows above the desk (0.6 = down to mid-chest)
    fade_top / fade_left  pixels of soft fade to transparent, to melt the shot into a card
    """
    src = plate()
    sc = w / src.width
    if src.height * sc < h:  # a tall frame: scale to the height instead
        sc = h / src.height
    room = src.resize((round(src.width * sc), round(src.height * sc)), Image.LANCZOS)
    cx = (room.width - w) // 2
    edge_mid = float(desk_edge(np.array([src.width / 2]), src.width)[0]) * sc
    top = int(round(edge_mid - edge * h))
    top = max(0, min(top, room.height - h))
    bg = room.crop((cx, top, cx + w, top + h)).convert("RGBA")
    out = bg.copy()
    if portrait and Path(portrait).exists():
        a = _warm(_cut(Path(portrait)))
        y0, y_edge = head * h, edge * h
        s = (y_edge - y0) / (chest * a.height)
        a = a.resize((round(a.width * s), round(a.height * s)), Image.LANCZOS)
        # A soft shadow on the back wall, down and to the right, so they sit in the room rather than on it.
        sh = Image.new("RGBA", a.size, (0, 0, 0, 0))
        sh.putalpha(a.getchannel("A").point(lambda v: v * 0.45).filter(ImageFilter.GaussianBlur(18)))
        px = round(x * w - a.width / 2)
        out.paste(sh, (px + 14, round(y0) + 10), sh)
        out.paste(a, (px, round(y0)), a)
        # The desk in front: every pixel below the desk's back edge comes from the plate again.
        cols = np.arange(w) + cx
        rows = desk_edge(cols / sc, src.width) * sc - top
        yy = np.arange(h)[:, None]
        m = np.clip((yy - rows[None, :] + 1.0) / 2.0, 0, 1)  # two-pixel feather
        mask = Image.fromarray((m * 255).astype(np.uint8), "L")
        out.paste(bg, (0, 0), mask)
    if fade_top or fade_left:
        al = np.ones((h, w), np.float32)
        if fade_top:
            al *= np.clip(np.arange(h) / fade_top, 0, 1)[:, None] ** 1.5
        if fade_left:
            al *= np.clip(np.arange(w) / fade_left, 0, 1)[None, :] ** 1.5
        out.putalpha(Image.fromarray((al * 255).astype(np.uint8), "L"))
    return out


def room(path: Path, w: int, h: int, focus: float = 0.5) -> Image.Image:
    """A set plate cropped to fill w by h (focus = where the crop sits vertically, 0 top to 1 bottom)."""
    src = plate(path)
    sc = max(w / src.width, h / src.height)
    im = src.resize((round(src.width * sc), round(src.height * sc)), Image.LANCZOS)
    x = (im.width - w) // 2
    y = round((im.height - h) * focus)
    return im.crop((x, y, x + w, y + h))


def cached(out_dir: Path, name: str, make, **spec) -> Path:
    """Save make(**spec) as a PNG under out_dir once per distinct spec; returns the file."""
    key = hashlib.sha1(repr(sorted((k, str(v)) for k, v in spec.items())).encode()).hexdigest()[:10]
    p = Path(out_dir) / f"{name}-{key}.png"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        make(**spec).save(p)
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("out")
    ap.add_argument("--w", type=int, default=1080)
    ap.add_argument("--h", type=int, default=860)
    ap.add_argument("--x", type=float, default=0.5)
    a = ap.parse_args()
    desk_shot(ROOT / "anchors" / f"{a.key}.webp", a.w, a.h, a.x).save(a.out)


if __name__ == "__main__":
    main()
