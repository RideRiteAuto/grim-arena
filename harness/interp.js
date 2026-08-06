// Proves monster position playback survives network jitter.
//
// The bug this guards: the two interpolation samples were stamped with
// performance.now() at the moment the packet ARRIVED, so the interpolation span
// was the network's jitter rather than the world time the segment covers. Two
// packets coalesced by TCP made a monster cover 100ms of travel in 60ms and
// then hold still; a late packet pinned it at a dead stop.
//
// This runs the real onNpcSnap and the real tick() against a monster walking a
// straight line at a constant 4 m/s, sampled by the "server" every 100ms
// exactly, but DELIVERED with realistic jitter: bunched pairs, late arrivals,
// one outright dropped packet. The wire timestamps stay perfectly regular. Only
// the arrival times move.
//
// It is deterministic: the render loop is frozen, Date.now is a fake clock, and
// tick() is driven with a fixed dt. That matters because the harness runs at
// roughly 20 percent of real time (see README) and any test that judged this by
// wall clock would be measuring SwiftShader, not the fix.
//
// Verified to FAIL before patch 30 with the monster stalling dead for whole
// frames and then sprinting to catch up.
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

    // Freeze the render loop and take the clock, so nothing here depends on how
    // fast this machine actually renders.
    g.alive = false;
    if (g.raf) cancelAnimationFrame(g.raf);
    const realNow = Date.now.bind(Date);
    let T = realNow();
    Date.now = () => T;

    // Look like a protocol-5 relay client so tick() takes the mirror branch.
    g._relayMode = true; g.sharedWorldOn = true; g._srvProto = 5;
    g._ws = { readyState: 1 };
    g._srvSim = true; g._clkOff = 0; g.isWorldHost = false;

    const n = g.npcs.find(v => v.hp > 0 && !v.wraith);
    const idx = g.npcs.indexOf(n);
    const SPEED = 4;                       // m/s, dead constant
    // Snap the path onto the wire grid. Positions go over the wire rounded to
    // 0.1m, and at 4 m/s a 100ms step is exactly 0.4m, so starting on a tenth
    // makes every sample exact and takes wire rounding out of the measurement
    // entirely. That rounding is a real and separate issue (it is worth about
    // 20% apparent speed variance on its own) but it is not what this test is
    // about, and leaving it in here would mask the thing that is.
    const x0 = Math.round((g.me.pos.x + 12) * 10) / 10, z0 = Math.round(g.me.pos.z * 10) / 10;
    n.pos.x = x0; n.pos.z = z0; n.hp = n.max || 30; n.deadHandled = false;

    // The server samples every 100ms of ITS time, forever regular.
    // Arrival offsets are the jitter: 0 = on time, negative = early/bunched,
    // positive = late. One entry is null, a dropped packet.
    const JIT = [0, 0, 40, -30, 0, 90, 0, 0, 55, -45, 0, null, 0, 70, 0, -20,
                 0, 110, 0, 0, 35, -25, 0, 0, 60, 0, -40, 0, 0, 80, 0, 0,
                 25, -15, 0, 0, 95, 0, 0, 30, 0, -35, 0, 0, 65, 0, 0, 0];
    const T0 = T;
    const queue = [];
    JIT.forEach((j, k) => {
      if (j === null) return;
      const at = T0 + k * 100;                  // wire timestamp: perfectly regular
      queue.push({ deliverAt: at + 25 + j, msg: { t: 'nsnap', at, r: [[idx,
        Math.round((x0 + SPEED * (k * 0.1)) * 10), Math.round(z0 * 10),   // exact on the grid by construction
        0, 'walk', 0, 100, 0]] } });
    });
    queue.sort((a, b) => a.deliverAt - b.deliverAt);

    const DT = 1 / 60, STEP = 1000 / 60;
    const xs = [];
    let qi = 0;
    for (let f = 0; f < 300; f++) {
      T += STEP;
      while (qi < queue.length && queue[qi].deliverAt <= T) { g.onNpcSnap(queue[qi].msg); qi++; }
      g._dtReal = DT;
      g._wAt = performance.now();          // the feed is alive; this is the real-clock liveness flag
      try { g.tick(DT); } catch (e) { return { threw: String(e && e.message) }; }
      xs.push(n.pos.x);
    }

    Date.now = realNow;
    return { xs, x0, speed: SPEED, dt: DT, frames: xs.length, dropped: JIT.filter(v => v === null).length };
  });

  const fails = [];
  if (out.threw) {
    console.log(JSON.stringify({ result: 'FAIL', threw: out.threw }, null, 2));
    await browser.close(); process.exit(1);
  }

  // Windowed speed, so the 0.1m wire quantisation (a separate, known issue)
  // does not masquerade as jitter. Six frames is a tenth of a second.
  const W = 6, xs = out.xs;
  const speeds = [];
  // Skip the first 40 frames: the buffer is still filling and the monster is
  // legitimately catching up from wherever the local sim left it.
  for (let i = 40; i + W < xs.length - 10; i++) speeds.push((xs[i + W] - xs[i]) / (W * out.dt));

  const mean = speeds.reduce((a, b) => a + b, 0) / speeds.length;
  const sd = Math.sqrt(speeds.reduce((a, b) => a + (b - mean) * (b - mean), 0) / speeds.length);
  const cv = sd / mean;
  const stalls = speeds.filter(s => s < out.speed * 0.35).length;   // dead stops
  const sprints = speeds.filter(s => s > out.speed * 1.65).length;  // catch-up dashes
  let back = 0;
  for (let i = 1; i < xs.length; i++) if (xs[i] < xs[i - 1] - 0.02) back++;

  // The monster walks a straight line at a constant speed. Everything the
  // player should see is that, regardless of what the network did.
  if (Math.abs(mean - out.speed) > out.speed * 0.15) fails.push(`mean speed ${mean.toFixed(2)} m/s, expected ${out.speed}`);
  if (cv > 0.22) fails.push(`speed varies by ${(cv * 100).toFixed(0)}% against a dead constant source`);
  if (stalls > 0) fails.push(`${stalls} windows stalled below 35% speed`);
  if (sprints > 0) fails.push(`${sprints} windows sprinted above 165% speed`);
  if (back > 2) fails.push(`${back} frames moved BACKWARDS along a one-way path`);

  console.log(JSON.stringify({
    source: `constant ${out.speed} m/s, wire timestamps exactly 100ms apart, ${out.dropped} packet dropped, arrivals jittered -45ms to +110ms`,
    meanSpeed: +mean.toFixed(3),
    speedVariationPct: +(cv * 100).toFixed(1),
    stalledWindows: stalls,
    sprintingWindows: sprints,
    backwardsFrames: back,
    consoleErrors: errs.filter(e => !/404/.test(e)),
    failures: fails,
    result: fails.length ? 'FAIL' : 'PASS'
  }, null, 2));

  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
