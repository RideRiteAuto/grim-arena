// Dressing engine test.
//
// Three things, all read off live objects rather than judged by eye:
//  1. DETERMINISM. Two fresh boots must generate byte-identical prop lists for
//     the same chunks: position, type, rotation, scale, node kind and node id.
//  2. RULES. Nothing in water, on a road, or inside a town safe zone.
//  3. COST. Draw calls and mesh count standing in a fully dressed area, and
//     whether a long walk loop leaks geometry.
const { chromium } = require('playwright');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

const CHUNKS = [];
for (let cx = 3; cx <= 7; cx++) for (let cz = 3; cz <= 7; cz++) CHUNKS.push([cx, cz]);
for (const c of [[-12, 9], [40, -6], [-20, -20], [25, 18], [0, 0], [-3, 4]]) CHUNKS.push(c);

async function boot(browser) {
  const page = await browser.newPage({ viewport: { width: 1024, height: 640 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));
  page.on('console', m => { if (m.type() === 'error' && !/404/.test(m.text())) errors.push(m.text()); });
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); });
  await page.waitForTimeout(8000);
  return { page, errors };
}

const propsOf = (page, chunks) => page.evaluate((cs) => {
  const g = window.__grim;
  const out = {};
  for (const [cx, cz] of cs) {
    const p = g.chunkProps(cx, cz);
    // rounded hard so a float printing difference cannot mask a real one
    const f = (n) => Number(n).toFixed(6);
    out[cx + ',' + cz] = {
      clutter: p.clutter.map(c => [c.type, c.zone, f(c.x), f(c.y), f(c.z), f(c.rot), f(c.sc)].join('|')),
      nodes: p.nodes.map(n => [n.kind, n.zone, n.nid, f(n.x), f(n.y), f(n.z), f(n.rot), f(n.sc)].join('|'))
    };
  }
  return out;
}, chunks);

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });

  // ---------------------------------------------------------- 1. determinism
  const a = await boot(browser);
  const propsA = await propsOf(a.page, CHUNKS);
  const b = await boot(browser);
  const propsB = await propsOf(b.page, CHUNKS);
  await b.page.close();

  let identical = true, firstDiff = null, totalClutter = 0, totalNodes = 0, dressedChunks = 0;
  for (const k of Object.keys(propsA)) {
    const A = propsA[k], B = propsB[k];
    totalClutter += A.clutter.length; totalNodes += A.nodes.length;
    if (A.clutter.length || A.nodes.length) dressedChunks++;
    if (JSON.stringify(A) !== JSON.stringify(B)) {
      identical = false;
      if (!firstDiff) firstDiff = { chunk: k, a: A, b: B };
    }
  }

  // ---------------------------------------------------- 2. rules + 3. cost
  const report = await a.page.evaluate(async (cs) => {
    const g = window.__grim;
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));

    // rule check across every generated prop
    const bad = { water: 0, road: 0, town: 0, sea: 0 };
    const RULES = g.RULES();
    const RC = RULES.GATHER.ROAD_CLEAR, TC = RULES.GATHER.TOWN_CLEAR;
    let checked = 0;
    for (const [cx, cz] of cs) {
      const p = g.chunkProps(cx, cz);
      for (const it of p.clutter.concat(p.nodes)) {
        checked++;
        if (g.WORLD().height(it.x, it.z) < 0.35) bad.water++;
        if (g.zoneAt(it.x, it.z) === 'SEA') bad.sea++;
        for (const s of RULES.SAFE) {
          const r = s.r + TC;
          if ((it.x - s.x) * (it.x - s.x) + (it.z - s.z) * (it.z - s.z) < r * r) { bad.town++; break; }
        }
        for (const s of (g.roadSegs || [])) {
          const dx = s[2] - s[0], dz = s[3] - s[1], len2 = dx * dx + dz * dz;
          let t = len2 ? ((it.x - s[0]) * dx + (it.z - s[1]) * dz) / len2 : 0;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          const px = s[0] + dx * t - it.x, pz = s[1] + dz * t - it.z;
          if (px * px + pz * pz < RC * RC) { bad.road++; break; }
        }
      }
    }

    const countMeshes = () => { let n = 0; g.scene.traverse(o => { if (o.isMesh) n++; }); return n; };
    // Move the player and then let the game's OWN loop run. Driving stepTerrain
    // by hand and placing the camera by hand gives a draw-call number for a view
    // no player will ever have, which is worse than no number at all.
    const settle = async (x, z, ms) => {
      g.me.pos.set(x, 0, z);
      g.me.pos.y = 0;
      await sleep(ms);
    };
    // Draw calls swing with where the camera happens to point, so the honest
    // reading is the worst frame over a slow turn on the spot, not one sample.
    const worstCalls = async (turns) => {
      let worst = 0, meshes = 0;
      for (let i = 0; i < turns; i++) {
        g.yaw = (i / turns) * Math.PI * 2;
        await sleep(700);
        const c = g.renderer.info.render.calls;
        if (c > worst) worst = c;
        meshes = countMeshes();
      }
      return { worst, meshes };
    };

    const clutterMeshes = () => { let n = 0; for (const [, rec] of g._chunks) if (rec.clutter) n++; return n; };

    // Baseline: the same ground with dressing suppressed, so the delta is the
    // cost of the dressing and nothing else.
    const SPOT = [-340, 200];
    g._dressOff = true;
    for (const [, rec] of g._chunks) g.dressDrop(rec);
    await settle(SPOT[0], SPOT[1], 9000);
    const baseTurn = await worstCalls(6);
    const base = { at: SPOT, zone: g.zoneAt(SPOT[0], SPOT[1]), meshes: baseTurn.meshes, worstCalls: baseTurn.worst };

    g._dressOff = false;
    const dressed = [];
    for (const [x, z] of [SPOT, [-600, 420], [-180, -420]]) {
      await settle(x, z, 10000);
      const t = await worstCalls(6);
      dressed.push({ at: [x, z], zone: g.zoneAt(x, z), meshes: t.meshes, worstCalls: t.worst,
                     zoneNodes: (g.zoneNodes || []).length, clutterMeshes: clutterMeshes() });
    }

    // Leak check: measure the SAME spot before and after a long loop away.
    await settle(SPOT[0], SPOT[1], 10000);
    const before = { meshes: countMeshes(), nodes: (g.zoneNodes || []).length, clutter: clutterMeshes() };
    for (let i = 0; i < 12; i++) await settle(SPOT[0] + i * 180, SPOT[1] + (i % 4) * 150, 2200);
    await settle(SPOT[0], SPOT[1], 12000);
    const after = { meshes: countMeshes(), nodes: (g.zoneNodes || []).length, clutter: clutterMeshes() };

    return { checked, bad, base, dressed, leak: { before, after, meshDelta: after.meshes - before.meshes } };
  }, CHUNKS);

  console.log(JSON.stringify({
    determinism: { identical, chunksTested: Object.keys(propsA).length, dressedChunks, totalClutter, totalNodes, firstDiff },
    report, errors: a.errors.slice(0, 10)
  }, null, 2));
  await browser.close();
  process.exit((identical && !a.errors.length) ? 0 : 1);
})();
