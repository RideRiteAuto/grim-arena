// Ground-surface probe. Boots the bundle, then asks the live game what the
// atlas system decided at a set of world points, so a wrong-looking ground can
// be diagnosed by reading the numbers instead of squinting at a screenshot.
const { chromium } = require('playwright');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(9000);

  const out = await page.evaluate(() => {
    const g = window.__grim;
    if (!g) return { err: 'no game handle' };
    const W = g.WORLD();
    const pts = [
      ['camp', 41, 31], ['capital', 0, 0], ['n of capital', 0, -120],
      ['heartland field', -180, 140], ['greenwood', -600, 420],
      ['frostwild', -430, -900], ['ironspire', -1030, -300],
      ['suncoast', -400, 1100], ['windscar', 1600, -340],
      ['ember', 2264, 152], ['mistfen', 1588, 852], ['sunscorch', 2800, 1024]
    ];
    const su = [0, 0, 0];
    const rows = pts.map(([n, x, z]) => {
      const h = W.height(x, z), zi = W.zone(x, z);
      g.groundSurface(zi, h, x, z, su);
      return {
        at: n, x: x, z: z, h: +h.toFixed(1), zone: W.zones[zi],
        tileA: su[0], tileB: su[1], mix: +su[2].toFixed(2),
        nearWater: W.nearWater(x, z),
        roadDist: +W.roadDist(x, z, 40).toFixed(1)
      };
    });
    // How many chunks actually carry a road ribbon right now
    let roadChunks = 0, roadTris = 0;
    for (const [, c] of g._chunks) if (c.road) { roadChunks++; roadTris += c.road.geometry.index.count / 3; }
    return {
      rows: rows, atlasMs: +(g._atlasMs || 0).toFixed(1),
      chunks: g._chunks.size, roadChunks: roadChunks, roadTris: roadTris,
      pos: [Math.round(g.me.pos.x), Math.round(g.me.pos.z)]
    };
  });
  console.log(JSON.stringify(out, null, 1));
  if (errors.length) console.log('ERRORS', errors);
  await browser.close();
})();
