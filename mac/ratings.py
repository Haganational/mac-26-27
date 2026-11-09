"""Bottom-up team ratings and game projections.

The model, in plain terms
-------------------------
Every D-I game gives three numbers: how many possessions it had, how many points
each side scored per 100 possessions. A team's rating is three numbers that best
explain all of its games at once, after accounting for who it played and where:

    offense   o  points per 100 it adds over an average D-I offense
    defense   d  points per 100 it allows over average (negative is good)
    tempo     t  possessions per 40 minutes it adds over an average game

For one team-game:   eff(A on B)  = mu + o[A] + d[B] + hca * loc
For one game:        poss(A vs B) = tau + t[A] + t[B]

loc is +1 for the home team, -1 for the visitor and 0 on a neutral floor.

All teams are solved together by weighted least squares, which is what "weight
opponents by strength" means here: beating a strong team moves you more than
beating a weak one, because the opponent's rating is in the equation, and that
rating is itself set by everyone it played. Three knobs shape the fit:

- Recency: each game's weight halves every `half_life` days, so recent form counts
  more than November.
- Blowouts: margins beyond `cap` points per 100 count at `cap_slope` of face value,
  so running up the score on a 350th-ranked team does not look like dominance.
- Preseason prior: each rating is pulled toward last season's final number,
  regressed `regress` of the way to average, with the weight of `prior_games` games.
  It fades on its own as real games pile up.

Outputs a projection per game (home margin, total, win probability) and per team
(adjusted offense, defense, net, tempo, strength of schedule).

Pure numpy over the files in data/ncaa/, so it runs the same everywhere.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import numpy as np

NON_D1 = "non-d1"  # every non-Division I opponent shares one rating
FT_WEIGHT = 0.475
DEFAULT_TO_MINUS_ORB = 1.5  # used for games without a full box score


@dataclass(frozen=True)
class Params:
    half_life: float = 90.0  # days
    cap: float = 45.0  # efficiency margin (per 100, ~30 pts) beyond which a margin is shrunk
    cap_slope: float = 0.7  # share of the margin past the cap that still counts
    prior_games: float = 2.0  # weight of the preseason prior, in games
    regress: float = 0.2  # share of last season's rating discarded toward average
    tempo_prior_games: float = 3.0
    tempo_regress: float = 0.25
    sigma_margin: float = 12.0  # std dev of the actual margin around the projection (backtest: 11.3 Jan on, 15 in Nov)
    sigma_total: float = 17.0
    min_weight: float = 0.05  # floor on recency weight, so old games never vanish
    non_d1_weight: float = 0.5  # games against non-D-I opponents count this much
    hca_prior_games: float = 3000.0  # home edge is carried over from last season this firmly (in team-games)


@dataclass
class Ratings:
    as_of: str
    mu: float  # average points per 100
    tau: float  # average possessions per 40
    hca: float  # home edge, points per 100, each side
    teams: dict[str, dict[str, float]] = field(default_factory=dict)
    games_used: int = 0
    params: dict[str, float] = field(default_factory=dict)

    def team(self, tid: str) -> dict[str, float]:
        return self.teams.get(tid) or self.teams.get(NON_D1) or {"o": 0.0, "d": 0.0, "t": 0.0, "games": 0}


# ---------------------------------------------------------------- inputs


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def side_possessions(side: dict[str, Any], to_minus_orb: float) -> float | None:
    fga, fta = side.get("fga"), side.get("fta")
    if fga is None or fta is None:
        return None
    if side.get("orb") is not None and side.get("to") is not None:
        return fga - side["orb"] + side["to"] + FT_WEIGHT * fta
    return fga + FT_WEIGHT * fta + to_minus_orb


def calibrate_to_minus_orb(games: Iterable[dict[str, Any]]) -> float:
    """Average (turnovers - offensive rebounds) per team-game where we have full boxes."""
    vals = [s["to"] - s["orb"] for g in games for s in (g["home"], g["away"])
            if s.get("to") is not None and s.get("orb") is not None]
    return float(np.mean(vals)) if len(vals) >= 40 else DEFAULT_TO_MINUS_ORB


def game_rows(games: Iterable[dict[str, Any]], d1: set[str], to_minus_orb: float) -> list[dict[str, Any]]:
    """Normalize raw games into model rows; drops games without the stats we need."""
    out = []
    for g in games:
        ph = side_possessions(g["home"], to_minus_orb)
        pa = side_possessions(g["away"], to_minus_orb)
        if not ph or not pa:
            continue
        poss = (ph + pa) / 2
        if poss < 40:  # garbage data
            continue
        ot = g.get("ot") or 0
        h = g["home"]["id"] if g["home"]["id"] in d1 else NON_D1
        a = g["away"]["id"] if g["away"]["id"] in d1 else NON_D1
        if h == a:
            continue
        out.append({
            "id": g["id"], "date": parse_dt(g["date"]), "home": h, "away": a,
            "neutral": bool(g.get("neutral")),
            "eff_h": 100 * g["home"]["pts"] / poss, "eff_a": 100 * g["away"]["pts"] / poss,
            "poss": poss, "poss40": poss * 40 / (40 + 5 * ot),
            "pts_h": g["home"]["pts"], "pts_a": g["away"]["pts"],
            "home_name": g["home"].get("name"), "away_name": g["away"].get("name"),
        })
    return out


# ---------------------------------------------------------------- fitting


def _cap(eff_h: float, eff_a: float, p: Params) -> tuple[float, float]:
    m = eff_h - eff_a
    if abs(m) <= p.cap:
        return eff_h, eff_a
    new_m = math.copysign(p.cap + (abs(m) - p.cap) * p.cap_slope, m)
    mid = (eff_h + eff_a) / 2
    return mid + new_m / 2, mid - new_m / 2


def fit(rows: list[dict[str, Any]], as_of: datetime, p: Params = Params(),
        prior: Ratings | None = None) -> Ratings:
    """Solve the ratings from every game played before `as_of`."""
    rows = [r for r in rows if r["date"] < as_of]
    teams = sorted({r["home"] for r in rows} | {r["away"] for r in rows} | set(prior.teams if prior else ()))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    games_played = {t: 0 for t in teams}

    # ---- efficiency: params [mu, hca, o_0..o_n-1, d_0..d_n-1]
    k = 2 + 2 * n
    A = np.zeros((k, k))
    b = np.zeros(k)

    def add(cols: list[int], y: float, w: float) -> None:
        for c1 in cols:
            b[c1] += w * y
            for c2 in cols:
                A[c1, c2] += w

    # Tempo: [tau, t_0..t_n-1]
    At = np.zeros((n + 1, n + 1))
    bt = np.zeros(n + 1)

    for r in rows:
        age = (as_of - r["date"]).total_seconds() / 86400
        w = max(p.min_weight, 0.5 ** (age / p.half_life))
        if NON_D1 in (r["home"], r["away"]):
            w *= p.non_d1_weight
        hi, ai = idx[r["home"]], idx[r["away"]]
        games_played[r["home"]] += 1
        games_played[r["away"]] += 1
        eh, ea = _cap(r["eff_h"], r["eff_a"], p)
        loc = 0.0 if r["neutral"] else 1.0
        # home offense vs away defense, and the reverse
        for off, de, y, sgn in ((hi, ai, eh, loc), (ai, hi, ea, -loc)):
            cols = [0, 2 + off, 2 + n + de]
            if sgn:
                # hca enters with coefficient +-1; handle by sign-flipping the row
                vec = {0: 1.0, 2 + off: 1.0, 2 + n + de: 1.0, 1: sgn}
                for c1, v1 in vec.items():
                    b[c1] += w * v1 * y
                    for c2, v2 in vec.items():
                        A[c1, c2] += w * v1 * v2
            else:
                add(cols, y, w)
        tc = [0, 1 + hi, 1 + ai]
        for c1 in tc:
            bt[c1] += w * r["poss40"]
            for c2 in tc:
                At[c1, c2] += w

    # ---- priors (ridge toward last season, regressed)
    po = np.zeros(n)
    pd = np.zeros(n)
    pt = np.zeros(n)
    if prior:
        for t, i in idx.items():
            if t in prior.teams:
                po[i] = prior.teams[t]["o"] * (1 - p.regress)
                pd[i] = prior.teams[t]["d"] * (1 - p.regress)
                pt[i] = prior.teams[t]["t"] * (1 - p.tempo_regress)
    lam = max(p.prior_games, 1e-3)
    for i in range(n):
        A[2 + i, 2 + i] += lam
        b[2 + i] += lam * po[i]
        A[2 + n + i, 2 + n + i] += lam
        b[2 + n + i] += lam * pd[i]
        At[1 + i, 1 + i] += max(p.tempo_prior_games, 1e-3)
        bt[1 + i] += max(p.tempo_prior_games, 1e-3) * pt[i]
    # weak anchors so mu/hca/tau are defined even with no games
    A[0, 0] += 1e-3
    b[0] += 1e-3 * 105.0
    # Home edge: early-season home games are mostly buy games, which would inflate a
    # freely fit home edge, so it leans on last season's number until data piles up.
    hca0 = prior.hca if prior else 1.6
    hw = p.hca_prior_games if prior else 1.0
    A[1, 1] += hw
    b[1] += hw * hca0
    At[0, 0] += 1e-3
    bt[0] += 1e-3 * 68.0

    x = np.linalg.solve(A, b)
    xt = np.linalg.solve(At, bt)
    mu, hca = float(x[0]), float(x[1])
    o, d = x[2:2 + n], x[2 + n:]
    # Center so the average D-I team is 0 on each axis (absorbed into mu).
    real = [i for t, i in idx.items() if t != NON_D1]
    oc, dc = float(o[real].mean()), float(d[real].mean())
    tau = float(xt[0])
    tt = xt[1:]
    tc = float(tt[real].mean())
    out = Ratings(as_of=as_of.isoformat(timespec="seconds"), mu=mu + oc + dc, tau=tau + 2 * tc, hca=hca,
                  games_used=len(rows), params=asdict(p))
    for t, i in idx.items():
        out.teams[t] = {"o": float(o[i] - oc), "d": float(d[i] - dc), "t": float(tt[i] - tc),
                        "games": games_played.get(t, 0)}
    return out


# ---------------------------------------------------------------- projecting


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def project(r: Ratings, home: str, away: str, neutral: bool = False, p: Params = Params()) -> dict[str, float]:
    """Projected score from the home team's side. spread follows the betting convention (negative = home favored)."""
    th, ta = r.team(home), r.team(away)
    loc = 0.0 if neutral else 1.0
    poss = r.tau + th["t"] + ta["t"]
    eh = r.mu + th["o"] + ta["d"] + r.hca * loc
    ea = r.mu + ta["o"] + th["d"] - r.hca * loc
    ph, pa = eh * poss / 100, ea * poss / 100
    margin = ph - pa
    return {
        "poss": poss, "home_pts": ph, "away_pts": pa,
        "margin": margin, "spread": -margin, "total": ph + pa,
        "home_win": norm_cdf(margin / p.sigma_margin),
    }


def team_table(r: Ratings, rows: list[dict[str, Any]], names: dict[str, dict[str, Any]], p: Params = Params()) -> list[dict[str, Any]]:
    """One row per rated D-I team with adjusted numbers, raw numbers, SOS and ranks."""
    as_of = parse_dt(r.as_of)
    raw: dict[str, dict[str, float]] = {}
    opp_em: dict[str, list[tuple[float, float]]] = {}
    for g in rows:
        if g["date"] >= as_of:
            continue
        w = max(p.min_weight, 0.5 ** ((as_of - g["date"]).total_seconds() / 86400 / p.half_life))
        for me, op, pf, pa in ((g["home"], g["away"], g["pts_h"], g["pts_a"]), (g["away"], g["home"], g["pts_a"], g["pts_h"])):
            x = raw.setdefault(me, {"g": 0, "pf": 0, "pa": 0, "poss": 0.0})
            x["g"] += 1
            x["pf"] += pf
            x["pa"] += pa
            x["poss"] += g["poss40"]
            ot = r.team(op)
            opp_em.setdefault(me, []).append((w, ot["o"] - ot["d"]))
    avg_poss = r.tau
    out = []
    for tid, t in r.teams.items():
        if tid == NON_D1:
            continue
        x = raw.get(tid, {"g": 0, "pf": 0, "pa": 0, "poss": 0.0})
        em = t["o"] - t["d"]
        sos = opp_em.get(tid, [])
        sos_val = sum(w * v for w, v in sos) / sum(w for w, _ in sos) if sos else None
        out.append({
            "id": tid,
            "name": names.get(tid, {}).get("name", tid),
            "short": names.get(tid, {}).get("short", tid),
            "abbr": names.get(tid, {}).get("abbr", ""),
            "games": x["g"],
            "adj_o": r.mu + t["o"],
            "adj_d": r.mu + t["d"],
            "adj_em": em,
            "adj_t": r.tau + t["t"],
            # Points per game better than an average D-I team, neutral floor, average pace.
            "net_pts": em * avg_poss / 100,
            "raw_margin": (x["pf"] - x["pa"]) / x["g"] if x["g"] else None,
            "raw_total": (x["pf"] + x["pa"]) / x["g"] if x["g"] else None,
            "raw_poss": x["poss"] / x["g"] if x["g"] else None,
            "sos": sos_val,
        })
    for key, rev in (("adj_em", True), ("adj_o", True), ("adj_d", False), ("adj_t", True), ("sos", True)):
        ranked = sorted((t for t in out if t[key] is not None), key=lambda t: t[key], reverse=rev)
        for i, t in enumerate(ranked, 1):
            t[f"rk_{key}"] = i
    out.sort(key=lambda t: -t["adj_em"])
    return out


def prior_from(r: Ratings) -> Ratings:
    """Last season's final ratings, used as this season's preseason prior."""
    return replace(r, teams={k: dict(v) for k, v in r.teams.items()})


def walk_forward(rows: list[dict[str, Any]], p: Params, prior: Ratings | None,
                 start: datetime | None = None, step_days: int = 1) -> list[dict[str, Any]]:
    """Refit each morning and project that day's games with only earlier information."""
    if not rows:
        return []
    first = min(r["date"] for r in rows)
    day = (start or first).astimezone(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    last = max(r["date"] for r in rows)
    out = []
    by_day: dict[datetime, list[dict[str, Any]]] = {}
    for g in rows:
        # 10:00 UTC "morning" cut: games tipping before the next morning belong to this slate
        anchor = g["date"].replace(hour=10, minute=0, second=0, microsecond=0)
        if g["date"] < anchor:
            anchor -= timedelta(days=1)
        by_day.setdefault(anchor, []).append(g)
    while day <= last:
        slate = by_day.get(day, [])
        if slate:
            rt = fit(rows, day, p, prior)
            for g in slate:
                pr = project(rt, g["home"], g["away"], g["neutral"], p)
                out.append({**g, "proj": pr, "games_h": rt.team(g["home"])["games"], "games_a": rt.team(g["away"])["games"]})
        day += timedelta(days=step_days)
    return out
