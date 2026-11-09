"""When games are and where to watch them: Eastern-time labels, day grouping, TV tiers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Linear networks you'd find on a cable/streaming TV package.
NATIONAL_TV = {
    "ESPN", "ESPN2", "ESPNU", "ESPNEWS", "CBSSN", "CBS", "FS1", "FOX", "BTN", "ACCN", "SECN",
    "CW", "NBC", "USA", "TNT", "truTV", "ION",
}
# Watch-it-online services.
STREAMING = {"ESPN+", "Peacock", "B1G+", "ACCNX", "SECN+", "FloSports", "FloHoops", "Paramount+", "Max", "Fox One", "Fubo"}


def tier(name: str) -> str:
    """'tv' for a national linear network, 'stream' for a streaming service, 'local' otherwise."""
    if name in NATIONAL_TV or name.upper() in NATIONAL_TV:
        return "tv"
    if name in STREAMING or name.endswith("+"):
        return "stream"
    return "local"


def watch(game: dict[str, Any]) -> dict[str, Any]:
    """Best way to watch: national TV first, then streaming, then local/regional."""
    seen, nets = set(), []
    for b in game.get("broadcasts") or []:
        if b["name"] in seen:
            continue
        seen.add(b["name"])
        nets.append({"name": b["name"], "tier": tier(b["name"]), "market": b.get("market") or ""})
    order = {"tv": 0, "stream": 1, "local": 2}
    nets.sort(key=lambda n: order[n["tier"]])
    return {"nets": nets, "tier": nets[0]["tier"] if nets else "none"}


def to_et(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)


def et_fields(game: dict[str, Any]) -> dict[str, Any]:
    t = to_et(game["date"])
    tba = bool(game.get("time_tba"))
    return {
        "day_key": t.strftime("%Y-%m-%d"),
        "day_label": f"{t:%a}, {t:%b} {t.day}",
        "weekday": t.strftime("%a"),
        "md": f"{t.month}/{t.day}",
        "time": "TBA" if tba else t.strftime("%-I:%M %p").replace(":00 ", " "),
        "hour": None if tba else t.hour + t.minute / 60,
        "tba": tba,
    }


def mac_side(game: dict[str, Any]) -> str:
    """Short label for the MAC team(s) in a game, e.g. 'AKR' or 'KENT–OHIO'."""
    a, h = game["away"], game["home"]
    if a.get("key") and h.get("key"):
        return f"{a['abbr']}–{h['abbr']}"
    return (h if h.get("key") else a)["abbr"]


def decorate(game: dict[str, Any]) -> dict[str, Any]:
    game["et"] = et_fields(game)
    game["watch"] = watch(game)
    game["mac_label"] = mac_side(game)
    return game


def group_by_day(games: list[dict[str, Any]], start: datetime | None = None, days: int | None = None) -> list[dict[str, Any]]:
    """[{key, label, games}] in date order. With start/days, empty days in the window are kept."""
    buckets: dict[str, dict[str, Any]] = {}
    if start is not None and days is not None:
        d0 = start.astimezone(ET)
        for i in range(days):
            d = d0 + timedelta(days=i)
            k = d.strftime("%Y-%m-%d")
            buckets[k] = {"key": k, "label": f"{d:%a}, {d:%b} {d.day}", "weekday": d.strftime("%a"), "md": f"{d.month}/{d.day}", "games": []}
    for g in sorted(games, key=lambda g: g["date"]):
        e = g["et"]
        buckets.setdefault(e["day_key"], {"key": e["day_key"], "label": e["day_label"], "weekday": e["weekday"], "md": e["md"], "games": []})["games"].append(g)
    return [buckets[k] for k in sorted(buckets)]


def group_by_week(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Monday-start weeks, each holding its days."""
    weeks: dict[str, list[dict[str, Any]]] = {}
    for day in group_by_day(games):
        d = datetime.strptime(day["key"], "%Y-%m-%d")
        monday = d - timedelta(days=d.weekday())
        weeks.setdefault(monday.strftime("%Y-%m-%d"), []).append(day)
    out = []
    for k in sorted(weeks):
        m = datetime.strptime(k, "%Y-%m-%d")
        out.append({"key": k, "label": f"Week of {m:%b} {m.day}", "days": weeks[k],
                    "count": sum(len(d["games"]) for d in weeks[k])})
    return out


def tv_counts(games: list[dict[str, Any]], teams: list[Any]) -> list[dict[str, Any]]:
    """National TV and streaming appearances per MAC team across the season."""
    rows = []
    for t in teams:
        mine = [g for g in games if t.key in (g["home"].get("key"), g["away"].get("key"))]
        nets: dict[str, int] = {}
        for g in mine:
            if g["watch"]["tier"] == "tv":
                n = g["watch"]["nets"][0]["name"]
                nets[n] = nets.get(n, 0) + 1
        rows.append({
            "key": t.key, "short": t.short, "abbr": t.abbr, "espn_id": t.espn_id,
            "tv": sum(1 for g in mine if g["watch"]["tier"] == "tv"),
            "stream": sum(1 for g in mine if g["watch"]["tier"] == "stream"),
            "none": sum(1 for g in mine if g["watch"]["tier"] in ("none", "local")),
            "nets": sorted(nets.items(), key=lambda kv: -kv[1]),
        })
    rows.sort(key=lambda r: (-r["tv"], -r["stream"], r["short"]))
    return rows


def assign_lanes(day_games: list[dict[str, Any]], width_hours: float = 0.9) -> int:
    """Give each game in a day a vertical lane so chips at nearby tip times don't overlap. Returns lane count."""
    ends: list[float] = []
    for g in sorted(day_games, key=lambda g: (g["et"]["hour"] if g["et"]["hour"] is not None else 99, g["mac_label"])):
        h = g["et"]["hour"]
        if h is None:
            g["lane"] = None
            continue
        for i, e in enumerate(ends):
            if e <= h:
                ends[i] = h + width_hours
                g["lane"] = i
                break
        else:
            ends.append(h + width_hours)
            g["lane"] = len(ends) - 1
    return max(1, len(ends))
