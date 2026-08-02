# GRIM ARENA — Developer Handoff

Third-person action RPG in the browser. One self-contained Design Component
(`Grim Arena.dc.html`), three.js via CDN import map, zero build step, zero
asset downloads (all geometry, textures and audio are procedural).

## Files

- **`Grim Arena.dc.html`** — the entire game: template (HUD/menus, between `<x-dc>` tags) + one `Component` logic class (~2700 lines). Everything below lives here.
- `grim-arena-standalone.html` — compiled single-file build (generated; do not edit).
- `server/index.js` + `package.json` — optional WebSocket relay fallback (~80 lines, `npm i && node index.js`, serves the project + `/ws` room relay).
- `README.md` — player-facing instructions.

## Architecture (all in the logic class, top to bottom)

- **`cfg()`** — ALL combat tuning: move frame-data (`MOVES`: wind/act/rec windows, damage, ranges), speeds, arena radius. Change a number, reload, feel it.
- **`boot()`** — renderer (pixelRatio ≤1.25, PCF shadows), scene/lights, `buildArena()`, entity creation, input binding, rAF loop. WebGL context loss is handled: `webglcontextlost` pauses hard, restore triggers `rebuild()` (full renderer teardown/re-boot; score survives).
- **`tick(dt)`** — fixed flow: hitstop scaling → title/pause branch (sim frozen) → countdown branch (net only) → `driveLocal` → world branch (`driveAI` per NPC, `stepFighter` per entity, `stepWorld`) or duel branch → projectiles → shouts → fx → camera → round logic → HUD → `netSend` → render.
- **Entities** — plain objects from `makeFighter(palette,isMe)` / `makeSaylors()`. Shared shape: `pos/vel/want` (vel eases toward want, exp damping — the smoothness core), `state` machine (`idle/attack/cast/draw/dodge/leap/charge/taunt/flourish/stagger/dead`), `st` (state time), `act` (current move + frame data), guard fields (`blocking/blockAge/guardBreak`), boss knobs (`aiD/dmgScale/spdScale/aggroR/spell/brawler/xp`). Rigs share part names (`upper/armR/armL/legR/legL/hand/handL/mount...`) so `animate()` runs every body.
- **Combat rules** — attacks fire on mouse-DOWN; input buffer (220ms) + recovery cancel at 45% chains combos (light,light,heavy); melee = arc+range check during active frames (`meleeCheck`); parry window = `blockAge < 0.2s` in SIM time; guard drains stamina per absorbed hit → guard break; projectiles in `projectiles[]`, player shots aim via `aimDirFrom()` (camera-ray through crosshair — never character yaw, the camera sits off-shoulder).
- **World** (`worldOn && mode==='ai'`) — `npcs[]` roam waypoints (`wander`), aggro by radius or on hit, deaggro at 32m. `stepWorld()`: NPC death → COMBAT XP + TESLA PAYCHECK drop + 26s respawn; player death → respawn at ring. `resources[]` (trees/rocks): `gatherCheck()` on 'chop' swings (weapon 3 pick↔rock, 4 axe↔tree), fell/shatter, LOGS/IRON ORE + WOODCUTTING/MINING XP, 28s respawn. Wall ring is solid except two gates (segments 0 & 4; collision in `stepFighter`).
- **Progression** — `wallet{}` + `skills{}` persisted to localStorage (`grim-wallet`, `grim-skills`); `lvl(xp)` curve; `renderWallet()` draws the Tab panel (CYBER WALLET + STATS).
- **Multiplayer** — PeerJS (CDN) data channels: reliable 'ctl' (hello/hits) + unreliable 'state' (20Hz snapshots), TURN relays over tcp/443 for corporate NATs (`peerOpts()`), staged status + 14s watchdog (`netStage`). Victim-authoritative damage. Host = `grim-duel-<CODE>` peer id. Legacy WS relay path kept (`tryConnect`, `#room=`).
- **FX** — pooled sparks/trails (`poolGet/poolPut` — never dispose pooled meshes), `fx[]` kinds: flame/ember/sway/fall/ring/spark/trail. Audio: WebAudio synth only (`sfx(name)`).
- **HUD/menus** — template refs (`hpFillRef`, `slot0-4Ref`, `walletRef`...); hitsplats + XP toasts are DOM projected from world space (`splat`); Saylors speech bubbles via `showShout`.

## Gotchas for the next engineer

1. `this.foe` is a POINTER to the current target (nearest NPC in world / `netFoe` online). Many systems read it; never null it.
2. Boot order matters: `fx`/`resources` arrays must exist before `buildArena()`.
3. Pooled fx meshes share geometry — always retire via `retireFx`, never `.dispose()`.
4. Hot paths avoid layout reads; `fit()` runs on ResizeObserver + every 45 frames only.
5. Test rig pattern (used throughout development): grab the logic instance via React fiber from the canvas, drive `g.tick(1/60)` manually (rAF throttles in hidden tabs), and read back rendered pixels with `renderer.domElement.toDataURL()` right after a manual `render()`.
6. IP guardrail: mechanics are genre-standard; all names, models, and art are original. Keep it that way.

## Controls
WASD/arrows move · mouse aim (pointer lock, free-aim fallback) · LMB attack (hold = chain) · RMB block/ward/rapid · Space roll · Shift sprint · E lock-on · Tab wallet · 1-5 blade/staff/bow/pick/axe · Enter ready (net).

## Tuning knobs (Tweaks panel)
`playerHealth`, `difficulty`, `roundsToWin` (net), `turnSpeed`, `volume`, `showDamage`. Difficulty also selectable in-game (SQUIRE 300hp / VETERAN 180 / CHAMPION 120 + AI ±).
