"""News ticker: recent MAC men's basketball headlines from free RSS/Atom feeds.

Why not Reddit: Reddit stops serving RSS on 2026-11-13, stopped taking new
public API requests on 2026-10-31 and closes public API access in March 2027,
and unauthenticated .json was deprecated mid-2026. So the ticker reads feeds
that stay free, and the dashboard links out to the subreddits instead.

Sources, all public and free:
  * Each school's athletics site (SIDEARM sites expose /rss.aspx?path=mbball;
    a few use another sport slug, so each feed tries a short list of URLs and
    falls back to a Google News site: search of that domain)
  * The MAC's own site, getsomemaction.com, same format
  * Google News search RSS, one query per team (covers student papers,
    local papers and national outlets)

Substack is excluded at Matthew's request (2026-11-09), as are women's
basketball stories.

Every run fetches each feed once (about 28 small requests, three times a day),
merges new items into data/news/items.json, keeps 45 days, and writes each
feed's last status to data/news/feeds.json so a dead feed is visible.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus, urlsplit
from xml.etree import ElementTree as ET

import requests

from .config import DATA_DIR, TEAMS

NEWS_DIR = DATA_DIR / "news"
ITEMS_PATH = NEWS_DIR / "items.json"
FEEDS_PATH = NEWS_DIR / "feeds.json"
KEEP_DAYS = 45
MAX_ITEMS = 1500
TIMEOUT = 20
USER_AGENT = "mac-26-27-news/1.0 (+https://github.com/Haganational/mac-26-27)"

# Athletics sites, by team key. All are SIDEARM sites.
ATHLETICS = {
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
}

# How each team is named in a Google News query and in headlines.
# `query` is quoted in Google News; `match` patterns tag league-wide items.
NAMES: dict[str, dict[str, Any]] = {
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
}

# Words that mark a general-news headline as being about men's hoops.
HOOPS = re.compile(r"basketball|hoops|\bMBB\b|\bMAC (tournament|tourney|title)|tip-?off|point guard|three-pointer|\bKenPom\b|NCAA tournament|March Madness", re.I)
WOMENS = re.compile(r"women[’']?s|\bWBB\b|\blady\b", re.I)
MENS = re.compile(r"\bmen[’']?s\b", re.I)
MENS_HOOPS = re.compile(r"\bmen[’']?s (college )?basketball\b|\bMBB\b", re.I)
OTHER_SPORT = re.compile(r"\b(soccer|football|volleyball|softball|baseball|hockey|wrestling|gymnastics|swimming|swim|track|cross country|golf|tennis|lacrosse|rowing)\b", re.I)
HIGH_SCHOOL = re.compile(r"high school|\bvarsity\b|\bHSRC\b|\bboys\b|\bgirls\b", re.I)
# Pick-site and betting-tout filler that Google News surfaces for every game.
SPAM = re.compile(r"\bpredictions?\b|\bpicks?\b|computer pick|best bets?\b|betting (preview|odds)|\bprops?\b|\broster\b - ", re.I)

# Subreddits, for links only (Reddit's feeds are closing; see module docstring).
# Campus subs were confirmed to exist; r/CollegeBasketball team searches always resolve.
SUBREDDITS = {
    "league": [("CollegeBasketball", "3.0M members; game threads for MAC games")],
    "buffalo": [("UBreddit", "University at Buffalo campus sub, about 34k")],
    "umass": [("umass", "UMass Amherst campus sub, about 29k")],
}


@dataclass(frozen=True)
class Feed:
    key: str  # stable id, e.g. "athletics:toledo"
    url: str
    source: str  # display name
    kind: str  # athletics | league | google
    team: str | None  # team key, or None for league-wide feeds
    alts: tuple[str, ...] = ()  # tried in order when `url` fails or comes back empty

    @property
    def urls(self) -> tuple[str, ...]:
        return (self.url, *self.alts)


def google_news_url(query: str, raw: bool = False) -> str:
    q = query if raw else f'"{query}" basketball when:14d'
    return f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-US&gl=US&ceid=US:en"


SIDEARM_PATHS = ("mbball", "mbb", "mens-basketball", "basketball-men")


def site_search_url(domain: str, extra: str = "") -> str:
    """Google News limited to one site: the fallback when a site's own feed is blocked or empty."""
    return google_news_url(f"site:{domain} {extra} when:30d".replace("  ", " "), raw=True)


def sidearm_urls(host: str) -> tuple[str, ...]:
    return tuple(f"https://{host}/rss.aspx?path={p}" for p in SIDEARM_PATHS)


def all_feeds() -> list[Feed]:
    mac = sidearm_urls("getsomemaction.com")
    feeds = [
        Feed("league:mac", mac[0], "MAC (getsomemaction.com)", "league", None, mac[1:]),
    ]
    by_key = {t.key: t for t in TEAMS}
    for key, host in ATHLETICS.items():
        urls = sidearm_urls(host) + (site_search_url(host, "basketball"),)
        feeds.append(Feed(f"athletics:{key}", urls[0], host, "athletics", key, urls[1:]))
    for key, n in NAMES.items():
        feeds.append(Feed(f"google:{key}", google_news_url(n["query"]), "Google News", "google", key))
    assert all(f.team is None or f.team in by_key for f in feeds)
    return feeds


# --- parsing ---------------------------------------------------------------

def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el: ET.Element, name: str) -> ET.Element | None:
    for c in el:
        if _strip_ns(c.tag) == name:
            return c
    return None


def _text(el: ET.Element, name: str) -> str:
    c = _child(el, name)
    return (c.text or "").strip() if c is not None and c.text else ""


def parse_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)  # RFC 822, used by RSS
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))  # ISO 8601, used by Atom
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def parse_feed(xml_text: str | bytes) -> list[dict[str, Any]]:
    """Return [{title, url, published, summary, publisher}] from RSS 2.0 or Atom."""
    root = ET.fromstring(xml_text)
    out = []
    if _strip_ns(root.tag) == "feed":  # Atom
        entries = [e for e in root if _strip_ns(e.tag) == "entry"]
        for e in entries:
            link = ""
            for c in e:
                if _strip_ns(c.tag) == "link" and c.get("rel", "alternate") == "alternate":
                    link = c.get("href", "")
                    break
            out.append({
                "title": clean(_text(e, "title")),
                "url": link,
                "published": parse_date(_text(e, "published") or _text(e, "updated")),
                "summary": clean(_text(e, "summary") or _text(e, "content"))[:300],
                "publisher": None,
            })
        return out
    channel = _child(root, "channel")
    for it in (channel if channel is not None else root):
        if _strip_ns(it.tag) != "item":
            continue
        src = _child(it, "source")
        out.append({
            "title": clean(_text(it, "title")),
            "url": _text(it, "link") or _text(it, "guid"),
            "published": parse_date(_text(it, "pubDate") or _text(it, "date")),
            "summary": clean(_text(it, "description"))[:300],
            "publisher": clean(src.text) if src is not None and src.text else None,
            "origin": src.get("url", "") if src is not None else "",
        })
    return out


# --- tagging and filtering --------------------------------------------------

def tag_teams(text: str) -> list[str]:
    hits = []
    for key, n in NAMES.items():
        if any(re.search(p, text) for p in n["match"]):
            hits.append(key)
    return hits


def _norm_title(title: str) -> str:
    title = re.sub(r"\s+[-–|]\s+[^-–|]{2,60}$", "", title)  # drop " - Publisher" suffix Google adds
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def item_id(title: str) -> str:
    return hashlib.sha1(_norm_title(title).encode()).hexdigest()[:16]


def headline_ok(title: str, kind: str, team: str | None, url: str = "") -> bool:
    """Rules every stored headline must pass; also re-applied to stored items on each run."""
    if WOMENS.search(title) and not MENS.search(title.replace("Women", "").replace("women", "")):
        return False
    if SPAM.search(title) or HIGH_SCHOOL.search(title):
        return False
    if OTHER_SPORT.search(title) and not re.search(r"basketball|hoops", title, re.I):
        return False
    if url and host(url).endswith("substack.com"):  # Matthew: no Substack in the ticker
        return False
    if kind == "google" and team:
        # A team search also returns opponents' and other sports' stories: the headline
        # must name the team, or be explicitly a men's basketball story.
        return team in tag_teams(title) or bool(MENS_HOOPS.search(title))
    return True


def keep(feed: Feed, raw: dict[str, Any]) -> bool:
    """Men's basketball only. Athletics mbball feeds are already filtered by sport."""
    text = f"{raw['title']} {raw.get('summary') or ''}"
    if feed.kind in ("athletics", "league"):
        return not WOMENS.search(raw["title"]) and not SPAM.search(raw["title"])
    if feed.kind == "google":
        return bool(HOOPS.search(text))
    return bool(HOOPS.search(text)) or bool(tag_teams(raw["title"]))


def normalize(feed: Feed, raw: dict[str, Any], seen_at: datetime) -> dict[str, Any] | None:
    if not raw["title"] or not raw["url"] or not keep(feed, raw):
        return None
    title = raw["title"]
    publisher = raw.get("publisher")
    if publisher and title.endswith(f" - {publisher}"):  # Google News appends the outlet
        title = title[: -len(f" - {publisher}")].strip()
    if not headline_ok(title, feed.kind, feed.team, raw["url"]) or not headline_ok(title, feed.kind, feed.team, raw.get("origin") or ""):
        return None
    teams = tag_teams(title)
    if feed.team and feed.team not in teams:
        teams.insert(0, feed.team)
    published = raw["published"] or seen_at
    return {
        "id": item_id(title),
        "title": title,
        "url": raw["url"],
        "origin": raw.get("origin") or "",
        "source": publisher or feed.source,
        "kind": feed.kind,
        "feed": feed.key,
        "teams": teams,
        "published": published.isoformat(timespec="seconds"),
        "first_seen": seen_at.isoformat(timespec="seconds"),
    }


def merge(existing: list[dict[str, Any]], new: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Dedupe on normalized title. Prefer the school's own link over a Google redirect."""
    rank = {"athletics": 0, "league": 1, "google": 3}
    by_id: dict[str, dict[str, Any]] = {i["id"]: i for i in existing}
    for item in new:
        old = by_id.get(item["id"])
        if old is None:
            by_id[item["id"]] = item
            continue
        teams = old["teams"] + [t for t in item["teams"] if t not in old["teams"]]
        if rank.get(item["kind"], 9) < rank.get(old["kind"], 9):
            item = {**item, "first_seen": old["first_seen"]}
            by_id[item["id"]] = item
        by_id[item["id"]]["teams"] = teams
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    future = (now + timedelta(days=1)).isoformat()
    items = [i for i in by_id.values() if cutoff <= i["published"] and headline_ok(i["title"], i["kind"], _feed_team(i), i["url"])]
    items = [i for i in items if i["kind"] != "substack" and not host(i.get("origin") or "x").endswith("substack.com")]
    for i in items:  # a feed with a bad clock should not pin an item to the top
        if i["published"] > future:
            i["published"] = i["first_seen"]
    items.sort(key=lambda i: i["published"], reverse=True)
    return items[:MAX_ITEMS]


def _feed_team(item: dict[str, Any]) -> str | None:
    key = item.get("feed", "")
    return key.split(":", 1)[1] if key.startswith("google:") else None


# --- I/O ---------------------------------------------------------------------

def load_items() -> list[dict[str, Any]]:
    if not ITEMS_PATH.exists():
        return []
    return json.loads(ITEMS_PATH.read_text()).get("items", [])


def load_feed_status() -> dict[str, Any]:
    if not FEEDS_PATH.exists():
        return {}
    return json.loads(FEEDS_PATH.read_text())


class EmptyFeed(ValueError):
    pass


def fetch(url: str, session: requests.Session) -> str | bytes:
    resp = session.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    resp.raise_for_status()
    if not resp.content.strip():
        raise EmptyFeed("empty response")
    return resp.content


def fetch_first(feed: Feed, session: requests.Session) -> tuple[str, list[dict[str, Any]]]:
    """Try the feed's URLs in order; return the first that parses with at least one entry."""
    errors = []
    for url in feed.urls:
        try:
            raws = parse_feed(fetch(url, session))
        except (requests.RequestException, ET.ParseError, EmptyFeed) as exc:
            errors.append(f"{type(exc).__name__}: {str(exc)[:100]}")
            continue
        if raws:
            return url, raws
        errors.append("no entries")
    raise EmptyFeed(" | ".join(errors)[:300])


def refresh(now: datetime | None = None, session: requests.Session | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    session = session or requests.Session()
    status = load_feed_status()
    new: list[dict[str, Any]] = []
    feeds = all_feeds()
    status = {k: v for k, v in status.items() if k in {f.key for f in feeds}}  # forget retired feeds
    for feed in feeds:
        st = status.get(feed.key, {})
        st.update({"url": feed.url, "source": feed.source, "kind": feed.kind, "team": feed.team, "checked_at": now.isoformat(timespec="seconds")})
        try:
            used, raws = fetch_first(feed, session)
            items = [x for x in (normalize(feed, r, now) for r in raws) if x]
            new.extend(items)
            st.update({"ok": True, "error": None, "entries": len(raws), "kept": len(items), "last_ok": st["checked_at"],
                       "used": used, "fallback": used != feed.url, "via_google": "news.google.com" in used and feed.kind != "google"})
        except EmptyFeed as exc:
            st.update({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
        status[feed.key] = st
    items = merge(load_items(), new, now)
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    ITEMS_PATH.write_text(json.dumps({"updated_at": now.isoformat(timespec="seconds"), "items": items}, indent=1))
    FEEDS_PATH.write_text(json.dumps(status, indent=1, sort_keys=True))
    ok = sum(1 for s in status.values() if s.get("ok"))
    return {"feeds_ok": ok, "feeds": len(status), "new_or_seen": len(new), "items": len(items)}


# --- view helpers ------------------------------------------------------------

def host(url: str) -> str:
    return urlsplit(url).netloc.removeprefix("www.")


def reddit_links(team_key: str | None) -> list[dict[str, str]]:
    """Subreddit links for a team page or the league page."""
    out = []
    for name, note in SUBREDDITS.get(team_key or "league", []):
        out.append({"label": f"r/{name}", "url": f"https://www.reddit.com/r/{name}/", "note": note})
    if team_key:
        q = quote_plus(NAMES[team_key]["query"].split()[0] if team_key != "miami-oh" else "Miami RedHawks")
        out.append({"label": "r/CollegeBasketball search", "url": f"https://www.reddit.com/r/CollegeBasketball/search/?q={q}&restrict_sr=1&sort=new",
                    "note": "newest posts mentioning the team"})
    return out


def view(now: datetime, team_key: str | None = None, limit: int = 40) -> dict[str, Any]:
    items = load_items()
    if team_key:
        items = [i for i in items if team_key in i["teams"]]
    out = []
    for i in items[:limit]:
        age_h = (now - datetime.fromisoformat(i["published"])).total_seconds() / 3600
        out.append({**i, "age": _age(age_h), "fresh": age_h < 24})
    status = load_feed_status()
    return {
        "headlines": out,
        "total": len(items),
        "feeds_ok": sum(1 for s in status.values() if s.get("ok")),
        "feeds": len(status),
        "status": sorted(status.items()),
        "reddit": reddit_links(team_key),
    }


def _age(hours: float) -> str:
    if hours < 1:
        return f"{max(1, int(hours * 60))}m"
    if hours < 48:
        return f"{int(hours)}h"
    return f"{int(hours // 24)}d"
