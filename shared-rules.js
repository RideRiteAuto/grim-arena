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
  WORLD_GEN: 5,

  // ---- world bounds -------------------------------------------------------
  WORLD_R: 4800,         // Asterra chart radius: covers the whole baked map;
                         // real bounds are the coastline + deep water + chart
                         // edge, enforced by GRIM_WORLD.walkable on the client
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
    leap:   { land: .78, dmg: [14, 20], range: 2.6, arc: 2.8, heavy: true }
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
      { tier: 2, name: 'COPPER',     axe: 'COPPER AXE',     pick: 'COPPER PICKAXE',      sickle: 'COPPER SICKLE' },
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
                   zones: ['HEARTLANDS', 'GREENWOOD', 'SUNCOAST', 'WINDSCAR', 'EASTRIDGE'] },
      zoak:      { skill: 'WOODCUTTING', lvl: 10, tool: 1, hp: 3,  xp: 50,  respawn: 45,  yield: ['OAK LOGS', 1, 2],
                   zones: ['HEARTLANDS', 'GREENWOOD'] },
      palm:      { skill: 'WOODCUTTING', lvl: 20, tool: 2, hp: 3,  xp: 100, respawn: 45,  yield: ['PALM LOGS', 1, 2],
                   zones: ['SUNCOAST', 'ISLES'] },
      willow:    { skill: 'WOODCUTTING', lvl: 30, tool: 2, hp: 5,  xp: 150, respawn: 45,  yield: ['WILLOW LOGS', 1, 2],
                   zones: ['MISTFEN'] },
      bogoak:    { skill: 'WOODCUTTING', lvl: 30, tool: 2, hp: 5,  xp: 150, respawn: 45,  yield: ['BOG OAK LOGS', 1, 2],
                   zones: ['MISTFEN'] },
      elder:     { skill: 'WOODCUTTING', lvl: 40, tool: 3, hp: 5,  xp: 200, respawn: 45,  yield: ['ELDER LOGS', 1, 2],
                   zones: ['GREENWOOD'] },
      acacia:    { skill: 'WOODCUTTING', lvl: 50, tool: 4, hp: 5,  xp: 250, respawn: 45,  yield: ['ACACIA LOGS', 1, 2],
                   zones: ['WINDSCAR'] },
      icewood:   { skill: 'WOODCUTTING', lvl: 60, tool: 4, hp: 7,  xp: 300, respawn: 45,  yield: ['ICEWOOD', 1, 2],
                   zones: ['FROSTWILD'] },
      emberbark: { skill: 'WOODCUTTING', lvl: 75, tool: 5, hp: 7,  xp: 375, respawn: 45,  yield: ['EMBERBARK', 1, 2],
                   zones: ['EMBER'] },
      elderking: { skill: 'WOODCUTTING', lvl: 90, tool: 6, hp: 10, xp: 450, respawn: 480, yield: ['ANCIENT ELDER LOGS', 1, 2],
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

    // Per 64m chunk, from the design plan's density budget.
    CLUTTER_PER_CHUNK: [14, 22],
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
