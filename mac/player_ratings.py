"""Player ratings for every MAC player.

Box-score rating (live now)
---------------------------
Same idea as Basketball-Reference's Box Plus/Minus, rebuilt for college:

1. **Learn what each box-score stat is worth.** Over ~6,000 D-I games from last
   season, regress each team's opponent-adjusted efficiency margin for the game on
   its per-100-possession box stats (made threes, made twos, made free throws,
   missed shots, missed free throws, offensive and defensive rebounds, assists,
   steals, blocks, turnovers, fouls). Offense gets its own regression on points per
   100, so every player gets an offensive and a defensive number.
2. **Apply the weights to each player's per-100 stats** while he was on the floor
   (possessions on floor = team possessions x minutes / 40).
3. **Shrink small samples** toward a prior: last season's rating for returning
   MAC players (regressed 30%), otherwise a newcomer baseline.
4. **Tie it to the team.** Shift every player on a team by the same amount so the
   minutes-weighted sum of five players equals the team's adjusted rating from the
   team model. A player on a team that wins more than its box score says gets credit.

Scale: points per 100 possessions better than an average D-I player. 0 is average,
+5 is all-conference, -3 is end of bench. A team's net rating is roughly five times
the minutes-weighted average of its players.

On/off (switches on in December)
--------------------------------
From play-by-play stints (see pbp.py), a ridge regression of each stint's margin
per 100 on who was on the floor, with each player pulled toward his box rating.
Non-MAC opponents enter as their team rating. It needs about 1,500 on-floor
possessions to move halfway from the box rating, so it stays hidden until December.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

import numpy as np

from . import ncaa, pbp
from . import ratings as R
from .config import BY_ESPN_ID, DATA_DIR, SEASON, SHARED_DIR, TEAMS

WEIGHTS_PATH = SHARED_DIR / "model" / "box_weights.json"
PLAYERS_PATH = DATA_DIR / "model" / "players.json"
STATS = ("tpm", "twom", "ftm", "fgx", "ftx", "orb", "drb", "ast", "stl", "blk", "to", "pf")
# Possessions are defined from these same stats (FGA - OREB + TOV + 0.475 FTA = 100 per 100),
# so the regression only pins weights down up to adding c x this vector. We pick c so a
# turnover costs exactly one average possession, which makes the weights read as
# "points above an average use of the ball".
POSS_IDENTITY = {"tpm": 1.0, "twom": 1.0, "fgx": 1.0, "ftm": 0.475, "ftx": 0.475, "orb": -1.0, "to": 1.0}
# Team-level regressions can't tell a passer from a scorer (assists move with made
# shots), and fouls pick up game-state noise, so both are left out of the regression.
# Assists instead earn a share of the basket they set up, taken from the scorers.
REGRESSED = ("tpm", "twom", "ftm", "fgx", "ftx", "orb", "drb", "stl", "blk", "to")
ASSIST_SHARE = 1 / 3
STAT_LABEL = {"tpm": "3PM", "twom": "2PM", "ftm": "FTM", "fgx": "Missed FG", "ftx": "Missed FT", "orb": "OREB",
              "drb": "DREB", "ast": "AST", "stl": "STL", "blk": "BLK", "to": "TOV", "pf": "PF"}
SHRINK_POSS = 250.0  # a player's own stats count half after this many possessions on the floor
PRIOR_REGRESS = 0.3
NEWCOMER_PRIOR = -1.0
ONOFF_LAMBDA = 1500.0
ONOFF_START = date(SEASON - 1, 12, 1)  # the page shows on/off from this date
MAC_IDS = {t.espn_id for t in TEAMS}


# ---------------------------------------------------------------- stat weights


def _team_rates(side: dict[str, Any], poss: float) -> dict[str, float] | None:
    need = ("fgm", "fga", "tpm", "ftm", "fta", "orb", "drb", "ast", "stl", "blk", "to", "pf")
    if any(side.get(k) is None for k in need) or poss <= 0:
        return None
    raw = {
        "tpm": side["tpm"], "twom": side["fgm"] - side["tpm"], "ftm": side["ftm"],
        "fgx": side["fga"] - side["fgm"], "ftx": side["fta"] - side["ftm"],
        "orb": side["orb"], "drb": side["drb"], "ast": side["ast"], "stl": side["stl"],
        "blk": side["blk"], "to": side["to"], "pf": side["pf"],
    }
    return {k: 100 * v / poss for k, v in raw.items()}


def fit_weights(season: int = SEASON - 1) -> dict[str, Any]:
    """Regress opponent-adjusted game efficiency on per-100 team box stats."""
    names = ncaa.load_d1_teams()
    d1 = set(names)
    games = ncaa.load_season(season)["games"]
    rows = R.game_rows(games, d1, R.calibrate_to_minus_orb(games))
    end = max(r["date"] for r in rows)
    rt = R.fit(rows, end.replace(hour=23, minute=59), R.Params(half_life=1e6))
    by_id = {g["id"]: g for g in games}
    X, y_net, y_off = [], [], []
    for r in rows:
        g = by_id[r["id"]]
        for side, opp, eff, eff_opp, loc in (("home", "away", r["eff_h"], r["eff_a"], 1), ("away", "home", r["eff_a"], r["eff_h"], -1)):
            rates = _team_rates(g[side], r["poss"])
            if rates is None:
                continue
            loc = 0 if r["neutral"] else loc
            ot = rt.team(r[opp])
            # What an average team would have done against this opponent here, removed.
            off_adj = eff - (rt.mu + ot["d"] + rt.hca * loc)
            def_adj = (rt.mu + ot["o"] - rt.hca * loc) - eff_opp
            X.append([rates[k] for k in STATS])
            y_net.append(off_adj + def_adj)
            y_off.append(off_adj)
    cols = [STATS.index(k) for k in REGRESSED]
    X = np.array(X)[:, cols]
    A = np.hstack([np.ones((len(X), 1)), X])
    ppp = rt.mu / 100

    def solve(y: list[float]) -> tuple[dict[str, float], float]:
        coef, *_ = np.linalg.lstsq(A, np.array(y), rcond=None)
        resid = np.array(y) - A @ coef
        w = {"const": float(coef[0]), **{k: float(c) for k, c in zip(REGRESSED, coef[1:])}}
        c = -ppp - w["to"]
        for k, v in POSS_IDENTITY.items():
            w[k] += c * v
        w["const"] -= 100 * c
        for k in STATS:
            w.setdefault(k, 0.0)
        return w, float(1 - resid.var() / np.var(y))

    net, r2 = solve(y_net)
    off, r2_off = solve(y_off)
    out = {
        "season": season, "games": len(X), "r2_net": round(r2, 3), "r2_off": round(r2_off, 3), "ppp": ppp,
        "net": net, "off": off, "assist_share": ASSIST_SHARE,
        "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS_PATH.write_text(json.dumps(out, indent=1))
    return out


def load_weights() -> dict[str, Any]:
    if not WEIGHTS_PATH.exists():
        return fit_weights()
    return json.loads(WEIGHTS_PATH.read_text())


# ---------------------------------------------------------------- player box ratings


def _player_rates(p: dict[str, float]) -> dict[str, float]:
    poss = p["poss"]
    return {
        "tpm": 100 * p["tpm"] / poss, "twom": 100 * (p["fgm"] - p["tpm"]) / poss, "ftm": 100 * p["ftm"] / poss,
        "fgx": 100 * (p["fga"] - p["fgm"]) / poss, "ftx": 100 * (p["fta"] - p["ftm"]) / poss,
        "orb": 100 * p["oreb"] / poss, "drb": 100 * p["dreb"] / poss, "ast": 100 * p["ast"] / poss,
        "stl": 100 * p["stl"] / poss, "blk": 100 * p["blk"] / poss, "to": 100 * p["to"] / poss, "pf": 100 * p["pf"] / poss,
    }


def _game_poss(game: dict[str, Any]) -> float | None:
    """Game possessions from the stints (sum of stint possessions)."""
    total = sum(s["poss"] for s in game.get("stints", []))
    return total if total > 30 else None


COUNT_KEYS = ("min", "pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "ast", "stl", "blk", "to", "pf")


def accumulate(games: list[dict[str, Any]], as_of: datetime | None = None, half_life: float = 90.0,
               team_ids: set[str] | None = MAC_IDS) -> dict[str, dict[str, Any]]:
    """Recency-weighted season totals per player (on `team_ids`, or every team), with possessions on the floor."""
    tot: dict[str, dict[str, Any]] = {}
    for g in games:
        when = R.parse_dt(g["date"]) if g.get("date") else None
        if as_of and when and when >= as_of:
            continue
        gp = _game_poss(g)
        if not gp:
            continue
        w = 1.0
        if as_of and when:
            w = max(0.05, 0.5 ** ((as_of - when).total_seconds() / 86400 / half_life))
        for p in g["players"]:
            if (team_ids is not None and p["team_espn_id"] not in team_ids) or p.get("dnp") or not p.get("min"):
                continue
            t = tot.setdefault(p["espn_id"], {"id": p["espn_id"], "name": p["name"], "team": p["team_espn_id"],
                                              "pos": p.get("position"), "gp": 0, "poss": 0.0, "min_raw": 0,
                                              **{k: 0.0 for k in COUNT_KEYS}})
            t["team"] = p["team_espn_id"]  # latest team wins
            t["gp"] += 1
            t["min_raw"] += p["min"]
            t["poss"] += w * gp * p["min"] / 40
            for k in COUNT_KEYS:
                t[k] += w * (p.get(k) or 0)
    return tot


def box_rating(t: dict[str, Any], weights: dict[str, Any], team_ast_per_fgm: float = 0.5) -> tuple[float, float]:
    """(offense, net) per 100 before shrinkage and team adjustment.

    Assist split: each assist moves `assist_share` of an average made basket's value
    from the scorer to the passer. Scorers give back in proportion to their made
    field goals times the team's assist rate, so the team total is unchanged.
    """
    rates = _player_rates(t)
    share = weights.get("assist_share", ASSIST_SHARE)
    out = []
    for part in ("off", "net"):
        w = weights[part]
        made = rates["tpm"] + rates["twom"]
        fg_value = (w["tpm"] * rates["tpm"] + w["twom"] * rates["twom"]) / made if made else (w["tpm"] + 2 * w["twom"]) / 3
        avg_fg_value = (w["tpm"] + 2 * w["twom"]) / 3  # ~1 three per 2 twos in college
        v = w["const"] / 5 + sum(w[k] * rates[k] for k in STATS)
        v += share * avg_fg_value * rates["ast"] - share * team_ast_per_fgm * made * fg_value
        out.append(v)
    return out[0], out[1]


def rate_players(games: list[dict[str, Any]], team_ratings: R.Ratings, prior: dict[str, dict[str, float]] | None = None,
                 as_of: datetime | None = None, weights: dict[str, Any] | None = None,
                 team_ids: set[str] | None = MAC_IDS) -> dict[str, dict[str, Any]]:
    weights = weights or load_weights()
    prior = prior or {}
    tot = accumulate(games, as_of, team_ids=team_ids)
    team_ast: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for t in tot.values():
        team_ast[t["team"]][0] += t["ast"]
        team_ast[t["team"]][1] += t["fgm"]
    out: dict[str, dict[str, Any]] = {}
    for pid, t in tot.items():
        if t["poss"] <= 0:
            continue
        ta, tf = team_ast[t["team"]]
        off, net = box_rating(t, weights, ta / tf if tf else 0.5)
        pr = prior.get(pid)
        p_net = pr["net"] * (1 - PRIOR_REGRESS) if pr else NEWCOMER_PRIOR
        p_off = pr["off"] * (1 - PRIOR_REGRESS) if pr else NEWCOMER_PRIOR / 2
        k = SHRINK_POSS / (SHRINK_POSS + t["poss"])
        out[pid] = {**t, "raw_off": off, "raw_net": net, "returning": pr is not None,
                    "off": off * (1 - k) + p_off * k, "net": net * (1 - k) + p_net * k, "prior_share": k}
    # Team adjustment: five times the minutes-weighted average must equal the team rating.
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in out.values():
        by_team[p["team"]].append(p)
    for tid, plist in by_team.items():
        tr = team_ratings.teams.get(tid)
        mins = sum(p["min"] for p in plist)
        if not tr or not mins:
            continue
        wavg_net = sum(p["net"] * p["min"] for p in plist) / mins
        wavg_off = sum(p["off"] * p["min"] for p in plist) / mins
        shift_net = ((tr["o"] - tr["d"]) - 5 * wavg_net) / 5
        shift_off = (tr["o"] - 5 * wavg_off) / 5
        for p in plist:
            p["team_adj"] = shift_net
            p["net"] += shift_net
            p["off"] += shift_off
            p["def"] = p["net"] - p["off"]
    for p in out.values():
        p.setdefault("def", p["net"] - p["off"])
        p.setdefault("team_adj", 0.0)
    return out


# ---------------------------------------------------------------- on/off


def onoff(games: list[dict[str, Any]], players: dict[str, dict[str, Any]], team_ratings: R.Ratings,
          as_of: datetime | None = None, team_ids: set[str] = MAC_IDS) -> dict[str, dict[str, Any]]:
    """Raw on/off splits and a ridge (adjusted plus-minus) rating pulled toward the box rating."""
    idx = {pid: i for i, pid in enumerate(players)}
    n = len(idx)
    A = np.zeros((n + 1, n + 1))  # last column: home court
    b = np.zeros(n + 1)
    on = defaultdict(lambda: [0.0, 0.0])  # pid -> [margin*poss, poss] on floor
    team_tot = defaultdict(lambda: [0.0, 0.0])  # team -> [margin, poss]
    for g in games:
        when = R.parse_dt(g["date"]) if g.get("date") else None
        if as_of and when and when >= as_of:
            continue
        sides = {t["home_away"]: t["espn_id"] for t in g["teams"]}
        if set(sides) != {"home", "away"}:
            continue
        loc = 0.0 if g.get("neutral_site") else 1.0
        for s in g["stints"]:
            if s.get("bad") or s["poss"] < 1:
                continue
            margin = 100 * (s["pts_h"] - s["pts_a"]) / s["poss"]
            y = margin
            cols: dict[int, float] = {n: loc * 2 * team_ratings.hca}
            for side, sign in (("home", 1.0), ("away", -1.0)):
                tid = sides[side]
                side_margin = sign * margin
                team_tot[tid][0] += side_margin * s["poss"]
                team_tot[tid][1] += s["poss"]
                if tid in team_ids:
                    for pid in s[side]:
                        on[pid][0] += side_margin * s["poss"]
                        on[pid][1] += s["poss"]
                        if pid in idx:
                            cols[idx[pid]] = cols.get(idx[pid], 0.0) + sign
                else:
                    tr = team_ratings.team(tid if tid in team_ratings.teams else R.NON_D1)
                    y -= sign * (tr["o"] - tr["d"])
            # hca is fixed from the team model: move it to the left side.
            y -= cols.pop(n)
            w = s["poss"]
            for c1, v1 in cols.items():
                b[c1] += w * v1 * y
                for c2, v2 in cols.items():
                    A[c1, c2] += w * v1 * v2
    for pid, i in idx.items():
        A[i, i] += ONOFF_LAMBDA
        b[i] += ONOFF_LAMBDA * players[pid]["net"]
    A[n, n] = 1.0
    x = np.linalg.solve(A, b)
    out = {}
    for pid, i in idx.items():
        m_on, p_on = on[pid]
        tm, tp = team_tot[players[pid]["team"]]
        off_poss = tp - p_on
        out[pid] = {
            "on_poss": p_on,
            "on_net": m_on / p_on if p_on else None,
            "off_net": (tm - m_on) / off_poss if off_poss > 50 else None,
            "apm": float(x[i]),
        }
        if out[pid]["on_net"] is not None and out[pid]["off_net"] is not None:
            out[pid]["onoff"] = out[pid]["on_net"] - out[pid]["off_net"]
    return out


# ---------------------------------------------------------------- season build


def d1_ids(team_ratings: R.Ratings) -> set[str]:
    return {t for t in team_ratings.teams if t != R.NON_D1}


def last_season_prior(team_prior: R.Ratings, weights: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Last season's rating for every D-I player the book has (transfers included)."""
    games = pbp.load_games(SEASON - 1, team_ids=None)
    if not games:
        return {}
    rated = rate_players(games, team_prior, prior=None, weights=weights, team_ids=d1_ids(team_prior))
    return {pid: {"off": p["off"], "net": p["net"]} for pid, p in rated.items() if p["poss"] >= 150}


def season_players(team_ratings: R.Ratings, team_prior: R.Ratings, now: datetime,
                   weights: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Every D-I player this season, rated once. Conference tables are slices of this."""
    prior = last_season_prior(team_prior, weights)
    games = pbp.load_games(SEASON, team_ids=None)
    return games, rate_players(games, team_ratings, prior, now, weights, team_ids=d1_ids(team_ratings))


def table(games: list[dict[str, Any]], players: dict[str, dict[str, Any]], team_ratings: R.Ratings, now: datetime,
          weights: dict[str, Any], team_ids: set[str], names: dict[str, dict[str, Any]] | None = None,
          with_onoff: bool = True) -> dict[str, Any]:
    """Player leaderboard for one group of teams (the MAC, or any conference)."""
    names = names or {}
    mine = {pid: p for pid, p in players.items() if p["team"] in team_ids}
    games = [g for g in games if any(t["espn_id"] in team_ids for t in g["teams"])]
    onoff_live = now.date() >= ONOFF_START
    oo = onoff(games, mine, team_ratings, now, team_ids) if mine and (with_onoff or onoff_live) else {}
    team_games: dict[str, int] = defaultdict(int)
    for g in games:
        gp = _game_poss(g)
        for t in g["teams"]:
            if t["espn_id"] in team_ids and gp:
                team_games[t["espn_id"]] += 1
    rows = []
    for pid, p in mine.items():
        team = BY_ESPN_ID.get(p["team"])
        nm = names.get(p["team"], {})
        gpl = p["gp"]
        row = {
            "id": pid, "name": p["name"], "team_id": p["team"],
            "team_key": team.key if team else p["team"],
            "team": team.short if team else nm.get("short", ""),
            "abbr": team.abbr if team else nm.get("abbr", ""), "pos": p.get("pos"), "gp": gpl,
            "mpg": round(p["min_raw"] / gpl, 1) if gpl else 0,
            "min_pct": round(100 * p["min_raw"] / (40 * team_games[p["team"]]), 1) if team_games[p["team"]] else None,
            "poss": round(p["poss"]),
            "ppg": round(p["pts"] / max(1e-9, p["min"]) * p["min_raw"] / gpl, 1) if gpl else 0,
            "usage": _usage(p),
            "ts": round(100 * p["pts"] / (2 * (p["fga"] + 0.44 * p["fta"])), 1) if (p["fga"] + p["fta"]) else None,
            "off": round(p["off"], 2), "def": round(p["def"], 2), "net": round(p["net"], 2),
            "raw_net": round(p["raw_net"], 2), "team_adj": round(p["team_adj"], 2),
            "prior_share": round(p["prior_share"], 2), "returning": p["returning"],
            **({k: (round(v, 2) if isinstance(v, float) else v) for k, v in oo.get(pid, {}).items()}),
        }
        rows.append(row)
    rows.sort(key=lambda r: -r["net"])
    for i, r in enumerate(rows, 1):
        r["rk"] = i
    return {
        "as_of": now.isoformat(timespec="seconds"),
        "onoff_live": onoff_live,
        "onoff_start": ONOFF_START.isoformat(),
        "weights": weights,
        "players": rows,
        "games": len(games),
    }


def build(team_ratings: R.Ratings, team_prior: R.Ratings, now: datetime | None = None) -> dict[str, Any]:
    """MAC leaderboard (players.html)."""
    now = now or datetime.now(timezone.utc)
    weights = load_weights()
    games, players = season_players(team_ratings, team_prior, now, weights)
    return table(games, players, team_ratings, now, weights, MAC_IDS)


def _usage(p: dict[str, Any]) -> float | None:
    """Share of possessions a player ends while on the floor (shots, free-throw trips, turnovers)."""
    if not p["poss"]:
        return None
    used = p["fga"] + 0.475 * p["fta"] + p["to"]
    return round(100 * used / p["poss"], 1)


def team_adjustment(players: list[dict[str, Any]], team_key: str, out_ids: set[str], replacement: float = -2.0) -> dict[str, Any]:
    """Change in a team's net rating (per 100) if these players don't play.

    Each missing player's minutes go to a replacement-level player. Uses the
    player's share of team minutes this season.
    """
    delta = 0.0
    who = []
    for p in players:
        if p["team_key"] == team_key and p["id"] in out_ids and p.get("min_pct"):
            share = p["min_pct"] / 100  # of one of five floor spots
            d = share * (replacement - p["net"])
            delta += d
            who.append({"name": p["name"], "net": p["net"], "min_pct": p["min_pct"], "delta": round(d, 2)})
    return {"delta_net": delta, "players": who}
