"""Player profiles: roster bio + game log + season averages + what coverage says."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from typing import Any

from .config import BY_ESPN_ID, DATA_DIR, TEAMS
from .rosters import load_boxscores, load_rosters

RESEARCH_DIR = DATA_DIR / "research"

COUNTING = ["min", "pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "reb", "oreb", "dreb", "ast", "to", "stl", "blk", "pf"]


def norm_name(name: str) -> str:
    """Lowercase ASCII letters only, so 'Jaylan Ouwinga' matches 'Jaylan Ouwinga Jr.' loosely."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", s.lower())
    return re.sub(r"[^a-z]", "", s)


def load_research(team_key: str) -> dict[str, Any]:
    path = RESEARCH_DIR / f"{team_key}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def load_league_research() -> dict[str, Any]:
    path = RESEARCH_DIR / "league.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _pct(made: int, att: int) -> float | None:
    return round(100 * made / att, 1) if att else None


def season_line(games: list[dict[str, Any]]) -> dict[str, Any]:
    played = [g for g in games if not g["dnp"] and g.get("min") is not None]
    gp = len(played)
    tot = {k: sum((g.get(k) or 0) for g in played) for k in COUNTING}
    starts = sum(1 for g in played if g["starter"])
    per = {k: (round(tot[k] / gp, 1) if gp else None) for k in ("min", "pts", "reb", "ast", "to", "stl", "blk")}
    return {
        "gp": gp,
        "gs": starts,
        "totals": tot,
        "per_game": per,
        "fg_pct": _pct(tot["fgm"], tot["fga"]),
        "tp_pct": _pct(tot["tpm"], tot["tpa"]),
        "ft_pct": _pct(tot["ftm"], tot["fta"]),
        "efg_pct": round(100 * (tot["fgm"] + 0.5 * tot["tpm"]) / tot["fga"], 1) if tot["fga"] else None,
        "ts_pct": round(100 * tot["pts"] / (2 * (tot["fga"] + 0.44 * tot["fta"])), 1) if (tot["fga"] or tot["fta"]) else None,
        "usage_proxy": round((tot["fga"] + 0.44 * tot["fta"] + tot["to"]) / tot["min"] * 40, 1) if tot["min"] else None,
    }


def build_profiles(schedule_games: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Return {team_key: [player profile, ...]} sorted by minutes per game."""
    game_meta = {g["game_id"]: g for g in schedule_games}
    logs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for box in load_boxscores():
        meta = game_meta.get(box["game_id"], {})
        for p in box["players"]:
            team = BY_ESPN_ID.get(p["team_espn_id"])
            if team is None:
                continue
            # Work out opponent and result from the box's team list.
            others = [t for t in box["teams"] if t["espn_id"] != p["team_espn_id"]]
            opp = others[0] if others else {}
            own = next((t for t in box["teams"] if t["espn_id"] == p["team_espn_id"]), {})
            home_side = meta.get("home", {}).get("espn_id") == p["team_espn_id"]
            own_score = meta.get("home" if home_side else "away", {}).get("score")
            opp_score = meta.get("away" if home_side else "home", {}).get("score")
            logs[p["espn_id"]].append({
                **{k: p.get(k) for k in ["starter", "dnp"] + COUNTING},
                "game_id": box["game_id"],
                "date": meta.get("date") or box.get("date"),
                "opponent": opp.get("name"),
                "opponent_abbr": opp.get("abbr"),
                "home": home_side,
                "result": (("W" if (own_score or 0) > (opp_score or 0) else "L") + f" {own_score}-{opp_score}") if own_score is not None else None,
            })

    rosters = load_rosters()["rosters"]
    out: dict[str, list[dict[str, Any]]] = {}
    for team in TEAMS:
        research = load_research(team.key)
        coverage = {}
        for p in research.get("players_in_coverage", []):
            name = p.get("name", "")
            coverage[norm_name(name)] = p
            m = re.search(r'["“](.+?)["”]', name)  # Durral "Phat Phat" Brooks -> Phat Phat Brooks
            if m and name.split():
                coverage.setdefault(norm_name(m.group(1) + " " + name.split()[-1]), p)
        claims: dict[str, list[dict[str, str]]] = defaultdict(list)
        for pv in research.get("previews", []):
            for c in pv.get("player_claims", []) or []:
                claims[norm_name(c.get("player", ""))].append({"claim": c.get("claim"), "outlet": pv.get("outlet"), "url": pv.get("url")})

        # Fallback: match on last name when it is unique on both sides (handles nicknames
        # such as 'Durral "Phat Phat" Brooks' vs ESPN's 'Phat Phat Brooks').
        def last(n: str) -> str:
            return norm_name(n.split()[-1]) if n and n.split() else ""
        roster_last: dict[str, list[str]] = defaultdict(list)
        for bio in rosters.get(team.key, []):
            roster_last[last(bio["name"])].append(norm_name(bio["name"]))
        cov_last: dict[str, list[str]] = defaultdict(list)
        for k in coverage:
            cov_last[last(next(p["name"] for p in research.get("players_in_coverage", []) if norm_name(p.get("name", "")) == k))].append(k)
        alias: dict[str, str] = {}
        for ln, roster_keys in roster_last.items():
            if len(roster_keys) == 1 and len(cov_last.get(ln, [])) == 1 and cov_last[ln][0] not in coverage.keys() - set(cov_last[ln]):
                alias[roster_keys[0]] = cov_last[ln][0]

        profiles = []
        seen = set()
        for bio in rosters.get(team.key, []):
            games = sorted(logs.get(bio["espn_id"], []), key=lambda g: g["date"] or "")
            key = norm_name(bio["name"])
            seen.add(bio["espn_id"])
            cov = coverage.get(key) or coverage.get(alias.get(key, ""), {})
            if key not in claims and alias.get(key) in claims:
                claims[key] = claims[alias[key]]
            profiles.append({
                **bio,
                "team_key": team.key,
                "season": season_line(games),
                "game_log": games,
                "coverage_status": cov.get("status"),
                "previous_school": cov.get("previous_school"),
                "coverage_notes": cov.get("notes"),
                "coverage_sources": cov.get("source_urls", []),
                "preview_claims": claims.get(key, []),
            })
        # Players who appeared in a box score but are missing from the roster feed.
        for pid, games in logs.items():
            if pid in seen:
                continue
            if not games or BY_ESPN_ID.get(next((b["team_espn_id"] for box in load_boxscores() for b in box["players"] if b["espn_id"] == pid), "")) is not team:
                continue
            first = games[0]
            profiles.append({
                "espn_id": pid, "name": next((b["name"] for box in load_boxscores() for b in box["players"] if b["espn_id"] == pid), pid),
                "jersey": None, "position": None, "height": None, "weight": None, "class": None, "class_name": None,
                "hometown": None, "headshot": None, "espn_url": None, "injuries": [], "team_key": team.key,
                "season": season_line(games), "game_log": sorted(games, key=lambda g: g["date"] or ""),
                "coverage_status": None, "previous_school": None, "coverage_notes": None, "coverage_sources": [], "preview_claims": [],
            })
        profiles.sort(key=lambda p: (-(p["season"]["per_game"]["min"] or 0), p["name"]))
        out[team.key] = profiles
    return out


def coverage_not_on_roster(team_key: str, profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Players named in coverage who are not on the ESPN roster: departures, redshirts, unverified adds."""
    research = load_research(team_key)
    roster_keys = {norm_name(p["name"]) for p in profiles}
    roster_last = {norm_name(p["name"].split()[-1]) for p in profiles if p["name"]}
    out = []
    for c in research.get("players_in_coverage", []):
        k = norm_name(c.get("name", ""))
        ln = norm_name(c.get("name", "").split()[-1]) if c.get("name") else ""
        if k in roster_keys or (ln in roster_last and c.get("status") not in ("transfer_out", "graduated", "departed")):
            continue
        out.append(c)
    return out


def team_context(team_key: str) -> dict[str, Any]:
    """Coach, sources, previews, storylines and recent news for a team page."""
    r = load_research(team_key)
    return {
        "researched_at": r.get("researched_at"),
        "coach": r.get("coach") or {},
        "sources": r.get("sources", []),
        "previews": r.get("previews", []),
        "storylines": r.get("storylines", []),
        "recent_news": r.get("recent_news", []),
    }
