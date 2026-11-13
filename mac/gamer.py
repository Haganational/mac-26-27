"""The gamer: a short written recap for each box score page, plus its news-style structured data.

Every fact comes from the box score, the closing line and the model, like MAC90: if a number
is missing, its sentence is left out. The one hand-written part is local flavor, from
data/flavor.json (see FLAVOR_HELP below), so a page can carry a line about the town, the
building or the rivalry that no box score has. Nothing there is generated; it is ours to write.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from markupsafe import Markup, escape

from .config import DATA_DIR, SITE_BASE, SITE_URL
from .today import school

ET = ZoneInfo("America/New_York")

STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
          "CT": "Connecticut", "DE": "Delaware", "DC": "D.C.", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
          "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
          "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
          "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
          "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
          "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
          "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
          "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
          "WI": "Wisconsin", "WY": "Wyoming"}


def town(hometown: str | None) -> str | None:
    """'Westerville, OH' -> 'Westerville, Ohio'; 'Cotonou, Benin' stays as it is."""
    if not hometown or not hometown.strip():
        return None
    parts = [x.strip() for x in hometown.split(",")]
    if len(parts) == 2 and parts[1].upper() in STATES:
        return f"{parts[0]}, {STATES[parts[1].upper()]}"
    return hometown.strip()


def linkify(text: str, links: dict[str, str]) -> Markup:
    """Escape text and turn each player name in `links` into a link (longest names first)."""
    out = str(escape(text))
    names = sorted((n for n in links if n), key=len, reverse=True)
    if not names:
        return Markup(out)
    pat = re.compile(r"(?<![\w-])(" + "|".join(re.escape(str(escape(n))) for n in names) + r")(?![\w-])")
    by_esc = {str(escape(n)): links[n] for n in names}
    return Markup(pat.sub(lambda m: f'<a href="{escape(by_esc[m.group(1)])}">{m.group(1)}</a>', out))

FLAVOR_PATH = DATA_DIR / "flavor.json"
PUBLISHED_PATH = DATA_DIR / "published.json"

FLAVOR_HELP = """data/flavor.json knobs:
  settings.enabled        false turns every flavor line off
  settings.byline         who the gamer is credited to ("Hardwood Bricks staff")
  settings.max_lines      how many flavor lines a gamer may carry (0 to 2)
  teams.<key>.town        "Akron", used as "in Akron" when the game is at home
  teams.<key>.home_floor  what we call the building ("the JAR")
  teams.<key>.home_lines  lines that only make sense at home ("Another night at the JAR"); home games only
  teams.<key>.lines       lines true wherever the team plays (history, town lore); one is picked per game, rotating
  a line is a string, or {"text", "source", "kind", "until"}: "source" is where the fact was checked,
  and a line with "until": "YYYY-MM-DD" is dropped from games played after that date (news goes stale)
  rivalries.<a>|<b>       keys sorted alphabetically: {"name": "...", "lines": [...]} for that matchup
Lines may use {winner}, {loser}, {home}, {away}, {town} and {floor}."""


def load_flavor(path: Path = FLAVOR_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"settings": {}, "teams": {}, "rivalries": {}}
    f = json.loads(path.read_text())
    f.setdefault("settings", {})
    f.setdefault("teams", {})
    f.setdefault("rivalries", {})
    return f


def _player_line(p: dict[str, Any]) -> str:
    bits = [f"{p['pts']} points"]
    if (p.get("reb") or 0) >= 8:
        bits.append(f"{p['reb']} rebounds")
    if (p.get("ast") or 0) >= 6:
        bits.append(f"{p['ast']} assists")
    if len(bits) == 1 and (p.get("tpm") or 0) >= 4:
        bits.append(f"{p['tpm']} 3-pointers")
    return ", ".join(bits[:-1]) + (" and " if len(bits) > 1 else "") + bits[-1]


def _top(players: list[dict[str, Any]]) -> dict[str, Any] | None:
    live = [p for p in players if not p.get("dnp") and p.get("pts") is not None]
    return max(live, key=lambda p: (p["pts"], p.get("reb") or 0)) if live else None


def _num(stats: dict[str, Any], key: str) -> int | None:
    try:
        return int(str(stats.get(key)).split("-")[0])
    except (TypeError, ValueError):
        return None


def _edge_sentence(w: dict[str, Any], l: dict[str, Any], wn: str, ln: str) -> str | None:
    """The one team-stat gap that most explains the result, if one stands out."""
    ws, ls = w.get("stats") or {}, l.get("stats") or {}
    cands = []
    for key, label, good_high, min_gap in (("offensiveRebounds", "offensive rebounds", True, 6),
                                           ("totalTurnovers", "turnovers", False, 6),
                                           ("threePointFieldGoalsMade-threePointFieldGoalsAttempted", "3-pointers", True, 5),
                                           ("pointsInPaint", "points in the paint", True, 14),
                                           ("fastBreakPoints", "fast-break points", True, 10)):
        a, b = _num(ws, key), _num(ls, key)
        if a is None or b is None:
            continue
        gap = (a - b) if good_high else (b - a)
        if gap >= min_gap:
            cands.append((gap / min_gap, key, label, a, b))
    if not cands:
        return None
    _, key, label, a, b = max(cands)
    if key == "totalTurnovers":
        return f"{wn} committed {a} turnovers to {ln}'s {b}."
    return f"{wn} had {a} {label} to {ln}'s {b}."


def line_text(item: Any, on: str = "") -> str:
    """A flavor line is a plain string, or {"text", "source", "kind", "until"} from the research desk.
    A note with "until" (YYYY-MM-DD) is news that goes stale: it is dropped for games after that date."""
    if isinstance(item, dict):
        until = str(item.get("until") or "")
        if until and on and on > until:
            return ""
        return str(item.get("text") or "")
    return item if isinstance(item, str) else ""


def _pick(lines: list[Any], seed: str, on: str = "") -> str | None:
    lines = [t for t in (line_text(s, on) for s in lines) if t.strip()]
    if not lines:
        return None
    i = int(hashlib.sha1(seed.encode()).hexdigest(), 16) % len(lines)
    return lines[i]


def flavor_lines(g: dict[str, Any], flavor: dict[str, Any], names: dict[str, str]) -> list[str]:
    """Up to settings.max_lines hand-written lines for this game: rivalry first, then the home team's."""
    st = flavor.get("settings", {})
    if st.get("enabled") is False:
        return []
    most = int(st.get("max_lines", 1))
    home_key, away_key = g["home"].get("key"), g["away"].get("key")
    teams = flavor.get("teams", {})
    ht = teams.get(home_key or "", {})
    fill = {**names, "town": ht.get("town") or g.get("venue_city") or "", "floor": ht.get("home_floor") or g.get("venue") or ""}
    out = []
    on = str(g.get("date") or "")[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if home_key and away_key:
        r = flavor.get("rivalries", {}).get("|".join(sorted([home_key, away_key])))
        if r:
            line = _pick(r.get("lines", []), g["game_id"] + "r", on)
            if line:
                out.append(line)
    # home_lines only when that team really is at home; lines go anywhere the team plays
    pool = [] if g.get("neutral_site") else list(ht.get("home_lines", []))
    pool += ht.get("lines", [])
    if not pool:  # a road game for our team: its anywhere lines, so the page still sounds like us
        pool = teams.get(away_key or "", {}).get("lines", [])
    line = _pick(pool, g["game_id"], on)
    if line:
        out.append(line)
    # with room for another line, the visitors get one of theirs too
    if ht.get("lines") or ht.get("home_lines"):
        line = _pick(teams.get(away_key or "", {}).get("lines", []), g["game_id"] + "a", on)
        if line:
            out.append(line)
    res = []
    for s in out[:max(0, most)]:
        try:
            res.append(s.format(**fill))
        except (KeyError, IndexError, ValueError):
            res.append(s)
    return res


def write(c: dict[str, Any], mp: dict[str, Any] | None = None, flavor: dict[str, Any] | None = None,
          bios: dict[str, dict[str, Any]] | None = None, nba: tuple[dict, dict] | None = None) -> dict[str, Any]:
    """Headline, paragraphs and flavor lines for one finished game, from game_page_context().

    bios: {espn_id: {"hometown": "Westerville, OH"}} for players we have rosters for. The top
    scorer and the game's leading rebounder get their hometown when we know it.
    """
    bios = bios or {}

    def native(p: dict[str, Any]) -> str:
        t = town((bios.get(str(p.get("espn_id"))) or {}).get("hometown"))
        return f"{t}, native {p['name']}" if t and "," in t else (f"{t} native {p['name']}" if t else p["name"])

    g, home, away = c["g"], c["home"], c["away"]
    flavor = flavor if flavor is not None else load_flavor()
    hn, an = school(home["name"], home.get("key")), school(away["name"], away.get("key"))
    home_won = (home["score"] or 0) > (away["score"] or 0)
    w, l = (home, away) if home_won else (away, home)
    wn, ln = (hn, an) if home_won else (an, hn)
    margin = abs((home["score"] or 0) - (away["score"] or 0))
    names = {"winner": wn, "loser": ln, "home": hn, "away": an}

    verb = "edged" if margin <= 3 else ("beat" if margin < 15 else "rolled past")
    where = ""
    if g.get("neutral_site"):
        where = f" at {g['venue']}" if g.get("venue") else ""
    elif home_won:
        where = f" at home" if not g.get("venue") else f" at {g['venue']}"
    else:
        where = f" on the road in {g['venue_city']}" if g.get("venue_city") else " on the road"
    ot = ""
    if (g.get("ot") or 0) or (c.get("box") or {}).get("ot"):
        ot = " in overtime"
    lede = f"{wn} {verb} {ln} {w['score']}-{l['score']}{ot}{where}."
    headline = f"{wn} {verb} {ln} {w['score']}-{l['score']}"

    paras = [lede]
    tw, tl = _top(w.get("players", [])), _top(l.get("players", []))
    if tw:
        s = f"{native(tw)} led {wn} with {_player_line(tw)}."
        rebs = [(p, wn if p in w.get("players", []) else ln) for p in w.get("players", []) + l.get("players", [])
                if not p.get("dnp") and (p.get("reb") or 0) >= 6]
        rb, rteam = max(rebs, key=lambda x: (x[0]["reb"], x[0].get("oreb") or 0)) if rebs else (None, None)
        if tl:
            line = _player_line(tl)
            if rb is tl:  # the loser's top scorer also owned the glass: say it once, with his hometown
                s += f" {native(tl)} had {line} for {ln}" + (", a game high on the boards." if "rebounds" in line
                                                               else f" and a game-high {tl['reb']} rebounds.")
            else:
                s += f" {tl['name']} had {line} for {ln}."
        if rb is not None and rb is not tw and rb is not tl:
            s += f" {native(rb)} led all players with {rb['reb']} rebounds for {rteam}."
        paras.append(s)
    edge = _edge_sentence(w, l, wn, ln)
    res = c.get("result") or {}
    tail = []
    if edge:
        tail.append(edge)
    if res.get("ats") and res["ats"] != "push":
        covered = res["ats"].split(" ")[0]
        team = hn if covered == home["abbr"] else an
        tail.append(f"{team} covered the closing spread.")
    if mp and mp.get("model_err") is not None:
        tail.append(f"Our model missed the final margin by {mp['model_err']:.1f} points.")
    if tail:
        paras.append(" ".join(tail))
    if nba:  # (nights, colleges) from nba_alumni: former players of either school who played in the NBA that night or the night before
        from . import nba_alumni
        try:
            day = datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(ET).date()
            para = nba_alumni.paragraph([(str(home.get("espn_id") or ""), hn), (str(away.get("espn_id") or ""), an)], day, *nba)
        except (KeyError, ValueError):
            para = None
        if para:
            paras.append(para)

    return {"headline": headline, "paragraphs": paras, "flavor": flavor_lines(g, flavor, names),
            "scoring": scoring_line([(wn, w.get("players", [])), (ln, l.get("players", []))]),
            "byline": flavor.get("settings", {}).get("byline") or "Hardwood Bricks staff"}


def scoring_line(sides: list[tuple[str, list[dict[str, Any]]]]) -> str:
    """The mini box score: everyone who scored, winner first, most points first.

    "Akron: Evan Mahaffey 9, James Black 6. Bowling Green: Javontae Evans 8."
    Full names on purpose: people search "[player] points".
    """
    parts = []
    for team, players in sides:
        scored = [p for p in players if not p.get("dnp") and (p.get("pts") or 0) > 0]
        scored.sort(key=lambda p: -p["pts"])
        if scored:
            parts.append(f"{team}: " + ", ".join(f"{p['name']} {p['pts']}" for p in scored) + ".")
    return " ".join(parts)


# ---------------------------------------------------------------- publish times + JSON-LD

def load_published(path: Path = PUBLISHED_PATH) -> dict[str, str]:
    return json.loads(path.read_text()) if path.exists() else {}


def stamp(published: dict[str, str], gid: str, now: datetime, tip: str | None = None) -> str:
    """When this gamer first went up. Kept in data/published.json so it never moves on rebuilds.

    A game first seen long after it ended (a backfill, or the first run of this code) is stamped
    with its estimated end, tip plus two hours, rather than claiming it was written today.
    """
    if gid not in published:
        when = now.astimezone(timezone.utc)
        if tip:
            end = datetime.fromisoformat(tip.replace("Z", "+00:00")) + timedelta(hours=2)
            if when - end > timedelta(hours=6):
                when = end
        published[gid] = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    return published[gid]


def save_published(published: dict[str, str], path: Path = PUBLISHED_PATH) -> None:
    path.write_text(json.dumps(dict(sorted(published.items())), indent=0) + "\n")


def _team_ld(side: dict[str, Any]) -> dict[str, Any]:
    t = {"@type": "SportsTeam", "name": side["name"], "sport": "Basketball"}
    if side.get("key"):
        t["url"] = f"{SITE_URL}teams/{side['key']}.html"
    return t


def photo_ld(ph: dict[str, str], site_url: str = SITE_URL) -> dict[str, Any]:
    """An ImageObject for one of our own game photos, credited to whoever took it."""
    o: dict[str, Any] = {"@type": "ImageObject", "contentUrl": f"{site_url}{ph['src']}", "url": f"{site_url}{ph['src']}"}
    if ph.get("caption"):
        o["caption"] = ph["caption"]
    if ph.get("credit"):
        o["creator"] = {"@type": "Person", "name": ph["credit"]}
        o["creditText"] = ph["credit"]
        o["copyrightNotice"] = ph["credit"]
    return o


def json_ld(c: dict[str, Any], gm: dict[str, Any], published: str, modified: str, site_name: str,
            site_url: str = SITE_URL, photos: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """schema.org NewsArticle (the gamer) about a SportsEvent (the game). Our own photos lead the images."""
    g, home, away = c["g"], c["home"], c["away"]
    url = f"{site_url}games/{g['game_id']}.html"
    start = g["date"].replace("Z", ":00Z") if g["date"].endswith("Z") and g["date"].count(":") == 1 else g["date"]
    end = (datetime.fromisoformat(g["date"].replace("Z", "+00:00")) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    event = {
        "@type": "SportsEvent",
        "@id": url + "#game",
        "name": f"{away['name']} at {home['name']}",
        "sport": "Basketball",
        "startDate": start,
        "endDate": end,
        "eventStatus": "https://schema.org/EventScheduled",
        "homeTeam": _team_ld(home),
        "awayTeam": _team_ld(away),
        "competitor": [_team_ld(away), _team_ld(home)],
        "url": url,
        # Google's recommended Event fields: the two teams play it, the home school hosts it.
        "performer": [_team_ld(away), _team_ld(home)],
        "organizer": _team_ld(home),
    }
    if g.get("venue"):
        place = {"@type": "Place", "name": g["venue"]}
        if g.get("venue_city"):
            place["address"] = {"@type": "PostalAddress", "addressLocality": g["venue_city"],
                                "addressRegion": g.get("venue_state") or "", "addressCountry": "US"}
        event["location"] = place
    org = {"@type": "NewsMediaOrganization", "@id": f"{SITE_BASE}#org", "name": site_name, "url": SITE_BASE,
           "masthead": f"{SITE_BASE}masthead.html", "publishingPrinciples": f"{SITE_BASE}masthead.html#standards",
           "logo": {"@type": "ImageObject", "url": f"{site_url}static/og/icon-512.png"}}
    article = {
        "@type": "NewsArticle",
        "@id": url + "#gamer",
        "headline": gm["headline"][:110],
        "description": " ".join(gm["paragraphs"][:2])[:300],
        "articleSection": "Men's college basketball",
        "datePublished": published,
        "dateModified": modified,
        "mainEntityOfPage": url,
        "url": url,
        "image": [photo_ld(ph, site_url) for ph in (photos or [])] + [f"{site_url}static/og/game-{g['game_id']}.png"],
        "author": [{"@type": "Organization", "name": gm["byline"], "url": f"{SITE_BASE}masthead.html#automation"}],
        "publisher": org,
        "about": {"@id": url + "#game"},
        "isAccessibleForFree": True,
    }
    # Same picture and summary as the story, so the game itself carries an image and description too.
    event["image"] = [im["url"] if isinstance(im, dict) else im for im in article["image"]]
    event["description"] = article["description"] or event["name"]
    tix = g.get("tickets")
    if tix and tix.get("url") and not g.get("completed"):
        offer = {"@type": "Offer", "url": tix["url"], "availability": "https://schema.org/InStock", "priceCurrency": "USD"}
        if tix.get("low"):
            offer["price"] = f"{tix['low']:.2f}"
        event["offers"] = offer
    return {"@context": "https://schema.org", "@graph": [article, event]}
