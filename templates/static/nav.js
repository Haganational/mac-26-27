/* Site chrome: mobile menu, search (/ or Ctrl+K), share, section links, "On this page" bar. */
(function () {
  const me = document.currentScript;
  const ROOT = (me && me.dataset.root) || '';
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const fold = (s) => String(s).normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();

  /* ---------- toast */
  let toastT;
  function toast(msg) {
    let t = $('#toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('on');
    clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('on'), 1800);
  }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) {
      const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      let ok = false; try { ok = document.execCommand('copy'); } catch (e2) {}
      ta.remove(); return ok;
    }
  }

  /* ---------- mobile menu + teams dropdown */
  const menuBtn = $('.tb-menu-btn'), nav = $('#tbnav');
  if (menuBtn && nav) menuBtn.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  document.addEventListener('click', (e) => {
    $$('details.tb-teams[open]').forEach(d => { if (!d.contains(e.target)) d.open = false; });
    const pop = $('#sharepop');
    if (pop && !pop.hidden && !pop.contains(e.target) && !e.target.closest('[data-share]')) pop.hidden = true;
  });

  /* ---------- share */
  function shareMenu(btn, url, title) {
    let pop = $('#sharepop');
    if (!pop) { pop = document.createElement('div'); pop.id = 'sharepop'; pop.className = 'sharepop'; pop.hidden = true; document.body.appendChild(pop); }
    const u = encodeURIComponent(url), t = encodeURIComponent(title);
    pop.innerHTML = `<div class="sp-title">Share</div><div class="sp-url">${esc(url.replace(/^https?:\/\//, ''))}</div>
      <button type="button" data-act="copy">Copy link</button>
      <a href="sms:?&body=${t}%20${u}">Text message</a>
      <a href="mailto:?subject=${t}&body=${u}">Email</a>
      <a href="https://x.com/intent/post?text=${t}&url=${u}" target="_blank" rel="noopener">Post on X</a>
      <a href="https://bsky.app/intent/compose?text=${t}%20${u}" target="_blank" rel="noopener">Post on Bluesky</a>`;
    pop.querySelector('[data-act=copy]').onclick = async () => { if (await copy(url)) toast('Link copied'); pop.hidden = true; };
    const r = btn.getBoundingClientRect();
    pop.hidden = false;
    const w = pop.offsetWidth;
    pop.style.top = (window.scrollY + r.bottom + 6) + 'px';
    pop.style.left = Math.max(8, Math.min(window.scrollX + r.right - w, window.scrollX + document.documentElement.clientWidth - w - 8)) + 'px';
  }
  document.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-share]');
    if (!b) return;
    e.preventDefault();
    const url = b.dataset.shareUrl || location.href;
    const title = b.dataset.shareTitle || document.title;
    if (navigator.share && matchMedia('(pointer: coarse)').matches) {
      try { await navigator.share({ title, url }); return; } catch (err) { if (err && err.name === 'AbortError') return; }
    }
    shareMenu(b, url, title);
  });

  /* ---------- section links + "On this page" */
  const main = $('main');
  const secs = main ? $$('section[id]', main).filter(s => s.querySelector('h2') && !s.closest('section:not([id]) section')) : [];
  secs.forEach(s => {
    const h = s.querySelector('h2');
    if (h.querySelector('.hlink')) return;
    const a = document.createElement('a');
    a.className = 'hlink'; a.href = '#' + s.id; a.title = 'Copy a link to this section'; a.setAttribute('aria-label', 'Link to ' + h.textContent.trim());
    a.textContent = '#';
    a.onclick = async (e) => {
      e.preventDefault();
      history.replaceState(null, '', '#' + s.id);
      if (await copy(location.href)) toast('Section link copied');
    };
    h.appendChild(a);
  });
  const top = secs.filter(s => !s.parentElement.closest('section'));
  if (main && top.length >= 3) {
    const bar = document.createElement('nav');
    bar.className = 'onpage'; bar.setAttribute('aria-label', 'On this page');
    bar.innerHTML = '<span class="op-k">On this page</span>' + top.map(s => {
      const h = s.querySelector('h2').cloneNode(true); h.querySelectorAll('.hlink, a.btnlink').forEach(x => x.remove());
      return `<a href="#${esc(s.id)}">${esc(h.textContent.trim())}</a>`;
    }).join('');
    let after = $(':scope > .ticker', main) || $(':scope > header', main);
    if (after && after.nextElementSibling && after.nextElementSibling.matches('div.sub')) after = after.nextElementSibling;
    if (after) after.after(bar); else main.prepend(bar);
    if ('IntersectionObserver' in window) {
      let hold = 0;
      const links = new Map($$('a', bar).map(a => [a.getAttribute('href').slice(1), a]));
      const io = new IntersectionObserver((ents) => {
        if (Date.now() < hold) return;
        ents.forEach(en => { if (en.isIntersecting) { links.forEach(a => a.classList.remove('on')); const a = links.get(en.target.id); if (a) { a.classList.add('on'); /* scroll only the bar sideways: scrollIntoView would also move the page and cut a jump short */ const l = a.offsetLeft - bar.offsetLeft, r = l + a.offsetWidth; if (l < bar.scrollLeft || r > bar.scrollLeft + bar.clientWidth) bar.scrollTo({ left: Math.max(0, l - 24) }); } } });
      }, { rootMargin: '-120px 0px -65% 0px' });
      top.forEach(s => io.observe(s));
      // The link you tapped stays lit, even when two sections sit side by side.
      bar.addEventListener('click', (e) => { const a = e.target.closest('a'); if (!a) return; hold = Date.now() + 1500; links.forEach(x => x.classList.remove('on')); a.classList.add('on'); });
    }
  }

  /* ---------- search */
  let index = null, loading = null, sel = 0, results = [];
  const KIND_ORDER = { Team: 0, Page: 1, Player: 2, Coach: 2, Game: 3, Section: 4, TV: 5, Travel: 5, News: 5 };
  function load() {
    if (index) return Promise.resolve(index);
    if (!loading) loading = fetch(ROOT + 'search.json').then(r => r.json()).then(j => {
      index = j.items.map(x => ({ ...x, _t: fold(x.t), _h: x.h || fold(x.t) }));
      return index;
    }).catch(() => { loading = null; return null; });
    return loading;
  }
  function score(it, toks, q) {
    for (const tk of toks) if (!it._h.includes(tk)) return null;
    let s = 0;
    if (it._t === q) s += 100;
    if (it._t.startsWith(q)) s += 40;
    else if (it._t.split(/[\s(]+/).some(w => w.startsWith(toks[0]))) s += 20;
    if (toks.every(tk => it._t.includes(tk))) s += 15;
    s -= (KIND_ORDER[it.k] ?? 6) * 3;
    return s;
  }
  function modal() {
    let m = $('#searchdlg');
    if (m) return m;
    m = document.createElement('div');
    m.id = 'searchdlg'; m.className = 'searchdlg'; m.hidden = true;
    m.innerHTML = `<div class="sd-box" role="dialog" aria-modal="true" aria-label="Search">
      <div class="sd-in"><svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M13 13l4.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      <input type="search" placeholder="Team, player, coach, game, page…" aria-label="Search" autocomplete="off" spellcheck="false"><kbd>Esc</kbd></div>
      <ul class="sd-res" role="listbox"></ul>
      <div class="sd-foot"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open</span><span>Try “Toledo”, “ESPN+”, “odds”, a player or a jersey like “#5”</span></div></div>`;
    document.body.appendChild(m);
    const input = $('input', m), list = $('.sd-res', m);
    m.addEventListener('click', (e) => { if (e.target === m) close(); });
    input.addEventListener('input', () => render(input.value));
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, results.length - 1); paint(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); paint(); }
      else if (e.key === 'Enter') { const r = results[sel]; if (r) { e.preventDefault(); go(r); } }
      else if (e.key === 'Escape') { close(); }
    });
    list.addEventListener('mousemove', (e) => { const li = e.target.closest('li[data-i]'); if (li && +li.dataset.i !== sel) { sel = +li.dataset.i; paint(); } });
    return m;
  }
  function go(r) {
    const url = ROOT + r.u;
    close();
    const here = location.pathname.split('/').pop() || 'index.html';
    const [p, h] = r.u.split('#');
    if (h && ROOT === '' && (p === here)) { location.hash = h; if (p === 'tv.html' || p === 'news.html' || p === 'travel.html') location.reload(); }
    else location.href = url;
  }
  function paint() {
    const list = $('#searchdlg .sd-res');
    $$('li[data-i]', list).forEach(li => li.classList.toggle('on', +li.dataset.i === sel));
    const on = $('li.on', list); if (on) on.scrollIntoView({ block: 'nearest' });
  }
  async function render(qraw) {
    const list = $('#searchdlg .sd-res');
    const q = fold(qraw.trim());
    const idx = await load();
    if (!idx) { list.innerHTML = '<li class="sd-empty">Search needs the published site (it can’t load from a file on disk).</li>'; return; }
    if (!q) {
      results = idx.filter(x => x.k === 'Page' || x.k === 'Team');
    } else {
      const toks = q.split(/\s+/).filter(Boolean);
      results = idx.map(it => [score(it, toks, q), it]).filter(x => x[0] !== null).sort((a, b) => b[0] - a[0]).slice(0, 40).map(x => x[1]);
    }
    sel = 0;
    list.innerHTML = results.length ? results.map((r, i) => `<li data-i="${i}" role="option"><a href="${esc(ROOT + r.u)}" class="${r.c ? 't-' + esc(r.c) : ''}"><span class="sd-k k-${esc(r.k)}">${esc(r.k)}</span><span class="sd-t">${esc(r.t)}${r.s ? `<small>${esc(r.s)}</small>` : ''}</span>${r.c ? '<i class="sd-dot"></i>' : ''}</a></li>`).join('')
      : `<li class="sd-empty">Nothing matches “${esc(qraw)}”.</li>`;
    $$('li[data-i] a', list).forEach((a, i) => a.addEventListener('click', (e) => { e.preventDefault(); go(results[i]); }));
    paint();
  }
  function open(prefill) {
    const m = modal(); m.hidden = false; document.documentElement.classList.add('noscroll');
    const input = $('input', m); input.value = prefill || ''; input.focus(); render(input.value);
  }
  function close() { const m = $('#searchdlg'); if (m) m.hidden = true; document.documentElement.classList.remove('noscroll'); }
  $$('[data-search]').forEach(b => b.addEventListener('click', () => open('')));
  document.addEventListener('keydown', (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
    if ((e.key === '/' && !typing) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k')) { e.preventDefault(); open(''); }
  });
  // Warm the index after load so the first search is instant.
  if ('requestIdleCallback' in window) requestIdleCallback(() => load()); else setTimeout(load, 1500);

})();

// Watch live: swap the click-to-play card for the Twitch player (parent must be this host).
document.addEventListener('click', function (e) {
  var b = e.target.closest('[data-twitch]');
  if (!b) return;
  var f = document.createElement('iframe');
  f.src = 'https://player.twitch.tv/?channel=' + encodeURIComponent(b.dataset.twitch) + '&parent=' + encodeURIComponent(location.hostname || 'localhost') + '&autoplay=true&muted=false';
  f.allowFullscreen = true;
  f.allow = 'autoplay; fullscreen';
  f.title = b.dataset.twitch + ' on Twitch';
  b.replaceWith(f);
});

// MAC90 on Home: swap the card for the YouTube Shorts player (latest upload first).
document.addEventListener('click', function (e) {
  var b = e.target.closest('[data-yt-list]');
  if (!b) return;
  var f = document.createElement('iframe');
  f.src = 'https://www.youtube-nocookie.com/embed/videoseries?list=' + encodeURIComponent(b.dataset.ytList) + '&autoplay=1&playsinline=1&rel=0';
  f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
  f.allowFullscreen = true;
  f.title = 'MAC90 on YouTube';
  b.replaceWith(f);
});

// Access code: locked screens ship as AES-GCM ciphertext (mac/access.py). One code opens all
// of them; it is remembered in this browser so the reader types it once.
(function () {
  var sealed = Array.prototype.slice.call(document.querySelectorAll('script.hb-sealed'));
  if (!sealed.length || !window.crypto || !crypto.subtle) return;
  var KEY = 'hb-access-code', cache = {};
  function bytes(b64) { return Uint8Array.from(atob(b64), function (c) { return c.charCodeAt(0); }); }
  function derive(code, salt, n) {
    var id = salt + ':' + n;
    if (!cache[id]) {
      cache[id] = crypto.subtle.importKey('raw', new TextEncoder().encode(code), 'PBKDF2', false, ['deriveKey']).then(function (base) {
        return crypto.subtle.deriveKey({ name: 'PBKDF2', salt: bytes(salt), iterations: n, hash: 'SHA-256' }, base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
      });
    }
    return cache[id];
  }
  // The page key is wrapped once per access code; try each wrap with the key this code derives.
  function pageKey(kek, wraps) {
    var i = 0;
    function next() {
      if (i >= wraps.length) return Promise.reject(new Error('wrong code'));
      var w = wraps[i++];
      return crypto.subtle.decrypt({ name: 'AES-GCM', iv: bytes(w.i) }, kek, bytes(w.c)).then(function (raw) {
        return crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['decrypt']);
      }, next);
    }
    return next();
  }
  function openOne(el, code) {
    var d = JSON.parse(el.textContent);
    return derive(code, d.s, d.n).then(function (kek) { return pageKey(kek, d.w || []); }).then(function (k) {
      return crypto.subtle.decrypt({ name: 'AES-GCM', iv: bytes(d.i) }, k, bytes(d.c));
    }).then(function (pt) { return JSON.parse(new TextDecoder().decode(pt)); });
  }
  function place(el, p) {
    var host = el.closest('.bp-body') || el.closest('.hb-region') || el.closest('main');
    host.innerHTML = p.html;
    host.classList.remove('bp-locked', 'hb-region');
    p.scripts.forEach(function (src) { var s = document.createElement('script'); s.textContent = src; document.body.appendChild(s); });
  }
  function tryCode(code) {
    cache = {};
    return Promise.all(sealed.map(function (el) { return openOne(el, code); })).then(function (all) {
      all.forEach(function (p, i) { place(sealed[i], p); });
      try { localStorage.setItem(KEY, code); } catch (e) {}
      document.documentElement.classList.add('hb-unlocked');
      if (location.hash) { var t = document.getElementById(location.hash.slice(1)); if (t) t.scrollIntoView(); }
      return true;
    }, function () { return false; });
  }
  var saved = null; try { saved = localStorage.getItem(KEY); } catch (e) {}
  if (saved) tryCode(saved).then(function (ok) { if (!ok) { try { localStorage.removeItem(KEY); } catch (e) {} } });
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('.hb-gate-form');
    if (!f) return;
    e.preventDefault();
    var err = document.querySelector('.hb-gate-err'), btn = f.querySelector('button');
    btn.disabled = true; err.hidden = true;
    tryCode(f.elements.code.value.trim()).then(function (ok) { btn.disabled = false; if (!ok) { err.hidden = false; f.elements.code.select(); } });
  });
})();
