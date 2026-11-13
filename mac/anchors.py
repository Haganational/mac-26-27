"""Courtside: a cast of AI anchors who talk about one game a night, on our own pages only.

The trial runs like this:

1. Game of the Night. Once per Eastern date (first build after 9 a.m. ET) we pick one game
   from every edition's board: tonight's games with at least one of our teams, conference
   games first, then the one our model projects closest, then the earlier tip. The pick and
   the reason are saved and never change.
2. Takes. About four hours before tip each anchor writes a pregame take; after the final
   (once a box score is in) each writes a postgame reaction. Takes are built from our own
   numbers with hand-written phrase banks, so they cost nothing and say nothing we can't
   back up. Saved once, never rewritten (data/anchors/nights/<date>.json).
3. Review. Nothing an anchor writes shows on the site until Matthew approves it on the
   Courtside desk (courtside-desk.html), which saves notes/courtside/<date>.json. That file
   also holds his own comments, which show with a human badge. Setting
   config.auto_publish_from to a date lets drafts from that night on publish without review
   (a held draft still stays down).
4. Readers. An optional hosted comment layer (Giscus or Cusdis) sits under the thread once
   config.comments is filled in. Until then the thread is anchors plus Matthew.

Every anchor comment carries a visible "AI anchor" badge and readers can hide the anchors.
Anchors never post anywhere but this site, and they don't reply to readers in this version.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .leagues import ALL, ROOT, League

ET = ZoneInfo("America/New_York")
ANCHOR_DIR = ROOT / "data" / "anchors"
NIGHTS_DIR = ANCHOR_DIR / "nights"
REVIEW_DIR = ROOT / "notes" / "courtside"
CONFIG_PATH = ANCHOR_DIR / "config.json"
CAST_PATH = ANCHOR_DIR / "cast.json"

PICK_HOUR_ET = 9  # the night's game is chosen at the first build after this hour
PREGAME_HOURS = 4  # pregame takes are written this long before tip
RULE = ("Game of the Night: of tonight's games with at least one of our teams, conference games come first, "
        "then the game our model projects closest, then the earlier tip. Picked each morning and never changed.")

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "auto_publish_from": None,  # "YYYY-MM-DD": from that night on, drafts publish without review
    "editor_name": "Matthew",
    "editor_title": "Editor",
    "comments": {"provider": ""},  # "giscus" or "cusdis"; see README
}


# ---------------------------------------------------------------- files

def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **load_json(path, {})}
    cfg["comments"] = {**DEFAULT_CONFIG["comments"], **(cfg.get("comments") or {})}
    return cfg


def load_cast(path: Path = CAST_PATH) -> list[dict[str, Any]]:
    return load_json(path, {}).get("anchors", [])


def load_night(date: str, nights_dir: Path = NIGHTS_DIR) -> dict[str, Any] | None:
    return load_json(nights_dir / f"{date}.json", None)


def save_night(night: dict[str, Any], nights_dir: Path = NIGHTS_DIR) -> None:
    nights_dir.mkdir(parents=True, exist_ok=True)
    (nights_dir / f"{night['date']}.json").write_text(json.dumps(night, indent=1) + "\n")


def load_review(date: str, review_dir: Path = REVIEW_DIR) -> dict[str, Any]:
    r = load_json(review_dir / f"{date}.json", {})
    return {"approve": list(r.get("approve") or []), "hold": list(r.get("hold") or []),
            "edit": dict(r.get("edit") or {}), "matthew": list(r.get("matthew") or [])}


# ---------------------------------------------------------------- the board

def _iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def et_date(dt: datetime) -> str:
    # A 1 a.m. ET tip still belongs to the night before.
    return (dt.astimezone(ET) - timedelta(hours=4)).strftime("%Y-%m-%d")


def latest_projections(lg: League, wanted: set[str]) -> dict[str, dict[str, Any]]:
    """The newest model row for each wanted game, read from the end of the log."""
    path = lg.data_dir / "model" / "projections.jsonl"
    out: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return out
    for line in reversed(lines):
        if len(out) == len(wanted):
            break
        try:
            row = json.loads(line)
        except ValueError:
            continue
        gid = str(row.get("game_id"))
        if gid in wanted and gid not in out:
            out[gid] = row
    return out


def team_short(lg: League, side: dict[str, Any]) -> str:
    for t in lg.teams:
        if t.espn_id == str(side.get("espn_id")):
            return t.short
    from .build import school  # late import: build imports this module
    return school(side.get("name") or side.get("abbr") or "")


def board(date: str, now: datetime, leagues: list[League] | None = None) -> list[dict[str, Any]]:
    """Every game on our board that night, one row per game (first edition in LEAGUES order owns it)."""
    rows: dict[str, dict[str, Any]] = {}
    for lg in leagues or list(ALL.values()):
        sched = load_json(lg.data_dir / "schedule.json", {}).get("games", [])
        mine = [g for g in sched if (g["home"].get("key") or g["away"].get("key")) and not g.get("completed")
                and et_date(_iso(g["date"])) == date and _iso(g["date"]) > now and g["game_id"] not in rows]
        proj = latest_projections(lg, {g["game_id"] for g in mine})
        for g in mine:
            p = proj.get(g["game_id"])
            if not p or p.get("non_d1"):
                continue
            rows[g["game_id"]] = {"g": g, "p": p, "lg": lg}
    return list(rows.values())


def pick(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return min(rows, key=lambda r: (not r["g"].get("conference_game"), abs(r["p"].get("proj_margin") or 0), r["g"]["date"]))


def _records(espn_ids: set[str]) -> dict[str, str]:
    from .config import SEASON
    games = load_json(ROOT / "data" / "ncaa" / f"games-{SEASON}.json", {}).get("games", [])
    wl = {i: [0, 0] for i in espn_ids}
    for g in games:
        h, a = g.get("home") or {}, g.get("away") or {}
        if h.get("pts") is None or a.get("pts") is None:
            continue
        for me, them in ((h, a), (a, h)):
            if me.get("id") in wl:
                wl[me["id"]][0 if me["pts"] > them["pts"] else 1] += 1
    return {i: f"{w}-{l}" for i, (w, l) in wl.items()}


def facts(row: dict[str, Any]) -> dict[str, Any]:
    """Everything the anchors may say before tip, from our own data."""
    g, p, lg = row["g"], row["p"], row["lg"]
    home, away = team_short(lg, g["home"]), team_short(lg, g["away"])
    margin = float(p.get("proj_margin") or 0)  # home minus away
    mkt = p.get("mkt_spread")  # home spread, negative = home favored
    rec = _records({str(g["home"]["espn_id"]), str(g["away"]["espn_id"])})
    flavor = load_json(lg.data_dir / "flavor.json", {}).get("teams", {})
    hf = flavor.get(g["home"].get("key") or "", {})
    tip = _iso(g["date"]).astimezone(ET)
    model_fav = home if margin >= 0 else away
    if mkt is not None:
        dog = away if mkt < 0 else home if mkt > 0 else (away if margin >= 0 else home)
        # the model's side against the number: home covers if its projected margin beats the spread
        edge = margin + float(mkt)
        number_side = home if edge > 0 else away
    else:
        dog = away if margin >= 0 else home
        edge = None
        number_side = model_fav
    if g.get("neutral_site"):
        ours = [team_short(lg, s) for s in (g["home"], g["away"]) if s.get("key")]
        homer = ours[0] if len(ours) == 1 else model_fav
    else:
        homer = home
    return {
        "game_id": g["game_id"], "edition": lg.key, "league": lg.short, "path": f"{lg.path}games/{g['game_id']}.html",
        "home": home, "away": away, "home_espn_id": str(g["home"]["espn_id"]), "away_espn_id": str(g["away"]["espn_id"]),
        "home_rec": rec.get(str(g["home"]["espn_id"]), ""), "away_rec": rec.get(str(g["away"]["espn_id"]), ""),
        "tip": g["date"], "tip_et": tip.strftime("%-I:%M p.m. ET") if tip.hour >= 12 else tip.strftime("%-I:%M a.m. ET"),
        "venue": g.get("venue") or "", "city": g.get("venue_city") or "", "floor": hf.get("home_floor") or g.get("venue") or "the building",
        "town": hf.get("town") or g.get("venue_city") or "", "neutral": bool(g.get("neutral_site")),
        "conference": bool(g.get("conference_game")), "tv": ", ".join(b["name"] for b in g.get("broadcasts") or [] if b.get("name")),
        "proj_margin": round(margin, 1), "proj_total": round(float(p.get("proj_total") or 0), 1),
        "win_prob_home": round(float(p.get("win_prob_home") or 0.5), 3), "mkt_spread": mkt,
        "model_fav": model_fav, "dog": dog, "number_side": number_side, "edge": None if edge is None else round(edge, 1),
        "homer": homer,
    }


# ---------------------------------------------------------------- what the anchors say

def _choose(options: list[str], seed: str) -> str:
    return options[int(hashlib.sha1(seed.encode()).hexdigest(), 16) % len(options)]


def _by(f: dict[str, Any]) -> str:
    """ "UNLV by 2.5", or "dead even" when the model can't split them."""
    m = abs(f["proj_margin"])
    return "dead even" if m < 0.5 else f"{f['model_fav']} by {m:.1f}"


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _spread_words(f: dict[str, Any]) -> str:
    m = f["mkt_spread"]
    if m is None:
        return "no line posted yet"
    if m == 0:
        return "a pick'em on the board"
    fav = f["home"] if m < 0 else f["away"]
    return f"{fav} {-abs(m):g}"


def side_of(anchor: dict[str, Any], f: dict[str, Any]) -> str:
    return {"home": f["homer"], "underdog": f["dog"], "model": f["number_side"]}.get(anchor.get("bias", ""), f["model_fav"])


def pregame(anchor: dict[str, Any], f: dict[str, Any], others: dict[str, str]) -> str:
    side, key, seed = side_of(anchor, f), anchor["key"], f["game_id"] + anchor["key"] + "pre"
    other = f["away"] if side == f["home"] else f["home"]
    pct = round(100 * (f["win_prob_home"] if f["model_fav"] == f["home"] else 1 - f["win_prob_home"]))
    agree = [o.split()[0] for o, s in others.items() if s == side and o != anchor["name"]]
    tail = f" For once {agree[0]} and I are on the same bench." if agree and key == "dee" else ""
    if key == "sully":
        place = f"a neutral floor in {f['city']}" if f["neutral"] else f"{f['floor']}"
        return _choose([
            f"I'll say it before anybody asks: {side}. {f['away']} has to walk into {place} and play {f['home']} at {f['tip_et']}, and buildings win games in November. {other} comes in {f['away_rec'] if other == f['away'] else f['home_rec']}. Fine. Records don't sit in the stands.",
            f"Give me {side} tonight. You know what {place} sounds like when the student section shows up? I do. {f['home']} is {f['home_rec']}, {f['away']} is {f['away_rec']}, and none of that matters once the lights come on.",
            f"{side}, and I'm not apologizing. {f['away']} at {f['home']}, {f['tip_et']}{', ' + f['tv'] if f['tv'] else ''}. Long bus ride, short memory, loud gym. That's my whole analysis and it's been right more than the computer.",
        ], seed)
    if key == "dee":
        return _choose([
            f"Everybody's looking at {f['model_fav']}. I'm looking at {side}. The board has it {_spread_words(f)}, which means somebody already decided how this goes. I like it better when the other guys didn't get the memo.{tail}",
            f"I'm riding {side}. Underdogs don't need to be better for 40 minutes, they need to be better for about six, and November gives you six-minute stretches all night. {_cap(_spread_words(f))}. Thank you, I'll take it.{tail}",
            f"{side}. Ugly game, low possessions, a couple of offensive boards, a couple of bad shots by the favorite. That's the recipe and {side} has the ingredients. Line's {_spread_words(f)}.{tail}",
        ], seed)
    if key == "ivy":
        if f["edge"] is not None:
            lead = f"Our model has it {_by(f)} with a total near {f['proj_total']:.0f}. The market says {_spread_words(f)}. That's a {abs(f['edge']):.1f}-point gap, and I go where the gap points: {side}."
        else:
            lead = f"Our model has it {_by(f)}, about a {pct} percent shot for {f['model_fav']}, with a total near {f['proj_total']:.0f}. No line yet, so I'm simply with the model: {side}."
        return _choose([
            lead + " Sully will tell you about the crowd. The crowd is in the home-court number already.",
            lead + " It's our Game of the Night because it's close, so I expect to be wrong a lot and I'm at peace with that.",
            lead + " If it's close at the under-eight timeout, watch free throw attempts. That's where projected games like this usually tip.",
        ], seed)
    return f"{anchor['name']} likes {side}."


def postgame(anchor: dict[str, Any], f: dict[str, Any], final: dict[str, Any]) -> str:
    side, key, seed = side_of(anchor, f), anchor["key"], f["game_id"] + anchor["key"] + "post"
    won = final["cover"] == side if anchor.get("bias") == "model" and final.get("cover") else final["winner"] == side
    w, l = final["winner"], final["loser"]
    score = f"{final['w_pts']}-{final['l_pts']}"
    star = final.get("star")
    star_line = f" {star['name']} had {star['pts']} for {star['team']}, and I'd buy that kid a sandwich." if star else ""
    if key == "sully":
        if won:
            return _choose([f"Told you. {w} {score}. Buildings win games.{star_line}",
                            f"{w} {score}, and I'd like the record to show I said {side} before the anthem.{star_line}"], seed)
        glass = (f" {w} won the glass {final['reb'][w]}-{final['reb'][l]}, and that's a building's whole job." if final["reb"][w] > final["reb"][l]
                 else f" {l} turned it over {final['to'][l]} times, and you can't hand anybody that many gifts.")
        return _choose([f"{w} {score}. I'll take the loss.{glass}",
                        f"Rough one. {w} {score}.{glass} Back at it tomorrow."], seed)
    if key == "dee":
        if won:
            return _choose([f"{w} {score}. Nobody believed and I don't need you to. That's the whole point of a dog.",
                            f"There it is. {w} {score}. I said six good minutes. They found about twelve."], seed)
        return _choose([f"{w} {score}. The favorite played like a favorite. Happens. I'll be back tomorrow with somebody nobody likes.",
                        f"Didn't get there. {w} {score}. {l} shot {final['fg'][l]} percent and dogs can't survive that."], seed)
    if key == "ivy":
        miss = final["margin_home"] - f["proj_margin"]
        cover = final.get("cover")
        line = f" Against the number, {cover} covered." if cover else ""
        return _choose([
            f"Final {w} {score}. The model had it {_by(f)}; it finished {w} by {abs(final['margin_home'])}, a miss of {abs(miss):.1f} points.{line} {'Fine night.' if won else 'Into the log it goes.'}",
            f"{w} {score}.{line} We projected a total near {f['proj_total']:.0f} and got {final['w_pts'] + final['l_pts']}. {'The process holds.' if won else 'The process still holds. Ask me again in February.'}",
        ], seed)
    return f"{w} {score}."


def final_from_box(f: dict[str, Any], box: dict[str, Any], hp: int, ap: int) -> dict[str, Any] | None:
    """The postgame facts: score from the schedule, the rest from our box score."""
    teams = {str(t["espn_id"]): t for t in box.get("teams", [])}
    h, a = teams.get(f["home_espn_id"]), teams.get(f["away_espn_id"])
    if not h or not a or hp == ap:
        return None
    name = {f["home_espn_id"]: f["home"], f["away_espn_id"]: f["away"]}
    w_id, l_id = (f["home_espn_id"], f["away_espn_id"]) if hp > ap else (f["away_espn_id"], f["home_espn_id"])

    def stat(t: dict[str, Any], k: str) -> int:
        try:
            return int(float(t["stats"].get(k) or 0))
        except (TypeError, ValueError):
            return 0
    top = max((p for p in box.get("players", []) if not p.get("dnp")), key=lambda p: p.get("pts") or 0, default=None)
    cover = None
    if f["mkt_spread"] is not None:
        d = (hp - ap) + float(f["mkt_spread"])
        cover = None if d == 0 else (f["home"] if d > 0 else f["away"])
    return {
        "winner": name[w_id], "loser": name[l_id], "w_pts": max(hp, ap), "l_pts": min(hp, ap), "margin_home": hp - ap,
        "reb": {name[i]: stat(teams[i], "totalRebounds") for i in name}, "to": {name[i]: stat(teams[i], "totalTurnovers") for i in name},
        "fg": {name[i]: stat(teams[i], "fieldGoalPct") for i in name}, "cover": cover,
        "star": {"name": top["name"], "pts": top["pts"], "team": name.get(str(top["team_espn_id"]), "")} if top and top.get("pts") else None,
    }


# ---------------------------------------------------------------- the nightly job

def _comment(anchor: dict[str, Any], phase: str, text: str, now: datetime) -> dict[str, Any]:
    return {"id": f"{anchor['key']}-{phase}", "who": anchor["key"], "phase": phase, "text": text,
            "written_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def advance(now: datetime, cast: list[dict[str, Any]] | None = None, nights_dir: Path = NIGHTS_DIR,
            leagues: list[League] | None = None) -> dict[str, Any] | None:
    """Pick tonight's game, write pregame takes near tip and postgame takes after the final. Idempotent."""
    cast = load_cast() if cast is None else cast
    date = et_date(now)
    night = load_night(date, nights_dir)
    if night is None and now.astimezone(ET).hour >= PICK_HOUR_ET:
        rows = board(date, now, leagues)
        chosen = pick(rows)
        night = {"date": date, "rule": RULE, "picked_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "candidates": len(rows), "game": facts(chosen) if chosen else None, "comments": []}
        if chosen:
            g = night["game"]
            why = "conference game" if g["conference"] else "game"
            pool = f"the only {why} on our board tonight" if len(rows) == 1 else f"the closest projected {why} of the {len(rows)} on our board tonight"
            night["why"] = f"{pool[0].upper()}{pool[1:]}: our model has it {_by(g)}."
        save_night(night, nights_dir)
    if night and night.get("game"):
        changed = False
        f = night["game"]
        have = {c["id"] for c in night["comments"]}
        if now >= _iso(f["tip"]) - timedelta(hours=PREGAME_HOURS):
            sides = {a["name"]: side_of(a, f) for a in cast}
            for a in cast:
                if f"{a['key']}-pre" not in have:
                    night["comments"].append(_comment(a, "pre", pregame(a, f, sides), now))
                    changed = True
        if now >= _iso(f["tip"]) and any(f"{a['key']}-post" not in have for a in cast):
            lg = ALL[f["edition"]]
            g = next((x for x in load_json(lg.data_dir / "schedule.json", {}).get("games", []) if x["game_id"] == f["game_id"]), None)
            box = load_json(lg.data_dir / "boxscores" / f"{f['game_id']}.json", None)
            fin = (final_from_box(f, box, int(g["home"]["score"]), int(g["away"]["score"]))
                   if box and g and g.get("completed") and g["home"].get("score") is not None else None)
            if fin:
                night["final"] = fin
                for a in cast:
                    if f"{a['key']}-post" not in have:
                        night["comments"].append(_comment(a, "post", postgame(a, f, fin), now))
                        changed = True
        if changed:
            save_night(night, nights_dir)
    return night


# ---------------------------------------------------------------- what the page shows

def is_live(c: dict[str, Any], date: str, review: dict[str, Any], cfg: dict[str, Any]) -> bool:
    if c["id"] in review["hold"]:
        return False
    if c["id"] in review["approve"]:
        return True
    auto = cfg.get("auto_publish_from")
    return bool(auto) and date >= str(auto)


def thread(night: dict[str, Any], cast: list[dict[str, Any]], cfg: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    """What readers see for one night: approved anchor takes and Matthew's comments, in time order."""
    by_key = {a["key"]: a for a in cast}
    items = []
    for c in night.get("comments", []):
        if not is_live(c, night["date"], review, cfg) or c["who"] not in by_key:
            continue
        items.append({"kind": "anchor", "anchor": by_key[c["who"]], "phase": c["phase"], "at": c["written_at"],
                      "text": review["edit"].get(c["id"], c["text"]), "id": c["id"]})
    for m in review["matthew"]:
        if m.get("text", "").strip():
            items.append({"kind": "human", "name": cfg["editor_name"], "title": cfg["editor_title"], "at": m.get("at", ""),
                          "text": m["text"].strip(), "id": m.get("id", "")})
    items.sort(key=lambda x: x["at"])
    for x in items:
        try:
            x["at_et"] = _iso(x["at"]).astimezone(ET).strftime("%b %-d, %-I:%M %p ET")
        except ValueError:
            x["at_et"] = ""
    pending = sum(1 for c in night.get("comments", []) if c["id"] not in review["approve"] and c["id"] not in review["hold"]
                  and not is_live(c, night["date"], review, cfg))
    return {"night": night, "game": night["game"], "posts": items, "pending": pending, "cast": cast, "cfg": cfg,
            "comments": cfg["comments"], "rule": night.get("rule", RULE), "why": night.get("why", "")}


def all_threads(nights_dir: Path = NIGHTS_DIR, review_dir: Path = REVIEW_DIR) -> list[dict[str, Any]]:
    cfg, cast = load_config(), load_cast()
    out = []
    for p in sorted(nights_dir.glob("*.json"), reverse=True):
        night = load_json(p, None)
        if night and night.get("game"):
            out.append(thread(night, cast, cfg, load_review(night["date"], review_dir)))
    return out


def refresh(now: datetime) -> dict[str, dict[str, Any]]:
    """Called by every edition's build: move tonight along, then return game id -> thread for the pages."""
    if not load_config().get("enabled", True):
        return {}
    try:
        advance(now)
    except Exception as exc:  # noqa: BLE001 - the anchors must never stop the site from publishing
        print(f"anchors: skipped ({exc!r})")
    return {t["game"]["game_id"]: t for t in all_threads()}


def render_pages(env: Any, site_dir: Path, data: dict[str, Any]) -> None:
    """courtside.html (tonight, the cast, the rule, earlier nights) and the private courtside-desk.html."""
    threads = all_threads()
    cast = load_cast()
    today = et_date(datetime.fromisoformat(data["generated_at"]))
    tonight = next((t for t in threads if t["night"]["date"] == today), None)
    (site_dir / "courtside.html").write_text(env.get_template("courtside.html").render(
        d=data, tonight=tonight, past=[t for t in threads if t is not tonight], cast=cast, rule=RULE))
    (site_dir / "courtside-desk.html").write_text(env.get_template("courtside-desk.html").render(
        d=data, nights=threads, cast=cast))
