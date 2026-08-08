// Proves the world editor's edit layer does what it claims, and, just as
// importantly, that it does NOTHING at all when it is empty.
//
// The layer ships to every player: it rewrites ground surfaces, moves terrain,
// suppresses procedural props and adds walkable geometry. So the first four
// checks here are not about features, they are about the promise that a player
// with no authored content near them runs the game that shipped yesterday.
//
// The layer is served by harness/serve.js from /tmp/grim-edits.json, which is
// the same code path the live relay serves, so this exercises fetch, validate,
// index and apply rather than a stubbed object.
//
// Written to FAIL without the editor: with GRIM_EDIT absent every check below
// throws, and with the layer ignored the paint, height, road, removal, object
// and deck checks all report the generated world.
const { chromium } = require('playwright');
const fs = require('fs');

const URL = 'http://127.0.0.1:8123/index.html';
const EDITS = '/tmp/grim-edits.json';
const CELL = 4;

const fails = [];
const notes = [];
function ok(cond, label, detail) {
  if (cond) { notes.push('  ok     ' + label + (detail ? '  (' + detail + ')' : '')); }
  else { fails.push(label + (detail ? '  (' + detail + ')' : '')); notes.push('  FAIL   ' + label + (detail ? '  (' + detail + ')' : '')); }
}

async function open(browser) {
  const page = await browser.newPage();
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  page.on('pageerror', e => errs.push('pageerror: ' + String(e)));
  await page.goto(URL, { waitUntil: 'load' });
  // Same route into gameplay boot.js uses: click through the guest button,
  // then call play() directly because the pointer lock never lands headless.
  // Wait for boot(), not just for the instance: play() before boot throws on
  // an undefined renderer, the catch below swallows it, and the test then
  // waits ninety seconds for a `started` that can never arrive. __grim.T is
  // set by boot and is the honest signal that the engine exists.
  await page.waitForFunction(() => window.__grim && window.__grim.T && window.__grim._chunks,
    null, { timeout: 90000 });
  await page.evaluate(() => {
    const want = 'PLAY AS GUEST';
    for (const el of document.querySelectorAll('button, div, span, a')) {
      if ((el.textContent || '').trim().toUpperCase() === want) { el.click(); return true; }
    }
    return false;
  }).catch(() => {});
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForFunction(() => window.__grim.started && window.__grim._chunks && window.__grim._chunks.size > 50,
    null, { timeout: 90000 });
  return { page, errs };
}

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });

  // ---- phase 1: EMPTY layer. Nothing may change. -------------------------
  try { fs.unlinkSync(EDITS); } catch (e) {}
  let a = await open(browser);
  const base = await a.page.evaluate(() => {
    const g = window.__grim;
    const p = { x: g.me.pos.x, z: g.me.pos.z };
    const su = [0, 0, 0, 0, 0, 0, 0];
    const samples = [];
    for (let i = 0; i < 24; i++) {
      const x = p.x + (i % 6) * 9 - 27, z = p.z + Math.floor(i / 6) * 9 - 18;
      const h = g.WORLD().height(x, z);
      const zi = g.WORLD().zone(x, z);
      g.groundSurface(zi, h, x, z, su);
      samples.push({ x: +x.toFixed(2), z: +z.toFixed(2), h: +h.toFixed(4), su: su.slice() });
    }
    return {
      pos: p, samples,
      editPresent: typeof g.EDIT() === 'object',
      on: g.EDIT().on, empty: g.EDIT().empty, ready: g.EDIT().ready,
      heightDelta0: g.EDIT().heightDelta(p.x, p.z),
      deck0: g.EDIT().deckY(p.x, p.z),
      clears0: g.EDIT().clears(p.x, p.z),
      gone0: g.EDIT().gone('anything'),
      nodeCount: g.zoneNodes.length,
      meshes: g.renderer.info.memory.geometries
    };
  });
  ok(base.editPresent, 'the edit layer module is in the bundle');
  ok(base.ready && !base.on && base.empty, 'an empty layer applies nothing', 'on=' + base.on);
  ok(base.heightDelta0 === 0, 'an empty layer moves no terrain');
  ok(base.deck0 === null, 'an empty layer adds no decks');
  ok(base.clears0 === false && base.gone0 === false, 'an empty layer clears nothing and deletes nothing');
  // Ground texture plan, Phase 3: with no authored capLo/capHi the altitude
  // cap must compute the exact pre-patch (h - 52) / 26, not a close cousin.
  const capDefaultOk = base.samples.every(s => {
    const want = Math.max(0, Math.min(1, (s.h - 52) / 26));
    return Math.abs(s.su[6] - want) < 1e-6;
  });
  ok(capDefaultOk, 'altitude cap defaults to the exact pre-patch 52..78m band with no override');
  await a.page.close();

  // ---- build a layer around wherever the player actually spawns ----------
  const P = base.pos;
  const cellOf = v => Math.floor(v / CELL);
  const chunkOfCell = (cx, cz) => Math.floor(cx * CELL / 64) + ',' + Math.floor(cz * CELL / 64);

  // A 5x5 cell patch of desert sand (14) centred on the player, and a hill.
  const paint = {}, height = {};
  const c0 = cellOf(P.x), z0 = cellOf(P.z);
  for (let dz = -2; dz <= 2; dz++) for (let dx = -2; dx <= 2; dx++) {
    const cx = c0 + dx, cz = z0 + dz, k = chunkOfCell(cx, cz);
    (paint[k] = paint[k] || []).push([cx, cz, 14]);
  }
  // A hill 40m east: a single 3-cell blob so the bilinear read is testable.
  const hx = cellOf(P.x + 40), hz = cellOf(P.z);
  for (let dz = -1; dz <= 1; dz++) for (let dx = -1; dx <= 1; dx++) {
    const cx = hx + dx, cz = hz + dz, k = chunkOfCell(cx, cz);
    (height[k] = height[k] || []).push([cx, cz, 6]);
  }
  const layer = {
    v: 1, gen: 7, paint, height,
    roads: [{ w: 8, s: 15, p: [[P.x - 60, P.z + 30], [P.x, P.z + 34], [P.x + 60, P.z + 30]] }],
    objects: [
      { i: 'plat1', k: 'platform', x: P.x + 14, z: P.z - 14, y: 0, r: 0, s: 1 },
      { i: 'crate1', k: 'crate', x: P.x + 6, z: P.z - 6, y: 0, r: 0.5, s: 1 },
      { i: 'bad1', k: 'no_such_kind_at_all', x: P.x + 3, z: P.z + 3, y: 0, r: 0, s: 1 }
    ],
    removed: [], spawns: [], prefabs: {}, districts: [], bookmarks: [],
    // Ground texture plan, Phase 3: a normal (non-editor) boot must honour
    // these from first render, not only inside the editor.
    slopeLo: 0.05, slopeHi: 0.5, capLo: 40, capHi: 55
  };
  fs.writeFileSync(EDITS, JSON.stringify(layer));

  // ---- phase 2: the layer applies ---------------------------------------
  let b = await open(browser);
  // The layer may land after boot, in which case the game refreshes the
  // chunks. Wait for that to settle rather than racing it.
  await b.page.waitForFunction(() => window.__grim.EDIT().on === true, null, { timeout: 30000 });
  await b.page.waitForTimeout(1500);

  const res = await b.page.evaluate(o => {
    const g = window.__grim, P = o.P;
    const su = [0, 0, 0, 0, 0, 0, 0];
    const surfAt = (x, z) => {
      const h = g.WORLD().height(x, z);
      g.groundSurface(g.WORLD().zone(x, z), h, x, z, su);
      return su.slice();
    };
    const centre = surfAt(P.x, P.z);
    const faraway = surfAt(P.x + 600, P.z + 600);

    // terrain: at the hill centre it must be up by close to the authored 6m,
    // and it must arrive smoothly rather than as a 4m step.
    const hBase = g.WORLD().baseHeight(P.x + 40, P.z);
    const hNow = g.WORLD().height(P.x + 40, P.z);
    // Continuity, not steepness. A 4m staircase and a steep smooth ramp both
    // show a big step when sampled coarsely; they differ in what happens when
    // you sample FINER. A staircase keeps the same jump however small the
    // step, because the jump lives at a single point. A continuous surface's
    // largest jump shrinks in proportion to the sample spacing.
    const delta = d => g.WORLD().height(P.x + 40 + d, P.z) - g.WORLD().baseHeight(P.x + 40 + d, P.z);
    const scan = (step) => {
      let m = 0, prev = delta(-16);
      for (let d = -16 + step; d <= 16; d += step) {
        const v = delta(d);
        m = Math.max(m, Math.abs(v - prev));
        prev = v;
      }
      return m;
    };
    const jumpCoarse = scan(2), jumpFine = scan(0.25);
    const ramp = [];
    for (let d = -14; d <= 14; d += 2) ramp.push(+delta(d).toFixed(3));
    const maxJump = jumpCoarse;

    // road
    const onRoad = g.EDIT().roadAt(P.x, P.z + 34);
    const offRoad = g.EDIT().roadAt(P.x, P.z + 90);
    const roadSurf = surfAt(P.x, P.z + 34);

    // objects in the scene
    let plat = null, crate = null, badFound = false;
    g.scene.traverse(n => {
      if (!n.userData || !n.userData.editId) return;
      if (n.userData.editId === 'plat1') plat = n;
      if (n.userData.editId === 'crate1') crate = n;
      if (n.userData.editId === 'bad1') badFound = true;
    });

    // deck: standing on the platform must read the deck, not the ground
    const deck = g.EDIT().deckY(P.x + 14, P.z - 14);
    const ground = g.WORLD().height(P.x + 14, P.z - 14);
    const surfaceY = g.surfaceY(P.x + 14, P.z - 14);
    const deckOff = g.EDIT().deckY(P.x + 40, P.z - 40);

    // footprint clears clutter
    const clearsUnder = g.keepGround(P.x + 14.5, P.z - 14.5);
    const clearsAway = g.keepGround(P.x + 300, P.z + 300);

    // Ground texture plan, Phase 3: authored capLo/capHi retexture the
    // altitude band. h is a plain argument to groundSurface, so this is
    // fully deterministic regardless of the real terrain height at the
    // sample point; a spot far from any authored ground avoids the paint
    // override at the end of groundSurface touching out[6].
    const su6 = (h, x, z, zi) => { const o = [0, 0, 0, 0, 0, 0, 0]; g.groundSurface(zi, h, x, z, o); return o[6]; };
    const capMid = su6(47, 2000, 2000, 3);
    const uSlope = (g._chunkMat && g._chunkMat.userData.uSlope)
      ? [g._chunkMat.userData.uSlope.value.x, g._chunkMat.userData.uSlope.value.y] : null;

    return {
      centre, faraway,
      hBase: +hBase.toFixed(3), hNow: +hNow.toFixed(3), ramp,
      maxJump: +maxJump.toFixed(3), jumpFine: +jumpFine.toFixed(4),
      jumpRatio: +(jumpCoarse / Math.max(1e-9, jumpFine)).toFixed(2),
      onRoad, offRoad, roadSurf,
      platAt: plat ? [+plat.position.x.toFixed(2), +plat.position.z.toFixed(2)] : null,
      crateAt: crate ? [+crate.position.x.toFixed(2), +crate.position.z.toFixed(2)] : null,
      badFound,
      deck: deck === null ? null : +deck.toFixed(2),
      ground: +ground.toFixed(2),
      surfaceY: +surfaceY.toFixed(2),
      deckOff,
      clearsUnder, clearsAway,
      capMid, uSlope,
      stats: g.EDIT().stats()
    };
  }, { P });

  // Paint: the authored surface must be present in the tile pair at the
  // centre, at full coverage, and absent 600m away.
  const paintedHere = (res.centre[0] === 14 || res.centre[1] === 14);
  const paintedThere = (res.faraway[0] === 14 || res.faraway[1] === 14);
  ok(paintedHere, 'painted ground carries the authored surface', 'tiles ' + res.centre.slice(0, 2));
  ok(!paintedThere, 'ground 600m away is untouched', 'tiles ' + res.faraway.slice(0, 2));

  // Terrain
  ok(Math.abs((res.hNow - res.hBase) - 6) < 0.35,
    'sculpted terrain rises by the authored amount', 'delta ' + (res.hNow - res.hBase).toFixed(2) + 'm of 6m');
  // 8x finer sampling must give a roughly 8x smaller largest jump. A hard
  // cell-edge staircase would hold its jump and score a ratio near 1.
  ok(res.jumpRatio > 5,
    'sculpted terrain is continuous, not a staircase of 4m cells',
    'largest jump 2m/0.25m = ' + res.maxJump + 'm / ' + res.jumpFine + 'm, ratio ' + res.jumpRatio);
  ok(res.ramp[0] < 0.4 && res.ramp[res.ramp.length - 1] < 0.4,
    'the sculpt falls back to the generated height at its edge');

  // Roads
  ok(res.onRoad && res.onRoad[0] === 15, 'the road answers on its centreline');
  ok(res.offRoad === null, 'the road does not answer 56m off it');
  ok(res.roadSurf[0] === 15 || res.roadSurf[1] === 15, 'the road paints the ground it runs over');

  // Objects
  ok(res.platAt && Math.abs(res.platAt[0] - (P.x + 14)) < 0.01, 'a placed platform is in the scene at its coordinates');
  ok(res.crateAt !== null, 'a placed crate is in the scene');
  ok(res.badFound === false, 'an unknown object kind is skipped rather than thrown');

  // Decks
  ok(res.deck !== null && res.deck > res.ground + 3, 'the platform has a walkable deck above the ground',
    'deck ' + res.deck + 'm vs ground ' + res.ground + 'm');
  ok(Math.abs(res.surfaceY - res.deck) < 0.01, 'the surfaces query returns the deck, so it is walkable',
    'surfaceY ' + res.surfaceY);
  ok(res.deckOff === null, 'the deck does not extend past the platform');

  // Clutter
  ok(res.clearsUnder === true, 'an object footprint suppresses procedural clutter');
  ok(res.clearsAway === false, 'clutter is untouched away from authored ground');

  ok(res.stats.objects === 3 && res.stats.roads === 1, 'the layer reports what it holds',
    JSON.stringify(res.stats.objects) + ' objects, ' + res.stats.roads + ' road');

  // Ground texture plan, Phase 3
  ok(Math.abs(res.capMid - (47 - 40) / (55 - 40)) < 1e-6,
    'authored capLo/capHi retexture the altitude cap band', 'cap ' + res.capMid);
  ok(res.uSlope && Math.abs(res.uSlope[0] - 0.05) < 1e-6 && Math.abs(res.uSlope[1] - 0.5) < 1e-6,
    'authored slopeLo/slopeHi reach the ground shader uniform for a normal player, not only the editor',
    JSON.stringify(res.uSlope));

  const pushed = await b.page.evaluate(() => {
    const g = window.__grim, T = g.T;
    // onBeforeCompile fires lazily on a material's first real draw call. The
    // road ribbon may not have drawn one yet if no road segment happens to be
    // in view, which would leave _roadMat.userData.uSlope unset through no
    // fault of setSlopeRule. Attach it to a throwaway mesh and force a
    // compile, the same thing a real frame eventually does on its own, so
    // this checks the push rather than racing whether a road ever rendered.
    const probe = new T.Mesh(new T.PlaneGeometry(1, 1), g._roadMat);
    g.scene.add(probe);
    try { g.renderer.compile(g.scene, g.cam); } catch (e) {}
    g.scene.remove(probe);
    g.setSlopeRule(0.2, 0.33);
    const chunk = g._chunkMat.userData.uSlope ? [g._chunkMat.userData.uSlope.value.x, g._chunkMat.userData.uSlope.value.y] : null;
    const road = g._roadMat.userData.uSlope ? [g._roadMat.userData.uSlope.value.x, g._roadMat.userData.uSlope.value.y] : null;
    return { chunk, road };
  });
  ok(pushed.chunk && Math.abs(pushed.chunk[0] - 0.2) < 1e-6 && Math.abs(pushed.chunk[1] - 0.33) < 1e-6,
    'setSlopeRule updates the ground material uniform live', JSON.stringify(pushed.chunk));
  ok(pushed.road && Math.abs(pushed.road[0] - 0.2) < 1e-6 && Math.abs(pushed.road[1] - 0.33) < 1e-6,
    'setSlopeRule updates the road material uniform too', JSON.stringify(pushed.road));

  const newErrs = b.errs.filter(e => !/404|Failed to load resource/.test(e));
  ok(newErrs.length === 0, 'no new console errors with a layer applied', newErrs.slice(0, 2).join(' | '));
  await b.page.close();

  // ---- phase 3: a corrupt layer must degrade, not explode ---------------
  fs.writeFileSync(EDITS, JSON.stringify({
    v: 1,
    paint: { 'x': 'not an array', '0,0': [[1, 2, 99], [3, 4, 'nope'], [5, 6, 2]] },
    height: { '0,0': [[1, 2, 1e9], [3, 4, NaN]] },
    roads: [{ w: 'wide', p: [[1, 2]] }, null, { p: [[0, 0], [10, 10]] }],
    // one fully valid object, and three that must not survive: no position,
    // an unparseable position, and something that is not an object at all
    objects: [{ k: 'crate', x: 12, z: 34 }, { k: 'crate' }, { k: 'crate', x: 'NaN', z: 3 }, 7],
    removed: [1, 'ok-id'], prefabs: { p: 'no' }, districts: [{ poly: [[0, 0]] }],
    // Ground texture plan, Phase 3: an inverted range on either pair must
    // degrade to "use the engine default", not a technically-clamped but
    // backwards band that would flip which side is rock or cap.
    slopeLo: 2, slopeHi: -1, capLo: 999, capHi: -999
  }));
  let c = await open(browser);
  await c.page.waitForTimeout(1200);
  const bad = await c.page.evaluate(() => ({
    started: window.__grim.started,
    stats: window.__grim.EDIT().stats(),
    // 99 is not a real surface and must have been dropped; 1e9 metres must
    // have been clamped to the authored maximum.
    hasBadSurf: JSON.stringify(window.__grim.EDIT().raw.paint).indexOf('99') >= 0,
    maxDelta: Math.max.apply(null, [0].concat(Object.values(window.__grim.EDIT().raw.height).flat().map(e => Math.abs(e[2])))),
    objKinds: window.__grim.EDIT().raw.objects.map(o => o.k),
    chunks: window.__grim._chunks.size,
    slopeNulled: window.__grim.EDIT().raw.slopeLo === null && window.__grim.EDIT().raw.slopeHi === null,
    capNulled: window.__grim.EDIT().raw.capLo === null && window.__grim.EDIT().raw.capHi === null
  }));
  ok(bad.started === true, 'the game still boots on a corrupt layer');
  ok(bad.chunks > 0, 'the world still builds on a corrupt layer', bad.chunks + ' chunks');
  ok(!bad.hasBadSurf, 'an out of range surface index is dropped');
  ok(bad.maxDelta <= 12.001, 'an absurd terrain delta is clamped', 'max ' + bad.maxDelta + 'm');
  ok(bad.objKinds.length === 1 && bad.objKinds[0] === 'crate', 'malformed objects are dropped, valid ones kept',
    JSON.stringify(bad.objKinds));
  ok(bad.slopeNulled, 'an inverted slope range degrades to the engine default rather than a backwards band');
  ok(bad.capNulled, 'an inverted cap range degrades to the engine default rather than a backwards band');
  await c.page.close();

  // ---- phase 4: the editor itself --------------------------------------
  try { fs.unlinkSync(EDITS); } catch (e) {}
  const page = await browser.newPage();
  const eErrs = [];
  page.on('console', m => { if (m.type() === 'error') eErrs.push(m.text()); });
  page.on('pageerror', e => eErrs.push('pageerror: ' + String(e)));
  // The editor asks for a key it cannot verify here, so answer the prompt.
  page.on('dialog', d => d.accept('harness-key'));
  await page.goto(URL + '?edit=1', { waitUntil: 'load' });
  await page.waitForFunction(() => window.__grim && window.__grim.editorOn === true, null, { timeout: 90000 });
  await page.waitForTimeout(2500);

  const ed = await page.evaluate(() => {
    const g = window.__grim, S = g.EDIT_UI().state;
    const before = { x: S.cam.x, z: S.cam.z };
    // Drive the free camera by hand for a second of game time.
    S.keys['w'] = true;
    for (let i = 0; i < 60; i++) g.EDIT_UI().tick(1 / 60);
    S.keys['w'] = false;
    const after = { x: S.cam.x, z: S.cam.z };
    return {
      panel: !!document.querySelector('div') && !!S,
      moved: Math.hypot(after.x - before.x, after.z - before.z),
      camFollowsPlayer: Math.abs(g.me.pos.x - S.cam.x) < 0.01,
      bodyHidden: g.me.g ? g.me.g.visible === false : true,
      aboveGround: S.cam.y > g.WORLD().height(S.cam.x, S.cam.z),
      tools: typeof g.EDIT_UI().tick === 'function',
      catalogSize: Object.keys(g.EDIT_CAT()).length,
      chunks: g._chunks.size,
      // the tick must render without the player's frame ever running
      editorOn: g.editorOn === true,
      menuHidden: !g.overlayRef || !g.overlayRef.current ||
        g.overlayRef.current.style.display === 'none' ||
        getComputedStyle(g.overlayRef.current).display === 'none',
      nearPlane: g.cam.near,
      seaDropped: !g.sea || g.sea.position.y < -0.3,
      lockNeutered: (() => { try { g.requestLock(); return !document.pointerLockElement; } catch (e) { return false; } })(),
      npcsParked: (() => {
        const withHome = (g.npcs || []).filter(n => n && n.g && n.home);
        if (!withHome.length) return 'no-npcs';
        let okc = 0;
        for (const n of withHome) {
          if (Math.abs(n.g.position.x - n.home.x) < 0.01 && Math.abs(n.g.position.z - n.home.z) < 0.01) okc++;
        }
        return okc + '/' + withHome.length;
      })()
    };
  });
  ok(ed.editorOn, '?edit=1 enters editor mode');
  ok(ed.menuHidden, 'the title menu is dismissed, not sitting over the editor');
  ok(ed.nearPlane === 1.0, 'the aerial camera gets a 1m near plane against sea z-fighting', 'near ' + ed.nearPlane);
  ok(ed.seaDropped, 'the sea sits lower in editor sessions');
  ok(ed.lockNeutered, 'pointer lock is neutered so right-drag look always answers');
  ok(/^(\d+)\/\1$/.test(ed.npcsParked), 'every NPC stands at its authored home, not the origin', ed.npcsParked);
  ok(ed.moved > 3, 'the free camera moves under WASD', ed.moved.toFixed(1) + 'm in a second');

  // movement axes: the fix for W climbing while looking down
  const mv = await page.evaluate(() => {
    const g = window.__grim, U = g.EDIT_UI(), S = U.state;
    const run = (key, yaw, pit, frames) => {
      S.cam.yaw = yaw; S.cam.pit = pit;
      S.vel.x = S.vel.y = S.vel.z = 0;
      const b = { x: S.cam.x, y: S.cam.y, z: S.cam.z };
      S.keys[key] = true;
      for (let i = 0; i < frames; i++) U.tick(1 / 60);
      S.keys[key] = false;
      return { dx: S.cam.x - b.x, dy: S.cam.y - b.y, dz: S.cam.z - b.z };
    };
    S.cam.y = 200;                     // well clear of the ground clamp
    const level = run('w', 0, 0, 40);
    S.cam.y = 200;
    const down = run('w', 0, -0.7, 40);
    S.cam.y = 200;
    const up = run('e', 0, 0, 30);
    S.cam.y = 200;
    const sink = run('q', 0, 0, 30);
    S.cam.y = 200;
    const strafe = run('d', 0, 0, 30);
    return { level, down, up, sink, strafe };
  });
  ok(mv.level.dz < -2 && Math.abs(mv.level.dy) < 0.5,
    'W flies level when looking level', 'dy ' + mv.level.dy.toFixed(2));
  ok(mv.down.dy < -1 && mv.down.dz < -1,
    'W descends when looking down', 'dy ' + mv.down.dy.toFixed(1));
  ok(mv.up.dy > 1 && Math.abs(mv.up.dz) < 0.5, 'E rises straight up');
  ok(mv.sink.dy < -1, 'Q sinks straight down');
  ok(mv.strafe.dx > 1 && Math.abs(mv.strafe.dz) < 0.5, 'D strafes right at yaw zero');

  // fly mode toggling and the editing chrome
  const fly = await page.evaluate(() => {
    const g = window.__grim, U = g.EDIT_UI(), S = U.state;
    const before = !!S.fly;
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    const after = !!S.fly;
    const crossOn = S.cross && S.cross.style.display === 'block';
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    const back = !!S.fly;
    const btns = [...document.querySelectorAll('button')].map(b => b.textContent);
    return { before, after, crossOn, back,
      hasUndo: btns.includes('Undo'), hasRedo: btns.includes('Redo'), hasSave: btns.includes('Save') };
  });
  ok(!fly.before && fly.after && !fly.back, 'TAB toggles fly mode', fly.before + '>' + fly.after + '>' + fly.back);
  ok(fly.crossOn, 'the crosshair shows while flying');
  ok(fly.hasUndo && fly.hasRedo && fly.hasSave, 'Undo, Redo and Save have visible buttons');

  // the game cannot hear editor keys: Q must not open the spell wheel
  const keyLeak = await page.evaluate(() => {
    const g = window.__grim;
    const before = !!g.wheelOpen;
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'q', bubbles: true, cancelable: true }));
    window.dispatchEvent(new KeyboardEvent('keyup', { key: 'q', bubbles: true, cancelable: true }));
    return { before, after: !!g.wheelOpen };
  });
  ok(!keyLeak.after, 'editor keys do not leak into the game (Q stays out of the spell wheel)');

  // painted borders are jittered but deterministic
  const jit = await page.evaluate(() => {
    const g = window.__grim, E = g.EDIT();
    const a = JSON.stringify(E.paintAt(12.7, 34.1));
    const b = JSON.stringify(E.paintAt(12.7, 34.1));
    return { same: a === b };
  });
  ok(jit.same, 'jittered paint sampling is deterministic');
  ok(ed.camFollowsPlayer, 'the terrain streamer follows the camera');
  ok(ed.bodyHidden, 'the player body is hidden in the editor');
  ok(ed.aboveGround, 'the camera never sinks under the world');
  ok(ed.chunks > 0, 'the editor streams the world', ed.chunks + ' chunks');
  ok(ed.catalogSize > 20, 'the object catalog is populated', ed.catalogSize + ' kinds');

  // The art track's kit models are placeable and correct
  const kits = await page.evaluate(() => {
    const g = window.__grim, CAT = g.EDIT_CAT(), R = g.EDIT_RENDER();
    const out = { have: {} };
    for (const k of ['furnace', 'anvil', 'campfire', 'tree_new', 'tree_oak', 'node_copper', 'node_gold', 'rock']) {
      out.have[k] = !!CAT[k];
    }
    // build each kit prop and confirm real geometry comes back
    const counts = {};
    for (const k of ['furnace', 'anvil', 'campfire', 'tree_new', 'tree_oak']) {
      const built = R.build(g, { i: 't' + k, k, x: 100, z: 100, y: 0, r: 0, s: 1 });
      let meshes = 0;
      if (built) built.traverse(o => { if (o.isMesh) meshes++; });
      counts[k] = meshes;
      out.noDispose = out.noDispose || (built && built.userData && built.userData._noDispose) || false;
    }
    out.counts = counts;
    // ore identity: copper and coal must build DIFFERENT geometry, which is
    // exactly what broke when the kind argument was dropped
    const fp = (kind) => {
      const built = R.build(g, { i: 'o' + kind, k: 'node_' + kind, x: 60, z: 60, y: 0, r: 0, s: 1 });
      let verts = 0, colorSum = 0;
      if (built) built.traverse(o => {
        if (o.isMesh && o.geometry && o.geometry.attributes.position) {
          verts += o.geometry.attributes.position.count;
          const col = o.geometry.attributes.color;
          if (col) for (let i = 0; i < Math.min(col.count, 200); i++) colorSum += col.getX(i);
        }
      });
      return verts + ':' + colorSum.toFixed(2);
    };
    out.copper = fp('copper');
    out.coal = fp('coal');
    // solid objects register a collider through the dress path
    const before = g.colliders.length;
    const rec = { cx: 9999, cz: 9999 };
    const L = g.EDIT().raw;
    L.objects.push({ i: 'coltest', k: 'furnace', x: 9999 * 64 + 5, z: 9999 * 64 + 5, y: 0, r: 0, s: 1 });
    g.EDIT().reindex();
    R.dress(g, rec);
    const during = g.colliders.length;
    R.drop(g, rec);
    const after = g.colliders.length;
    L.objects.pop(); g.EDIT().reindex();
    out.collider = { before, during, after };
    return out;
  });
  ok(Object.values(kits.have).every(Boolean), 'furnace, anvil, campfire, new trees, ores and boulder are all in the catalog',
    JSON.stringify(kits.have));
  ok(Object.values(kits.counts).every(n => n > 0), 'every kit model builds real geometry', JSON.stringify(kits.counts));
  ok(kits.noDispose, 'kit models are marked non-disposable so shared geometry survives streaming');
  ok(kits.copper !== kits.coal, 'copper and coal build different ore geometry (the kind argument reaches the kit)',
    kits.copper + ' vs ' + kits.coal);
  ok(kits.collider.during === kits.collider.before + 1 && kits.collider.after === kits.collider.before,
    'a solid placed object registers a collider and removes it when the chunk drops',
    JSON.stringify(kits.collider));

  // Paint through the real tool path and confirm the layer grew.
  const painted = await page.evaluate(() => {
    const g = window.__grim, S = g.EDIT_UI().state;
    const before = g.EDIT().stats().paint;
    S.tool = 'paint'; S.surf = 5; S.brush = 8;
    // Point the camera straight down and click the middle of the canvas, so
    // the REAL ground ray runs. Faking the ray result would prove only that
    // the brush maths works, not that the editor can find the ground.
    S.cam.pit = -1.5; S.cam.y = g.WORLD().height(S.cam.x, S.cam.z) + 60;
    g.EDIT_UI().tick(1 / 60);
    const el = g.renderer.domElement, r = el.getBoundingClientRect();
    const cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
    const hit = g.EDIT_UI().rayGround(0, 0);
    el.dispatchEvent(new MouseEvent('mousedown', { button: 0, clientX: cx, clientY: cy, bubbles: true }));
    window.dispatchEvent(new MouseEvent('mouseup', { button: 0, bubbles: true }));
    return {
      before, after: g.EDIT().stats().paint, dirty: S.dirty,
      rayHit: hit ? { x: +hit.x.toFixed(1), z: +hit.z.toFixed(1), y: +hit.y.toFixed(1) } : null,
      camAt: { x: +S.cam.x.toFixed(1), z: +S.cam.z.toFixed(1) },
      undoDepth: S.undo.length
    };
  });
  ok(painted.rayHit !== null, 'the ground ray finds the world under the cursor',
    painted.rayHit ? JSON.stringify(painted.rayHit) : 'no hit');
  ok(painted.after > painted.before, 'the paint tool writes cells into the layer',
    painted.before + ' -> ' + painted.after + ' cells');
  ok(painted.dirty === true, 'the editor knows it has unsaved work');

  // Every remaining tool, driven through its own entry point, plus undo,
  // redo and a real save round trip through the endpoint.
  const tools = await page.evaluate(async () => {
    const g = window.__grim, U = g.EDIT_UI(), E = g.EDIT(), S = U.state;
    const out = {};
    const here = { x: S.cam.x, z: S.cam.z, y: 0 };

    // undo and redo must restore the layer exactly
    const beforeUndo = E.exportLayer();
    S.tool = 'paint'; S.surf = 9;
    U.applyTool(here, true, false);
    const afterPaint = E.stats().paint;
    U.undo();
    out.undoRestores = E.exportLayer() === beforeUndo;
    U.redo();
    out.redoReapplies = E.stats().paint === afterPaint;

    // eyedropper: paint a known surface, then read it back off the world
    S.surf = 12; U.applyTool(here, true, false);
    out.eyedropped = U.eyedropAt(here);

    // spawns
    const s0 = E.raw.spawns.length;
    S.spawnKind = 'GOBLIN'; S.spawnN = 3; S.spawnRad = 20;
    U.addSpawn(here);
    out.spawnAdded = E.raw.spawns.length === s0 + 1;
    out.spawnRec = E.raw.spawns[E.raw.spawns.length - 1];
    U.removeSpawn(here);
    out.spawnRemoved = E.raw.spawns.length === s0;

    // districts
    S.tool = 'district'; S.districtName = 'testville';
    S.districtPts = [[here.x - 20, here.z - 20], [here.x + 20, here.z - 20], [here.x + 20, here.z + 20]];
    U.districtCommit();
    out.districtClosed = E.raw.districts.length === 1 && E.raw.districts[0].n === 'testville';
    out.overlayDrawn = !!g.scene.getObjectByName('__editOverlay');

    // copy and paste
    S.tool = 'place'; S.kind = 'barrel'; S.scale = 1; S.rot = 0;
    U.placeAt(here);
    const placed = E.raw.objects[E.raw.objects.length - 1];
    S.clipboard = Object.assign({}, placed);
    const n0 = E.raw.objects.length;
    U.paste({ x: here.x + 9, z: here.z + 9 });
    const pasted = E.raw.objects[E.raw.objects.length - 1];
    out.pasted = E.raw.objects.length === n0 + 1 && pasted.k === 'barrel' && pasted.i !== placed.i;

    // --- selecting the WORLD, not just your own objects -------------------
    // Kevin's report: he could not click a tree or an ore vein the world grew,
    // only things he had placed. The picker returns a tagged result now, so
    // these check both arms of it.
    S.tool = 'select';
    U.applyTool({ x: placed.x, z: placed.z, y: 0 }, true, false);
    out.pickedAuthored = !!(S.sel && S.sel.type === 'authored' && S.sel.o.i === placed.i);

    // a generated node: take a real one out of the live world and click it
    const grown = (g.zoneNodes || []).find(n => n && n.g && n.nid);
    out.hadGrown = !!grown;
    if (grown) {
      const gp = grown.g.position;
      U.applyTool({ x: gp.x, z: gp.z, y: 0 }, true, false);
      out.pickedWorld = !!(S.sel && S.sel.type === 'world' && S.sel.node.nid === grown.nid);
      // deleting it records the id rather than trying to splice a layer entry
      const rem0 = E.raw.removed.length;
      U.deleteSel();
      out.worldRemoved = E.raw.removed.length === rem0 + 1 && E.raw.removed.indexOf(grown.nid) >= 0;
      out.worldGoneFromScene = !(g.zoneNodes || []).some(n => n && n.nid === grown.nid);
    }

    // a hand-placed landmark asks once before it goes
    const landmark = (g.resources || []).find(r => r && r.nid);
    out.hadLandmark = !!landmark;
    if (landmark) {
      const lp = landmark.g.position;
      U.applyTool({ x: lp.x, z: lp.z, y: 0 }, true, false);
      out.pickedLandmark = !!(S.sel && S.sel.type === 'world' && S.sel.node.nid === landmark.nid);
      const rem1 = E.raw.removed.length;
      U.deleteSel();                                   // first press: warns only
      out.landmarkWarned = E.raw.removed.length === rem1 && !!S.sel;
      U.deleteSel();                                   // second press: commits
      out.landmarkDeleted = E.raw.removed.indexOf(landmark.nid) >= 0;
      out.landmarkGone = !(g.resources || []).some(r => r && r.nid === landmark.nid);
    }
    S.sel = null;

    // prefab save and stamp
    S.brush = 30;
    U.prefabSave('testfab', here);
    out.prefabSaved = !!E.raw.prefabs.testfab;
    const n1 = E.raw.objects.length;
    U.prefabStamp('testfab', { x: here.x + 120, z: here.z + 120 });
    out.prefabStamped = E.raw.objects.length > n1;

    // sculpt through the real tool
    const hBefore = g.WORLD().height(here.x + 60, here.z);
    S.tool = 'sculpt'; S.sculpt = 'raise'; S.brush = 16; S.strength = 3;
    for (let i = 0; i < 30; i++) U.applyTool({ x: here.x + 60, z: here.z, y: 0 }, i === 0, false);
    out.sculptRaised = g.WORLD().height(here.x + 60, here.z) - hBefore;

    // save round trip: PUT to the endpoint, then read it back
    S.key = 'harness-key';
    await U.save();
    const back = await fetch(E.CFG.URL + '?b=' + Date.now()).then(r => r.json());
    out.savedRev = E.rev;
    out.roundTrip = !!(back && back.objects && back.objects.length === E.raw.objects.length);
    out.dirtyCleared = S.dirty === false;
    return out;
  });
  ok(tools.undoRestores, 'undo restores the layer exactly');
  ok(tools.redoReapplies, 'redo puts the edit back');
  ok(tools.eyedropped === 12, 'the eyedropper reads back the surface that was painted',
    'got ' + tools.eyedropped);
  ok(tools.spawnAdded && tools.spawnRec && tools.spawnRec.n === 3 && tools.spawnRec.rad === 20,
    'a spawn marker records its creature, count and roam radius', JSON.stringify(tools.spawnRec));
  ok(tools.spawnRemoved, 'a spawn marker can be removed');
  ok(tools.districtClosed, 'a district closes into the layer');
  ok(tools.overlayDrawn, 'spawn and district markers are drawn in an editor-only overlay');
  ok(tools.pasted, 'copy and paste makes a new object rather than a second reference');
  ok(tools.pickedAuthored, 'clicking something you placed still selects it');
  ok(tools.hadGrown && tools.pickedWorld, 'clicking a tree or vein the WORLD grew selects it too');
  ok(tools.worldRemoved, 'deleting a grown node records its id in the removal list');
  ok(tools.worldGoneFromScene, 'the deleted node leaves the editor view immediately');
  ok(tools.hadLandmark && tools.pickedLandmark, 'a hand-placed landmark can be selected');
  ok(tools.landmarkWarned, 'deleting a landmark asks once instead of just doing it');
  ok(tools.landmarkDeleted, 'a second Delete press commits the landmark removal');
  ok(tools.landmarkGone, 'the deleted landmark leaves the editor view immediately');
  ok(tools.prefabSaved && tools.prefabStamped, 'a prefab saves and stamps');
  ok(tools.sculptRaised > 1.5, 'the sculpt tool raises real terrain',
    '+' + tools.sculptRaised.toFixed(2) + 'm');
  ok(tools.roundTrip, 'the layer saves to the endpoint and reads back intact');
  ok(tools.dirtyCleared, 'a successful save clears the unsaved flag');

  // Kevin's report: an older road could not be selected or removed, only the
  // most recently drawn one. Drives the real Select tool click path, then
  // clicks the actual "Delete this road" button the panel drew.
  const roadPick = await page.evaluate(() => {
    const g = window.__grim, U = g.EDIT_UI(), E = g.EDIT(), S = U.state;
    const L = E.raw;
    const before = L.roads.length;
    L.roads.push({ w: 6, s: 15, p: [[2000, 2000], [2040, 2000], [2080, 2000]] });
    E.reindex();
    const afterAdd = L.roads.length;
    S.tool = 'select'; S.sel = null;
    U.applyTool({ x: 2040, z: 2201, y: 0 }, true, false);   // 200m off any road
    const farType = S.sel ? S.sel.type : null;
    S.sel = null;
    U.applyTool({ x: 2040, z: 2001, y: 0 }, true, false);   // 1m off the centreline
    const pickedType = S.sel && S.sel.type;
    let clicked = false;
    for (const bt of document.querySelectorAll('button')) {
      if ((bt.textContent || '').trim() === 'Delete this road') { bt.click(); clicked = true; break; }
    }
    return { before, afterAdd, afterDelete: L.roads.length, pickedType, farType, clicked };
  });
  ok(roadPick.afterAdd === roadPick.before + 1, 'a second road can be added alongside an existing one');
  ok(roadPick.farType !== 'road', 'a point far from any road does not select one', String(roadPick.farType));
  ok(roadPick.pickedType === 'road', 'clicking near a road selects it through the Select tool, not only the most recent one');
  ok(roadPick.clicked, 'the selection panel draws a real Delete this road button');
  ok(roadPick.afterDelete === roadPick.before, 'the Delete this road button actually removes it', JSON.stringify(roadPick));

  // The four new brush controls, each driven through the real applyTool path.
  const brush = await page.evaluate(() => {
    const g = window.__grim, U = g.EDIT_UI(), E = g.EDIT(), S = U.state;
    const spot = { x: 3000, z: 3000, y: 0 };
    const countAt = () => { let c = 0; for (const k in E.raw.paint) c += E.raw.paint[k].length; return c; };

    // Hard edge (old, default behaviour): every cell in the radius commits.
    E.setLayer(null);
    S.tool = 'paint'; S.surf = 3; S.brush = 12; S.hardness = 1; S.flow = 1; S.organic = false; S.maskSurf = null;
    U.applyTool(spot, true, false);
    const hardCount = countAt();

    // Fully soft edge: only the centre cell is guaranteed, so fewer land.
    E.setLayer(null);
    S.hardness = 0;
    U.applyTool(spot, true, false);
    const softCount = countAt();

    // Low flow, full hardness: fewer cells commit per single pass.
    E.setLayer(null);
    S.hardness = 1; S.flow = 0.3;
    U.applyTool(spot, true, false);
    const lowFlowCount = countAt();

    // Mask: paint surface 5 solid, then try surface 6 locked to "unpainted
    // only" over the same patch (nothing should change), then lock to
    // surface 5 and paint 6 (every one of those cells should flip).
    E.setLayer(null);
    S.hardness = 1; S.flow = 1; S.organic = false; S.maskSurf = null;
    S.surf = 5; S.brush = 8;
    U.applyTool(spot, true, false);
    const paintedA = countAt();
    S.surf = 6; S.maskSurf = -1;
    U.applyTool(spot, true, false);
    const afterUnpaintedLock = countAt();
    let stillAllFive = true;
    for (const k in E.raw.paint) for (const e of E.raw.paint[k]) if (e[2] !== 5) stillAllFive = false;
    S.maskSurf = 5;
    U.applyTool(spot, true, false);
    let nowAllSix = true;
    for (const k in E.raw.paint) for (const e of E.raw.paint[k]) if (e[2] !== 6) nowAllSix = false;

    return { hardCount, softCount, lowFlowCount, paintedA, afterUnpaintedLock, stillAllFive, nowAllSix };
  });
  ok(brush.hardCount > 20, 'a full-hardness brush paints every cell in its radius, unchanged from before', brush.hardCount + ' cells');
  ok(brush.softCount > 0 && brush.softCount < brush.hardCount,
    'hardness 0 paints fewer cells than a full-hard brush of the same radius', brush.softCount + ' vs ' + brush.hardCount);
  ok(brush.lowFlowCount > 0 && brush.lowFlowCount < brush.hardCount,
    'flow below 1 commits fewer cells per pass than flow 1', brush.lowFlowCount + ' vs ' + brush.hardCount);
  ok(brush.afterUnpaintedLock === brush.paintedA && brush.stillAllFive,
    '"unpainted ground only" refuses to paint over an already-painted patch');
  ok(brush.nowAllSix, 'locking to a specific surface retextures exactly that surface and nothing else');

  const edErrs = eErrs.filter(e => !/404|Failed to load resource/.test(e));
  ok(edErrs.length === 0, 'no console errors in editor mode', edErrs.slice(0, 2).join(' | '));

  await page.close();
  await browser.close();

  console.log(notes.join('\n'));
  console.log('');
  if (fails.length) {
    console.log('FAILURES (' + fails.length + '):');
    for (const f of fails) console.log('  - ' + f);
    process.exit(1);
  }
  console.log('all world editor checks passed');
})().catch(e => { console.error(e); process.exit(1); });
