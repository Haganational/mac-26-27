/* Tidy long pages (Nov 21 2026). Three quiet helpers, shared by the edition pages and the hub pages:
   1. "On this page": a sticky row of section chips on any long page with four or more sections (opt out with data-nojump on <main>).
   2. Folds: data-fold="N" on a list (or data-fold-items="selector" for which children count) shows the first N
      and a "Show all" button. Anything a link points at (#hash) or a filter touches (data-fold-off) unfolds first.
   3. Picks: data-pick on a box whose children carry data-pick-name shows one at a time behind a row of chips.
   Plus a small "Top" button once a reader is a few screens down a long page. Nothing here is needed to read a page. */
(function () {
  'use strict';
  var d = document, main = d.querySelector('main') || d.body;
  function txt(el) { var c = el.cloneNode(true); c.querySelectorAll('.hlink,.author-only,.btn-dispatch,.hb-plus,a.btnlink,small').forEach(function (x) { x.remove(); }); return c.textContent.replace(/[#+→]/g, '').replace(/\s+/g, ' ').trim(); }
  function slug(s) { return s.toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'sec'; }
  function barH() { var t = d.querySelector('.topbar'); return t && getComputedStyle(t).position === 'sticky' ? t.getBoundingClientRect().height : 0; }

  /* ---------- 2. folds ---------- */
  function foldItems(box) { var sel = box.getAttribute('data-fold-items'); return [].filter.call(box.children, function (c) { return sel ? c.matches(sel) : !c.classList.contains('td-more'); }); }
  function setFold(box, open) {
    var n = +box.getAttribute('data-fold') || 6, items = foldItems(box), btn = box._tdBtn;
    items.forEach(function (c, i) { c.classList.toggle('td-x', !open && i >= n); });
    box.classList.toggle('td-open', open);
    if (btn) btn.innerHTML = open ? 'Show fewer <span aria-hidden="true">▴</span>' : 'Show all ' + items.length + (box.getAttribute('data-fold-label') ? ' ' + box.getAttribute('data-fold-label') : '') + ' <span aria-hidden="true">▾</span>';
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  d.querySelectorAll('[data-fold]').forEach(function (box) {
    var n = +box.getAttribute('data-fold') || 6, items = foldItems(box);
    if (items.length <= n + 2) return;  /* two extra rows are not worth a button */
    var btn = d.createElement('button'); btn.type = 'button'; btn.className = 'td-more';
    box._tdBtn = btn;
    if (box.getAttribute('data-fold-items')) { var last = items[items.length - 1]; last.parentNode.insertBefore(btn, last.nextSibling); }
    else if (box.matches('ul,ol,table,tbody')) { var host = box.closest('table') || box; host.parentNode.insertBefore(btn, host.nextSibling); }
    else box.appendChild(btn);
    btn.addEventListener('click', function () {
      var open = !box.classList.contains('td-open'); setFold(box, open);
      if (!open) { var r = box.getBoundingClientRect(); if (r.top < 0) window.scrollTo({ top: scrollY + r.top - barH() - 70 }); }
    });
    setFold(box, false);
    var off = box.getAttribute('data-fold-off');
    if (off) d.addEventListener('click', function (e) { if (e.target.closest(off)) setFold(box, true); }, true);
    if (off) d.addEventListener('change', function (e) { if (e.target.closest(off)) setFold(box, true); }, true);
  });
  function reveal() {
    var id = decodeURIComponent(location.hash.slice(1)); if (!id) return;
    var t = d.getElementById(id); if (!t) return;
    var f = t.closest('.td-x'); if (f) { var box = f.parentNode.closest('[data-fold]') || f.parentNode; if (box.hasAttribute('data-fold')) { setFold(box, true); t.scrollIntoView(); } }
    var p = t.closest('[data-pick-name]'); if (p && p._tdShow) p._tdShow();
  }
  window.addEventListener('hashchange', reveal);

  /* ---------- 3. picks ---------- */
  d.querySelectorAll('[data-pick]').forEach(function (box) {
    var kids = [].filter.call(box.children, function (c) { return c.hasAttribute('data-pick-name'); });
    if (kids.length < 4) return;
    var key = 'td-pick-' + (box.id || 'x'), row = d.createElement('div'), btns = [];
    row.className = 'td-pick'; row.setAttribute('role', 'tablist'); row.setAttribute('aria-label', box.getAttribute('data-pick') || 'Show');
    function show(name) {
      kids.forEach(function (k) { k.hidden = name !== '*' && k.getAttribute('data-pick-name') !== name; });
      btns.forEach(function (b) { b.setAttribute('aria-selected', b.dataset.v === name ? 'true' : 'false'); });
      try { localStorage.setItem(key, name); } catch (e) {}
    }
    kids.concat([null]).forEach(function (k) {
      var b = d.createElement('button'); b.type = 'button'; b.setAttribute('role', 'tab');
      b.dataset.v = k ? k.getAttribute('data-pick-name') : '*';
      b.textContent = k ? b.dataset.v : 'All';
      b.addEventListener('click', function () { show(b.dataset.v); });
      btns.push(b); row.appendChild(b);
      if (k) k._tdShow = function () { show(b.dataset.v); };
    });
    box.insertBefore(row, kids[0]);
    var start = box.getAttribute('data-pick-start') || kids[0].getAttribute('data-pick-name');
    try { var saved = localStorage.getItem(key); if (saved && btns.some(function (b) { return b.dataset.v === saved; })) start = saved; } catch (e) {}
    show(start);
  });
  reveal();

  /* ---------- 1. on this page ---------- */
  var tall = d.documentElement.scrollHeight > innerHeight * 3.2;
  if (!main.hasAttribute('data-nojump') && !d.querySelector('.onpage') && tall) {
    var hs = [].filter.call(main.querySelectorAll('h2'), function (h) { return h.offsetParent && !h.closest('[hidden],.tb-menu,.hb-panel,dialog,aside.rail,.td-x') && txt(h); });
    if (hs.length >= 4) {
      var nav = d.createElement('nav'), seen = {};
      nav.className = 'td-jump'; nav.setAttribute('aria-label', 'On this page');
      nav.innerHTML = '<span class="td-k">On this page</span>';
      var targets = hs.map(function (h) {
        var host = h.closest('section') || h, id = host.id || h.id;
        if (!id) { id = slug(txt(h)); while (seen[id] || d.getElementById(id)) id += '-2'; h.id = id; host = h; }
        seen[id] = 1;
        var a = d.createElement('a'); a.href = '#' + id; a.textContent = txt(h).replace(/:.*$/, '').slice(0, 34);
        nav.appendChild(a); return { el: host, a: a };
      });
      /* Sit the row just above the first section, at main's own level. */
      var first = hs[0]; while (first.parentNode && first.parentNode !== main) first = first.parentNode;
      if (first.parentNode === main) main.insertBefore(nav, first); else main.insertBefore(nav, main.firstChild);
      d.documentElement.style.setProperty('--td-top', barH() + 'px');
      var onNow = null;
      function spy() {
        var y = barH() + 90, cur = targets[0];
        targets.forEach(function (t) { if (t.el.getBoundingClientRect().top <= y) cur = t; });
        if (cur !== onNow) { if (onNow) onNow.a.classList.remove('on'); cur.a.classList.add('on'); onNow = cur;
          var l = cur.a.offsetLeft - nav.clientWidth / 2 + cur.a.clientWidth / 2; nav.scrollTo ? nav.scrollTo({ left: l }) : (nav.scrollLeft = l); }
      }
      addEventListener('scroll', function () { requestAnimationFrame(spy); }, { passive: true }); spy();
    }
  }

  /* ---------- the Top button ---------- */
  if (tall) {
    var top = d.createElement('button'); top.type = 'button'; top.className = 'td-top'; top.hidden = true;
    top.setAttribute('aria-label', 'Back to the top'); top.innerHTML = '<span aria-hidden="true">↑</span> Top';
    top.addEventListener('click', function () { scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); });
    d.body.appendChild(top);
    addEventListener('scroll', function () { top.hidden = scrollY < innerHeight * 2.5; }, { passive: true });
  }
})();
