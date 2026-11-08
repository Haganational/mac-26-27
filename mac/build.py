"""Render the static dashboard into site/index.html."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import analysis
from .config import SEASON_LABEL, SITE_DIR, TEAMS, TEMPLATES_DIR
from .espn import load_schedule
from .odds import load_all_rows


def dashboard_data(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    schedule = load_schedule()
    games = schedule["games"]
    history = analysis.line_history(load_all_rows())
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "schedule_fetched_at": schedule.get("fetched_at"),
        "season": SEASON_LABEL,
        "teams": [t.__dict__ for t in TEAMS],
        "standings": analysis.standings(games),
        "upcoming": analysis.upcoming(games, history, now),
        "recent": analysis.recent_results(games, history, now),
        "posting": analysis.posting_stats(history),
        "history": list(history.values()),
        "counts": {
            "games": len(games),
            "completed": sum(1 for g in games if g["completed"]),
            "events_with_lines": len(history),
            "snapshots": sum(len(h["snapshots"]) for h in history.values()),
        },
    }


def render_site() -> str:
    data = dashboard_data()
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    tpl = env.get_template("index.html")
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(tpl.render(d=data, data_json=json.dumps(data)))
    (SITE_DIR / "data.json").write_text(json.dumps(data))
    (SITE_DIR / ".nojekyll").write_text("")
    static = TEMPLATES_DIR / "static"
    if static.exists():
        shutil.copytree(static, SITE_DIR / "static", dirs_exist_ok=True)
    return str(SITE_DIR / "index.html")
