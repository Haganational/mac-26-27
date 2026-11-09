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
  * the pick's details in data.json and the copy embedded in index.html
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any

LOCKED_PAGES = ("odds.html", "viz.html")
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


def gate_card() -> str:
    return f"""<div class="hb-gate" role="region" aria-label="Access code required">
  <div class="hb-gate-in">
    <span class="hb-gate-k">Bettor's Desk</span>
    <h1>Enter your access code</h1>
    <p>Every book's line, best prices, model gaps and when each book posts. One code unlocks all of it.</p>
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
_BP_BODY = re.compile(r'(<details class="bestplay">.*?)<div class="bp-body">(.*?)</div>\s*</details>', re.S)
_DATA_JSON = re.compile(r'(<script id="data" type="application/json">)(.*?)(</script>)', re.S)


def lock_page(page: str, sealer: Sealer) -> str:
    """Replace <main> with the gate and seal the original body plus the inline scripts that follow it."""
    m = _MAIN.search(page)
    if not m:
        return page
    head, body, tail = page[:m.start()], m.group(2), page[m.end():]
    scripts = _INLINE_SCRIPT.findall(tail)
    tail = _INLINE_SCRIPT.sub("", tail)
    payload = json.dumps({"html": body, "scripts": scripts})
    return f'{head}{m.group(1)}{gate_card()}{_blob_tag(sealer.seal(payload))}{m.group(3)}{tail}'


def lock_best_play(page: str, sealer: Sealer, root: str = "") -> str:
    def sub(m: re.Match) -> str:
        inner = m.group(2)
        return (f'{m.group(1)}<div class="bp-body bp-locked">{_blob_tag(sealer.seal(json.dumps({"html": inner, "scripts": []})))}'
                f'<span class="bp-lock">Access code needed. <a href="{root}odds.html">Enter code</a> or email '
                f'{ask_links()}. 21+ only.</span></div></details>')
    return _BP_BODY.sub(sub, page)


def strip_best_play(data: dict[str, Any]) -> dict[str, Any]:
    bp = data.get("best_play")
    if isinstance(bp, dict):
        data = dict(data, best_play={k: v for k, v in bp.items() if k not in BEST_PLAY_PRIVATE})
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
        new = lock_page(page, sealer) if rel in LOCKED_PAGES else lock_best_play(page, sealer, "../" * rel.count("/"))
        new = _strip_embedded(new)
        if new != page:
            f.write_text(new)
            changed += 1
    dj = site_dir / "data.json"
    if dj.exists():
        dj.write_text(json.dumps(strip_best_play(json.loads(dj.read_text()))))
    print(f"access code: sealed {changed} pages for {len(cs)} code(s)")
    return changed
