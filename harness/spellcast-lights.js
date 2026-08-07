// Verifies the spell-light pooling fix: repeated fire/frost/snare casts must
// not change the scene's live PointLight count or grow the renderer's
// compiled-program list once the world has settled. Run against the
// unmodified bundle first (git stash) and then the patched one, and diff the
// two JSON reports - the whole point is the BEFORE run should show growth and
// the AFTER run should not.
const { chromium } = require('playwright');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const SHOT = process.env.SHOT || '/tmp/spellcast.png';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const want = 'PLAY AS GUEST';
    const all = Array.from(document.querySelectorAll('button, a, div, span'));
    const hits = all.filter(el => (el.textContent || '').toUpperCase().includes(want));
    const el = hits[hits.length - 1];
    if (el) el.click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);

  let streamed = false;
  for (let i = 0; i < 60; i++) {
    streamed = await page.evaluate(() => !!(window.__grim && window.__grim._chunks && window.__grim._chunks.size > 50)).catch(() => false);
    if (streamed) break;
    await page.waitForTimeout(2000);
  }

  const report = await page.evaluate(() => {
    const g = window.__grim;
    if (!g || !g.me) return { ok: false, reason: 'no game object' };

    function countLights(scene) {
      let n = 0;
      scene.traverse(o => { if (o.isPointLight) n++; });
      return n;
    }
    function programCount() { return g.renderer.info.programs ? g.renderer.info.programs.length : -1; }

    // Freeze world/AI streaming noise out of the measurement window: park the
    // player, give unlimited resources, and drive fireFrost/fireSnare
    // directly rather than through input, so this measures exactly the
    // functions the patch touches.
    g.me.mana = 9999; g.me.stam = 9999; g.me.hp = g.me.max;
    g.element = 'fire';

    const out = { ok: true };
    out.programsBaseline = programCount();
    out.lightsBaseline = countLights(g.scene);
    out.poolSize = (g._spellLights || []).length;   // -1-ish signal on the old bundle: undefined -> 0

    // Batch 1: eight rapid fire casts (fireFrost with this.element === 'fire').
    for (let i = 0; i < 8; i++) g.fireFrost(g.me);
    g.renderer.render(g.scene, g.cam);
    out.projectilesAfterBatch1 = g.projectiles.length;
    out.lightsAfterBatch1 = countLights(g.scene);
    out.programsAfterBatch1 = programCount();

    // Expire everything and let stepProjectiles process the removals - this
    // is the second churn point the original bug had (light removed with the
    // dead mesh).
    g.projectiles.forEach(p => { p.life = -1; });
    g.stepProjectiles(0.016);
    g.renderer.render(g.scene, g.cam);
    out.projectilesAfterExpiry = g.projectiles.length;
    out.lightsAfterExpiry = countLights(g.scene);
    out.programsAfterExpiry = programCount();

    // Batch 2: eight more, including three snares (volley-style), after the
    // pool has already cycled once.
    for (let i = 0; i < 5; i++) g.fireFrost(g.me);
    for (let i = 0; i < 3; i++) g.fireSnare(g.me, (i - 1) * 0.2);
    g.renderer.render(g.scene, g.cam);
    out.projectilesAfterBatch2 = g.projectiles.length;
    out.lightsAfterBatch2 = countLights(g.scene);
    out.programsAfterBatch2 = programCount();

    return out;
  }).catch(e => ({ ok: false, evalError: String(e) }));

  // One more frame with a live fireball on screen, camera nudged toward it,
  // for a visual check alongside the numbers.
  await page.evaluate(() => {
    const g = window.__grim;
    if (!g || !g.me) return;
    g.element = 'fire'; g.me.mana = 9999;
    g.fireFrost(g.me);
  }).catch(() => {});
  await page.waitForTimeout(300);
  await page.screenshot({ path: SHOT });

  console.log(JSON.stringify({ report, errors: errors.slice(0, 10), errorCount: errors.length }, null, 2));
  await browser.close();
  process.exit(0);
})();
