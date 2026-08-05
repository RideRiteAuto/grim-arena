// Server simulation smoke test. RUNS sim.js. Does not merely parse it.
//
// This exists because a change of mine shipped a ReferenceError into sim.js and
// took the entire monster simulation down in production: roamRadius read `R`,
// which is a local of stepNpc and not a module binding, so the first tick threw
// and no monster anywhere moved, attacked or respawned. `node --check` passed,
// because a free variable that resolves to nothing is valid syntax. It only
// fails when the line runs.
//
// So this builds the same ctx the relay builds, ticks a world of monsters
// through every branch that matters, and fails loudly on any throw.
import { mulberry32, makeSimNpc, stepNpc, separate, wander, integrate } from '../sim.js';
import { readFileSync } from 'fs';

const src = readFileSync(new URL('../shared-rules.js', import.meta.url), 'utf8');
const GRIM_RULES = eval('(function(){' + src + '; return GRIM_RULES;})()');

const fail = [];
const note = (m) => process.stdout.write(m + '\n');

function makeCtx(players, opts = {}) {
  const attacks = [], scripts = [];
  return {
    ctx: {
      rules: GRIM_RULES,
      rnd: mulberry32(12345),
      players,
      byId: Object.fromEntries(players.map(p => [p.id, p])),
      colliders: opts.colliders || [],
      safe: opts.safe || [{ x: 0, z: 0, r: 26 }, { x: 41, z: 31, r: 15 }],
      canAct: (n) => n.state === 'idle' && n.stagger <= 0 && n.frozen <= 0,
      attack: (n, move, tgt) => { attacks.push({ i: n.i, move, name: n.name }); },
      script: () => false
    },
    attacks, scripts
  };
}

// One of everything the world actually contains, so a change that only breaks
// beasts, or only breaks civilians, still gets caught.
const SPAWNS = [
  { x: 0, z: 240, max: 45, n: 'WILD BOAR', beast: true, w: 9, lockW: 9, zoneSpecies: 'BOAR', sig: 'TUSK CHARGE', aggroR: 9 },
  { x: 8, z: 240, max: 26, n: 'GIANT RAT', beast: true, w: 9, lockW: 9, zoneSpecies: 'GIANT_RAT', sig: 'TAIL WHIP', aggroR: 10 },
  { x: 14, z: 240, max: 30, n: 'YOUNG GOBLIN', w: 0, zoneSpecies: 'YOUNG_GOBLIN', sig: 'GOBLIN SHRIEK', aggroR: 11 },
  { x: 18, z: 240, max: 30, n: 'YOUNG GOBLIN', w: 0, zoneSpecies: 'YOUNG_GOBLIN', sig: 'GOBLIN SHRIEK', aggroR: 11 },
  { x: 24, z: 240, max: 8, n: 'HARE', beast: true, passive: true, skittish: true, zoneSpecies: 'HARE', aggroR: -1 },
  { x: 30, z: 240, max: 55, n: 'DIRE WOLF', beast: true, w: 9, lockW: 9, aggroR: 13 },
  { x: 36, z: 240, max: 70, n: 'BANDIT', w: 0, brawler: true, aggroR: 12 },
  { x: 42, z: 240, max: 60, n: 'BRIDA THE COOPER', civ: true, w: 9, lockW: 9, aggroR: 0 },
  { x: 48, z: 240, max: 480, n: 'THE PLAGUE RAT', beast: true, boss: true, w: 9, lockW: 9, aggroR: 15 },
  { x: 54, z: 240, max: 900, n: 'THE HOLLOW KING', king: true, boss: true, w: 5, aggroR: 16 }
];

function run(label, fn) {
  try { fn(); note('  ok   ' + label); }
  catch (e) { fail.push(label + ': ' + (e && e.stack ? e.stack.split('\n')[0] : e)); note('  FAIL ' + label + '  ' + e); }
}

note('server simulation smoke test');

// ---------------------------------------------------------------- 1. it ticks
run('a full world ticks for 60 simulated seconds without throwing', () => {
  const npcs = SPAWNS.map((s, i) => makeSimNpc(s, i));
  const player = { id: "p1", x: 0, z: 246, hp: 100, max: 100 };
  const { ctx } = makeCtx([player]);
  const dt = 0.1;
  for (let step = 0; step < 600; step++) {
    // walk the player around so every gate is exercised: in range, out of
    // range, inside a safe zone, and far enough to leash everything
    player.x = Math.sin(step / 40) * 70;
    player.z = 246 + Math.cos(step / 55) * 60;
    for (const n of npcs) { if (!n.dead) stepNpc(n, dt, ctx); }
    separate(npcs);
  }
  for (const n of npcs) {
    if (!Number.isFinite(n.x) || !Number.isFinite(n.z)) throw new Error(n.name + ' left the number line');
  }
});

// ------------------------------------------------- 2. the leash actually works
run('a monster dragged past its leash returns home, heals, and does not flip', () => {
  const npcs = [makeSimNpc(SPAWNS[0], 0)];
  const n = npcs[0];
  const player = { id: 'p1', x: 0, z: 240, hp: 100, max: 100 };
  const { ctx } = makeCtx([player]);
  const roam = GRIM_RULES.BESTIARY.BOAR.roamR;
  const chase = Math.min(GRIM_RULES.LEASH_R, roam + GRIM_RULES.LEASH.CHASE_EXTRA);
  // park it past its leash with the player right on top of it
  n.x = n.hx + chase + 1; n.z = n.hz;
  n.aggro = true; n.hp = 10;
  player.x = n.x; player.z = n.z + 1.5;
  let flips = 0, was = n.aggro, everHome = false, healed = false;
  for (let step = 0; step < 900; step++) {
    stepNpc(n, 0.1, ctx);
    if (n.aggro !== was) { flips++; was = n.aggro; }
    // It ARRIVES and then goes back to wandering its patch, so the check is
    // whether it ever got home, not where it happens to be standing at the end.
    if (Math.hypot(n.x - n.hx, n.z - n.hz) <= GRIM_RULES.LEASH.HOME_TOL) everHome = true;
    if (n.hp === n.max) healed = true;
  }
  if (flips > 1) throw new Error('aggro flipped ' + flips + ' times, the shake is back');
  if (!everHome) throw new Error('never reached home');
  if (!healed) throw new Error('never healed on arrival');
});

// --------------------------------------------------------- 3. it still fights
run('a monster in reach actually swings', () => {
  const n = makeSimNpc(SPAWNS[6], 0);       // bandit, sword and shield
  const player = { id: 'p1', x: n.x, z: n.z + 1.6, hp: 100, max: 100 };
  const { ctx, attacks } = makeCtx([player]);
  for (let step = 0; step < 300; step++) stepNpc(n, 0.1, ctx);
  if (!attacks.length) throw new Error('300 ticks in reach and never swung');
});

// ------------------------------------------------- 4. safe ground is respected
run('nothing picks a fight inside a safe zone', () => {
  const s = Object.assign({}, SPAWNS[6], { x: 2, z: 2 });
  const n = makeSimNpc(s, 0);
  const player = { id: 'p1', x: 0, z: 0, hp: 100, max: 100 };   // town centre
  const { ctx, attacks } = makeCtx([player]);
  for (let step = 0; step < 200; step++) stepNpc(n, 0.1, ctx);
  if (n.aggro) throw new Error('aggroed inside the town safe zone');
  if (attacks.length) throw new Error('swung inside the town safe zone');
});

// ------------------------------------------------------- 5. wander stays home
run('an idle monster stays inside its own patch', () => {
  const n = makeSimNpc(SPAWNS[5], 0);       // dire wolf, beast roam radius
  const player = { id: 'p1', x: 9999, z: 9999, hp: 100, max: 100 };
  const { ctx } = makeCtx([player]);
  let worst = 0;
  for (let step = 0; step < 3000; step++) {
    stepNpc(n, 0.1, ctx);
    worst = Math.max(worst, Math.hypot(n.x - n.hx, n.z - n.hz));
  }
  const roam = GRIM_RULES.ROAM_R.beast;
  if (worst > roam * 1.6) throw new Error('wandered ' + worst.toFixed(1) + 'm from home, patch is ' + roam + 'm');
});

note('');
if (fail.length) {
  note(fail.length + ' FAILED');
  for (const f of fail) note('  - ' + f);
  process.exit(1);
}
note('all green');
