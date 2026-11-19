"""The site root: hardwoodbricks.com/, a front door for every conference we cover.

Each edition builds its own pages and data.json. This page reads those data.json files
(whatever editions exist in site/), shows tonight's games and the latest finals for each
conference, and links every edition's front page. It also writes the root robots.txt,
which is the only robots.txt search engines read, listing every edition's sitemap.

    python -m mac.collect hub     # rebuild just this page, after the editions
"""
from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from . import frontscore, weekly
from .config import LEAGUES, SEASON_LABEL, SHARED_DIR, SITE_BASE, SITE_NOINDEX, SITE_ROOT, TEMPLATES_DIR


ET = ZoneInfo("America/New_York")


def front_page(lg: Any) -> str:
    """An edition's front page, from the site root."""
    return lg.path + "index.html" if lg.path else "mac/index.html"


def game_owner(*espn_ids: str) -> Any:
    """The one edition whose page is canonical for a game: the first in LEAGUES order with a team in it.
    A Horizon team at a MAC team gets a page in both editions; Google should index one."""
    ids = {str(i) for i in espn_ids if i}
    for lg in LEAGUES.values():
        if any(t.espn_id in ids for t in lg.teams):
            return lg
    return None


def _school(side: dict[str, Any]) -> str:
    from .today import school
    for lg in LEAGUES.values():
        for t in lg.teams:
            if t.espn_id == str(side.get("espn_id") or ""):
                return t.short
    return school(side.get("name") or "") or side.get("abbr") or ""


def _game(g: dict[str, Any], site_root: Path, prefix: str) -> dict[str, Any]:
    owner = game_owner(g["home"].get("espn_id"), g["away"].get("espn_id"))
    if owner is not None and owner.path != prefix and (site_root / owner.path / "games" / f"{g['game_id']}.html").exists():
        prefix = owner.path  # link the copy Google indexes
    box = (site_root / prefix / "games" / f"{g['game_id']}.html").exists()
    et = g.get("et") or {}
    return {
        "away": g["away"].get("abbr") or g["away"].get("name"), "home": g["home"].get("abbr") or g["home"].get("name"),
        "away_score": g["away"].get("score"), "home_score": g["home"].get("score"),
        "away_win": bool(g["away"].get("winner")), "home_win": bool(g["home"].get("winner")),
        "when": " ".join(x for x in (et.get("weekday"), et.get("time")) if x),
        "tv": ", ".join(b["name"] for b in (g.get("broadcasts") or [])[:1]),
        "live": bool(g.get("live")),
        "game_id": g.get("game_id"), "date": g.get("date") or "",
        "away_name": _school(g["away"]), "home_name": _school(g["home"]),
        "day": et.get("day_label") or "",
        "href": prefix + f"games/{g['game_id']}.html" if box else prefix + f"tv.html#g{g['game_id']}",
        "completed": bool(g.get("completed")), "detail": (g.get("detail") or "").replace(" - ", " "),
        "day_key": _day_key(g), "keys": [k for k in (g["home"].get("key"), g["away"].get("key")) if k],
    }


def _day_key(g: dict[str, Any]) -> str:
    """The game's date in Eastern time, YYYY-MM-DD."""
    k = (g.get("et") or {}).get("day_key")
    if k:
        return k
    try:
        return datetime.fromisoformat((g.get("date") or "").replace("Z", "+00:00")).astimezone(ET).date().isoformat()
    except ValueError:
        return ""


def edition(lg: Any, site_root: Path) -> dict[str, Any] | None:
    folder = site_root / lg.path if lg.path else site_root
    f = folder / "data.json"
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text())
    except ValueError:
        return None
    prefix = lg.path
    upcoming = [g for g in (d.get("tonight") or d.get("upcoming", [])) if not g.get("completed")]
    if not upcoming:
        upcoming = [g for g in d.get("upcoming", []) if not g.get("completed")][:4]
    finals = [g for g in d.get("recent", []) if g.get("completed")][:4]
    # Every game of the last day or so, finished or not, for the game-night scoreboard (game_night below).
    seen: set[str] = set()
    night = [g for g in (d.get("tonight") or []) + (d.get("recent") or [])[:30]
             if g.get("game_id") and not (g["game_id"] in seen or seen.add(g["game_id"]))]
    return {
        "key": lg.key, "short": lg.short, "name": lg.name, "region": lg.region,
        "href": front_page(lg), "prefix": prefix, "weekly": bool(weekly.issues(lg.key)), "n_teams": len(lg.teams),
        "tonight": [_game(g, site_root, prefix) for g in upcoming[:6]],
        "upcoming_all": [_game(g, site_root, prefix) for g in upcoming[:12]],
        "finals": [_game(g, site_root, prefix) for g in finals],
        "night": [_game(g, site_root, prefix) for g in night],
        "teams": [{"key": t.key, "short": t.short, "href": prefix + f"teams/{t.key}.html"} for t in lg.teams],
        "updated": d.get("generated_et") or "",
    }


# One accent per conference, used for its tag on the front page. Muted so they sit with the hickory and brick.
CONF_COLORS = {"mac": "#a8441c", "asun": "#2e7258", "horizon": "#3d5a80", "mw": "#7b5b8f", "metro": "#7a2e3a", "bigwest": "#b0772a", "mvc": "#5c6b2e", "a10": "#4a4f8a", "pac12": "#2f5d62", "wcc": "#8a5a3c", "american": "#356b8c", "sunbelt": "#9a4f6b", "ivy": "#3b4f2a", "caa": "#1f7a7a", "cusa": "#8a2f3c", "socon": "#4f5f8a", "bigsky": "#2f5f8a", "southland": "#5f6b2f", "summit": "#3a7a55", "uac": "#a0522d", "bigsouth": "#b5523a", "ovc": "#3a6f9a", "americaeast": "#7a3b34", "patriot": "#2f4470", "nec": "#2f6a8a", "meac": "#8a4a6a", "swac": "#8a3a3a"}


def _age(when: datetime, now: datetime) -> str:
    mins = max(0, int((now - when).total_seconds() // 60))
    if mins < 60:
        return f"{max(mins, 1)}m ago"
    if mins < 60 * 24:
        return f"{mins // 60}h ago"
    days = mins // (60 * 24)
    return "yesterday" if days == 1 else f"{days} days ago"


def _rel(url: str, base: str) -> str:
    return url[len(base):] if url.startswith(base) else url


_CLIP = re.compile(r'<figure class="hl-video">\s*<div class="hl-frame"><iframe src="([^"]+)"')


BLOWOUT = 30  # points


def _margin(title: str) -> int:
    """The winning margin in a recap headline like "Akron rolled past Toledo 90-70" (0 when there is no score)."""
    m = re.search(r"(\d+)-(\d+)\s*$", title.strip())
    return abs(int(m.group(1)) - int(m.group(2))) if m else 0


def front_stories(site_root: Path, now: datetime, base: str = SITE_BASE) -> list[dict[str, Any]]:
    """Our own recaps and previews, newest first, across every edition: headline, dek, card image, age.
    Read from each edition's news sitemap (the same list the social poster uses), so only canonical pages."""
    from .social import _meta, stories
    keys = {lg.short: lg.key for lg in LEAGUES.values()}
    seen, out = set(), []
    for it in stories(site_root):
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        try:
            when = datetime.fromisoformat(it["published"].replace("Z", "+00:00"))
        except ValueError:
            continue
        img = _rel(_meta(it["page"], "og:image"), base)
        key = keys.get(it["league"], "mac")
        html = it["page"].read_text() if it["page"] and it["page"].exists() else ""
        clip = _CLIP.search(html)
        out.append({"href": _rel(it["url"], base), "title": it["title"], "kind": it["kind"],
                    "dek": _meta(it["page"], "og:description"),
                    "video": 'class="hl-video"' in html,
                    "image": img if img and "/game-" in img else "",
                    # A real photo (a Fieldhouse Notes picture on the game page) or the ESPN highlight, for the lead.
                    "photo": img if img and "/game-" not in img and "/static/og/" not in img and not img.startswith("static/og/") else "",
                    "clip": clip.group(1).replace("&amp;", "&") if clip else "",
                    "league": it["league"], "key": key, "color": CONF_COLORS.get(key, "#a8441c"),
                    "when": when, "age": _age(when, now)})
    out.sort(key=lambda s: s["when"], reverse=True)
    return out


def _close_first(recaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The old order, for when the scorer can't load: the closer games among the newest recaps first."""
    close = [x for x in recaps[:16] if _margin(x["title"]) < BLOWOUT]
    return close + [x for x in recaps if x not in close]


def _scorer() -> frontscore.Scorer | None:
    try:
        return frontscore.Scorer()
    except Exception as e:  # the cover must build even if a data file is bad
        print("frontscore: skipped,", repr(e))
        return None


def _when(iso: str, today: str) -> str:
    from .cards import parse_iso
    t = parse_iso(iso).astimezone(ET)
    day = "Today" if t.date().isoformat() == today else t.strftime("%a")
    return f"{day} {t.strftime('%-I:%M %p')} ET"


def home_desk(scorer: frontscore.Scorer, today: str, site_root: Path) -> list[dict[str, Any]]:
    """The cover's MAC and Horizon box: Ohio pinned first, then Akron, Kent State and Cleveland State,
    each with its latest result (last three days) and next game."""
    out = []
    for row in frontscore.home_desk(scorer, today):
        tl = next(((t, lg) for lg in LEAGUES.values() for t in lg.teams if t.key == row["key"]), None)
        if not tl:
            continue
        t, lg = tl
        item = {"key": t.key, "short": t.short, "league": lg.short, "color": CONF_COLORS.get(lg.key, "#a8441c"),
                "href": f"{lg.path}teams/{t.key}.html", "pin": t.key in frontscore.TOP3, "last": "", "last_href": "", "next": ""}
        g = row["last"]
        if g:
            us, them = (g["home"], g["away"]) if g["home"].get("key") == t.key else (g["away"], g["home"])
            won = (us.get("score") or 0) > (them.get("score") or 0)
            where = "vs." if g["home"] is us or g.get("neutral_site") else "at"
            ot = " (OT)" if "OT" in (g.get("detail") or "") else ""
            item["last"] = f"{'W' if won else 'L'} {us.get('score')}-{them.get('score')}{ot} {where} {frontscore._name(them)}"
            owner = game_owner(g["home"].get("espn_id"), g["away"].get("espn_id")) or lg
            if (site_root / owner.path / "games" / f"{g['game_id']}.html").exists():
                item["last_href"] = f"{owner.path}games/{g['game_id']}.html"
        g = row["next"]
        if g:
            them = g["away"] if g["home"].get("key") == t.key else g["home"]
            where = "vs." if g["home"].get("key") == t.key or g.get("neutral_site") else "at"
            tv = ", ".join(b["name"] for b in (g.get("broadcasts") or [])[:1])
            item["next"] = f"{where} {frontscore._name(them)} · {_when(g['date'], today)}{' · ' + tv if tv else ''}"
        if item["last"] or item["next"]:
            out.append(item)
    return out


def edition_tops(ranked: list[dict[str, Any]], eds: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Each edition's best-ranked recap, for its tile in the conference index."""
    out: dict[str, dict[str, Any]] = {}
    for x in ranked:
        out.setdefault(x["key"], x)
    return out


def front_dispatches(site_root: Path, most: int = 3) -> list[dict[str, Any]]:
    """The newest Fieldhouse Notes from every edition, for the front page."""
    from . import notes
    eds = {lg.key: lg for lg in LEAGUES.values()}
    out = []
    if not notes.NOTES_DIR.exists():
        return out
    for path in notes.NOTES_DIR.glob("*.md"):
        if path.name.lower() == "readme.md":
            continue
        meta, body = notes.parse(path.read_text(encoding="utf-8"))
        if meta.get("draft", "").lower() in ("true", "yes", "1"):
            continue
        lg = eds.get((meta.get("league") or "mac").lower())
        if lg is None or not (site_root / lg.path / "notes.html").exists():
            continue
        text = re.sub(r"\s+", " ", re.sub(r"[*_>#\[\]]|\(https?://[^)]*\)", "", body)).strip()
        photos = notes.photos_of(meta, "")
        if not (text or photos):
            continue
        out.append({"title": meta.get("title") or "From the fieldhouse", "text": text,
                    "kind": notes.kind_of(meta.get("kind") or meta.get("icon")),
                    "published": notes._published(meta, path.stem), "date": meta.get("date") or path.stem[:10],
                    "href": f"{lg.path}notes.html#n-{path.stem}", "league": lg.short,
                    "photo": (lg.path + photos[0]["src"]) if photos else ""})
    out.sort(key=lambda d: d["published"], reverse=True)
    for d in out:
        d["kind_label"] = notes.KINDS[d["kind"]][0]
        try:
            d["date_label"] = datetime.fromisoformat(d["date"]).strftime("%b %-d")
        except ValueError:
            d["date_label"] = d["date"]
    return out[:most]


def tonight_across(eds: list[dict[str, Any]], most: int = 10) -> list[dict[str, Any]]:
    """Every edition's next games in one list, soonest first, each game once."""
    seen, out = set(), []
    for e in eds:
        for g in e["upcoming_all"]:
            if g["game_id"] in seen:
                continue
            seen.add(g["game_id"])
            out.append({**g, "league": e["short"], "color": CONF_COLORS.get(e["key"], "#a8441c")})
    out.sort(key=lambda g: (not g["live"], g["date"] or ""))
    return out[:most]


GAME_NIGHT_FROM = 12  # noon ET: from here on, today's slate takes the main column over last night's finals
NIGHT_ENDS = 6  # before 6 AM ET the night is still yesterday's (late West Coast tips)
SLATE_SHOWN = 12  # tiles before "All N games"


def game_night(eds: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """Tonight's games across every edition, for the cover's main column on game nights (Matthew, Nov 18 2026:
    "we shouldn't have yesterday's scores up during game nights on main").

    On from noon ET when today has games, and any other hour while a game is live; after the last
    late game ends (or by 6 AM ET) it steps aside and the night's finals lead again. Live games first,
    then the ones still to tip, soonest first, then tonight's finals, newest first; Ohio, Akron, Kent
    State and Cleveland State, then the MAC and the Horizon, go first within each group."""
    et = now.astimezone(ET)
    day = (et - timedelta(hours=NIGHT_ENDS)).date().isoformat()
    seen, games = set(), []
    for e in eds:
        for g in e.get("night", []):
            if g["day_key"] != day or g["game_id"] in seen:
                continue
            seen.add(g["game_id"])
            games.append({**g, "league": e["short"], "color": CONF_COLORS.get(e["key"], "#a8441c")})
    if not games:
        return None
    live = [g for g in games if g["live"]]
    if not live and not (GAME_NIGHT_FROM <= et.hour and et.date().isoformat() == day):
        return None

    def weight(g: dict[str, Any]) -> int:
        w = max([frontscore.HOME_TEAM.get(k, 0) for k in g["keys"]] + [0])
        lg = [lg.key for k in g["keys"] for lg in LEAGUES.values() if any(t.key == k for t in lg.teams)]
        return w + max([frontscore.HOME_CONF.get(k, 0) for k in lg] + [0])

    upcoming = sorted((g for g in games if not g["live"] and not g["completed"]), key=lambda g: (-weight(g), g["date"]))
    finals = sorted((g for g in games if g["completed"]), key=lambda g: g["date"], reverse=True)
    finals.sort(key=lambda g: -weight(g))
    order = sorted(live, key=lambda g: (-weight(g), g["date"])) + upcoming + finals
    return {"games": order[:SLATE_SHOWN], "more": order[SLATE_SHOWN:], "n": len(order), "live": len(live),
            "left": len(upcoming), "finals": len(finals), "label": datetime.fromisoformat(day).strftime("%A, %B %-d")}


def robots(base: str = SITE_BASE, noindex: bool = SITE_NOINDEX) -> str:
    if noindex:
        return "User-agent: *\nDisallow: /\n"
    maps = "".join(f"Sitemap: {base}{lg.path}{m}\n" for lg in LEAGUES.values() for m in ("sitemap.xml", "news-sitemap.xml"))
    return f"User-agent: *\nAllow: /\n{maps}"


def load_masthead() -> dict[str, Any]:
    p = SHARED_DIR / "masthead.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def staff(mh: dict[str, Any]) -> list[dict[str, Any]]:
    people = [dict(p) for p in mh.get("staff") or []] or (
        [{"name": mh["editor"], "title": mh.get("editor_title") or "Editor"}] if mh.get("editor") else [])
    for p in people:
        p["slug"] = _slug(p["name"])
    return people


def desks(mh: dict[str, Any], eds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per conference: its editor, or the editor in chief as acting editor until one is named."""
    named = mh.get("conference_editors") or {}
    out = []
    for e in eds:
        who = (named.get(e["key"]) or "").strip()
        out.append({"key": e["key"], "name": e["name"], "short": e.get("short") or e["name"], "href": e["href"], "editor": who or mh.get("editor", ""), "acting": not who})
    return out


def org_ld(mh: dict[str, Any], base: str = SITE_BASE) -> dict[str, Any]:
    """The NewsMediaOrganization, with the masthead and policy pages Google looks for."""
    m = base + "masthead.html"
    o: dict[str, Any] = {
        "@type": "NewsMediaOrganization", "@id": base + "#org", "name": "Hardwood Bricks", "url": base,
        "logo": {"@type": "ImageObject", "url": base + "static/og/icon-512.png"},
        "sameAs": ["https://www.youtube.com/@hardwoodbricks", "https://www.threads.com/@hardwoodbricks",
                   "https://www.instagram.com/hardwoodbricks/", "https://bsky.app/profile/hardwoodbricks.bsky.social",
                   "https://www.facebook.com/1388249761045376"] + ([f"https://x.com/{mh['x_handle']}"] if mh.get("x_handle") else []),
        "masthead": m, "publishingPrinciples": m + "#standards", "correctionsPolicy": m + "#corrections",
        "ethicsPolicy": m + "#ethics", "actionableFeedbackPolicy": m + "#contact",
    }
    if mh.get("editor"):
        o["founder"] = {"@type": "Person", "name": mh["editor"], "url": m + "#" + _slug(mh["editor"])}
    if mh.get("email"):
        o["email"] = mh["email"]
    if mh.get("based"):
        o["location"] = mh["based"]
    return o


def json_ld(eds: list[dict[str, Any]], base: str = SITE_BASE, mh: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": base + "#site", "name": "Hardwood Bricks", "url": base, "publisher": {"@id": base + "#org"}},
        org_ld(mh if mh is not None else load_masthead(), base),
        {"@type": "ItemList", "name": "Conferences", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": f"{e['name']} men's basketball", "url": base + e["href"].removesuffix("index.html")}
            for i, e in enumerate(eds)]},
    ]}


PRIVACY_UPDATED = "November 14, 2026"


def nobreak(text: str) -> Markup:
    """Keep a score ("73-71") on one line: big headlines were breaking it at the hyphen."""
    return Markup(re.sub(r"(\d+-\d+)", r'<span class="nw">\1</span>', str(escape(text))))


def build(site_root: Path | None = None, base: str = SITE_BASE) -> Path:
    site_root = site_root or SITE_ROOT
    eds = [e for lg in LEAGUES.values() if (e := edition(lg, site_root))]
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    names = ", ".join(e["short"] for e in eds[:-1]) + (f" and {eds[-1]['short']}" if len(eds) > 1 else (eds[0]["short"] if eds else ""))
    # Counts for page titles and the dateline: a list of every conference's name stops reading well past a handful.
    env.filters["nobreak"] = nobreak
    env.globals.update(n_conf=len(eds), n_schools=sum(len(LEAGUES[e["key"]].teams) for e in eds if e["key"] in LEAGUES))
    now = datetime.now(timezone.utc)
    sts = front_stories(site_root, now, base)
    recaps = [x for x in sts if x["kind"] == "recap"]
    # The Bricks Score orders the night's finals (mac.frontscore): upset, stakes, drama and the home weights
    # (Ohio first, then Akron, Kent State and Cleveland State, the MAC, the Horizon). Recaps it can't score,
    # and a 30-point rout among the newest when nothing else is there, fall back to newest first.
    scorer = _scorer()
    ranked = frontscore.rank(recaps, scorer) if scorer else _close_first(recaps)
    lead = next((x for x in ranked[:3] if x["image"] or x["photo"]), ranked[0] if ranked else (sts[0] if sts else None))
    rest = [x for x in ranked if x is not lead]
    cards = [x for x in rest if x["image"]][:4]
    today_et = now.astimezone(ET).date().isoformat()
    home = home_desk(scorer, today_et, site_root) if scorer else []
    tops = edition_tops(ranked, eds)
    mh = load_masthead()
    editor = (staff(mh) or [{}])[0]
    for e in eds:
        e["color"] = CONF_COLORS.get(e["key"], "#a8441c")
    den_data(site_root, now)  # site/den/*.json first, so the page and the front-page line read tonight's games
    den = den_page(env, site_root, eds, names, base, now)
    night = game_night(eds, now)
    if night:  # game night: tonight's games take the main column; last night's recaps move to the rail
        lead, cards = None, []
    html = env.get_template("hub.html").render(den=den, weave=weave_billing(now), night=night,
        eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX,
        lead=lead, cards=cards, river=[x for x in recaps if x is not lead and x not in cards][:8], home=home, tops=tops,
        tonight=tonight_across(eds), dispatches=front_dispatches(site_root), editor=editor,
        today=now.astimezone(ET).strftime("%A, %B %-d, %Y"),
        ld_json=json.dumps(json_ld(eds, base)).replace("</", "<\\/"),
        built=datetime.now(timezone.utc).isoformat(timespec="minutes"))
    site_root.mkdir(parents=True, exist_ok=True)
    (site_root / "index.html").write_text(html)
    (site_root / "robots.txt").write_text(robots(base))
    ppl = staff(mh)
    ld = {"@context": "https://schema.org", "@graph": [org_ld(mh, base)] + [
        {"@type": "Person", "@id": f"{base}masthead.html#{p['slug']}", "name": p["name"], "jobTitle": p.get("title", ""),
         "worksFor": {"@id": base + "#org"}, **({"description": p["bio"]} if p.get("bio") else {})} for p in ppl]}
    (site_root / "masthead.html").write_text(env.get_template("masthead.html").render(
        eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX, mh=mh, staff=ppl, desks=desks(mh, eds),
        ld_json=json.dumps(ld).replace("</", "<\\/")))
    from . import atlarge
    al = atlarge.page_context()
    if al:
        (site_root / "at-large.html").write_text(env.get_template("atlarge.html").render(
            eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX,
            built=datetime.now(timezone.utc).isoformat(timespec="minutes"), **al))
    from . import watch
    (site_root / "watch.html").write_text(env.get_template("watch.html").render(
        eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX,
        today=now.astimezone(ET).strftime("%A, %B %-d, %Y"),
        built=datetime.now(timezone.utc).isoformat(timespec="minutes"), **watch.page_context(now)))
    watch.build_profiles(env, site_root, eds=eds, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX,
                         built=datetime.now(timezone.utc).isoformat(timespec="minutes"))
    media = mh.get("media") or {}
    has_notes = {lg.key for lg in LEAGUES.values() if lg.has("notes")}
    mld = {"@context": "https://schema.org", "@graph": [org_ld(mh, base), {
        "@type": "WebPage", "@id": base + "media.html", "url": base + "media.html", "name": "Media and credentials",
        "about": {"@id": base + "#org"}, "isPartOf": {"@id": base + "#site"}}]}
    (site_root / "media.html").write_text(env.get_template("media.html").render(
        eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX, mh=mh, media=media, editor=editor,
        notes_eds=[e for e in eds if e["key"] in has_notes], samples=media_samples(media, sts),
        ld_json=json.dumps(mld).replace("</", "<\\/")))
    # Privacy policy: the Google OAuth consent screen for the YouTube uploader links here.
    (site_root / "privacy.html").write_text(env.get_template("privacy.html").render(
        eds=eds, base=base, noindex=SITE_NOINDEX, mh=mh, updated=PRIVACY_UPDATED))
    return site_root / "index.html"


def weave_billing(now: datetime, path: Path | None = None) -> dict[str, Any] | None:
    """MIDnight Weave on the front page (Matthew, Nov 16 2026): a published show gets top billing until
    11:59 AM ET the day after it aired. data/weave.json lists the shows; the newest one still in its window wins.
    "until" goes on the page too, so a copy built before noon hides the band once the window closes."""
    f = path or SHARED_DIR / "weave.json"
    try:
        shows = json.loads(f.read_text()).get("shows") or []
    except (OSError, ValueError):
        return None
    for s in shows:
        if not s.get("youtube") or not s.get("aired"):
            continue
        aired = datetime.fromisoformat(s["aired"]).date()
        until = datetime.combine(aired + timedelta(days=1), time(11, 59), tzinfo=ET)
        if now.astimezone(ET).date() >= aired and now < until:
            return {**s, "until": until.isoformat(), "until_ms": int(until.timestamp() * 1000)}
    return None


def den_teaser(site_root: Path, now: datetime) -> dict[str, Any] | None:
    """Tonight's line for the front page, from the Den's own slate file (None on a day with no slate)."""
    f = site_root / "den" / f"slate-{now.astimezone(ET):%Y-%m-%d}.json"
    try:
        games = json.loads(f.read_text()).get("games") or []
    except (OSError, ValueError, AttributeError):
        return None
    ours = {str(s["id"]) for g in games for s in (g.get("home") or {}, g.get("away") or {}) if s.get("edition") and s.get("id")}
    return {"games": len(games), "eligible": len(ours)} if games else None


def den_data(site_root: Path, now: datetime) -> None:
    """The Den's games (site/den/*.json via mac.den), then tonight's anchors, desk and partner links (mac.den_connect).
    Each step is fenced: a Den failure prints a line and never takes the front page down."""
    from . import den, den_connect
    try:
        den.build(site_root, now)
    except Exception as e:
        print("den: skipped,", repr(e))
        return
    try:  # Called Up, the NBA alumni grid (needs data/den/nba_alumni.json)
        from . import den_grid
        den_grid.build(site_root, now)
    except Exception as e:
        print("den_grid: skipped,", repr(e))
    d = site_root / "den"
    today = now.astimezone(ET).strftime("%Y-%m-%d")
    try:
        slate = json.loads((d / f"slate-{today}.json").read_text())
    except (OSError, ValueError):
        return
    try:
        results = json.loads((d / f"results-{today}.json").read_text())
    except (OSError, ValueError):
        results = None
    try:  # ledger_dir is read at call time so tests can point it at a temp folder
        den_connect.build(site_root, slate, results, now=now, ledger_dir=den_connect.LEDGER_DIR)
    except Exception as e:
        print("den_connect: skipped,", repr(e))


def den_connect_context(site_root: Path, now: datetime) -> dict[str, Any]:
    """Tonight's anchor desk, partner rail and season board for den.html (empty when there is no slate tonight)."""
    from .site_chrome import AD
    d = site_root / "den"
    today = now.astimezone(ET).strftime("%Y-%m-%d")
    out: dict[str, Any] = {"connect": None, "standings": None, "house_ad": AD}
    for k, f in (("connect", f"connect-{today}.json"), ("standings", "desk-standings.json")):
        try:
            out[k] = json.loads((d / f).read_text())
        except (OSError, ValueError):
            pass
    return out


def den_page(env: Environment, site_root: Path, eds: list[dict[str, Any]], names: str, base: str, now: datetime) -> dict[str, Any] | None:
    """The Den (/den.html): a static shell whose games run in the browser from site/den/*.json.
    Always written, so the nav link never 404s; on a day with no slate the page shows a quiet empty state.
    Returns the front page's one-line teaser, or None."""
    site_root.mkdir(parents=True, exist_ok=True)
    cfg = {"editions": {e["key"]: e["short"] for e in eds}, "colors": {**{e["key"]: e["color"] for e in eds}, **{e["short"]: e["color"] for e in eds}}}
    (site_root / "den.html").write_text(env.get_template("den.html").render(
        eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX,
        built=now.isoformat(timespec="minutes"), cfg_json=json.dumps(cfg).replace("</", "<\\/"),
        **den_connect_context(site_root, now)))
    # A small widget other sites (JuiceBox Nation) can frame: tonight's closest games and the Called Up grid.
    (site_root / "embed").mkdir(exist_ok=True)
    (site_root / "embed" / "den.html").write_text(env.get_template("embed_den.html").render(base=base))
    return den_teaser(site_root, now)


def media_samples(media: dict[str, Any], sts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coverage an SID can click through: the editor's hand-picked list, else our newest recaps and previews."""
    picked = [s for s in media.get("samples") or [] if s.get("href") and s.get("title")]
    if picked:
        return picked
    label = {"recap": "Recap", "preview": "Preview"}
    recaps = [s for s in sts if s["kind"] == "recap"][:3]
    previews = [s for s in sts if s["kind"] == "preview"][:2]
    return [{"title": s["title"], "href": s["href"], "kind": label[s["kind"]], "league": s["league"]} for s in recaps + previews]
