"""The daily local-flavor to-do list: ten schools a day until every school has a line.

Matthew writes the flavor lines (see FLAVOR_HELP in mac/gamer.py). This module picks
which ten schools to ask about each morning, prints the checklist, and loads his
answers back into each league's flavor.json.

    python -m mac.flavor_queue today [--date 2026-11-13] [--n 10]   # build and save today's list
    python -m mac.flavor_queue apply reply.txt                      # load a pasted reply
    python -m mac.flavor_queue status                               # done / started / to go

The reply is one line per school, numbered as in that day's list:

    x 1: A line true wherever they play. home: A line for home games only.
    ~ 2: Half a thought I'll finish later
    - 3
    x 4: First line | second line | floor: the Wolstein Center

x (or a number with text and no mark) = done: the lines go into flavor.json.
~ = started: the draft is saved here, never published, and comes back first tomorrow.
- = skip for now: the school drops to the back of the queue.
A number with nothing after it is left as it was.
"home:" starts a home-games-only line, "|" separates lines, "town:" and "floor:" fix those names.

Progress lives in data/flavor_progress.json. A school counts as done once its flavor.json
entry has a plain-string line (his own voice); researched {"text", "source"} notes don't count.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .leagues import ALL, ROOT, League, Team

ET = ZoneInfo("America/New_York")
PROGRESS_PATH = ROOT / "data" / "flavor_progress.json"
ORDER = ("mac", "horizon", "asun", "mw", "metro", "bigwest")  # ties go to the flagship first


def flavor_path(lg: League) -> Path:
    return lg.data_dir / "flavor.json"


def load_json(p: Path, default: Any) -> Any:
    return json.loads(p.read_text()) if p.exists() else default


def load_flavor(lg: League) -> dict[str, Any]:
    f = load_json(flavor_path(lg), None)
    if f is None:
        f = {"_help": f"{lg.short} local flavor for the gamer on each box score page. Same knobs as data/flavor.json "
                      "(see FLAVOR_HELP in mac/gamer.py). Only write what you know is true.",
             "settings": {"enabled": True, "byline": "Hardwood Bricks staff", "max_lines": 1},
             "teams": {}, "rivalries": {}}
    f.setdefault("teams", {})
    f.setdefault("rivalries", {})
    return f


def save_json(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def load_progress(path: Path = PROGRESS_PATH) -> dict[str, Any]:
    p = load_json(path, {})
    for k in ("days", "partial", "skipped"):
        p.setdefault(k, {})
    return p


def has_lines(entry: dict[str, Any] | None) -> bool:
    """True once a school has a line in Matthew's own voice: a plain string. Researched notes from the
    flavor desk are {"text", "source", ...} dicts and don't count, so the daily list keeps asking for his lines."""
    if not entry:
        return False
    return any(isinstance(x, str) and x.strip() for x in (entry.get("lines") or []) + (entry.get("home_lines") or []))


def all_schools() -> list[tuple[League, Team]]:
    return [(ALL[k], t) for k in ORDER if k in ALL for t in ALL[k].teams]


def sid(lg: League, t: Team) -> str:
    return f"{lg.key}/{t.key}"


def home_venue(lg: League, t: Team) -> tuple[str | None, str | None]:
    """The town and building where this team plays most of its home games, from the schedule."""
    games = load_json(lg.data_dir / "schedule.json", {}).get("games", [])
    c = Counter((g.get("venue_city"), g.get("venue")) for g in games
                if g.get("home", {}).get("key") == t.key and not g.get("neutral_site"))
    return c.most_common(1)[0][0] if c else (None, None)


def next_game(lg: League, t: Team, now: datetime) -> dict[str, Any] | None:
    games = load_json(lg.data_dir / "schedule.json", {}).get("games", [])
    best = None
    for g in games:
        if t.key not in (g.get("home", {}).get("key"), g.get("away", {}).get("key")):
            continue
        when = datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
        if when >= now and (best is None or when < best[0]):
            best = (when, g)
    if not best:
        return None
    when, g = best
    home = g["home"].get("key") == t.key
    opp = g["away" if home else "home"]
    from .today import school
    where = "vs" if home and not g.get("neutral_site") else ("at" if not home and not g.get("neutral_site") else "vs")
    loc = " (neutral)" if g.get("neutral_site") else ""
    return {"when": when, "home": home and not g.get("neutral_site"),
            "text": f"{when.astimezone(ET):%a %-m/%-d} {where} {school(opp.get('name'), opp.get('key'))}{loc}"}


def status(progress: dict[str, Any] | None = None) -> dict[str, int]:
    progress = progress if progress is not None else load_progress()
    fl = {k: load_flavor(lg) for k, lg in ALL.items()}
    done = sum(1 for lg, t in all_schools() if has_lines(fl[lg.key]["teams"].get(t.key)))
    started = sum(1 for lg, t in all_schools()
                  if sid(lg, t) in progress["partial"] and not has_lines(fl[lg.key]["teams"].get(t.key)))
    total = len(all_schools())
    return {"done": done, "started": started, "to_go": total - done, "total": total}


def pick(day: date, n: int = 10, progress: dict[str, Any] | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    """Today's schools: started ones first, then soonest game, skipped ones last."""
    progress = progress if progress is not None else load_progress()
    now = now or datetime.combine(day, datetime.min.time(), ET)
    fl = {k: load_flavor(lg) for k, lg in ALL.items()}
    far = datetime.max.replace(tzinfo=ET)
    rows = []
    for i, (lg, t) in enumerate(all_schools()):
        entry = fl[lg.key]["teams"].get(t.key)
        if has_lines(entry):
            continue
        s = sid(lg, t)
        ng = next_game(lg, t, now)
        town, floor = (entry or {}).get("town"), (entry or {}).get("home_floor")
        if not town or not floor:
            vt, vf = home_venue(lg, t)
            town, floor = town or vt, floor or vf
        skipped = progress["skipped"].get(s, "")
        rows.append({"id": s, "league": lg.short, "school": t.short, "town": town, "floor": floor,
                     "next": ng["text"] if ng else None, "draft": progress["partial"].get(s),
                     "_key": (s not in progress["partial"], skipped, ng["when"] if ng else far, i)})
    rows.sort(key=lambda r: r["_key"])
    out = rows[:n]
    for r in out:
        r.pop("_key")
    return out


def render(day: date, rows: list[dict[str, Any]], st: dict[str, int]) -> str:
    head = f"**Local flavor, {day:%a %b} {day.day}**: {st['done']} of {st['total']} schools done"
    if st["started"]:
        head += f", {st['started']} started"
    out = [head, ""]
    for i, r in enumerate(rows, 1):
        bits = [x for x in (r["town"], r["floor"]) if x]
        line = f"☐ {i}. **{r['school']}** ({r['league']})"
        if bits:
            line += f", {', '.join(bits)}"
        if r["next"]:
            line += f". Next: {r['next']}"
        out.append(line)
        if r["draft"]:
            out.append(f"   draft so far: {r['draft']}")
    out += ["", "Copy this, fill it in, send it back. x = done, ~ = started, - = skip. "
                "`home:` starts a home-games-only line, `|` splits two lines.", "", "```"]
    out += [f"x {i}: " for i in range(1, len(rows) + 1)]
    out.append("```")
    return "\n".join(out)


LINE = re.compile(r"^\s*(?:\[\s*([xX~✓✔-]?)\s*\]|([xX~✓✔-]))?\s*(\d{1,2})\s*[.:)\-]?\s*(.*)$")


def parse(text: str) -> list[dict[str, Any]]:
    out = []
    for raw in text.splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        mark = (m.group(1) or m.group(2) or "").lower()
        body = m.group(4).strip()
        if not body and mark not in ("-", "~"):
            continue  # an untouched template line
        kind = {"~": "started", "-": "skip"}.get(mark, "done")
        item: dict[str, Any] = {"n": int(m.group(3)), "kind": kind, "lines": [], "home_lines": [], "town": None,
                                "floor": None, "raw": body}
        for part in re.split(r"\s*\|\s*|\s+(?=(?:home|town|floor)\s*:)", body, flags=re.I):
            part = part.strip()
            if not part:
                continue
            km = re.match(r"(home|town|floor)\s*:\s*(.*)$", part, re.I)
            if not km:
                item["lines"].append(part)
            elif km.group(1).lower() == "home":
                item["home_lines"].append(km.group(2).strip())
            else:
                item[km.group(1).lower()] = km.group(2).strip() or None
        item["home_lines"] = [x for x in item["home_lines"] if x]
        out.append(item)
    return out


def apply(text: str, day: str | None = None, progress_path: Path = PROGRESS_PATH) -> list[str]:
    """Load a reply against that day's list (the latest list if no day is given). Returns a summary."""
    progress = load_progress(progress_path)
    if not progress["days"]:
        raise SystemExit("No daily list saved yet; run `today` first.")
    day = day or max(progress["days"])
    ids = progress["days"][day]
    leagues = {lg.key: lg for lg in ALL.values()}
    flavors: dict[str, dict[str, Any]] = {}
    report = []
    for it in parse(text):
        if not 1 <= it["n"] <= len(ids):
            report.append(f"? {it['n']}: no school with that number on the {day} list")
            continue
        s = ids[it["n"] - 1]
        lk, tk = s.split("/")
        lg = leagues[lk]
        name = next(t.short for t in lg.teams if t.key == tk)
        if it["kind"] == "skip":
            progress["skipped"][s] = day
            report.append(f"- {name}: skipped for now")
            continue
        if it["kind"] == "started":
            if it["raw"]:
                progress["partial"][s] = it["raw"]
            else:
                progress["partial"].setdefault(s, "")
            report.append(f"~ {name}: started, back on tomorrow's list")
            continue
        if not (it["lines"] or it["home_lines"]):
            report.append(f"? {name}: marked done but no line came with it; left as it was")
            continue
        f = flavors.setdefault(lk, load_flavor(lg))
        e = f["teams"].setdefault(tk, {})
        if not e.get("town") or not e.get("home_floor"):
            vt, vf = home_venue(lg, next(t for t in lg.teams if t.key == tk))
            e.setdefault("town", vt)
            e.setdefault("home_floor", vf)
        if it["town"]:
            e["town"] = it["town"]
        if it["floor"]:
            e["home_floor"] = it["floor"]
        e.setdefault("lines", [])
        e.setdefault("home_lines", [])
        e["lines"] += [x for x in it["lines"] if x not in e["lines"]]
        e["home_lines"] += [x for x in it["home_lines"] if x not in e["home_lines"]]
        progress["partial"].pop(s, None)
        progress["skipped"].pop(s, None)
        report.append(f"x {name}: {len(it['lines'])} line(s), {len(it['home_lines'])} home line(s)")
    for lk, f in flavors.items():
        save_json(flavor_path(leagues[lk]), f)
    save_json(progress_path, progress)
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m mac.flavor_queue")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("today")
    t.add_argument("--date")
    t.add_argument("--n", type=int, default=10)
    a = sub.add_parser("apply")
    a.add_argument("file", help="the pasted reply, or - for stdin")
    a.add_argument("--day")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    if args.cmd == "today":
        day = date.fromisoformat(args.date) if args.date else datetime.now(ET).date()
        progress = load_progress()
        rows = pick(day, args.n, progress, now=datetime.now(ET) if not args.date else None)
        progress["days"][day.isoformat()] = [r["id"] for r in rows]
        save_json(PROGRESS_PATH, progress)
        print(render(day, rows, status(progress)))
    elif args.cmd == "apply":
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text()
        print("\n".join(apply(text, args.day)))
        st = status()
        print(f"\n{st['done']} of {st['total']} done, {st['started']} started, {st['to_go']} to go")
    else:
        print(json.dumps(status()))


if __name__ == "__main__":
    main()
