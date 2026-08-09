# Grim World: Terrain/Dressing Web Worker Offload — Full Plan

Status as of 2026-08-08: **`GRIM_RULES.PERF.TERRAIN_WORKER` is now `true` —
the terrain worker is live in production**, flipped on Kevin's explicit
go-ahead after Phase 1's byte-diff comparison and Phase 2's own live-path
verification both confirmed the worker path matches the synchronous one
exactly (see the notes at the end of §8 for both phases). **The rollback
story is unchanged and still real: flip the flag back to `false` to revert
to the synchronous path instantly, no code change needed** — see the
important caveat on the throttle values in Phase 3's note if that ever
happens for real. Phase 4-5 below are still design-only and **not
authorized to start** without Kevin's explicit go-ahead, same as every
phase here. This is a handoff doc —
written so a fresh agent/chat with no memory of how it was produced can pick
this up. All line numbers below are from a `repack.py extract` taken at
commit `82303a3` and **will drift** — re-grep every anchor before writing a
patch, per house rule. (Original design pass by a prior chat; reviewed,
amended, and Phase 0 implemented by a fresh chat the same day — see the
review notes folded into §7/§10/§11 below.)

## Read before starting

- `PROJECT-MEMORY.md`, `CODE-SWEEP-AUG8.md`, `CAMERA-TURN-STUTTER-FIX.md`,
  `HARNESS-LOGIN-FIX-STATUS.md` — cited by the original plan as required
  reading (pushing/testing rules, where this was scoped, the bug this
  solves, harness-gate status). **None of these four files exist in this
  repo as of this writing.** They apparently live only in another chat's
  session state. Do not block on them, but flag this loudly to Kevin: a
  future fresh agent picking up this plan will hit the same gap. If you're
  Kevin: worth having whichever chat has these commit them to the repo root
  so they survive session handoffs like every other plan doc here does.
- One correction to what the original plan says about `HARNESS-LOGIN-FIX-STATUS.md`:
  it claims this sandbox can't complete a real boot at all. That's true for
  the actual Supabase **account login** network call, but **guest-mode boots
  work fine here** — `harness/boot.js` and `harness/dressing.js` both ran
  clean against a local `harness/serve.js` with zero network dependency (no
  Cloudflare/Supabase involved) as part of Phase 0's own verification. So
  "real boot" testing is NOT categorically blocked in this sandbox — only
  the authenticated-login path is. Re-test this assumption before citing it
  in a future phase's writeup.

## The non-negotiable outcome this plan is built around

Kevin's explicit requirement: **editor behavior must be identical whether a
chunk goes through the worker or not, and no dead/legacy second code path
gets left behind once this is proven working.** Two consequences that
shape everything below:

1. This is **one unified pipeline**, not "worker for normal chunks, old
   synchronous path forever for edited chunks." The world editor's live
   data (painted ground, height edits, deleted nodes, placed objects) gets
   synced into the worker on every edit, not just once at boot. See §3.
2. The temporary synchronous fallback added in Phase 2 for safe rollout is
   explicitly **not permanent** — §9 (Phase 5) is a real, scheduled cleanup
   step that deletes it and the feature flag once the worker path is
   trusted, not a "maybe someday" note.

---

## 1. What's portable to a worker, what must stay main-thread

### Portable (pure functions, verified against the real code, not assumed)

- `terrainColor(zi, h, wx, wz, out)` (`game-src.html:11312`) — already pure.
  Depends only on four memoized constant-array palettes and
  `GRIM_WORLD.zone()`. Copy verbatim, drop `this.` to module-level.
- `groundSurface(zi, h, wx, wz, out)` (`:11053`) — pure *provided* its
  dependencies are supplied: a static lookup table, `zoneVariant` (below),
  `bridgePad`/`padSurfaceFor` (static/pure), and `GRIM_EDIT.paint()` — the
  one real wrinkle, see §3/§8.
- `zoneVariant(zoneName, wx, wz)` (`:5991`) — pure, depends on two static
  memoized tables.
- `chunkProps(cx, cz)` (`:12277`, already labeled "THE PURE GENERATOR" in
  its own header comment) — returns plain data (`{clutter, nodes}` arrays
  of position/rotation/scale/kind), no THREE, no scene. Depends on
  `GRIM_RULES.GATHER.*` (static config), `grimSeed`/`grimRnd`/`grimNodeId`
  (pure integer-hash PRNG, no `Math.random`), `GRIM_WORLD.zone/.height`,
  `zoneVariant`, static clutter tables, and `dressBlocked()` — itself pure
  given its inputs, but see the anvil/campfire wrinkle in §8.
- `buildChunk`'s **vertex-loop body** (not the whole function — see below).
- **Found during Phase 0, not called out in the original list:**
  `bridgeGeom(b)` (`:5497`). `bridgePad` calls it, so it's a transitive
  dependency the worker needs too. It's pure (reads `GRIM_WORLD` plus the
  bridge object `b`) and memoizes onto `b._g`, exactly the same pattern the
  zone/palette tables use — `GRIM_WORLD.bridges` is baked static world data,
  not mutable session state, so memoizing on it is safe. Extracted alongside
  `bridgePad` in Phase 0.

### Must stay main-thread, unchanged

- `buildChunk`'s THREE-side construction: `new T.PlaneGeometry`,
  `computeVertexNormals()`, `setAttribute`, `new T.Mesh`, `scene.add`. A
  worker has no WebGL/DOM context — it can only hand back raw numbers. The
  worker computes a **plain vertex-loop function** (`buildChunkVerts`,
  factored out of `buildChunk`) that returns `{positions, colors, tiles,
  mixes, normals, index}` as typed arrays; the main thread turns those into
  the actual `BufferGeometry`/`Mesh`. Grid layout and normal computation
  were independently re-derived from three@0.160.1's own source
  (`PlaneGeometry.js`, `BufferGeometry.js:computeVertexNormals`) so the
  worker's output is bit-identical to today's, not an approximation.
  **Scoping note added after Phase 0** (see §8): the from-scratch,
  THREE-independent grid+normal rebuild described here is real work that
  Phase 1 still owes, not something Phase 0 already did. Phase 0's
  `buildChunkVerts` only factors out the per-vertex color/tile/mix fill —
  it still takes an already-built `PlaneGeometry`'s position attribute as
  input. Don't assume this box is checked; it isn't yet.
- `dressChunk`'s mesh side: `mergeGeos`, `makeZoneTree`/`makeZoneOre`/
  `makeZonePlant`, `scene.add`, and — critically — **live resource-system
  registration**: `this.zoneNodes.push(R)`, `this.colliders.push(R.col)`,
  harvest HP/dead/respawn state, `resourceDepleted()`. This is mutable
  session game state, not re-derivable math, and must never live in the
  worker. Only `chunkProps()`'s position/rotation/scale/kind *list* is
  offloadable; everything downstream that turns that list into scene
  objects and live game state stays exactly where it is today.
- `GRIM_EDIT_RENDER.dress/drop` (hand-placed objects) — untouched by this
  rework. It's driven by a tiny per-chunk authored list, not a real cost
  center per the Aug 8 sweep.
- `keepGround(x, z)` — cheap, low-call-count, reads the same live
  `GRIM_EDIT` state as `groundSurface`; simpler to leave on the thread that
  already owns the canonical copy.
- **Added after review, not in the original list:** `buildChunkRoads(cx, cz)`
  (`:11784`). It calls `this.terrainColor`/`this.groundSurface` per road
  vertex to compute road-ribbon color/tile blends, same math as
  `buildChunk`. It's small (only detail-level chunks with roads nearby get
  a ribbon) and out of scope for this plan's worker offload — but it was
  never mentioned, and should be measured rather than silently assumed
  cheap. Call this out explicitly in whichever phase's writeup covers final
  perf numbers.

---

## 2. Message protocol

Chunk key is identical to today's `_chunks` Map key: `cx + ',' + cz`.

**Request (main → worker)**, two message types (kept decoupled because
`buildChunk`/`dressChunk` already run on separate budgets/rings today):

```
{ type: 'buildChunk', reqId, cx, cz, seg, gfx, editGen }
{ type: 'dressChunk', reqId, cx, cz, gfx, editGen }
```

`reqId` is a monotonic, main-thread-assigned counter used to discard stale
responses (§5). `editGen` is the generation counter of the worker's
`GRIM_EDIT` mirror at request time (§3) — the worker cross-checks its own
copy's generation before answering.

**Response (worker → main)**:

```
{ type: 'buildChunkResult', reqId, cx, cz, seg,
  positions, colors, tiles, mixes, normals, index }   // all Float32/Uint32Array

{ type: 'dressChunkResult', reqId, cx, cz,
  clutter: [{type, zone, x, z, y, rot, sc}, ...],       // plain objects, ~150-220/chunk
  nodes:   [{kind, zone, x, z, y, rot, sc, nid}, ...] }  // ~2-4/chunk

{ type: 'staleEdit', reqId }   // worker's editGen didn't match — main thread
                                 // re-sends after the sync in §3 catches up
```

`buildChunkResult`'s typed arrays are transferred (`postMessage(msg,
[msg.positions.buffer, ...])`), not structured-cloned — real bytes at
`seg=32` (33×33 vertices × 5 arrays). `dressChunkResult`'s arrays are tiny
plain objects, not worth packing.

**Added after review, not in the original protocol:** neither message type
covers the worker dying or hanging. See §3a below — this is the one
substantive gap in an otherwise thorough protocol design, and it needs to
land no later than Phase 1, not as a Phase 5 afterthought.

---

## 3. Worker construction and keeping the editor in sync (answers "won't this desync from the editor?")

### Build via Blob URL, single source of truth

Follows `repack.py`'s existing `WBEGIN`/`WEND` pattern (already used for
`worldgen-data.js`/`worldgen.js`), not a new mechanism:

1. New file `terrain-worker-src.js` at repo root: the extracted pure
   functions from §1, plus an `onmessage` dispatcher and the sync handler
   below.
2. `repack.py` gets a new marker pair (`WORKERBEGIN`/`WORKEREND`) and a
   `sync_worker()` step that concatenates `worldgen-data.js + worldgen.js +
   shared-rules.js + editor-core.js + terrain-worker-src.js` into one
   JSON-escaped string literal (`GRIM_TERRAIN_WORKER_SRC`) embedded in
   `game-src.html`. One source of truth — a change to `worldgen.js` flows
   into both the main bundle and the worker bundle automatically on the
   next `repack.py pack`. Total payload ≈180KB, once, inside an
   already-multi-MB bundle. Trivial.
3. At runtime: `new Worker(URL.createObjectURL(new Blob([GRIM_TERRAIN_WORKER_SRC], {type: 'application/javascript'})))`.
4. Worker-side, on load: runs its own `GRIM_WORLD.init()` (same
   `DecompressionStream` inflate — a standard Worker-available API, not
   `window`-scoped), independently of the main thread's copy. Both decode
   the same baked bytes and are byte-identical by construction. Buffers
   incoming requests until `GRIM_WORLD.ready`, same guard `stepTerrain`
   already has today, just relocated.

**Sharp edge found by re-reading `repack.py` during Phase 0** (not mentioned
in the original plan, and it will bite whoever writes `sync_worker()` if
they don't know it going in): `sync_rules()`/`sync_world()`/`sync_editor()`
each find their marker pair in `game-src.html` and **wholesale-replace
everything between the markers** with fresh content read from the
standalone files, unconditionally, every `pack()`. Anything hand-inserted
inside one of those marker spans that isn't *also* in the corresponding
source file is silently deleted on the next pack. Confirmed by hitting it
directly in Phase 0 (see §8) — a first attempt at inserting new module-level
functions landed inside the `SHARED-RULES-BEGIN`/`END` span and vanished
completely as soon as `repack.py pack` ran, which broke the game at boot
with no compile-time warning. `sync_worker()` will define its own
`WORKERBEGIN`/`WORKEREND` span — just make sure nothing needed elsewhere
ever gets hand-edited inside it, and that the span itself doesn't
accidentally nest inside one of the other three.

### GRIM_EDIT sync — the actual answer to "does the editor stay in sync"

This is not a footnote, it's the load-bearing piece:

- Main thread's `GRIM_EDIT.load()` already fetches and sanitizes the
  authored layer once at boot. That **already-sanitized layer object**
  (not a URL) gets `postMessage`'d to the worker once; the worker runs the
  same `editor-core.js` sanitize+index logic locally on it. No second
  network fetch from the worker — avoids any chance the two copies load
  different revisions if the server's layer changes mid-session.
- Every subsequent edit — the same `GRIM_EDIT.reindex()` call already
  triggered today from `editor-ui.js` after any paint/sculpt/place/delete
  — **also** posts the updated raw layer to the worker, tagged with an
  incrementing `editGen` counter.
- Every chunk request carries the `editGen` the main thread believes is
  current. If the worker is still finishing an update when a request
  arrives, it replies `staleEdit` instead of silently building on
  half-applied paint data; main thread just re-sends once sync catches up.
  This handles the one real race (an edit landing and a chunk request
  crossing in flight) without ever producing a visibly wrong chunk.
- **Correction after review — this is smaller than the original plan
  thought.** The original plan says `editor-core.js`'s `load(url)` "needs
  splitting so the already-fetched, already-sanitized layer can be pushed to
  the worker directly," and flags it as a change to a file the editor track
  also actively works in. Reading `editor-core.js` during the review found
  this split **already exists**: `setLayer(raw)` (line 433) does exactly
  "take an already-sanitized layer, apply it, reindex" and is already
  exported (`GRIM_EDIT.setLayer`), and `GRIM_EDIT.raw` is already exposed
  for reading the current layer back out. `editor-ui.js` already calls
  `GRIM_EDIT.setLayer` itself (undo/redo, import, revert). So the worker
  sync in Phase 1 is very likely just: post `GRIM_EDIT.raw` to the worker
  after boot-load and after every `reindex()`, worker-side call
  `GRIM_EDIT.setLayer(postedRaw)`. Little to no `editor-core.js` surgery
  needed — still coordinate before touching it per `PROJECT-MEMORY.md`
  (once that file exists in-repo, see the note at the top of this doc), but
  the collision risk with the editor track is much smaller than originally
  scoped. Verify `setLayer`/`raw` are still there and still do this before
  relying on it — this doc could itself go stale if the editor track
  changes that file's shape.
- **Added after review, not in the original plan:** debounce the edit
  `postMessage`. `reindex()` fires on every paint/sculpt tick during a drag
  (per `editor-ui.js`'s own 150ms debounce pattern already used for
  `rebuildWorld()`), so posting the full raw layer on every single reindex
  will be chattier than it needs to be. Coalesce to the latest layer with
  the same ~150ms debounce `editor-ui.js` already uses elsewhere, rather
  than a new pattern.

Net result: every chunk, edited or not, goes through the same worker
pipeline. There is no separate "editor path."

### 3a. Worker failure and recovery (new section, not in the original plan)

The single biggest gap found in review. As designed, nothing handles the
worker throwing, being killed by the browser, or just never responding:

- No `worker.onerror`/`worker.onmessageerror` handler is specified anywhere.
  If the worker throws during `GRIM_WORLD.init()` or while processing a
  request, the main thread has no way to know.
- `_chunkReqs`/`_dressReqs` entries (§5) are never given a timeout. A
  request that never gets a response (worker dead, or a bug that drops a
  message) sits in the map forever; §5's ring-sweep only removes entries
  for chunks that fall out of view, not ones whose worker died. The visible
  symptom would be chunks near the player that simply never build, forever,
  with no error surfaced anywhere — worse than the stutter this plan fixes,
  because it fails silently instead of loudly.
- After Phase 5 removes the synchronous fallback entirely, there is no
  recovery path at all if the worker becomes unusable mid-session.

This needs to land in **Phase 1** (worker scaffolding), not deferred:

- `worker.onerror = (e) => { ... }` — log it (`agentLog_`-style, or the
  equivalent client-side signal this project already uses for surfaced
  errors) and mark the worker unusable.
- A per-request timeout (a few seconds is plenty given a chunk build is
  currently sub-frame) that, on expiry, either retries once or — while
  Phase 2's synchronous fallback still exists — falls back to it for that
  one chunk.
- A worker-restart path: construct a fresh `Worker`, re-run the `GRIM_EDIT`
  initial sync (§3), and re-issue whatever was still in-flight. Bound the
  retry count so a worker that dies repeatedly doesn't restart in a loop.
- Once Phase 5 deletes the synchronous fallback, re-decide what "the
  worker is unusable" degrades to — most likely: stop streaming new
  terrain and surface a visible error, rather than a silent freeze. Write
  this decision down when Phase 5 actually happens; don't leave it
  implicit.

---

## 4. Number of workers: one

A single worker fully removes the main-thread block (the actual cause of
the camera stutter) regardless of throughput. Current steady-state budget
(1 terrain + 1 dressing chunk per ~0.12s tick, post-85.100) is not a
throughput bottleneck today, it's a latency-on-the-wrong-thread bottleneck.
Boot backfill and the editor's `rebuildWorld()`/`repaintChunksNear()`
(`editor-ui.js:85`, `:1507` — both route through the same `stepTerrain`
loop, confirmed by reading both) push 200-260 requests through the queue
in a burst; with one worker that becomes a queue processed back-to-back
off-thread instead of a main-thread freeze — strictly better than today
either way. Revisit a worker pool only if real queue-depth measurement
after shipping shows it's needed (e.g. during boat/turbo fast travel) —
add a `_perfDebug` counter for this rather than guessing now.

---

## 5. `stepTerrain()` rework

Add `this._chunkReqs` / `this._dressReqs` (Maps, key = chunk key, value =
`{reqId, seg, kind}`) and `this._reqSeq` (monotonic counter).

Where today's ring-scan loop calls `this.buildChunk(cx, cz, wantSeg)`
synchronously and blocks, it instead:

- Skips if an identical in-flight request already covers this key (guard
  against re-posting every tick while waiting on a response).
- Drops the old chunk exactly as today if replacing one.
- Assigns a `reqId`, records it in `_chunkReqs`, posts the request,
  decrements `budget`. `budget` now throttles *requests sent per tick*,
  not main-thread time — since posting a message is ~free, **the 85.100
  stopgap (1+1) can very likely go back toward its pre-stopgap values
  (3+2) once this ships**. Flag as a separate follow-up tuning patch, not
  bundled into the offload patch itself.

On response: look up `_chunkReqs` by key, and if `reqId` doesn't match the
stored one, **discard silently, touch nothing** — this one check covers
all three ways a response can go stale: the player walked out of range
before it arrived, the chunk got re-requested at a different LOD, or an
editor rebuild nuked and re-requested everything. If it matches: build the
real `BufferGeometry`/`Mesh` from the transferred arrays (this part is
unchanged in spirit from today's tail of `buildChunk`) and add to scene.

Add the same sweep the code already does for built chunks
(`this._chunks`, drop when `r > COARSE+1`) over `_chunkReqs` too — an
in-flight request for a chunk that's since fallen out of range gets
removed from the map (no need to cancel it worker-side; the response's
`reqId` check will just find nothing to attach it to). Same pattern,
symmetric, for `_dressReqs` against the `DRESS+1` band. Also apply §3a's
per-request timeout here, not just the range sweep — a request can go
stale by falling out of range OR by the worker never answering, and only
the first of those two is covered by this sweep as originally scoped.

---

## 6. Determinism (why this can't desync multiplayer harvest nodes)

Checked line-by-line, not assumed:

- No `Math.random()` anywhere in the extraction set. All randomness is
  `grimRnd(grimSeed(cx, cz, salt))` — a hand-rolled mulberry32 PRNG seeded
  from an integer hash, every step a 32-bit integer op. No floating-point
  accumulation-order dependency, no `Date.now()`.
- No `performance.now()`, no `Map`/`Set` iteration-order dependency, no
  timing-sensitive code anywhere in the extracted functions.
- JS numeric ops (`Math.sin`, `Math.imul`, IEEE-754 float math) are
  specified to be bit-identical across threads within the same engine —
  the same guarantee `worldgen.js`'s own header comment already relies on
  for cross-*machine* determinism; a worker thread is a strictly easier
  case.
- `grimNodeId(cx, cz, i)` is unchanged math, just relocated — node IDs
  stay identical to today's, so nothing about multiplayer harvest-state
  sync changes.
- The one real hazard is **synchronization**, not determinism: the
  `editGen` protocol in §3 exists specifically to catch the case where a
  request and an edit-update cross in flight. **Verify this for real in
  Phase 1**, don't just trust the paragraph — byte-diff worker output
  against main-thread output for a representative sample of chunks
  (varied zones, water edges, bridge pads, a painted/road-authored test
  layer if available, world-edge chunks) before trusting it in Phase 2.

**Added after review:** keep Phase 1's byte-diff comparison as a
**permanent debug tool**, not a one-off check thrown away once it passes
once. `game-src.html`'s vertex-normal math was independently re-derived
from three@0.160.1's own source (§1), and this project's harness README
already documents that three is pinned to 0.160.1 on purpose because newer
builds change the module layout. If three ever gets upgraded, that
re-derivation needs re-verifying — keep the comparison callable on demand
(a debug menu item or a harness script) specifically so that future upgrade
doesn't silently reintroduce drift between the worker and main thread.

---

## 7. Wrinkles found reading the actual code — don't paper over these

1. `dressBlocked()` reads `this.anvils`/`this.campfires` — these are
   **not** part of `GRIM_WORLD` or `GRIM_EDIT`. They're two hardcoded
   coordinates from a single `buildCampForge()` boot-time call
   (`game-src.html:15964`) — one fixed spawn-camp anvil, one fixed
   campfire, never anything else. Must be serialized into the worker's
   init payload explicitly (a handful of numbers), not assumed to arrive
   via `GRIM_WORLD`/`GRIM_EDIT` sync — miss this and a prop can generate
   on top of the spawn-camp furniture. **Phase 0 already threads this
   through as a `ctx` object (`{anvils, campfires, roadSegs}`) passed
   explicitly into the free functions rather than read off `this` — see
   §8 — which is exactly the shape Phase 1 needs to serialize into the
   worker's init payload.** `this.roadSegs` travels the same way for the
   same reason, even though in practice it's always empty today (see the
   next wrinkle).
2. `editor-ui.js`'s `rebuildWorld()` and `repaintChunksNear()` don't call
   `buildChunk`/`dressChunk` directly — they both route through the same
   `stepTerrain` ring-scan loop this plan redesigns. Good news (one
   rework covers every call site) but Phase 2 needs a specific test for
   the 200-260-request burst case an editor rebuild produces, not just the
   steady-state 1-2-per-tick path.
3. `groundSurface()`'s call into `GRIM_EDIT.paint()` is easy to miss on a
   skim — it only surfaces if you read the function to its last line, not
   just the "obviously pure" palette math at the top.
4. **Found during review, not in the original list:** `registerRoad(pts)`
   (`:11969`, appends to `this.roadSegs`) has zero call sites anywhere in
   the bundle. The comment above it says roads come off the bake now and
   the hook only exists for "authored spurs inside a town" that would use
   it later. In the current build `this.roadSegs` is therefore always
   empty in practice. Not a behavior risk either way — `dressBlocked`
   already guards with `(this.roadSegs || [])` — but worth knowing so
   nobody spends time trying to reproduce a bug that depends on non-empty
   road spurs existing today.

---

## 8. Phased patch plan

Each phase is its own patch (`harness/patches/NN.NNN_name.py`, random
decimal per house rule, exact-string anchors), independently shippable and
verified before the next begins. Ship it or it didn't happen — don't leave
a finished phase sitting local.

**Phase 0 — pure extraction, zero behavior change, main-thread only. SHIPPED
2026-08-08, commit pending push.**
Moved `terrainColor`, `groundSurface`, `zoneVariant`, `bridgePad`,
`padSurfaceFor`, `bridgeGeom` (transitive dependency found during
extraction, see §1), `buildChunkVerts` (new — factored out of `buildChunk`'s
loop body), `chunkProps`, `dressBlocked`, `zoneNodeTable`, `CLUTTER_CLUMP`,
`ZONE_VARIANTS`/`VARIANT_CELL`/`ZONE_CLUTTER`/`ROADS_ON` (static-table
accessors these depend on) to module-level `grim*`-prefixed functions in
`game-src.html`, placed right before `class Component` (deliberately
**not** inside any of `repack.py`'s existing marker spans — see §3's new
sharp-edge note, that's exactly the mistake this avoided on the second
attempt). Every original class method is now a one-line delegate
(`terrainColor(zi, h, wx, wz, out) { return grimTerrainColor(zi, h, wx, wz, out); }`)
so every existing call site elsewhere in the class keeps working unchanged.
`dressBlocked`/`chunkProps` take their live per-instance state
(`anvils`/`campfires`/`roadSegs`/`gfx`) via an explicit `ctx` object instead
of reading `this.*`, on purpose — that's the exact shape Phase 1 needs to
serialize into the worker's init payload (§7, wrinkle 1).

**Verification performed** (not just asserted — see
`harness/phase0-baseline.js`, added this pass, plus the repo's existing
`harness/dressing.js`):
- Byte-diffed `chunkProps(cx, cz)` for 33 chunks (clutter + nodes, ~1,600
  clutter entries + 13 nodes), raw vertex `color`/`aTile`/`aMix`/`position`
  attributes for 41 live-streamed chunk meshes, 400 direct
  `terrainColor`/`groundSurface` samples across the map, and 126
  `bridgePad` samples along every baked bridge — all before vs. after the
  extraction, on two separate real (guest-mode, local, no-network) boots.
  Every category came back **byte-identical**.
- `node --check` on the extracted bundle script and `repack.py pack`'s own
  round-trip assertion both passed.
- `harness/boot.js` and `harness/dressing.js` both ran clean against the
  packed bundle with zero console errors.
- One real mistake made and caught in this same pass, left in §3 as a
  documented sharp edge for whoever writes Phase 1's `sync_worker()`: the
  first attempt inserted the new module block inside the
  `SHARED-RULES-BEGIN`/`END` span, which `repack.py pack()`'s `sync_rules()`
  silently wiped on the very next pack (it unconditionally replaces
  everything between those markers from `shared-rules.js` on disk). Caught
  by the verification boot throwing immediately, not by inspection — a good
  argument for always doing the boot-and-byte-diff pass rather than
  trusting a clean `node --check` alone.

This phase is valuable even standalone and is also the prerequisite for
Phase 1 (the worker needs these as standalone functions, not instance
methods). **What Phase 0 explicitly did NOT do, so Phase 1 doesn't assume
it's already done:** `buildChunkVerts` still takes an already-constructed
`THREE.PlaneGeometry` position attribute as input and only factors out the
per-vertex color/tile/mix fill; it does not yet independently reconstruct
grid layout or vertex normals without THREE. That THREE-independent
rebuild (§1's "must stay main-thread" section explains why it's needed) is
real Phase 1 work.

**Phase 1 — worker scaffolding, dormant. SHIPPED 2026-08-08.**
Added `terrain-worker-src.js` (own copies of Phase 0's pure functions, plus
a from-scratch THREE-independent chunk grid/normal builder, plus the
`onmessage` dispatcher and `GRIM_EDIT.setLayer` sync handler), `repack.py`'s
`WORKERBEGIN`/`WORKEREND` markers + `sync_worker()` (assembles
`worldgen-data.js + worldgen.js + shared-rules.js + editor-core.js +
terrain-worker-src.js` into `GRIM_TERRAIN_WORKER_SRC`, a JSON-escaped string
loaded via a Blob-URL `Worker` at runtime — not injected as executable code
like the other three sync steps, since a Blob worker shares no scope with
the main script). Constructs `_grimTerrainWorker` from inside `boot()`'s
`layer.then()`, posts the initial `GRIM_EDIT.raw` + a stripped-to-plain-data
`{anvils, campfires, roadSegs, gfx}` ctx (§7 wrinkle 1) at init, then keeps
the worker's copy in sync on every edit by wrapping `GRIM_EDIT.reindex`/
`setLayer` once (debounced ~150ms, matching `editor-ui.js`'s own pattern) —
not by touching `editor-core.js`/`editor-ui.js`'s many individual call
sites, per §3's correction. **`stepTerrain` does not send real requests —
this phase is fully dormant, nothing a player does differently.**

**Also lands §3a's worker failure/recovery in this phase, not deferred**:
`worker.onerror`/`onmessageerror` handlers, a per-request timeout (default
5s), and a bounded-retry (`5`) restart path that fails every in-flight
request rather than leaving any hanging forever.

**Verification performed** (§6: byte-diff worker output against real
main-thread output, for real, not just argued):
- The from-scratch chunk grid + normal math (`grimPlaneGridXZ`,
  `grimPlaneIndex`, `grimComputeNormals`) was independently verified
  bit-identical against the real, installed three@0.160.1
  `PlaneGeometry`/`rotateX`/`computeVertexNormals` source (including the
  Float32-accumulator-per-triangle rounding behavior, not a Float64 sum
  rounded once at the end) across five chunk-coordinate/segment-count
  combinations before this was ever wired into the worker.
- `window.__grim.debugCompareChunk`/`debugCompareSample` (new, permanent —
  kept callable on demand exactly per §6's note, since a future three.js
  upgrade could silently reintroduce drift) run against 10 real chunks on a
  real guest-mode local boot (varied zones, empty and dressed chunks, world
  origin, and far-out coordinates): positions, colors, tiles, mixes,
  normals, index, clutter list, and node list all **byte/structurally
  identical** between the worker and the main thread's own computation for
  every chunk, via `harness/worker-compare.js` (new).
- Two real bugs found and fixed by this same pass, both the kind
  `node --check`/a syntax gate cannot catch, only a real boot can (same
  lesson Phase 0 already documented for the `SHARED-RULES-BEGIN`/`END`
  sharp edge): an anchor-replacement patch mistake that silently dropped
  `class Component extends DCLogic {` entirely (caught by the game failing
  to boot at all — "logic class eval FAILED"), and a `DataCloneError` from
  posting the live `anvils`/`campfires` records (which carry real THREE
  objects — a mesh group, a cloned `Vector3`, the build kit) straight to the
  worker instead of the plain `{x, z, radius}` `dressBlocked`/`chunkProps`
  actually read.
- `harness/boot.js`, `harness/dressing.js`, `harness/ground-blend-live.js`,
  `harness/ground-paint-coverage.js` all ran clean against the packed bundle
  — same results as Phase 0 (determinism identical, 0 placement-rule
  violations). `harness/editor-gameplay.js` reproduces the same pre-existing
  failure confirmed unrelated to this work in Phase 0's own verification
  pass.
- `harness/editor.js`: 87 of 89 checks passed. The 2 new failures
  ("painted ground carries the authored surface", "the road paints the
  ground it runs over") were confirmed, via the same before/after stash
  comparison as everything else here, to reproduce identically on
  unmodified `origin/master` — a pre-existing gap from 86.160's ground-paint
  reveal-layer rework (`out[0]`/`out[1]` intentionally stay as the natural
  blend now; the authored paint shows through `out[3]`/`out[6]` instead),
  not something this phase caused or should fix. Worth flagging to whoever
  owns that track: `harness/editor.js` wasn't updated for the new
  architecture in 86.160's own commit.
- Re-verified against origin/master a second time after it moved mid-work
  (86.160's ground-paint reveal-layer rework landed while this was in
  progress) — re-extracted, re-applied, re-packed, and re-ran the full
  suite above against the new tip before pushing either time it moved.

**Phase 2 — `stepTerrain` cutover, feature-flagged. SHIPPED 2026-08-08.**
Added `GRIM_RULES.PERF.TERRAIN_WORKER` (shared-rules.js, landed `false`).
`stepTerrain`'s chunk-build loop and dressing loop each branch once at the
top on `useWorker = GRIM_RULES.PERF.TERRAIN_WORKER && _grimTerrainWorker &&
_grimWorkerReady`: the worker-request path is entirely new code, and the
`else` branch is the pre-existing synchronous loop copied verbatim,
untouched — not refactored, not shared, so there is zero chance a
refactoring slip changes what ships today. Added
`this._chunkReqs`/`_dressReqs`/`_reqSeq` (initTerrain, §5), and
`requestBuildChunk`/`requestDressChunk` (next to `buildChunk`), which post
to the Phase 1 worker and on response do exactly the same Mesh-assembly /
game-state tail the synchronous methods already do — `dressChunk` was split
into `dressChunk` (computes props) + `finishDressChunk(rec, props)`
(everything downstream) specifically so both paths call the identical tail,
per this doc's own Phase 5 note that the tail is shared plumbing, not "the
old path." On failure (timeout / staleEdit / no worker), both request
methods fall back to the synchronous call for that one chunk (§3a) rather
than leave a hole in the terrain — a deliberate simplification of §2's
literal "retry after edit-sync catches up" wording for staleEdit
specifically: falling back immediately is simpler and always correct
(the sync path reads current state directly, not through the worker); a
future patch could add the retry if staleEdit thrashing turns out to
matter in practice. A symmetric sweep drops stale `_chunkReqs`/`_dressReqs`
entries alongside the existing `_chunks` range sweep.

**One real gap found and closed during this phase's own verification, not
carried forward:** the worker's `ctx.gfx` (read by `chunkProps`' clutter-
density scaling) was only ever set once, at worker-init time (a known,
explicitly-flagged limitation from Phase 1). This surfaced as a real,
reproducible false positive in `worker-compare.js` once the flag was
tested live — traced to the exact cause, not just patched around blind.
Fixed: `stepTerrain` now re-posts a `'ctx'` message whenever `this.gfx`
changes and `useWorker` is active (`this._lastGfxSent` tracker), and
`grimDebugCompareChunk` (Phase 1) gets the same refresh directly, since it
bypasses `stepTerrain` and would otherwise still see the stale-ctx false
positive that surfaced this gap in the first place.

The flag branching is the rollback story exactly as designed — flip one
boolean to revert fully, no patch needed. **This dual state is
intentionally temporary** — see Phase 5, not "ship and forget."

**Verification performed** (with the flag both off, as shipped, and
temporarily flipped on locally to prove the live path — never committed
with it on):
- **Flag off (shipped state):** `harness/boot.js`, `harness/dressing.js`
  (determinism identical, 1,637 clutter + 13 nodes, 0 rule violations),
  `harness/worker-compare.js`, `harness/ground-blend-live.js`,
  `harness/ground-paint-coverage.js` all clean — byte-identical results to
  Phase 1's own baseline, confirming the untouched synchronous path is
  genuinely untouched. `harness/editor.js`: same 87/89 pre-existing result
  Phase 1 already found and attributed to 86.160, not a new regression.
  `harness/editor-gameplay.js` reproduces the same pre-existing failure
  Phase 0 already confirmed is unrelated.
- **Flag on (local only, to prove the cutover actually works):**
  `harness/boot.js` and `harness/dressing.js` both clean through the real
  worker-driven build+dress path (same 1,637/13/0-violations numbers,
  confirmed via a rerun after the first attempt hit the known SwiftShader
  auto-degrade artifact — see harness/README.md's existing note on that,
  reproduced identically on unmodified origin/master under the same system
  load, unrelated to this patch). `harness/worker-compare.js` clean after
  the gfx-staleness fix above.
- **One real, non-blocking finding surfaced only with the flag on:** in
  `?edit=1` sessions specifically, the worker's throttled per-tick dressing
  budget (unchanged from today's `1` per ~0.12s tick outside boot) means
  newly-streamed world-grown nodes can take noticeably longer to become
  clickable/selectable than the synchronous path — confirmed via direct
  instrumentation to be a throughput/latency effect, not a correctness bug
  (`window.__grim.debugCompareChunk` stays byte-identical throughout; given
  enough wait, dressing catches up completely). This is exactly the kind of
  thing the flag-off default and Phase 5's 1-2-week observation window
  exist to catch before it reaches a player — **not fixed here** (budget
  retuning is explicitly Phase 3's job, not bundled into the offload patch,
  per this doc's original design), but worth knowing before ever flipping
  the flag: Kevin's daily editor session may feel slower to populate at
  first if/when this goes live, and that's worth watching for specifically
  during the observation window.
- Origin moved once more during this phase's work (58744f2, an unrelated
  ground-shader fix) — re-extracted, re-applied, re-packed, and re-ran the
  full suite above against the new tip before pushing.

**`GRIM_RULES.PERF.TERRAIN_WORKER` flipped `true` 2026-08-08, on Kevin's
explicit go-ahead**, as its own standalone commit (kept separately
revertible per this section's own design). Re-verified the full suite
above against the actual shipped bundle with the flag live (not just a
local test): `boot.js`/`worker-compare.js`/`dressing.js` clean (determinism
confirmed via the subset-relationship check — see `harness/README.md` —
each time the SwiftShader auto-degrade artifact fired, which it did more
persistently in this session than earlier, unrelated to this change and
already independently confirmed against unmodified `origin/master`).
`editor.js` reproduces the same 5 failures (2 pre-existing + 3 from the
editor node-latency finding) documented in Phase 2's own notes above — no
surprises, matches exactly what live-local testing already predicted.

**Phase 3 — tune the throttle back up. SHIPPED 2026-08-08.**
Once Phase 2 is stable, revisit the 85.100 budget (1+1) — likely safe to
return to 3+2 or higher now that `budget` only throttles request-sending,
not blocking time. Needs its own before/after camera-smoothness check on a
real boot. Keep separately revertible from Phase 2.

**Phase 4 (optional).**
Worker pool — only if post-ship measurement shows single-worker queue
depth growing unbounded during fast travel. Not scoped in detail; revisit
with real data.

---

## 9. Phase 5 — delete the old path (do not skip this)

This is the phase that answers Kevin's actual ask: once the worker path is
trusted, the temporary fallback and flag get **removed**, not left dormant
forever as unreachable legacy code.

### Criteria before deleting anything (don't delete on a hunch)

- `GRIM_RULES.PERF.TERRAIN_WORKER` has been `true` in production for a
  real stretch (recommend at minimum 1-2 weeks of normal play / multiple
  sessions) with zero worker-related regressions reported.
- Kevin confirms the camera-turn stutter is actually gone on a real boot.
- No `staleEdit` thrashing or worker error logs observed in normal or
  editor-heavy (rebuild-burst) play, and §3a's failure/recovery path has
  not been observed firing in a way that indicates a flaky worker.
- Phase 1's byte-diff comparison still passes if re-run against current
  code (confirms nothing downstream silently reintroduced a divergence) —
  keep it runnable on demand per §6's note, don't let it bit-rot into
  something nobody can re-run.

### What actually gets deleted, precisely

- The `else` branch in `stepTerrain`'s ring-scan loop that calls
  `this.buildChunk(cx, cz, wantSeg)` / `this.dressChunk(rec)`
  synchronously — delete it, keep only the worker-request path.
- The `GRIM_RULES.PERF.TERRAIN_WORKER` flag — remove from
  `shared-rules.js`, remove the `if (flag)` branch entirely so the
  worker path is unconditional.
- Any synchronous wrapper that existed *only* to serve the fallback
  branch — grep for other call sites before deleting anything, the same
  way every other cleanup in this project already does (see
  `CODE-SWEEP-AUG8.md`'s dead-code section for the pattern, once that file
  exists in-repo: confirm zero other call sites, then delete).
- This doc — once shipped and cleaned up, add a "DONE, see commit X" line
  at the top rather than leaving it looking like an open plan, same
  pattern `PERF-AUDIT-AUG6.md` uses for its shipped items (if that file
  also turns out to only exist in another session, use whatever the
  in-repo equivalent convention is instead).
- `PROJECT-MEMORY.md` / `CODE-SWEEP-AUG8.md`'s Tier 3 item 1 — update from
  "no Web Worker anywhere" to done, so a future sweep doesn't re-flag it,
  once those files actually exist in this repo.

### What must NOT be deleted (so nobody over-cleans)

- `buildChunk`/`dressChunk`'s tail — `BufferGeometry`/`Mesh` assembly,
  `mergeGeos`, `scene.add`, collider/resource registration. This isn't
  "the old path," it's permanent main-thread plumbing the worker-response
  handler calls too, before and after cleanup.
- The extracted pure functions (`buildChunkVerts`, `chunkProps`, etc.) —
  these ARE the worker's logic via the shared-source assembly in
  `repack.py`. Nothing to remove there.
- §3a's worker failure/recovery path — this stays permanently, it isn't
  part of the temporary fallback.

---

## 10. Ownership / coordination reminders

- `editor-core.js` is shared with the editor track's active work — flag
  it loudly before touching it, per `PROJECT-MEMORY.md` (once that file
  exists in-repo). Per §3's correction, the actual change needed there in
  Phase 1 is likely small to none, since `setLayer`/`raw` already exist.
- This bundle also has an active combat/art/animation/sound track and a
  separate performance/engine track (per project memory) working
  concurrently. This plan touches `game-src.html`'s terrain/dressing
  methods and (per §3) briefly `editor-core.js` — grep for recent changes
  to those specific spots before starting a new phase, the same way this
  review did before touching anything.
- Real-boot testing: see the correction at the top of this doc. Guest-mode
  boots are NOT blocked in this sandbox; only authenticated Supabase login
  is. Re-verify this is still true before citing the old blanket claim in
  a future phase's writeup — sandboxes and their network policies can
  change between sessions.

---

## 11. Review notes (kept here rather than in a separate file)

This plan was reviewed against the actual code at commit `82303a3` before
any implementation started, per Kevin's ask ("look into why you're even
doing this... review his code, make sure we're doing best practices...
flag anything suspect"). Summary of that review, for anyone landing on this
doc without having seen the conversation it came out of:

- The architecture is correct for the problem (main-thread block causing a
  frame stutter → move the pure math off-thread, keep THREE/scene/live
  state on the main thread). SharedArrayBuffer was considered and correctly
  ruled out implicitly by the postMessage/transfer design — GitHub Pages
  doesn't serve the COOP/COEP headers SharedArrayBuffer requires.
- Every specific claim in the original plan (line anchors, purity claims,
  the no-`Math.random()` claim, the `GRIM_EDIT.paint()` wrinkle, the
  `this.anvils`/`this.campfires` wrinkle, the 1+1 budget) was independently
  re-verified against the real code and held up. Whoever wrote the
  original design pass actually read the code; this is disciplined,
  reviewed work, not something to distrust — the additions in this
  revision are refinements and one real gap (§3a), not a rebuttal.
- The one substantive gap: no worker failure/recovery story anywhere in
  the original design. Added as §3a and folded into Phase 1's scope.
- Smaller findings folded in above: the `bridgeGeom` transitive dependency
  (§1), the `SHARED-RULES-BEGIN`/`END` sharp edge in `repack.py` (§3, found
  by actually hitting it during Phase 0), the smaller-than-expected
  `editor-core.js` change (§3), the edit-sync debounce (§3),
  `buildChunkRoads` never being mentioned (§1), the dead `registerRoad`
  hook (§7), and the missing-referenced-docs gap (top of this doc).
