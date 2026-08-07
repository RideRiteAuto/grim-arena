// Prove the new trees and ore nodes in the REAL game: built by the world,
// felled by the real depletion path, restored by the real respawn path.
//
//   node harness/serve.js & node harness/nature-ingame.js
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/nature-ingame';

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

  const res = await page.evaluate(() => {
    const g = window.__grim;
    const out = { fail: [] };
    const trees = g.resources.filter(R => R.kind === 'tree' && !R.dead);
    const oaks = g.resources.filter(R => R.kind === 'oak' && !R.dead);
    const rocks = g.resources.filter(R => R.kind === 'rock' && !R.dead);
    out.counts = { trees: trees.length, oaks: oaks.length, rocks: rocks.length };
    if (!trees.length) out.fail.push('no starter trees');
    if (!oaks.length) out.fail.push('no oaks');
    if (!rocks.length) out.fail.push('no iron veins');
    if (out.fail.length) return out;

    const tr = trees[0], oak = oaks[0], rk = rocks[0];
    // new-build shape checks
    if (!tr.fell || Math.abs(tr.fell.position.y) < 0.01) out.fail.push('tree fell group not hinged at the break');
    if (!tr.stump) out.fail.push('tree has no stump group');
    if (tr.stump.visible) out.fail.push('stump crown visible while standing');
    if (!rk.studs || !rk.studs.length) out.fail.push('vein has no ore mesh');
    if (!rk.rubble) out.fail.push('vein has no rubble group');
    if (rk.rubble.visible) out.fail.push('rubble visible while full');
    let veinTris = 0;
    rk.g.traverse(o => { if (o.isMesh) veinTris += o.geometry.attributes.position.count / 3; });
    out.veinTris = Math.round(veinTris);
    if (veinTris < 400) out.fail.push('vein still the old low-tri prop');

    // ---- fell the tree through the real path ----
    if (g.audioInit) g.audioInit();
    g.resourceDepleted(tr, tr.g.position.clone());
    out.fellQueued = g.fx.some(f => f.kind === 'fall' && f.max > 5);
    if (!out.fellQueued) out.fail.push('fall fx not queued at the new length');
    if (!tr.stump.visible) out.fail.push('stump crown not revealed at the fell');
    out.treeRef = g.resources.indexOf(tr);

    // ---- deplete the vein through the real path ----
    g.resourceDepleted(rk, rk.g.position.clone());
    if (rk.studs.some(m => m.visible)) out.fail.push('ore still visible after depletion');
    if (!rk.rubble.visible) out.fail.push('rubble not shown after depletion');
    out.rockRef = g.resources.indexOf(rk);

    // camera hijack for the shots
    const rr = g.renderer.render.bind(g.renderer);
    g.renderer.render = (scene, cam) => {
      if (g._camLock) { g._camLock.updateProjectionMatrix(); return rr(scene, g._camLock); }
      return rr(scene, cam);
    };
    const p = oak.g.position;
    out.oakPos = [p.x, p.z];
    out.treePos = [tr.g.position.x, tr.g.position.z];
    out.rockPos = [rk.g.position.x, rk.g.position.z];
    return out;
  });

  if (res.fail && res.fail.length) {
    console.log(JSON.stringify({ ...res, errs }, null, 2));
    await browser.close();
    process.exit(1);
  }

  const look = async (name, cx, cz, dist, h, ly) => {
    await page.evaluate(([c]) => {
      const g = window.__grim, T = g.T;
      const cam = new T.PerspectiveCamera(50, 1180 / 700, 0.1, 900);
      const gy = g.groundY(c.cx, c.cz);
      cam.position.set(c.cx + c.dist * 0.8, gy + c.h, c.cz + c.dist);
      cam.lookAt(c.cx, gy + c.ly, c.cz);
      g._camLock = cam;
    }, [{ cx, cz, dist, h, ly }]);
    await page.waitForTimeout(700);
    await page.screenshot({ path: OUT + '/' + name + '.png' });
  };

  // mid-fall frame: the fall runs ~10x slower at headless fps, so wait for
  // the rotation to be visibly under way, then shoot
  await page.waitForTimeout(4000);
  await look('tree-falling', res.treePos[0], res.treePos[1], 7, 3.2, 2.2);
  await look('vein-empty', res.rockPos[0], res.rockPos[1], 3.2, 1.8, 0.5);
  await look('oak-standing', res.oakPos[0], res.oakPos[1], 9, 4.0, 3.4);

  // let the fall finish (headless-slow), then respawn both through the real path
  const res2 = await page.evaluate(async ([ti, ri]) => {
    const g = window.__grim;
    const out2 = { fail: [] };
    const tr = g.resources[ti], rk = g.resources[ri];
    for (let k = 0; k < 40; k++) {
      if (!g.fx.some(f => f.kind === 'fall')) break;
      await new Promise(r => setTimeout(r, 2000));
    }
    if (g.fx.some(f => f.kind === 'fall')) out2.fail.push('fall never finished');
    g.resourceRespawned(tr);
    g.resourceRespawned(rk);
    if (tr.stump.visible) out2.fail.push('stump crown still out after respawn');
    if (Math.abs(tr.fell.rotation.z) > 0.01) out2.fail.push('tree not stood back up');
    if (!tr.fell.visible) out2.fail.push('tree still hidden after respawn');
    if (rk.studs.some(m => !m.visible)) out2.fail.push('ore not restored');
    if (rk.rubble.visible) out2.fail.push('rubble still out after respawn');
    return out2;
  }, [res.treeRef, res.rockRef]);

  await look('tree-respawned', res.treePos[0], res.treePos[1], 7, 3.2, 2.2);

  const fail = (res.fail || []).concat(res2.fail || []);
  if (errs.length) fail.push(errs.length + ' page error(s): ' + errs.slice(0, 2).join(' | '));
  console.log(JSON.stringify({ ...res, ...res2, fail, out: OUT, errs }, null, 2));
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})();
