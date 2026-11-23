"""Delete repeat posts listed in promos/<film>/cleanup.json (only the exact ids listed).

    PYTHONPATH=. python promos/cleanup.py promos/<film>/cleanup.json

YouTube: each id is checked against its expected title before it is deleted.
Bluesky: each rkey is an app.bsky.feed.post record on the account's own repo.
"""
import json, os, sys
import requests
from mac import youtube as Y
from mac.social import PDS, _session


def main() -> None:
    c = json.load(open(sys.argv[1])); bad = 0
    if c.get("youtube"):
        tok = Y.access_token(os.environ["YT_CLIENT_ID"], os.environ["YT_CLIENT_SECRET"], os.environ["YT_REFRESH_TOKEN"])
        for v in c["youtube"]:
            items = Y._call(f"{Y.API}/videos?part=snippet&id={v['id']}", tok)[0].get("items", [])
            if not items:
                print(f"youtube {v['id']}: not found (already gone)"); continue
            if items[0]["snippet"]["title"] != v["title"]:
                print(f"youtube {v['id']}: title mismatch, NOT deleted: {items[0]['snippet']['title']}"); bad += 1; continue
            r = requests.delete(f"{Y.API}/videos", params={"id": v["id"]}, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
            print(f"youtube {v['id']}: {'deleted' if r.status_code == 204 else f'FAILED {r.status_code} {r.text[:300]}'}"); bad += r.status_code != 204
    if c.get("bluesky"):
        s = _session(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"]); h = {"Authorization": f"Bearer {s['accessJwt']}"}
        for rk in c["bluesky"]:
            g = requests.get(f"{PDS}/com.atproto.repo.getRecord", params={"repo": s["did"], "collection": "app.bsky.feed.post", "rkey": rk}, timeout=30)
            if g.status_code != 200:
                print(f"bluesky {rk}: not found (already gone)"); continue
            r = requests.post(f"{PDS}/com.atproto.repo.deleteRecord", headers=h, timeout=30,
                              json={"repo": s["did"], "collection": "app.bsky.feed.post", "rkey": rk})
            print(f"bluesky {rk}: {'deleted' if r.ok else f'FAILED {r.status_code} {r.text[:300]}'} ({g.json()['value'].get('text', '')[:60]!r})"); bad += not r.ok
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
