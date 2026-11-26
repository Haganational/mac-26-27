"""IndexNow: tell Bing (and Yandex, Naver, Seznam, Yep) the moment a page is new or changed.

Matthew, Nov 25 2026: "build it". Free and account-free: the key below is public by design and is
proved by a key file at the site root (hardwoodbricks.com/<KEY>.txt, written by hub.build). Google
does not read IndexNow; it reads our sitemaps.

Each collector run (python -m mac.indexnow, after the hub step):
  1. sends last run's queue, which is live by now (the deploy follows the run that queued it);
  2. reads every sitemap in site/ and queues pages we have never sent, plus news items whose
     title changed (a preview that became a recap keeps its URL).
State lives in data/indexnow/ (one append-only sent file per day + the queue), committed with the run's data. Pages only, never content.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import DATA_DIR, SITE_BASE, SITE_NOINDEX, SITE_ROOT

KEY = "5b2f8e1c9d4a47f3a6e0c2b7d81f9e34"
STATE = DATA_DIR / "indexnow"  # sent-<UTC day>.jsonl + queue.json
ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10_000  # the protocol's cap per request
ENABLED = os.environ.get("INDEXNOW", "1").strip().lower() not in ("0", "false", "no", "off")

_LOC = re.compile(r"<url>(.*?)</url>", re.S)


def key_file(site_root: Path | None = None) -> Path:
    site_root = site_root or SITE_ROOT
    f = site_root / f"{KEY}.txt"
    f.write_text(KEY)
    return f


def pages(site_root: Path | None = None) -> dict[str, str]:
    """Every URL in every sitemap under site/: {url: signature}. A news item's signature is its title."""
    site_root = site_root or SITE_ROOT
    out: dict[str, str] = {}
    for sm in sorted(site_root.rglob("*sitemap*.xml")):
        try:
            text = sm.read_text()
        except OSError:
            continue
        for block in _LOC.findall(text):
            m = re.search(r"<loc>(.*?)</loc>", block)
            if not m:
                continue
            url = m.group(1).strip()
            t = re.search(r"<news:title>(.*?)</news:title>", block, re.S)
            if t:
                out[url] = t.group(1).strip()
            else:
                out.setdefault(url, "")
    return out


def _day_files(folder: Path) -> list[Path]:
    return sorted(folder.glob("sent-*.jsonl")) if folder.exists() else []


def load(folder: Path | None = None) -> dict[str, Any]:
    """Sent pages come from one append-only file per UTC day (each run rewrites only today's small file;
    the repo already hurt from rewriting one big file every 30 minutes). The queue is small after day one."""
    folder = folder or STATE
    sent: dict[str, str] = {}
    for f in _day_files(folder):
        for line in f.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            sent[row["u"]] = row.get("s", "")
    try:
        q = json.loads((folder / "queue.json").read_text())
    except (OSError, ValueError):
        q = {}
    return {"sent": sent, "queue": q, "new_sent": {}}


def save(state: dict[str, Any], folder: Path | None = None) -> None:
    folder = folder or STATE
    folder.mkdir(parents=True, exist_ok=True)
    if state.get("new_sent"):
        day = datetime.now(timezone.utc).date().isoformat()
        with (folder / f"sent-{day}.jsonl").open("a") as f:
            for u, sig in sorted(state["new_sent"].items()):
                f.write(json.dumps({"u": u, "s": sig}, separators=(",", ":")) + "\n")
        state["new_sent"] = {}
    (folder / "queue.json").write_text(json.dumps(state["queue"], separators=(",", ":"), sort_keys=True))


def fresh(found: dict[str, str], state: dict[str, Any]) -> dict[str, str]:
    """Pages to queue: never sent or queued, or a news title that changed since we sent it."""
    known = {**state["sent"], **state["queue"]}
    return {u: s for u, s in found.items() if u not in known or (s and known[u] != s)}


def post(urls: list[str], base: str = SITE_BASE) -> list[int]:
    import requests
    host = urlparse(base).netloc
    codes = []
    for i in range(0, len(urls), BATCH):
        r = requests.post(ENDPOINT, json={"host": host, "key": KEY, "keyLocation": f"{base}{KEY}.txt",
                                          "urlList": urls[i:i + BATCH]},
                          headers={"Content-Type": "application/json; charset=utf-8"}, timeout=30)
        codes.append(r.status_code)
    return codes


def run(site_root: Path | None = None, base: str = SITE_BASE, send=post) -> dict[str, Any]:
    if SITE_NOINDEX or not ENABLED:
        return {"skipped": "noindex" if SITE_NOINDEX else "off"}
    state = load()
    host = urlparse(base).netloc
    sent_n, codes = 0, []
    queue = {u: s for u, s in state["queue"].items() if urlparse(u).netloc == host}
    if queue:
        codes = send(sorted(queue), base)
        # 200 = received, 202 = received and the key is still being checked. Anything else: keep the queue for next run.
        if codes and all(c in (200, 202) for c in codes):
            state["sent"].update(queue)
            state["new_sent"] = queue
            state["queue"] = {}
            sent_n = len(queue)
    new = {u: s for u, s in fresh(pages(site_root), state).items() if urlparse(u).netloc == host}
    state["queue"].update(new)
    save(state)
    return {"sent": sent_n, "codes": codes, "queued": len(new)}


if __name__ == "__main__":
    print("indexnow:", run())
    sys.exit(0)
