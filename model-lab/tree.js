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
    }
  };

  // bark paint: vertical ridge striations, dark bases, moss on the north side
  const barkPaint = (K, seed) => (c, x, y, z) => {
    const ang = Math.atan2(x, z);
    const ridge = 0.62 + 0.38 * Math.abs(Math.sin(ang * 4.5 + seed + y * 0.8));
    let h = Math.sin(Math.round(x * 210) * 12.99 + Math.round(y * 170) * 78.2 + Math.round(z * 190) * 37.7 + seed) * 43758.5;
    h -= Math.floor(h);
    const t = Math.min(1, Math.max(0, y / (K.h * 0.4)));
    const base = [
      K.barkDark[0] + (K.bark[0] - K.barkDark[0]) * t,
      K.barkDark[1] + (K.bark[1] - K.barkDark[1]) * t,
      K.barkDark[2] + (K.bark[2] - K.barkDark[2]) * t
    ];
    // moss creeps up the shaded side of the lower trunk
    const moss = Math.min(0.8, Math.max(0, -z) * Math.max(0, 1 - y / 1.9) * 0.85);
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

  // o: { kind: 'tree'|'oak', seed, x, y, z }
  kit.build = function (o) {
    o = o || {};
    const K = KINDS[o.kind || 'tree'] || KINDS.tree;
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
    const lean = (rnd() - 0.5) * 0.16;
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
      const rr = K.r * (1 - t * 0.72);
      const [lx, ly, lz] = IN(line(t).x, y, 0);
      upperSecs.push({ at: ly, hu: Math.max(0.05, rr), hv: Math.max(0.05, rr), cu: lx, p: 2.6 });
    }
    const upper = loftRect(T, 'y', upperSecs, 9, (c, x, y, z) => barkPaint(K, seed)(c, x + hingeX, y + K.breakY, z));
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
    for (let cc = 0; cc < 3; cc++) {
      const a2 = rnd() * Math.PI * 2, rr2 = rnd() * 0.7;
      clumpAt.push([line(tipY / K.h).x + Math.sin(a2) * rr2, tipY - 0.2 + rnd() * 0.7, Math.cos(a2) * rr2, 0.8 + rnd() * 0.3]);
    }

    // ---- foliage: asymmetric clumps at the limb ends ------------------------
    const canopies = [];
    let ci = 0;
    while (clumpAt.length < K.clumps + 2) {
      // a couple of filler clumps knit the clusters into one crown
      const a = rnd() * Math.PI * 2, rr = K.crownR * (0.3 + rnd() * 0.5);
      clumpAt.push([Math.sin(a) * rr, K.crownY0 + rnd() * (K.h - K.crownY0) * 0.6, Math.cos(a) * rr, 0.7]);
    }
    for (const [cx, cy, cz, cs] of clumpAt) {
      const r = (K.clumpR[0] + rnd() * (K.clumpR[1] - K.clumpR[0])) * cs;
      const geo = roughen(T, new T.IcosahedronGeometry(r, 1), 0.34, (ci + 1) * 31 + seed, 0.78);
      geo.scale(1, 0.78 + rnd() * 0.14, 1);
      paintByPos(T, geo, (c, x, y, z) => leafPaint(K, 0, r)(c, x, y, z));
      leafParts.push(placed(T, geo, ...IN(cx, cy, cz), rnd() * 3, rnd() * 3, rnd() * 3, 1));
      ci++;
    }

    // ---- the break faces ----------------------------------------------------
    // trunk butt: shards pointing back toward the stump, in hinge space
    for (const p of splinters(K, rngFor(seed * 3 + 5), false, M.wood)) {
      p.matrix = new T.Matrix4().makeTranslation(-hingeX + line(K.breakY / K.h).x, 0.005, 0).multiply(p.matrix);
      woodUp.push(p);
    }

    const woodMesh = new T.Mesh(mergeParts(T, woodUp), M.wood);
    woodMesh.castShadow = true; fell.add(woodMesh);
    const leafMesh = new T.Mesh(mergeParts(T, leafParts), M.leaf);
    leafMesh.castShadow = true; fell.add(leafMesh);
    kit._leafGeoTris = leafMesh.geometry.attributes.position.count / 3;

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
    return { g, fell, canopies: [leafMesh], stump: stumpG, base: baseMesh, radius: K.flare + 0.2, breakY: K.breakY, hingeX };
  };

  kit.tick = function () {};
  return kit;
}
