// Prove the zone trees in the REAL game: every shape built through the real
// makeZoneTree, streamed nodes carrying the new rig, the fell path running,
// and stream-in restores staying silent.
//
//   node harness/serve.js & node harness/zonetree-ingame.js
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/zonetree-ingame';

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

  // spawn sits in a dressed-node exclusion: march the player outward until
  // chunks with zone tree nodes stream in
  await page.evaluate(() => {
    window.__WOOD = { poplar: 1, zoak: 1, palm: 1, willow: 1, bogoak: 1, elder: 1, acacia: 1, icewood: 1, emberbark: 1, elderking: 1 };
  });
  const SPOTS = [[140, 140], [220, 60], [60, 220], [300, 300], [-180, 160], [160, -180], [420, 120], [-320, -120]];
  let streamed = 0;
  for (const [sx, sz] of SPOTS) {
    streamed = await page.evaluate(async ([x, z]) => {
      const g = window.__grim;
      g.me.pos.set(x, g.groundY ? g.groundY(x, z) : g.me.pos.y, z);
      g.me.g.position.copy(g.me.pos);
      for (let k = 0; k < 14; k++) {
        await new Promise(r => setTimeout(r, 1000));
        const n = (g.zoneNodes || []).filter(R => window.__WOOD[R.kind] && !R.dead).length;
        if (n >= 2) return n;
      }
      return (g.zoneNodes || []).filter(R => window.__WOOD[R.kind] && !R.dead).length;
    }, [sx, sz]);
    if (streamed >= 2) break;
  }

  const res = await page.evaluate(() => {
    const g = window.__grim;
    const out = { fail: [] };

    // ---- 1. every shape builds through the real makeZoneTree ---------------
    const LOOKS = g.ZONE_LOOK();
    const CASES = [
      ['poplar', 'HEARTLANDS'], ['broad', 'HEARTLANDS'], ['palm', 'SUNCOAST'],
      ['willow', 'MISTFEN'], ['snag', 'EMBER'], ['pine', 'FROSTWILD'], ['elder', 'GREENWOOD']
    ];
    out.shapes = {};
    for (const [shape, zone] of CASES) {
      const b = g.makeZoneTree(LOOKS[zone] || LOOKS.HEARTLANDS, 1, 7, shape);
      const rec = { meshes: 0, tris: 0 };
      b.g.traverse(o => {
        if (!o.isMesh) return;
        rec.meshes++;
        rec.tris += Math.round(o.geometry.attributes.position.count / 3);
      });
      rec.hinged = !!b.fell && Math.abs(b.fell.position.y) > 0.01;
      rec.stumpHidden = !!b.stump && !b.stump.visible;
      // merged: the falling half of a streamed tree is ONE mesh
      rec.fellMeshes = 0;
      b.fell.traverse(o => { if (o.isMesh) rec.fellMeshes++; });
      out.shapes[shape] = rec;
      if (!rec.hinged) out.fail.push(shape + ': fell not hinged at the break');
      if (!rec.stumpHidden) out.fail.push(shape + ': stump wrong while standing');
      if (rec.fellMeshes !== 1) out.fail.push(shape + ': fell is ' + rec.fellMeshes + ' meshes, wanted 1 (merged)');
      if (rec.tris < 300) out.fail.push(shape + ': suspiciously low tris, old prop? ' + rec.tris);
      if (shape === 'snag' && rec.tris > 1600) out.fail.push('snag has foliage-level tris: ' + rec.tris);
    }

    // ---- 2. streamed zone nodes carry the new rig ---------------------------
    const WOOD = { poplar: 1, zoak: 1, palm: 1, willow: 1, bogoak: 1, elder: 1, acacia: 1, icewood: 1, emberbark: 1, elderking: 1 };
    const zt = (g.zoneNodes || []).filter(R => WOOD[R.kind] && !R.dead);
    out.streamedTreeKinds = Array.from(new Set(zt.map(R => R.kind)));
    out.streamedCount = zt.length;
    if (zt.length) {
      const R = zt[0];
      if (!R.fell || Math.abs(R.fell.position.y) < 0.01) out.fail.push('streamed ' + R.kind + ' not hinged');
      if (!R.stump) out.fail.push('streamed ' + R.kind + ' has no stump');

      // ---- 3. the real fell path, with a position (audible, animated) ------
      if (g.audioInit) g.audioInit();
      const fxBefore = g.fx.filter(f => f.kind === 'fall').length;
      g.resourceDepleted(R, R.g.position.clone());
      const fxAfter = g.fx.filter(f => f.kind === 'fall').length;
      if (fxAfter !== fxBefore + 1) out.fail.push('zone fell did not queue the fall fx');
      if (!R.stump.visible) out.fail.push('zone fell did not reveal the stump');
      out.felledKind = R.kind;
      out.felledPos = [R.g.position.x, R.g.position.z];
      out.felledRef = g.zoneNodes.indexOf(R);

      // ---- 4. a stream-in restore is SILENT and snaps to the end state -----
      if (zt.length > 1) {
        const R2 = zt[1];
        const fx2Before = g.fx.filter(f => f.kind === 'fall').length;
        g.resourceDepleted(R2, null);
        const fx2After = g.fx.filter(f => f.kind === 'fall').length;
        if (fx2After !== fx2Before) out.fail.push('silent restore queued a fall fx');
        if (R2.fell.visible) out.fail.push('silent restore left the trunk standing');
        if (!R2.stump.visible) out.fail.push('silent restore did not reveal the stump');
        // put it back for the world's sake
        g.resourceRespawned(R2);
        if (!R2.fell.visible) out.fail.push('respawn after silent restore did not restore the trunk');
      } else out.fail.push('only one streamed tree, could not test the silent restore');
    } else out.fail.push('no zone trees streamed near spawn');

    // camera hijack for the shots
    const rr = g.renderer.render.bind(g.renderer);
    g.renderer.render = (scene, cam) => {
      if (g._camLock) { g._camLock.updateProjectionMatrix(); return rr(scene, g._camLock); }
      return rr(scene, cam);
    };
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

  // catch the felled zone tree mid-fall (headless runs ~10x slow)
  await page.waitForTimeout(4000);
  await look('zone-tree-falling', res.felledPos[0], res.felledPos[1], 8, 3.4, 2.4);

  // let the fall finish, then respawn through the real path
  const res2 = await page.evaluate(async ([ri]) => {
    const g = window.__grim;
    const out2 = { fail: [] };
    const R = g.zoneNodes[ri];
    let lastLife = null;
    for (let k = 0; k < 90; k++) {
      const f = g.fx.find(f2 => f2.kind === 'fall');
      if (!f) break;
      lastLife = f.life;
      await new Promise(r => setTimeout(r, 2000));
    }
    const still = g.fx.find(f2 => f2.kind === 'fall');
    if (still) out2.fail.push('zone fall never finished, life ' + still.life.toFixed(2) + ' (was ' + (lastLife === null ? '?' : lastLife.toFixed(2)) + ')');
    g.resourceRespawned(R);
    if (R.stump.visible) out2.fail.push('stump still out after zone respawn');
    if (!R.fell.visible) out2.fail.push('zone tree still hidden after respawn');
    if (Math.abs(R.fell.rotation.z) > 0.01) out2.fail.push('zone tree not stood back up');
    return out2;
  }, [res.felledRef]);

  await look('zone-tree-respawned', res.felledPos[0], res.felledPos[1], 8, 3.4, 2.4);

  const fail = (res.fail || []).concat(res2.fail || []);
  if (errs.length) fail.push(errs.length + ' page error(s): ' + errs.slice(0, 2).join(' | '));
  console.log(JSON.stringify({ ...res, ...res2, fail, out: OUT, errs }, null, 2));
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})();
