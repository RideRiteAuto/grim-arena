// Terrain worker byte-diff comparison (Phase 1 of TERRAIN-WORKER-OFFLOAD-
// PLAN.md, Sec6). Boots the real bundle, waits for the terrain worker to
// come up, then runs window.__grim.debugCompareSample() -- which asks the
// worker to build/dress a representative sample of real chunks and
// byte-diffs every array against the main thread's own computation for the
// same chunks. This is the "done, not just asserted" check Sec6 calls for,
// kept runnable on demand (not a one-off) since a future three.js upgrade
// could silently reintroduce drift in the from-scratch geometry math.
const { chromium } = require('playwright');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error' && !/404/.test(m.text())) errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push('PAGEERROR: ' + (e && e.message)));

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter((el) => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); });
  await page.waitForTimeout(6000);

  // give the worker a moment to finish its own GRIM_WORLD.init() + initial
  // GRIM_EDIT sync before the first comparison request
  await page.waitForTimeout(2000);

  const result = await page.evaluate(async () => {
    if (!window.__grim || !window.__grim.debugCompareSample) return { ok: false, reason: 'debugCompareSample not exposed' };
    return await window.__grim.debugCompareSample();
  });

  console.log(JSON.stringify({ result, errors: errors.slice(0, 20), errorCount: errors.length }, null, 2));
  await browser.close();
  process.exit(result.ok && !errors.length ? 0 : 1);
})();
