"""MAC90: a 90-second daily read built only from our own data.

Every fact in the script comes from the schedule, box scores, closing lines and the
model. Nothing is invented: if a number is missing, the sentence is left out.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from typing import Any

from . import schedule_view
from .config import BY_KEY

WPM = 155  # a calm read; 90 seconds is about 230 words
TARGET_WORDS = 230

# Nicknames that are more than one word, so "Campbell Fighting Camels" becomes "Campbell".
_TWO_WORD = {
    "fighting camels", "golden eagles", "blue devils", "red storm", "fighting irish", "tar heels", "nittany lions",
    "mean green", "golden flashes", "thundering herd", "ragin' cajuns", "red raiders", "blue raiders",
    "golden gophers", "crimson tide", "sun devils", "horned frogs", "yellow jackets", "demon deacons", "wolf pack",
    "running rebels", "big red", "black bears", "great danes", "river hawks", "purple eagles", "golden griffins",
    "red foxes", "mountain hawks", "fighting hawks", "golden hurricane", "golden lions", "delta devils", "blue hose",
    "red wolves", "green wave", "scarlet knights", "rainbow warriors", "golden bears", "fighting illini",
    "golden grizzlies", "golden panthers", "purple aces", "blue hens", "red flash", "black knights", "golden knights",
    "blue demons", "fighting bees", "golden rams", "red hawks", "sea hawks", "war hawks", "golden tornado",
    "blue jays", "fighting scots", "flying dutchmen", "fighting saints", "golden falcons", "lady",
}


# A nickname's first word that almost never ends a school name ("Muskingum Fighting Muskies").
_NICK_LEAD = {"fighting", "golden", "blue", "red", "big", "mean", "black", "purple", "lady", "crimson", "scarlet",
              "running", "flying", "great", "green", "orange", "silver", "ragin'", "thundering", "demon", "sun",
              "horned", "yellow", "tar", "nittany", "rainbow", "sea", "war", "river", "mountain", "delta", "wolf"}


def school(name: str | None, key: str | None = None) -> str:
    """Short school name: our own for MAC teams, ESPN's name minus the nickname otherwise."""
    if key and key in BY_KEY:
        return BY_KEY[key].short
    words = (name or "").split()
    if len(words) >= 3 and (" ".join(words[-2:]).lower() in _TWO_WORD or words[-2].lower() in _NICK_LEAD):
        return " ".join(words[:-2])
    return " ".join(words[:-1]) if len(words) >= 2 else (name or "")


def nickname(key: str) -> str:
    t = BY_KEY[key]
    return t.name[len(t.short):].strip() or t.name


def _num(x: float) -> str:
    return f"{abs(x):g}"


def _a(n: str) -> str:
    """'a 4.5-point' but 'an 8-point', 'an 11-point', 'an 18.5-point'."""
    lead = n.split(".")[0]
    return "an" if lead.startswith("8") or lead in ("11", "18") or (len(lead) == 2 and lead.startswith("8")) else "a"


def _top_scorer(box: dict | None, espn_id: str) -> dict | None:
    if not box:
        return None
    mine = [p for p in box.get("players", []) if p.get("team_espn_id") == espn_id and not p.get("dnp") and p.get("pts") is not None]
    return max(mine, key=lambda p: (p["pts"], p.get("reb") or 0), default=None)


def _scorer_line(p: dict | None, team_word: str) -> str:
    if not p or not p.get("pts"):
        return ""
    extra = ""
    if (p.get("reb") or 0) >= 10:
        extra = f" and {p['reb']} rebounds"
    elif (p.get("ast") or 0) >= 8:
        extra = f" and {p['ast']} assists"
    return f"{p['name']} led {team_word} with {p['pts']} points{extra}."


def result_item(g: dict, box: dict | None) -> dict:
    """One finished game, told from the MAC side (the home side if both are MAC)."""
    h, a = g["home"], g["away"]
    mac = h if h.get("key") in BY_KEY else a
    opp = a if mac is h else h
    won = bool(mac.get("winner")) or (mac.get("score") or 0) > (opp.get("score") or 0)
    ms, os_ = mac.get("score"), opp.get("score")
    me, them = school(mac["name"], mac.get("key")), school(opp["name"], opp.get("key"))
    hi, lo = (ms, os_) if won else (os_, ms)
    sent = [f"{me} beat {them} {hi}-{lo}." if won else f"{them} beat {me} {hi}-{lo}."]
    top = _top_scorer(box, mac["espn_id"])
    sc = _scorer_line(top, f"the {nickname(mac['key'])}")
    if sc:
        sent.append(sc)
    tune_up = g.get("closing_spread") is None
    if not tune_up:
        sp = g["closing_spread"] if mac is h else -g["closing_spread"]
        side = "home" if mac is h else "away"
        cover = g.get("ats_cover")
        if sp == 0:
            role = "in a pick'em"
        else:
            role = f"as {_a(_num(sp))} {_num(sp)}-point {'favorite' if sp < 0 else 'underdog'}"
        if cover == "push":
            sent.append(f"{me} pushed {role}.")
        elif cover == side:
            sent.append(f"{me} covered {role}." if won or sp < 0 else f"{me} lost but covered {role}.")
        elif cover:
            sent.append(f"{me} won but didn't cover {role}." if won else f"{me} failed to cover {role}.")
    links = [(top["name"], f"teams/{mac['key']}.html#p{top['espn_id']}")] if sc and top.get("espn_id") else []
    card = {"away": _side(a), "home": _side(h), "top": ({"name": top["name"], "pts": top["pts"], "reb": top.get("reb"), "ast": top.get("ast"),
            "team": mac.get("abbr")} if sc else None), "ats": sent[-1] if not tune_up and len(sent) > 1 else None, "final": True}
    return {"game_id": g["game_id"], "text": " ".join(sent), "tune_up": tune_up, "won": won, "links": links, "card": card,
            "short": f"{me} {'beat' if won else 'lost to'} {them} {ms}-{os_}"}


def _side(x: dict) -> dict:
    return {"name": school(x.get("name"), x.get("key")), "abbr": x.get("abbr"), "espn_id": x.get("espn_id"), "score": x.get("score"),
            "winner": x.get("winner"), "mac": x.get("key") in BY_KEY, "color": BY_KEY[x["key"]].color if x.get("key") in BY_KEY else None}


def preview_item(g: dict) -> dict:
    h, a = g["home"], g["away"]
    home, away = school(h["name"], h.get("key")), school(a["name"], a.get("key"))
    et = g.get("et") or {}
    when = "time to be announced" if et.get("tba") or not et.get("time") else et["time"].replace(":00", "").replace("PM", "p.m.").replace("AM", "a.m.")
    nets = [n["name"] for n in (g.get("watch") or {}).get("nets", [])]
    on = f" on {' and '.join(nets[:2])}" if nets else ""
    verb = "meets" if g.get("neutral_site") else "visits"
    sent = [f"{away} {verb} {home}, {when}{on}".rstrip(".") + "."]
    proj = g.get("model") or {}  # the model's entry for this game: {"model": {"spread": ...}, "non_d1": ...}
    m = proj.get("model") or {}
    latest = ((g.get("line") or {}).get("latest") or {})
    sp = latest.get("spread")
    if sp is not None:
        if sp == 0:
            sent.append("The market has it a pick'em.")
        else:
            fav_key = h.get("key") if sp < 0 else a.get("key")
            if fav_key in BY_KEY:
                s = f"The {nickname(fav_key)} are {_num(sp)}-point favorites"
            else:
                s = f"{home if sp < 0 else away} is {_a(_num(sp))} {_num(sp)}-point favorite"
            ms = m.get("spread")
            if ms:
                if (ms < 0) == (sp < 0):
                    s += f"; our model makes it {_num(ms)}"
                else:
                    s += f"; our model actually likes {home if ms < 0 else away} by {_num(ms)}"
            sent.append(s + ".")
        if latest.get("total") is not None:
            sent.append(f"The total is {latest['total']:g}.")
    elif (proj.get("home") or {}).get("non_d1") or (proj.get("away") or {}).get("non_d1"):
        mac = h if h.get("key") in BY_KEY else a
        return {"game_id": g["game_id"], "tune_up": True, "mac": school(mac["name"], mac.get("key")), "text": " ".join(sent),
                "card": {"away": _side(a), "home": _side(h), "when": when, "on": ", ".join(nets[:2])}}
    else:
        sent.append("No line posted yet.")
    card = {"away": _side(a), "home": _side(h), "when": when, "on": ", ".join(nets[:2]), "spread": sp, "total": latest.get("total"),
            "model": m.get("spread"), "fav": (home if sp < 0 else away) if sp else None}
    return {"game_id": g["game_id"], "tune_up": False, "text": " ".join(sent), "card": card}


MOVE_MIN = 1.5  # points a spread must move from its opener to be the line move of the day
NOTE_HOURS = 48  # how recent a Fieldhouse Note must be to make the show
NOTE_WORDS = 32  # most words read from it


def move_item(slate: list[dict]) -> dict | None:
    """The biggest spread move from opener to now among tonight's lined games, if it moved at least MOVE_MIN."""
    best = None
    for g in slate:
        ln = g.get("line") or {}
        op, now = ln.get("open_spread"), (ln.get("latest") or {}).get("spread")
        if op is None or now is None or abs(now - op) < MOVE_MIN:
            continue
        if not best or abs(now - op) > abs(best[2] - best[1]):
            best = (g, op, now)
    if not best:
        return None
    g, op, now = best
    h, a = g["home"], g["away"]
    home, away = school(h["name"], h.get("key")), school(a["name"], a.get("key"))
    fav_home = now < 0 if now != 0 else op < 0
    fav, dog = (home, away) if fav_home else (away, home)
    f_op, f_now = (op, now) if fav_home else (-op, -now)  # from the favorite's side: negative = favored

    def as_side(x: float) -> str:
        if x == 0:
            return "a pick'em"
        return f"{_a(_num(x))} {_num(x)}-point {'favorite' if x < 0 else 'underdog'}"

    text = f"Line move of the day: {fav} opened as {as_side(f_op)} against {dog} and is now {as_side(f_now)}."
    return {"text": text, "card": {"fav": fav, "dog": dog, "fav_abbr": (h if fav_home else a).get("abbr") or fav, "open": f_op, "now": f_now, "home": _side(h), "away": _side(a)}}


def ou_item(ou: dict | None) -> dict | None:
    """This season's over/under record in MAC games, from the over/under study."""
    cards = (ou or {}).get("season_cards") or []
    c = next((c for c in cards if c.get("season") == (ou or {}).get("cur_season")), None)
    if not c or c["n"] < 5 or c["avg_diff"] is None or c["o"] == c["u"]:
        return None
    side = "over" if c["o"] > c["u"] else "under"
    hi, lo = max(c["o"], c["u"]), min(c["o"], c["u"])
    where = "above" if c["avg_diff"] > 0 else "below"
    text = (f"Over-under watch: games with a MAC team are {hi}-{lo} to the {side} this season, "
            f"landing {_num(c['avg_diff'])} points {where} the closing total on average.")
    return {"text": text, "card": {"o": c["o"], "u": c["u"], "p": c["p"], "side": side, "diff": c["avg_diff"], "n": c["n"]}}


def note_item(dispatches: list[dict] | None, now: datetime) -> dict | None:
    """Matthew's newest Fieldhouse Note, if it was published in the last NOTE_HOURS."""
    for d in dispatches or []:
        try:
            pub = datetime.fromisoformat(d["published"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if pub.tzinfo is None or now - pub > timedelta(hours=NOTE_HOURS):
            return None  # newest first, so nothing later is fresher
        words = d.get("text", "").split()
        if not words:
            continue
        quote = " ".join(words[:NOTE_WORDS])
        cut = max(quote.rfind(". "), quote.rfind("! "), quote.rfind("? "))
        if len(words) > NOTE_WORDS:
            quote = quote[:cut + 1] if cut > 40 else quote.rstrip(",;:") + "..."
        title = d.get("title") or ""
        text = f"From the Fieldhouse Notes{': ' + title.rstrip('.') + '.' if title else ':'} {quote}"
        return {"text": text, "card": {"title": title, "quote": quote, "kind": d.get("kind_label")}}
    return None


def build(now: datetime, recent: list[dict], upcoming: list[dict], boxes: dict[str, dict], standings: list[dict],
          dispatches: list[dict] | None = None, ou: dict | None = None) -> dict[str, Any]:
    et_now = now.astimezone(schedule_view.ET)
    # Results: everything that finished in the last 36 hours, else the last day with MAC finals.
    def et_day(g):
        return datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(schedule_view.ET).date()
    cutoff = now - timedelta(hours=36)
    fresh = [g for g in recent if datetime.fromisoformat(g["date"].replace("Z", "+00:00")) >= cutoff]
    if not fresh and recent:
        last = max(et_day(g) for g in recent)
        fresh = [g for g in recent if et_day(g) == last]
    days = sorted({et_day(g) for g in fresh})
    yesterday = et_now.date() - timedelta(days=1)
    if not days:
        results_label = ""
    elif days == [et_now.date()]:
        results_label = "Earlier today"
    elif days == [yesterday]:
        results_label = "Last night"
    elif len(days) == 1:
        results_label = f"Last time out, {days[0].strftime('%A')}"
    else:
        results_label = f"Since {days[0].strftime('%A')}"
    results = [result_item(g, boxes.get(g["game_id"])) for g in sorted(fresh, key=lambda g: g["date"])]

    # Slate: today's games in Eastern time, else the next day with games.
    today_key = et_now.date().isoformat()
    slate = [g for g in upcoming if (g.get("et") or {}).get("day_key") == today_key]
    slate_label = "Tonight"
    if not slate and upcoming:
        nxt = min((g.get("et") or {}).get("day_key") or "9999" for g in upcoming)
        slate = [g for g in upcoming if (g.get("et") or {}).get("day_key") == nxt]
        if slate:
            slate_label = f"Next up, {datetime.fromisoformat(nxt).strftime('%A')}"
    previews = [preview_item(g) for g in slate]

    unbeaten = [r["team"] for r in standings if r.get("w") and not r.get("l")]
    winless = [r["team"] for r in standings if r.get("l") and not r.get("w")]

    date_label = et_now.strftime("%A, %B %-d")
    paras: list[str] = [f"This is MAC90 for {date_label}."]
    real = [r for r in results if not r["tune_up"]]
    tune = [r for r in results if r["tune_up"]]
    if results:
        paras.append(f"{results_label}: " + " ".join(r["text"] for r in real) if real else f"{results_label}:")
        if tune:
            paras[-1] = (paras[-1] + " " if real else paras[-1] + " ") + ("Also, " if real else "") + "; ".join(r["short"] for r in tune) + " against non-Division I competition."
    if previews:
        lined = [p["text"] for p in previews if not p["tune_up"]]
        tunes = [p["mac"] for p in previews if p["tune_up"]]
        tail = f"{_list(tunes)} {'plays a' if len(tunes) == 1 else 'play'} non-Division I {'opponent' if len(tunes) == 1 else 'opponents'}, so no {'line' if len(tunes) == 1 else 'lines'}." if tunes else ""
        paras.append(f"{slate_label}: " + " ".join(lined + ([("Also, " if lined else "") + tail] if tail else [])))
    move = move_item(slate)
    ou_s = ou_item(ou)
    note = note_item(dispatches, now)
    for extra in (move, ou_s):
        if extra:
            paras.append(extra["text"])
    if unbeaten:
        paras.append(f"Still unbeaten: {_list(unbeaten)}." + (f" Still looking for a first win: {_list(winless)}." if winless else ""))
    if note:
        paras.append(note["text"])
    paras.append("That's MAC90. Every line, box score and rating is at Hardwood Bricks dot com.")

    # The same script cut into segments, one card each, for the video.
    segs: list[dict] = [{"kind": "intro", "text": paras[0]}]
    for i, r in enumerate(real):
        segs.append({"kind": "result", "label": results_label, "text": (f"{results_label}: " if i == 0 else "") + r["text"], "card": r["card"]})
    if tune:
        segs.append({"kind": "tuneups", "label": results_label, "cards": [r["card"] for r in tune],
                     "text": (f"{results_label}: " if not real else "Also, ") + "; ".join(r["short"] for r in tune) + " against non-Division I competition."})
    lined_p = [p for p in previews if not p["tune_up"]]
    for i, p in enumerate(lined_p):
        segs.append({"kind": "preview", "label": slate_label, "text": (f"{slate_label}: " if i == 0 else "") + p["text"], "card": p["card"]})
    tune_p = [p for p in previews if p["tune_up"]]
    if tune_p:
        names = [p["mac"] for p in tune_p]
        segs.append({"kind": "tuneups_next", "label": slate_label, "cards": [p["card"] for p in tune_p],
                     "text": (f"{slate_label}: " if not lined_p else "Also, ") + f"{_list(names)} {'plays a' if len(names) == 1 else 'play'} non-Division I {'opponent' if len(names) == 1 else 'opponents'}, so no {'line' if len(names) == 1 else 'lines'}."})
    if move:
        segs.append({"kind": "move", "text": move["text"], "card": move["card"]})
    if ou_s:
        segs.append({"kind": "ou", "text": ou_s["text"], "card": ou_s["card"]})
    if unbeaten:
        segs.append({"kind": "standings", "unbeaten": unbeaten, "winless": winless,
                     "text": f"Still unbeaten: {_list(unbeaten)}." + (f" Still looking for a first win: {_list(winless)}." if winless else "")})
    if note:
        segs.append({"kind": "note", "text": note["text"], "card": note["card"]})
    segs.append({"kind": "outro", "text": paras[-1]})

    words = sum(len(p.split()) for p in paras)
    links = [ln for r in results for ln in r.get("links", [])]
    links += [(t.short, f"teams/{t.key}.html") for t in BY_KEY.values()]
    return {
        "date_label": date_label,
        "date_iso": et_now.date().isoformat(),
        "results_label": results_label,
        "slate_label": slate_label,
        "results": results,
        "previews": previews,
        "paragraphs": paras,
        "segments": segs,
        "paragraphs_html": [link_text(p, links) for p in paras],
        "words": words,
        "seconds": round(words / WPM * 60),
        "over": words > TARGET_WORDS + 40,
    }


def _list(xs: list[str]) -> str:
    if len(xs) <= 2:
        return " and ".join(xs)
    return ", ".join(xs[:-1]) + " and " + xs[-1]


def link_text(text: str, links: list[tuple[str, str]]) -> str:
    """Escape text and link the first mention of each player or MAC school in it."""
    out = html.escape(text)
    found: dict[str, str] = {}
    for i, (name, href) in enumerate(sorted(links, key=lambda x: -len(x[0]))):
        pat = re.compile(r"(?<![\w>])" + re.escape(html.escape(name)) + r"(?![\w<])")
        token = f"\x00{i}\x00"
        out, n = pat.subn(token, out, count=1)
        if n:
            found[token] = f'<a href="{html.escape(href)}">{html.escape(name)}</a>'
    for token, a in found.items():
        out = out.replace(token, a)
    return out
