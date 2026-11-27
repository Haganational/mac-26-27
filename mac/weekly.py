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
            "number": f"{int(issue.get('edition', 0)):03d}", "paper": paper()}


# ------------------------------------------------------------------ the papers
# Matthew, Nov 25 2026: 27 individual weekly papers, each with its own name, capital and look.
# A conference without an entry here keeps the BricksIt Weekly nameplate. `name` may mark one
# word with *asterisks* for the accent. `style` picks the nameplate and ornament in weekly.html.
PAPERS: dict[str, dict[str, Any]] = {
    "mac": {"name": "The Brick Street *Bugle*", "capital": "Athens, Ohio", "backup": "Kalamazoo, Mich.",
            "motto": "Keep it mid. Keep it real.", "style": "bugle", "accent": "#a8441c", "second": "#5b2a17",
            "sidebar": "right", "photo": True, "tone": "sepia"},
    "horizon": {"name": "The Steel *Rim*", "capital": "Cleveland, Ohio", "backup": "Milwaukee, Wis.",
                "motto": "Every miss clangs, and we print the clang.", "style": "steel", "accent": "#3f5368", "second": "#c0612b",
                "sidebar": "left", "photo": True, "tone": "newsprint"},
    "asun": {"name": "The River City *Rebound*", "capital": "Jacksonville, Fla.", "backup": "Fort Myers, Fla.",
             "motto": "Young league. Always coming back.", "style": "river", "accent": "#1d6b74", "second": "#d08a3a",
             "sidebar": "right", "photo": False, "tone": "cream"},
    "mw": {"name": "The Pit *Report*", "capital": "Albuquerque, N.M.", "backup": "Las Vegas, Nev.",
           "motto": "High desert. Thin air. Loud nights.", "style": "mesa", "accent": "#23827f", "second": "#b9572c",
           "sidebar": "left", "photo": False, "tone": "aged"},
    "pac12": {"name": "The Timberline *Telegraph*", "capital": "Boise, Idaho", "backup": "Spokane, Wash.",
              "motto": "Wires from the high timber, sent from Boise.", "style": "timber", "accent": "#2f5d3a", "second": "#a3502b",
              "sidebar": "left", "photo": False, "tone": "ivory"},
    "wcc": {"name": "The Mission *Bell*", "capital": "San Francisco, Calif.", "backup": "Portland, Ore.",
            "motto": "Fog on the bay. Bells in the tower.", "style": "mission", "accent": "#a9502e", "second": "#b8913a",
            "sidebar": "right", "photo": False, "tone": "sepia"},
    "american": {"name": "The Weekly *American*", "capital": "Wichita, Kan.", "backup": "Memphis, Tenn.",
                 "motto": "Big cities. One front page.", "style": "american", "accent": "#1f3a68", "second": "#a8322d",
                 "sidebar": "left", "photo": False, "tone": "newsprint"},
    "sunbelt": {"name": "The Live Oak *Ledger*", "capital": "Mobile, Ala.", "backup": "Boone, N.C.",
                "motto": "Porch talk under the Spanish moss.", "style": "oak", "accent": "#4f6b3a", "second": "#8a5a2b",
                "sidebar": "right", "photo": False, "tone": "cream"},
    "ivy": {"name": "The *Footnote*", "capital": "Princeton, N.J.", "backup": "Ithaca, N.Y.",
            "motto": "Annotated, overthought and very well cited.", "style": "footnote", "accent": "#8c1d2c", "second": "#24375e",
            "sidebar": "left", "photo": False, "tone": "ivory"},
    "caa": {"name": "The Battery *Brief*", "capital": "Charleston, S.C.", "backup": "Wilmington, N.C.",
            "motto": "Ports from the harbor wall, in brief.", "style": "battery", "accent": "#21506b", "second": "#b48a3c",
            "sidebar": "right", "photo": False, "tone": "newsprint"},
    "cusa": {"name": "The Water Tower *Weekly*", "capital": "Murfreesboro, Tenn.", "backup": "Bowling Green, Ky.",
             "motto": "Every town's name up on the tower.", "style": "tower", "accent": "#3b6c8c", "second": "#c4862c",
             "sidebar": "left", "photo": False, "tone": "aged"},
    "socon": {"name": "The Choo‑Choo *Chronicle*", "capital": "Chattanooga, Tenn.", "backup": "Greenville, S.C.",
              "motto": "Old league. Mountain towns. Long memories.", "style": "rail", "accent": "#7b2e2a", "second": "#3e4c5a",
              "sidebar": "right", "photo": False, "tone": "sepia"},
}


# Paper stock (Matthew, Nov 25 2026: "randomize the sepia and newspaper tone"). Each is the sheet
# color, a second shade for the chart box, and the ink. A paper without a set tone, sidebar side
# or photo choice gets one drawn from a generator seeded on its key, so it differs from its
# neighbors but stays the same paper week to week.
TONES: dict[str, dict[str, str]] = {
    "cream":     {"p": "#f4efe4", "p2": "#fffcf6", "ink": "#1a1410"},
    "sepia":     {"p": "#efe3cb", "p2": "#f6ecd8", "ink": "#2a1d12"},
    "newsprint": {"p": "#ebeae4", "p2": "#f4f3ee", "ink": "#16171a"},
    "aged":      {"p": "#e9d9b8", "p2": "#f1e4c8", "ink": "#2b2014"},
    "ivory":     {"p": "#f7f3e8", "p2": "#fdfaf2", "ink": "#1b1916"},
}


def _layout(key: str, p: dict[str, Any]) -> dict[str, Any]:
    import random
    rnd = random.Random(f"bricksit:{key}")
    side, photo, tone = rnd.choice(("left", "right")), rnd.random() < .5, rnd.choice(sorted(TONES))
    return {"sidebar": p.get("sidebar", side), "photo": p.get("photo", photo), "tone": p.get("tone", tone)}


def paper(league_key: str | None = None) -> dict[str, Any] | None:
    """This conference's paper with its name split for the nameplate, or None for the BricksIt default."""
    key = league_key or LEAGUE.key
    p = PAPERS.get(key)
    if not p:
        return None
    parts = [{"text": t, "accent": i % 2 == 1} for i, t in enumerate(p["name"].split("*")) if t]
    lay = _layout(key, p)
    return {**p, **lay, "stock": TONES[lay["tone"]], "parts": parts, "plain": p["name"].replace("*", "")}


def photo(issue: dict[str, Any], teams: list[Any], backdrops: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """The above-the-fold picture: a free-licensed backdrop of a school the lead story names, else one of
    the conference's backdrops in turn by edition number. None when the conference has none."""
    have = [t for t in teams if t.key in backdrops]
    if not have:
        return None
    lead = issue.get("lead") or {}
    text = " ".join([lead.get("kicker", ""), lead.get("headline", ""), lead.get("deck", "")])
    named = [t for t in have if t.short in text]
    t = named[0] if named else have[int(issue.get("edition", 0) or 0) % len(have)]
    return {**backdrops[t.key], "team": t.short}


# ------------------------------------------------------------------ the weekly rotation
# One issue per conference per week, four conferences a morning (three on Sunday), so each
# day's run stays small and a bad day costs four conferences, not 27. Every issue covers its
# own trailing seven days, so the day a conference lands on drops no games.
ROTATION: dict[str, tuple[str, ...]] = {
    "Mon": ("mac", "horizon", "asun", "mw"),
    "Tue": ("metro", "bigwest", "mvc", "a10"),
    "Wed": ("pac12", "wcc", "american", "sunbelt"),
    "Thu": ("ivy", "caa", "cusa", "socon"),
    "Fri": ("bigsky", "southland", "summit", "uac"),
    "Sat": ("bigsouth", "ovc", "americaeast", "patriot"),
    "Sun": ("nec", "meac", "swac"),
}


def due(day: date) -> tuple[str, ...]:
    """The conferences whose issue comes out on this (Eastern) day."""
    return ROTATION[day.strftime("%a")]


def check(issue: dict[str, Any], league_key: str, root: Path = WEEKLY_DIR, path: Path | None = None) -> list[str]:
    """Problems that would keep an issue off the site; empty means it is ready to publish.
    `path` is the issue's own file when it is already in the folder, so it isn't its own predecessor."""
    bad = []
    own = path.resolve() if path else None
    files = [f for f in issues(league_key, root) if f.resolve() != own]
    prev = json.loads(files[-1].read_text()) if files else None
    want = int(prev["edition"]) + 1 if prev else 0
    if issue.get("edition") != want:
        bad.append(f"edition should be {want}")
    try:
        date.fromisoformat(issue.get("date", ""))
    except (TypeError, ValueError):
        bad.append("date must be YYYY-MM-DD")
    lead = issue.get("lead") or {}
    for k in ("kicker", "headline", "deck"):
        if not (lead.get(k) or "").strip():
            bad.append(f"lead.{k} is empty")
    if not (3 <= len(lead.get("body") or []) <= 7):
        bad.append("lead.body needs 3 to 7 paragraphs")
    col = issue.get("column") or {}
    if not (col.get("dispatch") or (col.get("label") and col.get("title") and col.get("byline") and col.get("body"))):
        bad.append("column needs a dispatch slug, or label, title, byline and body")
    if col.get("byline", "").strip().lower() == "matthew hagan":
        bad.append("scheduled issues run under the staff byline, not Matthew's name")
    notes = issue.get("notes") or []
    if not (3 <= len(notes) <= 5) or not all((n.get("headline") or "").strip() and (n.get("body") or "").strip() for n in notes):
        bad.append("notes needs 3 to 5 items, each with a headline and body")
    return bad


def _cli() -> None:
    import sys
    from zoneinfo import ZoneInfo
    from datetime import datetime
    args = sys.argv[1:]
    if args[:1] == ["due"]:
        day = date.fromisoformat(args[1]) if len(args) > 1 else datetime.now(ZoneInfo("America/New_York")).date()
        print(" ".join(due(day)))
    elif args[:1] == ["check"] and len(args) == 3:
        problems = check(json.loads(Path(args[2]).read_text()), args[1], path=Path(args[2]))
        print("\n".join(problems) or "ok")
        sys.exit(1 if problems else 0)
    else:
        sys.exit("usage: python -m mac.weekly due [YYYY-MM-DD] | check <league> <issue.json>")


if __name__ == "__main__":
    _cli()
