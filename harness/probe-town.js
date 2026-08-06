// One-off survey around Hollowrest: where the road actually runs, where the
// ground is walkable, and where there is room for a barrow far enough from town
// to feel like a journey. Coordinates for a layout change should come from the
// world, not from guessing.
const { chromium } = require('playwright');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
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

  const out = await page.evaluate(() => {
    const g = window.__grim;
    const TX = -84, TZ = 96;
    // GRIM_WORLD is module-scoped inside the bundle, so bracket the road
    // distance through clearOfRoad instead: if it hands the point back
    // untouched at clearance W, the point is at least W from the centreline.
    const STEPS = [2, 4, 6, 8, 10, 12, 15, 18, 22, 26, 32, 40];
    const road = (x, z) => {
      let best = 0;
      for (const W of STEPS) {
        const p = g.clearOfRoad(x, z, W);
        if (Math.abs(p[0] - x) < 1e-6 && Math.abs(p[1] - z) < 1e-6) best = W; else break;
      }
      return best;
    };
    const h = (x, z) => g.groundY(x, z);
    const zone = (x, z) => (g.zoneAt ? g.zoneAt(x, z) : '?');

    // 1. road distance on a grid over the town, so buildings can be placed off it
    const grid = [];
    for (let dz = -40; dz <= 40; dz += 8) {
      const row = [];
      for (let dx = -40; dx <= 40; dx += 8) row.push(Math.round(road(TX + dx, TZ + dz)));
      grid.push(row);
    }

    // 2. where each existing building sits relative to the road
    const HUTS = [[-9, 4], [8, 6], [-11, -8], [11, -6], [2, 14], [-20, 12]];
    const huts = HUTS.map(([dx, dz]) => ({
      at: [dx, dz],
      roadDist: +road(TX + dx, TZ + dz).toFixed(1),
      h: +h(TX + dx, TZ + dz).toFixed(1)
    }));

    // 3. candidate barrow sites: far enough to be a journey, on land, off road
    const cands = [];
    for (let a = 0; a < 12; a++) {
      for (const rr of [90, 120, 150, 180]) {
        const ang = a * Math.PI / 6;
        const x = TX + Math.cos(ang) * rr, z = TZ + Math.sin(ang) * rr;
        if (Math.hypot(x, z) > 300) continue;
        const hh = h(x, z);
        if (hh < 3) continue;                     // sea or shoreline
        // flat enough for a mound: sample the ring
        let lo = 99, hi = -99;
        for (let k = 0; k < 8; k++) {
          const b = k * Math.PI / 4;
          const s = h(x + Math.cos(b) * 15, z + Math.sin(b) * 15);
          lo = Math.min(lo, s); hi = Math.max(hi, s);
        }
        cands.push({
          at: [Math.round(x), Math.round(z)], r: rr, ang: Math.round(ang * 57.3),
          h: +hh.toFixed(1), relief: +(hi - lo).toFixed(1),
          road: +road(x, z).toFixed(1), zone: zone(x, z),
          fromTown: rr
        });
      }
    }
    cands.sort((a, b) => (a.relief - b.relief) || (b.road - a.road));
    return {
      townH: +h(TX, TZ).toFixed(1),
      townRoad: +road(TX, TZ).toFixed(1),
      grid, huts,
      best: cands.filter(c => c.relief < 6 && c.road > 14 && c.r >= 120).slice(0, 12)
    };
  });
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
