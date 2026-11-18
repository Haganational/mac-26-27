"""Retire a released cut: YouTube videos go private and get a retired title (reversible); Facebook, Instagram,
Threads and Bluesky posts are deleted. Reads promos/<film>/takedown.json; "done": true makes it a no-op.

    PYTHONPATH=<checkout of main> python promos/takedown.py promos/franco/takedown.json
"""
import json, os, sys, urllib.parse
import requests
from mac import youtube as Y
from mac import reels as R

def main(path):
    m = json.load(open(path))
    if m.get("done"):
        print("takedown: done, nothing to do"); return
    e = os.environ
    if m.get("youtube"):
        tok = Y.access_token(e["YT_CLIENT_ID"], e["YT_CLIENT_SECRET"], e["YT_REFRESH_TOKEN"])
        for i, vid in enumerate(m["youtube"]):
            try:
                v = Y._call(f"{Y.API}/videos?part=snippet,status&id={vid}", tok)[0]["items"][0]
                sn = v["snippet"]; body = {"id": vid, "snippet": {"title": f"{m.get('retired_prefix', 'Retired cut')} {i + 1}",
                    "categoryId": sn.get("categoryId", "27"), "description": sn.get("description", ""), "tags": sn.get("tags", [])},
                    "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
                Y._call(f"{Y.API}/videos?part=snippet,status", tok, json.dumps(body).encode(), "application/json", "PUT")
                print(f"youtube: {vid} set private and renamed")
            except Exception as ex:  # noqa: BLE001
                print(f"youtube: {vid} FAILED ({ex})")
    if m.get("facebook") or m.get("instagram"):
        pt = R.page_token(e["FB_PAGE_ID"].strip(), e["FB_PAGE_TOKEN"].strip())
        for kind in ("facebook", "instagram"):
            for pid in m.get(kind, []):
                r = requests.delete(f"{R.GRAPH}/{pid}", params={"access_token": pt}, timeout=30)
                print(f"{kind}: {pid} {'deleted' if r.ok else 'FAILED ' + r.text[:200]}")
    for pid in m.get("threads", []):
        r = requests.delete(f"{R.THREADS}/{pid}", params={"access_token": e["THREADS_ACCESS_TOKEN"].strip()}, timeout=30)
        print(f"threads: {pid} {'deleted' if r.ok else 'FAILED ' + r.text[:200]}")
    if m.get("bluesky"):
        sess = R.bsky_session(e["BSKY_HANDLE"].strip(), e["BSKY_APP_PASSWORD"].strip())
        for uri in m["bluesky"]:
            rkey = uri.rsplit("/", 1)[-1]
            r = requests.post(f"{R.PDS}/com.atproto.repo.deleteRecord", timeout=30, headers={"Authorization": f"Bearer {sess['accessJwt']}"},
                              json={"repo": sess["did"], "collection": "app.bsky.feed.post", "rkey": rkey})
            print(f"bluesky: {rkey} {'deleted' if r.ok else 'FAILED ' + r.text[:200]}")

if __name__ == "__main__":
    for p in sys.argv[1:]: main(p)
