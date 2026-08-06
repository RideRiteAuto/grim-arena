// Patch 38 shield carry iteration: arm tilted slightly OUTWARD with a gap
// between hand and hip, shield horizontal at the side, point aft (3 o'clock
// in the shieldside view), face vertical. Orientation and position are
// SOLVED from world-space targets in elbow space, then printed for baking.
const { chromium } = require('playwright');
const fs = require('fs');

const BASE = process.env.URL || 'http://127.0.0.1:8123/model-lab/';
const OUT = '/tmp/pose38';

// candidates: [armLz outward tilt, outboard offset for the shield centre]
const CANDS = [
  ['B2', 0.20, 0.12]
];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 960, height: 660 } });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e && e.message)));
  await page.goto(BASE + 'character.html', { waitUntil: 'load', timeout: 60000 });
  for (let i = 0; i < 40; i++) {
    if (await page.evaluate(() => !!window.__ready).catch(() => false)) break;
    await page.waitForTimeout(300);
  }

  const solved = {};
  for (const [tag, armLz, outb] of CANDS) {
    for (const view of ['shieldside', 'front', 'three4']) {
      await page.evaluate(([v]) => window.__shot(v, 3.0, 'day', { armor: true, pose: 'shield' }), [view]);
      await page.evaluate(([zz, ob]) => window.__tweak(`
        P.armL.rotation.set(-0.05, 0, ${zz});
        P.elbowL.rotation.set(-0.30, 0, 0);
        model.g.updateMatrixWorld(true);
        const qParent = new T.Quaternion();
        P.elbowL.getWorldQuaternion(qParent);
        const m = new T.Matrix4().makeBasis(
          new T.Vector3(-1, 0, 0),
          new T.Vector3(0, 0, 1),
          new T.Vector3(0, 1, 0));
        const qWorld = new T.Quaternion().setFromRotationMatrix(m);
        P.shield.quaternion.copy(qParent).invert().multiply(qWorld);
        const fist = new T.Vector3();
        P.handL.getWorldPosition(fist);
        const target = fist.add(new T.Vector3(${ob}, -0.08, -0.15));
        P.elbowL.worldToLocal(target);
        P.shield.position.copy(target);
        model.g.updateMatrixWorld(true);
        const q = new T.Quaternion();
        P.shield.getWorldQuaternion(q);
        const pt = new T.Vector3(0, -1, 0).applyQuaternion(q);
        window.__r = {
          rot: [P.shield.rotation.x, P.shield.rotation.y, P.shield.rotation.z].map(v => +v.toFixed(3)),
          pos: [P.shield.position.x, P.shield.position.y, P.shield.position.z].map(v => +v.toFixed(3)),
          pointAims: [pt.x, pt.y, pt.z].map(v => +v.toFixed(2))
        };
      `), [armLz, outb]);
      const res = await page.evaluate(() => window.__r);
      await page.screenshot({ path: `${OUT}/shield-${tag}-${view}.png` });
      solved[tag] = res;
    }
  }
  console.log(JSON.stringify({ solved, errs }, null, 2));
  await browser.close();
})();
