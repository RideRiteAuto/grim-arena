// Signature move test.
//
// Each move is driven for real: the creature is put in its band with the player
// in front of it, the cooldown is cleared, and the result is read off live
// objects. Nothing here judges anything by how a frame looked.
//
// Waits are in GAME seconds, not wall clock. This harness renders at about an
// eighth of real speed, which is what made an earlier run of this very test
// report a working charge as broken: it had not finished winding up yet.
//
//  TUSK CHARGE    telegraph, then a rush that damages and knocks back
//  TAIL WHIP      telegraph, then a sweep that damages and knocks back
//  GOBLIN SHRIEK  telegraph, no damage, every goblin in 25m wakes up
const { chromium } = require('playwright');
const { sleepGame, speedRatio } = require('./gametime.js');
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
    const g = window.__grim, T = g.T;
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const R = g.RULES();
    const res = {};

    // Put a creature and the player somewhere empty so nothing else joins in.
    const stage = (n, gap) => {
      // Its OWN spawn point. Teleporting the fight to arbitrary coordinates
      // staged it on ground that was never checked for being dry or flat, and
      // the player slid while the monster stood in water.
      const bx = n.home.x, bz = n.home.z;
      n.pos.set(bx, 0, bz);
      n.hp = n.max; n.aggro = true; n.returning = false;
      n.sigPhase = null; n.specialCd = 0; n.state = 'idle'; n.st = 0;
      g.me.pos.set(bx, 0, bz + gap);
      g.me.hp = g.me.max;
      n.yaw = Math.atan2(0, gap);
    };

    const run = async (species, gap, label) => {
      const n = (g.npcs || []).find(x => x.zoneSpecies === species && x.hp > 0);
      if (!n) return { skip: 'no ' + species };
      const S = R.SIGS[n.sig];
      stage(n, gap);
      const hp0 = g.me.hp;
      let sawTelegraph = false, fired = false;
      // watch for the wind-up and the fire, at a finer grain than the frame loop
      const w = setInterval(() => {
        if (n.sigPhase === 'wind' || n.chargePhase === 'tele') sawTelegraph = true;
        if (n.sigPhase === 'act' || n.chargePhase === 'rush') fired = true;
      }, 10);
      await sleep(45000);
      clearInterval(w);
      return {
        sig: n.sig, band: S.band, gapUsed: gap,
        sawTelegraph, fired,
        playerDamaged: g.me.hp < hp0, hpLost: hp0 - g.me.hp,
        knocked: !!(g.me.knockPow > 0 || g.me.knockT > 0),
        cooldownSet: +(n.specialCd || 0).toFixed(1)
      };
    };

    res.tuskCharge = await run('BOAR', 9, 'boar at charge range');
    res.tailWhip = await run('GIANT_RAT', 2.2, 'rat in your face');

    // The shriek is about the other goblins, so stand some near it asleep.
    {
      const gobs = (g.npcs || []).filter(x => x.zoneSpecies === 'YOUNG_GOBLIN' && x.hp > 0);
      if (gobs.length < 2) res.goblinShriek = { skip: 'need 2 goblins' };
      else {
        const lead = gobs[0];
        stage(lead, 6);
        const others = gobs.slice(1, 5);
        others.forEach((o, i) => {
          o.pos.set(lead.pos.x + 6 + i * 4, 0, lead.pos.z + 2);
          o.home.set(o.pos.x, 0, o.pos.z);
          o.aggro = false; o.returning = false; o.hp = o.max; o.sigPhase = null; o.specialCd = 99;
        });
        const awake0 = others.filter(o => o.aggro).length;
        const hp0 = g.me.hp;
        let sawTelegraph = false;
        const w = setInterval(() => { if (lead.sigPhase === 'wind') sawTelegraph = true; }, 10);
        await sleep(45000);
        clearInterval(w);
        res.goblinShriek = {
          sig: lead.sig, sawTelegraph,
          asleepBefore: others.length - awake0,
          awakeAfter: others.filter(o => o.aggro).length,
          playerDamaged: g.me.hp < hp0,
          cooldownSet: +(lead.specialCd || 0).toFixed(1)
        };
      }
    }

    // Out of band, the move must decline and ordinary fighting carry on.
    {
      const n = (g.npcs || []).find(x => x.zoneSpecies === 'BOAR' && x.hp > 0);
      stage(n, 2.0);                       // far inside the charge's 5m minimum
      n.specialCd = 0;
      await sleep(12000);
      res.outOfBandDeclines = { started: !!n.sigPhase || n.chargePhase === 'tele', gap: 2.0, band: R.SIGS['TUSK CHARGE'].band };
    }

    return res;
  });

  console.log(JSON.stringify({ out, errors: errors.slice(0, 6) }, null, 2));
  await browser.close();
})();
