/**
 * Grim World relay.
 *
 * One Durable Object per world. Every player holds a WebSocket to it, so there
 * is no peer to peer connection anywhere in the system.
 *
 * State lives on the sockets, not in this object's memory. A Durable Object can
 * be evicted or hibernated at any moment; anything held in a field would be
 * silently lost. Each socket's attachment carries {id, name, color, joined,
 * seen, bg, owner} and is the only source of truth, so a restart is invisible.
 *
 * SIMULATION OWNERSHIP (v3): exactly one player runs monsters. The flag lives
 * on that player's socket attachment. Three things move it, all announced with
 * a 'sim' broadcast so no two clients can ever disagree:
 *   - the owner disconnects: oldest remaining player takes over
 *   - the owner's tab goes hidden and sends 'yield': the most recently active
 *     VISIBLE player takes over (a hidden Chrome tab freezes the simulation -
 *     monsters stop animating, stop fighting, and never process deaths - so a
 *     hidden owner is a frozen world for everyone)
 *   - the owner goes silent for 8s while others keep talking: same handover,
 *     for tabs that froze without managing to say anything
 */

import { mulberry32, makeSimNpc, stepNpc, separate } from './sim.js';

const PROTO = 7;
const RATE_LIMIT = 60;              // msgs/sec per player; the game sends ~20
const OWNER_STALE_MS = 8000;
// Tier 2 item #5: how long a dirty (unsaved) world can sit in memory before
// a debounced flush is forced. Cloudflare's own lifecycle docs put the
// hibernation threshold at "10 seconds of no incoming request or event",
// and hibernating discards whatever this.mem holds that was never written
// with storage.put(). 2000ms gives a comfortable 5x margin under that 10s
// line even accounting for scheduling jitter, while still cutting a rapid
// hit/loot burst down from one storage write per event to about one every
// two seconds. See PROJECT-MEMORY.md / TIER2-NETWORKING-EDITOR-PLAN.md
// item #5 for why this one shipped alone with extra scrutiny.
const SAVE_DEBOUNCE_MS = 2000;

// Messages the relay forwards. Anything else is dropped.
// ptyi/ptya/ptyd/ptyl/ptyk are listed for documentation even though they are
// intercepted and handled before this set is ever consulted (same as
// manifest/nreg/nhit/lreq/lall below) -- ptyu is deliberately NOT here: it is
// server-authored only (like ndead/skupd), so a client sending one is simply
// dropped by the generic RELAYED gate, no special-case exclusion needed.
// 'pproj' (patch 80.142): a player's own cast, mirrored cosmetically to
// everyone else in the world/PvP so an opponent's fireball or frost bolt is
// visible in flight, not just felt on impact. Plain broadcast, no ownership
// check needed - unlike 'w'/'ndead'/etc it isn't world truth, just a visual
// courtesy each client already trusts only for rendering (real damage still
// only ever arrives via 'hit'/'nhit'). Not to be confused with the server's
// own unrelated 'proj' (NPC casts, server to client only, never in this set).
const RELAYED = new Set(['s', 'w', 'nhit', 'ndead', 'rhit', 'rdead', 'phit', 'pvp', 'pvpk', 'lreq', 'lok', 'lno', 'skupd', 'sknew', 'skgone', 'chat', 'ptyi', 'ptya', 'ptyd', 'ptyl', 'ptyk', 'pproj']);
const PARTY_CAP = 5;
// Only the simulation owner may speak world truth.
const OWNER_ONLY = new Set(['w', 'ndead', 'rdead', 'phit', 'lok', 'lno', 'skupd', 'sknew', 'skgone']);
// Claims the owner alone needs to see (movement-only traffic).
const TO_OWNER = new Set(['rhit']);

// ---------------------------------------------------------------------------
// SERVER-AUTHORITATIVE COMBAT (v5)
//
// Monster health, death, respawn, kill credit and every loot sack now live
// here, not in a player's browser. A frozen or slow tab can no longer stop a
// monster taking damage, dying, or dropping anything, and no client can grant
// itself loot. Players still draw monster movement locally; only the facts
// that matter are decided here.
//
// State is persisted, because a Durable Object hibernates while sockets stay
// open and anything held only in memory would silently vanish mid-fight.
// ---------------------------------------------------------------------------

/* SHARED-RULES-BEGIN */
const GRIM_RULES = {
  V: 1,
  // World generation number. Part of the world manifest: when it goes up, the
  // relay REPLACES its stored manifest even with players online, so a new
  // world ships without the old one squatting the server. Bump it whenever
  // the terrain bake or manifest layout changes.
  WORLD_GEN: 7,   // bumped: the world manifest layout changed (monsters now
                  // carry species, signature and kin tags to the server), and
                  // the relay only replaces a stored manifest when this rises

  // ---- world bounds -------------------------------------------------------
  WORLD_R: 4800,         // Asterra chart radius: covers the whole baked map;
                         // real bounds are the coastline + deep water + chart
                         // edge, enforced by GRIM_WORLD.walkable on the client
  ARENA_R: 23,           // legacy duel arena

  // ---- movement -----------------------------------------------------------
  SPEED: 5.6,
  SPRINT: 8.4,
  DIFF: { squire: 0.62, veteran: 1.0, champion: 1.42 },

  // ---- the vertical layer (phase 1d) --------------------------------------
  // Every behaviour here has its own switch so any one can be turned off in
  // production without reverting the others. ELEV is the master: with it off
  // the player is glued to the ground exactly as the game always was.
  VERT: {
    ELEV: true,       // the player carries a real elevation (falling exists)
    GRAVITY: 26,      // m/s^2
    TERMINAL: 36,     // max fall speed; a long drop cannot tunnel a surface
    STEP: 0.55,       // walk over anything shorter than this without jumping
    SLOPE_FOLLOW: 2.2,// how steep a downslope the feet follow before it is a
                      // fall: drop per frame up to travel * this (about 65
                      // degrees) reads as ground, more reads as an edge
    JUMP_H: 1.15,     // preserved from the old parametric jump arc
    SLOPE_MAX: 0,     // climb limit in degrees; 0 = off until 1g's sweep
    FALL_DMG: 0,      // hp per m/s over FALL_SAFE; 0 = wired but off
    FALL_SAFE: 12,    // landing speed below which falling never hurts
  },

  // ---- the world editor (phases 3 to 6) -----------------------------------
  // The editor is the real game engine with an editor flag, so what Kevin
  // sees IS what players get. Nothing here ships any behaviour to a player
  // except LAYER, which is the authored edit layer the game fetches at boot.
  // With LAYER off the world is exactly the generated one, which is the
  // revert switch for the entire project.
  EDIT: {
    LAYER: true,      // fetch and apply the authored edit layer at boot
    UI: true,         // ?edit=1 can open the editor at all (master kill switch)
    CELL: 4,          // terrain sculpt grid size in metres (height only)
    PCELL: 1,         // ground paint grid size in metres. Finer than CELL on
                      // purpose: a brush and a blend width only mean anything
                      // small if the underlying cells are small too.
    // Patch 83.200: was 2m, exactly equal to the near-field terrain mesh's
    // 2m vertex spacing (64m chunks / 32 segments), so the blend band was
    // only ever wide enough to interpolate smoothly along a boundary that
    // happened to run with the grid, and jumped hard everywhere else. 5m
    // gives 2.5x that spacing, comfortably wide in every direction rather
    // than exactly one vertex wide in the best case.
    BLEND_DEFAULT: 5, // default paint/road edge softness, in metres
    BLEND_MAX: 6,     // clamp on the per-layer blend value, so a huge blend
                      // cannot make groundSurface scan an unreasonable
                      // neighbourhood on every vertex. Raised from 4: ground
                      // blending is dithered now instead of averaging colour
                      // (see the ground shader), so a wide soft blend no
                      // longer means a wide band of washed-out colour, and
                      // is worth letting Kevin dial in from the tool.
    SNAP: 0.5,        // object placement snap in metres; Alt places free
    FEATHER: 1,       // legacy, unused now that paint carries its own blend
    MAXH: 12,         // biggest terrain delta the sculpt tools may author (m)
    FLATMIN: 0.06,    // never flatten perfectly level: the walk-out-of-water
                      // routine marches things to the world origin on dead
                      // flat ground, so flatten always leaves this much tilt
    URL: 'https://grim-arena.kevin-230.workers.dev/world/main/edits',
  },

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
    // Tools and bare hands. The shape used to be written inline in the client
    // ("if the move is a chop, hit for 6-10 over 2.8m"), so when the fight moved
    // to the server it was left behind: the server read this table, found no
    // reach and no damage, and sent out swings that could never land and never
    // showed a hit splat. Jim, Pete and anyone else on a tool were harmless.
    chop:   { wind: .24, act: .12, rec: .3,  dmg: [6, 10],  range: 2.8, arc: 2.0, stam: 4 },
    // Beasts. A paw slash is the one-handed quick swing and a bite is the
    // committed one, the same light/heavy pairing that makes a goblin fun to
    // fight, with no shield in the other hand so nothing on a claw ever blocks.
    claw:   { wind: .26, act: .12, rec: .26, dmg: [12, 18], range: 2.8, arc: 2.0, stam: 5 },
    bite:   { wind: .44, act: .14, rec: .38, dmg: [20, 28], range: 3.0, arc: 2.2, stam: 12, heavy: true },
    shot:   { wind: .06, act: .04, rec: .30 },
    rapid:  { wind: .12, act: .62, rec: .26, stam: 14 },
    // The landing of a leap or a pounce. Same story as chop above: the shape
    // used to be written inline in the client ("at 0.7 through the hop, hit for
    // 14-20 over 2.6m"), and when the fight moved to the server that line
    // stopped running for monsters. The result was that the Hollow King's leap,
    // the Plague Rat's pounce and the Bandit Captain's leap all became pure
    // theatre: they crossed the ground at you and did nothing at all. These are
    // the original authored numbers, moved somewhere both sides can read them.
    // land is the fraction of the move's duration at which the boss touches
    // down, so a longer hop lands later without needing its own table.
    leap:   { land: .78, dmg: [14, 20], range: 2.6, arc: 2.8, heavy: true },
    // The Argent Warden. A thing three times a man's height cannot fight with a
    // man's reach: gheavy tops out at 3.9m, which on a model this size lands
    // somewhere inside its own chest. These are the same wind/act/rec grammar
    // as every other move, just scaled to the arm that swings them.
    maul:   { wind: .42, act: .16, rec: .36, dmg: [24, 32], range: 5.2, arc: 2.6, stam: 0 },
    hammer: { wind: .74, act: .20, rec: .56, dmg: [44, 58], range: 5.6, arc: 2.9, stam: 0, heavy: true },
    sunder: { wind: .88, act: .22, rec: .62, dmg: [34, 48], range: 8.0, arc: 6.3, stam: 0, heavy: true },
    // ---- signature move shapes ---------------------------------------------
    // These live in MOVES, not only in SIGS below, because the server does not
    // apply damage: it ANNOUNCES a swing by name and every client judges its own
    // dodge against the shape it finds under that name. A signature that existed
    // only as bespoke client code could never be thrown by a server-run monster.
    // SIGS points at these by name, so there is one set of numbers for both.
    whip:   { wind: .45, act: .10, rec: .40, dmg: [7, 11],  range: 3.2, arc: 6.283, stam: 0, knock: 7 },
    tusk:   { wind: .90, act: .12, rec: .50, dmg: [14, 20], range: 2.4, arc: 2.2,   stam: 0, heavy: true, knock: 9 }
  },

  // ---- safe ground --------------------------------------------------------
  // Nothing picks a fight inside these, and anything dragged in breaks off.
  SAFE: [
    { x: 0, z: 0, r: 26, follows: 'town' },   // Hollowrest / Northreach, centre filled in from the live town position
    { x: 41, z: 31, r: 15 }                   // starting camp
  ],
  LEASH_R: 46,           // hard ceiling: nothing chases further than this, ever
  DEAGGRO_R: 32,         // lose interest past this

  // ---- leashing -----------------------------------------------------------
  // How a monster lets go and goes home. This used to be a single distance
  // check with no state behind it, which meant a monster held at leash range
  // dropped aggro and re-acquired the player on alternating frames: it shook
  // on the spot and retriggered its aggro sound sixty times a second.
  //
  // The shape here is the one RuneScape and WoW both use, for the same reason:
  // breaking off has to be a STATE with a destination, not a distance test.
  // While returning, a monster cannot be re-aggroed at all, walks home a little
  // faster than it wanders, and heals on arrival so it cannot be ground down by
  // pulling it to the edge of its ground over and over.
  LEASH: {
    CHASE_EXTRA: 18,     // how far past its own roam radius a monster will follow
    RETURN_SPEED: 2.4,   // multiplier on wander pace while walking home. A monster
                         // that has given up should look like it is LEAVING, and it
                         // should clear the area fast enough that you stop tracking it.
    HOME_TOL: 3.2,       // close enough to count as home
    HEAL_ON_RETURN: true,
    MIN_AGGRO_GAP: 1.2   // seconds before the aggro sound can play again
  },
  RESPAWN_MS: 120000,
  RESPAWN_BOSS_MS: 150000,
  // An Argent Anchor re-forges itself far faster than anything else in the
  // world dies and returns. That number IS the two-player requirement: alone
  // you cannot break the second one before the first is standing again.
  RESPAWN_ANCHOR_MS: 26000,

  // Roam radius by role, for everything that predates the bestiary table. A
  // monster wanders inside this and chases CHASE_EXTRA beyond it, which is what
  // makes a camp of goblins feel like it guards a spot while a boar feels like
  // it owns a field.
  ROAM_R: {
    civilian: 6,     // townsfolk keep to their patch
    worker: 8,
    camp: 14,        // humanoids clustered on a landmark
    beast: 24,       // roaming animals
    wildlife: 20,
    boss: 18,        // bosses hold their lair
    def: 16
  },

  // ---- loot ---------------------------------------------------------------
  // Pure data so the game and the server roll the same table. qty may be a
  // number or a [min,max] inclusive range.
  LOOT: {
    gold: { warden: 1400, king: 900, captain: 280, wraith: 75, bandit: 48, wolf: 24, deer: 9, rat: 130, goblin: 6, other: 32 },
    // first matching rule wins, mirroring the original if/else chain exactly
    extra: [
      { tag: 'wolf',  items: [{ item: 'WOLF PELT', qty: 1 }] },
      { tag: 'deer',  items: [{ item: 'DEER HIDE', qty: 1 }, { item: 'VENISON', qty: [1, 2] }] },
      { tag: 'warden', items: [{ item: "WARDEN'S BULWARK", qty: 1 }] },
      { tag: 'anchor', items: [] },
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
    // Mr. Sailers, the caster. Three spells and two bits of theatre, and the
    // rule is that he should almost always be casting SOMETHING. The old table
    // opened on a taunt that stood him still for 2.1s and put every real spell
    // on a 6-11 second cooldown, so a fight began with him doing nothing for
    // several seconds and then a lone bolt. Bolt is now the backbone at under
    // two seconds; the taunt is short and rare.
    sailers: {
      phases: [
        { untilHpPct: 50, moves: ['bolt', 'bolt', 'snare', 'volley', 'charge'] },
        { untilHpPct: 0,  moves: ['bolt', 'volley', 'volley', 'snare', 'charge', 'taunt'], spdMul: 1.12, dmgMul: 1.15,
          onEnter: { shout: "YOU'LL PAY FOR THAT RIVET!" } }
      ],
      moves: {
        bolt:   { cd: [1.4, 2.2],  band: [2, 22], move: 'frost',  proj: { kind: 'frost', n: 1, spread: 0,    speed: 19, dmg: 12 } },
        volley: { cd: [4.5, 7],    band: [5, 24], move: 'volley', proj: { kind: 'snare', n: 3, spread: 0.22, speed: 16, dmg: 9 } },
        snare:  { cd: [5, 8],      band: [0, 18], move: 'snare',  proj: { kind: 'snare', n: 1, spread: 0,    speed: 17, dmg: 8 } },
        charge: { cd: [7, 11],     band: [9, 26], state: 'charge', dur: 1.0 },
        taunt:  { cd: [11, 16],    band: [0, 30], state: 'taunt',  dur: 1.2, shout: "WHERE'S THE RIVET?!" }
      }
    },
    // The Hollow King. A greatsword, so the pairing is a fast cleave and a
    // committed overhead, the same quick/heavy split every other fight in the
    // world now uses. His single melee move used to sit on a one to two second
    // cooldown behind a 1.3s animation, which left him swinging roughly once
    // every three seconds and falling back on ordinary filler swings between.
    // The ground slam is the thing you must actually read and dodge, so it
    // stays his signature and comes more often the angrier he gets.
    hollowKing: {
      phases: [
        { untilHpPct: 60, moves: ['cleave', 'cleave', 'crush', 'slam', 'leap'] },
        { untilHpPct: 25, moves: ['cleave', 'crush', 'slam', 'leap', 'leap'], spdMul: 1.15,
          onEnter: { shout: 'THE HOLLOW STIRS' } },
        { untilHpPct: 0,  moves: ['cleave', 'crush', 'slam', 'slam', 'leap'], spdMul: 1.25, dmgMul: 1.2,
          onEnter: { shout: 'THE CROWN BURNS' } }
      ],
      moves: {
        cleave: { cd: [0.6, 1.1], band: [0, 3.6],  move: 'glight' },
        crush:  { cd: [3, 5],     band: [0, 3.9],  move: 'gheavy' },
        slam:   { cd: [4.5, 7],   band: [0, 5.2],  move: 'slam' },
        leap:   { cd: [4, 7],     band: [5, 15],   state: 'leap', dur: 0.9, lunge: 14, hit: 'leap' }
      }
    },
    // The Bandit Captain. Leaps and shield bashes are what make him read as a
    // captain rather than a big bandit, so they stay. The flourish does not:
    // it was a psych-up the client played while closing the distance, and once
    // the server owned the fight it became 1.2 seconds of standing still at
    // range. His melee now swings on the same cadence as a goblin's instead of
    // once or twice a second.
    brawler: {
      phases: [ { untilHpPct: 0, moves: ['leap', 'bash', 'melee'] } ],
      moves: {
        leap:     { cd: [5, 8],    band: [3.4, 8.5], state: 'leap', dur: 0.8, lunge: 11, hit: 'leap' },
        bash:     { cd: [5, 8],    band: [0, 2.6],   move: 'bash' },
        melee:    { cd: [0.5, 1],  band: [0, 3.0],   move: 'light' }
      }
    },
    // THE ARGENT WARDEN. A siege golem the capital built and then lost control
    // of, standing derelict in the northern Heartlands.
    //
    // The fight is a two-player fight by construction rather than by having a
    // big health bar. While either of its Argent Anchors still stands the
    // Warden pulls the field back into itself and regenerates, and an anchor
    // re-forges 26 seconds after it falls. One player can comfortably break an
    // anchor; what one player cannot do is break the SECOND one before the
    // first is back up, so the regen never stops and the health bar never
    // really moves. Two players split the field, both anchors go down inside
    // the same window, the drain stops, and the Warden is mortal.
    //
    // Nothing about this is a locked door: a player fast enough to break both
    // alone inside 26 seconds has earned it.
    argentWarden: {
      anchors: 'ARGENT ANCHOR',
      regen: 70,                    // hp per second while ANY anchor stands
      phases: [
        { untilHpPct: 55, moves: ['maul', 'maul', 'hammer', 'sunder', 'lance'] },
        { untilHpPct: 0,  moves: ['maul', 'hammer', 'sunder', 'sunder', 'lance', 'vault'],
          spdMul: 1.22, dmgMul: 1.18,
          onEnter: { shout: 'THE BANDS ARE BROKEN' } }
      ],
      moves: {
        maul:   { cd: [0.7, 1.2], band: [0, 5.4],  move: 'maul' },
        hammer: { cd: [3.5, 5.5], band: [0, 5.6],  move: 'hammer' },
        sunder: { cd: [4.5, 7],   band: [0, 7.8],  move: 'sunder' },
        // the ranged answer: standing at fifteen metres plinking is not a plan
        lance:  { cd: [3.5, 6],   band: [6, 32],   move: 'volley',
                  proj: { kind: 'frost', n: 5, spread: 0.26, speed: 17, dmg: 16 } },
        vault:  { cd: [5, 8],     band: [7, 22],   state: 'leap', dur: 0.95, lunge: 16, hit: 'leap' }
      }
    },
    // The Plague Rat. A beast, so it fights with the same claw and bite as a
    // dire wolf rather than swinging a sword it does not have. Its toxin is the
    // whole point of the fight, so the spit is available from the first phase
    // instead of only appearing below half health.
    plagueRat: {
      phases: [
        { untilHpPct: 50, moves: ['slash', 'slash', 'maul', 'pounce', 'spit'] },
        { untilHpPct: 0,  moves: ['slash', 'spit', 'maul', 'pounce', 'spit'], spdMul: 1.2,
          onEnter: { shout: 'THE MERE SEETHES' } }
      ],
      moves: {
        slash:  { cd: [0.6, 1.1], band: [0, 2.8], move: 'claw' },
        maul:   { cd: [3, 5],     band: [0, 3.0], move: 'bite' },
        pounce: { cd: [5, 8],     band: [4, 14],  state: 'leap', dur: 0.85, lunge: 13, hit: 'leap' },
        // band starts at zero on purpose: the rat fights with its face in
        // yours, so a spit gated at three metres out simply never happened
        spit:   { cd: [4, 7],     band: [0, 20],  move: 'frost', proj: { kind: 'toxin', n: 2, spread: 0.3, speed: 14, dmg: 11 } }
      }
    }
  },

  // ---- networking ---------------------------------------------------------
  SIM_HZ: 10,            // server simulation timestep
  SNAP_HZ: 10,           // snapshot rate for any monster that is moving
  SNAP_IDLE_HZ: 2,       // snapshot rate for monsters genuinely standing still
  INTEREST_R: 60,        // a player is only told about monsters this close
  CLOCK_SAMPLES: 8,      // rolling median window for server-time offset

  // ---- zones --------------------------------------------------------------
  // The terrain bake stores a zone id per grid cell and GRIM_WORLD.zone(x, z)
  // reads it. That id is a TERRAIN label, not a design zone: the bake splits
  // Ember into two altitude bands and carries an EASTRIDGE the design plan
  // never names. This table is the one place the two vocabularies meet, so
  // dressing, spawn tables and node tables all key off design zones and the
  // bake stays free to resplit terrain without touching content.
  //
  // Index matches WG_ZONES in worldgen-data.js exactly. Do not reorder.
  //   0 SEA  1 FROSTWILD  2 IRONSPIRE  3 HEARTLANDS  4 GREENWOOD  5 SUNCOAST
  //   6 WINDSCAR  7 EMBER  8 EMBER_HI  9 MISTFEN  10 SUNSCORCH  11 EASTRIDGE
  //   12 ISLES
  ZONE_OF_BAKE: ['SEA', 'FROSTWILD', 'IRONSPIRE', 'HEARTLANDS', 'GREENWOOD', 'SUNCOAST',
                 'WINDSCAR', 'EMBER', 'EMBER', 'MISTFEN', 'SUNSCORCH', 'EASTRIDGE', 'ISLES'],
  // EMBER_HI (bake 8) is the volcanic core: same design zone as EMBER, but it
  // is the only ground that rolls the deep Ember nodes. Flagged here rather
  // than with a second zone name so nothing downstream has to special-case it.
  ZONE_DEEP_BAKE: { 8: 'EMBER' },

  ZONES: {
    SEA:        { name: 'Open Water',        cont: '-',        band: [0, 0],   dress: false },
    HEARTLANDS: { name: 'Heartlands',        cont: 'Valewold', band: [1, 5] },
    GREENWOOD:  { name: 'Greenwood Marches', cont: 'Valewold', band: [4, 9] },
    FROSTWILD:  { name: 'Frostwild North',   cont: 'Valewold', band: [8, 14] },
    IRONSPIRE:  { name: 'Ironspire Mountains', cont: 'Valewold', band: [10, 16] },
    SUNCOAST:   { name: 'Sun Coast',         cont: 'Valewold', band: [6, 12] },
    WINDSCAR:   { name: 'Windscar Steppe',   cont: 'Ashmar',   band: [12, 18] },
    EMBER:      { name: 'Ember Highlands',   cont: 'Ashmar',   band: [16, 22] },
    MISTFEN:    { name: 'Mistfen Wetlands',  cont: 'Ashmar',   band: [14, 20] },
    SUNSCORCH:  { name: 'Sunscorch Barrens', cont: 'Ashmar',   band: [18, 24] },
    // Not in the design plan, but it is in the bake and players can walk on
    // it, so it gets a set rather than staying bald. Rocky highland dressing
    // with LOOSE STONE only: iron and coal stay Ironspire-exclusive, which is
    // canon, so this ridge is scenery and stone, never a second ore country.
    EASTRIDGE:  { name: 'Eastridge',         cont: 'Ashmar',   band: [12, 18] },
    ISLES:      { name: 'Shattered Isles',   cont: 'Ashmar',   band: [10, 16] }
  },

  // ---- bestiary -----------------------------------------------------------
  // Who lives where. Pure data so the client and any future server sim spawn
  // the same roster, and so adding a species to a zone is a table row.
  //
  // pattern: 'roamer' wanders a home radius, 'camp' clusters around a landmark.
  // sig names the signature move; the move itself is implemented once and
  // switched on by name, so a species never gets a reskinned basic attack.
  BESTIARY: {
    BOAR:      { name: 'WILD BOAR',   rig: 'quad', profile: 'boar', hp: 45, xp: 50, band: [1, 5], roamR: 26,
                 sig: 'TUSK CHARGE', dmgScale: 0.5, spdScale: 1.0, aggroR: 9, aiD: 0.55,
                 loot: ['BOAR HIDE', 'RAW MEAT'], tags: { boar: true } },
    GIANT_RAT: { name: 'GIANT RAT',   rig: 'quad', profile: 'rat',  hp: 26, xp: 29, band: [1, 4], roamR: 12,
                 sig: 'TAIL WHIP', dmgScale: 0.4, spdScale: 1.12, aggroR: 10, aiD: 0.6,
                 loot: ['RAT TAIL'], tags: { rat: true } },
    YOUNG_GOBLIN: { name: 'YOUNG GOBLIN', rig: 'goblin', hp: 30, xp: 33, band: [1, 5], roamR: 14,
                 sig: 'GOBLIN SHRIEK', dmgScale: 0.45, spdScale: 0.95, aggroR: 11, aiD: 0.55,
                 loot: ['GOBLIN EAR'], tags: { goblin: true } },
    HARE:      { name: 'HARE',        rig: 'quad', profile: 'hare', hp: 8,  xp: 4, band: [1, 1], roamR: 20,
                 passive: true, skittish: true, spdScale: 1.45, aggroR: -1, dmgScale: 0,
                 loot: [], tags: {} }
  },

  // Signature moves. wind is the telegraph the player reads, act is when it
  // lands, and the rest is the move's own shape. These sit alongside MOVES
  // rather than inside it because they are not swings: they are events.
  // `move` names the MOVES entry that carries the contact shape, so the damage
  // numbers exist exactly once and cannot drift between the client and the
  // server. Everything here is about how the move is PERFORMED rather than what
  // it does on contact: how long the run lasts, how far the shriek carries.
  SIGS: {
    'TUSK CHARGE':   { move: 'tusk', cd: [7, 11],  band: [5, 12],  wind: 0.9,  dur: 1.1, speed: 15, kind: 'charge' },
    'TAIL WHIP':     { move: 'whip', cd: [5, 8],   band: [0, 3.0], wind: 0.45, dur: 0.5, kind: 'sweep' },
    'GOBLIN SHRIEK': {               cd: [12, 18], band: [0, 14],  wind: 0.55, dur: 0.8, kind: 'call', callR: 25, tag: 'goblin' }
  },

  // Deterministic zone rosters. count is the cap for that species in that zone;
  // the spawn points come from the same seeded generator the dressing uses, so
  // two players see the same boar in the same field.
  ZONE_SPAWNS: {
    // The design plan's roster, at full count. This was trimmed to 25 head to
    // stay under a 7,000 mesh budget that turned out not to measure anything
    // real: posing 31 quadrupeds costs 0.121ms a frame, and mesh count is not
    // what the renderer charges for. Content is not cut for a proxy again.
    // If a machine does struggle, GRAPHICS: LOW thins the world (see
    // GFX_SCALE below) rather than the world being thin for everybody.
    HEARTLANDS: [
      { of: 'BOAR', count: 6, pattern: 'roamer' },
      { of: 'GIANT_RAT', count: 10, pattern: 'camp', group: [2, 4] },
      { of: 'YOUNG_GOBLIN', count: 9, pattern: 'camp', group: [3, 5] },
      { of: 'HARE', count: 7, pattern: 'roamer' }
    ]
  },
  ZONE_MONSTER_CAP: { HEARTLANDS: 30 },

  // The graphics setting is the lever for a machine that cannot keep up. It
  // already turns shadows and extra lights off; it now also thins the world,
  // which is the honest place to give ground because it costs the player
  // scenery rather than costing them monsters or reach.
  GFX_SCALE: {
    high: { clutter: 1.0, dressRing: 2 },
    low:  { clutter: 0.45, dressRing: 1 }
  },

  // Adjustable draw distance (patch 78.104+, see that patch's docstring for
  // the full rationale). Scales camera far, fog near/far, and the terrain
  // detail/coarse/prop-dressing chunk rings together. normal = live today.
  VIEW_DIST: {
    near:   { mult: 0.72, label: 'NEAR' },
    normal: { mult: 1.0,  label: 'NORMAL' },
    far:    { mult: 1.35, label: 'FAR' }
  },

  // ---- gathering ----------------------------------------------------------
  // Three skills, one curve, tiered nodes, tiered tools. A node needs BOTH a
  // skill level and a tool tier; the trade economy is the tool ladder, because
  // no single zone's ground can build the top tiers.
  GATHER: {
    SKILLS: ['WOODCUTTING', 'MINING', 'FORAGING'],
    MAX_LEVEL: 99,
    // XP to advance from level n to n+1. Total to 99 is about 2.84M.
    XP_BASE: 75,
    XP_RATE: 1.085,
    // Every tier gathers 15 percent faster than the one below it.
    TOOL_SPEED: 1.15,
    // Tier 3 reuses IRON AXE and IRON PICKAXE, which already ship as items, so
    // a veteran's existing tools become tier 3 rather than being renamed out
    // from under them. New characters are granted the crude pair instead of
    // the iron pair, which is the "everyone logs in with these" line in the
    // plan. Foraging tier 1 is bare hands, so it has no item.
    TOOLS: [
      { tier: 1, name: 'CRUDE',      axe: 'CRUDE AXE',      pick: 'CRUDE PICK',          sickle: null },
      { tier: 2, name: 'BRONZE',     axe: 'BRONZE AXE',     pick: 'BRONZE PICKAXE',      sickle: 'BRONZE SICKLE' },
      { tier: 3, name: 'IRON',       axe: 'IRON AXE',       pick: 'IRON PICKAXE',        sickle: 'IRON SICKLE' },
      { tier: 4, name: 'STEEL',      axe: 'STEEL AXE',      pick: 'STEEL PICKAXE',       sickle: 'STEEL SICKLE' },
      { tier: 5, name: 'OBSIDIAN',   axe: 'OBSIDIAN AXE',   pick: 'OBSIDIAN PICKAXE',    sickle: 'OBSIDIAN SICKLE' },
      { tier: 6, name: 'MASTERWORK', axe: 'MASTERWORK AXE', pick: 'MASTERWORK PICKAXE',  sickle: 'MASTERWORK SICKLE' }
    ],
    TOOL_FOR: { WOODCUTTING: 'axe', MINING: 'pick', FORAGING: 'sickle' },

    // Physical collision radius for a harvestable node, in metres, scaled by
    // the node's own scale factor at build time. Trees and ore used to be
    // walk-through, which read wrong once Kevin started placing them by hand
    // to shape a path or wall off a cave mouth. Foraging nodes (herbs,
    // berries, mushrooms) are small and stay walk-through on purpose.
    NODE_SOLID_R: { WOODCUTTING: 0.5, MINING: 0.7 },

    // Tool tiers are deliberately NOT a straight band off node level. Every
    // tier's recipe needs material that a LOWER tier can already reach, or the
    // ladder eats its own tail: copper ore at level 10 cannot need a copper
    // pick, and obsidian flows cannot need an obsidian pick. Tier 6 gates
    // nothing but the three level-90 rares, which is the point of a prestige
    // tool.
    //
    // hp = swings to harvest, xp = per harvest (node level x 5),
    // respawn = seconds, yield = [item, min, max], deep = interior of the zone
    // only (the rares). zones lists every design zone the node rolls in.
    NODES: {
      // ---- legacy set: the arena and camp resources that already shipped.
      // Their gates and yields are unchanged on purpose. Retuning them would
      // lock existing players out of the smithing quest's iron and out of oaks
      // they can already fell, which is a live-save regression, not content.
      tree:      { skill: 'WOODCUTTING', lvl: 1,  tool: 1, hp: 3,  xp: 15,  respawn: 45,  yield: ['LOGS', 2, 2],        legacy: true },
      oak:       { skill: 'WOODCUTTING', lvl: 5,  tool: 1, hp: 5,  xp: 60,  respawn: 90,  yield: ['OAK LOGS', 3, 3],    legacy: true },
      rock:      { skill: 'MINING',      lvl: 1,  tool: 1, hp: 4,  xp: 20,  respawn: 60,  yield: ['IRON ORE', 2, 2],    legacy: true },

      // ---- woodcutting
      poplar:    { skill: 'WOODCUTTING', lvl: 1,  tool: 1, hp: 3,  xp: 5,   respawn: 45,  yield: ['LOGS', 1, 2],
                   shape: 'poplar',
                   zones: ['HEARTLANDS', 'GREENWOOD', 'SUNCOAST', 'WINDSCAR', 'EASTRIDGE'] },
      zoak:      { skill: 'WOODCUTTING', lvl: 10, tool: 1, hp: 3,  xp: 50,  respawn: 45,  yield: ['OAK LOGS', 1, 2],
                   shape: 'broad',
                   zones: ['HEARTLANDS', 'GREENWOOD'] },
      palm:      { skill: 'WOODCUTTING', lvl: 20, tool: 2, hp: 3,  xp: 100, respawn: 45,  yield: ['PALM LOGS', 1, 2],
                   shape: 'palm',
                   zones: ['SUNCOAST', 'ISLES'] },
      willow:    { skill: 'WOODCUTTING', lvl: 30, tool: 2, hp: 5,  xp: 150, respawn: 45,  yield: ['WILLOW LOGS', 1, 2],
                   shape: 'willow',
                   zones: ['MISTFEN'] },
      bogoak:    { skill: 'WOODCUTTING', lvl: 30, tool: 2, hp: 5,  xp: 150, respawn: 45,  yield: ['BOG OAK LOGS', 1, 2],
                   shape: 'snag',
                   zones: ['MISTFEN'] },
      elder:     { skill: 'WOODCUTTING', lvl: 40, tool: 3, hp: 5,  xp: 200, respawn: 45,  yield: ['ELDER LOGS', 1, 2],
                   shape: 'elder',
                   zones: ['GREENWOOD'] },
      acacia:    { skill: 'WOODCUTTING', lvl: 50, tool: 4, hp: 5,  xp: 250, respawn: 45,  yield: ['ACACIA LOGS', 1, 2],
                   shape: 'acacia',
                   zones: ['WINDSCAR'] },
      icewood:   { skill: 'WOODCUTTING', lvl: 60, tool: 4, hp: 7,  xp: 300, respawn: 45,  yield: ['ICEWOOD', 1, 2],
                   shape: 'pine',
                   zones: ['FROSTWILD'] },
      emberbark: { skill: 'WOODCUTTING', lvl: 75, tool: 5, hp: 7,  xp: 375, respawn: 45,  yield: ['EMBERBARK', 1, 2],
                   shape: 'emberbark',
                   zones: ['EMBER'] },
      elderking: { skill: 'WOODCUTTING', lvl: 90, tool: 6, hp: 10, xp: 450, respawn: 480, yield: ['ANCIENT ELDER LOGS', 1, 2],
                   shape: 'elder',
                   zones: ['GREENWOOD'], deep: true, rare: true },

      // ---- mining
      stone:     { skill: 'MINING', lvl: 1,  tool: 1, hp: 3,  xp: 5,   respawn: 60,  yield: ['LOOSE STONE', 1, 2],
                   zones: ['HEARTLANDS', 'GREENWOOD', 'IRONSPIRE', 'FROSTWILD', 'SUNCOAST', 'WINDSCAR', 'EMBER', 'SUNSCORCH', 'EASTRIDGE', 'ISLES'] },
      copper:    { skill: 'MINING', lvl: 10, tool: 1, hp: 3,  xp: 50,  respawn: 60,  yield: ['COPPER ORE', 1, 2],
                   zones: ['IRONSPIRE'] },
      salt:      { skill: 'MINING', lvl: 20, tool: 2, hp: 3,  xp: 100, respawn: 60,  yield: ['SALT', 1, 2],
                   zones: ['SUNCOAST'] },
      ironore:   { skill: 'MINING', lvl: 30, tool: 2, hp: 5,  xp: 150, respawn: 60,  yield: ['IRON ORE', 1, 2],
                   zones: ['IRONSPIRE'] },
      coal:      { skill: 'MINING', lvl: 40, tool: 3, hp: 5,  xp: 200, respawn: 60,  yield: ['COAL', 1, 2],
                   zones: ['IRONSPIRE'] },
      saltpeter: { skill: 'MINING', lvl: 50, tool: 4, hp: 5,  xp: 250, respawn: 60,  yield: ['SALTPETER', 1, 2],
                   zones: ['WINDSCAR'] },
      glasssand: { skill: 'MINING', lvl: 55, tool: 4, hp: 7,  xp: 275, respawn: 60,  yield: ['GLASS SAND', 1, 2],
                   zones: ['SUNSCORCH'] },
      gold:      { skill: 'MINING', lvl: 65, tool: 4, hp: 7,  xp: 325, respawn: 60,  yield: ['GOLD ORE', 1, 2],
                   zones: ['EMBER'] },
      obsidian:  { skill: 'MINING', lvl: 80, tool: 4, hp: 7,  xp: 400, respawn: 60,  yield: ['OBSIDIAN', 1, 2],
                   zones: ['EMBER'] },
      embercryst:{ skill: 'MINING', lvl: 90, tool: 6, hp: 10, xp: 450, respawn: 480, yield: ['EMBER CRYSTAL', 1, 2],
                   zones: ['EMBER'], deep: true, rare: true },

      // ---- foraging
      berry:     { skill: 'FORAGING', lvl: 1,  tool: 1, hp: 3,  xp: 5,   respawn: 35,  yield: ['BERRIES', 1, 2],
                   zones: ['HEARTLANDS'] },
      mushroom:  { skill: 'FORAGING', lvl: 15, tool: 1, hp: 3,  xp: 75,  respawn: 35,  yield: ['MUSHROOMS', 1, 2],
                   zones: ['GREENWOOD'] },
      reeds:     { skill: 'FORAGING', lvl: 25, tool: 2, hp: 5,  xp: 125, respawn: 35,  yield: ['REEDS', 1, 2],
                   zones: ['MISTFEN'] },
      holly:     { skill: 'FORAGING', lvl: 35, tool: 3, hp: 5,  xp: 175, respawn: 35,  yield: ['HOLLY', 1, 2],
                   zones: ['FROSTWILD'] },
      fenroot:   { skill: 'FORAGING', lvl: 45, tool: 3, hp: 5,  xp: 225, respawn: 35,  yield: ['FENROOT', 1, 2],
                   zones: ['MISTFEN'] },
      pearl:     { skill: 'FORAGING', lvl: 50, tool: 4, hp: 5,  xp: 250, respawn: 35,  yield: ['PEARL', 1, 1],
                   zones: ['SUNCOAST'], water: true },
      dyeflower: { skill: 'FORAGING', lvl: 55, tool: 4, hp: 7,  xp: 275, respawn: 35,  yield: ['DYE FLOWERS', 1, 2],
                   zones: ['SUNSCORCH'] },
      coral:     { skill: 'FORAGING', lvl: 65, tool: 4, hp: 7,  xp: 325, respawn: 35,  yield: ['CORAL', 1, 2],
                   zones: ['ISLES'], water: true },
      spice:     { skill: 'FORAGING', lvl: 70, tool: 4, hp: 7,  xp: 350, respawn: 35,  yield: ['SPICE', 1, 2],
                   zones: ['SUNSCORCH'] },
      firelily:  { skill: 'FORAGING', lvl: 75, tool: 5, hp: 7,  xp: 375, respawn: 35,  yield: ['FIRE LILY', 1, 2],
                   zones: ['EMBER'] },
      lotus:     { skill: 'FORAGING', lvl: 90, tool: 6, hp: 10, xp: 450, respawn: 480, yield: ['BLACK LOTUS', 1, 1],
                   zones: ['MISTFEN'], deep: true, rare: true }
    },

    // 5 percent of harvests drop a bonus on top of the yield. Future hooks.
    BONUS_CHANCE: 0.05,
    BONUS: { WOODCUTTING: 'BIRD NEST', MINING: 'GEM SHARD', FORAGING: 'WILD SEED' },

    // Crafted at the town forge. Every recipe above copper reaches into ground
    // the crafter's home zone does not have. That is the trade economy: it is
    // the same system as the skill ladder, wearing a different hat.
    RECIPES: {
      2: { need: [['COPPER ORE', 8], ['LOGS', 2]] },
      3: { need: [['IRON ORE', 10], ['LOGS', 4]] },
      4: { need: [['IRON ORE', 8], ['COAL', 6], ['OAK LOGS', 2]] },
      5: { need: [['OBSIDIAN', 6], ['ACACIA LOGS', 2]], head: 4 },
      6: { need: [['ICEWOOD', 2], ['GOLD ORE', 1]], head: 5 }
    },

    // Per 64m chunk. The design plan says 14 to 22, which was written before
    // the clutter was merged.
    //
    // Measured, at four densities, standing in the same dressed field:
    //
    //   density      meshes   draws   triangles   ms to build a chunk
    //   55 to 85      6780    1282       176k          7.0
    //   150 to 220    6807    1289       213k          6.1
    //   400 to 600    6815    1279       296k         21.3
    //   900 to 1300   6827    1281       539k         32.0
    //
    // Sixteen times the ground cover moves draw calls by ONE and mesh count by
    // forty seven, because it is all one merged mesh per chunk. What actually
    // grows is triangles, which are cheap, and the time to BUILD a chunk, which
    // is the hitch a player feels walking into new ground. That is the real
    // ceiling here, and it is why this sits at 150 to 220 rather than higher:
    // build cost is flat up to there and triples past it.
    CLUTTER_PER_CHUNK: [150, 220],
    NODES_PER_CHUNK: [2, 4],
    ROAD_CLEAR: 7,         // metres kept clear either side of a road centreline
    TOWN_CLEAR: 60         // metres kept clear around every safe zone
  }
};

// ---- gathering maths --------------------------------------------------------
// One curve, computed once, shared by the client and any future server check.
// XP to go from level n to n+1 is floor(75 * 1.085^n); the table below is the
// cumulative total needed to BE level n.
let GRIM_XP_TABLE = null;
function grimXpTable() {
  if (GRIM_XP_TABLE) return GRIM_XP_TABLE;
  const G = GRIM_RULES.GATHER;
  const t = [0, 0];                       // index 1 = level 1 = 0 xp
  for (let n = 1; n < G.MAX_LEVEL; n++) t[n + 1] = t[n] + Math.floor(G.XP_BASE * Math.pow(G.XP_RATE, n));
  GRIM_XP_TABLE = t;
  return t;
}
// Total XP required to reach a level.
function grimXpForLevel(lvl) {
  const t = grimXpTable();
  return t[Math.max(1, Math.min(GRIM_RULES.GATHER.MAX_LEVEL, lvl | 0))];
}
// Level from a raw XP total.
function grimLevelFromXp(xp) {
  const t = grimXpTable(), max = GRIM_RULES.GATHER.MAX_LEVEL;
  xp = Math.max(0, xp || 0);
  let lo = 1, hi = max;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (t[mid] <= xp) lo = mid; else hi = mid - 1; }
  return lo;
}
// The pre-zone-update curve, kept only so saves can be migrated off it.
function grimLegacyLevel(xp) { return Math.min(99, Math.max(1, Math.floor(Math.pow((xp || 0) / 60, 0.6)) + 1)); }
function grimLegacyXpForLevel(lvl) { return lvl <= 1 ? 0 : Math.ceil(60 * Math.pow(lvl - 1, 5 / 3)); }
// Convert a stored XP value from the old curve to the new one, preserving both
// the level and the fraction of progress through it. Nobody loses a level.
function grimMigrateXp(oldXp) {
  oldXp = Math.max(0, oldXp || 0);
  if (!oldXp) return 0;
  const L = grimLegacyLevel(oldXp);
  if (L >= GRIM_RULES.GATHER.MAX_LEVEL) return grimXpForLevel(GRIM_RULES.GATHER.MAX_LEVEL);
  const a = grimLegacyXpForLevel(L), b = grimLegacyXpForLevel(L + 1);
  const frac = b > a ? Math.max(0, Math.min(1, (oldXp - a) / (b - a))) : 0;
  const na = grimXpForLevel(L), nb = grimXpForLevel(L + 1);
  return Math.floor(na + frac * (nb - na));
}

// ---- deterministic placement ------------------------------------------------
// Every prop, node and spawn point in the world comes out of these. There is no
// Math.random anywhere in placement: two players standing in the same field must
// see the identical tree in the identical spot, because harvest state syncs by
// node id and a node id is only meaningful if both machines generated the same
// node list from the same inputs.
function grimSeed(cx, cz, salt) {
  // 32-bit integer hash of (chunkX, chunkZ, salt, WORLD_GEN). Signed inputs are
  // folded into unsigned space first so negative chunks hash as cleanly as
  // positive ones.
  let h = 0x811c9dc5 ^ (GRIM_RULES.WORLD_GEN * 0x9e3779b1);
  const mix = (v) => {
    h ^= (v | 0);
    h = Math.imul(h, 0x85ebca6b) >>> 0;
    h ^= h >>> 13;
    h = Math.imul(h, 0xc2b2ae35) >>> 0;
    h ^= h >>> 16;
  };
  mix(cx); mix(cz);
  if (typeof salt === 'string') { for (let i = 0; i < salt.length; i++) mix(salt.charCodeAt(i)); }
  else if (salt !== undefined) mix(salt);
  return h >>> 0;
}
// mulberry32: small, fast, and identical on every engine because every step is
// an integer op. Returns a function yielding [0, 1).
function grimRnd(seed) {
  let a = (seed >>> 0) || 1;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ (t + Math.imul(t ^ (t >>> 7), t | 61))) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
// Design zone name for a baked zone id, plus whether that id is the deep band.
function grimZoneName(bakeId) { return GRIM_RULES.ZONE_OF_BAKE[bakeId | 0] || 'HEARTLANDS'; }
function grimZoneIsDeep(bakeId) { return !!GRIM_RULES.ZONE_DEEP_BAKE[bakeId | 0]; }
// Stable id for a streamed node. Chunk coords plus its slot in that chunk's
// deterministic list, so every client names the same node the same thing.
function grimNodeId(cx, cz, i) { return cx + ':' + cz + ':' + i; }

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
/* SHARED-RULES-END */

export class World {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.mem = null;                        // {npcs, sacks, seq} cache of stored world state
    this._dirty = false;                    // true when mem has changes storage doesn't have yet
  }

  // ------------------------------------------------------- world state (durable)

  async world() {
    if (this.mem) return this.mem;
    const w = await this.state.storage.get('world');
    this.mem = w || { npcs: null, sacks: {}, seq: 0 };
    return this.mem;
  }
  async saveWorld() {
    if (!this.mem) return;
    try { await this.state.storage.put('world', this.mem); this._dirty = false; } catch (e) {}
  }
  // Tier 2 item #5: nhit and lreq land far more often than a manifest/nreg
  // setup or a respawn/expiry alarm ever does, so writing the full world
  // blob on every single one of them was real, avoidable storage-write
  // cost. This defers the write instead of skipping it: mark the change and
  // make sure an alarm is due within SAVE_DEBOUNCE_MS, reusing setAlarm's
  // existing "earliest wins" merge against whatever respawn/expiry alarm is
  // already scheduled (see setAlarm below). alarm() already calls
  // saveWorld() unconditionally on every firing regardless of why it fired,
  // so no change was needed there -- this only changes when the write gets
  // requested, never whether it eventually happens. A debounce window this
  // far under the hibernation threshold (see SAVE_DEBOUNCE_MS above) means
  // the worst case is losing up to ~2s of the *last* hit/loot event if the
  // Durable Object were killed outright (not hibernated) at the worst
  // possible instant, same residual risk any debounce carries -- not the
  // unbounded loss window an untriggered timer-based debounce would have.
  async markDirty() {
    this._dirty = true;
    await this.setAlarm(Date.now() + SAVE_DEBOUNCE_MS);
  }

  // ------------------------------------------------------ monster simulation
  //
  // Positions, facing, decisions and attacks all happen here. No player's
  // browser runs any of it, so a slow, hidden or crashed tab cannot stall the
  // world, and two players can never disagree about what a monster is doing.
  //
  // There is deliberately no timer: a Durable Object sleeps between events and
  // a real-time loop would cost an alarm per tick. Instead the clock advances
  // when messages arrive, and players already send their own position ten
  // times a second, so with anyone online the simulation runs at full rate for
  // nothing. An empty world simply stops, which is correct.
  ensureSim(w) {
    if (this.sim && this.sim.length) return this.sim;
    if (!w.manifest || !Array.isArray(w.manifest.spawns)) return null;
    this.sim = w.manifest.spawns.map((s, i) => {
      const n = makeSimNpc(s, i);
      // map the world's named bosses onto their scripts
      const nm = (s.n || '').toUpperCase();
      if (s.king || nm.indexOf('HOLLOW KING') >= 0) n.scriptId = 'hollowKing';
      else if (nm.indexOf('SAILERS') >= 0 || s.spell === 'snare') n.scriptId = 'sailers';
      else if ((s.tag && s.tag.rat) || nm.indexOf('PLAGUE RAT') >= 0) n.scriptId = 'plagueRat';
      else if ((s.tag && s.tag.warden) || nm.indexOf('ARGENT WARDEN') >= 0) n.scriptId = 'argentWarden';
      else if (s.brawler && s.boss) n.scriptId = 'brawler';
      return n;
    });
    // Bind every script that drains from anchors to the actual spawn indices of
    // its anchors, once, by name. Indices are a protocol invariant so this is
    // stable, and doing it here means the fight costs nothing per tick beyond
    // reading two health values.
    for (const n of this.sim) {
      const S = GRIM_RULES.SCRIPTS[n.scriptId];
      if (!S || !S.anchors) continue;
      n.anchorIdx = [];
      w.manifest.spawns.forEach((s, i) => {
        if (String(s.n || '').toUpperCase() === S.anchors) n.anchorIdx.push(i);
      });
    }
    this.colliders = w.manifest.colliders || [];
    // keep the whole shape: copying only {x,z,r} silently dropped the separate
    // player and monster radii, so safe ground stopped working
    this.safe = (w.manifest.safe || []).map(s => Object.assign({}, s));
    this.rnd = mulberry32(0x9e3779b9 ^ (w.manifest.hash || '').length);
    this.lastTick = Date.now();
    this.evSeq = 0;
    return this.sim;
  }

  // Keep the world moving on its own schedule. A Durable Object with live
  // sockets stays in memory, so a short self-rescheduling timer costs nothing
  // extra and does not touch the alarm budget. If the object is ever evicted
  // the timer dies with it and the next arriving message starts it again.
  startPump() {
    if (this._pump) return;
    const tick = async () => {
      this._pump = null;
      try {
        const socks = this.sockets();
        if (!socks.length) return;                 // empty world: stop, and cost nothing
        const w = await this.world();
        if (w.manifest) this.advance(w, socks);
        this._pump = setTimeout(tick, Math.round(1000 / GRIM_RULES.SIM_HZ));
      } catch (e) {
        this.simErr = String((e && e.stack) || e).slice(0, 300);
        this._pump = setTimeout(tick, 250);
      }
    };
    this._pump = setTimeout(tick, Math.round(1000 / GRIM_RULES.SIM_HZ));
  }

  advance(w, socks) {
    const sim = this.ensureSim(w);
    if (!sim || !w.npcs) return;
    const now = Date.now();
    const STEP = 1000 / GRIM_RULES.SIM_HZ;
    let steps = Math.floor((now - (this.lastTick || now)) / STEP);
    if (steps <= 0) { this.pushSnapshots(socks, sim, now); return; }
    // A cold start or a long quiet spell must not be replayed second by
    // second; catch up a little and then jump.
    if (steps > 12) { steps = 1; this.lastTick = now - STEP; }
    this.lastTick += steps * STEP;

    // everyone alive, as the monsters see them
    const players = [], byId = {};
    for (const s of socks) {
      const x = this.meta(s);
      if (!x || !x.id || x.px == null) continue;
      const p = { id: x.id, x: x.px, z: x.pz, hp: x.php == null ? 100 : x.php };
      players.push(p); byId[x.id] = p;
    }

    const events = [];
    const ctx = {
      rules: GRIM_RULES, rnd: this.rnd, players, byId,
      // The roster itself, so a monster that calls its own kind (the goblin
      // shriek) can reach them. Nothing else in the sim needs it.
      npcs: sim,
      colliders: this.colliders, safe: this.safe,
      canAct: (n) => n.state === 'idle' && n.stagger <= 0 && n.frozen <= 0,
      attack: (n, move, tgt) => this.scheduleAttack(n, move, tgt, events),
      script: (n, tgt, dp, dt, c) => this.runScript(n, tgt, dp, dt, c, events)
    };

    const dt = STEP / 1000;
    for (let s = 0; s < steps; s++) {
      for (let i = 0; i < sim.length; i++) {
        const n = sim[i], rec = w.npcs[i];
        if (!rec) continue;
        n.hp = rec.hp; n.dead = rec.dead;      // health is the stored world's word
        n.max = rec.max || n.max;
        if (rec.by && !n.aggroPeer) n.aggroPeer = rec.by;
        stepNpc(n, dt, ctx);
        // The drain. While any of this monster's anchors still stands it pulls
        // itself back together, and the stored world is what has to be written:
        // n.hp is overwritten from rec at the top of every step, so healing the
        // simulation copy alone would do nothing at all.
        if (n.anchorIdx && n.anchorIdx.length && !n.dead && rec.hp > 0 && rec.hp < (rec.max || 1)) {
          let up = 0;
          for (const ai of n.anchorIdx) { const ar = w.npcs[ai]; if (ar && !ar.dead && ar.hp > 0) up++; }
          n.anchorsUp = up;
          if (up > 0) {
            const S2 = GRIM_RULES.SCRIPTS[n.scriptId];
            n.regenAcc = (n.regenAcc || 0) + (S2.regen || 0) * dt;
            if (n.regenAcc >= 1) {
              const add = Math.floor(n.regenAcc);
              n.regenAcc -= add;
              rec.hp = Math.min(rec.max, rec.hp + add);
              n.hp = rec.hp;
              events.push({ t: 'nhp', i: n.i, hp: rec.hp, d: 0, k: 'regen', by: null, regen: 1 });
            }
          }
        } else if (n.anchorIdx) n.anchorsUp = 0;
        // an attack in flight runs its own clock: wind, damage frame, recovery
        if (n.act) {
          const m = GRIM_RULES.MOVES[n.act];
          const tot = m.wind + m.act + m.rec;
          if (n.st >= tot) { n.act = null; n.state = 'idle'; n.st = 0; }
        }
      }
      separate(sim);
    }
    // Tier 2 item #2: during any multi-monster fight, combat/theatre events
    // (atk/boss/proj/regen-nhp, all pushed onto `events` above) used to go
    // out one ws.send() per event, one per connected player -- event count
    // directly multiplied send calls. Batched the same way nsnap already
    // batches NPC snapshots: one 'evb' message carrying the whole array,
    // client-side unpacked back through the same per-type handlers (onRelay
    // recurses on each contained event, so nothing about how an individual
    // atk/boss/proj/nhp is handled changes, only how many messages it took
    // to arrive). A real protocol change -- ships with the matching client
    // decoder in the same commit so neither side can deploy alone.
    if (events.length) this.broadcast(socks, { t: 'evb', at: now, e: events });
    this.pushSnapshots(socks, sim, now);
  }

  // nhit used to call advance() straight, unconditionally, on every landed
  // melee hit -- on top of the ~10Hz pump that already just ran. When a real
  // tick is due (steps > 0) that is correct and this is just advance() with
  // extra steps, so it falls straight through. The waste was the OTHER case:
  // steps <= 0 already short-circuits advance()'s own O(players x npcs) step
  // loop, but it still runs a full pushSnapshots() every single time, and a
  // burst of hits landing within the same ~10Hz window (an AoE, several
  // players hitting at once) each triggered their own redundant pass. hp and
  // death themselves never went through advance() at all -- nhit's handler
  // mutates w.npcs directly -- so nothing about the fix below touches damage
  // or death timing. What advance() actually did here was keep this.sim's
  // aggro flags current and push one fresh snapshot so the target's reaction
  // shows up right away instead of waiting for the next tick; collapsing a
  // burst into one flush (20ms, far under the 100ms pump cadence and any
  // player-perceptible delay) keeps that immediacy while dropping the rest.
  advanceForHit(w, socks) {
    const sim = this.ensureSim(w);
    if (!sim || !w.npcs) return;
    const now = Date.now();
    const STEP = 1000 / GRIM_RULES.SIM_HZ;
    const steps = Math.floor((now - (this.lastTick || now)) / STEP);
    if (steps > 0) { this.advance(w, socks); return; }
    if (now - (this._lastHitPush || 0) < 20) return;
    this._lastHitPush = now;
    this.pushSnapshots(socks, sim, now);
  }

  // An attack is announced once, in full, with the moment it begins on the
  // server's clock. Every player plays the identical telegraph at the identical
  // instant; each player's own machine then decides whether THEY were inside
  // the swing when it landed, judged against where they actually were. That is
  // what makes a dodge honest instead of being decided on somebody else's
  // stale copy of your position.
  // ownProj: the caller (a boss script) is firing its own projectiles, so the
  // generic fallback below must stay out of the way. Without this a scripted
  // spell threw two sets at once - the script's, plus a default set of the
  // wrong kind - which is why the Plague Rat's toxin spit also spat frost.
  scheduleAttack(n, move, tgt, events, ownProj) {
    const m = GRIM_RULES.MOVES[move];
    if (!m) return;
    n.state = (move === 'frost' || move === 'snare' || move === 'volley' || move === 'storm' || move === 'heal') ? 'cast' : 'attack';
    n.st = 0; n.act = move; n.hitDone = false;
    if (m.stam) n.stam = Math.max(0, n.stam - m.stam);
    if (m.mana) n.mana = Math.max(0, n.mana - m.mana);
    const dmg = m.dmg ? Math.round((m.dmg[0] + this.rnd() * (m.dmg[1] - m.dmg[0])) * n.dmgScale) : 0;
    // A move with no reach is a ranged one: staves and bows throw something.
    // Without this an archer or a mage played its whole wind-up and then
    // nothing left its hands, so it looked like it was ignoring you.
    if (!m.range && tgt && !ownProj) {
      const SPEC = {
        frost: { kind: 'frost', n: 1, spread: 0, speed: 16, dmg: 14 },
        snare: { kind: 'snare', n: 1, spread: 0, speed: 15, dmg: 8 },
        volley: { kind: 'snare', n: 3, spread: 0.24, speed: 15, dmg: 8 },
        shot:  { kind: 'arrow', n: 1, spread: 0, speed: 30, dmg: 16 },
        rapid: { kind: 'arrow', n: 3, spread: 0.12, speed: 30, dmg: 9 },
        storm: { kind: 'fire', n: 4, spread: 0.3, speed: 14, dmg: 12 }
      }[move];
      if (SPEC) this.fireProjectiles(n, tgt, { move: move, proj: SPEC }, n.dmgScale, events);
    }
    events.push({
      t: 'atk', ev: ++this.evSeq, i: n.i, m: move, at: Date.now(),
      w: m.wind, a: m.act, r: m.rec,
      x: +n.x.toFixed(2), z: +n.z.toFixed(2), yaw: +n.yaw.toFixed(3),
      rng: m.range || 0, arc: m.arc || 0, dmg: dmg,
      heavy: !!m.heavy, bash: !!m.bash, proj: !m.range
    });
  }

  // Snapshots are the only expensive part, so a player is told about the
  // monsters near THEM and nothing else. That is what keeps a much larger world
  // costing the same per player as this one.
  pushSnapshots(socks, sim, now) {
    const R = GRIM_RULES;
    const fast = 1000 / R.SNAP_HZ, slow = 1000 / R.SNAP_IDLE_HZ;
    for (const ws of socks) {
      const x = this.meta(ws);
      if (!x || x.px == null) continue;
      const rows = [];
      for (const n of sim) {
        const d = Math.hypot(n.x - x.px, n.z - x.pz);
        if (d > R.INTEREST_R) continue;
        const moving = n.aggro || (n.vx * n.vx + n.vz * n.vz) > 0.05 || n.act || n.state !== 'idle';
        const due = moving ? fast : slow;
        if (now - (n.sentAt || 0) < due) continue;
        // Tier 2 item #6 (patch 84.760, matching edit in the client bundle's
        // onNpcSnap decoder): x10/round/divide-by-10 was flagged in the Aug 6
        // audit as worth roughly 20% apparent speed variance on its own --
        // at 0.1m precision the rounding error on a slow-moving monster's
        // per-tick step can be a meaningful fraction of the real step. x100
        // (0.01m) is a real protocol change, shipped in the same commit as
        // the client decoder so neither side can deploy alone.
        rows.push([n.i, Math.round(n.x * 100), Math.round(n.z * 100), Math.round(n.yaw * 100),
                   n.state, Math.round(n.st * 100), Math.round(n.moveAmt * 100), n.act || 0]);
      }
      if (!rows.length) {
        // Silence is not the same as nothing to say. A player who has walked
        // away from every monster was sent NOTHING, so the client's 2s
        // is-the-feed-alive timer expired and it quietly fell back to
        // simulating all 88 NPCs locally, colliders and all. WORLD_R is 4800
        // against an INTEREST_R of 60, so that is the ordinary case out in
        // the world, and the fallback was flapping on and off as you walked.
        // An empty snapshot costs about 30 bytes. onNpcSnap already handles
        // an empty r, and the idle rate keeps this well inside the timer.
        if (now - (x.hbAt || 0) >= slow) { this.send(ws, { t: 'nsnap', at: now, r: [] }); x.hbAt = now; this.setMeta(ws, x); }
        continue;
      }
      this.send(ws, { t: 'nsnap', at: now, r: rows });
    }
    for (const n of sim) {
      const moving = n.aggro || (n.vx * n.vx + n.vz * n.vz) > 0.05 || n.act || n.state !== 'idle';
      if (now - (n.sentAt || 0) >= (moving ? fast : slow)) n.sentAt = now;
    }
  }

  // ---------------------------------------------------------- boss scripts
  //
  // A boss's behaviour is a data table, not code: phases switch on health,
  // each phase lists the moves it can use, and each move declares its own
  // cooldown and the distance band it wants. Adding a bigger boss is adding a
  // table. Returning true means the script took the turn.
  runScript(n, tgt, dp, dt, ctx, events) {
    const S = GRIM_RULES.SCRIPTS[n.scriptId];
    if (!S) return false;

    // a move already playing owns the clock
    if (n.state === 'charge' || n.state === 'taunt' || n.state === 'flourish' || n.state === 'leap') {
      n.scriptT = (n.scriptT || 0) - dt;
      if (n.lungeT > 0) {
        n.lungeT -= dt;
        n.x += n.lungeX * n.lungePow * dt;
        n.z += n.lungeZ * n.lungePow * dt;
        n.dirty = 1;
      }
      if (n.scriptT <= 0) { n.state = 'idle'; n.st = 0; n.lungeT = 0; }
      else { n.wx = 0; n.wz = 0; }
      return true;
    }
    // An announced attack is running. Hand the turn BACK rather than taking
    // it: the ordinary movement step already slows a monster to a crawl while
    // it swings or casts, keeps it facing its target and holds it at its
    // weapon's range. Taking the turn here instead left the boss frozen on
    // whatever velocity it happened to have, which is most of what read as
    // broken pathing. It cannot start a second attack from here because that
    // needs an idle state.
    if (n.act) return false;

    // phase by health
    const pct = n.max ? (n.hp / n.max) * 100 : 100;
    let ph = S.phases.length - 1;
    for (let i = 0; i < S.phases.length; i++) {
      if (pct > S.phases[i].untilHpPct) { ph = i; break; }
    }
    if (ph !== n.phase) {
      n.phase = ph;
      const on = S.phases[ph].onEnter;
      if (on) events.push({ t: 'boss', i: n.i, kind: 'phase', phase: ph, shout: on.shout || null });
    }
    const phase = S.phases[ph];
    const spdMul = phase.spdMul || 1, dmgMul = phase.dmgMul || 1;

    n.specialCd = Math.max(0, (n.specialCd || 0) - 0);
    if (n.specialCd > 0) return false;       // let the ordinary brain steer between moves

    // pick a move that is off cooldown and whose band matches the range
    if (!n.cds) n.cds = {};
    const options = phase.moves.filter(k => {
      const mv = S.moves[k];
      if (!mv) return false;
      if ((n.cds[k] || 0) > Date.now()) return false;
      return dp >= mv.band[0] && dp <= mv.band[1];
    });
    if (!options.length) return false;
    const key = options[Math.floor(ctx.rnd() * options.length)];
    const mv = S.moves[key];
    n.cds[key] = Date.now() + (mv.cd[0] + ctx.rnd() * (mv.cd[1] - mv.cd[0])) * 1000;

    if (mv.proj) {
      this.scheduleAttack(n, mv.move, tgt, events, true);
      this.fireProjectiles(n, tgt, mv, dmgMul, events);
      return true;
    }
    if (mv.move) {
      const before = n.dmgScale;
      n.dmgScale = before * dmgMul;
      this.scheduleAttack(n, mv.move, tgt, events);
      n.dmgScale = before;
      return true;
    }
    // a pure state move: charge, leap, taunt, flourish
    n.state = mv.state; n.st = 0; n.scriptT = mv.dur || 1;
    n.wx = 0; n.wz = 0;
    if (mv.lunge) {
      const d = Math.hypot(tgt.x - n.x, tgt.z - n.z) || 1;
      n.lungeX = (tgt.x - n.x) / d; n.lungeZ = (tgt.z - n.z) / d;
      n.lungePow = mv.lunge * spdMul; n.lungeT = mv.dur || 0.9;
    }
    // A leap that comes down on top of you has to actually hurt. The landing
    // blow rides along with the move, timed as an offset from the move's own
    // start so it cannot drift with the clock, and shaped from the shared move
    // table rather than from numbers written out here. Each player judges it on
    // their own machine against where the boss ACTUALLY lands, which is the
    // entire point of a lunge: it closes the gap, so the blow must be measured
    // after it closes, not from where the boss took off.
    let hit = null;
    if (mv.hit) {
      const hm = GRIM_RULES.MOVES[mv.hit];
      if (hm && hm.dmg) {
        hit = { m: mv.hit,
                t: Math.round((mv.dur || 0.9) * (hm.land == null ? 0.78 : hm.land) * 1000),
                rng: hm.range, arc: hm.arc, heavy: !!hm.heavy,
                dmg: Math.round((hm.dmg[0] + ctx.rnd() * (hm.dmg[1] - hm.dmg[0])) * n.dmgScale * dmgMul) };
      }
    }
    events.push({ t: 'boss', i: n.i, kind: 'move', move: key, state: mv.state, dur: mv.dur || 1,
                  at: Date.now(), shout: mv.shout || null, hit: hit,
                  x: +n.x.toFixed(2), z: +n.z.toFixed(2), yaw: +n.yaw.toFixed(3) });
    return true;
  }

  // Projectiles are announced once with a start point, a velocity and a time.
  // Every machine then draws the identical arc without another byte crossing
  // the network, and each player checks only themselves for a hit. That also
  // means a boss throwing fifty bolts costs the network nothing extra.
  fireProjectiles(n, tgt, mv, dmgMul, events) {
    const p = mv.proj;
    const at = Date.now() + Math.round((GRIM_RULES.MOVES[mv.move] || { wind: 0.4 }).wind * 1000);
    const base = Math.atan2(tgt.x - n.x, tgt.z - n.z);
    const count = p.n || 1;
    for (let k = 0; k < count; k++) {
      const off = count === 1 ? 0 : (k - (count - 1) / 2) * (p.spread || 0);
      const a = base + off;
      events.push({
        t: 'proj', i: n.i, id: ++this.evSeq, k: p.kind, at: at,
        x: +(n.x + Math.sin(a) * 1.1).toFixed(2), y: 1.7, z: +(n.z + Math.cos(a) * 1.1).toFixed(2),
        vx: +(Math.sin(a) * (p.speed || 15)).toFixed(2), vy: 0, vz: +(Math.cos(a) * (p.speed || 15)).toFixed(2),
        dmg: Math.round((p.dmg || 8) * dmgMul), life: 2.4
      });
    }
  }

  /* EDITOR-STORE-BEGIN */
  // ------------------------------------------------------------- edit layer
  //
  // The world editor's authored layer: ground paint, roads, placed objects,
  // deleted procedural props, terrain deltas, spawn markers, prefabs and
  // districts. Reads are PUBLIC because every player's client fetches this at
  // boot to draw the world Kevin authored. Writes require the editor key.
  //
  // Stored in chunks. A Durable Object storage value caps at 128 KiB and the
  // plan expects 100 to 300 KB of edits, so a single put would start failing
  // silently somewhere around Kevin's third road. The chunk count lives in the
  // index record, so a shrinking layer cannot leave orphaned tail chunks
  // behind that a later read would splice back on.
  static EDIT_CHUNK = 96 * 1024;

  async editsRead() {
    const idx = await this.state.storage.get('edits:idx');
    if (!idx || !idx.n) return null;
    const keys = [];
    for (let i = 0; i < idx.n; i++) keys.push('edits:' + i);
    const got = await this.state.storage.get(keys);
    let s = '';
    for (let i = 0; i < idx.n; i++) {
      const part = got.get('edits:' + i);
      if (typeof part !== 'string') return null;     // torn write: refuse it
      s += part;
    }
    return { body: s, rev: idx.rev || 0, at: idx.at || 0, bytes: s.length };
  }

  async editsWrite(body) {
    const CH = World.EDIT_CHUNK;
    const n = Math.max(1, Math.ceil(body.length / CH));
    const prev = await this.state.storage.get('edits:idx');
    const put = {};
    for (let i = 0; i < n; i++) put['edits:' + i] = body.slice(i * CH, (i + 1) * CH);
    await this.state.storage.put(put);
    // Index last, so a failure mid-write leaves the OLD layer readable rather
    // than a half-written new one.
    const rev = ((prev && prev.rev) || 0) + 1;
    await this.state.storage.put('edits:idx', { n, rev, at: Date.now(), bytes: body.length });
    if (prev && prev.n > n) {
      const stale = [];
      for (let i = n; i < prev.n; i++) stale.push('edits:' + i);
      try { await this.state.storage.delete(stale); } catch (e) {}
    }
    return rev;
  }

  async editsFetch(request, url) {
    const key = (this.env && this.env.EDIT_KEY) || '';
    const given = request.headers.get('x-edit-key') || '';

    if (request.method === 'GET') {
      const cur = await this.editsRead();
      if (!cur) return new Response('{"v":1,"empty":true}', {
        headers: {
          'content-type': 'application/json',
          'access-control-allow-origin': '*',
          'cache-control': 'no-cache',
          'x-edit-rev': '0'
        }
      });
      return new Response(cur.body, {
        headers: {
          'content-type': 'application/json',
          'access-control-allow-origin': '*',
          'cache-control': 'no-cache',
          'x-edit-rev': String(cur.rev),
          'etag': '"e' + cur.rev + '"'
        }
      });
    }

    // Anything that writes needs the key. With no key configured on the
    // worker the editor is READ ONLY, which is the safe default: a
    // misconfigured deploy cannot leave the world open to anyone who guesses
    // the URL.
    if (request.method === 'PUT' || request.method === 'POST') {
      if (!key) return json({ ok: false, err: 'no-key-configured' }, 503);
      if (given !== key) return json({ ok: false, err: 'bad-key' }, 403);
      let body;
      try { body = await request.text(); } catch (e) { return json({ ok: false, err: 'unreadable' }, 400); }
      if (body.length > 4 * 1024 * 1024) return json({ ok: false, err: 'too-big' }, 413);
      try { JSON.parse(body); } catch (e) { return json({ ok: false, err: 'not-json' }, 400); }
      const rev = await this.editsWrite(body);
      return json({ ok: true, rev, bytes: body.length });
    }

    // A key check with no write, so the editor can verify a password before
    // it lets Kevin spend an hour painting.
    if (request.method === 'HEAD') {
      if (!key) return new Response(null, { status: 503, headers: { 'access-control-allow-origin': '*' } });
      return new Response(null, {
        status: given === key ? 204 : 403,
        headers: { 'access-control-allow-origin': '*' }
      });
    }
    return json({ ok: false, err: 'method' }, 405);
  }
  /* EDITOR-STORE-END */

  async fetch(request) {
    const url = new URL(request.url);

    /* EDITOR-STORE-ROUTE */
    if (url.pathname.endsWith('/edits')) return this.editsFetch(request, url);

    if (url.pathname.endsWith('/health') || request.headers.get('Upgrade') !== 'websocket') {
      const socks = this.sockets();
      const owner = this.resolveOwner(socks);
      return json({
        ok: true,
        proto: PROTO,
        players: socks.length,
        sim: owner ? owner.meta.id : null,
        simNpcs: this.sim ? this.sim.length : 0,
        simErr: this.simErr || null,
        names: socks.map(s => (this.meta(s) || {}).name || '?')
      });
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];

    const now = Date.now();
    const id = 'p' + Math.random().toString(36).slice(2, 8) + now.toString(36).slice(-3);
    // Tagged with its own id: getWebSockets(id) below is then a direct
    // lookup instead of a linear scan, and (unlike a hand-rolled Map) the
    // tag is held by the platform's own hibernatable-websockets runtime, so
    // it is correct again the instant a hibernated Durable Object wakes up
    // and this class's constructor reruns -- nothing here has to rebuild it.
    this.state.acceptWebSocket(server, [id]);
    server.serializeAttachment({ id, name: 'PLAYER', color: 0, joined: now, seen: now, bg: 0, sec: 0, count: 0 });

    this.send(server, { t: 'welcome', proto: PROTO, id, sv: now });
    this.startPump();
    const socks = this.sockets();
    const owner = this.resolveOwner(socks);
    this.broadcast(socks, { t: 'sim', i: owner ? owner.meta.id : null });

    return new Response(null, { status: 101, webSocket: client });
  }

  // ---------------------------------------------------------------- handlers

  async webSocketMessage(ws, raw) {
    const meta = this.meta(ws);
    if (!meta) return;
    const now = Date.now();

    const sec = Math.floor(now / 1000);
    if (sec !== meta.sec) { meta.sec = sec; meta.count = 0; }
    meta.count++;
    meta.seen = now;

    let m;
    try { m = JSON.parse(raw); } catch (e) { this.setMeta(ws, meta); return; }
    if (!m || typeof m.t !== 'string') { this.setMeta(ws, meta); return; }
    if (m.t === 's') {
      meta.bg = m.bg ? 1 : 0;
      // monsters need to know where everyone is standing
      if (Array.isArray(m.p)) { meta.px = m.p[0]; meta.pz = m.p[2]; }
      if (typeof m.h === 'number') meta.php = m.h;
    }
    this.setMeta(ws, meta);
    if (meta.count > RATE_LIMIT) return;

    const socks = this.sockets();

    if (m.t === 'hello') {
      meta.name = String(m.n || 'PLAYER').slice(0, 14).toUpperCase();
      meta.color = (m.c | 0) || 0;
      this.setMeta(ws, meta);
      const owner = this.resolveOwner(socks);
      this.send(ws, {
        t: 'roster',
        sim: owner ? owner.meta.id : null,
        players: socks.map(s => { const x = this.meta(s) || {}; return { i: x.id, n: x.name, c: x.color }; })
      });
      this.broadcast(socks, { t: 'join', i: meta.id, n: meta.name, c: meta.color }, ws);
      return;
    }

    if (m.t === 'ping') { this.send(ws, { t: 'pong', ts: m.ts, sv: now }); return; }
    if (m.t === 'bye') { try { ws.close(1000, 'bye'); } catch (e) {} return; }

    if (m.t === 'yield') {                          // hidden owner hands the world off
      if (meta.owner) {
        const nb = this.pickNewOwner(socks, ws, true);
        if (nb) { delete meta.owner; this.setMeta(ws, meta); this.makeOwner(socks, nb.ws, nb.meta); }
      }
      return;
    }

    // A frozen owner that never even said goodbye: anyone else's traffic
    // evicts it after 8 silent seconds.
    let owner = this.resolveOwner(socks);
    if (owner && owner.ws !== ws && now - (owner.meta.seen || 0) > OWNER_STALE_MS) {
      const nb = this.pickNewOwner(socks, owner.ws);
      if (nb) { const om = owner.meta; delete om.owner; this.setMeta(owner.ws, om); this.makeOwner(socks, nb.ws, nb.meta); owner = { ws: nb.ws, meta: nb.meta }; }
    }

    // ---- server-authoritative combat ------------------------------------
    if (m.t === 'manifest' || m.t === 'nreg' || m.t === 'nhit' || m.t === 'lreq' || m.t === 'lall') {
      await this.combat(ws, meta, m, socks);
      return;
    }
    // ---- party membership (relay-owned, see the note above RELAYED) -----
    if (m.t === 'ptyi' || m.t === 'ptya' || m.t === 'ptyd' || m.t === 'ptyl' || m.t === 'ptyk') {
      this.party(ws, meta, m, socks);
      return;
    }
    // The owner no longer speaks for monster health or death; the server does.
    if (m.t === 'ndead' || m.t === 'lok' || m.t === 'lno' || m.t === 'skupd' || m.t === 'sknew' || m.t === 'skgone') return;

    // every message is a heartbeat for the simulation
    const world = await this.world();
    if (world.manifest) { this.startPump(); }

    // With the server driving monsters, a player's world snapshot is no longer
    // truth and is dropped; players speak only for themselves.
    if (m.t === 'w' && world.manifest) return;

    if (!RELAYED.has(m.t)) return;
    if (OWNER_ONLY.has(m.t) && (!owner || meta.id !== owner.meta.id)) return;

    // Player combat is strictly one-to-one. A pvp/pvpk without an address
    // would fall through to broadcast and hit every player at once.
    if ((m.t === 'pvp' || m.t === 'pvpk') && !m.to) return;

    m._p = meta.id;                                 // sender, stamped here and never trusted from the client
    delete m.to_;                                   // reserved

    // Party chat is scoped server-side to the sender's current party rather
    // than trusting each client to loop over member ids itself -- one send
    // in, correctly scoped delivery out, and it can't drift from ptyu.
    if (m.t === 'chat' && m.ch === 'party') {
      if (meta.party) {
        for (const s of this.partyMembers(socks, meta.party)) { if (s !== ws) this.send(s, m); }
      }
      return;
    }

    // Position broadcasts get the same interest filter NPC snapshots already
    // use (GRIM_RULES.INTEREST_R) -- every player's move otherwise reached
    // every other connected player regardless of distance, cost growing with
    // concurrent players. Party membership is checked first and exempts the
    // distance filter entirely: the party "where's my partner" overlay needs
    // a member's position even far away, same reasoning as the party chat
    // scoping just above. Failing open (send when either side's position
    // isn't known yet) matches how every other path here already behaves --
    // a silently dropped position update reads to a player as "everyone else
    // stopped moving," a far worse failure than one extra send.
    if (m.t === 's') {
      const R = GRIM_RULES;
      for (const w of socks) {
        if (w === ws) continue;
        const x = this.meta(w);
        if (!x) continue;
        if (meta.party && x.party === meta.party) { this.send(w, m); continue; }
        if (meta.px == null || meta.pz == null || x.px == null || x.pz == null) { this.send(w, m); continue; }
        if (Math.hypot(meta.px - x.px, meta.pz - x.pz) <= R.INTEREST_R) this.send(w, m);
      }
      return;
    }

    if (m.to) {                                     // directed reply, used for loot grants
      const target = this.oneById(m.to);
      if (target) this.send(target, m);
      return;
    }

    if (TO_OWNER.has(m.t)) {
      if (owner && owner.ws !== ws) this.send(owner.ws, m);
      return;
    }

    this.broadcast(socks, m, ws);
  }

  // -------------------------------------------------------------- combat

  async combat(ws, meta, m, socks) {
    const w = await this.world();
    const now = Date.now();

    // A client hands over the monster roster once. The server owns health from
    // that moment on; later registrations are ignored so nobody can reset a
    // fight by reloading.
    // The world manifest: colliders, safe ground and monster spawns, uploaded
    // once with a fingerprint. The server keeps the first one it is given. A
    // client arriving with a different fingerprint is told so and defers to the
    // stored copy, which is what stops one player's stale build from putting
    // monsters where nobody else can see them. A genuinely new build replaces
    // it only when the world is empty of other players.
    if (m.t === 'manifest') {
      const mf = m.w;
      const alone = socks.length <= 1;
      if (!mf || typeof mf.hash !== 'string') return;
      // A higher WORLD_GEN replaces the stored world even with players online:
      // a new terrain bake must never be blocked by someone on the old build.
      if (!w.manifest || ((mf.gen | 0) > (w.manifest.gen | 0)) ||
          (w.manifest.hash !== mf.hash && alone)) {
        w.manifest = mf;
        w.npcs = null;                        // a new world means new monsters
        w.sacks = {};
        await this.saveWorld();
      }
      const agreed = w.manifest.hash === mf.hash;
      if (!w.npcs && Array.isArray(w.manifest.spawns)) {
        w.npcs = w.manifest.spawns.map(s => ({
          hp: Math.max(1, s.max | 0), max: Math.max(1, s.max | 0), tag: s.tag || {},
          xp: s.xp | 0, boss: !!s.boss, dead: 0, at: 0, by: null
        }));
        await this.saveWorld();
      }
      this.send(ws, {
        t: 'msync', hash: w.manifest.hash, agreed, sv: Date.now(),
        n: (w.npcs || []).map(n => [n.hp, n.dead ? 1 : 0])
      });
      return;
    }

    if (m.t === 'nreg') {
      if (!w.npcs && Array.isArray(m.n) && m.n.length && m.n.length < 400) {
        w.npcs = m.n.map(x => ({ hp: Math.max(1, x.m | 0), max: Math.max(1, x.m | 0), tag: x.tag || {}, xp: x.xp | 0, boss: !!x.boss, dead: 0, at: 0, by: null }));
        await this.saveWorld();
      }
      this.send(ws, { t: 'nsync', n: (w.npcs || []).map(n => [n.hp, n.dead ? 1 : 0]) });
      return;
    }

    if (m.t === 'nhit') {
      if (!w.npcs) return;
      try { this.advanceForHit(w, socks); } catch (e) {}
      const i = m.i | 0;
      const n = w.npcs[i];
      if (!n || n.dead || n.hp <= 0) return;
      const dmg = Math.max(0, Math.min(9999, Math.round(+m.d || 0)));
      if (!dmg) return;
      n.hp = Math.max(0, n.hp - dmg);
      n.by = meta.id;
      const live = this.sim && this.sim[i];
      if (live) { live.aggro = true; live.aggroPeer = meta.id; live.hasWay = false; }
      // Everyone hears the hit: the attacker for confirmation, the others so
      // the health bar matches. The monster's own reaction rides along.
      this.broadcast(socks, { t: 'nhp', i: i, hp: n.hp, d: dmg, k: m.k || 'hit', by: meta.id, p: m.p || null, o: m.o || null });
      if (n.hp <= 0) {
        n.dead = 1;
        // An anchor re-forges on its own short clock. That number is the
        // whole two-player requirement, so it lives in the shared rules and
        // not in a magic number here.
        n.at = now + ((n.tag && n.tag.anchor) ? (GRIM_RULES.RESPAWN_ANCHOR_MS || 26000)
                     : n.boss ? GRIM_RULES.RESPAWN_BOSS_MS : GRIM_RULES.RESPAWN_MS);
        // An anchor drops nothing and grants nothing. It comes back every 26
        // seconds, so anything it gave would be an infinite tap, and the loot
        // roll always adds gold no matter what the table says.
        const entries = (n.tag && n.tag.anchor) ? [] : grimRollLoot(n.tag).filter(e => e && e.qty > 0);
        let sack = null;
        if (entries.length) {
          w.seq = (w.seq || 0) + 1;
          const id = 'k' + w.seq.toString(36) + now.toString(36).slice(-4);
          sack = { id, x: (m.p && +(+m.p[0]).toFixed(2)) || 0, z: (m.p && +(+m.p[2]).toFixed(2)) || 0,
                   entries: entries.map((e, k) => ({ e: k, item: e.item, qty: Math.floor(e.qty) })),
                   owner: meta.id, pub: now + GRIM_RULES.SACK_OWN_MS, die: now + GRIM_RULES.SACK_LIFE_MS };
          w.sacks[id] = sack;
          const ids = Object.keys(w.sacks);
          if (ids.length > GRIM_RULES.SACK_CAP) {
            let oldest = ids[0];
            for (const k2 of ids) if (w.sacks[k2].die < w.sacks[oldest].die) oldest = k2;
            delete w.sacks[oldest];
            this.broadcast(socks, { t: 'skgone', id: oldest });
          }
        }
        this.broadcast(socks, { t: 'ndead', i: i, xp: n.xp, tag: n.tag, killer: meta.id, p: m.p || null, at: n.at - now });
        if (sack) this.broadcast(socks, { t: 'sknew', s: this.wire(sack, now) });
        await this.setAlarm(n.at);
      }
      // Tier 2 item #5: hp/death state above is mutated on this.mem (the
      // in-memory cache) either way; only the storage.put() itself is
      // deferred, and only up to SAVE_DEBOUNCE_MS. See markDirty().
      await this.markDirty();
      return;
    }

    if (m.t === 'lreq') {                    // take from a sack
      const s = w.sacks[m.id];
      if (!s) { this.send(ws, { t: 'lno', tok: m.tok }); return; }
      if (now < s.pub && meta.id !== s.owner) { this.send(ws, { t: 'lno', tok: m.tok, locked: 1 }); return; }
      const en = s.entries.find(x => x.e === (m.e | 0));
      if (!en || en.qty < 1) { this.send(ws, { t: 'lno', tok: m.tok }); return; }
      const take = Math.max(1, Math.min(Math.floor(+m.q) || 1, en.qty));
      en.qty -= take;
      this.send(ws, { t: 'lok', tok: m.tok, item: en.item, qty: take });
      if (en.qty <= 0) s.entries = s.entries.filter(x => x.qty > 0);
      if (!s.entries.length) { delete w.sacks[m.id]; this.broadcast(socks, { t: 'skgone', id: m.id }); }
      else this.broadcast(socks, { t: 'skupd', id: m.id, e: en.e, qty: en.qty });
      // Tier 2 item #5: same debounce as nhit above -- the sack mutation is
      // already applied to this.mem, only the storage write is deferred.
      await this.markDirty();
      return;
    }

    if (m.t === 'lall') {                    // a player asks for everything present
      this.send(ws, { t: 'lsync', sacks: Object.keys(w.sacks).map(k => this.wire(w.sacks[k], now)) });
      return;
    }
  }

  wire(s, now) {
    return { id: s.id, x: s.x, z: s.z, entries: s.entries, owner: s.owner,
             pubIn: Math.max(0, s.pub - now), dieIn: Math.max(0, s.die - now) };
  }

  // Respawns and sack expiry must survive hibernation, so they run on an alarm
  // rather than a timer, which a hibernated object would never fire.
  async setAlarm(at) {
    try {
      const cur = await this.state.storage.getAlarm();
      if (cur === null || at < cur) await this.state.storage.setAlarm(at);
    } catch (e) {}
  }

  async alarm() {
    const w = await this.world();
    const now = Date.now();
    const socks = this.sockets();
    let next = 0;
    if (w.npcs) {
      for (let i = 0; i < w.npcs.length; i++) {
        const n = w.npcs[i];
        if (!n.dead) continue;
        if (n.at <= now) { n.dead = 0; n.hp = n.max; n.by = null; n.at = 0; this.broadcast(socks, { t: 'nrsp', i: i, hp: n.hp }); }
        else if (!next || n.at < next) next = n.at;
      }
    }
    for (const k of Object.keys(w.sacks)) {
      const s = w.sacks[k];
      if (s.die <= now) { delete w.sacks[k]; this.broadcast(socks, { t: 'skgone', id: k }); }
      else if (!next || s.die < next) next = s.die;
    }
    await this.saveWorld();
    if (next) { try { await this.state.storage.setAlarm(next); } catch (e) {} }
  }

  async webSocketClose(ws) { this.gone(ws); }
  async webSocketError(ws) { this.gone(ws); }

  gone(ws) {
    const meta = this.meta(ws);
    const socks = this.sockets().filter(s => s !== ws);
    if (meta) this.broadcast(socks, { t: 'left', i: meta.id });
    if (meta && meta.party) this.partyLeaveInternal(meta, socks);
    const flagged = socks.find(s => { const x = this.meta(s); return x && x.owner; });
    if (!flagged) {
      const nb = this.pickNewOwner(socks, null);
      if (nb) { this.makeOwner(socks, nb.ws, nb.meta); return; }   // makeOwner broadcasts 'sim'
    }
    const owner = this.resolveOwner(socks);
    this.broadcast(socks, { t: 'sim', i: owner ? owner.meta.id : null });
  }

  // ------------------------------------------------------------------ party
  //
  // Every party op reads/writes the mutating socket's own attachment plus
  // whichever other sockets are affected, then always finishes by pushing a
  // fresh ptyu to every remaining member so nobody's client can go stale.
  // Nothing here is trusted from the client except which target id a client
  // is asking about -- membership itself is decided from live attachments.

  party(ws, meta, m, socks) {
    if (m.t === 'ptyi') {                             // pure notification, no membership change
      if (!m.to || m.to === meta.id) return;
      const target = this.oneById(m.to);
      if (target) this.send(target, { t: 'ptyi', from: meta.id, name: meta.name, color: meta.color });
      return;
    }
    if (m.t === 'ptyd') {                             // decline: notify the inviter only
      if (!m.to) return;
      const target = this.oneById(m.to);
      if (target) this.send(target, { t: 'ptyd', from: meta.id, name: meta.name });
      return;
    }
    if (m.t === 'ptya') { this.partyAccept(ws, meta, m, socks); return; }
    if (m.t === 'ptyl') { this.partyLeave(ws, meta, socks); return; }
    if (m.t === 'ptyk') { this.partyKick(ws, meta, m, socks); return; }
  }

  partyMembers(socks, partyId) {
    return socks.filter(s => { const x = this.meta(s); return x && x.party === partyId; });
  }

  partyRosterPush(socks, partyId) {
    const members = this.partyMembers(socks, partyId);
    const roster = members.map(s => { const x = this.meta(s); return { i: x.id, n: x.name, c: x.color, leader: !!x.partyLeader }; });
    for (const s of members) this.send(s, { t: 'ptyu', party: partyId, members: roster });
  }

  partyAccept(ws, meta, m, socks) {
    if (!m.to) return;
    const inviter = this.oneById(m.to);
    if (!inviter) return;
    let invMeta = this.meta(inviter);
    if (!invMeta) return;

    // the inviter's first accepted invite is what starts a party
    let partyId = invMeta.party;
    if (!partyId) {
      partyId = 'pty_' + invMeta.id;
      invMeta.party = partyId; invMeta.partyLeader = true;
      this.setMeta(inviter, invMeta);
    }

    if (meta.party === partyId) return;               // already in it (duplicate accept)

    const already = this.partyMembers(socks, partyId);
    if (already.length >= PARTY_CAP) {
      this.send(ws, { t: 'ptyu', party: null, members: [], full: true });
      return;
    }

    // joining a new party means leaving whatever party you were already in
    if (meta.party) this.partyLeaveInternal(meta, socks);

    meta.party = partyId; meta.partyLeader = false;
    this.setMeta(ws, meta);
    this.partyRosterPush(socks, partyId);
  }

  partyLeave(ws, meta, socks) {
    if (!meta.party) return;
    this.partyLeaveInternal(meta, socks);
    this.setMeta(ws, meta);
    this.send(ws, { t: 'ptyu', party: null, members: [] });
  }

  // Shared by an explicit /leave, a kick target, and a plain disconnect.
  // Mutates the departing member's own `meta` object (caller persists or
  // discards it) and repromotes / dissolves the remainder.
  partyLeaveInternal(meta, socks) {
    const partyId = meta.party;
    const leavingId = meta.id;
    const wasLeader = !!meta.partyLeader;
    delete meta.party; delete meta.partyLeader;

    const remaining = this.partyMembers(socks, partyId).filter(s => { const x = this.meta(s); return x && x.id !== leavingId; });
    if (!remaining.length) return;                     // party dissolves with nobody left

    if (remaining.length === 1) {                       // no reason to keep a lone member "in a party"
      const only = this.meta(remaining[0]);
      delete only.party; delete only.partyLeader;
      this.setMeta(remaining[0], only);
      this.send(remaining[0], { t: 'ptyu', party: null, members: [] });
      return;
    }

    if (wasLeader) {                                    // hand leadership to the longest-standing member,
      let best = null;                                  // the same seniority rule pickNewOwner already uses
      for (const s of remaining) {
        const x = this.meta(s);
        if (!best || x.joined < best.x.joined) best = { s, x };
      }
      if (best) { best.x.partyLeader = true; this.setMeta(best.s, best.x); }
    }
    this.partyRosterPush(socks, partyId);
  }

  partyKick(ws, meta, m, socks) {
    if (!meta.party || !meta.partyLeader || !m.to || m.to === meta.id) return;
    const target = this.oneById(m.to);
    if (!target) return;
    const tMeta = this.meta(target);
    if (!tMeta || tMeta.party !== meta.party) return;   // party check, not id-taggable (party changes post-connect)
    delete tMeta.party; delete tMeta.partyLeader;
    this.setMeta(target, tMeta);
    this.send(target, { t: 'ptyu', party: null, members: [], kicked: true });
    this.partyRosterPush(socks, meta.party);
  }

  // ------------------------------------------------------------------ owner

  // The sticky flag wins; with no flag in the room the oldest connection is
  // stamped. Always resolved from the live socket set, so hibernation and
  // restarts cannot fork ownership.
  resolveOwner(socks) {
    for (const s of socks) { const x = this.meta(s); if (x && x.owner) return { ws: s, meta: x }; }
    let best = null;
    for (const s of socks) {
      const x = this.meta(s);
      if (!x || !x.id) continue;
      if (!best || x.joined < best.meta.joined || (x.joined === best.meta.joined && x.id < best.meta.id)) best = { ws: s, meta: x };
    }
    if (best) { best.meta.owner = true; this.setMeta(best.ws, best.meta); }
    return best;
  }

  makeOwner(socks, ws, meta) {
    for (const s of socks) { const x = this.meta(s); if (x && x.owner && s !== ws) { delete x.owner; this.setMeta(s, x); } }
    meta.owner = true; this.setMeta(ws, meta);
    this.broadcast(socks, { t: 'sim', i: meta.id });
  }

  // Prefer the most recently active VISIBLE player; a hidden tab would just
  // freeze the world all over again. Falls back to most recently active.
  pickNewOwner(socks, exceptWs, onlyVisible) {
    let best = null;
    for (const s of socks) {
      if (s === exceptWs) continue;
      const x = this.meta(s);
      if (!x || !x.id) continue;
      if (onlyVisible && x.bg) continue;
      const score = (x.bg ? 0 : 1e15) + (x.seen || 0);
      if (!best || score > best.score) best = { ws: s, meta: x, score };
    }
    return best;
  }

  // ------------------------------------------------------------------ utils

  sockets() { try { return this.state.getWebSockets(); } catch (e) { return []; } }
  meta(ws) { try { return ws.deserializeAttachment(); } catch (e) { return null; } }
  // Direct-by-id lookup via the accept-time tag (see fetch()), for the
  // directed-message call sites (loot grants, party invite/accept/kick)
  // that used to linear-scan every socket for one x.id === m.to match.
  // Deliberately NOT used for owner lookups: ownership is a flag that
  // flips after connect, tags are fixed at accept time, so resolveOwner()
  // and friends still scan -- see TIER2 patch notes for why.
  oneById(id) { try { return this.state.getWebSockets(id)[0] || null; } catch (e) { return null; } }
  setMeta(ws, meta) { try { ws.serializeAttachment(meta); } catch (e) {} }
  send(ws, obj) { try { ws.send(JSON.stringify(obj)); } catch (e) {} }
  broadcast(socks, obj, except) {
    const s = JSON.stringify(obj);
    for (const w of socks) { if (w === except) continue; try { w.send(s); } catch (e) {} }
  }
}

function json(o, status) {
  return new Response(JSON.stringify(o), {
    status: status || 200,
    headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' }
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'access-control-allow-origin': '*',
          'access-control-allow-headers': '*',
          // The editor PUTs its layer with an x-edit-key header, which makes
          // it a preflighted request: without an explicit method list the
          // browser refuses the write and reports it as a network error.
          'access-control-allow-methods': 'GET, PUT, POST, HEAD, OPTIONS',
          'access-control-expose-headers': 'x-edit-rev, etag',
          'access-control-max-age': '86400'
        }
      });
    }
    const parts = url.pathname.split('/').filter(Boolean);
    if (parts.length && parts[0] !== 'world' && parts[0] !== 'health') {
      return json({ ok: false, hint: 'connect to /world/<name>' });
    }
    const world = (parts[0] === 'world' && parts[1]) ? parts[1] : 'main';
    const id = env.WORLD.idFromName(world);
    return env.WORLD.get(id).fetch(request);
  }
};
