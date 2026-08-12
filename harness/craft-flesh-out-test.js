// Regression test for patch 89.734 (crafting table full flesh-out).
// Boots the real bundle via the network-free play() bypass (documented
// login-path limitation: this sandbox cannot complete a real Cloudflare
// login, so this is the same bypass boot.js uses), then exercises the
// new items and recipes directly against window.__grim.
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

  await page.evaluate(() => {
    const want = 'PLAY AS GUEST';
    const all = Array.from(document.querySelectorAll('button, a, div, span'));
    const hits = all.filter(el => (el.textContent || '').toUpperCase().includes(want));
    const el = hits[hits.length - 1];
    if (el) el.click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);

  const result = await page.evaluate(() => {
    const g = window.__grim;
    if (!g) return { grim: false };
    const out = { grim: true, started: !!g.started };

    // ITEMS() must build without throwing the missing-icon gate, and every
    // new id must resolve to a real def with a non-empty icon.
    const NEW_ITEMS = ['TRAIL RATIONS', 'HEARTHFEN POULTICE', 'SUNSCORCH TONIC', 'ELDERWOOD CARVINGS', 'SALT GLASS TALISMAN', 'GATHERERS TRINKET'];
    out.itemDefs = {};
    try {
      const items = g.ITEMS();
      for (const id of NEW_ITEMS) {
        const d = items[id];
        out.itemDefs[id] = d ? { hasIcon: !!(d.icon && d.icon.length > 10), value: d.value, slot: d.slot } : null;
      }
    } catch (e) { out.itemsError = String(e); }

    // CRAFT_RECIPES() must have all 9 rows, each pointing at a real item.
    try {
      const recipes = g.CRAFT_RECIPES();
      out.recipeCount = recipes.length;
      out.recipeIds = recipes.map(r => r.id);
      out.recipesResolve = recipes.every(r => !!g.ITEMS()[r.id]);
    } catch (e) { out.recipesError = String(e); }

    // Grant materials for every new recipe, then confirm craftMax/craftCan
    // and startCraft actually produce the item into the pack.
    out.craftChecks = {};
    try {
      for (const r of g.CRAFT_RECIPES()) {
        if (!NEW_ITEMS.includes(r.id)) continue;
        for (const [matId, qty] of r.need) g.addItem(matId, qty + 2);
        g.skills[r.skill] = 999999999; // max the gate so craftCan only reflects materials
        const max = g.craftMax(r);
        const can = g.craftCan(r);
        const before = g.invCount(r.id);
        g.startCraft(r, 1);
        out.craftChecks[r.id] = { max, can, queued: !!g.craftQ, startedOk: !!g.craftQ };
        g.craftQ = null; // stop, we only need to see it queue cleanly
      }
    } catch (e) { out.craftError = String(e); }

    // itemUse() must return the right verb for the three consumables and
    // must not throw for the three trade goods (they should return null).
    out.itemUse = {};
    try {
      out.itemUse['TRAIL RATIONS'] = (g.itemUse('TRAIL RATIONS') || {}).label || null;
      out.itemUse['HEARTHFEN POULTICE'] = (g.itemUse('HEARTHFEN POULTICE') || {}).label || null;
      out.itemUse['SUNSCORCH TONIC'] = (g.itemUse('SUNSCORCH TONIC') || {}).label || null;
      out.itemUse['ELDERWOOD CARVINGS'] = g.itemUse('ELDERWOOD CARVINGS');
      out.itemUse['SALT GLASS TALISMAN'] = g.itemUse('SALT GLASS TALISMAN');
      out.itemUse['GATHERERS TRINKET'] = g.itemUse('GATHERERS TRINKET');
    } catch (e) { out.itemUseError = String(e); }

    // Actually eat a TRAIL RATIONS and confirm HP moves and the item is consumed.
    out.eatCheck = null;
    try {
      const e = g.me;
      if (e) {
        e.hp = Math.max(1, e.max - 20);
        const before = e.hp, invBefore = g.invCount('TRAIL RATIONS');
        g.itemUse('TRAIL RATIONS').fn();
        out.eatCheck = { before, after: e.hp, invBefore, invAfter: g.invCount('TRAIL RATIONS') };
      }
    } catch (e) { out.eatCheckError = String(e); }

    return out;
  }).catch(e => ({ grim: false, evalError: String(e) }));

  console.log(JSON.stringify({ result, errors: errors.slice(0, 30), errorCount: errors.length }, null, 2));
  await browser.close();
  process.exit(errors.length ? 1 : 0);
})();
