"""BricksIt Weekly: one newsletter per conference, laid out like an old Sunday sports page.

Each issue is a hand-edited file, data/weekly/<league key>/<NNN>.json:

    {"edition": 1, "date": "2026-11-16", "label": "",
     "lead":   {"kicker", "headline", "deck", "body": [paragraphs]},
     "column": {"dispatch": "<Fieldhouse Notes slug>"}            # a contributor's column, or
               {"label": "Look Ahead", "title", "byline", "body": [paragraphs]},
     "notes":  [{"headline", "body"}, ...]}                       # below the fold

The infographic (the model's pecking order, with each team's record) is drawn from the
build's own data, so it is always current to the issue's build. The page is weekly.html in
each edition; the newest issue is the one shown.
"""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .config import LEAGUE, SHARED_DIR

WEEKLY_DIR = SHARED_DIR / "weekly"
NAME = "BricksIt Weekly"


def issues(league_key: str | None = None, root: Path = WEEKLY_DIR) -> list[Path]:
    d = root / (league_key or LEAGUE.key)
    return sorted(d.glob("[0-9][0-9][0-9].json")) if d.exists() else []


def latest(league_key: str | None = None, root: Path = WEEKLY_DIR) -> dict[str, Any] | None:
    files = issues(league_key, root)
    return json.loads(files[-1].read_text()) if files else None


def _inline(text: str) -> str:
    """Escape, then allow **bold** and *italic*, the only markup a column needs."""
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", t)


def chart(standings: list[dict[str, Any]], model: dict[str, dict[str, Any]], width: int = 320) -> dict[str, Any]:
    """The pecking order: each team's model rating (net points per 100 possessions against an average
    D-I team), best first, with its record. Returned as rows for the template to draw as SVG bars."""
    rows = []
    for s in standings:
        m = model.get(s["key"]) or {}
        if "adj_em" not in m:
            continue
        rows.append({"key": s["key"], "team": s["team"], "rec": f"{s['w']}-{s['l']}", "em": round(m["adj_em"], 1) + 0.0,
                     "rk": m.get("rk_adj_em")})
    rows.sort(key=lambda r: r["em"], reverse=True)
    if not rows:
        return {"rows": [], "height": 0}
    hi = max(max(r["em"] for r in rows), 1.0)
    lo = min(min(r["em"] for r in rows), -1.0)
    label_w, pad = 118, 8
    val_w = 34
    plot = width - label_w - pad * 2 - val_w
    zero = label_w + pad + plot * (-lo) / (hi - lo)
    row_h = 20
    for i, r in enumerate(rows):
        x = label_w + pad + plot * (min(r["em"], 0) - lo) / (hi - lo)
        r["x"], r["w"] = round(x, 1), round(max(plot * abs(r["em"]) / (hi - lo), 1.5), 1)
        r["y"] = 26 + i * row_h
        r["pos"] = r["em"] >= 0
    return {"rows": rows, "zero": round(zero, 1), "width": width, "height": 26 + len(rows) * row_h + 8,
            "label_w": label_w, "row_h": row_h, "bar_h": 11}


def context(issue: dict[str, Any], data: dict[str, Any], dispatches: list[dict[str, Any]]) -> dict[str, Any]:
    """Everything weekly.html needs: the issue with its text ready to print, the column, and the chart."""
    lead = dict(issue.get("lead") or {})
    lead["paras"] = [_inline(p) for p in lead.get("body") or []]
    col = dict(issue.get("column") or {})
    if col.get("dispatch"):
        d = next((x for x in dispatches if x.get("slug") == col["dispatch"]), None)
        if d:
            col.update({"title": d["title"], "byline": d.get("author") or col.get("byline") or "Matthew Hagan",
                        "html": d["html"], "href": f"notes.html#n-{d['slug']}"})
    if "html" not in col:
        col["html"] = "".join(f"<p>{_inline(p)}</p>" for p in col.get("body") or [])
    notes = [{"headline": n.get("headline", ""), "html": _inline(n.get("body", ""))} for n in issue.get("notes") or []]
    try:
        when = date.fromisoformat(issue.get("date", ""))
        dateline = when.strftime("%A, %B %-d, %Y")
    except ValueError:
        dateline = issue.get("date", "")
    return {"issue": issue, "lead": lead, "column": col, "notes": notes, "dateline": dateline,
            "chart": chart(data.get("standings") or [], data.get("model_mac") or {}), "name": NAME,
            "number": f"{int(issue.get('edition', 0)):03d}"}
