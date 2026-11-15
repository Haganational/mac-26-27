"""Image posts for the social accounts, drawn from the data the nightly build already has.

    python -m mac.cards --kind potn --out out/cards        # render one kind for today (Eastern)
    python -m mac.cards --kind all --date 2026-11-15 --out out/cards

Four kinds (Matthew picked these on Nov 15, 2026 from the preview page):

  potn     Mid-Major Players of the Night: a carousel, one slide per edition, from last night's
           box scores (best game score among our schools in each edition).
  bricked  The night's biggest miss: the largest closing-spread favorite that lost outright in a
           game with one of our schools. Skipped on a night without one (favorite of 3+ points).
  slate    Tonight's Four: the four best games today with our schools, by TV and stakes.
  desk     Beat the Desk: today's desk anchor and their Pick 4 from data/den/desk/<date>.json.

Each card is 1080x1350 (Instagram portrait) drawn in HTML with the house fonts and shot with
headless Chrome, then saved as JPEG (Instagram takes only JPEG). render() writes the images and a
<kind>.json beside them with the captions for every network; mac.cardpost posts them.

Captions differ by network on purpose: the same words posted everywhere at the same minute reads
as spam. The first line of each network's caption is fixed for the day, so a re-run can find
what it already posted.
"""
from __future__ import annotations

import argparse
import html
import json
import tempfile
from dataclasses import dataclass, field
from datetime import date as Date, datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image

from . import anchors
from .den import ET, TEAM, data_dirs, load_boxes, load_games, parse_iso
from .leagues import ALL, ROOT

W, H = 1080, 1350
SITE = "https://hardwoodbricks.com"
KINDS = ("potn", "bricked", "slate", "desk")
DISCLOSURE = "Anchors are fictional AI personas, not affiliated with any school."
MIN_BRICK = 3.0  # a favorite must have been at least this many points to count as bricked
NATIONAL_TV = ("ESPN", "ESPN2", "ESPNU", "FS1", "FS2", "CBS", "CBSSN", "BTN", "CW", "FOX", "NBC", "TNT", "truTV", "USA")


@dataclass
class Card:
    kind: str
    day: str  # the ET date the card is about (last night for potn/bricked, today for slate/desk)
    slides: list[str]  # HTML bodies, one per image
    captions: dict[str, str]  # network -> full caption
    alt: list[str] = field(default_factory=list)  # alt text per slide
    link: str = SITE


# ---------------------------------------------------------------- data


def team_of(espn_id: Any) -> tuple[Any, Any] | None:
    return TEAM.get(str(espn_id))


_NAMES: dict[str, dict[str, str]] | None = None


def nick(side: dict[str, Any]) -> str:
    """A short school name for any D-I team ("Brown", not "Brown Bears")."""
    global _NAMES
    tl = team_of(side.get("espn_id"))
    if tl:
        return tl[0].short
    if _NAMES is None:
        from .den import load_names
        _NAMES = load_names(ROOT / "data" / "model" / "ratings.json")
    got = (_NAMES.get(str(side.get("espn_id"))) or {}).get("short")
    return got or side.get("name", "").rsplit(" ", 1)[0]


def anchor_for(key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    a = anchors.roster().get(key)
    p = anchors.portrait(key)
    if not a:
        return None
    c = anchors.color().get(key, {})
    return {"key": key, "name": a["name"], "first": anchors.first_name(a["name"]), "portrait": p,
            "catch": c.get("catch", ""), "signoff": c.get("signoff", "")}


def et_day(iso: str) -> str:
    return parse_iso(iso).astimezone(ET).date().isoformat()


def game_score(p: dict[str, Any]) -> float:
    """Hollinger's game score from a box-score line."""
    q = {k: (p.get(k) or 0) for k in ("pts", "fgm", "fga", "ftm", "fta", "oreb", "dreb", "stl", "ast", "blk", "pf", "to")}
    return (q["pts"] + 0.4 * q["fgm"] - 0.7 * q["fga"] - 0.4 * (q["fta"] - q["ftm"]) + 0.7 * q["oreb"] + 0.3 * q["dreb"]
            + q["stl"] + 0.7 * q["ast"] + 0.7 * q["blk"] - 0.4 * q["pf"] - q["to"])


def games_on(day: str, games: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    games = games if games is not None else load_games(data_dirs())
    return sorted((g for g in games.values() if et_day(g["date"]) == day), key=lambda g: g["date"])


def players_of_the_night(day: str, games: dict[str, dict[str, Any]] | None = None,
                         boxes: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The best line by one of our players in each edition on `day`, best first."""
    finals = [g for g in games_on(day, games) if g.get("completed")]
    boxes = boxes if boxes is not None else load_boxes(data_dirs(), {g["game_id"] for g in finals})
    best: dict[str, dict[str, Any]] = {}
    for g in finals:
        b = boxes.get(g["game_id"])
        if not b:
            continue
        side = {str(g["home"]["espn_id"]): g["home"], str(g["away"]["espn_id"]): g["away"]}
        for p in b.get("players", []):
            tl = team_of(p.get("team_espn_id"))
            if p.get("dnp") or p.get("pts") is None or not tl:
                continue
            team, lg = tl
            us = side.get(str(p["team_espn_id"]))
            them = next((v for k, v in side.items() if k != str(p["team_espn_id"])), None)
            if not us or not them:
                continue
            row = {"gs": round(game_score(p), 1), "name": p["name"], "pts": p.get("pts") or 0, "reb": p.get("reb") or 0,
                   "ast": p.get("ast") or 0, "fgm": p.get("fgm") or 0, "fga": p.get("fga") or 0, "tpm": p.get("tpm") or 0,
                   "stl": p.get("stl") or 0, "blk": p.get("blk") or 0, "team": team, "league": lg, "won": bool(us.get("winner")),
                   "us": us.get("score"), "them": them.get("score"), "opp": nick(them),
                   "home": us is g["home"], "neutral": bool(g.get("neutral_site")), "game_id": g["game_id"]}
            if lg.key not in best or row["gs"] > best[lg.key]["gs"]:
                best[lg.key] = row
    return sorted(best.values(), key=lambda r: -r["gs"])


def closing_spreads(day: str) -> list[dict[str, Any]]:
    """The last spread captured before tip for each event on `day`: favorite key/name, points."""
    last: dict[str, dict[str, Any]] = {}
    for lg in ALL.values():
        d = lg.data_dir / "lines"
        for f in (d / f"{day}.jsonl", d / f"{(Date.fromisoformat(day) + timedelta(days=1)).isoformat()}.jsonl"):
            if not f.exists():
                continue
            for line in f.read_text().splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("market") != "spreads" or r.get("point") is None or et_day(r["commence_time"]) != day:
                    continue
                if r.get("captured_at", "") > r["commence_time"]:
                    continue
                if r["outcome"] != r["home_team"]:
                    continue
                k = r["odds_event_id"]
                if k not in last or r["captured_at"] > last[k]["captured_at"]:
                    last[k] = r
    out = []
    for r in last.values():
        home_fav = float(r["point"]) < 0
        out.append({"points": abs(float(r["point"])), "fav_key": r.get("home_key") if home_fav else r.get("away_key"),
                    "dog_key": r.get("away_key") if home_fav else r.get("home_key"),
                    "fav_name": r["home_team"] if home_fav else r["away_team"],
                    "dog_name": r["away_team"] if home_fav else r["home_team"], "commence": r["commence_time"]})
    return out


def bricks(day: str, games: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Favorites of MIN_BRICK+ points that lost outright on `day`, biggest first."""
    finals = [g for g in games_on(day, games) if g.get("completed")]
    by_key: dict[str, dict[str, Any]] = {}
    for g in finals:
        for s in ("home", "away"):
            tl = team_of(g[s]["espn_id"])
            if tl:
                by_key.setdefault(tl[0].key, g)
    out = []
    for s in closing_spreads(day):
        if s["points"] < MIN_BRICK:
            continue
        g = by_key.get(s["fav_key"] or "") or by_key.get(s["dog_key"] or "")
        if not g:
            continue
        sides = {}
        for side in ("home", "away"):
            tl = team_of(g[side]["espn_id"])
            sides[tl[0].key if tl else f"x{side}"] = g[side]
        fav = sides.get(s["fav_key"]) if s["fav_key"] else None
        dog = sides.get(s["dog_key"]) if s["dog_key"] else None
        if fav is None and dog is None:
            continue
        if fav is None:
            fav = g["home"] if dog is g["away"] else g["away"]
        if dog is None:
            dog = g["home"] if fav is g["away"] else g["away"]
        if not dog.get("winner"):
            continue
        out.append({"points": s["points"], "fav": fav, "dog": dog, "fav_key": s["fav_key"], "dog_key": s["dog_key"],
                    "game": g, "fav_home": fav is g["home"] and not g.get("neutral_site")})
    return sorted(out, key=lambda b: -b["points"])


def tonights_four(day: str, games: dict[str, dict[str, Any]] | None = None, n: int = 4) -> list[dict[str, Any]]:
    """Today's best games with our schools: national TV first, then conference games, then earliest."""
    todays = [g for g in games_on(day, games) if not g.get("completed") and g.get("status") not in
              ("STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED")]

    def tv(g: dict[str, Any]) -> str:
        names = [b.get("name", "") for b in g.get("broadcasts") or []]
        nat = [x for x in names if x in NATIONAL_TV]
        return (nat or names or [""])[0]

    def score(g: dict[str, Any]) -> tuple:
        return (-(tv(g) in NATIONAL_TV), -bool(g.get("conference_game")), g["date"])
    picked = sorted(todays, key=score)[:n]
    out = []
    for g in sorted(picked, key=lambda g: g["date"]):
        ours = [s for s in ("home", "away") if team_of(g[s]["espn_id"])]
        lead = "home" if "home" in ours else ours[0] if ours else "home"
        other = "away" if lead == "home" else "home"
        tl = team_of(g[lead]["espn_id"])
        out.append({"game": g, "lead": g[lead], "other": g[other], "lead_home": lead == "home",
                    "neutral": bool(g.get("neutral_site")), "tv": tv(g), "team": tl[0] if tl else None,
                    "tip": parse_iso(g["date"]).astimezone(ET)})
    return out


def desk(day: str) -> dict[str, Any] | None:
    f = ROOT / "data" / "den" / "desk" / f"{day}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text()).get("desk") or {}
    return d if d.get("picks") and d.get("anchor") else None


# ---------------------------------------------------------------- drawing

def _esc(s: Any) -> str:
    return html.escape(str(s))


def short(team_name: str, team: Any = None) -> str:
    return team.short if team is not None else team_name


def tip_time(t: datetime) -> str:
    return t.strftime("%I:%M").lstrip("0")


def pretty_day(day: str) -> str:
    d = Date.fromisoformat(day)
    return f"{d.strftime('%A')}, {d.strftime('%b.').replace('May.', 'May').replace('Jun.', 'June').replace('Jul.', 'July')} {d.day}"


def light(hexcolor: str) -> bool:
    h = hexcolor.lstrip("#")
    if len(h) != 6:
        return False
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b > 160


def accent(team: Any) -> str:
    """A second color that reads on the team's primary."""
    return team.color2 if team.color2.upper() not in ("#FFFFFF", "#FFF") and not light(team.color) else "#d6a34a"


CSS = """
:root{--night:#15120f;--paper:#efe7da;--ink:#e9e1d3;--dim:#a39787;--brick:#a8442c;--brick2:#8d3824;--mortar:#3a2f27;--gold:#d6a34a}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;overflow:hidden;background:var(--night)}
body{font-family:"Barlow",sans-serif;color:var(--paper)}
.card{position:relative;width:1080px;height:1350px;overflow:hidden;background:var(--night)}
.kick{font-family:"Barlow Condensed";font-weight:600;text-transform:uppercase;letter-spacing:.16em;font-size:32px}
.cond{font-family:"Barlow Condensed";font-weight:700;text-transform:uppercase}
.serif{font-family:"Newsreader"}
.por{position:absolute;bottom:0;right:-54px;width:540px;z-index:1}
.bricks{position:absolute;left:0;right:0;bottom:0;height:26px;z-index:2;background:repeating-linear-gradient(90deg,var(--brick) 0 97px,var(--night) 97px 103px)}
.bricks::before{content:"";position:absolute;left:-51px;right:0;top:-31px;height:26px;background:repeating-linear-gradient(90deg,var(--brick2) 0 97px,var(--night) 97px 103px)}
.brand{position:absolute;left:54px;right:54px;bottom:46px;display:flex;justify-content:space-between;align-items:baseline;font-family:"Barlow Condensed";font-weight:600;text-transform:uppercase;letter-spacing:.12em;font-size:28px;color:var(--dim);z-index:3}
.brand b{color:var(--paper);font-weight:700}
.quote{font-family:"Newsreader";font-style:italic;font-size:36px;line-height:1.3}
.who{font-family:"Barlow Condensed";font-weight:600;text-transform:uppercase;letter-spacing:.08em;font-size:26px;color:var(--dim);font-style:normal}
"""


def brand(right: str = "hardwoodbricks.com", left: str = "Hardwood Bricks") -> str:
    return f'<div class="bricks"></div><div class="brand"><span><b>{_esc(left)}</b></span><span>{_esc(right)}</span></div>'


def portrait_img(a: dict[str, Any] | None, style: str = "") -> str:
    if not a or not a.get("portrait"):
        return ""
    return f'<img class="por" style="{style}" src="{a["portrait"].resolve().as_uri()}" alt="">'


def page(body: str) -> str:
    from .midmaxx60 import font_faces
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{font_faces()}{CSS}</style></head><body>{body}</body></html>'


def stat_line(r: dict[str, Any]) -> tuple[str, str]:
    """The big numbers and their label: '28·12' / 'points · rebounds'."""
    extras = [("reb", "rebounds", 10), ("ast", "assists", 7), ("blk", "blocks", 5), ("stl", "steals", 5)]
    for k, name, floor in extras:
        if r[k] >= floor:
            return f"{r['pts']}·{r[k]}", f"points · {name}"
    return str(r["pts"]), "points"


def result_line(r: dict[str, Any]) -> str:
    opp = r["opp"]
    if r["won"]:
        where = "beat" if r["home"] or r["neutral"] else "won at"
        return f"{where} {opp} {r['us']}-{r['them']}" if where == "beat" else f"won {r['us']}-{r['them']} at {opp}"
    where = "lost to" if r["home"] or r["neutral"] else "lost at"
    return f"{where} {opp} {r['them']}-{r['us']}"


def potn_card(day: str, rows: list[dict[str, Any]]) -> Card | None:
    if not rows:
        return None
    n = len(rows)
    lines = "".join(f'{_esc(r["name"])} · {_esc(r["team"].short)} · {_esc(stat_line(r)[0].replace("·", " & "))}<br>' for r in rows[:4])
    more = f'<span style="color:var(--dim)">+ {n - 4} more · swipe →</span>' if n > 4 else '<span style="color:var(--dim)">swipe →</span>'
    cover = f'''<div class="card"><div style="position:absolute;inset:0;background:radial-gradient(120% 70% at 50% 0%,#3a2a1e 0%,var(--night) 70%)"></div>
 <div style="position:absolute;left:66px;right:66px;top:100px;z-index:2">
  <div class="kick" style="color:var(--gold)">{_esc(pretty_day(day))} · {n} edition{"s" if n != 1 else ""}</div>
  <div class="serif" style="font-weight:600;font-size:162px;line-height:.92;margin-top:44px">Mid-Major<br>Players<br><i style="font-weight:400">of the Night</i></div>
  <div class="cond" style="font-weight:600;letter-spacing:.06em;font-size:44px;margin-top:70px;line-height:1.5;color:var(--ink)">{lines}{more}</div>
 </div>{brand()}</div>'''
    slides, alts = [cover], [f"Mid-Major Players of the Night, {pretty_day(day)}: " + "; ".join(
        f'{r["name"]}, {r["team"].short}, {stat_line(r)[0].replace("·", " and ")}' for r in rows)]
    for r in rows:
        t, lg = r["team"], r["league"]
        a = anchor_for(t.key)
        big, label = stat_line(r)
        c2 = accent(t)
        shot = f'{r["fgm"]}-of-{r["fga"]} from the floor' + (f', {r["tpm"]} threes' if r["tpm"] >= 4 else "")
        sub = f'{shot}. {"" if r["won"] else "In a loss, still the best line in the " + lg.short + "."}'
        quote = (f'<div class="quote" style="color:var(--dim);margin-top:44px">“{_esc(a["catch"])}”<br><span class="who">{_esc(a["name"])}, '
                 f'{_esc(t.short)} AI anchor</span></div>') if a and a["catch"] else ""
        name_size = 134 if len(r["name"]) <= 16 else 110 if len(r["name"]) <= 22 else 92
        slides.append(f'''<div class="card" style="background:linear-gradient(160deg,{t.color} 0%,{t.color} 46%,var(--night) 46.2%)">
 <div style="position:absolute;left:54px;top:54px;right:54px;z-index:2">
  <div class="kick" style="color:{c2}">{_esc(lg.short)} · Player of the Night</div>
  <div class="cond" style="font-size:{name_size}px;line-height:.88;margin-top:22px;max-width:720px">{_esc(r["name"])}</div>
  <div class="serif" style="font-style:italic;font-size:44px;margin-top:20px;opacity:.92">{_esc(t.short)} · {_esc(result_line(r))}</div>
 </div>
 <div style="position:absolute;left:54px;top:650px;z-index:2;max-width:560px">
  <div class="cond" style="font-size:160px;line-height:.9">{_esc(big)}</div>
  <div class="cond" style="font-weight:600;letter-spacing:.1em;font-size:36px;color:{c2}">{_esc(label)}</div>
  <div style="font-size:36px;color:var(--ink);margin-top:30px;line-height:1.35">{_esc(sub)}</div>
  {quote}
 </div>{portrait_img(a)}{brand("" if a and a.get("portrait") else "hardwoodbricks.com", "Hardwood Bricks · box score: link in bio")}</div>''')
        alts.append(f'{r["name"]} of {t.short}: {r["pts"]} points, {r["reb"]} rebounds, {r["ast"]} assists, {result_line(r)}.')
    top = rows[0]
    big = stat_line(top)[0].replace("·", " and ")
    link = f"{SITE}/players.html"
    tags = " ".join(sorted({"#" + (r["league"].hashtag or r["league"].short).lstrip("#").replace(" ", "").replace("-", "") for r in rows[:3]}))
    caps = {
        "instagram": f"Mid-Major Players of the Night, {pretty_day(day)}.\n\n{top['name']} put up {big} for {top['team'].short}. "
                     f"Swipe for the best line in every edition we cover. Box scores: link in bio.\n\n#MidMaxxing #CollegeBasketball {tags}\n\n{DISCLOSURE}",
        "facebook": f"Players of the Night from {n} mid-major leagues, {pretty_day(day)}.\n\n"
                    + "\n".join(f"{r['league'].short}: {r['name']}, {r['team'].short} ({stat_line(r)[0].replace('·', ' and ')})" for r in rows)
                    + f"\n\nBox scores and recaps: {link}\n\n{DISCLOSURE}",
        "threads": f"{n} leagues, {n} best lines from {Date.fromisoformat(day).strftime('%A')}. {top['team'].short}'s {top['name']} ({big}) leads the way. Which one's your guy?",
        "bluesky": f"Mid-Major Players of the Night, {pretty_day(day)} 🧱\n{top['name']}, {top['team'].short}: {big}.\nAll {n}: {link}",
    }
    return Card("potn", day, slides, caps, alts, link)


def bricked_card(day: str, b: dict[str, Any] | None, also: list[dict[str, Any]]) -> Card | None:
    if not b:
        return None
    g, fav, dog = b["game"], b["fav"], b["dog"]
    ft, dt = team_of(fav["espn_id"]), team_of(dog["espn_id"])
    fname, dname = nick(fav), nick(dog)
    margin = int(dog["score"]) - int(fav["score"])
    pts = f'{b["points"]:g}'
    a = anchor_for(dt[0].key if dt else None) or anchor_for(ft[0].key if ft else None)
    dog_color = dt[0].color if dt else "#a8442c"
    where = "at home" if b["fav_home"] else ("on a neutral floor" if g.get("neutral_site") else "on the road")
    won_by = "by one" if margin == 1 else f"by {margin}"
    also_line = ""
    if also:
        x = also[0]
        also_line = (f'Also bricked: {_esc(nick(x["fav"]))}, −{x["points"]:g}, lost '
                     f'{x["dog"]["score"]}-{x["fav"]["score"]} to {_esc(nick(x["dog"]))}.')
    quote = (f'<div style="position:absolute;right:40px;top:440px;z-index:3;max-width:330px;text-align:right;background:rgba(21,18,15,.72);'
             f'padding:16px 22px;border-radius:10px" class="quote">“{_esc(a["catch"])}”<br><span class="who">{_esc(a["name"])}, AI anchor</span></div>') if a and a["catch"] else ""
    slide = f'''<div class="card">
 <div style="position:absolute;left:54px;right:54px;top:54px;z-index:2">
  <div class="kick" style="color:var(--brick)">Bricked · {_esc(Date.fromisoformat(day).strftime("%A"))}'s biggest miss</div>
  <div class="cond" style="font-size:226px;line-height:.8;margin-top:30px">Bricked.</div>
  <div class="serif" style="font-size:64px;line-height:1.1;margin-top:44px;max-width:620px">{_esc(fname)} was a <b>{pts}-point</b> favorite {where}.</div>
  <div class="serif" style="font-style:italic;font-size:64px;line-height:1.1;margin-top:10px;color:var(--gold);max-width:620px">{_esc(dname)} won {won_by}.</div>
  <div class="cond" style="display:flex;gap:40px;margin-top:60px;font-size:80px;line-height:1">
   <div><span style="background:{dog_color};color:#fff;padding:0 20px">{_esc(dog.get("abbr") or dname)} {dog["score"]}</span></div>
   <div style="color:var(--dim)">{_esc(fav.get("abbr") or fname)} {fav["score"]}</div></div>
  <div style="font-size:34px;color:var(--dim);margin-top:50px;max-width:600px;line-height:1.4">{also_line}</div>
 </div>{portrait_img(a, "width:430px;right:-60px")}{quote}{brand("" if a and a.get("portrait") else "hardwoodbricks.com")}</div>'''
    link = f"{SITE}/"
    head_score = f"{dname} {dog['score']}, {fname} {fav['score']}"
    caps = {
        "threads": f"{fname} was −{pts} {where}. {dname} won {won_by}. Somebody check on the {fname} desk.",
        "bluesky": f"Bricked 🧱 {fname} (−{pts}) lost outright: {head_score}. {pretty_day(day)}.\n{link}",
        "facebook": f"Biggest miss of {Date.fromisoformat(day).strftime('%A')}: {dname} (+{pts}) beat {fname} outright, {head_score}.\n\n"
                    f"Every recap: {link}\n\n{DISCLOSURE}",
        "instagram_story": "",
    }
    return Card("bricked", day, [slide], caps, [f"Bricked: {fname}, a {pts}-point favorite, lost {dog['score']}-{fav['score']} to {dname}."], link)


def slate_card(day: str, four: list[dict[str, Any]], total: int) -> Card | None:
    if not four:
        return None
    rows = ""
    for s in four:
        lead = s["team"].short if s["team"] else s["lead"].get("name", "")
        other = nick(s["other"])
        how = "vs" if s["lead_home"] or s["neutral"] else "at"
        color = s["team"].color if s["team"] else "#a8442c"
        rows += f'''<div style="display:grid;grid-template-columns:190px 1fr auto;gap:30px;align-items:center;border-top:3px solid var(--mortar);padding:34px 0">
  <div class="cond" style="font-size:76px;line-height:1">{tip_time(s["tip"])}<span style="font-size:32px;color:var(--dim);font-weight:600"> {s["tip"].strftime("%p")}</span></div>
  <div><div class="cond" style="font-size:66px;line-height:1;border-left:15px solid {color};padding-left:22px">{_esc(lead)}</div>
  <div class="serif" style="font-style:italic;font-size:40px;color:var(--dim);padding-left:37px">{how} {_esc(other)}</div></div>
  <div class="cond" style="letter-spacing:.08em;font-size:34px;color:var(--gold);font-weight:600">{_esc(s["tv"])}</div></div>'''
    head = "Tonight's Four" if four[0]["tip"].hour >= 17 else "Today's Four"
    slide = f'''<div class="card"><div style="position:absolute;left:66px;right:66px;top:66px;z-index:2">
  <div class="kick" style="color:var(--gold)">{_esc(pretty_day(day))} · all times Eastern</div>
  <div class="serif" style="font-weight:600;font-size:130px;line-height:1;margin:22px 0 44px">{head}</div>
  {rows}
  <div style="border-top:3px solid var(--mortar);padding-top:32px;font-size:36px;color:var(--dim)">Our pick and the line for all {total} games: hardwoodbricks.com</div>
 </div>{brand()}</div>'''

    def say(s: dict[str, Any]) -> str:
        lead = s["team"].short if s["team"] else s["lead"].get("name", "")
        other = nick(s["other"])
        how = "vs" if s["lead_home"] or s["neutral"] else "at"
        return f"{lead} {how} {other} ({tip_time(s['tip'])} {s['tip'].strftime('%p')}{', ' + s['tv'] if s['tv'] else ''})"
    link = f"{SITE}/"
    caps = {
        "bluesky": f"{head}, {pretty_day(day)}: " + "; ".join(say(s) for s in four) + f". All {total}: {link}",
        "threads": f"Four worth your {'night' if head.startswith('Tonight') else 'day'}: " + ", ".join(say(s) for s in four)
                   + ". Which one are you watching?",
        "instagram_story": "",
    }
    return Card("slate", day, [slide], caps, [f"{head}: " + "; ".join(say(s) for s in four)], link)


def desk_card(day: str, d: dict[str, Any] | None) -> Card | None:
    if not d:
        return None
    a = d["anchor"]
    key = a.get("key")
    first = anchors.first_name(a["name"])
    an = anchor_for(key) or {"portrait": None, "catch": ""}
    names = {}
    for g in load_games(data_dirs()).values():
        names[g["game_id"]] = g
    rows = ""
    for p in d["picks"]:
        g = names.get(p["game_id"])
        opp = ""
        if g:
            other = g["home"] if p["side"] == "away" else g["away"]
            opp = ("at " if p["side"] == "away" and not g.get("neutral_site") else "vs ") + nick(other)
        why = "Homer pick. Always." if p.get("kind") == "homer" else p.get("why", "").replace("Our ratings", "Ratings").replace("pregame win chance", "market").rstrip(".")
        rows += f'''<div style="display:grid;grid-template-columns:1fr auto;gap:20px;align-items:center;border-top:3px solid rgba(255,255,255,.18);padding:20px 0">
 <div><div class="cond" style="font-size:56px;line-height:1">{_esc(p["short"])}</div>
 <div style="font-size:29px;color:#d8cde6;margin-top:4px">{_esc(opp)} · {_esc(why)}</div></div>
 <div class="cond" style="font-size:58px;color:var(--gold)">{p.get("worth", "")}<span style="font-size:26px;font-weight:600"> PTS</span></div></div>'''
    c = a.get("color") or "#2c1846"
    quote = f'<div class="quote" style="font-size:36px;margin-top:26px">“{_esc(an["catch"])}”</div>' if an.get("catch") else ""
    slide = f'''<div class="card" style="background:linear-gradient(180deg,{c} 0%,var(--night) 100%)">
 <div style="position:absolute;inset:0;background:rgba(10,8,6,.25)"></div>
 <div style="position:absolute;left:54px;top:54px;right:54px;z-index:2">
  <div class="kick" style="color:var(--gold)">Beat the Desk · {_esc(pretty_day(day))}</div>
  <div class="cond" style="font-size:100px;line-height:.9;margin-top:22px">Think you're<br>smarter than<br>{_esc(first)}?</div>
 </div>{portrait_img(an, "width:470px;right:-50px")}
 <div style="position:absolute;left:54px;top:450px;width:620px;z-index:2">{rows}{quote}
  <div class="cond" style="font-weight:600;letter-spacing:.08em;font-size:32px;color:var(--gold);margin-top:22px">Play in the Den · locks at tip</div>
 </div>{brand("", "Hardwood Bricks · the Den: link in bio")}</div>'''
    link = f"{SITE}/den.html"
    homer = next((p["short"] for p in d["picks"] if p.get("kind") == "homer"), None)
    picks = ", ".join(p["short"] for p in d["picks"])
    caps = {
        "instagram": f"Beat the Desk, {pretty_day(day)}. Today's anchor is {a['name']} from the {a.get('school', '')} desk, and these are the four picks. "
                     f"Think you can do better? Play in the Den: link in bio.\n\n#MidMaxxing #CollegeBasketball #BeatTheDesk\n\n{DISCLOSURE}",
        "facebook": f"Today's desk anchor is {a['name']} ({a.get('school', '')}). Four picks: {picks}. Think you can beat them? "
                    f"Make yours in the Den before tip: {link}\n\n{DISCLOSURE}",
        "threads": (f"{first} from the {a.get('school', '')} desk has {homer} today. Of course. " if homer else f"{first} is on the desk today. ")
                   + "Beat the four picks in the Den.",
        "bluesky": f"Beat the Desk, {pretty_day(day)}: {a['name']} ({a.get('school', '')}) picks {picks}. Your turn: {link}",
    }
    return Card("desk", day, [slide], caps, [f"Beat the Desk: {a['name']} picks {picks}."], link)


def build(kind: str, today: str) -> Card | None:
    """The card for `kind` on the ET date `today` (potn and bricked look at the night before)."""
    last_night = (Date.fromisoformat(today) - timedelta(days=1)).isoformat()
    if kind == "potn":
        return potn_card(last_night, players_of_the_night(last_night))
    if kind == "bricked":
        bs = bricks(last_night)
        return bricked_card(last_night, bs[0] if bs else None, bs[1:2])
    if kind == "slate":
        games = load_games(data_dirs())
        todays = [g for g in games_on(today, games) if not g.get("completed")]
        return slate_card(today, tonights_four(today, games), len(todays))
    if kind == "desk":
        return desk_card(today, desk(today))
    raise ValueError(kind)


# ---------------------------------------------------------------- render

def shoot_jpeg(html_text: str, jpg: Path) -> None:
    from .midmaxx60 import shoot
    with tempfile.TemporaryDirectory() as tmp:
        h = Path(tmp) / "card.html"
        h.write_text(html_text)
        png = Path(tmp) / "card.png"
        shoot(h, png, W, H)
        Image.open(png).convert("RGB").save(jpg, "JPEG", quality=88, optimize=True, progressive=True)


def render(card: Card, out: Path) -> dict[str, Any]:
    """Write <out>/<kind>-<n>.jpg for every slide and <out>/<kind>.json; returns the manifest."""
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for i, body in enumerate(card.slides, 1):
        jpg = out / f"{card.kind}-{card.day}-{i}.jpg"
        shoot_jpeg(page(body), jpg)
        files.append(jpg.name)
    man = {"kind": card.kind, "day": card.day, "files": files, "captions": card.captions, "alt": card.alt, "link": card.link}
    (out / f"{card.kind}.json").write_text(json.dumps(man, indent=1))
    return man


def today_et() -> str:
    return datetime.now(ET).date().isoformat()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="all", choices=KINDS + ("all",))
    ap.add_argument("--date", default="", help="the ET date to post on (default: today)")
    ap.add_argument("--out", default="out/cards")
    ap.add_argument("--html", action="store_true", help="write the HTML instead of shooting it (for a quick look)")
    a = ap.parse_args()
    day = a.date or today_et()
    out = Path(a.out)
    for kind in (KINDS if a.kind == "all" else (a.kind,)):
        card = build(kind, day)
        if not card:
            print(f"cards: {kind}: nothing to post for {day}")
            continue
        if a.html:
            out.mkdir(parents=True, exist_ok=True)
            for i, body in enumerate(card.slides, 1):
                (out / f"{kind}-{i}.html").write_text(page(body))
            print(f"cards: {kind}: {len(card.slides)} slide(s) as HTML in {out}")
            continue
        man = render(card, out)
        print(f"cards: {kind}: {len(man['files'])} image(s) for {card.day}")


if __name__ == "__main__":
    main()
