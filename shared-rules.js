// ===========================================================================
// GRIM WORLD - SHARED RULES
//
// THE single source of truth for anything the game and the server must agree
// on. This file is injected verbatim into BOTH the game bundle and the
// Cloudflare worker by repack.py, between the SHARED-RULES markers. Never edit
// the injected copies; edit this file and run `python3 repack.py pack`.
//
// If the game and the server ever disagree about a wind-up time, an attack
// reach or a loot roll, players see monsters hit them through walls of air and
// loot that differs per screen. That whole class of bug is what this file
// exists to make impossible.
// ===========================================================================
const GRIM_RULES = {
  V: 1,

  // ---- world bounds -------------------------------------------------------
  WORLD_R: 168,          // open-world edge, clamped identically on both sides
  ARENA_R: 23,           // legacy duel arena

  // ---- movement -----------------------------------------------------------
  SPEED: 5.6,
  SPRINT: 8.4,
  DIFF: { squire: 0.62, veteran: 1.0, champion: 1.42 },

  // ---- attacks ------------------------------------------------------------
  // wind = telegraph, act = damage frame, rec = recovery. range/arc define the
  // hit shape; a client judges only ITSELF against this shape, so these numbers
  // are what makes a dodge fair.
  MOVES: {
    light:  { wind: .32, act: .12, rec: .22, dmg: [8, 12],  range: 3.0, arc: 1.9, stam: 6 },
    heavy:  { wind: .48, act: .15, rec: .40, dmg: [22, 30], range: 3.4, arc: 2.5, stam: 18, heavy: true },
    glight: { wind: .30, act: .16, rec: .34, dmg: [18, 26], range: 3.6, arc: 2.7, stam: 12 },
    gheavy: { wind: .60, act: .18, rec: .52, dmg: [34, 46], range: 3.9, arc: 3.0, stam: 26, heavy: true },
    frost:  { wind: .62, act: .06, rec: .34, mana: 22 },
    snare:  { wind: .48, act: .05, rec: .42, mana: 14 },
    volley: { wind: .7,  act: .05, rec: .5,  mana: 20 },
    heal:   { wind: 1.2, act: .06, rec: .3,  mana: 30 },
    storm:  { wind: .5,  act: .06, rec: .36, mana: 26 },
    bash:   { wind: .3,  act: .1,  rec: .3,  dmg: [4, 7],   range: 2.3, arc: 1.7, stam: 8, bash: true },
    slam:   { wind: .72, act: .18, rec: .52, dmg: [24, 36], range: 5.4, arc: 6.3, stam: 0, heavy: true },
    chop:   { wind: .24, act: .12, rec: .3,  stam: 4 },
    shot:   { wind: .06, act: .04, rec: .30 },
    rapid:  { wind: .12, act: .62, rec: .26, stam: 14 }
  },

  // ---- safe ground --------------------------------------------------------
  // Nothing picks a fight inside these, and anything dragged in breaks off.
  SAFE: [
    { x: 0, z: 0, r: 26, follows: 'town' },   // Hollowrest / Northreach, centre filled in from the live town position
    { x: 41, z: 31, r: 15 }                   // starting camp
  ],
  LEASH_R: 46,           // dragged this far from home, a monster gives up
  DEAGGRO_R: 32,         // lose interest past this
  RESPAWN_MS: 120000,
  RESPAWN_BOSS_MS: 150000,

  // ---- loot ---------------------------------------------------------------
  // Pure data so the game and the server roll the same table. qty may be a
  // number or a [min,max] inclusive range.
  LOOT: {
    gold: { king: 900, captain: 280, wraith: 75, bandit: 48, wolf: 24, deer: 9, rat: 130, goblin: 6, other: 32 },
    // first matching rule wins, mirroring the original if/else chain exactly
    extra: [
      { tag: 'wolf',  items: [{ item: 'WOLF PELT', qty: 1 }] },
      { tag: 'deer',  items: [{ item: 'DEER HIDE', qty: 1 }, { item: 'VENISON', qty: [1, 2] }] },
      { tag: 'king',  items: [{ item: 'HOLLOW PLATE', qty: 1 }, { item: 'HOLLOW AMULET', qty: 1 }] },
      { tag: 'rat',   items: [{ item: 'RAT TAIL', qty: 1 }] },
      { notTags: ['goblin', 'bandit', 'wraith', 'captain'], items: [{ item: 'TESLA PAYCHECK', qty: 1 }] }
    ]
  },

  // ---- sacks --------------------------------------------------------------
  SACK_OWN_MS: 60000,    // killer's exclusive claim
  SACK_LIFE_MS: 240000,  // then public, then gone
  SACK_CAP: 40,

  // ---- boss scripts -------------------------------------------------------
  // A boss is an archetype plus a script the server interprets. Phases switch
  // on health, each phase has its own move list, and a move describes its own
  // cooldown, the distance band it wants, and what it does. A bigger, meaner
  // boss is a longer table here, not new engine code.
  SCRIPTS: {
    sailers: {
      phases: [
        { untilHpPct: 45, moves: ['charge', 'taunt', 'volley', 'snare'] },
        { untilHpPct: 0,  moves: ['volley', 'volley', 'charge', 'snare'], spdMul: 1.12, dmgMul: 1.15,
          onEnter: { shout: "YOU'LL PAY FOR THAT RIVET!" } }
      ],
      moves: {
        charge: { cd: [6, 10], band: [7, 26], state: 'charge', dur: 1.1 },
        taunt:  { cd: [7, 11], band: [0, 30], state: 'taunt',  dur: 2.1, shout: "WHERE'S THE RIVET?!" },
        volley: { cd: [6, 10], band: [4, 24], move: 'volley', proj: { kind: 'snare', n: 3, spread: 0.24, speed: 15, dmg: 8 } },
        snare:  { cd: [2, 4],  band: [0, 16], move: 'snare',  proj: { kind: 'snare', n: 1, spread: 0, speed: 15, dmg: 8 } }
      }
    },
    hollowKing: {
      phases: [
        { untilHpPct: 60, moves: ['slam', 'leap', 'melee'] },
        { untilHpPct: 25, moves: ['slam', 'leap', 'leap', 'melee'], spdMul: 1.15,
          onEnter: { shout: 'THE HOLLOW STIRS' } },
        { untilHpPct: 0,  moves: ['slam', 'slam', 'leap', 'melee'], spdMul: 1.25, dmgMul: 1.2,
          onEnter: { shout: 'THE CROWN BURNS' } }
      ],
      moves: {
        slam:  { cd: [5, 8],  band: [0, 6.2],  move: 'slam' },
        leap:  { cd: [4, 7],  band: [5, 15],   state: 'leap', dur: 0.9, lunge: 14 },
        melee: { cd: [1, 2],  band: [0, 3.9],  move: 'gheavy' }
      }
    },
    brawler: {
      phases: [ { untilHpPct: 0, moves: ['leap', 'bash', 'flourish', 'melee'] } ],
      moves: {
        leap:     { cd: [4, 7], band: [3.4, 8.5], state: 'leap', dur: 0.8, lunge: 11 },
        bash:     { cd: [4, 7], band: [0, 2.6],   move: 'bash' },
        flourish: { cd: [6, 9], band: [9, 30],    state: 'flourish', dur: 1.2 },
        melee:    { cd: [1, 2], band: [0, 3.0],   move: 'light' }
      }
    },
    plagueRat: {
      phases: [
        { untilHpPct: 50, moves: ['pounce', 'melee'] },
        { untilHpPct: 0,  moves: ['pounce', 'spit', 'melee'], spdMul: 1.2,
          onEnter: { shout: 'THE MERE SEETHES' } }
      ],
      moves: {
        pounce: { cd: [4, 7], band: [4, 14],  state: 'leap', dur: 0.85, lunge: 13 },
        spit:   { cd: [5, 8], band: [3, 20],  move: 'frost', proj: { kind: 'toxin', n: 2, spread: 0.3, speed: 13, dmg: 10 } },
        melee:  { cd: [1, 2], band: [0, 3.4], move: 'heavy' }
      }
    }
  },

  // ---- networking ---------------------------------------------------------
  SIM_HZ: 10,            // server simulation timestep
  SNAP_HZ: 10,           // snapshot rate for any monster that is moving
  SNAP_IDLE_HZ: 2,       // snapshot rate for monsters genuinely standing still
  INTEREST_R: 60,        // a player is only told about monsters this close
  CLOCK_SAMPLES: 8       // rolling median window for server-time offset
};

// Roll a loot table entry set. Both sides call this with the same tag object.
// `rnd` is injected so the server can use a seeded generator and the client can
// use Math.random without either importing the other's plumbing.
function grimRollLoot(tag, rnd) {
  tag = tag || {};
  rnd = rnd || Math.random;
  const G = GRIM_RULES.LOOT.gold;
  const gold = tag.king ? G.king : tag.captain ? G.captain : tag.wraith ? G.wraith
             : tag.bandit ? G.bandit : tag.wolf ? G.wolf : tag.deer ? G.deer
             : tag.rat ? G.rat : tag.goblin ? G.goblin : G.other;
  const out = [{ item: 'GOLD CROWNS', qty: gold }];
  for (const rule of GRIM_RULES.LOOT.extra) {
    let match;
    if (rule.tag) match = !!tag[rule.tag];
    else match = !rule.notTags.some(t => tag[t]);
    if (!match) continue;
    for (const it of rule.items) {
      const q = Array.isArray(it.qty) ? it.qty[0] + Math.floor(rnd() * (it.qty[1] - it.qty[0] + 1)) : it.qty;
      out.push({ item: it.item, qty: q });
    }
    break;                                   // first match only, like the original
  }
  return out;
}

// Stable order-independent-ish fingerprint of the world manifest. Both sides
// compute it the same way, so a mismatch is detected on join instead of
// showing up later as a monster standing inside a wall.
function grimHash(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h.toString(36);
}
