"""The preview gamer: a short written story on a game's preview page, published the day before tip.

Like the recap, every fact comes from our own data (schedule, standings, the rating model, the
market line, players to watch, rest and travel), and a sentence is left out when its number is
missing. The one hand-written part is local flavor from data/flavor.json, using only lines that
don't name a winner or loser.

The story goes up once the game is within WINDOW_HOURS of tip, so it lands in the news sitemap
while people are searching for the game. When the game goes final, the recap replaces it at the
same URL.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import json
from pathlib import Path

from . import gamer
from .config import DATA_DIR
from .today import school

WINDOW_HOURS = 36
STORE = DATA_DIR / "previews.json"
ORD = {2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh"}


def due(g: dict[str, Any], now: datetime, hours: float = WINDOW_HOURS) -> bool:
    """True once a game is close enough to tip for its preview story to go up."""
    try:
        tip = datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False
    return not g.get("completed") and tip - now <= timedelta(hours=hours) and tip > now - timedelta(hours=3)


def _named(take: str, by_abbr: dict[str, str]) -> str:
    """'UML +11.5' -> 'UMass Lowell +11.5'."""
    head, _, rest = take.partition(" ")
    return f"{by_abbr[head]} {rest}" if head in by_abbr and rest else take


def _record(key: str | None, standings: dict[str, dict[str, Any]]) -> str:
    s = standings.get(key or "")
    if not s or not (s.get("w") or s.get("l")):
        return ""
    rec = f"{s['w']}-{s['l']}"
    if s.get("cw") or s.get("cl"):
        rec += f", {s['cw']}-{s['cl']} in conference"
    return f" ({rec})"


def _rest_travel(name: str, c: dict[str, Any] | None, city: str = "") -> str | None:
    if not c:
        return None
    bits = []
    rest = c.get("rest_days")
    if rest == 0:
        bits.append("played yesterday")
    elif rest == 1:
        bits.append("is on one day of rest")
    streak = c.get("road_streak") or 0
    if streak >= 2:
        bits.append(f"is playing its {ORD.get(streak, f'{streak}th')} straight road game")
    miles = c.get("miles_in") or 0
    if miles >= 400:
        tz = c.get("tz_shift") or 0
        hop = f"traveled about {miles:,} miles" + (f" to {city}" if city else " for this one")
        if tz:
            hop += f" and crossed {abs(tz)} time zone{'s' if abs(tz) > 1 else ''}"
        bits.append(hop)
    if not bits:
        return None
    return f"{name} " + " and ".join(bits) + "."


def write(g: dict[str, Any], standings: list[dict[str, Any]] | None = None,
          flavor: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Headline and paragraphs for one upcoming game (an entry of data['upcoming'] with mv set)."""
    mv = g.get("mv")
    if not mv:
        return None
    flavor = flavor if flavor is not None else gamer.load_flavor()
    st = {s["key"]: s for s in standings or [] if s.get("key")}
    home, away = g["home"], g["away"]
    hn, an = school(home["name"], home.get("key")), school(away["name"], away.get("key"))
    names = {"home": hn, "away": an}
    by_abbr = {home.get("abbr"): hn, away.get("abbr"): an}
    et = g.get("et") or {}
    try:
        when = datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(gamer.ET).strftime("%A")
    except (KeyError, ValueError):
        when = et.get("weekday", "")
    if when and not et.get("tba") and et.get("time"):
        when += f" at {et['time']} ET"
    nets = [n["name"] for n in (g.get("broadcasts") or [])][:2]
    tv = f" on {' and '.join(nets)}" if nets else ""

    if g.get("neutral_site"):
        where = f" at {g['venue']}" if g.get("venue") else " on a neutral floor"
        lede = f"{an}{_record(away.get('key'), st)} and {hn}{_record(home.get('key'), st)} meet{where} {when}{tv}."
    else:
        where = f" at {g['venue']}" if g.get("venue") else ""
        city = f" in {g['venue_city']}" if g.get("venue_city") else ""
        lede = f"{an}{_record(away.get('key'), st)} visits {hn}{_record(home.get('key'), st)}{where}{city} {when}{tv}."
    lede = " ".join(lede.split()).replace(" .", ".")
    if g.get("conference_game"):
        lede = lede[:-1] + ", a conference game."
    paras = [lede]

    fav = by_abbr.get(mv.get("fav_abbr")) or mv.get("fav_abbr")
    dog = by_abbr.get(mv.get("dog_abbr")) or mv.get("dog_abbr")
    margin = abs(mv.get("spread") or 0)
    model = []
    if fav and margin >= 0.5:
        hi, lo = max(mv["home_pts"], mv["away_pts"]), min(mv["home_pts"], mv["away_pts"])
        pct = max(mv.get("home_win") or 0, mv.get("away_win") or 0)
        art = "an" if str(hi).startswith("8") or hi in (11, 18) or 110 <= hi < 120 else "a"
        model.append(f"Our model makes {fav} a {margin:g}-point favorite, projecting {art} {hi}-{lo} final"
                     + (f", and gives {fav} a {pct}% chance to win." if pct and pct < 100 else "."))
    elif fav:
        model.append("Our model calls it a toss-up.")
    if mv.get("non_d1"):
        md = g.get("model") or {}
        nd = an if (md.get("away") or {}).get("non_d1") else hn
        model.append(f"{nd} is not a Division I team, so books don't post a line and the model's number is rough.")
    mk = mv.get("market") or {}
    if mk.get("spread") is not None:
        s = mk["spread"]
        line = "a pick'em" if s == 0 else f"{hn if s < 0 else an} favored by {abs(s):g}"
        tot = f" with a total of {mk['total']:g}" if mk.get("total") is not None else ""
        model.append(f"The betting market has {line}{tot}.")
        leans = [_named(x["take"], by_abbr) for x in (mv.get("side"), mv.get("ou")) if x and x.get("take")]
        if leans:
            model.append("The model leans " + " and ".join(leans) + ".")
    if model:
        paras.append(" ".join(model))

    watch = []
    for p in sorted((g.get("ptw") or [])[:3], key=lambda p: -(p.get("ppg") or 0)):
        team = by_abbr.get(p.get("abbr"))
        if not p.get("name") or not team:
            continue
        stat = f", {p['ppg']:g} points a game" if p.get("ppg") is not None else ""
        watch.append(f"{p['name']} of {team}{stat}")
    if watch:
        paras.append("Players to watch: " + "; ".join(watch) + ".")

    rt = [s for s in (_rest_travel(an, g.get("travel_away"), g.get("venue_city") or ""),
                       _rest_travel(hn, g.get("travel_home"), g.get("venue_city") or "")) if s]
    if rt:
        paras.append(" ".join(rt))

    flv = [s for s in gamer.flavor_lines(g, flavor, names) if "{" not in s]
    headline = f"{an} vs. {hn} prediction"
    if fav and margin >= 0.5:
        by = int(margin + 0.5)
        headline += f": model has {fav} by {by}" if by else f": model has {fav} by a hair"
    return {"headline": headline, "paragraphs": paras, "flavor": flv,
            "byline": flavor.get("settings", {}).get("byline") or "Hardwood Bricks staff"}


def json_ld(g: dict[str, Any], story: dict[str, Any], published: str, modified: str, site_name: str,
            site_url: str = gamer.SITE_URL) -> dict[str, Any]:
    """The recap's NewsArticle + SportsEvent shape, for the preview story."""
    c = {"g": g, "home": g["home"], "away": g["away"]}
    ld = gamer.json_ld(c, story, published, modified, site_name, site_url=site_url)
    ld["@graph"][0]["@id"] = ld["@graph"][0]["@id"].replace("#gamer", "#preview")
    ld["@graph"][0]["articleSection"] = "Men's college basketball previews"
    return ld


def load(path: Path = STORE) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text()) if path.exists() else {}


def save(saved: dict[str, dict[str, Any]], path: Path = STORE) -> None:
    path.write_text(json.dumps(dict(sorted(saved.items())), indent=0) + "\n")


def remember(saved: dict[str, dict[str, Any]], g: dict[str, Any], story: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Keep the latest version of a preview until tip, then freeze it.

    After the game the recap leads the page and this saved preview sits under it, as we wrote
    it before tip, so the page shows what we said going in.
    """
    gid = g["game_id"]
    old = saved.get(gid) or {}
    tip = datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
    stamp = now.astimezone(tip.tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ")
    if old and now >= tip:
        return old
    saved[gid] = {**story, "published": old.get("published") or stamp, "modified": stamp}
    return saved[gid]
