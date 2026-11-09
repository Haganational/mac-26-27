"""Data Visualized page: geometry for the line-posting clocks.

Each game is one analog dial with tip-off at 12 o'clock. A book that posted L hours
before tip sits L/span of a turn counterclockwise from 12, so the sweep from the first
book to tip runs clockwise, the way time runs toward the game.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .oddsboard import book_name

ET = ZoneInfo("America/New_York")
C = 130.0          # SVG center (viewBox 0 0 260 260)
R_DIAL = 104.0     # dial face
R_DOT = 94.0       # ring for book dots
R_SWEEP = 76.0     # clockwise sweep arrow
R_WINDOW = 140.0   # first-to-last posting window band
R_DOT_OUT = 114.0  # second ring when two markers would overlap

BOOK_COLORS = {
    "draftkings": "#53a318", "fanduel": "#1493ff", "betmgm": "#b8975a", "williamhill_us": "#c9a14a",
    "betrivers": "#1d4f91", "espnbet": "#e2252c", "hardrockbet": "#7b3fe4", "bovada": "#c8102e",
    "betonlineag": "#f2a900", "novig": "#6d5dfc", "pinnacle": "#f37021", "lowvig": "#14a89a",
    "fanatics": "#0b4ea2", "betus": "#0f7a3c", "mybookieag": "#e8641b",
}


def _pt(angle_deg: float, r: float) -> tuple[float, float]:
    """Clock angle: 0 = 12 o'clock, positive = clockwise."""
    a = math.radians(angle_deg)
    return round(C + r * math.sin(a), 2), round(C - r * math.cos(a), 2)


def _arc(a0: float, a1: float, r: float) -> str:
    """Clockwise arc from angle a0 to a1 (a0 < a1)."""
    x0, y0 = _pt(a0, r)
    x1, y1 = _pt(a1, r)
    large = 1 if (a1 - a0) > 180 else 0
    return f"M{x0} {y0} A{r} {r} 0 {large} 1 {x1} {y1}"


def _ago(h: float) -> str:
    if h >= 24:
        d, rem = divmod(h, 24)
        return f"{int(d)}d {round(rem)}h" if round(rem) else f"{int(d)}d"
    if h >= 1:
        hh = int(h)
        mm = round((h - hh) * 60)
        return f"{hh}h {mm:02d}m" if mm else f"{hh}h"
    return f"{round(h * 60)}m"


def clock(c: dict[str, Any]) -> dict[str, Any]:
    span = c["span_h"]
    ang = lambda lead: -360.0 * lead / span  # noqa: E731 - tiny mapping
    ticks = []
    for i in range(12):
        a = i * 30
        major = i % 3 == 0
        x0, y0 = _pt(a, R_DIAL - (10 if major else 5))
        x1, y1 = _pt(a, R_DIAL)
        t = {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "major": major}
        if major and i:
            hrs = round(span * (12 - i) / 12)
            t["lx"], t["ly"] = _pt(a, R_DIAL + 15)
            t["label"] = f"-{hrs}h"
        ticks.append(t)
    dots = []
    for b in c["books"]:
        t_et = datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET)
        dots.append({**b, "name": book_name(b["book"]), "color": BOOK_COLORS.get(b["book"], "#8a8f98"),
                     "ago": _ago(b["lead_h"]), "et": t_et.strftime("%a %-I:%M %p")})
    # Books first seen in the same snapshot share one marker, sized by how many posted together.
    clusters: list[dict[str, Any]] = []
    for d in dots:
        if clusters and clusters[-1]["t"] == d["t"]:
            clusters[-1]["books"].append(d)
        else:
            clusters.append({"t": d["t"], "lead_h": d["lead_h"], "ago": d["ago"], "et": d["et"], "books": [d]})
    prev = None
    for k in clusters:
        n = len(k["books"])
        k["r"] = 7 if n == 1 else min(13, 8 + n)
        ring = R_DOT
        if prev is not None:  # step to the outer ring when this marker would sit on the previous one
            px, py, pr = prev
            x, y = _pt(ang(k["lead_h"]), ring)
            if math.hypot(x - px, y - py) < k["r"] + pr + 2:
                ring = R_DOT_OUT
        k["x"], k["y"] = _pt(ang(k["lead_h"]), ring)
        prev = (k["x"], k["y"], k["r"])
        k["n"] = n
        k["color"] = k["books"][0]["color"] if n == 1 else "var(--gold)"
        k["names"] = ", ".join(d["name"] for d in k["books"])
    first, last = c["books"][0]["lead_h"], c["books"][-1]["lead_h"]
    a_first, a_last = ang(first), ang(last)
    sweep_end = -4.0  # stop just short of 12 so the arrowhead sits on TIP
    hand = None
    if c.get("now_h") is not None:  # a short pointer on the rim, so it never crosses the center readout
        a = ang(c["now_h"])
        (x0, y0), (x1, y1) = _pt(a, R_SWEEP + 4), _pt(a, R_DIAL - 2)
        hand = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
    tip_et = datetime.fromisoformat(c["tip"].replace("Z", "+00:00")).astimezone(ET)
    return {
        **c,
        "dots": dots,
        "clusters": clusters,
        "ticks": ticks,
        "tip_label": _pt(0, R_DIAL + 14),
        "sweep": _arc(a_first, sweep_end, R_SWEEP) if a_first < sweep_end else None,
        "window": _arc(a_first, a_last, R_WINDOW) if a_last - a_first > 1 else None,
        "sweep_len": round(math.radians(sweep_end - a_first) * R_SWEEP, 1),
        "hand": hand,
        "first_name": dots[0]["name"],
        "lead_txt": _ago(first),
        "gap_txt": _ago(first - last) if first - last >= 0.25 else "same snapshot",
        "tip_et": tip_et.strftime("%a %b %-d, %-I:%M %p ET"),
    }


def page_context(clocks: list[dict[str, Any]]) -> dict[str, Any]:
    games = [clock(c) for c in clocks]
    firsts: dict[str, int] = {}
    for g in games:
        firsts[g["first_name"]] = firsts.get(g["first_name"], 0) + 1
    return {"games": games, "firsts": sorted(firsts.items(), key=lambda kv: -kv[1])}
