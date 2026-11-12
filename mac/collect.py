"""Command line entry point.

  python -m mac.collect schedule   # refresh data/schedule.json from ESPN
  python -m mac.collect rosters    # refresh rosters and fetch new box scores
  python -m mac.collect lines     # append a lines snapshot (needs ODDS_API_KEY)
  python -m mac.collect build-db   # write data/mac.sqlite
  python -m mac.collect site       # render the dashboard into site/
  python -m mac.collect news     # refresh the news ticker feeds into data/news/
  python -m mac.collect venues     # geocode any new venue city into data/venues.json
  python -m mac.collect ncaa       # refresh every D-I result this season (+ box extras, closing lines)
  python -m mac.collect ncaa-backfill  # one-time: last two seasons, for the prior and the backtest
  python -m mac.collect conferences  # refresh data/book/conferences.json (also weekly inside ncaa)
  python -m mac.collect book       # print every conference's table summary (the site publishes them under book/)
  python -m mac.collect ratings    # print the MAC ratings table
  python -m mac.collect box-weights  # refit what each box-score stat is worth (last season)
  python -m mac.collect live       # live scores for games in progress (ESPN only), new box scores, re-render
  python -m mac.collect all        # schedule + D-I results + lines + site (what the cron job runs)
  LEAGUE=asun python -m mac.collect edition   # another league's full refresh: schedule, rosters, news, site
  LEAGUE=asun python -m mac.collect lines-backfill  # one-time: that league's line history from the Almanac snapshots

The MAC run's odds pull also writes every other edition's lines, so an edition never calls the Odds API.
"""

from __future__ import annotations

import json
import sys

from .config import SEASON

from . import build, db, espn, ncaa, news, odds, rosters, travel


def refresh_ncaa() -> dict:
    from . import book, pbp

    if not ncaa.TEAMS_PATH.exists():
        ncaa.fetch_d1_teams()
    if book.conferences_stale():
        try:
            book.fetch_conferences(SEASON)
        except Exception as exc:  # keep the old registry; never fail the run over it
            print(f"conferences: {exc}", file=sys.stderr)
    out = ncaa.refresh_season(SEASON)
    # One summary call per finished D-I game: team box, closing line, and the book's player lines + lineups.
    out["enrich"] = ncaa.enrich_season(SEASON, limit=400)
    out["pbp"] = pbp.refresh(SEASON)  # MAC games enrichment missed, if any
    return out


def refresh_live() -> None:
    """In-progress scores from ESPN's scoreboard; box scores for games that just went final. Never fails the run."""
    try:
        out = espn.refresh_live()
        print("live:", out)
        if out["finished"]:
            print("boxscores:", rosters.refresh_boxscores())
    except Exception as exc:  # noqa: BLE001 - a scoreboard hiccup must not block the build
        print(f"live: skipped ({exc})", file=sys.stderr)


def refresh_nba() -> None:
    """NBA rosters (weekly) and finished NBA nights, for the alumni line in recaps. Never blocks the build."""
    from . import nba_alumni
    try:
        print("nba rosters:", nba_alumni.refresh_rosters())
        print("nba nights:", nba_alumni.refresh_nights())
    except Exception as exc:  # noqa: BLE001
        print(f"nba: skipped ({exc})", file=sys.stderr)


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd == "schedule":
        out = espn.refresh_schedule()
        print(f"schedule: {len(out['games'])} games written")
    elif cmd == "rosters":
        out = rosters.refresh_rosters()
        print(f"rosters: {sum(len(v) for v in out['rosters'].values())} players")
        print("boxscores:", rosters.refresh_boxscores())
    elif cmd == "lines":
        print(json.dumps(odds.snapshot_lines(), indent=1))
    elif cmd == "quick":
        # Every-30-minute run: one odds snapshot (3 requests), live scores and a re-render. No news or ratings refresh.
        refresh_live()
        try:
            print(json.dumps(odds.snapshot_lines(), indent=1))
        except odds.OddsApiError as exc:
            print(f"lines: skipped ({exc})", file=sys.stderr)
        refresh_nba()
        print("site:", build.render_site())
    elif cmd == "live":
        # Every-15-minute game-night run: ESPN scores only (no Odds API credits), then a re-render.
        refresh_live()
        print("site:", build.render_site())
    elif cmd == "build-db":
        print("sqlite:", db.build())
    elif cmd == "site":
        print("site:", build.render_site())
    elif cmd == "social":
        from . import social
        print(social.run())
    elif cmd == "hub":
        from . import hub
        print("hub:", hub.build())
    elif cmd == "news":
        print("news:", news.refresh())
    elif cmd == "venues":
        print("venues:", travel.geocode_missing(espn.load_schedule()["games"]))
    elif cmd == "ncaa":
        print("ncaa:", refresh_ncaa())
    elif cmd == "conferences":
        from . import book
        out = book.fetch_conferences(SEASON)
        print(f"conferences: {len(out['conferences'])}")
    elif cmd == "book":
        from . import model
        b = model.build_model().get("book") or {"conferences": []}
        for c in b["conferences"]:
            print(f"{c['rk']:>3} {c['short']:<14} teams {c['teams']:>2}  players {c['players']:>4}  games {c['games']:>4}  avg net {c['avg_em'] or 0:+5.1f}  top {c['top']}")
    elif cmd == "ncaa-backfill":
        ncaa.fetch_d1_teams()
        for season in (SEASON - 2, SEASON - 1):
            print(ncaa.refresh_season(season, full=True))
            print(ncaa.enrich_season(season))
    elif cmd == "box-weights":
        from . import player_ratings
        w = player_ratings.fit_weights()
        print(json.dumps({k: w[k] for k in ("season", "games", "r2_net", "r2_off")}), json.dumps({k: round(v, 2) for k, v in w["net"].items()}))
    elif cmd == "ratings":
        from . import model
        m = model.build_model()
        print(f"as of {m['as_of']}: {m['games_used']} D-I games, home edge {m['hca_pts']:.1f} pts")
        for t in m["mac"]:
            print(f"{t['rk_adj_em']:>4} {t['short']:<18} off {t['adj_o']:6.1f}  def {t['adj_d']:6.1f}  net {t['adj_em']:+5.1f}  pace {t['adj_t']:5.1f}  sos {t['sos'] or 0:+5.1f}")
    elif cmd == "edition":
        # A non-MAC edition: everything but the D-I refresh and odds, which the MAC run already did.
        out = espn.refresh_schedule()
        print(f"schedule: {len(out['games'])} games written")
        print("venues:", travel.geocode_missing(out["games"]))
        try:
            rosters.refresh_rosters()
            print("boxscores:", rosters.refresh_boxscores())
        except Exception as exc:  # noqa: BLE001
            print(f"rosters/boxscores: skipped ({exc})", file=sys.stderr)
        try:
            print("news:", news.refresh())
        except Exception as exc:  # noqa: BLE001
            print(f"news: skipped ({exc})", file=sys.stderr)
        print("site:", build.render_site())
    elif cmd == "lines-backfill":
        from .config import LEAGUE
        print(LEAGUE.key, "lines:", odds.backfill_from_book(LEAGUE))
    elif cmd == "all":
        out = espn.refresh_schedule()
        print(f"schedule: {len(out['games'])} games written")
        geo = travel.geocode_missing(out["games"])
        print("venues:", geo)
        if geo["unresolved"]:
            print(f"venues: add these to travel.OVERRIDES: {geo['unresolved']}", file=sys.stderr)
        try:
            rosters.refresh_rosters()
            print("boxscores:", rosters.refresh_boxscores())
        except Exception as exc:  # noqa: BLE001 - never let ESPN hiccups block the line snapshot
            print(f"rosters/boxscores: skipped ({exc})", file=sys.stderr)
        try:
            print("ncaa:", refresh_ncaa())
        except Exception as exc:  # noqa: BLE001 - ratings fall back to the results we already have
            print(f"ncaa: skipped ({exc})", file=sys.stderr)
        try:
            print(json.dumps(odds.snapshot_lines(), indent=1))
        except odds.OddsApiError as exc:
            # Keep the schedule and site fresh even when the odds pull fails.
            print(f"lines: skipped ({exc})", file=sys.stderr)
        try:
            print("news:", news.refresh())
        except Exception as exc:  # noqa: BLE001 - a feed outage must not block the site build
            print(f"news: skipped ({exc})", file=sys.stderr)
        refresh_nba()
        print("site:", build.render_site())
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
