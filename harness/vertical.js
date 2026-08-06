// Phase 1d proof: real elevation for the player, behind GRIM_RULES.VERT.ELEV.
//
// Boots the real bundle, enters gameplay as a guest, then drives the player
// by hand with the render loop running and reads e.elev / worldY frame by
// frame on the game's own clock. Checks, in order:
//
//   grounded   standing still, elev equals the terrain under the feet
//   jump       ballistic rise to about the old 1.15m apex, then a landing
//   fall       teleported 6m above ground, the player FALLS (elev decreases
//              monotonically) and lands on the surface, not through it
//   bridge     standing on a crossing's deck, elev equals the deck height
//              from the game's own bridgeDeckY, and swimF stays false
//   water      standing in deep water, physics suspended (swimF true)
//   switch     ELEV off restores the glued-to-ground formula exactly
//
// The harness renders at ~0.125x real time; everything below waits on game
// state, never on wall clock.
const { chromium } = require('playwright');

const fail = [];
const ok = (name, cond, detail) => {
  console.log((cond ? '  ok     ' : '  FAIL   ') + name + (detail ? ('  (' + detail + ')') : ''));
  if (!cond) fail.push(name);
};

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox'],
  });
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('http://127.0.0.1:8123/index.html', { waitUntil: 'load', timeout: 90000 });
  await page.waitForFunction(() => typeof window.__grim === 'object', null, { timeout: 90000 });

  // Enter the world as a guest exactly the way boot.js does.
  await page.evaluate(() => {
    const want = 'PLAY AS GUEST';
    const all = Array.from(document.querySelectorAll('button, a, div, span'));
    const hits = all.filter(el => (el.textContent || '').toUpperCase().includes(want));
    const el = hits[hits.length - 1];
    if (el) el.click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForFunction(() => {
    const g = window.__grim;
    return g && g.started && g.me && g.worldOn && g.mode === 'ai';
  }, null, { timeout: 120000 });
  await page.waitForTimeout(4000);

  // Helper: run inside the page against the live game.
  const evalG = (fn, arg) => page.evaluate(fn, arg);

  // ---- grounded ----------------------------------------------------------
  const grounded = await evalG(() => {
    const g = window.__grim, me = g.me;
    g.VERT.ELEV = true;
    // stand somewhere plain near the camp and let a few frames settle
    me.pos.set(60, 0, 40); me.elev = null; me._vy = 0; me._air = false;
    g._terrAcc = 99; if (g.stepTerrain) g.stepTerrain(0, 260);
    return null;
  });
  await page.waitForTimeout(2500);
  const g1 = await evalG(() => {
    const g = window.__grim, me = g.me;
    return { elev: me.elev, ground: g.groundY(me.pos.x, me.pos.z), air: !!me._air, elevFlag: !!me._elev };
  });
  ok('the elevation flag is live', g1.elevFlag);
  ok('grounded elev equals the terrain underfoot', g1.elev != null && Math.abs(g1.elev - g1.ground) < 0.02, 'elev ' + (g1.elev && g1.elev.toFixed ? g1.elev.toFixed(2) : g1.elev) + ' vs ground ' + g1.ground.toFixed(2));
  ok('standing still is not airborne', !g1.air);

  // ---- jump --------------------------------------------------------------
  await evalG(() => { const g = window.__grim; g._jumpTrace = []; g.tryJump(); });
  await page.waitForFunction(() => {
    const g = window.__grim, me = g.me;
    if (me._air) g._jumpTrace.push(me.elev);
    return !me._air && g._jumpTrace.length > 3;   // took off and landed again
  }, null, { timeout: 60000 });
  const j = await evalG(() => {
    const g = window.__grim, me = g.me;
    const base = g.groundY(me.pos.x, me.pos.z);
    const apex = Math.max.apply(null, g._jumpTrace) - base;
    return { apex, endElev: me.elev, ground: base };
  });
  ok('the jump rises to about the old 1.15m apex', j.apex > 0.7 && j.apex < 1.5, 'apex ' + j.apex.toFixed(2) + 'm');
  ok('the jump lands back on the surface', Math.abs(j.endElev - j.ground) < 0.02);

  // ---- fall --------------------------------------------------------------
  await evalG(() => {
    const g = window.__grim, me = g.me;
    me.elev = g.groundY(me.pos.x, me.pos.z) + 6; me._air = true; me._vy = 0;
    g._fallTrace = [];
  });
  await page.waitForFunction(() => {
    const g = window.__grim, me = g.me;
    if (me._air) g._fallTrace.push(me.elev);
    return !me._air && g._fallTrace.length > 2;
  }, null, { timeout: 60000 });
  const f = await evalG(() => {
    const g = window.__grim, me = g.me;
    const t = g._fallTrace;
    let monotone = true;
    for (let i = 1; i < t.length; i++) if (t[i] > t[i - 1] + 1e-6) monotone = false;
    return { monotone, endElev: me.elev, ground: g.groundY(me.pos.x, me.pos.z), frames: t.length, landed: me._landed || 0 };
  });
  ok('a dropped player falls monotonically', f.monotone, f.frames + ' airborne frames');
  ok('the fall lands on the surface, not through it', Math.abs(f.endElev - f.ground) < 0.02);
  ok('the landing records its impact speed for later phases', f.landed > 5, f.landed.toFixed(1) + ' m/s');

  // ---- bridge deck -------------------------------------------------------
  const b = await evalG(() => {
    const g = window.__grim, me = g.me;
    // GRIM_WORLD is module-scoped, so find a crossing through the game's own
    // deck query: coarse grid sweep, then stand on the first deck found.
    let bx = null, bz = null;
    outer: for (let x = -2000; x <= 2000; x += 60) {
      for (let z = -2000; z <= 2000; z += 60) {
        if (g.bridgeDeckY(x, z) !== null) { bx = x; bz = z; break outer; }
      }
    }
    if (bx === null) return { skip: true };
    me.pos.set(bx, 0, bz); me.elev = null; me._vy = 0; me._air = false;
    g._terrAcc = 99; if (g.stepTerrain) g.stepTerrain(0, 260);
    return { deck: g.bridgeDeckY(bx, bz) };
  });
  await page.waitForTimeout(2500);
  const b2 = await evalG(() => {
    const g = window.__grim, me = g.me;
    return { elev: me.elev, swim: !!me.swimF, deck: g.bridgeDeckY(me.pos.x, me.pos.z) };
  });
  if (b.skip) ok('bridge deck check (skipped: no bridges in bake)', true);
  else {
    ok('standing on a crossing puts you on the deck', b2.deck != null && Math.abs(b2.elev - b2.deck) < 0.02, 'elev ' + b2.elev.toFixed(2) + ' vs deck ' + (b2.deck == null ? 'null' : b2.deck.toFixed(2)));
    ok('a deck over water does not read as swimming', !b2.swim);
  }

  // ---- deep water --------------------------------------------------------
  await evalG(() => {
    const g = window.__grim, me = g.me;
    // march outward from the camp until the water is genuinely deep
    let fx = null, fz = null;
    outer: for (let r = 40; r < 1200; r += 12) {
      for (let a = 0; a < 6.28; a += 0.4) {
        const x = 41 + Math.cos(a) * r, z = 31 + Math.sin(a) * r;
        if (g.waterDepthAt(x, z) > 1.6) { fx = x; fz = z; break outer; }
      }
    }
    if (fx !== null) { me.pos.set(fx, 0, fz); me.elev = null; me._vy = 0; me._air = false; g._terrAcc = 99; if (g.stepTerrain) g.stepTerrain(0, 260); }
    g._deepFound = fx !== null;
  });
  await page.waitForTimeout(2500);
  const w = await evalG(() => {
    const g = window.__grim, me = g.me;
    return { found: g._deepFound, swim: !!me.swimF, air: !!me._air };
  });
  if (!w.found) ok('deep water check (skipped: none found near camp)', true);
  else {
    ok('deep water reads as swimming', w.swim);
    ok('swimming suspends the fall physics', !w.air);
  }

  // ---- the switch --------------------------------------------------------
  const sw = await evalG(() => {
    const g = window.__grim, me = g.me;
    g.VERT.ELEV = false;
    me.pos.set(60, 0, 40); me.elev = null; me._vy = 0; me._air = false;
    return null;
  });
  await page.waitForTimeout(1500);
  const s2 = await evalG(() => {
    const g = window.__grim, me = g.me;
    const gy = g.groundY(me.pos.x, me.pos.z);
    return { elevFlag: !!me._elev, wy: g.worldY(me), oldFormula: (me.pos.y || 0) + gy };
  });
  ok('ELEV off drops the flag', !s2.elevFlag);
  ok('ELEV off restores the old height formula exactly', Math.abs(s2.wy - s2.oldFormula) < 1e-9);
  await evalG(() => { window.__grim.VERT.ELEV = true; });

  const newErrors = errors.filter(e => !/404|net::|workers\.dev/.test(e));
  ok('no new console errors', newErrors.length === 0, newErrors.slice(0, 2).join(' | '));

  console.log(fail.length ? '\nFAILURES: ' + fail.join(', ') : '\nall vertical checks passed');
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
