"""The At-Large Watch: which teams in our six conferences have a real shot at an at-large NCAA bid.

The method, in plain terms
--------------------------
1. Team strength rank (S). Our own rating rank among all D-I teams (the ratings page's
   adjusted efficiency margin). Once the NCAA publishes the NET (early December), S is the
   average of our rank and the team's NET rank.
2. Conference at-large weight (C). How many at-large bids the conference has averaged per
   tournament since 2010, with recent seasons counting more: a season's weight halves every
   HALF_LIFE seasons. History is by the league as it was that year (data/atlarge/bids.json).
3. Watch rank = S - BOOST x C. Each at-large bid a league has averaged per year moves its
   teams up BOOST spots. Lower is better. The table is sorted by it.

    watch = S - 10 x C

Zones read off the watch rank: up to IN_LINE "in the picture", up to BUBBLE "bubble",
up to FRINGE "fringe", and beyond that a team's road to the tournament is the auto bid.

The NET comes from ncaa.com (python -m mac.atlarge net), saved to data/atlarge/net.json.
A NET file from an earlier season is ignored, so last March's final NET never leaks in.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .config import SEASON, SHARED_DIR
from .leagues import ALL

DIR = SHARED_DIR / "atlarge"
BIDS = DIR / "bids.json"
NET = DIR / "net.json"
NET_URL = "https://www.ncaa.com/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings"

HALF_LIFE = 4.0  # seasons
BOOST = 10.0  # rank spots per average at-large bid a season
IN_LINE, BUBBLE, FRINGE = 30, 55, 85  # the 2027 field grows from 68 to 76, so about 44 at-large spots instead of 36
ZONES = (("in", "In the picture"), ("bubble", "Bubble"), ("fringe", "Fringe"), ("auto", "Auto bid or bust"))


def load_bids(path: Path = BIDS) -> dict[str, dict[str, dict[str, Any]]]:
    return json.loads(path.read_text())["seasons"]


def season_weight(year: int, now: int = SEASON) -> float:
    return 0.5 ** ((now - year) / HALF_LIFE)


def conference_weight(bids: dict[str, dict[str, dict[str, Any]]], conf: str, now: int = SEASON) -> float:
    """Recency-weighted average of at-large bids per tournament (seasons before `now` only)."""
    num = den = 0.0
    for y, confs in bids.items():
        year = int(y)
        if year >= now or conf not in confs:
            continue
        w = season_weight(year, now)
        num += w * len(confs[conf]["at_large"])
        den += w
    return num / den if den else 0.0


def history(bids: dict[str, dict[str, dict[str, Any]]], now: int = SEASON) -> list[dict[str, Any]]:
    """One row per conference: total at-large bids, seasons with one, the weight C and the seasons."""
    years = sorted(int(y) for y in bids if int(y) < now)
    out = []
    for key, lg in ALL.items():
        seasons = [{"year": y, **bids[str(y)].get(key, {"auto": "", "at_large": []})} for y in years]
        out.append({
            "key": key, "short": lg.short, "name": lg.name,
            "total": sum(len(s["at_large"]) for s in seasons),
            "multi": sum(1 for s in seasons if s["at_large"]),
            "weight": round(conference_weight(bids, key, now), 2),
            "boost": round(BOOST * conference_weight(bids, key, now), 1),
            "seasons": seasons,
            "last": next((s for s in reversed(seasons) if s["at_large"]), None),
        })
    out.sort(key=lambda c: (-c["weight"], c["short"]))
    return out


# ---------------------------------------------------------------- NET


class _Table(HTMLParser):
    """Rows of the first <table> on the page, as lists of cell text."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.text: list[str] = []
        self._depth = 0
        self._done = False
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if self._done:
            return
        if tag == "table":
            self._depth += 1
        elif self._depth and tag == "tr":
            self._row = []
        elif self._depth and tag in ("td", "th"):
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if self._done:
            return
        if tag == "table" and self._depth:
            self._depth -= 1
            self._done = not self._depth
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        self.text.append(data)


def parse_net(html: str) -> dict[str, Any]:
    """ncaa.com's NET page -> {"through": "YYYY-MM-DD" or "", "teams": [{"rank", "school", "record", "conf"}]}."""
    p = _Table()
    p.feed(html)
    if not p.rows:
        return {"through": "", "teams": []}
    head = [h.lower() for h in p.rows[0]]

    def col(*names: str) -> int | None:
        return next((i for i, h in enumerate(head) if h in names), None)

    ir, isch, irec, iconf = col("rank"), col("school", "team"), col("record"), col("conf", "conference")
    teams = []
    for r in p.rows[1:]:
        if ir is None or isch is None or len(r) <= max(ir, isch) or not r[ir].isdigit():
            continue
        teams.append({"rank": int(r[ir]), "school": r[isch],
                      "record": r[irec] if irec is not None and irec < len(r) else "",
                      "conf": r[iconf] if iconf is not None and iconf < len(r) else ""})
    m = re.search(r"[Tt]hrough [Gg]ames\s+(\d{1,2})/(\d{1,2})/(\d{4})", " ".join(p.text))
    through = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""
    return {"through": through, "teams": teams}


def fetch_net(path: Path = NET) -> str:
    """Save the current NET to data/atlarge/net.json. Runs on GitHub Actions (the cloud sandbox can't reach ncaa.com)."""
    import requests
    r = requests.get(NET_URL, timeout=30, headers={"User-Agent": "HardwoodBricks/1.0 (+https://hardwoodbricks.com)"})
    r.raise_for_status()
    net = parse_net(r.text)
    if not net["teams"]:
        if not path.exists():  # leave a marker so the workflow waits for tomorrow's run instead of retrying all day
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"teams": [], "season": None, "through": "", "fetched": datetime.now(timezone.utc).isoformat(timespec="minutes")}) + "\n")
        return "net: no table on the page; kept the old file"
    net["fetched"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    net["season"] = SEASON if net["through"] >= f"{SEASON - 1}-11-01" else None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(net, indent=1) + "\n")
    return f"net: {len(net['teams'])} teams through {net['through'] or '?'} (season {net['season']})"


def _norm(s: str) -> str:
    s = s.lower().replace("&", "and").replace("saint ", "st ").replace("state", "st")
    return re.sub(r"[^a-z0-9]", "", s)


NET_NAMES = {  # ncaa.com school name (normalized) -> our team key, where the short names differ
    "miamioh": "miami-oh", "massachusetts": "umass", "flagulfcoast": "fgcu",
    "floridagulfcoast": "fgcu", "queensnc": "queens", "iuindy": "iu-indy", "iuindianapolis": "iu-indy",
    "purduefortwayne": "purdue-fort-wayne", "pfw": "purdue-fort-wayne", "detroit": "detroit-mercy",
    "mtstmarys": "mount-st-marys", "mountstmarys": "mount-st-marys", "stpeters": "saint-peters",
    "hawaii": "hawaii", "sanjosest": "san-jose-state", "calbaptist": "cal-baptist", "californiabaptist": "cal-baptist",
    "csubakersfield": "csu-bakersfield", "calstbakersfield": "csu-bakersfield", "calstfullerton": "cal-state-fullerton",
    "csufullerton": "cal-state-fullerton", "calstnorthridge": "csun", "csun": "csun", "longbeachst": "long-beach-state",
    "sacramentost": "sacramento-state", "ucsantabarbara": "uc-santa-barbara", "ucsb": "uc-santa-barbara",
    "westflorida": "west-florida", "northflorida": "north-florida", "unlv": "unlv", "utep": "utep",
}


def net_ranks(net: dict[str, Any] | None, now: int = SEASON) -> dict[str, int]:
    """{our team key: NET rank} for this season's NET only."""
    if not net or net.get("season") != now:
        return {}
    ours = {}
    for lg in ALL.values():
        for t in lg.teams:
            ours[_norm(t.short)] = t.key
            ours[_norm(t.name.rsplit(" ", 1)[0])] = t.key
    out = {}
    for row in net.get("teams", []):
        n = _norm(row["school"])
        key = NET_NAMES.get(n) or ours.get(n)
        if key:
            out[key] = row["rank"]
    return out


def load_net(path: Path = NET) -> dict[str, Any] | None:
    return json.loads(path.read_text()) if path.exists() else None


# ---------------------------------------------------------------- ratings and the watch


def load_ratings(root: Path = SHARED_DIR) -> dict[str, Any] | None:
    """The newest ratings.json any edition wrote (every edition fits all of D-I, so they agree but for timing)."""
    best = None
    for f in [root / "model" / "ratings.json", *sorted((root / "leagues").glob("*/model/ratings.json"))]:
        if not f.exists():
            continue
        try:
            d = json.loads(f.read_text())
        except ValueError:
            continue
        if best is None or d.get("as_of", "") > best.get("as_of", ""):
            best = d
    return best


def zone(watch: float) -> str:
    if watch <= IN_LINE:
        return "in"
    if watch <= BUBBLE:
        return "bubble"
    if watch <= FRINGE:
        return "fringe"
    return "auto"


def watch(ratings: dict[str, Any], bids: dict[str, dict[str, dict[str, Any]]], net: dict[str, int] | None = None,
          now: int = SEASON) -> list[dict[str, Any]]:
    """Every team in our six conferences, best watch rank first."""
    net = net or {}
    by_id = {t["id"]: t for t in ratings.get("teams", [])}
    n_teams = len(by_id)
    weights = {k: conference_weight(bids, k, now) for k in ALL}
    out = []
    for key, lg in ALL.items():
        for t in lg.teams:
            r = by_id.get(t.espn_id)
            if not r:
                continue
            ours = r["rk_adj_em"]
            n = net.get(t.key)
            s = (ours + n) / 2 if n else float(ours)
            w = s - BOOST * weights[key]
            out.append({"key": t.key, "short": t.short, "conf": key, "conf_short": lg.short, "href": f"{lg.path}teams/{t.key}.html",
                        "color": t.color, "ours": ours, "net": n, "strength": round(s, 1), "c": round(weights[key], 2),
                        "boost": round(BOOST * weights[key], 1), "watch": round(w, 1), "zone": zone(w),
                        "net_pts": r.get("net_pts"), "games": r.get("games", 0), "of": n_teams})
    out.sort(key=lambda x: (x["watch"], x["ours"]))
    for i, x in enumerate(out, 1):
        x["rank"] = i
    return out


def page_context(root: Path = SHARED_DIR, now: int = SEASON) -> dict[str, Any] | None:
    ratings = load_ratings(root)
    if not ratings:
        return None
    bids = load_bids(root / "atlarge" / "bids.json")
    raw_net = load_net(root / "atlarge" / "net.json")
    net = net_ranks(raw_net, now)
    rows = watch(ratings, bids, net, now)
    hist = history(bids, now)
    years = sorted(int(y) for y in bids if int(y) < now)
    as_of = ratings.get("as_of", "")
    try:
        as_of_label = datetime.fromisoformat(as_of).strftime("%b %-d, %Y")
    except ValueError:
        as_of_label = as_of
    return {
        "rows": rows, "history": hist, "years": years, "first_year": years[0] if years else None,
        "last_year": years[-1] if years else None, "zones": ZONES,
        "zone_counts": {z: sum(1 for r in rows if r["zone"] == z) for z, _ in ZONES},
        "half_life": HALF_LIFE, "boost": BOOST, "in_line": IN_LINE, "bubble": BUBBLE, "fringe": FRINGE,
        "net_on": bool(net), "net_through": (raw_net or {}).get("through", "") if net else "",
        "as_of": as_of_label, "n_teams": len(ratings.get("teams", [])),
        "weights_table": [{"year": y, "w": round(season_weight(y, now) / season_weight(years[-1], now), 2)} for y in reversed(years)][:6],
    }


if __name__ == "__main__":  # python -m mac.atlarge net
    import sys
    if sys.argv[1:] == ["net"]:
        print(fetch_net())
    else:
        for r in watch(load_ratings() or {}, load_bids(), net_ranks(load_net()))[:25]:
            print(f"{r['rank']:>3} {r['short']:<20} {r['conf_short']:<14} ours {r['ours']:>3} net {r['net'] or '-':>3} "
                  f"C {r['c']:.2f} watch {r['watch']:>6} {r['zone']}")
