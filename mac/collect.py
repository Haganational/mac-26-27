"""Command line entry point.

  python -m mac.collect schedule   # refresh data/schedule.json from ESPN
  python -m mac.collect rosters    # refresh rosters and fetch new box scores
  python -m mac.collect lines     # append a lines snapshot (needs ODDS_API_KEY)
  python -m mac.collect build-db   # write data/mac.sqlite
  python -m mac.collect site       # render the dashboard into site/
  python -m mac.collect all        # schedule + lines + site (what the cron job runs)
"""

from __future__ import annotations

import json
import sys

from . import build, db, espn, odds, rosters


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
    elif cmd == "all":
        out = espn.refresh_schedule()
        print(f"schedule: {len(out['games'])} games written")
        try:
            rosters.refresh_rosters()
            print("boxscores:", rosters.refresh_boxscores())
        except Exception as exc:  # noqa: BLE001 - never let ESPN hiccups block the line snapshot
            print(f"rosters/boxscores: skipped ({exc})", file=sys.stderr)
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
