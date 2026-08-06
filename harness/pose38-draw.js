// Patch 38, parts 2 and 3.
//  RUN: fist solved so the bow rides at the side with the STRING UP
//       (local -Z -> world +Y), long axis along the direction of travel.
//       Solved at the arm's mid-swing so the error spreads evenly.
//  DRAW: the right hand put ON the string with two-bone IK, at two draw
//       times - the reach (t=0.15) and the anchor (t=0.9). The game lerps
//       between the two baked poses while setDraw moves the string, so the
//       fist tracks the nock through the whole pull.
const { chromium } = require('playwright');
const fs = require('fs');

const BASE = process.env.URL || 'http://127.0.0.1:8123/model-lab/';
const OUT = '/tmp/pose38';

const IK_SRC = (drawT) => `
  // bow arm: extended at the target (unchanged from 37)
  P.armL.rotation.set(-1.50, 0, -0.04);
  P.elbowL.rotation.set(-0.08, 0, 0);
  P.handL.rotation.set(-(P.armL.rotation.x + P.elbowL.rotation.x), 0, -0.10);
  P.bow.visible = true;
  P.bowSet.setDraw(${drawT});
  P.bowSet.arrow.visible = true;
  P.upper.rotation.y = 0.45;
  model.g.updateMatrixWorld(true);
  // world position of the nocking point at this draw
  const np = new T.Vector3(0, -0.015, -0.148 - ${drawT} * 0.46);
  P.bow.localToWorld(np);
  // two-bone IK for the right arm
  const sh = new T.Vector3();
  P.armR.getWorldPosition(sh);
  const L1 = 0.2952, L2 = 0.3055;
  const to = new T.Vector3().subVectors(np, sh);
  let d = to.length();
  d = Math.min(d, (L1 + L2) * 0.999);
  const dir = to.clone().normalize();
  // elbow circle: distance a along dir, height h off it, toward a pole that
  // puts the elbow OUT to the right and slightly up - a high draw elbow
  const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(0, L1 * L1 - a * a));
  const poleRaw = new T.Vector3(-0.45, 0.22, -0.9);
  const pole = poleRaw.addScaledVector(dir, -poleRaw.dot(dir)).normalize();
  const elbow = sh.clone().addScaledVector(dir, a).addScaledVector(pole, h);
  const mY = new T.Vector3(0, -1, 0);
  const qSE = new T.Quaternion().setFromUnitVectors(mY, new T.Vector3().subVectors(elbow, sh).normalize());
  // armR is parented to upper, which is yawed 0.35: express in parent space
  const qUp = new T.Quaternion();
  P.armR.parent.getWorldQuaternion(qUp);
  P.armR.quaternion.copy(qUp).invert().multiply(qSE);
  // aim the HAND, not the bare -Y: the fist sits at (0,-0.305,0.018) in
  // elbow space, so map that actual direction onto elbow->nock
  const handDir = new T.Vector3(0, -0.305, 0.018).normalize();
  const qEC = new T.Quaternion().setFromUnitVectors(handDir, new T.Vector3().subVectors(np, elbow).normalize());
  P.elbowR.quaternion.copy(qSE).invert().multiply(qEC);
  model.g.updateMatrixWorld(true);
  const fist = new T.Vector3();
  P.hand.getWorldPosition(fist);
  window.__r = {
    armR: [P.armR.rotation.x, P.armR.rotation.y, P.armR.rotation.z].map(v => +v.toFixed(3)),
    elbowR: [P.elbowR.rotation.x, P.elbowR.rotation.y, P.elbowR.rotation.z].map(v => +v.toFixed(3)),
    missBy: +fist.distanceTo(np).toFixed(3)
  };
`;

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

  // ---- RUN fist ----
  for (const view of ['profile', 'three4']) {
    await page.evaluate(([v]) => window.__shot(v, 0.18, 'day', { armor: true, pose: 'bowrun' }), [view]);
    await page.evaluate(() => window.__tweak(`
      // solve at mid-swing: armL neutral x, run elbow
      const saveX = P.armL.rotation.x;
      P.armL.rotation.set(0, 0, -0.08);
      P.elbowL.rotation.set(-0.35, 0, 0);
      model.g.updateMatrixWorld(true);
      const qParent = new T.Quaternion();
      P.elbowL.getWorldQuaternion(qParent);
      // string up: local Y (riser) -> +Z travel, local Z (target) -> -Y
      const m = new T.Matrix4().makeBasis(
        new T.Vector3(1, 0, 0),
        new T.Vector3(0, 0, 1),
        new T.Vector3(0, -1, 0));
      const qWorld = new T.Quaternion().setFromRotationMatrix(m);
      const qh = qParent.clone().invert().multiply(qWorld);
      P.handL.quaternion.copy(qh);
      window.__r = { hand: [P.handL.rotation.x, P.handL.rotation.y, P.handL.rotation.z].map(v => +v.toFixed(3)) };
      // photograph back at the swung arm position so the shot matches the game
      P.armL.rotation.x = saveX;
      model.g.updateMatrixWorld(true);
    `));
    solved.run = await page.evaluate(() => window.__r);
    await page.screenshot({ path: `${OUT}/bowrun-${view}.png` });
  }

  // ---- DRAW IK at both ends ----
  for (const [tag, t] of [['reach', 0.15], ['full', 0.9]]) {
    for (const view of ['three4', 'front', 'profile']) {
      await page.evaluate(([v]) => window.__shot(v, 3.0, 'day', { armor: true, pose: 'bowdraw' }), [view]);
      await page.evaluate(([src]) => window.__tweak(src), [IK_SRC(t)]);
      solved[tag] = await page.evaluate(() => window.__r);
      await page.screenshot({ path: `${OUT}/draw-${tag}-${view}.png` });
    }
  }
  console.log(JSON.stringify({ solved, errs }, null, 2));
  await browser.close();
})();
