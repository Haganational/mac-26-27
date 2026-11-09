"""Shapes the model's projections for display: color-coded leans and players to watch.

Colors carry the meaning everywhere the model shows up:
- totals: over leans are ember orange, under leans are blue (the same pair the O/U study uses)
- sides: a lean on the favorite is violet, a lean on the underdog is teal
- intensity: the bigger the gap between the model and the market, the deeper the shade

Templates read `lean_pct` (a 0-100 mix strength for CSS color-mix) and `tier` (a word).
"""

from __future__ import annotations

from typing import Any

LEAN_CAP = 6.0  # points of model-vs-market gap at which a lean reaches full color
MIN_SHARE = 40.0  # % of team minutes (about 16 a game) a player needs before he can be a player to watch


def lean_pct(gap: float) -> int:
    """Color strength for a gap: faint at 0, full at LEAN_CAP points and beyond."""
    return int(round(18 + 72 * min(abs(gap) / LEAN_CAP, 1.0)))


def tier(gap: float) -> str:
    g = abs(gap)
    return "slight" if g < 1.5 else ("lean" if g < 3 else ("strong" if g < 5 else "big"))


def _spread_txt(v: float) -> str:
    return "PK" if abs(v) < 0.05 else f"{v:+.1f}"


def view(u: dict[str, Any] | None) -> dict[str, Any] | None:
    """Display shape for one projected game (an entry of model.build_model()["upcoming"])."""
    if not u:
        return None
    m, h, a = u["model"], u["home"], u["away"]
    non_d1 = bool(h.get("non_d1") or a.get("non_d1"))
    hw = m["home_win"]
    fav, dog = (h, a) if m["spread"] <= 0 else (a, h)
    out: dict[str, Any] = {
        "game_id": u["game_id"], "non_d1": non_d1,
        "home_pts": round(m["home_pts"]), "away_pts": round(m["away_pts"]),
        "spread": m["spread"], "total": m["total"], "poss": m["poss"],
        "home_win": round(100 * hw), "away_win": 100 - round(100 * hw),
        "fav_abbr": fav["abbr"], "fav_line": f"{fav['abbr']} {_spread_txt(-abs(m['spread']))}",
        "dog_abbr": dog["abbr"],
        "home_key": h.get("key"), "away_key": a.get("key"),
        "market": u.get("market"), "side": None, "ou": None,
    }
    se, te = u.get("spread_edge"), u.get("total_edge")
    if se and not non_d1 and se["abs"] > 0:
        num = float(se["take"].split()[-1].replace("PK", "0"))
        kind = "dog" if num > 0 else "fav"
        out["side"] = {"kind": kind, "label": "Underdog" if kind == "dog" else "Favorite", "take": se["take"],
                       "abbr": se["abbr"], "gap": se["abs"], "pct": lean_pct(se["abs"]), "tier": tier(se["abs"])}
    if te and not non_d1 and te["abs"] > 0:
        kind = "over" if te["gap"] > 0 else "under"
        out["ou"] = {"kind": kind, "label": kind.title(), "take": te["take"], "gap": te["abs"],
                     "pct": lean_pct(te["abs"]), "tier": tier(te["abs"])}
    gaps = [x["gap"] for x in (out["side"], out["ou"]) if x]
    out["max_gap"] = max(gaps) if gaps else 0.0
    return out


def past_view(s: dict[str, Any] | None) -> dict[str, Any] | None:
    """Display shape for a finished game's walk-forward projection (model.season_to_date row)."""
    if not s:
        return None
    out = {**s, "side": None, "ou": None}
    if s.get("spread_gap"):
        g = s["spread_gap"]
        # gap < 0: model liked home more than the close did
        take_home = g < 0
        num = s["close_spread"] if take_home else -s["close_spread"]
        kind = "dog" if num > 0 else "fav"
        out["side"] = {"kind": kind, "label": "Underdog" if kind == "dog" else "Favorite", "home": take_home,
                       "num": num, "gap": abs(g), "pct": lean_pct(g), "tier": tier(g), "res": s.get("model_ats")}
    if s.get("total_gap"):
        g = s["total_gap"]
        kind = "over" if g > 0 else "under"
        out["ou"] = {"kind": kind, "label": kind.title(), "gap": abs(g), "pct": lean_pct(g), "tier": tier(g),
                     "res": s.get("model_ou")}
    return out


def _pick(pool: list[dict[str, Any]], key: str, taken: set[str]) -> dict[str, Any] | None:
    left = [p for p in pool if p["id"] not in taken and p.get(key) is not None]
    return max(left, key=lambda p: p[key]) if left else None


ROLES = (("net", "Best overall", "rk", "overall"), ("off", "Offensive engine", "off_rk", "offense"),
         ("def", "Defensive anchor", "def_rk", "defense"))


def players_to_watch(team_keys: list[str], prate: dict[str, dict[str, Any]], n_rated: int) -> list[dict[str, Any]]:
    """Up to three players for a game: the best overall, offensive and defensive ratings among its MAC rosters.

    Players need a real share of minutes (MIN_SHARE) so a hot 6-minute cameo doesn't headline.
    Each player appears once; the overall pick goes first.
    """
    keys = [k for k in team_keys if k]
    if not keys:
        return []
    pool = [p for p in prate.values() if p.get("team_key") in keys]
    regulars = [p for p in pool if (p.get("min_pct") or 0) >= MIN_SHARE]
    pool = regulars or pool
    out, taken = [], set()
    for key, label, rk_key, word in ROLES:
        p = _pick(pool, key, taken)
        if not p:
            continue
        taken.add(p["id"])
        val = p[key]
        out.append({"role": label, "word": word, "kind": key, "id": p["id"], "name": p["name"],
                    "team_key": p["team_key"], "abbr": p["abbr"], "pos": p.get("pos") or "",
                    "value": val, "rank": p.get(rk_key), "of": n_rated, "net": p.get("net"), "off": p.get("off"),
                    "def": p.get("def"), "ppg": p.get("ppg"), "mpg": p.get("mpg"),
                    "early": (p.get("prior_share") or 0) > 0.5,
                    "href": f"teams/{p['team_key']}.html#p{p['id']}"})
    return out
