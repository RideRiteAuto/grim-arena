// Plague Rat quad-rig test.
//
// The rat carried the best boss geometry in the game and was posed the whole
// time by animate(), the BIPED path, which swings two of its four legs like
// arms. This asserts it is now driven by poseQuadRig and that the joints the
// rig needs actually articulate, then shoots the four states from a fixed
// camera so the result can be looked at rather than assumed.
//
// It does NOT count wall-clock time. The render loop is cancelled and every
// pose is stepped by calling animate() with an explicit dt, so the harness
// running at an eighth of real time cannot affect a single reading.
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/ratrig';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1200, height: 780 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const want = 'PLAY AS GUEST';
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes(want));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  for (let i = 0; i < 60; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim.rat)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(1500);
  }

  // ---- contract assertions ------------------------------------------------
  const shape = await page.evaluate(() => {
    const g = window.__grim, e = g && g.rat;
    if (!e) return { found: false };
    const q = e.qr;
    return {
      found: true,
      name: e.name,
      hasQr: !!q,
      legs: q ? q.legs.length : 0,
      legsJointed: q ? q.legs.every(l => !!l.hip && !!l.knee) : false,
      frontLegs: q ? q.legs.filter(l => l.front).length : 0,
      hasNeck: !!(q && q.neckG),
      hasJaw: !!(q && q.jaw),
      ears: q ? q.ears.length : 0,
      tailSegs: q ? q.tailSegs.length : 0,
      bodyIsUpper: !!(q && q.body === e.parts.upper),
      baseY: q ? q.baseY : null,
      // the tail must be a real chain: every link after the root is a
      // descendant of the one before it
      tailChained: q ? q.tailSegs.every((s, i) => i === 0 || s.parent === q.tailSegs[i - 1] ||
        (s.parent && s.parent.parent === q.tailSegs[i - 1])) : false,
      standY: (() => { if (!q) return null; const l = q.legs[0];
        const v = new g.T.Vector3(); l.knee.getWorldPosition(v); return +(v.y).toFixed(3); })()
    };
  });

  // ---- pose sampling ------------------------------------------------------
  // Cancel the render loop so nothing advances behind our back, then step the
  // rig by explicit dt and read the joints back.
  const samples = await page.evaluate(() => {
    const g = window.__grim, e = g.rat, T = g.T;
    if (g.raf) { cancelAnimationFrame(g.raf); g.raf = null; }
    const q = e.qr;
    // Degrade rather than throw on a build where the rig is absent, so the
    // same script can shoot a before-and-after.
    if (!q) return { noRig: true, kneeTravelWalk: 0, kneeTravelRun: 0, hipTravelWalk: 0, jawPeak: 0, jawAtRest: 0 };
    const snap = () => ({
      hip: q.legs.map(l => +l.hip.rotation.x.toFixed(3)),
      knee: q.legs.map(l => +l.knee.rotation.x.toFixed(3)),
      neck: +q.neckG.rotation.x.toFixed(3),
      jaw: +q.jaw.rotation.x.toFixed(3),
      bodyY: +q.body.position.y.toFixed(3),
      tail0: +q.tailSegs[0].rotation.x.toFixed(3)
    });
    const run = (state, moveAmt, steps, dt, act) => {
      e.state = state; e.moveAmt = moveAmt; e.act = act || null; e.st = 0;
      const seen = [];
      for (let i = 0; i < steps; i++) {
        if (act) e.st += dt;
        g.animate(e, dt);
        if (i % Math.ceil(steps / 4) === 0 || i === steps - 1) seen.push(snap());
      }
      return seen;
    };
    const idle = run('idle', 0, 12, 1 / 60);
    const walk = run('idle', 0.4, 40, 1 / 60);
    const runn = run('idle', 1.2, 40, 1 / 60);
    // a bite: MOVES.bite wind .44 - the snap must peak on the damage frame
    const bite = run('attack', 0, 32, 0.44 / 26, Object.assign({ name: 'bite' }, g.C.MOVES.bite));
    const spread = arr => {
      const lo = Math.min(...arr), hi = Math.max(...arr);
      return +(hi - lo).toFixed(3);
    };
    return {
      idle, walk, runn, bite,
      // the diagnostics that matter: do the knees move at all, and does the
      // gait differ between walk and run?
      kneeTravelWalk: spread(walk.flatMap(s => s.knee)),
      kneeTravelRun: spread(runn.flatMap(s => s.knee)),
      hipTravelWalk: spread(walk.flatMap(s => s.hip)),
      jawPeak: Math.max(...bite.map(s => s.jaw)),
      jawAtRest: bite[0].jaw
    };
  });

  // ---- screenshots --------------------------------------------------------
  const views = [
    ['idle', 'idle', 0, null],
    ['walk', 'idle', 0.4, null],
    ['run', 'idle', 1.2, null],
    ['bite', 'attack', 0, 'bite']
  ];
  for (const [label, state, mv, move] of views) {
    for (const [vname, dx, dy, dz] of [['side', 20, 4.5, -2.5], ['front', 0.6, 4.2, 16], ['three4', 14, 6.0, 12]]) {
      await page.evaluate(([state, mv, move, dx, dy, dz]) => {
        const g = window.__grim, e = g.rat, T = g.T;
        // The world streams and far-hides by distance from the player, and the
        // render loop is cancelled, so nothing is syncing e.g.position. Park the
        // rat next to the player, force it visible, and drive it by hand.
        e.pos.set(g.me.pos.x + 4, g.me.pos.y, g.me.pos.z - 2);
        e.g.position.copy(e.pos);
        e.yaw = 0; e.vyaw = 0; e.g.rotation.y = 0;
        e._farHide = 0; e.g.visible = true;
        e.g.traverse(o => { o.matrixAutoUpdate = true; });
        e.state = state; e.moveAmt = mv; e.st = 0;
        e.act = move ? Object.assign({ name: move }, g.C.MOVES[move]) : null;
        const dt = 1 / 60;
        // settle the pose: for the bite, stop exactly on the damage frame
        const steps = move ? 26 : 34;
        for (let i = 0; i < steps; i++) { if (move) e.st += (g.C.MOVES[move].wind / 26); g.animate(e, dt); }
        // Test-only fill light. The world is a dusk scene and a silhouette in
        // the dark cannot be reviewed. Not shipped: this lives in the harness.
        if (!g.__ratFill) {
          g.__ratFill = new T.DirectionalLight(0xffffff, 2.2);
          g.scene.add(g.__ratFill);
          g.__ratFill2 = new T.HemisphereLight(0xdfe6f2, 0x6a6250, 1.4);
          g.scene.add(g.__ratFill2);
        }
        g.__ratFill.position.set(e.pos.x + 8, e.pos.y + 12, e.pos.z + 10);
        g.__ratFill.target.position.copy(e.pos); g.__ratFill.target.updateMatrixWorld();
        const c = g.cam;
        c.position.set(e.pos.x + dx, e.pos.y + dy, e.pos.z + dz);
        c.lookAt(e.pos.x, e.pos.y + 1.9, e.pos.z - 2.5);
        c.updateProjectionMatrix();
        g.renderer.render(g.scene, c);
      }, [state, mv, move, dx, dy, dz]);
      await page.locator('canvas').first().screenshot({ path: `${OUT}/${label}-${vname}.png` });
    }
  }

  const fails = [];
  if (!shape.found) fails.push('rat not found');
  else {
    if (!shape.hasQr) fails.push('no qr rig');
    if (shape.legs !== 4) fails.push('legs != 4');
    if (!shape.legsJointed) fails.push('a leg has no knee');
    if (shape.frontLegs !== 2) fails.push('front leg count != 2');
    if (!shape.hasNeck) fails.push('no neck group');
    if (!shape.hasJaw) fails.push('no jaw');
    if (shape.ears < 2) fails.push('ears missing');
    if (shape.tailSegs < 3) fails.push('tail too short');
    if (!shape.tailChained) fails.push('tail is not a parented chain');
    if (!shape.bodyIsUpper) fails.push('qr.body is not parts.upper - animate() and poseQuadRig will fight');
  }
  if (samples.kneeTravelWalk < 0.15) fails.push('knees barely move while walking: ' + samples.kneeTravelWalk);
  if (samples.kneeTravelRun <= samples.kneeTravelWalk) fails.push('run gait is not wider than walk');
  if (samples.hipTravelWalk < 0.3) fails.push('hips barely move while walking');
  if (samples.jawPeak < 0.4) fails.push('jaw does not open on the bite: ' + samples.jawPeak);

  console.log(JSON.stringify({ shape, samples, errors: errors.slice(0, 10), fails }, null, 2));
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
