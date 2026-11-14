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
    midmaxx60      the daily 60-second script, video and YouTube card
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
    features=frozenset({"notes"}),  # Fieldhouse Notes from Craig, the Miami contributor
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
    features=frozenset(),
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
    features=frozenset(),
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
    features=frozenset(),
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
    features=frozenset(),
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


ALL: dict[str, League] = {lg.key: lg for lg in (MAC, ASUN, HORIZON, MW, METRO, BIGWEST)}


def current() -> League:
    key = (os.environ.get("LEAGUE") or "mac").strip().lower()
    if key not in ALL:
        raise SystemExit(f"LEAGUE={key!r} is not one of {sorted(ALL)}")
    return ALL[key]
