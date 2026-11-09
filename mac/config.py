"""Static configuration: the 12 MAC members for 2026-27 and their identifiers.

ESPN ids come from the ESPN groups feed (Mid-American Conference, season 2027).
`odds_name` is how The Odds API names the team; it matches ESPN's displayName
except where noted. Update `ODDS_ALIASES` if a book spells a team differently.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SEASON = 2027  # ESPN season id for 2026-27
SEASON_LABEL = "2026-27"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LINES_DIR = DATA_DIR / "lines"
SITE_DIR = ROOT / "site"
TEMPLATES_DIR = ROOT / "templates"

# Public address of the published site, used for share cards (og:url, og:image) and
# canonical links. Set the repo variable SITE_URL to move it to a custom domain.
SITE_URL = (os.environ.get("SITE_URL") or "https://haganational.github.io/mac-26-27/").rstrip("/") + "/"
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


@dataclass(frozen=True)
class Team:
    key: str  # short slug used everywhere internally
    espn_id: str
    abbr: str
    name: str  # ESPN displayName, e.g. "Toledo Rockets"
    short: str  # e.g. "Toledo"
    color: str = "#444444"  # primary school color
    color2: str = "#ffffff"  # secondary / accent color


TEAMS: tuple[Team, ...] = (
    Team("akron", "2006", "AKR", "Akron Zips", "Akron", "#041E42", "#A89968"),
    Team("ball-state", "2050", "BALL", "Ball State Cardinals", "Ball State", "#BA0C2F", "#FFFFFF"),
    Team("bowling-green", "189", "BGSU", "Bowling Green Falcons", "Bowling Green", "#FE5000", "#4F2C1D"),
    Team("buffalo", "2084", "BUF", "Buffalo Bulls", "Buffalo", "#005BBB", "#FFFFFF"),
    Team("central-michigan", "2117", "CMU", "Central Michigan Chippewas", "Central Michigan", "#6A0032", "#FFC82E"),
    Team("eastern-michigan", "2199", "EMU", "Eastern Michigan Eagles", "Eastern Michigan", "#006633", "#FFFFFF"),
    Team("kent-state", "2309", "KENT", "Kent State Golden Flashes", "Kent State", "#002664", "#EAAB00"),
    Team("miami-oh", "193", "M-OH", "Miami (OH) RedHawks", "Miami (OH)", "#C3142D", "#FFFFFF"),
    Team("ohio", "195", "OHIO", "Ohio Bobcats", "Ohio", "#00694E", "#FFFFFF"),
    Team("toledo", "2649", "TOL", "Toledo Rockets", "Toledo", "#15397F", "#FFCE00"),
    Team("umass", "113", "MASS", "Massachusetts Minutemen", "UMass", "#881C1C", "#FFFFFF"),
    Team("western-michigan", "2711", "WMU", "Western Michigan Broncos", "Western Michigan", "#6C4023", "#F1C500"),
)

BY_KEY = {t.key: t for t in TEAMS}
BY_ESPN_ID = {t.espn_id: t for t in TEAMS}
BY_NAME = {t.name: t for t in TEAMS}

# Alternate spellings seen in odds feeds, mapped to our team key.
ODDS_ALIASES: dict[str, str] = {
    "Miami (OH) RedHawks": "miami-oh",
    "Miami Ohio RedHawks": "miami-oh",
    "Miami (Ohio) RedHawks": "miami-oh",
    "UMass Minutemen": "umass",
    "Massachusetts Minutemen": "umass",
    "Kent State Golden Flashes": "kent-state",
    "Kent St Golden Flashes": "kent-state",
    "Ball State Cardinals": "ball-state",
    "Ball St Cardinals": "ball-state",
    "Central Michigan Chippewas": "central-michigan",
    "Eastern Michigan Eagles": "eastern-michigan",
    "Western Michigan Broncos": "western-michigan",
    "Bowling Green Falcons": "bowling-green",
}


def team_key_for_odds_name(name: str) -> str | None:
    """Return our team key for a name as The Odds API spells it, or None if not MAC."""
    if name in BY_NAME:
        return BY_NAME[name].key
    return ODDS_ALIASES.get(name)
