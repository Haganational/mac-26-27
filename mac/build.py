"""Render the static dashboard into site/: index.html plus one page per team."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import access, analysis, model, news, notes, oddsboard, players, schedule_view, site_chrome, today, travel, viz
from .config import BY_KEY, DATA_DIR, SEASON_LABEL, SITE_DIR, SITE_NOINDEX, SITE_URL, TEAMS, TEMPLATES_DIR
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
    line_rows = load_all_rows()
    history = analysis.line_history(line_rows)
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
        "posting": {**analysis.posting_stats(history), "by_book": [{**b, "name": oddsboard.book_name(b["book"])} for b in analysis.book_posting(line_rows)]},
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


def model_page_context(m: dict[str, Any]) -> dict[str, Any]:
    """Extra shapes the ratings page wants: scatter points and axis ranges, Eastern tip times."""
    pts = [(t["adj_o"], t["adj_d"], t["short"]) for t in m.get("all_teams", [])]
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        lo_x, hi_x = 5 * int(min(xs) // 5), 5 * int(max(xs) // 5 + 1)
        lo_y, hi_y = 5 * int(min(ys) // 5), 5 * int(max(ys) // 5 + 1)
    else:
        lo_x, hi_x, lo_y, hi_y = 90, 125, 90, 125
    m["scatter"] = {
        "d1": [[round(p[0], 1), round(p[1], 1), p[2]] for p in pts],
        "x": [lo_x, hi_x], "y": [lo_y, hi_y],  # y runs low (good defense) at the top
        "xticks": list(range(lo_x, hi_x + 1, 5)), "yticks": list(range(lo_y, hi_y + 1, 5)),
    }
    for u in m["upcoming"]:
        e = schedule_view.et_fields(u)
        u["et"] = f"{e['weekday']} {e['md']} {e['time']}"
    return m

def follow_context() -> dict[str, Any]:
    """Team, coach, player and writer accounts to follow on X, from data/x_follow.json."""
    path = DATA_DIR / "x_follow.json"
    x = json.loads(path.read_text()) if path.exists() else {"teams": {}, "league": [], "league_media": []}
    teams, handles, with_handle, roster = [], set(), 0, 0
    for team in TEAMS:
        t = x["teams"].get(team.key, {"team_accounts": [], "coaches": [], "players": [], "media": [], "roster_url": ""})
        own = list(t["team_accounts"]) + [c["handle"] for c in t["coaches"]] + [p["handle"] for p in t["players"] if p.get("handle")]
        handles.update(h.lower() for h in own)
        with_handle += sum(1 for p in t["players"] if p.get("handle"))
        roster += len(t["players"])
        writers = [{"name": w, "outlet": m["name"]} for m in t.get("media", []) for w in m.get("writers", []) if w]
        teams.append({**t, "key": team.key, "short": team.short, "name": team.name, "espn_id": team.espn_id,
                      "n_handles": len(set(h.lower() for h in own)), "writers": writers})
    handles.update(a["handle"].lower() for a in x.get("league", []))
    return {"x": x, "teams": teams, "counts": {"handles": len(handles), "players": with_handle, "roster": roster}}


def _name_key(name: str) -> str:
    n = re.sub(r"[^a-z ]", "", (name or "").lower())
    return " ".join(w for w in n.split() if w not in ("jr", "sr", "ii", "iii", "iv"))


def attach_x_handles(profiles: dict[str, list[dict[str, Any]]]) -> None:
    """Copy each player's X handle from data/x_follow.json onto his profile (matched by name, then jersey)."""
    path = DATA_DIR / "x_follow.json"
    if not path.exists():
        return
    teams = json.loads(path.read_text()).get("teams", {})
    for key, plist in profiles.items():
        listed = [p for p in teams.get(key, {}).get("players", []) if p.get("handle")]
        by_name = {_name_key(p["name"]): p["handle"] for p in listed}
        by_jersey = {str(p.get("jersey")): p["handle"] for p in listed if p.get("jersey")}
        for p in plist:
            h = by_name.get(_name_key(p.get("name", "")))
            if not h and p.get("jersey") and str(p["jersey"]) in by_jersey:
                cand = next(x for x in listed if str(x.get("jersey")) == str(p["jersey"]))
                if _name_key(cand["name"]).split()[-1:] == _name_key(p.get("name", "")).split()[-1:]:
                    h = cand["handle"]
            if h:
                p["x_handle"] = h.lstrip("@")


def render_site() -> str:
    data = dashboard_data()
    now = datetime.fromisoformat(data["generated_at"])
    sched = load_schedule()["games"]
    game_teams = {g["game_id"]: [t for t in (g["home"].get("key"), g["away"].get("key")) if t] for g in sched}
    dispatches = notes.load(game_teams=game_teams)  # Fieldhouse Notes: filed with games, teams, players and in the feed
    data["news"] = notes.merge_feed(news.view(now, limit=30), dispatches, now, limit=30)
    try:
        m = model.build_model(now, log=True)
    except Exception as exc:  # noqa: BLE001 - the rest of the site must still publish
        print(f"model: skipped ({exc!r})")
        m = None
    if m:
        proj = {u["game_id"]: u for u in m["upcoming"]}
        for g in data["upcoming"]:
            g["model"] = proj.get(g["game_id"])
        data["model_mac"] = {t["key"]: {k: t[k] for k in ("adj_o", "adj_d", "adj_em", "adj_t", "rk_adj_em", "sos", "net_pts")} for t in m["mac"]}
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    env.filters["book"] = oddsboard.book_name
    env.globals.update(site_url=SITE_URL, noindex=SITE_NOINDEX, season=SEASON_LABEL, brand=site_chrome.BRAND, site_name=site_chrome.SITE_NAME, floor=site_chrome.FLOOR, twitch=site_chrome.TWITCH_CHANNEL, youtube=site_chrome.YOUTUBE_CHANNEL, youtube_shorts=('UUSH' + site_chrome.YOUTUBE_CHANNEL_ID[2:]) if site_chrome.YOUTUBE_CHANNEL_ID else '', house_ad=site_chrome.AD, tip=site_chrome.TIP, asset_v=hashlib.sha1((TEMPLATES_DIR / 'static' / 'site.css').read_bytes() + (TEMPLATES_DIR / 'static' / 'nav.js').read_bytes()).hexdigest()[:8], notes_repo=notes.REPO, notes_kinds=notes.KINDS, notes_color=notes.COLOR,
                       nav_pages=site_chrome.PAGES, nav_teams=site_chrome.nav_teams())
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
    attach_x_handles(profiles)
    standings = {r["key"]: r for r in data["standings"]}
    itins = travel.all_itineraries(games)
    ctx = travel.game_context(itins)
    mapping = analysis.match_lines_to_games(games, history)
    boxes = {b["game_id"]: b for b in load_boxscores()}
    teamlinks = [{"key": t.key, "short": t.short} for t in TEAMS]

    notes_by_game = notes.by_game(dispatches)
    notes_by_player = notes.by_player(dispatches)

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
        html = game_tpl.render(d=data, teamlinks=teamlinks, fmt_spread=fmt_spread, game_notes=notes_by_game.get(gid, []),
                               **game_page_context(g, box, snap, ctx))
        (SITE_DIR / "games" / f"{gid}.html").write_text(html)
        have_box.add(gid)

    # Where a game name links: its box score once played, otherwise its odds while a line is up.
    game_href = {g["game_id"]: f"odds.html#ev{g['line']['odds_event_id']}" for g in data["upcoming"]
                 if g.get("line") and g["line"].get("odds_event_id")}
    game_href.update({gid: f"games/{gid}.html" for gid in have_box})
    env.globals["game_href"] = game_href

    # TV schedule: every game, by week and day, Eastern time.
    season = [schedule_view.decorate(dict(g)) for g in games]
    for g in season:
        g["box"] = g["game_id"] in have_box

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
    data["best_play"] = odds_ctx["best_play"]

    # News ticker: the full feed, with team filter chips and feed health.
    full_news = notes.merge_feed(news.view(now, limit=400), dispatches, now)
    (SITE_DIR / "news.html").write_text(env.get_template("news.html").render(
        d=data, n=full_news, host=news.host))

    # Follow-on-X checklist.
    (SITE_DIR / "follow.html").write_text(env.get_template("follow.html").render(d=data, **follow_context()))

    # About / masthead: who we are, coverage, cadence, standards (for readers and press offices).
    mh_path = DATA_DIR / "masthead.json"
    masthead = json.loads(mh_path.read_text()) if mh_path.exists() else {}
    (SITE_DIR / "about.html").write_text(env.get_template("about.html").render(d=data, mh=masthead))

    # MAC90: the 90-second daily script, built only from our own data.
    t = today.build(now, data["recent"], data["upcoming"], boxes, data["standings"])
    (SITE_DIR / "mac90.json").write_text(json.dumps(t))
    (SITE_DIR / "mac90.html").write_text(env.get_template("mac90.html").render(d=data, t=t, game_href=game_href))

    # Data Visualized: one posting clock per game.
    (SITE_DIR / "viz.html").write_text(env.get_template("viz.html").render(
        d=data, v=viz.page_context(analysis.posting_clocks(load_all_rows(), now))))

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
    # Schedule & TV: this week's grid plus every game, with lines, model and rest/travel for the next 8 days.
    (SITE_DIR / "tv.html").write_text(env.get_template("tv.html").render(
        d=data, weeks=schedule_view.group_by_week(season), counts=schedule_view.tv_counts(season, TEAMS),
        now_iso=data["generated_at"], notes_by_game=notes_by_game))

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
            team_news=notes.merge_feed(news.view(now, team.key, limit=12), dispatches, now, root="../", team_key=team.key, limit=12),
            team_notes=notes.for_team(dispatches, team.key), player_notes=notes_by_player,
            rating=next((t for t in m["mac"] if t["key"] == team.key), None) if m else None,
            proj={u["game_id"]: u for u in m["upcoming"]} if m else {},
            prate={pl["id"]: pl for pl in ((m.get("players") or {}).get("players") or [])} if m else {},
        )
        (SITE_DIR / "teams" / f"{team.key}.html").write_text(html)
    (SITE_DIR / "players.json").write_text(json.dumps(profiles))

    if m:
        (SITE_DIR / "ratings.html").write_text(env.get_template("ratings.html").render(d=data, m=model_page_context(m)))
        if m.get("players"):
            (SITE_DIR / "players.html").write_text(env.get_template("players.html").render(d=data, pr=m["players"], teamlinks=[{"key": t.key, "short": t.short, "abbr": t.abbr} for t in TEAMS]))
        (SITE_DIR / "model.json").write_text(json.dumps({k: v for k, v in m.items() if k not in ("all_teams", "scatter", "book")}, default=str))
        render_book(env, data, m.get("book"))
    render_notes(env, data, season, dispatches, notes_by_game, profiles)

    static = TEMPLATES_DIR / "static"
    if static.exists():
        shutil.copytree(static, SITE_DIR / "static", dirs_exist_ok=True)
    finish_site(games, have_box, profiles, standings, m)
    return str(SITE_DIR / "index.html")


def render_notes(env: Environment, data: dict[str, Any], season: list[dict[str, Any]],
                 dispatches: list[dict[str, Any]], notes_by_game: dict[str, list[dict[str, Any]]],
                 profiles: dict[str, list[dict[str, Any]]]) -> None:
    """Fieldhouse Notes page. The author panel lists every MAC game, recent and upcoming first."""
    now = datetime.fromisoformat(data["generated_at"])
    links, rows, game_keys = {}, [], {}
    key_abbr = {t.key: t.abbr for t in TEAMS}
    for g in season:
        game_keys[g["game_id"]] = [k for k in (g["home"].get("key"), g["away"].get("key")) if k]
        a, h = g["away"], g["home"]
        label = f"{a.get('short') or a['name']} {'vs' if g.get('neutral_site') else 'at'} {h.get('short') or h['name']}"
        if g.get("completed") and a.get("score") is not None:
            label += f", {a['score']}-{h['score']}"
        href = f"games/{g['game_id']}.html" if g.get("box") else f"tv.html#g{g['game_id']}"
        links[g["game_id"]] = {"href": href, "label": label}
        when = datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
        rows.append({"game_id": g["game_id"], "label": label, "href": href, "when": f"{g['et']['weekday']} {g['et']['md']}",
                     "dt": when, "title": f"{a.get('abbr') or a['name']} at {h.get('abbr') or h['name']}",
                     "count": len(notes_by_game.get(g["game_id"], []))})
    week = timedelta(days=7)
    groups = [
        ("Last 7 days", sorted((r for r in rows if now - week <= r["dt"] <= now), key=lambda r: r["dt"], reverse=True)),
        ("Next 7 days", sorted((r for r in rows if now < r["dt"] <= now + week), key=lambda r: r["dt"])),
        ("Earlier this season", sorted((r for r in rows if r["dt"] < now - week), key=lambda r: r["dt"], reverse=True)),
        ("Later this season", sorted((r for r in rows if r["dt"] > now + week), key=lambda r: r["dt"])),
    ]
    # Author desk: private page for writing dispatches (noindex, not in nav, sitemap or search).
    players_list = sorted(({"id": str(p["espn_id"]), "name": p["name"], "label": f"{p['name']} ({key_abbr.get(key, key)})"}
                           for key, plist in profiles.items() for p in plist), key=lambda p: p["label"])
    desk = {
        "games": [{"id": r["game_id"], "label": f"{r['when']} · {r['label']}", "teams": game_keys.get(r["game_id"], [])}
                  for r in sorted(rows, key=lambda r: r["dt"])],
        "players": players_list,
        "teams": [{"key": t.key, "short": t.short} for t in TEAMS],
        "kinds": {k: [v[0], f'<svg class="fh-ic" viewBox="0 0 20 20" width="15" height="15" aria-hidden="true">{v[1]}</svg>'] for k, v in notes.KINDS.items()},
        "aliases": notes.ALIASES,
    }
    (SITE_DIR / "desk.html").write_text(env.get_template("desk.html").render(
        d=data, games=desk["games"], players=players_list, desk_json=json.dumps(desk).replace("</", "<\\/")))

    (SITE_DIR / "notes.html").write_text(env.get_template("notes.html").render(
        d=data, notes=dispatches, game_links=links, author_games=[(k, v) for k, v in groups if v],
        player_links={str(p["espn_id"]): {"href": f"teams/{key}.html#p{p['espn_id']}", "label": p["name"]}
                      for key, plist in profiles.items() for p in plist}))


def render_book(env: Environment, data: dict[str, Any], b: dict[str, Any] | None) -> None:
    """The Book: every conference's tables as site/book/<slug>.json plus book.html. Derived, never committed."""
    if not b or not b.get("tables"):
        return
    out = SITE_DIR / "book"
    out.mkdir(exist_ok=True)
    for slug, t in b["tables"].items():
        (out / f"{slug}.json").write_text(json.dumps(t, separators=(",", ":")))
    (out / "index.json").write_text(json.dumps(b["conferences"], separators=(",", ":")))
    first = b["tables"].get("mac") or next(iter(b["tables"].values()))
    (SITE_DIR / "book.html").write_text(env.get_template("book.html").render(
        d=data, b=b, first=first, first_json=json.dumps(first, separators=(",", ":")).replace("</", "<\\/")))


def finish_site(games: list[dict[str, Any]], have_box: set[str], profiles: dict[str, list[dict[str, Any]]],
                standings: dict[str, dict[str, Any]], m: dict | None) -> None:
    """Section anchors, search index, team colors, share cards, manifest, robots, sitemap."""
    (SITE_DIR / "static").mkdir(exist_ok=True)
    (SITE_DIR / "static" / "teams.css").write_text(site_chrome.teams_css())

    pages = sorted(p for p in SITE_DIR.rglob("*.html"))
    sections: dict[str, list[tuple[str, str]]] = {}
    for f in pages:
        rel = f.relative_to(SITE_DIR).as_posix()
        html, found = site_chrome.anchor_sections(f.read_text())
        f.write_text(html)
        if rel != "desk.html":
            sections[rel] = found

    coaches = {t.key: (players.team_context(t.key).get("coach") or {}).get("name") or "" for t in TEAMS}
    mac_games = [schedule_view.decorate(dict(g)) for g in games if g["home"].get("key") or g["away"].get("key")]

    def et_label(g: dict[str, Any]) -> str:
        e = schedule_view.et_fields(g)
        return f"{e['weekday']} {e['md']}, {e['time']} ET" if e.get("time") else f"{e['weekday']} {e['md']}"

    items = site_chrome.build_search_index(sections, mac_games, have_box, profiles, coaches, standings, et_label)
    (SITE_DIR / "search.json").write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                      "items": items}, separators=(",", ":")))
    access.lock_site(SITE_DIR)  # no-op unless ACCESS_CODE is set; after the search index so sections are still indexed

    (SITE_DIR / "manifest.webmanifest").write_text(site_chrome.manifest())
    (SITE_DIR / "robots.txt").write_text(site_chrome.robots())
    (SITE_DIR / "sitemap.xml").write_text(site_chrome.sitemap(
        f.relative_to(SITE_DIR).as_posix() for f in pages if not f.name.startswith("_") and f.name != "desk.html"))

    if not site_chrome.pillow_ok():
        print("share cards: skipped (Pillow not installed)")
        return
    og = SITE_DIR / "static" / "og"
    for size, name in ((180, "icon-180.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        site_chrome.app_icon(og / name, size)
    site_chrome.share_card(og / "site.png", site_chrome.SITE_NAME,
                           "MAC men's basketball: scores, lines from ten books, ratings, TV, travel and news for all 12 teams.",
                           kicker=f"MAC MEN'S BASKETBALL {SEASON_LABEL}")
    for path, label, purpose, accent, _ in site_chrome.PAGES[1:]:
        site_chrome.share_card(og / f"{path[:-5]}.png", label, purpose, accent=site_chrome.GOLD)
    ratings = {t["key"]: t for t in (m or {}).get("mac", [])}
    for t in TEAMS:
        rec = standings.get(t.key, {})
        lines = [f"{rec.get('w', 0)}-{rec.get('l', 0)} overall · {rec.get('cw', 0)}-{rec.get('cl', 0)} MAC"]
        r = ratings.get(t.key)
        if r:
            lines.append(f"Net rating {r['adj_em']:+.1f} per 100 · #{r['rk_adj_em']} in D-I")
        if coaches.get(t.key):
            lines.append(f"Coach {coaches[t.key]}")
        site_chrome.share_card(og / f"team-{t.key}.png", t.name, "Roster, player profiles, schedule, lines, travel and news.",
                               bg=t.color, accent=site_chrome.accent_for(t), lines=lines)
    colors = {t.key: t.color for t in TEAMS}
    by_id = {g["game_id"]: g for g in games}
    for gid in have_box:
        site_chrome.game_card(og / f"game-{gid}.png", by_id[gid], colors)
