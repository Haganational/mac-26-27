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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import weekly
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
    }


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
    return {
        "key": lg.key, "short": lg.short, "name": lg.name, "region": lg.region,
        "href": front_page(lg), "prefix": prefix, "weekly": bool(weekly.issues(lg.key)), "n_teams": len(lg.teams),
        "tonight": [_game(g, site_root, prefix) for g in upcoming[:6]],
        "upcoming_all": [_game(g, site_root, prefix) for g in upcoming[:12]],
        "finals": [_game(g, site_root, prefix) for g in finals],
        "teams": [{"key": t.key, "short": t.short, "href": prefix + f"teams/{t.key}.html"} for t in lg.teams],
        "updated": d.get("generated_et") or "",
    }


# One accent per conference, used for its tag on the front page. Muted so they sit with the hickory and brick.
CONF_COLORS = {"mac": "#a8441c", "asun": "#2e7258", "horizon": "#3d5a80", "mw": "#7b5b8f", "metro": "#7a2e3a", "bigwest": "#b0772a"}


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
        out.append({"href": _rel(it["url"], base), "title": it["title"], "kind": it["kind"],
                    "dek": _meta(it["page"], "og:description"),
                    "video": bool(it["page"] and it["page"].exists() and 'class="hl-video"' in it["page"].read_text()),
                    "image": img if img and "/game-" in img else "",
                    "league": it["league"], "key": key, "color": CONF_COLORS.get(key, "#a8441c"),
                    "when": when, "age": _age(when, now)})
    out.sort(key=lambda s: s["when"], reverse=True)
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
        out.append({"key": e["key"], "name": e["name"], "href": e["href"], "editor": who or mh.get("editor", ""), "acting": not who})
    return out


def org_ld(mh: dict[str, Any], base: str = SITE_BASE) -> dict[str, Any]:
    """The NewsMediaOrganization, with the masthead and policy pages Google looks for."""
    m = base + "masthead.html"
    o: dict[str, Any] = {
        "@type": "NewsMediaOrganization", "@id": base + "#org", "name": "Hardwood Bricks", "url": base,
        "logo": {"@type": "ImageObject", "url": base + "static/og/icon-512.png"},
        "sameAs": ["https://www.youtube.com/@hardwoodbricks", "https://www.threads.com/@hardwoodbricks",
                   "https://www.instagram.com/hardwoodbricks/", "https://bsky.app/profile/hardwoodbricks.bsky.social"] + ([f"https://x.com/{mh['x_handle']}"] if mh.get("x_handle") else []),
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


def build(site_root: Path | None = None, base: str = SITE_BASE) -> Path:
    site_root = site_root or SITE_ROOT
    eds = [e for lg in LEAGUES.values() if (e := edition(lg, site_root))]
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    names = ", ".join(e["short"] for e in eds[:-1]) + (f" and {eds[-1]['short']}" if len(eds) > 1 else (eds[0]["short"] if eds else ""))
    now = datetime.now(timezone.utc)
    sts = front_stories(site_root, now, base)
    recaps = [x for x in sts if x["kind"] == "recap"]
    lead = next((x for x in recaps if x["image"]), recaps[0] if recaps else (sts[0] if sts else None))
    rest = [x for x in recaps if x is not lead]
    cards = [x for x in rest if x["image"]][:4]
    mh = load_masthead()
    editor = (staff(mh) or [{}])[0]
    for e in eds:
        e["color"] = CONF_COLORS.get(e["key"], "#a8441c")
    html = env.get_template("hub.html").render(
        eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX,
        lead=lead, cards=cards, river=[x for x in rest if x not in cards][:8],
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
    from . import den
    try:  # data for the Den's games (site/den/*.json); the page itself is built elsewhere
        den.build(site_root, now)
    except Exception as e:  # never let the games take the front page down
        print("den: skipped,", repr(e))
    media = mh.get("media") or {}
    has_notes = {lg.key for lg in LEAGUES.values() if lg.has("notes")}
    mld = {"@context": "https://schema.org", "@graph": [org_ld(mh, base), {
        "@type": "WebPage", "@id": base + "media.html", "url": base + "media.html", "name": "Media and credentials",
        "about": {"@id": base + "#org"}, "isPartOf": {"@id": base + "#site"}}]}
    (site_root / "media.html").write_text(env.get_template("media.html").render(
        eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX, mh=mh, media=media, editor=editor,
        notes_eds=[e for e in eds if e["key"] in has_notes], samples=media_samples(media, sts),
        ld_json=json.dumps(mld).replace("</", "<\\/")))
    return site_root / "index.html"


def media_samples(media: dict[str, Any], sts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coverage an SID can click through: the editor's hand-picked list, else our newest recaps and previews."""
    picked = [s for s in media.get("samples") or [] if s.get("href") and s.get("title")]
    if picked:
        return picked
    label = {"recap": "Recap", "preview": "Preview"}
    recaps = [s for s in sts if s["kind"] == "recap"][:3]
    previews = [s for s in sts if s["kind"] == "preview"][:2]
    return [{"title": s["title"], "href": s["href"], "kind": label[s["kind"]], "league": s["league"]} for s in recaps + previews]
