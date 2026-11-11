"""One page per player: players/<name>-<espn id>.html.

Built from the same profiles as the team pages (roster bio + every box score we hold), so the
numbers always match. The page leads with what people search for: the name, points per game,
the last game's line and the hometown. Nothing here is invented: a missing field is left out.
"""
from __future__ import annotations

from typing import Any

from .config import BY_KEY, SITE_URL
from .gamer import town
from .site_chrome import slug
from .today import school


POSITIONS = {"G": "guard", "F": "forward", "C": "center", "PG": "point guard", "SG": "guard", "SF": "forward",
             "PF": "forward", "G-F": "wing", "F-C": "forward"}


def position_word(pos: str | None) -> str:
    return POSITIONS.get((pos or "").upper(), "player")


def path(p: dict[str, Any]) -> str:
    return f"players/{slug(p['name'])}-{p['espn_id']}.html"


def hrefs(profiles: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """{espn_id: 'players/....html'} for every profiled player."""
    return {str(p["espn_id"]): path(p) for plist in profiles.values() for p in plist}


def last_game(p: dict[str, Any]) -> dict[str, Any] | None:
    played = [g for g in p.get("game_log", []) if not g.get("dnp") and g.get("min") is not None]
    return played[-1] if played else None


def stat_line(g: dict[str, Any]) -> str:
    bits = [f"{g.get('pts') or 0} points"]
    if g.get("reb"):
        bits.append(f"{g['reb']} rebounds")
    if g.get("ast"):
        bits.append(f"{g['ast']} assists")
    return ", ".join(bits[:-1]) + (" and " if len(bits) > 1 else "") + bits[-1]


def career_highs(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Season highs in points and rebounds, with the game they came in."""
    played = [g for g in p.get("game_log", []) if not g.get("dnp") and g.get("min") is not None]
    out = {}
    for k in ("pts", "reb", "ast"):
        if played:
            best = max(played, key=lambda g: (g.get(k) or 0, g.get("date") or ""))
            if (best.get(k) or 0) > 0:
                out[k] = best
    return out


def context(p: dict[str, Any], season_label: str) -> dict[str, Any]:
    team = BY_KEY[p["team_key"]]
    for g in p.get("game_log", []):
        g["opp"] = school(g.get("opponent")) or g.get("opponent_abbr") or ""
    ht = town(p.get("hometown"))
    pg = (p.get("season") or {}).get("per_game") or {}
    gp = (p.get("season") or {}).get("gp") or 0
    lg = last_game(p)
    title = f"{p['name']} stats"
    if gp and pg.get("pts") is not None:
        title += f": {pg['pts']} points per game"
    title += f", {season_label} · {team.short}"
    desc = f"{p['name']}, {team.short} {position_word(p.get('position'))}" + (f" from {ht}" if ht else "") + "."
    if gp:
        desc += f" {pg.get('pts')} points, {pg.get('reb')} rebounds and {pg.get('ast')} assists a game over {gp} games."
    if lg:
        desc += f" Last game: {stat_line(lg)} {'vs' if lg.get('home') else 'at'} {lg['opp']}."
    return {"p": p, "team": team, "hometown": ht, "position": position_word(p.get("position")), "pg": pg, "gp": gp, "last": lg, "highs": career_highs(p),
            "page_title": title, "page_desc": desc, "path": path(p)}


def json_ld(c: dict[str, Any], site_name: str, site_url: str = SITE_URL) -> dict[str, Any]:
    """schema.org ProfilePage about a Person who plays for a SportsTeam."""
    p, team = c["p"], c["team"]
    url = f"{site_url}{c['path']}"
    person: dict[str, Any] = {
        "@type": "Person",
        "@id": url + "#person",
        "name": p["name"],
        "url": url,
        "affiliation": {"@type": "SportsTeam", "name": team.name, "sport": "Basketball",
                        "url": f"{site_url}teams/{team.key}.html"},
    }
    if p.get("position"):
        person["jobTitle"] = f"Basketball player ({p['position']})"
    if c["hometown"]:
        person["homeLocation"] = {"@type": "Place", "name": c["hometown"]}
    if p.get("height"):
        person["height"] = p["height"]
    if p.get("espn_url"):
        person["sameAs"] = [p["espn_url"]]
    return {"@context": "https://schema.org", "@type": "ProfilePage", "url": url, "name": c["page_title"],
            "about": {"@id": url + "#person"}, "mainEntity": person,
            "isPartOf": {"@type": "WebSite", "name": site_name, "url": site_url}}
