// In-game regression test for patch 79.617 (frostbolt model + ice block +
// 25%/1.5s freeze + 15% slow) and (once added) the cross-client projectile
// visibility fix.
//
// Boot sequence copied from harness/rf-hotkey-test.js (the proven route:
// drive __grim.play() directly since headless has no pointer lock to grant).
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

  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);

  const started = await page.evaluate(() => !!(window.__grim && window.__grim.started)).catch(() => false);

  const results = [];
  const check = (label, cond) => results.push({ label, ok: !!cond });
  check('game started', started);

  if (started) {
    // ---- frostKits() builds without throwing, caches, and returns both kits
    const kitInfo = await page.evaluate(() => {
      const g = window.__grim;
      try {
        const k1 = g.frostKits();
        const k2 = g.frostKits();
        return {
          ok: true,
          same: k1 === k2,
          hasBolt: !!(k1 && k1.bolt && typeof k1.bolt.build === 'function' && typeof k1.bolt.tick === 'function'),
          hasBlock: !!(k1 && k1.block && typeof k1.block.build === 'function' && typeof k1.block.tick === 'function')
        };
      } catch (e) { return { ok: false, err: e.message }; }
    });
    check('frostKits() builds without throwing', kitInfo.ok);
    check('frostKits() caches (same object on 2nd call)', kitInfo.same);
    check('frostKits().bolt has build/tick', kitInfo.hasBolt);
    check('frostKits().block has build/tick', kitInfo.hasBlock);

    // ---- fireFrost spawns a real mesh built from frostKits().bolt, not the
    //      old placeholder icosahedron
    const castInfo = await page.evaluate(() => {
      const g = window.__grim;
      const before = g.projectiles ? g.projectiles.length : 0;
      try {
        g.element = 'frost';
        g.me.pos = g.me.pos || new g.T.Vector3(0, 0, 0);
        g.fireFrost(g.me);
      } catch (e) { return { ok: false, err: e.message }; }
      const after = g.projectiles ? g.projectiles.length : 0;
      const p = g.projectiles && g.projectiles[g.projectiles.length - 1];
      return {
        ok: true,
        spawned: after === before + 1,
        isGroup: !!(p && p.mesh && p.mesh.isGroup),
        meshChildren: p && p.mesh ? p.mesh.children.length : -1
      };
    });
    check('fireFrost does not throw', castInfo.ok);
    check('fireFrost spawns a projectile', castInfo.spawned);
    check('frost projectile mesh is the new kit-built group (not a lone icosahedron)', castInfo.isGroup);

    // ---- spawnIceBlock + stepFx 'iceblock' lifecycle: grows in, disposes
    //      cleanly on expiry without throwing (the retireFx-incompatibility
    //      concern from the patch's own design notes)
    const blockInfo = await page.evaluate(() => {
      const g = window.__grim;
      const target = { pos: new g.T.Vector3(2, 0, 2) };
      const fxBefore = g.fx.length;
      try {
        g.spawnIceBlock(target);
      } catch (e) { return { ok: false, stage: 'spawn', err: e.message }; }
      const fxAfterSpawn = g.fx.length;
      const entry = g.fx[g.fx.length - 1];
      const kindOk = entry && entry.kind === 'iceblock';
      const inScene = entry && g.scene.children.includes(entry.mesh);
      try {
        // fast-forward past its life in a few steps, like real frame dt's
        for (let i = 0; i < 20; i++) g.stepFx(0.1);
      } catch (e) { return { ok: false, stage: 'stepFx', err: e.message }; }
      const fxAfterExpiry = g.fx.length;
      const removedFromScene = entry ? !g.scene.children.includes(entry.mesh) : false;
      return {
        ok: true,
        fxBefore, fxAfterSpawn, fxAfterExpiry,
        kindOk, inScene, removedFromScene
      };
    });
    check('spawnIceBlock does not throw', blockInfo.ok);
    check('spawnIceBlock pushes exactly one fx entry', blockInfo.ok && blockInfo.fxAfterSpawn === blockInfo.fxBefore + 1);
    check('fx entry kind is "iceblock"', blockInfo.kindOk);
    check('ice block mesh added to scene', blockInfo.inScene);
    check('stepFx expires and disposes the ice block without throwing (Group-safe cleanup)', blockInfo.ok && blockInfo.fxAfterExpiry === blockInfo.fxBefore);
    check('ice block mesh removed from scene on expiry', blockInfo.removedFromScene);

    // ---- the freeze roll is now probabilistic (25%) and shorter (1.5s), not
    //      the old unconditional 2s. Run applyDamage's freeze branch many
    //      times with freezeCd forced clear each time and check the
    //      DISTRIBUTION lands near 25%, and that a successful roll sets
    //      1.5 (not 2) and spawns a block.
    const freezeInfo = await page.evaluate(() => {
      const g = window.__grim;
      let hits = 0, blocksSpawned = 0, sawWrongDuration = false;
      const N = 400;
      for (let i = 0; i < N; i++) {
        const t = { pos: new g.T.Vector3(0, 0, 0), hp: 100, maxHp: 100, freezeCd: 0, frozen: 0, iframe: 0 };
        const fxBefore = g.fx.length;
        try {
          g.applyDamage(g.me, t, 5, 'frost', t.pos, { magic: true, freeze: true, chill: true });
        } catch (e) { return { ok: false, err: e.message }; }
        if (t.frozen > 0) {
          hits++;
          if (t.frozen !== 1.5) sawWrongDuration = true;
          if (g.fx.length === fxBefore + 1 && g.fx[g.fx.length - 1].kind === 'iceblock') blocksSpawned++;
        }
      }
      return { ok: true, hits, N, blocksSpawned, sawWrongDuration };
    });
    check('applyDamage freeze branch does not throw across many rolls', freezeInfo.ok);
    check('freeze duration is always 1.5s when it lands (never the old 2s)', freezeInfo.ok && !freezeInfo.sawWrongDuration);
    const rate = freezeInfo.ok ? freezeInfo.hits / freezeInfo.N : -1;
    check(`freeze roll rate is near 25% (got ${(rate * 100).toFixed(1)}% over ${freezeInfo.N} trials, want 15-35%)`, rate > 0.15 && rate < 0.35);
    check('every landed freeze also spawned exactly one ice block', freezeInfo.ok && freezeInfo.blocksSpawned === freezeInfo.hits);

    // ---- the slow (opt.chill) is unconditional on every unblocked hit that
    //      deals damage, independent of the freeze roll, and multiplies
    //      speed by 0.85 in both the player and AI speed functions.
    const slowInfo = await page.evaluate(() => {
      const g = window.__grim;
      const t = { pos: new g.T.Vector3(0, 0, 0), hp: 100, maxHp: 100, freezeCd: 999, frozen: 0, iframe: 0, slowT: 0 };
      try {
        g.applyDamage(g.me, t, 5, 'frost', t.pos, { magic: true, freeze: true, chill: true });
      } catch (e) { return { ok: false, err: e.message }; }
      return { ok: true, slowT: t.slowT, notFrozen: t.frozen === 0 };
    });
    check('opt.chill sets slowT even when freezeCd blocks the freeze roll entirely', slowInfo.ok && slowInfo.slowT > 0);
    check('(sanity) that same hit did not freeze, since freezeCd was maxed', slowInfo.notFrozen);
  }

  check('no page/console errors', errors.length === 0);

  console.log(JSON.stringify({ results, errors: errors.slice(0, 20) }, null, 2));
  const failed = results.filter(r => !r.ok);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('TEST CRASHED:', e); process.exit(1); });
