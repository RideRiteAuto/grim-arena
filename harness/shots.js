// Look at the thing. Parks the camera at named spots around Hollowrest and the
// keep and writes a png for each, at roughly the height a player's camera rides
// at so the shots answer the question actually being asked: is the door taller
// than the man walking through it.
const { chromium } = require('playwright');
const fs = require('fs');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/shots';

const SHOTS = [
  // name,        camera x,y,z,           look at x,y,z
  ['town-high', -84 + 6, 58, 96 + 74, -84, 2, 96],
  ['town-mid', -84 + 26, 14, 96 + 46, -84 + 4, 3, 96 + 8],
  ['market', -84 + 1, 7.5, 96 + 26, -84, 2.5, 96],
  ['door-approach', 43.2 - 84 + 0.2, 2.4, 15.7 + 96 + 11.5, 43.2 - 84 - 3.2, 2.2, 15.7 + 96],
  ['inside-house', 43.2 - 84 + 4.4, 2.7, 15.7 + 96 + 3.0, 43.2 - 84 - 2, 1.6, 15.7 + 96],
  ['inn-front', 17 - 84, 3.2, -29.4 + 96 - 13, 17 - 84, 3.0, -29.4 + 96],
  ['keep-approach', -84, 11, 246 + 62, -84, 8, 246],
  ['keep-gate', -84, 2.6, 246 + 30, -84, 5.0, 246 - 6],
  ['keep-inside', -84 + 1, 4.2, 246 + 15, -84, 3.0, 246 - 12],
  ['keep-high', -84 + 4, 66, 246 + 52, -84, 4, 246],
];

// ONLY=name,name runs a subset. SwiftShader falls over after a handful of
// full-scene captures, so the shot list is taken in batches.
const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
const LIST = ONLY.length ? SHOTS.filter(s => ONLY.includes(s[0])) : SHOTS;

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1180, height: 700 } });
  page.on('pageerror', e => console.log('PAGEERROR', e.message));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(5000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  for (let i = 0; i < 40; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim.started && window.__grim._chunks && window.__grim._chunks.size > 40)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(1500);
  }

  // The game's own loop renders after anything we do, so setting the camera
  // and calling render() by hand just gets overwritten before the screenshot
  // lands. Hook renderer.render instead: whatever the game asks for, the frame
  // that actually reaches the canvas uses our camera.
  await page.evaluate(() => {
    const g = window.__grim;
    const rr = g.renderer.render.bind(g.renderer);
    g.renderer.render = (scene, cam) => {
      if (g._camLock) {
        const [ax, ay, az, bx, by, bz] = g._camLock;
        cam.position.set(ax, ay, az);
        cam.lookAt(new g.T.Vector3(bx, by, bz));
        cam.updateMatrixWorld();
      }
      rr(scene, cam);
    };
  });

  for (const [name, cx, cy, cz, tx, ty, tz] of LIST) {
    await page.evaluate(([cx, cy, cz, tx, ty, tz]) => {
      const g = window.__grim;
      // park the player at the subject so chunks stream in and the distance
      // culler keeps the props alive
      g.me.pos.set(tx, 0, tz);
      g._farHide = 0;
      g._camLock = [cx, cy, cz, tx, ty, tz];
    }, [cx, cy, cz, tx, ty, tz]);
    await page.waitForTimeout(2600);
    await page.screenshot({ path: `${OUT}/${name}.png` });
    console.log('shot', name);
  }
  await browser.close();
})();
