// GRIM WORLD: the smelting furnace.
//
// A full rework of the Hollowrest furnace, built the way the real thing is
// built. A smelting furnace is a SHAFT: the charge of ore and charcoal goes in
// at the top, air is driven in through a tuyere near the base by a bellows,
// and the melt is worked through a brick arch at the bottom. The old prop was
// two cylinders and a glowing sticker; nothing of it survives.
//
// What this one gets right, in the order a player reads it:
//
//   1. The SILHOUETTE: a bulging clay shaft (the bosh) on a course of field
//      stones, narrowing to a firebrick crown, with a big double-lung bellows
//      leaning into its flank. That bellows is the thing that says "furnace"
//      from fifty metres, and it BREATHES.
//   2. The HEAT: coals and flame down the arch throat, a glowing charge hole
//      at the top with embers riding the updraft, firebrick scorched black
//      above the mouth, and soot climbing the stack. Everything hot glows;
//      everything near the heat remembers it.
//   3. The WORK: a slag gutter running to a pit of cooled black glass, a mold
//      bench with bars still cooling from the last melt, and an ore trough
//      holding the three ores it smelts - copper, iron and gold.
//
// Everything animated runs off one uTime uniform (flames, embers, smoke) plus
// two CPU writes a frame for the bellows boards and the crown pulse.
//
// The module touches nothing outside itself: T comes in as an argument,
// terrain comes in as an optional callback, and the lab page and the game run
// this same file.

import {
  rngFor, mergeParts, roughen, paintByPos, logBetween, placed,
  loftRect, flameMat, driftMat, driftField, tongueParts, glowMat, drapedDisc
} from './grim-kit.js';

export function makeFurnaceKit(T, opt) {
  opt = opt || {};
  const kit = { T, mats: {}, _t: 0, _anim: [] };

  // ---- shared materials ----------------------------------------------------
  // One of each, shared by every instance, so the whole world's furnaces cost
  // a handful of uniform writes per frame.
  const M = kit.mats;
  M.clay = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.94, metalness: 0, flatShading: true });
  M.stone = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.95, metalness: 0.02, flatShading: true });
  M.wood = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.86, metalness: 0, flatShading: true });
  M.leather = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.9, metalness: 0.04, flatShading: true });
  M.iron = new T.MeshStandardMaterial({ color: 0x33312e, roughness: 0.55, metalness: 0.6, flatShading: true });
  // Hot things are UNLIT: coals, cooling bars, the melt. Vertex colours carry
  // the temperature ramp and no light in the scene can wash it out.
  M.hot = new T.MeshBasicMaterial({ vertexColors: true });
  M.dark = new T.MeshBasicMaterial({ color: 0x120603 });
  M.flame = flameMat(T, { c0: 0xffe9a0, c1: 0xffa63e, c2: 0xff4d18, alpha: 0.85, erode: 1.15, sway: 0.8, lick: 0.9, rate: 1.0 });
  M.flameCore = flameMat(T, { c0: 0xfffbd8, c1: 0xffcf6e, c2: 0xff7a28, alpha: 0.8, erode: 0.7, sway: 0.45, lick: 0.7, rate: 1.25 });
  M.embers = driftMat(T, { rise: 1.7, size: 0.042, grow: 0.4, wander: 0.16, spread: 0.30, ease: 0.62, lean: 0.06, col: 0xffd08a, col2: 0xff5a20, alpha: 0.9, rate: 0.16, hold: 0.72, flick: 0.55, additive: true });
  M.mouthSp = driftMat(T, { rise: 0.55, size: 0.03, grow: 0.2, wander: 0.10, spread: 0.14, ease: 0.7, lean: 0.22, col: 0xffe4a8, col2: 0xff6a24, alpha: 0.85, rate: 0.22, hold: 0.6, flick: 0.7, additive: true });
  M.smoke = driftMat(T, { rise: 2.4, size: 0.34, grow: 2.6, wander: 0.42, spread: 0.30, ease: 0.75, lean: 0.35, col: 0x2b2724, col2: 0x4a453f, alpha: 0.16, rate: 0.05, hold: 0.55, flick: 0, additive: false });
  M.glow = glowMat(T, [
    [0.00, 'rgba(255,184,104,0.75)'],
    [0.25, 'rgba(255,148,58,0.42)'],
    [0.52, 'rgba(255,116,34,0.16)'],
    [1.00, 'rgba(255,96,26,0.00)']
  ]);
  M.mouthGlow = glowMat(T, [
    [0.00, 'rgba(255,214,140,0.95)'],
    [0.30, 'rgba(255,150,60,0.55)'],
    [0.65, 'rgba(255,100,30,0.16)'],
    [1.00, 'rgba(255,90,26,0.00)']
  ]);

  // ---------------------------------------------------------------------------
  // build one furnace
  // ---------------------------------------------------------------------------
  // o: { seed, x, y, z, heightAt }  Returns { g, radius, light, mouth, top }.
  kit.build = function (o) {
    o = o || {};
    const rnd = rngFor(o.seed || 7);
    const g = new T.Group();

    const clayParts = [], stoneParts = [], woodParts = [], ironParts = [], hotParts = [], leatherParts = [];

    // ---- the shaft -----------------------------------------------------------
    // Round loft, bulging at the bosh, waisting toward a firebrick crown. The
    // paint does most of the work: warm clay low, soot climbing the top half,
    // a scorch fan above the mouth, and heat-blackening on the crown.
    const shaft = loftRect(T, 'y', [
      { at: 0.04, hu: 0.86, hv: 0.86, p: 2.4 },
      { at: 0.38, hu: 0.93, hv: 0.93, p: 2.4 },
      { at: 0.86, hu: 0.90, hv: 0.90, p: 2.3 },
      { at: 1.48, hu: 0.70, hv: 0.70, p: 2.3 },
      { at: 2.02, hu: 0.56, hv: 0.56, p: 2.3 },
      { at: 2.28, hu: 0.60, hv: 0.60, p: 2.3 },
      { at: 2.42, hu: 0.63, hv: 0.63, p: 2.5 },
      { at: 2.46, hu: 0.52, hv: 0.52, p: 2.5 },
      { at: 2.30, hu: 0.36, hv: 0.36, p: 2.3 }
    ], 20, (c, x, y, z, t) => {
      // base clay, hashed so no two courses read as one flat pour
      let h = Math.sin(Math.round(x * 91) * 12.9898 + Math.round(y * 77) * 78.233 + Math.round(z * 83) * 37.719) * 43758.5453;
      h -= Math.floor(h);
      let r = 0.58 + h * 0.10, gr = 0.44 + h * 0.08, b = 0.32 + h * 0.06;
      // soot climbs the stack hard: near-black through the upper third
      const soot = Math.min(1, Math.max(0, (y - 0.95) / 1.05));
      // scorch fan above the mouth (+z), widening as it rises
      const fan = (z > 0.2 && y > 1.15 && y < 2.3)
        ? Math.max(0, 1 - Math.abs(x) / (0.30 + (y - 1.15) * 0.55)) * Math.max(0, 1 - (y - 1.15) / 1.25) : 0;
      const dk = Math.min(1, soot * 0.95 + fan * 0.9);
      r *= (1 - dk * 0.88); gr *= (1 - dk * 0.92); b *= (1 - dk * 0.86);
      // the crown is fired brick, dark red-black
      if (y > 2.22) { r = r * 0.3 + 0.145; gr = gr * 0.3 + 0.055; b = b * 0.3 + 0.035; }
      // the throat: the shaft wall the doorway looks onto is char black,
      // holding a little ember red near the coal line
      if (z > 0.5 && Math.abs(x) < 0.58 && y < 1.35) {
        const emb = Math.max(0, 1 - Math.abs(y - 0.35) / 0.55) * 0.16;
        r = 0.05 + emb; gr = 0.028 + emb * 0.35; b = 0.022;
      }
      c.setRGB(r, gr, b);
    });
    roughen(T, shaft, 0.035, 3 + (o.seed || 7), 1);
    clayParts.push({ geo: shaft });

    // ---- foundation stones and hearth pad -----------------------------------
    const stonePaint = (base, sootFn) => (c, x, y, z) => {
      let h = Math.sin(Math.round(x * 133) * 12.9898 + Math.round(y * 121) * 78.233 + Math.round(z * 117) * 37.719) * 43758.5453;
      h -= Math.floor(h);
      let r = base[0] * (0.82 + h * 0.36), gr = base[1] * (0.82 + h * 0.36), b = base[2] * (0.82 + h * 0.36);
      const s = sootFn ? sootFn(x, y, z) : 0;
      c.setRGB(r * (1 - s * 0.8), gr * (1 - s * 0.82), b * (1 - s * 0.78));
    };
    // one course of field stones tucked against the flared base, the mouth
    // side left completely clear so the arch owns the front
    for (let i = 0; i < 18; i++) {
      const a = i / 18 * Math.PI * 2 + rnd() * 0.12;
      const sx = Math.sin(a) * 0.92, sz = Math.cos(a) * 0.92;
      if (sz > 0.45 && Math.abs(sx) < 0.72) continue;   // door gap
      const s = 0.10 + rnd() * 0.06;
      const geo = roughen(T, new T.DodecahedronGeometry(s, 0), 0.22, i * 7 + (o.seed || 7), 0.72);
      paintByPos(T, geo, stonePaint([0.47, 0.45, 0.41], () => 0.10));
      stoneParts.push(placed(T, geo, sx, s * 0.7, sz, rnd() * 0.6, rnd() * 3.1, rnd() * 0.6, 1));
    }
    // flagstone hearth pad
    for (let i = 0; i < 9; i++) {
      const a = rnd() * Math.PI * 2, r = 0.55 + rnd() * 0.6;
      const px = Math.sin(a) * r, pz = Math.cos(a) * r * 1.15;
      const s = 0.18 + rnd() * 0.12;
      const geo = roughen(T, new T.CylinderGeometry(s, s * 1.06, 0.04, 6), 0.10, i * 13 + 5, 1);
      paintByPos(T, geo, stonePaint([0.30, 0.29, 0.265], (x, y, z) => Math.max(0, 0.55 - (Math.hypot(px, pz - 0.9)) * 0.3)));
      stoneParts.push(placed(T, geo, px, 0.03, pz, 0, rnd() * 3.1, 0, 1));
    }

    // ---- the firebrick arch --------------------------------------------------
    // Nine voussoirs on a semicircle, proud of the shaft face, black inside
    // where the fire has licked them for years. Jambs below the spring line.
    const brickPaint = stonePaint([0.55, 0.30, 0.23], (x, y, z) => {
      const dm = Math.hypot(x, y - 0.62);
      return Math.max(0, 1 - dm / 0.42) * 0.85;
    });
    for (let i = 0; i < 9; i++) {
      const a = Math.PI * (i / 8);         // 0..PI over the arch
      const bx = Math.cos(a) * 0.42, by = 0.62 + Math.sin(a) * 0.42;
      const geo = new T.BoxGeometry(0.15, 0.115, 0.16);
      paintByPos(T, geo, (c, x, y, z) => brickPaint(c, x + bx, y + by, z));
      stoneParts.push(placed(T, geo, bx, by, 1.16, 0, 0, a - Math.PI / 2, 1));
    }
    for (const sx of [-1, 1]) {
      for (let j = 0; j < 3; j++) {
        const geo = new T.BoxGeometry(0.16, 0.15, 0.17);
        const by = 0.12 + j * 0.16;
        paintByPos(T, geo, (c, x, y, z) => brickPaint(c, x + sx * 0.44, y + by, z));
        stoneParts.push(placed(T, geo, sx * 0.44, by, 1.16, 0, 0, (rnd() - 0.5) * 0.06, 1));
      }
    }

    // ---- the forebox ---------------------------------------------------------
    // The working mouth PROJECTS from the shaft, the way tap arches do: a
    // masonry porch with the brick arch on its face and a genuinely open
    // chamber behind it. The first two cuts put the arch flat on the shaft
    // wall - a solid wall - so the "fire" was lamplight on clay. The shell is
    // scorched masonry outside; the liner boxes inside are near-black with a
    // held ember red, and the coals sit on the liner floor in plain view.
    {
      const shellPaint = stonePaint([0.40, 0.245, 0.185], (x, y, z) =>
        Math.min(1, Math.max(0, (y - 0.75) * 1.1) + Math.max(0, (z - 0.95) * 0.9)));
      const shell = (w, h, d, px, py, pz) => {
        const geo = new T.BoxGeometry(w, h, d);
        paintByPos(T, geo, (c, x, y, z) => shellPaint(c, x + px, y + py, z + pz));
        stoneParts.push(placed(T, geo, px, py, pz, 0, 0, 0, 1));
      };
      shell(1.06, 0.14, 0.58, 0, 0.07, 0.86);      // plinth
      shell(0.14, 1.02, 0.58, -0.46, 0.65, 0.86);  // walls
      shell(0.14, 1.02, 0.58, 0.46, 0.65, 0.86);
      shell(1.06, 0.13, 0.58, 0, 1.22, 0.86);      // roof slab
      // spandrels close the corners between the arch ring and the shell
      for (const sx of [-1, 1]) {
        const sp = new T.BoxGeometry(0.13, 0.15, 0.15);
        paintByPos(T, sp, (c, x, y, z) => brickPaint(c, x + sx * 0.37, y + 1.0, z));
        stoneParts.push(placed(T, sp, sx * 0.37, 1.02, 1.14, 0, 0, sx * 0.5, 1));
      }
      // dark liner: what you see through the arch, recessed so the reveal
      // reads as depth
      const bp = [];
      bp.push(placed(T, new T.BoxGeometry(0.76, 0.06, 0.50), 0, 0.17, 0.81, 0, 0, 0, 1));   // hearth floor
      bp.push(placed(T, new T.BoxGeometry(0.06, 1.0, 0.50), -0.38, 0.66, 0.81, 0, 0, 0, 1));
      bp.push(placed(T, new T.BoxGeometry(0.06, 1.0, 0.50), 0.38, 0.66, 0.81, 0, 0, 0, 1));
      bp.push(placed(T, new T.BoxGeometry(0.76, 0.06, 0.50), 0, 1.13, 0.81, 0, 0, 0, 1));
      bp.push(placed(T, new T.BoxGeometry(0.78, 1.05, 0.04), 0, 0.68, 0.93, 0, 0, 0, 1));   // throat backdrop, proud of the shaft bulge
      g.add(new T.Mesh(mergeParts(T, bp), M.dark));
    }

    const coalParts = [];
    for (let i = 0; i < 9; i++) {
      const cx = (rnd() - 0.5) * 0.54, cz = 0.97 + rnd() * 0.14, cy = 0.23 + rnd() * 0.05;
      const s = 0.055 + rnd() * 0.055;
      const geo = roughen(T, new T.IcosahedronGeometry(s, 0), 0.3, i * 3 + 1, 0.8);
      paintByPos(T, geo, (c, x, y, z) => {
        const d = Math.hypot(x + cx, (z + cz) - 1.04) / 0.40;
        const t = Math.max(0, 1 - d);
        c.setRGB(0.40 + t * 0.60, 0.06 + t * 0.42, 0.015 + t * 0.06);
      });
      coalParts.push(placed(T, geo, cx, cy, cz, rnd() * 3, rnd() * 3, rnd() * 3, 1));
    }
    // cooling bars on the mold bench get merged into the same hot mesh below

    // flames: a small cluster licking up from the coals, two layers
    const tongues = [];
    for (let i = 0; i < 4; i++) {
      const a = rnd() * Math.PI * 2, r = rnd() * 0.16;
      tongues.push({ R: 0.055 + rnd() * 0.03, H: 0.52 + rnd() * 0.22, x: Math.sin(a) * r, z: 1.03 + Math.cos(a) * r * 0.35, y: 0.26, seed: rnd() * 9, tx: (rnd() - 0.5) * 0.16, tz: (rnd() - 0.5) * 0.16 });
    }
    const flame = new T.Mesh(mergeParts(T, tongueParts(T, tongues, 7, 9)), M.flame);
    flame.renderOrder = 4; g.add(flame);
    const core = new T.Mesh(mergeParts(T, tongueParts(T, [
      { R: 0.045, H: 0.34, x: -0.04, z: 1.0, y: 0.25, seed: 3.1 },
      { R: 0.04, H: 0.28, x: 0.06, z: 1.06, y: 0.25, seed: 7.7 }
    ], 7, 8)), M.flameCore);
    core.renderOrder = 5; g.add(core);

    // ---- iron banding --------------------------------------------------------
    // Two riveted hoops holding the clay, the way working kilns are strapped.
    // The LOWER hoop is a partial arc: it stops at the arch jambs instead of
    // running a bar straight across the doorway, which the first cut did.
    for (const [by, br, gap] of [[0.52, 0.925, 1.3], [1.42, 0.725, 0]]) {
      const geo = new T.TorusGeometry(br, 0.026, 6, 22, Math.PI * 2 - gap);
      geo.rotateX(Math.PI / 2);
      // torus arc starts at +x; rotate so the gap centres on the mouth (+z)
      ironParts.push(placed(T, geo, 0, by, 0, 0, gap ? -(Math.PI / 2 + gap / 2) : 0, 0, 1));
      for (let i = 0; i < 6; i++) {
        const a = i / 6 * Math.PI * 2 + 0.3;
        if (gap && Math.abs(Math.atan2(Math.sin(a), Math.cos(a)) - Math.PI / 2) < gap / 2 + 0.2) continue;
        ironParts.push(placed(T, new T.BoxGeometry(0.05, 0.05, 0.05), Math.sin(a) * br, by, Math.cos(a) * br, 0, a, 0, 1));
      }
    }

    // ---- slag gutter and pit -------------------------------------------------
    // The melt's waste runs out of the arch, right and down, into a pit of
    // cooled black glass with the last heat still in its cracks.
    {
      const gy = Math.atan2(0.98 - 0.38, 1.44 - 0.96) * 0 + 0.95;   // heading of the run
      const mk = (w, h, off) => {
        const geo = new T.BoxGeometry(0.72, h, w);
        paintByPos(T, geo, stonePaint([0.28, 0.26, 0.24], () => 0.45));
        stoneParts.push(placed(T, geo, 0.80, 0.05 + (off ? 0.045 : 0), 1.52 + off, -0.09, gy, 0, 1));
      };
      mk(0.16, 0.035, 0);          // floor
      mk(0.045, 0.09, 0.085);      // rail
      mk(0.045, 0.09, -0.085);     // rail
    }
    for (let i = 0; i < 6; i++) {
      const px = 1.12 + (rnd() - 0.5) * 0.34, pz = 1.85 + (rnd() - 0.5) * 0.3;
      const s = 0.055 + rnd() * 0.06;
      const geo = roughen(T, new T.IcosahedronGeometry(s, 0), 0.32, i * 5 + 2, 0.7);
      paintByPos(T, geo, (c, x, y, z) => {
        const glow = Math.max(0, -y) * 2.2;       // heat lingers in the underside cracks
        c.setRGB(0.05 + glow * 0.55, 0.045 + glow * 0.09, 0.05);
      });
      ironParts.push(placed(T, geo, px, s * 0.55, pz, rnd() * 3, rnd() * 3, rnd() * 3, 1));
    }

    // ---- mold bench ----------------------------------------------------------
    // A stone slab left of the mouth. Three dark molds are sunk flush in its
    // top and two bars still sit IN them, one blazing fresh, one dull red -
    // the furnace's product, visible at a glance.
    {
      const bx = -1.05, bz = 1.02;
      const slab = new T.BoxGeometry(0.58, 0.08, 0.38);
      paintByPos(T, slab, stonePaint([0.30, 0.285, 0.26], () => 0.2));
      stoneParts.push(placed(T, slab, bx, 0.40, bz, 0, 0, 0, 1));
      for (const [lx, lz] of [[bx - 0.24, bz - 0.13], [bx + 0.24, bz - 0.13], [bx - 0.24, bz + 0.13], [bx + 0.24, bz + 0.13]]) {
        const leg = new T.BoxGeometry(0.12, 0.36, 0.12);
        paintByPos(T, leg, stonePaint([0.38, 0.36, 0.33], () => 0.1));
        stoneParts.push(placed(T, leg, lx, 0.18, lz, 0, 0, 0, 1));
      }
      for (let i = 0; i < 3; i++) {
        const mz = bz - 0.13 + i * 0.13;
        const mold = new T.BoxGeometry(0.40, 0.035, 0.11);
        paintByPos(T, mold, stonePaint([0.16, 0.15, 0.14], () => 0.5));
        stoneParts.push(placed(T, mold, bx, 0.455, mz, 0, 0, 0, 1));
        if (i === 2) continue;                       // one mold stands empty
        const bar = new T.BoxGeometry(0.32, 0.035, 0.08);
        paintByPos(T, bar, i === 0
          ? ((c, x) => { const t = 1 - Math.abs(x) / 0.16; c.setRGB(0.78 + t * 0.22, 0.48 + t * 0.4, 0.12 + t * 0.26); })
          : ((c, x) => { const t = Math.max(0, 1 - Math.abs(x) / 0.11); c.setRGB(0.34 + t * 0.36, 0.06 + t * 0.10, 0.02); }));
        coalParts.push(placed(T, bar, bx, 0.468, mz, 0, 0, 0, 1));
      }
    }

    // ---- ore trough ----------------------------------------------------------
    // The feedstock, right of the mouth: a proper V-trough with copper, iron
    // and gold ore heaped down its middle. Says "this thing smelts everything"
    // without a word.
    {
      const tx = 1.22, tz = 0.68, ty = 0.20, ry = -0.35;
      const woodPaint2 = stonePaint([0.36, 0.25, 0.15], () => 0.05);
      const side = (sgn) => {
        const p = new T.BoxGeometry(0.86, 0.035, 0.24);
        paintByPos(T, p, woodPaint2);
        stoneParts.push(placed(T, p, tx + Math.sin(ry) * sgn * -0.098, ty, tz + Math.cos(ry) * sgn * 0.098, sgn * 0.62, ry, 0, 1));
      };
      side(-1); side(1);
      for (const ex of [-0.43, 0.43]) {
        const cap = new T.BoxGeometry(0.035, 0.22, 0.20);
        paintByPos(T, cap, woodPaint2);
        stoneParts.push(placed(T, cap, tx + Math.cos(ry) * ex, ty + 0.02, tz - Math.sin(ry) * ex, 0, ry, 0, 1));
      }
      for (const lx of [-0.3, 0.3]) {
        const leg = new T.BoxGeometry(0.06, 0.16, 0.28);
        paintByPos(T, leg, woodPaint2);
        stoneParts.push(placed(T, leg, tx + Math.cos(ry) * lx, 0.08, tz - Math.sin(ry) * lx, 0, ry, 0, 1));
      }
      const ORES = [
        [0.45, 0.28, 0.18, 0.22, 0.52, 0.38],   // copper: brown with verdigris
        [0.40, 0.28, 0.22, 0.30, 0.20, 0.16],   // iron: rust brown
        [0.70, 0.55, 0.20, 0.92, 0.76, 0.30]    // gold: warm yellow flecks
      ];
      for (let i = 0; i < 8; i++) {
        const O = ORES[i % 3];
        const s = 0.055 + rnd() * 0.035;
        const geo = roughen(T, new T.IcosahedronGeometry(s, 0), 0.3, i * 9 + 4, 0.85);
        paintByPos(T, geo, (c, x, y, z) => {
          let h = Math.sin(Math.round(x * 210) * 12.99 + Math.round(y * 190) * 78.2 + Math.round(z * 170) * 37.7) * 43758.5;
          h -= Math.floor(h);
          if (h > 0.6) c.setRGB(O[3], O[4], O[5]); else c.setRGB(O[0], O[1], O[2]);
        });
        const along = -0.34 + i * 0.1 + (rnd() - 0.5) * 0.04;
        stoneParts.push(placed(T, geo, tx + Math.cos(ry) * along, ty + 0.075 + (i % 2) * 0.02, tz - Math.sin(ry) * along, rnd() * 3, rnd() * 3, rnd() * 3, 1));
      }
    }

    // ---- the bellows ---------------------------------------------------------
    // A BIG double-lung bellows on the left flank, the length of a man, on a
    // low trestle, nozzle into a clay tuyere at the air line. The top board
    // and the leather are ANIMATED: the lung squeezes shut fast and refills
    // slow, which is exactly the rhythm the roar surges to.
    const bel = new T.Group();
    bel.position.set(-1.78, 0.58, 0.66);
    bel.rotation.y = 0.28;                        // local +x aims at the flank
    bel.rotation.z = -0.16;                       // nozzle dips to the air line
    const woodPaint = stonePaint([0.34, 0.235, 0.14], () => 0.05);
    const board = (top) => loftRect(T, 'x', [
      { at: -0.62, hu: 0.21, hv: 0.028, p: 3.2 },
      { at: -0.12, hu: 0.27, hv: 0.030, p: 3.2 },
      { at: 0.38, hu: 0.14, hv: 0.026, p: 3.0 },
      { at: 0.60, hu: 0.05, hv: 0.022, p: 2.4 }
    ], 12, top
      ? stonePaint([0.385, 0.265, 0.16], () => 0.03)
      : woodPaint);
    // static: lower board, trestle legs, cross-brace - one merged mesh
    {
      const parts = [{ geo: board(false) }];
      const leg = (lx, lz0, lz1) => {
        const l = logBetween(T, new T.Vector3(lx, -0.02, lz0), new T.Vector3(lx, -0.50, lz1), 0.035, 0.045, { rough: 0.05, seed: 71, segments: 6 });
        paintByPos(T, l.geo, woodPaint);
        parts.push(l);
      };
      leg(-0.38, 0.16, 0.24); leg(-0.38, -0.16, -0.24); leg(0.28, 0.13, 0.20); leg(0.28, -0.13, -0.20);
      const brace = logBetween(T, new T.Vector3(-0.38, -0.30, 0), new T.Vector3(0.28, -0.30, 0), 0.028, 0.028, { rough: 0.04, seed: 77, segments: 6 });
      paintByPos(T, brace.geo, woodPaint);
      parts.push(brace);
      const stat = new T.Mesh(mergeParts(T, parts), M.wood);
      stat.castShadow = true; bel.add(stat);
    }
    // animated: top board + its handle, hinged at the nozzle
    const upperPiv = new T.Group();
    upperPiv.position.set(0.60, 0.03, 0);
    {
      const parts = [placed(T, board(true), -0.60, 0, 0, 0, 0, 0, 1)];
      const hnd = logBetween(T, new T.Vector3(-1.32, 0.03, 0), new T.Vector3(-0.68, 0.03, 0), 0.026, 0.033, { rough: 0.03, seed: 61, segments: 6 });
      paintByPos(T, hnd.geo, woodPaint);
      parts.push(hnd);
      const up = new T.Mesh(mergeParts(T, parts), M.wood);
      up.castShadow = true; upperPiv.add(up);
    }
    bel.add(upperPiv);
    // the lung: a leather wedge between the boards, scaled by the breath
    const lung = loftRect(T, 'x', [
      { at: -0.56, hu: 0.145, hv: 0.5, p: 2.6 },
      { at: -0.10, hu: 0.195, hv: 0.5, p: 2.6 },
      { at: 0.38, hu: 0.095, hv: 0.5, p: 2.4 },
      { at: 0.56, hu: 0.035, hv: 0.5, p: 2.2 }
    ], 12, (c, x, y, z) => {
      // pleats: darker folds every few centimetres along the length
      const pl = Math.sin(x * 26) > 0.25 ? 0.6 : 1;
      c.setRGB(0.20 * pl, 0.115 * pl, 0.075 * pl);
    });
    const lungM = new T.Mesh(lung, M.leather);
    lungM.scale.y = 0.28; bel.add(lungM);
    const noz = new T.Mesh(new T.CylinderGeometry(0.028, 0.042, 0.22, 8), M.iron);
    noz.rotation.z = Math.PI / 2; noz.position.set(0.68, 0.02, 0); bel.add(noz);
    g.add(bel);
    // tuyere: clay pipe carrying the blast from the nozzle into the shaft
    const nozzleTip = new T.Vector3(0.66, 0.53, 0).applyAxisAngle(new T.Vector3(0, 1, 0), 0.28).add(new T.Vector3(-1.72, 0, 0.62));
    const tuy = logBetween(T, nozzleTip, new T.Vector3(-0.72, 0.42, 0.30), 0.045, 0.075, { rough: 0.05, seed: 81, segments: 7 });
    paintByPos(T, tuy.geo, stonePaint([0.5, 0.38, 0.27], () => 0.3));
    clayParts.push(tuy);

    // ---- merged static meshes ------------------------------------------------
    const mkMesh = (parts, mat, shadow) => {
      if (!parts.length) return null;
      const m = new T.Mesh(mergeParts(T, parts), mat);
      m.castShadow = !!shadow; m.receiveShadow = true;
      g.add(m); return m;
    };
    mkMesh(clayParts, M.clay, true);
    mkMesh(stoneParts, M.stone, true);
    mkMesh(woodParts, M.wood, true);
    mkMesh(ironParts, M.iron, true);
    const hotMesh = mkMesh(coalParts.concat(hotParts), M.hot, false);
    if (hotMesh) hotMesh.receiveShadow = false;

    // ---- glows, particles, light --------------------------------------------
    // Backlight plane inside the arch: the opening pours light.
    const mg = new T.Mesh(new T.PlaneGeometry(0.44, 0.44), M.mouthGlow);
    mg.position.set(0, 0.40, 0.955); mg.renderOrder = 3; g.add(mg);
    // Crown glow: the charge hole seen from above and its halo seen from afar.
    const cg = new T.Mesh(new T.CircleGeometry(0.34, 14), M.mouthGlow);
    cg.rotation.x = -Math.PI / 2; cg.position.y = 2.36; cg.renderOrder = 3; g.add(cg);
    kit._crown = cg;

    const rndE = rngFor((o.seed || 7) * 3 + 1);
    const embers = new T.Mesh(driftField(T, 24, 0.16, 2.42, rndE), M.embers);
    embers.renderOrder = 6; embers.frustumCulled = false; g.add(embers);
    const msp = new T.Mesh(driftField(T, 10, 0.12, 0.5, rndE), M.mouthSp);
    msp.position.z = 1.05; msp.renderOrder = 6; msp.frustumCulled = false; g.add(msp);
    const smoke = new T.Mesh(driftField(T, 14, 0.2, 2.5, rndE), M.smoke);
    smoke.renderOrder = 2; smoke.frustumCulled = false; g.add(smoke);

    const gg = new T.Mesh(drapedDisc(T, 1.3, 26, o.x || 0, (o.z || 0) + 1.1, o.heightAt, 0.06), M.glow);
    gg.position.set(0, 0, 1.1); gg.renderOrder = 1; g.add(gg);

    const light = new T.PointLight(0xff9636, 6, 10, 2);
    light.position.set(0, 0.72, 1.28);
    g.add(light);

    kit._anim.push({ upperPiv, lungM });

    if (o.x !== undefined) g.position.set(o.x, o.y || 0, o.z || 0);
    return { g, radius: 1.6, light, mouth: new T.Vector3(0, 0.62, 1.3), top: new T.Vector3(0, 2.5, 0) };
  };

  // ---------------------------------------------------------------------------
  // one call a frame for every furnace in the world
  // ---------------------------------------------------------------------------
  kit.tick = function (t) {
    kit._t = t;
    for (const m of [M.flame, M.flameCore, M.embers, M.mouthSp, M.smoke]) {
      if (m.userData.U) m.userData.U.uTime.value = t;
    }
    // The breath: squeeze fast, refill slow. pow sharpens the squeeze.
    const ph = t * 0.85;
    const pump = Math.pow(Math.max(0, Math.sin(ph)), 1.7);
    for (const a of kit._anim) {
      const rz = 0.44 - pump * 0.38;
      a.upperPiv.rotation.z = rz;
      a.lungM.scale.y = 0.08 + rz * 0.72;
      a.lungM.position.y = rz * 0.28;
    }
    if (kit._crown) kit._crown.material.opacity = 0.42 + 0.16 * Math.sin(t * 2.6) + 0.08 * Math.sin(t * 7.1);
  };

  // ---------------------------------------------------------------------------
  // sound: the roar of a fed fire
  // ---------------------------------------------------------------------------
  // Deeper than the campfire: a furnace under bellows is mostly LOW roar, and
  // it SURGES on the bellows rhythm - same 0.85 rad/s the boards move at, so
  // eye and ear agree. Sparse deep pops; no light crackle, this is not a
  // marshmallow fire.
  kit.sound = function (ac, dest, o) {
    o = o || {};
    if (!ac) return null;
    const gain = o.gain === undefined ? 0.5 : o.gain;
    const out = ac.createGain();
    out.gain.value = 0;
    out.connect(dest || ac.destination);

    const LEN = Math.floor(ac.sampleRate * 4);
    const buf = ac.createBuffer(1, LEN, ac.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < LEN; i++) {
      const w = Math.random() * 2 - 1;
      last = (last + 0.024 * w) / 1.024;
      d[i] = last * 3.2;
    }
    const X = Math.floor(ac.sampleRate * 0.25);
    for (let i = 0; i < X; i++) {
      const tt = i / X;
      d[i] = d[i] * tt + d[LEN - X + i] * (1 - tt);
    }
    const src = ac.createBufferSource();
    src.buffer = buf; src.loop = true;

    const roar = ac.createBiquadFilter();
    roar.type = 'lowpass'; roar.frequency.value = 300; roar.Q.value = 0.8;
    const roarG = ac.createGain(); roarG.gain.value = 0.55;
    src.connect(roar); roar.connect(roarG); roarG.connect(out);

    // the air blast: a mid band that swells with the bellows
    const blast = ac.createBiquadFilter();
    blast.type = 'bandpass'; blast.frequency.value = 520; blast.Q.value = 0.9;
    const blastG = ac.createGain(); blastG.gain.value = 0.05;
    src.connect(blast); blast.connect(blastG); blastG.connect(out);
    const lfo = ac.createOscillator();
    lfo.type = 'sine'; lfo.frequency.value = 0.85 / (2 * Math.PI);
    const lfoG = ac.createGain(); lfoG.gain.value = 0.13;
    lfo.connect(lfoG); lfoG.connect(blastG.gain);

    src.start(); lfo.start();

    let stopped = false, timer = null;
    const popAt = (t0) => {
      const cs = ac.createBufferSource();
      cs.buffer = buf; cs.playbackRate.value = 0.6 + Math.random() * 0.3;
      const bp = ac.createBiquadFilter();
      bp.type = 'bandpass'; bp.frequency.value = 300 + Math.random() * 500; bp.Q.value = 1.2;
      const pg = ac.createGain();
      const peak = 0.5 * (0.5 + Math.random() * 0.9);
      pg.gain.setValueAtTime(0, t0);
      pg.gain.linearRampToValueAtTime(peak, t0 + 0.008);
      pg.gain.exponentialRampToValueAtTime(0.001, t0 + 0.11 + Math.random() * 0.1);
      cs.connect(bp); bp.connect(pg); pg.connect(out);
      cs.start(t0, Math.random() * 3.0, 0.35);
    };
    if (o.prerender) {
      // offline render: setTimeout never fires, so lay the pops out now
      let pt = 0.6;
      while (pt < o.prerender) { popAt(pt); pt += 0.9 + Math.random() * 2.4; }
    } else {
      const schedule = () => {
        if (stopped) return;
        popAt(ac.currentTime + 0.02);
        timer = setTimeout(schedule, 900 + Math.random() * 2400);
      };
      timer = setTimeout(schedule, 700);
    }

    let vol = 1, dist = 1;
    const apply = () => { out.gain.value = gain * vol * dist; };
    apply();
    return {
      stop() { stopped = true; clearTimeout(timer); try { src.stop(); lfo.stop(); } catch (e) {} out.disconnect(); },
      setDistance(dd, gone) { const f = Math.max(0, 1 - dd / (gone || 30)); dist = f * f; apply(); },
      setVolume(v) { vol = v; apply(); }
    };
  };

  // The smelt one-shot: a bar comes off the melt. A molten hiss with a low
  // thump under it, played by the game when a bar completes.
  kit.pour = function (ac, dest, o) {
    o = o || {};
    if (!ac) return;
    const t0 = o.at !== undefined ? o.at : ac.currentTime;
    const gain = o.gain === undefined ? 0.5 : o.gain;
    const out = ac.createGain();
    out.gain.value = gain;
    out.connect(dest || ac.destination);
    // sizzle: white noise, highpassed, fast decay
    const N = Math.floor(ac.sampleRate * 0.8);
    const nb = ac.createBuffer(1, N, ac.sampleRate);
    const nd = nb.getChannelData(0);
    for (let i = 0; i < N; i++) nd[i] = (Math.random() * 2 - 1);
    const ns = ac.createBufferSource(); ns.buffer = nb;
    const hp = ac.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 2400;
    const ng = ac.createGain();
    ng.gain.setValueAtTime(0, t0);
    ng.gain.linearRampToValueAtTime(0.5, t0 + 0.015);
    ng.gain.exponentialRampToValueAtTime(0.001, t0 + 0.55);
    ns.connect(hp); hp.connect(ng); ng.connect(out);
    ns.start(t0);
    // thump: a short low sine
    const os = ac.createOscillator(); os.type = 'sine';
    os.frequency.setValueAtTime(150, t0);
    os.frequency.exponentialRampToValueAtTime(58, t0 + 0.14);
    const og = ac.createGain();
    og.gain.setValueAtTime(0.55, t0);
    og.gain.exponentialRampToValueAtTime(0.001, t0 + 0.2);
    os.connect(og); og.connect(out);
    os.start(t0); os.stop(t0 + 0.25);
    ns.stop(t0 + 0.9);
    setTimeout(() => { try { out.disconnect(); } catch (e) {} }, ((t0 - ac.currentTime) + 1.1) * 1000);
  };

  return kit;
}
