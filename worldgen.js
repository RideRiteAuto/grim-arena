// ===========================================================================
// GRIM WORLD - ASTERRA WORLD GENERATOR (runtime)
//
// Pure deterministic terrain for the whole of Asterra. The macro shape comes
// from worldgen-data.js (baked from "Asterra World Map v2.html" by
// bake_world.py); micro detail is seeded value noise. Same inputs, same
// heights, on every machine — the same discipline as shared-rules.js. This
// file plus the data file are injected into the game bundle by repack.py
// between the WORLD-GEN markers. When the server sim needs terrain, inject
// the same pair into relay-worker.js — never fork the logic.
//
// API (all pure once ready):
//   GRIM_WORLD.init()            -> Promise, decodes the baked layers once
//   GRIM_WORLD.ready             -> true after init resolves
//   GRIM_WORLD.height(x, z)      -> terrain height in meters (sea level = 0)
//   GRIM_WORLD.zone(x, z)        -> zone id (index into GRIM_WORLD.zones)
//   GRIM_WORLD.waterDepth(x, z)  -> meters of water above the ground here
//   GRIM_WORLD.walkable(x, z)    -> inside the charted world, not deep water
//   GRIM_WORLD.anchors           -> [{kind, name, x, z}] settlement/POI sites
//   GRIM_WORLD.toMap(x, z)       -> [mapPx, mapPy] for the world-map screen
//   GRIM_WORLD.roadPaths()       -> smoothed trade routes, [[x,z],...] per road
//   GRIM_WORLD.roadDist(x, z, m) -> metres to the nearest road, capped at m
// ===========================================================================
const GRIM_WORLD = (() => {
  const SEED = 1337;                       // WORLD SEED — never change casually
  const M = WG_META;                       // from worldgen-data.js
  // world meters -> bake grid cells: cell = (world/M_PER_PX + origin_px) / G
  const PX_PER_CELL = M.MAP_W / M.GW;      // 2 map px per cell
  const gx0 = M.ORIGIN[0] / PX_PER_CELL;   // grid coords of world origin
  const gz0 = M.ORIGIN[1] / PX_PER_CELL;

  let elev = null, zone = null, readyP = null;

  async function inflate(b64) {
    const raw = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const ds = new DecompressionStream('deflate');
    const out = new Response(new Blob([raw]).stream().pipeThrough(ds));
    return new Uint8Array(await out.arrayBuffer());
  }

  function init() {
    if (!readyP) readyP = (async () => {
      elev = await inflate(WG_ELEV_B64);
      zone = await inflate(WG_ZONE_B64);
      api.ready = true;
    })();
    return readyP;
  }

  // ---- deterministic value noise -----------------------------------------
  function hash2(ix, iz) {
    let h = (ix * 374761393 + iz * 668265263 + SEED * 971) | 0;
    h = (h ^ (h >> 13)) | 0; h = Math.imul(h, 1274126177); h = (h ^ (h >> 16)) >>> 0;
    return h / 4294967295;                 // 0..1
  }
  function vnoise(x, z) {
    const ix = Math.floor(x), iz = Math.floor(z);
    let fx = x - ix, fz = z - iz;
    fx = fx * fx * (3 - 2 * fx); fz = fz * fz * (3 - 2 * fz);
    const a = hash2(ix, iz), b = hash2(ix + 1, iz);
    const c = hash2(ix, iz + 1), d = hash2(ix + 1, iz + 1);
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fz - 0.5;
  }
  function fbm(x, z) {                     // ~[-0.9, 0.9]
    return vnoise(x / 41, z / 41) + 0.5 * vnoise(x / 16.7 + 71, z / 16.7 - 33)
         + 0.25 * vnoise(x / 6.9 - 19, z / 6.9 + 57);
  }

  // Noise roughness per zone id (meters, matches bake_world.py intent).
  const ROUGH = [0, 3.2, 5.0, 1.6, 2.6, 1.4, 1.8, 5.2, 5.6, 0.7, 2.2, 4.0, 2.0];

  // Terrain is baked flat at gameplay sites; keep the noise out of them too.
  // [x, z, r0, r1] in meters — mirrors the bake's flatten radii.
  const CALM = [];
  for (const a of WG_ANCHORS) {
    if (a.kind === 'capital') CALM.push([a.x, a.z, 190, 350]);
    else if (a.kind === 'choke') CALM.push([a.x, a.z, 62, 126]);
    else if (a.kind === 'bridge') CALM.push([a.x, a.z, 38, 94]);
    else CALM.push([a.x, a.z, 94, 206]);
  }
  function calm(x, z) {
    let m = 1;
    for (let i = 0; i < CALM.length; i++) {
      const c = CALM[i];
      const dx = x - c[0], dz = z - c[1];
      if (dx > c[3] || dx < -c[3] || dz > c[3] || dz < -c[3]) continue;
      const d = Math.sqrt(dx * dx + dz * dz);
      const t = d <= c[2] ? 0 : d >= c[3] ? 1 : (d - c[2]) / (c[3] - c[2]);
      if (t < m) m = t * t * (3 - 2 * t);
    }
    return m;
  }

  // ---- sampling -----------------------------------------------------------
  function gridPos(x, z) {                 // world meters -> fractional cell
    return [x / (M.M_PER_PX * PX_PER_CELL) + gx0, z / (M.M_PER_PX * PX_PER_CELL) + gz0];
  }
  function macro(x, z) {
    const g = gridPos(x, z);
    let cx = g[0] - 0.5, cz = g[1] - 0.5;
    if (cx < 0) cx = 0; if (cz < 0) cz = 0;
    if (cx > M.GW - 1.001) cx = M.GW - 1.001;
    if (cz > M.GH - 1.001) cz = M.GH - 1.001;
    const ix = Math.floor(cx), iz = Math.floor(cz);
    const fx = cx - ix, fz = cz - iz, row = iz * M.GW;
    const a = elev[row + ix], b = elev[row + ix + 1];
    const c = elev[row + M.GW + ix], d = elev[row + M.GW + ix + 1];
    const q = (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fz;
    return q * M.ELEV_SCALE + M.ELEV_OFF;
  }
  function zoneAt(x, z) {
    const g = gridPos(x, z);
    const ix = Math.max(0, Math.min(M.GW - 1, Math.round(g[0] - 0.5)));
    const iz = Math.max(0, Math.min(M.GH - 1, Math.round(g[1] - 0.5)));
    return zone[iz * M.GW + ix];
  }
  function height(x, z) {
    if (!api.ready) return 0;
    const m = macro(x, z);
    if (m < -1.5) return m;                // under water: keep beds smooth
    const zi = zoneAt(x, z);
    // fade the noise out at the waterline so beaches and banks stay gentle
    const shore = Math.min(1, Math.max(0, (m - 0.4) / 3.2));
    return m + fbm(x, z) * (ROUGH[zi] || 1.5) * 0.62 * shore * calm(x, z);
  }
  const bounds = {
    minX: (0 - M.ORIGIN[0]) * M.M_PER_PX, maxX: (M.MAP_W - M.ORIGIN[0]) * M.M_PER_PX,
    minZ: (0 - M.ORIGIN[1]) * M.M_PER_PX, maxZ: (M.MAP_H - M.ORIGIN[1]) * M.M_PER_PX,
  };

  // ---- trade routes -------------------------------------------------------
  // WG_ROADS holds the map's own polyline vertices in world metres. The map
  // draws them as long straight runs between sparse points, which would read
  // as a folded ribbon in three dimensions, so they are smoothed here with a
  // centripetal Catmull-Rom pass and resampled at a fixed step. Built lazily
  // and once: the result is pure, so the renderer, the placement rules and any
  // future server check all read the same curve rather than three copies of it.
  const ROAD_STEP = 4;                    // metres between resampled points
  const RCELL = 64;                       // spatial index cell, metres
  let paths = null, segs = null, grid = null;

  function crSpline(a, b, c, d, t) {      // centripetal-ish, tension 0.5
    const t2 = t * t, t3 = t2 * t;
    return 0.5 * ((2 * b) + (-a + c) * t +
                  (2 * a - 5 * b + 4 * c - d) * t2 +
                  (-a + 3 * b - 3 * c + d) * t3);
  }

  function smoothRoad(pts) {
    if (pts.length < 2) return pts.slice();
    const out = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i > 0 ? i - 1 : 0], p1 = pts[i], p2 = pts[i + 1];
      const p3 = pts[i + 2 < pts.length ? i + 2 : pts.length - 1];
      const n = Math.max(1, Math.ceil(Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / ROAD_STEP));
      for (let k = 0; k < n; k++) {
        const t = k / n;
        out.push([crSpline(p0[0], p1[0], p2[0], p3[0], t),
                  crSpline(p0[1], p1[1], p2[1], p3[1], t)]);
      }
    }
    out.push([pts[pts.length - 1][0], pts[pts.length - 1][1]]);
    return out;
  }

  // Uniform grid over the road segments. Without it, one distance query walks
  // every segment in the world: the dressing pass alone asks this thousands of
  // times per chunk, which would be roughly two million distance tests for a
  // single chunk of grass. With it, a query touches the handful of segments in
  // the cells it actually overlaps.
  function buildRoads() {
    if (paths) return;
    paths = (typeof WG_ROADS !== 'undefined' ? WG_ROADS : []).map(smoothRoad);
    segs = [];
    for (let r = 0; r < paths.length; r++) {
      const p = paths[r];
      for (let i = 0; i < p.length - 1; i++) segs.push([p[i][0], p[i][1], p[i + 1][0], p[i + 1][1]]);
    }
    grid = new Map();
    for (let i = 0; i < segs.length; i++) {
      const s = segs[i];
      const cx0 = Math.floor(Math.min(s[0], s[2]) / RCELL), cx1 = Math.floor(Math.max(s[0], s[2]) / RCELL);
      const cz0 = Math.floor(Math.min(s[1], s[3]) / RCELL), cz1 = Math.floor(Math.max(s[1], s[3]) / RCELL);
      for (let cx = cx0; cx <= cx1; cx++) {
        for (let cz = cz0; cz <= cz1; cz++) {
          const k = cx + ',' + cz;
          let b = grid.get(k);
          if (!b) { b = []; grid.set(k, b); }
          b.push(i);
        }
      }
    }
  }

  // Distance in metres from (x, z) to the nearest road centreline, capped at
  // maxD. Returns maxD when nothing is near, so callers can treat the cap as
  // "far away" without a second branch.
  function roadDist(x, z, maxD) {
    buildRoads();
    if (!segs.length) return maxD;
    const rad = Math.ceil(maxD / RCELL);
    const cx = Math.floor(x / RCELL), cz = Math.floor(z / RCELL);
    let best = maxD * maxD;
    for (let dx = -rad; dx <= rad; dx++) {
      for (let dz = -rad; dz <= rad; dz++) {
        const b = grid.get((cx + dx) + ',' + (cz + dz));
        if (!b) continue;
        for (let n = 0; n < b.length; n++) {
          const s = segs[b[n]];
          const ax = s[2] - s[0], az = s[3] - s[1];
          const len2 = ax * ax + az * az;
          let t = len2 ? ((x - s[0]) * ax + (z - s[1]) * az) / len2 : 0;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          const px = s[0] + ax * t - x, pz = s[1] + az * t - z;
          const d2 = px * px + pz * pz;
          if (d2 < best) best = d2;
        }
      }
    }
    return Math.sqrt(best);
  }
  const api = {
    ready: false, init: init, anchors: WG_ANCHORS, zones: WG_ZONES, bounds: bounds,
    height: height,
    zone: zoneAt,
    waterDepth: (x, z) => { const h = height(x, z); return h < 0 ? -h : 0; },
    // true when baked water (macro < 0) lies within ~3 cells (24 m) — used
    // for beach coloring; raw grid reads, cheap enough for chunk building
    nearWater: (x, z) => {
      if (!api.ready) return false;
      const g = gridPos(x, z);
      const ix = Math.round(g[0] - 0.5), iz = Math.round(g[1] - 0.5);
      const lo = (M.ELEV_OFF !== undefined ? (0 - M.ELEV_OFF) / M.ELEV_SCALE : 80);
      for (let dz = -3; dz <= 3; dz++) {
        const rz = iz + dz;
        if (rz < 0 || rz >= M.GH) continue;
        for (let dx = -3; dx <= 3; dx++) {
          const rx = ix + dx;
          if (rx < 0 || rx >= M.GW) continue;
          if (elev[rz * M.GW + rx] < lo) return true;
        }
      }
      return false;
    },
    bridges: (typeof WG_BRIDGES !== 'undefined' ? WG_BRIDGES : []),
    roadPaths: () => { buildRoads(); return paths; },
    roadSegs: () => { buildRoads(); return segs; },
    roadDist: roadDist,
    walkable: (x, z) =>
      x > bounds.minX + 8 && x < bounds.maxX - 8 &&
      z > bounds.minZ + 8 && z < bounds.maxZ - 8 && height(x, z) > -1.15,
    toMap: (x, z) => [x / M.M_PER_PX + M.ORIGIN[0], z / M.M_PER_PX + M.ORIGIN[1]],
  };
  return api;
})();
