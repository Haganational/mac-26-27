"""Access-code lock for the Bettor's Desk screens.

When the ACCESS_CODE environment variable is set (a repo secret in Actions), the build
encrypts the locked screens after rendering them. ACCESS_CODE may hold several codes, one
per line (or comma-separated); any of them opens everything. Each build picks a random page
key, encrypts the locked content with it (AES-GCM), and stores that key once per code,
wrapped under a key derived from the code with PBKDF2. Without a valid code the content
can't be read from the page source. Delete a code's line to cut that reader off.
The browser remembers the code (localStorage) so a reader types it once.

Without ACCESS_CODE nothing is locked and the site renders exactly as before.

What is locked:
  * every page in LOCKED_PAGES (the whole <main>, plus its inline scripts)
  * the "Best number today" pick, wherever its card appears (the teaser line stays visible)
  * any <!--hb-lock:name--> region (Home's line moves), shown greyed out from its <!--hb-tease--> block
  * the pick's details and line history in data.json and the copy embedded in index.html
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any

LOCKED_PAGES = ("odds.html", "ratings.html", "viz.html", "players.html", "book.html", "travel.html")
PAGE_BLURB = {
    "odds.html": ("Odds", "Every book's line, best prices, open vs now and where the market is off."),
    "ratings.html": ("Ratings", "Power ratings for all 365 D-I teams, projected spreads and totals, and where the model disagrees with the market."),
    "viz.html": ("Data Viz", "When each book posts each game, on a clock that runs to tip-off."),
    "players.html": ("Players", "Box-score ratings for every MAC player, tied to the team model."),
    "book.html": ("Almanac", "Team and player ratings for every D-I conference."),
    "travel.html": ("Travel", "Routes, miles, road trips, rest days and time zones for every team."),
}
REQUEST_EMAILS = ("bernice@hardwoodbricks.com", "info@hardwoodbricks.com")
ELIGIBILITY = ("Not for anyone under 21, anyone taking part in or holding a stake in the games discussed "
               "(players, coaches, staff, officials and their families), or anyone else barred from betting on "
               "or discussing sides and totals. By unlocking, you confirm none of these apply to you.")


def ask_links() -> str:
    subject = "Hardwood%20Bricks%20access%20code"
    return " or ".join(f'<a href="mailto:{e}?subject={subject}">{e}</a>' for e in REQUEST_EMAILS)


ITERATIONS = 150_000
BEST_PLAY_PRIVATE = ("pick", "price", "books", "model", "odds_event_id", "side", "line")


def codes() -> list[str]:
    raw = os.environ.get("ACCESS_CODE") or ""
    out: list[str] = []
    for c in re.split(r"[\n,]", raw):
        c = c.strip()
        if c and not c.startswith("#") and c not in out:
            out.append(c)
    return out


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _kek(access_code: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS).derive(access_code.encode())


class Sealer:
    """Encrypts strings under one random page key per build; that key is wrapped once per code.

    All wraps share one salt, so the browser runs PBKDF2 once and then tries each wrap (cheap)."""

    def __init__(self, access_codes: str | list[str], salt: bytes | None = None):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if isinstance(access_codes, str):
            access_codes = [access_codes]
        self.salt = salt or secrets.token_bytes(16)
        self._key = AESGCM.generate_key(bit_length=256)
        self._aes = AESGCM(self._key)
        self.wraps = []
        for c in access_codes:
            iv = secrets.token_bytes(12)
            self.wraps.append({"i": _b64(iv), "c": _b64(AESGCM(_kek(c, self.salt)).encrypt(iv, self._key, None))})
        secrets.SystemRandom().shuffle(self.wraps)  # order says nothing about which code is whose

    def seal(self, text: str) -> str:
        iv = secrets.token_bytes(12)
        ct = self._aes.encrypt(iv, text.encode(), None)
        return json.dumps({"s": _b64(self.salt), "n": ITERATIONS, "w": self.wraps, "i": _b64(iv), "c": _b64(ct)},
                          separators=(",", ":"))


def open_blob(blob: str, access_code: str) -> str:
    """Decrypt a sealed blob with one code (the browser does the same in nav.js). Raises if the code is wrong."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    d = json.loads(blob)
    kek = AESGCM(_kek(access_code, base64.b64decode(d["s"])))
    for w in d["w"]:
        try:
            key = kek.decrypt(base64.b64decode(w["i"]), base64.b64decode(w["c"]), None)
        except Exception:
            continue
        return AESGCM(key).decrypt(base64.b64decode(d["i"]), base64.b64decode(d["c"]), None).decode()
    raise ValueError("wrong code")


def _blob_tag(blob: str) -> str:
    return f'<script type="application/json" class="hb-sealed">{blob}</script>'


def unlock_list() -> str:
    names = [PAGE_BLURB[p][0] for p in LOCKED_PAGES if p in PAGE_BLURB] + ["line moves"]
    return ", ".join(names[:-1]) + " and " + names[-1]


def gate_card(page: str = "") -> str:
    label, blurb = PAGE_BLURB.get(page, ("Access", ""))
    return f"""<div class="hb-gate" role="region" aria-label="Access code required">
  <div class="hb-gate-in">
    <span class="hb-gate-k">&#128274; {label}</span>
    <h1>Enter your access code</h1>
    <p>{blurb} One code unlocks {unlock_list()}.</p>
    <form class="hb-gate-form" autocomplete="off">
      <input type="password" name="code" placeholder="Access code" aria-label="Access code" required autocapitalize="off" spellcheck="false">
      <button type="submit">Unlock</button>
    </form>
    <p class="hb-gate-err" role="alert" hidden>That code didn't work. Check it and try again.</p>
    <p class="hb-gate-ask">No code yet? Email {ask_links()} and we'll send one.</p>
    <p class="hb-gate-fine"><b>Who can't use it:</b> {ELIGIBILITY} Lines and model numbers are information, not a guarantee.</p>
  </div>
</div>"""


_MAIN = re.compile(r'(<main id="main"[^>]*>)(.*?)(</main>)', re.S)
_INLINE_SCRIPT = re.compile(r"<script>(.*?)</script>", re.S)
_JSON_TAG = re.compile(r'<script id="[^"]+" type="application/json">.*?</script>', re.S)
_BP_BODY = re.compile(r'(<details class="bestplay">.*?)<div class="bp-body">(.*?)</div>\s*</details>', re.S)
_DATA_JSON = re.compile(r'(<script id="data" type="application/json">)(.*?)(</script>)', re.S)


def lock_page(page: str, sealer: Sealer, rel: str = "") -> str:
    """Replace <main> with the gate and seal the original body plus the inline scripts that follow it."""
    m = _MAIN.search(page)
    if not m:
        return page
    head, body, tail = page[:m.start()], m.group(2), page[m.end():]
    data_tags = _JSON_TAG.findall(tail)  # page data (travel routes, the almanac's first table) goes in the envelope too
    tail = _JSON_TAG.sub("", tail)
    scripts = _INLINE_SCRIPT.findall(body) + _INLINE_SCRIPT.findall(tail)
    body = _INLINE_SCRIPT.sub("", body) + "".join(data_tags)
    tail = _INLINE_SCRIPT.sub("", tail)
    payload = json.dumps({"html": body, "scripts": scripts})
    return f'{head}{m.group(1)}{gate_card(rel)}{_blob_tag(sealer.seal(payload))}{m.group(3)}{tail}'


def lock_best_play(page: str, sealer: Sealer, root: str = "") -> str:
    def sub(m: re.Match) -> str:
        inner = m.group(2)
        return (f'{m.group(1)}<div class="bp-body bp-locked">{_blob_tag(sealer.seal(json.dumps({"html": inner, "scripts": []})))}'
                f'<span class="bp-lock">Access code needed. <a href="{root}odds.html">Enter code</a> or email '
                f'{ask_links()}. 21+ only.</span></div></details>')
    return _BP_BODY.sub(sub, page)


_REGION = re.compile(r'<!--hb-lock:(\w+)-->(.*?)<!--/hb-lock-->', re.S)
_TEASE = re.compile(r'<!--hb-tease-->(.*?)<!--/hb-tease-->', re.S)
_PLAIN_SCRIPT = re.compile(r"<script>(.*?)</script>", re.S)


def lock_regions(page: str, sealer: Sealer, root: str = "") -> str:
    """Seal every <!--hb-lock:name--> … <!--/hb-lock--> region; show its <!--hb-tease--> block greyed out instead."""
    def sub(m: re.Match) -> str:
        inner = m.group(2)
        tease = _TEASE.search(inner)
        inner = _TEASE.sub("", inner)
        scripts = _PLAIN_SCRIPT.findall(inner)
        body = _PLAIN_SCRIPT.sub("", inner)
        blob = _blob_tag(sealer.seal(json.dumps({"html": body, "scripts": scripts})))
        return (f'<div class="hb-region hb-{m.group(1)}">{blob}<div class="hb-tease" aria-hidden="true">{tease.group(1) if tease else ""}</div>'
                f'<div class="hb-tease-lock"><b>&#128274; Behind the access wall</b><span><a href="{root}odds.html">Enter your code</a> or email {ask_links()}.</span></div></div>')
    return _REGION.sub(sub, page)


def strip_best_play(data: dict[str, Any]) -> dict[str, Any]:
    bp = data.get("best_play")
    if isinstance(bp, dict):
        data = dict(data, best_play={k: v for k, v in bp.items() if k not in BEST_PLAY_PRIVATE})
    if "history" in data:
        data = dict(data, history=[])
    return data


def _strip_embedded(page: str) -> str:
    def sub(m: re.Match) -> str:
        try:
            d = json.loads(m.group(2).replace("<\\/", "</"))
        except ValueError:
            return m.group(0)
        return m.group(1) + json.dumps(strip_best_play(d)).replace("</", "<\\/") + m.group(3)
    return _DATA_JSON.sub(sub, page)


def lock_site(site_dir: Path) -> int:
    """Seal the locked screens in a rendered site. Returns how many pages changed."""
    cs = codes()
    if not cs:
        return 0
    sealer = Sealer(cs)
    changed = 0
    for f in site_dir.rglob("*.html"):
        rel = f.relative_to(site_dir).as_posix()
        if rel == "desk.html":
            continue
        page = f.read_text()
        root = "../" * rel.count("/")
        new = lock_page(page, sealer, rel) if rel in LOCKED_PAGES else lock_regions(lock_best_play(page, sealer, root), sealer, root)
        new = _strip_embedded(new)
        if new != page:
            f.write_text(new)
            changed += 1
    dj = site_dir / "data.json"
    if dj.exists():
        dj.write_text(json.dumps(strip_best_play(json.loads(dj.read_text()))))
    print(f"access code: sealed {changed} pages for {len(cs)} code(s)")
    return changed
