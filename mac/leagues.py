"""Every league the site publishes, and which one this run builds.

The MAC is the flagship and builds at the site root. Other leagues reuse the same
pipeline and publish under their own folder (hardwoodbricks.com/asun/), with their
own data folder (data/leagues/<key>/). Pick one with the LEAGUE environment variable:

    python -m mac.collect site               # the MAC
    LEAGUE=asun python -m mac.collect site   # the ASUN edition

`features` switches the hand-built parts on per league. A league without a feature
skips that page and its links:
    x          follow-on-X list and player handles
    research   coach, storylines and preseason research files
    mac90      the daily 90-second script, video and YouTube card
    notes      Fieldhouse Notes and the author desk
    book       the Almanac (built once, by the MAC edition)
    athletics  per-school athletics-site news feeds (without it: Google News only)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Team:
    key: str  # short slug used everywhere internally
    espn_id: str
    abbr: str
    name: str  # ESPN displayName, e.g. "Toledo Rockets"
    short: str  # e.g. "Toledo"
    color: str = "#444444"  # primary school color
    color2: str = "#ffffff"  # secondary / accent color


@dataclass(frozen=True)
class League:
    key: str  # "mac", "asun"
    short: str  # what pages call it: "MAC"
    name: str  # "Mid-American Conference"
    region: str  # a few words on where it plays, for blurbs
    teams: tuple[Team, ...]
    features: frozenset[str]
    path: str = ""  # folder under the site root: "" for the MAC, "asun/" for the ASUN
    theme: str = "brick"  # body class lg-<theme> picks the palette
    odds_aliases: dict[str, str] = field(default_factory=dict)
    news_names: dict[str, dict[str, Any]] = field(default_factory=dict)
    athletics: dict[str, str] = field(default_factory=dict)
    league_feed: tuple[str, str] | None = None  # (host, label) of the league's own SIDEARM site
    tournament: str = ""  # where the conference tournament is played, for the About page

    @property
    def data_dir(self) -> Path:
        return ROOT / "data" if not self.path else ROOT / "data" / "leagues" / self.key

    @property
    def site_dir(self) -> Path:
        return ROOT / "site" / self.path if self.path else ROOT / "site"

    def has(self, feature: str) -> bool:
        return feature in self.features

    def team_for_odds_name(self, name: str) -> str | None:
        for t in self.teams:
            if t.name == name:
                return t.key
        return self.odds_aliases.get(name)


MAC = League(
    key="mac", short="MAC", name="Mid-American Conference", region="Ohio, Michigan, Indiana, New York and Massachusetts",
    teams=(
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
    ),
    features=frozenset({"x", "research", "mac90", "notes", "book", "athletics"}),
    # Alternate spellings seen in odds feeds, mapped to our team key.
    odds_aliases={
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
    },
    # How each team is named in a Google News query and in headlines.
    # `query` is quoted in Google News; `match` patterns tag league-wide items.
    news_names={
        "akron": {"query": "Akron Zips", "match": [r"\bAkron\b", r"\bZips\b"]},
        "ball-state": {"query": "Ball State", "match": [r"\bBall St(ate|\.)?\b"]},
        "bowling-green": {"query": "Bowling Green", "match": [r"\bBowling Green\b", r"\bBGSU\b", r"\bFalcons\b"]},
        "buffalo": {"query": "Buffalo Bulls", "match": [r"\bBuffalo\b", r"\bUB Bulls\b"]},
        "central-michigan": {"query": "Central Michigan", "match": [r"\bCentral Michigan\b", r"\bCMU\b", r"\bChippewas\b"]},
        "eastern-michigan": {"query": "Eastern Michigan", "match": [r"\bEastern Michigan\b", r"\bEMU\b"]},
        "kent-state": {"query": "Kent State", "match": [r"\bKent St(ate|\.)?\b", r"\bGolden Flashes\b"]},
        "miami-oh": {"query": "Miami RedHawks", "match": [r"\bRedHawks\b", r"\bMiami \(OH\)", r"\bMiami \(Ohio\)", r"\bMiami University\b"]},
        "ohio": {"query": "Ohio Bobcats", "match": [r"\bOhio Bobcats\b", r"\bOhio University\b", r"\bOhio U\.?\b", r"\bBobcats\b", r"^Ohio\b(?! State)", r"\bOhio men[’']?s\b"]},
        "toledo": {"query": "Toledo Rockets", "match": [r"\bToledo\b"]},
        "umass": {"query": "UMass Minutemen", "match": [r"\bUMass\b", r"\bMinutemen\b", r"\bMassachusetts\b"]},
        "western-michigan": {"query": "Western Michigan", "match": [r"\bWestern Michigan\b", r"\bWMU\b", r"\bBroncos\b"]},
    },
    # Athletics sites, by team key. All are SIDEARM sites.
    athletics={
        "akron": "gozips.com",
        "ball-state": "ballstatesports.com",
        "bowling-green": "bgsufalcons.com",
        "buffalo": "ubbulls.com",
        "central-michigan": "cmuchippewas.com",
        "eastern-michigan": "emueagles.com",
        "kent-state": "kentstatesports.com",
        "miami-oh": "miamiredhawks.com",
        "ohio": "ohiobobcats.com",
        "toledo": "utrockets.com",
        "umass": "umassathletics.com",
        "western-michigan": "wmubroncos.com",
    },
    league_feed=("getsomemaction.com", "MAC (getsomemaction.com)"),
    tournament="the MAC tournament in Cleveland",
)

# ASUN 2026-27 membership from ESPN's conference feed (data/book/conferences.json, group 46).
# Colors are each school's primary and accent, from their athletics branding.
ASUN = League(
    key="asun", short="ASUN", name="ASUN Conference", region="Florida, plus Charlotte, Nashville and Louisville",
    teams=(
        Team("bellarmine", "91", "BELL", "Bellarmine Knights", "Bellarmine", "#A6192E", "#A2AAAD"),
        Team("fgcu", "526", "FGCU", "Florida Gulf Coast Eagles", "FGCU", "#002D72", "#00885A"),
        Team("jacksonville", "294", "JAX", "Jacksonville Dolphins", "Jacksonville", "#00523E", "#C5B783"),
        Team("lipscomb", "288", "LIP", "Lipscomb Bisons", "Lipscomb", "#331E54", "#F4AA00"),
        Team("north-florida", "2454", "UNF", "North Florida Ospreys", "North Florida", "#0A2240", "#A2AAAD"),
        Team("queens", "2511", "QUC", "Queens University Royals", "Queens", "#1F2A44", "#B3A369"),
        Team("stetson", "56", "STET", "Stetson Hatters", "Stetson", "#0A5640", "#FFFFFF"),
        Team("west-florida", "2697", "UWF", "West Florida Argonauts", "West Florida", "#004C97", "#00843D"),
    ),
    features=frozenset(),
    path="asun/",
    theme="glades",
    odds_aliases={
        "Florida Gulf Coast Eagles": "fgcu",
        "FGCU Eagles": "fgcu",
        "Queens University Royals": "queens",
        "Queens Royals": "queens",
        "Queens University of Charlotte Royals": "queens",
        "North Florida Ospreys": "north-florida",
        "UNF Ospreys": "north-florida",
        "West Florida Argonauts": "west-florida",
        "Jacksonville Dolphins": "jacksonville",
        "Stetson Hatters": "stetson",
        "Lipscomb Bisons": "lipscomb",
        "Bellarmine Knights": "bellarmine",
    },
    news_names={
        "bellarmine": {"query": "Bellarmine Knights", "match": [r"\bBellarmine\b"]},
        "fgcu": {"query": "FGCU", "match": [r"\bFGCU\b", r"\bFlorida Gulf Coast\b"]},
        "jacksonville": {"query": "Jacksonville Dolphins", "match": [r"\bJacksonville Dolphins\b", r"\bJU\b"]},
        "lipscomb": {"query": "Lipscomb Bisons", "match": [r"\bLipscomb\b"]},
        "north-florida": {"query": "North Florida Ospreys", "match": [r"\bNorth Florida\b", r"\bUNF\b", r"\bOspreys\b"]},
        "queens": {"query": "Queens Royals", "match": [r"\bQueens Royals\b", r"\bQueens University\b"]},
        "stetson": {"query": "Stetson Hatters", "match": [r"\bStetson\b", r"\bHatters\b"]},
        "west-florida": {"query": "West Florida Argonauts", "match": [r"\bWest Florida\b", r"\bUWF\b", r"\bArgonauts\b"]},
    },
    tournament="the ASUN tournament",
)

ALL: dict[str, League] = {lg.key: lg for lg in (MAC, ASUN)}


def current() -> League:
    key = (os.environ.get("LEAGUE") or "mac").strip().lower()
    if key not in ALL:
        raise SystemExit(f"LEAGUE={key!r} is not one of {sorted(ALL)}")
    return ALL[key]
