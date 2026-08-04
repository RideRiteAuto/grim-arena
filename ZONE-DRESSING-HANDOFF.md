# GRIM WORLD — ZONE GENERATION UPDATE: AGENT HANDOFF

You are taking over one large, well-specified feature: filling Asterra's
empty world with per-zone terrain dressing, harvestable resources, a 1-99
gathering skill system, and zone-appropriate wildlife and monsters.

Read this document top to bottom before touching a single line. It contains
the mission, the codebase's unusual build system, the rules that keep the
project from breaking, the exact scope of the first phase, and the self-audit
you must pass before you report anything as done.

The full design content — every zone's flora, ore, wildlife, monster roster,
signature moves, XP tables, tool recipes and density budgets — lives in
`ZONE-DRESSING-PLAN.md` in the repo root. This document is HOW to build it.
That document is WHAT to build. You need both.

---

## 0. GOLDEN RULES (violating any of these breaks the game for real players)

1. **Never edit `index.html` or `grim-arena-standalone.html` directly.** The
   game source is embedded inside them as a JSON string. Use `repack.py`
   (section 2). Editing the bundle by hand will brick the live site.
2. **Determinism is non-negotiable.** Every prop, node, and spawn must derive
   from a seeded hash of its chunk coordinates. Two players standing in the
   same field must see the identical tree in the identical spot, because
   harvesting syncs by array index. `Math.random()` anywhere in placement
   code is a bug that will desync the world.
3. **Never break the water wall.** Nothing spawns in water. The dry-land test
   already exists and already shipped; use it, do not reinvent it.
4. **Do not touch combat timing, the server sim's attack logic, or NPC
   movement interpolation.** Separate work is in flight there (section 8).
   You are adding content and systems, not changing how monsters fight.
5. **Every push updates the patch notes** via `python3 notes.py` (section 3),
   and gets boot-tested with a screenshot before it goes out. Kevin refreshes
   and reads the notes to know what landed. This is a hard requirement he has
   stated repeatedly.
6. **Ship in small, tested pushes.** One zone or one system at a time. Never
   one big drop.
7. **Brand voice in all player-facing text:** no em dashes anywhere, use
   commas or periods. Plain, grim, honest language. Never invent lore that
   contradicts `ZONE-DRESSING-PLAN.md`.

---

## 1. THE MISSION

Asterra is currently a large, beautiful, and almost entirely empty world.
The map is real, the terrain is baked, the zones exist geographically, but
walking through them feels the same everywhere: scattered generic trees, a
few ore rocks, and monsters that could be anywhere.

When you are done:

- Every zone looks unmistakably like itself. Frostwild is snow-dusted pines
  and lichen; Ember is charred snags and ash drifts; Mistfen is willows and
  reeds and drifting fen-lights.
- Every zone produces something no other zone has, and lacks something it
  must import. No zone is self-sufficient. This is the trade economy and it
  is load-bearing canon, not flavor.
- Three gathering skills (WOODCUTTING, MINING, FORAGING) each run 1 to 99 on
  a shared XP curve, gated by both skill level and tool tier, with the best
  tools in the game requiring materials from opposite ends of two continents.
- Every zone's creatures match its level band, and every species has a
  SIGNATURE move that makes fighting it feel different from fighting anything
  else.

The design intent Kevin locked in, in his words: signature move per species,
real level gates, wildlife killable except town pets, and the update ships
zone by zone.

---

## 2. THE CODEBASE (unusual — read carefully)

**The entire game is one self-contained HTML bundle.** No build system, no
node_modules, no modules, no framework.

- `index.html` and `grim-arena-standalone.html` are identical bundles. Both
  are committed, both must always be updated together. GitHub Pages serves
  `index.html`.
- The real game source lives EMBEDDED inside the bundle as a JSON string at
  roughly line 390.
- `repack.py` is the ONLY edit path:
  - `python3 repack.py extract` writes the editable source to
    `/tmp/game-src.html`
  - `python3 repack.py pack` re-embeds it into BOTH bundles and verifies a
    byte-exact round trip
  - It escapes `</` on the way in. That escaping is load-bearing: an
    unescaped `</` terminates the script tag and bricks the page.
- `Grim Arena.dc.html` is a STALE legacy artifact. Never edit it, never
  rebuild from it.
- The game is a single large class. three.js r160 loads from unpkg via
  importmap. World init runs in `boot()` after three.js arrives, NOT in the
  constructor. `window.__grim` is the live debug handle.

**How to make an edit, every time:**

1. `python3 repack.py extract`
2. Write a Python patch script that replaces exact-string anchors in
   `/tmp/game-src.html`. **Always `assert src.count(old) == 1` before
   replacing.** Anchors go stale fast: re-grep the current text every time,
   never trust an anchor from an earlier session or from this document.
3. **A patch script must write the file only once, at the very end.** If an
   assert fails midway, nothing is written and no partial edit persists.
   This has bitten previous agents: a mid-script assert failure silently
   rolled back every earlier replacement in that script.
4. `python3 repack.py pack`
5. Boot-test (section 4), screenshot, then commit and push.

**Files that sync into the bundle automatically during `pack`:**

- `shared-rules.js` — the single source of truth for anything the client and
  the server must agree on (move tables, world radius, aggro ranges, tick
  rates). It is injected into the game source AND into `relay-worker.js`.
  **The XP curve and all node/tool tier tables belong here**, so any future
  server-side validation cannot disagree with the client.
- `worldgen.js` / `worldgen-data.js` — the baked terrain. If you change
  anything that alters world generation, you must bump `WORLD_GEN` in
  `shared-rules.js`, or clients running the old bake will place props in
  the wrong spots and the server will flag a world version mismatch.

---

## 3. HOW IT SHIPS

One push to `master` deploys everything:

1. GitHub Pages redeploys the game (about 1 minute).
2. Cloudflare Workers Builds auto-deploys `relay-worker.js` as the Worker
   named `grim-arena` (about 2 to 3 minutes). The `name` field in
   `wrangler.jsonc` must stay `grim-arena` or builds fail.

**Patch notes are mandatory on every push:**

```
python3 notes.py "## <Month Day, Year> (<tag>) — <short title>" "<body>"
```

It prepends the entry and auto-prunes to the newest 12 so the file never
becomes clutter. Write the body in plain language, honest about what was
broken and what changed. Kevin reads these directly.

**Pushing:** the sandbox's git proxy may refuse the repo. If a normal
`git push` fails with an authorization error, use the explicit-header form:

```
TOKEN=$(sed -n 's#https://[^:]*:\([^@]*\)@github.com#\1#p' ~/.git-credentials | head -1)
git -c http.extraHeader="Authorization: Basic $(printf 'RideRiteAuto:%s' "$TOKEN" | base64 -w0)" \
    push https://github.com/RideRiteAuto/grim-arena.git master
git fetch https://github.com/RideRiteAuto/grim-arena.git master:refs/remotes/origin/master
```

That last fetch matters: without it the local tracking ref goes stale and
you will get false "unpushed commits" warnings for work that already shipped.

---

## 4. HOW TO TEST (do this before every push, no exceptions)

There is a working Playwright harness pattern. Serve the built bundle
locally with the three.js importmap rewritten to a local copy, launch the
pre-installed Chromium, click PLAY AS GUEST, then drive and inspect the game
through `window.__grim`.

```js
const browser = await chromium.launch({
  executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--use-gl=swiftshader', '--no-sandbox']
});
```

Wait for `window.__grim._chunks.size > 50` before interacting.

**The harness runs at roughly 20 percent of real time.** Budget generous
waits, and never conclude "the animation is not playing" or "nothing spawned"
from a short wait. Prefer logic assertions (read the actual arrays and
counts through `__grim`) over visual timing.

**Safe zones suppress combat.** Town has radius 24/26 around the origin and
the camp sits at (41, 31) with radius 15. Any spawn or combat test must be
run well outside those, or you will measure nothing and conclude wrongly.

**Determinism test you must write and keep passing:** boot the game twice
with the same seed, walk to the same chunk, and assert the generated prop
list is byte-identical (position, type, rotation, scale). If it is not,
stop and fix it before building anything on top.

---

## 5. WHAT ALREADY EXISTS (build on these, do not rebuild them)

- **Model kit:** `loftMesh(sections, sides, colorTop, colorBelly, material)`
  builds a lofted tube with vertex colors and end caps, and normalizes
  section order so faces always wind outward. `furTex(base, dark)` makes
  cached fur. `jitterGeo(geo, amount, seed, ys)` displaces vertices hashed by
  ROUNDED POSITION, so duplicated corners of non-indexed geometry move
  identically and never crack open at the seams. Use these for every new
  model. Hand-rolled geometry will look off-style and will crack.
- **Quadruped rig contract:** entities carry
  `qr = { legs:[{hip,knee,front}], neckG, head, jaw, ears, tailSegs, body, baseY }`
  and `poseQuadRig(e, dt)` owns every joint, running at the end of the frame.
  Wolf and deer are shipped reference implementations. Copy their structure.
- **Biped/fighter contract:** parts must include
  `{ upper, torso, head, armR, armL, legR, legL, hand, handL, weapon slots,
  ward, orb, crest, capePiv, bladeTip, mount }`. Goblin and the knight are
  shipped references. A custom model that omits any of these will throw when
  the animation code reaches for it.
- **Resource/harvest system:** resources are
  `{ kind, g, fell, stump, studs, hp, max, dead, respawn }`. Trees hinge and
  fall from a stump; ore nodes go to a visible empty state (nuggets vanish,
  boulder stays). `resourceDepleted()` / `resourceRespawned()` are shared by
  all four code routes (local swing, client-predicted swing, relayed hit,
  legacy feed) — **register new node types through these, never with parallel
  logic**, or nodes will desync between players.
- **Skills page:** a K-key skills panel already exists with 7 skills, a
  level curve `lvl(xp) = min(99, floor((xp/60)^0.6)+1)`, progress bars, XP
  remaining, and tooltips. WOODCUTTING and MINING are already in it. You are
  extending this, not replacing it. Note the plan's XP curve
  (`floor(75 * 1.085^n)`) differs from the shipped one — see section 9,
  question 1.
- **Chunk streaming:** `stepTerrain()` streams 64m chunks at two detail
  levels around the player and disposes distant ones. Prop placement must
  hook into chunk load/unload and dispose its geometry the same way.
- **Performance safeguards:** `tuneShadows()` strips shadow casting from tiny
  meshes, decor lights are capped to the nearest five, distant monsters are
  culled, and static scenery has `matrixAutoUpdate` frozen. **New props must
  arrive frozen and merged** — see section 6's performance budget. The scene
  already carries about 5,300 meshes and roughly 1,050 draw calls; a careless
  clutter pass will double that and make the game unplayable.

---

## 6. PHASE 1 — ENGINE AND SKILLS CORE (your first deliverable)

Do not start any zone's art until all of this is done, tested, and pushed.
Phase 1 is three pieces plus a model-lab prerequisite.

### 6a. Deterministic per-chunk dressing engine

- A function that, given chunk coordinates and the zone that chunk belongs
  to, returns a deterministic list of props: ground clutter, harvestable
  nodes, and spawn points.
- Seeded from a hash of `(chunkX, chunkZ, WORLD_GEN)`. Same inputs, same
  output, on every machine, forever.
- Respects: the water wall, road corridors, and a 60m exclusion around town
  safe zones.
- **Ground clutter must be MERGED into a small number of meshes per chunk**
  (one per material is the target), with `castShadow = false` and
  `matrixAutoUpdate = false`. Density 14 to 22 per chunk as specified in the
  plan, but merged geometry means that costs a handful of draw calls, not
  twenty.
- Harvestable nodes are separate objects (they animate and change state), 2
  to 4 per chunk, registered through the existing resource system.
- Unloading a chunk must dispose its prop geometry exactly as terrain does.

**Performance budget, and you must measure it:** after the dressing engine
is live in the Heartlands, total draw calls must stay under 1,400 and total
scene meshes under 7,000 with the player standing in a dressed area. Report
the measured numbers in your patch notes. If you exceed them, merge harder
or reduce density; do not ship over budget.

### 6b. Zone identification

There must be a single function that answers "which zone is this world
position in" and it must agree with the map. Zones: Heartlands, Greenwood
Marches, Frostwild North, Ironspire Mountains, Sun Coast (Valewold);
Windscar Steppe, Ember Highlands, Mistfen Wetlands, Sunscorch Barrens
(Ashmar); Shattered Isles and Driftwatch. Everything downstream keys off
this, so get it right and make it cheap to call.

### 6c. Gathering skills core

- WOODCUTTING, MINING, FORAGING (FORAGING is new; the other two exist).
- XP curve and every tier table live in `shared-rules.js`.
- A node requires BOTH a minimum skill level AND a minimum tool tier. When
  the player cannot harvest something, the message must say exactly which
  requirement failed and what they need. Never a generic refusal.
- Higher skill and better tools gather slightly faster.
- Every player is granted crude tools (tier 1) on first login.
- Tool crafting at the town forge for tiers 2 through 6, using the recipes
  in the plan. The recipes are the trade economy: do not simplify them.
- Gather XP splats in skill color (wood green, ore orange, forage teal) and
  a level-up banner with sound.
- Skills persist in the existing cloud save alongside the rest of the
  character.

### 6d. Model lab: five new rigs, proven before use

Five rig types in the bestiary do not exist yet: SERPENT (segment chain),
WISP (floating glow, easiest), FLYER (wing flap, swoop, perch), CRAB (quad
variant with side-strafe), INSECT (six-leg quad variant).

Build each one in `model-lab/` as a standalone turntable page first, exactly
as `model-lab/wolf.html` was built. Get each one looking right in isolation,
with its idle, move, and attack animations, before a single one is wired
into the game. A rig that ships broken means every monster using it ships
broken.

---

## 7. PHASES 2 THROUGH 12

Each is its own tested push with its own patch notes. Order is fixed
(easiest and most-visited zones first, so problems surface early):

2. Heartlands — full dressing, boar, giant rat, goblin shriek
3. Greenwood Marches — old-growth timber, timber wolves, woodcutters, Old Shellback
4. Frostwild North — snow set, icewood, white wolves, ice sprites, frost goblins
5. Ironspire Mountains — ore country, rock crawlers, kobold miners, cave bats
6. Sun Coast — palms, salt flats, pearl beds, giant crabs, smugglers
7. Windscar Steppe — steppe, wild horses, jackals, raiders, dust devils
8. Ember Highlands — volcanic set, magma crawlers, ash imps, gold-diggers
9. Mistfen Wetlands — marsh set, bog serpents, wisps, fen lurkers, mud crabs
10. Sunscorch Barrens — desert set, scorpions, sand goblins, bone jackals
11. Bridges and isles — Argent Bridge (-472, -364) and Kingsford Bridge
    (-292, 376) as proper wooden builds with river and road alignment, plus
    a light pass on the Shattered Isles and Driftwatch
12. Balance pass — node counts against trade routes, monster tuning, XP pace

Per-zone content (species, signature moves, HP, loot, flora, ore, level
bands) is fully specified in `ZONE-DRESSING-PLAN.md`. Follow it. If you
believe something in it is wrong, say so and propose the change rather than
quietly deviating.

---

## 8. IN-FLIGHT WORK — DO NOT TOUCH

Combat timing and monster movement are being actively fixed in a parallel
effort. Stay out of these files and functions:

- The announced-attack path on the client (`onAttackEvent`, `judgeMyDodge`,
  the swing clock anchor) and `killNpcVisual`.
- The snapshot handler `onNpcSnap` and the NPC position interpolation in the
  frame loop.
- The attack decision block in `sim.js` and its client mirror `driveAI`.

**Known open issue you should be aware of but must not fix:** under server
simulation there is no separation between monsters and players, so monsters
walk into the player's body and stand inside them, which also hides their
swing behind the player model. That is on the combat track, not yours. If
your spawn work appears to make it worse or better, note it and move on.

If your work genuinely requires a change in one of those areas, stop and
raise it rather than editing around it.

---

## 9. OPEN QUESTIONS FOR KEVIN (get answers before Phase 1 ships)

1. **XP curve conflict.** The shipped skills page uses
   `lvl(xp) = min(99, floor((xp/60)^0.6)+1)`. The plan specifies
   `floor(75 * 1.085^n)` per level, totaling about 2.8M XP for 99. These are
   different curves. Recommendation: adopt the plan's curve as the single
   formula in `shared-rules.js` and migrate the existing WOODCUTTING and
   MINING XP values through it, since the plan's curve was designed around
   the node tiers and gather rates. Confirm before migrating live saves.
2. **FORAGING vs the existing skill list.** The skills page currently shows
   7 skills. Adding FORAGING makes 8 and changes the TOTAL LEVEL cap from
   693 to 792. Confirm that is wanted.
3. **Wild horses.** The plan calls them the world's only mount source but
   says "look, don't tame, for now." Confirm they stay purely decorative in
   this update.

Do not block all progress waiting on these: the model lab work (6d) and the
dressing engine (6a, 6b) are unaffected. Only the skills core (6c) depends
on question 1.

---

## 10. SELF-AUDIT — pass every line before reporting done

Run this against your own work, honestly, before you tell Kevin anything is
finished. If a check fails, fix it and run the list again.

**Build integrity**
- [ ] Every edit went through `repack.py extract` / `pack`, never direct
      bundle editing
- [ ] `pack` reported a verified byte-exact round trip
- [ ] Both `index.html` and `grim-arena-standalone.html` are updated and
      committed
- [ ] No `Math.random()` anywhere in placement, spawn, or generation code
- [ ] `WORLD_GEN` bumped if anything altered world generation

**Correctness**
- [ ] Booted the game, clicked through to gameplay, no console errors
- [ ] Same-seed determinism test passes: identical props in identical spots
      across two fresh boots
- [ ] Nothing spawns in water, on roads, or inside town safe zones
- [ ] New harvestables register through `resourceDepleted` /
      `resourceRespawned`, not parallel logic
- [ ] Gathering a node with too low a skill OR too low a tool tier gives a
      message naming the exact missing requirement
- [ ] Skills persist across a logout and login

**Performance (measured, not assumed)**
- [ ] Draw calls under 1,400 and scene meshes under 7,000 while standing in
      a fully dressed area, numbers recorded in the patch notes
- [ ] All ground clutter is merged, shadow-free, and
      `matrixAutoUpdate = false`
- [ ] Chunk unload disposes prop geometry (walk a long loop, confirm mesh
      count returns to baseline instead of climbing)

**Content fidelity**
- [ ] Every zone's flora, ore, wildlife and monsters match
      `ZONE-DRESSING-PLAN.md` exactly
- [ ] No zone is self-sufficient: each still lacks what canon says it imports
- [ ] Every new species has its signature move implemented, not just a
      reskinned basic attack
- [ ] Every new rig was proven in `model-lab/` before being wired in
- [ ] No em dashes in any player-facing string

**Shipping**
- [ ] Patch notes entry added via `notes.py`
- [ ] Screenshot taken of the new content in the live boot
- [ ] Pushed, and `git status` is clean against `origin/master` after a fetch
- [ ] Did not touch any file or function listed in section 8

**Honesty check**
- [ ] Anything you could not verify is stated plainly as unverified, with
      the reason, rather than reported as working
