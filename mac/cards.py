"""Share cards: one image per recap, preview and Bricks Index capsule, made on every build.

Each card comes in two sizes from the same layout:
    static/og/<name>.png     1200x630, the link preview (og:image) and the Bluesky / Threads link card
    static/og/ig/<name>.png  1080x1350, a 4:5 portrait for Instagram and image posts on Threads

The look is the site's: a brick wall across the top with the wordmark, dark hickory in the
middle, a strip of hardwood floor along the bottom, team colors on the chips.

A card is described by a plain dict (see recap(), preview(), capsule(), ranking()) so the
drawing never needs to know where the numbers came from:
    kicker    "FINAL · MAC"            gold, top right of the wall
    date      "Sat, Nov 7"
    rows      [{"abbr", "name", "color", "right", "dim", "pre"}]  one row per team
    headline  the story's headline (serif)
    label     "TOP SCORER"             small gold caps over the stat
    stat      "Jane Doe, 24 points and 9 rebounds (Akron)"
"""
from __future__ import annotations

import functools
import random
import re
from pathlib import Path
from typing import Any, Iterable

from .config import SITE_URL
from .site_chrome import BRAND, BRICK_TONES, GOLD, MORTAR, SITE_NAME, _mix, _wrap, ink_on

IVORY = "#f6efe2"
MUTED = "#b9a58c"
SIZES = {"wide": (1200, 630), "tall": (1080, 1350)}
MAPLE = ("#c8914f", "#d29b58", "#bf8746", "#cf9a5c", "#c48d4d", "#d6a463")


def _font(size: int, *, serif: bool = False, bold: bool = True):
    from PIL import ImageFont
    if serif:
        names = (["DejaVuSerif-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", "LiberationSerif-Bold.ttf"] if bold else
                 ["DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"])
    else:
        names = (["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold
                 else ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _fit(d, text: str, max_w: float, size: int, floor: int = 18, **kw):
    while size > floor and d.textlength(text, font=_font(size, **kw)) > max_w:
        size -= 2
    return _font(size, **kw)


def _clip(d, text: str, font, max_w: float) -> str:
    if d.textlength(text, font=font) <= max_w:
        return text
    while text and d.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text.rstrip(" ,;·") + "…"


def _wall(img, y0: int, y1: int, brick: int, course: int) -> None:
    """Running-bond brick, toned down toward hickory so gold type reads over it."""
    from PIL import Image, ImageDraw
    W = img.width
    wall = Image.new("RGB", (W, y1 - y0), MORTAR)
    d = ImageDraw.Draw(wall)
    rnd, gap, row, y = random.Random(11), max(2, course // 7), 0, 0
    while y < y1 - y0:
        x = -(brick // 2 if row % 2 else 0)
        while x < W:
            d.rectangle([x + gap // 2, y + gap // 2, x + brick - gap, y + course - gap], fill=rnd.choice(BRICK_TONES))
            x += brick
        y += course
        row += 1
    img.paste(Image.blend(wall, Image.new("RGB", wall.size, BRAND), 0.42), (0, y0))


def _floor(img, y0: int) -> None:
    """Maple boards with a little grain: the court."""
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    W, H = img.size
    rnd, board = random.Random(5), max(14, (H - y0) // 5)
    y, row = y0, 0
    while y < H:
        x = -rnd.randint(0, 300)
        while x < W:
            ln = rnd.randint(260, 520)
            tone = rnd.choice(MAPLE)
            d.rectangle([x, y, x + ln - 2, y + board - 2], fill=tone)
            for _ in range(3):
                gy = y + rnd.randint(2, board - 4)
                d.line([x + 6, gy, x + ln - 8, gy + rnd.randint(-1, 1)], fill=_mix(tone, "#7a4f22", 0.25), width=1)
            x += ln
        d.line([0, y + board - 1, W, y + board - 1], fill="#8a5a2b", width=2)
        y += board
        row += 1
    d.rectangle([0, y0, W, y0 + 5], fill=GOLD)  # the sideline


@functools.lru_cache(maxsize=None)
def _base(size: str):
    """The empty card (wall, hickory, floor), drawn once per size per build."""
    from PIL import Image
    W, H = SIZES[size]
    tall = size == "tall"
    img = Image.new("RGB", (W, H), BRAND)
    _wall(img, 0, 150 if tall else 96, brick=int(64 * (1.1 if tall else 1)), course=int(26 * (1.2 if tall else 1)))
    _floor(img, H - (150 if tall else 64))
    return img


def draw(path: Path, card: dict[str, Any], size: str = "wide") -> Path:
    """Render one card. Returns the path written."""
    from PIL import Image, ImageDraw
    W, H = SIZES[size]
    tall = size == "tall"
    wall_h = 150 if tall else 96
    floor_h = 150 if tall else 64
    img = _base(size).copy()
    d = ImageDraw.Draw(img)
    pad = 56 if tall else 56

    # The wall: wordmark, kicker and date.
    word = SITE_NAME.upper()
    if tall:
        f = _font(64, serif=True)
        d.text(((W - d.textlength(word, font=f)) / 2, 22), word, font=f, fill=GOLD)
        k = " · ".join(x for x in (card.get("kicker"), card.get("date")) if x)
        fk = _fit(d, k, W - 2 * pad, 30)
        d.text(((W - d.textlength(k, font=fk)) / 2, 104), k, font=fk, fill=IVORY)
    else:
        f = _font(44, serif=True)
        d.text((pad, 24), word, font=f, fill=GOLD)
        k = " · ".join(x for x in (card.get("kicker"), card.get("date")) if x)
        fk = _fit(d, k, W - pad * 2 - d.textlength(word, font=f) - 40, 28)
        d.text((W - pad - d.textlength(k, font=fk), 34), k, font=fk, fill=IVORY)
    d.rectangle([0, wall_h, W, wall_h + 4], fill=GOLD)

    # Size everything first, so the tall card can sit its block in the middle of the space.
    rows = card.get("rows") or []
    floor_top = H - floor_h
    avail = floor_top - wall_h - 4
    area = (440 if tall else 220) if len(rows) <= 2 else (560 if tall else 300)
    rh = min(area // max(1, len(rows)), 210 if tall else 110) if rows else 0
    chip = int(rh * 0.82)
    stat, label = card.get("stat") or "", card.get("label") or ""
    fl, fs = _font(24 if tall else 19), _font(34 if tall else 25, bold=False)
    stat_lines = _wrap(d, stat, fs, W - 2 * pad) if stat else []
    if len(stat_lines) > (2 if tall else 1):
        stat_lines = stat_lines[:2 if tall else 1]
        stat_lines[-1] = _clip(d, stat_lines[-1] + " …", fs, W - 2 * pad)
    stat_h = ((fl.size + 10) if label and stat else 0) + len(stat_lines) * fs.size * 1.25
    gap_top = 44 if tall else 30
    rule_h = (56 if tall else 30)
    room = avail - gap_top - rh * len(rows) - rule_h - stat_h - (40 if tall else 26)
    head = card.get("headline") or ""
    max_lines = 3 if tall else 2
    for hs in ((66, 60, 54, 48, 42, 36) if tall else (46, 42, 38, 34, 30, 27)):
        fh = _font(hs, serif=True)
        lines = _wrap(d, head, fh, W - 2 * pad)
        if len(lines) <= max_lines and len(lines) * hs * 1.22 <= room:
            break
    max_lines = max(1, min(max_lines, int(room // (fh.size * 1.22))))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _clip(d, lines[-1] + " …", fh, W - 2 * pad)
    head_h = len(lines) * fh.size * 1.22
    if tall:
        block = rh * len(rows) + rule_h + head_h + (40 if stat_lines else 0) + stat_h
        top = wall_h + 4 + max(gap_top, (avail - block) / 2)
    else:
        top = wall_h + gap_top

    # Team rows.
    for i, r in enumerate(rows):
        y = top + i * rh
        x = pad
        if r.get("pre"):
            fp = _font(int(chip * 0.5))
            d.text((x, y + (chip - fp.size) / 2 - 4), r["pre"], font=fp, fill=GOLD)
            x += int(chip * 0.85)
        col = r.get("color") or "#3a3f4a"
        d.rounded_rectangle([x, y, x + int(chip * 1.35), y + chip], radius=max(4, chip // 12), fill=col,
                            outline=_mix(col, "#ffffff", 0.25), width=2)
        ab = r.get("abbr") or ""
        fa = _fit(d, ab, chip * 1.35 - 16, int(chip * 0.42))
        d.text((x + (chip * 1.35 - d.textlength(ab, font=fa)) / 2, y + (chip - fa.size) / 2 - 3), ab, font=fa,
               fill=ink_on(col))
        x += int(chip * 1.35) + (28 if tall else 24)
        right = str(r.get("right") if r.get("right") is not None else "")
        fr = _fit(d, right, W * (0.2 if len(rows) == 1 else 0.24), int(chip * (0.92 if len(rows) <= 2 else 0.6)))
        rw = d.textlength(right, font=fr)
        ink = MUTED if r.get("dim") else IVORY
        if right:
            d.text((W - pad - rw, y + (chip - fr.size) / 2 - fr.size * 0.12), right, font=fr, fill=ink)
        if i == 0 and card.get("right_label"):  # e.g. "MODEL", so a projection never reads as a final
            frl = _font(20 if tall else 15)
            lab = card["right_label"].upper()
            d.text((W - pad - d.textlength(lab, font=frl), y - frl.size - 6), lab, font=frl, fill=GOLD)
        name_w = W - pad - rw - 30 - x
        fn = _fit(d, r.get("name") or "", name_w, int(chip * (0.42 if len(rows) <= 2 else 0.5)), floor=16)
        sub = r.get("sub")
        ny = y + (chip - fn.size) / 2 - (fn.size * 0.45 if sub else 4)
        d.text((x, ny), _clip(d, r.get("name") or "", fn, name_w), font=fn, fill=ink)
        if sub:
            fsub = _font(max(16, int(fn.size * 0.55)), bold=False)
            d.text((x, ny + fn.size * 1.2), _clip(d, sub, fsub, name_w), font=fsub, fill=MUTED)

    # Headline, then the one stat.
    y = top + rh * len(rows) + rule_h * 0.4
    d.line([pad, y, W - pad, y], fill=_mix(BRAND, GOLD, 0.35), width=2)
    y += rule_h * 0.6
    for ln in lines:
        d.text((pad, y), ln, font=fh, fill=IVORY)
        y += fh.size * 1.22
    if stat_lines:
        sy = y + 40 if tall else floor_top - stat_h - 14
        if label:
            d.text((pad, sy), label.upper(), font=fl, fill=GOLD)
            sy += fl.size + 10
        for ln in stat_lines:
            d.text((pad, sy), ln, font=fs, fill=IVORY)
            sy += fs.size * 1.25

    # The address, on the floor.
    url = SITE_URL.split("//", 1)[-1].rstrip("/")
    fu = _font(34 if tall else 24)
    uy = H - floor_h / 2 - fu.size / 2 + 2
    tw = d.textlength(url, font=fu)
    ux = (W - tw) / 2 if tall else W - pad - tw
    d.rounded_rectangle([ux - 16, uy - 8, ux + tw + 16, uy + fu.size + 10], radius=6, fill=BRAND)
    d.text((ux, uy), url, font=fu, fill=GOLD)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, compress_level=6)  # optimize=True is 5x slower for 4% smaller files
    return path


def render(og_dir: Path, name: str, card: dict[str, Any]) -> None:
    """Both sizes: og_dir/<name>.png and og_dir/ig/<name>.png."""
    draw(og_dir / f"{name}.png", card, "wide")
    draw(og_dir / "ig" / f"{name}.png", card, "tall")


# ---------------------------------------------------------------- what goes on each card

def _day(iso: str) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
    except (ValueError, AttributeError):
        return ""
    return t.strftime("%a, %b %-d")


def _stat_bits(p: dict[str, Any]) -> str:
    bits = [f"{p['pts']} points"]
    for k, word, need in (("reb", "rebounds", 5), ("ast", "assists", 5), ("tpm", "3-pointers", 3), ("stl", "steals", 3), ("blk", "blocks", 3)):
        if (p.get(k) or 0) >= need and len(bits) < 3:
            bits.append(f"{p[k]} {word}")
    return ", ".join(bits)


def top_scorer(c: dict[str, Any], school=lambda n, k=None: n) -> str:
    """'Jane Doe, 24 points, 9 rebounds (Akron)': the game's leading scorer."""
    best = None
    for side in ("home", "away"):
        for p in c[side].get("players", []):
            if p.get("dnp") or p.get("pts") is None:
                continue
            if not best or (p["pts"], p.get("reb") or 0) > (best[0]["pts"], best[0].get("reb") or 0):
                best = (p, c[side])
    if not best:
        return ""
    p, side = best
    return f"{p['name']}, {_stat_bits(p)} ({school(side['name'], side.get('key'))})"


def recap(league_short: str, c: dict[str, Any], gm: dict[str, Any], colors: dict[str, str],
          school=lambda n, k=None: n) -> dict[str, Any]:
    g, home, away = c["g"], c["home"], c["away"]
    hs, as_ = home.get("score") or 0, away.get("score") or 0
    ot = (g.get("ot") or 0) or (c.get("box") or {}).get("ot")
    rows = [{"abbr": s.get("abbr"), "name": school(s["name"], s.get("key")), "right": s.get("score"),
             "color": colors.get(s.get("key") or "") or s.get("color") and "#" + str(s["color"]).lstrip("#") or None,
             "dim": (s is home and hs < as_) or (s is away and as_ < hs)} for s in (away, home)]
    return {"kicker": f"FINAL{' / OT' if ot else ''} · {league_short}", "date": _day(g.get("date", "")), "rows": rows,
            "headline": gm.get("headline", ""), "label": "Top scorer", "stat": top_scorer(c, school)}


def preview(league_short: str, g: dict[str, Any], story: dict[str, Any] | None, colors: dict[str, str],
            records: dict[str, str] | None = None, school=lambda n, k=None: n) -> dict[str, Any]:
    mv = g.get("mv") or {}
    et = g.get("et") or {}
    when = " ".join(x for x in (et.get("weekday"), et.get("md")) if x)
    tip = f"{et['time']} ET" if et.get("time") and not et.get("tba") else ""
    nets = ", ".join(n.get("name", "") for n in ((g.get("watch") or {}).get("nets") or []) if n.get("name"))
    rows = []
    for s, pts in ((g["away"], mv.get("away_pts")), (g["home"], mv.get("home_pts"))):
        rows.append({"abbr": s.get("abbr"), "name": school(s["name"], s.get("key")),
                     "sub": (records or {}).get(s.get("key") or "", ""), "right": pts if pts is not None else "",
                     "color": colors.get(s.get("key") or "") or (("#" + str(s["color"]).lstrip("#")) if s.get("color") else None)})
    stat = " · ".join(x for x in (tip, nets, g.get("venue") or "") if x)
    return {"kicker": f"PREVIEW · {league_short}", "date": when, "rows": rows, "right_label": "Model projection" if mv else "",
            "headline": (story or {}).get("headline") or f"{rows[0]['name']} at {rows[1]['name']}",
            "label": "Tip and TV" if tip or nets else "Where", "stat": stat}


def first_sentence(text: str, most: int = 220) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()
    m = re.match(r"(.{30,}?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    return s if len(s) <= most else s[:most].rsplit(" ", 1)[0] + "…"


def _move(t: dict[str, Any]) -> str:
    p = t.get("prev_rank")
    if not p or p == t["rank"]:
        return "" if not p else "No change"
    return f"Up {p - t['rank']}" if p > t["rank"] else f"Down {t['rank'] - p}"


def _wk(week: str) -> str:
    return f"{int(week[5:7])}/{int(week[8:10])}"


def capsule(league_short: str, week: str, t: dict[str, Any], text: str, team: Any | None) -> dict[str, Any]:
    """One team's Bricks Index capsule."""
    sub = " · ".join(x for x in (f"{t.get('record', '')} overall", f"{t.get('conf_record', '')} {league_short}", _move(t)) if x)
    row = {"pre": f"{t['rank']}", "abbr": getattr(team, "abbr", "") or t["short"][:4].upper(), "name": t["short"], "sub": sub,
           "right": f"{t['score']:+.1f}", "color": getattr(team, "color", None)}
    return {"kicker": f"BRICKS INDEX · {league_short}", "date": f"Week of {_wk(week)}", "rows": [row],
            "headline": first_sentence(text), "label": "Recent form + road wins",
            "stat": f"Form {t.get('form', 0):+.1f} + road wins {t.get('road', 0):+.1f} = {t['score']:+.1f} points a game"}


def ranking(league_short: str, week: str, teams: list[dict[str, Any]], by_key: dict[str, Any], most: int = 5) -> dict[str, Any]:
    """The conference's top of the week, for the power page's own link preview."""
    rows = []
    for t in teams[:most]:
        tm = by_key.get(t["key"])
        rows.append({"pre": str(t["rank"]), "abbr": getattr(tm, "abbr", "") or t["short"][:4].upper(), "name": t["short"],
                     "right": f"{t['score']:+.1f}", "color": getattr(tm, "color", None)})
    return {"kicker": f"BRICKS INDEX · {league_short}", "date": f"Week of {_wk(week)}", "rows": rows,
            "headline": f"{league_short} power rankings, week of {_wk(week)}", "label": "", "stat": ""}


def records(standings: dict[str, dict[str, Any]], short: str) -> dict[str, str]:
    return {k: f"{r.get('w', 0)}-{r.get('l', 0)}, {r.get('cw', 0)}-{r.get('cl', 0)} {short}" for k, r in standings.items()}

