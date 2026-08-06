// Second Hollowrest survey, for the scale-up.
//
// The first survey sized plots for a 20-40m town. The houses are being made
// roughly half again as large and pushed further out, so the road-distance
// field has to be read over a wider area, and the barrow site has to be
// re-checked for a square keep footprint rather than a round mound.
//
// Everything here READS the world. Nothing is judged by eye.
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
    const STEPS = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 34, 40];
    const road = (x, z) => {
      let best = 0;
      for (const W of STEPS) {
        const p = g.clearOfRoad(x, z, W);
        if (Math.abs(p[0] - x) < 1e-6 && Math.abs(p[1] - z) < 1e-6) best = W; else break;
      }
      return best;
    };
    const h = (x, z) => g.groundY(x, z);

    // relief across a rectangle: how flat a footprint is, which is what decides
    // whether a square keep sits on the ground or hangs off one corner
    const relief = (x, z, hw, hd) => {
      let lo = 1e9, hi = -1e9;
      for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) {
        const s = h(x + a * hw, z + b * hd);
        lo = Math.min(lo, s); hi = Math.max(hi, s);
      }
      return +(hi - lo).toFixed(2);
    };

    // 1. candidate house plots on a ring sweep: want big road clearance and
    //    flat ground for a footprint about 11 x 9 plus its yard
    const plots = [];
    for (let a = 0; a < 48; a++) {
      for (const rr of [30, 34, 38, 42, 46, 50, 54]) {
        const ang = a * Math.PI * 2 / 48;
        const x = TX + Math.cos(ang) * rr, z = TZ + Math.sin(ang) * rr;
        plots.push({
          dx: +(Math.cos(ang) * rr).toFixed(1), dz: +(Math.sin(ang) * rr).toFixed(1),
          r: rr, deg: Math.round(ang * 57.2958),
          road: road(x, z), relief: relief(x, z, 9, 8), h: +h(x, z).toFixed(1)
        });
      }
    }

    // 2. the market yard sits on the square itself; check it is flat and how
    //    much of it the road eats
    const market = { relief: relief(TX, TZ, 13, 11), road: road(TX, TZ) };

    // 3. keep footprint at the barrow site, and nearby alternatives
    const keeps = [];
    for (const [kx, kz] of [[-84, 246], [-84, 250], [-80, 244], [-90, 248], [-84, 240], [-76, 250]]) {
      keeps.push({
        at: [kx, kz], h: +h(kx, kz).toFixed(2),
        relief: relief(kx, kz, 20, 20), road: road(kx, kz),
        // the ground under each wall line, so a wall can be sunk far enough
        walls: [[0, -18], [0, 18], [-18, 0], [18, 0]].map(([ox, oz]) => +h(kx + ox, kz + oz).toFixed(2))
      });
    }

    const ring = [];
    for (let a = 0; a < 24; a++) {
      const ang = a * Math.PI * 2 / 24;
      const row = [Math.round(ang * 57.2958)];
      for (const rr of [28, 34, 40, 46, 52]) {
        row.push(road(TX + Math.cos(ang) * rr, TZ + Math.sin(ang) * rr));
      }
      ring.push(row);
    }
    return {
      ring,
      townH: +h(TX, TZ).toFixed(2),
      market,
      keeps,
      // best plots: flat, well clear of the road, sorted by clearance
      plotCount: plots.length,
      maxRoad: Math.max.apply(null, plots.map(p => p.road)),
      minRelief: Math.min.apply(null, plots.map(p => p.relief)),
      plots: plots.filter(p => p.road >= 14 && p.h > -1)
        .sort((a, b) => (b.road - a.road) || (a.relief - b.relief)).slice(0, 44)
        .map(p => [p.dx, p.dz, p.deg, p.r, p.road, p.relief, p.h])
    };
  });
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
