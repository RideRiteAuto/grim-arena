// Proves that what Kevin PLACES in the editor is real in the game.
//
// This is the test for his two reports: that he could not select or delete the
// things the world grew, and that objects he placed showed up but did nothing.
// The second one is the point of the whole editor, so the checks here are
// deliberately end-to-end and played rather than inspected: the harness walks
// a real player up to a placed copper vein, points them at it, swings a real
// pick through the game's own gatherCheck, and asserts ORE LANDS IN THE PACK.
// Nothing here reads the edit layer back to itself.
//
// Written to FAIL before this work: with placed objects as scenery the vein is
// not in allResources at all, the swing falls through to the melee path, and
// the placed furnace/anvil/bank never appear in interactCandidates.
//
// The game is booted WITHOUT ?edit=1 on purpose. This is the player's build.
const { chromium } = require('playwright');
const fs = require('fs');

const URL = 'http://127.0.0.1:8123/index.html';
const EDITS = '/tmp/grim-edits.json';

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

// Any throw still prints everything that passed first, so a failure halfway
// through does not hide the twenty checks that got there.
process.on('uncaughtException', e => {
  console.log(notes.join('\n'));
  console.log('\nTHREW: ' + (e && e.stack ? e.stack : e));
  process.exit(1);
});

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });

  // ---- find the spawn, then author around it -----------------------------
  try { fs.unlinkSync(EDITS); } catch (e) {}
  let a = await open(browser);
  const P = await a.page.evaluate(() => ({ x: window.__grim.me.pos.x, z: window.__grim.me.pos.z }));
  await a.page.close();

  const layer = {
    v: 1, gen: 9, paint: {}, height: {}, roads: [],
    objects: [
      { i: 'ore1',  k: 'node_copper', x: P.x + 10, z: P.z,      y: 0, r: 0, s: 1 },
      { i: 'tree1', k: 'node_poplar', x: P.x,      z: P.z + 10, y: 0, r: 0, s: 1 },
      { i: 'furn1', k: 'furnace',     x: P.x - 12, z: P.z,      y: 0, r: 0, s: 1 },
      { i: 'anv1',  k: 'anvil',       x: P.x - 12, z: P.z + 6,  y: 0, r: 0, s: 1 },
      { i: 'bank1', k: 'bankbooth',   x: P.x - 12, z: P.z - 6,  y: 0, r: 0, s: 1 }
    ],
    removed: [], spawns: [], prefabs: {}, districts: [], bookmarks: []
  };
  fs.writeFileSync(EDITS, JSON.stringify(layer));

  const b = await open(browser);
  await b.page.waitForFunction(() => window.__grim.EDIT().on === true, null, { timeout: 30000 });
  await b.page.waitForTimeout(2000);

  // ---- 1. placed harvestables are REAL NODES -----------------------------
  const reg = await b.page.evaluate(() => {
    const g = window.__grim;
    const find = (nid) => (g.zoneNodes || []).find(n => n && n.nid === nid) || null;
    const ore = find('ed:ore1'), tree = find('ed:tree1');
    const all = g.allResources();
    return {
      oreFound: !!ore, treeFound: !!tree,
      oreKind: ore && ore.kind, treeKind: tree && tree.kind,
      oreHp: ore && ore.hp, treeHp: tree && tree.hp,
      oreInAll: !!(ore && all.indexOf(ore) >= 0),
      treeInAll: !!(tree && all.indexOf(tree) >= 0),
      // the depletion animation needs these; a display-only build has none
      oreHasStuds: !!(ore && ore.studs && ore.studs.length),
      treeHasFell: !!(tree && tree.fell),
      treeHasStump: !!(tree && tree.stump)
    };
  });
  ok(reg.oreFound, 'a placed ore vein registers as a real world node', 'ed:ore1');
  ok(reg.treeFound, 'a placed tree registers as a real world node', 'ed:tree1');
  ok(reg.oreKind === 'copper', 'the placed vein keeps its authored kind', String(reg.oreKind));
  ok(reg.treeKind === 'poplar', 'the placed tree keeps its authored kind', String(reg.treeKind));
  ok(reg.oreHp === 3, 'the vein takes its HP from the gather table, not a guess', 'hp ' + reg.oreHp);
  ok(reg.oreInAll && reg.treeInAll, 'placed nodes are in allResources, which is what every gather path walks');
  ok(reg.oreHasStuds, 'the placed vein was built by the game builder, so it has ore studs to hide when emptied');
  ok(reg.treeHasFell && reg.treeHasStump, 'the placed tree has a fell trunk and a stump, so felling can animate');

  // ---- 2. MINE IT. The whole point. --------------------------------------
  const mined = await b.page.evaluate(() => {
    const g = window.__grim;
    const node = g.zoneNodes.find(n => n.nid === 'ed:ore1');
    const p = node.g.position;
    // stand next to it, face it, hold a pick, and have the level for copper
    g.me.pos.set(p.x - 1.6, 0, p.z);
    g.me.yaw = Math.atan2(p.x - g.me.pos.x, p.z - g.me.pos.z);
    g.me.weapon = 3;
    g.skills.MINING = 400000;
    const before = g.invCount('COPPER ORE');
    let swings = 0;
    while (!node.dead && swings < 40) { g.gatherCheck(g.me); swings++; }
    return {
      dead: node.dead, swings,
      gained: g.invCount('COPPER ORE') - before,
      respawn: node.respawn,
      studsHidden: !!(node.studs && node.studs.every(s => !s.visible))
    };
  });
  ok(mined.dead, 'a placed copper vein can actually be mined out', mined.swings + ' swings');
  ok(mined.gained > 0, 'mining a placed vein puts real ore in the pack', '+' + mined.gained + ' COPPER ORE');
  ok(mined.respawn > 0, 'the emptied vein is on a respawn clock like any other', mined.respawn.toFixed(0) + 's');
  ok(mined.studsHidden, 'the emptied vein reads as empty, its ore studs are hidden');

  // ---- 3. CHOP IT --------------------------------------------------------
  const chopped = await b.page.evaluate(() => {
    const g = window.__grim;
    const node = g.zoneNodes.find(n => n.nid === 'ed:tree1');
    const p = node.g.position;
    g.me.pos.set(p.x, 0, p.z - 1.8);
    g.me.yaw = Math.atan2(p.x - g.me.pos.x, p.z - g.me.pos.z);
    g.me.weapon = 4;
    g.skills.WOODCUTTING = 400000;
    const before = g.invCount('LOGS');
    let swings = 0;
    while (!node.dead && swings < 40) { g.gatherCheck(g.me); swings++; }
    return { dead: node.dead, swings, gained: g.invCount('LOGS') - before, respawn: node.respawn };
  });
  ok(chopped.dead, 'a placed tree can actually be felled', chopped.swings + ' swings');
  ok(chopped.gained > 0, 'felling a placed tree puts real logs in the pack', '+' + chopped.gained + ' LOGS');
  ok(chopped.respawn > 0, 'the felled tree is regrowing');

  // ---- 4. harvested state survives the chunk streaming out and back -------
  const persisted = await b.page.evaluate(async () => {
    const g = window.__grim;
    // force every chunk to drop and rebuild, the same path walking away does
    for (const [k, ch] of g._chunks) { try { g.dressDrop(ch); } catch (e) {} }
    const gone = !g.zoneNodes.some(n => n.nid === 'ed:ore1');
    g._chunks.forEach(ch => { try { g.dressChunk(ch); } catch (e) {} });
    const back = g.zoneNodes.find(n => n.nid === 'ed:ore1');
    return { droppedCleanly: gone, cameBack: !!back, stillEmpty: !!(back && back.dead) };
  });
  ok(persisted.droppedCleanly, 'a placed node leaves the world with its chunk, no leak');
  ok(persisted.cameBack, 'a placed node comes back when its chunk does');
  ok(persisted.stillEmpty, 'a vein you emptied is still empty when you walk back, not refilled');

  // ---- 5. placed STATIONS work -------------------------------------------
  const stations = await b.page.evaluate(() => {
    const g = window.__grim;
    const at = (kind) => {
      const st = g.stationsList().find(s => s.authored && s.kind === kind);
      if (!st) return { found: false };
      g.me.pos.set(st.pos.x + 1.4, 0, st.pos.z);
      const near = !!g.nearestStation(kind, kind === 'bank' ? 4.0 : 3.2);
      const cands = g.interactCandidates().map(c => c.label);
      return { found: true, near, cands };
    };
    const f = at('furnace');
    const smelted = f.found ? g.trySmelt() : false;
    const furnOpen = g.furnOpen;
    if (g.furnOpen) g.closeFurnace();

    const an = at('anvil');
    const forged = an.found ? g.tryForge() : false;
    const anvOpen = g.anvOpen;
    if (g.anvOpen) g.closeAnvil();

    const bk = at('bank');
    const banked = bk.found ? g.tryBank() : false;
    const bankOpen = g.bankOpen;
    if (g.bankOpen) g.closeBank();

    return { f, smelted, furnOpen, an, forged, anvOpen, bk, banked, bankOpen,
             total: g.stationsList().length };
  });
  ok(stations.f.found, 'a placed furnace registers as a station');
  ok(stations.f.near, 'the placed furnace answers "is a furnace in reach"');
  ok(stations.f.cands.some(l => /SMELT ORE/.test(l)), 'standing at a placed furnace offers SMELT ORE', stations.f.cands.join(' | ') || 'no prompt');
  ok(stations.smelted && stations.furnOpen, 'F at a placed furnace actually opens the furnace');

  ok(stations.an.found && stations.an.near, 'a placed anvil registers and is reachable');
  ok(stations.an.cands.some(l => /SMITH/.test(l)), 'standing at a placed anvil offers SMITH', stations.an.cands.join(' | ') || 'no prompt');
  ok(stations.forged && stations.anvOpen, 'F at a placed anvil actually opens the anvil');

  ok(stations.bk.found && stations.bk.near, 'a placed bank booth registers and is reachable');
  ok(stations.bk.cands.some(l => /OPEN YOUR BANK/.test(l)), 'standing at a placed bank offers OPEN YOUR BANK', stations.bk.cands.join(' | ') || 'no prompt');
  ok(stations.banked && stations.bankOpen, 'F at a placed bank booth actually opens the vault');

  // ---- 6. the camp forge and the real bank still work --------------------
  const camp = await b.page.evaluate(() => {
    const g = window.__grim;
    const out = {};
    g.me.pos.set(g.furnace.pos.x + 1.4, 0, g.furnace.pos.z);
    out.campFurnace = g.trySmelt() && g.furnOpen; if (g.furnOpen) g.closeFurnace();
    g.me.pos.set(g.anvil.pos.x + 1.4, 0, g.anvil.pos.z);
    out.campAnvil = g.tryForge() && g.anvOpen; if (g.anvOpen) g.closeAnvil();
    g.me.pos.set(g.bankPos.x + 1.4, 0, g.bankPos.z);
    out.hollowrestBank = g.tryBank() && g.bankOpen; if (g.bankOpen) g.closeBank();
    // and nothing answers from an empty field
    g.me.pos.set(g.furnace.pos.x + 400, 0, g.furnace.pos.z + 400);
    out.nothingInAField = !g.nearestStation('furnace', 3.2) && !g.trySmelt();
    return out;
  });
  ok(camp.campFurnace, 'REGRESSION: the camp furnace still smelts');
  ok(camp.campAnvil, 'REGRESSION: the camp anvil still smiths');
  ok(camp.hollowrestBank, 'REGRESSION: the Bank of Hollowrest still opens');
  ok(camp.nothingInAField, 'no station answers from the middle of an empty field');

  // ---- 7. hand-placed world resources now carry ids ----------------------
  const fixedIds = await b.page.evaluate(() => {
    const g = window.__grim;
    const withId = (g.resources || []).filter(r => r && r.nid).length;
    const total = (g.resources || []).length;
    const sample = (g.resources || []).find(r => r && r.nid);
    return { withId, total, sample: sample ? sample.nid : null, kind: sample ? sample.kind : null };
  });
  ok(fixedIds.total > 0 && fixedIds.withId === fixedIds.total,
    'every hand-placed world resource now has a stable id, so it can be named and deleted',
    fixedIds.withId + '/' + fixedIds.total + ' e.g. ' + fixedIds.sample);
  await b.page.close();

  // ---- 8. deleting a grown thing keeps it gone FOR PLAYERS ---------------
  // The nid is read off the live world, then written into the removal list and
  // the game rebooted as an ordinary player.
  const target = fixedIds.sample;
  layer.removed = [target];
  fs.writeFileSync(EDITS, JSON.stringify(layer));
  const c = await open(browser);
  await c.page.waitForFunction(() => window.__grim.EDIT().on === true, null, { timeout: 30000 });
  await c.page.waitForTimeout(2000);
  const del = await c.page.evaluate(nid => {
    const g = window.__grim;
    const stillThere = (g.resources || []).some(r => r && r.nid === nid);
    const inScene = (g.resources || []).length;
    return { stillThere, inScene };
  }, target);
  ok(!del.stillThere, 'a hand-placed resource Kevin deleted is gone for players too', target);

  const errs = c.errs.filter(e => !/404|Failed to load resource/.test(e));
  ok(errs.length === 0, 'no console errors in the played build', errs.slice(0, 2).join(' | '));
  await c.page.close();

  await browser.close();
  console.log(notes.join('\n'));
  if (fails.length) {
    console.log('\n' + fails.length + ' FAILED:\n  ' + fails.join('\n  '));
    process.exit(1);
  }
  console.log('\nall editor gameplay checks passed');
})();
