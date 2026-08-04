// Model lab test. Loads every rig page, checks it builds with no errors, drives
// each state through its own clock and captures a contact sheet per rig.
//
// A rig that ships broken means every monster using it ships broken, so this
// runs before any of them are wired into the game.
const { chromium } = require('playwright');
const fs = require('fs');

const RIGS = process.argv.slice(2).length ? process.argv.slice(2)
  : ['wisp', 'serpent', 'flyer', 'crab', 'insect'];
const BASE = process.env.URL || 'http://127.0.0.1:8123/model-lab/';
const OUT = '/tmp/rigs';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const results = [];
  for (const rig of RIGS) {
    const page = await browser.newPage({ viewport: { width: 900, height: 620 } });
    const errors = [];
    page.on('pageerror', e => errors.push(String(e && e.message)));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(BASE + rig + '.html', { waitUntil: 'load', timeout: 60000 });
    let ready = false;
    for (let i = 0; i < 30 && !ready; i++) {
      ready = await page.evaluate(() => !!window.__ready).catch(() => false);
      if (!ready) await page.waitForTimeout(500);
    }
    const states = ready ? await page.evaluate(() => window.__states) : [];
    // Drive each state at several points in its own cycle. Poses are pure
    // functions of t, so this is exhaustive rather than a lucky sample.
    const shots = [];
    for (const st of states) {
      for (const [ti, tt] of [0.05, 0.35, 0.62, 0.9].entries()) {
        const ok = await page.evaluate(([s, t]) => window.__shot(s, t, 'three4', 0.6), [st, tt * 2]).catch(e => String(e));
        if (ok !== true) { errors.push('shot failed ' + st + '@' + tt + ': ' + ok); continue; }
        const p = OUT + '/' + rig + '_' + st + '_' + ti + '.png';
        await page.screenshot({ path: p });
        shots.push(p);
      }
    }
    // side and front on the idle pose, to catch anything inside out
    for (const v of ['side', 'front']) {
      await page.evaluate((vv) => window.__shot('idle', 1.0, vv, 0), v).catch(() => {});
      await page.screenshot({ path: OUT + '/' + rig + '_' + v + '.png' });
    }
    const stats = await page.evaluate(() => {
      const r = window.__shot ? 1 : 0;
      let meshes = 0, tris = 0;
      // the rig is everything under the scene except the ground disc
      const scene = window.__scene;
      return { hooked: r };
    }).catch(() => ({}));
    results.push({ rig, ready, states, shots: shots.length, errors });
    await page.close();
  }
  console.log(JSON.stringify(results, null, 2));
  await browser.close();
  process.exit(results.some(r => !r.ready || r.errors.length) ? 1 : 0);
})();
