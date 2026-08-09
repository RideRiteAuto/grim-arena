#!/usr/bin/env python3
"""Patch 87.500 (Phase 2 of TERRAIN-WORKER-OFFLOAD-PLAN.md): stepTerrain
cutover, feature-flagged. GRIM_RULES.PERF.TERRAIN_WORKER (shared-rules.js,
lands false) branches stepTerrain's chunk-build and dressing loops between
the worker-request path (new) and the exact original synchronous calls
(untouched -- same code, not touched at all when the flag is false).

Everything here is INERT with the flag false, which is how this ships:
identical behavior to before this patch, byte-diff verified. Flipping the
flag true is intentionally a separate, later step once real play confirms
the worker path is solid -- not bundled into this patch.

What this adds:
- this._chunkReqs / this._dressReqs / this._reqSeq (initTerrain), per Sec5.
- requestBuildChunk/requestDressChunk: post to the Phase 1 worker via
  grimWorkerRequest, and on response build the real Mesh / register real
  game state -- the same tail work buildChunk/dressChunk already do, so
  results are indistinguishable from the synchronous path. On failure
  (timeout, staleEdit, no worker) each falls back to the synchronous call
  for that ONE chunk (Sec3a) rather than leaving a hole in the terrain.
  Simplification vs. the plan's literal "retry after edit-sync catches up"
  wording for staleEdit specifically: this falls back to the synchronous
  path immediately instead, which is always correct (it reads current
  state directly, not through the worker) and simpler; a future patch
  could add the retry if staleEdit thrashing turns out to be common enough
  to matter.
- dressChunk split into dressChunk (computes props, sync path only) +
  finishDressChunk(rec, props) (everything downstream: meshes, zoneNodes,
  colliders, resource state) so the worker-response handler can call the
  same tail with the worker's props instead of a freshly computed one --
  per Sec9's own description of this tail as permanent shared plumbing,
  not the "old path."
- A symmetric sweep for _chunkReqs/_dressReqs alongside the existing
  _chunks range sweep, so an in-flight request for a chunk that fell out
  of range gets dropped from the map (no need to cancel worker-side; the
  reqId check in the response handler already finds nothing to attach a
  late answer to).
- Closes a real gap surfaced by worker-compare.js during this pass (not
  hypothetical -- it reproduced on already-shipped Phase 1 code too, so
  it's pre-existing, not something this patch introduced): the worker's
  ctx.gfx (used by chunkProps' clutter-density scaling) was only ever set
  once, at worker-init time. If gfx changes afterward (the game's own
  perf auto-degrade, or the player toggling it), the worker's copy goes
  stale and dressChunk's clutter counts silently diverge from what the
  synchronous path would produce. stepTerrain now re-posts a 'ctx' message
  (the Phase 1 dispatcher already handles this message type) whenever
  this.gfx changes and useWorker is active, via a new this._lastGfxSent
  tracker (initTerrain). grimDebugCompareChunk (Phase 1) gets the same
  refresh directly, since it bypasses stepTerrain and would otherwise still
  see the stale-ctx false positive that surfaced this gap in the first
  place.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

# ---- anchor 1: initTerrain -- add the request-tracking maps ---------------
ANCHOR1 = """  initTerrain(S) {
    const T = this.T;
    this._chunks = new Map();"""
assert s.count(ANCHOR1) == 1, 'patch 87.500: anchor1 found %d times, wanted 1' % s.count(ANCHOR1)
NEW1 = """  initTerrain(S) {
    const T = this.T;
    this._chunks = new Map();
    // Terrain worker offload, Phase 2 (TERRAIN-WORKER-OFFLOAD-PLAN.md Sec5).
    // Only ever populated when GRIM_RULES.PERF.TERRAIN_WORKER is true.
    this._chunkReqs = new Map();   // key -> {reqId, seg, cx, cz}
    this._dressReqs = new Map();   // key -> {reqId, cx, cz}
    this._reqSeq = 0;
    this._lastGfxSent = null;      // last this.gfx value posted to the worker"""
out = s.replace(ANCHOR1, NEW1, 1)
assert out != s, 'patch 87.500: anchor1 replacement had no effect'
s = out

# ---- anchor 2: the chunk-build loop ---------------------------------------
ANCHOR2 = """    let budget = boot || ((this.boating || this.rideTurbo) ? 10 : 1);
    for (let ring = 0; ring <= COARSE && budget > 0; ring++) {
      for (let dx = -ring; dx <= ring && budget > 0; dx++) {
        for (let dz = -ring; dz <= ring && budget > 0; dz++) {
          if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;
          const cx = pcx + dx, cz = pcz + dz, key = cx + ',' + cz;
          const have = this._chunks.get(key);
          // Hysteresis: once a chunk is at full detail, keep it there until the
          // player is a full ring further out, so a chunk sitting right on the
          // boundary does not dispose+rebuild its geometry on every crossing.
          const wantSeg = (have && have.seg === 32) ? (ring <= DETAIL + 1 ? 32 : 8) : (ring <= DETAIL ? 32 : 8);
          if (have && have.seg === wantSeg) continue;
          if (have) { this.dressDrop(have); this.roadDrop(have); this.scene.remove(have.mesh); have.mesh.geometry.dispose(); this._chunks.delete(key); }
          const nmch = this.buildChunk(cx, cz, wantSeg);
          if (this._frozeStatic) { nmch.matrixAutoUpdate = false; nmch.updateMatrix(); }
          const rec = { mesh: nmch, seg: wantSeg, cx: cx, cz: cz };
          // The ribbon only goes on detail chunks: see buildChunkRoads.
          if (wantSeg > 16) rec.road = this.buildChunkRoads(cx, cz);
          this._chunks.set(key, rec);
          budget--;
        }
      }
    }"""
assert s.count(ANCHOR2) == 1, 'patch 87.500: anchor2 found %d times, wanted 1' % s.count(ANCHOR2)
NEW2 = """    // Sec4: one worker. Only route through it once it has answered its own
    // 'ready' message -- see grimStartTerrainWorker in the Phase 1 block.
    const useWorker = GRIM_RULES.PERF.TERRAIN_WORKER && _grimTerrainWorker && _grimWorkerReady;
    // Keep the worker's ctx.gfx current: chunkProps' clutter-density scaling
    // reads it, and it's otherwise only ever set once, at worker-init time.
    if (useWorker && this.gfx !== this._lastGfxSent) {
      this._lastGfxSent = this.gfx;
      _grimTerrainWorker.postMessage(Object.assign({ type: 'ctx' }, grimTerrainWorkerCtx()));
    }
    let budget = boot || ((this.boating || this.rideTurbo) ? 10 : 1);
    if (useWorker) {
      for (let ring = 0; ring <= COARSE && budget > 0; ring++) {
        for (let dx = -ring; dx <= ring && budget > 0; dx++) {
          for (let dz = -ring; dz <= ring && budget > 0; dz++) {
            if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;
            const cx = pcx + dx, cz = pcz + dz, key = cx + ',' + cz;
            const have = this._chunks.get(key);
            const wantSeg = (have && have.seg === 32) ? (ring <= DETAIL + 1 ? 32 : 8) : (ring <= DETAIL ? 32 : 8);
            if (have && have.seg === wantSeg) continue;
            if (this._chunkReqs.has(key)) continue;   // already in flight, don't re-post every tick
            if (have) { this.dressDrop(have); this.roadDrop(have); this.scene.remove(have.mesh); have.mesh.geometry.dispose(); this._chunks.delete(key); }
            const reqId = ++this._reqSeq;
            this._chunkReqs.set(key, { reqId: reqId, seg: wantSeg, cx: cx, cz: cz });
            this.requestBuildChunk(key, cx, cz, wantSeg, reqId);
            budget--;
          }
        }
      }
    } else {
      for (let ring = 0; ring <= COARSE && budget > 0; ring++) {
        for (let dx = -ring; dx <= ring && budget > 0; dx++) {
          for (let dz = -ring; dz <= ring && budget > 0; dz++) {
            if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;
            const cx = pcx + dx, cz = pcz + dz, key = cx + ',' + cz;
            const have = this._chunks.get(key);
            // Hysteresis: once a chunk is at full detail, keep it there until the
            // player is a full ring further out, so a chunk sitting right on the
            // boundary does not dispose+rebuild its geometry on every crossing.
            const wantSeg = (have && have.seg === 32) ? (ring <= DETAIL + 1 ? 32 : 8) : (ring <= DETAIL ? 32 : 8);
            if (have && have.seg === wantSeg) continue;
            if (have) { this.dressDrop(have); this.roadDrop(have); this.scene.remove(have.mesh); have.mesh.geometry.dispose(); this._chunks.delete(key); }
            const nmch = this.buildChunk(cx, cz, wantSeg);
            if (this._frozeStatic) { nmch.matrixAutoUpdate = false; nmch.updateMatrix(); }
            const rec = { mesh: nmch, seg: wantSeg, cx: cx, cz: cz };
            // The ribbon only goes on detail chunks: see buildChunkRoads.
            if (wantSeg > 16) rec.road = this.buildChunkRoads(cx, cz);
            this._chunks.set(key, rec);
            budget--;
          }
        }
      }
    }"""
out = s.replace(ANCHOR2, NEW2, 1)
assert out != s, 'patch 87.500: anchor2 replacement had no effect'
s = out

# ---- anchor 3: the existing range sweep -- add a symmetric one for the ----
# ---- in-flight request maps ------------------------------------------------
ANCHOR3 = """    for (const [key, ch] of this._chunks) {
      const r = Math.max(Math.abs(ch.cx - pcx), Math.abs(ch.cz - pcz));
      if (r > COARSE + 1) {
        this.dressDrop(ch); this.roadDrop(ch); this.scene.remove(ch.mesh); ch.mesh.geometry.dispose(); this._chunks.delete(key);
      } else if (r > DRESS + 1 && ch.dressed) {   // hysteresis: promoted at ring<=DRESS, dropped only past DRESS+1
        // walked away: the props go, the harvest state they carried does not
        this.dressDrop(ch);
      }
    }"""
assert s.count(ANCHOR3) == 1, 'patch 87.500: anchor3 found %d times, wanted 1' % s.count(ANCHOR3)
NEW3 = ANCHOR3 + """
    // Sec5: an in-flight request for a chunk/dress that fell out of range
    // just gets dropped from the map -- no need to cancel it worker-side,
    // the reqId check in the response handler will find nothing to attach
    // a late answer to and discard it silently.
    if (this._chunkReqs.size) {
      for (const [key, req] of this._chunkReqs) {
        if (Math.max(Math.abs(req.cx - pcx), Math.abs(req.cz - pcz)) > COARSE + 1) this._chunkReqs.delete(key);
      }
    }
    if (this._dressReqs.size) {
      for (const [key, req] of this._dressReqs) {
        if (Math.max(Math.abs(req.cx - pcx), Math.abs(req.cz - pcz)) > DRESS + 1) this._dressReqs.delete(key);
      }
    }"""
out = s.replace(ANCHOR3, NEW3, 1)
assert out != s, 'patch 87.500: anchor3 replacement had no effect'
s = out

# ---- anchor 4: the dressing loop ------------------------------------------
ANCHOR4 = """    if (this.worldOn && this.started && GRIM_WORLD.ready && !this._dressOff) {
      let dbud = boot ? 40 : 1;
      for (let ring = 0; ring <= DRESS && dbud > 0; ring++) {
        for (let dx = -ring; dx <= ring && dbud > 0; dx++) {
          for (let dz = -ring; dz <= ring && dbud > 0; dz++) {
            if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;
            const rec = this._chunks.get((pcx + dx) + ',' + (pcz + dz));
            if (!rec || rec.dressed) continue;
            this.dressChunk(rec);
            rec.dressed = true;
            dbud--;
          }
        }
      }
    }"""
assert s.count(ANCHOR4) == 1, 'patch 87.500: anchor4 found %d times, wanted 1' % s.count(ANCHOR4)
NEW4 = """    if (this.worldOn && this.started && GRIM_WORLD.ready && !this._dressOff) {
      let dbud = boot ? 40 : 1;
      if (useWorker) {
        for (let ring = 0; ring <= DRESS && dbud > 0; ring++) {
          for (let dx = -ring; dx <= ring && dbud > 0; dx++) {
            for (let dz = -ring; dz <= ring && dbud > 0; dz++) {
              if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;
              const key = (pcx + dx) + ',' + (pcz + dz);
              const rec = this._chunks.get(key);
              if (!rec || rec.dressed) continue;
              if (this._dressReqs.has(key)) continue;
              const reqId = ++this._reqSeq;
              this._dressReqs.set(key, { reqId: reqId, cx: rec.cx, cz: rec.cz });
              this.requestDressChunk(key, rec, reqId);
              dbud--;
            }
          }
        }
      } else {
        for (let ring = 0; ring <= DRESS && dbud > 0; ring++) {
          for (let dx = -ring; dx <= ring && dbud > 0; dx++) {
            for (let dz = -ring; dz <= ring && dbud > 0; dz++) {
              if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;
              const rec = this._chunks.get((pcx + dx) + ',' + (pcz + dz));
              if (!rec || rec.dressed) continue;
              this.dressChunk(rec);
              rec.dressed = true;
              dbud--;
            }
          }
        }
      }
    }"""
out = s.replace(ANCHOR4, NEW4, 1)
assert out != s, 'patch 87.500: anchor4 replacement had no effect'
s = out

# ---- anchor 5: split dressChunk into dressChunk (props) + finishDressChunk
# ---- (everything downstream -- the shared tail Sec9 describes) -----------
ANCHOR5 = """  dressChunk(rec) {
    if (!GRIM_WORLD.ready) return;
    this.dressInit();
    const T = this.T;
    const props = this.chunkProps(rec.cx, rec.cz);
    // clutter: one merged mesh, no shadows, frozen matrix"""
assert s.count(ANCHOR5) == 1, 'patch 87.500: anchor5 found %d times, wanted 1' % s.count(ANCHOR5)
NEW5 = """  dressChunk(rec) {
    if (!GRIM_WORLD.ready) return;
    const props = this.chunkProps(rec.cx, rec.cz);
    this.finishDressChunk(rec, props);
  }

  // Everything downstream of "here is the {clutter, nodes} list for this
  // chunk" -- meshes, zoneNodes/collider registration, harvest state. Called
  // by dressChunk() (synchronous path, props computed locally) and by
  // requestDressChunk()'s worker-response handler (props computed by the
  // worker instead) -- the same tail either way, per TERRAIN-WORKER-OFFLOAD-
  // PLAN.md Sec9: this isn't "the old path," it's permanent main-thread
  // plumbing both paths share.
  finishDressChunk(rec, props) {
    this.dressInit();
    const T = this.T;
    // clutter: one merged mesh, no shadows, frozen matrix"""
out = s.replace(ANCHOR5, NEW5, 1)
assert out != s, 'patch 87.500: anchor5 replacement had no effect'
s = out

# ---- anchor 6: insert requestBuildChunk/requestDressChunk right after -----
# ---- buildChunk (they belong next to the method they parallel) -----------
ANCHOR6 = """    this.scene.add(m);
    return m;
  }

  // Build one crossing."""
assert s.count(ANCHOR6) == 1, 'patch 87.500: anchor6 found %d times, wanted 1' % s.count(ANCHOR6)
NEW6 = """    this.scene.add(m);
    return m;
  }

  // Terrain worker offload, Phase 2 (TERRAIN-WORKER-OFFLOAD-PLAN.md Sec5).
  // Posts a buildChunk request to the Phase 1 worker (grimWorkerRequest,
  // module-level) and, on response, does exactly the Mesh-assembly tail
  // buildChunk's THREE-side already does -- just fed the worker's transferred
  // typed arrays instead of computing them synchronously here. The reqId
  // check is the one thing that has to be right: if _chunkReqs no longer
  // has this key, or has it pointing at a DIFFERENT reqId, this response is
  // stale (walked out of range, re-requested at a different LOD, or an
  // editor rebuild nuked and re-requested everything) -- discard silently,
  // touch nothing, per Sec5.
  requestBuildChunk(key, cx, cz, seg, reqId) {
    const self = this;
    grimWorkerRequest({ type: 'buildChunk', cx: cx, cz: cz, seg: seg }, 5000).then((msg) => {
      const pending = self._chunkReqs.get(key);
      if (!pending || pending.reqId !== reqId) return;
      self._chunkReqs.delete(key);
      const T = self.T, CH = 64, x0 = cx * CH + CH / 2, z0 = cz * CH + CH / 2;
      const g = new T.BufferGeometry();
      g.setAttribute('position', new T.BufferAttribute(msg.positions, 3));
      g.setAttribute('color', new T.BufferAttribute(msg.colors, 3));
      g.setAttribute('aTile', new T.BufferAttribute(msg.tiles, 4));
      g.setAttribute('aMix', new T.BufferAttribute(msg.mixes, 3));
      g.setAttribute('normal', new T.BufferAttribute(msg.normals, 3));
      g.setIndex(new T.BufferAttribute(msg.index, 1));
      const m = new T.Mesh(g, self._chunkMat);
      m.position.set(x0, 0, z0);
      m.receiveShadow = seg > 16;
      self.scene.add(m);
      if (self._frozeStatic) { m.matrixAutoUpdate = false; m.updateMatrix(); }
      const rec = { mesh: m, seg: seg, cx: cx, cz: cz };
      if (seg > 16) rec.road = self.buildChunkRoads(cx, cz);
      self._chunks.set(key, rec);
    }).catch((err) => {
      const pending = self._chunkReqs.get(key);
      if (!pending || pending.reqId !== reqId) return;
      self._chunkReqs.delete(key);
      // Sec3a: worker timeout / staleEdit / no worker -- fall back to the
      // synchronous path for just this one chunk rather than leave a hole
      // in the terrain. Always correct: buildChunk reads current state
      // directly on the main thread, not through the worker.
      grimTerrainWorkerLog('buildChunk fallback for ' + key + ': ' + (err && err.message || err));
      const nmch = self.buildChunk(cx, cz, seg);
      if (self._frozeStatic) { nmch.matrixAutoUpdate = false; nmch.updateMatrix(); }
      const rec = { mesh: nmch, seg: seg, cx: cx, cz: cz };
      if (seg > 16) rec.road = self.buildChunkRoads(cx, cz);
      self._chunks.set(key, rec);
    });
  }

  // Same shape as requestBuildChunk, for chunkProps() instead of geometry.
  // On success hands the worker's {clutter, nodes} to finishDressChunk --
  // the exact same tail dressChunk()'s synchronous path uses.
  requestDressChunk(key, rec, reqId) {
    const self = this;
    grimWorkerRequest({ type: 'dressChunk', cx: rec.cx, cz: rec.cz }, 5000).then((msg) => {
      const pending = self._dressReqs.get(key);
      if (!pending || pending.reqId !== reqId) return;
      self._dressReqs.delete(key);
      self.finishDressChunk(rec, { clutter: msg.clutter, nodes: msg.nodes });
      rec.dressed = true;
    }).catch((err) => {
      const pending = self._dressReqs.get(key);
      if (!pending || pending.reqId !== reqId) return;
      self._dressReqs.delete(key);
      grimTerrainWorkerLog('dressChunk fallback for ' + key + ': ' + (err && err.message || err));
      self.dressChunk(rec);
      rec.dressed = true;
    });
  }

  // Build one crossing."""
out = s.replace(ANCHOR6, NEW6, 1)
assert out != s, 'patch 87.500: anchor6 replacement had no effect'
s = out

# ---- anchor 7: grimDebugCompareChunk (Phase 1) also needs a fresh ctx -----
# ---- before comparing, for the same reason stepTerrain now does -- it -----
# ---- bypasses stepTerrain entirely, so Phase 2's stepTerrain-side refresh -
# ---- never runs for it. Without this the debug tool itself can flag a ----
# ---- false positive if gfx drifted since worker init (reproduced this ----
# ---- during Phase 2's own verification pass, on unmodified Phase 1 code). -
ANCHOR7 = """async function grimDebugCompareChunk(cx, cz, seg) {
  seg = seg || 32;
  if (!_grimTerrainWorker) return { cx: cx, cz: cz, seg: seg, ok: false, reason: 'no terrain worker' };
  const mainG = grimComputeChunkGeometryMainThread(cx, cz, seg);
  const ctx = grimTerrainWorkerCtx();
  const dressMain = grimChunkProps(cx, cz, ctx);"""
assert s.count(ANCHOR7) == 1, 'patch 87.500: anchor7 found %d times, wanted 1' % s.count(ANCHOR7)
NEW7 = """async function grimDebugCompareChunk(cx, cz, seg) {
  seg = seg || 32;
  if (!_grimTerrainWorker) return { cx: cx, cz: cz, seg: seg, ok: false, reason: 'no terrain worker' };
  const mainG = grimComputeChunkGeometryMainThread(cx, cz, seg);
  const ctx = grimTerrainWorkerCtx();
  // Refresh the worker's ctx (gfx in particular) before comparing -- this
  // tool bypasses stepTerrain, so its gfx-refresh (Phase 2) never runs for
  // this path. Message order is FIFO within the worker, so this is
  // guaranteed to land before the buildChunk/dressChunk requests below.
  _grimTerrainWorker.postMessage(Object.assign({ type: 'ctx' }, ctx));
  const dressMain = grimChunkProps(cx, cz, ctx);"""
out = s.replace(ANCHOR7, NEW7, 1)
assert out != s, 'patch 87.500: anchor7 replacement had no effect'
s = out

io.open(PATH, 'w', encoding='utf-8').write(s)
print('87.500_terrain_worker_cutover: edited %s (7 anchors)' % PATH)
