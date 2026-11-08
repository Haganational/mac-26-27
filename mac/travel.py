"""Travel: geocode venues, then work out each team's itinerary, miles and rest.

Venue coordinates are cached in data/venues.json (committed) keyed by
"City|ST". New cities are geocoded offline with geonamescache (largest US
city with that name in that state); a few places it does not know live in
OVERRIDES.

Travel model (an estimate, not a flight log):
- Each team starts the season at its home arena.
- Between two road/neutral games the team stays on the road only if the second
  game is within ROAD_TRIP_DAYS days and stopping at home would add more than
  DETOUR_RATIO to the direct distance; otherwise it goes home in between
  (a bus back to campus that is on the way costs almost nothing extra).
- Home games after a road game count the trip home.
- Distances are great-circle miles. Time zones come from the city's IANA zone.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .config import BY_KEY, DATA_DIR, TEAMS

VENUES_PATH = DATA_DIR / "venues.json"
ROAD_TRIP_DAYS = 4
DETOUR_RATIO = 1.25

# Places geonamescache cannot resolve from the ESPN city/state strings.
OVERRIDES: dict[str, dict[str, Any]] = {
    "Cancun|Mexico": {"lat": 21.1619, "lon": -86.8515, "tz": "America/Cancun"},
    "Moon Township|PA": {"lat": 40.5223, "lon": -80.2128, "tz": "America/New_York"},
    "Paradise Island|Bahamas": {"lat": 25.0833, "lon": -77.3167, "tz": "America/Nassau"},
    "Nassau|Bahamas": {"lat": 25.0480, "lon": -77.3554, "tz": "America/Nassau"},
}


def venue_key(city: str | None, state: str | None) -> str:
    return f"{city or ''}|{state or ''}"


def load_venues() -> dict[str, dict[str, Any]]:
    if VENUES_PATH.exists():
        return json.loads(VENUES_PATH.read_text())
    return {}


def geocode_missing(games: list[dict[str, Any]]) -> dict[str, Any]:
    """Fill data/venues.json for any city in the schedule we have not placed yet."""
    venues = load_venues()
    wanted = {venue_key(g["venue_city"], g["venue_state"]) for g in games if g.get("venue_city")}
    missing = sorted(k for k in wanted if k not in venues)
    if not missing:
        return {"added": 0, "unresolved": []}
    index: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        import geonamescache  # optional; only needed when a new city appears

        for c in geonamescache.GeonamesCache(min_city_population=500).get_cities().values():
            if c["countrycode"] != "US":
                continue
            k = (c["name"].lower(), c["admin1code"])
            if k not in index or c["population"] > index[k]["population"]:
                index[k] = c
    except ImportError:
        pass
    added, unresolved = 0, []
    for k in missing:
        if k in OVERRIDES:
            venues[k] = {**OVERRIDES[k], "source": "override"}
            added += 1
            continue
        city, state = k.split("|", 1)
        hit = index.get((city.lower(), state))
        if hit:
            venues[k] = {"lat": hit["latitude"], "lon": hit["longitude"], "tz": hit["timezone"], "source": "geonames"}
            added += 1
        else:
            unresolved.append(k)
    VENUES_PATH.write_text(json.dumps(dict(sorted(venues.items())), indent=1))
    return {"added": added, "unresolved": unresolved}


def miles(a: dict[str, Any], b: dict[str, Any]) -> float:
    r = 3958.8
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def utc_offset_hours(tz: str | None, when: datetime) -> float | None:
    if not tz:
        return None
    try:
        return ZoneInfo(tz).utcoffset(when.replace(tzinfo=None)).total_seconds() / 3600
    except Exception:  # noqa: BLE001 - unknown zone name
        return None


def _parse(d: str) -> datetime:
    return datetime.fromisoformat(d.replace("Z", "+00:00"))


def home_base(team_key: str, games: list[dict[str, Any]], venues: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """The team's home arena: the most common venue among its non-neutral home games."""
    counts: dict[tuple[str, str], int] = {}
    for g in games:
        if g["home"]["key"] == team_key and not g["neutral_site"]:
            k = (g["venue"], venue_key(g["venue_city"], g["venue_state"]))
            counts[k] = counts.get(k, 0) + 1
    if not counts:
        return None
    (arena, vk), _ = max(counts.items(), key=lambda kv: kv[1])
    v = venues.get(vk)
    if not v:
        return None
    city, state = vk.split("|", 1)
    return {"arena": arena, "city": city, "state": state, **v}


def itinerary(team_key: str, games: list[dict[str, Any]], venues: dict[str, dict[str, Any]]) -> dict[str, Any]:
    team = BY_KEY[team_key]
    base = home_base(team_key, games, venues)
    mine = sorted((g for g in games if team_key in (g["home"]["key"], g["away"]["key"])), key=lambda g: g["date"])
    legs: list[dict[str, Any]] = []
    where = base
    prev_date: datetime | None = None
    prev_away = False
    streak_road = 0
    home_tz = ZoneInfo((base or {}).get("tz") or "America/New_York")
    for g in mine:
        # Calendar days in the team's home zone: a 7pm ET tip is 00:00Z the next day.
        when = _parse(g["date"]).astimezone(home_tz)
        is_home = g["home"]["key"] == team_key and not g["neutral_site"]
        loc_key = venue_key(g["venue_city"], g["venue_state"])
        loc = base if is_home else venues.get(loc_key)
        rest = (when.date() - prev_date.date()).days - 1 if prev_date else None
        travel = 0.0
        via_home = False
        if loc and where and base:
            if is_home:
                travel = miles(where, base)
            else:
                direct = miles(where, loc)
                detour = miles(where, base) + miles(base, loc)
                stay_out = (
                    prev_away and prev_date is not None
                    and (when.date() - prev_date.date()).days <= ROAD_TRIP_DAYS
                    and detour > DETOUR_RATIO * max(direct, 1.0)
                )
                if stay_out:
                    travel = direct
                else:
                    via_home = where is not base and prev_away
                    travel = detour if via_home else miles(base, loc)
        away = not is_home
        streak_road = (1 if via_home else streak_road + 1) if away else 0
        tz_shift = None
        if loc and base:
            a, b = utc_offset_hours(base.get("tz"), when), utc_offset_hours(loc.get("tz"), when)
            if a is not None and b is not None:
                tz_shift = b - a
        own, opp = (g["home"], g["away"]) if g["home"]["key"] == team_key else (g["away"], g["home"])
        legs.append({
            "game_id": g["game_id"],
            "date": g["date"],
            "opponent": opp["name"],
            "opp_key": opp["key"],
            "site": "home" if is_home else ("neutral" if g["neutral_site"] else "away"),
            "venue": g["venue"],
            "city": g["venue_city"],
            "state": g["venue_state"],
            "lat": loc["lat"] if loc else None,
            "lon": loc["lon"] if loc else None,
            "miles_in": round(travel),
            "via_home": via_home,
            "miles_from_home": round(miles(base, loc)) if (loc and base) else None,
            "rest_days": rest,
            "road_streak": streak_road,
            "tz_shift": tz_shift,
            "conference_game": g["conference_game"],
            "completed": g["completed"],
            "result": (("W" if (own["score"] or 0) > (opp["score"] or 0) else "L") + f" {own['score']}-{opp['score']}") if g["completed"] else None,
        })
        if loc:
            where = loc
        prev_date = when
        prev_away = away
    # Count the trip home after the last road game.
    tail = round(miles(where, base)) if (where and base and where is not base) else 0
    done = [l for l in legs if l["completed"]]
    trips = _road_trips(legs, base)
    return {
        "team_key": team_key,
        "team": team.short,
        "abbr": team.abbr,
        "espn_id": team.espn_id,
        "base": base,
        "legs": legs,
        "totals": {
            "miles": sum(l["miles_in"] for l in legs) + tail,
            "miles_to_date": sum(l["miles_in"] for l in done),
            "road_games": sum(1 for l in legs if l["site"] == "away"),
            "neutral_games": sum(1 for l in legs if l["site"] == "neutral"),
            "home_games": sum(1 for l in legs if l["site"] == "home"),
            "farthest": max((l for l in legs if l["miles_from_home"] is not None), key=lambda l: l["miles_from_home"], default=None),
            "longest_trip": max(trips, key=lambda t: t["miles"], default=None),
            "short_rest_games": sum(1 for l in legs if l["rest_days"] is not None and l["rest_days"] <= 1),
            "tz_games": sum(1 for l in legs if l["tz_shift"]),
        },
        "trips": trips,
    }


def _road_trips(legs: list[dict[str, Any]], base: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Group consecutive away/neutral games played without a stop at home."""
    trips: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    for l in legs:
        if l["site"] == "home":
            if cur:
                trips.append(cur)
            cur = []
            continue
        if cur and l["via_home"]:  # went home in between: a new trip starts
            trips.append(cur)
            cur = []
        cur.append(l)
    if cur:
        trips.append(cur)
    out = []
    for t in trips:
        pts = [base] + [l for l in t if l["lat"] is not None] + [base]
        dist = sum(miles(a, b) for a, b in zip(pts, pts[1:])) if base else 0.0
        out.append({
            "start": t[0]["date"],
            "end": t[-1]["date"],
            "games": len(t),
            "stops": [l["city"] for l in t],
            "miles": round(dist),  # out, between stops, and back home
        })
    return out


def all_itineraries(games: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    venues = load_venues()
    return {t.key: itinerary(t.key, games, venues) for t in TEAMS}


def game_context(itins: dict[str, dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """(game_id, team_key) -> that team's leg, for rest/travel columns elsewhere."""
    return {(l["game_id"], k): l for k, it in itins.items() for l in it["legs"]}
