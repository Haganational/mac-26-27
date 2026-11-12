"""Run the rating model on this season and line its projections up against the market.

Writes, under data/model/:
- ratings.json        every D-I team's current ratings (and the preseason prior)
- projections.jsonl   append-only: our number for each upcoming MAC game at each run,
                      next to the market number at that moment. This is the record the
                      line-timing study needs (does the market move toward the model?).
- mac_history.jsonl   one row per MAC team per day: how its ratings evolve.

`build_model()` returns everything the site needs in one dict.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from . import analysis, backtest, ncaa, power
from . import ratings as R
from .config import BY_ESPN_ID, DATA_DIR, SEASON, TEAMS
from .espn import load_schedule
from .odds import load_all_rows

MODEL_DIR = DATA_DIR / "model"
RATINGS_PATH = MODEL_DIR / "ratings.json"
PROJ_LOG = MODEL_DIR / "projections.jsonl"
MAC_HISTORY = MODEL_DIR / "mac_history.jsonl"

PARAMS = R.Params()
MODEL_VERSION = "1.0"  # bump when the method or knobs change, so logged projections stay comparable
EDGE_FLAG = 3.0  # points of disagreement with the market worth a look
MAC_IDS = {t.espn_id for t in TEAMS}


def _r1(v: float | None) -> float | None:
    return None if v is None else round(v, 1)


def current_ratings(now: datetime, p: R.Params = PARAMS) -> tuple[R.Ratings, R.Ratings, list[dict[str, Any]], dict]:
    names = ncaa.load_d1_teams()
    d1 = set(names)
    prior = backtest.season_end_prior(SEASON - 1, d1, p)
    rows, _ = backtest.season_rows(SEASON, d1)
    return R.fit(rows, now, p, prior), prior, rows, names


def market_for(game: dict[str, Any], mapping: dict[str, str], history: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    ev = history.get(mapping.get(game["game_id"], ""))
    if not ev:
        return None
    by_book = ev.get("latest_by_book") or {}
    dk = by_book.get("draftkings") or {}
    return {
        "spread": ev["latest"]["spread"], "total": ev["latest"]["total"],
        "open_spread": ev["open_spread"], "open_total": ev["open_total"],
        "books": ev["latest"]["books"], "captured_at": ev["latest"]["captured_at"],
        "first_seen": ev["first_seen"],
        "dk_spread": dk.get("spread"), "dk_total": dk.get("total"),
    }


def edge_side(game: dict[str, Any], model_spread: float, market_spread: float | None) -> dict[str, Any] | None:
    """Which side the model likes against the number, and by how much."""
    if market_spread is None:
        return None
    gap = model_spread - market_spread  # negative: model likes the home team more
    side = game["home"] if gap < 0 else game["away"]
    num = market_spread if gap < 0 else -market_spread
    return {"gap": round(gap, 1), "abs": round(abs(gap), 1), "team": side["name"], "abbr": side["abbr"],
            "take": f"{side['abbr']} {num:+.1f}".replace("+0.0", "PK").replace("-0.0", "PK"),
            "flag": abs(gap) >= EDGE_FLAG}


def total_side(model_total: float, market_total: float | None) -> dict[str, Any] | None:
    if market_total is None:
        return None
    gap = model_total - market_total
    return {"gap": round(gap, 1), "abs": round(abs(gap), 1), "take": f"{'Over' if gap > 0 else 'Under'} {market_total:g}",
            "flag": abs(gap) >= EDGE_FLAG}


def team_label(r: R.Ratings, tid: str) -> str:
    return tid if tid in r.teams else R.NON_D1


def project_upcoming(r: R.Ratings, games: list[dict[str, Any]], now: datetime, days: int = 10,
                     p: R.Params = PARAMS) -> list[dict[str, Any]]:
    rows_ = load_all_rows()
    history = analysis.line_history(rows_)
    mapping = analysis.match_lines_to_games(games, history)
    out = []
    horizon = now + timedelta(days=days)
    for g in games:
        tip = analysis.parse_iso(g["date"])
        if g["completed"] or tip < now - timedelta(hours=3) or tip > horizon:
            continue
        h, a = team_label(r, g["home"]["espn_id"]), team_label(r, g["away"]["espn_id"])
        pr = R.project(r, h, a, g["neutral_site"], p)
        mkt = market_for(g, mapping, history)
        out.append({
            "game_id": g["game_id"], "date": g["date"], "conference_game": g["conference_game"],
            "neutral_site": g["neutral_site"], "time_tba": g.get("time_tba"),
            "home": {**g["home"], "games": r.team(h)["games"], "non_d1": h == R.NON_D1},
            "away": {**g["away"], "games": r.team(a)["games"], "non_d1": a == R.NON_D1},
            "model": {"spread": _r1(pr["spread"]), "margin": _r1(pr["margin"]), "total": _r1(pr["total"]), "home_pts": _r1(pr["home_pts"]),
                      "away_pts": _r1(pr["away_pts"]), "poss": _r1(pr["poss"]), "home_win": round(pr["home_win"], 3)},
            "market": mkt,
            "spread_edge": edge_side(g, pr["spread"], mkt["spread"] if mkt else None),
            "total_edge": total_side(pr["total"], mkt["total"] if mkt else None),
        })
    out.sort(key=lambda x: x["date"])
    return out


def season_to_date(rows: list[dict[str, Any]], prior: R.Ratings, p: R.Params = PARAMS) -> list[dict[str, Any]]:
    """Walk-forward projections for MAC games already played this season: model vs close vs result."""
    proj = R.walk_forward(rows, p, prior)
    out = []
    for g in proj:
        if g["home"] not in MAC_IDS and g["away"] not in MAC_IDS:
            continue
        line = g.get("line") or {}
        margin = g["pts_h"] - g["pts_a"]
        res = {"id": g["id"], "date": g["date"].isoformat(), "home": g["home"], "away": g["away"],
               "home_raw_name": g.get("home_name"), "away_raw_name": g.get("away_name"),
               "pts_h": g["pts_h"], "pts_a": g["pts_a"],
               "model_spread": _r1(g["proj"]["spread"]), "model_total": _r1(g["proj"]["total"]),
               "close_spread": line.get("home_spread"), "close_total": line.get("total")}
        res["model_err"] = _r1(abs(g["proj"]["margin"] - margin))
        if res["close_spread"] is not None:
            res["close_err"] = _r1(abs(-res["close_spread"] - margin))
            gap = g["proj"]["spread"] - res["close_spread"]
            cover = margin + res["close_spread"]
            res["spread_gap"] = _r1(gap)
            res["model_ats"] = None if cover == 0 or gap == 0 else ("W" if (cover > 0) == (gap < 0) else "L")
        if res["close_total"] is not None:
            pts = g["pts_h"] + g["pts_a"]
            gap_t = g["proj"]["total"] - res["close_total"]
            res["total_gap"] = _r1(gap_t)
            res["model_ou"] = None if pts == res["close_total"] or gap_t == 0 else ("W" if (pts > res["close_total"]) == (gap_t > 0) else "L")
        out.append(res)
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def mac_table(r: R.Ratings, prior: R.Ratings, rows: list[dict[str, Any]], names: dict, games: list[dict[str, Any]],
              now: datetime, p: R.Params = PARAMS) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    table = R.team_table(r, rows, names, p)
    by_id = {t["id"]: t for t in table}
    # Remaining schedule strength: average net rating of opponents still to play.
    remaining: dict[str, list[float]] = {}
    for g in games:
        if g["completed"]:
            continue
        for me, op in ((g["home"], g["away"]), (g["away"], g["home"])):
            if me["espn_id"] in MAC_IDS:
                ot = r.team(team_label(r, op["espn_id"]))
                remaining.setdefault(me["espn_id"], []).append(ot["o"] - ot["d"])
    mac = []
    for t in TEAMS:
        row = dict(by_id.get(t.espn_id) or {})
        if not row:
            continue
        pt = prior.teams.get(t.espn_id, {"o": 0, "d": 0, "t": 0})
        rem = remaining.get(t.espn_id, [])
        row.update({
            "key": t.key, "short": t.short, "abbr": t.abbr,
            "prior_em": (pt["o"] - pt["d"]) * (1 - p.regress),
            "last_season_em": pt["o"] - pt["d"],
            "prior_share": p.prior_games / (p.prior_games + row.get("games", 0)) if row.get("games") is not None else 1.0,
            "rem_sos": sum(rem) / len(rem) if rem else None,
            "rem_games": len(rem),
        })
        mac.append(row)
    mac.sort(key=lambda x: -x["adj_em"])
    # D-I rank of remaining SOS among MAC only (D-I-wide would need every schedule).
    for i, row in enumerate(sorted([m for m in mac if m["rem_sos"] is not None], key=lambda m: -m["rem_sos"]), 1):
        row["rk_rem_sos_mac"] = i
    return mac, table


def _append_jsonl(path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def log_run(now: datetime, upcoming: list[dict[str, Any]], mac: list[dict[str, Any]]) -> None:
    """Append this run's numbers; one ratings row per MAC team per day."""
    stamp = now.isoformat(timespec="seconds")
    _append_jsonl(PROJ_LOG, [{
        "generated_at": stamp, "model_version": MODEL_VERSION, "game_id": u["game_id"], "tip": u["date"],
        "home_key": u["home"].get("key"), "away_key": u["away"].get("key"),
        "home_espn_id": u["home"]["espn_id"], "away_espn_id": u["away"]["espn_id"],
        "non_d1": bool(u["home"]["non_d1"] or u["away"]["non_d1"]),
        "proj_margin": u["model"]["margin"], "proj_total": u["model"]["total"], "proj_pace": u["model"]["poss"],
        "win_prob_home": u["model"]["home_win"],
        "model_spread": u["model"]["spread"], "model_total": u["model"]["total"],
        "mkt_spread": (u["market"] or {}).get("spread"), "mkt_total": (u["market"] or {}).get("total"),
        "mkt_captured_at": (u["market"] or {}).get("captured_at"),
    } for u in upcoming])
    day = now.date().isoformat()
    seen = set()
    if MAC_HISTORY.exists():
        for line in MAC_HISTORY.read_text().splitlines():
            row = json.loads(line)
            if row["day"] == day:
                seen.add(row["key"])
    _append_jsonl(MAC_HISTORY, [{
        "day": day, "key": m["key"], "adj_o": round(m["adj_o"], 2), "adj_d": round(m["adj_d"], 2),
        "adj_em": round(m["adj_em"], 2), "adj_t": round(m["adj_t"], 2), "rk": m["rk_adj_em"], "games": m["games"],
    } for m in mac if m["key"] not in seen])


def load_backtest() -> dict[str, Any] | None:
    if not backtest.BACKTEST_PATH.exists():
        return None
    return json.loads(backtest.BACKTEST_PATH.read_text())


def _players(r: R.Ratings, prior: R.Ratings, now: datetime, log: bool, table: list[dict[str, Any]],
             names: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Box-score player ratings for the MAC page, and every conference's tables for the book.

    Every D-I player is rated once; the MAC and each conference are slices. Shown on
    the site; not yet used in projections.
    """
    from . import book, player_ratings

    try:
        weights = player_ratings.load_weights()
        games, players = player_ratings.season_players(r, prior, now, weights)
        out = player_ratings.table(games, players, r, now, weights, MAC_IDS)
    except Exception as exc:  # noqa: BLE001 - player layer must never block the team model
        print(f"players: skipped ({exc!r})")
        return None, None
    if log:
        player_ratings.PLAYERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        player_ratings.PLAYERS_PATH.write_text(json.dumps(out, indent=0))
    try:
        tables = book.conference_tables(games, players, r, table, names, now, weights)
    except Exception as exc:  # noqa: BLE001
        print(f"book: skipped ({exc!r})")
        tables = None
    return out, tables


def build_model(now: datetime | None = None, log: bool = False) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    r, prior, rows, names = current_ratings(now)
    games = load_schedule()["games"]
    mac, table = mac_table(r, prior, rows, names, games, now)
    upcoming = project_upcoming(r, games, now)
    by_id = {t["id"]: t for t in table}
    for u in upcoming:  # each side's ratings and D-I ranks, for the game preview pages
        for side in ("home", "away"):
            t = by_id.get(u[side]["espn_id"])
            u[side]["rt"] = {k: t[k] for k in ("adj_o", "adj_d", "adj_em", "adj_t", "rk_adj_em", "rk_adj_o", "rk_adj_d", "rk_adj_t")} if t else None
    std = season_to_date(rows, prior)
    for g in std:
        for side in ("home", "away"):
            tid = g[side]
            g[f"{side}_name"] = (BY_ESPN_ID[tid].short if tid in BY_ESPN_ID
                                 else names.get(tid, {}).get("short") or g.get(f"{side}_raw_name") or "Non-D-I")
            g[f"{side}_mac"] = tid in MAC_IDS
    lined = [g for g in std if g.get("close_spread") is not None]
    record = {
        "games": len(std),
        "model_mae": _r1(sum(g["model_err"] for g in std) / len(std)) if std else None,
        "lined": len(lined),
        "model_mae_lined": _r1(sum(g["model_err"] for g in lined) / len(lined)) if lined else None,
        "close_mae": _r1(sum(g["close_err"] for g in lined) / len(lined)) if lined else None,
        "ats_w": sum(1 for g in lined if g.get("model_ats") == "W"),
        "ats_l": sum(1 for g in lined if g.get("model_ats") == "L"),
        "ou_w": sum(1 for g in std if g.get("model_ou") == "W"),
        "ou_l": sum(1 for g in std if g.get("model_ou") == "L"),
    }
    out = {
        "as_of": r.as_of, "mu": r.mu, "tau": r.tau, "hca": r.hca,
        "hca_pts": r.hca * 2 * r.tau / 100,
        "games_used": r.games_used, "params": r.params, "edge_flag": EDGE_FLAG,
        "mac": mac, "top25": table[:25], "d1_count": len(table),
        "all_teams": [{"adj_o": t["adj_o"], "adj_d": t["adj_d"], "short": t["short"]} for t in table if t["games"]],
        "upcoming": upcoming, "season_to_date": std, "record": record,
        "backtest": load_backtest(),
    }
    out["power"] = power.index(rows, r, prior, now, [(t.espn_id, t.key, t.short) for t in TEAMS])
    out["players"], out["book"] = _players(r, prior, now, log, table, names)
    if log:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        RATINGS_PATH.write_text(json.dumps({
            "as_of": r.as_of, "mu": r.mu, "tau": r.tau, "hca": r.hca, "params": r.params,
            "teams": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in t.items()} for t in table],
        }, indent=0))
        log_run(now, upcoming, mac)
    return out
