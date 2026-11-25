"""Our towns: one landing page per college town we cover, for local search.

Matthew, Nov 25 2026: "local SEO and landing page ... for our pages in our markets". Each of the
286 schools sits in a town (data/school_facts.json, desk research Nov 17); a town with three schools
(Chicago, Nashville, Philadelphia) gets one page with all of them. A page carries what a reader
searching "<town> college basketball" wants: who plays there, where, every home date left with TV,
the last few home results, the hometown paper and a rotating handful of the research desk's checked
notes. Pages live at towns/<town>-<state>.html under the site root, with a towns/index.html by state,
their own sitemap (listed in robots.txt) and schema.org CollectionPage + SportsTeam + SportsEvent.

    python -m mac.towns            # write site/towns/ from the editions already built
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import gamer, press, weekly
from .config import LEAGUES, SEARCH, SEASON_LABEL, SHARED_DIR, SITE_BASE, SITE_NOINDEX, SITE_ROOT, TEMPLATES_DIR

ET = ZoneInfo("America/New_York")
FACTS = SHARED_DIR / "school_facts.json"
FOLDER = "towns"
STATE_ABBR = {
    "Alabama": "AL", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO", "Connecticut": "CT",
    "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME",
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
    "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
    "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def town_label(town: str, state: str) -> str:
    """'Akron, Ohio'; 'Washington, D.C.'; 'The Bronx, New York' (a heading never starts lower case)."""
    town = town[:1].upper() + town[1:]
    return "Washington, D.C." if state == "District of Columbia" else f"{town}, {state}"


def town_slug(town: str, state: str) -> str:
    return slug(f"{town} {STATE_ABBR.get(state, state)}")


def _facts() -> dict[str, dict[str, Any]]:
    return json.loads(FACTS.read_text()).get("schools", {}) if FACTS.exists() else {}


def _val(field: Any) -> Any:
    return field.get("value") if isinstance(field, dict) else field


def _schedule(lg: Any) -> list[dict[str, Any]]:
    f = lg.data_dir / "schedule.json"
    try:
        return json.loads(f.read_text()).get("games", []) if f.exists() else []
    except ValueError:
        return []


def _when(iso: str) -> tuple[datetime | None, str, str]:
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)
    except ValueError:
        return None, "", ""
    return d, d.strftime("%a, %b %-d"), d.strftime("%-I:%M %p ET").replace(":00 ", " ")


def _name(side: dict[str, Any]) -> str:
    from .hub import _school
    return _school(side) or side.get("name") or ""


def _href(g: dict[str, Any], prefix: str, site_root: Path) -> str:
    from .hub import game_owner
    owner = game_owner(g["home"].get("espn_id"), g["away"].get("espn_id"))
    for p in ([owner.path] if owner is not None else []) + [prefix]:
        if (site_root / p / "games" / f"{g['game_id']}.html").exists():
            return f"{p}games/{g['game_id']}.html"
    return f"{prefix}tv.html#g{g['game_id']}"


def home_arena(team_key: str, games: list[dict[str, Any]]) -> dict[str, str]:
    """The building a team plays most of its true home games in this season (ESPN's venue name)."""
    seen = Counter((g.get("venue") or "", g.get("venue_city") or "", g.get("venue_state") or "")
                   for g in games if g["home"].get("key") == team_key and not g.get("neutral_site") and g.get("venue"))
    if not seen:
        return {}
    (name, city, state), _ = seen.most_common(1)[0]
    return {"name": name, "city": city, "state": state}


def home_games(team_key: str, games: list[dict[str, Any]], prefix: str, site_root: Path, now: datetime,
               ahead: int = 8, back: int = 3) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Home dates left (soonest first) and the last few home results (newest first). Neutral sites aren't home."""
    mine = sorted((g for g in games if g["home"].get("key") == team_key and not g.get("neutral_site")), key=lambda g: g.get("date") or "")
    up, done = [], []
    for g in mine:
        d, day, tip = _when(g.get("date") or "")
        if d is None:
            continue
        row = {"game_id": g["game_id"], "date": g["date"], "day": day, "tip": "" if g.get("time_tba") else tip,
               "opp": _name(g["away"]), "tv": ", ".join(b["name"] for b in (g.get("broadcasts") or [])[:1]),
               "href": _href(g, prefix, site_root), "venue": g.get("venue") or "", "conf": bool(g.get("conference_game")),
               "us": g["home"].get("score"), "them": g["away"].get("score"), "won": bool(g["home"].get("winner")),
               "home_name": g["home"].get("name") or "", "away_name": g["away"].get("name") or "",
               "venue_city": g.get("venue_city") or "", "venue_state": g.get("venue_state") or ""}
        if g.get("completed"):
            done.append(row)
        elif d >= now.astimezone(ET).replace(hour=0, minute=0, second=0, microsecond=0):
            up.append(row)
    return up[:ahead], done[::-1][:back]


def collect(site_root: Path | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    """Every town we cover, each with its schools. Schools without a town in school_facts are left out."""
    site_root = site_root or SITE_ROOT
    now = now or datetime.now(timezone.utc)
    on = now.astimezone(ET).date().isoformat()
    facts = _facts()
    towns: dict[str, dict[str, Any]] = {}
    for lg in LEAGUES.values():
        games = _schedule(lg)
        flavor = gamer.load_flavor(lg.data_dir / "flavor.json")
        paper = weekly.paper(lg.key)
        depth = lg.path.count("/")
        for t in lg.teams:
            f = facts.get(t.key) or {}
            if not f.get("town") or not f.get("state"):
                continue
            key = town_slug(f["town"], f["state"])
            town = towns.setdefault(key, {
                "slug": key, "town": f["town"][:1].upper() + f["town"][1:], "state": f["state"],
                "abbr": STATE_ABBR.get(f["state"], ""), "label": town_label(f["town"], f["state"]),
                "county": _val(f.get("county")) or "", "county_src": (f.get("county") or {}).get("source", "") if isinstance(f.get("county"), dict) else "",
                "population": _val(f.get("population")), "pop_year": (f.get("population") or {}).get("year", "") if isinstance(f.get("population"), dict) else "",
                "pop_src": (f.get("population") or {}).get("source", "") if isinstance(f.get("population"), dict) else "",
                "schools": []})
            up, done = home_games(t.key, games, lg.path, site_root, now)
            pd = press.desk(t.key, depth) or {}
            notes = gamer.around_town(t.key, flavor, on, n=3)
            town["schools"].append({
                "key": t.key, "name": t.name, "short": t.short, "abbr": t.abbr, "color": t.color, "color2": t.color2,
                "league": lg.key, "conf": lg.short, "conf_name": lg.name, "edition": lg.path + ("index.html" if lg.path else ""),
                "team_href": f"{lg.path}teams/{t.key}.html", "weekly_href": f"{lg.path}weekly.html",
                "weekly_paper": paper["plain"] if paper else "BricksIt Weekly",
                "arena": home_arena(t.key, games), "floor": (flavor.get("teams", {}).get(t.key) or {}).get("home_floor") or "",
                "upcoming": up, "recent": done,
                "paper": pd.get("paper") or "", "anchor": pd.get("name") or "",
                "anchor_href": f"anchors/{t.key}.html" if pd.get("name") else "",
                "enrollment": _val(f.get("enrollment")),
                "notes": (notes or {}).get("notes", []),
            })
    for town in towns.values():
        town["schools"].sort(key=lambda s: s["short"])
        town["next"] = min((g for s in town["schools"] for g in s["upcoming"][:1]), key=lambda g: g["date"], default=None)
    return sorted(towns.values(), key=lambda x: (x["state"], x["town"]))


def _names(schools: list[dict[str, Any]], attr: str = "short") -> str:
    n = [s[attr] for s in schools]
    return n[0] if len(n) == 1 else ", ".join(n[:-1]) + f" and {n[-1]}"


def title(town: dict[str, Any]) -> str:
    s = town["schools"]
    who = s[0]["name"] if len(s) == 1 else _names(s)
    return f"{town['label']} college basketball: {who} home games, TV and scores · Hardwood Bricks"


def description(town: dict[str, Any]) -> str:
    s = town["schools"]
    if len(s) == 1:
        a = s[0]["arena"].get("name")
        where = f" at {a}" if a else ""
        return (f"{s[0]['name']} men's basketball in {town['label']}: every home date left{where}, tip times and TV, "
                f"recent results and local notes, from our {s[0]['conf']} edition.")
    return (f"Men's college basketball in {town['label']}: {_names(s)}. Every home date left, tip times and TV, "
            f"recent results and local notes, all on one page.")


def json_ld(town: dict[str, Any], base: str = SITE_BASE) -> dict[str, Any]:
    url = f"{base}{FOLDER}/{town['slug']}.html"
    city = {"@type": "City", "name": town["town"], "containedInPlace": {"@type": "State", "name": town["state"]}}
    graph: list[dict[str, Any]] = [
        {"@type": "CollectionPage", "@id": url, "url": url, "name": title(town), "description": description(town),
         "about": city, "isPartOf": {"@id": base + "#site"}, "inLanguage": "en-US",
         "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
             {"@type": "ListItem", "position": 1, "name": "Hardwood Bricks", "item": base},
             {"@type": "ListItem", "position": 2, "name": "Our towns", "item": f"{base}{FOLDER}/"},
             {"@type": "ListItem", "position": 3, "name": town["label"], "item": url}]}},
    ]
    for s in town["schools"]:
        team = {"@type": "SportsTeam", "@id": f"{base}{s['team_href']}#team", "name": s["name"], "sport": "Basketball",
                "url": base + s["team_href"], "memberOf": {"@type": "SportsOrganization", "name": s["conf_name"]}}
        arena = s["arena"]
        place = None
        if arena.get("name"):
            place = {"@type": "Place", "name": arena["name"], "address": {
                "@type": "PostalAddress", "addressLocality": arena.get("city") or town["town"],
                "addressRegion": arena.get("state") or town["state"], "addressCountry": "US"}}
            team["location"] = place
        events = []
        for g in s["upcoming"][:5]:
            ev = {"@type": "SportsEvent", "name": f"{g['away_name']} at {g['home_name']}", "sport": "Basketball",
                  "startDate": g["date"].replace("Z", ":00Z") if g["date"].endswith("Z") and g["date"].count(":") == 1 else g["date"],
                  "eventStatus": "https://schema.org/EventScheduled", "url": base + g["href"],
                  "homeTeam": {"@type": "SportsTeam", "name": g["home_name"]}, "awayTeam": {"@type": "SportsTeam", "name": g["away_name"]}}
            if g["venue"]:
                ev["location"] = {"@type": "Place", "name": g["venue"], "address": {
                    "@type": "PostalAddress", "addressLocality": g["venue_city"] or town["town"],
                    "addressRegion": g["venue_state"] or town["state"], "addressCountry": "US"}}
            elif place:
                ev["location"] = place
            events.append(ev)
        if events:
            team["event"] = events
        graph.append(team)
    return {"@context": "https://schema.org", "@graph": graph}


def by_state(towns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in towns:
        if not out or out[-1]["state"] != t["state"]:
            out.append({"state": t["state"], "abbr": t["abbr"], "towns": []})
        out[-1]["towns"].append(t)
    return out


def sitemap(towns: list[dict[str, Any]], base: str = SITE_BASE) -> str:
    urls = [f"{base}{FOLDER}/"] + [f"{base}{FOLDER}/{t['slug']}.html" for t in towns]
    rows = "".join(f"<url><loc>{u}</loc><changefreq>daily</changefreq></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>\n'


def team_link(team_key: str) -> dict[str, str] | None:
    """The town page a team page links to: {'label': 'Akron, Ohio', 'href': 'towns/akron-oh.html'} from the site root."""
    f = _facts().get(team_key) or {}
    if not f.get("town") or not f.get("state"):
        return None
    return {"label": town_label(f["town"], f["state"]), "href": f"{FOLDER}/{town_slug(f['town'], f['state'])}.html",
            "town": f["town"][:1].upper() + f["town"][1:], "state": f["state"]}


def team_ld(team: Any, league: Any, games: list[dict[str, Any]], site_url: str, base: str = SITE_BASE) -> dict[str, Any]:
    """schema.org SportsTeam for a team page: its conference, its home floor and its town page."""
    url = f"{site_url}teams/{team.key}.html"
    ld: dict[str, Any] = {"@context": "https://schema.org", "@type": "SportsTeam", "@id": url + "#team", "name": team.name,
                          "alternateName": team.short, "sport": "Basketball", "url": url,
                          "memberOf": {"@type": "SportsOrganization", "name": league.name}}
    t = team_link(team.key)
    arena = home_arena(team.key, games)
    if arena.get("name") or t:
        ld["location"] = {"@type": "Place", "name": arena.get("name") or (t or {}).get("label", ""), "address": {
            "@type": "PostalAddress", "addressLocality": arena.get("city") or (t or {}).get("town", ""),
            "addressRegion": arena.get("state") or (t or {}).get("state", ""), "addressCountry": "US"}}
    if t:
        ld["subjectOf"] = {"@type": "WebPage", "url": base + t["href"], "name": f"{t['label']} college basketball"}
    return ld


def build(site_root: Path | None = None, base: str = SITE_BASE, eds: list[dict[str, Any]] | None = None,
          now: datetime | None = None) -> list[dict[str, Any]]:
    site_root = site_root or SITE_ROOT
    now = now or datetime.now(timezone.utc)
    if eds is None:
        from .hub import edition
        eds = [e for lg in LEAGUES.values() if (e := edition(lg, site_root))]
    towns = collect(site_root, now)
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    env.globals["search"] = SEARCH
    out = site_root / FOLDER
    out.mkdir(parents=True, exist_ok=True)
    common = dict(eds=eds, base=base, season=SEASON_LABEL, noindex=SITE_NOINDEX,
                  built=now.astimezone(ET).strftime("%B %-d, %Y"), n_towns=len(towns),
                  n_schools=sum(len(t["schools"]) for t in towns))
    tpl = env.get_template("town.html")
    for t in towns:
        neighbors = [x for x in towns if x["state"] == t["state"] and x is not t]
        (out / f"{t['slug']}.html").write_text(tpl.render(
            town=t, title=title(t), desc=description(t), neighbors=neighbors,
            ld_json=json.dumps(json_ld(t, base)).replace("</", "<\\/"), **common))
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "@id": f"{base}{FOLDER}/", "url": f"{base}{FOLDER}/",
          "name": "Our towns", "isPartOf": {"@id": base + "#site"},
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(towns), "itemListElement": [
              {"@type": "ListItem", "position": i + 1, "name": t["label"], "url": f"{base}{FOLDER}/{t['slug']}.html"}
              for i, t in enumerate(towns)]}}
    (out / "index.html").write_text(env.get_template("towns.html").render(
        states=by_state(towns), ld_json=json.dumps(ld).replace("</", "<\\/"), **common))
    (out / "sitemap.xml").write_text(sitemap(towns, base))
    return towns


if __name__ == "__main__":
    ts = build()
    print(f"towns: {len(ts)} pages, {sum(len(t['schools']) for t in ts)} schools")
