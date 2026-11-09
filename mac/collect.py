"""Command line entry point.

  python -m mac.collect schedule   # refresh data/schedule.json from ESPN
  python -m mac.collect rosters    # refresh rosters and fetch new box scores
  python -m mac.collect lines     # append a lines snapshot (needs ODDS_API_KEY)
  python -m mac.collect build-db   # write data/mac.sqlite
  python -m mac.collect site       # render the dashboard into site/
  python -m mac.collect venues     # geocode any new venue city into data/venues.json
  python -m mac.collect ncaa       # refresh every D-I result this season (+ box extras, closing lines)
  python -m mac.collect ncaa-backfill  # one-time: last two seasons, for the prior and the backtest
  python -m mac.collect ratings    # print the MAC ratings table
  python -m mac.collect all        # schedule + D-I results + lines + site (what the cron job runs)
"""

from __future__ import annotations

import json
import sys

from .config import SEASON

from . import build, db, espn, ncaa, odds, rosters, travel


def refresh_ncaa() -> dict:
    if not ncaa.TEAMS_PATH.exists():
        ncaa.fetch_d1_teams()
    out = ncaa.refresh_season(SEASON)
    out["enrich"] = ncaa.enrich_season(SEASON, limit=400)
    return out


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
    elif cmd == "build-db":
        print("sqlite:", db.build())
    elif cmd == "site":
        print("site:", build.render_site())
    elif cmd == "venues":
        print("venues:", travel.geocode_missing(espn.load_schedule()["games"]))
    elif cmd == "ncaa":
        print("ncaa:", refresh_ncaa())
    elif cmd == "ncaa-backfill":
        ncaa.fetch_d1_teams()
        for season in (SEASON - 2, SEASON - 1):
            print(ncaa.refresh_season(season, full=True))
            print(ncaa.enrich_season(season))
    elif cmd == "ratings":
        from . import model
        m = model.build_model()
        print(f"as of {m['as_of']}: {m['games_used']} D-I games, home edge {m['hca_pts']:.1f} pts")
        for t in m["mac"]:
            print(f"{t['rk_adj_em']:>4} {t['short']:<18} off {t['adj_o']:6.1f}  def {t['adj_d']:6.1f}  net {t['adj_em']:+5.1f}  pace {t['adj_t']:5.1f}  sos {t['sos'] or 0:+5.1f}")
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
        print("site:", build.render_site())
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
