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

## Build order (once Kevin approves)

1. Tree scale pass (+25 percent) and the shared prop/dressing engine:
   deterministic per-chunk placement with per-zone catalogs, merged
   clutter, harvestable registration.
1b. Gathering skill core: XP curve in shared-rules, skill save fields,
   XP popups and a skills readout, level + tool gating on every
   harvestable, crude starter tools granted on login.
2. Valewold zone catalogs (Heartlands, Greenwood, Frostwild, Ironspire,
   Sun Coast) - trees, clutter, nodes.
3. Ashmar zone catalogs (Windscar, Ember, Mistfen, Sunscorch).
4. Wildlife + monster spawn tables per zone (zone-keyed, water-walled,
   level-banded as above).
5. The two wooden bridges + river/road alignment fix.
6. Balance pass: node counts per zone tuned so trade actually has to
   happen (no zone can feed, arm, and build from its own ground).
