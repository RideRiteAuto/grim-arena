// Skills-core test. Boots into gameplay, then drives real harvests through the
// real code path and reads the results off the live objects rather than judging
// anything from a screenshot.
//
// Covers: harvest yields and XP, the two gate refusals naming their exact
// requirement, the wrong-tool refusal, tool tier detection, and the save
// migration from the old curve.
const { chromium } = require('playwright');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1024, height: 640 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));
  page.on('console', m => { if (m.type() === 'error' && !/404/.test(m.text())) errors.push(m.text()); });

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const want = 'PLAY AS GUEST';
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes(want));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); });
  await page.waitForTimeout(8000);

  const out = await page.evaluate(() => {
    const g = window.__grim, T = g.T;
    const res = [];
    const banners = [];
    const realBanner = g.banner.bind(g);
    g.banner = (a, b, c, d) => { banners.push([a, b].filter(Boolean).join(' | ')); return realBanner(a, b, c, d); };

    const countItem = (id) => {
      let n = 0;
      for (const c of g.inv || []) if (c && c.item === id) n += c.qty;
      return n;
    };
    // Stand at a node, face it, and swing until it gives.
    const swingAt = (R, times) => {
      g.me.pos.set(R.g.position.x, 0, R.g.position.z - 2.0);
      g.me.yaw = 0;                                   // +z is yaw 0
      for (let i = 0; i < times; i++) g.gatherCheck(g.me);
    };
    const findLive = (kind) => (g.resources || []).find(R => R.kind === kind && !R.dead);

    // ---- 1. a plain tree with the crude axe: yields, XP, and it falls
    const setWeapon = (id) => {
      g.worn.WEAPON = id ? { item: id, qty: 1 } : null;
      const d = id ? g.itemDef(id) : null;
      g.me.weapon = d ? d.wieldAs : 0;
    };
    setWeapon('CRUDE AXE');
    let tree = findLive('tree');
    if (tree) {
      const logs0 = countItem('LOGS'), xp0 = g.skills.WOODCUTTING || 0;
      banners.length = 0;
      swingAt(tree, 6);
      res.push({ t: 'chop tree', dead: !!tree.dead, logsGained: countItem('LOGS') - logs0, xpGained: (g.skills.WOODCUTTING || 0) - xp0, banners: banners.slice() });
    } else res.push({ t: 'chop tree', skip: 'no live tree' });

    // ---- 2. wrong tool: swing a pick at a tree
    setWeapon('CRUDE PICK');
    tree = findLive('tree');
    if (tree) { banners.length = 0; swingAt(tree, 1); res.push({ t: 'pick at tree', banners: banners.slice(), dead: !!tree.dead }); }

    // ---- 3. skill gate: a great oak needs WOODCUTTING 5
    setWeapon('CRUDE AXE');
    const oak = findLive('oak');
    if (oak) {
      const keep = g.skills.WOODCUTTING;
      g.skills.WOODCUTTING = 0;
      banners.length = 0; swingAt(oak, 1);
      const lowLvl = banners.slice();
      g.skills.WOODCUTTING = keep;
      res.push({ t: 'oak under level', banners: lowLvl, stillAlive: !oak.dead });
    } else res.push({ t: 'oak under level', skip: 'no live oak' });

    // ---- 4. tool gate: force a node that needs a tier the player lacks
    const R2 = findLive('tree');
    if (R2) {
      const NODES = g.constructor && null;
      // borrow a real high-tier node definition by relabelling one live tree
      const kindWas = R2.kind;
      R2.kind = 'icewood';                 // WOODCUTTING 60, tier 4 axe
      g.skills.WOODCUTTING = g.xpFor(70);  // level is fine, the axe is not
      banners.length = 0; swingAt(R2, 1);
      res.push({ t: 'icewood with crude axe', banners: banners.slice(), stillAlive: !R2.dead });
      R2.kind = kindWas;
      g.skills.WOODCUTTING = 0;
    }

    // ---- 5. tool tier detection off the pack
    const tiers = {};
    for (const id of ['CRUDE AXE', 'BRONZE AXE', 'IRON AXE', 'STEEL AXE', 'OBSIDIAN AXE', 'MASTERWORK AXE']) {
      g.inv[27] = { item: id, qty: 1 };
      tiers[id] = g.toolTierFor('WOODCUTTING');
    }
    g.inv[27] = null;

    // ---- 6. save migration off the old curve
    const mig = [];
    for (const oldXp of [0, 60, 1000, 50000, 400000]) {
      const store = { skills: { WOODCUTTING: oldXp }, skillCurve: 0 };
      const before = Math.min(99, Math.max(1, Math.floor(Math.pow(oldXp / 60, 0.6)) + 1));
      g.migrateSkillCurve(store);
      mig.push({ oldXp, oldLevel: before, newXp: store.skills.WOODCUTTING, newLevel: g.lvl(store.skills.WOODCUTTING), ranTwice: g.migrateSkillCurve(store) });
    }

    g.banner = realBanner;
    return { res, tiers, mig, itemsDefined: ['CRUDE AXE', 'MASTERWORK PICKAXE', 'ICEWOOD', 'BLACK LOTUS', 'GEM SHARD'].map(i => [i, !!g.itemDef(i)]) };
  });

  console.log(JSON.stringify({ out, errors }, null, 2));
  await browser.close();
  process.exit(errors.length ? 1 : 0);
})();
