// Scaling experiment: what actually costs, and how does it grow?
//
// The 1,400 draw call / 7,000 mesh budget is a proxy. This measures the things
// that are hardware independent so the proxy can be checked against reality:
//
//  - draw calls and triangles at four ground-cover densities
//  - the wall time to BUILD one dressed chunk, which is the hitch a player feels
//    when they walk into new ground
//  - the per-frame JS cost of the creature roster, which is the cost that does
//    NOT merge away and does grow linearly with head count
//
// Absolute frame rate is deliberately not reported. This harness renders in
// software, so any FPS number from it would be fiction.
const { chromium } = require('playwright');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e && e.message)));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const h = [...document.querySelectorAll('button,a,div,span')]
      .filter(e => (e.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (h.length) h[h.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => window.__grim.play());
  await page.waitForTimeout(9000);

  const out = await page.evaluate(async () => {
    const g = window.__grim;
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const R = g.RULES();
    const SPOT = [-340, 200];

    const meshCount = () => { let n = 0; g.scene.traverse(o => { if (o.isMesh) n++; }); return n; };
    const settle = async (ms) => { g.me.pos.set(SPOT[0], 0, SPOT[1]); await sleep(ms); };

    // Worst frame over a full turn, so the reading is not a lucky camera angle.
    const turn = async () => {
      let calls = 0, tris = 0;
      for (let i = 0; i < 8; i++) {
        g.yaw = (i / 8) * Math.PI * 2;
        await sleep(600);
        const info = g.renderer.info.render;
        if (info.calls > calls) calls = info.calls;
        if (info.triangles > tris) tris = info.triangles;
      }
      return { calls, tris };
    };

    const redress = async () => {
      for (const [, rec] of g._chunks) g.dressDrop(rec);
      await settle(9000);
    };

    // --- 1. ground cover scaling
    const DENS = [[55, 85], [150, 220], [400, 600], [900, 1300]];
    const ground = [];
    for (const d of DENS) {
      R.GATHER.CLUTTER_PER_CHUNK = d;
      g._zoneClutter = null;                    // nothing cached off density, but be safe
      await redress();
      const t = await turn();
      // build cost: time one chunk's dressing from scratch, pure JS
      let buildMs = 0, built = 0;
      for (const [, rec] of g._chunks) {
        if (!rec.dressed) continue;
        g.dressDrop(rec);
        const t0 = performance.now();
        g.dressChunk(rec);
        buildMs += performance.now() - t0;
        rec.dressed = true;
        if (++built >= 8) break;
      }
      ground.push({
        density: d, meshes: meshCount(), calls: t.calls, triangles: t.tris,
        msPerChunk: built ? +(buildMs / built).toFixed(2) : null
      });
    }
    R.GATHER.CLUTTER_PER_CHUNK = [55, 85];
    await redress();

    // --- 2. what the per-frame CPU actually goes on
    // Pose every NPC the way the frame loop does and time it. This is the cost
    // that does NOT merge away: it is linear in head count, forever.
    const npcs = (g.npcs || []).filter(n => n.qr);
    const timePose = (n) => {
      const t0 = performance.now();
      for (let i = 0; i < 200; i++) for (const e of npcs) g.poseQuadRig(e, 0.016);
      return (performance.now() - t0) / 200;
    };
    const poseMs = npcs.length ? +timePose().toFixed(4) : 0;

    // --- 3. what the scene is actually made of
    let shadowCasters = 0, frozen = 0, live = 0, lights = 0;
    g.scene.traverse(o => {
      if (o.isLight) lights++;
      if (!o.isMesh) return;
      if (o.castShadow) shadowCasters++;
      if (o.matrixAutoUpdate) live++; else frozen++;
    });

    return {
      ground, poseMs, quadNpcs: npcs.length, totalNpcs: (g.npcs || []).length,
      scene: { shadowCasters, frozenMeshes: frozen, liveMeshes: live, lights },
      perfMode: { dropAtFrameMs: 27, forceDropAtFrameMs: 55, gfx: g.gfx }
    };
  });

  console.log(JSON.stringify({ out, errors: errors.slice(0, 5) }, null, 2));
  await browser.close();
})();
