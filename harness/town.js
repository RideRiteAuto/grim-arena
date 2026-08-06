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
      if (Math.abs(p.x - TX) < 30 && Math.abs(p.z - TZ) < 30) nearMeshes++;
    });
    const cols = (g.colliders || []).filter(c => Math.abs(c.x - TX) < 30 && Math.abs(c.z - TZ) < 30);
    return {
      meshes, nearMeshes, calls: info.render.calls, tris: info.render.triangles,
      townColliders: cols.length,
      colliderRadii: cols.map(c => +c.r.toFixed(2)).sort((a, b) => a - b)
    };
  }, [TX, TZ]);

  // ---- views ---------------------------------------------------------------
  const VIEWS = [
    ['approach', 22, 9, 26, 0, 2.5, 0],
    ['square', 13, 5.5, 15, 0, 2.0, 0],
    ['cottage', -6, 3.4, 11, -9, 2.2, 4],
    ['inn', 12, 5.0, 26, 2, 2.6, 14],
    ['stalls', 1, 3.2, 6.5, 0, 1.6, -3.5],
    ['high', 4, 34, 34, 0, 0, 0]
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

  const fails = [];
  if (!streamed) fails.push('town never streamed in');
  if (town.townColliders < 6) fails.push('expected at least 6 town colliders, found ' + town.townColliders);
  // Regression guard, measured rather than guessed. Most of the ~1120 meshes
  // within 30m are zone dressing, pines, NPCs and terrain chunks, NOT the town
  // itself: the buildings, well and stalls are one merged mesh each. Recorded on
  // the build that shipped the rebuilt town (1121 meshes, 1152 calls); the
  // box-and-cone version it replaced measured 1143 and 1203. If someone adds a
  // building part as its own mesh instead of merging it, these move.
  if (town.nearMeshes > 1180) fails.push('town mesh count regressed: ' + town.nearMeshes + ' within 30m, was 1121');
  if (town.calls > 1260) fails.push('draw calls at the town regressed: ' + town.calls + ', was 1152');
  const hard = errors.filter(e => !/404|Failed to load resource|WebSocket/.test(e));
  if (hard.length) fails.push('console errors: ' + hard.slice(0, 3).join(' | '));

  console.log(JSON.stringify({ base, town, streamed, fails, errors: errors.slice(0, 5) }, null, 2));
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
