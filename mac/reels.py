"""Cross-post a finished show video to Facebook, Instagram, Threads and Bluesky.

    python -m mac.reels --out out --show midmaxx60
    python -m mac.reels --out out --show bigmid

Runs after the YouTube upload, on the same MP4 and description in out/. Each network posts
on its own once its secrets are set; with none set this prints a note and exits cleanly.

  Facebook Page (Reel for MidMaxx60, regular Page video for The Big Mid):
      FB_PAGE_ID, FB_PAGE_TOKEN  (a Page token from a long-lived user token; it does not expire)
  Instagram Reel (MidMaxx60 only; The Big Mid is 16:9):
      IG_ACCESS_TOKEN (Instagram API with Instagram Login, instagram_business_content_publish);
      IG_USER_ID optional, defaults to "me". The token lasts about 60 days.
  Threads video (MidMaxx60 only; Threads video tops out at 5 minutes):
      THREADS_ACCESS_TOKEN, THREADS_USER_ID optional (the same secrets mac/social.py uses)
  Bluesky video (both shows; Bluesky takes up to 10 minutes):
      BSKY_HANDLE, BSKY_APP_PASSWORD (the same secrets mac/social.py uses)

Instagram and Threads fetch the video from a public URL, so the show must already be published
as a GitHub release (the step before YouTube does that). Facebook and Bluesky get the bytes.

A show is never posted twice: before posting, each network's recent posts are checked for the
show's title line, the same way mac/youtube.py checks the channel. A failure on one network
does not stop the others; each failure emails Matthew through mac.alert and the step fails
at the end so the run shows red. SOCIAL_DRY_RUN=1 prints what would be posted.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from . import alert
from .youtube import title

REPO = "Haganational/mac-26-27"
GRAPH = "https://graph.facebook.com/v21.0"
RUPLOAD = "https://rupload.facebook.com/video-upload/v21.0"
IG = "https://graph.instagram.com/v21.0"
THREADS = "https://graph.threads.net/v1.0"
PDS = "https://bsky.social/xrpc"
BSKY_VIDEO = "https://video.bsky.app/xrpc"
SITE = "https://hardwoodbricks.com"
DISCLOSURE = "Anchors are fictional AI personas, not affiliated with any school."
POLL_SECONDS, POLL_TRIES = 10, 60  # wait up to ten minutes for a network to finish processing
SHOW_PAGE = {"midmaxx60": f"{SITE}/midmaxx60.html", "bigmid": f"{SITE}/watch.html"}


# ---------- the post text ----------

def caption(stem: str, description: str, show: str, limit: int = 2200) -> str:
    """Title line (the dedupe key), the show's opening line, the link, tags and the AI disclosure."""
    paras = [p.strip() for p in description.split("\n\n") if p.strip()]
    lead = paras[0] if paras else ""
    tags = "#Midmaxxing #MidMaxx60 #CollegeBasketball" if show == "midmaxx60" else "#Midmaxxing #TheBigMid #CollegeBasketball"
    parts = [title(stem), lead, f"Full slate: {SHOW_PAGE[show]}", tags, DISCLOSURE]
    text = "\n\n".join(p for p in parts if p)
    if len(text) > limit:  # drop the lead before anything else
        text = "\n\n".join(p for p in [title(stem), f"Full slate: {SHOW_PAGE[show]}", tags] if p)
    return text[:limit]


def short_caption(stem: str, show: str) -> str:
    """For Bluesky's 300-character posts and Threads' 500: title, link, tags, disclosure."""
    tags = "#Midmaxxing #CollegeBasketball"
    return f"{title(stem)}\n\n{SHOW_PAGE[show]}\n\n{tags}\n{DISCLOSURE}"


def release_url(stem: str, repo: str = REPO) -> str:
    """The public download link of the release asset the workflow published."""
    return f"https://github.com/{repo}/releases/download/{stem}/{stem}.mp4"


def resolve(url: str) -> str:
    """GitHub answers release downloads with a redirect; hand Meta the final, signed URL (valid 30 minutes)."""
    r = requests.head(url, allow_redirects=False, timeout=30)
    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
        return r.headers["Location"]
    r.raise_for_status()
    return url


def _ok(r: requests.Response) -> dict[str, Any]:
    if not r.ok:
        raise RuntimeError(f"{r.request.method} {r.url.split('?')[0]} answered {r.status_code}: {r.text[:400]}")
    return r.json() if r.content.strip() else {}


def _wait(check: Callable[[], str], done: set[str], failed: set[str], what: str) -> None:
    for _ in range(POLL_TRIES):
        state = check()
        if state in done:
            return
        if state in failed:
            raise RuntimeError(f"{what} processing failed ({state})")
        time.sleep(POLL_SECONDS)
    raise RuntimeError(f"{what} still processing after {POLL_SECONDS * POLL_TRIES} seconds")


# ---------- Facebook Page ----------

def fb_already(page: str, token: str, head: str) -> bool:
    for edge in ("video_reels", "videos"):
        data = _ok(requests.get(f"{GRAPH}/{page}/{edge}", timeout=30,
                                params={"fields": "description", "limit": 15, "access_token": token})).get("data", [])
        if any((v.get("description") or "").startswith(head) for v in data):
            return True
    return False


def fb_reel(page: str, token: str, mp4: Path, text: str) -> str:
    """Reels Publishing API: start, upload the bytes, finish with PUBLISHED."""
    start = _ok(requests.post(f"{GRAPH}/{page}/video_reels", timeout=30,
                              data={"upload_phase": "start", "access_token": token}))
    vid = start["video_id"]
    blob = mp4.read_bytes()
    _ok(requests.post(start.get("upload_url") or f"{RUPLOAD}/{vid}", data=blob, timeout=600,
                      headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(blob))}))
    _ok(requests.post(f"{GRAPH}/{page}/video_reels", timeout=60, data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED", "description": text, "access_token": token}))
    return vid


def fb_video(page: str, token: str, mp4: Path, text: str, name: str) -> str:
    """A regular Page video, for the 16:9 Big Mid (Reels must be 9:16 and 90 seconds or less)."""
    with mp4.open("rb") as f:
        r = _ok(requests.post(f"https://graph-video.facebook.com/v21.0/{page}/videos", timeout=900,
                              data={"description": text, "title": name, "access_token": token},
                              files={"source": (mp4.name, f, "video/mp4")}))
    return r.get("id", "")


# ---------- Instagram ----------

def ig_already(user: str, token: str, head: str) -> bool:
    data = _ok(requests.get(f"{IG}/{user}/media", timeout=30,
                            params={"fields": "caption", "limit": 15, "access_token": token})).get("data", [])
    return any((m.get("caption") or "").startswith(head) for m in data)


def ig_reel(user: str, token: str, url: str, text: str) -> str:
    c = _ok(requests.post(f"{IG}/{user}/media", timeout=60, data={
        "media_type": "REELS", "video_url": url, "caption": text, "share_to_feed": "true", "access_token": token}))
    cid = c["id"]
    _wait(lambda: _ok(requests.get(f"{IG}/{cid}", timeout=30, params={"fields": "status_code", "access_token": token})).get("status_code", ""),
          {"FINISHED"}, {"ERROR", "EXPIRED"}, "Instagram")
    return _ok(requests.post(f"{IG}/{user}/media_publish", timeout=60, data={"creation_id": cid, "access_token": token})).get("id", "")


# ---------- Threads ----------

def th_already(user: str, token: str, head: str) -> bool:
    data = _ok(requests.get(f"{THREADS}/{user}/threads", timeout=30,
                            params={"fields": "text", "limit": 15, "access_token": token})).get("data", [])
    return any((t.get("text") or "").startswith(head) for t in data)


def th_video(user: str, token: str, url: str, text: str) -> str:
    c = _ok(requests.post(f"{THREADS}/{user}/threads", timeout=60, data={
        "media_type": "VIDEO", "video_url": url, "text": text, "access_token": token}))
    cid = c["id"]
    _wait(lambda: _ok(requests.get(f"{THREADS}/{cid}", timeout=30, params={"fields": "status", "access_token": token})).get("status", ""),
          {"FINISHED"}, {"ERROR", "EXPIRED"}, "Threads")
    return _ok(requests.post(f"{THREADS}/{user}/threads_publish", timeout=60, data={"creation_id": cid, "access_token": token})).get("id", "")


# ---------- Bluesky ----------

def _facets(text: str) -> list[dict[str, Any]]:
    from .social import _facets as tags
    out = tags(text)
    b = text.encode()
    start = b.find(b"https://")
    if start >= 0:
        end = start
        while end < len(b) and b[end:end + 1] not in (b" ", b"\n"):
            end += 1
        out.append({"index": {"byteStart": start, "byteEnd": end},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": b[start:end].decode()}]})
    return out


def bsky_session(handle: str, password: str) -> dict[str, Any]:
    return _ok(requests.post(f"{PDS}/com.atproto.server.createSession", timeout=30,
                             json={"identifier": handle, "password": password}))


def bsky_already(sess: dict[str, Any], head: str) -> bool:
    feed = _ok(requests.get(f"{PDS}/app.bsky.feed.getAuthorFeed", timeout=30,
                            headers={"Authorization": f"Bearer {sess['accessJwt']}"},
                            params={"actor": sess["did"], "limit": 30, "filter": "posts_no_replies"})).get("feed", [])
    return any((f.get("post", {}).get("record", {}).get("text") or "").startswith(head) for f in feed)


def _pds_did(sess: dict[str, Any]) -> str:
    """The service DID of the account's PDS, which the video service wants as the token audience."""
    for s in (sess.get("didDoc") or {}).get("service", []):
        if s.get("id", "").endswith("atproto_pds"):
            return "did:web:" + s["serviceEndpoint"].split("://", 1)[-1].rstrip("/")
    return "did:web:bsky.social"


def bsky_video(sess: dict[str, Any], mp4: Path, text: str, size: tuple[int, int]) -> str:
    auth = {"Authorization": f"Bearer {sess['accessJwt']}"}
    exp = int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp())
    svc = _ok(requests.get(f"{PDS}/com.atproto.server.getServiceAuth", timeout=30, headers=auth,
                           params={"aud": _pds_did(sess), "lxm": "com.atproto.repo.uploadBlob", "exp": exp}))["token"]
    r = requests.post(f"{BSKY_VIDEO}/app.bsky.video.uploadVideo", timeout=600, data=mp4.read_bytes(),
                      params={"did": sess["did"], "name": mp4.name},
                      headers={"Authorization": f"Bearer {svc}", "Content-Type": "video/mp4"})
    body = r.json() if r.content.strip() else {}
    job = body.get("jobId") or (body.get("jobStatus") or {}).get("jobId")
    if not job:  # a 409 for a file already uploaded still carries the job id; anything else is an error
        _ok(r)
        raise RuntimeError(f"Bluesky video upload gave no job id: {r.text[:300]}")
    box: dict[str, Any] = {}

    def state() -> str:
        js = _ok(requests.get(f"{BSKY_VIDEO}/app.bsky.video.getJobStatus", timeout=30,
                              headers={"Authorization": f"Bearer {svc}"}, params={"jobId": job}))["jobStatus"]
        if js.get("blob"):
            box["blob"] = js["blob"]
        return js.get("state", "")
    _wait(state, {"JOB_STATE_COMPLETED"}, {"JOB_STATE_FAILED"}, "Bluesky video")
    record = {"$type": "app.bsky.feed.post", "text": text[:300], "facets": _facets(text[:300]), "langs": ["en"],
              "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
              "embed": {"$type": "app.bsky.embed.video", "video": box["blob"],
                        "aspectRatio": {"width": size[0], "height": size[1]}, "alt": text.split("\n")[0]}}
    return _ok(requests.post(f"{PDS}/com.atproto.repo.createRecord", timeout=30, headers=auth,
                             json={"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record})).get("uri", "")


# ---------- the run ----------

def networks(show: str, env: dict[str, str] | None = None) -> list[str]:
    """The networks this show goes to whose secrets are set, in posting order."""
    e = {k: v.strip() for k, v in (env if env is not None else os.environ).items()}
    out = []
    if e.get("FB_PAGE_ID") and e.get("FB_PAGE_TOKEN"):
        out.append("facebook")
    if show == "midmaxx60" and e.get("IG_ACCESS_TOKEN"):
        out.append("instagram")
    if show == "midmaxx60" and e.get("THREADS_ACCESS_TOKEN"):
        out.append("threads")
    if e.get("BSKY_HANDLE") and e.get("BSKY_APP_PASSWORD"):
        out.append("bluesky")
    return out


def post_one(net: str, show: str, mp4: Path, description: str) -> str:
    """Post to one network; returns what happened, raises on failure."""
    e = os.environ
    stem = mp4.stem
    head = title(stem)
    long_text, short_text = caption(stem, description, show), short_caption(stem, show)
    if net == "facebook":
        page, token = e["FB_PAGE_ID"].strip(), e["FB_PAGE_TOKEN"].strip()
        if fb_already(page, token, head):
            return "already posted"
        vid = fb_reel(page, token, mp4, long_text) if show == "midmaxx60" else fb_video(page, token, mp4, long_text, head)
        return f"posted video {vid}"
    if net in ("instagram", "threads"):
        token = e[f"{'IG' if net == 'instagram' else 'THREADS'}_ACCESS_TOKEN"].strip()
        user = e.get(f"{'IG' if net == 'instagram' else 'THREADS'}_USER_ID", "").strip() or "me"
        if (ig_already if net == "instagram" else th_already)(user, token, head):
            return "already posted"
        url = resolve(release_url(stem, e.get("GITHUB_REPOSITORY", "").strip() or REPO))
        pid = ig_reel(user, token, url, long_text) if net == "instagram" else th_video(user, token, url, short_text)
        return f"posted {pid}"
    if net == "bluesky":
        sess = bsky_session(e["BSKY_HANDLE"].strip(), e["BSKY_APP_PASSWORD"].strip())
        if bsky_already(sess, head):
            return "already posted"
        size = (1080, 1920) if show == "midmaxx60" else (1920, 1080)
        return f"posted {bsky_video(sess, mp4, short_text, size)}"
    raise ValueError(net)


def run(out: Path, show: str) -> int:
    """Post to every configured network; returns how many failed."""
    found = sorted(out.glob(f"{show}-*.mp4"))
    if not found:
        print(f"reels: no {show} video in {out}, nothing to post")
        return 0
    mp4 = found[-1]
    txt = out / f"{mp4.stem}.txt"
    description = txt.read_text() if txt.exists() else ""
    if os.environ.get("SOCIAL_DRY_RUN") == "1":
        print(f"[dry] long caption:\n{caption(mp4.stem, description, show)}\n\n[dry] short caption:\n{short_caption(mp4.stem, show)}")
        print(f"[dry] would post to: {', '.join(networks(show)) or 'nothing (no secrets set)'}")
        return 0
    nets = networks(show)
    if not nets:
        print("reels: no Facebook, Instagram, Threads or Bluesky secrets set, skipped")
        return 0
    name = "The Big Mid" if show == "bigmid" else "MidMaxx60"
    failed = 0
    for net in nets:
        try:
            print(f"reels: {net}: {post_one(net, show, mp4, description)}")
        except Exception as ex:  # noqa: BLE001 - one network's trouble must not stop the others
            failed += 1
            print(f"reels: {net} failed: {ex}")
            alert.send(f"{name} did not post to {net.title()}",
                       f"{type(ex).__name__}: {ex}\n\nThe usual cause is an expired or missing permission on the "
                       f"access token in the repo secrets. Re-running the workflow retries only the networks that "
                       f"do not have today's {name} yet.")
    return failed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--show", default="midmaxx60", choices=sorted(SHOW_PAGE))
    a = ap.parse_args()
    if run(Path(a.out), a.show):
        sys.exit(1)


if __name__ == "__main__":
    main()
