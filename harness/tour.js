// Walks the camera to a list of world points and screenshots each one, so the
// ground and the roads can be judged where they actually are rather than only
// from the spawn. Also reports what the placement rules decided at each stop.
const { chromium } = require('playwright');
const fs = require('fs');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const DIR = process.env.DIR || '/tmp/tour';

const STOPS = [
  ['01-camp', 41, 31],
  ['02-capital-road-north', 6, -150],
  ['03-heartland-road-west', -300, -330],
  ['04-heartland-open', -190, 250],
  ['05-greenwood', -640, 470],
  ['06-frostwild', -430, -900],
  ['07-ironspire', -1010, -300],
  ['08-suncoast-road', -380, 1040],
  ['09-windscar-road', 1640, -390],
  ['10-mistfen', 1700, 700]
];

(async () => {
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));
  page.on('console', m => { if (m.type() === 'error' && !/404/.test(m.text())) errors.push(m.text()); });

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const h = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (h.length) h[h.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(9000);

  const report = [];
  for (const [name, x, z] of STOPS) {
    const info = await page.evaluate(([x, z]) => {
      const g = window.__grim;
      g.me.pos.set(x, 0, z);
      g.me.g.position.set(x, g.groundY(x, z), z);
      return true;
    }, [x, z]);
    // Give the streamer time to build and dress the ring around the new spot.
    await page.waitForTimeout(9000);
    const stat = await page.evaluate(() => {
      const g = window.__grim, W = g.WORLD();
      let roadChunks = 0, dressed = 0;
      for (const [, c] of g._chunks) { if (c.road) roadChunks++; if (c.dressed) dressed++; }
      const su = [0, 0, 0];
      const x = g.me.pos.x, z = g.me.pos.z, h = W.height(x, z), zi = W.zone(x, z);
      g.groundSurface(zi, h, x, z, su);
      return {
        zone: W.zones[zi], h: +h.toFixed(1),
        tiles: [su[0], su[1]], mix: +su[2].toFixed(2),
        roadDist: +W.roadDist(x, z, 60).toFixed(1),
        chunks: g._chunks.size, roadChunks: roadChunks, dressed: dressed,
        draws: g.renderer.info.render.calls, meshes: g.renderer.info.memory.geometries
      };
    });
    await page.screenshot({ path: DIR + '/' + name + '.png' });
    report.push(Object.assign({ at: name, x: x, z: z }, stat));
    console.log(JSON.stringify(report[report.length - 1]));
  }
  if (errors.length) console.log('ERRORS', errors.slice(0, 5));
  else console.log('no console errors');
  await browser.close();
})();
