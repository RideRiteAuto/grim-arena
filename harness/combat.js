// Proves the position playout buffer did NOT move the moment a blow lands.
//
// Patch 30 draws monsters at a playout point two snapshot intervals behind the
// newest sample, to absorb network jitter. That changes WHERE a body is drawn
// at a given instant, so the fair question is whether it also changed WHEN a
// swing does its damage, and whether the blow is still judged against the body
// the player can actually see (GAME-HANDOFF rules 11 and 12).
//
// It should not have, because the swing rides its own clock: onAttackEvent
// schedules play() off the server's `at`, sets n._atkAt, and stepServerSwing
// fires judgeMyDodge on the frame n.st passes the wind-up. None of that is
// touched by the playout change. This measures it rather than assuming it.
//
// Two scenarios:
//   PLANTED   - what actually happens in game. The server plants an attacker
//               (sim.js zeroes wx/wz on commit), so the playout delay cannot
//               move the body during the damage window at all.
//   MOVING    - the pathological case, a monster still travelling when the
//               blade lands. Reports how far the drawn body is from the
//               server's own position, so the cost is a number and not a
//               shrug.
//
// Deterministic: render loop frozen, fake clock, fixed dt.
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  page.on('pageerror', e => errs.push('PAGEERROR: ' + (e && e.message)));
  await page.goto('http://127.0.0.1:8123/index.html', { waitUntil: 'load' });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);
  for (let i = 0; i < 60; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim._chunks && window.__grim._chunks.size > 50)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(2000);
  }
  await page.waitForFunction(() => window.__grim && window.__grim.started && window.__grim.me && window.__grim.npcs.length, null, { timeout: 60000 });

  const out = await page.evaluate(() => {
    const g = window.__grim;
    g.alive = false;
    if (g.raf) cancelAnimationFrame(g.raf);
    const realNow = Date.now.bind(Date);
    const realPerf = performance.now.bind(performance);
    let T = realNow();
    const TBASE = T, PBASE = realPerf();
    Date.now = () => T;
    // The swing clock runs on performance.now (n._atkAt, and n.st derived from
    // it), so the fake clock has to drive that too or the wind-up never
    // elapses and nothing ever fires.
    performance.now = () => PBASE + (T - TBASE);
    const realTO = window.setTimeout;
    // setTimeout is driven off the fake clock too, or play() would fire on wall
    // time while everything else runs on the test's clock.
    const timers = [];
    window.setTimeout = (fn, ms) => { timers.push({ at: T + (ms || 0), fn }); return 0; };
    const pumpTimers = () => { for (let i = 0; i < timers.length; i++) if (timers[i] && timers[i].at <= T) { const f = timers[i].fn; timers[i] = null; f(); } };

    g._relayMode = true; g.sharedWorldOn = true; g._srvProto = 5;
    g._ws = { readyState: 1 }; g._srvSim = true; g._clkOff = 0; g.isWorldHost = false;

    const realJudge = g.judgeMyDodge.bind(g);
    const run = (moving) => {
      const n = g.npcs.find(v => v.hp > 0 && !v.wraith);
      const idx = g.npcs.indexOf(n);
      n.sbuf = null; n.sbT = null; n.hp = n.max || 30; n.deadHandled = false;
      n.act = null; n._atkAt = 0; n._pend = null; n.hitDone = false; n.state = 'idle';
      g._newestSnapT = null; g._playT = null;
      g.me.hp = g.me.max || 100; g.me.iframe = 0;

      // Stand the monster 2m in front of the player, well inside any reach.
      const SPD = moving ? 3 : 0;
      const z0 = g.me.pos.z, x0 = g.me.pos.x + 2;
      const truth = k => x0 + SPD * (k * 0.1);

      const fired = [];
      g.judgeMyDodge = function (m, nn) {
        fired.push({ srvT: g.srvNow(), st: nn.st, drawnX: nn.pos.x, hpBefore: g.me.hp });
        return realJudge(m, nn);
      };

      const T0 = T, DT = 1 / 60, STEP = 1000 / 60;
      // The swing is announced at T0+600 and the move's wind-up is read off the
      // wire, exactly as the relay sends it.
      const WIND = 0.45, ACT = 0.2, REC = 0.35;
      let announced = false;
      let atkSrvT = null, k = 0;
      for (let f = 0; f < 180; f++) {
        T += STEP;
        // 10Hz feed, no jitter: this test is about the blow, not the network.
        // Once the swing is announced the feed reports it, exactly as the relay
        // does. Feeding idle rows through a swing is not a realistic fixture:
        // it cancels the attack, which is correct behaviour and was quietly
        // making an earlier version of this test measure nothing at all.
        while (T0 + k * 100 <= T - 25) {
          const swinging = announced && (T0 + k * 100) < atkSrvT + (WIND + ACT + REC) * 1000;
          g.onNpcSnap({ t: 'nsnap', at: T0 + k * 100, r: [[idx, Math.round(truth(k) * 10), Math.round(z0 * 10), 0,
            swinging ? 'attack' : (moving ? 'walk' : 'idle'), 0, (moving && !swinging) ? 100 : 0, swinging ? 'light' : 0]] });
          k++;
        }
        if (!announced && T >= T0 + 600) {
          announced = true;
          atkSrvT = T;                       // server time the swing begins
          g.onAttackEvent({ t: 'atk', i: idx, m: 'light', at: atkSrvT, w: WIND, a: ACT, r: REC,
                            x: truth(6), z: z0, yaw: 0, rng: 6, arc: 3.2, dmg: 5 });
        }
        pumpTimers();
        g._dtReal = DT; g._wAt = performance.now();
        try { g.tick(DT); } catch (e) { return { threw: String(e && e.message) }; }
      }
      g.judgeMyDodge = realJudge;
      const hit = fired[0] || null;
      return {
        moving, fired: fired.length,
        // ms from the announced start of the swing to the damage instant
        windDelayMs: hit ? Math.round(hit.srvT - atkSrvT) : null,
        expectedWindMs: Math.round(WIND * 1000),
        stAtHit: hit ? +hit.st.toFixed(3) : null,
        drawnX: hit ? +hit.drawnX.toFixed(3) : null,
        serverX: hit ? +truth((hit.srvT - T0) / 100).toFixed(3) : null,
        playerHp: g.me.hp, playerMax: g.me.max || 100
      };
    };

    const planted = run(false);
    const moving = run(true);
    Date.now = realNow; window.setTimeout = realTO; performance.now = realPerf;
    return { planted, moving };
  });

  const fails = [];
  if (out.threw) { console.log(JSON.stringify({ result: 'FAIL', threw: out.threw }, null, 2)); await browser.close(); process.exit(1); }
  const P = out.planted, M = out.moving;

  // 1. The blow fires, once, and at the wind-up. This is the whole question.
  if (P.fired !== 1) fails.push(`planted: judgeMyDodge fired ${P.fired} times, expected exactly 1`);
  if (P.windDelayMs == null || Math.abs(P.windDelayMs - P.expectedWindMs) > 34) {
    fails.push(`planted: damage landed ${P.windDelayMs}ms after the swing began, wind-up is ${P.expectedWindMs}ms`);
  }
  if (P.stAtHit == null || P.stAtHit < 0.45 || P.stAtHit > 0.45 + 0.2) {
    fails.push(`planted: animation clock read ${P.stAtHit}s at the damage instant, expected between the wind-up and the end of the active window`);
  }
  // 2. Planted is the real case: the drawn body IS the server's body.
  if (P.drawnX != null && Math.abs(P.drawnX - P.serverX) > 0.02) {
    fails.push(`planted: drawn body ${Math.abs(P.drawnX - P.serverX).toFixed(3)}m from the server's, expected 0`);
  }
  // 3. It actually connected on a player standing 2m away inside the arc.
  if (P.playerHp >= P.playerMax) fails.push('planted: the blow did no damage to a player standing 2m in front of it');
  // 4. Moving case: still on time. Position error is reported, not asserted, but
  //    it must not be so large that a landed blow turns into a miss.
  if (M.fired !== 1) fails.push(`moving: judgeMyDodge fired ${M.fired} times, expected exactly 1`);
  if (M.windDelayMs == null || Math.abs(M.windDelayMs - M.expectedWindMs) > 34) {
    fails.push(`moving: damage landed ${M.windDelayMs}ms after the swing began, wind-up is ${M.expectedWindMs}ms`);
  }
  if (M.playerHp >= M.playerMax) fails.push('moving: the blow did no damage');

  console.log(JSON.stringify({
    planted: {
      note: 'what actually happens: the server plants an attacker on commit',
      damageLandedAfterMs: P.windDelayMs, windUpIsMs: P.expectedWindMs,
      animationClockAtHit: P.stAtHit,
      drawnBodyVsServerBody: P.drawnX != null ? +(P.drawnX - P.serverX).toFixed(3) : null,
      playerTookDamage: P.playerHp < P.playerMax
    },
    movingWhileSwinging: {
      note: 'pathological case, reported so the cost of the playout buffer is a number',
      damageLandedAfterMs: M.windDelayMs, windUpIsMs: M.expectedWindMs,
      drawnBodyVsServerBody: M.drawnX != null ? +(M.drawnX - M.serverX).toFixed(3) : null,
      playerTookDamage: M.playerHp < M.playerMax
    },
    consoleErrors: errs.filter(e => !/404/.test(e)),
    failures: fails,
    result: fails.length ? 'FAIL' : 'PASS'
  }, null, 2));

  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
