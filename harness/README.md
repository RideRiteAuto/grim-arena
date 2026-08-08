# Harness and patch scripts

Tooling, not game code. None of this is served to players.

- `serve.js` serves the built bundle on 127.0.0.1:8123 with the three.js
  importmap rewritten to a local copy, so a boot test needs no network.
- `boot.js` boots the bundle, clicks PLAY AS GUEST, enters gameplay and reports
  console errors plus live readings off `window.__grim` (chunk count, mesh
  count, draw calls, skills, tool tiers).
- `skills.js` drives real harvests through the real code path and checks the
  gate messages, tool tier detection and the save migration.
- `ratrig.js` proves THE PLAGUE RAT is driven by `poseQuadRig` and not the biped
  path: asserts the `qr` contract, steps the rig by explicit `dt` with the render
  loop cancelled, checks the knees and hips actually travel, that the run gait is
  wider than the walk, that the jaw opens on the bite, and that the tail is a
  parented chain. Writes idle / walk / run / bite from three angles to
  `/tmp/ratrig/`. Use it as the template for any future creature-rig test: read
  joint values, do not judge a frame by eye alone.
- `plants.js` builds all nine foraging kinds through the real `makeZonePlant` and
  asserts they are genuinely different geometry rather than one mesh recoloured:
  fingerprints the vertex buffer of each, checks no two match, checks each is
  deterministic for a fixed seed and varies with the seed, checks each is exactly
  ONE mesh carrying vertex colours (the draw-call and `_nodeMat` contract), holds
  a per-plant vertex budget, and checks the picked state. Writes a portrait of
  every kind and its picked state to `/tmp/plants/`.
- `bridges.js` proves the deck ends where the ground is. Runs the real
  worldgen here in node for terrain, walks each of the six crossings in 5cm
  steps through the game's own `bridgeDeckY` to find where the deck really
  stops, and asserts: it answers at the exact endpoints, both ends sit on the
  ground to within 5cm, the deck is never buried, and the ribbon AS BUILT
  descends monotonically to each end. Then checks the torches: one shared
  lathed flame geometry, at least eight of them round the town square, and no
  emissive lamp balls left behind. Verified to FAIL on the bundle before patch
  27 with 23 assertions, so it is a real regression test and not a tautology.
- `savecurve.js` proves a login cannot eat your skill XP. Drives the real
  `charSave` / `applySaveBlob` pair through ten save-and-log-back-in cycles and
  asserts nothing moved, checks the blob carries `v: 2` and its curve stamp,
  and checks a genuine `v: 1` save still converts exactly once and keeps a
  `skillXpV1` backup. Verified to FAIL on the bundle before patch 29, where it
  reproduced Kevin's exact numbers (woodcutting 11, 7, 5, 4, 3), so it is a
  real regression test and not a tautology.
- `ground.js` proves a distant NPC stays on the terrain and stops blinking at
  the cull line. Parks an NPC on genuinely uneven ground inside the thinning
  band, reads `g.position.y` frame by frame, and fails if ANY frame lands at
  sea level; then sweeps it back and forth across the 90m line and counts
  visibility flips. Verified to FAIL before patch 29 with 20 of 30 frames at
  sea level, so it is a real regression test and not a tautology.
- `interp.js` proves position playback survives network jitter. Drives the real
  `onNpcSnap` and the real `tick()` against a monster walking a dead straight
  line at a constant speed, sampled every 100ms exactly but DELIVERED early,
  late, out of order and with one packet dropped, then measures the speed the
  player would actually see. Deterministic: render loop frozen, `Date.now`
  faked, fixed `dt`, so it is not measuring SwiftShader. Verified to FAIL
  before patch 30 with 40 percent speed variance, 14 sprints and 2 dead stops;
  passes at 1.6 percent with none of either.
- `combat.js` proves the playout buffer did NOT move the moment a blow lands.
  Announces a real swing through `onAttackEvent` and records the exact instant
  `judgeMyDodge` resolves it, planted and moving. 450ms after the swing begins,
  which is the wind-up, on both sides of patch 30. Also reports how far the
  drawn body is from the server's at the damage instant: zero when the attacker
  is planted, which is what the server sim actually does. Fake `performance.now`
  as well as `Date.now`, because the swing clock runs on the former; and the
  snapshot fixture has to report the attack while it is playing, since feeding
  idle rows through a swing correctly cancels it.
- `patches/` holds the exact scripts used to edit `/tmp/game-src.html`, one per
  shipped change, so every bundle edit is reproducible and reviewable.
- `phase0-baseline.js` byte-diffs the terrain/dressing pure-function outputs
  (`chunkProps`, live chunk-mesh `color`/`aTile`/`aMix`/`position`
  attributes, direct `terrainColor`/`groundSurface` samples, `bridgePad`
  samples along every baked bridge) between two boots. Written to verify
  patch 85.920 (Phase 0 of `TERRAIN-WORKER-OFFLOAD-PLAN.md`, the module-level
  extraction) made zero behavior change, and kept around as the permanent
  parity check that plan's later phases call for (Sec 6): run once as
  `node harness/phase0-baseline.js before`, make the change, run again as
  `node harness/phase0-baseline.js after`, diff `/tmp/phase0-before.json`
  against `/tmp/phase0-after.json`. Most useful for a future three.js version
  bump (the worker's vertex/normal math is re-derived from three@0.160.1's
  own source) or for Phase 1's worker-vs-main-thread comparison.

Run:

    node harness/serve.js &
    node harness/boot.js
    node harness/skills.js
    node harness/ratrig.js
    node harness/plants.js
    node harness/bridges.js
    node harness/savecurve.js
    node harness/ground.js
    node harness/interp.js
    node harness/combat.js

## `dressing.js` determinism failures here are usually not real

`determinism.identical: false` with matching node lists but a clutter count
ratio near 0.45 is `stepPerf` auto-degrading the graphics mid-test: LOW thins
ground cover to 45 percent, and SwiftShader is slow enough to trip the 27ms
threshold on one boot and not the other. Compare `firstDiff.a` and
`firstDiff.b` before believing it: if the entries that ARE present are
byte-identical and only the counts differ, placement is deterministic and the
graphics tier moved underneath you. Reproduced on unmodified `origin/master`.

## Node dependencies

The browser harnesses need `three` and `playwright` installed in the PARENT
directory of the repo (`serve.js` resolves `../node_modules/three/build/three.module.js`):

    cd .. && npm install three@0.160.1 playwright

**Pin three to 0.160.x.** The bundle's importmap expects the single-file r160
build. Newer three splits `three.module.js` and `three.core.js`, `serve.js` only
maps the first, and the page then dies on a 404 with `window.__grim` present but
`scene` undefined - which looks exactly like a broken patch and is not one.
Chromium comes from `/opt/pw-browsers/`; do not run `playwright install`.

The harness runs at roughly 20 percent of real time. Never judge an animation
or a spawn by how long it took; read the arrays.
