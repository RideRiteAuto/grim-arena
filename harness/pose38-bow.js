// Patch 38 bow poses. Three jobs:
//  idle - bow crosses the FRONT of the body at hip height, string side
//         toward the character (local -Z faces world -Z), full curve visible
//  run  - same carry but rolled 180 about the long axis: string faces UP
//  draw - the right hand actually gripping the string (solved elsewhere)
// The fist euler is SOLVED from the desired world basis of the bow, never
// hand-tuned: qHand(local) = qElbowWorld^-1 * qBowWorldDesired.
const { chromium } = require('playwright');
const fs = require('fs');

const BASE = process.env.URL || 'http://127.0.0.1:8123/model-lab/';
const OUT = '/tmp/pose38';

// idle candidates: [tag, tipX, tipY] - direction the TOP tip aims (world),
// slight upward diagonal reads livelier than dead level
const IDLE = [
  ['R', -0.96, 0.28],   // top tip toward the character's right, tilted up
  ['L', 0.96, 0.28]     // top tip toward the character's left, tilted up
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
  for (const [tag, tx, ty] of IDLE) {
    for (const view of ['front', 'three4', 'profile']) {
      await page.evaluate(([v]) => window.__shot(v, 3.0, 'day', { armor: true, pose: 'bow' }), [view]);
      await page.evaluate(([sx, sy]) => window.__tweak(`
        // arm: forward from the shoulder so the fist sits in front of the
        // hip, near the body midline
        P.armL.rotation.set(-0.50, 0, 0.06);
        P.elbowL.rotation.set(-0.30, 0, 0);
        model.g.updateMatrixWorld(true);
        const qParent = new T.Quaternion();
        P.elbowL.getWorldQuaternion(qParent);
        // desired bow world basis: +Y (up the riser) -> the tip direction,
        // +Z (target side) -> world +Z-ish so the STRING (-Z) faces the body.
        const yb = new T.Vector3(${sx}, ${sy}, 0).normalize();
        // z must be perpendicular to y: project world +Z onto the plane
        const zb = new T.Vector3(0, 0, 1).addScaledVector(yb, -yb.z).normalize();
        const xb = new T.Vector3().crossVectors(yb, zb);
        const m = new T.Matrix4().makeBasis(xb, yb, zb);
        const qWorld = new T.Quaternion().setFromRotationMatrix(m);
        // handL holds the bow at identity, so fist world = bow world
        const qh = qParent.clone().invert().multiply(qWorld);
        P.handL.quaternion.copy(qh);
        P.bowSet.setDraw(0);
        model.g.updateMatrixWorld(true);
        window.__r = {
          hand: [P.handL.rotation.x, P.handL.rotation.y, P.handL.rotation.z].map(v => +v.toFixed(3))
        };
      `), [tx, ty]);
      const res = await page.evaluate(() => window.__r);
      await page.screenshot({ path: `${OUT}/bowidle-${tag}-${view}.png` });
      solved[tag] = res;
    }
  }
  console.log(JSON.stringify({ solved, errs }, null, 2));
  await browser.close();
})();
