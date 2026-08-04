# Grim World — server simulation: the buildable plan

This is the working blueprint for moving monster simulation fully onto the
Cloudflare Worker. It is written so a session can pick it up cold and start.
Prerequisite knowledge lives in HANDOFF.md (repack workflow, deploy pipeline).

Decision on record: full faithful port. Monsters and bosses must attack at the
same moment on every screen so players can dodge and react together. Each
player's own dodge is judged on their machine against what they saw; everything
else is the server's word.

---

## 0. Where things stand today (already shipped)

- Relay (`relay-worker.js`, one Durable Object per world, PROTO 5) already owns:
  monster HEALTH, death, kill credit, loot rolls, sacks, claim windows,
  respawn timers (storage alarms), player presence, sim-owner election.
- One elected player still runs monster MOVEMENT and broadcasts positions at
  10Hz ('w' messages). Everyone else mirrors that feed exactly, with local AI
  as a fallback when the feed stops.
- The client already animates every monster locally from state + phase data, so
  the renderer needs almost nothing new.
- 53 NPCs exist, built inline at boot in a DETERMINISTIC order (this is what
  makes index-addressed messages work — preserve this invariant forever).

What phase 1-5 below removes: the elected player. The Durable Object becomes
the only thing that decides where monsters are and when they attack.

---

## 1. Architecture

```
Cloudflare Durable Object (per world)
  - world manifest: archetypes, spawns, colliders, safe zones  (uploaded once, hashed)
  - sim state: per-NPC pos/yaw/state/phase/cooldowns/aggro     (storage-backed)
  - sim loop: fixed 8Hz timestep, advanced on message arrival  (no idle cost)
  - outputs: interest-filtered snapshots, scheduled attack events,
             projectile spawn events, boss-script events

Every client (equal peers, no owner)
  - renders monsters by interpolating server snapshots
  - plays attack telegraphs on the server's clock
  - judges ONLY its own dodge at the damage frame, reports hit/miss
  - full local AI kept as disconnect fallback (already shipped)
```

### The sim loop without a server-side timer
A Durable Object sleeps between events; a real-time timer would cost alarms.
Instead: every inbound message runs `advance()`, which steps the accumulator
`(now - lastTick) / 125ms` in fixed 125ms steps (capped at 12 steps; beyond
that, jump-and-resync). Players already send 10Hz each, so with anyone online
the sim ticks at full rate for free. Empty world = no ticks = no cost; the
existing respawn/expiry alarm (low rate) still fires. On the first message
after a quiet spell, monsters advance at most 1.5s then snap — invisible in
practice because an empty world has no one watching.

### Clock sync (required for "same moment on every screen")
- Server stamps every attack event with `at` (server ms).
- Client keeps `offset = serverNow - localNow`, re-estimated from every pong
  (already flowing at 5s intervals; keep a rolling median of 8).
- Telegraphs are scheduled at `at + offset` locally. Anyone's telegraph starts
  within ~1 frame of everyone else's regardless of their ping.

---

## 2. Data model (this is the scalability answer)

### 2a. Archetype registry — adding a monster is adding a data row
```js
// shared-rules.js (single source, generated into BOTH bundles - see 3a)
ARCHETYPES: {
  goblin:  { max:30, xp:18, spd:0.8, aggroR:-1, weapon:0, ai:'melee', loot:'goblin' },
  wolf:    { max:45, xp:26, spd:1.1, aggroR:12, weapon:0, ai:'pack',  loot:'wolf', packR:14 },
  bandit:  { max:70, xp:40, spd:0.9, aggroR:10, weapon:0, ai:'melee', loot:'bandit', guard:true },
  sailers: { max:320, xp:150, spd:0.88, weapon:1, ai:'boss', loot:'captain', script:'sailers' },
  hollowKing: { max:600, xp:400, spd:0.9, weapon:5, ai:'boss', loot:'king', script:'hollowKing' },
  ...
}
```
The 53 current NPCs map onto ~12 archetypes. New monster = new archetype +
spawn entries. No server code changes, no protocol changes.

### 2b. Boss scripts — bigger bosses without bigger code
A boss is an archetype plus a SCRIPT: a small data-described state machine the
server interprets. This is the piece that makes "larger and more complex
bosses" cheap later.

```js
SCRIPTS: {
  hollowKing: {
    phases: [
      { untilHpPct: 60, moves: ['slam','leap','melee'] },
      { untilHpPct: 25, moves: ['slam','leap','leap','volley'], spdMul: 1.15,
        onEnter: { shout: 'THE HOLLOW STIRS', spawnAdds: { arch: 'wraith', n: 2, ring: 8 } } },
      { untilHpPct: 0,  moves: ['slam','volley','leap'], spdMul: 1.25, dmgMul: 1.2 }
    ],
    moves: {
      slam:   { cd: [5,8],  range: [0,6.2],  telegraph: 0.72, shape: { kind:'circle', r: 5.4 } },
      leap:   { cd: [4,7],  range: [5,15],   telegraph: 0.55, travel: true, shape: { kind:'circle', r: 3.2 } },
      volley: { cd: [6,10], range: [6,20],   telegraph: 0.70, proj: { kind:'snare', n: 5, spread: 0.5 } }
    }
  }
}
```
The interpreter is one function (~120 lines): pick phase by hp, roll an
off-cooldown move whose range matches the target, emit the scheduled event.
Phase transitions, add-spawning, enrage multipliers, and shouts are data.
Multi-shape attacks (cones, rings, lines) are just more `shape` kinds — the
client already gets told the shape, so ground telegraphs (red decals) become
drawable later with zero protocol changes.

### 2c. World geometry manifest — the drift killer
Client-side generator walks the already-built world at boot and produces:
```
{ hash, worldR: 168, colliders: [{x,z,r} | {x,z,hw,hd}], safeZones: [...],
  spawns: [{arch, x, z, name?, overrides?}] }   // in npcs[] order
```
- Uploaded once per world via `manifest` message; server persists it.
- `hash` = stable hash of the payload. Server rejects a manifest whose hash
  differs from the stored one UNLESS no players are connected (that is a game
  update deploying). Client compares hashes on join: mismatch → log + the
  server's copy wins for this session.
- This makes "server says the monster is in a wall" structurally impossible:
  both sides run the identical collider list or the join says so loudly.

---

## 3. Code moves (exact, by anchor)

### 3a. Shared rules generation
- New file `shared-rules.js` in the repo: `MOVES` (13 attack defs), SPEED, AI
  constants, ARCHETYPES, SCRIPTS, damage formulas (`armourCut`,
  `styleDamageMult` shapes), loot tables.
- `repack.py` gets a step: inject the file's contents between
  `/* SHARED-RULES-BEGIN */ ... END */` markers in BOTH `game-src.html` (replacing
  the literals in `cfg()`/`lootEntriesFor`) and `relay-worker.js`. One source,
  two outputs, drift impossible. Round-trip check extended to verify markers.

### 3b. Server (`relay-worker.js`) — new module ~600-800 lines
Port, in this order (all pure 2D math, no three.js dependency):
1. `resolveColliders` (589 chars, trivial) + world-edge clamp + NPC separation
   shove (from stepWorld, ~10 lines).
2. `wander` (1,330 chars) — needs a seeded RNG (mulberry32) so replays/tests
   are deterministic.
3. `driveAI` (8,201 chars) — target pick from server-known player positions;
   aggro/leash/safe-town; hold-radius + strafe steering; guard cadence; dodge
   rolls. Boss branches REPLACED by the script interpreter (2b).
4. Movement half of `stepFighter` (~3,000 of its 9,336 chars): velocity
   integration, lunge, knockback, stagger/freeze timers, stamina/mana regen,
   attack state machine timing (wind→act→rec). The animation/render half stays
   client-side untouched.
5. Attack resolution: at `act` start the server emits the event; it does NOT
   compute player hits (each client judges its own dodge, see 3c). It DOES
   compute NPC-vs-NPC nothing (doesn't exist) and boss add-spawns.
6. Projectiles: server spawns `{id, kind, from, vel, t0, dmg, owner:'npc'}`
   events; it does not integrate them per-tick (clients do, deterministically
   from t0 — dodge judgment is local, matching 3c).

### 3c. Client edits (in `game-src.html` via patch scripts)
- `nreg` grows into `manifest` upload (2c). Keep `nreg` path for one release
  as fallback (server answers both).
- New snapshot consumer: `nsnap` (see protocol) → per-NPC target pos/yaw/
  state/phase; reuse the existing mirror-the-feed path (`following` branch) —
  it is already exactly this, just fed by the server instead of a player.
- `attackEv` consumer: schedule telegraph at `at+offset` on the NPC (set
  state/act/st the same way `updateRemote` does); at `at + wind`, run a LOCAL
  hit test of the event's shape against MY position only (new ~30-line
  `judgeMyDodge(ev)` using the shape kinds); on hit, apply damage to self via
  the existing `phit` path semantics and report `hitrep` (server uses it only
  for stats/anti-cheat sanity, not for truth).
- `projEv` consumer: call the existing projectile spawn with owner=cosmetic
  NPC; hit-vs-me judged locally as today; NPC projectiles stop being spawned by
  `driveAI` locally in server mode.
- Remove the client 'w' NPC broadcast in server mode (players only ever send
  their own 's').
- Fallback: if snapshots stop for >2.5s with a live socket, or socket drops —
  existing local-AI fallback already handles it; extend the gate
  (`following`) to cover `nsnap` freshness.

### 3d. Protocol v6 (additions)
| msg | dir | content |
|---|---|---|
| `manifest` | c→s | full world manifest + hash (accepted per 2c rules) |
| `msync` | s→c | manifest hash + full NPC state on join/resync |
| `nsnap` | s→c | interest-filtered delta: `[i, x*10, z*10, yaw*100, state, phase*100, hp?]` int-packed |
| `attackEv` | s→c | `{i, move, at, dur:[wind,act,rec], shape, aim:{x,z,yaw}, dmg}` |
| `projEv` | s→c | `{id, kind, x, z, y, vx, vz, t0, dmg}` |
| `bossEv` | s→c | `{i, kind: 'phase'|'shout'|'adds', ...}` |
| `hitrep` | c→s | `{ev, hit, dmg}` self-reported damage taken (sanity-capped) |
| `svtime` | s→c | rides on pong; server ms for offset estimation |

### 3e. Interest management (the scale knob)
- Sim ticks ALL monsters (cheap: 8Hz × N × arithmetic; 500 NPCs ≈ well under
  1ms per tick).
- SNAPSHOTS are the expensive part, so: per player, send only NPCs within 60m
  (grid-bucketed, 16m cells), full set at join, adds/removes as they cross the
  radius. Idle monsters (no aggro, wander target unchanged) send at 1Hz;
  fighting monsters at 8Hz. At today's 53 NPCs this is a strict reduction from
  the current whole-roster 10Hz feed; at 500 NPCs it stays roughly constant
  per player because interest, not population, bounds the payload.

---

## 4. Phases, each shipping alone

| # | Ships | Acceptance test (automated, two headless browsers + local wrangler) |
|---|---|---|
| 1 | shared-rules generation + manifest upload/persist/hash + svtime clock sync | round-trip verified; second differing manifest rejected while occupied; client offset stabilizes within ±40ms in test harness |
| 2 | server movement sim + nsnap + client mirror; player 'w' feed retired in v6 mode | two clients see mean position delta < 0.5m; hiding/killing ANY tab changes nothing for the other (no owner exists to freeze) |
| 3 | attackEv + local dodge judgment + hitrep | scripted: client A stands in slam → takes damage on A's screen; client B outside → no damage; both telegraphs start within 50ms of each other on the shared clock |
| 4 | projEv, NPC projectiles server-spawned, client-integrated | volley hits a stationary client, misses a strafing one; zero per-projectile network traffic after spawn |
| 5 | boss scripts for Hollow King, Mr. Sailers, Austin Little, Plague Rat + phase/adds/enrage plumbing | each boss's current moves reproduced; phase transition spawns adds; all four fight correctly in the two-browser harness |

Rollback per phase: everything is gated on PROTO≥6 features the client
detects at welcome; redeploying the previous worker version reverts the world
to the current (v5) behavior with no client change needed.

## 5. Budget check (free tier)

- No new request classes: sim rides existing messages; snapshots replace the
  old 'w' feed byte-for-byte or better; alarms unchanged (respawn/expiry only).
- Interest filtering caps outbound per player regardless of monster count.
- Storage: manifest ~10-20KB + NPC state ~50 bytes each — nothing against 5GB.
- CPU per invocation stays micro; DO is single-threaded per world which is
  exactly what a game room wants.

## 6. Risks, restated for the implementer

1. Collider/edge mismatch → jitter against walls. Mitigated by the manifest
   hash; test by driving a monster along every collider in the harness.
2. Determinism: server RNG must be seeded per-world; NEVER use Math.random in
   the sim path (loot rolls exempt — server-only).
3. The 12-step catch-up cap: after DO cold start mid-fight, snap don't slide.
4. Keep npc index order sacred between client build and manifest.
5. `Date.now()` inside the DO is fine; performance.now() is not available —
   the sim clock is Date-based everywhere on the server.
