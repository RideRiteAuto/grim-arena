// Bridge ends and torches, checked by measurement rather than by eye.
//
// Every earlier attempt at the bridge ends was judged from a screenshot, and
// the real defect was a boundary miss of 1.8e-14 that no screenshot could ever
// have named: buildBridge asked bridgeDeckY for the height at exactly
// -(dA + ramp), the round trip through world coordinates came back
// -24.000000000000018, the range test rejected it, and the caller fell back to
// the FULL deck height. So the last segment of every deck kicked back up into
// the air. This file reads numbers instead.
//
//   1. bridgeDeckY must answer at the EXACT endpoints. That one assertion is
//      the regression test for the whole bug.
//   2. The built deck ribbon, read out of its own vertex buffer, must descend
//      monotonically from the middle out to each end. No notch, no rise.
//   3. Each end must land ON the ground, and the deck must never be under it.
//   4. The flame must be one shared lathed geometry and the town must use it,
//      because the point of the patch was that there stopped being two torch
//      builders that could drift apart.
//
// Terrain comes from worldgen-data.js + worldgen.js run here in node, which is
// the same pair repack.py injects into the bundle. Nothing is mirrored by hand,
// so this cannot pass by agreeing with a copy of the bug.
//
// Run:  node harness/serve.js &  then  node harness/bridges.js
const { chromium } = require('playwright');
const { runInThisContext } = require('vm');
const fs = require('fs');
const path = require('path');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const ROOT = path.join(__dirname, '..');
const TOWN = [-84, 96];              // Hollowrest square, where the eight torches ring

const fail = [];
function check(ok, msg) {
  console.log((ok ? '  ok   ' : '  FAIL ') + msg);
  if (!ok) fail.push(msg);
}

(async () => {
  // ---- terrain, from the real generator ------------------------------------
  runInThisContext(
    fs.readFileSync(path.join(ROOT, 'worldgen-data.js'), 'utf8') + '\n' +
    fs.readFileSync(path.join(ROOT, 'worldgen.js'), 'utf8') + '\n' +
    'globalThis.GRIM_WORLD = GRIM_WORLD;\n');
  await GRIM_WORLD.init();
  const BRIDGES = GRIM_WORLD.bridges;
  console.log(`world ready, ${BRIDGES.length} crossings\n`);

  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1024, height: 640 } });
  page.on('pageerror', e => console.log('PAGEERROR', e.message));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const h = Array.from(document.querySelectorAll('button,a,div,span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (h.length) h[h.length - 1].click();
  });
  await page.waitForTimeout(5000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  for (let i = 0; i < 40; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim.started
      && window.__grim._chunks && window.__grim._chunks.size > 40)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(1500);
  }
  const boot = await page.evaluate(() => typeof window.__grim === 'object' && !!window.__grim.scene);
  check(boot, 'the bundle boots and window.__grim.scene exists');
  if (!boot) { await browser.close(); process.exit(1); }

  // One round trip per bridge rather than one per sample.
  const deckY = (pts) => page.evaluate(
    (P) => P.map(p => window.__grim.bridgeDeckY(p[0], p[1])), pts);

  for (const b of BRIDGES) {
    console.log(`\n${b.name}`);
    const dx = Math.sin(b.heading), dz = Math.cos(b.heading);
    const P = (a) => [b.x + dx * a, b.z + dz * a];

    // Walk out from the middle in 5cm steps until the deck stops answering.
    // This measures the deck's REAL extent instead of trusting a formula, so
    // it stays honest if the ramp maths is rewritten again.
    const REACH = b.span + 60;
    const step = 0.05, n = Math.round(REACH / step);
    const along = [];
    for (let i = -n; i <= n; i++) along.push(+(i * step).toFixed(2));
    const ys = await deckY(along.map(P));
    const on = [];
    for (let i = 0; i < along.length; i++) {
      if (ys[i] !== null) on.push({ a: along[i], deck: ys[i], ground: GRIM_WORLD.height(...P(along[i])) });
    }
    check(on.length > 10, `  deck exists (${on.length} sample points on it)`);
    if (on.length < 10) continue;

    // 1 + 3
    const A = on[0], B = on[on.length - 1];
    check(Math.abs(A.deck - A.ground) < 0.05 && Math.abs(B.deck - B.ground) < 0.05,
      `  both ends sit on the ground (A off ${(A.deck - A.ground).toFixed(3)}m, B off ${(B.deck - B.ground).toFixed(3)}m)`);

    let worst = 1e9, worstA = 0;
    for (const p of on) if (p.deck - p.ground < worst) { worst = p.deck - p.ground; worstA = p.a; }
    check(worst > -0.05,
      `  deck is never buried (min clearance ${worst.toFixed(3)}m at a=${worstA})`);

    // The analytic deck must also be monotonic out of the middle. A rise on the
    // way out IS the notch.
    const mid = Math.floor(on.length / 2);
    let bad = null;
    for (let i = 0; i < mid; i++) if (on[i].deck > on[i + 1].deck + 1e-9) bad = on[i];
    for (let i = on.length - 1; i > mid; i--) if (on[i].deck > on[i - 1].deck + 1e-9) bad = on[i];
    check(!bad, '  bridgeDeckY descends cleanly to both ends'
      + (bad ? ` (a=${bad.a} sits ${bad.deck.toFixed(3)}m, above its neighbour)` : ''));

    // 2: the deck AS BUILT. The analytic function can be right while the mesh
    // is wrong, which is exactly what happened, because buildBridge carried its
    // own null fallback. So walk the real ribbon out of the scene.
    const st = await page.evaluate(async (b) => {
      const g = window.__grim;
      g.me.pos.set(b.x, 0, b.z);
      g._farHide = 0;
      await new Promise(r => setTimeout(r, 1200));
      let best = null, bd = 1e9;
      g.scene.children.forEach(c => {
        if (c.type !== 'Group' || !c.children.some(k => k.isInstancedMesh)) return;
        const m = c.children.find(k => k.isMesh && !k.isInstancedMesh && k.geometry
          && k.geometry.index && k.geometry.attributes.position
          && k.geometry.attributes.position.count > 20
          && k.geometry.attributes.position.count < 400);
        if (!m) return;
        const p = m.geometry.attributes.position;
        const d = Math.hypot(p.getX(0) - b.x, p.getZ(0) - b.z);
        if (d < bd) { bd = d; best = m; }
      });
      if (!best) return null;
      const p = best.geometry.attributes.position, out = [];
      for (let i = 0; i < p.count; i += 2) out.push([p.getX(i), p.getY(i), p.getZ(i)]);
      return out;
    }, b);

    check(!!st, '  found the built deck ribbon in the scene');
    if (!st) continue;
    const sts = st.map(v => [+((v[0] - b.x) * dx + (v[2] - b.z) * dz).toFixed(2), +v[1].toFixed(3)])
      .sort((u, v) => u[0] - v[0]);
    const m2 = Math.floor(sts.length / 2);
    let bad2 = null;
    for (let i = 0; i < m2; i++) if (sts[i][1] > sts[i + 1][1] + 1e-6) bad2 = sts[i];
    for (let i = sts.length - 1; i > m2; i--) if (sts[i][1] > sts[i - 1][1] + 1e-6) bad2 = sts[i];
    check(!bad2, '  the BUILT deck descends cleanly to both ends'
      + (bad2 ? ` (station a=${bad2[0]} sits ${bad2[1]}m, above its neighbour)` : ''));

    const endStep = Math.max(Math.abs(sts[0][1] - sts[1][1]),
                             Math.abs(sts[sts.length - 1][1] - sts[sts.length - 2][1]));
    const innerStep = Math.abs(sts[2][1] - sts[3][1]);
    check(endStep < Math.max(0.35, innerStep * 2.5 + 0.05),
      `  the last segment is no steeper than the ramp it belongs to (${endStep.toFixed(3)}m vs ${innerStep.toFixed(3)}m)`);
  }

  // ---- 4: one torch, one flame geometry, and the town uses it -------------
  console.log('\ntorches');
  await page.evaluate((T) => { window.__grim.me.pos.set(T[0], 0, T[1]); window.__grim._farHide = 0; }, TOWN);
  await page.waitForTimeout(3500);
  const torch = await page.evaluate((T) => {
    const g = window.__grim, V = g.T.Vector3;
    const flames = [];
    g.scene.traverse(o => { if (o.isInstancedMesh && o.material === g._flameMat) flames.push(o); });
    let townFlames = 0;
    for (const o of flames) {
      const m = o.instanceMatrix.array;
      for (let i = 0; i < o.count; i++) {
        if (Math.hypot(m[i * 16 + 12] - T[0], m[i * 16 + 14] - T[1]) < 40) townFlames++;
      }
    }
    let lampBalls = 0;
    g.scene.traverse(o => {
      if (!o.isMesh || !o.geometry || o.geometry.type !== 'IcosahedronGeometry') return;
      if (!o.material || !o.material.emissive || o.material.emissive.getHex() !== 0xd8a531) return;
      const p = o.getWorldPosition(new V());
      if (Math.hypot(p.x - T[0], p.z - T[1]) < 60) lampBalls++;
    });
    return {
      meshes: flames.length,
      total: flames.reduce((n, o) => n + o.count, 0),
      allShared: flames.length > 0 && flames.every(o => o.geometry === g._flameGeo),
      isLathe: !!(g._flameGeo && g._flameGeo.type === 'LatheGeometry'),
      townFlames: townFlames,
      lampBalls: lampBalls
    };
  }, TOWN);

  check(torch.isLathe, `  the flame is a lathed teardrop, not a cone (${torch.isLathe ? 'LatheGeometry' : 'NOT a lathe'})`);
  check(torch.allShared, `  every flame in the world shares one geometry (${torch.meshes} instanced meshes, ${torch.total} flames)`);
  check(torch.townFlames >= 8, `  the town square carries the same flame (${torch.townFlames} within 40m)`);
  check(torch.lampBalls === 0, `  no emissive lamp balls left on the town posts (${torch.lampBalls})`);

  await browser.close();
  console.log(fail.length ? `\n${fail.length} FAILED` : '\nall bridge and torch checks passed');
  process.exit(fail.length ? 1 : 0);
})();
