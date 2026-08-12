// Regression test for patch 75.273 (click-to-auto-gather).
// Boots the real bundle via the network-free play() bypass (documented
// login-path limitation: this sandbox cannot complete a real Cloudflare
// login, so this is the same bypass boot.js/craft-flesh-out-test.js use),
// then drives a real click at a real rock via onPrimaryDown() and lets the
// game's own tick loop walk the character in and mine it to depletion.
const { chromium } = require('playwright');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);

  // Accounts are mandatory now (a different track's change) -- no guest
  // button exists anymore, so drive __grim.play() directly, same proven
  // route as harness/rf-hotkey-test.js.
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  let started = false;
  for (let i = 0; i < 10; i++) {
    await page.waitForTimeout(3000);
    started = await page.evaluate(() => !!(window.__grim && window.__grim.started && window.__grim.me)).catch(() => false);
    if (started) break;
    await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  }

  // Set up: equip the starting CRUDE PICK, find a live rock node, place the
  // player 10m off it facing away, then fire the exact same call the real
  // left-click makes.
  const setup = await page.evaluate(() => {
    const g = window.__grim;
    if (!g || !g.me) return { ok: false, reason: 'no grim/me', started: g && g.started, hasGrim: !!g, keys: g ? Object.keys(g).slice(0, 20) : [] };
    let idx = -1;
    for (let i = 0; i < 28; i++) if (g.inv[i] && g.inv[i].item === 'CRUDE PICK') { idx = i; break; }
    if (idx < 0) return { ok: false, reason: 'no CRUDE PICK in starting inventory', inv: g.inv };
    g.equipFromSlot(idx);
    if (g.me.weapon !== 3) return { ok: false, reason: 'equip did not set weapon=3', weapon: g.me.weapon };

    const R = (g.resources || []).find(r => r.kind === 'rock' && !r.dead);
    if (!R) return { ok: false, reason: 'no live rock node found', count: (g.resources || []).length };

    const off = 10;
    g.me.pos.set(R.g.position.x + off, 0, R.g.position.z);
    const to = { x: R.g.position.x - g.me.pos.x, z: R.g.position.z - g.me.pos.z };
    const yaw = Math.atan2(to.x, to.z);
    g.me.yaw = yaw; g.yaw = yaw; g.pitch = -0.1;
    g.me.autoGather = null;

    const before = {
      nodeHp: R.hp, dead: R.dead,
      mining: g.skills.MINING || 0,
      ore: g.invCount('COPPER ORE'),
      dist: g.me.pos.distanceTo(R.g.position)
    };

    g.onPrimaryDown();

    return {
      ok: true, before,
      hasAutoGather: !!g.me.autoGather,
      phase: g.me.autoGather && g.me.autoGather.phase,
      nodeKind: R.kind
    };
  });

  let poll = [];
  let final = null;
  if (setup.ok) {
    for (let i = 0; i < 20; i++) {
      await page.waitForTimeout(3000);
      const snap = await page.evaluate(() => {
        const g = window.__grim;
        const e = g.me;
        const ag = e.autoGather;
        return {
          hasAutoGather: !!ag,
          phase: ag && ag.phase,
          weapon: e.weapon,
          pos: [Math.round(e.pos.x * 10) / 10, Math.round(e.pos.z * 10) / 10],
          mining: g.skills.MINING || 0,
          ore: g.invCount('COPPER ORE')
        };
      });
      poll.push(snap);
      if (!snap.hasAutoGather) { final = snap; break; }
    }
    if (!final) final = poll[poll.length - 1];
  }

  const result = { setup, pollCount: poll.length, poll: poll.slice(0, 6), final };
  console.log(JSON.stringify({ result, errors: errors.slice(0, 30), errorCount: errors.length }, null, 2));
  await browser.close();
  process.exit(errors.length ? 1 : 0);
})();
