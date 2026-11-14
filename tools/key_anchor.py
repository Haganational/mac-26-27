"""Key an anchor portrait off its green screen: anchors/<team key>.webp with a transparent background.

    python tools/key_anchor.py <team key> <portrait.jpg> [<team key> <portrait.jpg> ...]

Screen is green close to the color at the top of the frame, connected to the border, near it (hair),
or in a sizable enclosed patch (between an arm and the body). A green shirt, stripe or tie is a
different green and stays. Green spill is pulled out near the cut line
only, and the result is scaled to 720 wide to keep the repo light.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "anchors"
WIDTH = 720
SCREEN_HUE = 10  # degrees: Jacksonville's collar is a bluer green (~154) than the screen (~132)
SCREEN_DIST = 60  # how far (RGB distance) a pixel may be from the screen's color and still be screen


def key(src: Path) -> Image.Image:
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # The screen's own color, from the top of the frame. Green clothing (Jacksonville's stripes, FGCU's tie) is a
    # different, darker green, so only green close to the screen's color counts as screen.
    h0 = a.shape[0]
    screen = np.median(a[: h0 // 20].reshape(-1, 3), axis=0)
    def hue(px: np.ndarray) -> np.ndarray:  # for green-dominant pixels: 120 is pure green, higher leans blue
        rr, gg, bb = px[..., 0], px[..., 1], px[..., 2]
        return 60 * (2 + (bb - rr) / np.maximum(gg - np.minimum(rr, bb), 1))
    near = (np.linalg.norm(a - screen, axis=-1) < SCREEN_DIST) & (np.abs(hue(a) - hue(screen)) < SCREEN_HUE)
    vivid = g - np.maximum(r, b) > 40
    # Clothing is a solid block of off-screen green; an opening drops thin strands, so hair edges still get keyed.
    # Off-screen green that is bluer than the screen (stripes, ties); hair over the screen and the darker
    # corners of the screen keep the screen's hue.
    other = vivid & ~near & (hue(a) - hue(screen) > SCREEN_HUE)
    off = Image.fromarray(np.where(other, 255, 0).astype(np.uint8))
    clothing = np.asarray(off.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(9))) > 0
    green = vivid & (g > 100) & ~clothing
    mask = Image.fromarray(np.where(green, 255, 0).astype(np.uint8)).copy()  # a copy: floodfill needs its own buffer
    w, h = mask.size
    seeds = [(x, y) for x in range(0, w, 32) for y in (0, h - 1)] + [(x, y) for y in range(0, h, 32) for x in (0, w - 1)]
    for x, y in seeds:
        if mask.getpixel((x, y)) == 255:
            ImageDraw.floodfill(mask, (x, y), 128)
    bg = np.asarray(mask) == 128

    def grow(m: np.ndarray, times: int) -> np.ndarray:
        im = Image.fromarray(np.where(m, 255, 0).astype(np.uint8))
        for _ in range(times):
            im = im.filter(ImageFilter.MaxFilter(9))
        return np.asarray(im) > 0

    # Screen showing through loose hair is cut off from the border; take green that sits near the background too.
    bg = bg | (green & grow(bg, 20))
    # Screen seen through a gap between an arm and the body is cut off too; take any sizable patch of it.
    # A green logo or shirt is darker (G at most ~27 over R, B) and does not count as screen.
    gaps = Image.fromarray(np.where(green & ~bg, 255, 0).astype(np.uint8)).copy()
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            if gaps.getpixel((x, y)) == 255:
                ImageDraw.floodfill(gaps, (x, y), 100)
                g_arr = np.asarray(gaps)
                patch = g_arr == 100
                big = patch.sum() >= 400
                if big:
                    bg = bg | patch
                ImageDraw.floodfill(gaps, (x, y), 50 if big else 1)
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.6))
    # Despill: a band a few pixels inside the cut, where green light wraps around hair and shoulders.
    edge = grow(bg, 12)
    out = a.copy()
    cap = np.maximum(r, b)
    out[..., 1] = np.where(edge & ~clothing & (g - cap > 12), cap + 12, g)  # a green shirt (G at most ~27 over R, B) barely changes
    rgba = Image.fromarray(out.clip(0, 255).astype(np.uint8)).convert("RGBA")
    rgba.putalpha(alpha)
    return rgba.resize((WIDTH, round(h * WIDTH / w)), Image.LANCZOS)


def main() -> None:
    args = sys.argv[1:]
    if not args or len(args) % 2:
        raise SystemExit(__doc__)
    OUT.mkdir(exist_ok=True)
    for k, src in zip(args[::2], args[1::2]):
        dest = OUT / f"{k}.webp"
        key(Path(src)).save(dest, "WEBP", quality=88, method=6)
        print(f"{dest} {dest.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
