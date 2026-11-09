"""Fieldhouse Notes: Matthew's own dispatches about games.

Each dispatch is a Markdown file in notes/dispatches/, committed to the repo:

    ---
    kind: arena              phone, paper, tv or arena (in person): the icon it is filed with
    game: 401812345          ESPN game id: filed with the game and both teams
    team: ohio               team key(s), comma separated: filed with the team
    player: 5105569          ESPN player id: filed with the player
    title: Short headline
    date: 2026-11-12
    draft: true              optional: stays off the site
    ---
    The dispatch itself, in Markdown.

Every published dispatch also joins the news feed (ticker, news page, team
headlines), marked with its icon and highlighted in the Fieldhouse color.

Who can add one is decided by GitHub, not the site: only accounts with write
access to the repo can commit, so readers can only read. Matthew writes them on
the author desk (templates/desk.html): each saved draft is its own pull request,
Publish merges it, and the push to notes/ republishes the site. The desk uses a
fine-grained token kept in his browser only. "+ Add dispatch" buttons (author
mode) open the desk with the game, team or player filled in.

Bodies are rendered with a small, escaping Markdown subset: paragraphs, headings,
bold, italic, links, lists, quotes and line breaks. Raw HTML is never passed through.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .config import DATA_DIR

NOTES_DIR = DATA_DIR.parent / "notes" / "dispatches"
REPO = "Haganational/mac-26-27"
BRANCH = "main"


def parse(text: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            for line in parts[0].splitlines()[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    v = re.split(r"\s+#", v, maxsplit=1)[0]  # allow "kind: arena   # phone, paper, tv or arena"
                    meta[k.strip().lower()] = v.strip().strip('"').strip("'")
            body = parts[1].split("\n", 1)[1] if "\n" in parts[1] else ""
    return meta, body.strip()


def _inline(s: str) -> str:
    s = html.escape(s, quote=True)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" rel="noopener" target="_blank">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<em>\1</em>", s)
    return s


def render_markdown(md: str) -> str:
    out: list[str] = []
    for block in re.split(r"\n\s*\n", md.strip()):
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", lines[0])
        if m and len(lines) == 1:
            lvl = len(m.group(1)) + 2  # # -> h3, the page owns h1/h2
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
        elif all(re.match(r"^\s*[-*]\s+", ln) for ln in lines):
            out.append("<ul>" + "".join(f"<li>{_inline(re.sub(r'^\s*[-*]\s+', '', ln))}</li>" for ln in lines) + "</ul>")
        elif all(re.match(r"^\s*\d+[.)]\s+", ln) for ln in lines):
            out.append("<ol>" + "".join(f"<li>{_inline(re.sub(r'^\s*\d+[.)]\s+', '', ln))}</li>" for ln in lines) + "</ol>")
        elif all(ln.startswith(">") for ln in lines):
            out.append("<blockquote>" + "<br>".join(_inline(ln.lstrip("> ")) for ln in lines) + "</blockquote>")
        else:
            out.append("<p>" + "<br>".join(_inline(ln) for ln in lines) + "</p>")
    return "\n".join(out)


ET = ZoneInfo("America/New_York")
COLOR = "#b5482a"  # Fieldhouse Notes' own color in the feed: brick

# kind -> (label, inline SVG path data on a 20x20 grid)
KINDS: dict[str, tuple[str, str]] = {
    "phone": ("Telephone", '<path d="M6.5 3h-2A1.5 1.5 0 0 0 3 4.6C3.3 11 9 16.7 15.4 17a1.5 1.5 0 0 0 1.6-1.5v-2l-3.3-1.5-1.6 1.6a9 9 0 0 1-4.7-4.7L9 7.3z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>'),
    "paper": ("Newspaper", '<path d="M3 4h11v11.5a1.5 1.5 0 0 0 1.5 1.5H4.5A1.5 1.5 0 0 1 3 15.5zM14 7h3v8.5a1.5 1.5 0 0 1-1.5 1.5M5.5 7h6M5.5 10h6M5.5 13h4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"/>'),
    "tv": ("Television", '<path d="M2.5 6h15v9h-15zM7 18h6M7 2.5 10 6l3-3.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"/>'),
    "arena": ("Arena, in person", '<path d="M2 16h16M3 16V9.5C3 7 6.1 5 10 5s7 2 7 4.5V16M6 16v-4.5M10 16v-5M14 16v-4.5M3 10h14M10 5V2.5l3 1-3 1" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'),
}
ALIASES = {"telephone": "phone", "call": "phone", "phone": "phone", "newspaper": "paper", "paper": "paper", "print": "paper",
           "television": "tv", "tv": "tv", "broadcast": "tv", "arena": "arena", "in person": "arena", "in-person": "arena",
           "inperson": "arena", "live": "arena", "fieldhouse": "arena"}


def kind_of(v: str | None) -> str:
    return ALIASES.get((v or "").strip().lower(), "arena")


def _published(meta: dict[str, str], stem: str) -> str:
    """ISO time: the date in the file, plus the HHMM the editor put at the end of the file name (Eastern)."""
    day = meta.get("date") or stem[:10]
    m = re.search(r"-(\d{2})(\d{2})$", stem)
    hh, mm = (int(m.group(1)), int(m.group(2))) if m and int(m.group(1)) < 24 and int(m.group(2)) < 60 else (12, 0)
    try:
        dt = datetime.fromisoformat(day[:10]).replace(hour=hh, minute=mm, tzinfo=ET)
    except ValueError:
        dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _list(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def load(notes_dir: Path | None = None, include_drafts: bool = False,
         game_teams: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """Every published dispatch, newest first, with where it is filed.

    game_teams maps a game id to its MAC team keys, so a game note is filed with both teams.
    """
    notes_dir = notes_dir or NOTES_DIR
    game_teams = game_teams or {}
    if not notes_dir.exists():
        return []
    out = []
    for path in sorted(notes_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        meta, body = parse(path.read_text(encoding="utf-8"))
        if not body or (meta.get("draft", "").lower() in ("true", "yes", "1") and not include_drafts):
            continue
        gid = meta.get("game") or None
        teams = _list(meta.get("team"))
        for t in game_teams.get(str(gid), []) if gid else []:
            if t not in teams:
                teams.append(t)
        kind = kind_of(meta.get("kind") or meta.get("icon"))
        out.append({
            "file": path.name,
            "slug": path.stem,
            "game_id": gid,
            "teams": teams,
            "team_tags": _list(meta.get("team")),  # filed directly to the team, not via a game
            "player": meta.get("player") or None,
            "kind": kind, "kind_label": KINDS[kind][0],
            "title": meta.get("title") or "",
            "date": meta.get("date") or path.stem[:10],
            "published": _published(meta, path.stem),
            "html": render_markdown(body),
            "text": re.sub(r"\s+", " ", re.sub(r"[*_>#\[\]]|\(https?://[^)]*\)", "", body)).strip(),
            "words": len(body.split()),
            "edit_url": f"https://github.com/{REPO}/edit/{BRANCH}/notes/dispatches/{quote(path.name)}",
        })
    out.sort(key=lambda d: (d["published"], d["file"]), reverse=True)
    return out


def for_team(dispatches: list[dict[str, Any]], team_key: str) -> list[dict[str, Any]]:
    """Game and team notes filed with a team. Player notes stay with the player."""
    return [d for d in dispatches if team_key in d["teams"]]


def by_player(dispatches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for d in dispatches:
        if d["player"]:
            out.setdefault(str(d["player"]), []).append(d)
    return out


def feed_items(dispatches: list[dict[str, Any]], root: str = "") -> list[dict[str, Any]]:
    """Dispatches shaped like news headlines, for the ticker, news page and team headlines."""
    out = []
    for d in dispatches:
        title = d["title"] or (d["text"][:110] + ("…" if len(d["text"]) > 110 else ""))
        out.append({"title": title, "url": f"{root}notes.html#n-{d['slug']}", "source": "Fieldhouse Notes",
                    "teams": d["teams"], "published": d["published"], "mine": True,
                    "kind": d["kind"], "kind_label": d["kind_label"]})
    return out


def merge_feed(view: dict[str, Any], dispatches: list[dict[str, Any]], now: datetime, root: str = "",
               team_key: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """Fold dispatches into a news.view() result, newest first."""
    from .news import _age

    items = feed_items([d for d in dispatches if team_key is None or team_key in d["teams"]], root)
    for i in items:
        age_h = max(0.0, (now - datetime.fromisoformat(i["published"])).total_seconds() / 3600)
        i.update(age=_age(age_h), fresh=age_h < 24)
    heads = sorted(view.get("headlines", []) + items, key=lambda i: i["published"], reverse=True)
    return {**view, "headlines": heads[:limit] if limit else heads, "total": view.get("total", 0) + len(items), "mine": len(items)}


def by_game(dispatches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for d in dispatches:
        if d["game_id"]:
            out.setdefault(str(d["game_id"]), []).append(d)
    return out


NEW_URL = f"https://github.com/{REPO}/new/{BRANCH}"
