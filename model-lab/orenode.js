// GRIM WORLD: the ore nodes, rebuilt.
//
// The old node was three grey lumps with six octahedra floating around them,
// and when you emptied it the octahedra simply winked out. What a real vein
// needs, in the order a player reads it:
//
//   1. ONE rock, not a lump pile: boulders packed into a single mass with
//      strata banding, dirt at the footing, weathered light on top.
//   2. The ORE IN the rock: every nugget sits in a visible crater socket,
//      proud of the surface, so it reads as embedded, not sprinkled.
//   3. TWO honest states. Full: nuggets in their sockets. Emptied: the same
//      sockets EMPTY and dark, chipped rubble at the base - you can tell at
//      a glance from across the field whether it is worth walking to.
//   4. Per-ore identity on a shared base: same rock, unmistakable nuggets.
//      Copper is verdigris-streaked knobs, iron rusty octahedra, coal matte
//      black blocks, gold bright faceted grains, obsidian glassy shards,
//      ember crystal glowing spikes.
//
// Contract: build() returns { g, studs, rubble }. The game hides every mesh
// in `studs` when the vein empties and shows it again on respawn; `rubble`
// is the inverse. Same art language as the anvil, furnace and trees.

import {
  rngFor, mergeParts, roughen, paintByPos, placed
} from './grim-kit.js';

export function makeOreNodeKit(T, opt) {
  opt = opt || {};
  const kit = { T, mats: {} };
  const M = kit.mats;
  M.rock = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.96, metalness: 0.02, flatShading: true });
  M.ore = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.42, metalness: 0.5, flatShading: true });
  M.glow = new T.MeshBasicMaterial({ vertexColors: true });

  // Per-kind identity. `shape` picks the nugget silhouette; main/fleck the
  // two-tone paint; `glow` routes the mesh to the unlit material.
  const ORES = {
    iron:      { shape: 'octa', main: [0.44, 0.24, 0.16], fleck: [0.16, 0.11, 0.10], per: 2, size: 1.0 },
    copper:    { shape: 'lump', main: [0.50, 0.30, 0.18], fleck: [0.22, 0.60, 0.42], per: 3, size: 1.0 },
    coal:      { shape: 'cube', main: [0.085, 0.082, 0.095], fleck: [0.20, 0.21, 0.25], per: 3, size: 1.1 },
    gold:      { shape: 'octa', main: [0.91, 0.72, 0.26], fleck: [0.99, 0.93, 0.72], per: 3, size: 0.62 },
    salt:      { shape: 'crystal', main: [0.91, 0.89, 0.84], fleck: [0.84, 0.76, 0.74], per: 3, size: 0.8 },
    saltpeter: { shape: 'lump', main: [0.84, 0.82, 0.70], fleck: [0.68, 0.66, 0.52], per: 2, size: 0.9 },
    glasssand: { shape: 'lump', main: [0.85, 0.75, 0.52], fleck: [0.95, 0.88, 0.68], per: 2, size: 0.95 },
    obsidian:  { shape: 'shard', main: [0.075, 0.06, 0.10], fleck: [0.23, 0.16, 0.30], per: 2, size: 1.0 },
    embercryst:{ shape: 'crystal', main: [1.0, 0.42, 0.10], fleck: [1.0, 0.76, 0.34], glow: true, per: 2, size: 1.0 },
    stone:     { shape: 'lump', main: [0.55, 0.55, 0.52], fleck: [0.40, 0.40, 0.38], per: 2, size: 0.9 }
  };

  const rockPaint = (stone, seed) => (c, x, y, z) => {
    let h = Math.sin(Math.round(x * 170) * 12.99 + Math.round(y * 150) * 78.2 + Math.round(z * 190) * 37.7 + seed) * 43758.5;
    h -= Math.floor(h);
    // strata: darker horizontal bands running through the mass
    const band = 0.62 + 0.38 * Math.abs(Math.sin(y * 5.2 + seed * 0.7));
    // dirt at the footing, weathered light on top
    const foot = Math.max(0, 1 - y / 0.5) * 0.30;
    const topl = Math.min(1, Math.max(0, (y - 0.7) / 0.9)) * 0.18;
    const v = band * (0.62 + h * 0.6) * (1 - foot) + topl;
    c.setRGB(stone[0] * v + foot * 0.09, stone[1] * v + foot * 0.07, stone[2] * v + foot * 0.05);
  };

  // one nugget cluster for a socket, in socket-local space (y up out of the rock)
  const nuggets = (O, rnd) => {
    const parts = [];
    const n = O.per;
    for (let i = 0; i < n; i++) {
      const s = (0.105 + rnd() * 0.06) * O.size;
      let geo;
      if (O.shape === 'octa') geo = new T.OctahedronGeometry(s, 0);
      else if (O.shape === 'cube') geo = new T.BoxGeometry(s * 1.5, s * 1.2, s * 1.4);
      else if (O.shape === 'shard') { geo = new T.TetrahedronGeometry(s * 1.5, 0); }
      else if (O.shape === 'crystal') { geo = new T.OctahedronGeometry(s, 0); geo.scale(0.62, 2.1, 0.62); }
      else { geo = roughen(T, new T.IcosahedronGeometry(s, 0), 0.3, i * 7 + 3, 0.9); }
      paintByPos(T, geo, (c, x, y, z) => {
        let h = Math.sin(Math.round(x * 410) * 12.99 + Math.round(y * 390) * 78.2 + Math.round(z * 370) * 37.7) * 43758.5;
        h -= Math.floor(h);
        const f = h > 0.62 ? 1 : 0;
        c.setRGB(
          O.main[0] * (1 - f) * (0.8 + h * 0.35) + O.fleck[0] * f,
          O.main[1] * (1 - f) * (0.8 + h * 0.35) + O.fleck[1] * f,
          O.main[2] * (1 - f) * (0.8 + h * 0.35) + O.fleck[2] * f);
      });
      const a = rnd() * Math.PI * 2, rr = i ? 0.06 + rnd() * 0.05 : 0;
      const tilt = O.shape === 'crystal' ? 0.5 : 1.6;
      parts.push(placed(T, geo, Math.sin(a) * rr, s * (O.shape === 'crystal' ? 0.9 : 0.45), Math.cos(a) * rr,
        (rnd() - 0.5) * tilt, rnd() * 3.1, (rnd() - 0.5) * tilt, 1));
    }
    return parts;
  };

  // o: { kind, sc, seed, stone: [r,g,b] zone rock tint (optional) }
  kit.build = function (o) {
    o = o || {};
    const O = ORES[o.kind || 'iron'] || ORES.stone;
    const sc = o.sc || 1;
    const rnd = rngFor((o.seed || 5) * 3 + 11);
    const seed = (o.seed || 5) % 97;
    const stone = o.stone || [0.37, 0.36, 0.33];
    const g = new T.Group();

    // ---- the rock mass ------------------------------------------------------
    const rockParts = [];
    const B = [
      [0.78, 0, 0.30, 0],
      [0.55, 0.42, 0.24, 0.20],
      [0.48, -0.40, 0.22, 0.26],
      [0.38, 0.10, 0.52, -0.30],
      [0.30, -0.28, 0.16, -0.34],
      [0.26, 0.48, 0.14, -0.18]
    ];
    const tops = [];   // candidate socket anchors: [x, y, z, nx, ny, nz]
    for (let bi = 0; bi < B.length; bi++) {
      const [r0, bx, by0, bz] = B[bi];
      const r = r0 * sc * (0.92 + rnd() * 0.16);
      const geo = roughen(T, new T.DodecahedronGeometry(r, 1), 0.30, bi * 13 + seed, 0.8);
      geo.scale(1, 0.82, 1);
      paintByPos(T, geo, (c) => c.setRGB(0.5, 0.5, 0.5));   // placeholder, repainted after merge
      const by = r * 0.62 + by0 * sc * 0.3;
      rockParts.push(placed(T, geo, bx * sc, by, bz * sc, rnd() * 0.5, rnd() * 3.1, rnd() * 0.5, 1));
      // upper-hemisphere anchors on this boulder for sockets
      for (let k = 0; k < 3; k++) {
        const a = rnd() * Math.PI * 2;
        const el = 0.6 + rnd() * 0.75;                // elevation: strongly up
        const nx = Math.sin(a) * Math.cos(el), ny = Math.sin(el), nz = Math.cos(a) * Math.cos(el);
        tops.push([bx * sc + nx * r * 0.74, by + ny * r * 0.62, bz * sc + nz * r * 0.74, nx, ny, nz]);
      }
    }
    // craters: dark chipped sockets, part of the rock mesh, ALWAYS visible
    const sites = [];
    const wanted = 6;
    while (sites.length < wanted && tops.length) {
      const i = Math.floor(rnd() * tops.length);
      const cand = tops.splice(i, 1)[0];
      if (sites.some(s2 => Math.hypot(s2[0] - cand[0], s2[1] - cand[1], s2[2] - cand[2]) < 0.34 * sc)) continue;
      sites.push(cand);
    }
    for (const [sx, sy, sz] of sites) {
      const crater = roughen(T, new T.IcosahedronGeometry(0.20 * sc, 0), 0.2, seed + sites.length, 1);
      crater.scale(1, 0.30, 1);
      paintByPos(T, crater, (c) => c.setRGB(0.10, 0.085, 0.07));
      rockParts.push(placed(T, crater, sx, sy, sz, rnd() * 0.4, rnd() * 3, rnd() * 0.4, 1));
    }
    // Strata and footing are painted AFTER the merge so the bands run through
    // the whole mass in world terms - but the crater sockets were painted
    // near-black before it, and must SURVIVE the repaint. Walk the merged
    // attribute directly: dark vertices are craters, keep them.
    const rockGeo = mergeParts(T, rockParts);
    {
      const pos = rockGeo.getAttribute('position');
      const col = rockGeo.getAttribute('color');
      const c = new T.Color();
      const paint = rockPaint(stone, seed);
      for (let i = 0; i < pos.count; i++) {
        if (col && (col.getX(i) + col.getY(i) + col.getZ(i)) < 0.4) continue;   // crater stays
        paint(c, pos.getX(i), pos.getY(i), pos.getZ(i));
        col.setXYZ(i, c.r, c.g, c.b);
      }
      col.needsUpdate = true;
    }
    const rockMesh = new T.Mesh(rockGeo, M.rock);
    rockMesh.castShadow = true; rockMesh.receiveShadow = true;
    g.add(rockMesh);

    // ---- the ore, one mesh, hidden when emptied ----------------------------
    const oreParts = [];
    for (const [sx, sy, sz, nx, ny, nz] of sites) {
      const local = nuggets(O, rnd);
      // orient the cluster out along the socket normal
      const q = new T.Quaternion().setFromUnitVectors(new T.Vector3(0, 1, 0), new T.Vector3(nx, ny, nz).normalize());
      const m = new T.Matrix4().compose(new T.Vector3(sx, sy, sz), q, new T.Vector3(1, 1, 1));
      for (const p of local) {
        p.matrix = m.clone().multiply(p.matrix);
        oreParts.push(p);
      }
    }
    const oreMesh = new T.Mesh(mergeParts(T, oreParts), O.glow ? M.glow : M.ore);
    oreMesh.castShadow = true;
    g.add(oreMesh);

    // ---- the rubble: shown when emptied ------------------------------------
    const rub = new T.Group();
    rub.visible = false;
    const rubParts = [];
    for (let i = 0; i < 7; i++) {
      const a = rnd() * Math.PI * 2, rr = (0.75 + rnd() * 0.55) * sc;
      const s = 0.05 + rnd() * 0.055;
      const geo = roughen(T, new T.DodecahedronGeometry(s, 0), 0.3, i * 5 + seed, 0.8);
      paintByPos(T, geo, (c) => {
        const v = 0.65 + rnd() * 0.3;
        c.setRGB(stone[0] * v, stone[1] * v, stone[2] * v);
      });
      rubParts.push(placed(T, geo, Math.sin(a) * rr, s * 0.5, Math.cos(a) * rr, rnd() * 3, rnd() * 3, rnd() * 3, 1));
    }
    // a couple of spent ore crumbs in the rubble, so the pile says what lived here
    for (let i = 0; i < 2; i++) {
      const a = rnd() * Math.PI * 2, rr = (0.7 + rnd() * 0.4) * sc;
      const geo = new T.OctahedronGeometry(0.035 * O.size + 0.015, 0);
      paintByPos(T, geo, (c) => c.setRGB(O.main[0] * 0.7, O.main[1] * 0.7, O.main[2] * 0.7));
      rubParts.push(placed(T, geo, Math.sin(a) * rr, 0.035, Math.cos(a) * rr, rnd() * 3, rnd() * 3, rnd() * 3, 1));
    }
    const rubMesh = new T.Mesh(mergeParts(T, rubParts), M.rock);
    rubMesh.castShadow = true; rub.add(rubMesh);
    g.add(rub);

    if (o.x !== undefined) g.position.set(o.x, o.y || 0, o.z || 0);
    return { g, studs: [oreMesh], rubble: rub, radius: 1.15 * sc };
  };

  kit.tick = function () {};
  return kit;
}
