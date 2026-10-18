const { chromium } = require(process.env.PLAYWRIGHT || 'playwright');
const fs = require('fs');
// node style_shot.js OUT STYLE '[["app","#hash","theme",w,h,scroll],...]' [fontcss]
const [out, style, specsJ, fontCssPath] = process.argv.slice(2);
const fontCss = fontCssPath ? fs.readFileSync(fontCssPath, 'utf8') : '';
(async () => {
  const b = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  for (const [app, hash, theme, w, h, scroll] of JSON.parse(specsJ)) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: theme, isMobile: w < 700, hasTouch: w < 700 });
    await ctx.route(/fonts\.(googleapis|gstatic)/, r => r.abort());
    await ctx.addInitScript(s => { try { localStorage.setItem('suite-style', s); } catch (e) {} }, style);
    const pg = await ctx.newPage(); const errs = []; pg.on('pageerror', e => errs.push(e.message));
    pg.on('response', r => { if (r.status() >= 400) errs.push(r.status() + ' ' + r.url()); });
    await pg.goto(`${process.env.BASE || "http://localhost:8765/"}${app === 'hub' ? '' : app + '/'}${hash}`); await pg.reload(); await pg.waitForTimeout(2200);
    if (fontCss) await pg.addStyleTag({ content: fontCss });
    if (scroll) await pg.evaluate(y => window.scrollTo(0, y), scroll); await pg.waitForTimeout(500);
    await pg.screenshot({ path: `${out}/${style}-${app}-${hash.replace(/\W/g, '')}-${theme}-${w}.png` });
    if (errs.length) console.log(style, app, theme, errs.slice(0, 4).join(' | '));
    await ctx.close();
  }
  await b.close();
})();
