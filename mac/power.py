"""Weekly power rankings: the Bricks Index, a frozen Monday snapshot, and the capsules.

The Bricks Index, in plain terms
--------------------------------
1. Recent form. The same opponent- and venue-adjusted rating model as the ratings page,
   fit again with a much shorter memory: a game's weight halves every HALF_LIFE days
   (21, against 90 on the ratings page), so the last three weeks carry the number.
2. Road wins. Every win away from home adds a bonus, scaled by how good the team it
   beat is (season-long rating) and faded with the same 21-day half-life. A neutral-site
   win counts NEUTRAL_SHARE of a true road win. Home wins add nothing beyond the model.

    index = recent net rating + sum over road/neutral wins of ROAD_BONUS * quality * recency

Shown in points per game (per 100 possessions scaled to an average game's pace).

Each week (Monday, 6 a.m. Eastern) the ranking is frozen into data/power/<monday>.json with
a fact sheet per team: record, last week's results, next week's games, top scorers. The
capsules, written by hand from that fact sheet, live in data/power/capsules-<monday>.json
as {team key: text}. The page shows the frozen ranking and any capsules that exist.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import ratings as R
from .config import DATA_DIR

HALF_LIFE = 21.0  # days
ROAD_BONUS = 2.0  # points per 100 for a road win over an average D-I team, at full recency
NEUTRAL_SHARE = 0.5
Q_SCALE = 15.0  # opponent net rating (per 100) that doubles a win's quality
Q_MIN, Q_MAX = 0.3, 2.0
POWER_DIR = DATA_DIR / "power"
ET = ZoneInfo("America/New_York")
FREEZE_HOUR = 6  # Monday, Eastern
FIRST_WEEK = "2026-11-16"  # the first published week; nothing is frozen before it


def quality(opp_net: float) -> float:
    return max(Q_MIN, min(Q_MAX, 1 + opp_net / Q_SCALE))


def _site(row: dict[str, Any], tid: str) -> str:
    if row["neutral"]:
        return "neutral"
    return "home" if row["home"] == tid else "road"


def index(rows: list[dict[str, Any]], season: R.Ratings, prior: R.Ratings | None, now: datetime,
          teams: list[tuple[str, str, str]], p: R.Params = R.Params()) -> list[dict[str, Any]]:
    """The Bricks Index for `teams` [(espn id, key, short)], best first, with rank."""
    fast = R.fit(rows, now, replace(p, half_life=HALF_LIFE), prior)
    pts = fast.tau / 100  # per 100 possessions -> per game
    out = []
    for tid, key, short in teams:
        t = fast.teams.get(tid)
        if not t:
            continue
        bonus, wins = 0.0, []
        for r in rows:
            if r["date"] >= now or tid not in (r["home"], r["away"]):
                continue
            site = _site(r, tid)
            mine, theirs = (r["pts_h"], r["pts_a"]) if r["home"] == tid else (r["pts_a"], r["pts_h"])
            if site == "home" or mine <= theirs:
                continue
            opp = r["away"] if r["home"] == tid else r["home"]
            o = season.team(opp)
            q = quality(o["o"] - o["d"])
            w = max(p.min_weight, 0.5 ** ((now - r["date"]).total_seconds() / 86400 / HALF_LIFE))
            b = ROAD_BONUS * q * w * (NEUTRAL_SHARE if site == "neutral" else 1.0)
            bonus += b
            wins.append({"opp": r["away_name"] if r["home"] == tid else r["home_name"], "site": site,
                         "score": f"{mine}-{theirs}", "date": r["date"].astimezone(ET).strftime("%b %-d"),
                         "bonus": round(b * pts, 2)})
        net = t["o"] - t["d"]
        out.append({"id": tid, "key": key, "short": short, "form": round(net * pts, 1),
                    "road": round(bonus * pts, 1), "score": round((net + bonus) * pts, 1), "road_wins": wins, "scale": pts})
    out.sort(key=lambda x: -x["score"])
    for i, x in enumerate(out, 1):
        x["rank"] = i
    return out


def week_of(now: datetime) -> str:
    """The Monday that names the current ranking week (it turns over Monday at FREEZE_HOUR ET)."""
    et = now.astimezone(ET) - timedelta(hours=FREEZE_HOUR)
    return (et - timedelta(days=et.weekday())).strftime("%Y-%m-%d")


def weeks(d: Path = POWER_DIR) -> list[str]:
    return sorted(f.stem for f in d.glob("20??-??-??.json")) if d.exists() else []


def load(week: str, d: Path = POWER_DIR) -> dict[str, Any] | None:
    f = d / f"{week}.json"
    return json.loads(f.read_text()) if f.exists() else None


def capsules(week: str, d: Path = POWER_DIR) -> dict[str, str]:
    f = d / f"capsules-{week}.json"
    return {k: v for k, v in json.loads(f.read_text()).items() if not k.startswith("_")} if f.exists() else {}


def _game_line(g: dict[str, Any], key: str) -> dict[str, Any]:
    me, op = (g["home"], g["away"]) if g["home"].get("key") == key else (g["away"], g["home"])
    site = "neutral" if g.get("neutral_site") else ("home" if me is g["home"] else "road")
    out = {"date": datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(ET).strftime("%a %b %-d"),
           "opp": op.get("name"), "site": site, "conf": bool(g.get("conference_game"))}
    if g.get("completed") and me.get("score") is not None:
        out["result"] = f"{'W' if me['score'] > op['score'] else 'L'} {me['score']}-{op['score']}"
    return out


def fact_sheet(idx: list[dict[str, Any]], games: list[dict[str, Any]], standings: dict[str, dict[str, Any]],
               profiles: dict[str, list[dict[str, Any]]], week: str, prev: dict[str, Any] | None) -> dict[str, Any]:
    """Everything a capsule may say, frozen for the week."""
    start = datetime.fromisoformat(week).replace(hour=FREEZE_HOUR, tzinfo=ET)
    last = (start - timedelta(days=7), start)
    nxt = (start, start + timedelta(days=7))
    before = {t["key"]: t["rank"] for t in (prev or {}).get("teams", [])}

    def when(g: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(g["date"].replace("Z", "+00:00"))

    teams = []
    for t in idx:
        key = t["key"]
        mine = [g for g in games if key in (g["home"].get("key"), g["away"].get("key"))]
        rec = standings.get(key, {})
        scorers = sorted((pl for pl in profiles.get(key, []) if (pl.get("season") or {}).get("gp")),
                         key=lambda pl: -pl["season"]["per_game"]["pts"])[:3]
        teams.append({
            **{k: t[k] for k in ("key", "short", "rank", "score", "form", "road", "road_wins")},
            "prev_rank": before.get(key),
            "record": f"{rec.get('w', 0)}-{rec.get('l', 0)}", "conf_record": f"{rec.get('cw', 0)}-{rec.get('cl', 0)}",
            "streak": rec.get("streak"),
            "last_week": [_game_line(g, key) for g in sorted(mine, key=when) if g.get("completed") and last[0] <= when(g) < last[1]],
            "next_week": [_game_line(g, key) for g in sorted(mine, key=when) if not g.get("completed") and nxt[0] <= when(g) < nxt[1]],
            "top_scorers": [{"name": pl["name"], "class": pl.get("class_name"), "pos": pl.get("position"),
                             "ppg": pl["season"]["per_game"]["pts"], "rpg": pl["season"]["per_game"]["reb"],
                             "apg": pl["season"]["per_game"]["ast"], "gp": pl["season"]["gp"]} for pl in scorers],
        })
    return {"week": week, "frozen_at": datetime.now(ET).isoformat(timespec="minutes"),
            "method": {"half_life_days": HALF_LIFE, "road_bonus_pts": round(ROAD_BONUS * (idx[0]["scale"] if idx else 0.68), 2),
                       "neutral_share": NEUTRAL_SHARE},
            "teams": teams}


def freeze(idx: list[dict[str, Any]], games: list[dict[str, Any]], standings: dict[str, dict[str, Any]],
           profiles: dict[str, list[dict[str, Any]]], now: datetime, d: Path = POWER_DIR) -> str:
    """Write this week's snapshot once; later builds in the same week leave it alone."""
    week = week_of(now)
    f = d / f"{week}.json"
    if not f.exists() and idx and week >= FIRST_WEEK:
        prior_weeks = [w for w in weeks(d) if w < week]
        prev = load(prior_weeks[-1], d) if prior_weeks else None
        d.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(fact_sheet(idx, games, standings, profiles, week, prev), indent=1) + "\n")
    return week
