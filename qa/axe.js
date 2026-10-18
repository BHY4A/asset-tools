const { chromium } = require(process.env.PLAYWRIGHT || 'playwright');
const fs = require('fs'); const AXE = fs.readFileSync(__dirname + '/node_modules/axe-core/axe.min.js', 'utf8');
const T = JSON.parse(process.argv[2]);
(async () => {
  const b = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}); const agg = {};
  for (const theme of ['light', 'dark']) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
    await ctx.route(/fonts\.(googleapis|gstatic)/, r => r.abort());
    for (const [app, hash] of T) {
      const pg = await ctx.newPage();
      await pg.goto(`${process.env.BASE || "http://localhost:8765/"}${app === 'hub' ? '' : app + '/'}${hash}`); await pg.waitForTimeout(2500);
      await pg.evaluate(AXE);
      const r = await pg.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] }, rules: { 'color-contrast': { enabled: true } } })).violations.map(v => ({ id: v.id, impact: v.impact, n: v.nodes.length, ex: v.nodes.slice(0, 3).map(n => n.target.join(' ') + ' :: ' + (n.any[0] ? n.any[0].message : '')).join(' || ') })));
      for (const v of r) { const k = `${v.id} | ${app} | ${theme}`; agg[k] = v; }
      await pg.close();
    }
    await ctx.close();
  }
  for (const [k, v] of Object.entries(agg)) console.log(`${k} | ${v.impact} | n=${v.n}\n    ${v.ex.slice(0, 600)}`);
  await b.close();
})();
