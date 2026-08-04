# Asterra Zone Dressing Plan (v1, for Kevin's review)

Fills the barren world with per-zone trees, plants, ground clutter, ore
nodes, wildlife, and low-level monsters, plus the two wooden bridges drawn
on the map. Built on "Asterra World Reference v2": every zone's nodes and
creatures reinforce its canon exports, and every zone is MISSING what it
must import. Nothing here is self-sufficient.

## Global rules (apply everywhere)

- All existing tree models get scaled up 25 percent. New trees are built
  at the new scale.
- Everything places procedurally and deterministically: same seed on every
  machine, keyed by chunk + zone, so all players see the identical world
  and harvest sync keeps working by index.
- Nothing spawns in water (the dry-land rule already shipped), on roads,
  or inside town safe zones.
- Ground clutter tier (small stones, sticks, grass tufts, zone-tinted
  bushes) is dense but cheap: merged geometry per chunk, no shadows, purely
  decorative at first. Sticks and small stones can become pickups later.
- Harvestable tiers: trees (axe), ore nodes (pick), plant nodes (hand).
  Each zone's UNIQUE nodes are the economy hook and exist nowhere else.
- Wildlife = passive critters (flee when hit). Monsters = low-level
  aggressives, roughly matched to a zone's distance from the capital.
  All zone-keyed spawn tables, all obey the water wall.

## Gathering skills: 1 to 99, tiered nodes, tiered tools

Three gathering skills at launch, each leveling 1-99 on the same XP curve.
(Fishing is reserved as a fourth skill for a later update.)

- WOODCUTTING - axe - trees
- MINING - pick - ore, stone, and mineral nodes
- FORAGING - hands, sickle later - herbs, plants, pearls, coral

### How leveling works
- Every successful gather grants XP scaled to the node's tier. Each level
  needs roughly 8 percent more XP than the last, so 1-40 comes fast, the
  50s feel earned, and 99 is a long-haul prestige goal (the level 99 cape
  moment can come later).
- A node needs BOTH a skill level and a minimum tool tier. Too low on
  either and you get a clear message telling you what you are missing.
- Higher skill and better tools also gather slightly faster, so veterans
  feel the difference on every swing.
- Skill XP and levels persist in the cloud save with the rest of the
  character. One shared curve formula lives in shared-rules so the client
  and any future server sim always agree.

### Tool tiers (the trade hook)
Tools gate access, and BUILDING each tier forces cross-zone trade:

| Tier | Axe / Pick / Sickle | Materials | Where the parts come from |
| 1 | Crude | starter gift | everyone logs in with these |
| 2 | Copper | copper bars | Ironspire foothills |
| 3 | Iron | iron bars | Ironspire |
| 4 | Steel | iron + coal | coal exists ONLY in Ironspire |
| 5 | Obsidian | obsidian + steel | obsidian exists ONLY in Ember |
| 6 | Masterwork | obsidian head + icewood haft | Ember AND Frostwild - a cross-continent flex |

### Woodcutting tiers
| Lvl | Tree | Where |
| 1 | Poplar and scrub wood | Heartlands, roadsides everywhere |
| 10 | Oak | Heartlands, Greenwood |
| 20 | Palm | Sun Coast, Shattered Isles |
| 30 | Willow and bog oak | Mistfen |
| 40 | Old-growth elder | Greenwood |
| 50 | Acacia ironbark | Windscar |
| 60 | Icewood | Frostwild ONLY |
| 75 | Emberbark blackwood | Ember ONLY |
| 90 | Ancient elder (rare spawns) | deep Greenwood |

### Mining tiers
| Lvl | Node | Where |
| 1 | Loose stone | rocky ground everywhere |
| 10 | Copper | Ironspire foothills |
| 20 | Salt flats | Sun Coast ONLY |
| 30 | Iron | Ironspire ONLY |
| 40 | Coal seams | Ironspire ONLY |
| 50 | Saltpeter crust | Windscar ONLY |
| 55 | Glass-sand pits | Sunscorch ONLY |
| 65 | Gold veins | Ember ONLY |
| 80 | Obsidian flows | Ember ONLY |
| 90 | Ember crystal (rare minerals) | deep Ember |

### Foraging tiers
| Lvl | Plant or node | Where |
| 1 | Berry bushes | Heartlands |
| 15 | Mushroom rings | Greenwood |
| 25 | Reeds and cattails | Mistfen |
| 35 | Holly and lichen | Frostwild |
| 45 | Fenroot | Mistfen ONLY |
| 50 | Pearl beds (dive for them) | Sun Coast ONLY |
| 55 | Dye flowers | Sunscorch ONLY |
| 65 | Coral (dive) | Shattered Isles ONLY |
| 70 | Spice bushes | Sunscorch ONLY |
| 75 | Fire lilies | Ember ONLY |
| 90 | Black lotus (rare spawns) | deep Mistfen |

### Why this layout
Reaching 99 in ANY skill forces travel through at least five zones and
both continents, and the best tools in the game cannot be built from any
single zone's ground. The skill ladder and the trade economy are the same
system wearing two hats.

## Valewold (west, temperate)

### Heartlands (starter zone, gentlest)
- Trees: broad oaks, poplars, orchard apple trees near farms.
- Plants and clutter: wheat-grass tufts, berry bushes (harvest: berries),
  wildflowers, hay bales near the capital, sticks and field stones.
- Ore: NONE. The Heartlands import all metal - that is canon.
- Wildlife: cows, sheep, chickens, dogs and cats around the capital,
  rabbits, deer.
- Monsters: young goblins, giant rats, the occasional boar. Level 1-5.
- Unique: grain and livestock (future farm plots), commerce.

### Greenwood Marches (southwest forest)
- Trees: HUGE old-growth oaks and elders (best timber yields in the
  west), mossy fallen logs.
- Plants and clutter: ferns, mushroom rings (harvest: mushrooms), ivy
  stones, thick underbrush bushes.
- Ore: none. Metal tools come in by road, canon.
- Wildlife: deer herds, squirrels, foxes, owls.
- Monsters: timber wolves, boars, bandit woodcutters. Level 4-9.
- Unique: timber + leather (deer/boar hides).

### Frostwild North (taiga and tundra)
- Trees: snow-dusted pines, bare birches, and ICEWOOD trees (unique
  harvest, pale blue wood, the zone's export).
- Plants and clutter: snow drifts, frosted grass, lichen rocks, holly
  bushes with red berries.
- Ore: none (furs and wood country, not mine country).
- Wildlife: elk, snow foxes, snowy owls, hares (fur sources).
- Monsters: white wolves, ice sprites, frost goblins. Level 8-14.
- Unique: icewood + furs. Needs grain and metal, canon.

### Ironspire Mountains (mining country)
- Trees: sparse, wind-bent hardy pines only; mostly bare rock.
- Plants and clutter: scree, boulders, hardy thistle, mountain moss.
- Ore: IRON nodes, COAL seams, cut-stone quarries - the world's only
  coal, and its richest iron. This is the economy anchor.
- Wildlife: mountain goats, marmots, eagles overhead.
- Monsters: rock crawlers, kobold miners, cave bats near mine mouths.
  Level 10-16.
- Unique: iron + coal + stone. Imports ALL food, canon: no berry bushes,
  no game herds up here on purpose.

### Sun Coast (warm south shore)
- Trees: palms along the beaches, cypress by the delta.
- Plants and clutter: dune grass, driftwood, seashells, beach stones.
- Ore: SALT flats (unique evaporation nodes) and PEARL beds in the
  shallows (harvest while swimming - our swimming finally pays off).
- Wildlife: gulls, crabs scuttling the sand, pelicans, stray dogs at the
  harbor.
- Monsters: giant crabs, smuggler thugs near coves. Level 6-12.
- Unique: salt + pearls + shipyards. Timber must come from Greenwood.

## Ashmar (east, hotter and harsher)

### Windscar Steppe (dry grassland)
- Trees: lone acacias and gnarled scrub trees, very sparse by design.
- Plants and clutter: tall dry grass everywhere, tumble-brush, sun-
  bleached bones, wool tufts on fences.
- Ore: SALTPETER crusts (unique node, the gunpowder hook).
- Wildlife: WILD HORSES (the world's only mount source - look, don't
  tame, for now), steppe sheep (wool), prairie dogs, hawks.
- Monsters: jackals, steppe raiders, dust devils. Level 12-18.
- Unique: horses + wool + saltpeter. No timber to speak of, canon.

### Ember Highlands (volcanic core)
- Trees: charred snags and ember-barked blackwoods, glowing at the seams.
- Plants and clutter: ash drifts, obsidian shards, fumaroles venting
  smoke, fire lilies.
- Ore: GOLD veins, OBSIDIAN flows, rare mineral crystals - the world's
  gold, nowhere else.
- Wildlife: ash goats, salamanders, ember moths at night.
- Monsters: magma crawlers, ash imps, kobold gold-diggers. Level 16-22.
- Unique: gold + obsidian. Imports food, timber, cloth - the most
  import-hungry zone, canon.

### Mistfen Wetlands (marsh)
- Trees: willows trailing into the water, mangroves along the Cinder Run,
  dead bog oaks.
- Plants and clutter: reeds, cattails, lily pads, glowing fen-light
  wisps, HERB nodes (unique: alchemy reagents - fenroot, marsh sage,
  black lotus).
- Ore: none. Bog iron maybe someday; for now the fen trades in reagents.
- Wildlife: frogs, herons, dragonflies, marsh deer.
- Monsters: bog serpents, mud crabs, will-o-wisps, fen lurkers.
  Level 14-20.
- Unique: herbs + reagents + rare fish. Needs dry timber and metal, canon.

### Sunscorch Barrens (desert)
- Trees: saguaro-style cacti, bleached dead trees, palm cluster at
  Duskwell Oasis only.
- Plants and clutter: dunes, sun-cracked earth, animal skulls, glass-sand
  glitter patches, SPICE bushes and DYE flowers (unique harvests).
- Ore: GLASS-SAND pits (unique, the glass economy).
- Wildlife: camels(?), vultures circling, desert hares, geckos.
- Monsters: scorpions (small and giant), sand goblins, bone jackals.
  Level 18-24, the hardest open zone.
- Unique: glass + spice + dye - the farthest, richest packs in the game,
  canon. Practically nothing else grows: max import need.

### Shattered Isles + Driftwatch (light pass for now)
- Isles: storm-bent palms, wreck debris, coral outcrops (unique CORAL
  nodes), giant crabs and pirate scouts.
- Driftwatch: neutral, tidy, a few palms and market crates, no monsters.

## The bridges (build alongside the dressing)

Two bridges are drawn on the map, and they are canon chokepoints - both
get beautiful wooden builds: arched laminated beams, plank decks, rope
and post railings, lantern posts at each end, wide enough for two mounts
to pass.

- ARGENT BRIDGE - north crossing of the Great River, world (-472, -364).
- KINGSFORD BRIDGE - south crossing near the capital-to-Suncoast road,
  world (-292, 376).

The terrain bake gets a matching fix so the river genuinely flows under
each bridge (Argent's site is currently a flattened ford from an early
bake) and the road lines up with both ends.

## THE BESTIARY (v3, complete)

Kevin's calls, locked: every species gets a SIGNATURE move (plus a basic
hit), far zones are genuinely deadly to under-leveled players, wildlife
is killable except town pets inside safe zones, and the update ships
zone by zone.

Rig types: QUAD (done - wolf/deer), BIPED (done - goblin/knight),
SERPENT (new: segment chain), WISP (new: floating glow, easy), FLYER
(new: wing flap, swoop, perch), CRAB (quad variant, side-strafe),
INSECT (six-leg quad variant). Every monster below names its rig, its
signature move, stats band, and loot.

### Heartlands (lv 1-5)
- YOUNG GOBLIN - biped (shipped) - sig GOBLIN SHRIEK: calls all goblins
  within 25m to aggro. hp 30, loot: goblin ears, copper coins.
- GIANT RAT - quad, low+long - sig TAIL WHIP: 180-degree knockback
  sweep. hp 26, loot: rat tail.
- WILD BOAR - quad, heavy head - sig TUSK CHARGE: telegraphed line
  charge, knockdown. hp 45, loot: hide, meat. (Also huntable game.)

### Greenwood Marches (lv 4-9)
- TIMBER WOLF - quad (wolf recolor, brown) - sig PACK HOWL: +30 percent
  speed to wolves within 20m for 6s. hp 55, loot: wolf pelt.
- BANDIT WOODCUTTER - biped + hood + axe - sig AXE THROW: ranged
  spinning axe, 12m. hp 70, loot: coins, logs.
- OLD SHELLBACK (rare) - giant tortoise quad - sig SHELL SLAM: AoE
  ground pound. hp 200, loot: shell fragment (future shield mat).

### Frostwild North (lv 8-14)
- WHITE WOLF - quad (wolf, white) - sig FROST HOWL: 4s slow in 12m
  cone. hp 80, loot: white pelt.
- ICE SPRITE - wisp - sig SHATTER: on death, bursts into a 6m chill
  nova - back off before the kill lands. hp 40, loot: ice shard.
- FROST GOBLIN - biped (goblin, blue skin, fur scraps) - sig ICICLE
  TOSS: ranged pierce, brief slow. hp 65, loot: icewood splinters, ears.

### Ironspire Mountains (lv 10-16)
- ROCK CRAWLER - insect - sig BURROW AMBUSH: submerges, erupts under
  the player after 2s (dust telegraph). hp 90, loot: chitin, stone.
- KOBOLD MINER - biped, small, candle hat - sig PICK TOSS: ranged.
  hp 70, loot: coal chunk, copper.
- CAVE BAT - flyer - sig SCREECH: 1.5s blur/disorient, then swoop.
  hp 35, loot: bat wing.

### Sun Coast (lv 6-12)
- GIANT CRAB - crab - sig PINCER GRAB: holds the player 1.5s with
  squeeze damage, break free by mashing move keys. hp 85, loot: crab
  meat, shell.
- SMUGGLER THUG - biped + bandana - sig NET THROW: ranged 3s snare.
  hp 75, loot: coins, rope.

### Windscar Steppe (lv 12-18)
- JACKAL - quad, lean - sig HAMSTRING: bleed DoT + 20 percent player
  slow 5s. hp 85, loot: jackal hide.
- STEPPE RAIDER - biped + horse-clan garb - sig LASSO: pulls the player
  to the raider from 10m. hp 110, loot: coins, wool, saltpeter pinch.
- DUST DEVIL - wisp, large spinning - sig WHIRLWIND: pulls players
  within 8m inward, fling on contact. hp 95, loot: nothing (dissipates).

### Ember Highlands (lv 16-22)
- MAGMA CRAWLER - insect, glowing seams - sig MOLTEN SPIT: ranged glob
  leaves a 4s fire pool. hp 130, loot: magma core, obsidian chip.
- ASH IMP - biped, small, ember eyes - sig CINDER DASH: blink-dash
  through the player leaving a fire trail. hp 90, loot: ash, gold dust.
- KOBOLD GOLD-DIGGER - biped - sig ROCK BARRAGE: three quick ranged
  stones. hp 120, loot: gold nugget (rare), coal.

### Mistfen Wetlands (lv 14-20)
- BOG SERPENT - SERPENT rig - sig CONSTRICT: roots the player 2s with
  DoT, breaks on damage threshold. hp 140, loot: serpent scale, venom sac.
- MUD CRAB - crab, mossy - sig MUD SLING: ranged glob, screen-edge mud
  vignette + slow. hp 100, loot: crab meat, bog iron trace.
- WILL-O-WISP - wisp - sig LURE: drifts away glowing brighter, shocks
  8m nova if followed for 4s. hp 50, loot: wisp mote (reagent).
- FEN LURKER - biped, swamp-thing reeds and moss - sig SWAMP GRAB: an
  arm erupts under the player, rooting 2s (bubble telegraph). hp 160,
  loot: fenroot, rare herbs.

### Sunscorch Barrens (lv 18-24)
- SCORPION - insect - sig VENOM STING: stacking poison DoT (3 stacks
  kills an unprepared low-level). hp 110, loot: stinger, chitin.
- GIANT SCORPION (rare) - insect, x2.2 - sig same, plus BURROW. hp 320,
  loot: grand stinger, glass sand.
- SAND GOBLIN - biped (goblin, dusty wraps) - sig SAND BLIND: 3s heavy
  screen-edge vignette. hp 130, loot: dye pinch, ears.
- BONE JACKAL - quad, skeletal - sig DEATH HOWL: fear - nearby wildlife
  and donkeys flee, players take a burst of shadow damage. hp 150,
  loot: bone, bone meal.
- VULTURE - flyer - circles corpses, swoop attack only when the player
  is below half health (opportunist). hp 60, loot: feathers.

### Shattered Isles (light pass)
- PIRATE SCOUT - biped + tricorn - sig HOOK TOSS: pull-snare. hp 120,
  loot: coins, coral.
- GIANT CRAB - reused from Sun Coast, storm palette.

## WILDLIFE ROSTER

Huntable (HP, flee when hit, drop mats): boar, hare, elk (Frostwild,
antler + hide), snow fox (fur), mountain goat, marmot, steppe sheep
(wool), prairie dog, camel (Sunscorch, hide + meat), ash goat, marsh
deer, gecko. WILD HORSES are killable per the rule but drop only
horsehair, flee at 1.6x player sprint, and never aggro - killing them
is possible, pointless, and hard.

Ambient killable (tiny hp, no loot, scenery with consequences):
squirrels, frogs, herons, dragonflies (fx), gulls, pelicans, small
crabs, owls, hawks, eagles, salamanders, ember moths (fx), vultures
circling high.

PROTECTED (town pets, inside safe zones only): cats, dogs, chickens,
cows, and every civilian NPC's animals. Untargetable inside the zone.

## THE NUMBERS

### Gathering XP + curve
- XP to advance level n -> n+1: floor(75 * 1.085^n). Level 40 ~ half a
  session per level, 90s are a grind, 99 is prestige. Total ~2.8M XP.
- Gather XP = node tier level x 5 (a lv-60 icewood chop = 300 XP).
- Node HP (swings to harvest): tier 1-20 nodes 3, 25-50 nodes 5,
  55-75 nodes 7, 90 nodes 10. Respawns: trees 45s, ore 60s, plants 35s,
  rare (ancient elder, black lotus, ember crystal) 8 min.
- Each harvest yields 1-2 of the material + small chance (5 percent) of
  a bonus rare (bird nest, gem shard, seed - future hooks).

### Tool recipes (crafted at the town forge; zone forges later)
- Copper: 8 copper ore + 2 logs. Iron: 10 iron + 4 logs.
- Steel: 8 iron + 6 coal + 2 oak logs. Obsidian: 6 obsidian + 1 steel
  head + 2 acacia logs. Masterwork: obsidian head + 2 icewood + 1 gold.
- Each tier gathers 15 percent faster and unlocks its tier band.

### Monster stats + level gates
- Damage scales so a zone's monsters two-shot a player 8+ levels under
  band, and feel fair at band. HP as listed per species. XP = hp x 1.1.
- Spawn patterns: CAMPS (3-6 around a landmark, 90s respawn) for
  humanoids; ROAMERS (wander home radius 30m) for beasts; RARES on an
  8-minute timer at fixed lairs. All obey the water wall and stay 60m
  clear of towns and roads.

### Density budgets (per 64m chunk, deterministic by seed)
- Ground clutter (merged, no shadow): 14-22 per chunk, zone-tinted.
- Harvestable nodes: 2-4 per chunk in that zone's spread.
- Monsters: zone total capped (Heartlands ~30, far zones ~45) with
  distance-based activation like the current NPC LOD.

### Skills UI
- Gather popup: +XP splat at the node in skill color (wood green, ore
  orange, forage teal) with a level-up banner + sfx at each level.
- Skills readout: a SKILLS block in the Tab pack panel: three bars with
  level, progress, and next unlock name ("Woodcutting 47 - next: Acacia
  ironbark at 50").

## ROLLOUT (zone by zone, each its own tested push)

1. ENGINE + SKILLS CORE: per-chunk deterministic prop placement,
   harvest gating, XP curve in shared-rules, skills UI, crude tools
   granted, tool crafting at the forge. New rigs built: serpent, wisp,
   flyer, crab, insect (in the model lab first).
2. HEARTLANDS: full dressing + boar, giant rat, goblin shriek.
3. GREENWOOD: old-growth + timber wolves, woodcutters, Old Shellback.
4. FROSTWILD: snow set + icewood + white wolves, sprites, frost goblins.
5. IRONSPIRE: ore country + crawlers, kobolds, bats.
6. SUN COAST: palms, salt, pearls + crabs, smugglers.
7. WINDSCAR: steppe + horses, jackals, raiders, dust devils.
8. EMBER: volcanic set + magma crawlers, imps, gold-diggers.
9. MISTFEN: marsh set + serpents, wisps, lurkers, mud crabs.
10. SUNSCORCH: desert set + scorpions, sand goblins, bone jackals.
11. BRIDGES + ISLES: the two wooden bridges with river/road alignment,
    Shattered Isles light pass, Driftwatch tidy-up.
12. BALANCE PASS: node counts vs trade routes, monster tuning, XP pace.

Each push ships with patch notes and gets tested in a live boot with
screenshots before it goes out, same as the model rewrite.
