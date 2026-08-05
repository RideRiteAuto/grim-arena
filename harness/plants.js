// Forage plant shape test.
//
// Every foraging node used to be the same four-blob lump with a different hex
// tint. This builds all nine kinds through the real makeZonePlant, asserts they
// are genuinely different geometry (not the same mesh recoloured), checks the
// determinism the dressing engine depends on, checks the vertex budget, checks
// the picked state, and lays them out in a row for a look.
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/plants';
const KINDS = ['berry', 'mushroom', 'reeds', 'holly', 'fenroot', 'dyeflower', 'spice', 'firelily', 'lotus'];
const BUDGET = 900;   // vertices per plant; the old lump was 240

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 620, height: 620 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  for (let i = 0; i < 60; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim._chunks && window.__grim._chunks.size > 20)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(1500);
  }

  const report = await page.evaluate((args) => {
    const [KINDS, BUDGET] = args;
    const g = window.__grim;
    g.dressInit();
    const look = g.ZONE_LOOK().HEARTLANDS;
    const vcount = (grp) => { let n = 0; grp.traverse(o => { if (o.isMesh) n += o.geometry.getAttribute('position').count; }); return n; };
    const posHash = (grp) => {
      // cheap fingerprint of the actual vertex data
      let h = 0;
      grp.traverse(o => {
        if (!o.isMesh) return;
        const a = o.geometry.getAttribute('position').array;
        for (let i = 0; i < a.length; i++) { h = (h * 31 + Math.round(a[i] * 4096)) | 0; }
      });
      return h;
    };
    const out = {};
    for (const k of KINDS.concat(['__unknown__'])) {
      const b1 = g.makeZonePlant(look, 1, 12345, g.NODE_TINT(k), k);
      const b2 = g.makeZonePlant(look, 1, 12345, g.NODE_TINT(k), k);
      const b3 = g.makeZonePlant(look, 1, 999, g.NODE_TINT(k), k);
      out[k] = {
        verts: vcount(b1.fell),
        stubVerts: vcount(b1.stump),
        hash: posHash(b1.fell),
        deterministic: posHash(b1.fell) === posHash(b2.fell),
        seedVaries: posHash(b1.fell) !== posHash(b3.fell),
        hasFell: !!b1.fell, hasStump: !!b1.stump,
        stumpHiddenByDefault: b1.stump.visible === false,
        // every plant must be exactly one mesh: the draw-call contract
        meshes: (() => { let n = 0; b1.fell.traverse(o => { if (o.isMesh) n++; }); return n; })(),
        // and it must carry vertex colours, or _nodeMat renders it white
        hasColor: (() => { let ok = true; b1.fell.traverse(o => { if (o.isMesh && !o.geometry.getAttribute('color')) ok = false; }); return ok; })()
      };
    }
    return out;
  }, [KINDS, BUDGET]);

  // ---- shoot each kind on its own, then tile a contact sheet -------------
  await page.evaluate(() => {
    const g = window.__grim, T = g.T;
    if (g.raf) { cancelAnimationFrame(g.raf); g.raf = null; }
    g.dressInit();
    g.__stage = new T.Group(); g.scene.add(g.__stage);
    if (!g.__pFill) {
      g.__pFill = new T.DirectionalLight(0xffffff, 2.6); g.scene.add(g.__pFill);
      g.__pFill2 = new T.HemisphereLight(0xe8eef8, 0x6a6250, 1.6); g.scene.add(g.__pFill2);
    }
  });

  for (const kind of KINDS) {
    for (const picked of [false, true]) {
      await page.evaluate(([kind, picked]) => {
        const g = window.__grim, T = g.T;
        while (g.__stage.children.length) g.__stage.remove(g.__stage.children[0]);
        const look = g.ZONE_LOOK().HEARTLANDS;
        const base = new T.Vector3(g.me.pos.x, g.me.pos.y, g.me.pos.z - 5);
        const b = g.makeZonePlant(look, 1.6, 4242, g.NODE_TINT(kind), kind);
        if (picked) { b.fell.visible = false; b.stump.visible = true; }
        b.g.position.copy(base);
        g.__stage.add(b.g);
        g.__pFill.position.set(base.x + 3, base.y + 8, base.z + 6);
        g.__pFill.target.position.copy(base); g.__pFill.target.updateMatrixWorld();
        const c = g.cam;
        c.position.set(base.x + 2.1, base.y + 2.05, base.z + 3.8);
        c.lookAt(base.x, base.y + 0.95, base.z);
        c.updateProjectionMatrix();
        g.renderer.render(g.scene, c);
      }, [kind, picked]);
      await page.locator('canvas').first().screenshot({ path: `${OUT}/${kind}${picked ? '-picked' : ''}.png` });
    }
  }

  const fails = [];
  const hashes = {};
  for (const k of KINDS) {
    const r = report[k];
    if (!r) { fails.push(k + ': did not build'); continue; }
    if (!r.deterministic) fails.push(k + ': not deterministic for a fixed seed');
    if (!r.seedVaries) fails.push(k + ': ignores the seed, every instance identical');
    if (r.meshes !== 1) fails.push(k + ': ' + r.meshes + ' meshes, must be exactly 1');
    if (!r.hasColor) fails.push(k + ': no vertex colours, _nodeMat will render it white');
    if (r.verts > BUDGET) fails.push(k + ': ' + r.verts + ' verts over the ' + BUDGET + ' budget');
    if (r.verts < 60) fails.push(k + ': suspiciously empty, ' + r.verts + ' verts');
    if (!r.stumpHiddenByDefault) fails.push(k + ': stump visible before it is picked');
    if (r.stubVerts < 12) fails.push(k + ': picked state is empty');
    if (hashes[r.hash]) fails.push(k + ' and ' + hashes[r.hash] + ' are the SAME geometry');
    hashes[r.hash] = k;
  }
  const verts = KINDS.map(k => report[k].verts);
  console.log(JSON.stringify({
    report, fails, errors: errors.slice(0, 6),
    vertsMin: Math.min(...verts), vertsMax: Math.max(...verts),
    vertsAvg: Math.round(verts.reduce((a, b) => a + b, 0) / verts.length),
    distinctShapes: Object.keys(hashes).length
  }, null, 2));
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
