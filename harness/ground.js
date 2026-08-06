// Proves a distant NPC stays on the ground, and stops blinking at the cull line.
//
// The bug this guards: animate() owned the only write of g.position.y, and
// animate() is skipped on 2 of 3 frames past 50m and 5 of 6 past 85m. On every
// skipped frame the body was drawn at y = 0, absolute sea level. Terrain here
// runs from -27m to +87m, so a distant NPC was being thrown roughly 23 metres
// vertically at 10-20Hz. That was the "flash and flicker".
//
// The second bug: hide at 90m was a bare compare on a distance that moves every
// frame, so an NPC pacing the line blinked in and out once per pass.
//
// Verified to FAIL on the bundle before patch 29: the y samples read
// 0, 0, 0, -0.542, 0, 0, ... and the visibility log flipped on every crossing.
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await page.goto('http://127.0.0.1:8123/index.html', { waitUntil: 'load' });
  await page.waitForTimeout(6000);
  // Same route into gameplay boot.js uses: click the guest button by its text,
  // then drive play() directly, because headless has no pointer lock to grant.
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

  const out = await page.evaluate(async () => {
    const g = window.__grim, me = g.me;
    const frame = () => new Promise(r => requestAnimationFrame(() => r()));

    // Find a spot with real terrain under it, far enough out to be thinned.
    // The starting grassland is flattened to h = 0, which is exactly why this
    // bug hid for so long, so search outward for ground that is not flat.
    let spot = null;
    for (let r = 60; r <= 88 && !spot; r += 2) {
      for (let a = 0; a < 24; a++) {
        const x = me.pos.x + Math.cos(a / 24 * 6.283) * r, z = me.pos.z + Math.sin(a / 24 * 6.283) * r;
        const h = g.groundY(x, z);
        if (Math.abs(h) > 0.25) { spot = { x, z, h, r }; break; }
      }
    }
    if (!spot) return { skipped: 'no non-flat ground within the thinning band' };

    const n = g.npcs.find(v => v.hp > 0 && !v.wraith);
    n.pos.x = spot.x; n.pos.z = spot.z; n.pos.y = 0;
    n.home && (n.home.x = spot.x, n.home.z = spot.z);
    n.aggro = false; n.state = 'idle';

    // Hold it there and read the actual rendered height every frame.
    const ys = [];
    for (let i = 0; i < 30; i++) { n.pos.x = spot.x; n.pos.z = spot.z; await frame(); ys.push(+n.g.position.y.toFixed(3)); }

    // Now walk it back and forth across the 90m cull line and watch for blinks.
    const vis = [];
    for (let i = 0; i < 40; i++) {
      const d = 88 + Math.sin(i / 3) * 4;                 // 84m .. 92m
      n.pos.x = me.pos.x + d; n.pos.z = me.pos.z;
      await frame();
      vis.push(n.g.visible ? 1 : 0);
    }
    let flips = 0;
    for (let i = 1; i < vis.length; i++) if (vis[i] !== vis[i - 1]) flips++;

    return { spot, ys, expectedH: +spot.h.toFixed(3), visFlips: flips, visPattern: vis.join('') };
  });

  const fails = [];
  if (out.skipped) {
    console.log(JSON.stringify({ result: 'SKIP', why: out.skipped }, null, 2));
    await browser.close();
    process.exit(0);
  }

  // 1. Every frame must sit on the ground. Not most frames. Every frame.
  const atSea = out.ys.filter(y => Math.abs(y) < 0.02).length;
  const onGround = out.ys.filter(y => Math.abs(y - out.expectedH) < 0.25).length;
  if (atSea > 0) fails.push(`${atSea} of ${out.ys.length} frames drew the body at sea level (y ~ 0) while the ground is at ${out.expectedH}`);
  if (onGround !== out.ys.length) fails.push(`only ${onGround} of ${out.ys.length} frames sat on the ground at ${out.expectedH}`);

  // 2. The height must not jump around between frames.
  let worst = 0;
  for (let i = 1; i < out.ys.length; i++) worst = Math.max(worst, Math.abs(out.ys[i] - out.ys[i - 1]));
  if (worst > 0.2) fails.push(`vertical jump of ${worst.toFixed(3)}m between consecutive frames`);

  // 3. Crossing the cull line must not blink. With hysteresis a sweep that
  //    straddles the line should settle, not toggle on every pass.
  if (out.visFlips > 4) fails.push(`visibility flipped ${out.visFlips} times across the cull line: ${out.visPattern}`);

  console.log(JSON.stringify({
    testedAt: `${out.spot.r}m out, ground height ${out.expectedH}m`,
    renderedHeights: out.ys,
    framesAtSeaLevel: atSea,
    worstFrameToFrameJump: +worst.toFixed(3),
    cullLineVisibilityFlips: out.visFlips,
    consoleErrors: errs.filter(e => !/404/.test(e)),
    failures: fails,
    result: fails.length ? 'FAIL' : 'PASS'
  }, null, 2));

  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
