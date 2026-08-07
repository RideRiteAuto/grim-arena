// Prove the new furnace in the REAL game, not the lab: built by
// buildCampForge, ticked by the frame loop, smelting every ore through the
// real inventory, level gate holding, colliders pushing back.
//
//   node harness/serve.js & node harness/furnace-ingame.js
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/furnace-ingame';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox', '--autoplay-policy=no-user-gesture-required']
  });
  const page = await browser.newPage({ viewport: { width: 1180, height: 700 } });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e && e.message)));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll('button, a, div, span'));
    const hits = all.filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    const el = hits[hits.length - 1];
    if (el) el.click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);
  await page.waitForFunction(() => {
    const g = window.__grim;
    return g && g.started && g.me && g.me.g;
  }, null, { timeout: 150000 });
  await page.waitForTimeout(2000);

  const res = await page.evaluate(async () => {
    const g = window.__grim, T = g.T;
    const out = { fail: [] };
    if (!g.furnace) { out.fail.push('no furnace'); return out; }
    if (!g.furnace.kit) out.fail.push('furnace has no kit - old prop still built');
    if (!g.furnace.light) out.fail.push('no furnace light');
    if (!g.furnace.rec || !g.furnace.rec.g) out.fail.push('no built group');

    // structure: enough meshes to be the new build, materials shared
    let meshes = 0, tris = 0;
    g.furnace.rec.g.traverse(o => {
      if (!o.isMesh) return;
      meshes++;
      const p = o.geometry.attributes.position;
      tris += (o.geometry.index ? o.geometry.index.count : p.count) / 3;
    });
    out.meshes = meshes; out.tris = Math.round(tris);
    if (meshes < 12) out.fail.push('too few meshes: old prop? ' + meshes);

    // the tick moves the shader clock and the bellows
    const kit = g.furnace.kit;
    const t0 = kit.mats.flame.userData.U ? kit.mats.flame.userData.U.uTime.value : -1;
    const b0 = kit._anim.length ? kit._anim[0].upperPiv.rotation.z : -9;
    await new Promise(r => setTimeout(r, 900));
    const t1 = kit.mats.flame.userData.U ? kit.mats.flame.userData.U.uTime.value : -1;
    out.flameClock = [t0, t1];
    if (!(t1 > t0)) out.fail.push('flame clock not ticking');
    if (kit._anim.length === 0) out.fail.push('no bellows registered');

    // colliders registered: the furnace body plus its three furniture rings
    const near = (g.colliders || []).filter(c => Math.hypot(c.x - 33.5, c.z - 24.5) < 2.6);
    out.colliders = near.length;
    if (near.length < 4) out.fail.push('missing station colliders: ' + near.length);

    // ---- smelting, the real inventory ----
    g.me.pos.set(33.5, g.me.pos.y, 27.2);
    g.me.g.position.set(33.5, g.me.g.position.y, 27.2);
    const inv0 = { cu: g.invCount('COPPER BAR'), fe: g.invCount('IRON BAR'), au: g.invCount('GOLD BAR') };
    g.addItem('COPPER ORE', 1); g.addItem('IRON ORE', 1); g.addItem('GOLD ORE', 1);
    if (g.audioInit) g.audioInit();
    const started = g.trySmelt();
    out.smeltStarted = started && g.smelting;
    // Headless dt is clamped hard: worldT advances at roughly a tenth of
    // wall clock, so three 1.1s cycles need ~35s of real time. Poll rather
    // than guess, and stop as soon as the gate question is answerable.
    for (let k = 0; k < 30; k++) {
      await new Promise(r => setTimeout(r, 2000));
      if (g.invCount('COPPER BAR') - inv0.cu >= 1 && g.invCount('IRON BAR') - inv0.fe >= 1 && !g.smelting) break;
    }
    out.bars = {
      cu: g.invCount('COPPER BAR') - inv0.cu,
      fe: g.invCount('IRON BAR') - inv0.fe,
      au: g.invCount('GOLD BAR') - inv0.au
    };
    out.oreLeft = { au: g.invCount('GOLD ORE') };
    out.smithLvl = g.lvl(g.skills.SMITHING || 0);
    if (out.bars.cu < 1) out.fail.push('copper did not smelt');
    if (out.bars.fe < 1) out.fail.push('iron did not smelt');
    if (out.smithLvl < 40 && out.bars.au > 0) out.fail.push('gold smelted below the level gate');
    if (out.smithLvl < 40 && out.oreLeft.au < 1) out.fail.push('gold ore vanished without a bar');
    if (g.smelting && out.smithLvl < 40) out.fail.push('smelting did not stop at the gold gate');

    // the new items exist as real, sellable things
    const priceOk = g.sellPrices && g.sellPrices()['COPPER BAR'] > 0 && g.sellPrices()['GOLD BAR'] > 0;
    if (!priceOk) out.fail.push('new bars not priced');

    // camera hijack for the ring
    const rr = g.renderer.render.bind(g.renderer);
    g.renderer.render = (scene, cam) => {
      if (g._camLock) { g._camLock.updateProjectionMatrix(); return rr(scene, g._camLock); }
      return rr(scene, cam);
    };
    return out;
  });

  const SHOTS = [
    ['front', [0, 1.5, 4.4]],
    ['three4', [3.4, 2.1, 3.4]],
    ['bellows-side', [-4.0, 1.6, 1.6]],
    ['night-far', [6.5, 2.6, 7.0]],
    ['player-eye', [0.6, 1.55, 3.1]]
  ];
  for (const [name, off] of SHOTS) {
    await page.evaluate(([o]) => {
      const g = window.__grim, T = g.T;
      const cam = new T.PerspectiveCamera(50, 1180 / 700, 0.1, 900);
      cam.position.set(33.5 + o[0], o[1], 24.5 + o[2]);
      cam.lookAt(33.5, 1.15, 24.5);
      g._camLock = cam;
    }, [off]);
    await page.waitForTimeout(900);
    await page.screenshot({ path: OUT + '/' + name + '.png' });
  }

  if (errs.length) res.fail.push(errs.length + ' page error(s): ' + errs.slice(0, 2).join(' | '));
  console.log(JSON.stringify({ ...res, out: OUT }, null, 2));
  await browser.close();
  process.exit(res.fail && res.fail.length ? 1 : 0);
})();
