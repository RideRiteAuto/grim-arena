// Find somewhere to put a thing.
//
// "Put it at roughly 30, 28" is how the campfire ended up half inside a
// boulder. dressBlocked keeps zone CLUTTER off a prop, but it cannot help with
// anything that was placed by hand or by another builder, and it does not run
// at all for geometry that was already in the scene. So the honest way to pick
// a spot is to ask the loaded world what is actually standing there.
//
// Scores a grid of candidates on:
//   - distance to the nearest collider (the thing the player bumps into)
//   - distance to the nearest piece of scene geometry of any kind, measured
//     against real bounding boxes, which is what catches the boulder
//   - road clearance and walkability, through the game's own dressBlocked
//   - flatness, because a fire on a slope looks dropped rather than built
//   - distance from a named anchor, so it stays somewhere a player will go
//
//   node harness/serve.js & node harness/campsite.js 33 25 18
const { chromium } = require('playwright');

const CX = Number(process.argv[2] || 33);
const CZ = Number(process.argv[3] || 25);
const R = Number(process.argv[4] || 18);
const NEED = Number(process.env.NEED || 2.3);       // metres of clear space wanted
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
  page.on('pageerror', e => console.log('PAGEERROR', e.message));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(6000);
  for (let i = 0; i < 40; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim.started
      && window.__grim._chunks && window.__grim._chunks.size > 40)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(1500);
  }

  const out = await page.evaluate(([cx, cz, r, need]) => {
    const g = window.__grim, T = g.T;

    // Every mesh in the scene that is not ground, not the sky and not a
    // creature, with a real world bounding box. This is what a hand-placed
    // boulder shows up in and a collider list does not.
    // Anything already inside a campfire is excluded, or the fire that is
    // being moved counts itself as the obstruction and every candidate scores
    // zero clearance including the one it is standing on.
    const own = new Set();
    for (const f of (g.campfires || [])) f.g.traverse(o => own.add(o));
    const boxes = [];
    g.scene.traverse(o => {
      if (!o.isMesh || !o.geometry || !o.visible) return;
      if (own.has(o)) return;
      const b = new T.Box3().setFromObject(o);
      if (!isFinite(b.min.x) || !isFinite(b.max.x)) return;
      const w = b.max.x - b.min.x, d = b.max.z - b.min.z, h = b.max.y - b.min.y;
      if (w > 40 || d > 40) return;                // ground chunks, water planes
      if (h < 0.18) return;                        // decals, glows, road strips
      if (b.max.x < cx - r - 6 || b.min.x > cx + r + 6) return;
      if (b.max.z < cz - r - 6 || b.min.z > cz + r + 6) return;
      boxes.push([b.min.x, b.min.z, b.max.x, b.max.z, h]);
    });

    const clearOf = (x, z) => {
      let best = 1e9;
      for (const [x0, z0, x1, z1, h] of boxes) {
        const dx = Math.max(x0 - x, 0, x - x1);
        const dz = Math.max(z0 - z, 0, z - z1);
        const d = Math.hypot(dx, dz);
        if (d < best) best = d;
      }
      return best;
    };
    const colClear = (x, z) => {
      let best = 1e9;
      for (const c of (g.colliders || [])) {
        const d = c.r
          ? Math.hypot(x - c.x, z - c.z) - c.r
          : Math.hypot(Math.max(Math.abs(x - c.x) - c.hw, 0), Math.max(Math.abs(z - c.z) - c.hd, 0));
        if (d < best) best = d;
      }
      return best;
    };
    const slopeAt = (x, z) => {
      const e = 1.2, H = (a, b) => g.groundY(a, b);
      const gx = (H(x + e, z) - H(x - e, z)) / (2 * e);
      const gz = (H(x, z + e) - H(x, z - e)) / (2 * e);
      return Math.hypot(gx, gz);
    };

    const cands = [];
    for (let x = cx - r; x <= cx + r; x += 0.5) {
      for (let z = cz - r; z <= cz + r; z += 0.5) {
        if (Math.hypot(x - cx, z - cz) > r) continue;
        const dressed = g.dressBlocked ? g.dressBlocked(x, z) : false;
        const geo = clearOf(x, z);
        if (geo < need) continue;
        const col = colClear(x, z);
        if (col < need) continue;
        const sl = slopeAt(x, z);
        if (sl > 0.30) continue;
        // Prefer clear, flat, and near the middle of the camp rather than out
        // in a field: a campfire nobody walks past is a campfire nobody sees.
        const home = Math.hypot(x - cx, z - cz);
        const score = Math.min(geo, col) * 2.4 - sl * 6 - Math.max(0, home - 9) * 0.55;
        cands.push({ x: +x.toFixed(2), z: +z.toFixed(2), geo: +geo.toFixed(2),
                     col: +col.toFixed(2), slope: +sl.toFixed(3), home: +home.toFixed(1),
                     dressBlocked: dressed, score: +score.toFixed(2) });
      }
    }
    cands.sort((a, b) => b.score - a.score);

    // thin the list so the top ten are not ten samples of the same puddle
    const picked = [];
    for (const c of cands) {
      if (picked.some(p => Math.hypot(p.x - c.x, p.z - c.z) < 5)) continue;
      picked.push(c);
      if (picked.length >= 8) break;
    }
    return { scanned: cands.length, boxes: boxes.length, best: picked,
             existing: (g.campfires || []).map(f => ({ x: f.x, z: f.z, geo: +clearOf(f.x, f.z).toFixed(2) })) };
  }, [CX, CZ, R, NEED]);

  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})();
