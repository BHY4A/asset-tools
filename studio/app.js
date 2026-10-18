/* Студия ассетов: интерфейс. Считает движок — Python в веб-воркере (GitHub Pages) или локальный studio.py. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const el = (tag, attrs = {}, ...kids) => { const e = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) { if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v === true ? '' : v); } for (const c of kids) if (c != null) e.append(c); return e; };
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* хранилище недоступно */ } } };
  const toast = (msg, err) => { const t = $('#toast'); t.textContent = msg; t.className = 'toast' + (err ? ' err' : ''); t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, err ? 6000 : 2600); };
  const rndSeed = () => Math.floor(Math.random() * 999999) + 1;

  /* ---------- движок ---------- */
  const Engine = {
    mode: null, worker: null, seq: 0, wait: new Map(),
    async init() {
      if (/^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname)) try {
        const r = await fetch('api/ping', { cache: 'no-store' });
        if (r.ok && (await r.json()).engine === 'native') { this.mode = 'native'; return 'native'; }
      } catch (e) { /* не локальный сервер — работаем в браузере */ }
      this.mode = 'browser';
      return new Promise((resolve, reject) => {
        this.worker = new Worker('studio/worker.js');
        this.worker.onmessage = (ev) => {
          const m = ev.data;
          if (m.type === 'status') bootStatus(m.text, m.pct);
          else if (m.type === 'ready') resolve('browser');
          else if (m.type === 'fail') reject(new Error(m.error));
          else if (m.type === 'result') { const w = this.wait.get(m.id); if (w) { this.wait.delete(m.id); w(m); } }
        };
        this.worker.onerror = (e) => reject(new Error(e.message || 'ошибка воркера'));
      });
    },
    async call(cmd, args = {}, blobs = []) {
      let res;
      if (this.mode === 'native') {
        const b64 = await Promise.all(blobs.map(bytesToB64));
        const r = await fetch('api/call', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cmd, args, blobs: b64 }) });
        const j = await r.json(); res = { result: j.result, blobs: j.blobs.map(b64ToBytes) };
      } else {
        const id = ++this.seq;
        res = await new Promise((resolve) => { this.wait.set(id, resolve); this.worker.postMessage({ id, cmd, args, blobs }, blobs.map((b) => b.buffer)); });
      }
      if (res.result && res.result.error) { const e = new Error(res.result.error); e.trace = res.result.trace; throw e; }
      return res;
    }
  };
  function bytesToB64(u8) { return new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(',')[1]); fr.readAsDataURL(new Blob([u8])); }); }
  function b64ToBytes(s) { const bin = atob(s); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
  const MIME = { png: 'image/png', jpg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif', zip: 'application/zip' };
  const blobUrl = (u8, fmt) => URL.createObjectURL(new Blob([u8], { type: MIME[fmt] || 'application/octet-stream' }));
  function bootStatus(text, pct) { $('#boot-text').textContent = text; $('#boot-bar').style.width = (pct || 0) + '%'; $('#engine').textContent = text; }

  /* ---------- состояние ---------- */
  let TOOLS = {}, ORDER = [];
  const S = { steps: [], sel: 0, photo: null, view: 'frame', mock: 'none', locks: {}, amount: .5 };
  const H = { list: [], pos: -1 };
  let photoBytes = null, lastUrl = null, beforeUrl = null, rendering = false, again = false, timer = 0;

  const tool = (s) => TOOLS[s.tool];
  const cur = () => S.steps[S.sel];
  const persist = () => store.set('at-studio', { steps: S.steps, sel: S.sel, view: S.view, mock: S.mock, locks: S.locks, amount: S.amount });
  const defaults = (t) => Object.fromEntries(t.params.map((p) => [p.name, p.default]));
  function newStep(id) { const t = TOOLS[id]; return { tool: id, params: defaults(t), seed: rndSeed(), on: true }; }

  /* ---------- цепочка ---------- */
  function renderSteps() {
    const ol = $('#steps'); ol.textContent = '';
    S.steps.forEach((s, i) => {
      const t = tool(s);
      const li = el('li', { class: 'step' + (s.on ? '' : ' off'), 'aria-current': i === S.sel ? 'true' : 'false', tabindex: 0, onclick: () => { S.sel = i; renderSteps(); renderParams(); persist(); },
        onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); li.click(); } } },
        el('span', { class: 'n', text: i + 1 }),
        el('span', { class: 't' }, el('b', {}, t.title, el('span', { class: 'k' + (t.kind === 'filter' ? ' f' : ''), text: t.kind === 'filter' ? 'фильтр' : 'генератор' })), el('small', { text: summary(s) })),
        el('span', { class: 'ops' },
          el('button', { title: s.on ? 'Выключить шаг' : 'Включить шаг', 'aria-label': s.on ? 'Выключить шаг' : 'Включить шаг', text: s.on ? '◉' : '○', onclick: (e) => { e.stopPropagation(); s.on = !s.on; changed(true); } }),
          el('button', { title: 'Выше', 'aria-label': 'Выше', text: '↑', disabled: i === 0, onclick: (e) => { e.stopPropagation(); move(i, -1); } }),
          el('button', { title: 'Ниже', 'aria-label': 'Ниже', text: '↓', disabled: i === S.steps.length - 1, onclick: (e) => { e.stopPropagation(); move(i, 1); } }),
          el('button', { title: 'Удалить шаг', 'aria-label': 'Удалить шаг', text: '✕', onclick: (e) => { e.stopPropagation(); S.steps.splice(i, 1); S.sel = Math.max(0, Math.min(S.sel, S.steps.length - 1)); changed(true); } })));
      ol.append(li);
    });
    const first = S.steps.find((s) => s.on);
    const needPhoto = first && tool(first).kind === 'filter';
    $('#chain-hint').textContent = !S.steps.length ? 'Добавьте генератор, чтобы нарисовать с нуля, или фильтр — чтобы обработать фото.' :
      needPhoto && !S.photo ? 'Первый шаг — фильтр: нужно фото (перетащите на холст).' : 'Генератор рисует с нуля, фильтры дальше по цепочке обрабатывают результат.';
    $('#drop').hidden = !(needPhoto && !S.photo);
    const last = [...S.steps].reverse().find((s) => s.on);
    $('#view-tile').hidden = !(last && tool(last).flags && tool(last).flags.tile);
    if ($('#view-tile').hidden && S.view === 'tile') setView('frame');
  }
  function presetOf(s) {
    const t = tool(s); const p = t.presetValues || {}; const d = defaults(t);
    return Object.keys(p).find((k) => t.params.every((x) => JSON.stringify(s.params[x.name]) === JSON.stringify(x.name in p[k] ? p[k][x.name] : d[x.name])));
  }
  function summary(s) {
    const t = tool(s); const name = presetOf(s);
    const diff = t.params.filter((x) => JSON.stringify(s.params[x.name]) !== JSON.stringify(x.default)).length;
    return (name ? 'пресет «' + name + '»' : diff ? 'изменено параметров: ' + diff : 'по умолчанию') + ' · зерно ' + s.seed;
  }
  function move(i, d) { const j = i + d; [S.steps[i], S.steps[j]] = [S.steps[j], S.steps[i]]; S.sel = j; changed(true); }

  /* ---------- параметры ---------- */
  function fmtVal(p, v) { if (p.kind === 'float') { const span = Math.abs(p.hi - p.lo); return (+v).toFixed(span <= 2 ? 2 : span <= 20 ? 1 : 0); } return String(v); }
  function renderParams() {
    const box = $('#params'); box.textContent = '';
    const s = cur(); if (!s) return;
    const t = tool(s); const locks = S.locks[s.tool] || (S.locks[s.tool] = []);
    box.append(el('div', { class: 'p-head' }, el('b', { text: t.title }), el('p', { text: t.about })));
    const preset = el('select', { id: 'preset', onchange: () => { if (!preset.value) return; s.params = Object.assign(defaults(t), t.presetValues[preset.value]); changed(true); } },
      el('option', { value: '', text: '— пресет —' }), ...t.presets.map((n) => el('option', { value: n, text: n, selected: n === presetOf(s) })));
    const seed = el('input', { type: 'number', id: 'seed', value: s.seed, min: 1, onchange: () => { s.seed = Math.max(1, parseInt(seed.value) || 1); changed(true); } });
    const amt = el('input', { type: 'range', min: .05, max: 1, step: .05, value: S.amount, 'aria-label': 'Сила случайности', oninput: () => { S.amount = +amt.value; out.value = (+amt.value).toFixed(2); persist(); } });
    const out = el('output', { text: (+S.amount).toFixed(2) });
    box.append(el('div', { class: 'p-tools' },
      el('label', {}, 'Пресет', preset),
      el('label', {}, 'Зерно', el('span', { class: 'seed' }, seed, el('button', { class: 'btn', title: 'Новое зерно: другая раскладка при тех же параметрах (N)', 'aria-label': 'Новое зерно', text: '↻', onclick: () => { s.seed = rndSeed(); changed(true); } }))),
      el('div', { class: 'rnd' }, el('button', { class: 'btn pri sm', title: 'Случайные параметры этого шага (R). Сила: 1 — что угодно, 0.2 — рядом с текущим', text: '🎲 Случайно', onclick: () => randomize() }), amt, out,
        el('button', { class: 'btn sm', title: '9 вариантов вокруг текущего (V)', text: '×9', onclick: () => setView('grid') }))));
    const groups = {}; t.params.forEach((p) => (groups[p.group || 'прочее'] = groups[p.group || 'прочее'] || []).push(p));
    const open = store.get('at-open', {});
    Object.entries(groups).forEach(([g, ps], gi) => {
      const key = s.tool + ':' + g;
      const d = el('details', { class: 'g', open: open[key] !== undefined ? open[key] : gi < 3, ontoggle: () => { open[key] = d.open; store.set('at-open', open); } }, el('summary', { text: g }));
      ps.forEach((p) => d.append(paramRow(s, t, p, locks)));
      box.append(d);
    });
  }
  function paramRow(s, t, p, locks) {
    const id = 'p-' + p.name; const v = s.params[p.name];
    const lock = el('button', { class: 'lock', 'aria-pressed': locks.includes(p.name) ? 'true' : 'false', title: 'Не менять при «Случайно»', 'aria-label': 'Закрепить ' + (p.help || p.name), text: '🔒',
      onclick: () => { const i = locks.indexOf(p.name); if (i >= 0) locks.splice(i, 1); else locks.push(p.name); lock.setAttribute('aria-pressed', i >= 0 ? 'false' : 'true'); persist(); } });
    if (p.rand === false && !locks.includes(p.name)) lock.style.visibility = 'hidden';
    const label = el('label', { class: 'l', for: id }, p.help || p.name, el('code', { text: p.name }));
    const row = el('div', { class: 'prm' + (JSON.stringify(v) !== JSON.stringify(p.default) ? ' changed' : '') });
    const set = (val) => { s.params[p.name] = val; row.classList.toggle('changed', JSON.stringify(val) !== JSON.stringify(p.default)); queue(); scheduleHistory(); };
    if (p.kind === 'int' || p.kind === 'float') {
      const val = el('span', { class: 'v', text: fmtVal(p, v) });
      const step = p.step || (p.kind === 'int' ? 1 : (p.hi - p.lo) / 200);
      const r = el('input', { type: 'range', id, min: p.lo, max: p.hi, step, value: v, oninput: () => { const x = p.kind === 'int' ? parseInt(r.value) : parseFloat(r.value); val.textContent = fmtVal(p, x); set(x); } });
      r.addEventListener('dblclick', () => { r.value = p.default; val.textContent = fmtVal(p, p.default); set(p.default); });
      row.append(label, val, lock, r);
    } else if (p.kind === 'choice') {
      row.classList.add('span-c');
      const sel = el('select', { id, onchange: () => set(sel.value) }, ...p.choices.map((c) => el('option', { value: c, text: c, selected: c === v })));
      row.append(label, lock, sel);
    } else if (p.kind === 'bool') {
      row.classList.add('span-c');
      const cb = el('input', { type: 'checkbox', id, checked: !!v, onchange: () => set(cb.checked) });
      row.append(el('label', { class: 'l', for: id }, cb, ' ', p.help || p.name, el('code', { text: p.name })), lock);
    } else if (p.kind === 'color') {
      row.classList.add('span-c');
      const tx = el('input', { type: 'text', id, value: v, spellcheck: 'false' }); const col = el('input', { type: 'color', value: /^#[0-9a-f]{6}$/i.test(v) ? v : '#000000', 'aria-label': 'Выбрать цвет' });
      col.addEventListener('input', () => { tx.value = col.value; set(col.value); });
      tx.addEventListener('change', () => { if (/^#[0-9a-f]{6}$/i.test(tx.value)) col.value = tx.value; set(tx.value); });
      row.append(label, lock, el('span', { class: 'colrow' }, col, tx));
    } else {
      row.classList.add('span-c');
      const tx = el('input', { type: 'text', id, value: v, spellcheck: 'false', onchange: () => set(tx.value) });
      row.append(label, lock, tx);
    }
    return row;
  }

  /* ---------- случайность и варианты ---------- */
  async function randomize() {
    const s = cur(); if (!s) return;
    try {
      const seed = rndSeed();
      const r = await Engine.call('random', { tool: s.tool, params: s.params, amount: S.amount, lock: S.locks[s.tool] || [], seed });
      s.params = r.result.params; s.seed = seed; changed(true);
    } catch (e) { toast(e.message, true); }
  }
  let gridToken = 0;
  async function buildGrid() {
    const s = cur(); const box = $('#grid'); box.textContent = ''; if (!s) return;
    const token = ++gridToken; const cells = [];
    for (let i = 0; i < 9; i++) { const c = el('button', { class: 'cell wait', 'aria-label': 'Вариант ' + (i + 1) }); box.append(c); cells.push(c); }
    const side = Math.min(520, Math.round(Math.max(box.clientWidth / 3, box.clientHeight / 3) * (window.devicePixelRatio || 1)));
    for (let i = 0; i < 9; i++) {
      if (token !== gridToken) return;
      try {
        const seed = rndSeed();
        const params = i === 4 ? s.params : (await Engine.call('random', { tool: s.tool, params: s.params, amount: S.amount, lock: S.locks[s.tool] || [], seed })).result.params;
        const steps = S.steps.map((x, k) => k === S.sel ? Object.assign({}, x, { params, seed: i === 4 ? x.seed : seed }) : x);
        const r = await Engine.call('render', { steps, max_side: side, fmt: 'jpg', quality: 82 });
        if (token !== gridToken) return;
        const c = cells[i]; c.classList.remove('wait'); c.textContent = '';
        c.append(el('img', { src: blobUrl(r.blobs[0], r.result.fmt), alt: '' }), el('span', { text: i === 4 ? 'текущий' : '#' + (i + 1) }));
        c.onclick = () => { s.params = params; if (i !== 4) s.seed = seed; setView('frame'); changed(true); toast('Вариант выбран. «×9» снова — варианты уже вокруг него'); };
      } catch (e) { cells[i].classList.remove('wait'); cells[i].textContent = '—'; if (i === 0) { toast(e.message, true); return; } }
    }
  }

  /* ---------- отрисовка ---------- */
  function queue() { clearTimeout(timer); timer = setTimeout(render, 140); }
  function previewSide() {
    const c = $('#canvas'); const dpr = Math.min(2, window.devicePixelRatio || 1);
    const cap = Engine.mode === 'native' ? 1800 : 1100;
    return Math.max(320, Math.min(cap, Math.round(Math.max(c.clientWidth, c.clientHeight) * dpr)));
  }
  async function render() {
    if (!S.steps.length) { $('#out').removeAttribute('src'); $('#info').textContent = ''; return; }
    const first = S.steps.find((s) => s.on); if (first && tool(first).kind === 'filter' && !S.photo) return;
    if (rendering) { again = true; return; }
    rendering = true; $('#busy').hidden = false;
    try {
      const r = await Engine.call('render', { steps: S.steps, max_side: previewSide(), fmt: 'jpg', quality: 90 });
      const url = blobUrl(r.blobs[0], r.result.fmt); if (lastUrl) URL.revokeObjectURL(lastUrl); lastUrl = url;
      $('#out').src = url; $('#tile').style.backgroundImage = 'url(' + url + ')';
      const i = r.result; let txt = `${i.w}×${i.h} · ${i.ms} мс · ${Engine.mode === 'native' ? 'Python на компьютере' : 'Python в браузере'}`;
      $('#info').textContent = txt;
      if (i.seam !== undefined) $('#info').append(' · стык: ', el('span', { class: i.seam < .05 ? 'good' : 'bad', text: i.seam < .05 ? 'незаметен' : 'заметен (' + Math.round(i.seam * 100) + '%)' }));
      if (S.view === 'compare') await renderBefore();
      const hi = H.list[H.pos]; if (hi && !hi.thumb) $('#out').addEventListener('load', () => { hi.thumb = thumb(); renderHist(); }, { once: true });
      if (S.view === 'tile') $('#tile').style.backgroundSize = (i.w / (window.devicePixelRatio || 1) / 1) + 'px';
    } catch (e) { toast('Ошибка: ' + e.message, true); console.error(e.trace || e); }
    finally { rendering = false; $('#busy').hidden = true; if (again) { again = false; render(); } }
  }
  async function renderBefore() {
    const on = S.steps.filter((s) => s.on);
    let url;
    if (on.length <= 1) {
      if (S.photo && tool(on[0]).kind === 'filter') url = S.photo.url; else { $('#before').removeAttribute('src'); return; }
    } else {
      const r = await Engine.call('render', { steps: S.steps, max_side: previewSide(), fmt: 'jpg', quality: 88, upto: on.length - 1 });
      url = blobUrl(r.blobs[0], r.result.fmt);
    }
    if (beforeUrl && beforeUrl !== (S.photo && S.photo.url)) URL.revokeObjectURL(beforeUrl);
    beforeUrl = url; $('#before').src = url;
  }

  /* ---------- история ---------- */
  let histTimer = 0;
  function snapshot() { return JSON.stringify({ steps: S.steps, sel: S.sel }); }
  function pushHistory() {
    const snap = snapshot(); if (H.list[H.pos] && H.list[H.pos].snap === snap) return;
    H.list = H.list.slice(0, H.pos + 1); H.list.push({ snap, thumb: null }); if (H.list.length > 40) H.list.shift(); H.pos = H.list.length - 1;
    const item = H.list[H.pos]; setTimeout(() => { item.thumb = thumb(); renderHist(); }, 900);
    renderHist(); updUndo();
  }
  function thumb() {
    const img = $('#out'); if (!img.naturalWidth) return null;
    const c = document.createElement('canvas'); const k = 104 / Math.max(img.naturalWidth, img.naturalHeight);
    c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
    try { c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); return c.toDataURL('image/jpeg', .7); } catch (e) { return null; }
  }
  function scheduleHistory() { clearTimeout(histTimer); histTimer = setTimeout(pushHistory, 700); persist(); }
  function restore(i) { if (i < 0 || i >= H.list.length) return; H.pos = i; const d = JSON.parse(H.list[i].snap); S.steps = d.steps; S.sel = d.sel; renderSteps(); renderParams(); persist(); queue(); renderHist(); updUndo(); }
  function renderHist() {
    const row = $('#hist'); row.textContent = '';
    H.list.forEach((h, i) => row.append(el('button', { 'aria-label': 'Состояние ' + (i + 1), 'aria-current': i === H.pos ? 'true' : 'false', style: h.thumb ? `background-image:url(${h.thumb})` : '', onclick: () => restore(i) })));
    row.scrollLeft = row.scrollWidth;
  }
  function updUndo() { $('#undo').disabled = H.pos <= 0; $('#redo').disabled = H.pos >= H.list.length - 1; }
  function changed(hist) { renderSteps(); renderParams(); persist(); queue(); if (S.view === 'grid') setView('frame'); if (hist) { clearTimeout(histTimer); histTimer = setTimeout(pushHistory, 250); } }

  /* ---------- виды ---------- */
  function setView(v) {
    S.view = v; persist();
    $$('[data-view]').forEach((b) => b.setAttribute('aria-checked', b.dataset.view === v ? 'true' : 'false'));
    $('#frame').hidden = v === 'grid' || v === 'tile'; $('#grid').hidden = v !== 'grid'; $('#tile').hidden = v !== 'tile';
    $('#cmp').hidden = v !== 'compare'; $('#frame').classList.toggle('cmp-on', v === 'compare');
    if (v === 'grid') buildGrid(); else gridToken++;
    if (v === 'compare') renderBefore().catch((e) => toast(e.message, true));
    if (v === 'tile') { const img = $('#out'); $('#tile').style.backgroundSize = (img.naturalWidth / (window.devicePixelRatio || 1)) + 'px'; }
  }
  function setMock(m) {
    S.mock = m; persist(); $$('[data-mock]').forEach((b) => b.setAttribute('aria-checked', b.dataset.mock === m ? 'true' : 'false'));
    $('#mock').hidden = m === 'none'; $('#mock').classList.toggle('dark', m === 'dark');
  }
  function cmpDrag(e) {
    const r = $('#frame').getBoundingClientRect(); const x = Math.max(0, Math.min(1, ((e.touches ? e.touches[0].clientX : e.clientX) - r.left) / r.width));
    $('#cmp').style.clipPath = `inset(0 ${(1 - x) * 100}% 0 0)`; $('#cmp-line').style.left = x * 100 + '%';
  }

  /* ---------- фото ---------- */
  async function setPhoto(file) {
    if (!file || !/^image\//.test(file.type)) { toast('Это не изображение', true); return; }
    const buf = new Uint8Array(await file.arrayBuffer());
    try {
      const r = await Engine.call('photo', { name: file.name }, [buf.slice()]);
      if (S.photo) URL.revokeObjectURL(S.photo.url);
      S.photo = { name: file.name, url: URL.createObjectURL(file), w: r.result.w, h: r.result.h }; photoBytes = buf;
      toast(`Фото ${file.name}: ${r.result.w}×${r.result.h}`);
      if (!S.steps.length) { S.steps.push(newStep('signal')); S.sel = 0; }
      changed(true);
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- сохранение, рецепты ---------- */
  function download(u8, name, fmt) { const a = el('a', { href: blobUrl(u8, fmt), download: name }); document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); }
  const baseName = () => (S.photo ? S.photo.name.replace(/\.[^.]+$/, '') + '-' : '') + S.steps.filter((s) => s.on).map((s) => s.tool).join('+');
  async function saveFull() {
    if (!S.steps.length) return;
    toast('Считаю в полном размере…');
    try {
      const fmt = $('#fmt').value; const r = await Engine.call('render', { steps: S.steps, max_side: 0, fmt, quality: 92 });
      download(r.blobs[0], baseName() + '.' + r.result.fmt, r.result.fmt);
      download(new TextEncoder().encode(recipeJson()), baseName() + '.json', 'json');
      toast(`Сохранено: ${r.result.w}×${r.result.h} + рецепт .json`);
    } catch (e) { toast(e.message, true); }
  }
  const recipeJson = () => JSON.stringify({ kind: 'assetkit-recipe', version: 1, steps: S.steps }, null, 1);
  function openRecipe(text) {
    let d; try { d = JSON.parse(text); } catch (e) { toast('Не получилось прочитать .json', true); return; }
    let steps = Array.isArray(d) ? d : d.steps ? d.steps : d.tool ? [{ tool: d.tool, params: d.params || {}, seed: d.seed || 7 }] : null;
    if (!steps) { toast('В файле нет шагов', true); return; }
    const ids = Object.keys(TOOLS); const bySpec = Object.fromEntries(ORDER.map((t) => [t.tool, t.id]));
    steps = steps.map((s) => { const id = ids.includes(s.tool) ? s.tool : bySpec[s.tool]; if (!id) throw new Error('неизвестный инструмент ' + s.tool); return { tool: id, params: Object.assign(defaults(TOOLS[id]), s.params || {}), seed: s.seed || 7, on: s.on !== false }; });
    S.steps = steps; S.sel = 0; changed(true); toast('Рецепт открыт');
  }

  /* ---------- диалоги ---------- */
  function openAdd() {
    const mk = (t) => el('button', { type: 'button', onclick: () => { S.steps.push(newStep(t.id)); S.sel = S.steps.length - 1; $('#add-dlg').close(); changed(true); } },
      el('span', { class: 'ic' + (t.kind === 'filter' ? ' f' : ''), text: t.title.trim()[0] }), el('span', {}, el('b', { text: t.title }), el('small', { text: t.about })));
    $('#pick-gen').replaceChildren(...ORDER.filter((t) => t.kind === 'gen').map(mk));
    $('#pick-flt').replaceChildren(...ORDER.filter((t) => t.kind === 'filter').map(mk));
    $('#add-dlg').showModal();
  }
  const MODE_HINT = { 'фаза': 'Петля по фазе: сетка «Эфира» едет, неон мигает, волны бегут. Последний кадр стыкуется с первым.', 'зерно': 'Меняется только зерно: брызги, шум, снег живут, композиция на месте.', 'переход': 'Числовые параметры выбранного шага плавно уходят к случайным и возвращаются.' };
  async function openAnim() {
    if (!S.steps.length) return;
    const r = await Engine.call('anim_modes', { steps: S.steps }); const sel = $('#anim-mode');
    sel.replaceChildren(...r.result.modes.map((m) => el('option', { value: m, text: m })));
    const upd = () => { $('#anim-mode-hint').textContent = MODE_HINT[sel.value] || ''; $('#anim-amt-l').hidden = sel.value !== 'переход'; };
    sel.onchange = upd; upd(); $('#anim-dl').hidden = true; $('#anim-img').hidden = true; $('#anim-dlg').showModal();
  }
  async function makeAnim() {
    const mode = $('#anim-mode').value; const fmt = $('#anim-fmt').value; const s = cur();
    let target = null;
    if (mode === 'переход') target = (await Engine.call('random', { tool: s.tool, params: s.params, amount: +$('#anim-amt').value, lock: S.locks[s.tool] || [], seed: rndSeed() })).result.params;
    $('#anim-prog').hidden = false; $('#anim-prog i').style.width = '30%'; $('#anim-go').disabled = true;
    try {
      const r = await Engine.call('anim', { steps: S.steps, n: +$('#anim-n').value, fps: +$('#anim-fps').value, mode, fmt, max_side: +$('#anim-size').value, step_index: S.sel, target });
      const url = blobUrl(r.blobs[0], fmt); $('#anim-img').src = url; $('#anim-img').hidden = false;
      const a = $('#anim-dl'); a.href = url; a.download = baseName() + '-' + mode + '.' + fmt; a.hidden = false;
    } catch (e) { toast(e.message, true); }
    finally { $('#anim-prog').hidden = true; $('#anim-go').disabled = false; }
  }
  async function makeBatch() {
    const files = Array.from($('#batch-files').files); if (!files.length) return;
    $('#batch-prog').hidden = false; $('#batch-go').disabled = true; $('#batch-prog i').style.width = '20%';
    try {
      const blobs = await Promise.all(files.map(async (f) => new Uint8Array(await f.arrayBuffer())));
      const r = await Engine.call('batch', { steps: S.steps, names: files.map((f) => f.name), fmt: $('#batch-fmt').value }, blobs);
      $('#batch-prog i').style.width = '100%';
      const a = $('#batch-dl'); a.href = blobUrl(r.blobs[0], 'zip'); a.hidden = false; toast(`Готово: ${r.result.count} шт.`);
      if (photoBytes) await Engine.call('photo', { name: S.photo.name }, [photoBytes.slice()]);
    } catch (e) { toast(e.message, true); }
    finally { $('#batch-go').disabled = false; setTimeout(() => { $('#batch-prog').hidden = true; }, 800); }
  }

  /* ---------- запуск ---------- */
  function bind() {
    $('#add-step').onclick = openAdd;
    $('#undo').onclick = () => restore(H.pos - 1); $('#redo').onclick = () => restore(H.pos + 1);
    $('#photo-btn').onclick = () => $('#photo-file').click(); $('#photo-file').onchange = (e) => setPhoto(e.target.files[0]);
    $('#save').onclick = saveFull;
    $('#theme').onclick = () => { const r = document.documentElement; const curT = r.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); const nx = curT === 'dark' ? 'light' : 'dark'; r.setAttribute('data-theme', nx); store.set('at-theme-x', nx); try { localStorage.setItem('at-theme', nx); } catch (e) { /* нет хранилища */ } };
    const mb = $('#more-btn'), mm = $('#more-menu');
    const closeMenu = () => { mm.hidden = true; mb.setAttribute('aria-expanded', 'false'); };
    mb.onclick = (e) => { e.stopPropagation(); mm.hidden = !mm.hidden; mb.setAttribute('aria-expanded', String(!mm.hidden)); if (!mm.hidden) mm.querySelector('button').focus(); };
    document.addEventListener('click', (e) => { if (!mm.contains(e.target)) closeMenu(); });
    mm.addEventListener('keydown', (e) => { const items = $$('button', mm); const i = items.indexOf(document.activeElement); if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); } if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); } if (e.key === 'Escape') { closeMenu(); mb.focus(); } });
    mm.onclick = async (e) => {
      const act = e.target.dataset.act; if (!act) return; closeMenu();
      if (act === 'recipe-save') download(new TextEncoder().encode(recipeJson()), (baseName() || 'recipe') + '.json', 'json');
      if (act === 'recipe-open') $('#recipe-file').click();
      if (act === 'batch') { $('#batch-dl').hidden = true; $('#batch-dlg').showModal(); }
      if (act === 'anim') openAnim().catch((er) => toast(er.message, true));
      if (act === 'clear-photo') { await Engine.call('clear_photo'); if (S.photo) URL.revokeObjectURL(S.photo.url); S.photo = null; photoBytes = null; changed(false); }
      if (act === 'reset') { S.steps = [newStep('ether')]; S.sel = 0; changed(true); }
    };
    $('#recipe-file').onchange = async (e) => { const f = e.target.files[0]; if (f) openRecipe(await f.text()); e.target.value = ''; };
    $('#anim-go').onclick = makeAnim;
    $('#batch-files').onchange = (e) => { const n = e.target.files.length; $('#batch-count').textContent = n ? 'Выбрано фото: ' + n : 'Выберите фото…'; $('#batch-go').disabled = !n; };
    $('#batch-go').onclick = makeBatch;
    $$('[data-view]').forEach((b) => (b.onclick = () => setView(b.dataset.view)));
    $$('[data-mock]').forEach((b) => (b.onclick = () => setMock(b.dataset.mock)));
    const fr = $('#frame'); let drag = false;
    fr.addEventListener('pointerdown', (e) => { if (S.view === 'compare') { drag = true; fr.setPointerCapture(e.pointerId); cmpDrag(e); } });
    fr.addEventListener('pointermove', (e) => { if (drag) cmpDrag(e); }); fr.addEventListener('pointerup', () => { drag = false; });
    const cv = $('#canvas');
    cv.addEventListener('dragover', (e) => { e.preventDefault(); $('#drop').hidden = false; $('#drop').classList.add('on'); });
    cv.addEventListener('dragleave', (e) => { if (!cv.contains(e.relatedTarget)) { $('#drop').classList.remove('on'); renderSteps(); } });
    cv.addEventListener('drop', (e) => { e.preventDefault(); $('#drop').classList.remove('on'); const f = e.dataTransfer.files[0]; if (f && /json/.test(f.type + f.name)) f.text().then(openRecipe); else setPhoto(f); });
    document.addEventListener('paste', (e) => { const it = Array.from(e.clipboardData.items).find((x) => x.type.startsWith('image/')); if (it) setPhoto(it.getAsFile()); });
    document.addEventListener('keydown', (e) => {
      const typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName) && document.activeElement.type !== 'range';
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); restore(e.shiftKey ? H.pos + 1 : H.pos - 1); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); restore(H.pos + 1); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveFull(); }
      else if (!typing && !e.ctrlKey && !e.metaKey && !e.altKey && !document.querySelector('dialog[open]')) {
        if (e.key === 'r' || e.key === 'к') randomize();
        if (e.key === 'n' || e.key === 'т') { const s = cur(); if (s) { s.seed = rndSeed(); changed(true); } }
        if (e.key === 'v' || e.key === 'м') setView(S.view === 'grid' ? 'frame' : 'grid');
      }
    });
    let rz = 0; window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { if (S.view === 'grid') buildGrid(); }, 300); });
  }

  async function start() {
    bind();
    const saved = store.get('at-studio', null);
    try {
      const mode = await Engine.init();
      const r = await Engine.call('tools');
      ORDER = r.result.tools; TOOLS = Object.fromEntries(ORDER.map((t) => [t.id, t]));
      $('#engine').textContent = mode === 'native' ? 'Python на этом компьютере' : 'Python в браузере'; $('#engine').classList.add('ok');
      $('#boot').hidden = true;
    } catch (e) {
      $('#engine').textContent = 'движок не запустился'; $('#engine').classList.add('err');
      $('#boot-text').textContent = 'Не получилось запустить Python: ' + e.message + '. Обновите страницу; если не поможет — откройте в Chrome, Edge или Firefox последних версий.';
      return;
    }
    if (saved && saved.steps && saved.steps.every((s) => TOOLS[s.tool])) {
      S.steps = saved.steps.map((s) => ({ tool: s.tool, params: Object.assign(defaults(TOOLS[s.tool]), s.params), seed: s.seed, on: s.on !== false }));
      S.sel = Math.min(saved.sel || 0, S.steps.length - 1); S.locks = saved.locks || {}; S.amount = saved.amount || .5;
      if (saved.mock) setMock(saved.mock);
    }
    if (!S.steps.length) S.steps = [newStep('ether')];
    renderSteps(); renderParams(); pushHistory();
    setView(saved && saved.view && saved.view !== 'grid' && saved.view !== 'compare' ? saved.view : 'frame');
    render();
  }
  start();
})();
