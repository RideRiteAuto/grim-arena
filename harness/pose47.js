// Patch 47 solver: Kevin's second-round corrections.
//  SHIELD: arm outward tilt halved (0.20 -> 0.10), shield WORLD orientation
//          unchanged - re-solved in elbow space at the new arm pose.
//  BOW IDLE: the arm crosses the front so the hand sits at the body's
//          centreline, plus a slight hunch (upper pitch) per the reference.
//          Fist re-solved for the same bow world basis at the new arm pose.
//  DRAW: real archer form (researched): torso near-sideways to the target,
//          drawing forearm IN LINE with the arrow, elbow pointing straight
//          away from the target at shoulder height. Both arms and the bow
//          fist are solved from world targets at upper yaw 0.75; the right
//          arm two-bone IK targets the nock with a pole that holds the
//          elbow out and back along the arrow line.
const { chromium } = require('playwright');
const fs = require('fs');

const BASE = process.env.URL || 'http://127.0.0.1:8123/model-lab/';
const OUT = '/tmp/pose47';

const SHIELD_SRC = `
  P.sword.visible = true; P.shield.visible = true; P.bow.visible = false;
  P.armL.rotation.set(-0.05, 0, 0.10);
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
  const target = fist.add(new T.Vector3(0.12, -0.08, -0.15));
  P.elbowL.worldToLocal(target);
  P.shield.position.copy(target);
  model.g.updateMatrixWorld(true);
  window.__r = {
    rot: [P.shield.rotation.x, P.shield.rotation.y, P.shield.rotation.z].map(v => +v.toFixed(3)),
    pos: [P.shield.position.x, P.shield.position.y, P.shield.position.z].map(v => +v.toFixed(3))
  };
`;

const IDLE_SRC = (armLz, pitch) => `
  P.bow.visible = true;
  P.upper.rotation.x = ${pitch};
  P.head.rotation.x = ${-pitch * 0.5};
  P.armL.rotation.set(-0.50, 0, ${armLz});
  P.elbowL.rotation.set(-0.30, 0, 0);
  model.g.updateMatrixWorld(true);
  const qParent = new T.Quaternion();
  P.elbowL.getWorldQuaternion(qParent);
  const yb = new T.Vector3(-0.96, 0.28, 0).normalize();
  const zb = new T.Vector3(0, 0, 1).addScaledVector(yb, -yb.z).normalize();
  const xb = new T.Vector3().crossVectors(yb, zb);
  const m = new T.Matrix4().makeBasis(xb, yb, zb);
  const qWorld = new T.Quaternion().setFromRotationMatrix(m);
  P.handL.quaternion.copy(qParent).invert().multiply(qWorld);
  P.bowSet.setDraw(0);
  model.g.updateMatrixWorld(true);
  const fw = new T.Vector3(); P.handL.getWorldPosition(fw);
  window.__r = {
    hand: [P.handL.rotation.x, P.handL.rotation.y, P.handL.rotation.z].map(v => +v.toFixed(3)),
    fistWorldX: +fw.x.toFixed(3)
  };
`;

// yaw: how sideways the torso stands. Aim is world +Z regardless.
const DRAW_SRC = (drawT, yaw) => `
  P.bow.visible = true;
  P.upper.rotation.set(0.04, ${yaw}, 0);
  P.head.rotation.y = ${-yaw * 0.8};
  model.g.updateMatrixWorld(true);
  const aim = new T.Vector3(0, 0, 1);
  const mY = new T.Vector3(0, -1, 0);
  // ---- bow arm: straight at the target from the yawed shoulder ----
  const qUpW = new T.Quaternion();
  P.armL.parent.getWorldQuaternion(qUpW);
  const armDir = new T.Vector3(0.10, -0.06, 1).normalize();  // fractionally down and in
  const qAL = new T.Quaternion().setFromUnitVectors(mY, armDir);
  P.armL.quaternion.copy(qUpW).invert().multiply(qAL);
  P.elbowL.rotation.set(-0.06, 0, 0);
  model.g.updateMatrixWorld(true);
  // ---- bow fist: vertical bow, belly at the target, slight cant ----
  const qEW = new T.Quaternion();
  P.elbowL.getWorldQuaternion(qEW);
  const zb = aim.clone();
  const yb = new T.Vector3(0, 1, 0).addScaledVector(zb, -zb.y).normalize();
  const xb = new T.Vector3().crossVectors(yb, zb);
  const mB = new T.Matrix4().makeBasis(xb, yb, zb);
  const qBow = new T.Quaternion().setFromRotationMatrix(mB)
    .multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(0, 0, 1), -0.08));
  P.handL.quaternion.copy(qEW).invert().multiply(qBow);
  P.bowSet.setDraw(${drawT});
  P.bowSet.arrow.visible = true;
  model.g.updateMatrixWorld(true);
  // ---- string arm: two-bone IK to the nock, elbow OUT along the arrow ----
  const np = new T.Vector3(0, -0.015, -0.148 - ${drawT} * 0.46);
  P.bow.localToWorld(np);
  const sh = new T.Vector3();
  P.armR.getWorldPosition(sh);
  const L1 = 0.2952, L2 = 0.3055;
  const to = new T.Vector3().subVectors(np, sh);
  let d = Math.min(to.length(), (L1 + L2) * 0.999);
  const dir = to.clone().normalize();
  const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(0, L1 * L1 - a * a));
  // pole: straight away from the target and slightly up/out, so the
  // forearm finishes IN LINE with the arrow - textbook full draw
  const poleRaw = new T.Vector3(-0.35, 0.30, -1);
  const pole = poleRaw.addScaledVector(dir, -poleRaw.dot(dir)).normalize();
  const elbow = sh.clone().addScaledVector(dir, a).addScaledVector(pole, h);
  const qSE = new T.Quaternion().setFromUnitVectors(mY, new T.Vector3().subVectors(elbow, sh).normalize());
  const qUpW2 = new T.Quaternion();
  P.armR.parent.getWorldQuaternion(qUpW2);
  P.armR.quaternion.copy(qUpW2).invert().multiply(qSE);
  const handDir = new T.Vector3(0, -0.305, 0.018).normalize();
  const qEC = new T.Quaternion().setFromUnitVectors(handDir, new T.Vector3().subVectors(np, elbow).normalize());
  P.elbowR.quaternion.copy(qSE).invert().multiply(qEC);
  model.g.updateMatrixWorld(true);
  const fist = new T.Vector3(); P.hand.getWorldPosition(fist);
  const elW = new T.Vector3(); P.elbowR.getWorldPosition(elW);
  window.__r = {
    armL: [P.armL.rotation.x, P.armL.rotation.y, P.armL.rotation.z].map(v => +v.toFixed(3)),
    handL: [P.handL.rotation.x, P.handL.rotation.y, P.handL.rotation.z].map(v => +v.toFixed(3)),
    armR: [P.armR.rotation.x, P.armR.rotation.y, P.armR.rotation.z].map(v => +v.toFixed(3)),
    elbowR: [P.elbowR.rotation.x, P.elbowR.rotation.y, P.elbowR.rotation.z].map(v => +v.toFixed(3)),
    missBy: +fist.distanceTo(np).toFixed(3),
    elbowWorld: [elW.x, elW.y, elW.z].map(v => +v.toFixed(2))
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

  const shot = async (view, pose, src, name) => {
    await page.evaluate(([v, p]) => window.__shot(v, 3.0, 'day', { armor: true, pose: p }), [view, pose]);
    await page.evaluate(([s]) => window.__tweak(s), [src]);
    const r = await page.evaluate(() => window.__r);
    await page.screenshot({ path: `${OUT}/${name}.png` });
    return r;
  };

  solved.shield = await shot('front', 'shield', SHIELD_SRC, 'shield-front');
  await shot('shieldside', 'shield', SHIELD_SRC, 'shield-side');

  for (const [tag, z, pitch] of [['A', -0.10, 0.14], ['B', -0.22, 0.18]]) {
    solved['idle' + tag] = await shot('front', 'bow', IDLE_SRC(z, pitch), `idle-${tag}-front`);
    await shot('three4', 'bow', IDLE_SRC(z, pitch), `idle-${tag}-three4`);
  }

  for (const [tag, yaw] of [['y60', 0.60], ['y80', 0.80]]) {
    solved['full' + tag] = await shot('profile', 'bowdraw', DRAW_SRC(0.9, yaw), `draw-${tag}-profile`);
    await shot('front', 'bowdraw', DRAW_SRC(0.9, yaw), `draw-${tag}-front`);
    await shot('three4', 'bowdraw', DRAW_SRC(0.9, yaw), `draw-${tag}-three4`);
  }

  console.log(JSON.stringify({ solved, errs }, null, 2));
  await browser.close();
})();
