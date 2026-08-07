// Verifies the locomotion overhaul (patches 73.140 / 73.260 / 73.375 /
// 73.480) against the REAL running rig, not a stub - same boot route
// harness/char-ingame.js and harness/pivotstep.js already use. Checks the
// actual numeric behaviour Kevin asked for (walk/run/sprint genuinely
// distinct, turn-in-place duration/foot choice responds to real input,
// ankle joint exists and moves, quadruped gait crossfades) and takes
// screenshots so a human can also just look at it.
//
//   node harness/serve.js & node harness/locomotion-verify.js
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/locomotion-verify';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1180, height: 700 } });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e && e.message)));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll('button, a, div, span'));
    const hits = all.filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    const el = hits[hits.length - 1];
    if (el) el.click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);
  await page.waitForFunction(() => {
    const g = window.__grim;
    return g && g.started && g.me && g.me.g;
  }, { timeout: 120000 });
  await page.waitForTimeout(2500);

  // camera hijack (harness/campfire.js / char-ingame.js pattern)
  await page.evaluate(() => {
    const g = window.__grim;
    const rr = g.renderer.render.bind(g.renderer);
    g.renderer.render = (scene, cam) => {
      if (g._camLock) { g._camLock.updateProjectionMatrix(); return rr(scene, g._camLock); }
      return rr(scene, cam);
    };
  });

  const fail = [];
  const note = {};

  // ---- Phase 1: walk/run/sprint gait blend --------------------------------
  // Calls g.animate() directly in a synchronous loop, same technique
  // pivotstep.js uses and for the same reason: the real per-frame input
  // handler (reads actual keys, none pressed here) fights any moveAmt this
  // test sets if the real game loop is left running via requestAnimationFrame
  // - it decays a forced moveAmt back toward 0 within a few frames. Driving
  // animate() directly bypasses that handler entirely, so the forced moveAmt
  // never gets clobbered by anything except this test.
  const gaitSamples = await page.evaluate(() => {
    const g = window.__grim, me = g.me, P = me.parts;
    me.state = 'move';
    function sampleAt(ma, frames) {
      me.moveAmt = ma;
      let hipMax = 0, kneeMax = 0, leanMax = 0, armMax = 0;
      for (let i = 0; i < frames; i++) {
        g.animate(me, 1 / 60);
        hipMax = Math.max(hipMax, Math.abs(P.legR.rotation.x));
        kneeMax = Math.max(kneeMax, P.kneeR.rotation.x);
        leanMax = Math.max(leanMax, P.upper.rotation.x);
        armMax = Math.max(armMax, Math.abs(P.armR.rotation.x));
      }
      return { hipMax: +hipMax.toFixed(3), kneeMax: +kneeMax.toFixed(3), leanMax: +leanMax.toFixed(3), armMax: +armMax.toFixed(3) };
    }
    const walk = sampleAt(0.55, 90);
    const run = sampleAt(1.0, 90);
    const sprint = sampleAt(1.5, 90);
    me.moveAmt = 0; me.state = 'idle';
    return { walk, run, sprint };
  });
  note.gait = gaitSamples;
  // Sprint must clearly exceed run (the old bug: identical because of the
  // spd = min(1, moveAmt) clamp). Walk must be clearly smaller than run, in
  // both amplitude AND lean, not just a scaled copy.
  if (!(gaitSamples.sprint.kneeMax > gaitSamples.run.kneeMax + 0.15)) fail.push('sprint knee not clearly above run: ' + JSON.stringify(gaitSamples));
  if (!(gaitSamples.sprint.leanMax > gaitSamples.run.leanMax + 0.08)) fail.push('sprint lean not clearly above run: ' + JSON.stringify(gaitSamples));
  if (!(gaitSamples.walk.hipMax < gaitSamples.run.hipMax - 0.15)) fail.push('walk hip not clearly below run: ' + JSON.stringify(gaitSamples));
  if (!(gaitSamples.walk.leanMax < gaitSamples.run.leanMax - 0.02)) fail.push('walk lean not clearly below run: ' + JSON.stringify(gaitSamples));

  // side-view screenshots at each gait, mid-stride. The real per-frame input
  // handler decays a forced moveAmt back toward 0 within a few frames (no
  // keys pressed), so this pins it by reasserting every rAF tick rather than
  // setting it once and waiting - same underlying issue as the sampler above,
  // just needing the real render loop (for the screenshot) instead of a
  // bypass, so it can't use the direct-animate() trick.
  for (const [name, ma] of [['walk', 0.55], ['run', 1.0], ['sprint', 1.5]]) {
    await page.evaluate((v) => {
      const g = window.__grim, me = g.me;
      me.state = 'move';
      if (g.__holdMoveAmt) cancelAnimationFrame(g.__holdMoveAmt);
      const pin = () => { me.moveAmt = v; g.__holdMoveAmt = requestAnimationFrame(pin); };
      pin();
    }, ma);
    await page.waitForTimeout(650);
    await page.evaluate(() => {
      const g = window.__grim, T = g.T, me = g.me;
      const cam = new T.PerspectiveCamera(50, 1180 / 700, 0.1, 900);
      const p = me.g.position;
      cam.position.set(p.x + 2.6, p.y + 1.3, p.z + 0.15);
      cam.lookAt(p.x, p.y + 1.0, p.z);
      g._camLock = cam;
    });
    await page.waitForTimeout(120);
    await page.screenshot({ path: OUT + '/gait_' + name + '.png' });
  }
  await page.evaluate(() => {
    const g = window.__grim;
    if (g.__holdMoveAmt) cancelAnimationFrame(g.__holdMoveAmt);
    g.me.moveAmt = 0; g.me.state = 'idle';
  });

  // ---- Phase 2: ankle joint exists and actually moves ----------------------
  // Direct animate() calls again, same reason as the gait sampler above.
  const ankle = await page.evaluate(() => {
    const g = window.__grim, me = g.me, P = me.parts;
    if (!P.ankleR) return { present: false };
    me.state = 'move'; me.moveAmt = 1.0;
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < 90; i++) {
      g.animate(me, 1 / 60);
      lo = Math.min(lo, P.ankleR.rotation.x); hi = Math.max(hi, P.ankleR.rotation.x);
    }
    me.moveAmt = 0; me.state = 'idle';
    return { present: true, lo: +lo.toFixed(3), hi: +hi.toFixed(3), range: +(hi - lo).toFixed(3) };
  });
  note.ankle = ankle;
  if (!ankle.present) fail.push('P.ankleR missing - phase 2 rig threading did not land');
  else if (ankle.range < 0.05) fail.push('ankle barely moves while running: ' + JSON.stringify(ankle));

  await page.evaluate(() => {
    const g = window.__grim, T = g.T, me = g.me;
    const cam = new T.PerspectiveCamera(55, 1180 / 700, 0.1, 900);
    const p = me.g.position;
    cam.position.set(p.x + 0.55, p.y + 0.55, p.z + 0.9);
    cam.lookAt(p.x, p.y + 0.25, p.z + 0.15);
    g._camLock = cam;
  });
  await page.evaluate(() => {
    const g = window.__grim, me = g.me;
    me.state = 'move';
    if (g.__holdMoveAmt) cancelAnimationFrame(g.__holdMoveAmt);
    const pin = () => { me.moveAmt = 1.0; g.__holdMoveAmt = requestAnimationFrame(pin); };
    pin();
  });
  await page.waitForTimeout(500);
  await page.screenshot({ path: OUT + '/ankle_close.png' });
  await page.evaluate(() => {
    const g = window.__grim;
    if (g.__holdMoveAmt) cancelAnimationFrame(g.__holdMoveAmt);
    g.me.moveAmt = 0; g.me.state = 'idle';
  });

  // ---- Phase 4: turn-in-place, direction-based foot + rate-blended dur -----
  const pivot = await page.evaluate(() => {
    const g = window.__grim, me = g.me;
    me.moveAmt = 0; me.state = 'idle';
    // e._pivPlant is set true and then immediately read-and-cleared by
    // footTick_ INSIDE the same animate() call (that hand-off is the whole
    // point of 68.520 - the sound fires exactly on the plant, same frame).
    // So it's already false again by the time control returns here -
    // pivotstep.js hit the same thing and watches the _pivActive
    // true->false edge instead, which lands on the exact same frame.
    function resetPivot() {
      me._pivAccum = 0; me._pivActive = false; me._pivIdleT = 0;
      me._pivFoot = undefined; me._pivT = 0; me._pivPlant = false;
      me._pvY = me.vyaw; me._pivRateS = 0; me._pivDirS = 0;
    }
    function driveTurn(n, dt, deltaPerFrame) {
      const feet = [], durs = [];
      let wasActive = !!me._pivActive;
      for (let i = 0; i < n; i++) {
        me.yaw += deltaPerFrame;
        g.animate(me, dt);
        const active = !!me._pivActive;
        if (wasActive && !active) { feet.push(me._pivFoot); durs.push(+(me._pivDur || 0).toFixed(3)); }
        wasActive = active;
      }
      return { feet, durs };
    }
    // Slow, deliberate turn one way: ~0.72 rad/s.
    resetPivot();
    const slowRight = driveTurn(240, 1 / 60, 0.012);
    // Fast flick the other way: ~5.4 rad/s.
    resetPivot();
    const fastLeft = driveTurn(90, 1 / 60, -0.09);
    return { slowRight, fastLeft };
  });
  note.pivot = pivot;
  if (!pivot.slowRight.feet.length) fail.push('slow turn produced no pivot steps');
  if (!pivot.fastLeft.feet.length) fail.push('fast turn produced no pivot steps');
  if (pivot.slowRight.feet.length && pivot.fastLeft.feet.length) {
    const slowAvgDur = pivot.slowRight.durs.reduce((a, b) => a + b, 0) / pivot.slowRight.durs.length;
    const fastAvgDur = pivot.fastLeft.durs.reduce((a, b) => a + b, 0) / pivot.fastLeft.durs.length;
    note.slowAvgDur = +slowAvgDur.toFixed(3); note.fastAvgDur = +fastAvgDur.toFixed(3);
    if (!(fastAvgDur < slowAvgDur - 0.02)) fail.push('fast flick-turn steps not shorter than slow turn: slow=' + slowAvgDur + ' fast=' + fastAvgDur);
    // Same-direction turn should mostly reuse one foot (not alternate every step).
    const allSame = pivot.slowRight.feet.every(f => f === pivot.slowRight.feet[0]);
    note.slowRightAllSameFoot = allSame;
    if (!allSame) fail.push('turning one direction repeatedly did not stay on one foot: ' + JSON.stringify(pivot.slowRight.feet));
  }

  await page.evaluate(() => {
    const g = window.__grim, T = g.T, me = g.me;
    me.moveAmt = 0; me.state = 'idle';
    me._pivAccum = 0.5; // primed just under the trigger threshold
    const cam = new T.PerspectiveCamera(50, 1180 / 700, 0.1, 900);
    const p = me.g.position;
    cam.position.set(p.x + 2.2, p.y + 1.3, p.z + 1.2);
    cam.lookAt(p.x, p.y + 1.0, p.z);
    g._camLock = cam;
  });
  await page.evaluate(() => {
    const g = window.__grim, me = g.me;
    for (let i = 0; i < 20; i++) { me.yaw += 0.03; g.animate(me, 1 / 60); }
  });
  await page.waitForTimeout(100);
  await page.screenshot({ path: OUT + '/pivot_step.png' });

  // ---- Phase 3: quadruped gait crossfade + gaitStyle -----------------------
  const quad = await page.evaluate(async () => {
    const g = window.__grim, T = g.T;
    const wolf = g.makeWolfBeast({ fur: 0x6e685c, eye: 0xffd24a, scale: 1.1 });
    const deer = g.makeDeerBeast({ scale: 1.0 });
    wolf.g.position.set(4, 0, 4); deer.g.position.set(-4, 0, 4);
    g.scene.add(wolf.g); g.scene.add(deer.g);
    function sample(ent, mv, ms) {
      ent.moveAmt = mv; ent.state = 'idle'; ent.hp = 40;
      let hipLo = Infinity, hipHi = -Infinity, bodyYhi = -Infinity;
      const t0 = performance.now();
      const t1 = t0 + ms;
      return new Promise(res => {
        (function step() {
          g.poseQuadRig(ent, 1 / 60);
          hipLo = Math.min(hipLo, ent.qr.legs[0].hip.rotation.x);
          hipHi = Math.max(hipHi, ent.qr.legs[0].hip.rotation.x);
          bodyYhi = Math.max(bodyYhi, ent.qr.body.position.y);
          if (performance.now() < t1) requestAnimationFrame(step);
          else res({ hipRange: +(hipHi - hipLo).toFixed(3), bodyYhi: +bodyYhi.toFixed(3) });
        })();
      });
    }
    const wolfWalk = await sample(wolf, 0.4, 500);
    const wolfGallop = await sample(wolf, 1.5, 900);
    const deerGallop = await sample(deer, 1.5, 900);
    return {
      wolfGaitStyle: wolf.qr.gaitStyle, deerGaitStyle: deer.qr.gaitStyle,
      wolfWalk, wolfGallop, deerGallop
    };
  });
  note.quad = quad;
  if (quad.wolfGaitStyle !== 'rotatory') fail.push('wolf.qr.gaitStyle not rotatory: ' + quad.wolfGaitStyle);
  if (quad.deerGaitStyle !== 'transverse') fail.push('deer.qr.gaitStyle not transverse: ' + quad.deerGaitStyle);
  if (!(quad.wolfGallop.hipRange > quad.wolfWalk.hipRange)) fail.push('wolf gallop hip range not above walk: ' + JSON.stringify(quad));
  if (!(quad.wolfGallop.bodyYhi > quad.wolfWalk.bodyYhi)) fail.push('wolf gallop body lift not above walk (suspension phase not landing): ' + JSON.stringify(quad));

  await page.evaluate(() => {
    const g = window.__grim, T = g.T;
    const cam = new T.PerspectiveCamera(50, 1180 / 700, 0.1, 900);
    cam.position.set(0, 3, 12); cam.lookAt(0, 0.7, 4);
    g._camLock = cam;
  });
  await page.evaluate(() => {
    const g = window.__grim;
    for (const ent of g.scene.children.filter(o => o.__ent)) {}
  });
  await page.waitForTimeout(600);
  await page.screenshot({ path: OUT + '/quad_gallop.png' });

  if (errs.length) fail.push(errs.length + ' page error(s): ' + errs.slice(0, 4).join(' | '));
  console.log(JSON.stringify({ note, fail, out: OUT }, null, 2));
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})();
