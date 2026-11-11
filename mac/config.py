"""Static configuration: the league this run builds, its teams, and where things live.

The league comes from mac/leagues.py (LEAGUE env var; the MAC by default). ESPN ids come
from the ESPN groups feed. `odds_name` matching: a team's ESPN displayName, or an alias in
the league's `odds_aliases` when a book spells a team differently.
"""

from __future__ import annotations

import os
from pathlib import Path

from .leagues import ALL as LEAGUES, Team, current

LEAGUE = current()

SEASON = 2027  # ESPN season id for 2026-27
SEASON_LABEL = "2026-27"

ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = ROOT / "data"  # D-I results, the Almanac, box-score weights, venues, odds-run log: one copy for every league
DATA_DIR = LEAGUE.data_dir  # this league's schedule, rosters, lines, news, model output (data/ for the MAC)
LINES_DIR = DATA_DIR / "lines"
SITE_ROOT = ROOT / "site"
SITE_DIR = LEAGUE.site_dir
TEMPLATES_DIR = ROOT / "templates"

# Public address of the published site, used for share cards (og:url, og:image), canonical
# links and sitemaps. GitHub Pages serves it at hardwoodbricks.com; the repo variable SITE_URL
# overrides it (leave it unset, or set it to https://hardwoodbricks.com/).
SITE_BASE = (os.environ.get("SITE_URL") or "https://hardwoodbricks.com/").rstrip("/") + "/"
SITE_URL = SITE_BASE + LEAGUE.path
# The site root is the all-conference hub (mac/hub.py). Each edition's front page lives in its
# folder; the MAC's pages sit at the root, so its front page gets its own folder, mac/.
HOME = "mac/index.html" if not LEAGUE.path else "index.html"
HOME_PATH = "mac/" if not LEAGUE.path else ""
# SITE_NOINDEX=1 asks search engines to stay away (robots.txt + noindex meta). Links still work.
SITE_NOINDEX = os.environ.get("SITE_NOINDEX", "").strip().lower() in ("1", "true", "yes")

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
ODDS_BASE = "https://api.the-odds-api.com/v4"
ODDS_SPORT = "basketball_ncaab"
ODDS_MARKETS = ("h2h", "spreads", "totals")
ODDS_REGIONS = ("us",)  # fallback only; ODDS_BOOKMAKERS takes priority when set
# Naming books directly bills like regions: every 10 books (from any region) = 1 region.
# Ten books x 3 markets = 3 requests a run, the same as regions=us, but with Pinnacle
# (eu), theScore Bet (us2, still keyed espnbet) and Novig (us_ex exchange) included.
# Not offered by The Odds API: BetJACK. Caesars and Fanatics need a paid plan.
ODDS_BOOKMAKERS: tuple[str, ...] = (
    "draftkings", "fanduel", "betmgm", "espnbet", "novig",
    "pinnacle", "betrivers", "hardrockbet", "betonlineag", "bovada",
)


TEAMS: tuple[Team, ...] = LEAGUE.teams

BY_KEY = {t.key: t for t in TEAMS}
BY_ESPN_ID = {t.espn_id: t for t in TEAMS}
BY_NAME = {t.name: t for t in TEAMS}

ODDS_ALIASES: dict[str, str] = LEAGUE.odds_aliases


def team_key_for_odds_name(name: str) -> str | None:
    """Return our team key for a name as The Odds API spells it, or None if not in this league."""
    return LEAGUE.team_for_odds_name(name)
