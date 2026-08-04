# Grim World — Asterra World Generator: the buildable plan

Written Aug 4, 2026, after Kevin's map v2 approval. This is the blueprint for
replacing the current 168m-radius world with the full two-continent world of
Asterra, generated to match "Asterra World Map v2.html" so that same map can be
used as the in-game world map. Companion docs: SERVER-SIM-PLAN.md (server
simulation), "Asterra World Reference v2" (zones, resources, trade packs, in
Drive), GAME-HANDOFF.md (how the bundle is built and shipped).

Decisions on record (Kevin, Aug 4):

- Scale: LARGE. ~4 meters per map pixel → world is ~6,600m x 4,000m. Running
  across one continent takes roughly 20-30 minutes. Mounts, boats, and trade
  friction are meant to matter.
- Old content: FRESH START. The Northreach layout is retired. Towns are placed
  from scratch at the map's settlement sites. (NPCs, items, bank, quests as
  SYSTEMS survive; their placement in the world is redone.)
- Phasing: TERRAIN FIRST. Phase order below; each phase ships alone and is
  playable. Boats and housing come after the world is walkable.
- The map is the source of truth. The generator must reproduce the map's
  coastlines, zones, mountains, rivers, roads, and settlement positions —
  not approximate them with free-running noise.

---

## 0. The core idea: bake the map, detail with noise

Two-layer terrain. The MACRO layer is baked offline from the actual map SVG:
where land is, which zone you are in, how high the ground roughly is, where
rivers run. The MICRO layer is seeded noise added at runtime: hills, bumps,
cliff detail, prop placement. Macro guarantees the world matches the map.
Micro makes it feel natural and costs zero storage.

Everything is a pure deterministic function of (x, z) plus baked data plus
WORLD_SEED — the same discipline as `groundY` and shared-rules today. The
client and the Cloudflare worker run the SAME code on the SAME data, injected
by repack.py exactly like shared-rules.js is now. No mesh raycasts anywhere.

### Coordinates

- Map space: the SVG's 1650 x 1000 viewBox.
- World space: meters. `world = (mapPx - mapOrigin) * 4`. One fixed affine
  transform, used by the bake, the runtime, and later the world-map player
  arrow. World is roughly x ∈ [0, 6600], z ∈ [0, 4000]; we recenter so the
  capital site is near a round number.
- Sea level is y = 0. Terrain below 0 is seabed / riverbed.

---

## 1. The bake step (offline tool, committed to the repo)

New file `bake_world.py` (same spirit as repack.py — no build system, run by
hand, output committed). It parses `Asterra World Map v2.html` directly:

1. **Land mask + distance field.** From the two continent `<path>`s and the
   island paths. Signed distance to coast (positive inland, negative at sea)
   at ~8m resolution. This drives beaches, coastal falloff, and the fjorded
   coastline shape — the jagged map coastline IS the world coastline.
2. **Zone ID map.** From the region overlay paths (Frostwild, Ironspire,
   Heartlands, Greenwood, Sun Coast, Windscar, Ember, Mistfen, Sunscorch,
   Shattered Isles, Driftwatch). Every world point knows its zone. Zone edges
   get a blend band (~60m) so biomes fade into each other.
3. **Elevation control grid.** Coarse (~16m res) target elevation built from:
   zone base heights (Heartlands low rolling, steppes mid, coasts near zero)
   + mountain fields around the map's peak-glyph clusters (Ironspire and
   Ember Highlands become real ranges, tallest at the glyph centers) + a
   basin pulled down around Lake Argent. Smoothed so macro slopes are sane.
4. **Hydrology.** The Great River and Cinder Run traced as polylines with a
   width profile (narrow streams at the headwaters → wide navigable stems
   exactly per the reference doc: Lake Argent→delta, marshes→Fenmouth).
   Lake Argent as a polygon. Minor mountain streams as narrow non-navigable
   decorations. Baked as a distance-to-river field + depth/width field.
5. **Roads and crossings.** The trade-road polylines, the two bridges, the
   passes (Highpass, Frost Gate, Ember Gap). Roads bake as a distance field
   used to flatten terrain slightly and blend a dirt texture; bridges are
   placed props with colliders.
6. **Anchor points.** Every settlement, port, and chokepoint's world
   coordinate, exported as a table the game reads to place towns.
7. **Housing districts.** One large NON-rectangular polygon per zone (hand
   authored in the bake tool config, near each hub town, on viable ground),
   baked into a district mask. Reserved in phase 1 (kept clear of trees and
   spawns) even though claiming ships later, so land does not shift under
   players when housing arrives.

Output: `world-data.bin` — all layers quantized (u8/u16) and deflate-packed,
embedded in the bundle as base64 the same way audio already is, and included
in the worker build. Budget: under ~250KB compressed so the worker stays well
inside free-tier script size. Bake is versioned: `WORLD_GEN_V` in shared
rules; the manifest fingerprint (already in the game) extends to cover it so
client and server can never disagree about the world silently.

## 2. Runtime terrain function (shared client + worker)

```
worldHeight(x, z):
  m  = sample(elevationControl, x, z)            // bilinear macro height
  d  = sample(coastDistance, x, z)
  m *= coastFalloff(d)                            // land slides under sea level at the coast
  n  = fbm(seed, x, z) * roughness(zoneId(x,z))   // micro detail: 2-3 octaves,
                                                  // big in mountains, gentle in farmland,
                                                  // near-zero in marsh/desert flats
  h  = m + n
  h  = carveRiver(h, riverDist(x,z), riverDepth)  // rivers cut below 0, banks ease down
  h  = flattenNear(roads, towns, districts)       // same trick as today's flat() sites
  return h
```

Pure, allocation-free, cheap (a few array samples + noise). It replaces
`groundY` everywhere via one switch, so every existing system (NPC walk,
props, donkey, sacks, decals) keeps working untouched. `WORLD_R` clamp is
replaced by "you cannot swim past the charted border" — fog walls at the
uncharted edges, matching the map's fog.

`waterDepth(x, z) = max(0, waterSurface(x,z) - worldHeight(x,z))` where
waterSurface is 0 at sea and the river's baked surface height inland
(rivers step gently downhill in long flat reaches so boats work later).

## 3. Streaming (this is what makes HUGE possible)

The world is ~300x the current one's area; nothing can be built all at once.

- Chunk grid: 64m tiles. Around the player: detailed ring (~4 chunks out,
  2m vertex resolution, full props + colliders) → coarse ring (~8 chunks,
  8m resolution, no props) → beyond that, nothing but sky, sea plane, and
  distant mountain silhouettes (a cheap prebaked skyline mesh per zone).
- Chunks generate on a budget (one or two per frame max) from the pure
  function; leaving range disposes geometry. Nothing about a chunk is
  stored — it regenerates identically every time from seed + bake data.
- Props (trees, rocks, grass, cacti, reeds — per-zone catalogs) place
  deterministically: `hash(seed, chunkX, chunkZ, i)` picks species, position,
  scale; rejected on slope, in water, on roads, in towns, in housing
  districts. One InstancedMesh per species per chunk keeps draw calls flat.
  Harvestable trees/rocks register into the existing resource system by
  stable ID `(chunkX, chunkZ, i)` — the same ID on every machine and on the
  server, so multiplayer chopping/mining stays in sync.
- This chunk grid IS the interest-management seam SERVER-SIM-PLAN already
  calls for: the DO filters snapshots by chunk distance, and monster spawn
  tables later key off zone + chunk.

## 4. Water: swimming now, boats next

Phase 1 (swimming):
- `waterDepth > 1.1m` → swim state: slower move, no sprint, no attacks or
  blocking, gentle stamina drain with a drowning tick at zero (souls-lite,
  forgiving numbers). Camera and animations stay simple: bob the player at
  the surface, hide the legs. Shallow water just splashes and slows slightly.
- Water renders as two things: one big sea plane at y=0 with the existing
  low-poly material style, and river surface strips generated per chunk from
  the baked river field.

Phase 2 (boats):
- A boat is a mount (the donkey pattern generalizes): board at a dock,
  WASD drives it, constrained to `waterDepth > draft`. Rowboat (1 player,
  rivers + coast) first; the bigger cargo ship for trade packs comes with
  the trade system later. Navigability is data we already baked — wide
  stems of Great River / Cinder Run + open sea, exactly per the reference.
- Multiplayer: a boat is just a moving entity in the existing net protocol;
  the driver simulates, passengers attach. (Same rule as mounts today.)

## 5. Housing districts + the claim grid (phase 3, designed now)

- **Global claim grid**: the XZ plane divided into 2m x 2m cells with integer
  coords `(gx, gz) = floor(world / 2)`. The grid is flat 2D — elevation does
  not bend it. A plot is a SET of cells (so plots can be any shape), and
  buildings later snap to this same grid. This is the "underlying grid that
  works even with elevation changes": claims are footprints; terrain height
  just drapes under them.
- **Districts**: each zone's baked housing polygon (large, organic, NOT a
  rectangle — it follows terrain and the zone's character). A cell is
  claimable iff its center is inside the district AND mean slope in the cell
  is under the build threshold AND `waterDepth == 0` AND it is unclaimed.
  Districts are sized generously (hundreds of plots each) and sit near the
  hub town + a road, per zone.
- **Mailbox claim flow**: craft/carry the mailbox item → place it on a valid
  cell inside a district → it anchors a claim of tier-sized area (starter
  ~10x10 cells = 20m x 20m, bigger mailboxes claim more later). Placement
  preview shows green/red cells live. Click a mailbox → owner, tier, tax due.
- **Persistence split (already agreed)**: Supabase owns permanent claims —
  new table + RPCs in the locked-down style of grim_login/grim_save:
  `plot_claim(u, h, district, cells)`, `plot_release`, `plot_pay_tax`.
  The Durable Object caches the claim map for live validation (two players
  claiming the same cells race at the DO, not at the database) and
  broadcasts claim changes. Tax/foreclosure timers run on storage alarms
  like respawns do now. The farming patch is the first placeable and rides
  the same grid.
- Once housing ships, the bake data under districts is FROZEN: any future
  WORLD_GEN_V change must keep district terrain byte-identical (regression
  test in the bake tool) so nobody's plot geometry ever shifts.

## 6. Towns, spawns, and the fresh start

- Placement comes from the baked anchor table: THE CAPITAL (SE shore of Lake
  Argent) plus hubs/ports per the map: Frostwatch, Frosthaven, Ironspire
  Hold, Timberdown, Suncoast Harbor, Windscar Post, Ashport, Ember Hold,
  Fenmouth, Duskwell Oasis, Driftwatch Isle.
- Phase 1 builds the CAPITAL as the one real town (bank booth + teller,
  login spawn point, safe zone) and marks every other site with a simple
  waystone + name sign + safe-zone circle so the world is legible end to
  end. Towns get built out one at a time in later passes.
- New characters and existing saves both spawn at the capital on first login
  after the switch (saved positions from the old world are outside the new
  world's bounds and already fall back to spawn by the existing rule).
- Monster spawn tables move to zone-keyed data (goblins/wolves per biome,
  bosses at authored lairs). SAFE zones list in shared-rules grows to all
  town sites.

## 7. The world map UI

The Asterra SVG ships in the bundle as the world map screen (M key). Player
arrow = the same affine transform from section 0 applied to player position,
drawn on top; friends' arrows ride existing presence data. This is the "later
task" Kevin flagged — the transform work is free because the whole world is
built in map coordinates. The minimap redesign in the UI backlog reuses the
zone-color data for a live local map.

## 8. Phases and acceptance

- **A. Bake + terrain core.** bake_world.py, world-data.bin, worldHeight,
  chunk streamer, sea plane, biome ground colors, fog borders, capital spawn.
  DONE when: walk (or dev-teleport) capital→Suncoast with no seams, stable
  60fps on Kevin's machines, determinism test passes (client and worker hash
  identical heights on a 10k-point sample grid).
- **B. Water + swimming + rivers.** Carved rivers, lake, swim state,
  drowning, bridges you can cross, roads visible.
  DONE when: you can swim the Great River, cross both bridges, and cannot
  leave the charted world.
- **C. Dressing + towns + map.** Per-zone props with harvest sync, waystone
  towns, safe zones, monster re-seeding, world map screen with player arrow.
  DONE when: a friend joins, you both chop the same tree in Greenwood and
  fight the same wolves in Frostwild, and patch notes ship.
- **D. Boats.** Rowboat + docks at ports.
- **E. Housing.** Districts live, mailbox claims, farming patch, Supabase
  plot schema + DO claim cache.

Each phase = small pushes to master, PATCH-NOTES.md entry on top, honest
about breakage, per house rules.

## 9. Risks and their answers

- **Worker size / free tier**: bake data budgeted ≤250KB compressed; the
  worker only needs the coarse layers (it never renders), so its slice can
  be smaller still.
- **Determinism drift**: single shared module + fingerprint over
  WORLD_GEN_V + data hash; refuse to join a world whose hash differs
  (message already exists for proto mismatch — same pattern).
- **Perf on big terrain**: chunk budget + instancing + no per-frame
  allocation in worldHeight; test on the weakest machine that currently
  plays (ELDER's).
- **Old saves**: positions fall back to spawn (existing rule); inventory,
  bank, skills, quests untouched. Quest steps that referenced old-world
  landmarks get re-pointed to capital NPCs in phase C.
- **The bundle grows**: +map SVG +world data ≈ 400-500KB. Fine for GitHub
  Pages; repack.py round-trip test already guards corruption.
