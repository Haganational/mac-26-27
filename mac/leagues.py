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
    midmaxx60      this edition's daily script (the video combines every edition's) and YouTube card
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
    hashtag: str = ""  # the tag on social posts; blank = the short name ("#MAC")

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
    features=frozenset({"x", "research", "midmaxx60", "notes", "book", "athletics"}),
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
    features=frozenset({"notes", "midmaxx60"}),  # Fieldhouse Notes from Craig, the Miami contributor
    path="asun/",
    league_feed=("asunsports.org", "ASUN (asunsports.org)"),
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

# Horizon 2026-27 membership from ESPN's conference feed (group 45). Northern Illinois joined from the MAC.
HORIZON = League(
    key="horizon", short="Horizon", name="Horizon League", region="the Rust Belt: Ohio, Michigan, Pennsylvania, Indiana, Illinois, Wisconsin and Kentucky",
    teams=(
        Team("cleveland-state", "325", "CLE", "Cleveland State Vikings", "Cleveland State", "#006747", "#FFFFFF"),
        Team("detroit-mercy", "2174", "DETM", "Detroit Mercy Titans", "Detroit Mercy", "#A5093E", "#002D72"),
        Team("green-bay", "2739", "GB", "Green Bay Phoenix", "Green Bay", "#006F44", "#FFFFFF"),
        Team("iu-indy", "85", "IUIN", "IU Indianapolis Jaguars", "IU Indy", "#990000", "#FFC72C"),
        Team("milwaukee", "270", "MILW", "Milwaukee Panthers", "Milwaukee", "#1B1B1B", "#FFBD00"),
        Team("northern-illinois", "2459", "NIU", "Northern Illinois Huskies", "Northern Illinois", "#BA0C2F", "#1B1B1B"),
        Team("northern-kentucky", "94", "NKU", "Northern Kentucky Norse", "Northern Kentucky", "#1B1B1B", "#FFC72C"),
        Team("oakland", "2473", "OAK", "Oakland Golden Grizzlies", "Oakland", "#1B1B1B", "#B59A57"),
        Team("purdue-fort-wayne", "2870", "PFW", "Purdue Fort Wayne Mastodons", "Purdue Fort Wayne", "#003A70", "#CFB991"),
        Team("robert-morris", "2523", "RMU", "Robert Morris Colonials", "Robert Morris", "#14234B", "#A6192E"),
        Team("wright-state", "2750", "WRST", "Wright State Raiders", "Wright State", "#007A33", "#CBA052"),
        Team("youngstown-state", "2754", "YSU", "Youngstown State Penguins", "Youngstown State", "#C8102E", "#FFFFFF"),
    ),
    features=frozenset({"midmaxx60"}),
    path="horizon/",
    league_feed=("horizonleague.org", "Horizon League (horizonleague.org)"),
    hashtag="HorizonLeague",
    theme="steel",
    odds_aliases={
        "Cleveland St Vikings": "cleveland-state",
        "Youngstown St Penguins": "youngstown-state",
        "Wright St Raiders": "wright-state",
        "IUPUI Jaguars": "iu-indy",
        "IU Indy Jaguars": "iu-indy",
        "IU Indianapolis Jaguars": "iu-indy",
        "Fort Wayne Mastodons": "purdue-fort-wayne",
        "Purdue Fort Wayne Mastodons": "purdue-fort-wayne",
        "Detroit Mercy Titans": "detroit-mercy",
        "Detroit Titans": "detroit-mercy",
        "Milwaukee Panthers": "milwaukee",
        "Green Bay Phoenix": "green-bay",
        "N Kentucky Norse": "northern-kentucky",
        "Northern Kentucky Norse": "northern-kentucky",
        "N Illinois Huskies": "northern-illinois",
        "Northern Illinois Huskies": "northern-illinois",
        "Oakland Golden Grizzlies": "oakland",
        "Robert Morris Colonials": "robert-morris",
    },
    news_names={
        "cleveland-state": {"query": "Cleveland State Vikings", "match": [r"\bCleveland St(ate|\.)?\b", r"\bCSU Vikings\b"]},
        "detroit-mercy": {"query": "Detroit Mercy Titans", "match": [r"\bDetroit Mercy\b", r"\bTitans\b"]},
        "green-bay": {"query": "Green Bay Phoenix", "match": [r"\bGreen Bay Phoenix\b", r"\bUW-Green Bay\b", r"\bUWGB\b"]},
        "iu-indy": {"query": "IU Indy Jaguars", "match": [r"\bIU Indy\b", r"\bIU Indianapolis\b", r"\bIUPUI\b"]},
        "milwaukee": {"query": "Milwaukee Panthers", "match": [r"\bMilwaukee Panthers\b", r"\bUW-Milwaukee\b", r"\bUWM\b"]},
        "northern-illinois": {"query": "Northern Illinois Huskies", "match": [r"\bNorthern Illinois\b", r"\bNIU\b"]},
        "northern-kentucky": {"query": "Northern Kentucky Norse", "match": [r"\bNorthern Kentucky\b", r"\bNKU\b", r"\bNorse\b"]},
        "oakland": {"query": "Oakland Golden Grizzlies", "match": [r"\bOakland Golden Grizzlies\b", r"\bOakland University\b"]},
        "purdue-fort-wayne": {"query": "Purdue Fort Wayne", "match": [r"\bPurdue Fort Wayne\b", r"\bPFW\b", r"\bMastodons\b"]},
        "robert-morris": {"query": "Robert Morris Colonials", "match": [r"\bRobert Morris\b", r"\bRMU\b"]},
        "wright-state": {"query": "Wright State Raiders", "match": [r"\bWright St(ate|\.)?\b"]},
        "youngstown-state": {"query": "Youngstown State Penguins", "match": [r"\bYoungstown St(ate|\.)?\b", r"\bYSU\b"]},
    },
    tournament="the Horizon League tournament in Indianapolis",
)

# Mountain West 2026-27 membership from ESPN's conference standings (group 44), after the Pac-12 rebuild:
# Grand Canyon, UC Davis and UTEP are new; Hawai'i joined from the Big West.
MW = League(
    key="mw", short="Mountain West", name="Mountain West Conference",
    region="the high country: Nevada, New Mexico, Colorado, Wyoming, Arizona, Texas, California and Hawai'i",
    teams=(
        Team("air-force", "2005", "AF", "Air Force Falcons", "Air Force", "#003594", "#8A8D8F"),
        Team("grand-canyon", "2253", "GCU", "Grand Canyon Lopes", "Grand Canyon", "#522398", "#FFFFFF"),
        Team("hawaii", "62", "HAW", "Hawai'i Rainbow Warriors", "Hawai'i", "#024731", "#FFFFFF"),
        Team("nevada", "2440", "NEV", "Nevada Wolf Pack", "Nevada", "#041E42", "#8A8D8F"),
        Team("new-mexico", "167", "UNM", "New Mexico Lobos", "New Mexico", "#BA0C2F", "#A7A8AA"),
        Team("san-jose-state", "23", "SJSU", "San José State Spartans", "San José St", "#0038A8", "#FFB81A"),
        Team("uc-davis", "302", "UCD", "UC Davis Aggies", "UC Davis", "#002855", "#B3A369"),
        Team("unlv", "2439", "UNLV", "UNLV Rebels", "UNLV", "#CF0A2C", "#CAC8C8"),
        Team("utep", "2638", "UTEP", "UTEP Miners", "UTEP", "#FF8200", "#041E42"),
        Team("wyoming", "2751", "WYO", "Wyoming Cowboys", "Wyoming", "#492F24", "#FFC425"),
    ),
    features=frozenset({"midmaxx60"}),
    path="mw/",
    league_feed=("themw.com", "Mountain West (themw.com)"),
    hashtag="MountainWest",
    theme="peaks",
    odds_aliases={
        "Grand Canyon Antelopes": "grand-canyon",
        "Grand Canyon Lopes": "grand-canyon",
        "Hawaii Rainbow Warriors": "hawaii",
        "Hawai'i Rainbow Warriors": "hawaii",
        "San Jose St Spartans": "san-jose-state",
        "San José St Spartans": "san-jose-state",
        "San Jose State Spartans": "san-jose-state",
        "UC Davis Aggies": "uc-davis",
        "UTEP Miners": "utep",
        "UNLV Rebels": "unlv",
        "Air Force Falcons": "air-force",
        "Nevada Wolf Pack": "nevada",
        "New Mexico Lobos": "new-mexico",
        "Wyoming Cowboys": "wyoming",
    },
    news_names={
        "air-force": {"query": "Air Force Falcons basketball", "match": [r"\bAir Force\b"]},
        "grand-canyon": {"query": "Grand Canyon Lopes", "match": [r"\bGrand Canyon\b", r"\bGCU\b", r"\bLopes\b"]},
        "hawaii": {"query": "Hawaii Rainbow Warriors", "match": [r"\bHawai.?i\b", r"\bRainbow Warriors\b"]},
        "nevada": {"query": "Nevada Wolf Pack", "match": [r"\bWolf Pack\b", r"\bNevada\b"]},
        "new-mexico": {"query": "New Mexico Lobos", "match": [r"\bLobos\b", r"\bUNM\b"]},
        "san-jose-state": {"query": "San Jose State Spartans", "match": [r"\bSan Jos[eé] St(ate|\.)?\b", r"\bSJSU\b"]},
        "uc-davis": {"query": "UC Davis Aggies", "match": [r"\bUC Davis\b"]},
        "unlv": {"query": "UNLV Runnin' Rebels", "match": [r"\bUNLV\b", r"\bRunnin.? Rebels\b"]},
        "utep": {"query": "UTEP Miners", "match": [r"\bUTEP\b", r"\bMiners\b"]},
        "wyoming": {"query": "Wyoming Cowboys basketball", "match": [r"\bWyoming\b", r"\bPokes\b"]},
    },
    tournament="the Mountain West tournament in Las Vegas",
)

# Metro Conference 2026-27 membership from ESPN's conference feed (group 13). This is the old
# MAAC (Metro Atlantic Athletic Conference), renamed the Metro Conference on July 1, 2026.
METRO = League(
    key="metro", short="Metro", name="Metro Conference",
    region="the Northeast corridor: New York, New Jersey, Connecticut, Massachusetts and Maryland",
    teams=(
        Team("canisius", "2099", "CAN", "Canisius Golden Griffins", "Canisius", "#002D62", "#FFC72C"),
        Team("fairfield", "2217", "FAIR", "Fairfield Stags", "Fairfield", "#C8102E", "#FFFFFF"),
        Team("iona", "314", "IONA", "Iona Gaels", "Iona", "#6F263D", "#F2A900"),
        Team("manhattan", "2363", "MAN", "Manhattan Jaspers", "Manhattan", "#00703C", "#FFFFFF"),
        Team("marist", "2368", "MRST", "Marist Red Foxes", "Marist", "#C8102E", "#FFFFFF"),
        Team("merrimack", "2771", "MRMK", "Merrimack Warriors", "Merrimack", "#003768", "#F2A900"),
        Team("mount-st-marys", "116", "MSM", "Mount St. Mary's Mountaineers", "Mount St. Mary's", "#003A70", "#FFFFFF"),
        Team("niagara", "315", "NIA", "Niagara Purple Eagles", "Niagara", "#582C83", "#FFFFFF"),
        Team("quinnipiac", "2514", "QUIN", "Quinnipiac Bobcats", "Quinnipiac", "#0C2340", "#FFB81C"),
        Team("rider", "2520", "RID", "Rider Broncs", "Rider", "#9D2235", "#FFFFFF"),
        Team("sacred-heart", "2529", "SHU", "Sacred Heart Pioneers", "Sacred Heart", "#CE1141", "#A2AAAD"),
        Team("saint-peters", "2612", "SPU", "Saint Peter's Peacocks", "Saint Peter's", "#0057B8", "#FFFFFF"),
        Team("siena", "2561", "SIE", "Siena Saints", "Siena", "#006A4E", "#FFC72C"),
    ),
    features=frozenset({"midmaxx60"}),
    path="metro/",
    theme="harbor",
    hashtag="MetroConference",
    odds_aliases={
        "Canisius Golden Griffins": "canisius",
        "Canisius Griffins": "canisius",
        "Fairfield Stags": "fairfield",
        "Iona Gaels": "iona",
        "Manhattan Jaspers": "manhattan",
        "Marist Red Foxes": "marist",
        "Merrimack Warriors": "merrimack",
        "Mount St. Mary's Mountaineers": "mount-st-marys",
        "Mount St Marys Mountaineers": "mount-st-marys",
        "Mt. St. Mary's Mountaineers": "mount-st-marys",
        "Mt St Mary's Mountaineers": "mount-st-marys",
        "Niagara Purple Eagles": "niagara",
        "Quinnipiac Bobcats": "quinnipiac",
        "Rider Broncs": "rider",
        "Sacred Heart Pioneers": "sacred-heart",
        "Saint Peter's Peacocks": "saint-peters",
        "St. Peter's Peacocks": "saint-peters",
        "St Peter's Peacocks": "saint-peters",
        "Siena Saints": "siena",
    },
    news_names={
        "canisius": {"query": "Canisius Golden Griffins", "match": [r"\bCanisius\b", r"\bGolden Griffins\b"]},
        "fairfield": {"query": "Fairfield Stags", "match": [r"\bFairfield\b", r"\bStags\b"]},
        "iona": {"query": "Iona Gaels", "match": [r"\bIona\b", r"\bGaels\b"]},
        "manhattan": {"query": "Manhattan Jaspers", "match": [r"\bManhattan Jaspers\b", r"\bJaspers\b"]},
        "marist": {"query": "Marist Red Foxes", "match": [r"\bMarist\b", r"\bRed Foxes\b"]},
        "merrimack": {"query": "Merrimack Warriors", "match": [r"\bMerrimack\b"]},
        "mount-st-marys": {"query": "Mount St. Mary's Mountaineers", "match": [r"\bMount St\.? Mary.?s\b", r"\bMt\.? St\.? Mary.?s\b"]},
        "niagara": {"query": "Niagara Purple Eagles", "match": [r"\bNiagara Purple Eagles\b", r"\bPurple Eagles\b", r"\bNiagara University\b"]},
        "quinnipiac": {"query": "Quinnipiac Bobcats", "match": [r"\bQuinnipiac\b"]},
        "rider": {"query": "Rider Broncs", "match": [r"\bRider Broncs\b", r"\bBroncs\b", r"\bRider University\b"]},
        "sacred-heart": {"query": "Sacred Heart Pioneers", "match": [r"\bSacred Heart\b"]},
        "saint-peters": {"query": "Saint Peter's Peacocks", "match": [r"\bSaint Peter.?s\b", r"\bSt\.? Peter.?s\b", r"\bPeacocks\b"]},
        "siena": {"query": "Siena Saints", "match": [r"\bSiena\b"]},
    },
    tournament="the Metro Conference tournament",
)
# Big West 2026-27 membership from ESPN's conference feed (group 9). Cal Baptist, Sacramento State and
# Utah Valley are new; UC Davis and Hawai'i left for the Mountain West. UC San Diego and UC Santa Barbara
# leave for the WCC on July 1, 2027, so this is their last Big West season.
BIGWEST = League(
    key="bigwest", short="Big West", name="The Big West Conference",
    region="California, from Sacramento down the coast to San Diego, plus Orem, Utah",
    teams=(
        Team("cal-baptist", "2856", "CBU", "California Baptist Lancers", "Cal Baptist", "#002D62", "#A48C5B"),
        Team("cal-poly", "13", "CP", "Cal Poly Mustangs", "Cal Poly", "#154734", "#BD8B13"),
        Team("csu-bakersfield", "2934", "CSUB", "Cal State Bakersfield Roadrunners", "CSU Bakersfield", "#003594", "#FFC72C"),
        Team("cal-state-fullerton", "2239", "CSUF", "Cal State Fullerton Titans", "CS Fullerton", "#00274C", "#FF7900"),
        Team("csun", "2463", "CSUN", "Cal State Northridge Matadors", "CSUN", "#CE1126", "#1B1B1B"),
        Team("long-beach-state", "299", "LBSU", "Long Beach State Beach", "Long Beach St", "#1B1B1B", "#F6B800"),
        Team("sacramento-state", "16", "SAC", "Sacramento State Hornets", "Sacramento St", "#043927", "#C4B581"),
        Team("uc-irvine", "300", "UCI", "UC Irvine Anteaters", "UC Irvine", "#0064A4", "#FFD200"),
        Team("uc-riverside", "27", "UCR", "UC Riverside Highlanders", "UC Riverside", "#2D6CC0", "#F1AB00"),
        Team("uc-san-diego", "28", "UCSD", "UC San Diego Tritons", "UC San Diego", "#182B49", "#C69214"),
        Team("uc-santa-barbara", "2540", "UCSB", "UC Santa Barbara Gauchos", "UCSB", "#003660", "#FEBC11"),
        Team("utah-valley", "3084", "UVU", "Utah Valley Wolverines", "Utah Valley", "#275D38", "#FFFFFF"),
    ),
    features=frozenset({"midmaxx60"}),
    path="bigwest/",
    theme="coast",
    odds_aliases={
        "Cal Baptist Lancers": "cal-baptist",
        "California Baptist Lancers": "cal-baptist",
        "CSU Bakersfield Roadrunners": "csu-bakersfield",
        "Cal St Bakersfield Roadrunners": "csu-bakersfield",
        "CSU Fullerton Titans": "cal-state-fullerton",
        "Cal St Fullerton Titans": "cal-state-fullerton",
        "CSU Northridge Matadors": "csun",
        "Cal St Northridge Matadors": "csun",
        "CSUN Matadors": "csun",
        "Long Beach St 49ers": "long-beach-state",
        "Long Beach State 49ers": "long-beach-state",
        "Long Beach St Beach": "long-beach-state",
        "Sacramento St Hornets": "sacramento-state",
        "Utah Valley Wolverines": "utah-valley",
        "Utah Valley St Wolverines": "utah-valley",
        "UC Irvine Anteaters": "uc-irvine",
        "UC Riverside Highlanders": "uc-riverside",
        "UC San Diego Tritons": "uc-san-diego",
        "UC Santa Barbara Gauchos": "uc-santa-barbara",
        "Cal Poly Mustangs": "cal-poly",
    },
    news_names={
        "cal-baptist": {"query": "Cal Baptist Lancers", "match": [r"\bCal Baptist\b", r"\bCalifornia Baptist\b", r"\bCBU\b"]},
        "cal-poly": {"query": "Cal Poly Mustangs basketball", "match": [r"\bCal Poly\b(?! Pomona)"]},
        "csu-bakersfield": {"query": "CSU Bakersfield Roadrunners", "match": [r"\bCSU Bakersfield\b", r"\bCal State Bakersfield\b", r"\bCSUB\b"]},
        "cal-state-fullerton": {"query": "Cal State Fullerton Titans", "match": [r"\bCal State Fullerton\b", r"\bCSU Fullerton\b", r"\bCSUF\b"]},
        "csun": {"query": "CSUN Matadors", "match": [r"\bCSUN\b", r"\bCal State Northridge\b", r"\bMatadors\b"]},
        "long-beach-state": {"query": "Long Beach State basketball", "match": [r"\bLong Beach St(ate|\.)?\b", r"\bLBSU\b"]},
        "sacramento-state": {"query": "Sacramento State Hornets", "match": [r"\bSacramento St(ate|\.)?\b", r"\bSac State\b"]},
        "uc-irvine": {"query": "UC Irvine Anteaters", "match": [r"\bUC Irvine\b", r"\bUCI\b", r"\bAnteaters\b"]},
        "uc-riverside": {"query": "UC Riverside Highlanders", "match": [r"\bUC Riverside\b", r"\bUCR\b", r"\bHighlanders\b"]},
        "uc-san-diego": {"query": "UC San Diego Tritons", "match": [r"\bUC San Diego\b", r"\bUCSD\b", r"\bTritons\b"]},
        "uc-santa-barbara": {"query": "UC Santa Barbara Gauchos", "match": [r"\bUC Santa Barbara\b", r"\bUCSB\b", r"\bGauchos\b"]},
        "utah-valley": {"query": "Utah Valley Wolverines", "match": [r"\bUtah Valley\b", r"\bUVU\b"]},
    },
    league_feed=("bigwest.org", "Big West (bigwest.org)"),
    hashtag="BigWest",
    tournament="the Big West tournament at Lee's Family Forum in Henderson, Nevada",
)

# Missouri Valley 2026-27 membership from ESPN's conference feed (data/book/conferences.json, group 18).
# Colors are each school's primary and accent from their athletics branding; check them against the schools' style guides.
MVC = League(
    key="mvc", short="Missouri Valley", name="Missouri Valley Conference",
    region="the Midwest: Illinois, Iowa and Indiana, plus Nashville and Murray, Kentucky",
    teams=(
        Team("belmont", "2057", "BEL", "Belmont Bruins", "Belmont", "#002469", "#C8102E"),
        Team("bradley", "71", "BRAD", "Bradley Braves", "Bradley", "#A50000", "#FFFFFF"),
        Team("drake", "2181", "DRKE", "Drake Bulldogs", "Drake", "#004477", "#FFFFFF"),
        Team("evansville", "339", "EVAN", "Evansville Purple Aces", "Evansville", "#4E2A84", "#F68B1F"),
        Team("illinois-state", "2287", "ILST", "Illinois State Redbirds", "Illinois State", "#CE1126", "#FFFFFF"),
        Team("indiana-state", "282", "INST", "Indiana State Sycamores", "Indiana State", "#00669A", "#FFFFFF"),
        Team("murray-state", "93", "MUR", "Murray State Racers", "Murray State", "#002148", "#ECAC00"),
        Team("northern-iowa", "2460", "UNI", "Northern Iowa Panthers", "Northern Iowa", "#4B116F", "#FFCC00"),
        Team("southern-illinois", "79", "SIU", "Southern Illinois Salukis", "Southern Illinois", "#720000", "#FFFFFF"),
        Team("uic", "82", "UIC", "UIC Flames", "UIC", "#001E62", "#D50032"),
        Team("valparaiso", "2674", "VAL", "Valparaiso Beacons", "Valparaiso", "#613318", "#FFCC00"),
    ),
    features=frozenset({"midmaxx60"}),
    path="mvc/",
    theme="arch",
    odds_aliases={
        "Illinois St Redbirds": "illinois-state",
        "Indiana St Sycamores": "indiana-state",
        "Murray St Racers": "murray-state",
        "Valparaiso Crusaders": "valparaiso",
        "Valpo Beacons": "valparaiso",
        "Illinois-Chicago Flames": "uic",
    },
    news_names={
        "belmont": {"query": "Belmont Bruins basketball", "match": [r"\bBelmont\b"]},
        "bradley": {"query": "Bradley Braves basketball", "match": [r"\bBradley Braves\b", r"\bBradley University\b", r"^Bradley\b"]},
        "drake": {"query": "Drake Bulldogs basketball", "match": [r"\bDrake Bulldogs\b", r"\bDrake University\b", r"^Drake\b"]},
        "evansville": {"query": "Evansville Purple Aces", "match": [r"\bEvansville\b", r"\bPurple Aces\b", r"\bUE\b"]},
        "illinois-state": {"query": "Illinois State Redbirds", "match": [r"\bIllinois St(ate|\.)?\b", r"\bRedbirds\b"]},
        "indiana-state": {"query": "Indiana State Sycamores", "match": [r"\bIndiana St(ate|\.)?\b", r"\bSycamores\b"]},
        "murray-state": {"query": "Murray State Racers", "match": [r"\bMurray St(ate|\.)?\b", r"\bRacers\b"]},
        "northern-iowa": {"query": "Northern Iowa Panthers", "match": [r"\bNorthern Iowa\b", r"\bUNI\b"]},
        "southern-illinois": {"query": "Southern Illinois Salukis", "match": [r"\bSouthern Illinois\b", r"\bSalukis\b", r"\bSIU\b(?!-?E)"]},
        "uic": {"query": "UIC Flames", "match": [r"\bUIC\b", r"\bIllinois Chicago\b"]},
        "valparaiso": {"query": "Valparaiso Beacons", "match": [r"\bValparaiso\b", r"\bValpo\b", r"\bBeacons\b"]},
    },
    league_feed=("mvc-sports.com", "Missouri Valley (mvc-sports.com)"),
    hashtag="MVCHoops",
    tournament="Arch Madness, the Missouri Valley tournament in St. Louis",
)

# Atlantic 10 2026-27 membership from ESPN's conference feed (group 3).
A10 = League(
    key="a10", short="A-10", name="Atlantic 10 Conference",
    region="the East, from Rhode Island and the Bronx down to Richmond, and west to Dayton, St. Louis and Chicago",
    teams=(
        Team("davidson", "2166", "DAV", "Davidson Wildcats", "Davidson", "#D42121", "#000000"),
        Team("dayton", "2168", "DAY", "Dayton Flyers", "Dayton", "#CE1141", "#004B8D"),
        Team("duquesne", "2184", "DUQ", "Duquesne Dukes", "Duquesne", "#041E42", "#BA0C2F"),
        Team("fordham", "2230", "FOR", "Fordham Rams", "Fordham", "#860038", "#FFFFFF"),
        Team("george-mason", "2244", "GMU", "George Mason Patriots", "George Mason", "#006633", "#FFCC33"),
        Team("george-washington", "45", "GW", "George Washington Revolutionaries", "George Washington", "#033C5A", "#AA9868"),
        Team("la-salle", "2325", "LAS", "La Salle Explorers", "La Salle", "#00205B", "#FFC72C"),
        Team("loyola-chicago", "2350", "LUC", "Loyola Chicago Ramblers", "Loyola Chicago", "#8A1538", "#FDB913"),
        Team("rhode-island", "227", "URI", "Rhode Island Rams", "Rhode Island", "#68ABE8", "#002147"),
        Team("richmond", "257", "RICH", "Richmond Spiders", "Richmond", "#990000", "#000066"),
        Team("saint-josephs", "2603", "JOES", "Saint Joseph's Hawks", "Saint Joseph's", "#9E1B32", "#A2AAAD"),
        Team("saint-louis", "139", "SLU", "Saint Louis Billikens", "Saint Louis", "#003DA5", "#FFFFFF"),
        Team("st-bonaventure", "179", "SBU", "St. Bonaventure Bonnies", "St. Bonaventure", "#5A3825", "#FFFFFF"),
        Team("vcu", "2670", "VCU", "VCU Rams", "VCU", "#000000", "#F8B800"),
    ),
    features=frozenset({"midmaxx60"}),
    path="a10/",
    theme="ironbridge",
    odds_aliases={
        "GW Revolutionaries": "george-washington",
        "George Washington Colonials": "george-washington",
        "Loyola (Chi) Ramblers": "loyola-chicago",
        "Loyola Chicago Ramblers": "loyola-chicago",
        "St Bonaventure Bonnies": "st-bonaventure",
        "St. Bonaventure Bonnies": "st-bonaventure",
        "Saint Joseph's Hawks": "saint-josephs",
        "St. Joseph's Hawks": "saint-josephs",
        "Virginia Commonwealth Rams": "vcu",
    },
    news_names={
        "davidson": {"query": "Davidson Wildcats basketball", "match": [r"\bDavidson\b"]},
        "dayton": {"query": "Dayton Flyers", "match": [r"\bDayton Flyers\b", r"\bUD Arena\b", r"\bUniversity of Dayton\b", r"^Dayton\b"]},
        "duquesne": {"query": "Duquesne Dukes basketball", "match": [r"\bDuquesne\b"]},
        "fordham": {"query": "Fordham Rams basketball", "match": [r"\bFordham\b"]},
        "george-mason": {"query": "George Mason Patriots basketball", "match": [r"\bGeorge Mason\b", r"\bGMU\b"]},
        "george-washington": {"query": "George Washington Revolutionaries", "match": [r"\bGeorge Washington\b(?! Carver)", r"\bGW Revolutionaries\b", r"\bGWU\b"]},
        "la-salle": {"query": "La Salle Explorers", "match": [r"\bLa Salle\b", r"\bExplorers\b"]},
        "loyola-chicago": {"query": "Loyola Chicago Ramblers", "match": [r"\bLoyola Chicago\b", r"\bLoyola-Chicago\b", r"\bRamblers\b"]},
        "rhode-island": {"query": "Rhode Island Rams basketball", "match": [r"\bRhode Island\b(?! College)", r"\bURI\b"]},
        "richmond": {"query": "Richmond Spiders", "match": [r"\bRichmond Spiders\b", r"\bSpiders\b", r"\bUniversity of Richmond\b"]},
        "saint-josephs": {"query": "Saint Joseph's Hawks", "match": [r"\bSaint Joseph[’']s\b", r"\bSt\.? Joseph[’']s\b", r"\bSt\.? Joe[’']s\b"]},
        "saint-louis": {"query": "Saint Louis Billikens", "match": [r"\bSaint Louis\b(?! Cardinals)", r"\bBillikens\b", r"\bSLU\b"]},
        "st-bonaventure": {"query": "St. Bonaventure Bonnies", "match": [r"\bSt\.? Bonaventure\b", r"\bBonnies\b"]},
        "vcu": {"query": "VCU Rams basketball", "match": [r"\bVCU\b"]},
    },
    league_feed=("atlantic10.com", "Atlantic 10 (atlantic10.com)"),
    hashtag="A10MBB",
    tournament="the Atlantic 10 tournament",
)

# Rebuilt Pac-12, 2026-27 membership from ESPN's conference feed (data/book/conferences.json, group 21):
# the two holdovers, Oregon State and Washington State, plus the five from the Mountain West, Gonzaga and Texas State.
# Colors are each school's primary and accent from their athletics branding; check them against the schools' style guides.
PAC12 = League(
    key="pac12", short="Pac-12", name="Pac-12 Conference",
    region="the West, from Pullman and Corvallis down through Boise, Logan and Fort Collins to Fresno, San Diego and San Marcos, Texas",
    teams=(
        Team("boise-state", "68", "BOIS", "Boise State Broncos", "Boise State", "#0033A0", "#D64309"),
        Team("colorado-state", "36", "CSU", "Colorado State Rams", "Colorado St", "#1E4D2B", "#C8C372"),
        Team("fresno-state", "278", "FRES", "Fresno State Bulldogs", "Fresno St", "#DB0032", "#002E6D"),
        Team("gonzaga", "2250", "GONZ", "Gonzaga Bulldogs", "Gonzaga", "#041E42", "#C8102E"),
        Team("oregon-state", "204", "ORST", "Oregon State Beavers", "Oregon St", "#DC4405", "#000000"),
        Team("san-diego-state", "21", "SDSU", "San Diego State Aztecs", "San Diego St", "#A6192E", "#000000"),
        Team("texas-state", "326", "TXST", "Texas State Bobcats", "Texas State", "#501214", "#8D734A"),
        Team("utah-state", "328", "USU", "Utah State Aggies", "Utah State", "#0F2439", "#8A8D8F"),
        Team("washington-state", "265", "WSU", "Washington State Cougars", "Washington St", "#981E32", "#5E6A71"),
    ),
    features=frozenset({"midmaxx60"}),
    path="pac12/",
    theme="timber",
    odds_aliases={
        "Colorado St Rams": "colorado-state",
        "Fresno St Bulldogs": "fresno-state",
        "Oregon St Beavers": "oregon-state",
        "San Diego St Aztecs": "san-diego-state",
        "Washington St Cougars": "washington-state",
        "Boise St Broncos": "boise-state",
        "Utah St Aggies": "utah-state",
        "Texas St Bobcats": "texas-state",
    },
    news_names={
        "boise-state": {"query": "Boise State Broncos basketball", "match": [r"\bBoise St(ate|\.)?\b"]},
        "colorado-state": {"query": "Colorado State Rams basketball", "match": [r"\bColorado St(ate|\.)?\b", r"\bCSU Rams\b"]},
        "fresno-state": {"query": "Fresno State Bulldogs basketball", "match": [r"\bFresno St(ate|\.)?\b"]},
        "gonzaga": {"query": "Gonzaga Bulldogs basketball", "match": [r"\bGonzaga\b", r"\bZags\b"]},
        "oregon-state": {"query": "Oregon State Beavers basketball", "match": [r"\bOregon St(ate|\.)?\b", r"\bBeavers\b"]},
        "san-diego-state": {"query": "San Diego State Aztecs basketball", "match": [r"\bSan Diego St(ate|\.)?\b", r"\bSDSU\b", r"\bAztecs\b"]},
        "texas-state": {"query": "Texas State Bobcats basketball", "match": [r"\bTexas St(ate|\.)?\b(?! Fair)", r"\bTXST\b"]},
        "utah-state": {"query": "Utah State Aggies basketball", "match": [r"\bUtah St(ate|\.)?\b", r"\bUSU\b"]},
        "washington-state": {"query": "Washington State Cougars basketball", "match": [r"\bWashington St(ate|\.)?\b", r"\bWSU\b", r"\bWazzu\b"]},
    },
    # No league_feed: the rebuilt Pac-12's site isn't a known SIDEARM host, so news comes from Google News and the schools.
    hashtag="Pac12MBB",
    tournament="the Pac-12 tournament",
)

# West Coast Conference 2026-27 membership from ESPN's conference feed (group 29). Gonzaga left for the Pac-12;
# Denver is new. UC San Diego and UC Santa Barbara join in 2027-28 and stay in the Big West edition until then.
WCC = League(
    key="wcc", short="WCC", name="West Coast Conference",
    region="the Pacific coast, Seattle to San Diego, plus Stockton and Denver",
    teams=(
        Team("denver", "2172", "DEN", "Denver Pioneers", "Denver", "#8B2332", "#8B6F4E"),
        Team("loyola-marymount", "2351", "LMU", "Loyola Marymount Lions", "LMU", "#8A0028", "#00447C"),
        Team("pacific", "279", "PAC", "Pacific Tigers", "Pacific", "#F47920", "#000000"),
        Team("pepperdine", "2492", "PEPP", "Pepperdine Waves", "Pepperdine", "#00205B", "#E35205"),
        Team("portland", "2501", "PORT", "Portland Pilots", "Portland", "#1E1656", "#FFFFFF"),
        Team("saint-marys", "2608", "SMC", "Saint Mary's Gaels", "Saint Mary's", "#06315B", "#D80024"),
        Team("san-diego", "301", "USD", "San Diego Toreros", "San Diego", "#002E5D", "#84BCE8"),
        Team("san-francisco", "2539", "SF", "San Francisco Dons", "San Francisco", "#00543C", "#FDBB30"),
        Team("santa-clara", "2541", "SCU", "Santa Clara Broncos", "Santa Clara", "#862633", "#FFFFFF"),
        Team("seattle", "2547", "SEA", "Seattle U Redhawks", "Seattle U", "#AA0000", "#FFFFFF"),
    ),
    features=frozenset({"midmaxx60"}),
    path="wcc/",
    theme="mission",
    odds_aliases={
        "Seattle Redhawks": "seattle",
        "Seattle University Redhawks": "seattle",
        "St. Mary's Gaels": "saint-marys",
        "Saint Mary's (CA) Gaels": "saint-marys",
        "LMU Lions": "loyola-marymount",
        "San Francisco Dons": "san-francisco",
    },
    news_names={
        "denver": {"query": "Denver Pioneers basketball", "match": [r"\bDenver Pioneers\b", r"\bUniversity of Denver\b"]},
        "loyola-marymount": {"query": "Loyola Marymount Lions basketball", "match": [r"\bLoyola Marymount\b", r"\bLMU\b"]},
        "pacific": {"query": "Pacific Tigers basketball", "match": [r"\bPacific Tigers\b", r"\bUniversity of the Pacific\b", r"\bPacific\b(?! Northwest| Coast| Time|-12| 12)"]},
        "pepperdine": {"query": "Pepperdine Waves basketball", "match": [r"\bPepperdine\b"]},
        "portland": {"query": "Portland Pilots basketball", "match": [r"\bPortland Pilots\b", r"\bUniversity of Portland\b", r"\bPilots\b"]},
        "saint-marys": {"query": "Saint Mary's Gaels basketball", "match": [r"\bSaint Mary[’']s\b", r"\bSt\.? Mary[’']s\b(?! \(MD\))", r"\bGaels\b"]},
        "san-diego": {"query": "San Diego Toreros basketball", "match": [r"\bToreros\b", r"\bUniversity of San Diego\b", r"\bUSD\b"]},
        "san-francisco": {"query": "San Francisco Dons basketball", "match": [r"\bSan Francisco Dons\b", r"\bUSF Dons\b", r"\bDons\b"]},
        "santa-clara": {"query": "Santa Clara Broncos basketball", "match": [r"\bSanta Clara\b"]},
        "seattle": {"query": "Seattle U Redhawks basketball", "match": [r"\bSeattle U\b", r"\bSeattle University\b", r"\bRedhawks\b"]},
    },
    league_feed=("wccsports.com", "WCC (wccsports.com)"),
    hashtag="WCCHoops",
    tournament="the WCC tournament",
)

# American Conference 2026-27 membership from ESPN's conference feed (group 62). The league dropped "Athletic"
# from its name in 2025. Colors are each school's primary and accent from their athletics branding.
AMERICAN = League(
    key="american", short="American", name="American Conference",
    region="from Philadelphia and Charlotte down to Tampa and Boca Raton, and west through Memphis, Birmingham and New Orleans to Tulsa, Wichita, Denton, Houston and San Antonio",
    teams=(
        Team("charlotte", "2429", "CLT", "Charlotte 49ers", "Charlotte", "#005035", "#A49665"),
        Team("east-carolina", "151", "ECU", "East Carolina Pirates", "East Carolina", "#592A8A", "#FDC82F"),
        Team("fau", "2226", "FAU", "Florida Atlantic Owls", "FAU", "#003366", "#CC0000"),
        Team("memphis", "235", "MEM", "Memphis Tigers", "Memphis", "#003087", "#898D8D"),
        Team("north-texas", "249", "UNT", "North Texas Mean Green", "North Texas", "#00853E", "#000000"),
        Team("rice", "242", "RICE", "Rice Owls", "Rice", "#00205B", "#C1C6C8"),
        Team("south-florida", "58", "USF", "South Florida Bulls", "South Florida", "#006747", "#CFC493"),
        Team("temple", "218", "TEM", "Temple Owls", "Temple", "#9D2235", "#FFFFFF"),
        Team("tulane", "2655", "TULN", "Tulane Green Wave", "Tulane", "#006747", "#418FDE"),
        Team("tulsa", "202", "TLSA", "Tulsa Golden Hurricane", "Tulsa", "#002D72", "#C5B783"),
        Team("uab", "5", "UAB", "UAB Blazers", "UAB", "#1E6B52", "#F4C300"),
        Team("utsa", "2636", "UTSA", "UTSA Roadrunners", "UTSA", "#0C2340", "#F15A22"),
        Team("wichita-state", "2724", "WICH", "Wichita State Shockers", "Wichita State", "#FFC72C", "#000000"),
    ),
    features=frozenset({"midmaxx60"}),
    path="american/",
    theme="levee",
    odds_aliases={
        "Wichita St Shockers": "wichita-state",
        "FAU Owls": "fau",
        "USF Bulls": "south-florida",
        "UT San Antonio Roadrunners": "utsa",
        "Texas-San Antonio Roadrunners": "utsa",
        "Alabama-Birmingham Blazers": "uab",
    },
    news_names={
        "charlotte": {"query": "Charlotte 49ers basketball", "match": [r"\bCharlotte 49ers\b", r"\bUNC Charlotte\b"]},
        "east-carolina": {"query": "East Carolina Pirates basketball", "match": [r"\bEast Carolina\b", r"\bECU\b"]},
        "fau": {"query": "FAU Owls basketball", "match": [r"\bFAU\b", r"\bFlorida Atlantic\b"]},
        "memphis": {"query": "Memphis Tigers basketball", "match": [r"\bMemphis Tigers\b", r"\bMemphis\b(?! Grizzlies| Grizz)", r"\bPenny Hardaway\b"]},
        "north-texas": {"query": "North Texas Mean Green basketball", "match": [r"\bNorth Texas\b", r"\bMean Green\b", r"\bUNT\b"]},
        "rice": {"query": "Rice Owls basketball", "match": [r"\bRice Owls\b", r"\bRice University\b", r"^Rice\b"]},
        "south-florida": {"query": "South Florida Bulls basketball", "match": [r"\bSouth Florida\b", r"\bUSF Bulls\b"]},
        "temple": {"query": "Temple Owls basketball", "match": [r"\bTemple Owls\b", r"\bTemple University\b", r"^Temple\b"]},
        "tulane": {"query": "Tulane Green Wave basketball", "match": [r"\bTulane\b", r"\bGreen Wave\b"]},
        "tulsa": {"query": "Tulsa Golden Hurricane basketball", "match": [r"\bTulsa\b", r"\bGolden Hurricane\b"]},
        "uab": {"query": "UAB Blazers basketball", "match": [r"\bUAB\b"]},
        "utsa": {"query": "UTSA Roadrunners basketball", "match": [r"\bUTSA\b"]},
        "wichita-state": {"query": "Wichita State Shockers basketball", "match": [r"\bWichita St(ate|\.)?\b", r"\bShockers\b"]},
    },
    league_feed=("theamerican.org", "American (theamerican.org)"),
    hashtag="AmericanMBB",
    tournament="the American tournament",
)

# Sun Belt 2026-27 membership from ESPN's conference feed (group 27). Texas State left for the Pac-12;
# Louisiana Tech is new.
SUNBELT = League(
    key="sunbelt", short="Sun Belt", name="Sun Belt Conference",
    region="the Southeast, from Boone, Harrisonburg and Huntington down the coast to Conway, Statesboro and Mobile, and west through Troy, Hattiesburg and Louisiana to Jonesboro",
    teams=(
        Team("app-state", "2026", "APP", "App State Mountaineers", "App State", "#222222", "#FFCC00"),
        Team("arkansas-state", "2032", "ARST", "Arkansas State Red Wolves", "Arkansas State", "#CC092F", "#000000"),
        Team("coastal-carolina", "324", "CCU", "Coastal Carolina Chanticleers", "Coastal Carolina", "#006F71", "#A27752"),
        Team("georgia-southern", "290", "GASO", "Georgia Southern Eagles", "Georgia Southern", "#011E41", "#87714D"),
        Team("georgia-state", "2247", "GAST", "Georgia State Panthers", "Georgia State", "#0039A6", "#C60C30"),
        Team("james-madison", "256", "JMU", "James Madison Dukes", "James Madison", "#450084", "#CBB677"),
        Team("louisiana", "309", "UL", "Louisiana Ragin' Cajuns", "Louisiana", "#CE181E", "#FFFFFF"),
        Team("louisiana-tech", "2348", "LT", "Louisiana Tech Bulldogs", "Louisiana Tech", "#002F8B", "#E31B23"),
        Team("marshall", "276", "MRSH", "Marshall Thundering Herd", "Marshall", "#00B140", "#000000"),
        Team("old-dominion", "295", "ODU", "Old Dominion Monarchs", "Old Dominion", "#003057", "#7C878E"),
        Team("south-alabama", "6", "USA", "South Alabama Jaguars", "South Alabama", "#00205B", "#BF0D3E"),
        Team("southern-miss", "2572", "USM", "Southern Miss Golden Eagles", "Southern Miss", "#000000", "#FFAB00"),
        Team("troy", "2653", "TROY", "Troy Trojans", "Troy", "#8A2432", "#B3B5B8"),
        Team("ul-monroe", "2433", "ULM", "UL Monroe Warhawks", "UL Monroe", "#840029", "#BA9B37"),
    ),
    features=frozenset({"midmaxx60"}),
    path="sunbelt/",
    theme="liveoak",
    odds_aliases={
        "Appalachian St Mountaineers": "app-state",
        "Appalachian State Mountaineers": "app-state",
        "Arkansas St Red Wolves": "arkansas-state",
        "Georgia St Panthers": "georgia-state",
        "Louisiana Ragin Cajuns": "louisiana",
        "UL Lafayette Ragin' Cajuns": "louisiana",
        "Louisiana-Lafayette Ragin' Cajuns": "louisiana",
        "Louisiana-Monroe Warhawks": "ul-monroe",
        "Southern Mississippi Golden Eagles": "southern-miss",
    },
    news_names={
        "app-state": {"query": "App State Mountaineers basketball", "match": [r"\bApp(alachian)? St(ate|\.)?\b"]},
        "arkansas-state": {"query": "Arkansas State Red Wolves basketball", "match": [r"\bArkansas St(ate|\.)?\b", r"\bRed Wolves\b", r"\bA-State\b"]},
        "coastal-carolina": {"query": "Coastal Carolina Chanticleers basketball", "match": [r"\bCoastal Carolina\b", r"\bChanticleers\b"]},
        "georgia-southern": {"query": "Georgia Southern Eagles basketball", "match": [r"\bGeorgia Southern\b"]},
        "georgia-state": {"query": "Georgia State Panthers basketball", "match": [r"\bGeorgia St(ate|\.)?\b"]},
        "james-madison": {"query": "James Madison Dukes basketball", "match": [r"\bJames Madison\b", r"\bJMU\b"]},
        "louisiana": {"query": "Louisiana Ragin' Cajuns basketball", "match": [r"\bRagin[’']? Cajuns\b", r"\bUL Lafayette\b", r"\bLouisiana-Lafayette\b"]},
        "louisiana-tech": {"query": "Louisiana Tech Bulldogs basketball", "match": [r"\bLouisiana Tech\b", r"\bLa\. Tech\b"]},
        "marshall": {"query": "Marshall Thundering Herd basketball", "match": [r"\bThundering Herd\b", r"\bMarshall University\b", r"^Marshall\b"]},
        "old-dominion": {"query": "Old Dominion Monarchs basketball", "match": [r"\bOld Dominion\b", r"\bODU\b"]},
        "south-alabama": {"query": "South Alabama Jaguars basketball", "match": [r"\bSouth Alabama\b"]},
        "southern-miss": {"query": "Southern Miss Golden Eagles basketball", "match": [r"\bSouthern Miss(issippi)?\b"]},
        "troy": {"query": "Troy Trojans basketball", "match": [r"\bTroy Trojans\b", r"\bTroy University\b", r"^Troy\b"]},
        "ul-monroe": {"query": "UL Monroe Warhawks basketball", "match": [r"\bUL Monroe\b", r"\bULM\b", r"\bLouisiana-Monroe\b", r"\bWarhawks\b"]},
    },
    league_feed=("sunbeltsports.org", "Sun Belt (sunbeltsports.org)"),
    hashtag="SunBeltMBB",
    tournament="the Sun Belt tournament",
)


# Ivy League 2026-27 membership from ESPN's conference feed (group 12).
IVY = League(
    key="ivy", short="Ivy", name="Ivy League",
    region="the Northeast, from Hanover and Ithaca down through Providence, Cambridge and New Haven to New York, Princeton and Philadelphia",
    teams=(
        Team("brown", "225", "BRWN", "Brown Bears", "Brown", "#4E3629", "#C00404"),
        Team("columbia", "171", "COLU", "Columbia Lions", "Columbia", "#1D4F91", "#B9D9EB"),
        Team("cornell", "172", "COR", "Cornell Big Red", "Cornell", "#B31B1B", "#FFFFFF"),
        Team("dartmouth", "159", "DART", "Dartmouth Big Green", "Dartmouth", "#00693E", "#FFFFFF"),
        Team("harvard", "108", "HARV", "Harvard Crimson", "Harvard", "#A51C30", "#1E1E1E"),
        Team("penn", "219", "PENN", "Pennsylvania Quakers", "Penn", "#011F5B", "#990000"),
        Team("princeton", "163", "PRIN", "Princeton Tigers", "Princeton", "#E77500", "#000000"),
        Team("yale", "43", "YALE", "Yale Bulldogs", "Yale", "#00356B", "#FFFFFF"),
    ),
    features=frozenset({"midmaxx60"}),
    path="ivy/",
    theme="quad",
    odds_aliases={"Penn Quakers": "penn"},
    news_names={
        "brown": {"query": "Brown Bears basketball", "match": [r"\bBrown Bears\b", r"\bBrown University\b"]},
        "columbia": {"query": "Columbia Lions basketball", "match": [r"\bColumbia Lions\b", r"\bColumbia University\b"]},
        "cornell": {"query": "Cornell Big Red basketball", "match": [r"\bCornell\b", r"\bBig Red\b"]},
        "dartmouth": {"query": "Dartmouth Big Green basketball", "match": [r"\bDartmouth\b", r"\bBig Green\b"]},
        "harvard": {"query": "Harvard Crimson basketball", "match": [r"\bHarvard\b"]},
        "penn": {"query": "Penn Quakers basketball", "match": [r"\bPenn Quakers\b", r"\bQuakers\b", r"^Penn\b(?! State| St\.?\b)"]},
        "princeton": {"query": "Princeton Tigers basketball", "match": [r"\bPrinceton\b"]},
        "yale": {"query": "Yale Bulldogs basketball", "match": [r"\bYale\b"]},
    },
    league_feed=("ivyleague.com", "Ivy League (ivyleague.com)"),
    hashtag="IvyMBB",
    tournament="Ivy Madness, the four-team Ivy League tournament",
)

# Coastal Athletic Association 2026-27 membership from ESPN's conference feed (group 10).
CAA = League(
    key="caa", short="CAA", name="Coastal Athletic Association",
    region="the East Coast, from Boston and Long Island down through Philadelphia, Towson and Williamsburg to the Carolinas and Charleston",
    teams=(
        Team("campbell", "2097", "CAM", "Campbell Fighting Camels", "Campbell", "#F58025", "#000000"),
        Team("charleston", "232", "COFC", "Charleston Cougars", "Charleston", "#800000", "#CBAE68"),
        Team("drexel", "2182", "DREX", "Drexel Dragons", "Drexel", "#07294D", "#FFC600"),
        Team("elon", "2210", "ELON", "Elon Phoenix", "Elon", "#73000A", "#B59A57"),
        Team("hampton", "2261", "HAMP", "Hampton Pirates", "Hampton", "#0067AC", "#FFFFFF"),
        Team("hofstra", "2275", "HOF", "Hofstra Pride", "Hofstra", "#00337D", "#FFC72C"),
        Team("monmouth", "2405", "MONM", "Monmouth Hawks", "Monmouth", "#041E42", "#FFFFFF"),
        Team("nc-at", "2448", "NCAT", "North Carolina A&T Aggies", "NC A&T", "#004684", "#FDB927"),
        Team("northeastern", "111", "NE", "Northeastern Huskies", "Northeastern", "#C8102E", "#000000"),
        Team("stony-brook", "2619", "STBK", "Stony Brook Seawolves", "Stony Brook", "#990000", "#16243E"),
        Team("towson", "119", "TOW", "Towson Tigers", "Towson", "#000000", "#FFBB00"),
        Team("uncw", "350", "UNCW", "UNC Wilmington Seahawks", "UNC Wilmington", "#006666", "#FFD400"),
        Team("william-mary", "2729", "W&M", "William & Mary Tribe", "William & Mary", "#115740", "#B9975B"),
    ),
    features=frozenset({"midmaxx60"}),
    path="caa/",
    theme="harbor",
    odds_aliases={
        "College of Charleston Cougars": "charleston",
        "NC A&T Aggies": "nc-at",
        "N Carolina A&T Aggies": "nc-at",
        "UNCW Seahawks": "uncw",
        "William and Mary Tribe": "william-mary",
    },
    news_names={
        "campbell": {"query": "Campbell Fighting Camels basketball", "match": [r"\bFighting Camels\b", r"\bCampbell University\b"]},
        "charleston": {"query": "Charleston Cougars basketball", "match": [r"\bCharleston Cougars\b", r"\bCollege of Charleston\b", r"\bCofC\b"]},
        "drexel": {"query": "Drexel Dragons basketball", "match": [r"\bDrexel\b"]},
        "elon": {"query": "Elon Phoenix basketball", "match": [r"\bElon Phoenix\b", r"\bElon University\b"]},
        "hampton": {"query": "Hampton Pirates basketball", "match": [r"\bHampton Pirates\b", r"\bHampton University\b"]},
        "hofstra": {"query": "Hofstra Pride basketball", "match": [r"\bHofstra\b"]},
        "monmouth": {"query": "Monmouth Hawks basketball", "match": [r"\bMonmouth Hawks\b", r"\bMonmouth University\b"]},
        "nc-at": {"query": "North Carolina A&T Aggies basketball", "match": [r"\bN\.?C\.? A&T\b", r"\bNorth Carolina A&T\b"]},
        "northeastern": {"query": "Northeastern Huskies basketball", "match": [r"\bNortheastern\b(?! Illinois| State)"]},
        "stony-brook": {"query": "Stony Brook Seawolves basketball", "match": [r"\bStony Brook\b", r"\bSeawolves\b"]},
        "towson": {"query": "Towson Tigers basketball", "match": [r"\bTowson\b"]},
        "uncw": {"query": "UNC Wilmington Seahawks basketball", "match": [r"\bUNCW\b", r"\bUNC Wilmington\b"]},
        "william-mary": {"query": "William & Mary Tribe basketball", "match": [r"\bWilliam (&|and) Mary\b", r"\bW&M\b"]},
    },
    league_feed=("caasports.com", "CAA (caasports.com)"),
    hashtag="CAAHoops",
    tournament="the CAA tournament",
)

# Conference USA 2026-27 membership from ESPN's conference feed (group 11).
CUSA = League(
    key="cusa", short="CUSA", name="Conference USA",
    region="a long stretch of the South and beyond, from Newark, Delaware and Lynchburg down to Miami, west through Kennesaw, Murfreesboro and Bowling Green to Springfield, Huntsville and Las Cruces",
    teams=(
        Team("delaware", "48", "DEL", "Delaware Blue Hens", "Delaware", "#00539F", "#FFD200"),
        Team("fiu", "2229", "FIU", "FIU Panthers", "FIU", "#081E3F", "#B6862C"),
        Team("jacksonville-state", "55", "JVST", "Jacksonville State Gamecocks", "Jacksonville State", "#CC0000", "#FFFFFF"),
        Team("kennesaw-state", "338", "KENN", "Kennesaw State Owls", "Kennesaw State", "#FDBB30", "#0B1315"),
        Team("liberty", "2335", "LIB", "Liberty Flames", "Liberty", "#002D62", "#C41230"),
        Team("middle-tennessee", "2393", "MTSU", "Middle Tennessee Blue Raiders", "Middle Tennessee", "#0066CC", "#FFFFFF"),
        Team("missouri-state", "2623", "MOST", "Missouri State Bears", "Missouri State", "#5E0009", "#FFFFFF"),
        Team("new-mexico-state", "166", "NMSU", "New Mexico State Aggies", "New Mexico State", "#8C0B42", "#FFFFFF"),
        Team("sam-houston", "2534", "SHSU", "Sam Houston Bearkats", "Sam Houston", "#F76800", "#FFFFFF"),
        Team("western-kentucky", "98", "WKU", "Western Kentucky Hilltoppers", "Western Kentucky", "#C60C30", "#FFFFFF"),
    ),
    features=frozenset({"midmaxx60"}),
    path="cusa/",
    theme="watertower",
    odds_aliases={
        "Florida International Panthers": "fiu",
        "Florida Int'l Golden Panthers": "fiu",
        "Jacksonville St Gamecocks": "jacksonville-state",
        "Kennesaw St Owls": "kennesaw-state",
        "Middle Tennessee St Blue Raiders": "middle-tennessee",
        "Missouri St Bears": "missouri-state",
        "New Mexico St Aggies": "new-mexico-state",
        "Sam Houston St Bearkats": "sam-houston",
        "Sam Houston State Bearkats": "sam-houston",
        "Western Kentucky Hilltoppers": "western-kentucky",
    },
    news_names={
        "delaware": {"query": "Delaware Blue Hens basketball", "match": [r"\bBlue Hens\b", r"\bUniversity of Delaware\b"]},
        "fiu": {"query": "FIU Panthers basketball", "match": [r"\bFIU\b", r"\bFlorida International\b"]},
        "jacksonville-state": {"query": "Jacksonville State Gamecocks basketball", "match": [r"\bJacksonville State\b", r"\bJax State\b"]},
        "kennesaw-state": {"query": "Kennesaw State Owls basketball", "match": [r"\bKennesaw State\b"]},
        "liberty": {"query": "Liberty Flames basketball", "match": [r"\bLiberty Flames\b", r"\bLiberty University\b"]},
        "middle-tennessee": {"query": "Middle Tennessee Blue Raiders basketball", "match": [r"\bMiddle Tennessee\b", r"\bMTSU\b", r"\bBlue Raiders\b"]},
        "missouri-state": {"query": "Missouri State Bears basketball", "match": [r"\bMissouri State\b"]},
        "new-mexico-state": {"query": "New Mexico State Aggies basketball", "match": [r"\bNew Mexico State\b", r"\bNMSU\b"]},
        "sam-houston": {"query": "Sam Houston Bearkats basketball", "match": [r"\bSam Houston\b(?! Rockets)", r"\bBearkats\b"]},
        "western-kentucky": {"query": "Western Kentucky Hilltoppers basketball", "match": [r"\bWestern Kentucky\b", r"\bWKU\b", r"\bHilltoppers\b"]},
    },
    league_feed=("conferenceusa.com", "Conference USA (conferenceusa.com)"),
    hashtag="CUSAMBB",
    tournament="the Conference USA tournament",
)

# Southern Conference 2026-27 membership from ESPN's conference feed (group 24).
SOCON = League(
    key="socon", short="SoCon", name="Southern Conference",
    region="the Southern Appalachians and the Piedmont, from Lexington, Virginia and Greensboro through Johnson City, Cullowhee and Cookeville to Chattanooga, Spartanburg, Greenville, Charleston, Macon and Birmingham",
    teams=(
        Team("chattanooga", "236", "UTC", "Chattanooga Mocs", "Chattanooga", "#00386B", "#E0AA0F"),
        Team("etsu", "2193", "ETSU", "East Tennessee State Buccaneers", "ETSU", "#041E42", "#FFC72C"),
        Team("furman", "231", "FUR", "Furman Paladins", "Furman", "#582C83", "#FFFFFF"),
        Team("mercer", "2382", "MER", "Mercer Bears", "Mercer", "#F76800", "#000000"),
        Team("samford", "2535", "SAM", "Samford Bulldogs", "Samford", "#002D72", "#C8102E"),
        Team("tennessee-tech", "2635", "TNTC", "Tennessee Tech Golden Eagles", "Tennessee Tech", "#4F2984", "#FFDD00"),
        Team("the-citadel", "2643", "CIT", "The Citadel Bulldogs", "The Citadel", "#3975B7", "#FFFFFF"),
        Team("unc-greensboro", "2430", "UNCG", "UNC Greensboro Spartans", "UNC Greensboro", "#0F2044", "#FFB71B"),
        Team("vmi", "2678", "VMI", "VMI Keydets", "VMI", "#AE122A", "#FFD619"),
        Team("western-carolina", "2717", "WCU", "Western Carolina Catamounts", "Western Carolina", "#592C88", "#C1A875"),
        Team("wofford", "2747", "WOF", "Wofford Terriers", "Wofford", "#886E4C", "#000000"),
    ),
    features=frozenset({"midmaxx60"}),
    path="socon/",
    theme="blueridge",
    odds_aliases={
        "UT Chattanooga Mocs": "chattanooga",
        "Tenn-Chattanooga Mocs": "chattanooga",
        "East Tennessee St Buccaneers": "etsu",
        "ETSU Buccaneers": "etsu",
        "Tennessee Tech Golden Eagles": "tennessee-tech",
        "Citadel Bulldogs": "the-citadel",
        "UNCG Spartans": "unc-greensboro",
        "UNC Greensboro Spartans": "unc-greensboro",
    },
    news_names={
        "chattanooga": {"query": "Chattanooga Mocs basketball", "match": [r"\bChattanooga Mocs\b", r"\bMocs\b", r"\bUTC\b"]},
        "etsu": {"query": "ETSU Buccaneers basketball", "match": [r"\bETSU\b", r"\bEast Tennessee State\b"]},
        "furman": {"query": "Furman Paladins basketball", "match": [r"\bFurman\b"]},
        "mercer": {"query": "Mercer Bears basketball", "match": [r"\bMercer Bears\b", r"\bMercer University\b"]},
        "samford": {"query": "Samford Bulldogs basketball", "match": [r"\bSamford\b"]},
        "tennessee-tech": {"query": "Tennessee Tech Golden Eagles basketball", "match": [r"\bTennessee Tech\b"]},
        "the-citadel": {"query": "The Citadel Bulldogs basketball", "match": [r"\bThe Citadel\b"]},
        "unc-greensboro": {"query": "UNC Greensboro Spartans basketball", "match": [r"\bUNCG\b", r"\bUNC Greensboro\b"]},
        "vmi": {"query": "VMI Keydets basketball", "match": [r"\bVMI\b", r"\bKeydets\b"]},
        "western-carolina": {"query": "Western Carolina Catamounts basketball", "match": [r"\bWestern Carolina\b", r"\bCatamounts\b"]},
        "wofford": {"query": "Wofford Terriers basketball", "match": [r"\bWofford\b"]},
    },
    league_feed=("soconsports.com", "SoCon (soconsports.com)"),
    hashtag="SoConMBB",
    tournament="the SoCon tournament in Asheville",
)


# Big Sky 2026-27 membership from ESPN's conference feed (group 5).
BIGSKY = League(
    key="bigsky", short="Big Sky", name="Big Sky Conference",
    region="the Mountain West and the Pacific Northwest, from Cheney, Moscow and Portland through Missoula, Bozeman and Pocatello to Ogden, Cedar City, St. George, Flagstaff and Greeley",
    teams=(
        Team("eastern-washington", "331", "EWU", "Eastern Washington Eagles", "Eastern Washington", "#A10022", "#FFFFFF"),
        Team("idaho", "70", "IDHO", "Idaho Vandals", "Idaho", "#B3A369", "#000000"),
        Team("idaho-state", "304", "IDST", "Idaho State Bengals", "Idaho State", "#F47920", "#000000"),
        Team("montana", "149", "MONT", "Montana Grizzlies", "Montana", "#70263A", "#A7A9AC"),
        Team("montana-state", "147", "MTST", "Montana State Bobcats", "Montana State", "#002A5C", "#B9975B"),
        Team("northern-arizona", "2464", "NAU", "Northern Arizona Lumberjacks", "Northern Arizona", "#003466", "#FFD200"),
        Team("northern-colorado", "2458", "UNCO", "Northern Colorado Bears", "Northern Colorado", "#013C65", "#F6B000"),
        Team("portland-state", "2502", "PRST", "Portland State Vikings", "Portland State", "#154734", "#FFFFFF"),
        Team("southern-utah", "253", "SUU", "Southern Utah Thunderbirds", "Southern Utah", "#C8102E", "#FFFFFF"),
        Team("utah-tech", "3101", "UTU", "Utah Tech Trailblazers", "Utah Tech", "#003058", "#BA1C21"),
        Team("weber-state", "2692", "WEB", "Weber State Wildcats", "Weber State", "#492365", "#FFFFFF"),
    ),
    features=frozenset({"midmaxx60"}),
    path="bigsky/",
    theme="peaks",
    odds_aliases={
        "Montana St Bobcats": "montana-state",
        "N Colorado Bears": "northern-colorado",
        "Portland St Vikings": "portland-state",
        "Idaho St Bengals": "idaho-state",
        "Weber St Wildcats": "weber-state",
    },
    news_names={
        "eastern-washington": {"query": "Eastern Washington Eagles basketball", "match": [r'\bEastern Washington\b', r'\bEWU\b']},
        "idaho-state": {"query": "Idaho State Bengals basketball", "match": [r'\bIdaho State\b']},
        "idaho": {"query": "Idaho Vandals basketball", "match": [r'\bIdaho Vandals\b', r'\bVandals\b']},
        "montana": {"query": "Montana Grizzlies basketball", "match": [r'\bMontana Grizzlies\b', r'\bGriz\b']},
        "montana-state": {"query": "Montana State Bobcats basketball", "match": [r'\bMontana State\b']},
        "northern-arizona": {"query": "Northern Arizona Lumberjacks basketball", "match": [r'\bNorthern Arizona\b', r'\bNAU\b']},
        "northern-colorado": {"query": "Northern Colorado Bears basketball", "match": [r'\bNorthern Colorado\b', r'\bUNC Bears\b']},
        "portland-state": {"query": "Portland State Vikings basketball", "match": [r'\bPortland State\b']},
        "southern-utah": {"query": "Southern Utah Thunderbirds basketball", "match": [r'\bSouthern Utah\b', r'\bSUU\b']},
        "utah-tech": {"query": "Utah Tech Trailblazers basketball", "match": [r'\bUtah Tech\b']},
        "weber-state": {"query": "Weber State Wildcats basketball", "match": [r'\bWeber State\b']},
    },
    league_feed=("bigskyconf.com", "Big Sky (bigskyconf.com)"),
    hashtag="BigSkyMBB",
    tournament="the Big Sky tournament",
)

# Southland 2026-27 membership from ESPN's conference feed (group 25).
SOUTHLAND = League(
    key="southland", short="Southland", name="Southland Conference",
    region="the Gulf South, from Natchitoches, Hammond, Thibodaux, Lake Charles and New Orleans across East Texas to Houston, San Antonio, Corpus Christi and the Rio Grande Valley",
    teams=(
        Team("east-texas-am", "2837", "ETAM", "East Texas A&M Lions", "East Texas A&M", "#00386C", "#FFC333"),
        Team("houston-christian", "2277", "HCU", "Houston Christian Huskies", "Houston Christian", "#00269A", "#F58025"),
        Team("incarnate-word", "2916", "UIW", "Incarnate Word Cardinals", "Incarnate Word", "#CB2C30", "#000000"),
        Team("lamar", "2320", "LAM", "Lamar Cardinals", "Lamar", "#C8102E", "#FFFFFF"),
        Team("mcneese", "2377", "MCN", "McNeese Cowboys", "McNeese", "#00529B", "#FFD204"),
        Team("new-orleans", "2443", "UNO", "New Orleans Privateers", "New Orleans", "#003DA5", "#A2AAAD"),
        Team("nicholls", "2447", "NICH", "Nicholls Colonels", "Nicholls", "#C41230", "#9EA2A2"),
        Team("northwestern-state", "2466", "NWST", "Northwestern State Demons", "Northwestern State", "#492F92", "#F58025"),
        Team("southeastern-louisiana", "2545", "SELA", "Southeastern Louisiana Lions", "SE Louisiana", "#006341", "#EEB111"),
        Team("stephen-f-austin", "2617", "SFA", "Stephen F. Austin Lumberjacks", "Stephen F. Austin", "#3F2A56", "#FFFFFF"),
        Team("texas-am-cc", "357", "AMCC", "Texas A&M-Corpus Christi Islanders", "Texas A&M-CC", "#0067C5", "#007F3E"),
        Team("utrgv", "292", "RGV", "UT Rio Grande Valley Vaqueros", "UTRGV", "#F05023", "#005893"),
    ),
    features=frozenset({"midmaxx60"}),
    path="southland/",
    theme="bayou",
    odds_aliases={
        "Nicholls St Colonels": "nicholls",
        "Northwestern St Demons": "northwestern-state",
        "SE Louisiana Lions": "southeastern-louisiana",
        "Texas A&M-CC Islanders": "texas-am-cc",
        "McNeese St Cowboys": "mcneese",
        "McNeese Cowboys": "mcneese",
        "New Orleans Privateers": "new-orleans",
        "UTRGV Vaqueros": "utrgv",
        "Lamar Cardinals": "lamar",
    },
    news_names={
        "east-texas-am": {"query": "East Texas A&M Lions basketball", "match": [r'\bEast Texas A&M\b']},
        "houston-christian": {"query": "Houston Christian Huskies basketball", "match": [r'\bHouston Christian\b']},
        "incarnate-word": {"query": "Incarnate Word Cardinals basketball", "match": [r'\bIncarnate Word\b', r'\bUIW\b']},
        "new-orleans": {"query": "New Orleans Privateers basketball", "match": [r'\bNew Orleans Privateers\b', r'\bUNO\b', r'\bPrivateers\b']},
        "lamar": {"query": "Lamar Cardinals basketball", "match": [r'\bLamar Cardinals\b', r'\bLamar University\b']},
        "mcneese": {"query": "McNeese Cowboys basketball", "match": [r'\bMcNeese\b']},
        "nicholls": {"query": "Nicholls Colonels basketball", "match": [r'\bNicholls\b']},
        "northwestern-state": {"query": "Northwestern State Demons basketball", "match": [r'\bNorthwestern State\b']},
        "southeastern-louisiana": {"query": "Southeastern Louisiana Lions basketball", "match": [r'\bSoutheastern Louisiana\b', r'\bSE Louisiana\b']},
        "stephen-f-austin": {"query": "Stephen F. Austin Lumberjacks basketball", "match": [r'\bStephen F\.? Austin\b', r'\bSFA\b']},
        "texas-am-cc": {"query": "Texas A&M-Corpus Christi Islanders basketball", "match": [r'\bCorpus Christi\b', r'\bTAMUCC\b']},
        "utrgv": {"query": "UTRGV Vaqueros basketball", "match": [r'\bUTRGV\b', r'\bRio Grande Valley\b']},
    },
    league_feed=("southland.org", "Southland (southland.org)"),
    hashtag="SouthlandMBB",
    tournament="the Southland tournament",
)


# Summit League 2026-27 membership from ESPN's conference feed (group 49).
SUMMIT = League(
    key="summit", short="Summit", name="Summit League",
    region="the Upper Midwest and the Plains, from Grand Forks, Fargo and St. Paul down through Vermillion, Brookings and Omaha to Kansas City and Tulsa",
    teams=(
        Team("kansas-city", "140", "KC", "Kansas City Roos", "Kansas City", "#0067B1", "#FFC82E"),
        Team("north-dakota", "155", "UND", "North Dakota Fighting Hawks", "North Dakota", "#009A44", "#000000"),
        Team("north-dakota-state", "2449", "NDSU", "North Dakota State Bison", "North Dakota State", "#0A5640", "#FFC82E"),
        Team("omaha", "2437", "OMA", "Omaha Mavericks", "Omaha", "#D71920", "#000000"),
        Team("oral-roberts", "198", "ORU", "Oral Roberts Golden Eagles", "Oral Roberts", "#002855", "#C5B783"),
        Team("south-dakota", "233", "SDAK", "South Dakota Coyotes", "South Dakota", "#AD0000", "#FFFFFF"),
        Team("south-dakota-state", "2571", "SDST", "South Dakota State Jackrabbits", "South Dakota State", "#0033A0", "#FFD100"),
        Team("st-thomas", "2900", "STMN", "St. Thomas Tommies", "St. Thomas", "#510C76", "#FFFFFF"),
    ),
    features=frozenset({"midmaxx60"}),
    path="summit/",
    theme="prairie",
    odds_aliases={
        "UMKC Kangaroos": "kansas-city",
        "North Dakota St Bison": "north-dakota-state",
        "South Dakota St Jackrabbits": "south-dakota-state",
        "St. Thomas (MN) Tommies": "st-thomas",
    },
    news_names={
        "kansas-city": {"query": "Kansas City Roos basketball", "match": [r"\bKansas City Roos\b", r"\bUMKC\b"]},
        "north-dakota": {"query": "North Dakota Fighting Hawks basketball", "match": [r"\bNorth Dakota\b(?! State)", r"\bFighting Hawks\b"]},
        "north-dakota-state": {"query": "North Dakota State Bison basketball", "match": [r"\bNorth Dakota State\b", r"\bNDSU\b"]},
        "omaha": {"query": "Omaha Mavericks basketball", "match": [r"\bOmaha Mavericks\b", r"\bUNO Mavericks\b"]},
        "oral-roberts": {"query": "Oral Roberts Golden Eagles basketball", "match": [r"\bOral Roberts\b", r"\bORU\b"]},
        "south-dakota": {"query": "South Dakota Coyotes basketball", "match": [r"\bSouth Dakota\b(?! State)", r"\bUSD Coyotes\b"]},
        "south-dakota-state": {"query": "South Dakota State Jackrabbits basketball", "match": [r"\bSouth Dakota State\b", r"\bJackrabbits\b"]},
        "st-thomas": {"query": "St. Thomas Tommies basketball", "match": [r"\bSt\.? Thomas\b", r"\bTommies\b"]},
    },
    league_feed=("thesummitleague.org", "Summit League (thesummitleague.org)"),
    hashtag="SummitMBB",
    tournament="the Summit League tournament",
)

# United Athletic Conference 2026-27 membership from ESPN's conference feed (group 30).
UAC = League(
    key="uac", short="UAC", name="United Athletic Conference",
    region="the South and Texas, from Richmond, Kentucky and Clarksville down through Florence, Carrollton, Conway and Little Rock to Arlington, Stephenville and Abilene",
    teams=(
        Team("abilene-christian", "2000", "ACU", "Abilene Christian Wildcats", "Abilene Christian", "#4F2683", "#FFFFFF"),
        Team("austin-peay", "2046", "APSU", "Austin Peay Governors", "Austin Peay", "#C41E3A", "#FFFFFF"),
        Team("central-arkansas", "2110", "UCA", "Central Arkansas Bears", "Central Arkansas", "#4F2D7F", "#818A8F"),
        Team("eastern-kentucky", "2198", "EKU", "Eastern Kentucky Colonels", "Eastern Kentucky", "#861F41", "#FFFFFF"),
        Team("little-rock", "2031", "UALR", "Little Rock Trojans", "Little Rock", "#6F263D", "#A2AAAD"),
        Team("north-alabama", "2453", "UNA", "North Alabama Lions", "North Alabama", "#46166B", "#DB9F11"),
        Team("tarleton-state", "2627", "TAR", "Tarleton State Texans", "Tarleton State", "#4F2D7F", "#FFFFFF"),
        Team("ut-arlington", "250", "UTA", "UT Arlington Mavericks", "UT Arlington", "#0064B1", "#F58025"),
        Team("west-georgia", "2698", "UWG", "West Georgia Wolves", "West Georgia", "#0656A5", "#E31B23"),
    ),
    features=frozenset({"midmaxx60"}),
    path="uac/",
    theme="silo",
    odds_aliases={
        "UT-Arlington Mavericks": "ut-arlington",
        "Arkansas-Little Rock Trojans": "little-rock",
        "Little Rock Trojans": "little-rock",
        "Central Arkansas Bears": "central-arkansas",
    },
    news_names={
        "abilene-christian": {"query": "Abilene Christian Wildcats basketball", "match": [r"\bAbilene Christian\b"]},
        "austin-peay": {"query": "Austin Peay Governors basketball", "match": [r"\bAustin Peay\b"]},
        "central-arkansas": {"query": "Central Arkansas Bears basketball", "match": [r"\bCentral Arkansas\b"]},
        "eastern-kentucky": {"query": "Eastern Kentucky Colonels basketball", "match": [r"\bEastern Kentucky\b", r"\bEKU\b"]},
        "little-rock": {"query": "Little Rock Trojans basketball", "match": [r"\bLittle Rock Trojans\b", r"\bUALR\b"]},
        "north-alabama": {"query": "North Alabama Lions basketball", "match": [r"\bNorth Alabama\b"]},
        "tarleton-state": {"query": "Tarleton State Texans basketball", "match": [r"\bTarleton\b"]},
        "ut-arlington": {"query": "UT Arlington Mavericks basketball", "match": [r"\bUT Arlington\b", r"\bUTA\b"]},
        "west-georgia": {"query": "West Georgia Wolves basketball", "match": [r"\bWest Georgia\b"]},
    },
    league_feed=("uacsports.com", "UAC (uacsports.com)"),
    hashtag="UACMBB",
    tournament="the UAC tournament",
)


# Big South 2026-27 membership from ESPN's conference feed (group 6).
BIGSOUTH = League(
    key="bigsouth", short="Big South", name="Big South Conference",
    region="the Carolinas and Virginia, from Farmville and Radford down through High Point, Boiling Springs and Asheville to Rock Hill, Spartanburg, Clinton and Charleston",
    teams=(
        Team("charleston-southern", "2127", "CHSO", "Charleston Southern Buccaneers", "Charleston Southern", "#002855", "#A89968"),
        Team("gardner-webb", "2241", "GWEB", "Gardner-Webb Runnin' Bulldogs", "Gardner-Webb", "#BF2E1A", "#000000"),
        Team("high-point", "2272", "HPU", "High Point Panthers", "High Point", "#330072", "#FFFFFF"),
        Team("longwood", "2344", "LONG", "Longwood Lancers", "Longwood", "#002B5C", "#9EA2A2"),
        Team("presbyterian", "2506", "PRE", "Presbyterian Blue Hose", "Presbyterian", "#0060A9", "#9D2235"),
        Team("radford", "2515", "RAD", "Radford Highlanders", "Radford", "#C2011B", "#FFFFFF"),
        Team("usc-upstate", "2908", "UPST", "South Carolina Upstate Spartans", "USC Upstate", "#00703C", "#000000"),
        Team("unc-asheville", "2427", "UNCA", "UNC Asheville Bulldogs", "UNC Asheville", "#003DA5", "#FFFFFF"),
        Team("winthrop", "2737", "WIN", "Winthrop Eagles", "Winthrop", "#872434", "#FFC72C"),
    ),
    features=frozenset({"midmaxx60"}),
    path="bigsouth/",
    theme="porch",
    odds_aliases={
        "Gardner-Webb Bulldogs": "gardner-webb",
        "SC Upstate Spartans": "usc-upstate",
        "USC Upstate Spartans": "usc-upstate",
    },
    news_names={
        "charleston-southern": {"query": "Charleston Southern Buccaneers basketball", "match": [r"\bCharleston Southern\b"]},
        "gardner-webb": {"query": "Gardner-Webb Runnin' Bulldogs basketball", "match": [r"\bGardner-Webb\b"]},
        "high-point": {"query": "High Point Panthers basketball", "match": [r"\bHigh Point\b"]},
        "longwood": {"query": "Longwood Lancers basketball", "match": [r"\bLongwood\b"]},
        "presbyterian": {"query": "Presbyterian Blue Hose basketball", "match": [r"\bPresbyterian\b", r"\bBlue Hose\b"]},
        "radford": {"query": "Radford Highlanders basketball", "match": [r"\bRadford\b"]},
        "usc-upstate": {"query": "South Carolina Upstate Spartans basketball", "match": [r"\bUSC Upstate\b", r"\bSouth Carolina Upstate\b"]},
        "unc-asheville": {"query": "UNC Asheville Bulldogs basketball", "match": [r"\bUNC Asheville\b", r"\bUNCA\b"]},
        "winthrop": {"query": "Winthrop Eagles basketball", "match": [r"\bWinthrop\b"]},
    },
    league_feed=("bigsouthsports.com", "Big South (bigsouthsports.com)"),
    hashtag="BigSouthMBB",
    tournament="the Big South tournament",
)

# Ohio Valley Conference 2026-27 membership from ESPN's conference feed (group 20).
OVC = League(
    key="ovc", short="OVC", name="Ohio Valley Conference",
    region="the river country of the Midwest and the mid-South, from Macomb, Charleston and Edwardsville down through St. Charles, Evansville and Morehead to Cape Girardeau, Martin and Nashville",
    teams=(
        Team("eastern-illinois", "2197", "EIU", "Eastern Illinois Panthers", "Eastern Illinois", "#004B83", "#999999"),
        Team("lindenwood", "2815", "LIN", "Lindenwood Lions", "Lindenwood", "#000000", "#B5A36A"),
        Team("morehead-state", "2413", "MORE", "Morehead State Eagles", "Morehead State", "#005EB8", "#FFC82E"),
        Team("siue", "2565", "SIUE", "SIU Edwardsville Cougars", "SIUE", "#E21836", "#000000"),
        Team("southeast-missouri", "2546", "SEMO", "Southeast Missouri State Redhawks", "SEMO", "#C8102E", "#000000"),
        Team("southern-indiana", "88", "USI", "Southern Indiana Screaming Eagles", "Southern Indiana", "#002D72", "#C8102E"),
        Team("tennessee-state", "2634", "TNST", "Tennessee State Tigers", "Tennessee State", "#00539F", "#FFFFFF"),
        Team("ut-martin", "2630", "UTM", "UT Martin Skyhawks", "UT Martin", "#0E1C59", "#F79728"),
        Team("western-illinois", "2710", "WIU", "Western Illinois Leathernecks", "Western Illinois", "#663399", "#FFCC00"),
    ),
    features=frozenset({"midmaxx60"}),
    path="ovc/",
    theme="riverboat",
    odds_aliases={
        "Morehead St Eagles": "morehead-state",
        "SIU-Edwardsville Cougars": "siue",
        "SE Missouri St Redhawks": "southeast-missouri",
        "Southeast Missouri St Redhawks": "southeast-missouri",
        "Tennessee St Tigers": "tennessee-state",
        "Tenn-Martin Skyhawks": "ut-martin",
    },
    news_names={
        "eastern-illinois": {"query": "Eastern Illinois Panthers basketball", "match": [r"\bEastern Illinois\b"]},
        "lindenwood": {"query": "Lindenwood Lions basketball", "match": [r"\bLindenwood\b"]},
        "morehead-state": {"query": "Morehead State Eagles basketball", "match": [r"\bMorehead State\b"]},
        "siue": {"query": "SIU Edwardsville Cougars basketball", "match": [r"\bSIUE\b", r"\bSIU Edwardsville\b"]},
        "southeast-missouri": {"query": "Southeast Missouri State Redhawks basketball", "match": [r"\bSoutheast Missouri\b", r"\bSEMO\b"]},
        "southern-indiana": {"query": "Southern Indiana Screaming Eagles basketball", "match": [r"\bSouthern Indiana\b"]},
        "tennessee-state": {"query": "Tennessee State Tigers basketball", "match": [r"\bTennessee State\b"]},
        "ut-martin": {"query": "UT Martin Skyhawks basketball", "match": [r"\bUT Martin\b", r"\bSkyhawks\b"]},
        "western-illinois": {"query": "Western Illinois Leathernecks basketball", "match": [r"\bWestern Illinois\b"]},
    },
    league_feed=("ovcsports.com", "OVC (ovcsports.com)"),
    hashtag="OVCMBB",
    tournament="the OVC tournament",
)


# America East 2026-27 membership from ESPN's conference feed (group 1).
AMEAST = League(
    key="americaeast", short="America East", name="America East Conference",
    region="New England and the Northeast, from Orono, Burlington and Durham down through Lowell, Smithfield and Albany to Binghamton, Newark and Baltimore",
    teams=(
        Team("binghamton", "2066", "BING", "Binghamton Bearcats", "Binghamton", "#005A43", "#FFFFFF"),
        Team("bryant", "2803", "BRY", "Bryant Bulldogs", "Bryant", "#000000", "#B8A16E"),
        Team("maine", "311", "ME", "Maine Black Bears", "Maine", "#003263", "#B0D7FF"),
        Team("njit", "2885", "NJIT", "NJIT Highlanders", "NJIT", "#D22630", "#071D49"),
        Team("new-hampshire", "160", "UNH", "New Hampshire Wildcats", "New Hampshire", "#003591", "#FFFFFF"),
        Team("ualbany", "399", "ALB", "UAlbany Great Danes", "UAlbany", "#46166B", "#EEB211"),
        Team("umbc", "2378", "UMBC", "UMBC Retrievers", "UMBC", "#000000", "#FDB515"),
        Team("umass-lowell", "2349", "UML", "UMass Lowell River Hawks", "UMass Lowell", "#0067B1", "#C8102E"),
        Team("vermont", "261", "UVM", "Vermont Catamounts", "Vermont", "#154734", "#FFD100"),
    ),
    features=frozenset({"midmaxx60"}),
    path="americaeast/",
    theme="covered",
    odds_aliases={
        "Albany Great Danes": "ualbany",
    },
    news_names={
        "binghamton": {"query": "Binghamton Bearcats basketball", "match": [r"\bBinghamton\b"]},
        "bryant": {"query": "Bryant Bulldogs basketball", "match": [r"\bBryant Bulldogs\b", r"\bBryant University\b"]},
        "maine": {"query": "Maine Black Bears basketball", "match": [r"\bMaine Black Bears\b", r"\bUniversity of Maine\b"]},
        "njit": {"query": "NJIT Highlanders basketball", "match": [r"\bNJIT\b"]},
        "new-hampshire": {"query": "New Hampshire Wildcats basketball", "match": [r"\bNew Hampshire Wildcats\b", r"\bUNH\b"]},
        "ualbany": {"query": "UAlbany Great Danes basketball", "match": [r"\bUAlbany\b", r"\bAlbany Great Danes\b"]},
        "umbc": {"query": "UMBC Retrievers basketball", "match": [r"\bUMBC\b"]},
        "umass-lowell": {"query": "UMass Lowell River Hawks basketball", "match": [r"\bUMass Lowell\b"]},
        "vermont": {"query": "Vermont Catamounts basketball", "match": [r"\bVermont Catamounts\b", r"\bUVM\b"]},
    },
    league_feed=("americaeast.com", "America East (americaeast.com)"),
    hashtag="AEHoops",
    tournament="the America East tournament",
)

# Patriot League 2026-27 membership from ESPN's conference feed (group 22).
PATRIOT = League(
    key="patriot", short="Patriot", name="Patriot League",
    region="the Northeast and the Mid-Atlantic, from Boston, Worcester and Hamilton through Lewisburg, Bethlehem, Easton and West Point to Baltimore, Annapolis and Washington",
    teams=(
        Team("american-u", "44", "AMER", "American University Eagles", "American", "#C4122F", "#002D72"),
        Team("army", "349", "ARMY", "Army Black Knights", "Army", "#000000", "#D4BF91"),
        Team("boston-u", "104", "BU", "Boston University Terriers", "Boston University", "#CC0000", "#FFFFFF"),
        Team("bucknell", "2083", "BUCK", "Bucknell Bison", "Bucknell", "#003865", "#E87722"),
        Team("colgate", "2142", "COLG", "Colgate Raiders", "Colgate", "#821019", "#FFFFFF"),
        Team("holy-cross", "107", "HC", "Holy Cross Crusaders", "Holy Cross", "#602D89", "#FFFFFF"),
        Team("lafayette", "322", "LAF", "Lafayette Leopards", "Lafayette", "#98002E", "#FFFFFF"),
        Team("lehigh", "2329", "LEH", "Lehigh Mountain Hawks", "Lehigh", "#653819", "#FFFFFF"),
        Team("loyola-md", "2352", "L-MD", "Loyola Maryland Greyhounds", "Loyola Maryland", "#00694E", "#B9B9B9"),
        Team("navy", "2426", "NAVY", "Navy Midshipmen", "Navy", "#00205B", "#C5B783"),
    ),
    features=frozenset({"midmaxx60"}),
    path="patriot/",
    theme="colonial",
    odds_aliases={
        "American Eagles": "american-u",
        "Army Knights": "army",
        "Boston Univ. Terriers": "boston-u",
        "Loyola (MD) Greyhounds": "loyola-md",
    },
    news_names={
        "american-u": {"query": "American University Eagles basketball", "match": [r"\bAmerican University\b", r"\bAmerican Eagles\b"]},
        "army": {"query": "Army Black Knights basketball", "match": [r"\bArmy Black Knights\b", r"\bArmy West Point\b"]},
        "boston-u": {"query": "Boston University Terriers basketball", "match": [r"\bBoston University\b", r"\bBU Terriers\b"]},
        "bucknell": {"query": "Bucknell Bison basketball", "match": [r"\bBucknell\b"]},
        "colgate": {"query": "Colgate Raiders basketball", "match": [r"\bColgate\b"]},
        "holy-cross": {"query": "Holy Cross Crusaders basketball", "match": [r"\bHoly Cross\b"]},
        "lafayette": {"query": "Lafayette Leopards basketball", "match": [r"\bLafayette Leopards\b", r"\bLafayette College\b"]},
        "lehigh": {"query": "Lehigh Mountain Hawks basketball", "match": [r"\bLehigh\b"]},
        "loyola-md": {"query": "Loyola Maryland Greyhounds basketball", "match": [r"\bLoyola Maryland\b", r"\bLoyola \(Md\.?\)", r"\bGreyhounds\b"]},
        "navy": {"query": "Navy Midshipmen basketball", "match": [r"\bNavy Midshipmen\b", r"\bNaval Academy\b"]},
    },
    league_feed=("patriotleague.org", "Patriot League (patriotleague.org)"),
    hashtag="PatriotLeagueMBB",
    tournament="the Patriot League tournament",
)



ALL: dict[str, League] = {lg.key: lg for lg in (MAC, ASUN, HORIZON, MW, METRO, BIGWEST, MVC, A10, PAC12, WCC, AMERICAN, SUNBELT, IVY, CAA, CUSA, SOCON, BIGSKY, SOUTHLAND, SUMMIT, UAC, BIGSOUTH, OVC, AMEAST, PATRIOT)}


def current() -> League:
    key = (os.environ.get("LEAGUE") or "mac").strip().lower()
    if key not in ALL:
        raise SystemExit(f"LEAGUE={key!r} is not one of {sorted(ALL)}")
    return ALL[key]


if __name__ == "__main__":  # python -m mac.leagues editions: every edition key but the MAC's, for the workflows' loops
    import sys
    if sys.argv[1:] == ["editions"]:
        print(" ".join(k for k in ALL if k != "mac"))
    else:
        print(__doc__)
