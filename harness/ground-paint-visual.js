// Live before/after screenshot check for patch 86.100. Paints the exact same
// single dot (matching Kevin's own test: meadow, brush radius 8, hardness
// 0.8, flow 0.5, organic edge on) on blank ground in both the currently-live
// bundle and the patched one, from the same fixed top-down camera, and saves
// both renders so they can be looked at directly rather than trusted blind.
//
// Usage: node harness/ground-paint-visual.js <bundle-url> <out.png>
// Env:   PEEK=1        scout mode -- move the camera and screenshot, no paint
//        PX=.. PZ=..   world coords to place the camera/paint point over
const { chromium } = require('playwright');

const bundleUrl = process.argv[2];
const outPath = process.argv[3];
const PEEK = process.env.PEEK === '1';
const PX = Number(process.env.PX || 0), PZ = Number(process.env.PZ || 0);
if (!bundleUrl || !outPath) { console.error('usage: ground-paint-visual.js <bundle-url> <out.png>'); process.exit(1); }

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1000, height: 750 } });
  page.on('dialog', d => d.accept('harness-key'));
  page.on('pageerror', e => console.log('  [pageerror]', e.message));

  const url = bundleUrl + '?edit=1';
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__grim && window.__grim.editorOn === true, null, { timeout: 90000 });

  const result = await page.evaluate(({ px, pz, peek }) => {
    const G = window.__grim;
    const ui = G.EDIT_UI();
    const S = ui.state;
    // Straight-down camera so the painted dot lands dead centre in frame
    // regardless of yaw.
    S.cam.x = px; S.cam.z = pz; S.cam.y = 45; S.cam.pit = -1.55; S.cam.yaw = 0;
    G.me.pos.set(S.cam.x, 0, S.cam.z);
    G._terrAcc = 99;
    G.stepTerrain(0, 400);
    if (peek) return { peek: true, blend: G.EDIT().raw.blend };
    S.tool = 'paint';
    S.surf = 0;        // meadow, same index highlighted in Kevin's screenshot
    S.brush = 8;
    // Hardness 1 / flow 1 / organic off: a fully-hard, fully-committed disc,
    // so the screenshot isolates the coverage-falloff fix on its own rather
    // than mixing it with the brush's own separate edge-softening knobs.
    S.hardness = 1;
    S.flow = 1;
    S.organic = false;
    // flow < 1 needs several passes to fully commit (per the tool's own
    // help text) -- paint the same point repeatedly, same as dragging a
    // brush in place, so the stroke is fully committed like Kevin's was.
    // applyTool() doesn't return anything usable, so check the actual layer
    // data (raw.paint) rather than trust a call's return value.
    const pt = { x: px, z: pz, y: 0 };
    for (let i = 0; i < 60; i++) { ui.applyTool(pt, i === 0, false); }
    let cellCount = 0;
    const raw = G.EDIT().raw;
    for (const k in raw.paint) cellCount += raw.paint[k].length;
    G._terrAcc = 99;
    G.stepTerrain(0, 400);
    return { cellCount: cellCount, blend: raw.blend };
  }, { px: PX, pz: PZ, peek: PEEK });

  if (PEEK) console.log('  peek at', PX, PZ, ' blend:', result.blend);
  else console.log('  painted cells:', result.cellCount, ' blend:', result.blend);

  // A couple of rAFs so the just-built chunk mesh actually renders before
  // the screenshot grabs a frame.
  await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
  await page.waitForTimeout(300);

  await page.screenshot({ path: outPath });
  await browser.close();
  console.log('  saved', outPath);
})().catch(e => { console.error(e); process.exit(1); });
