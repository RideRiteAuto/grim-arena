// Character review driver: the shots that answer Kevin's v4 critique, which
// the generic prop sheet cannot take because they need armor toggled off
// (face, hair, joints) and specific states. Writes a small named set instead
// of a 54-image sheet, so each pass is reviewable in one glance.
//
//   node harness/serve.js & node harness/char-review.js
const { chromium } = require('playwright');
const fs = require('fs');

const BASE = process.env.URL || 'http://127.0.0.1:8123/model-lab/';
const OUT = process.env.OUT || '/tmp/char-review';

const SHOTS = [
  // the joint/seam review: NO armor, NO weapons - just the body
  { view: 'front',   light: 'day',  opts: { armor: false, weapons: false }, name: 'body-front' },
  { view: 'three4',  light: 'day',  opts: { armor: false, weapons: false }, name: 'body-three4' },
  { view: 'profile', light: 'day',  opts: { armor: false, weapons: false }, name: 'body-profile' },
  { view: 'back',    light: 'day',  opts: { armor: false, weapons: false }, name: 'body-back' },
  { view: 'face',    light: 'day',  opts: { armor: false, weapons: false }, name: 'face' },
  { view: 'face',    light: 'dusk', opts: { armor: false, weapons: false }, name: 'face-dusk' },
  { view: 'feet',    light: 'day',  opts: { armor: false, weapons: false }, name: 'feet' },
  { view: 'under',   light: 'day',  opts: { armor: false, weapons: false }, name: 'under' },
  // armored, with sword and shield: what the game actually shows
  { view: 'front',   light: 'day',  opts: { armor: true, weapons: true }, name: 'armored-front' },
  { view: 'three4',  light: 'dusk', opts: { armor: true, weapons: true }, name: 'armored-three4' },
  { view: 'shieldside', light: 'day', opts: { armor: true, weapons: true }, name: 'shield-carry' },
  { view: 'profile', light: 'day',  opts: { armor: true, weapons: true }, name: 'armored-profile' },
  { view: 'feet',    light: 'dusk', opts: { armor: true, weapons: true }, name: 'feet-armored' },
  { view: 'hands',   light: 'day',  opts: { armor: true, weapons: true }, name: 'sword-hand' }
];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 960, height: 660 } });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e && e.message)));
  await page.goto(BASE + 'character.html', { waitUntil: 'load', timeout: 60000 });
  for (let i = 0; i < 40; i++) {
    if (await page.evaluate(() => !!window.__ready).catch(() => false)) break;
    await page.waitForTimeout(300);
  }
  for (const s of SHOTS) {
    await page.evaluate(([v, l, o]) => window.__shot(v, 3.0, l, o), [s.view, s.light, s.opts]);
    await page.waitForTimeout(60);
    await page.screenshot({ path: OUT + '/' + s.name + '.png' });
  }
  const stats = await page.evaluate(() => window.__stats());
  console.log(JSON.stringify({ stats, errs, out: OUT }, null, 2));
  await browser.close();
  process.exit(errs.length ? 1 : 0);
})();
