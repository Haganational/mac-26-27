"""Travel art: every road trip in a league of the season as light, for backdrops and share images.

Each leg of each team's schedule is an arc of light in that team's color. Where the
corridors pile up (the Ohio-Michigan heartland) they burn white-hot. Campuses are
nuclei with electron orbits, particles ride the arcs, and a shockwave of sparks
bursts out of the middle of the league. Athens gets a ring of street bricks.

    python -m tools.travel_art              # the MAC: art into /mnt/project-files/art/ (or ./art), backdrop JPGs into templates/static/art/
    LEAGUE=asun python -m tools.travel_art  # the ASUN edition

Outputs a desktop (16:9) and phone (9:19.5) version, each with and without a caption.
"""

from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac import espn, travel  # noqa: E402
from mac.config import LEAGUE, SEASON_LABEL, TEAMS, TEMPLATES_DIR  # noqa: E402

SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
SERIF_I = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
SERIF_B = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
GOLD = (240, 199, 94)
# One look per league. The MAC burns hot over the Ohio-Michigan heartland, with Athens ringed
# in street bricks; the ASUN is Gulf water and sawgrass, bursting out of the middle of Florida;
# the Horizon is a molten pour over the Rust Belt, from Green Bay to Pittsburgh.
PROFILES = {
    "mac": {
        "title": "The MAC in Motion",
        "towns": {"akron": "Akron", "ball-state": "Muncie", "bowling-green": "Bowling Green", "buffalo": "Buffalo",
                  "central-michigan": "Mount Pleasant", "eastern-michigan": "Ypsilanti", "kent-state": "Kent",
                  "miami-oh": "Oxford", "ohio": "Athens", "toledo": "Toledo", "umass": "Amherst", "western-michigan": "Kalamazoo"},
        "big": ("ohio", ", Ohio"),
        "offsets": {"toledo": (-1, -1), "bowling-green": (-1, 1), "eastern-michigan": (1, -1), "akron": (1, 1), "kent-state": (1, -1),
                    "miami-oh": (-1, 1), "ball-state": (-1, -1), "central-michigan": (1, -1), "western-michigan": (-1, -1),
                    "buffalo": (1, -1), "umass": (-1, -1), "ohio": (1, 1)},
        "heart": (-83.0, 41.0),
        "bg": ((0.055, 0.06, 0.12), (0.04, 0.022, 0.014)),  # deep indigo at the heart, hickory-black at the edges
        "shock": (1.0, 0.62, 0.25),
        "spark": lambda hot: (1.0, 0.45 + 0.4 * hot, 0.12 + 0.3 * hot ** 2),
        "ember": (1.0, 0.7, 0.35),
        "map": ((214, 170, 90), (24, 46, 92), (150, 195, 245)),
        "halo": "bricks",
        "frames": {"desktop": (3200, 1800, (-82.6, 39.6), 27.0), "phone": (1290, 2796, (-80.4, 37.6), 14.8)},
    },
    "asun": {
        "title": "The ASUN in Motion",
        "towns": {"bellarmine": "Louisville", "fgcu": "Fort Myers", "jacksonville": "Jacksonville", "lipscomb": "Nashville",
                  "north-florida": "", "queens": "Charlotte", "stetson": "DeLand", "west-florida": "Pensacola"},
        "big": ("fgcu", ", Florida"),
        "offsets": {"bellarmine": (1, -1), "fgcu": (1, 1), "jacksonville": (1, -1), "lipscomb": (-1, -1), "queens": (1, -1),
                    "stetson": (1, 1), "west-florida": (-1, 1)},
        "heart": (-82.0, 28.8),
        "bg": ((0.02, 0.10, 0.12), (0.008, 0.035, 0.05)),  # lagoon teal at the heart, deep Gulf at the edges
        "shock": (0.35, 0.95, 0.85),
        "spark": lambda hot: (0.25 + 0.7 * hot, 0.85, 0.65 + 0.2 * hot),  # sea-foam to sand
        "ember": (0.95, 0.85, 0.55),
        "map": ((150, 210, 200), (10, 70, 90), (140, 220, 230)),
        "halo": "",
        "frames": {"desktop": (3200, 1800, (-83.4, 32.7), 22.0), "phone": (1290, 2796, (-82.9, 32.0), 11.5)},
    },
    "horizon": {
        "title": "The Horizon in Motion",
        "towns": {"cleveland-state": "Cleveland", "detroit-mercy": "Detroit", "green-bay": "Green Bay", "iu-indy": "Indianapolis",
                  "milwaukee": "Milwaukee", "northern-illinois": "DeKalb", "northern-kentucky": "Highland Heights",
                  "oakland": "Rochester", "purdue-fort-wayne": "Fort Wayne", "robert-morris": "Pittsburgh",
                  "wright-state": "Dayton", "youngstown-state": "Youngstown"},
        "big": ("youngstown-state", ", Ohio"),
        "offsets": {"cleveland-state": (-1, -1), "detroit-mercy": (-1, 1), "green-bay": (1, -1), "iu-indy": (-1, 1),
                    "milwaukee": (-1, 1), "northern-illinois": (-1, 1), "northern-kentucky": (1, 1), "oakland": (1, -1),
                    "purdue-fort-wayne": (-1, -1), "robert-morris": (1, 1), "wright-state": (1, 1), "youngstown-state": (1, -1)},
        "heart": (-84.4, 41.6),
        "bg": ((0.09, 0.05, 0.03), (0.025, 0.028, 0.034)),  # furnace glow at the heart, cold steel at the edges
        "shock": (1.0, 0.55, 0.18),
        "spark": lambda hot: (1.0, 0.35 + 0.5 * hot, 0.05 + 0.35 * hot ** 2),  # molten pour: red-orange to white-hot
        "ember": (1.0, 0.62, 0.25),
        "map": ((190, 196, 205), (34, 40, 48), (130, 150, 170)),
        "halo": "",
        "frames": {"desktop": (3200, 1800, (-84.4, 41.9), 17.0), "phone": (1290, 2796, (-84.3, 41.7), 10.5)},
    },
}
P = PROFILES[LEAGUE.key]
TOWN = P["towns"]


def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255


def glow_color(h: str) -> np.ndarray:
    """Team color lifted for light: keep the hue, push brightness and saturation."""
    c = hex_rgb(h)
    m = c.max() or 1
    c = c / m  # full brightness
    c = 0.72 * c + 0.28 * np.array([1, 0.95, 0.85])  # warm toward white a touch
    return c.astype(np.float32)


class Canvas:
    def __init__(self, w: int, h: int, center: tuple[float, float], span_x: float):
        self.w, self.h = w, h
        self.lon0, self.lat0 = center
        self.k = math.cos(math.radians(self.lat0))
        self.scale = w / span_x  # px per projected degree
        self.light = np.zeros((h, w, 3), np.float32)
        self.u = min(w, h) / 1800  # size unit (1 at desktop height)

    def xy(self, lon: float, lat: float) -> tuple[float, float]:
        x = (lon - self.lon0) * self.k * self.scale + self.w / 2
        y = (self.lat0 - lat) * self.scale + self.h / 2
        return x, y

    def splat(self, pts: np.ndarray, color: np.ndarray, weights: np.ndarray | float = 1.0) -> None:
        """Add light at float pixel positions (bilinear)."""
        if len(pts) == 0:
            return
        x, y = pts[:, 0], pts[:, 1]
        ok = (x >= 0) & (x < self.w - 1) & (y >= 0) & (y < self.h - 1)
        x, y = x[ok], y[ok]
        wv = np.broadcast_to(np.asarray(weights, np.float32), ok.shape)[ok]
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = x - x0, y - y0
        for dx, dy, f in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            amt = (f * wv)[:, None] * color[None, :]
            np.add.at(self.light, (y0 + dy, x0 + dx), amt)


def bezier(p0, p1, bend: float, n: int) -> np.ndarray:
    p0, p1 = np.array(p0, np.float32), np.array(p1, np.float32)
    mid = (p0 + p1) / 2
    d = p1 - p0
    perp = np.array([-d[1], d[0]], np.float32)
    c = mid + perp * bend
    t = np.linspace(0, 1, n, dtype=np.float32)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * c + t ** 2 * p1


def _box(a: np.ndarray, r: int, axis: int) -> np.ndarray:
    """Running mean of width 2r+1 along an axis (edges padded)."""
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
    hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
    lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(arr: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur, approximated by three box passes; big radii run on a downsampled copy."""
    f = 1
    while sigma / f > 12 and min(arr.shape[:2]) // (f * 2) > 64:
        f *= 2
    a = arr
    if f > 1:
        h, w = arr.shape[:2]
        a = arr[: h - h % f, : w - w % f].reshape(h // f, f, w // f, f, -1).mean(axis=(1, 3))
    r = max(1, int(round(math.sqrt(12 * (sigma / f) ** 2 / 3 + 1) / 2)))
    for _ in range(3):
        a = _box(_box(a, r, 0), r, 1)
    if f > 1:
        h, w = arr.shape[:2]
        im = [Image.fromarray(np.ascontiguousarray(a[:, :, ch]), mode="F").resize((w, h), Image.BILINEAR) for ch in range(3)]
        a = np.stack([np.asarray(x, np.float32) for x in im], axis=2)
    return a


def background(w: int, h: int, focus: tuple[float, float]) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - focus[0]) / w) ** 2 + ((yy - focus[1]) / h) ** 2)
    inner = np.array(P["bg"][0], np.float32)
    outer = np.array(P["bg"][1], np.float32)
    t = np.clip(d / 0.75, 0, 1)[:, :, None]
    return inner * (1 - t) + outer * t


def draw_basemap(img: Image.Image, cv: Canvas) -> None:
    import json
    bm = json.loads((TEMPLATES_DIR / "static" / "basemap.json").read_text())
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lw = max(1, round(1.4 * cv.u))

    def lines(geom):
        if geom["type"] == "MultiLineString":
            yield from geom["coordinates"]
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                yield from poly
        elif geom["type"] == "Polygon":
            yield from geom["coordinates"]

    for f in bm["countries"]["features"]:
        for ring in lines(f["geometry"]):
            d.line([cv.xy(*p) for p in ring], fill=P["map"][0] + (80,), width=lw)
    for ring in lines(bm["states"]["geometry"]):
        d.line([cv.xy(*p) for p in ring], fill=P["map"][0] + (34,), width=lw)
    for ring in lines(bm["lakes"]["geometry"]):
        pts = [cv.xy(*p) for p in ring]
        if len(pts) > 2:
            d.polygon(pts, fill=P["map"][1] + (85,))
            d.line(pts + [pts[0]], fill=P["map"][2] + (110,), width=lw)
    img.alpha_composite(layer)


def render(w: int, h: int, center: tuple[float, float], span_x: float, seed: int = 26) -> tuple[Image.Image, Canvas, dict]:
    rnd = random.Random(seed)
    nrng = np.random.default_rng(seed)
    cv = Canvas(w, h, center, span_x)
    u = cv.u
    itins = travel.all_itineraries(espn.load_schedule()["games"])
    bases = {k: (it["base"]["lon"], it["base"]["lat"]) for k, it in itins.items()}
    colors = {t.key: glow_color(t.color) for t in TEAMS}

    # 1. Road trips: every leg, home -> stop -> stop -> home, as arcs of team light.
    arcs = []
    total_miles, legs = 0, 0
    for key, it in itins.items():
        prev = bases[key]
        total_miles += it["totals"]["miles"]
        for leg in it["legs"]:
            if leg["site"] == "home":
                here = bases[key]
            else:
                here = (leg["lon"], leg["lat"])
                if None in here:  # a venue we couldn't place: skip the leg
                    continue
            if here != prev:
                arcs.append((key, prev, here))
                legs += 1
            prev = here
        if prev != bases[key]:
            arcs.append((key, prev, bases[key]))
    for key, a, b in arcs:
        p0, p1 = cv.xy(*a), cv.xy(*b)
        dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if dist < 2:
            continue
        bend = rnd.choice((-1, 1)) * rnd.uniform(0.12, 0.26)
        n = int(dist * 1.6) + 8
        pts = bezier(p0, p1, bend, n)
        # brighter in the middle of the flight, a faint wobble of "quantum" uncertainty
        t = np.linspace(0, 1, n, dtype=np.float32)
        wgt = (0.14 + 0.18 * np.sin(np.pi * t)) * 0.9
        cv.splat(pts, colors[key], wgt)
        # an electron (or two) riding the arc, with a comet tail behind it
        for _ in range(rnd.choice((1, 1, 2))):
            head = rnd.uniform(0.15, 0.95)
            tail = np.linspace(max(0, head - rnd.uniform(0.06, 0.14)), head, 60, dtype=np.float32)
            idx = (tail * (n - 1)).astype(int)
            fade = np.linspace(0, 1, len(idx), dtype=np.float32) ** 2.2
            cv.splat(pts[idx], colors[key] * 0.6 + 0.4, fade * 1.6)
            cv.splat(pts[idx[-1:]], np.array([1, 0.97, 0.9], np.float32), 22.0)

    # 2. The heart of the league: a shockwave and a spray of sparks (mind, blown).
    hx, hy = cv.xy(*P["heart"])
    for i, r in enumerate((90, 170, 270, 400, 560)):
        r *= u
        ang = np.linspace(0, 2 * np.pi, int(2 * np.pi * r * 1.2), dtype=np.float32)
        jitter = 1 + 0.02 * np.sin(ang * (7 + i * 3) + i)
        pts = np.stack([hx + r * jitter * np.cos(ang), hy + r * 0.82 * jitter * np.sin(ang)], 1)
        cv.splat(pts, np.array(P["shock"], np.float32), 1.1 / (1 + i * 0.45))
    for _ in range(int(900 * u + 200)):
        a = rnd.uniform(0, 2 * math.pi)
        r0 = rnd.uniform(20, 140) * u
        ln = rnd.expovariate(1 / (140 * u)) + 20 * u
        steps = max(6, int(ln))
        s = np.linspace(r0, r0 + ln, steps, dtype=np.float32)
        curve = rnd.uniform(-0.0012, 0.0012) / u
        aa = a + curve * (s - r0)
        pts = np.stack([hx + s * np.cos(aa), hy + 0.82 * s * np.sin(aa)], 1)
        hot = rnd.random()
        col = np.array(P["spark"](hot), np.float32)
        fade = np.linspace(1, 0, steps, dtype=np.float32) ** 1.5
        cv.splat(pts, col, fade * rnd.uniform(0.15, 0.7))
    embers = nrng.normal(0, 1, (int(5000 * u + 800), 2)).astype(np.float32)
    rad = np.abs(nrng.standard_cauchy(len(embers))).clip(0, 9).astype(np.float32) * 120 * u
    embers = embers / (np.linalg.norm(embers, axis=1, keepdims=True) + 1e-6) * rad[:, None]
    embers[:, 1] *= 0.82
    embers += np.array([hx, hy], np.float32)
    cv.splat(embers, np.array(P["ember"], np.float32), nrng.uniform(0.4, 2.6, len(embers)).astype(np.float32))

    # 3. Campuses as nuclei, each with electron orbits.
    for key, (lon, lat) in bases.items():
        x, y = cv.xy(lon, lat)
        col = colors[key]
        for j in range(3):
            rx, ry = (34 + 9 * j) * u, (13 + 3 * j) * u
            rot = rnd.uniform(0, math.pi)
            ang = np.linspace(0, 2 * np.pi, int(2 * np.pi * rx * 1.5), dtype=np.float32)
            ex, ey = rx * np.cos(ang), ry * np.sin(ang)
            pts = np.stack([x + ex * math.cos(rot) - ey * math.sin(rot), y + ex * math.sin(rot) + ey * math.cos(rot)], 1)
            cv.splat(pts, col * 0.7 + 0.3, 0.55)
            e = rnd.randrange(len(pts))
            cv.splat(pts[e:e + 1], np.array([1, 1, 1], np.float32), 30.0)
        cv.splat(np.array([[x, y]], np.float32), col * 0.5 + 0.5, 260.0)

    # Tone map: sharp light plus three glows, rolled off so crowded corridors go white-hot.
    L = cv.light
    hdr = L * 1.0 + blur(L, 2.2 * u) * 1.3 + blur(L, 9 * u) * 1.7 + blur(L, 38 * u) * 1.5 + blur(L, 120 * u) * 1.1
    bg = background(w, h, (hx, hy))
    img_lin = 1 - np.exp(-hdr * 0.95)
    rgb = bg + (1 - bg) * img_lin
    rgb = np.clip(rgb, 0, 1) ** (1 / 1.08)
    grain = nrng.normal(0, 0.012, (h, w, 1)).astype(np.float32)
    rgb = np.clip(rgb + grain, 0, 1)
    img = Image.fromarray((rgb * 255).astype(np.uint8), "RGB").convert("RGBA")

    # Basemap drawn faintly over the dark, under the labels.
    base = Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8), "RGB").convert("RGBA")
    draw_basemap(base, cv)
    mapmask = Image.fromarray(((np.clip(1 - img_lin.max(axis=2), 0, 1)) * 255).astype(np.uint8), "L")
    img = Image.composite(Image.blend(base, img, 0.5), img, mapmask)

    if P["halo"] != "bricks":
        return img, cv, {"bases": bases, "miles": total_miles, "legs": legs, "games": sum(len(i["legs"]) for i in itins.values())}
    # 4. Athens: a ring of Court Street bricks around Ohio's nucleus.
    ax, ay = cv.xy(*bases["ohio"])
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for ring, (r, bw, bh) in enumerate(((78, 22, 10), (92, 22, 10))):
        r, bw, bh = r * u, bw * u, bh * u
        n = int(2 * math.pi * r / (bw + 3 * u))
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * ring) / n
            cx, cy = ax + r * math.cos(a), ay + r * math.sin(a)
            ca, sa = math.cos(a + math.pi / 2), math.sin(a + math.pi / 2)
            hw, hh = bw / 2, bh / 2
            corners = [(cx + dx * ca - dy * sa, cy + dx * sa + dy * ca) for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
            shade = rnd.choice(((158, 59, 38), (140, 51, 34), (168, 69, 44), (127, 45, 29)))
            d.polygon(corners, fill=shade + (170,), outline=(240, 199, 94, 110))
    glow = layer.filter(ImageFilter.GaussianBlur(10 * u))
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, layer)
    return img, cv, {"bases": bases, "miles": total_miles, "legs": legs, "games": sum(len(i["legs"]) for i in itins.values())}


def font(path: str, size: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, max(8, int(size)))


def spaced(d: ImageDraw.ImageDraw, xy, text: str, f, fill, track: float, anchor_right: bool = False) -> None:
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + track * (len(text) - 1)
    x, y = xy
    if anchor_right:
        x -= total
    for ch, wd in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill)
        x += wd + track


def labels(img: Image.Image, cv: Canvas, meta: dict, caption: bool) -> Image.Image:
    u = cv.u
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # Town names: small gold italics beside each nucleus, no boxes.
    offsets = P["offsets"]
    for key, (lon, lat) in meta["bases"].items():
        if not TOWN.get(key):
            continue
        x, y = cv.xy(lon, lat)
        sx, sy = offsets.get(key, (1, -1))
        big = key == P["big"][0]
        f = font(SERIF_I, (46 if big else 30) * u)
        name = TOWN[key] + (P["big"][1] if big else "")
        tw = d.textlength(name, font=f)
        gap = (112 if big else 50) * u
        tx = x + gap * 0.75 if sx > 0 else x - gap * 0.75 - tw
        ty = y + (gap * 0.55 if sy > 0 else -gap * 0.55 - f.size)
        d.text((tx + 2 * u, ty + 2 * u), name, font=f, fill=(0, 0, 0, 150))
        d.text((tx, ty), name, font=f, fill=GOLD + (235 if big else 200,))
    if caption:
        k = font(SERIF_B, 30 * u)
        t = font(SERIF, 84 * u)
        s = font(SERIF_I, 34 * u)
        x0, y0 = 90 * u, cv.h - 300 * u
        spaced(d, (x0, y0), "HARDWOOD BRICKS", k, GOLD + (230,), 9 * u)
        d.text((x0, y0 + 46 * u), P["title"], font=t, fill=(255, 246, 230, 245))
        line = f"{SEASON_LABEL}  ·  {len(TEAMS)} schools  ·  {meta['miles']:,} miles on the road"
        d.text((x0, y0 + 150 * u), line, font=s, fill=(243, 230, 210, 210))
        spaced(d, (cv.w - 90 * u, cv.h - 120 * u), "HARDWOODBRICKS.COM", k, GOLD + (190,), 7 * u, anchor_right=True)
    return Image.alpha_composite(img, layer)


def main() -> None:
    out = Path("/mnt/project-files/art") if Path("/mnt/project-files").exists() else Path("art")
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{LEAGUE.key}-in-motion"
    art = TEMPLATES_DIR / "static" / "art"
    backdrop = "backdrop" if LEAGUE.key == "mac" else f"backdrop-{LEAGUE.key}"
    for name, (w, h, center, span) in P["frames"].items():
        img, cv, meta = render(w, h, center, span)
        img.convert("RGB").save(out / f"{stem}-{name}-bare.png", optimize=True)  # no text: site backdrop
        labels(img, cv, meta, caption=False).convert("RGB").save(out / f"{stem}-{name}-clean.png", optimize=True)
        labels(img, cv, meta, caption=True).convert("RGB").save(out / f"{stem}-{name}.png", optimize=True)
        bw = 1920 if name == "desktop" else 860
        img.convert("RGB").resize((bw, round(h * bw / w)), Image.LANCZOS).save(art / f"{backdrop}-{name}.jpg", quality=72, optimize=True)
        print(name, meta["games"], meta["legs"], meta["miles"])
    print(out)


if __name__ == "__main__":
    main()
