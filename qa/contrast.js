// Контраст текста по пикселям (с учётом фона-картинки): node qa/contrast.js СТИЛЬ [BASE_URL] [ШРИФТЫ.css|-] [--json]
// Для каждой страницы и темы снимает подложку под текстом (сам текст делается прозрачным) и считает
// худший и средний контраст цвета текста к пикселям подложки. Нужны playwright и pngjs (npm install в папке qa).
const { chromium } = require('playwright');
const { PNG } = require('pngjs');
const fs = require('fs');
const args = process.argv.slice(2); const JSONOUT = args.includes('--json'); const pos = args.filter((a) => !a.startsWith('--'));
const STYLE = pos[0] || 'journal'; const BASE = (pos[1] || 'http://localhost:8765/').replace(/\/?$/, '/');
const fontCss = pos[2] && pos[2] !== '-' ? fs.readFileSync(pos[2], 'utf8') : '';
const SEL = ['.brand small', '.var-ctl label', 'nav.rail > a .s', 'nav.rail > a .t', '.rail-toc a', '.rail .rail-foot', '.sheet-head p.lead', '.sheet-head .eyebrow', '.fld label', '.calc-desc', '.kpi .k', '.opt-t span', '.ex-tbl th', '.stamp td.k', '.dhint', '.intro .lead', '.intro .eyebrow', '.last', '.chips li', '.foot', '.card-e', '.brand b'];
const PAGES = JSON.parse(process.env.PAGES || '[["hub",""],["sapr-labs","#v1-data"],["op-coursework","#n13-data"],["eco-pdv","#v1-s2"],["krrs-robot","#v1-lr2"]]');
const L = (c) => { const f = (v) => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
const ratio = (a, b) => { const x = L(a), y = L(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
(async () => {
  const b = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}); const rows = [];
  for (const [app, hash] of PAGES) for (const theme of ['light', 'dark']) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
    if (fontCss) await ctx.route(/fonts\.(googleapis|gstatic)/, (r) => r.abort());
    await ctx.addInitScript((s) => { try { localStorage.setItem('suite-style', s); } catch (e) { /* нет хранилища */ } }, STYLE);
    const pg = await ctx.newPage(); await pg.goto(`${BASE}${app === 'hub' ? '' : app + '/'}${hash}`); await pg.reload(); await pg.waitForTimeout(1800);
    if (fontCss) await pg.addStyleTag({ content: fontCss }); await pg.waitForTimeout(300);
    for (const sel of SEL) {
      const el = pg.locator(sel).first(); if (!(await el.count()) || !(await el.isVisible())) continue;
      await el.scrollIntoViewIfNeeded(); await pg.waitForTimeout(120);
      const col = await el.evaluate((e) => { const c = getComputedStyle(e).color; const hide = (k) => { k.style.setProperty('color', 'transparent', 'important'); k.style.setProperty('text-shadow', 'none', 'important'); }; hide(e); e.querySelectorAll('*').forEach(hide); return c; });
      const buf = await el.screenshot();
      await el.evaluate((e) => { const un = (k) => { k.style.removeProperty('color'); k.style.removeProperty('text-shadow'); }; un(e); e.querySelectorAll('*').forEach(un); });
      const m = col.match(/[\d.]+/g).map(Number); const isC = /^color\(srgb/.test(col); const fg = m.slice(0, 3).map((v) => (isC ? v * 255 : v)); const a = m[3] === undefined ? 1 : m[3];
      const img = PNG.sync.read(buf); let worst = 99, sum = 0, n = 0;
      for (let y = 0; y < img.height; y += 2) for (let x = 0; x < img.width; x += 2) { const i = (y * img.width + x) * 4; const bg = [img.data[i], img.data[i + 1], img.data[i + 2]]; const f = fg.map((v, k) => v * a + bg[k] * (1 - a)); const r = ratio(f, bg); if (r < worst) worst = r; sum += r; n++; }
      rows.push({ app, theme, sel, avg: +(sum / n).toFixed(2), min: +worst.toFixed(2) });
    }
    await ctx.close();
  }
  await b.close();
  if (JSONOUT) { console.log(JSON.stringify(rows)); return; }
  const bad = rows.filter((r) => r.avg < 4.5);
  console.log(STYLE + ': ' + (bad.map((r) => `${r.avg.toFixed(2).padStart(6)} min ${r.min.toFixed(2).padStart(5)} | ${r.app} ${r.theme} ${r.sel}`).join('\n') || 'всё ≥ 4.5'));
  console.log('проверено элементов:', rows.length);
})();
