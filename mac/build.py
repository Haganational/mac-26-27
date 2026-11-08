"""Render the static dashboard into site/: index.html plus one page per team."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import analysis, players
from .config import BY_KEY, SEASON_LABEL, SITE_DIR, TEAMS, TEMPLATES_DIR
from .espn import load_schedule
from .odds import load_all_rows
from .rosters import load_boxscores


def espn_lines_by_game() -> dict[str, dict[str, Any]]:
    """DraftKings line ESPN carried for finished games, keyed by ESPN game id."""
    return {b["game_id"]: b["espn_line"] for b in load_boxscores() if b.get("espn_line")}


def poll_rank_by_key() -> dict[str, int]:
    league = players.load_league_research()
    by_short = {t.short: t.key for t in TEAMS}
    out: dict[str, int] = {}
    for row in league.get("preseason_poll", []) or []:
        key = by_short.get(row.get("team", ""))
        if key and row.get("rank"):
            out[key] = row["rank"]
    return out


def dashboard_data(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    schedule = load_schedule()
    games = schedule["games"]
    history = analysis.line_history(load_all_rows())
    espn_lines = espn_lines_by_game()
    recent = analysis.recent_results(games, history, now)
    for g in recent:  # fall back to ESPN's DraftKings number when we have no snapshot
        if g["closing_spread"] is None and g["game_id"] in espn_lines:
            g["closing_spread"] = espn_lines[g["game_id"]]["home_spread"]
            g["closing_source"] = "espn"
            if g["closing_spread"] is not None:
                diff = g["margin"] + g["closing_spread"]
                g["ats_cover"] = "push" if diff == 0 else ("home" if diff > 0 else "away")
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "schedule_fetched_at": schedule.get("fetched_at"),
        "season": SEASON_LABEL,
        "teams": [t.__dict__ for t in TEAMS],
        "espn_ids": {t.key: t.espn_id for t in TEAMS},
        "poll_rank": poll_rank_by_key(),
        "league": players.load_league_research(),
        "standings": analysis.standings(games),
        "upcoming": analysis.upcoming(games, history, now),
        "recent": recent,
        "posting": analysis.posting_stats(history),
        "history": list(history.values()),
        "counts": {
            "games": len(games),
            "completed": sum(1 for g in games if g["completed"]),
            "events_with_lines": len(history),
            "snapshots": sum(len(h["snapshots"]) for h in history.values()),
        },
    }


def team_games(team_key: str, games: list[dict[str, Any]], history: dict[str, dict[str, Any]], espn_lines: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    mapping = analysis.match_lines_to_games(games, history)
    out = []
    for g in games:
        if team_key not in (g["home"]["key"], g["away"]["key"]):
            continue
        is_home = g["home"]["key"] == team_key
        own, opp = (g["home"], g["away"]) if is_home else (g["away"], g["home"])
        home_spread = None
        ev = history.get(mapping.get(g["game_id"], ""))
        if ev and ev["latest"]["spread"] is not None:
            home_spread = ev["latest"]["spread"]
        elif g["game_id"] in espn_lines:
            home_spread = espn_lines[g["game_id"]]["home_spread"]
        team_spread = home_spread if is_home else (-home_spread if home_spread is not None else None)
        ats = None
        if g["completed"] and team_spread is not None and own["score"] is not None:
            diff = (own["score"] - opp["score"]) + team_spread
            ats = "push" if diff == 0 else ("cover" if diff > 0 else "miss")
        out.append({
            **g,
            "is_home": is_home,
            "opp_name": opp["name"],
            "opp_key": opp["key"],
            "own_score": own["score"],
            "opp_score": opp["score"],
            "won": (own["score"] or 0) > (opp["score"] or 0) if g["completed"] else None,
            "team_spread": team_spread,
            "ats": ats,
        })
    return out


def render_site() -> str:
    data = dashboard_data()
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "teams").mkdir(exist_ok=True)

    index = env.get_template("index.html")
    (SITE_DIR / "index.html").write_text(index.render(d=data, data_json=json.dumps(data)))
    (SITE_DIR / "data.json").write_text(json.dumps(data))
    (SITE_DIR / ".nojekyll").write_text("")

    games = load_schedule()["games"]
    history = analysis.line_history(load_all_rows())
    espn_lines = espn_lines_by_game()
    profiles = players.build_profiles(games)
    standings = {r["key"]: r for r in data["standings"]}
    team_tpl = env.get_template("team.html")
    for team in TEAMS:
        html = team_tpl.render(
            d=data,
            team=team,
            rec=standings[team.key],
            poll_rank=data["poll_rank"].get(team.key),
            ctx=players.team_context(team.key),
            profiles=profiles[team.key],
            others=players.coverage_not_on_roster(team.key, profiles[team.key]),
            games=team_games(team.key, games, history, espn_lines),
        )
        (SITE_DIR / "teams" / f"{team.key}.html").write_text(html)
    (SITE_DIR / "players.json").write_text(json.dumps(profiles))

    static = TEMPLATES_DIR / "static"
    if static.exists():
        shutil.copytree(static, SITE_DIR / "static", dirs_exist_ok=True)
    return str(SITE_DIR / "index.html")
