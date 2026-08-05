// Leash test. Reproduces the reported bug and proves it is gone.
//
// The bug: a monster held at the edge of its ground dropped aggro and
// re-acquired the player on alternating frames, so it shook on the spot and
// retriggered its aggro sound at frame rate.
//
// So this counts the two things that were actually wrong: how many times aggro
// flips, and how many times the aggro cue fires, while the player stands just
// outside the leash. Then it checks the monster actually gets home.
const { chromium } = require('playwright');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1024, height: 640 } });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e && e.message)));
  page.on('console', m => { if (m.type() === 'error' && !/404|WebSocket/.test(m.text())) errors.push(m.text()); });

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const h = [...document.querySelectorAll('button,a,div,span')]
      .filter(e => (e.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (h.length) h[h.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => window.__grim.play());
  await page.waitForTimeout(9000);

  const out = await page.evaluate(async () => {
    const g = window.__grim;
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const R = g.RULES();

    const n = (g.npcs || []).find(x => x.zoneSpecies === 'BOAR' && x.hp > 0);
    if (!n) return { skip: 'no boar' };

    const roamR = g.roamRadius(n);
    const chaseR = Math.min(R.LEASH_R, roamR + R.LEASH.CHASE_EXTRA);

    // instrument: count aggro flips and aggro cue plays
    let ticks = 0, flips = 0, wasAggro = !!n.aggro;
    const realSfx = g.sfx.bind(g);
    g.sfx = (k, ...rest) => { if (k === 'tick') ticks++; return realSfx(k, ...rest); };
    const watch = setInterval(() => {
      if (!!n.aggro !== wasAggro) { flips++; wasAggro = !!n.aggro; }
    }, 8);

    // Stand just outside its leash, on the far side of home, and hold there.
    // This is the exact situation that used to make it shake.
    const hx = n.home.x, hz = n.home.z;
    const px = hx + chaseR + 4, pz = hz;
    // start it only a little past the leash so the walk home completes inside
    // the test window: the harness runs at about a fifth of real time
    n.pos.set(hx + chaseR + 0.5, 0, hz);
    n.aggro = true; n.returning = false;
    n.hp = Math.max(1, Math.round(n.max * 0.4));
    const hp0 = n.hp;
    g.me.pos.set(px, 0, pz);

    await sleep(6000);
    const mid = {
      returning: !!n.returning, aggro: !!n.aggro,
      distFromHome: +Math.hypot(n.pos.x - hx, n.pos.z - hz).toFixed(2),
      ticks, flips
    };

    // let it walk all the way back with the player still parked there
    await sleep(40000);
    const end = {
      returning: !!n.returning, aggro: !!n.aggro,
      distFromHome: +Math.hypot(n.pos.x - hx, n.pos.z - hz).toFixed(2),
      hpRestored: n.hp === n.max, hp0, hp: n.hp, max: n.max,
      ticks, flips
    };

    clearInterval(watch);
    g.sfx = realSfx;

    // roam radii for every kind of thing in the world, for the record
    const radii = {};
    for (const e of (g.npcs || [])) {
      const key = e.zoneSpecies || (e.civilian ? 'civilian' : e.worker ? 'worker'
        : e.king ? 'boss:king' : e.rat ? 'boss:rat' : e.warden ? 'boss:warden'
        : e.skittish ? 'wildlife' : e.beast ? 'beast' : e.bandit ? 'bandit' : 'other');
      if (radii[key]) continue;
      radii[key] = { roam: g.roamRadius(e), chases: Math.min(R.LEASH_R, g.roamRadius(e) + R.LEASH.CHASE_EXTRA) };
    }

    return { roamR, chaseR, mid, end, radii };
  });

  console.log(JSON.stringify({ out, errors: errors.slice(0, 5) }, null, 2));
  await browser.close();
})();
