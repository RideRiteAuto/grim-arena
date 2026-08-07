// GRIM WORLD: the trees, rebuilt from the ground up.
//
// The old starter tree was a lofted pole with three colored balls on it and a
// flat poker-chip stump. What a real broadleaf has, in the order a player
// reads it:
//
//   1. ROOT FLARE. A trunk does not emerge from the ground like a fence post;
//      it spreads into buttress roots. This is the single strongest "real
//      tree" cue at ground level, where the player actually is.
//   2. VISIBLE STRUCTURE. Limbs leave the trunk as wood you can see, and the
//      foliage sits in asymmetric clumps AT THE ENDS of those limbs. Oaks
//      branch LOW and wide; young broadleaves keep a leader and branch high.
//   3. THE BREAK. When it is felled it must read as ONE trunk splitting: a
//      splinter crown on the stump and a matching splintered butt on the
//      fallen trunk, hinged AT the break line, not at the ground.
//
// Contract preserved from the old builders: build() returns { g, fell,
// canopies, stump } - the game's fall fx rotates `fell`, reveals `stump`,
// and resourceRespawned resets both. The fell group's pivot is at the break
// hinge; the fx code was retimed to the tree-fell recording (crack at 0,
// ground hit at 3.15s), see the patch.
//
// Same art language as the anvil and furnace: roughened flat-shaded
// geometry, vertex paint for bark, moss and sun, no textures, seeded so no
// two trees repeat.
//
// Zone shapes (patch 58): the same rig now builds every zone tree. Each
// KINDS row states the one structural fact that makes the species readable
// at fifty metres - poplar branches nearly VERTICAL from low down, a palm
// is a bare ringed stem with a frond crown, a willow hangs curtains off a
// dome, a snag is dead wood with a shattered top, a pine stacks shrinking
// cones on a straight leader. Zone identity comes in through o.tint
// (trunk/leaf/leaf2 from ZONE_LOOK) and o.sc scales the whole build.

import {
  rngFor, mergeParts, roughen, paintByPos, logBetween, placed, loftRect
} from './grim-kit.js';

export function makeTreeKit(T, opt) {
  opt = opt || {};
  const kit = { T, mats: {} };
  const M = kit.mats;
  M.wood = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.95, metalness: 0, flatShading: true });
  M.leaf = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, metalness: 0, flatShading: true });

  // per-kind identity: sizes, bark and leaf ramps, branching habit
  const KINDS = {
    tree: {   // the starter broadleaf: one leader, branches in the upper third
      h: 5.6, r: 0.30, flare: 0.62, breakY: 0.55,
      bark: [0.42, 0.31, 0.19], barkDark: [0.24, 0.175, 0.11],
      leaf: [0.30, 0.46, 0.20], leafDeep: [0.155, 0.29, 0.13], leafSun: [0.50, 0.62, 0.26],
      limbs: 3, limbY: [0.55, 0.85], limbLen: [1.1, 1.7], limbUp: [0.5, 0.85],
      clumps: 6, clumpR: [0.85, 1.25], crownR: 1.5, crownY0: 3.4
    },
    oak: {    // the great oak: squat heavy trunk, limbs leave LOW and spread wide
      h: 7.6, r: 0.52, flare: 1.05, breakY: 0.72,
      bark: [0.30, 0.225, 0.145], barkDark: [0.16, 0.115, 0.075],
      leaf: [0.22, 0.38, 0.16], leafDeep: [0.115, 0.24, 0.10], leafSun: [0.42, 0.54, 0.21],
      limbs: 5, limbY: [0.32, 0.62], limbLen: [1.9, 3.0], limbUp: [0.35, 0.7],
      clumps: 9, clumpR: [1.05, 1.6], crownR: 2.4, crownY0: 4.2
    },
    // ---- zone shapes: tints come from ZONE_LOOK via o.tint ------------------
    broad: {  // generic zone broadleaf (zoak, acacia): wide spreading crown
      h: 6.4, r: 0.36, flare: 0.75, breakY: 0.58,
      bark: [0.38, 0.28, 0.17], barkDark: [0.21, 0.15, 0.09],
      leaf: [0.28, 0.44, 0.19], leafDeep: [0.14, 0.27, 0.12], leafSun: [0.48, 0.60, 0.25],
      limbs: 4, limbY: [0.42, 0.68], limbLen: [1.4, 2.2], limbUp: [0.4, 0.75],
      clumps: 7, clumpR: [0.95, 1.35], crownR: 1.9, crownY0: 3.6
    },
    poplar: { // fastigiate: branches nearly VERTICAL, one continuous column
      h: 8.4, r: 0.24, flare: 0.48, breakY: 0.50,
      bark: [0.46, 0.42, 0.34], barkDark: [0.26, 0.23, 0.18],
      leaf: [0.30, 0.46, 0.20], leafDeep: [0.155, 0.29, 0.13], leafSun: [0.52, 0.62, 0.26],
      limbs: 4, limbY: [0.28, 0.55], limbLen: [0.55, 0.8], limbUp: [1.9, 2.6],
      clumps: 7, clumpR: [0.62, 0.88], crownR: 0.4, crownY0: 2.6,
      clumpYScale: 1.6, column: true
    },
    elder: {  // the ancient one: massive trunk, heavy low limbs, huge crown
      h: 9.4, r: 0.66, flare: 1.35, breakY: 0.82,
      bark: [0.28, 0.21, 0.14], barkDark: [0.14, 0.10, 0.07],
      leaf: [0.22, 0.38, 0.16], leafDeep: [0.115, 0.24, 0.10], leafSun: [0.42, 0.54, 0.21],
      limbs: 6, limbY: [0.30, 0.60], limbLen: [2.2, 3.4], limbUp: [0.35, 0.7],
      clumps: 10, clumpR: [1.2, 1.8], crownR: 2.8, crownY0: 5.0
    },
    willow: { // stout trunk, up-arching scaffolds, dome with HANGING curtains
      h: 6.6, r: 0.44, flare: 0.9, breakY: 0.60,
      bark: [0.34, 0.27, 0.17], barkDark: [0.18, 0.14, 0.09],
      leaf: [0.30, 0.42, 0.22], leafDeep: [0.16, 0.26, 0.13], leafSun: [0.48, 0.56, 0.27],
      limbs: 5, limbY: [0.34, 0.58], limbLen: [1.3, 2.0], limbUp: [0.8, 1.25],
      clumps: 8, clumpR: [0.9, 1.3], crownR: 2.2, crownY0: 3.4,
      drapes: 7
    },
    pine: {   // conifer: straight leader, stacked cone tiers shrinking to a point
      h: 7.8, r: 0.34, flare: 0.62, breakY: 0.52,
      bark: [0.33, 0.24, 0.15], barkDark: [0.17, 0.12, 0.08],
      leaf: [0.16, 0.33, 0.20], leafDeep: [0.09, 0.20, 0.12], leafSun: [0.34, 0.50, 0.30],
      limbs: 0, clumps: 0, crownR: 1.7, crownY0: 2.5,
      canopy: 'tiers', tiers: 5, moss: 0.5, tintMix: 0.38
    },
    palm: {   // one bare ringed stem, swept, frond crown at the very top
      h: 7.0, r: 0.26, flare: 0.40, breakY: 0.50,
      bark: [0.48, 0.40, 0.28], barkDark: [0.28, 0.23, 0.15],
      leaf: [0.30, 0.50, 0.22], leafDeep: [0.14, 0.30, 0.13], leafSun: [0.50, 0.64, 0.28],
      limbs: 0, clumps: 0, crownR: 0, crownY0: 0,
      canopy: 'fronds', fronds: 10, rings: true, moss: 0, sweep: 2.2, taper: 0.30
    },
    snag: {   // DEAD: shattered top, crooked bare limbs, not one leaf
      h: 5.4, r: 0.40, flare: 0.82, breakY: 0.55,
      bark: [0.30, 0.26, 0.22], barkDark: [0.15, 0.13, 0.11],
      leaf: [0, 0, 0], leafDeep: [0, 0, 0], leafSun: [0, 0, 0],
      limbs: 3, limbY: [0.35, 0.72], limbLen: [1.0, 1.7], limbUp: [0.3, 0.9],
      clumps: 0, crownR: 0, crownY0: 0,
      canopy: 'none', crooked: true, shatterTop: true, moss: 0.35
    }
  };
  KINDS.zoak = KINDS.broad; KINDS.acacia = KINDS.broad; KINDS.orchard = KINDS.broad;
  KINDS.bogoak = KINDS.snag; KINDS.emberbark = KINDS.snag;
  KINDS.icewood = KINDS.pine; KINDS.elderking = KINDS.elder;

  // scale every linear dimension; fractions and slopes stay put
  const scaled = (K, S) => {
    if (S === 1) return K;
    const K2 = Object.assign({}, K);
    ['h', 'r', 'flare', 'breakY', 'crownR', 'crownY0'].forEach(f => { K2[f] = K[f] * S; });
    ['limbLen', 'clumpR'].forEach(f => { if (K[f]) K2[f] = [K[f][0] * S, K[f][1] * S]; });
    return K2;
  };

  // zone tint: trunk/leaf/leaf2 hex colors from ZONE_LOOK replace the ramps
  const hx = (n) => [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  const tinted = (K, tint) => {
    if (!tint) return K;
    const K2 = Object.assign({}, K);
    const tr = hx(tint.trunk), lf = hx(tint.leaf), lf2 = hx(tint.leaf2 || tint.leaf);
    K2.bark = tr;
    K2.barkDark = [tr[0] * 0.52, tr[1] * 0.52, tr[2] * 0.52];
    if (K.canopy !== 'none') {
      // BLEND the zone hue with the species' own ramp instead of replacing
      // it: a full swap let FROSTWILD's ice tint blow the pine out to white.
      const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
      const mt = K.tintMix === undefined ? 0.62 : K.tintMix;
      K2.leaf = mix(K.leaf, lf, mt);
      K2.leafDeep = mix(K.leafDeep, [(lf[0] + lf2[0]) * 0.29, (lf[1] + lf2[1]) * 0.29, (lf[2] + lf2[2]) * 0.29], mt);
      const sun = [Math.min(0.85, lf[0] * 1.3 + 0.05), Math.min(0.85, lf[1] * 1.3 + 0.05), Math.min(0.85, lf[2] * 1.3 + 0.05)];
      K2.leafSun = mix(K.leafSun, sun, mt);
    }
    return K2;
  };

  // bark paint: vertical ridge striations, dark bases, moss on the north
  // side. K.rings switches to horizontal frond-scar rings (palms), K.moss
  // scales the moss down for dead wood and dry species.
  const barkPaint = (K, seed) => (c, x, y, z) => {
    const ang = Math.atan2(x, z);
    const ridge = K.rings
      ? 0.60 + 0.40 * Math.abs(Math.sin(y * 6.5 + seed))
      : 0.62 + 0.38 * Math.abs(Math.sin(ang * 4.5 + seed + y * 0.8));
    let h = Math.sin(Math.round(x * 210) * 12.99 + Math.round(y * 170) * 78.2 + Math.round(z * 190) * 37.7 + seed) * 43758.5;
    h -= Math.floor(h);
    const t = Math.min(1, Math.max(0, y / (K.h * 0.4)));
    const base = [
      K.barkDark[0] + (K.bark[0] - K.barkDark[0]) * t,
      K.barkDark[1] + (K.bark[1] - K.barkDark[1]) * t,
      K.barkDark[2] + (K.bark[2] - K.barkDark[2]) * t
    ];
    // moss creeps up the shaded side of the lower trunk
    const mossAmt = (K.moss === undefined ? 1 : K.moss);
    const moss = Math.min(0.8, Math.max(0, -z) * Math.max(0, 1 - y / 1.9) * 0.85 * mossAmt);
    c.setRGB(
      base[0] * ridge * (0.72 + h * 0.55) * (1 - moss),
      base[1] * ridge * (0.72 + h * 0.55) * (1 - moss * 0.2) + moss * 0.10,
      base[2] * ridge * (0.72 + h * 0.55) * (1 - moss)
    );
  };

  // leaf paint: deep shadow low and inside, sunlit tops, per-vertex breakup
  const leafPaint = (K, cy, cr) => (c, x, y, z) => {
    let h = Math.sin(Math.round(x * 310) * 12.99 + Math.round(y * 290) * 78.2 + Math.round(z * 270) * 37.7) * 43758.5;
    h -= Math.floor(h);
    const up = Math.min(1, Math.max(0, (y - cy) / cr * 0.62 + 0.5));
    const sun = up * up * up;
    c.setRGB(
      (K.leafDeep[0] + (K.leaf[0] - K.leafDeep[0]) * up) * (0.85 + h * 0.3) + K.leafSun[0] * sun * 0.35 * h,
      (K.leafDeep[1] + (K.leaf[1] - K.leafDeep[1]) * up) * (0.85 + h * 0.3) + K.leafSun[1] * sun * 0.35 * h,
      (K.leafDeep[2] + (K.leaf[2] - K.leafDeep[2]) * up) * (0.85 + h * 0.3) + K.leafSun[2] * sun * 0.35 * h
    );
  };

  // The splinter crown: a ring of jagged shards around a torn core. Built
  // once per break as two matching halves - `up` for the stump (shards point
  // up), `down` for the trunk butt (shards point down in TRUNK-local space,
  // i.e. toward the break when the trunk lies on the ground).
  const splinters = (K, rnd, upward, mat) => {
    const parts = [];
    const R = K.r * 0.92;
    const n = 9;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + rnd() * 0.3;
      const rr = R * (0.35 + rnd() * 0.6);
      const hgt = (0.10 + rnd() * 0.22) * (upward ? 1 : 0.8);
      const geo = new T.ConeGeometry(0.035 + rnd() * 0.04, hgt, 4);
      if (!upward) geo.rotateX(Math.PI);
      // pale torn wood inside, bark color out at the rim
      paintByPos(T, geo, (c, x, y, z) => {
        const edge = rr / R;
        const pale = 1 - edge * 0.55;
        c.setRGB(0.62 * pale + K.bark[0] * (1 - pale), 0.50 * pale + K.bark[1] * (1 - pale), 0.33 * pale + K.bark[2] * (1 - pale));
      });
      parts.push(placed(T, geo, Math.sin(a) * rr, upward ? hgt * 0.4 : -hgt * 0.4, Math.cos(a) * rr,
        (rnd() - 0.5) * 0.5, 0, (rnd() - 0.5) * 0.5, 1));
    }
    // the torn core disc
    const core = new T.CylinderGeometry(R * 0.9, R * 0.98, 0.05, 9);
    roughen(T, core, 0.15, 5, 1);
    paintByPos(T, core, (c, x, y, z) => {
      const rr2 = Math.hypot(x, z) / R;
      const pale = 1 - rr2 * 0.4;
      c.setRGB(0.60 * pale, 0.47 * pale, 0.31 * pale);
    });
    parts.push(placed(T, core, 0, upward ? 0.012 : -0.012, 0, 0, 0, 0, 1));
    return parts;
  };

  // o: { kind, seed, x, y, z, sc, tint: {trunk,leaf,leaf2}, merged }
  // merged: one mesh for wood + leaves (zone streaming - draw calls matter
  // more than a sway split the zone registration never uses).
  kit.build = function (o) {
    o = o || {};
    let K = KINDS[o.kind || 'tree'] || KINDS.broad;
    K = tinted(scaled(K, o.sc || 1), o.tint);
    const rnd = rngFor((o.seed || 3) * 7 + (o.kind === 'oak' ? 131 : 17));
    const seed = (o.seed || 3) % 100;
    const g = new T.Group();

    // ---- the fell group hinges at the BREAK, not the ground -----------------
    // Geometry above the break line is authored in hinge space (origin at the
    // break, on the falling side's edge) so fx rotation looks like a tree
    // tipping off its stump instead of a flagpole swiveling out of the dirt.
    const hingeX = K.r * 0.7;
    const fell = new T.Group();
    fell.position.set(hingeX, K.breakY, 0);
    g.add(fell);
    const IN = (x, y, z) => [x - hingeX, y - K.breakY, z];   // world -> hinge space

    const woodUp = [];    // merged into the fell group's wood mesh
    const leafParts = [];
    const woodDown = [];  // the planted part: flare + stump, revealed on fell

    // ---- trunk: root flare to tip, split at the break line ------------------
    const lean = (rnd() - 0.5) * 0.16 * (K.sweep || 1) + (K.sweep ? (rnd() > 0.5 ? 0.08 : -0.08) * K.sweep : 0);
    const line = (t) => ({ x: lean * t * t * 2.4, y: t });   // gentle sweep
    const trunkSecs = [];
    const steps = [[0, K.flare * 0.82, 2.0], [0.04, K.r * 1.30, 2.5], [0.10, K.r * 1.06, 2.6]];
    for (const [tt, rr, p] of steps) {
      const y = tt * K.h;
      if (y > K.breakY) break;
      trunkSecs.push({ at: y, hu: rr, hv: rr, cu: line(y / K.h).x, p });
    }
    // the flare gets buttress roots: lobes pushed out at 4-5 angles
    const rootN = 4 + (rnd() > 0.5 ? 1 : 0);
    for (let i = 0; i < rootN; i++) {
      const a = (i / rootN) * Math.PI * 2 + rnd() * 0.5;
      const len = K.flare * (0.85 + rnd() * 0.5);
      const root = logBetween(T,
        new T.Vector3(Math.sin(a) * K.r * 0.55, 0.26, Math.cos(a) * K.r * 0.55),
        new T.Vector3(Math.sin(a) * (K.r + len), -0.06, Math.cos(a) * (K.r + len)),
        K.r * 0.42, K.r * 0.10, { rough: 0.14, seed: i * 9 + seed, segments: 6 });
      root.geo.scale(1, 0.8, 1);
      paintByPos(T, root.geo, barkPaint(K, seed));
      woodDown.push(root);
    }
    // lower trunk (planted): flare up to the break
    const lower = loftRect(T, 'y', trunkSecs.concat([{ at: K.breakY, hu: K.r, hv: K.r, cu: line(K.breakY / K.h).x, p: 2.6 }]), 9,
      barkPaint(K, seed));
    roughen(T, lower, 0.085, seed + 2, 1);   // same seed as the upper loft
    woodDown.push({ geo: lower });

    // upper trunk (falls): break line to tip, in hinge space
    const upperSecs = [];
    const tipY = K.h * (0.86 + rnd() * 0.1);
    const nSec = 5;
    for (let i = 0; i <= nSec; i++) {
      const y = K.breakY + (tipY - K.breakY) * (i / nSec);
      const t = y / K.h;
      const rr = K.r * (1 - t * (K.taper === undefined ? 0.72 : K.taper));
      const [lx, ly, lz] = IN(line(t).x, y, 0);
      upperSecs.push({ at: ly, hu: Math.max(0.05, rr), hv: Math.max(0.05, rr), cu: lx, p: 2.6 });
    }
    const upper = loftRect(T, 'y', upperSecs, 9, (c, x, y, z) => barkPaint(K, seed)(c, x + hingeX, y + K.breakY, z));
    // a snag's top is TORN, not sawn: a jagged ring of upward shards
    if (K.shatterTop) {
      const topR = K.r * (1 - (K.taper === undefined ? 0.72 : K.taper) * (tipY / K.h));
      for (let i = 0; i < 6; i++) {
        const a = (i / 6) * Math.PI * 2 + rnd() * 0.4;
        const hgt = 0.25 + rnd() * 0.45;
        const shard = new T.ConeGeometry(0.05 + rnd() * 0.05, hgt, 4);
        const pale = 0.5 + rnd() * 0.2;
        paintByPos(T, shard, (c) => {
          c.setRGB(K.bark[0] * 0.6 + 0.30 * pale, K.bark[1] * 0.6 + 0.24 * pale, K.bark[2] * 0.6 + 0.15 * pale);
        });
        woodUp.push(placed(T, shard,
          ...IN(line(tipY / K.h).x + Math.sin(a) * topR * 0.6, tipY + hgt * 0.3, Math.cos(a) * topR * 0.6),
          (rnd() - 0.5) * 0.5, 0, (rnd() - 0.5) * 0.5, 1));
      }
    }
    // dead branch stubs on the bare trunk
    for (let i = 0; i < 2 + (K.limbs > 3 ? 1 : 0); i++) {
      const a = rnd() * Math.PI * 2;
      const sy = K.h * (0.28 + rnd() * 0.22);
      const sr = K.r * (1 - (sy / K.h) * 0.6);
      const stub = logBetween(T,
        new T.Vector3(...IN(line(sy / K.h).x + Math.sin(a) * sr * 0.7, sy, Math.cos(a) * sr * 0.7)),
        new T.Vector3(...IN(line(sy / K.h).x + Math.sin(a) * (sr + 0.34), sy + 0.1 + rnd() * 0.12, Math.cos(a) * (sr + 0.34))),
        K.r * 0.14, K.r * 0.05, { rough: 0.12, seed: i * 7 + seed, segments: 5 });
      paintByPos(T, stub.geo, (c, x, y, z) => barkPaint(K, seed)(c, x + hingeX, y + K.breakY, z));
      woodUp.push(stub);
    }
    roughen(T, upper, 0.085, seed + 2, 1);   // matches the lower loft at the break ring
    woodUp.push({ geo: upper });

    // ---- limbs: real wood between trunk and foliage -------------------------
    const clumpAt = [];
    const limbN = K.limbs;
    for (let i = 0; i < limbN; i++) {
      const a = (i / limbN) * Math.PI * 2 + rnd() * 0.9;
      const t0 = K.limbY[0] + rnd() * (K.limbY[1] - K.limbY[0]);
      const y0 = K.h * t0;
      const len = K.limbLen[0] + rnd() * (K.limbLen[1] - K.limbLen[0]);
      const up = K.limbUp[0] + rnd() * (K.limbUp[1] - K.limbUp[0]);
      const sx = line(t0).x, r0 = K.r * (1 - t0 * 0.6);
      const p0 = new T.Vector3(sx + Math.sin(a) * r0 * 0.6, y0, Math.cos(a) * r0 * 0.6);
      const p1 = new T.Vector3(sx + Math.sin(a) * len, y0 + len * up, Math.cos(a) * len);
      if (K.crooked) {
        // dead limbs grow in two crooked segments with a hard elbow
        const mid = p0.clone().lerp(p1, 0.5);
        mid.x += (rnd() - 0.5) * 0.5; mid.y += (rnd() - 0.2) * 0.55; mid.z += (rnd() - 0.5) * 0.5;
        const seg1 = logBetween(T, new T.Vector3(...IN(p0.x, p0.y, p0.z)), new T.Vector3(...IN(mid.x, mid.y, mid.z)),
          r0 * 0.42, r0 * 0.2, { rough: 0.2, seed: i * 13 + seed, segments: 5 });
        const seg2 = logBetween(T, new T.Vector3(...IN(mid.x, mid.y, mid.z)), new T.Vector3(...IN(p1.x, p1.y, p1.z)),
          r0 * 0.2, r0 * 0.05, { rough: 0.2, seed: i * 13 + seed + 4, segments: 5 });
        paintByPos(T, seg1.geo, (c, x, y, z) => barkPaint(K, seed)(c, x + hingeX, y + K.breakY, z));
        paintByPos(T, seg2.geo, (c, x, y, z) => barkPaint(K, seed)(c, x + hingeX, y + K.breakY, z));
        woodUp.push(seg1, seg2);
        continue;
      }
      const limb = logBetween(T,
        new T.Vector3(...IN(p0.x, p0.y, p0.z)),
        new T.Vector3(...IN(p1.x, p1.y, p1.z)),
        r0 * 0.5, r0 * 0.13, { rough: 0.16, seed: i * 13 + seed, segments: 6 });
      paintByPos(T, limb.geo, (c, x, y, z) => barkPaint(K, seed)(c, x + hingeX, y + K.breakY, z));
      woodUp.push(limb);
      // a CLUSTER at the limb end, pushed past the tip so the wood is buried
      const dir = new T.Vector3().subVectors(p1, p0).normalize();
      const cN = 2 + (rnd() > 0.55 ? 1 : 0);
      for (let cc = 0; cc < cN; cc++) {
        const off = new T.Vector3((rnd() - 0.5) * 0.55, (rnd() - 0.25) * 0.5, (rnd() - 0.5) * 0.55);
        const ctr = p1.clone().addScaledVector(dir, 0.10 + rnd() * 0.15).add(off);
        clumpAt.push([ctr.x, ctr.y, ctr.z, 0.7 + rnd() * 0.25]);
      }
    }
    // the crown leader gets its own cluster
    if ((K.canopy || 'clumps') === 'clumps') for (let cc = 0; cc < 3; cc++) {
      const a2 = rnd() * Math.PI * 2, rr2 = rnd() * 0.7;
      clumpAt.push([line(tipY / K.h).x + Math.sin(a2) * rr2, tipY - 0.2 + rnd() * 0.7, Math.cos(a2) * rr2, 0.8 + rnd() * 0.3]);
    }

    // ---- foliage ------------------------------------------------------------
    const canopies = [];
    const style = K.canopy || 'clumps';
    if (style === 'clumps') {
      // asymmetric clumps at the limb ends, fillers knitting them into a crown
      let ci = 0;
      if (K.column) {
        // fastigiate: ONE unbroken column of clumps up the leader. The limb
        // clusters scatter too wide for the silhouette, so they are replaced
        // outright - the near-vertical limb wood still shows at the edges.
        clumpAt.length = 0;
        const n = K.clumps + 4;
        for (let i = 0; i < n; i++) {
          const u = i / (n - 1);
          const cy = K.crownY0 + (tipY + 0.35 - K.crownY0) * u;
          clumpAt.push([line(cy / K.h).x + (rnd() - 0.5) * 0.22, cy, (rnd() - 0.5) * 0.22,
            (0.95 - u * 0.35) * (0.9 + rnd() * 0.2)]);
        }
      } else while (clumpAt.length < K.clumps + 2) {
        const a = rnd() * Math.PI * 2, rr = K.crownR * (0.3 + rnd() * 0.5);
        clumpAt.push([Math.sin(a) * rr, K.crownY0 + rnd() * (K.h - K.crownY0) * 0.6, Math.cos(a) * rr, 0.7]);
      }
      for (const [cx, cy, cz, cs] of clumpAt) {
        const r = (K.clumpR[0] + rnd() * (K.clumpR[1] - K.clumpR[0])) * cs;
        const geo = roughen(T, new T.IcosahedronGeometry(r, 1), 0.34, (ci + 1) * 31 + seed, 0.78);
        geo.scale(1, (0.78 + rnd() * 0.14) * (K.clumpYScale || 1), 1);
        paintByPos(T, geo, (c, x, y, z) => leafPaint(K, 0, r)(c, x, y, z));
        leafParts.push(placed(T, geo, ...IN(cx, cy, cz), rnd() * 3, rnd() * 3, rnd() * 3, 1));
        ci++;
      }
      // willow: curtains hang off the crown rim, almost to the ground
      if (K.drapes) {
        for (let i = 0; i < K.drapes; i++) {
          const a = (i / K.drapes) * Math.PI * 2 + rnd() * 0.5;
          const rr = K.crownR * (0.75 + rnd() * 0.3);
          const topY = K.crownY0 + 0.6 + rnd() * 0.5;
          const dropLen = topY - (0.9 + rnd() * 0.5);
          const geo = roughen(T, new T.IcosahedronGeometry(0.5, 1), 0.26, i * 17 + seed, 0.9);
          geo.scale(0.42 + rnd() * 0.12, dropLen / 1.0, 0.42 + rnd() * 0.12);
          // darker toward the hanging tip, like leaves in their own shade
          paintByPos(T, geo, (c, x, y, z) => {
            const d = Math.min(1, Math.max(0, 0.5 - y * 0.9));
            let h2 = Math.sin(Math.round(x * 300) * 12.9 + Math.round(y * 280) * 78.2 + Math.round(z * 260) * 37.7) * 43758.5;
            h2 -= Math.floor(h2);
            c.setRGB(
              (K.leaf[0] * (1 - d) + K.leafDeep[0] * d) * (0.82 + h2 * 0.3),
              (K.leaf[1] * (1 - d) + K.leafDeep[1] * d) * (0.82 + h2 * 0.3),
              (K.leaf[2] * (1 - d) + K.leafDeep[2] * d) * (0.82 + h2 * 0.3));
          });
          leafParts.push(placed(T, geo,
            ...IN(Math.sin(a) * rr, topY - dropLen * 0.5, Math.cos(a) * rr),
            0, rnd() * 3, 0, 1));
        }
      }
    } else if (style === 'tiers') {
      // conifer: stacked cones shrinking to the leader's point. Each tier's
      // skirt OVERLAPS the one below - gaps read as stacked umbrellas.
      const nT = K.tiers || 5;
      const topY = tipY + 0.35;
      const span = topY - K.crownY0;
      const ch = span / nT * 2.6;
      for (let i = 0; i < nT; i++) {
        const u = i / (nT - 1);
        const cy = K.crownY0 + span * u;
        const cr = K.crownR * (1 - u * 0.72) * (0.94 + rnd() * 0.12);
        const geo = new T.ConeGeometry(cr, ch, 8);
        roughen(T, geo, 0.20, i * 23 + seed, 0.9);
        paintByPos(T, geo, (c, x, y, z) => leafPaint(K, -ch * 0.4, ch * 0.9)(c, x, y, z));
        leafParts.push(placed(T, geo,
          ...IN(line(cy / K.h).x + (rnd() - 0.5) * 0.12, cy + ch * 0.30, (rnd() - 0.5) * 0.12),
          0, rnd() * 3, 0, 1));
      }
    } else if (style === 'fronds') {
      // palm crown: a fan of drooping blades from the very tip, nuts beneath
      const nF = K.fronds || 10;
      const crownY = tipY;
      const crownX = line(tipY / K.h).x;
      // the fibrous husk where the fronds sheath the stem - also plugs the
      // dark hole the blade roots leave when seen from below
      {
        const husk = roughen(T, new T.IcosahedronGeometry(0.30, 1), 0.2, seed + 77, 1);
        husk.scale(1, 0.8, 1);
        paintByPos(T, husk, (c) => c.setRGB(K.bark[0] * 0.9, K.bark[1] * 0.85, K.bark[2] * 0.8));
        woodUp.push(placed(T, husk, ...IN(crownX, crownY + 0.05, 0), 0, 0, 0, 1));
      }
      for (let i = 0; i < nF + 6; i++) {
        const young = i % 5 === 0;
        const a = (i / nF) * Math.PI * 2 + rnd() * 0.35;
        const len = (young ? 1.6 : 2.3) + rnd() * 0.6;
        // tilt is the blade's ELEVATION above horizontal (rotX(PI/2 - tilt)).
        // Working fronds hang a little BELOW horizontal; only the young
        // center blades stand up.
        const tilt = young ? 1.05 + rnd() * 0.3 : -0.22 + rnd() * 0.5;
        const geo = new T.ConeGeometry(0.42, len, 4);
        geo.scale(1.3, 1, 0.13);                             // flatten into a blade
        // bow the blade so the mid arches while the tip drops
        {
          const pp = geo.getAttribute('position');
          for (let vi = 0; vi < pp.count; vi++) {
            const vy = pp.getY(vi);
            const uu = vy / len + 0.5;
            pp.setZ(vi, pp.getZ(vi) - Math.sin(uu * Math.PI) * 0.30);
          }
        }
        roughen(T, geo, 0.10, i * 29 + seed, 1);
        // darker rib at the base, bright tip - but the ramp floor stays HIGH:
        // a drooping frond shows you its underside, and an underside painted
        // near-black plus unlit shading reads as a black star
        paintByPos(T, geo, (c, x, y, z) => {
          const u = 0.35 + 0.65 * Math.min(1, Math.max(0, y / len + 0.5));
          let h2 = Math.sin(Math.round(x * 330) * 12.9 + Math.round(y * 300) * 78.2) * 43758.5;
          h2 -= Math.floor(h2);
          c.setRGB(
            (K.leafDeep[0] + (K.leaf[0] - K.leafDeep[0]) * u) * (0.95 + h2 * 0.3) + K.leafSun[0] * u * u * 0.35,
            (K.leafDeep[1] + (K.leaf[1] - K.leafDeep[1]) * u) * (0.95 + h2 * 0.3) + K.leafSun[1] * u * u * 0.35,
            (K.leafDeep[2] + (K.leaf[2] - K.leafDeep[2]) * u) * (0.95 + h2 * 0.3) + K.leafSun[2] * u * u * 0.35);
        });
        // lay the blade out along its angle, base at the crown, tip drooping
        const m = new T.Matrix4().makeTranslation(...IN(crownX, crownY + 0.1, 0))
          .multiply(new T.Matrix4().makeRotationY(a))
          .multiply(new T.Matrix4().makeRotationX(Math.PI / 2 - tilt))
          .multiply(new T.Matrix4().makeTranslation(0, len * 0.5, 0));
        // a drooped blade shows its underside, whose down normals catch only
        // the dark ground hemisphere and go black. Pre-brighten those verts
        // so both faces of the crown read as the same leaf.
        {
          const g2 = geo.index ? geo.toNonIndexed() : geo;
          g2.computeVertexNormals();
          const nn = g2.getAttribute('normal'), cc = g2.getAttribute('color');
          const nm3 = new T.Matrix3().getNormalMatrix(m);
          const v = new T.Vector3();
          if (nn && cc) for (let vi = 0; vi < nn.count; vi++) {
            v.set(nn.getX(vi), nn.getY(vi), nn.getZ(vi)).applyMatrix3(nm3);
            if (v.y < -0.15) {
              const k2 = 1 + Math.min(1.3, -v.y * 1.8);
              cc.setXYZ(vi, Math.min(1, cc.getX(vi) * k2), Math.min(1, cc.getY(vi) * k2), Math.min(1, cc.getZ(vi) * k2));
            }
          }
          leafParts.push({ geo: g2, matrix: m });
        }
      }
      // coconuts tucked under the crown
      for (let i = 0; i < 3; i++) {
        const a = rnd() * Math.PI * 2;
        const nut = new T.IcosahedronGeometry(0.13, 0);
        paintByPos(T, nut, (c) => c.setRGB(0.30, 0.22, 0.12));
        woodUp.push(placed(T, nut,
          ...IN(crownX + Math.sin(a) * 0.24, crownY - 0.16, Math.cos(a) * 0.24), 0, 0, 0, 1));
      }
    }
    // style 'none' (snags): not one leaf

    // ---- the break faces ----------------------------------------------------
    // trunk butt: shards pointing back toward the stump, in hinge space
    for (const p of splinters(K, rngFor(seed * 3 + 5), false, M.wood)) {
      p.matrix = new T.Matrix4().makeTranslation(-hingeX + line(K.breakY / K.h).x, 0.005, 0).multiply(p.matrix);
      woodUp.push(p);
    }

    let leafMesh = null;
    if (o.merged) {
      // zone streaming: one mesh per falling tree, draw calls beat a sway
      // split the zone registration never uses anyway
      const woodMesh = new T.Mesh(mergeParts(T, woodUp.concat(leafParts)), M.wood);
      woodMesh.castShadow = true; fell.add(woodMesh);
    } else {
      const woodMesh = new T.Mesh(mergeParts(T, woodUp), M.wood);
      woodMesh.castShadow = true; fell.add(woodMesh);
      if (leafParts.length) {
        leafMesh = new T.Mesh(mergeParts(T, leafParts), M.leaf);
        leafMesh.castShadow = true; fell.add(leafMesh);
        kit._leafGeoTris = leafMesh.geometry.attributes.position.count / 3;
      }
    }

    // ---- the planted base: root flare and lower trunk, ALWAYS visible ------
    // It is the bottom of the living tree and, once the top breaks off, it IS
    // the stump body. Nothing about it changes at the fell.
    const baseMesh = new T.Mesh(mergeParts(T, woodDown), M.wood);
    baseMesh.castShadow = true; g.add(baseMesh);

    // ---- the stump crown: the game's toggled stump group -------------------
    // ONLY the splinter crown and torn core live here, hidden while the tree
    // stands (the upper trunk loft covers the same footprint) and revealed at
    // the exact moment the trunk breaks off. resourceRespawned hides it again.
    const stumpG = new T.Group();
    stumpG.visible = false;
    g.add(stumpG);
    const crownParts = [];
    for (const p of splinters(K, rngFor(seed * 3 + 5), true, M.wood)) {
      p.matrix = new T.Matrix4().makeTranslation(line(K.breakY / K.h).x, K.breakY, 0).multiply(p.matrix);
      crownParts.push(p);
    }
    const stumpMesh = new T.Mesh(mergeParts(T, crownParts), M.wood);
    stumpMesh.castShadow = true; stumpG.add(stumpMesh);

    if (o.x !== undefined) g.position.set(o.x, o.y || 0, o.z || 0);
    g.traverse(m => { if (m.isMesh) m.castShadow = true; });
    return { g, fell, canopies: leafMesh ? [leafMesh] : [], stump: stumpG, base: baseMesh, radius: K.flare + 0.2, breakY: K.breakY, hingeX };
  };

  kit.tick = function () {};
  return kit;
}
