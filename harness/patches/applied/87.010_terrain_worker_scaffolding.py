#!/usr/bin/env python3
"""Patch 87.010 (Phase 1 of TERRAIN-WORKER-OFFLOAD-PLAN.md): worker
scaffolding, dormant. Adds the terrain worker construction, GRIM_EDIT sync
(initial + debounced on every edit, wrapping GRIM_EDIT.reindex/setLayer
rather than touching editor-core.js/editor-ui.js call sites -- see the
plan's Sec3 correction that little to no editor-core.js surgery is needed),
worker failure/recovery (Sec3a: onerror, per-request timeout, restart with a
bounded retry count), and a debug byte-diff comparison tool
(window.__grim.debugCompareChunk / debugCompareSample) that proves worker
output matches main-thread output for real, per Sec6.

Does NOT wire stepTerrain to send real requests -- that's Phase 2, behind
GRIM_RULES.PERF.TERRAIN_WORKER (landed false). Nothing in this patch changes
what a player sees; it's inert until Phase 2 flips the flag.

GRIM_TERRAIN_WORKER_SRC (the worker's own script, assembled from
worldgen-data.js + worldgen.js + shared-rules.js + editor-core.js +
terrain-worker-src.js) is injected by repack.py's new sync_worker() step
between the WORKERBEGIN/WORKEREND markers this patch inserts -- this patch
only seeds a placeholder for those markers; the real content is filled in by
the next `repack.py pack`, same pattern WORLD-GEN/EDITOR markers already use.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

# ---- anchor 1: module block, right after Phase 0's block, before class Component
ANCHOR1 = """// ============================================================================

class Component extends DCLogic {"""
assert s.count(ANCHOR1) == 1, 'patch 87.010: anchor1 found %d times, wanted 1' % s.count(ANCHOR1)

WORKER_BLOCK = """// ============================================================================

/* WORKERBEGIN */
// Placeholder -- repack.py's sync_worker() replaces everything between these
// markers with the real GRIM_TERRAIN_WORKER_SRC string on every pack. Do not
// hand-edit inside this span; it will be silently wiped, the same sharp edge
// Phase 0 already hit and documented for SHARED-RULES-BEGIN/END.
const GRIM_TERRAIN_WORKER_SRC = '';
/* WORKEREND */

// ----------------------------------------------------------------------------
// Terrain worker scaffolding -- Phase 1 of the worker offload plan, dormant
// (stepTerrain does not send real requests yet; see
// TERRAIN-WORKER-OFFLOAD-PLAN.md Sec8, Phase 2). Builds the worker, keeps
// its GRIM_EDIT copy in sync on every edit, handles worker failure/recovery
// (Sec3a), and exposes a debug byte-diff tool
// (window.__grim.debugCompareChunk/debugCompareSample) to prove worker
// output matches main-thread output before Phase 2 depends on it for real.
let _grimTerrainWorker = null;
let _grimWorkerReady = false;
let _grimWorkerFailCount = 0;
const _grimWorkerReqs = new Map(); // reqId -> {resolve, reject, timeout}
let _grimReqSeq = 0;
let _grimEditGenMain = 0;
let _grimEditSyncTimer = null;
let _grimEditWrapped = false;

function grimTerrainWorkerLog(msg) {
  try { console.error('[terrain-worker] ' + msg); } catch (e) {}
}

function grimStartTerrainWorker() {
  let w;
  try {
    const blob = new Blob([GRIM_TERRAIN_WORKER_SRC], { type: 'application/javascript' });
    w = new Worker(URL.createObjectURL(blob));
  } catch (e) {
    grimTerrainWorkerLog('construction failed: ' + (e && e.message || e));
    return null;
  }
  _grimWorkerReady = false;
  w.onmessage = (ev) => {
    const msg = ev.data;
    if (!msg || !msg.type) return;
    if (msg.type === 'ready') { _grimWorkerReady = true; return; }
    if (msg.type === 'workerError') { grimTerrainWorkerLog(msg.error); return; }
    const pending = _grimWorkerReqs.get(msg.reqId);
    // Unknown/stale reqId (chunk fell out of range, or answered after a
    // restart already re-issued it) -- discard silently, touch nothing.
    // Same rule Phase 2's stepTerrain integration will use.
    if (!pending) return;
    _grimWorkerReqs.delete(msg.reqId);
    clearTimeout(pending.timeout);
    if (msg.type === 'staleEdit') { pending.reject(new Error('staleEdit')); return; }
    pending.resolve(msg);
  };
  w.onerror = (e) => {
    grimTerrainWorkerLog('onerror: ' + (e && e.message || e));
    grimRestartTerrainWorker();
  };
  w.onmessageerror = () => { grimTerrainWorkerLog('onmessageerror (structured clone failure)'); };
  return w;
}

function grimRestartTerrainWorker() {
  _grimWorkerFailCount++;
  // Bounded retries so a worker that dies repeatedly doesn't restart in a
  // loop -- Sec3a.
  if (_grimWorkerFailCount > 5) {
    grimTerrainWorkerLog('failed ' + _grimWorkerFailCount + ' times, giving up on restarts');
    _grimTerrainWorker = null;
    return;
  }
  for (const [, p] of _grimWorkerReqs) { clearTimeout(p.timeout); p.reject(new Error('worker restarted')); }
  _grimWorkerReqs.clear();
  _grimTerrainWorker = grimStartTerrainWorker();
  if (_grimTerrainWorker) grimSendWorkerInit(_grimTerrainWorker);
}

function grimTerrainWorkerCtx() {
  // anvils/campfires are live records carrying real THREE objects (mesh
  // group, a cloned Vector3, the build kit) -- not postMessage-cloneable,
  // and dressBlocked/chunkProps only ever read .x/.z/.radius off them
  // (Phase 0's ctx usage). Strip to plain data before it crosses the
  // worker boundary. roadSegs is already a plain [x1,z1,x2,z2] array.
  const g = window.__grim;
  const plain = (arr) => (arr || []).map((r) => ({ x: r.x, z: r.z, radius: r.radius }));
  return {
    anvils: plain(g && g.anvils), campfires: plain(g && g.campfires),
    roadSegs: (g && g.roadSegs) || [], gfx: (g && g.gfx) || 'low'
  };
}

function grimSendWorkerInit(w) {
  const ctx = grimTerrainWorkerCtx();
  _grimEditGenMain++;
  w.postMessage({
    type: 'init', anvils: ctx.anvils, campfires: ctx.campfires, roadSegs: ctx.roadSegs, gfx: ctx.gfx,
    editLayer: GRIM_EDIT.raw, editGen: _grimEditGenMain
  });
}

function grimScheduleEditSync() {
  // Debounced to match editor-ui.js's own ~150ms pattern (reindex() fires on
  // every paint/sculpt tick during a drag) -- coalesce to the latest layer
  // rather than posting the full raw layer on every single reindex.
  if (_grimEditSyncTimer) clearTimeout(_grimEditSyncTimer);
  _grimEditSyncTimer = setTimeout(() => {
    _grimEditSyncTimer = null;
    if (!_grimTerrainWorker) return;
    _grimEditGenMain++;
    _grimTerrainWorker.postMessage({ type: 'editLayer', editLayer: GRIM_EDIT.raw, editGen: _grimEditGenMain });
  }, 150);
}

function grimWrapEditSyncOnce() {
  // Wrapping GRIM_EDIT's two external mutation entry points (rather than
  // editor-ui.js's many individual reindex() call sites) catches every edit
  // however it was triggered, without touching editor-core.js/editor-ui.js
  // -- see TERRAIN-WORKER-OFFLOAD-PLAN.md Sec3's correction that this needed
  // little to no editor-core.js surgery. setLayer already calls reindex()
  // internally, so this schedules at most one sync per external call either
  // way, not a double-trigger.
  if (_grimEditWrapped) return;
  _grimEditWrapped = true;
  const _reindex = GRIM_EDIT.reindex;
  GRIM_EDIT.reindex = function () { const r = _reindex.apply(GRIM_EDIT, arguments); grimScheduleEditSync(); return r; };
  const _setLayer = GRIM_EDIT.setLayer;
  GRIM_EDIT.setLayer = function (raw) { const r = _setLayer.call(GRIM_EDIT, raw); grimScheduleEditSync(); return r; };
}

function grimInitTerrainWorker() {
  _grimTerrainWorker = grimStartTerrainWorker();
  if (_grimTerrainWorker) { grimSendWorkerInit(_grimTerrainWorker); grimWrapEditSyncOnce(); }
  return _grimTerrainWorker;
}

// Per-request timeout (Sec3a) -- a chunk build is currently sub-frame, so a
// few seconds is generous. Exposed (not just used internally) so the debug
// compare tool and, later, Phase 2's stepTerrain integration share one path.
function grimWorkerRequest(msg, timeoutMs) {
  return new Promise((resolve, reject) => {
    if (!_grimTerrainWorker) { reject(new Error('no terrain worker')); return; }
    const reqId = ++_grimReqSeq;
    const full = Object.assign({}, msg, { reqId: reqId, editGen: _grimEditGenMain });
    const timeout = setTimeout(() => {
      _grimWorkerReqs.delete(reqId);
      reject(new Error('timeout'));
    }, timeoutMs || 5000);
    _grimWorkerReqs.set(reqId, { resolve: resolve, reject: reject, timeout: timeout });
    _grimTerrainWorker.postMessage(full);
  });
}

// Main-thread reference computation for one chunk -- exactly what buildChunk
// does today minus the Mesh/scene.add tail, reusing Phase 0's already-
// shipped, already-verified grimBuildChunkVerts for the color/tile/mix +
// height-write math and real THREE for the grid/normals it still owns. This
// is the ground truth the worker's from-scratch geometry gets byte-diffed
// against.
function grimComputeChunkGeometryMainThread(cx, cz, seg) {
  const T = window.THREE;
  const CH = 64, x0 = cx * CH + CH / 2, z0 = cz * CH + CH / 2;
  const g = new T.PlaneGeometry(CH, CH, seg, seg);
  g.rotateX(-Math.PI / 2);
  const pa = g.attributes.position;
  const vd = grimBuildChunkVerts(pa, x0, z0);
  g.computeVertexNormals();
  const out = {
    positions: new Float32Array(pa.array), colors: vd.colors, tiles: vd.tiles, mixes: vd.mixes,
    normals: new Float32Array(g.attributes.normal.array), index: new Uint32Array(g.index.array)
  };
  g.dispose();
  return out;
}

function grimCmpTypedArray(name, a, b) {
  if (!a || !b) return { name: name, ok: false, reason: 'missing' };
  if (a.length !== b.length) return { name: name, ok: false, reason: 'length ' + a.length + ' vs ' + b.length };
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return { name: name, ok: false, reason: 'value at ' + i + ': ' + a[i] + ' vs ' + b[i] };
  }
  return { name: name, ok: true };
}

// TERRAIN-WORKER-OFFLOAD-PLAN.md Sec6: byte-diff worker output against
// main-thread output for real, kept as a permanent on-demand debug tool
// (not a one-off check) since a future three.js upgrade could silently
// reintroduce drift in the from-scratch geometry math.
async function grimDebugCompareChunk(cx, cz, seg) {
  seg = seg || 32;
  if (!_grimTerrainWorker) return { cx: cx, cz: cz, seg: seg, ok: false, reason: 'no terrain worker' };
  const mainG = grimComputeChunkGeometryMainThread(cx, cz, seg);
  const ctx = grimTerrainWorkerCtx();
  const dressMain = grimChunkProps(cx, cz, ctx);
  let workerMsg, dressWorker;
  try {
    [workerMsg, dressWorker] = await Promise.all([
      grimWorkerRequest({ type: 'buildChunk', cx: cx, cz: cz, seg: seg }, 10000),
      grimWorkerRequest({ type: 'dressChunk', cx: cx, cz: cz }, 10000)
    ]);
  } catch (e) {
    return { cx: cx, cz: cz, seg: seg, ok: false, reason: 'worker request failed: ' + (e && e.message || e) };
  }
  const results = [
    grimCmpTypedArray('positions', mainG.positions, workerMsg.positions),
    grimCmpTypedArray('colors', mainG.colors, workerMsg.colors),
    grimCmpTypedArray('tiles', mainG.tiles, workerMsg.tiles),
    grimCmpTypedArray('mixes', mainG.mixes, workerMsg.mixes),
    grimCmpTypedArray('normals', mainG.normals, workerMsg.normals),
    grimCmpTypedArray('index', mainG.index, workerMsg.index),
    { name: 'clutterCount', ok: dressMain.clutter.length === dressWorker.clutter.length,
      reason: dressMain.clutter.length + ' vs ' + dressWorker.clutter.length },
    { name: 'nodeCount', ok: dressMain.nodes.length === dressWorker.nodes.length,
      reason: dressMain.nodes.length + ' vs ' + dressWorker.nodes.length },
    { name: 'clutterIdentical', ok: JSON.stringify(dressMain.clutter) === JSON.stringify(dressWorker.clutter) },
    { name: 'nodesIdentical', ok: JSON.stringify(dressMain.nodes) === JSON.stringify(dressWorker.nodes) }
  ];
  return { cx: cx, cz: cz, seg: seg, ok: results.every((r) => r.ok), results: results };
}

// Representative sample per Sec6: varied zones, water edges, bridge pads,
// world-edge chunks. Returns aggregate pass/fail plus every per-chunk
// failure detail, not just a boolean.
async function grimDebugCompareSample() {
  const CHUNKS = [
    [0, 0, 32], [3, -5, 32], [12, 7, 16], [-8, -8, 24], [5, 5, 32],
    [-20, 15, 32], [40, -6, 32], [-340 / 64 | 0, 200 / 64 | 0, 32],
    [200, 200, 32], [-200, -200, 32]
  ];
  const out = [];
  for (const [cx, cz, seg] of CHUNKS) out.push(await grimDebugCompareChunk(cx, cz, seg));
  return { ok: out.every((r) => r.ok), chunks: out };
}

class Component extends DCLogic {"""

out = s.replace(ANCHOR1, WORKER_BLOCK, 1)
assert out != s, 'patch 87.010: anchor1 replacement had no effect'
s = out

# ---- anchor 2: hook worker init into the boot flow, inside layer.then() ----
ANCHOR2 = """        layer.then(() => {
          if (!this.alive) return;
          try {
            if (GRIM_EDIT.on && this._chunks && this._chunks.size) GRIM_EDIT_RENDER.refresh(this);
          } catch (e) {}"""
assert s.count(ANCHOR2) == 1, 'patch 87.010: anchor2 found %d times, wanted 1' % s.count(ANCHOR2)
NEW2 = """        layer.then(() => {
          if (!this.alive) return;
          try { grimInitTerrainWorker(); } catch (e) { console.error('terrain-worker init', e); }
          try {
            if (GRIM_EDIT.on && this._chunks && this._chunks.size) GRIM_EDIT_RENDER.refresh(this);
          } catch (e) {}"""
out = s.replace(ANCHOR2, NEW2, 1)
assert out != s, 'patch 87.010: anchor2 replacement had no effect'
s = out

# ---- expose the debug tool on window.__grim, right after it's set --------
ANCHOR3 = "window.__grim = this;   // test/debug handle"
assert s.count(ANCHOR3) == 1, 'patch 87.010: anchor3 found %d times, wanted 1' % s.count(ANCHOR3)
NEW3 = ANCHOR3 + """
    window.__grim.debugCompareChunk = grimDebugCompareChunk;
    window.__grim.debugCompareSample = grimDebugCompareSample;"""
out = s.replace(ANCHOR3, NEW3, 1)
assert out != s, 'patch 87.010: anchor3 replacement had no effect'
s = out

io.open(PATH, 'w', encoding='utf-8').write(s)
print('87.010_terrain_worker_scaffolding: edited %s (3 anchors)' % PATH)
