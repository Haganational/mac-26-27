"""Render the static dashboard into site/: index.html plus one page per team."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import analysis, oddsboard, players, schedule_view, travel
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
    upcoming = [schedule_view.decorate(g) for g in analysis.upcoming(games, history, now)]
    window_days = schedule_view.group_by_day(upcoming, start=now, days=8)
    for day in window_days:
        day["lanes"] = schedule_view.assign_lanes(day["games"])
    hours = [g["et"]["hour"] for g in upcoming if g["et"]["hour"] is not None]
    lo = min([11] + [int(h) for h in hours])
    hi = max([23] + [int(h) + 1 for h in hours])
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_et": now.astimezone(schedule_view.ET).strftime("%a %b %-d, %-I:%M %p ET"),
        "schedule_fetched_at": schedule.get("fetched_at"),
        "season": SEASON_LABEL,
        "teams": [t.__dict__ for t in TEAMS],
        "espn_ids": {t.key: t.espn_id for t in TEAMS},
        "poll_rank": poll_rank_by_key(),
        "league": players.load_league_research(),
        "standings": analysis.standings(games),
        "upcoming": upcoming,
        "days": window_days,
        "hour_range": list(range(lo, hi)),
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
            "odds_event_id": ev["odds_event_id"] if ev else None,
        })
    return out


STAT_ROWS = [
    ("FG", "fieldGoalsMade-fieldGoalsAttempted"), ("FG%", "fieldGoalPct"),
    ("3PT", "threePointFieldGoalsMade-threePointFieldGoalsAttempted"), ("3P%", "threePointFieldGoalPct"),
    ("FT", "freeThrowsMade-freeThrowsAttempted"), ("FT%", "freeThrowPct"),
    ("Rebounds", "totalRebounds"), ("Offensive rebounds", "offensiveRebounds"), ("Defensive rebounds", "defensiveRebounds"),
    ("Assists", "assists"), ("Steals", "steals"), ("Blocks", "blocks"), ("Turnovers", "totalTurnovers"),
    ("Points off turnovers", "turnoverPoints"), ("Fast break points", "fastBreakPoints"), ("Points in paint", "pointsInPaint"),
    ("Fouls", "fouls"), ("Largest lead", "largestLead"),
]


def fmt_spread(v: float | None) -> str:
    return "–" if v is None else ("PK" if v == 0 else f"{v:+.1f}")


def _num(stats: dict[str, Any], key: str) -> float:
    try:
        return float(stats.get(key) or 0)
    except ValueError:
        return 0.0


def possessions(stats: dict[str, Any]) -> float:
    fga = _num({"x": (stats.get("fieldGoalsMade-fieldGoalsAttempted") or "0-0").split("-")[-1]}, "x")
    fta = _num({"x": (stats.get("freeThrowsMade-freeThrowsAttempted") or "0-0").split("-")[-1]}, "x")
    return fga - _num(stats, "offensiveRebounds") + _num(stats, "totalTurnovers") + 0.475 * fta


def game_page_context(g: dict[str, Any], box: dict[str, Any], snap: dict[str, Any] | None, ctx: dict) -> dict[str, Any]:
    sides = {}
    for side in ("home", "away"):
        t = g[side]
        tb = next((x for x in box["teams"] if str(x["espn_id"]) == str(t["espn_id"])), {"stats": {}})
        players_ = [p for p in box["players"] if str(p["team_espn_id"]) == str(t["espn_id"])]
        players_.sort(key=lambda p: (not p["starter"], p["dnp"], -(p.get("min") or 0)))
        poss = possessions(tb["stats"])
        sides[side] = {
            **t,
            "stats": tb["stats"],
            "players": players_,
            "poss": round(poss, 1) if poss else "–",
            "ortg": round(100 * (t["score"] or 0) / poss, 1) if poss else "–",
            "travel": ctx.get((g["game_id"], t["key"])) if t["key"] else None,
        }
    margin = (g["home"]["score"] or 0) - (g["away"]["score"] or 0)
    line = (box.get("espn_line") or {}).get("home_spread")
    if line is None and snap:
        line = snap["latest"]["spread"]
    total = (box.get("espn_line") or {}).get("total")
    if total is None and snap:
        total = snap["latest"]["total"]
    points = (g["home"]["score"] or 0) + (g["away"]["score"] or 0)
    ats = None
    if line is not None:
        diff = margin + line
        ats = "push" if diff == 0 else (f"{g['home']['abbr']} covered" if diff > 0 else f"{g['away']['abbr']} covered")
    total_res = None
    if total is not None:
        total_res = "push" if points == total else ("over" if points > total else "under")
    return {
        "g": g, "box": box, "snap": snap,
        "home": sides["home"], "away": sides["away"],
        "result": {"margin": margin, "ats": ats, "points": points, "total_res": total_res},
        "stat_rows": STAT_ROWS,
    }


def render_site() -> str:
    data = dashboard_data()
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    env.filters["book"] = oddsboard.book_name
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
    itins = travel.all_itineraries(games)
    ctx = travel.game_context(itins)
    mapping = analysis.match_lines_to_games(games, history)
    boxes = {b["game_id"]: b for b in load_boxscores()}
    teamlinks = [{"key": t.key, "short": t.short} for t in TEAMS]

    # Box score pages, one per finished game we have a box for.
    (SITE_DIR / "games").mkdir(exist_ok=True)
    game_tpl = env.get_template("game.html")
    by_id = {g["game_id"]: g for g in games}
    have_box = set()
    for gid, box in boxes.items():
        g = by_id.get(gid)
        if not g or not g["completed"]:
            continue
        snap = history.get(mapping.get(gid, ""))
        html = game_tpl.render(d=data, teamlinks=teamlinks, fmt_spread=fmt_spread, **game_page_context(g, box, snap, ctx))
        (SITE_DIR / "games" / f"{gid}.html").write_text(html)
        have_box.add(gid)

    # TV schedule: every game, by week and day, Eastern time.
    season = [schedule_view.decorate(dict(g)) for g in games]
    for g in season:
        g["box"] = g["game_id"] in have_box
    (SITE_DIR / "tv.html").write_text(env.get_template("tv.html").render(
        d=data, weeks=schedule_view.group_by_week(season), counts=schedule_view.tv_counts(season, TEAMS),
        now_iso=data["generated_at"]))

    # Odds screen: per-book prices, best number, open vs now, movement, model gaps.
    now = datetime.fromisoformat(data["generated_at"])
    line_rows = load_all_rows()
    odds_ctx = oddsboard.page_context(now, games, line_rows, mapping, oddsboard.load_projections(),
                                      decorate=schedule_view.decorate)
    odds_ctx["budget"] = oddsboard.budget(now, line_rows)
    (SITE_DIR / "odds.html").write_text(env.get_template("odds.html").render(
        d=data, o=odds_ctx, fmt_spread=fmt_spread, book_name=oddsboard.book_name))
    data["odds_summary"] = {"games": len(odds_ctx["board"]), "books": len(odds_ctx["books"]), "edges": odds_ctx["edges"],
                            "budget": odds_ctx["budget"]}

    # Travel map.
    board = sorted(itins.values(), key=lambda t: -t["totals"]["miles"])
    for it in itins.values():
        for leg in it["legs"]:
            leg["box"] = leg["game_id"] in have_box
    (SITE_DIR / "travel.html").write_text(env.get_template("travel.html").render(
        d=data, board=board, travel_json=json.dumps(itins).replace("</", "<\\/")))

    # Home page again, now that we know which games have box score pages and travel context.
    for g in data["recent"]:
        g["box"] = g["game_id"] in have_box
    for g in data["upcoming"]:
        g["travel_home"] = ctx.get((g["game_id"], g["home"]["key"])) if g["home"].get("key") else None
        g["travel_away"] = ctx.get((g["game_id"], g["away"]["key"])) if g["away"].get("key") else None
    (SITE_DIR / "index.html").write_text(index.render(d=data, data_json=json.dumps(data).replace("</", "<\\/")))

    for team in TEAMS:
        for p in profiles[team.key]:
            for gl in p.get("game_log", []):
                gl["box"] = gl["game_id"] in have_box
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
            games=[schedule_view.decorate({**tg, "box": tg["game_id"] in have_box, "trav": ctx.get((tg["game_id"], team.key))}) for tg in team_games(team.key, games, history, espn_lines)],
            itin=itins[team.key],
        )
        (SITE_DIR / "teams" / f"{team.key}.html").write_text(html)
    (SITE_DIR / "players.json").write_text(json.dumps(profiles))

    static = TEMPLATES_DIR / "static"
    if static.exists():
        shutil.copytree(static, SITE_DIR / "static", dirs_exist_ok=True)
    return str(SITE_DIR / "index.html")
