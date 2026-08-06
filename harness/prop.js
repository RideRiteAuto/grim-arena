// Prop lab harness.
//
// The rig harness (rigs.js) asks "does this rig move correctly". A prop does
// not move, so the only question left is "does it LOOK like the thing", and
// that cannot be asserted, only looked at. What this harness can do is make
// looking at it cheap and honest:
//
//   - every named camera, so nothing is judged from the one flattering angle
//   - every lighting rig, because additive fire hides in the dark
//   - several points in the animation cycle, so a lucky frame cannot pass
//   - a contact sheet, so all of it is one image instead of forty
//   - the hard numbers that CAN be asserted: mesh count, triangle count, draw
//     calls and console errors
//
// Usage:
//   node harness/serve.js & node harness/prop.js campfire
//   SHEET=1 ONLY=stand,close node harness/prop.js campfire
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const PROP = process.argv[2] || 'campfire';
const BASE = process.env.URL || 'http://127.0.0.1:8123/model-lab/';
const OUT = process.env.OUT || ('/tmp/prop-' + PROP);
const ONLY = process.env.ONLY ? process.env.ONLY.split(',') : null;
const LIGHTS = process.env.LIGHTS ? process.env.LIGHTS.split(',') : ['dusk', 'day', 'night'];
const TIMES = process.env.TIMES ? process.env.TIMES.split(',').map(Number) : [2.3, 5.7, 9.1];
const BUDGET = { meshes: Number(process.env.MAX_MESH || 12), tris: Number(process.env.MAX_TRIS || 9000) };

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 960, height: 660 } });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e && e.message)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

  await page.goto(BASE + PROP + '.html', { waitUntil: 'load', timeout: 60000 });
  let ready = false;
  for (let i = 0; i < 40 && !ready; i++) {
    ready = await page.evaluate(() => !!window.__ready).catch(() => false);
    if (!ready) await page.waitForTimeout(400);
  }
  if (!ready) {
    console.log(JSON.stringify({ prop: PROP, ready: false, errors }, null, 2));
    await browser.close();
    process.exit(1);
  }

  const views = ONLY || await page.evaluate(() => window.__views);
  const stats = await page.evaluate(() => window.__stats());
  const shots = [];

  // SwiftShader falls over after enough full-scene captures, so this walks the
  // list rather than holding frames, and reports how far it got if it dies.
  for (const light of LIGHTS) {
    for (const view of views) {
      for (const t of TIMES) {
        const name = PROP + '_' + light + '_' + view + '_t' + String(t).replace('.', 'p') + '.png';
        const ok = await page.evaluate(([v, tt, l, m]) => window.__shot(v, tt, l, { man: m }),
          [view, t, light, view === 'scale']).catch(e => String(e));
        if (ok !== true) { errors.push('shot failed ' + view + '/' + light + ': ' + ok); continue; }
        await page.screenshot({ path: path.join(OUT, name) });
        shots.push(name);
      }
    }
  }

  const fail = [];
  if (stats.meshes > BUDGET.meshes) fail.push('mesh count ' + stats.meshes + ' over budget ' + BUDGET.meshes);
  if (stats.tris > BUDGET.tris) fail.push('triangle count ' + stats.tris + ' over budget ' + BUDGET.tris);
  if (errors.length) fail.push(errors.length + ' console error(s)');

  console.log(JSON.stringify({ prop: PROP, ready, stats, shots: shots.length, out: OUT, errors, fail }, null, 2));
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})();
