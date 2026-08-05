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
- `patches/` holds the exact scripts used to edit `/tmp/game-src.html`, one per
  shipped change, so every bundle edit is reproducible and reviewable.

Run:

    node harness/serve.js &
    node harness/boot.js
    node harness/skills.js
    node harness/ratrig.js
    node harness/plants.js

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
