// Boot test. Loads the built bundle, clicks through to gameplay, waits for the
// world to stream in, then reports console errors and a few live readings off
// window.__grim.
//
// The harness runs at roughly 20 percent of real time, so every wait here is
// deliberately generous and every assertion reads real arrays and counts rather
// than judging anything by how a frame looked.
const { chromium } = require('playwright');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const SHOT = process.env.SHOT || '/tmp/boot.png';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [], logs = [];
  page.on('console', m => {
    const t = m.text();
    logs.push(m.type() + ': ' + t);
    if (m.type() === 'error') errors.push(t);
  });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);

  // Click through to gameplay. The guest button is matched by its text so a
  // layout change does not silently turn this into a no-op.
  // Matched on its own text and clicked through the DOM: getByText resolves to
  // the whole banner line here, which is not the clickable node.
  const entered = await page.evaluate(() => {
    const want = 'PLAY AS GUEST';
    const all = Array.from(document.querySelectorAll('button, a, div, span'));
    // deepest element carrying the label is the one wired to the handler
    const hits = all.filter(el => (el.textContent || '').toUpperCase().includes(want));
    const el = hits[hits.length - 1];
    if (!el) return false;
    el.click();
    return true;
  });
  await page.waitForTimeout(6000);
  // Guest login drops you back on the menu with a PLAY button. Headless has no
  // pointer lock to grant, so the last step is driven directly rather than
  // through a click that would sit waiting on a lock that never arrives.
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);

  // Wait for the world to actually stream rather than guessing at a duration.
  let streamed = false;
  for (let i = 0; i < 60; i++) {
    streamed = await page.evaluate(() => !!(window.__grim && window.__grim._chunks && window.__grim._chunks.size > 50)).catch(() => false);
    if (streamed) break;
    await page.waitForTimeout(2000);
  }

  const read = await page.evaluate(() => {
    const g = window.__grim;
    if (!g) return { grim: false };
    const scene = g.scene;
    let meshes = 0;
    if (scene) scene.traverse(o => { if (o.isMesh) meshes++; });
    const info = g.renderer && g.renderer.info;
    return {
      grim: true,
      started: !!g.started,
      mode: g.mode,
      chunks: g._chunks ? g._chunks.size : 0,
      resources: (g.resources || []).length,
      zoneNodes: (g.zoneNodes || []).length,
      meshes: meshes,
      drawCalls: info ? info.render.calls : null,
      skills: g.skills ? Object.keys(g.skills).filter(k => k.indexOf('__') !== 0) : null,
      lvlOf: g.skills ? { WOODCUTTING: g.lvl(g.skills.WOODCUTTING || 0), FORAGING: g.lvl(g.skills.FORAGING || 0) } : null,
      pos: g.me ? [Math.round(g.me.pos.x), Math.round(g.me.pos.z)] : null,
      toolTiers: g.toolTierFor ? { axe: g.toolTierFor('WOODCUTTING'), pick: g.toolTierFor('MINING'), sickle: g.toolTierFor('FORAGING') } : null,
      xp99: g.xpFor ? g.xpFor(99) : null
    };
  }).catch(e => ({ grim: false, evalError: String(e) }));

  await page.screenshot({ path: SHOT });
  console.log(JSON.stringify({ entered, streamed, read, errors: errors.slice(0, 20), errorCount: errors.length }, null, 2));
  await browser.close();
  process.exit(errors.length ? 1 : 0);
})();
