"""Anchor notebooks (Matthew, Nov 17 2026): every anchor keeps one markdown file that grows.

data/notebooks/<key>.md is the anchor's running file on their school and town:

- who they are (roster, voice, lean, dossier) and how they look (portrait, gear, colors, set), so the writing
  matches the picture;
- the barometer: a 0-100 read of how the team is going, from its results, and the mood it puts the anchor in;
- the school and the town in numbers (data/school_facts.json: enrollment, tuition, endowment, football, the
  coach's pay, and the town's income, rent, home values and the rest from the Census);
- the program's best player and best run (data/best_of.json);
- what we've made about the school: films, fight songs, MIDnight Weave spots, social posts;
- a dated log that only ever grows: one line per finished game and per new piece we make.

Everything above the log is rewritten on every run; the log keeps its old lines and adds new ones.

The barometer also feeds the coverage: press.aside() asks for the anchor's mood going into a game, and hot or
cold anchors editorialize more often (mood_rate). Moods are worked out as of the game's tip, so a story never
changes after it runs.

Run: python -m mac.notebook  (all 286; nightly in collect.yml).
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import anchors
from .config import SHARED_DIR

OUT = SHARED_DIR / "notebooks"
FACTS = SHARED_DIR / "school_facts.json"
BEST = SHARED_DIR / "best_of.json"
FILMS = SHARED_DIR / "films.json"
SONGS = SHARED_DIR / "fight_songs.json"
WEAVE = SHARED_DIR / "weave.json"
POSTED = SHARED_DIR / "social_posted.json"
LOG_HEAD = "## Log"
DISCLOSURE = "Anchors are fictional AI personas, not affiliated with any school."

# Barometer to mood. The anchor's mood is the team's form, never a verdict on any real person.
MOODS = ((80, "giddy"), (65, "buoyant"), (45, "steady"), (30, "testy"), (0, "despondent"))


# ---------------------------------------------------------------- data

def _load(p: Path, key: str | None = None) -> Any:
    if not p.exists():
        return {}
    d = json.loads(p.read_text())
    return d.get(key, {}) if key else d


@lru_cache(maxsize=1)
def teams() -> dict[str, dict[str, Any]]:
    """key -> {short, name, league, path, data_dir} for all 286 schools."""
    from .leagues import ALL
    return {t.key: {"short": t.short, "name": t.name, "league": lg.key, "league_name": lg.short,
                    "path": lg.path, "data_dir": lg.data_dir} for lg in ALL.values() for t in lg.teams}


@lru_cache(maxsize=None)
def _schedule(data_dir: str) -> list[dict[str, Any]]:
    p = Path(data_dir) / "schedule.json"
    return json.loads(p.read_text()).get("games", []) if p.exists() else []


def results(key: str, before: str | None = None) -> list[dict[str, Any]]:
    """The team's finished games, oldest first: {id, date, won, us, them, margin, where, opp}.
    before = an ISO time; only games that tipped before it."""
    t = teams().get(key)
    if not t:
        return []
    out = []
    for g in _schedule(str(t["data_dir"])):
        if not g.get("completed"):
            continue
        side = "home" if (g.get("home") or {}).get("key") == key else "away" if (g.get("away") or {}).get("key") == key else None
        if not side or (before and g.get("date", "") >= before):
            continue
        me, op = g[side], g["away" if side == "home" else "home"]
        try:
            us, them = int(me.get("score")), int(op.get("score"))
        except (TypeError, ValueError):
            continue
        where = "neutral" if g.get("neutral_site") else side
        out.append({"id": str(g.get("game_id")), "date": g.get("date", ""), "won": us > them, "us": us, "them": them,
                    "margin": abs(us - them), "where": where, "opp": _short_name(op), "opp_key": op.get("key"),
                    "conf": bool(g.get("conference_game"))})
    out.sort(key=lambda r: r["date"])
    return out


def _short_name(side: dict[str, Any]) -> str:
    k = side.get("key")
    if k and k in teams():
        return teams()[k]["short"]
    return side.get("name") or side.get("abbr") or "?"


# ---------------------------------------------------------------- barometer

def barometer(key: str, before: str | None = None) -> dict[str, Any]:
    """{score 0-100, mood, record, streak, last5, games}. 50 = level. Recent games count most (each older game
    0.8 as much), a win by 20 counts more than a win by 1, and a run of three or more pushes it further."""
    rs = results(key, before)
    if not rs:
        return {"score": 50, "mood": "steady", "record": "0-0", "conf": "0-0", "streak": "", "last5": "", "games": 0}
    tot = wsum = 0.0
    for i, r in enumerate(reversed(rs[-10:])):
        w = 0.8 ** i
        tot += w * (1 if r["won"] else -1) * (0.6 + 0.4 * min(r["margin"], 20) / 20)
        wsum += w
    n = len(rs)
    s = 50 + 42 * (tot / wsum) * n / (n + 2)  # two or three games can't make anyone giddy yet
    run = 0
    for r in reversed(rs):
        if r["won"] != rs[-1]["won"]:
            break
        run += 1
    if run >= 3:
        s += (1 if rs[-1]["won"] else -1) * min(3 * (run - 2), 9)
    s = int(round(max(2, min(98, s))))
    w = sum(r["won"] for r in rs)
    cw = sum(r["won"] for r in rs if r["conf"])
    cl = sum(not r["won"] for r in rs if r["conf"])
    return {"score": s, "mood": mood_word(s), "record": f"{w}-{len(rs) - w}", "conf": f"{cw}-{cl}",
            "streak": f"{'W' if rs[-1]['won'] else 'L'}{run}", "last5": "".join("W" if r["won"] else "L" for r in rs[-5:]),
            "games": len(rs)}


def mood_word(score: int) -> str:
    return next(w for floor, w in MOODS if score >= floor)


def mood_rate(key: str | None, before: str | None = None) -> float:
    """How much more often this anchor editorializes going into a game: 1.0 at level, up to 1.0 + 0.5 on a
    tear or in a slump (the press aside rate is multiplied by this, then capped at 1)."""
    if not key or key not in teams():
        return 1.0
    b = barometer(key, before)
    return 1.0 + 0.5 * abs(b["score"] - 50) / 48


# ---------------------------------------------------------------- facts

def _v(f: dict[str, Any], k: str) -> Any:
    x = f.get(k)
    return x.get("value") if isinstance(x, dict) else x


def _money(n: Any) -> str:
    if not isinstance(n, (int, float)):
        return ""
    if n >= 1e9:
        return f"${n / 1e9:.2f} billion"
    if n >= 1e6:
        return f"${n / 1e6:.1f} million"
    return f"${n:,.0f}"


def facts_lines(key: str) -> list[str]:
    f = _load(FACTS, "schools").get(key) or {}
    if not f:
        return ["_Not filled in yet. The desk is researching enrollment, tuition, endowment, football, the coach's "
                "pay and the town's Census figures._"]
    out = []

    def row(label: str, k: str, fmt=lambda v: f"{v:,}" if isinstance(v, (int, float)) else str(v)) -> None:
        val = _v(f, k)
        if val is None or val == "":
            return
        x = f.get(k) if isinstance(f.get(k), dict) else {}
        yr = f" ({x['year']})" if x.get("year") else ""
        note = f", {x['note']}" if x.get("note") else ""
        out.append(f"- {label}: {fmt(val)}{yr}{note}")

    out.append("**School**")
    row("Enrollment", "enrollment")
    row("Tuition and fees, in state", "tuition_in", _money)
    row("Tuition and fees, out of state", "tuition_out", _money)
    row("Endowment", "endowment", _money)
    row("Football", "football")
    row("Men's basketball coach's pay", "mbb_coach_pay", _money)
    row("Students on Pell Grants", "pell_pct", lambda v: f"{v}%")
    row("Median debt at graduation", "median_debt", _money)
    g = f.get("grants_terminated_2025")
    if isinstance(g, dict) and (g.get("count") or g.get("dollars")):
        out.append(f"- Federal research grants cut in 2025: {g.get('count') or '?'}" + (f", {_money(g['dollars'])}" if g.get("dollars") else ""))
    a = f.get("arena_named_for")
    if isinstance(a, dict) and a.get("value"):
        out.append(f"- Arena named for: {a['value']}" + (f" ({a['money_from']})" if a.get("money_from") else "")
                   + (", a billionaire" if a.get("billionaire") else ""))
    out.append("")
    out.append(f"**{f.get('town') or 'Town'}**")
    row("Population", "population")
    row("Population in 2020", "population_2020")
    row("Median household income", "median_household_income", _money)
    row("Income per person", "per_capita_income", _money)
    row("Median rent", "median_gross_rent", lambda v: f"${v:,.0f} a month")
    row("Median home value", "median_home_value", _money)
    row("Poverty rate", "poverty_rate", lambda v: f"{v}%")
    row("Median age", "median_age")
    row("Adults with a bachelor's degree", "bachelors_pct", lambda v: f"{v}%")
    row("Homeownership", "homeownership_pct", lambda v: f"{v}%")
    row("Average commute", "commute_minutes", lambda v: f"{v} minutes")
    row("Veterans", "veterans")
    row("Born abroad", "foreign_born_pct", lambda v: f"{v}%")
    row("Founded", "founded", str)
    row("County seat", "county_seat", lambda v: "yes" if v else "no")
    row("Biggest employer", "largest_employer", str)
    row("January average", "jan_avg_temp_f", lambda v: f"{v}°F")
    row("Snow a year", "snowfall_in", lambda v: f"{v} inches")
    row("Elevation", "elevation_ft", lambda v: f"{v:,} feet")
    if f.get("county"):
        out.append(f"- County: {_v(f, 'county')}")
    row("Local news outlets in the county", "news_outlets_county")
    row("News desert", "news_desert", lambda v: "yes" if v else "no")
    ice = f.get("ice_287g")
    if isinstance(ice, dict) and ice.get("value") is not None:
        out.append("- ICE 287(g) agreement in the county: " + (f"yes, {ice.get('agency', '')} ({ice.get('model', '')})" if ice["value"] else "no"))
    det = f.get("detention_center_nearby")
    if isinstance(det, dict) and det.get("value"):
        out.append(f"- Nearest ICE detention site: {det['value']}" + (f", {det['miles']} miles" if det.get("miles") else ""))
    h = households(f)
    if h:
        out.append(f"- The coach's pay equals {h} median {f.get('town') or 'town'} household incomes")
    idx = college_town_index(f)
    if idx is not None:
        out.append(f"- College-town index: {idx:.2f} students per resident "
                   f"({'the school is the town' if idx >= 0.5 else 'a big presence' if idx >= 0.15 else 'a guest in a bigger place'})")
    return out


def households(f: dict[str, Any]) -> int | None:
    """How many of the town's median household incomes the men's basketball coach's pay comes to."""
    pay, inc = _v(f, "mbb_coach_pay"), _v(f, "median_household_income")
    if isinstance(pay, (int, float)) and isinstance(inc, (int, float)) and inc > 0:
        return int(round(pay / inc))
    return None


def college_town_index(f: dict[str, Any]) -> float | None:
    e, p = _v(f, "enrollment"), _v(f, "population")
    if isinstance(e, (int, float)) and isinstance(p, (int, float)) and p > 0:
        return e / p
    return None


# ---------------------------------------------------------------- the file

def _ymd(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return iso[:10]


def made_about(key: str) -> list[dict[str, str]]:
    """Every piece we've made about this school: {id, kind, text}."""
    out = []
    for f in _load(FILMS, "films").get(key, []):
        out.append({"id": f"film:{f.get('youtube')}", "kind": "film",
                    "text": f"Film: *{f['title']}* (https://youtu.be/{f.get('youtube')}). {f.get('dek', '')}".strip()})
    s = _load(SONGS, "songs").get(key) or {}
    if s.get("youtube"):
        out.append({"id": f"song:{s['youtube']}", "kind": "song",
                    "text": f"Fight song: *{s.get('title', '')}* (https://youtu.be/{s['youtube']})"})
    me = (anchors.roster().get(key) or {}).get("name", "")
    for sh in _load(WEAVE).get("shows", []):
        if me and me in (sh.get("cast", "") + sh.get("dek", "")):
            out.append({"id": f"weave:{sh.get('youtube')}", "kind": "weave",
                        "text": f"On MIDnight Weave, {sh.get('aired', '')}: *{sh.get('title', '')}* (https://youtu.be/{sh.get('youtube')})"})
    return out


def posts(key: str) -> list[dict[str, str]]:
    """Game previews and recaps of this team's games that went out on social: {id, date, text}."""
    ids = {r["id"]: r for r in results(key)}
    t = teams().get(key) or {}
    upcoming = {str(g.get("game_id")) for g in _schedule(str(t.get("data_dir", ""))) if key in
                ((g.get("home") or {}).get("key"), (g.get("away") or {}).get("key"))}
    out = []
    for k, when in _load(POSTED).items():
        m = re.search(r"/games/(\d+)\.html\|(\w+)$", k)
        if not m or m.group(1) not in upcoming:
            continue
        r = ids.get(m.group(1))
        what = f"{'recap' if m.group(2) == 'recap' else 'preview'}"
        vs = f" ({'W' if r['won'] else 'L'} {r['us']}-{r['them']} vs {r['opp']})" if r and what == "recap" else ""
        out.append({"id": f"post:{m.group(1)}:{m.group(2)}", "date": _ymd(when), "text": f"Social {what} posted{vs}: {k.split('|')[0].split(':', 1)[-1] if k.startswith(('threads:', 'bsky:')) else k.split('|')[0]}"})
    one = {}
    for p in sorted(out, key=lambda p: p["date"]):
        one.setdefault(p["id"], p)  # Bluesky and Threads post the same story; log it once
    return list(one.values())


def _old_log(path: Path) -> tuple[list[str], set[str]]:
    if not path.exists():
        return [], set()
    txt = path.read_text()
    if LOG_HEAD not in txt:
        return [], set()
    lines = [ln for ln in txt.split(LOG_HEAD, 1)[1].splitlines() if ln.startswith("- ")]
    return lines, {m for ln in lines for m in re.findall(r"<!-- (\S+) -->", ln)}


def render(key: str, today: str | None = None) -> str:
    t = teams()[key]
    a = anchors.roster().get(key) or {}
    from . import press
    ln = press.leans().get(key) or {}
    col = anchors.color().get(key) or {}
    dos = _load(SHARED_DIR / "anchor_dossiers.json", "dossiers").get(key) or {}
    best = _load(BEST, "schools").get(key) or {}
    p = press.papers().get(key) or {}
    b = barometer(key)
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    name = a.get("name") or "Anchor to be cast"
    paper = p.get("title") or "paper to come"
    rv = press.rival(key)

    L = [f"# {name}, {paper}", "",
         f"_{t['short']} ({t['league_name']}). {DISCLOSURE} This file grows: everything above the log is refreshed "
         f"each run, and the log keeps every entry. Last refreshed {today}._", "",
         "## Who they are", ""]
    if dos.get("bio"):
        L += [dos["bio"], ""]
    if a:
        L.append(f"- {a.get('age', '')} {a.get('gender', '').lower()}, edits *{paper}* in {p.get('town') or 'town'}, {p.get('state') or ''}".rstrip(", "))
    if col.get("voice"):
        L.append(f"- Voice: {col['voice']}")
    if col.get("catch") or col.get("signoff"):
        L.append(f"- Opens with \"{col.get('catch', '')}\" and signs off \"{col.get('signoff', '')}\"")
    if ln:
        L.append(f"- Lean (homer {ln.get('homer', '?')} of 3): {ln.get('lean', '')}")
        if ln.get("pet"):
            L.append(f"- Pet subject: {ln['pet']}")
    if rv:
        L.append(f"- Rival desk: {teams().get(rv, {}).get('short', rv)}")
    for k in ("temperament", "humor", "worldview"):
        if dos.get(k):
            L.append(f"- {k.capitalize()}: {dos[k]}")
    L.append("- House stance: logic and empathy, not power and cruelty. Fair game: rival anchors, towns, teams, the Trump "
             "administration and its circle, fascist groups and billionaires, for their public conduct. Never players, "
             "coaches, students, fans or other private people, and never a made-up quote.")
    L += ["", "## How they look", ""]
    if anchors.portrait(key):
        L.append(f"- Portrait: anchors/{key}.webp")
    if a.get("gear") or a.get("colors"):
        L.append(f"- Wears a {a.get('colors', '').lower()} {a.get('gear', '').lower()}".rstrip())
    if dos.get("look"):
        L.append(f"- {dos['look']}")
    bd = anchors.backdrop(key)
    if bd:
        L.append(f"- Set: sets/{bd.name}")
    L.append("- House look: sequins or rhinestones in team colors, never green on a green screen.")

    L += ["", "## Barometer", "",
          f"**{b['score']} of 100, {b['mood']}.** Record {b['record']} ({b['conf']} in conference)"
          + (f", streak {b['streak']}, last five {b['last5']}" if b["games"] else "") + ".", "",
          "50 is level. Recent games count most and big margins count more. The mood sets how often "
          f"{a.get('name', 'the anchor').split(' ')[0]} editorializes: "
          f"{round(100 * min(1, press.settings()['aside_rate'] * mood_rate(key)))}% of stories right now.", ""]

    L += ["## School and town", ""] + facts_lines(key) + [""]

    L += ["## The program's best", ""]
    if best.get("player"):
        L.append(f"- Best player: {best['player']}" + (f" ({best['player_years']})" if best.get("player_years") else "")
                 + (f". {best['player_why']}" if best.get("player_why") else ""))
    if best.get("run_season"):
        L.append(f"- Best run: {best['run_season']}, {best.get('run_level', '')}, {best.get('run_result', '')}."
                 + (f" {best['run_detail']}" if best.get("run_detail") else ""))
    if best.get("confidence") and best["confidence"] != "high":
        L.append(f"- Desk confidence: {best['confidence']} (check before air)")
    if not best:
        L.append("_Not researched yet._")
    L.append("")

    made = made_about(key)
    pst = posts(key)
    L += ["## What we've made about them", ""]
    L += [f"- {m['text']}" for m in made] or ["- No film or fight song yet."]
    L.append(f"- Social posts on their games: {len(pst)}")
    L.append("")

    path = OUT / f"{key}.md"
    old, seen = _old_log(path)
    new: list[tuple[str, str]] = []
    for r in results(key):
        tag = f"g:{r['id']}"
        if tag in seen:
            continue
        bb = barometer(key, before=r["date"][:10] + "T23:59Z")
        where = "vs" if r["where"] == "home" else "at" if r["where"] == "away" else "vs (neutral)"
        new.append((_ymd(r["date"]), f"{'W' if r['won'] else 'L'} {r['us']}-{r['them']} {where} {r['opp']}. "
                    f"Barometer {bb['score']} ({bb['mood']}). <!-- {tag} -->"))
    for m in made:
        if m["id"] not in seen:
            new.append((today, f"{m['text']} <!-- {m['id']} -->"))
    for pp in pst:
        if pp["id"] not in seen:
            new.append((pp["date"], f"{pp['text']} <!-- {pp['id']} -->"))
    new.sort(key=lambda x: x[0])
    L += [LOG_HEAD, ""] + old + [f"- {d}: {t_}" for d, t_ in new]
    return "\n".join(L).rstrip() + "\n"


def write_all(keys: list[str] | None = None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for k in keys or sorted(teams()):
        txt = render(k)
        p = OUT / f"{k}.md"
        if not p.exists() or p.read_text() != txt:
            p.write_text(txt)
            n += 1
    return n


if __name__ == "__main__":
    import sys
    print(f"notebooks updated: {write_all(sys.argv[1:] or None)}")
