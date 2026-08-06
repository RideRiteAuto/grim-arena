// Campfire regression test, run against the real bundle.
//
// The turntable proves the model looks right. This proves the game AGREES: that
// the fire actually got built, that it sits on the terrain rather than hovering
// or sinking, that it costs what it is supposed to cost, that its collider
// stops you walking into the flames, that the shared materials are shared
// rather than one set per fire, and that a second fire a hundred metres away
// dances on its own phase instead of in lockstep with the first.
//
// It also photographs it from the height a player's camera actually rides at,
// because a prop that only looks right from a turntable is a prop nobody has
// looked at properly.
//
//   node harness/serve.js & node harness/campfire.js
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/campfire-game';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1180, height: 700 } });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e && e.message)));
  page.on('console', m => { if (m.type() === 'error' && m.text().indexOf('404') < 0) errors.push(m.text()); });

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  // Guest login drops you back on the menu with a PLAY button, and headless has
  // no pointer lock to grant, so the last step is driven directly. Without it
  // the world streams in fine behind a login panel that is still on top of it,
  // and every screenshot is a photograph of the menu.
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(6000);
  for (let i = 0; i < 40; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim.started
      && window.__grim._chunks && window.__grim._chunks.size > 40)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(1500);
  }

  const checks = [];
  const fail = [];
  const ok = (name, cond, detail) => { checks.push({ name, pass: !!cond, detail }); if (!cond) fail.push(name + ': ' + detail); };

  const r = await page.evaluate(() => {
    const g = window.__grim;
    const out = { fires: (g.campfires || []).length };
    if (!out.fires) return out;
    const f = g.campfires[0];
    out.pos = [+f.x.toFixed(2), +f.z.toFixed(2)];
    out.radius = +f.radius.toFixed(3);

    // does it SIT on the ground, or hover / sink
    // GRIM_WORLD is module scoped inside the bundle and not on window, so the
    // ground has to be asked for through the game object.
    const terrain = g.groundY ? g.groundY(f.x, f.z) : null;
    out.terrainY = terrain === null ? null : +terrain.toFixed(3);
    out.groupY = +f.g.position.y.toFixed(3);
    out.sitError = terrain === null ? null : +Math.abs(f.g.position.y - terrain).toFixed(4);

    // cost
    let meshes = 0, tris = 0;
    const mats = new Set();
    f.g.traverse(o => {
      if (!o.isMesh) return;
      meshes++;
      mats.add(o.material.uuid);
      const p = o.geometry.attributes.position;
      tris += (o.geometry.index ? o.geometry.index.count : p.count) / 3;
    });
    out.meshes = meshes; out.tris = Math.round(tris); out.materials = mats.size;

    // does the flame actually reach a sensible height above the fuel
    const T = g.T;
    const solid = f.g.children[0];                 // fuel, stones and ash, merged
    const sbox = new T.Box3().setFromObject(solid);
    out.fuelWidth = +(sbox.max.x - sbox.min.x).toFixed(3);
    const flame = f.g.children.find(c => c.isGroup);
    const fbox = new T.Box3().setFromObject(flame || solid);
    out.height = +(fbox.max.y - f.g.position.y).toFixed(3);
    const box = new T.Box3().setFromObject(f.g);
    out.width = +(box.max.x - box.min.x).toFixed(3);   // includes the glow disc

    // shared materials: a SECOND fire must reuse them, not clone them
    const before = g.campfires.length;
    const f2 = g.addCampfire(f.x + 140, f.z + 90, { seed: 22, quiet: true });
    const mats2 = new Set();
    f2.g.traverse(o => { if (o.isMesh) mats2.add(o.material.uuid); });
    out.secondFireNewMaterials = [...mats2].filter(u => !mats.has(u)).length;
    out.firesAfter = g.campfires.length;
    out.addedOne = g.campfires.length === before + 1;

    // and it must not be geometrically identical: a different seed is a
    // different fire, otherwise every camp in the world is the same camp
    const a0 = f.g.children[0].geometry.attributes.position.array;
    const b0 = f2.g.children[0].geometry.attributes.position.array;
    let same = a0.length === b0.length;
    if (same) for (let i = 0; i < a0.length; i += 97) { if (a0[i] !== b0[i]) { same = false; break; } }
    out.seedsDiffer = !same;

    // same seed must reproduce exactly, or a streamed world flickers
    const f3 = g.addCampfire(f.x + 300, f.z, { seed: 7, quiet: true, light: false });
    const c0 = f3.g.children[0].geometry.attributes.position.array;
    let det = a0.length === c0.length;
    if (det) for (let i = 0; i < a0.length; i += 53) { if (Math.abs(a0[i] - c0[i]) > 1e-6) { det = false; break; } }
    out.deterministic = det;

    // The collider has to actually stop you. resolveColliders takes an ENTITY
    // and pushes its .pos out of anything it is inside, so the honest test is
    // to stand a probe in the middle of the flames and see where it ends up.
    out.hasCollider = (g.colliders || []).some(c => Math.abs(c.x - f.x) < 0.01 && Math.abs(c.z - f.z) < 0.01);
    const probe = { pos: new T.Vector3(f.x + 0.05, 0, f.z + 0.02) };
    g.resolveColliders(probe);
    out.pushedOut = +Math.hypot(probe.pos.x - f.x, probe.pos.z - f.z).toFixed(3);

    // the tick must move the shader clock, and the light with it
    const kit = g._cfKit;
    kit.tick(1.0);
    const l1 = f.light ? f.light.intensity : 0;
    const o1 = kit.mats.glow.opacity;
    kit.tick(1.37);
    out.uTimeMoved = kit.mats.flameOuter.userData.U.uTime.value === 1.37;
    out.lightFlickers = f.light ? Math.abs(f.light.intensity - l1) > 1e-4 : false;
    out.glowBreathes = Math.abs(kit.mats.glow.opacity - o1) > 1e-4;

    // clean up the probes so the screenshots are of one fire
    for (const probe of [f2, f3]) {
      g.scene.remove(probe.g);
      const i = g.campfires.indexOf(probe);
      if (i >= 0) g.campfires.splice(i, 1);
    }
    // Burn. Stand the player in the flames, run the step, and read the burn
    // timer back; then stand them a stride clear and confirm it does NOT fire.
    // A hazard that only ever triggers is the same bug as one that never does.
    const savedPos = g.me.pos.clone();
    const savedBurn = g.me.burnS || 0;
    g.me.burnS = 0;
    g.me.pos.set(f.x + 0.2, savedPos.y, f.z);
    g.stepCampfireBurn();
    out.burnInside = +(g.me.burnS || 0).toFixed(2);
    g.me.burnS = 0;
    g.me.pos.set(f.x + f.heat + 1.0, savedPos.y, f.z);
    g.stepCampfireBurn();
    out.burnOutside = +(g.me.burnS || 0).toFixed(2);
    out.heat = +f.heat.toFixed(2);
    g.me.burnS = savedBurn;
    g.me.pos.copy(savedPos);

    // How much room the fire actually has. This is the check that would have
    // caught the boulder: the nearest piece of scene geometry that is not part
    // of the fire and not the ground.
    const own = new Set();
    f.g.traverse(o => own.add(o));
    let nearest = 1e9;
    g.scene.traverse(o => {
      if (!o.isMesh || !o.geometry || !o.visible || own.has(o)) return;
      const b = new T.Box3().setFromObject(o);
      if (!isFinite(b.min.x)) return;
      if (b.max.x - b.min.x > 40 || b.max.z - b.min.z > 40) return;   // ground
      if (b.max.y - b.min.y < 0.18) return;                           // decals
      const dx = Math.max(b.min.x - f.x, 0, f.x - b.max.x);
      const dz = Math.max(b.min.z - f.z, 0, f.z - b.max.z);
      const d = Math.hypot(dx, dz);
      if (d < nearest) nearest = d;
    });
    out.clearance = +nearest.toFixed(2);

    out.glowR = +(kit.mats.glow.map ? 1 : 0);
    out.drawCalls = g.renderer.info.render.calls;
    return out;
  });

  ok('built', r.fires >= 1, r.fires + ' campfire(s) in the world');
  if (r.fires) {
    ok('sits on the terrain', r.sitError !== null && r.sitError < 0.05,
      'group y ' + r.groupY + ' against terrain ' + r.terrainY + ', error ' + r.sitError);
    ok('mesh budget', r.meshes <= 10, r.meshes + ' meshes');
    ok('triangle budget', r.tris <= 12000, r.tris + ' triangles');
    ok('flame height sane', r.height > 0.55 && r.height < 1.30, r.height + ' m tall');
    ok('footprint sane', r.fuelWidth > 1.2 && r.fuelWidth < 2.2,
      'fuel and stones ' + r.fuelWidth + ' m across, glow pool ' + r.width + ' m');
    ok('materials shared between fires', r.secondFireNewMaterials === 0,
      r.secondFireNewMaterials + ' new material(s) on the second fire');
    ok('addCampfire registers', r.addedOne, 'campfires list grew by one');
    ok('different seed, different fire', r.seedsDiffer, 'geometry differs');
    ok('same seed, same fire', r.deterministic, 'geometry reproduces');
    ok('collider registered', r.hasCollider, 'a collider stands at the fire');
    ok('you cannot stand in the fire', r.pushedOut >= r.radius - 0.01,
      'a probe dropped in the flames is pushed out to ' + r.pushedOut + ' m against a ' + r.radius + ' m ring');
    ok('shader clock advances', r.uTimeMoved, 'uTime follows tick');
    ok('light flickers', r.lightFlickers, 'point light intensity moves with the tick');
    ok('glow breathes', r.glowBreathes, 'ground glow opacity moves with the tick');
    ok('standing in it burns you', r.burnInside > 0,
      'burn timer ' + r.burnInside + 's inside a ' + r.heat + ' m heat radius');
    ok('standing clear does not', r.burnOutside === 0,
      'burn timer ' + r.burnOutside + 's a stride outside it');
    ok('it is not inside anything', r.clearance > 2.0,
      r.clearance + ' m to the nearest other mesh');
  }

  // photographs, at player camera height
  await page.evaluate(() => {
    const g = window.__grim;
    const rr = g.renderer.render.bind(g.renderer);
    g.renderer.render = (scene, cam) => {
      if (g._camLock) {
        g._camLock.updateProjectionMatrix();
        return rr(scene, g._camLock);
      }
      return rr(scene, cam);
    };
  });

  // Matching the login panel by its text was a false alarm: the node stays in
  // the document once the menu closes and still reports an offsetParent, so the
  // check failed on runs whose screenshots plainly showed the world. The game's
  // own state is the honest signal.
  const state = await page.evaluate(() => {
    const g = window.__grim;
    return { started: !!(g && g.started), world: !!(g && g.worldOn), mode: g && g.mode, gfx: g && g.gfx };
  });
  ok('reached gameplay', state.started && state.world && state.mode === 'ai',
    'started ' + state.started + ', worldOn ' + state.world + ', mode ' + state.mode + ', graphics ' + state.gfx);

  const SHOTS = [
    ['approach', [3.4, 1.62, 3.9], [0, 0.4, 0]],
    ['standing', [1.9, 1.55, 2.1], [0, 0.35, 0]],
    ['crouched', [1.5, 0.75, 1.7], [0, 0.35, 0]],
    ['wide', [8.5, 3.2, 9.5], [0, 0.6, 0]]
  ];
  const shots = [];
  for (const [name, off, look] of SHOTS) {
    await page.evaluate(([o, l]) => {
      const g = window.__grim, T = g.T, f = g.campfires[0];
      const cam = new T.PerspectiveCamera(55, 1180 / 700, 0.1, 900);
      cam.position.set(f.x + o[0], f.g.position.y + o[1], f.z + o[2]);
      cam.lookAt(f.x + l[0], f.g.position.y + l[1], f.z + l[2]);
      g._camLock = cam;
      // stand the player at the fire so the chunks around it stay streamed in
      g.me.pos.set(f.x + 6, g.me.pos.y, f.z + 6);
    }, [off, look]);
    await page.waitForTimeout(2200);
    const p = OUT + '/campfire_' + name + '.png';
    await page.screenshot({ path: p });
    shots.push(p);
  }

  if (errors.length) fail.push(errors.length + ' console/page error(s): ' + errors.slice(0, 3).join(' | '));

  console.log(JSON.stringify({ readings: r, checks, shots, errors, fail }, null, 2));
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})();
