"""The game prep sheet: a one-page, printable notes package for radio crews, SIDs and writers.

games/<id>-notes.html for every upcoming game with a preview. Everything on it comes from
data we already publish (schedule, standings, box scores, rosters, the model, the market,
rest and travel). A section is left out when its data is missing. No birthdates or family
details: hometown, class, height and previous school only, as on the player pages.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from . import preview_story
from .gamer import ET


def _when(g: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(g["date"].replace("Z", "+00:00"))


def last_games(key: str, games: list[dict[str, Any]], before: datetime, n: int = 5) -> list[dict[str, Any]]:
    """The team's last n finals before `before`, newest first."""
    done = [g for g in games if g.get("completed") and key in (g["home"].get("key"), g["away"].get("key"))
            and g["home"].get("score") is not None and _when(g) < before]
    out = []
    for g in sorted(done, key=_when, reverse=True)[:n]:
        me, op = (g["home"], g["away"]) if g["home"].get("key") == key else (g["away"], g["home"])
        site = "N" if g.get("neutral_site") else ("vs" if me is g["home"] else "at")
        out.append({"date": _when(g).astimezone(ET).strftime("%-m/%-d"), "site": site, "opp": op.get("name"),
                    "wl": "W" if me["score"] > op["score"] else "L", "score": f"{me['score']}-{op['score']}",
                    "game_id": g["game_id"], "conf": bool(g.get("conference_game"))})
    return out


def meetings(g: dict[str, Any], games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Earlier meetings this season between the same two teams."""
    ids = {g["home"].get("espn_id"), g["away"].get("espn_id")}
    out = []
    for x in sorted(games, key=_when):
        if x["game_id"] == g["game_id"] or not x.get("completed") or {x["home"].get("espn_id"), x["away"].get("espn_id")} != ids:
            continue
        w, l = (x["home"], x["away"]) if x["home"]["score"] > x["away"]["score"] else (x["away"], x["home"])
        out.append({"date": _when(x).astimezone(ET).strftime("%-m/%-d"), "winner": w.get("name"),
                    "score": f"{w['score']}-{l['score']}", "where": x.get("venue_city") or ""})
    return out


def roster(plist: list[dict[str, Any]], n: int = 10) -> list[dict[str, Any]]:
    """Players who have played, by minutes per game, with the numbers a broadcaster reads on air."""
    out = []
    for p in plist:
        s = p.get("season") or {}
        if not s.get("gp"):
            continue
        pg = s.get("per_game") or {}
        last = (p.get("game_log") or [])[-1:] or [{}]
        out.append({"name": p["name"], "jersey": p.get("jersey"), "pos": p.get("position"), "cl": p.get("class"),
                    "ht": p.get("height"), "hometown": p.get("hometown"), "prev": p.get("previous_school"),
                    "gp": s["gp"], "gs": s.get("gs"), "min": pg.get("min"), "pts": pg.get("pts"), "reb": pg.get("reb"),
                    "ast": pg.get("ast"), "fg": s.get("fg_pct"), "tp": s.get("tp_pct"), "ft": s.get("ft_pct"),
                    "last": f"{last[0].get('pts')} pts vs {last[0].get('opponent_abbr')}" if last[0].get("pts") is not None else "",
                    "espn_id": p.get("espn_id")})
    out.sort(key=lambda r: -(r["min"] or 0))
    return out[:n]


def side(g: dict[str, Any], which: str, games: list[dict[str, Any]], standings: dict[str, dict[str, Any]],
         profiles: dict[str, list[dict[str, Any]]], coach_for, opp: dict[str, Any] | None = None) -> dict[str, Any]:
    t = g[which]
    key = t.get("key")
    rt = ((g.get("model") or {}).get(which) or {}).get("rt") or {}
    out: dict[str, Any] = {"name": t.get("name"), "abbr": t.get("abbr"), "key": key, "espn_id": t.get("espn_id"), "ours": bool(key), "rt": rt}
    if not key:
        f = (opp or {}).get(t.get("espn_id"))
        if f:
            out.update({"record": f["record"], "ppg": f["ppg"], "opp_ppg": f["opp_ppg"],
                        "last5": [{**x, "date": datetime.fromisoformat(x["date"]).strftime("%-m/%-d"), "conf": False} for x in f["last"]]})
        return out
    rec = standings.get(key) or {}
    out.update({
        "record": f"{rec.get('w', 0)}-{rec.get('l', 0)}", "conf": f"{rec.get('cw', 0)}-{rec.get('cl', 0)}",
        "streak": rec.get("streak"), "ppg": round(rec["pf"] / rec["games"], 1) if rec.get("games") else None,
        "opp_ppg": round(rec["pa"] / rec["games"], 1) if rec.get("games") else None,
        "last5": last_games(key, games, _when(g)), "roster": roster(profiles.get(key, [])),
        "coach": (coach_for(key) or {}).get("name"),
        "travel": preview_story._rest_travel(t.get("name", ""), g.get(f"travel_{which}"), g.get("venue_city") or ""),
    })
    return out


def context(g: dict[str, Any], games: list[dict[str, Any]], standings: dict[str, dict[str, Any]],
            profiles: dict[str, list[dict[str, Any]]], coach_for, opp: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"away": side(g, "away", games, standings, profiles, coach_for, opp),
            "home": side(g, "home", games, standings, profiles, coach_for, opp),
            "meetings": meetings(g, games),
            "tv": ", ".join(b["name"] for b in (g.get("broadcasts") or [])[:3])}
