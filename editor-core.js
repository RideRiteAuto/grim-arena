// ===========================================================================
// GRIM WORLD - WORLD EDIT LAYER (runtime)
//
// The authored world on top of the generated one: ground paint, roads, placed
// objects, deleted procedural props, terrain deltas, spawn markers, prefabs
// and housing districts.
//
// THIS FILE SHIPS TO PLAYERS. Everything here runs in every client, because a
// player has to see the world Kevin authored. The editor TOOLS live in
// editor-tools.js and the editor UI in editor-ui.js; neither of those does
// anything unless ?edit=1 is on the URL.
//
// Injected into the game bundle by repack.py between the EDITOR markers, the
// same discipline as shared-rules.js and worldgen.js. Never edit the injected
// copy.
//
// Design rules that must hold, because breaking any of them breaks the game
// for people who are not editing anything:
//
//   1. With no layer loaded, every query here must be a single null check and
//      a return. GRIM_WORLD.height is called thousands of times per chunk by
//      the dressing pass, so a slow query is a frame rate bug, not a feature.
//   2. Queries must be PURE and deterministic. The dressing determinism test
//      compares two boots of the same world; anything time or order dependent
//      in here fails it.
//   3. The layer is data, not code. It is fetched over the network from the
//      relay, so it is never eval'd, never trusted for types, and every field
//      is validated on load. A corrupt layer must degrade to the generated
//      world rather than throwing inside a chunk build.
//
// API used by the game:
//   GRIM_EDIT.load(url)           -> Promise, fetches and indexes the layer
//   GRIM_EDIT.on                  -> true when a non-empty layer is applied
//   GRIM_EDIT.heightDelta(x, z)   -> metres to add to the generated terrain
//   GRIM_EDIT.paint(wx, wz, out)  -> rewrites a groundSurface result in place
//   GRIM_EDIT.gone(nid)           -> a procedural prop was deleted here
//   GRIM_EDIT.clears(x, z)        -> authored ground suppresses clutter here
//   GRIM_EDIT.objectsIn(cx, cz)   -> authored objects in that 64m chunk
//   GRIM_EDIT.spawnsIn(cx, cz)    -> authored monster spawns in that chunk
//   GRIM_EDIT.deckY(x, z)         -> walkable deck height, or null
// ===========================================================================
const GRIM_EDIT = (() => {
  const CFG = (typeof GRIM_RULES !== 'undefined' && GRIM_RULES.EDIT) || {
    LAYER: true, UI: true, CELL: 4, PCELL: 1, BLEND_DEFAULT: 2, BLEND_MAX: 4,
    SNAP: 0.5, FEATHER: 1, MAXH: 12, FLATMIN: 0.06, URL: ''
  };
  const CELL = CFG.CELL || 4;              // terrain sculpt grid, metres
  const PCELL = CFG.PCELL || 1;            // ground paint grid, metres
  const BLEND_DEFAULT = CFG.BLEND_DEFAULT || 2;
  const BLEND_MAX = CFG.BLEND_MAX || 4;
  const HALF = 2048;                       // cell-key bias; world is 1200 cells either way
  const PHALF = 8192;                      // paint cell-key bias; PCELL is finer than
  const PMUL = 16384;                      // CELL so the ~4800m world needs a wider key

  function emptyLayer() {
    return {
      v: 1, gen: 0, pcell: PCELL, blend: BLEND_DEFAULT,
      paint: {}, roads: [], objects: [], removed: [],
      height: {}, spawns: [], prefabs: {}, districts: [], bookmarks: []
    };
  }

  let L = null;                            // the live layer
  let rev = 0;                             // server revision it came from
  const api = {
    on: false, ready: false, layer: null, rev: 0, err: null, empty: true,
    CELL: CELL, CFG: CFG
  };

  // ---- indexes ------------------------------------------------------------
  // Built once on load. Every hot query below is a Map lookup or better.
  let paintIdx = null;    // cellKey -> surface index
  let heightIdx = null;   // cellKey -> delta metres
  let goneSet = null;     // Set of deleted procedural node ids
  let objIdx = null;      // "cx,cz" -> [object]
  let spawnIdx = null;    // "cx,cz" -> [spawn]
  let clearIdx = null;    // "cx,cz" -> [{x, z, r}]
  let deckIdx = null;     // "cx,cz" -> [{x, z, y, hw, hd, rot}]
  let roadSegs = null;    // [[x0,z0,x1,z1,halfWidth,surf]]
  let roadGrid = null;    // spatial index over roadSegs
  let paintBounds = null; // {x0,z0,x1,z1} of everything authored, for early-out

  const RCELL = 64;

  function cellKey(cx, cz) { return (cx + HALF) * 4096 + (cz + HALF); }
  function pCellKey(cx, cz) { return (cx + PHALF) * PMUL + (cz + PHALF); }
  function pChunkKey(cx, cz) { return Math.floor(cx * PCELL / 64) + ',' + Math.floor(cz * PCELL / 64); }
  function chunkKey(cx, cz) { return cx + ',' + cz; }
  function num(v, d) { const n = +v; return isFinite(n) ? n : d; }

  // ---- loading ------------------------------------------------------------

  // Validate hard. The layer arrives over the network and is applied inside
  // the chunk builder, where a bad number becomes NaN geometry and the whole
  // world disappears with no error anyone can read.
  function sanitize(raw) {
    const out = emptyLayer();
    if (!raw || typeof raw !== 'object') return out;
    out.v = num(raw.v, 1);
    out.gen = num(raw.gen, 0);

    // Ground paint. A cell coordinate only means something together with the
    // grid size it was authored at, which is why every layer stamps its own
    // pcell. A layer saved before per-layer grids existed has no pcell field
    // at all; CELL was the only grid there was back then, so that is the
    // size to assume for it.
    const oldPcell = num(raw.pcell, CELL);
    if (raw.paint && typeof raw.paint === 'object') {
      const flat = [];
      for (const k in raw.paint) {
        const list = raw.paint[k];
        if (!Array.isArray(list)) continue;
        for (const e of list) {
          if (!Array.isArray(e) || e.length < 3) continue;
          const cx = e[0] | 0, cz = e[1] | 0, s = e[2] | 0;
          if (s < 0 || s > 15) continue;              // 16 surfaces, fixed
          flat.push([cx, cz, s]);
        }
      }
      if (flat.length) {
        const put = (cx, cz, s) => {
          const key = pChunkKey(cx, cz);
          let list = out.paint[key]; if (!list) list = out.paint[key] = [];
          list.push([cx, cz, s]);
        };
        if (oldPcell === PCELL) {
          for (const e of flat) put(e[0], e[1], e[2]);
        } else {
          // The grid has resized since this layer was authored (or last
          // migrated): expand each old cell into every new-grid cell that
          // covers the exact same ground, so a repaint at the old cell size
          // still looks identical and is simply editable at the new,
          // finer size from here on. Nothing painted is lost or moved.
          const n = Math.max(1, Math.round(oldPcell / PCELL));
          for (const e of flat) {
            const ncx0 = e[0] * n, ncz0 = e[1] * n;
            for (let dz = 0; dz < n; dz++) for (let dx = 0; dx < n; dx++) {
              put(ncx0 + dx, ncz0 + dz, e[2]);
            }
          }
        }
      }
    }
    out.pcell = PCELL;
    out.blend = Math.max(0.5, Math.min(BLEND_MAX, num(raw.blend, BLEND_DEFAULT)));
    if (raw.height && typeof raw.height === 'object') {
      const MAXH = CFG.MAXH || 12;
      for (const k in raw.height) {
        const list = raw.height[k];
        if (!Array.isArray(list)) continue;
        const keep = [];
        for (const e of list) {
          if (!Array.isArray(e) || e.length < 3) continue;
          let dy = num(e[2], 0);
          if (!isFinite(dy)) continue;
          if (dy > MAXH) dy = MAXH; if (dy < -MAXH) dy = -MAXH;
          keep.push([e[0] | 0, e[1] | 0, +dy.toFixed(3)]);
        }
        if (keep.length) out.height[k] = keep;
      }
    }
    if (Array.isArray(raw.roads)) {
      for (const r of raw.roads) {
        if (!r || !Array.isArray(r.p) || r.p.length < 2) continue;
        const pts = [];
        for (const p of r.p) {
          if (!Array.isArray(p) || p.length < 2) continue;
          const x = num(p[0], NaN), z = num(p[1], NaN);
          if (!isFinite(x) || !isFinite(z)) continue;
          pts.push([x, z]);
        }
        if (pts.length < 2) continue;
        out.roads.push({
          w: Math.max(1, Math.min(40, num(r.w, 6))),
          s: Math.max(0, Math.min(15, r.s | 0 || 15)),
          p: pts
        });
      }
    }
    if (Array.isArray(raw.objects)) {
      for (const o of raw.objects) {
        if (!o || typeof o.k !== 'string') continue;
        const x = num(o.x, NaN), z = num(o.z, NaN);
        if (!isFinite(x) || !isFinite(z)) continue;
        out.objects.push({
          i: String(o.i || ('o' + out.objects.length)),
          k: o.k.slice(0, 40),
          x: +x.toFixed(3), z: +z.toFixed(3),
          y: +num(o.y, 0).toFixed(3),
          r: +num(o.r, 0).toFixed(4),
          s: Math.max(0.05, Math.min(20, num(o.s, 1))),
          t: o.t ? String(o.t).slice(0, 60) : ''
        });
      }
    }
    if (Array.isArray(raw.spawns)) {
      for (const s of raw.spawns) {
        if (!s || typeof s.k !== 'string') continue;
        const x = num(s.x, NaN), z = num(s.z, NaN);
        if (!isFinite(x) || !isFinite(z)) continue;
        out.spawns.push({
          i: String(s.i || ('s' + out.spawns.length)),
          k: s.k.slice(0, 40),
          x: +x.toFixed(2), z: +z.toFixed(2), y: +num(s.y, 0).toFixed(2),
          n: Math.max(1, Math.min(20, s.n | 0 || 1)),
          rad: Math.max(0, Math.min(120, num(s.rad, 12)))
        });
      }
    }
    if (Array.isArray(raw.removed)) {
      for (const r of raw.removed) if (typeof r === 'string') out.removed.push(r.slice(0, 60));
    }
    if (Array.isArray(raw.bookmarks)) {
      for (const b of raw.bookmarks) {
        if (!b) continue;
        out.bookmarks.push({
          n: String(b.n || 'mark').slice(0, 40),
          x: num(b.x, 0), y: num(b.y, 40), z: num(b.z, 0),
          yaw: num(b.yaw, 0), pit: num(b.pit, -0.5)
        });
      }
    }
    if (raw.prefabs && typeof raw.prefabs === 'object') {
      for (const k in raw.prefabs) {
        const parts = raw.prefabs[k];
        if (!Array.isArray(parts)) continue;
        const keep = [];
        for (const p of parts) {
          if (!p || typeof p.k !== 'string') continue;
          keep.push({
            k: p.k.slice(0, 40), dx: num(p.dx, 0), dz: num(p.dz, 0),
            dy: num(p.dy, 0), r: num(p.r, 0), s: Math.max(0.05, Math.min(20, num(p.s, 1)))
          });
        }
        if (keep.length) out.prefabs[String(k).slice(0, 40)] = keep;
      }
    }
    if (Array.isArray(raw.districts)) {
      for (const d of raw.districts) {
        if (!d || !Array.isArray(d.poly) || d.poly.length < 3) continue;
        const poly = [];
        for (const p of d.poly) {
          if (!Array.isArray(p) || p.length < 2) continue;
          poly.push([num(p[0], 0), num(p[1], 0)]);
        }
        if (poly.length < 3) continue;
        out.districts.push({
          n: String(d.n || 'district').slice(0, 40),
          poly: poly,
          tiers: Array.isArray(d.tiers) ? d.tiers.map(t => t | 0).filter(t => t >= 1 && t <= 3) : [1, 2, 3]
        });
      }
    }
    return out;
  }

  // The object catalog decides which placed objects are solid decks and how
  // much ground they clear. Defined in editor-tools.js so the tools and the
  // renderer cannot disagree; core reads it defensively because core loads
  // first and must work if the tools file is ever dropped from a build.
  function cat(kind) {
    const C = (typeof GRIM_EDIT_CATALOG !== 'undefined') ? GRIM_EDIT_CATALOG : null;
    return (C && C[kind]) || null;
  }

  function reindex() {
    paintIdx = new Map(); heightIdx = new Map(); goneSet = new Set();
    objIdx = new Map(); spawnIdx = new Map(); clearIdx = new Map(); deckIdx = new Map();
    roadSegs = []; roadGrid = new Map();
    let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
    const grow = (x, z, pad) => {
      if (x - pad < x0) x0 = x - pad; if (x + pad > x1) x1 = x + pad;
      if (z - pad < z0) z0 = z - pad; if (z + pad > z1) z1 = z + pad;
    };

    const blendM = (L.blend || BLEND_DEFAULT);
    for (const k in L.paint) {
      for (const e of L.paint[k]) {
        paintIdx.set(pCellKey(e[0], e[1]), e[2]);
        grow(e[0] * PCELL + PCELL / 2, e[1] * PCELL + PCELL / 2, PCELL * 2 + blendM);
      }
    }
    for (const k in L.height) {
      for (const e of L.height[k]) {
        heightIdx.set(cellKey(e[0], e[1]), e[2]);
        grow(e[0] * CELL + CELL / 2, e[1] * CELL + CELL / 2, CELL * 2);
      }
    }
    for (const r of L.removed) goneSet.add(r);

    for (const o of L.objects) {
      const ck = chunkKey(Math.floor(o.x / 64), Math.floor(o.z / 64));
      let b = objIdx.get(ck); if (!b) { b = []; objIdx.set(ck, b); }
      b.push(o);
      const c = cat(o.k);
      grow(o.x, o.z, 8);
      if (c && c.clear) {
        const rr = c.clear * (o.s || 1);
        // A footprint can straddle chunk borders, so it is registered in
        // every chunk it touches. Missing this made trees grow through the
        // corner of a house whenever the house sat near a chunk seam.
        const cx0 = Math.floor((o.x - rr) / 64), cx1 = Math.floor((o.x + rr) / 64);
        const cz0 = Math.floor((o.z - rr) / 64), cz1 = Math.floor((o.z + rr) / 64);
        for (let cx = cx0; cx <= cx1; cx++) for (let cz = cz0; cz <= cz1; cz++) {
          const kk = chunkKey(cx, cz);
          let cb = clearIdx.get(kk); if (!cb) { cb = []; clearIdx.set(kk, cb); }
          cb.push({ x: o.x, z: o.z, r: rr });
        }
      }
      if (c && c.deck) {
        const hw = (c.deck.w * (o.s || 1)) / 2, hd = (c.deck.d * (o.s || 1)) / 2;
        const rr = Math.max(hw, hd) + 1;
        const cx0 = Math.floor((o.x - rr) / 64), cx1 = Math.floor((o.x + rr) / 64);
        const cz0 = Math.floor((o.z - rr) / 64), cz1 = Math.floor((o.z + rr) / 64);
        const rec = { x: o.x, z: o.z, dy: c.deck.h * (o.s || 1) + (o.y || 0), hw, hd, rot: o.r || 0 };
        for (let cx = cx0; cx <= cx1; cx++) for (let cz = cz0; cz <= cz1; cz++) {
          const kk = chunkKey(cx, cz);
          let db = deckIdx.get(kk); if (!db) { db = []; deckIdx.set(kk, db); }
          db.push(rec);
        }
      }
    }
    for (const s of L.spawns) {
      const ck = chunkKey(Math.floor(s.x / 64), Math.floor(s.z / 64));
      let b = spawnIdx.get(ck); if (!b) { b = []; spawnIdx.set(ck, b); }
      b.push(s);
    }

    // Roads: resampled to segments with a uniform grid, the same shape
    // GRIM_WORLD.roadDist uses. One query then touches a handful of segments
    // instead of every road in the world.
    for (const r of L.roads) {
      const pts = smooth(r.p);
      for (let i = 0; i < pts.length - 1; i++) {
        const seg = [pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], r.w / 2, r.s];
        const si = roadSegs.push(seg) - 1;
        const pad = r.w / 2 + blendM + 2;
        grow(seg[0], seg[1], pad); grow(seg[2], seg[3], pad);
        const gx0 = Math.floor((Math.min(seg[0], seg[2]) - pad) / RCELL);
        const gx1 = Math.floor((Math.max(seg[0], seg[2]) + pad) / RCELL);
        const gz0 = Math.floor((Math.min(seg[1], seg[3]) - pad) / RCELL);
        const gz1 = Math.floor((Math.max(seg[1], seg[3]) + pad) / RCELL);
        for (let gx = gx0; gx <= gx1; gx++) for (let gz = gz0; gz <= gz1; gz++) {
          const kk = gx + ',' + gz;
          let b = roadGrid.get(kk); if (!b) { b = []; roadGrid.set(kk, b); }
          b.push(si);
        }
      }
    }

    paintBounds = (x0 === Infinity) ? null : { x0, z0, x1, z1 };
    api.empty = !(paintIdx.size || heightIdx.size || goneSet.size ||
                  L.objects.length || L.spawns.length || roadSegs.length);
    api.on = !api.empty;
    api.layer = L;

    // Indexing is the ONE place the terrain hook is registered, so it can
    // never drift out of step with the layer. Registering it only at boot
    // meant the editor could sculpt a hill into the layer and the world would
    // not move, because the layer had been empty when the game started and
    // the hook was therefore null: Kevin would drag the brush and watch
    // nothing happen.
    try {
      if (typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.setHeightEdit) {
        GRIM_WORLD.setHeightEdit((api.on && heightIdx.size) ? heightDelta : null);
      }
    } catch (e) {}
  }

  // Centripetal-ish Catmull-Rom, resampled at a fixed step. Same curve shape
  // the generated trade routes use, so an authored road and a generated one
  // read as the same kind of thing.
  function smooth(pts) {
    if (pts.length < 3) return pts.slice();
    const STEP = 3, out = [];
    const cr = (a, b, c, d, t) => {
      const t2 = t * t, t3 = t2 * t;
      return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 +
                    (-a + 3 * b - 3 * c + d) * t3);
    };
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i > 0 ? i - 1 : 0], p1 = pts[i], p2 = pts[i + 1];
      const p3 = pts[i + 2 < pts.length ? i + 2 : pts.length - 1];
      const n = Math.max(1, Math.ceil(Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / STEP));
      for (let k = 0; k < n; k++) {
        const t = k / n;
        out.push([cr(p0[0], p1[0], p2[0], p3[0], t), cr(p0[1], p1[1], p2[1], p3[1], t)]);
      }
    }
    out.push(pts[pts.length - 1].slice());
    return out;
  }

  function setLayer(raw) {
    L = sanitize(raw);
    reindex();
    api.ready = true;
    return api;
  }

  // Memoized: the fetch is kicked off as early as the page can manage and
  // whoever asks for it later gets the same promise rather than a second
  // request.
  let loadP = null;
  function load(url) {
    if (!loadP) loadP = doLoad(url);
    return loadP;
  }

  // One attempt at the fetch, with its own hard timeout. Broken out so
  // doLoad can retry it once without duplicating the abort/timer plumbing.
  async function fetchLayerOnce(u, ms) {
    let ac = null, timer = null;
    try {
      try { ac = new AbortController(); } catch (e) { ac = null; }
      if (ac) timer = setTimeout(() => { try { ac.abort(); } catch (e) {} }, ms);
      const res = await fetch(u + (u.indexOf('?') < 0 ? '?' : '&') + 'b=' + Date.now(), {
        method: 'GET', cache: 'no-store', signal: ac ? ac.signal : undefined
      });
      if (!res.ok) throw new Error('http ' + res.status);
      const gotRev = +(res.headers.get('x-edit-rev') || 0) || 0;
      const body = await res.json();
      return { rev: gotRev, body };
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  async function doLoad(url) {
    if (!CFG.LAYER) { setLayer(null); api.on = false; return api; }
    const u = url || CFG.URL;
    if (!u) { setLayer(null); return api; }
    // Boot must never wait on the network for longer than it takes a player
    // to notice. If the relay is slow or unreachable the generated world is
    // shown immediately; the layer is not worth a black screen. A single
    // dropped connection or a cold Durable Object used to mean one lost race
    // silently showed the bare generated map with zero sign of why, so this
    // gets one retry before it gives up - still well inside that budget.
    let lastErr = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const got = await fetchLayerOnce(u, 2500);
        rev = got.rev;
        api.rev = rev;
        setLayer(got.body && got.body.empty ? null : got.body);
        return api;
      } catch (e) {
        lastErr = e;
      }
    }
    // A world edit layer that cannot be fetched must never stop the game
    // booting. The generated world is a complete, playable world; the
    // authored layer is an improvement on it, not a dependency. But two
    // failed tries is worth a clear console line, so this is diagnosable
    // instead of a mystery next time.
    api.err = String((lastErr && lastErr.message) || lastErr);
    try { console.warn('[GRIM_EDIT] authored layer failed to load after 2 tries, showing the generated world:', api.err); } catch (e) {}
    setLayer(null);
    return api;
  }

  // ---- queries the game makes --------------------------------------------

  // Terrain delta, bilinear across the 4m cell grid so sculpted ground is a
  // smooth surface rather than a staircase of 4m steps. Everything that reads
  // terrain (props, bridges, collision, the chunk mesh) goes through
  // GRIM_WORLD.height, so hooking here means an authored hill has trees
  // standing ON it rather than buried in it.
  function heightDelta(x, z) {
    if (!heightIdx || !heightIdx.size) return 0;
    const fx = x / CELL - 0.5, fz = z / CELL - 0.5;
    const ix = Math.floor(fx), iz = Math.floor(fz);
    const tx = fx - ix, tz = fz - iz;
    const a = heightIdx.get(cellKey(ix, iz)) || 0;
    const b = heightIdx.get(cellKey(ix + 1, iz)) || 0;
    const c = heightIdx.get(cellKey(ix, iz + 1)) || 0;
    const d = heightIdx.get(cellKey(ix + 1, iz + 1)) || 0;
    if (!a && !b && !c && !d) return 0;
    const sx = tx * tx * (3 - 2 * tx), sz = tz * tz * (3 - 2 * tz);
    const top = a + (b - a) * sx, bot = c + (d - c) * sx;
    return top + (bot - top) * sz;
  }

  // Nearest road under this point: returns [surface, coverage 0..1] or null.
  function roadAt(x, z) {
    if (!roadSegs || !roadSegs.length) return null;
    const gx = Math.floor(x / RCELL), gz = Math.floor(z / RCELL);
    let bestD = Infinity, bestS = -1, bestW = 0;
    for (let dx = -1; dx <= 1; dx++) {
      for (let dz = -1; dz <= 1; dz++) {
        const b = roadGrid.get((gx + dx) + ',' + (gz + dz));
        if (!b) continue;
        for (let n = 0; n < b.length; n++) {
          const s = roadSegs[b[n]];
          const ax = s[2] - s[0], az = s[3] - s[1];
          const len2 = ax * ax + az * az;
          let t = len2 ? ((x - s[0]) * ax + (z - s[1]) * az) / len2 : 0;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          const px = s[0] + ax * t - x, pz = s[1] + az * t - z;
          const d2 = px * px + pz * pz;
          if (d2 < bestD) { bestD = d2; bestS = s[5]; bestW = s[4]; }
        }
      }
    }
    if (bestS < 0) return null;
    const d = Math.sqrt(bestD);
    // Solid to the edge, then a soft edge so the ribbon does not end on a
    // hard line the way a stencil would. Shares the paint layer's own blend
    // width, so a road and the ground it crosses fade at the same rate.
    const soft = Math.max(0.5, (L && L.blend) || BLEND_DEFAULT);
    if (d > bestW + soft) return null;
    const t = d <= bestW ? 1 : 1 - (d - bestW) / soft;
    return [bestS, t * t * (3 - 2 * t)];
  }

  // Painted surface coverage, blended. Returns [surface, coverage] or null.
  //
  // The nearest painted cell to a deterministically jittered sample point
  // wins as THE surface, so an interior is always exactly what was painted
  // rather than an average of neighbours. Coverage then falls off smoothly
  // with distance out to L.blend metres, weighing every painted cell within
  // that radius rather than just the four immediate corners, so the border
  // is a soft gradient at whatever width was dialled in rather than being
  // stuck at exactly one paint cell wide.
  //
  // Jittering the sample point breaks up the cell grid itself: sampled
  // straight, a boundary follows the grid and reads as stair-steps, and
  // neighbouring vertices jittered together disagree in a noisy way that
  // interlocks instead, the same trick the zone borders use. Pure function
  // of position and the layer, so two machines paint the same border and
  // the dressing determinism test cannot see it.
  function paintAt(x, z) {
    if (!paintIdx || !paintIdx.size) return null;
    const jAmp = PCELL * 0.6;
    const jx = Math.sin(x * 0.83 + z * 1.31) * jAmp;
    const jz = Math.cos(x * 1.17 - z * 0.71) * jAmp;
    const sx = x + jx, sz = z + jz;
    const blend = Math.max(PCELL * 0.5, (L && L.blend) || BLEND_DEFAULT);
    const rc = Math.max(1, Math.ceil(blend / PCELL) + 1);
    const c0 = Math.floor(sx / PCELL), z0 = Math.floor(sz / PCELL);
    let nearSurf, nearD = Infinity;
    const hits = [];                       // flattened [d, surf, d, surf, ...]
    for (let dz = -rc; dz <= rc; dz++) {
      for (let dx = -rc; dx <= rc; dx++) {
        const cx = c0 + dx, cz = z0 + dz;
        const s = paintIdx.get(pCellKey(cx, cz));
        if (s === undefined) continue;
        const wx = (cx + 0.5) * PCELL, wz = (cz + 0.5) * PCELL;
        const ddx = wx - sx, ddz = wz - sz;
        const d = Math.sqrt(ddx * ddx + ddz * ddz);
        if (d > blend + PCELL) continue;
        hits.push(d, s);
        if (d < nearD) { nearD = d; nearSurf = s; }
      }
    }
    if (nearSurf === undefined) return null;
    let wSum = 0, wMatch = 0;
    for (let i = 0; i < hits.length; i += 2) {
      const d = hits[i], s = hits[i + 1];
      const t = Math.min(1, d / blend);
      const w = 1 - t * t * (3 - 2 * t);   // smoothstep falloff, 1 at d=0
      wSum += w;
      if (s === nearSurf) wMatch += w;
    }
    const cov = wSum > 0 ? wMatch / wSum : 1;
    if (cov <= 0.02) return null;
    return [nearSurf, cov];
  }

  // Rewrite a groundSurface() result in place. Roads sit on top of paint, so
  // a road drawn across a painted field still reads as a road.
  //
  // This rides the EXISTING A-to-B blend rather than adding a channel, which
  // is the same trick the bridge abutment pads use: keep whichever surface is
  // locally dominant as A, put the authored surface in B, and hand the
  // coverage to the blend. The feather is then the ground's own feather, so
  // the join is seamless by construction and costs nothing extra to draw.
  function paint(wx, wz, out) {
    if (!api.on) return;
    if (paintBounds && (wx < paintBounds.x0 || wx > paintBounds.x1 ||
                        wz < paintBounds.z0 || wz > paintBounds.z1)) return;
    let hit = paintAt(wx, wz);
    const rd = roadAt(wx, wz);
    if (rd && (!hit || rd[1] >= hit[1])) hit = rd;
    if (!hit) return;
    const surf = hit[0], cov = hit[1];
    const around = (out[4] > 0.5) ? out[1] : out[0];
    if (surf === around) { out[0] = around; out[1] = around; return; }
    out[0] = around; out[1] = surf;
    out[4] = Math.max(out[4] * (1 - cov), cov);
    // Authored ground beats the snow cap and the shore blend: if Kevin paints
    // a courtyard at altitude he means a courtyard, not a courtyard under
    // snow.
    if (cov > 0.6) { out[5] = out[5] * (1 - cov); out[6] = out[6] * (1 - cov); }
  }

  function gone(nid) { return !!(goneSet && goneSet.size && goneSet.has(nid)); }

  // Authored ground suppresses procedural clutter: object footprints, and
  // roads, which should not have grass tufts growing down the middle.
  function clears(x, z) {
    if (!api.on) return false;
    if (clearIdx && clearIdx.size) {
      const b = clearIdx.get(chunkKey(Math.floor(x / 64), Math.floor(z / 64)));
      if (b) for (let i = 0; i < b.length; i++) {
        const dx = x - b[i].x, dz = z - b[i].z;
        if (dx * dx + dz * dz < b[i].r * b[i].r) return true;
      }
    }
    if (roadSegs && roadSegs.length) {
      const rd = roadAt(x, z);
      if (rd && rd[1] > 0.5) return true;
    }
    return false;
  }

  function objectsIn(cx, cz) { return (objIdx && objIdx.get(chunkKey(cx, cz))) || null; }
  function spawnsIn(cx, cz) { return (spawnIdx && spawnIdx.get(chunkKey(cx, cz))) || null; }

  // Walkable deck height at a point, for elevated structures. Pushed into the
  // game's surfaces provider list, so standing on a watchtower deck is the
  // same code path as standing on a bridge.
  function deckY(x, z) {
    if (!deckIdx || !deckIdx.size) return null;
    const b = deckIdx.get(chunkKey(Math.floor(x / 64), Math.floor(z / 64)));
    if (!b) return null;
    let best = null;
    for (let i = 0; i < b.length; i++) {
      const d = b[i];
      let lx = x - d.x, lz = z - d.z;
      if (d.rot) {
        const c = Math.cos(-d.rot), s = Math.sin(-d.rot);
        const nx = lx * c - lz * s; lz = lx * s + lz * c; lx = nx;
      }
      if (lx < -d.hw || lx > d.hw || lz < -d.hd || lz > d.hd) continue;
      const y = groundOf(d.x, d.z) + d.dy;
      if (best === null || y > best) best = y;
    }
    return best;
  }

  // Deck heights are anchored to the ground under the object's origin, not
  // under your feet, or a platform would follow the terrain like a carpet.
  function groundOf(x, z) {
    return (typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.ready) ? GRIM_WORLD.height(x, z) : 0;
  }

  // ---- authoring support (used by the tools, harmless here) ---------------

  function exportLayer() { return JSON.stringify(L || emptyLayer()); }
  function stats() {
    return {
      paint: paintIdx ? paintIdx.size : 0,
      height: heightIdx ? heightIdx.size : 0,
      roads: L ? L.roads.length : 0,
      objects: L ? L.objects.length : 0,
      spawns: L ? L.spawns.length : 0,
      removed: goneSet ? goneSet.size : 0,
      prefabs: L ? Object.keys(L.prefabs).length : 0,
      districts: L ? L.districts.length : 0,
      bytes: L ? exportLayer().length : 0,
      rev: api.rev
    };
  }

  Object.assign(api, {
    load, setLayer, emptyLayer, reindex, sanitize, smooth,
    heightDelta, paint, paintAt, roadAt, gone, clears,
    objectsIn, spawnsIn, deckY, exportLayer, stats, cellKey, chunkKey
  });
  // NOT via Object.assign: assign READS a getter on the source and copies the
  // value it happened to return, which here was null, permanently. Every
  // editor tool reads GRIM_EDIT.raw, so that silently made the whole editor
  // unable to see its own layer while every other check still passed.
  Object.defineProperty(api, 'raw', { get() { return L; }, enumerable: true });
  return api;
})();
