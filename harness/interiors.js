// Can you actually get in, and can you not get through?
//
// Everything here WALKS the collision resolver rather than looking at a
// picture. A doorway that renders correctly and pushes you back out is still a
// wall, and a wall you can stroll through still renders fine.
const { chromium } = require('playwright');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
  const errs = [];
  page.on('pageerror', e => errs.push(e.message));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(5000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  for (let i = 0; i < 40; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim.started && window.__grim._chunks && window.__grim._chunks.size > 40)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(1500);
  }

  const res = await page.evaluate(() => {
    const g = window.__grim, T = g.T;
    const fails = [];
    const out = {};

    // --- how tall is the player, really
    const box = new T.Box3().setFromObject(g.me.g);
    const playerH = +(box.max.y - box.min.y).toFixed(2);
    out.playerH = playerH;
    out.doorClear = 3.2;
    if (out.doorClear <= playerH) fails.push('door ' + out.doorClear + 'm is not taller than the player at ' + playerH + 'm');

    // --- walk a probe through the resolver, one small step at a time
    const walk = (x0, z0, x1, z1, steps) => {
      const e = { pos: new T.Vector3(x0, 0, z0) };
      const n = steps || Math.max(20, Math.round(Math.hypot(x1 - x0, z1 - z0) / 0.2));
      for (let i = 1; i <= n; i++) {
        const t = i / n;
        // move a step toward the goal from wherever the resolver left us, so a
        // wall actually stops the probe instead of teleporting it past
        const gx = x0 + (x1 - x0) * t, gz = z0 + (z1 - z0) * t;
        const dx = gx - e.pos.x, dz = gz - e.pos.z, dd = Math.hypot(dx, dz);
        const st = Math.min(dd, 0.22);
        if (dd > 1e-6) { e.pos.x += dx / dd * st; e.pos.z += dz / dd * st; }
        g.resolveColliders(e);
      }
      return [+e.pos.x.toFixed(2), +e.pos.z.toFixed(2)];
    };

    const STEPS = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20];
    const road = (x, z) => {
      let best = 0;
      for (const W of STEPS) {
        const p = g.clearOfRoad(x, z, W);
        if (Math.abs(p[0] - x) < 1e-6 && Math.abs(p[1] - z) < 1e-6) best = W; else break;
      }
      return best;
    };

    // --- the houses
    const huts = g._huts || [];
    out.hutCount = huts.length;
    if (huts.length !== 6) fails.push('expected 6 houses, found ' + huts.length);
    out.houses = [];
    for (let hi = 0; hi < huts.length; hi++) {
      const ht = huts[hi];
      // local -> world for this house
      const w2 = (lx, lz) => [ht.x + lx * ht.c + lz * ht.s, ht.z - lx * ht.s + lz * ht.c];
      const inRoom = (p) => {
        const dx = p[0] - ht.x, dz = p[1] - ht.z;
        const lx = dx * ht.c - dz * ht.s, lz = dx * ht.s + dz * ht.c;
        return Math.abs(lx) < ht.hw - 0.3 && Math.abs(lz) < ht.hd - 0.3;
      };
      const start = w2(0, ht.hd + 7);
      const goal = w2(0, -ht.hd * 0.4);
      const got = walk(start[0], start[1], goal[0], goal[1]);
      const entered = inRoom(got);
      // and now try the three walls that are not the doorway
      const thru = [];
      const probes = [
        ['back', w2(0, -(ht.hd + 7)), w2(0, 0)],
        ['left', w2(-(ht.hw + 7), 0), w2(0, 0)],
        ['right', w2(ht.hw + 7, 0), w2(0, 0)]
      ];
      for (const [nm, s2, e2] of probes) {
        const p = walk(s2[0], s2[1], e2[0], e2[1]);
        if (inRoom(p)) thru.push(nm);
      }
      const rd = road(ht.x, ht.z);
      out.houses.push({ at: [+ht.x.toFixed(1), +ht.z.toFixed(1)], entered: entered, walkedThrough: thru, road: rd });
      if (!entered) fails.push('house ' + hi + ' at ' + ht.x.toFixed(0) + ',' + ht.z.toFixed(0) + ' cannot be walked into through its own door');
      if (thru.length) fails.push('house ' + hi + ' can be walked through: ' + thru.join(', '));
      if (rd < 13) fails.push('house ' + hi + ' is ' + rd + 'm from the road, wanted 13m');
    }

    // --- no two houses within 24m, and none facing another head on
    let minGap = 1e9;
    for (let a = 0; a < huts.length; a++) for (let b = a + 1; b < huts.length; b++) {
      minGap = Math.min(minGap, Math.hypot(huts[a].x - huts[b].x, huts[a].z - huts[b].z));
    }
    out.minHouseGap = +minGap.toFixed(1);
    if (minGap < 24) fails.push('two houses are only ' + minGap.toFixed(1) + 'm apart, wanted 24m');

    // fronts: local +z is the door side. Two houses face each other if each
    // one's front direction points at the other.
    const facing = [];
    for (let a = 0; a < huts.length; a++) for (let b = 0; b < huts.length; b++) {
      if (a === b) continue;
      const A = huts[a], B = huts[b];
      const fx = A.s, fz = A.c;                       // A's front direction in world
      const dx = B.x - A.x, dz = B.z - A.z, dd = Math.hypot(dx, dz);
      if (dd > 40) continue;
      if ((fx * dx + fz * dz) / dd > 0.85) facing.push(a + '->' + b);
    }
    out.frontToFront = facing;
    for (const f of facing) {
      const [a, b] = f.split('->').map(Number);
      if (facing.includes(b + '->' + a)) fails.push('houses ' + a + ' and ' + b + ' face each other');
    }

    // --- the market precinct: walled, with four ways in
    const TX = -84, TZ = 96;
    const gateIn = walk(TX, TZ + 26, TX, TZ);
    const wallIn = walk(TX + 26, TZ + 8, TX, TZ + 8);
    out.marketGate = gateIn;
    out.marketWall = wallIn;
    if (Math.hypot(gateIn[0] - TX, gateIn[1] - TZ) > 3) fails.push('the market gate does not let you in');
    if (Math.abs(wallIn[0] - TX) < 12) fails.push('you can walk through the market wall');
    // and the stalls are not in anybody's garden
    let nearestHouse = 1e9;
    for (const ht of huts) nearestHouse = Math.min(nearestHouse, Math.hypot(ht.x - TX, ht.z - TZ));
    out.nearestHouseToSquare = +nearestHouse.toFixed(1);
    if (nearestHouse < 30) fails.push('a house is only ' + nearestHouse.toFixed(1) + 'm from the market');

    // --- the keep
    const KX = -84, KZ = 246, KH = 20;
    const inKeep = (p) => Math.abs(p[0] - KX) < KH - 2 && Math.abs(p[1] - KZ) < KH - 2;
    const thruGate = walk(KX, KZ + KH + 16, KX, KZ);
    out.keepGate = thruGate;
    if (!inKeep(thruGate)) fails.push('the keep gateway does not let you in, probe stopped at ' + thruGate);
    const keepWalls = [];
    for (const [nm, sx, sz] of [['north', 0, -1], ['east', 1, 0], ['west', -1, 0]]) {
      const p = walk(KX + sx * (KH + 16), KZ + sz * (KH + 16), KX, KZ);
      if (inKeep(p)) keepWalls.push(nm);
    }
    // the south wall either side of the gateway
    for (const s of [-1, 1]) {
      const p = walk(KX + s * 13, KZ + KH + 16, KX + s * 13, KZ);
      if (inKeep(p)) keepWalls.push('south' + (s > 0 ? '+' : '-'));
    }
    out.keepWalkThrough = keepWalls;
    if (keepWalls.length) fails.push('the keep walls can be walked through: ' + keepWalls.join(', '));

    // --- the King is in his keep, the wraiths are not in the masonry
    const king = g.npcs.filter(n => n.name === 'THE HOLLOW KING')[0];
    out.king = king ? [+king.home.x.toFixed(1), +king.home.z.toFixed(1)] : null;
    if (!king) fails.push('no Hollow King');
    else if (!inKeep([king.home.x, king.home.z])) fails.push('the King is not inside his own keep');
    const wr = g.npcs.filter(n => n.wraith).map(n => +Math.hypot(n.home.x - KX, n.home.z - KZ).toFixed(1));
    out.wraithRadii = wr;
    for (const r of wr) if (r < 26) fails.push('a frost wraith spawns at ' + r + 'm, inside the keep towers');

    // --- the interior hook: roof off, fire on, near wall out of the way
    const ht0 = huts[0];
    g.me.pos.set(ht0.x, 0, ht0.z);
    g.cam.position.set(ht0.x + ht0.s * (ht0.hd + 8), 3, ht0.z + ht0.c * (ht0.hd + 8));
    g.stepWorld(0.016);
    out.insideRoofHidden = ht0.roof.visible === false;
    out.insideFireOn = ht0.light.visible === true;
    out.insideNearWallHidden = ht0.sides.front.visible === false;
    out.insideFarWallShown = ht0.sides.back.visible === true;
    if (!out.insideRoofHidden) fails.push('the roof stays on when you are inside');
    if (!out.insideFireOn) fails.push('the hearth light does not come on inside');
    if (!out.insideNearWallHidden) fails.push('the wall between the camera and the room is not hidden');
    if (!out.insideFarWallShown) fails.push('the far wall is hidden too, so you can see out of the world');
    g.me.pos.set(ht0.x, 0, ht0.z + 40);
    g.stepWorld(0.016);
    out.outsideRestored = ht0.roof.visible === true && ht0.sides.front.visible === true && ht0.light.visible === false;
    if (!out.outsideRestored) fails.push('walking back out does not put the house back together');

    // --- the keep grounds are the keep's, not the world's
    // Kevin's "cluttered junk" was mostly the procedural dressing growing
    // through the castle floor, so assert it is actually gone rather than
    // trusting that the filter is wired up.
    let nodesInKeep = 0;
    for (const n of (g.zoneNodes || [])) {
      if (!n.g) continue;
      const p2 = n.g.position;
      if (Math.abs(p2.x - KX) < 22 && Math.abs(p2.z - KZ) < 22) nodesInKeep++;
    }
    out.nodesInKeep = nodesInKeep;
    if (nodesInKeep) fails.push(nodesInKeep + ' gather nodes are still growing inside the keep');
    out.keepGroundInside = g.keepGround(KX, KZ) === true;
    out.keepGroundOutside = g.keepGround(KX + 60, KZ) === false;
    if (!out.keepGroundInside || !out.keepGroundOutside) fails.push('keepGround does not mark the right ground');

    // --- fell fire: a real material, animating
    out.fellFlame = !!g._fellMat;
    if (!g._fellMat) fails.push('the braziers are not burning fell fire');
    else {
      const t0 = g._fellMat.userData.uTime.value;
      g.tickTorches(t0 * 1000 + 900);
      out.fellFlameAnimates = g._fellMat.userData.uTime.value > t0;
      if (!out.fellFlameAnimates) fails.push('the fell flame is not animating');
    }

    // --- props are solid. Kevin: everything in the buildings needs collision.
    // Walk into the hearth from the middle of the room and see if it stops.
    {
      const ht1 = huts[0];
      const w3 = (lx, lz) => [ht1.x + lx * ht1.c + lz * ht1.s, ht1.z - lx * ht1.s + lz * ht1.c];
      const hearth = w3(ht1.hw - 0.95, 0);
      const mid = w3(0, 0);
      const p3 = walk(mid[0], mid[1], hearth[0], hearth[1]);
      const reach = Math.hypot(p3[0] - hearth[0], p3[1] - hearth[1]);
      out.hearthBlocksAt = +reach.toFixed(2);
      if (reach < 0.5) fails.push('you can stand inside the hearth');
    }
    // and a fruit stand outside the keep gate
    {
      const sx4 = KX - 10.5, sz4 = KZ + KH + 9;
      const p4 = walk(sx4, sz4 - 8, sx4, sz4);
      out.standBlocksAt = +Math.abs(p4[1] - sz4).toFixed(2);
      if (Math.abs(p4[1] - sz4) < 0.5) fails.push('you can walk through the fruit stands');
    }

    // --- budget
    let meshes = 0, tris = 0;
    g.scene.traverse(o => { if (o.isMesh) { meshes++; const p = o.geometry && o.geometry.attributes && o.geometry.attributes.position; if (p) tris += p.count / 3; } });
    out.meshes = meshes;
    out.tris = Math.round(tris);
    out.colliders = (g.colliders || []).length;
    out.calls = g.renderer.info.render.calls;

    return { out: out, fails: fails };
  });

  console.log(JSON.stringify(res, null, 1));
  if (errs.length) console.log('PAGE ERRORS', errs);
  await browser.close();
  process.exit(res.fails.length || errs.length ? 1 : 0);
})();
