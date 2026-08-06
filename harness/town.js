// Hollowrest look test.
//
// The town is the one place the player stands still, so it is the one place
// worth shooting from several angles. This teleports there, waits for the world
// to actually stream in rather than guessing, records the draw call and mesh
// cost on the spot, and writes a set of views.
//
// The budget assertion is the point of the numbers: the buildings carry roughly
// ten times the geometry they used to and must still cost about what they did,
// because every building merges into one mesh. If someone later adds a building
// part as its own mesh, this is what notices.
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/town';
const TX = -84, TZ = 96;

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 760 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
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
  for (let i = 0; i < 60; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim.started && window.__grim._chunks && window.__grim._chunks.size > 40)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(1500);
  }

  const base = await page.evaluate(() => {
    const g = window.__grim, info = g.renderer.info;
    let meshes = 0; g.scene.traverse(o => { if (o.isMesh) meshes++; });
    return { at: [Math.round(g.me.pos.x), Math.round(g.me.pos.z)], meshes, calls: info.render.calls };
  });

  // walk to town and let the world stream in around it
  await page.evaluate(([TX, TZ]) => {
    const g = window.__grim;
    g.me.pos.set(TX, g.groundY(TX, TZ), TZ);
  }, [TX, TZ]);
  let streamed = false;
  for (let i = 0; i < 40; i++) {
    streamed = await page.evaluate(([TX, TZ]) => {
      const g = window.__grim;
      // a chunk key near the town has to be resident, not just any 200 chunks
      let near = 0;
      g.scene.traverse(o => {
        if (!o.isMesh) return;
        const p = o.getWorldPosition(new g.T.Vector3());
        if (Math.abs(p.x - TX) < 40 && Math.abs(p.z - TZ) < 40) near++;
      });
      return near > 60;
    }, [TX, TZ]).catch(() => false);
    if (streamed) break;
    await page.waitForTimeout(2000);
  }

  const town = await page.evaluate(([TX, TZ]) => {
    const g = window.__grim, info = g.renderer.info;
    let meshes = 0, nearMeshes = 0;
    g.scene.traverse(o => {
      if (!o.isMesh) return;
      meshes++;
      const p = o.getWorldPosition(new g.T.Vector3());
      if (Math.abs(p.x - TX) < 50 && Math.abs(p.z - TZ) < 50) nearMeshes++;
    });
    const cols = (g.colliders || []).filter(c => Math.abs(c.x - TX) < 50 && Math.abs(c.z - TZ) < 50);
    // bracket road distance through clearOfRoad: if the point comes back
    // untouched at clearance W, it is at least W from the centreline
    const roadClear = (x, z) => {
      let best = 0;
      for (const W of [2, 4, 6, 8, 10, 12, 15, 18, 22, 26]) {
        const p = g.clearOfRoad(x, z, W);
        if (Math.abs(p[0] - x) < 1e-6 && Math.abs(p[1] - z) < 1e-6) best = W; else break;
      }
      return best;
    };
    // building colliders are the big ones; stalls are 1.3, menhirs 0.85
    const buildings = cols.filter(c => c.r > 2.5);
    return {
      meshes, nearMeshes, calls: info.render.calls, tris: info.render.triangles,
      townColliders: cols.length,
      buildings: buildings.map(c => ({
        at: [Math.round(c.x - TX), Math.round(c.z - TZ)],
        r: +c.r.toFixed(2),
        road: roadClear(c.x, c.z),
        fromSquare: Math.round(Math.hypot(c.x - TX, c.z - TZ))
      })).sort((a, b) => a.road - b.road)
    };
  }, [TX, TZ]);

  // ---- the barrow ----------------------------------------------------------
  const barrow = await page.evaluate(() => {
    const g = window.__grim;
    const b = g.barrowPos;
    if (!b) return { found: false };
    const k = g.hollowKing;
    const cols = (g.colliders || []).filter(c => Math.hypot(c.x - b.x, c.z - b.z) < 26);
    // A collider ring with a real gap. Measure the bearings directly and look
    // at the spacing between neighbours: binning them into buckets counts
    // quantisation as gaps, which is what the first version of this did.
    const bear = cols.filter(c => c.r >= 2)
      .map(c => Math.atan2(c.z - b.z, c.x - b.x))
      .sort((p, q) => p - q);
    let gap = 0, gaps = 0;
    for (let i = 0; i < bear.length; i++) {
      const nxt = i === bear.length - 1 ? bear[0] + Math.PI * 2 : bear[i + 1];
      const d = (nxt - bear[i]) * 57.2958;
      gap = Math.max(gap, d);
      if (d > 25) gaps++;                      // wider than the regular spacing
    }
    return {
      found: true,
      at: [Math.round(b.x), Math.round(b.z)],
      fromTown: Math.round(Math.hypot(b.x - (-84), b.z - 96)),
      shellColliders: cols.filter(c => c.r >= 2).length,
      gapDegrees: Math.round(gap),
      distinctGaps: gaps,
      king: k ? {
        at: [Math.round(k.pos.x), Math.round(k.pos.z)],
        fromBarrowCentre: +Math.hypot(k.pos.x - b.x, k.pos.z - b.z).toFixed(1),
        scale: +k.g.scale.x.toFixed(2)
      } : null
    };
  });

  // ---- views ---------------------------------------------------------------
  const VIEWS = [
    ['approach', 34, 13, 40, 0, 2.5, 0],
    ['square', 15, 6.5, 17, 0, 2.0, 0],
    ['cottage', -12, 4.2, 16, -22, 2.4, 6],
    ['inn', 34, 8.0, 44, 26, 3.0, 29],
    ['stalls', 1, 3.2, 7.5, 0, 1.6, -3.5],
    ['high', 6, 62, 62, 0, 0, 2]
  ];
  for (const [name, dx, dy, dz, lx, ly, lz] of VIEWS) {
    await page.evaluate(([TX, TZ, dx, dy, dz, lx, ly, lz]) => {
      const g = window.__grim, T = g.T;
      if (g.raf) { cancelAnimationFrame(g.raf); g.raf = null; }
      const gy = g.groundY(TX, TZ);
      if (!g.__townFill) {
        g.__townFill = new T.DirectionalLight(0xfff2e0, 1.5); g.scene.add(g.__townFill);
        g.__townFill2 = new T.HemisphereLight(0xcfd8e8, 0x6a6250, 0.85); g.scene.add(g.__townFill2);
      }
      g.__townFill.position.set(TX + 24, gy + 34, TZ + 20);
      g.__townFill.target.position.set(TX, gy, TZ); g.__townFill.target.updateMatrixWorld();
      const c = g.cam;
      c.position.set(TX + dx, gy + dy, TZ + dz);
      c.lookAt(TX + lx, gy + ly, TZ + lz);
      c.updateProjectionMatrix();
      g.renderer.render(g.scene, c);
    }, [TX, TZ, dx, dy, dz, lx, ly, lz]);
    await page.locator('canvas').first().screenshot({ path: `${OUT}/${name}.png` });
  }

  // ---- barrow views --------------------------------------------------------
  if (barrow.found) {
    await page.evaluate(() => {
      const g = window.__grim;
      const b = g.barrowPos;
      g.me.pos.set(b.x, g.groundY(b.x, b.z - 30), b.z - 30);
    });
    await page.waitForTimeout(9000);
    for (const [name, dx, dy, dz, ly] of [
      ['barrow-door', 0, 6, -34, 5],
      ['barrow-close', 11, 5.5, -30, 4.5],
      ['barrow-side', 34, 14, -18, 6]
    ]) {
      await page.evaluate(([dx, dy, dz, ly]) => {
        const g = window.__grim, T = g.T;
        if (g.raf) { cancelAnimationFrame(g.raf); g.raf = null; }
        const b = g.barrowPos, gy = g.groundY(b.x, b.z);
        // the king has to be visible for these to mean anything
        const k = g.hollowKing;
        if (k) { k._farHide = 0; k.g.visible = true; k.g.position.copy(k.pos); k.g.traverse(o => { o.matrixAutoUpdate = true; }); }
        if (!g.__townFill) {
          g.__townFill = new T.DirectionalLight(0xfff2e0, 1.5); g.scene.add(g.__townFill);
          g.__townFill2 = new T.HemisphereLight(0xcfd8e8, 0x6a6250, 0.85); g.scene.add(g.__townFill2);
        }
        g.__townFill.position.set(b.x + 20, gy + 40, b.z - 30);
        g.__townFill.target.position.set(b.x, gy, b.z); g.__townFill.target.updateMatrixWorld();
        const c = g.cam;
        c.position.set(b.x + dx, gy + dy, b.z + dz);
        c.lookAt(b.x, gy + ly, b.z);
        c.updateProjectionMatrix();
        g.renderer.render(g.scene, c);
      }, [dx, dy, dz, ly]);
      await page.locator('canvas').first().screenshot({ path: `${OUT}/${name}.png` });
    }
  }

  const fails = [];
  if (!streamed) fails.push('town never streamed in');
  if (town.townColliders < 6) fails.push('expected at least 6 town colliders, found ' + town.townColliders);
  // Regression guard, measured rather than guessed. Most of the ~1120 meshes
  // within 30m are zone dressing, pines, NPCs and terrain chunks, NOT the town
  // itself: the buildings, well and stalls are one merged mesh each. Recorded on
  // the build that shipped the rebuilt town (1121 meshes, 1152 calls); the
  // box-and-cone version it replaced measured 1143 and 1203. If someone adds a
  // building part as its own mesh instead of merging it, these move.
  if (town.calls > 1320) fails.push('draw calls at the town regressed: ' + town.calls);
  // Kevin's complaint, made into a test: buildings were sitting IN the road,
  // one of them dead on the centreline. Nothing with a building-sized collider
  // may be inside the corridor again.
  for (const b of town.buildings) {
    if (b.road < 10) fails.push('building at ' + JSON.stringify(b.at) + ' is only ' + b.road + 'm from the road');
  }
  // and it must not be a huddle any more
  const spread = Math.max(...town.buildings.map(b => b.fromSquare));
  if (spread < 25) fails.push('town is still cramped, furthest building only ' + spread + 'm from the square');
  if (!barrow.found) fails.push('no barrow');
  else {
    if (barrow.fromTown < 100) fails.push('barrow still ' + barrow.fromTown + 'm from town');
    if (barrow.shellColliders < 15) fails.push('barrow shell has only ' + barrow.shellColliders + ' colliders: monsters will clip through');
    if (barrow.distinctGaps !== 1) fails.push('barrow collider ring has ' + barrow.distinctGaps + ' gaps, expected exactly 1 (the doorway)');
    if (barrow.gapDegrees < 30 || barrow.gapDegrees > 90) fails.push('doorway gap is ' + barrow.gapDegrees + ' degrees, expected roughly 40');
    if (barrow.king && barrow.king.fromBarrowCentre < 16) fails.push('the king is inside the mound: ' + barrow.king.fromBarrowCentre + 'm from centre');
  }
  const hard = errors.filter(e => !/404|Failed to load resource|WebSocket/.test(e));
  if (hard.length) fails.push('console errors: ' + hard.slice(0, 3).join(' | '));

  console.log(JSON.stringify({ base, town, barrow, streamed, fails, errors: errors.slice(0, 5) }, null, 2));
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
