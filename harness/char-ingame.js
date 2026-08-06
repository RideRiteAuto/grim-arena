// Photograph the PLAYER in the real game, and assert the v5 idle pose landed.
//
// The lab proves the model reads; this proves the game agrees: the bundle's
// own animate() drives the rig, the real lighting rig lights it, and the
// screenshots show what Kevin sees. Uses the renderer hijack from
// harness/campfire.js - the game keeps rendering, we just swap the camera.
//
//   node harness/serve.js & node harness/char-ingame.js
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/char-ingame';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1180, height: 700 } });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e && e.message)));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  // Click through the menu the same way harness/boot.js does: guest login,
  // then the PLAY button it drops you back onto.
  await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll('button, a, div, span'));
    const hits = all.filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    const el = hits[hits.length - 1];
    if (el) el.click();
  });
  await page.waitForTimeout(6000);
  // Headless has no pointer lock, so the PLAY step is driven directly - the
  // same route harness/boot.js takes.
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);
  await page.waitForFunction(() => {
    const g = window.__grim;
    return g && g.started && g.me && g.me.g;
  }, { timeout: 120000 });
  await page.waitForTimeout(2500);

  // camera hijack
  await page.evaluate(() => {
    const g = window.__grim;
    const rr = g.renderer.render.bind(g.renderer);
    g.renderer.render = (scene, cam) => {
      if (g._camLock) { g._camLock.updateProjectionMatrix(); return rr(scene, g._camLock); }
      return rr(scene, cam);
    };
  });

  // Wait for the idle pose to CONVERGE rather than guessing a duration. The
  // spawn fall leaves the arms many radians from rest, and at headless frame
  // rates the ap() blend takes ~10 s of wall clock to shed that. At 60 fps
  // the same decay is over in under a second, so this is purely a test-rig
  // patience problem - measured by sampling the decay series, not assumed.
  let pose = null;
  for (let k = 0; k < 20; k++) {
    pose = await page.evaluate(() => {
      const g = window.__grim, P = g.me.parts;
      return {
        state: g.me.state, moveAmt: +(g.me.moveAmt || 0).toFixed(2),
        armLx: +P.armL.rotation.x.toFixed(3), armLz: +P.armL.rotation.z.toFixed(3),
        armRz: +P.armR.rotation.z.toFixed(3),
        elbowL: P.elbowL ? +P.elbowL.rotation.x.toFixed(3) : null,
        kneeR: P.kneeR ? +P.kneeR.rotation.x.toFixed(3) : null,
        shX: +P.shield.rotation.x.toFixed(3), shY: +P.shield.rotation.y.toFixed(3),
        weapon: g.me.weapon
      };
    });
    if (pose.state === 'idle' && Math.abs(pose.armLz - (-0.16)) < 0.03 && Math.abs(pose.armLx - (-0.10)) < 0.03
        && (pose.elbowL === null || Math.abs(pose.elbowL - (-1.22)) < 0.06)) break;
    await page.waitForTimeout(2000);
  }

  // Compass ring around the character at eye height, fixed yaw. Which frame
  // is the "front" is read off the contact sheet, not derived.
  const SHOTS = [
    ['ring-north', [0, 1.45, -3.0]],
    ['ring-east', [3.0, 1.45, 0]],
    ['ring-south', [0, 1.45, 3.0]],
    ['ring-west', [-3.0, 1.45, 0]],
    ['ring-low', [-2.0, 0.7, -2.2]]
  ];
  for (const [name, off] of SHOTS) {
    await page.evaluate(([o]) => {
      const g = window.__grim, T = g.T, me = g.me;
      const cam = new T.PerspectiveCamera(50, 1180 / 700, 0.1, 900);
      const p = me.g.position;
      cam.position.set(p.x + o[0], p.y + o[1], p.z + o[2]);
      cam.lookAt(p.x, p.y + 1.05, p.z);
      g._camLock = cam;
    }, [off]);
    await page.waitForTimeout(900);
    await page.screenshot({ path: OUT + '/' + name + '.png' });
  }

  const fail = [];
  if (pose.weapon === 0) {
    if (pose.elbowL === null) fail.push('rig has no elbows - v6 module missing');
    if (pose.kneeR === null) fail.push('rig has no knees - v6 module missing');
    if (pose.elbowL !== null && Math.abs(pose.elbowL - (-1.22)) > 0.08) fail.push('shield elbow not bent to carry: ' + pose.elbowL);
    if (Math.abs(pose.armLz - (-0.16)) > 0.05) fail.push('armL.z not at carry: ' + pose.armLz);
    if (Math.abs(pose.shX - Math.PI) > 0.1) fail.push('shield not in forearm carry: x=' + pose.shX);
  }
  if (errs.length) fail.push(errs.length + ' page error(s): ' + errs.slice(0, 2).join(' | '));
  console.log(JSON.stringify({ pose, fail, out: OUT }, null, 2));
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})();
