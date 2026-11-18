"""Facebook Page and Instagram Stories from the Hardwood Bricks library.

The library is every vertical video and image card already published as a GitHub release
asset (film promos, MidMaxx60, Players of the Night, Bricked). Matthew's rules (Nov 18, 2026):

* Four Stories a day at 7 AM, 11 AM, 4 PM and 9 PM Eastern, drawn at random from the library.
* New content gets an immediate Story push when it is published, on top of the four.
* Verticals cut from evergreen material (film promos, teasers, fight songs) that have never had
  a Story jump the line ahead of random picks.
* Nothing repeats too soon: an item that had a Story in the last REST_DAYS days is skipped while
  anything fresher is left.

The workflow runs hourly. Each run: (1) pushes at most one brand-new item, (2) fills the most
recent scheduled slot if it has not been filled (GitHub's cron runs late, so a slot stays open for
SLOT_GRACE hours), and (3) honours EXTRA_SLOTS, one-off extra hours. What was posted is kept in
stories.json on the `stories-ledger` release, so no commit to main is needed.

Run by hand: python -m mac.stories --now   (post one pick right away)
             python -m mac.stories --dry   (show what would post)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from . import alert
from .reels import GRAPH, REPO, _ok, _wait, ig_auth, page_token, resolve

ET = ZoneInfo("America/New_York")
SLOT_HOURS = (7, 11, 16, 21)          # 7 AM, 11 AM, 4 PM, 9 PM Eastern
SLOT_GRACE = 3                        # a late cron still fills a slot up to three hours after it
# One-off extra Story hours (Eastern), on top of the four. Matthew, Nov 18 2026: one now and one
# on the hour until the 9 PM slot takes over.
EXTRA_SLOTS = {"2026-11-18": (17, 18, 19, 20)}
REST_DAYS = 14                        # don't repeat an item inside two weeks while others are left
NEW_HOURS = 30                        # "new" = published in the last 30 hours and never storied
MAX_SECONDS = 60                      # Story videos are trimmed to a minute
LEDGER_TAG = "stories-ledger"
LEDGER_FILE = "stories.json"

# Release tags that are evergreen material (films, docs, fight songs, statements), vs dated dailies.
EVERGREEN_MARKS = ("-promos", "teaser", "fightsong", "hb-statement")
SKIP_TAGS = ("mac90-", "after-dark", "bigmid-", LEDGER_TAG)   # 16:9 or retired shows


@dataclass(frozen=True)
class Item:
    tag: str
    name: str
    published: str          # ISO time of the release
    kind: str               # "video" or "image"

    @property
    def key(self) -> str:
        return f"{self.tag}/{self.name}"

    @property
    def url(self) -> str:
        return f"https://github.com/{REPO}/releases/download/{self.tag}/{self.name}"

    @property
    def evergreen(self) -> bool:
        return any(m in self.tag for m in EVERGREEN_MARKS)


# ---------- the library ----------

def wanted(tag: str, name: str) -> str | None:
    """'video', 'image' or None: which release assets can be Stories."""
    if any(tag.startswith(s) or s in tag for s in SKIP_TAGS):
        return None
    if name.endswith(".mp4"):
        return "video"
    # Tonight's Four and Beat the Desk are about one night's games, so only the timeless cards go.
    if name.endswith(".jpg") and name.startswith(("potn-", "bricked-")):
        return "image"
    return None


def items_from(releases: list[dict[str, Any]]) -> list[Item]:
    out = []
    for r in releases:
        if r.get("draft"):
            continue
        for a in r.get("assets", []):
            kind = wanted(r["tag_name"], a["name"])
            if kind:
                out.append(Item(r["tag_name"], a["name"], r.get("published_at") or "", kind))
    return out


def library(repo: str = REPO) -> list[Item]:
    tok = os.environ.get("GH_TOKEN", "").strip()
    headers = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {tok}"} if tok else {})}
    rels: list[dict[str, Any]] = []
    for page in range(1, 11):
        r = requests.get(f"https://api.github.com/repos/{repo}/releases", headers=headers, timeout=30,
                         params={"per_page": 100, "page": page})
        r.raise_for_status()
        batch = r.json()
        rels += batch
        if len(batch) < 100:
            break
    return items_from(rels)


# ---------- choosing ----------

def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def is_new(item: Item, ledger: dict[str, Any], now: datetime) -> bool:
    """Published recently, after the ledger started, and never storied."""
    if item.key in ledger["posted"] or not item.published:
        return False
    pub = _t(item.published)
    return pub > _t(ledger["since"]) and now - pub < timedelta(hours=NEW_HOURS)


def pick_new(items: list[Item], ledger: dict[str, Any], now: datetime) -> Item | None:
    """The oldest unstoried new item, videos before images; MidMaxx60 counts once a day anyway."""
    fresh = [i for i in items if is_new(i, ledger, now)]
    if not fresh:
        return None
    fresh.sort(key=lambda i: (i.kind != "video", i.published, i.name))
    return fresh[0]


def pick(items: list[Item], ledger: dict[str, Any], now: datetime, rng: random.Random) -> Item | None:
    """Evergreen verticals never storied first; then a random item not storied inside REST_DAYS;
    then whatever was storied longest ago."""
    posted = ledger["posted"]
    never_evergreen = [i for i in items if i.evergreen and i.kind == "video" and i.key not in posted]
    if never_evergreen:
        return rng.choice(never_evergreen)
    rested = [i for i in items if i.key not in posted or now - _t(posted[i.key][-1]) > timedelta(days=REST_DAYS)]
    if rested:
        # Players of the Night has ~25 cards a day; weight so videos and Bricked aren't drowned out.
        weights = [4.0 if i.kind == "video" else (2.0 if i.name.startswith("bricked-") else 0.25) for i in rested]
        return rng.choices(rested, weights=weights, k=1)[0]
    if not items:
        return None
    return min(items, key=lambda i: posted[i.key][-1])


def due_slot(ledger: dict[str, Any], now: datetime) -> str | None:
    """The key ("2026-11-18T16") of the latest scheduled or extra hour that is due and unfilled."""
    local = now.astimezone(ET)
    for back in range(SLOT_GRACE + 1):
        h = local - timedelta(hours=back)
        day = h.strftime("%Y-%m-%d")
        if h.hour in SLOT_HOURS or h.hour in EXTRA_SLOTS.get(day, ()):
            key = f"{day}T{h.hour:02d}"
            if key not in ledger["slots"]:
                return key
            return None  # the latest slot is filled; older ones are history
    return None


# ---------- the ledger (a JSON file on a release) ----------

def load_ledger(now: datetime) -> dict[str, Any]:
    r = requests.get(f"https://github.com/{REPO}/releases/download/{LEDGER_TAG}/{LEDGER_FILE}", timeout=30)
    if r.ok:
        led = r.json()
    else:
        led = {}
    led.setdefault("since", now.isoformat())
    led.setdefault("posted", {})      # item key -> [ISO times]
    led.setdefault("slots", {})       # slot key -> item key
    led.setdefault("log", [])
    return led


def save_ledger(led: dict[str, Any]) -> None:
    led["log"] = led["log"][-500:]
    path = Path(tempfile.gettempdir()) / LEDGER_FILE
    path.write_text(json.dumps(led, indent=1, sort_keys=True))
    sh = lambda *a: subprocess.run(["gh", "release", *a], check=False, capture_output=True, text=True)  # noqa: E731
    if sh("view", LEDGER_TAG).returncode != 0:
        sh("create", LEDGER_TAG, "--title", "Stories ledger",
           "--notes", "What mac/stories.py has posted as Facebook and Instagram Stories. Not a show.")
    up = sh("upload", LEDGER_TAG, str(path), "--clobber")
    if up.returncode != 0:
        raise RuntimeError(f"could not save the stories ledger: {up.stderr[:300]}")


# ---------- posting ----------

def networks(env: dict[str, str] | None = None) -> list[str]:
    e = {k: v.strip() for k, v in (env if env is not None else os.environ).items()}
    only = [n for n in e.get("STORY_NETWORKS", "facebook,instagram").split(",") if n]
    out = []
    if "facebook" in only and e.get("FB_PAGE_ID") and e.get("FB_PAGE_TOKEN"):
        out.append("facebook")
    if "instagram" in only and (e.get("IG_ACCESS_TOKEN") or (e.get("IG_USER_ID") and e.get("FB_PAGE_TOKEN"))):
        out.append("instagram")
    return out


def duration(mp4: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def fetch_video(item: Item, folder: Path) -> tuple[Path, float]:
    """Download the video; trim anything over a minute (the cover frame at the start is kept)."""
    src = folder / item.name
    with requests.get(item.url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with src.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    secs = duration(src)
    if secs > MAX_SECONDS:
        cut = folder / f"cut-{item.name}"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-t", str(MAX_SECONDS - 1),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-movflags", "+faststart",
                        str(cut)], check=True)
        return cut, secs
    return src, secs


def fb_video_story(page: str, token: str, mp4: Path) -> str:
    start = _ok(requests.post(f"{GRAPH}/{page}/video_stories", timeout=30,
                              data={"upload_phase": "start", "access_token": token}))
    vid = start["video_id"]
    blob = mp4.read_bytes()
    _ok(requests.post(start.get("upload_url") or f"https://rupload.facebook.com/video-upload/v21.0/{vid}",
                      data=blob, timeout=600,
                      headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(blob))}))
    done = _ok(requests.post(f"{GRAPH}/{page}/video_stories", timeout=120, data={
        "upload_phase": "finish", "video_id": vid, "access_token": token}))
    return str(done.get("post_id") or vid)


def fb_photo_story(page: str, token: str, url: str) -> str:
    photo = _ok(requests.post(f"{GRAPH}/{page}/photos", timeout=120, data={
        "url": url, "published": "false", "temporary": "true", "access_token": token}))
    done = _ok(requests.post(f"{GRAPH}/{page}/photo_stories", timeout=60, data={
        "photo_id": photo["id"], "access_token": token}))
    return str(done.get("post_id") or photo["id"])


def ig_story(user: str, token: str, host: str, url: str, kind: str) -> str:
    field = "video_url" if kind == "video" else "image_url"
    c = _ok(requests.post(f"{host}/{user}/media", timeout=60, data={
        "media_type": "STORIES", field: url, "access_token": token}))
    cid = c["id"]
    _wait(lambda: _ok(requests.get(f"{host}/{cid}", timeout=30, params={"fields": "status_code", "access_token": token})).get("status_code", "FINISHED"),
          {"FINISHED"}, {"ERROR", "EXPIRED"}, "Instagram Story")
    return _ok(requests.post(f"{host}/{user}/media_publish", timeout=60, data={"creation_id": cid, "access_token": token})).get("id", "")


def post(item: Item, nets: list[str]) -> dict[str, str]:
    """Post one item to each network; returns {network: result}, never raises."""
    e = os.environ
    results: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        mp4: Path | None = None
        secs = 0.0
        if item.kind == "video":
            try:
                mp4, secs = fetch_video(item, Path(tmp))
            except Exception as ex:  # noqa: BLE001
                return {n: f"failed: could not fetch the video ({ex})" for n in nets}
        for net in nets:
            try:
                if net == "facebook":
                    page = e["FB_PAGE_ID"].strip()
                    token = page_token(page, e["FB_PAGE_TOKEN"].strip())
                    sid = fb_video_story(page, token, mp4) if mp4 else fb_photo_story(page, token, item.url)
                    results[net] = f"posted {sid}"
                elif net == "instagram":
                    if item.kind == "video" and secs > MAX_SECONDS:
                        results[net] = "skipped (over a minute; Instagram Stories take the trimmed cut only on Facebook)"
                        continue
                    token, user, host = ig_auth(e)
                    results[net] = f"posted {ig_story(user, token, host, resolve(item.url), item.kind)}"
            except Exception as ex:  # noqa: BLE001 - one network's trouble must not stop the other
                results[net] = f"failed: {ex}"
    return results


def record(led: dict[str, Any], item: Item, why: str, results: dict[str, str], now: datetime, slot: str | None) -> None:
    if any(r.startswith("posted") for r in results.values()):
        led["posted"].setdefault(item.key, []).append(now.isoformat())
        if slot:
            led["slots"][slot] = item.key
    led["log"].append({"at": now.isoformat(), "item": item.key, "why": why, **results})


# ---------- the run ----------

def run(now: datetime, force: bool = False, dry: bool = False, seed: int | None = None) -> int:
    nets = networks()
    items = library()
    led = load_ledger(now)
    rng = random.Random(seed)
    plan: list[tuple[Item, str, str | None]] = []
    new = pick_new(items, led, now)
    if new:
        plan.append((new, "new", None))
    slot = due_slot(led, now)
    if slot or force:
        chosen = pick([i for i in items if not new or i.key != new.key], led, now, rng)
        if chosen:
            extra = not slot or int(slot[-2:]) not in SLOT_HOURS
            why = (f"extra {slot}" if extra else f"slot {slot}") if slot else "by hand"
            plan.append((chosen, why, slot))
    print(f"stories: {len(items)} items in the library, networks: {', '.join(nets) or 'none set'}")
    if not plan:
        print("stories: nothing due this hour")
        return 0
    failed = 0
    for item, why, s in plan:
        if dry or not nets:
            print(f"[dry] {why}: {item.key}")
            continue
        # Extra hours are Facebook only; Instagram gets the four, new items and by-hand pushes.
        use = [n for n in nets if n == "facebook"] if why.startswith("extra") else nets
        if not use:
            continue
        results = post(item, use)
        for net, res in results.items():
            print(f"stories: {why}: {item.key} -> {net}: {res}")
        record(led, item, why, results, now, s)
        bad = {n: r for n, r in results.items() if r.startswith("failed")}
        if bad:
            failed += 1
            alert.send("A Story did not post", "\n".join(f"{n}: {r}" for n, r in bad.items()) +
                       "\n\nThe usual cause is a missing Page permission (pages_manage_posts) or an expired token.")
    if not dry and nets:
        save_ledger(led)
    return failed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true", help="post one pick right away, whatever the hour")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if run(datetime.now(timezone.utc), force=a.now, dry=a.dry or os.environ.get("SOCIAL_DRY_RUN") == "1"):
        sys.exit(1)


if __name__ == "__main__":
    main()
