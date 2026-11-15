"""Hashtags for every post (Matthew, Nov 15 2026): 3 to 5 per post, never more.

    #Midmaxxing  #CollegeBasketball  + one to three specific tags from that day's content

The specific tags are school and conference names (#KentState, #MACtion), because fans follow
their team, and that is the tag that finds new people. City tags belong only on the town films;
schools are never @-mentioned automatically.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

BRAND = "#Midmaxxing"
SPORT = "#CollegeBasketball"
MOST = 5


def clean(words: str) -> str:
    """'San José St' -> '#SanJoseSt', "Hawai'i" -> '#Hawaii', 'Texas A&M-CC' -> '#TexasAMCC'."""
    plain = unicodedata.normalize("NFKD", words).encode("ascii", "ignore").decode()
    body = re.sub(r"[^A-Za-z0-9]", "", plain)
    return f"#{body}" if body else ""


def school(team: Any) -> str:
    return clean(team.short)


def conference(lg: Any) -> str:
    return clean(lg.hashtag or lg.short)


def specific(pairs: Iterable[tuple[Any, Any]], most: int = 3) -> list[str]:
    """School then conference, story by story, skipping repeats: [(Kent State, MAC), (Drake, MVC)]
    -> ['#KentState', '#MACtion', '#Drake']."""
    out: list[str] = []
    for team, lg in pairs:
        for t in (school(team) if team else "", conference(lg) if lg else ""):
            if t and t not in out and t not in (BRAND, SPORT):
                out.append(t)
            if len(out) >= most:
                return out
    return out


def line(extra: Iterable[str] = (), first: Iterable[str] = ()) -> str:
    """The tag line: `first` (e.g. #Shorts), the brand, the sport, then the specific tags, capped at five."""
    tags: list[str] = []
    for t in [*first, BRAND, SPORT, *extra]:
        if t and t not in tags:
            tags.append(t)
    return " ".join(tags[:MOST])


def from_file(path: Any) -> list[str]:
    """The day's specific tags that mac.midmaxx60 wrote next to the video (empty if none)."""
    try:
        return [t for t in path.read_text().split() if t.startswith("#")]
    except OSError:
        return []
