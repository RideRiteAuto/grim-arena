# Harness and patch scripts

Tooling, not game code. None of this is served to players.

- `serve.js` serves the built bundle on 127.0.0.1:8123 with the three.js
  importmap rewritten to a local copy, so a boot test needs no network.
- `boot.js` boots the bundle, clicks PLAY AS GUEST, enters gameplay and reports
  console errors plus live readings off `window.__grim` (chunk count, mesh
  count, draw calls, skills, tool tiers).
- `skills.js` drives real harvests through the real code path and checks the
  gate messages, tool tier detection and the save migration.
- `patches/` holds the exact scripts used to edit `/tmp/game-src.html`, one per
  shipped change, so every bundle edit is reproducible and reviewable.

Run:

    node harness/serve.js &
    node harness/boot.js
    node harness/skills.js

The harness runs at roughly 20 percent of real time. Never judge an animation
or a spawn by how long it took; read the arrays.
