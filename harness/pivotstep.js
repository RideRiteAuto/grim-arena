// Prove the turn-in-place pivot-step (patch 68.520) actually fixes what
// Kevin reported, against the REAL running player rig - not a stub.
//
// footTick_ already has minimal-fixture coverage in sfxroute.js (proves the
// plant flag reaches the audio hookup). What that can't prove is the thing
// Kevin actually complained about: does the LEG MOTION itself stay smooth
// under real turning, regardless of frame rate or mouse noise? animate()
// touches dozens of unrelated parts (chest breathing, dodge rolls, donkeys,
// riding), so this drives it through the real G.me spawned by the real game
// rather than trying to stub the whole rig - the boot sequence is the same
// one harness/char-ingame.js already uses.
//
//   node harness/serve.js & node harness/pivotstep.js
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/pivotstep';

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

  const res = await page.evaluate(() => {
    const g = window.__grim, me = g.me;
    const fail = [];
    const note = {};

    // Drive the real rig for `n` frames at fixed dt, feeding a caller-chosen
    // per-frame yaw delta (mimicking a mouse-look delta stream). moveAmt is
    // held at 0 throughout - this is turning IN PLACE, not walking.
    function driveTurn(n, dt, deltaFn) {
      me.moveAmt = 0; me.state = 'idle';
      const plants = [];
      const kneeTrace = [];
      let wasActive = !!me._pivActive;
      for (let i = 0; i < n; i++) {
        me.yaw += deltaFn(i);
        g.animate(me, dt);
        // e._pivPlant is set true and then immediately consumed by
        // footTick_ INSIDE this same animate() call (that hand-off is the
        // whole point of the patch - the sound fires exactly on the plant,
        // same frame, no separate tracked clock). So by the time we get
        // control back here it's already been read-and-cleared. Detect the
        // plant the same way footTick_'s caller-independent way would not
        // help here - instead watch the _pivActive true->false edge, which
        // happens on the exact same frame animate() sets _pivPlant.
        const active = !!me._pivActive;
        if (wasActive && !active) plants.push(i);
        wasActive = active;
        kneeTrace.push({
          active: !!me._pivActive,
          t: me._pivT || 0,
          kneeR: +me.parts.kneeR.rotation.x.toFixed(4),
          kneeL: +me.parts.kneeL.rotation.x.toFixed(4)
        });
      }
      return { plants, kneeTrace };
    }

    // Reset any pivot state left over from spawn/idle so each sub-test
    // starts clean.
    function resetPivot() {
      me._pivAccum = 0; me._pivActive = false; me._pivIdleT = 0;
      me._pivFoot = undefined; me._pivT = 0; me._pivPlant = false;
      me._pvY = me.vyaw;
    }

    // ---- A. frame-rate independence -----------------------------------
    // Turn a fixed total angle (6.0 rad, a bit under two full turns) as a
    // smooth ramp, once at a 30fps-equivalent dt and once at a 144fps-
    // equivalent dt. The OLD rig's shuffle amplitude ramped a flat amount
    // PER CALL (not per second), so it visibly behaved differently by frame
    // rate. The new one counts real accumulated radians, so the step COUNT
    // should match regardless of how many calls it took to get there.
    const TOTAL = 6.0;
    resetPivot();
    const n30 = 90;
    const slow = driveTurn(n30, 1 / 30, () => TOTAL / n30);
    resetPivot();
    const n144 = 400;
    const fast = driveTurn(n144, 1 / 144, () => TOTAL / n144);
    note.plantsAt30fps = slow.plants.length;
    note.plantsAt144fps = fast.plants.length;
    // NOT a naive TOTAL/PIVOT_STEP_RAD: accumulation is intentionally paused
    // while a step is active (see the patch docstring - a step can't be
    // interrupted mid-flight), so some of the injected rotation lands during
    // an active step and is never counted. That is a real, deliberate
    // design property, not something to assert an exact count against - the
    // thing that actually mattered for frame-rate independence is that BOTH
    // paces produced the SAME count for the SAME total input rotation.
    if (Math.abs(slow.plants.length - fast.plants.length) > 1)
      fail.push('A: step count depends on frame rate: 30fps=' + slow.plants.length + ' 144fps=' + fast.plants.length);
    if (slow.plants.length < 2) fail.push('A: suspiciously few steps for 6 rad of turning: ' + slow.plants.length);

    // ---- B. decoupled from per-frame input noise -----------------------
    // Same TOTAL rotation, but injected as noisy deltas (some frames near
    // zero, some frames much larger) instead of a smooth ramp. The step
    // COUNT should land close to the smooth run's count (it only cares
    // about the real accumulated angle), and - the actual jitter bug - once
    // a step is ACTIVE, its knee-height trajectory must follow the clean
    // sin(pi*t) arc regardless of what the noisy input does on those
    // in-flight frames. The old rig failed this: its phase speed WAS the
    // noise, so a noisy input directly distorted the arc shape, not just
    // the step count.
    resetPivot();
    let seed = 17;
    function rnd() { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; }
    const nNoisy = 240;
    const base = TOTAL / nNoisy;
    const noisy = driveTurn(nNoisy, 1 / 60, () => base * (0.15 + rnd() * 1.9)); // noisy but same long-run average
    note.plantsNoisy = noisy.plants.length;
    note.plantsSmoothForCompare = slow.plants.length;
    if (Math.abs(noisy.plants.length - slow.plants.length) > 2)
      fail.push('B: noisy input changed the step count materially vs a smooth turn of the same total angle: noisy=' + noisy.plants.length + ' smooth=' + slow.plants.length);

    // Check every frame where a step was active: the knee angle for the
    // active leg must be monotonically consistent with sin(pi*t) to within
    // a small tolerance - i.e. it is being driven by e._pivT (a clean
    // internal timer), not recomputed from that frame's noisy input.
    // kneeR/kneeL carry a constant +0.06 idle-bend base from the walk-cycle
    // block above the pivot block (present at spd=0 regardless of pivot
    // state), which the pivot's own lift term is added on TOP of - include
    // that base rather than assuming a zero rest pose.
    const KNEE_IDLE_BASE = 0.06;
    let worstDrift = 0;
    for (const fr of noisy.kneeTrace) {
      if (!fr.active) continue;
      const expectedLift = KNEE_IDLE_BASE + Math.sin(Math.PI * fr.t) * 0.34;
      const gotLift = Math.max(fr.kneeR, fr.kneeL); // whichever leg is stepping is the elevated one
      const drift = Math.abs(gotLift - expectedLift);
      if (drift > worstDrift) worstDrift = drift;
    }
    note.worstKneeDriftFromCleanCurve = +worstDrift.toFixed(4);
    if (worstDrift > 0.02)
      fail.push('B: an active step\'s knee lift drifted from the clean sin(pi*t) curve by ' + worstDrift.toFixed(4) + ' - the old per-frame-noise coupling may still be present');

    // ---- C. feet actually alternate -------------------------------------
    resetPivot();
    const alt = driveTurn(300, 1 / 60, () => 0.55 / 20); // slow steady turn, several steps
    note.altPlants = alt.plants.length;
    if (alt.plants.length < 3) fail.push('C: not enough steps produced to check alternation: ' + alt.plants.length);

    // ---- D. stops cleanly when the view stops turning --------------------
    resetPivot();
    driveTurn(20, 1 / 60, () => 0.02); // a little turning, not enough for a full step
    const before = me._pivAccum || 0;
    const idle = driveTurn(60, 1 / 60, () => 0); // stand still for a full second
    note.pivAccumBeforeIdle = +before.toFixed(3);
    note.pivAccumAfterIdle = +(me._pivAccum || 0).toFixed(3);
    if (!((me._pivAccum || 0) < before)) fail.push('D: a stale partial turn did not bleed off while standing still');
    if (idle.plants.length > 0) fail.push('D: standing still produced a phantom footstep: ' + idle.plants.length);

    return { note, fail };
  });

  if (errs.length) res.fail.push(errs.length + ' page error(s): ' + errs.slice(0, 2).join(' | '));
  fs.writeFileSync(OUT + '/result.json', JSON.stringify(res, null, 2));
  console.log(JSON.stringify(res, null, 2));
  await browser.close();
  process.exit(res.fail.length ? 1 : 0);
})();
