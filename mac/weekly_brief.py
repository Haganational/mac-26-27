"""The facts sheet a BricksIt Weekly issue is written from.

    LEAGUE=<key> python -m mac.weekly_brief            # prints JSON for the current league

Everything here comes from the repo's own data (schedule, lines, box scores, model, power
rankings, news feed), so every number in an issue can be traced to it. The writer of the
issue (data/weekly/WRITING.md) uses only facts from this sheet, or from a source it cites.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from . import bigmid, model, news, weekly
from .build import dashboard_data
from .config import BY_KEY, DATA_DIR, LEAGUE
from .rosters import load_boxscores

WEEK = timedelta(days=7)


def _when(g: dict) -> datetime:
    return datetime.fromisoformat(g["date"].replace("Z", "+00:00"))


def _side(s: dict) -> dict:
    return {"team": s.get("name"), "key": s.get("key"), "score": s.get("score")}


def _result(g: dict, box: dict | None) -> dict[str, Any]:
    out = {"date_et": g.get("md"), "home": _side(g["home"]), "away": _side(g["away"]),
           "neutral": bool(g.get("neutral")), "conference_game": bool(g["home"].get("key") in BY_KEY and g["away"].get("key") in BY_KEY),
           "closing_home_spread": g.get("closing_spread"), "ats_cover": g.get("ats_cover")}
    if box:
        ours = [p for p in box.get("players", []) if not p.get("dnp") and (p.get("pts") or 0) >= 15]
        team = {g[s].get("espn_id"): g[s].get("name") for s in ("home", "away")}
        out["top_scorers"] = [{"name": p["name"], "team": team.get(p.get("team_espn_id")), "pts": p["pts"], "reb": p.get("reb"), "ast": p.get("ast")}
                              for p in sorted(ours, key=lambda p: -p["pts"])[:3]]
    return out


def _upcoming(g: dict) -> dict[str, Any]:
    latest = (g.get("line") or {}).get("latest") or {}
    m = g.get("model") or {}
    return {"date_et": _when(g).astimezone(weekly_et()).strftime("%a %b %-d, %-I:%M %p ET"),
            "home": g["home"].get("name"), "away": g["away"].get("name"),
            "conference_game": bool(g["home"].get("key") in BY_KEY and g["away"].get("key") in BY_KEY),
            "home_spread": latest.get("spread"), "total": latest.get("total"),
            "model_home_margin": m.get("margin") if isinstance(m, dict) else None, "tv": g.get("tv")}


def weekly_et():
    from .schedule_view import ET
    return ET


def _power() -> dict[str, Any]:
    files = sorted((DATA_DIR / "power").glob("*.json")) if (DATA_DIR / "power").exists() else []
    if not files:
        return {}
    now = json.loads(files[-1].read_text())
    prev = {t["key"]: t["rank"] for t in json.loads(files[-2].read_text())["teams"]} if len(files) > 1 else {}
    return {"week": now.get("week"), "teams": [{"rank": t["rank"], "team": t.get("short"), "score": t.get("score"),
                                                 "last_week": prev.get(t["key"])} for t in now["teams"]]}


def brief(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    data = dashboard_data(now)
    boxes = {b["game_id"]: b for b in load_boxscores()}
    try:
        m = model.build_model(now)
    except Exception as exc:  # noqa: BLE001 - the sheet is still useful without the model
        print(f"model: skipped ({exc!r})", file=sys.stderr)
        m = None
    if m:
        proj = {u["game_id"]: u for u in m["upcoming"]}
        for g in data["upcoming"]:
            g["model"] = proj.get(g["game_id"])
    ratings = sorted(({"team": BY_KEY[t["key"]].short, "rank_in_di": t["rk_adj_em"], "net_per_100": round(t["adj_em"], 1),
                       "sos": t.get("sos")} for t in (m or {}).get("mac", []) if t["key"] in BY_KEY), key=lambda r: r["rank_in_di"])
    week = [g for g in data["recent"] if now - WEEK <= _when(g) <= now and g["home"].get("score") is not None]
    nxt = [g for g in data["upcoming"] if now <= _when(g) <= now + WEEK]
    feed = news.view(now, limit=25)
    items = [{"title": i.get("title"), "source": i.get("source"), "url": i.get("url"), "published": i.get("published"),
              "teams": i.get("teams")} for i in (feed.get("headlines") or [])][:25]
    last = weekly.latest()
    return {
        "league": LEAGUE.key, "name": LEAGUE.name, "short": LEAGUE.short,
        "built_utc": now.isoformat(timespec="minutes"),
        "next_edition_number": (int(last["edition"]) + 1) if last else 0,
        "last_issue_date": last.get("date") if last else None,
        "standings": [{"team": r["team"], "w": r["w"], "l": r["l"], "conf_w": r.get("cw"), "conf_l": r.get("cl")}
                      for r in data["standings"]],
        "model_ratings": ratings,
        "power_rankings": _power(),
        "results_last_7_days": [_result(g, boxes.get(g["game_id"])) for g in sorted(week, key=_when)],
        "next_7_days": [_upcoming(g) for g in sorted(nxt, key=_when)],
        "big_mid_picks": bigmid.edition(now, data["recent"], data["upcoming"], boxes, data["standings"]),
        "news": items,
    }


def main() -> None:
    json.dump(brief(), sys.stdout, indent=1, default=str)
    print()


if __name__ == "__main__":
    main()
