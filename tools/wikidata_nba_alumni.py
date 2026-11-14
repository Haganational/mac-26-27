"""All-time NBA alumni of every school we cover (all editions in mac/leagues.py), with the NBA franchises each one played for, from Wikidata.

Wikidata is CC0, so the result can be published. Run where wikidata.org is reachable (GitHub Actions):

    python tools/wikidata_nba_alumni.py            # writes data/den/nba_alumni.json

A player counts for a school when Wikidata lists that school's men's basketball team as one of
their teams (P54) or the university as where they studied (P69). A player counts for a franchise
when Wikidata lists any NBA team (league P118 = NBA) that is that franchise under any of its names
(Seattle SuperSonics -> Thunder, New Jersey Nets -> Nets and so on, see FRANCHISE below).
Unmatched college and team labels are printed so the maps can be fixed by hand.
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "den" / "nba_alumni.json"
SPARQL = "https://query.wikidata.org/sparql"
UA = "HardwoodBricksDen/1.0 (https://hardwoodbricks.com; NBA alumni grid)"
NBA = "Q155223"

# Short tags for the grid's row labels; any edition not listed uses its league's short name.
EDITION_TAG = {"mw": "MW", "mvc": "MVC"}

# Every name an NBA franchise has gone by (Wikidata labels), mapped to today's franchise code.
FRANCHISE = {
    "ATL": ["Atlanta Hawks", "St. Louis Hawks", "Milwaukee Hawks", "Tri-Cities Blackhawks"],
    "BOS": ["Boston Celtics"],
    "BKN": ["Brooklyn Nets", "New Jersey Nets", "New York Nets", "New Jersey Americans"],
    "CHA": ["Charlotte Hornets", "Charlotte Bobcats"],
    "CHI": ["Chicago Bulls"],
    "CLE": ["Cleveland Cavaliers"],
    "DAL": ["Dallas Mavericks"],
    "DEN": ["Denver Nuggets", "Denver Rockets"],
    "DET": ["Detroit Pistons", "Fort Wayne Pistons", "Fort Wayne Zollner Pistons"],
    "GSW": ["Golden State Warriors", "San Francisco Warriors", "Philadelphia Warriors"],
    "HOU": ["Houston Rockets", "San Diego Rockets"],
    "IND": ["Indiana Pacers"],
    "LAC": ["Los Angeles Clippers", "San Diego Clippers", "Buffalo Braves"],
    "LAL": ["Los Angeles Lakers", "Minneapolis Lakers"],
    "MEM": ["Memphis Grizzlies", "Vancouver Grizzlies"],
    "MIA": ["Miami Heat"],
    "MIL": ["Milwaukee Bucks"],
    "MIN": ["Minnesota Timberwolves"],
    "NOP": ["New Orleans Pelicans", "New Orleans Hornets", "New Orleans/Oklahoma City Hornets"],
    "NYK": ["New York Knicks", "New York Knickerbockers"],
    "OKC": ["Oklahoma City Thunder", "Seattle SuperSonics"],
    "ORL": ["Orlando Magic"],
    "PHI": ["Philadelphia 76ers", "Syracuse Nationals"],
    "PHX": ["Phoenix Suns"],
    "POR": ["Portland Trail Blazers"],
    "SAC": ["Sacramento Kings", "Kansas City Kings", "Kansas City-Omaha Kings", "Cincinnati Royals", "Rochester Royals"],
    "SAS": ["San Antonio Spurs"],
    "TOR": ["Toronto Raptors"],
    "UTA": ["Utah Jazz", "New Orleans Jazz"],
    "WAS": ["Washington Wizards", "Washington Bullets", "Capital Bullets", "Baltimore Bullets", "Chicago Zephyrs", "Chicago Packers"],
}
NICK = {"ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets", "CHI": "Bulls", "CLE": "Cavaliers",
        "DAL": "Mavericks", "DEN": "Nuggets", "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers",
        "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat", "MIL": "Bucks", "MIN": "Timberwolves",
        "NOP": "Pelicans", "NYK": "Knicks", "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
        "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors", "UTA": "Jazz", "WAS": "Wizards"}

# University or team labels that don't share words with our team names. Filled from the run log.
SCHOOL_ALIASES: dict[str, list[str]] = {
    "VCU Rams": ["Virginia Commonwealth University"],
    "UIC Flames": ["University of Illinois Chicago", "University of Illinois at Chicago", "UIC Flames men's basketball"],
    "Southern Illinois Salukis": ["Southern Illinois University Carbondale"],
    "Loyola Chicago Ramblers": ["Loyola University Chicago", "Loyola Ramblers"],
    "George Washington Revolutionaries": ["George Washington Colonials"],
    "Valparaiso Beacons": ["Valparaiso Crusaders"],
    "Saint Joseph's Hawks": ["St. Joseph's Hawks"],
    "UNLV Rebels": ["University of Nevada, Las Vegas", "UNLV Runnin' Rebels"],
    "Nevada Wolf Pack": ["University of Nevada, Reno"],
    "IU Indianapolis Jaguars": ["IUPUI Jaguars", "Indiana University-Purdue University Indianapolis", "Indiana University Indianapolis"],
    "Purdue Fort Wayne Mastodons": ["IPFW Mastodons", "Indiana University-Purdue University Fort Wayne"],
    "Detroit Mercy Titans": ["University of Detroit Mercy", "Detroit Titans", "University of Detroit"],
    "Miami (OH) RedHawks": ["Miami University", "Miami RedHawks", "Miami Redskins"],
    "Long Beach State Beach": ["California State University, Long Beach", "Long Beach State 49ers"],
    "Cal State Fullerton Titans": ["California State University, Fullerton"],
    "Cal State Northridge Matadors": ["California State University, Northridge"],
    "Cal State Bakersfield Roadrunners": ["California State University, Bakersfield"],
    "Hawai'i Rainbow Warriors": ["University of Hawaiʻi at Mānoa", "University of Hawaii", "Hawaii Rainbow Warriors"],
    "UC Santa Barbara Gauchos": ["University of California, Santa Barbara"],
    "UC Irvine Anteaters": ["University of California, Irvine"],
    "UC Riverside Highlanders": ["University of California, Riverside"],
    "UC Davis Aggies": ["University of California, Davis"],
    "UC San Diego Tritons": ["University of California, San Diego"],
    "Cal Poly Mustangs": ["California Polytechnic State University"],
    "San José State Spartans": ["San Jose State Spartans", "San José State University", "San Jose State University"],
    "Air Force Falcons": ["United States Air Force Academy"],
    "Saint Peter's Peacocks": ["Saint Peter's University", "St. Peter's Peacocks"],
    "Mount St. Mary's Mountaineers": ["Mount St. Mary's University"],
    "Youngstown State Penguins": ["Youngstown State University"],
    "Wright State Raiders": ["Wright State University"],
    "Cleveland State Vikings": ["Cleveland State University"],
    "Kent State Golden Flashes": ["Kent State University"],
    "Bowling Green Falcons": ["Bowling Green State University"],
    "Florida Gulf Coast Eagles": ["Florida Gulf Coast University"],
    "Massachusetts Minutemen": ["University of Massachusetts Amherst", "UMass Minutemen"],
    "UTEP Miners": ["University of Texas at El Paso", "Texas Western Miners", "Texas Western College"],
    "Sacramento State Hornets": ["California State University, Sacramento"],
    "Green Bay Phoenix": ["University of Wisconsin–Green Bay", "Wisconsin–Green Bay Phoenix"],
    "Milwaukee Panthers": ["University of Wisconsin–Milwaukee", "Wisconsin–Milwaukee Panthers"],
    "Buffalo Bulls": ["University at Buffalo"],
    "Queens University Royals": ["Queens University of Charlotte", "Queens Royals"],
    "Long Beach State Beach": ["California State University, Long Beach", "Long Beach State 49ers"],
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("men's basketball", "").replace("basketball", "")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def query(q: str) -> list[dict[str, str]]:
    for attempt in range(4):
        r = requests.post(SPARQL, data={"query": q}, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"}, timeout=180)
        if r.status_code == 200:
            try:
                return [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]
            except ValueError as e:  # a response cut off at the 60 s query limit
                print("wikidata: bad JSON,", e)
        else:
            print("wikidata", r.status_code, r.text[:200])
        time.sleep(10 * (attempt + 1))
    raise SystemExit("wikidata: gave up after 4 tries")


def our_teams() -> dict[str, dict[str, str]]:
    """Every school in every edition in mac/leagues.py, so a new conference is picked up with no edit here."""
    sys.path.insert(0, str(ROOT))
    from mac import leagues

    try:
        rated = {t["id"]: t for t in json.loads((ROOT / "data" / "model" / "ratings.json").read_text())["teams"]}
    except (OSError, ValueError, KeyError):
        rated = {}
    out = {}
    for key, lg in leagues.ALL.items():
        for t in lg.teams:
            r = rated.get(t.espn_id, {})
            out[t.espn_id] = {"id": t.espn_id, "name": t.name, "short": r.get("short") or t.short,
                              "long": t.short, "edition": EDITION_TAG.get(key, lg.short)}
    return out


def main() -> int:
    teams = our_teams()
    keys: dict[str, str] = {}  # normalized label -> our team id
    for tid, t in teams.items():
        generic = [f for sh in {t["short"], t["long"]}
                   for f in (f"University of {sh}", f"{sh} University", f"{sh} College")]
        for lab in [t["name"], *SCHOOL_ALIASES.get(t["name"], []), *generic]:
            keys.setdefault(norm(lab), tid)
    label_franchise = {norm(lab): code for code, labs in FRANCHISE.items() for lab in labs}

    # Three small queries instead of one huge one (a single query came back cut off at 22 MB).
    # 1. Every NBA roster spot: player -> NBA team item.
    spots = query(f"SELECT ?p ?t WHERE {{ ?p wdt:P54 ?t . ?t wdt:P118 wd:{NBA} . }}")
    # 2. English names of those NBA team items, and of the players.
    tnames = {r["t"]: r["l"] for r in query(f"""
SELECT DISTINCT ?t ?l WHERE {{ ?t wdt:P118 wd:{NBA} ; rdfs:label ?l . FILTER(LANG(?l) = "en") }}""")}
    pnames = {r["p"]: r["l"] for r in query(f"""
SELECT DISTINCT ?p ?l WHERE {{ ?p wdt:P54 ?t . ?t wdt:P118 wd:{NBA} . ?p rdfs:label ?l . FILTER(LANG(?l) = "en") }}""")}
    # 3. Their college teams and universities, already narrowed to college-looking labels.
    cols = query(f"""
SELECT DISTINCT ?p ?l WHERE {{
  ?p wdt:P54 ?x . ?x wdt:P118 wd:{NBA} .
  ?p wdt:P54|wdt:P69 ?c . ?c rdfs:label ?l . FILTER(LANG(?l) = "en")
  FILTER(CONTAINS(?l, "basketball") || CONTAINS(?l, "Universit") || CONTAINS(?l, "College") || CONTAINS(?l, "Academy"))
}}""")
    print("rows", len(spots), len(tnames), len(pnames), len(cols))
    players: dict[str, dict] = {}
    unknown_nba: dict[str, int] = {}
    for r in spots:
        p = players.setdefault(r["p"], {"name": pnames.get(r["p"], ""), "schools": set(), "teams": set()})
        lab = tnames.get(r["t"], "")
        code = label_franchise.get(norm(lab))
        if code:
            p["teams"].add(code)
        else:
            unknown_nba[lab] = unknown_nba.get(lab, 0) + 1
    for r in cols:
        tid = keys.get(norm(r["l"]))
        if tid and r["p"] in players:
            players[r["p"]]["schools"].add(tid)
    by_school: dict[str, list] = {tid: [] for tid in teams}
    for qid, p in players.items():
        if not p["teams"] or re.fullmatch(r"Q\d+", p["name"]):
            continue
        for tid in p["schools"]:
            by_school[tid].append({"name": p["name"], "qid": qid.rsplit("/", 1)[-1], "teams": sorted(p["teams"])})
    for v in by_school.values():
        v.sort(key=lambda x: x["name"])
    print("NBA team labels not mapped (fix FRANCHISE if any is a real NBA franchise):", json.dumps(unknown_nba, sort_keys=True))
    counts = sorted(((len(v), teams[t]["name"]) for t, v in by_school.items()), reverse=True)
    print("alumni per school:", counts)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Wikidata (CC0): players with an NBA team (P54, league NBA) and our school's team (P54) or university (P69).",
        "franchises": NICK,
        "schools": {tid: {"name": teams[tid]["name"], "short": teams[tid]["short"], "edition": teams[tid]["edition"],
                          "alumni": by_school[tid]} for tid in teams},
    }, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
