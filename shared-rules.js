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
    BLEND_DEFAULT: 2, // default paint/road edge softness, in metres
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
