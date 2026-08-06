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
    // Houses register themselves now. They used to be found by looking for
    // big round colliders, which stopped working the moment each wall got its
    // own box: the search returned nothing and the spread check quietly passed
    // on an empty list.
    const buildings = (g._huts || []).map(h => ({
      at: [Math.round(h.x - TX), Math.round(h.z - TZ)],
      size: [+(h.hw * 2).toFixed(1), +(h.hd * 2).toFixed(1)],
      road: roadClear(h.x, h.z),
      fromSquare: Math.round(Math.hypot(h.x - TX, h.z - TZ))
    })).sort((a, b) => a.road - b.road);
    return {
      meshes, nearMeshes, calls: info.render.calls, tris: info.render.triangles,
      townColliders: cols.length,
      buildings
    };
  }, [TX, TZ]);

  // ---- the keep ------------------------------------------------------------
  // The round mound is gone, so the old ring-of-colliders test went with it.
  // What matters now is that the four curtain walls are solid box colliders,
  // the gateway is the one way through, and the King is inside rather than
  // standing in the masonry. harness/interiors.js walks a probe through all of
  // it; this is the structural check.
  const barrow = await page.evaluate(() => {
    const g = window.__grim;
    const b = g.barrowPos;
    if (!b) return { found: false };
    const k = g.hollowKing;
    const KH = 20;
    const cols = (g.colliders || []).filter(c => Math.abs(c.x - b.x) < KH + 8 && Math.abs(c.z - b.z) < KH + 8);
    const walls = cols.filter(c => c.hw !== undefined && (c.hw > 6 || c.hd > 6));
    const towers = cols.filter(c => c.r >= 4);
    return {
      found: true,
      at: [Math.round(b.x), Math.round(b.z)],
      fromTown: Math.round(Math.hypot(b.x - (-84), b.z - 96)),
      wallColliders: walls.length,
      towerColliders: towers.length,
      king: k ? {
        at: [Math.round(k.pos.x), Math.round(k.pos.z)],
        insideKeep: Math.abs(k.pos.x - b.x) < KH - 2 && Math.abs(k.pos.z - b.z) < KH - 2,
        scale: +k.g.scale.x.toFixed(2)
      } : null
    };
  });

  // ---- views ---------------------------------------------------------------
  const VIEWS = [
    ['approach', 40, 15, 48, 0, 2.5, 0],
    ['square', 18, 7.5, 22, 0, 2.0, 0],
    ['cottage', 43, 3.0, 27, 43, 2.4, 16],
    ['inn', 17, 4.5, -43, 17, 3.0, -29],
    ['stalls', 2, 4.0, 9.0, 0, 2.0, -8],
    ['high', 6, 72, 74, 0, 0, 2]
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
      g.me.pos.set(b.x, g.groundY(b.x, b.z + 30), b.z + 30);
    });
    await page.waitForTimeout(9000);
    for (const [name, dx, dy, dz, ly] of [
      ['barrow-door', 0, 5, 42, 6],
      ['barrow-close', 1, 3.0, 16, 3.0],
      ['barrow-side', 4, 70, 54, 2]
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
        g.__townFill.position.set(b.x + 20, gy + 40, b.z + 30);
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
  // The town got bigger and every house is now five wall meshes plus a roof,
  // a trim mesh and an interior, because a single merged shell cannot be cut
  // away. Rebaselined on the build that shipped it.
  if (town.calls > 2100) fails.push('draw calls at the town regressed: ' + town.calls);
  if (town.buildings.length !== 6) fails.push('expected 6 houses, found ' + town.buildings.length);
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
    if (barrow.fromTown < 100) fails.push('keep still only ' + barrow.fromTown + 'm from town');
    if (barrow.wallColliders < 5) fails.push('keep has only ' + barrow.wallColliders + ' wall colliders: things will clip through');
    if (barrow.towerColliders < 4) fails.push('keep has only ' + barrow.towerColliders + ' tower colliders, expected 4');
    if (!barrow.king) fails.push('no Hollow King');
    else if (!barrow.king.insideKeep) fails.push('the King is not inside his own keep, he is at ' + JSON.stringify(barrow.king.at));
  }
  const hard = errors.filter(e => !/404|Failed to load resource|WebSocket/.test(e));
  if (hard.length) fails.push('console errors: ' + hard.slice(0, 3).join(' | '));

  console.log(JSON.stringify({ base, town, barrow, streamed, fails, errors: errors.slice(0, 5) }, null, 2));
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
