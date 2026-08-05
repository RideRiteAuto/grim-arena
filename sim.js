// ===========================================================================
// GRIM WORLD - SERVER-SIDE MONSTER SIMULATION
//
// A faithful port of the game's own monster brain and movement step, rewritten
// without three.js so it can run inside the Durable Object. Every monster in
// the world is simulated here and nowhere else: no player's browser decides
// where a monster stands, which way it faces, or when it swings.
//
// Ported from, and kept in step with, the client's driveAI / wander /
// stepFighter. The numbers all come from GRIM_RULES so the two can never drift.
//
// Everything is flat X/Z. Height is decoration the client applies when drawing,
// so the server never needs the terrain.
// ===========================================================================

// Deterministic RNG. Math.random is forbidden in the sim path: identical
// inputs must produce an identical world, or a restart mid-fight would replay
// differently and desync every player at once.
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const TAU = Math.PI * 2;

// Build the live simulation state for one monster from its manifest spawn row.
function makeSimNpc(s, i) {
  return {
    i: i,
    // max health is what boss phases switch on; without it every boss sits in
    // phase one forever
    hp: Math.max(1, s.max | 0), max: Math.max(1, s.max | 0), dead: 0,
    x: s.x, z: s.z, yaw: 0,
    hx: s.x, hz: s.z,                      // home
    vx: 0, vz: 0, wx: 0, wz: 0,            // velocity, wanted velocity
    state: 'idle', st: 0, act: null, hitDone: false,
    moveAmt: 0,
    aggro: false, aggroPeer: null, returning: false,
    homeR: s.homeR == null ? null : s.homeR, zoneSpecies: s.zoneSpecies || null,
    wayX: 0, wayZ: 0, wayT: 0, hasWay: false,
    aiT: 0, aiSwitch: 0, aiStrafe: 1,
    guardT: 0, blocking: false, dodgeCd: 0,
    stagger: 0, frozen: 0, stam: 100, mana: 100,
    specialCd: 0,
    spd: s.spd == null ? 1 : s.spd,
    dmgScale: s.dmg == null ? 1 : s.dmg,
    aiD: s.ai == null ? 1 : s.ai,
    aggroR: s.aggroR == null ? 10 : s.aggroR,
    weapon: s.w || 0,
    lockW: s.lockW == null ? null : s.lockW,
    spell: s.spell || null,
    brawler: !!s.brawler,
    civ: !!s.civ, passive: !!s.passive, skittish: !!s.skittish,
    beast: !!s.beast,                      // four legs: claws, never a shield
    king: !!s.king, boss: !!s.boss,
    name: s.n || '',
    scriptId: s.script || null,
    phase: 0,
    dirty: 1, sentAt: 0
  };
}

// One monster, one fixed timestep. `players` is a live array of
// {id, x, z, hp} for everyone connected; `out` collects events for broadcast.
function stepNpc(n, dt, ctx) {
  const R = ctx.rules, rnd = ctx.rnd;

  // ---- timers ------------------------------------------------------------
  n.frozen = Math.max(0, n.frozen - dt);
  n.stagger = Math.max(0, n.stagger - dt);
  n.dodgeCd = Math.max(0, n.dodgeCd - dt);
  n.specialCd = Math.max(0, n.specialCd - dt);
  n.st += dt;

  // A dead monster must SAY it is dead. Reporting it as idle left corpses
  // walking on the spot forever on every screen.
  if (n.dead || n.hp <= 0) {
    n.state = 'dead'; n.act = null; n.aggro = false; n.aggroPeer = null;
    n.wx = 0; n.wz = 0; n.vx = 0; n.vz = 0;
    return;
  }

  // ---- pick a target: whoever hit it, else the nearest living player -----
  let tgt = null, bestD = 1e9;
  if (n.aggroPeer) {
    const p = ctx.byId[n.aggroPeer];
    if (p && p.hp > 0) { tgt = p; bestD = Math.hypot(p.x - n.x, p.z - n.z); }
  }
  if (!tgt) {
    for (const p of ctx.players) {
      if (!(p.hp > 0)) continue;
      const d = Math.hypot(p.x - n.x, p.z - n.z);
      if (d < bestD) { bestD = d; tgt = p; }
    }
  }

  // Walking home outranks everything, including having no target at all. This
  // check used to live below, after the aggro gates, so a monster that gave up
  // and then lost sight of every player fell through to `wander` and ambled
  // back at a third of the pace, sometimes never arriving. Returning is a
  // journey with a destination; it does not care whether anyone is watching.
  if (n.returning) {
    const fh = Math.hypot(n.x - n.hx, n.z - n.hz);
    if (fh <= R.LEASH.HOME_TOL) {
      n.returning = false; n.hasWay = false; n.wayT = 0;
      if (R.LEASH.HEAL_ON_RETURN && n.hp > 0 && n.max) n.hp = n.max;
    } else {
      n.aggro = false; n.aggroPeer = null;
      walkHome(n, dt, R); integrate(n, dt, ctx); return;
    }
  }

  if (!tgt) { wander(n, dt, ctx); integrate(n, dt, ctx); return; }

  const dp = bestD;

  // ---- safe ground, leashing, aggro gates --------------------------------
  // Towns and the camp are safe: nothing starts a fight inside one, and
  // anything dragged in breaks off. Dragged too far from home, it goes back.
  let meSafe = false, npcSafe = false;
  for (const s of ctx.safe) {
    const rMe = s.rMe != null ? s.rMe : s.r;
    const rNpc = s.rNpc != null ? s.rNpc : (s.r != null ? s.r + 2 : 0);
    if (rMe && Math.hypot(tgt.x - s.x, tgt.z - s.z) < rMe) meSafe = true;
    if (rNpc && Math.hypot(n.x - s.x, n.z - s.z) < rNpc) npcSafe = true;
  }
  // How far this one follows: its own ground plus a fixed overrun, capped by
  // the world ceiling. Mirrors roamRadius on the client exactly; if the two
  // sides disagree about who is aggro'd, monsters teleport on screen.
  const roamR = roamRadius(n, R);
  const chaseR = Math.min(R.LEASH_R, roamR + R.LEASH.CHASE_EXTRA);
  const fromHome = Math.hypot(n.x - n.hx, n.z - n.hz);
  const leashed = fromHome > chaseR;
  const safe = meSafe || npcSafe;

  // Only the timid and the genuinely passive refuse a fight outright. A
  // townsperson will absolutely defend themselves once you swing at them,
  // which is how it has always worked - adding civilians to this list made
  // them permanent punching bags.
  if (n.skittish || (n.passive && !n.aggro)) { wander(n, dt, ctx); integrate(n, dt, ctx); return; }

  // (the returning state is handled above, before target selection)

  if (n.aggro && (safe || leashed)) {
    n.aggro = false; n.aggroPeer = null; n.hasWay = false; n.wayT = 0;
    if (leashed) { n.returning = true; walkHome(n, dt, R); integrate(n, dt, ctx); return; }
    wander(n, dt, ctx); integrate(n, dt, ctx); return;
  }
  if (!n.aggro) {
    // Do not start a fight from outside your own ground either.
    if (n.aggroR >= 0 && dp < n.aggroR && !safe && !leashed) { n.aggro = true; }
    else { wander(n, dt, ctx); integrate(n, dt, ctx); return; }
  } else if (dp > R.DEAGGRO_R) {
    n.aggro = false; n.aggroPeer = null;
    if (fromHome > roamR) { n.returning = true; walkHome(n, dt, R); integrate(n, dt, ctx); return; }
    wander(n, dt, ctx); integrate(n, dt, ctx); return;
  }

  // ---- face the target ---------------------------------------------------
  // A committed swing does NOT steer. The attack event carries the facing the
  // blow was launched with, and every player judges their own dodge against
  // the monster they can see; if the monster keeps turning through its own
  // commit window those two stop describing the same arc, and worse, a
  // monster that tracks you all the way through its wind-up cannot be dodged
  // by moving, which is the whole point of a telegraph. It aimed when it
  // decided to swing. It lives with that until the swing is over.
  const tox = (tgt.x - n.x) / (dp || 1), toz = (tgt.z - n.z) / (dp || 1);
  if (!n.act) n.yaw = Math.atan2(tox, toz);

  n.aiT -= dt; n.aiSwitch -= dt;
  if (n.aiT <= 0) { n.aiT = 1.1 + rnd() * 1.6; n.aiStrafe = rnd() < 0.5 ? -1 : 1; }

  // ---- boss scripts take over decision making when one is attached -------
  if (ctx.script && ctx.script(n, tgt, dp, dt, ctx)) { integrate(n, dt, ctx); return; }

  // ---- weapon choice -----------------------------------------------------
  if (n.lockW != null) n.weapon = n.lockW;
  else if (n.aiSwitch <= 0 && n.state === 'idle') {
    n.aiSwitch = 9 + rnd() * 9;
    n.weapon = dp > 9 ? (rnd() < 0.5 ? 1 : 2) : (rnd() < 0.72 ? 0 : 1);
  }

  // ---- hold distance + circling -----------------------------------------
  // The hold radius sits INSIDE the weapon's reach and the deadband is
  // narrower than the gap, or the monster parks just out of its own range and
  // never swings. Circling only kicks in once already in reach, otherwise
  // every approach turns into a spiral.
  const ranged = n.weapon === 1 || n.weapon === 2;
  const want = n.weapon === 1 ? 8.5 : n.weapon === 2 ? 11 : n.weapon === 5 ? 2.6 : n.weapon === 0 ? 2.0 : 1.6;
  const band = ranged ? 1.1 : 0.3;
  const err = dp - want;
  const closing = Math.abs(err) > band;
  let mx = 0, mz = 0;
  if (closing) { const s = Math.sign(err); mx += tox * s; mz += toz * s; }
  const strafe = n.aiStrafe * (closing ? 0.14 : 0.7);
  mx += toz * strafe; mz += -tox * strafe;
  const ml = Math.hypot(mx, mz);
  if (ml > 0.1) { mx /= ml; mz /= ml; } else { mx = 0; mz = 0; }

  let sp = R.SPEED * (0.72 + 0.3 * n.aiD) * n.spd;
  if (n.blocking) sp *= 0.4;
  if (n.state === 'attack' || n.state === 'cast') sp *= 0.22;
  if (n.frozen > 0 || n.stagger > 0) sp = 0;
  n.wx = mx * sp; n.wz = mz * sp;
  n.moveAmt += ((sp > 0.5 ? 1 : 0) - n.moveAmt) * Math.min(1, dt * 12);

  // ---- guard cadence -----------------------------------------------------
  n.guardT -= dt;
  if (n.weapon === 0 && dp < 4.6 && n.state === 'idle') {
    if (n.guardT <= 0) {
      if (n.blocking) { n.blocking = false; n.guardT = 0.7 + rnd() * 1.4 / n.aiD; }
      else if (rnd() < 0.32 * n.aiD) { n.blocking = true; n.guardT = 0.35 + rnd() * 0.6; }
      else n.guardT = 0.4 + rnd() * 0.7;
    }
  } else { n.blocking = false; n.guardT = 0; }
  if (n.stam < 12) { n.blocking = false; n.guardT = 1.2; }

  // ---- attack decision (emits a scheduled event; see attack()) -----------
  //
  // MELEE_RATE is the goblin's cadence, and the goblin is the one that feels
  // right, so everything that fights up close uses it. Each branch gates on the
  // move's OWN declared reach rather than a number written here, which is what
  // let a monster sit inside its range swinging a move that could not reach.
  if (ctx.canAct(n) && !n.blocking) {
    const M = R.MOVES;
    const MELEE_RATE = 2.6;
    // Mirrors the client combat-feel fix (Aug 5): melee starts from 85% of
    // max reach so the swing you see actually connects; the longer a monster
    // stands in reach without swinging the more certain the next swing
    // becomes (first attack near-guaranteed inside ~0.6s); and the dice are
    // clamped so a slow tick can never burst-fire attacks.
    const rdt = Math.min(dt, 0.1);   // server ticks a fixed 10Hz; clamp only guards the catch-up loop
    const meleeGate = n.weapon === 0 ? M.light.range * 0.85
      : n.weapon === 5 ? M.glight.range * 0.85
      : (n.weapon === 3 || n.weapon === 4 || n.weapon === 9) ? M[n.beast ? 'claw' : 'chop'].range * 0.85
      : 0;
    n.inR = (meleeGate && dp < meleeGate && n.state === 'idle') ? (n.inR || 0) + dt : 0;
    const eager = 1 + Math.min(4, (n.inR || 0) * 5);
    if (n.weapon === 0 && dp < meleeGate && rnd() < MELEE_RATE * eager * n.aiD * rdt) {
      ctx.attack(n, rnd() < 0.26 ? 'heavy' : 'light', tgt); n.inR = 0;
    } else if (n.weapon === 1 && dp < 16 && n.mana > 25 && rnd() < (n.spell === 'snare' ? 1.3 : 0.9) * n.aiD * rdt) {
      ctx.attack(n, n.spell === 'snare' ? 'snare' : 'frost', tgt);
    } else if (n.weapon === 5) {
      // two-handers: a wide cleave, and the overhead when it commits
      const mv = rnd() < 0.26 ? 'gheavy' : 'glight';
      if (dp < M[mv].range * 0.85 && rnd() < MELEE_RATE * eager * n.aiD * rdt) { ctx.attack(n, mv, tgt); n.inR = 0; }
    } else if (n.weapon === 3 || n.weapon === 4 || n.weapon === 9) {
      // A beast rakes with a paw and occasionally commits to a bite, the same
      // 26% mix a sword-and-shield fighter uses for its heavy. Everyone else
      // swings the tool in their hands, or their fists.
      const mv = n.beast ? (rnd() < 0.26 ? 'bite' : 'claw') : 'chop';
      if (dp < M[mv].range * 0.85 && rnd() < MELEE_RATE * eager * n.aiD * rdt) { ctx.attack(n, mv, tgt); n.inR = 0; }
    } else if (n.weapon === 2 && dp < 20 && rnd() < 1.1 * n.aiD * rdt) {
      ctx.attack(n, rnd() < 0.5 ? 'rapid' : 'shot', tgt);
    }
  }

  integrate(n, dt, ctx);
}

// How much ground this creature calls its own. Species first, then the role
// defaults. Kept identical to roamRadius on the client.
// The rules have to be PASSED IN. `R` only exists as a local inside stepNpc,
// so reading it here threw ReferenceError on the very first tick and took the
// whole simulation down with it: no monster moved, attacked or respawned
// anywhere in the world.
function roamRadius(n, R) {
  if (n._roamR != null) return n._roamR;
  const RR = R.ROAM_R;
  let r = n.homeR;
  if (r == null && n.zoneSpecies && R.BESTIARY[n.zoneSpecies]) r = R.BESTIARY[n.zoneSpecies].roamR;
  if (r == null) {
    r = n.civilian ? RR.civilian
      : n.worker ? RR.worker
      : (n.king || n.rat || n.warden || n.captain) ? RR.boss
      : (n.passive || n.skittish) ? RR.wildlife
      : n.beast ? RR.beast
      : RR.camp;
  }
  n._roamR = r;
  return r;
}

// The walk back: straight at the home point, a little quicker than a wander.
// Same story as roamRadius: R is a local of stepNpc, not a module global.
function walkHome(n, dt, R) {
  const dx = n.hx - n.x, dz = n.hz - n.z;
  const d = Math.hypot(dx, dz);
  if (d < 0.6) { n.wx = 0; n.wz = 0; n.moveAmt *= 0.85; return; }
  n.yaw = Math.atan2(dx / d, dz / d);
  const sp = 2.3 * R.LEASH.RETURN_SPEED;
  n.wx = (dx / d) * sp; n.wz = (dz / d) * sp;
  n.moveAmt += (0.6 - n.moveAmt) * Math.min(1, dt * 6);
}

function wander(n, dt, ctx) {
  const rnd = ctx.rnd;
  // Skittish wildlife bolts from the nearest player and never fights back.
  if (n.skittish) {
    let near = null, nd = 1e9;
    for (const p of ctx.players) {
      if (!(p.hp > 0)) continue;
      const d = Math.hypot(n.x - p.x, n.z - p.z);
      if (d < nd) { nd = d; near = p; }
    }
    if (near && nd < 15 && nd > 0.001) {
      const dx = (n.x - near.x) / nd, dz = (n.z - near.z) / nd;
      n.yaw = Math.atan2(dx, dz);
      n.wx = dx * 7.4; n.wz = dz * 7.4;
      n.moveAmt += (1 - n.moveAmt) * Math.min(1, dt * 9);
      n.hasWay = false; n.wayT = 0;
      return;
    }
  }
  n.wayT -= dt;
  const dwx = n.wayX - n.x, dwz = n.wayZ - n.z;
  if (!n.hasWay || Math.hypot(dwx, dwz) < 1.6 || n.wayT <= 0) {
    const a = rnd() * TAU;
    const r = n.name === 'MR. SAILERS' ? 14 + rnd() * 22 : roamRadius(n, ctx.rules) * (0.35 + rnd() * 0.65);
    let wx = n.hx + Math.cos(a) * r, wz = n.hz + Math.sin(a) * r;
    // Keep the waypoint inside the WORLD, not inside a 162m circle around the
    // world origin. The old clamp measured the waypoint's distance from 0,0 and
    // pulled anything past 162m back toward it, which was harmless when the
    // whole game was one arena and badly wrong in a 4,800m world: every monster
    // living further out than that had its wander target dragged toward the
    // capital, so nothing stayed in its own field.
    const WR = (ctx.rules && ctx.rules.WORLD_R) || 4800;
    const rr = Math.hypot(wx, wz);
    if (rr > WR) { wx *= WR / rr; wz *= WR / rr; }
    n.wayX = wx; n.wayZ = wz; n.hasWay = true;
    n.wayT = 6 + rnd() * 6;
  }
  const dx = n.wayX - n.x, dz = n.wayZ - n.z, dl = Math.hypot(dx, dz);
  if (dl > 0.6) {
    n.yaw = Math.atan2(dx / dl, dz / dl);
    n.wx = dx / dl * 2.3; n.wz = dz / dl * 2.3;
    n.moveAmt += (0.45 - n.moveAmt) * Math.min(1, dt * 6);
  } else { n.wx = 0; n.wz = 0; }
}

// Velocity damping, integration, world edge and collision. Exactly the client's
// order of operations - damp toward wanted, move, clamp to the world, push out
// of colliders - because doing them in a different order puts monsters in
// visibly different places.
function integrate(n, dt, ctx) {
  const acc = (n.wx * n.wx + n.wz * n.wz) > 0.01 ? 26 : 20;
  const k = 1 - Math.exp(-acc * dt);
  n.vx += (n.wx - n.vx) * k;
  n.vz += (n.wz - n.vz) * k;

  if (!n.blocking && n.state !== 'dodge') n.stam = Math.min(100, n.stam + 21 * dt);
  if (n.state !== 'cast') n.mana = Math.min(100, n.mana + 11 * dt);

  n.x += n.vx * dt;
  n.z += n.vz * dt;

  const r = Math.hypot(n.x, n.z);
  const WR = ctx.rules.WORLD_R;
  if (r > WR) { n.x *= WR / r; n.z *= WR / r; }

  for (const c of ctx.colliders) {
    const dx = n.x - c.x, dz = n.z - c.z;
    if (c.r) {
      const d = Math.hypot(dx, dz);
      if (d < c.r && d > 0.0001) { n.x = c.x + dx / d * c.r; n.z = c.z + dz / d * c.r; }
    } else {
      if (Math.abs(dx) < c.hw + 0.42 && Math.abs(dz) < c.hd + 0.42) {
        const px = c.hw + 0.42 - Math.abs(dx), pz = c.hd + 0.42 - Math.abs(dz);
        if (px < pz) n.x = c.x + (dx >= 0 ? 1 : -1) * (c.hw + 0.42);
        else n.z = c.z + (dz >= 0 ? 1 : -1) * (c.hd + 0.42);
      }
    }
  }
  n.dirty = 1;
}

// Monsters in a fight shove each other apart so a pack surrounds a player
// instead of collapsing onto one point.
function separate(npcs) {
  const eng = [];
  for (const n of npcs) if (!n.dead && n.hp > 0 && n.aggro) eng.push(n);
  for (let i = 0; i < eng.length; i++) {
    for (let j = i + 1; j < eng.length; j++) {
      const a = eng[i], b = eng[j];
      const dx = b.x - a.x, dz = b.z - a.z;
      const d = Math.hypot(dx, dz);
      if (d < 1.6 && d > 0.001) {
        const p = (1.6 - d) * 0.5, nx = dx / d, nz = dz / d;
        a.x -= nx * p; a.z -= nz * p; b.x += nx * p; b.z += nz * p;
        a.dirty = 1; b.dirty = 1;
      }
    }
  }
}

export { mulberry32, makeSimNpc, stepNpc, separate, wander, integrate };
