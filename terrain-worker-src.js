// ===========================================================================
// GRIM TERRAIN WORKER -- runs inside a dedicated Web Worker (Phase 1 of
// TERRAIN-WORKER-OFFLOAD-PLAN.md).
//
// Concatenated by repack.py's sync_worker() as:
//   worldgen-data.js + worldgen.js + shared-rules.js + editor-core.js + THIS FILE
// into one string (GRIM_TERRAIN_WORKER_SRC), embedded in game-src.html
// between the WORKERBEGIN/WORKEREND markers, and loaded at runtime via
// `new Worker(URL.createObjectURL(new Blob([GRIM_TERRAIN_WORKER_SRC], ...)))`.
// One source of truth: a change to worldgen.js/shared-rules.js/editor-core.js
// flows into both the main bundle and this worker bundle on the next
// `repack.py pack` -- see repack.py's WORLD-GEN/SHARED-RULES/EDITOR sync
// steps, which this mirrors.
//
// A worker has no `this`, no DOM, no THREE, no window. Everything below is
// either a pure function (the same math the main thread's grim*-prefixed
// module-level functions use -- see game-src.html's own copy, extracted in
// Phase 0) or a from-scratch, THREE-independent rebuild of the one piece
// that needed one: buildChunk's vertex grid + normals (see
// grimBuildChunkGeometry below). Both copies must stay in sync by hand if
// the Phase 0 math ever changes -- there is no shared module scope between
// the main script and a Blob-URL worker, same reason worldgen.js itself is
// synced into two places rather than shared by reference.
//
// GRIM_WORLD initializes itself independently here (own DecompressionStream
// inflate of the same baked WG_ELEV_B64/WG_ZONE_B64 bytes worldgen-data.js
// already carries) -- zero network dependency, byte-identical to the main
// thread's copy by construction. GRIM_EDIT does NOT self-load: the main
// thread's already-fetched, already-sanitized layer is posted in via
// `setLayer` (see the 'editLayer' message below) so there is never a second
// network fetch that could race a server-side layer change mid-session.
// ===========================================================================
'use strict';

// ---- per-session live state, serialized in at init (see TERRAIN-WORKER- --
// ---- OFFLOAD-PLAN.md Sec7 wrinkle 1: this.anvils/campfires/roadSegs/gfx --
// ---- are NOT part of GRIM_WORLD/GRIM_RULES/GRIM_EDIT) --------------------
let _grimCtx = { anvils: [], campfires: [], roadSegs: [], gfx: 'low' };
let _grimEditGen = 0;
let _grimReady = false;
const _grimPending = [];

// Terrain/dressing pure functions -- Phase 0 of the worker offload plan.
// Extracted verbatim (behavior unchanged) from Component's terrain/dressing
// methods below, which now delegate to these. This is prep for Phase 1: a
// Web Worker has no `this`, so these have to exist as free functions before
// they can be copied into terrain-worker-src.js. Byte-diffed against the
// pre-extraction build with harness/phase0-baseline.js -- see
// TERRAIN-WORKER-OFFLOAD-PLAN.md.
//
// A few of these need per-instance "live" state that is not part of
// GRIM_WORLD/GRIM_RULES/GRIM_EDIT: this.anvils, this.campfires, this.roadSegs
// (dressBlocked/chunkProps) and this.gfx (chunkProps, picks the clutter
// density table). Rather than read `this.*` from inside a free function,
// that state is passed explicitly via a small ctx object. This is exactly
// the shape the plan's wrinkle #1 says has to be serialized into the
// worker's init payload in Phase 1, so Phase 0 is setting up that contract
// on purpose, not inventing a new one later.

function grimRoadsOn() { return false; }

let _grimZoneVariants = null;
function grimZoneVariantsTable() {
  return _grimZoneVariants || (_grimZoneVariants = {
    HEARTLANDS: [
      { n: 'pasture',    surf: [0, 0], dens: 1.20, node: 0.8, clut: [['tallgrass', 10], ['flower', 5], ['tuft', 4], ['bush', 2], ['pebble', 2]] },
      { n: 'wheatfield', surf: [1, 0], dens: 0.85, node: 0.4, clut: [['wheat', 13], ['hay', 2], ['tuft', 2], ['stick', 1]] },
      { n: 'heath',      surf: [2, 0], dens: 0.90, node: 0.7, clut: [['tuft', 8], ['bush', 5], ['pebble', 4], ['stick', 2]] },
      { n: 'copse',      surf: [3, 0], dens: 1.35, node: 2.2, clut: [['fern', 6], ['tallgrass', 5], ['stick', 5], ['log', 2], ['bush', 3]] },
      { n: 'stonyrise',  surf: [7, 2], dens: 0.55, node: 0.9, clut: [['pebble', 9], ['boulder', 4], ['tuft', 3]] }
    ],
    GREENWOOD: [
      { n: 'densewood',  surf: [3, 4], dens: 1.40, node: 2.4, clut: [['fern', 9], ['stick', 6], ['log', 3], ['bush', 5], ['tuft', 2]] },
      { n: 'clearing',   surf: [0, 3], dens: 1.05, node: 0.5, clut: [['tallgrass', 10], ['flower', 4], ['tuft', 4], ['stick', 2]] },
      { n: 'fernhollow', surf: [4, 3], dens: 1.30, node: 1.4, clut: [['fern', 12], ['bush', 4], ['log', 2], ['pebble', 1]] },
      { n: 'deadfall',   surf: [3, 2], dens: 1.10, node: 1.6, clut: [['log', 6], ['stick', 9], ['fern', 3], ['bush', 2]] }
    ],
    FROSTWILD: [
      { n: 'snowfield',  surf: [5, 5], dens: 0.55, node: 0.7, clut: [['drift', 9], ['tuft', 2], ['pebble', 2]] },
      { n: 'windrock',   surf: [6, 5], dens: 0.70, node: 1.0, clut: [['pebble', 8], ['boulder', 3], ['drift', 4]] },
      { n: 'frozenscrub',surf: [5, 6], dens: 1.00, node: 1.3, clut: [['bush', 6], ['tuft', 5], ['drift', 4], ['stick', 3]] }
    ],
    IRONSPIRE: [
      { n: 'scree',      surf: [7, 8], dens: 0.75, node: 1.2, clut: [['pebble', 12], ['boulder', 5]] },
      { n: 'barerock',   surf: [8, 7], dens: 0.40, node: 1.0, clut: [['pebble', 8], ['boulder', 6]] },
      { n: 'alpinegrass',surf: [2, 7], dens: 1.05, node: 0.8, clut: [['tuft', 9], ['bush', 3], ['pebble', 5]] }
    ],
    SUNCOAST: [
      { n: 'dune',       surf: [9, 10], dens: 0.60, node: 0.5, clut: [['shell', 6], ['tuft', 4], ['pebble', 2]] },
      { n: 'coastgrass', surf: [10, 0], dens: 1.10, node: 1.1, clut: [['tuft', 10], ['bush', 4], ['stick', 3], ['shell', 2]] },
      { n: 'shingle',    surf: [7, 9], dens: 0.80, node: 0.9, clut: [['pebble', 11], ['shell', 5], ['boulder', 2]] }
    ],
    WINDSCAR: [
      { n: 'opensteppe', surf: [11, 11], dens: 0.85, node: 0.6, clut: [['wheat', 11], ['tuft', 5]] },
      { n: 'dryheath',   surf: [2, 11], dens: 1.00, node: 1.0, clut: [['tuft', 9], ['bush', 4], ['wheat', 4], ['pebble', 2]] },
      { n: 'bonefield',  surf: [11, 7], dens: 0.75, node: 1.1, clut: [['bone', 7], ['pebble', 5], ['tuft', 4], ['bush', 1]] }
    ],
    EMBER: [
      { n: 'cinderplain',surf: [12, 12], dens: 0.80, node: 1.0, clut: [['ash', 9], ['shard', 4], ['pebble', 3]] },
      { n: 'ashdrift',   surf: [12, 8], dens: 0.65, node: 0.8, clut: [['ash', 12], ['stick', 2]] },
      { n: 'scorchrock', surf: [8, 12], dens: 0.70, node: 1.3, clut: [['shard', 8], ['pebble', 6], ['boulder', 3]] }
    ],
    EMBER_HI: [
      { n: 'corecinder', surf: [12, 12], dens: 0.60, node: 1.2, clut: [['ash', 8], ['shard', 7], ['pebble', 3]] }
    ],
    MISTFEN: [
      { n: 'bog',        surf: [13, 13], dens: 1.05, node: 1.1, clut: [['reed', 11], ['fern', 4], ['tuft', 3]] },
      { n: 'reedbed',    surf: [13, 4], dens: 1.30, node: 0.8, clut: [['reed', 14], ['tuft', 3]] },
      { n: 'sunkenwood', surf: [3, 13], dens: 1.20, node: 1.9, clut: [['log', 6], ['fern', 6], ['reed', 4], ['stick', 4]] }
    ],
    SUNSCORCH: [
      { n: 'dunesea',    surf: [14, 14], dens: 0.45, node: 0.5, clut: [['pebble', 4], ['bone', 2]] },
      { n: 'hardpan',    surf: [2, 14], dens: 0.75, node: 1.0, clut: [['pebble', 7], ['tuft', 4], ['bone', 3], ['shard', 2]] },
      { n: 'stonywaste', surf: [7, 14], dens: 0.70, node: 1.2, clut: [['pebble', 10], ['boulder', 3], ['bone', 3]] }
    ],
    EASTRIDGE: [
      { n: 'ridgeslate', surf: [8, 6], dens: 0.60, node: 1.0, clut: [['pebble', 10], ['boulder', 4], ['tuft', 2]] },
      { n: 'ridgescree', surf: [6, 8], dens: 0.75, node: 1.1, clut: [['pebble', 12], ['boulder', 3], ['bush', 1]] }
    ],
    ISLES: [
      { n: 'isleGrass',  surf: [10, 0], dens: 1.10, node: 1.2, clut: [['tuft', 9], ['bush', 4], ['shell', 3], ['stick', 3]] },
      { n: 'isleSand',   surf: [9, 10], dens: 0.65, node: 0.6, clut: [['shell', 7], ['pebble', 4], ['tuft', 3]] }
    ]
  });
}

// Nearest jittered cell centre on the variant grid. Pure, deterministic, and
// cheap enough to call per vertex and per prop.
function grimVariantCell() { return 180; }
function grimZoneVariant(zoneName, wx, wz) {
  const list = grimZoneVariantsTable()[zoneName];
  if (!list || !list.length) return null;
  if (list.length === 1) return list[0];
  const C = grimVariantCell();
  const cx = Math.floor(wx / C), cz = Math.floor(wz / C);
  let best = 1e18, pick = 0;
  for (let dx = -1; dx <= 1; dx++) {
    for (let dz = -1; dz <= 1; dz++) {
      const gx = cx + dx, gz = cz + dz;
      // one hash, three uses: two for the jitter, one for the choice
      let h = (gx * 374761393 + gz * 668265263) | 0;
      h = (h ^ (h >> 13)) | 0; h = Math.imul(h, 1274126177); h = (h ^ (h >> 16)) >>> 0;
      const jx = ((h & 1023) / 1023 - 0.5) * 0.78;
      const jz = (((h >>> 10) & 1023) / 1023 - 0.5) * 0.78;
      const px = (gx + 0.5 + jx) * C, pz2 = (gz + 0.5 + jz) * C;
      const ddx = wx - px, ddz = wz - pz2;
      const d = ddx * ddx + ddz * ddz;
      if (d < best) { best = d; pick = (h >>> 20) % list.length; }
    }
  }
  return list[pick];
}

// Bridge geometry for one bridge object, memoized onto the bridge itself
// (b._g) since GRIM_WORLD.bridges is baked static data, not mutable session
// state -- same memo pattern as the zone/palette tables above.
function grimBridgeGeom(b) {
  if (b._g) return b._g;
  const cause = b.kind === 'causeway';
  const dx = Math.sin(b.heading), dz = Math.cos(b.heading);
  let half = b.span / 2;
  const ramp = cause ? 12 : 8;
  const bank = (sgn) => {
    const step = 1.0, maxOut = 34;
    let d = half;
    for (let s = 0; s <= maxOut; s += step) {
      const px2 = b.x + dx * sgn * (half + s), pz2 = b.z + dz * sgn * (half + s);
      d = half + s;
      const wet = GRIM_WORLD.ready ? GRIM_WORLD.waterDepth(px2, pz2) : 0;
      if (wet <= 0.02) break;                 // first dry ground on this side
    }
    return d;
  };
  const dA = bank(-1), dB = bank(1);
  half = Math.max(half, dA, dB);
  const hA = GRIM_WORLD.height(b.x - dx * (dA + ramp), b.z - dz * (dA + ramp));
  const hB = GRIM_WORLD.height(b.x + dx * (dB + ramp), b.z + dz * (dB + ramp));
  const deckY = Math.max(hA, hB, 1.6) + (cause ? 1.4 : 1.0);
  b._g = { dx: dx, dz: dz, half: half, ramp: ramp, hA: hA, hB: hB, dA: dA, dB: dB,
           deckY: deckY, wide: (cause ? 6.4 : 4.6) * 0.5, cause: cause };
  return b._g;
}

// The pad is an ellipse: long in the direction you walk on and off the deck,
// narrow across it. Its edge radius is jittered by the same kind of cheap
// trig noise the ground blend uses, so it never reads as a drawn circle.
function grimBridgePad(wx, wz) {
  const B = GRIM_WORLD.bridges;
  if (!B || !B.length) return 0;
  let best = 0;
  for (let i = 0; i < B.length; i++) {
    const b = B[i];
    const rx = wx - b.x, rz = wz - b.z;
    const reach = b.span * 0.5 + 46;
    if (rx > reach || rx < -reach || rz > reach || rz < -reach) continue;
    const g = grimBridgeGeom(b);
    const along = rx * g.dx + rz * g.dz;
    const across = rx * g.dz - rz * g.dx;
    const foot = g.half + g.ramp * 0.55;
    const da = Math.abs(along) - foot;
    const LA = g.ramp + 13, LC = g.wide + 7.5;
    const u = (da < 0 ? da * 1.9 : da) / LA, v = across / LC;
    let e = Math.sqrt(u * u + v * v);
    e += Math.sin(wx / 5.3 + wz / 7.1) * 0.085 + Math.sin(wz / 4.1 - wx / 6.7) * 0.065;
    if (e >= 1) continue;
    const w = 1 - Math.max(0, Math.min(1, (e - 0.34) / 0.66));
    const s = w * w * (3 - 2 * w);
    if (s > best) best = s;
  }
  return best;
}

// What a worn patch looks like depends on what it is worn INTO. Dirt through
// grass, sand on a beach, gravel above the snow line. Anything else would be
// a brown disc sitting on a white bank.
function grimPadSurfaceFor(base) {
  if (base === 9 || base === 10) return 9;    // coast and dune stay sand
  if (base === 14) return 14;                 // desert stays desert sand
  if (base === 5 || base === 6) return 7;     // snow and frozen scree: gravel
  if (base === 12) return 8;                  // cinder: bare slate
  return 15;                                  // everywhere else: packed dirt
}

let _grimZoneSurf = null;
function grimGroundSurface(zi, h, wx, wz, out) {
  // [base A, base B, rock for steep ground, cap above the tree line]
  const Z = _grimZoneSurf || (_grimZoneSurf = [
    [0, 0, 8, 8],     // SEA (never drawn dry)
    [5, 6, 6, 5],     // FROSTWILD   snow / scree
    [7, 8, 8, 5],     // IRONSPIRE   gravel / slate
    [0, 2, 8, 8],     // HEARTLANDS  meadow / heath
    [3, 4, 8, 8],     // GREENWOOD   forest floor / moss
    [10, 9, 7, 8],    // SUNCOAST    dry coastal / sand
    [11, 2, 8, 8],    // WINDSCAR    steppe / heath
    [12, 8, 8, 8],    // EMBER       cinder / slate
    [12, 12, 8, 8],   // EMBER_HI    cinder
    [13, 4, 8, 8],    // MISTFEN     bog / moss
    [14, 2, 7, 8],    // SUNSCORCH   desert / heath
    [8, 6, 6, 5],     // EASTRIDGE   slate / scree
    [10, 0, 7, 8]     // ISLES       dry coastal / meadow
  ]);
  const p = Z[zi] || Z[3];
  out[2] = p[2]; out[3] = p[3];                  // rock and cap stay per zone
  const V = grimZoneVariant(grimZoneName(zi), wx, wz);
  if (V) { out[0] = V.surf[0]; out[1] = V.surf[1]; }
  else { out[0] = p[0]; out[1] = p[1]; }

  const d = Math.sin(wx / 47.3 + Math.cos(wz / 61.7) * 1.7) * 0.62 +
            Math.sin(wz / 38.1 - Math.cos(wx / 71.3) * 1.3) * 0.62 +
            Math.sin(wx / 132.0 - wz / 158.0) * 0.34;
  const raw = Math.max(0, Math.min(1, 0.5 + d * 0.58));
  const s0 = Math.max(0, Math.min(1, (raw - 0.40) / 0.20));
  out[4] = s0 * s0 * (3 - 2 * s0);

  out[5] = 0;

  const pad = grimBridgePad(wx, wz);
  if (pad > 0.002) {
    const around = (out[4] > 0.5) ? out[1] : out[0];
    const worn = grimPadSurfaceFor(around);
    if (worn !== around) {
      out[0] = around; out[1] = worn;
      out[4] = Math.max(out[4] * (1 - pad), pad);
    }
  }

  {
    const capR = (typeof GRIM_EDIT !== 'undefined') ? GRIM_EDIT.raw : null;
    const capLo = (capR && capR.capLo != null) ? capR.capLo : 52;
    const capHi = (capR && capR.capHi != null) ? capR.capHi : 78;
    out[6] = Math.max(0, Math.min(1, (h - capLo) / Math.max(1, capHi - capLo)));
  }

  GRIM_EDIT.paint(wx, wz, out);
}

let _grimZonePal = null, _grimCBed = null, _grimCSnow = null, _grimCRock = null;
function grimTerrainColor(zi, h, wx, wz, out) {
  // Zone data lives on an 8m grid; sampling it point-blank drew hard
  // stair-stepped seams where regions meet. Blend five spread samples with
  // a dithered offset so each biome fades into the next over ~15m.
  const P = _grimZonePal || (_grimZonePal = [
    [0.42, 0.50, 0.44], [0.78, 0.82, 0.78], [0.55, 0.50, 0.40], [0.45, 0.55, 0.30],
    [0.33, 0.44, 0.26], [0.62, 0.60, 0.38], [0.60, 0.56, 0.32], [0.52, 0.38, 0.30],
    [0.45, 0.32, 0.26], [0.38, 0.46, 0.34], [0.72, 0.60, 0.38], [0.62, 0.62, 0.60],
    [0.58, 0.56, 0.38]]);
  const BED = _grimCBed || (_grimCBed = [0.55, 0.52, 0.40]);
  const SNOW = _grimCSnow || (_grimCSnow = [0.88, 0.90, 0.92]);
  const ROCK = _grimCRock || (_grimCRock = [0.50, 0.47, 0.44]);
  const base = (z2) => {
    if (h < 0) return BED;
    if ((z2 === 1 || z2 === 11) && h > 24) return SNOW;
    if (h > 46 && z2 !== 10) return ROCK;
    return P[z2] || P[3];
  };
  let r = 0, g2 = 0, b = 0;
  for (let i = 0; i < 5; i++) {
    const ang = i * 2.51, rad = i ? 8.5 : 0;
    const jx = Math.sin(Math.floor(wx) * 12.9898 + Math.floor(wz) * 78.233 + i * 37.7) * 4.2;
    const c = base(GRIM_WORLD.zone(wx + Math.sin(ang) * rad + jx, wz + Math.cos(ang) * rad - jx));
    r += c[0]; g2 += c[1]; b += c[2];
  }
  r /= 5; g2 /= 5; b /= 5;
  const j = (Math.sin(Math.floor(wx * 0.5) * 12.9898 + Math.floor(wz * 0.5) * 78.233) * 43758.5453) % 1;
  const k = 0.92 + 0.16 * Math.abs(j);
  const sh = h < 0 ? Math.max(0.45, 1 + h * 0.045) : Math.min(1.08, 0.95 + h * 0.0032);
  out.r = r * k * sh; out.g = g2 * k * sh; out.b = b * k * sh;
}

// Per-vertex fill for one chunk's plane geometry. Factored verbatim out of
// buildChunk's loop body (the plan's "buildChunkVerts", new in Phase 0).
// Takes the already-built PlaneGeometry position attribute (pa) plus the
// chunk's world origin, mutates pa's Y in place (height), and returns the
// color/tile/mix typed arrays. Grid layout (new T.PlaneGeometry) and
// computeVertexNormals() stay in buildChunk on the main thread for this
// phase: a from-scratch, THREE-independent grid+normal rebuild (matching
// PlaneGeometry.js / BufferGeometry.js:computeVertexNormals bit-for-bit) is
// real work the worker needs in Phase 1, not something Phase 0's "zero
// behavior change" pass should also be doing at the same time.
let _grimSurfBuf = null;
function grimBuildChunkVerts(pa, x0, z0) {
  const colors = new Float32Array(pa.count * 3);
  const tiles = new Float32Array(pa.count * 4);
  const mixes = new Float32Array(pa.count * 3);
  const c = { r: 0, g: 0, b: 0 };
  const su = _grimSurfBuf || (_grimSurfBuf = [0, 0, 0, 0, 0, 0, 0]);
  for (let i = 0; i < pa.count; i++) {
    const wx = pa.getX(i) + x0, wz = pa.getZ(i) + z0;
    const h = GRIM_WORLD.height(wx, wz);
    pa.setY(i, h - 0.03);
    // The zone is sampled at a per-vertex jittered offset, the same trick
    // terrainColor already uses. With flat indices a zone border would
    // otherwise be a dead straight line; jittering makes neighbouring
    // vertices disagree in a noisy way, so the change interlocks instead.
    const jx = Math.sin(wx * 0.7 + wz * 1.3) * 5.5;
    const jz = Math.cos(wx * 1.1 - wz * 0.9) * 5.5;
    const zi = GRIM_WORLD.zone(wx + jx, wz + jz);
    grimTerrainColor(GRIM_WORLD.zone(wx, wz), h, wx, wz, c);
    colors[i * 3] = 0.55 + c.r * 0.78;
    colors[i * 3 + 1] = 0.55 + c.g * 0.78;
    colors[i * 3 + 2] = 0.55 + c.b * 0.78;
    grimGroundSurface(zi, h, wx, wz, su);
    tiles[i * 4] = su[0]; tiles[i * 4 + 1] = su[1];
    tiles[i * 4 + 2] = su[2]; tiles[i * 4 + 3] = su[3];
    mixes[i * 3] = su[4]; mixes[i * 3 + 1] = su[5]; mixes[i * 3 + 2] = su[6];
  }
  return { colors: colors, tiles: tiles, mixes: mixes };
}

// How a clutter type clumps: [min count, max count, radius in metres].
function grimClutterClump(type) {
  const C = {
    wheat: [4, 7, 1.9], reed: [4, 7, 1.6], flower: [3, 6, 1.7], tuft: [3, 5, 1.6],
    tallgrass: [5, 9, 2.4],
    fern: [2, 4, 1.6], pebble: [2, 5, 1.5], shell: [2, 4, 1.3], ash: [2, 4, 2.1],
    shard: [2, 4, 1.5], drift: [2, 3, 2.0], bone: [1, 3, 1.4], stick: [1, 3, 1.5],
    bush: [1, 2, 1.8], boulder: [1, 2, 2.2], log: [1, 1, 0], hay: [1, 3, 2.4]
  };
  return C[type] || [1, 2, 1.4];
}

let _grimZoneClutter = null;
function grimZoneClutterTable() {
  return _grimZoneClutter || (_grimZoneClutter = {
    HEARTLANDS: [['tallgrass', 9], ['wheat', 6], ['flower', 4], ['tuft', 3], ['bush', 2], ['pebble', 3], ['stick', 2]],
    GREENWOOD:  [['tallgrass', 6], ['fern', 7], ['bush', 5], ['tuft', 3], ['log', 2], ['stick', 4], ['pebble', 2]],
    FROSTWILD:  [['drift', 6], ['tuft', 3], ['bush', 2], ['pebble', 5], ['stick', 3]],
    IRONSPIRE:  [['pebble', 9], ['boulder', 4], ['tuft', 2], ['bush', 1]],
    SUNCOAST:   [['tuft', 5], ['shell', 4], ['pebble', 4], ['stick', 3], ['bush', 2]],
    WINDSCAR:   [['wheat', 8], ['tuft', 4], ['bone', 2], ['pebble', 2], ['bush', 1]],
    EMBER:      [['ash', 6], ['shard', 4], ['pebble', 4], ['stick', 3], ['bush', 1]],
    MISTFEN:    [['reed', 7], ['fern', 4], ['tuft', 3], ['log', 2], ['pebble', 1]],
    SUNSCORCH:  [['pebble', 6], ['bone', 3], ['tuft', 3], ['bush', 2], ['shard', 2]],
    EASTRIDGE:  [['pebble', 8], ['boulder', 3], ['tuft', 3], ['bush', 1]],
    ISLES:      [['tuft', 5], ['shell', 4], ['pebble', 3], ['stick', 3], ['bush', 2]]
  });
}

// ---- placement rules -------------------------------------------------------
// Water, roads and town ground are all hard rejections rather than nudges: a
// nudged prop would move if the rule ever changed, and a moved prop is a
// desynced prop.
//
// ctx = { anvils, campfires, roadSegs } -- see the header note above on why
// these are passed in rather than read off `this`.
function grimDressBlocked(x, z, ctx) {
  if (!GRIM_WORLD.ready) return true;
  const h = GRIM_WORLD.height(x, z);
  if (h < 0.35) return true;                       // the water wall
  if (!GRIM_WORLD.walkable(x, z)) return true;
  const TC = GRIM_RULES.GATHER.TOWN_CLEAR;
  for (const s of GRIM_RULES.SAFE) {
    const r = s.r + TC;
    if ((x - s.x) * (x - s.x) + (z - s.z) * (z - s.z) < r * r) return true;
  }
  for (const a of (GRIM_WORLD.anchors || [])) {
    if (a.kind !== 'town' && a.kind !== 'capital' && a.kind !== 'port') continue;
    if ((x - a.x) * (x - a.x) + (z - a.z) * (z - a.z) < TC * TC) return true;
  }
  const RC = GRIM_RULES.GATHER.ROAD_CLEAR, RC2 = RC * RC;
  if (grimRoadsOn() && GRIM_WORLD.roadDist(x, z, RC) < RC) return true;
  for (const s of ((ctx && ctx.roadSegs) || [])) {
    const dx = s[2] - s[0], dz = s[3] - s[1];
    const len2 = dx * dx + dz * dz;
    let t = len2 ? ((x - s[0]) * dx + (z - s[1]) * dz) / len2 : 0;
    t = t < 0 ? 0 : t > 1 ? 1 : t;
    const px = s[0] + dx * t - x, pz = s[1] + dz * t - z;
    if (px * px + pz * pz < RC2) return true;
  }
  for (const a of ((ctx && ctx.anvils) || [])) {
    const r = a.radius + 1.0;
    if ((x - a.x) * (x - a.x) + (z - a.z) * (z - a.z) < r * r) return true;
  }
  for (const f of ((ctx && ctx.campfires) || [])) {
    const r = f.radius + 1.2;
    if ((x - f.x) * (x - f.x) + (z - f.z) * (z - f.z) < r * r) return true;
  }
  const e = 1.5;
  const gx = (GRIM_WORLD.height(x + e, z) - h) / e;
  const gz = (GRIM_WORLD.height(x, z + e) - h) / e;
  return (gx * gx + gz * gz) > 1.2;
}

let _grimZoneTbl = null;
function grimZoneNodeTable(zone, deep) {
  const key = zone + (deep ? ':deep' : '');
  _grimZoneTbl = _grimZoneTbl || {};
  if (_grimZoneTbl[key]) return _grimZoneTbl[key];
  const out = [];
  const N = GRIM_RULES.GATHER.NODES;
  for (const k in N) {
    const nd = N[k];
    if (nd.legacy || !nd.zones || nd.zones.indexOf(zone) < 0) continue;
    if (nd.deep && !deep) continue;
    if (nd.water) continue;
    out.push({ kind: k, w: nd.rare ? 0.4 : (24 / (12 + nd.lvl)) });
  }
  let tot = 0; for (const o of out) tot += o.w;
  _grimZoneTbl[key] = { list: out, total: tot };
  return _grimZoneTbl[key];
}

// ---- THE PURE GENERATOR -----------------------------------------------------
// Given a chunk, return exactly what stands on it. No scene, no player, no
// clock, no randomness that is not seeded off the chunk itself. This is the
// function the determinism test asserts on.
//
// ctx = { anvils, campfires, roadSegs, gfx } -- gfx only scales clutter
// COUNT after an identical seeded draw, never which values get drawn (see
// the inline comment below); node placement never reads gfx at all, so two
// players on different graphics settings still agree on every node id.
function grimChunkProps(cx, cz, ctx) {
  const CH = 64, x0 = cx * CH, z0 = cz * CH;
  const G = GRIM_RULES.GATHER;
  const rnd = grimRnd(grimSeed(cx, cz, 'dress'));
  const clutter = [], nodes = [];
  const gs = (GRIM_RULES.GFX_SCALE || {})[(ctx && ctx.gfx) === 'high' ? 'high' : 'low'] || { clutter: 1 };
  const cFull = G.CLUTTER_PER_CHUNK[0] + Math.floor(rnd() * (G.CLUTTER_PER_CHUNK[1] - G.CLUTTER_PER_CHUNK[0] + 1));
  const cN = Math.max(6, Math.round(cFull * (gs.clutter || 1)));
  const nN = G.NODES_PER_CHUNK[0] + Math.floor(grimRnd(grimSeed(cx, cz, 'nodecount'))() * (G.NODES_PER_CHUNK[1] - G.NODES_PER_CHUNK[0] + 1));

  let guard = 0;
  while (clutter.length < cN && guard++ < 200) {
    const x = x0 + rnd() * CH, z = z0 + rnd() * CH;
    const rot = rnd() * Math.PI * 2, sc = 0.7 + rnd() * 0.8, pick = rnd();
    const spread = rnd(), count = rnd();
    if (grimDressBlocked(x, z, ctx)) continue;
    const bake = GRIM_WORLD.zone(x, z);
    const zone = grimZoneName(bake);
    if (zone === 'SEA') continue;
    const V = grimZoneVariant(zone, x, z);
    const set = (V && V.clut) || grimZoneClutterTable()[zone] || grimZoneClutterTable().HEARTLANDS;
    let mt = 0;
    for (const e of set) mt += e[1];
    let acc = pick * mt, type = set[0][0];
    for (const e of set) { if (acc < e[1]) { type = e[0]; break; } acc -= e[1]; }
    if (zone === 'HEARTLANDS' && type === 'wheat') {
      const d = Math.hypot(x, z);
      if (d < 220 && pick > 0.93) type = 'hay';
    }
    const cl = grimClutterClump(type);
    const dens = (V && V.dens) || 1;
    const n = Math.max(1, Math.round((cl[0] + Math.floor(count * (cl[1] - cl[0] + 1))) * dens));
    for (let j = 0; j < n && clutter.length < cN; j++) {
      const a = (j * 2.39996 + spread * 6.283);
      const r = cl[2] * Math.sqrt((j + 0.35) / n);
      const px = x + Math.cos(a) * r, pz = z + Math.sin(a) * r;
      if (grimDressBlocked(px, pz, ctx)) continue;
      clutter.push({
        type: type, zone: zone, x: px, z: pz, y: GRIM_WORLD.height(px, pz),
        rot: rot + j * 1.7, sc: sc * (0.78 + ((j * 37) % 11) / 24)
      });
    }
  }

  const rndN = grimRnd(grimSeed(cx, cz, 'nodes'));
  for (let i = 0; i < nN; i++) {
    const x = x0 + 4 + rndN() * (CH - 8), z = z0 + 4 + rndN() * (CH - 8);
    const rot = rndN() * Math.PI * 2, roll = rndN(), sc = 0.9 + rndN() * 0.35;
    if (grimDressBlocked(x, z, ctx)) continue;
    const bake = GRIM_WORLD.zone(x, z);
    const zone = grimZoneName(bake);
    if (zone === 'SEA') continue;
    const tbl = grimZoneNodeTable(zone, grimZoneIsDeep(bake));
    if (!tbl.total) continue;
    const Vn = grimZoneVariant(zone, x, z);
    if (Vn && Vn.node !== undefined && rndN() > Math.min(1, Vn.node)) continue;
    let acc = roll * tbl.total, kind = tbl.list[0].kind;
    for (const o of tbl.list) { if (acc < o.w) { kind = o.kind; break; } acc -= o.w; }
    let clash = false;
    for (const p of nodes) { const dx = p.x - x, dz = p.z - z; if (dx * dx + dz * dz < 64) { clash = true; break; } }
    if (clash) continue;
    nodes.push({ kind: kind, zone: zone, x: x, z: z, y: GRIM_WORLD.height(x, z), rot: rot, sc: sc,
                 nid: grimNodeId(cx, cz, i) });
  }
  return { clutter: clutter, nodes: nodes };
}
// ============================================================================

// ---------------------------------------------------------------------------
// From-scratch chunk vertex grid + normals, no THREE (Phase 1). Independently
// re-derived from three@0.160.1's own source (PlaneGeometry.js,
// BufferGeometry.js: rotateX/computeVertexNormals, Matrix4/Vector3 math) so
// this is bit-identical to what buildChunk's THREE-based pipeline produces
// today -- verified by direct byte-diff against real three@0.160.1 output
// across varied chunk coords and segment counts, not assumed. three is
// pinned to 0.160.1 in this repo on purpose (see harness/README.md); if that
// ever changes, re-run the debug byte-diff tool (window.__grim.debugCompareChunk
// in the main bundle) before trusting this again -- TERRAIN-WORKER-OFFLOAD-
// PLAN.md Sec6 flags this exact risk.
//
// Why this can skip literally replaying buildChunk's g.rotateX(-Math.PI/2):
// PlaneGeometry pushes each vertex as (x, -y, 0); rotateX(-PI/2) uses
// c=Math.cos(-PI/2) (~6.12e-17, not exactly 0) and s=Math.sin(-PI/2) (exactly
// -1), giving rotated (x, -y*c, -y*s) = (x, ~0, y). buildChunk immediately
// overwrites the Y component with the real terrain height
// (pa.setY(i, h - 0.03)), so that ~0 never survives, and the surviving X/Z
// are exactly PlaneGeometry's own pre-rotation X and Y with no rotation
// residue. Verified by direct comparison, not just argued -- see the
// commit message / harness note for the standalone check.
function grimPlaneGridXZ(chunkSize, seg) {
  const half = chunkSize / 2, seg1 = seg + 1, step = chunkSize / seg;
  const gx = new Float32Array(seg1 * seg1), gz = new Float32Array(seg1 * seg1);
  for (let iy = 0; iy < seg1; iy++) {
    for (let ix = 0; ix < seg1; ix++) {
      const i = ix + seg1 * iy;
      gx[i] = ix * step - half;
      gz[i] = iy * step - half;
    }
  }
  return { gx: gx, gz: gz, seg1: seg1 };
}

// Mirrors PlaneGeometry's triangulation loop exactly (two triangles per
// grid cell, same winding).
function grimPlaneIndex(seg) {
  const seg1 = seg + 1;
  const index = new Uint32Array(seg * seg * 6);
  let p = 0;
  for (let iy = 0; iy < seg; iy++) {
    for (let ix = 0; ix < seg; ix++) {
      const a = ix + seg1 * iy;
      const b = ix + seg1 * (iy + 1);
      const c = (ix + 1) + seg1 * (iy + 1);
      const d = (ix + 1) + seg1 * iy;
      index[p++] = a; index[p++] = b; index[p++] = d;
      index[p++] = b; index[p++] = c; index[p++] = d;
    }
  }
  return index;
}

// Bit-for-bit port of BufferGeometry.computeVertexNormals()'s indexed path:
// accumulate each triangle's (unnormalized) cross product onto all three of
// its corners, then normalize. The accumulator arrays are Float32Array ON
// PURPOSE, not Float64: three.js accumulates through a Float32BufferAttribute
// (read -> add -> write, rounding to float32 on every single triangle a
// vertex touches), so a double-precision running sum rounded only once at
// the end would NOT reproduce the same bits. Positions passed in must
// already be float32-rounded (grimBuildChunkGeometry does this) for the same
// reason -- three's own position attribute is a Float32BufferAttribute too.
function grimComputeNormals(px, py, pz, index) {
  const n = px.length;
  const nx = new Float32Array(n), ny = new Float32Array(n), nz = new Float32Array(n);
  for (let i = 0; i < index.length; i += 3) {
    const vA = index[i], vB = index[i + 1], vC = index[i + 2];
    const cbx = px[vC] - px[vB], cby = py[vC] - py[vB], cbz = pz[vC] - pz[vB];
    const abx = px[vA] - px[vB], aby = py[vA] - py[vB], abz = pz[vA] - pz[vB];
    const rx = cby * abz - cbz * aby;
    const ry = cbz * abx - cbx * abz;
    const rz = cbx * aby - cby * abx;
    nx[vA] += rx; ny[vA] += ry; nz[vA] += rz;
    nx[vB] += rx; ny[vB] += ry; nz[vB] += rz;
    nx[vC] += rx; ny[vC] += ry; nz[vC] += rz;
  }
  const outN = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const len = Math.sqrt(nx[i] * nx[i] + ny[i] * ny[i] + nz[i] * nz[i]) || 1;
    const inv = 1 / len; // three's divideScalar multiplies by 1/scalar, not a direct divide -- same rounding
    outN[i * 3] = nx[i] * inv; outN[i * 3 + 1] = ny[i] * inv; outN[i * 3 + 2] = nz[i] * inv;
  }
  return outN;
}

// The worker's version of buildChunk: everything buildChunk does except the
// THREE/scene half, which stays main-thread (TERRAIN-WORKER-OFFLOAD-PLAN.md
// Sec1). Returns exactly what the main thread needs to build the real
// BufferGeometry/Mesh from transferable typed arrays -- same color/tile/mix
// math as Phase 0's grimBuildChunkVerts, plus the from-scratch grid+normals
// Phase 0 explicitly did not yet do (see that function's own header comment
// in the module block above).
function grimBuildChunkGeometry(cx, cz, seg) {
  const CH = 64, x0 = cx * CH + CH / 2, z0 = cz * CH + CH / 2;
  const grid = grimPlaneGridXZ(CH, seg);
  const gx = grid.gx, gz = grid.gz, count = grid.seg1 * grid.seg1;
  const positions = new Float32Array(count * 3);
  const py = new Float32Array(count);
  const c = { r: 0, g: 0, b: 0 };
  const su = [0, 0, 0, 0, 0, 0, 0];
  const colors = new Float32Array(count * 3);
  const tiles = new Float32Array(count * 4);
  const mixes = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const wx = gx[i] + x0, wz = gz[i] + z0;
    const h = GRIM_WORLD.height(wx, wz);
    py[i] = Math.fround(h - 0.03);
    positions[i * 3] = gx[i]; positions[i * 3 + 1] = py[i]; positions[i * 3 + 2] = gz[i];
    const jx = Math.sin(wx * 0.7 + wz * 1.3) * 5.5;
    const jz = Math.cos(wx * 1.1 - wz * 0.9) * 5.5;
    const zi = GRIM_WORLD.zone(wx + jx, wz + jz);
    grimTerrainColor(GRIM_WORLD.zone(wx, wz), h, wx, wz, c);
    colors[i * 3] = 0.55 + c.r * 0.78;
    colors[i * 3 + 1] = 0.55 + c.g * 0.78;
    colors[i * 3 + 2] = 0.55 + c.b * 0.78;
    grimGroundSurface(zi, h, wx, wz, su);
    tiles[i * 4] = su[0]; tiles[i * 4 + 1] = su[1];
    tiles[i * 4 + 2] = su[2]; tiles[i * 4 + 3] = su[3];
    mixes[i * 3] = su[4]; mixes[i * 3 + 1] = su[5]; mixes[i * 3 + 2] = su[6];
  }
  const index = grimPlaneIndex(seg);
  const normals = grimComputeNormals(gx, py, gz, index);
  return { positions: positions, colors: colors, tiles: tiles, mixes: mixes, normals: normals, index: index };
}

// ---------------------------------------------------------------------------
// Message protocol -- see TERRAIN-WORKER-OFFLOAD-PLAN.md Sec2.
onmessage = function (ev) {
  const msg = ev.data;
  if (!msg || !msg.type) return;

  if (msg.type === 'init') {
    _grimCtx = { anvils: msg.anvils || [], campfires: msg.campfires || [], roadSegs: msg.roadSegs || [], gfx: msg.gfx || 'low' };
    GRIM_WORLD.init().then(function () {
      _grimReady = true;
      if (msg.editLayer !== undefined) { GRIM_EDIT.setLayer(msg.editLayer); _grimEditGen = msg.editGen || 0; }
      postMessage({ type: 'ready' });
      const pending = _grimPending.splice(0, _grimPending.length);
      for (let i = 0; i < pending.length; i++) handle(pending[i]);
    }).catch(function (e) {
      postMessage({ type: 'workerError', error: 'GRIM_WORLD.init failed: ' + (e && e.message || e) });
    });
    return;
  }

  if (msg.type === 'editLayer') {
    // Debounced on the main-thread side (matches editor-ui.js's own ~150ms
    // pattern); every edit, however it was triggered, lands here.
    try {
      GRIM_EDIT.setLayer(msg.editLayer);
      _grimEditGen = msg.editGen || 0;
    } catch (e) {
      postMessage({ type: 'workerError', error: 'GRIM_EDIT.setLayer failed: ' + (e && e.message || e) });
    }
    return;
  }

  if (msg.type === 'ctx') {
    _grimCtx = { anvils: msg.anvils || [], campfires: msg.campfires || [], roadSegs: msg.roadSegs || [], gfx: msg.gfx || 'low' };
    return;
  }

  if (msg.type === 'buildChunk' || msg.type === 'dressChunk') {
    if (!_grimReady) { _grimPending.push(msg); return; }
    handle(msg);
    return;
  }
};

onerror = function (e) {
  postMessage({ type: 'workerError', error: 'uncaught: ' + (e && e.message || e) });
};

function handle(msg) {
  if (msg.editGen !== undefined && msg.editGen !== _grimEditGen) {
    postMessage({ type: 'staleEdit', reqId: msg.reqId });
    return;
  }
  try {
    if (msg.type === 'buildChunk') {
      const g = grimBuildChunkGeometry(msg.cx, msg.cz, msg.seg);
      postMessage({
        type: 'buildChunkResult', reqId: msg.reqId, cx: msg.cx, cz: msg.cz, seg: msg.seg,
        positions: g.positions, colors: g.colors, tiles: g.tiles, mixes: g.mixes, normals: g.normals, index: g.index
      }, [g.positions.buffer, g.colors.buffer, g.tiles.buffer, g.mixes.buffer, g.normals.buffer, g.index.buffer]);
    } else if (msg.type === 'dressChunk') {
      const r = grimChunkProps(msg.cx, msg.cz, _grimCtx);
      postMessage({ type: 'dressChunkResult', reqId: msg.reqId, cx: msg.cx, cz: msg.cz, clutter: r.clutter, nodes: r.nodes });
    }
  } catch (e) {
    postMessage({ type: 'workerError', reqId: msg.reqId, error: (msg.type + ' failed: ') + (e && e.message || e) });
  }
}
