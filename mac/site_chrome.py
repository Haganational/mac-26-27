"""Site-wide chrome built after the pages render: team colors, section anchors,
the search index, share cards, the web app manifest and robots.txt.

Everything here reads the rendered site/ folder or static config, so the page
templates stay simple: a template only needs to include the shared header and
footer from templates/_layout.html.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

from .config import LEAGUE, SEASON_LABEL, SITE_NOINDEX, SITE_URL, TEAMS, Team

SITE_NAME = "Hardwood Bricks"
FLOOR = "parquet"  # home hero hardwood: parquet, light or dark
YOUTUBE_CHANNEL = "hardwoodbricks"  # where MidMaxx60 videos post (youtube.com/@hardwoodbricks, "Hardwood Bricks", from 2026-11-12)
YOUTUBE_CHANNEL_ID = "UCbh8k_bBCN7lUHmTmwyF7aQ"  # its Shorts playlist is "UUSH" + this id minus "UC"
TWITCH_CHANNEL = "juiceboxtv"  # kept for live streams; Home now leads with the YouTube Shorts player
# House banner ad. Placeholder until real sponsors: JuiceBox Nation, Matthew's own site.
TIP = {"venmo": "hardwoodbricks", "url": "https://venmo.com/u/hardwoodbricks",
       "line": "Hardwood Bricks is free and independent. Tips cover the data feeds, gas and arena trips."}
AD = {"name": "JuiceBox Nation", "url": "https://juiceboxnation.com/", "line": "Fresh takes, live streams and the JuiceBox crew.", "cta": "Visit juiceboxnation.com"}
BRAND = "#2a1a10"  # dark hickory: share cards, app icon and the phone address-bar tint (was green)
GOLD = "#f0c75e"
MORTAR = "#cdb99a"
BRICK_TONES = ("#9e3b26", "#8c3322", "#a8452c", "#93371f", "#b04d31", "#98402a", "#87301f", "#a33f27", "#7f2d1d")

# Pages in the order the top bar and footer list them. (path, label, one-line purpose, accent, search keywords)
PAGES: tuple[tuple[str, str, str, str, str], ...] = (
    ("index.html", f"{LEAGUE.short} home", "Tonight's games, teams, results, standings and against-the-spread records", "#2a78d6", "dashboard scores today tonight standings results"),
    ("midmaxx60.html", "MidMaxx60", "The day in 60 seconds: last night's results, tonight's slate, read-aloud script", "#b8862b", "today in the mac daily recap podcast script 60 seconds roundup last night tonight"),
    ("tv.html", "Schedule & TV", "This week's grid and every game: tip time, TV, lines, model, rest and travel", "#6250d6", "schedule tv watch network espn+ calendar tip time this week tonight games rest travel"),
    ("odds.html", "Odds", "Every book's spread, total and moneyline, best price, open vs now", "#1baf7a", "odds lines spread total moneyline books best price betting"),
    ("ratings.html", "Ratings", "Power ratings, projected spreads and totals, where the model disagrees with the market", "#eb6834", "model ratings kenpom efficiency projections edge backtest"),
    ("weekly.html", "BricksIt Weekly", "The week on one page: the lead story, the column, news and notes", "#a8441c", "bricksit weekly newsletter week in review column look ahead predictions notes"),
    ("power.html", "Bricks Index", "The weekly power rankings: recent form plus road wins, with a capsule on every team", "#a8322a", "power rankings weekly poll top bricks index road wins capsule column"),
    ("players.html", "Players", f"Box-score ratings for every {LEAGUE.short} player, tied to the team model", "#199e70", "players player ratings bpm box score impact leaderboard"),
    ("book.html", "Almanac", "Every D-I conference: team ratings and player ratings from every game", "#9e3b26", "almanac book conferences d-i college basketball power ratings players acc sec big ten big 12 big east"),
    ("notes.html", "Fieldhouse Notes", "Dispatches from the season, game by game", "#7a2e1e", "fieldhouse notes dispatches column blog writing game notes"),
    ("news.html", "News", "Men's basketball headlines from every school, plus the preseason picture", "#d03b3b", "news headlines ticker articles preseason poll previews all-mac"),
    ("viz.html", "Data Visualized", "Line movement for every game, and when each book posts, on a clock that runs to tip-off", "#c9962c", "data visualized charts clock posting time opener first line books when lines post line movement steam move"),
    ("travel.html", "Travel", "Routes, miles, road trips, rest days and time zones for every team", "#0f8fa8", "travel map miles rest road trip fatigue"),
)

_PAGE_FEATURE = {"midmaxx60.html": "midmaxx60", "notes.html": "notes", "book.html": "book"}
# Pages this league publishes: the MAC gets every page; other leagues skip the hand-built ones.
PAGES = tuple(p for p in PAGES if LEAGUE.has(_PAGE_FEATURE.get(p[0], "")) or p[0] not in _PAGE_FEATURE)


# ---------------------------------------------------------------- colors

def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def ink_on(bg: str) -> str:
    """White or near-black text, whichever reads better on the background."""
    return "#ffffff" if contrast(bg, "#ffffff") >= 3 else "#111111"


def accent_for(team: Team) -> str:
    """Second color that stands out on the primary (falls back to white)."""
    return team.color2 if contrast(team.color, team.color2) >= 2.2 else "#ffffff"


def teams_css(teams: Iterable[Team] = TEAMS) -> str:
    """One class per team (.t-akron ...) that sets --tc / --tc2 / --tci for any element."""
    lines = ["/* Generated by mac/site_chrome.py from mac/config.py team colors. */"]
    for t in teams:
        sel = f'.t-{t.key}, [data-team="{t.key}"], a.pill[href$="teams/{t.key}.html"]'
        lines.append(f"{sel} {{ --tc: {t.color}; --tc2: {accent_for(t)}; --tci: {ink_on(t.color)}; --tca: var(--tc); }}")
    return "\n".join(lines) + "\n"


def nav_teams() -> list[dict[str, Any]]:
    return [{"key": t.key, "abbr": t.abbr, "short": t.short, "name": t.name, "espn_id": t.espn_id,
             "color": t.color, "color2": accent_for(t), "ink": ink_on(t.color)} for t in TEAMS]


# ---------------------------------------------------------------- section anchors

def slug(text: str) -> str:
    """Same rule as slug() in static/nav.js: ascii, lowercase, dashes."""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:48].rstrip("-") or "section"


_TAG = re.compile(r"<[^>]+>")
_SECTION = re.compile(r"<section\b([^>]*)>", re.I)
_H2 = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.I | re.S)


def heading_text(inner_html: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub("", inner_html))).strip()


def anchor_sections(page: str) -> tuple[str, list[tuple[str, str]]]:
    """Give every <section> that has an <h2> a stable id, so any section has a link.

    Returns the new HTML and the (id, heading) list in page order. Existing ids win.
    """
    out, found, used, pos = [], [], set(re.findall(r'\bid="([^"]+)"', page)), 0
    for m in _SECTION.finditer(page):
        out.append(page[pos:m.start()])
        attrs = m.group(1)
        nxt = _SECTION.search(page, m.end())
        stop = nxt.start() if nxt else len(page)
        h2 = _H2.search(page, m.end(), stop)
        title = heading_text(h2.group(1)) if h2 else ""
        idm = re.search(r'\bid="([^"]+)"', attrs)
        if title and not idm:
            base = slug(title)
            sid, n = base, 2
            while sid in used:
                sid, n = f"{base}-{n}", n + 1
            used.add(sid)
            attrs = f' id="{sid}"' + attrs
            found.append((sid, title))
        elif title and idm:
            found.append((idm.group(1), title))
        out.append(f"<section{attrs}>")
        pos = m.end()
    out.append(page[pos:])
    return "".join(out), found


# ---------------------------------------------------------------- search index

def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def search_entry(kind: str, title: str, url: str, sub: str = "", key: str = "", extra: str = "") -> dict[str, str]:
    e = {"k": kind, "t": title, "u": url}
    if sub:
        e["s"] = sub
    if key:
        e["c"] = key
    hay = _fold(" ".join(x for x in (title, sub, extra) if x))
    if hay != _fold(title):
        e["h"] = hay
    return e


def build_search_index(sections: dict[str, list[tuple[str, str]]], games: list[dict[str, Any]],
                       have_box: set[str], profiles: dict[str, list[dict[str, Any]]],
                       coaches: dict[str, str], standings: dict[str, dict[str, Any]],
                       et_label) -> list[dict[str, str]]:
    """Everything a visitor might type: pages, page sections, teams, coaches, players, games."""
    idx: list[dict[str, str]] = []
    page_label = {p[0]: p[1] for p in PAGES}
    page_kw = {p[0]: p[4] for p in PAGES}
    for path, label, purpose, _, kw in PAGES:
        idx.append(search_entry("Page", label, path, purpose, extra=kw))
    for t in TEAMS:
        rec = standings.get(t.key, {})
        sub = f"{rec.get('w', 0)}-{rec.get('l', 0)}, {rec.get('cw', 0)}-{rec.get('cl', 0)} {LEAGUE.short}" if rec else ""
        if coaches.get(t.key):
            sub += f" · Coach {coaches[t.key]}"
        idx.append(search_entry("Team", t.name, f"teams/{t.key}.html", sub, t.key, f"{t.abbr} {t.short}"))
        if coaches.get(t.key):
            idx.append(search_entry("Coach", coaches[t.key], f"teams/{t.key}.html", f"{t.short} head coach", t.key))
        idx.append(search_entry("TV", f"{t.short} TV schedule", f"tv.html#{t.key}", "Every game, tip time and network", t.key, f"{t.abbr} watch"))
        idx.append(search_entry("Travel", f"{t.short} travel map", f"travel.html#{t.key}", "Route, miles and rest", t.key, t.abbr))
        idx.append(search_entry("News", f"{t.short} news", f"news.html#{t.key}", "Latest headlines", t.key, t.abbr))
    for path, secs in sections.items():
        team_key = path[6:-5] if path.startswith("teams/") else ""
        team = next((t for t in TEAMS if t.key == team_key), None)
        if path.startswith("games/"):
            continue  # games are listed below with a better title
        where = team.short if team else page_label.get(path, path)
        for sid, title in secs:
            idx.append(search_entry("Section", title, f"{path}#{sid}", where, team_key,
                                    (team.abbr if team else page_kw.get(path, ""))))
    for key, plist in profiles.items():
        team = next(t for t in TEAMS if t.key == key)
        for p in plist:
            bits = [team.short]
            if p.get("jersey"):
                bits.append(f"#{p['jersey']}")
            bits += [x for x in (p.get("position"), p.get("class_name")) if x]
            pg = (p.get("season") or {}).get("per_game") or {}
            if (p.get("season") or {}).get("gp"):
                bits.append(f"{pg.get('pts')} ppg")
            url = f"players/{slug(p['name'])}-{p['espn_id']}.html" if p.get("name") else f"teams/{key}.html#p{p['espn_id']}"
            idx.append(search_entry("Player", p["name"], url, " · ".join(bits), key,
                                    f"{team.abbr} {p.get('hometown') or ''} {p.get('previous_school') or ''}"))
    # Upcoming games first (soonest on top), then results (latest on top); the search keeps this order on ties.
    ordered = sorted((g for g in games if not g["completed"]), key=lambda g: g["date"]) + \
        sorted((g for g in games if g["completed"]), key=lambda g: g["date"], reverse=True)
    for g in ordered:
        h, a = g["home"], g["away"]
        mac_key = h.get("key") or a.get("key") or ""
        when = et_label(g)
        if g["completed"]:
            title = f"{a['abbr']} {a['score']}, {h['abbr']} {h['score']}"
            sub = f"Final · {when}"
        elif g.get("live"):
            title = f"{a['abbr']} {a['score'] or 0}, {h['abbr']} {h['score'] or 0}"
            sub = f"Live · {(g.get('detail') or '').replace(' - ', ' ')}"
        else:
            title = f"{a['abbr']} {'vs' if g.get('neutral_site') else 'at'} {h['abbr']}"
            sub = when
        url = f"games/{g['game_id']}.html" if g["game_id"] in have_box else f"tv.html#g{g['game_id']}"
        nets = " ".join(n["name"] for n in (g.get("watch") or {}).get("nets", []))
        if nets and not g["completed"]:
            sub += f" · {nets}"
        idx.append(search_entry("Game", title, url, sub, mac_key,
                                f"{a['name']} {h['name']} {g.get('venue') or ''} {g.get('venue_city') or ''} {nets}"))
    return idx


# ---------------------------------------------------------------- share images

# Athens Block on the share cards: paper, ink and rules, the same faces as the site.
FONT_DIR = Path(__file__).resolve().parent.parent / "templates" / "static" / "fonts"
PAPER, INK, INK2, MUTED, GRID, BRICK = "#f4efe4", "#1a1410", "#4a4038", "#857a6c", "#ddd3c2", "#9e3b26"
_FACES = {"serif": "Newsreader-SemiBold.ttf", "serif-reg": "Newsreader-Regular.ttf", "serif-it": "Newsreader-SemiBoldItalic.ttf",
          "cond": "BarlowCondensed-SemiBold.ttf", "cond-bold": "BarlowCondensed-Bold.ttf", "sans": "Barlow-Regular.ttf"}


def _font(size: int, bold: bool = True, face: str | None = None):
    """A house face from templates/static/fonts; DejaVu if the files are missing."""
    from PIL import ImageFont
    names = ([str(FONT_DIR / _FACES[face])] if face else []) + (
        ["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
        if bold else ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _fit(draw, text: str, max_w: int, size: int, bold: bool = True, face: str | None = None):
    while size > 18:
        f = _font(size, bold, face)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(size, bold, face)


def _spaced(draw, xy: tuple[float, float], text: str, font, fill: str, track: float = 0.12) -> float:
    """Letter-spaced caps, the way the site sets its labels. Returns the width drawn."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + font.size * track
    return x - xy[0]


def _spaced_len(draw, text: str, font, track: float = 0.12) -> float:
    return sum(draw.textlength(ch, font=font) + font.size * track for ch in text)


def _stripe(draw, y: int, h: int, w: int, x0: int = 0) -> None:
    n = len(TEAMS)
    for i, t in enumerate(TEAMS):
        draw.rectangle([x0 + i * (w - x0) // n, y, x0 + (i + 1) * (w - x0) // n, y + h], fill=t.color)


def _bricks(draw, x0: int, y0: int, x1: int, y1: int, brick: int = 44, course: int = 20, gap: int = 3) -> None:
    """Running-bond red brick with mortar joints, like the walks across a college green."""
    import random
    rnd = random.Random(7)
    draw.rectangle([x0, y0, x1, y1], fill=MORTAR)
    row = 0
    y = y0
    while y < y1:
        x = x0 - (brick // 2 if row % 2 else 0)
        while x < x1:
            draw.rectangle([max(x0, x + gap // 2), y + gap // 2, min(x1, x + brick - gap // 2 - 1), min(y1, y + course - gap // 2 - 1)],
                           fill=rnd.choice(BRICK_TONES))
            x += brick
        y += course
        row += 1


def _footer(d, W: int, H: int) -> None:
    """One course of brick and the team stripe along the foot, the site's address above them."""
    _bricks(d, 0, H - 40, W, H - 10, brick=56, course=15, gap=3)
    _stripe(d, H - 10, 10, W)
    url = SITE_URL.split("//", 1)[-1].rstrip("/").upper()
    f = _font(24, face="cond")
    _spaced(d, (W - 72 - _spaced_len(d, url, f), H - 84), url, f, MUTED)


def share_card(path: Path, title: str, subtitle: str, *, bg: str = BRAND, accent: str = GOLD,
               kicker: str = f"{SITE_NAME.upper()} · {LEAGUE.short} {SEASON_LABEL}", lines: Iterable[str] = ()) -> None:
    """1200x630 PNG for link previews (Open Graph / X cards / iMessage), set like a page of the paper.
    A team card (bg is the team color) runs that color down the left edge and in its kicker."""
    from PIL import Image, ImageDraw
    W, H = 1200, 630
    team = bg != BRAND
    tone = bg if team else BRICK
    if contrast(tone, PAPER) < 2.2:  # a pale team color would vanish on the paper
        tone = _mix(tone, INK, 0.55)
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    left = 72
    if team:
        d.rectangle([0, 0, 28, H - 40], fill=bg)
        left = 92
    d.rectangle([left, 52, W - 72, 59], fill=INK)  # heavy rule over the kicker, like a section head
    _spaced(d, (left, 80), kicker.upper(), _font(28, face="cond"), tone, 0.14)
    title_font = _fit(d, title, W - left - 72, 104, face="serif")
    d.text((left - 4, 126), title, font=title_font, fill=INK)
    y = 140 + title_font.size + 18
    sub_font = _font(36, False, face="serif-reg")
    for chunk in _wrap(d, subtitle, sub_font, W - left - 110)[:3]:
        d.text((left, y), chunk, font=sub_font, fill=INK2)
        y += 48
    ls = list(lines)[:3]
    if ls:
        y += 14
        d.line([left, y, W - 72, y], fill=GRID, width=2)
        y += 14
        for ln in ls:
            d.text((left, y), ln, font=_font(34, face="cond-bold"), fill=INK)
            y += 44
    _footer(d, W, H)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


def game_card(path: Path, g: dict[str, Any], colors: dict[str, str]) -> None:
    """Final score card, set like a box-score head: each side capped in its team color, the winner in full ink."""
    from PIL import Image, ImageDraw
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([72, 52, W - 72, 59], fill=INK)
    _spaced(d, (72, 76), f"FINAL · {g['date'][:10]}", _font(28, face="cond"), BRICK, 0.14)
    venue = (g.get("venue") or "")[:44].upper()
    vf = _font(24, face="cond")
    _spaced(d, (W - 72 - _spaced_len(d, venue, vf, 0.1), 80), venue, vf, MUTED, 0.1)
    col = (W - 144 - 48) // 2
    for i, side in enumerate((g["away"], g["home"])):
        x0 = 72 + i * (col + 48)
        tc = colors.get(side.get("key") or "", "#3a3f4a")
        won = (side["score"] or 0) > (g["home" if i == 0 else "away"]["score"] or 0)
        d.rectangle([x0, 132, x0 + col, 146], fill=tc)
        _spaced(d, (x0, 166), side["abbr"].upper(), _font(30, face="cond-bold"), INK2, 0.1)
        name = side["name"]
        d.text((x0, 204), name, font=_fit(d, name, col, 46, face="serif"), fill=INK)
        d.text((x0 - 6, 250), str(side["score"]), font=_font(230, face="cond-bold"), fill=INK if won else "#b9ad9a")
        d.line([x0, 520, x0 + col, 520], fill=INK, width=2)
    d.line([W // 2, 132, W // 2, 520], fill=GRID, width=2)
    _footer(d, W, H)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


def app_icon(path: Path, size: int) -> None:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (size, size), BRAND)
    d = ImageDraw.Draw(img)
    # Brick walk along the bottom third, the masthead's serif "HB" above: gold H, paper B, like the top bar.
    _bricks(d, 0, int(size * 0.68), size, size, brick=max(8, size // 5), course=max(4, size // 10), gap=max(1, size // 90))
    f = _font(int(size * 0.44), face="serif")
    w = d.textlength("HB", font=f)
    x = (size - w) / 2
    d.text((x, size * 0.1), "H", font=f, fill=GOLD)
    d.text((x + d.textlength("H", font=f), size * 0.1), "B", font=f, fill="#f6ecd8")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    out, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def _mix(a: str, b: str, t: float) -> str:
    pa = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    pb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def pillow_ok() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------- manifest, robots

def manifest() -> str:
    return json.dumps({
        "name": f"{SITE_NAME} · {LEAGUE.short} Men's Basketball {SEASON_LABEL}",
        "short_name": SITE_NAME,
        "description": f"Scores, lines, ratings, TV, travel and news for all {len(TEAMS)} {LEAGUE.short} teams.",
        "start_url": "./index.html",
        "scope": "./",
        "display": "standalone",
        "background_color": BRAND,
        "theme_color": BRAND,
        "icons": [
            {"src": "static/og/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "static/og/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }, indent=1)


def robots() -> str:
    if SITE_NOINDEX:
        return "User-agent: *\nDisallow: /\n"
    return f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n"


def news_sitemap(items: Iterable[tuple[str, str, str]], now: datetime, days: float = 2.0) -> str:
    """Google News sitemap: game recaps published in the last two days (Google reads no older)."""
    cut = now.astimezone(timezone.utc).timestamp() - days * 86400
    rows = []
    for path, title, pub in sorted(items, key=lambda x: x[2], reverse=True):
        try:
            ts = datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if ts < cut:
            continue
        rows.append(f"<url><loc>{html.escape(SITE_URL + path)}</loc><news:news><news:publication><news:name>{SITE_NAME}</news:name>"
                    f"<news:language>en</news:language></news:publication><news:publication_date>{html.escape(pub)}</news:publication_date>"
                    f"<news:title>{html.escape(title)}</news:title></news:news></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">' + "".join(rows[:1000]) + "</urlset>\n")


def sitemap(paths: Iterable[str]) -> str:
    # A folder's index.html is listed as the folder, matching its canonical link.
    urls = "".join(f"<url><loc>{html.escape(SITE_URL + (p[:-10] if p.endswith('index.html') else p))}</loc></url>" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'
