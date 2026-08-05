// Dumps the live ground atlas to a PNG so the surfaces can be looked at
// directly, instead of inferred from how a lit, tinted, blended frame came out.
const { chromium } = require('playwright');
const fs = require('fs');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/atlas.png';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 600, height: 400 } });
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  const r = await page.evaluate(() => {
    const g = window.__grim;
    if (!g) return { err: 'no handle' };
    const t0 = performance.now();
    const tex = g.buildGroundAtlas();
    const ms = performance.now() - t0;
    return { ms: +ms.toFixed(1), w: tex.image.width, url: tex.image.toDataURL('image/png') };
  });
  if (r.err) { console.log(r.err); await browser.close(); return; }
  fs.writeFileSync(OUT, Buffer.from(r.url.split(',')[1], 'base64'));
  console.log('atlas', r.w + 'px painted in', r.ms, 'ms ->', OUT);
  await browser.close();
})();
