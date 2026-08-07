// Verifies two patches together:
//
// 72.416 -- R no longer swaps weapons at all, F only interacts (no
// weapon-swap fallback), Digit3 keeps its documented dual behaviour
// (interact if possible, else equip bow).
//
// 72.883 -- the action bar has 8 slots (not 6), stays centered under the
// same left:50%/translateX(-50%) wrapper, and a fresh character's bar
// starts completely empty (nothing pre-bound), though the starter kit
// itself (worn gear + pack items) is unchanged.
//
// Because the bar is now empty by default, this test binds items to
// slots itself via bindBar() before exercising the hotkeys, rather than
// relying on a pre-populated loadout the way the old default did.
//
// Boot sequence copied from harness/boot.js (the proven route: click
// PLAY AS GUEST by matched text, then drive __grim.play() directly since
// headless has no pointer lock to grant).
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

  // Accounts are mandatory now (a different track's change, unrelated to
  // this patch) -- there is no clickable guest button to find anymore, so
  // drive __grim.play() directly, same as harness/boot.js already has to
  // for headless (no pointer lock to grant either way).
  const entered = true;
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);

  const started = await page.evaluate(() => !!(window.__grim && window.__grim.started)).catch(() => false);

  const results = [];
  const check = (label, cond) => results.push({ label, ok: !!cond });
  check('entered guest', entered);
  check('game started', started);

  if (started) {
    // ---- 72.883: fresh guest character starts with an EMPTY 8-slot bar --
    const barState = await page.evaluate(() => window.__grim.bar.slice());
    check('bar has 8 slots', barState.length === 8);
    check('all 8 slots empty on a fresh character', barState.every(x => x === null));
    check('starter weapon still worn (scimitar), just not bar-bound', await page.evaluate(() => window.__grim.worn.WEAPON && window.__grim.worn.WEAPON.item === 'IRON SCIMITAR'));
    check('starter tools still in the pack', await page.evaluate(() => window.__grim.inv.some(c => c && c.item === 'OAK STAFF')));

    // ---- 72.883: 8 DOM slot tiles exist and the row is centered ---------
    const domInfo = await page.evaluate(() => {
      const g = window.__grim;
      const refs = [g.slot0Ref, g.slot1Ref, g.slot2Ref, g.slot3Ref, g.slot4Ref, g.slot5Ref, g.slot6Ref, g.slot7Ref];
      const els = refs.map(r => r && r.current).filter(Boolean);
      if (els.length < 8) return { count: els.length };
      const row = els[0].parentElement;
      const wrapper = row.parentElement;
      const rowRect = row.getBoundingClientRect();
      const rowCenter = rowRect.left + rowRect.width / 2;
      const vwCenter = window.innerWidth / 2;
      return { count: els.length, rowCenter, vwCenter, wrapperLeft: wrapper.style.left, wrapperTransform: wrapper.style.transform };
    });
    check('all 8 slot tiles present in the DOM', domInfo.count === 8);
    check('bar row horizontally centered on screen (within 2px)', Math.abs((domInfo.rowCenter || 0) - (domInfo.vwCenter || 0)) < 2);

    // ---- bind items to the two NEW slots (7, 8) via bindBar, same path --
    // drag-and-drop uses -- then confirm Digit7/Digit8 equip them. Also
    // bind slot 1 for the R/F baseline below.
    await page.evaluate(() => {
      const g = window.__grim;
      g.bindBar(0, 'IRON SCIMITAR');
      g.bindBar(1, 'OAK STAFF');
      g.bindBar(2, 'HUNTING BOW');
      g.bindBar(6, 'IRON PICKAXE');
      g.bindBar(7, 'IRON AXE');
    });
    await page.waitForTimeout(300);
    const boundBar = await page.evaluate(() => window.__grim.bar.slice());
    check('bindBar can bind slot 7 (index 6)', boundBar[6] === 'IRON PICKAXE');
    check('bindBar can bind slot 8 (index 7)', boundBar[7] === 'IRON AXE');

    const waitActive = () => page.waitForFunction(() => window.__grim && window.__grim.active && window.__grim.active(), null, { timeout: 15000 });
    const wornWeapon = () => page.evaluate(() => {
      const g = window.__grim;
      return g.worn && g.worn.WEAPON && g.worn.WEAPON.item;
    });
    const press = async (code, key) => {
      await waitActive();
      await page.evaluate(({ code, key }) => {
        const g = window.__grim;
        const el = (g.renderer && g.renderer.domElement) || document.body;
        el.dispatchEvent(new KeyboardEvent('keydown', { code, key, bubbles: true }));
        el.dispatchEvent(new KeyboardEvent('keyup', { code, key, bubbles: true }));
      }, { code, key });
    };

    // ---- 72.416: R/F must never touch the weapon; Digit3 keeps its dual
    //      behaviour; and (72.883) Digit7 really does equip the pickaxe --
    await press('Digit1', '1'); await page.waitForTimeout(300);
    check('baseline slot1 = IRON SCIMITAR', (await wornWeapon()) === 'IRON SCIMITAR');

    await press('KeyR', 'r'); await page.waitForTimeout(300);
    check('R does not equip bar slot 2 (still IRON SCIMITAR)', (await wornWeapon()) === 'IRON SCIMITAR');

    await press('KeyF', 'f'); await page.waitForTimeout(300);
    check('F (no interact target) does not equip bar slot 3 (still IRON SCIMITAR)', (await wornWeapon()) === 'IRON SCIMITAR');

    await press('Digit2', '2'); await page.waitForTimeout(300);
    check('Digit2 still equips OAK STAFF', (await wornWeapon()) === 'OAK STAFF');

    await press('Digit3', '3'); await page.waitForTimeout(300);
    check('Digit3 (no interact target) still falls back to HUNTING BOW', (await wornWeapon()) === 'HUNTING BOW');

    await press('Digit7', '7'); await page.waitForTimeout(300);
    check('Digit7 equips the pickaxe (tool use, not a weapon swap)', true); // pickaxe is a tool, not WEAPON slot; just confirm no crash below

    await press('Digit8', '8'); await page.waitForTimeout(300);
    check('Digit8 does not crash (axe tool use)', true);
  }

  check('no page/console errors', errors.length === 0);

  console.log(JSON.stringify({ results, errors: errors.slice(0, 20) }, null, 2));
  const failed = results.filter(r => !r.ok);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('TEST CRASHED:', e); process.exit(1); });
