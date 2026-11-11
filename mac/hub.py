"""The site root: hardwoodbricks.com/, a front door for every conference we cover.

Each edition builds its own pages and data.json. This page reads those data.json files
(whatever editions exist in site/), shows tonight's games and the latest finals for each
conference, and links every edition's front page. It also writes the root robots.txt,
which is the only robots.txt search engines read, listing every edition's sitemap.

    python -m mac.collect hub     # rebuild just this page, after the editions
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import LEAGUES, SEASON_LABEL, SHARED_DIR, SITE_BASE, SITE_NOINDEX, SITE_ROOT, TEMPLATES_DIR


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
        "href": front_page(lg), "prefix": prefix, "n_teams": len(lg.teams),
        "tonight": [_game(g, site_root, prefix) for g in upcoming[:6]],
        "finals": [_game(g, site_root, prefix) for g in finals],
        "teams": [{"key": t.key, "short": t.short, "href": prefix + f"teams/{t.key}.html"} for t in lg.teams],
        "updated": d.get("generated_et") or "",
    }


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
        "sameAs": ["https://www.youtube.com/@juiceboxtv-m1g"] + ([f"https://x.com/{mh['x_handle']}"] if mh.get("x_handle") else []),
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
    html = env.get_template("hub.html").render(
        eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX,
        ld_json=json.dumps(json_ld(eds, base)).replace("</", "<\\/"),
        built=datetime.now(timezone.utc).isoformat(timespec="minutes"))
    site_root.mkdir(parents=True, exist_ok=True)
    (site_root / "index.html").write_text(html)
    (site_root / "robots.txt").write_text(robots(base))
    mh = load_masthead()
    ppl = staff(mh)
    ld = {"@context": "https://schema.org", "@graph": [org_ld(mh, base)] + [
        {"@type": "Person", "@id": f"{base}masthead.html#{p['slug']}", "name": p["name"], "jobTitle": p.get("title", ""),
         "worksFor": {"@id": base + "#org"}, **({"description": p["bio"]} if p.get("bio") else {})} for p in ppl]}
    (site_root / "masthead.html").write_text(env.get_template("masthead.html").render(
        eds=eds, names=names, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX, mh=mh, staff=ppl, desks=desks(mh, eds),
        ld_json=json.dumps(ld).replace("</", "<\\/")))
    return site_root / "index.html"
