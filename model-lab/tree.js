// GRIM WORLD: the trees, rebuilt from the ground up.
//
// The old starter tree was a lofted pole with three colored balls on it and a
// flat poker-chip stump. What a real broadleaf has, in the order a player
// reads it:
//
//   1. A TRUNK THAT WIDENS AT THE GROUND. Not buttress roots reaching out as
//      separate limbs (that read as four planks stuck on a pole - cut after
//      one round of trying to fix it and left alone), just the trunk's own
//      loft flaring wider at its base, same as every tree in this file
//      always had underneath the roots.
//   2. VISIBLE STRUCTURE. Limbs leave the trunk as wood you can see, and the
//      foliage sits in asymmetric clumps AT THE ENDS of those limbs. Oaks
//      branch LOW and wide; young broadleaves keep a leader and branch high.
//   3. THE BREAK. When it is felled it must read as ONE trunk splitting: a
//      plain cut face with painted growth rings on the stump, matched on the
//      fallen trunk's butt, hinged AT the break line, not at the ground. No
//      "shattered wood" shard geometry - a felled trunk's cut face is flat,
//      and the rings alone read as wood without pretending to be splintered.
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
// Zone shapes: the same rig builds every zone tree. Each KINDS row states
// the one structural fact that makes the species readable at fifty metres -
// poplar branches nearly VERTICAL from low down, a palm is a bare ringed
// stem with a frond crown, a willow hangs silvery curtains off a dome, a
// snag is dead wood with a shattered top, a conifer (pine, redwood) is
// built from soft roughened needle clumps staged in tiers on real branch
// stubs, not smooth stacked cones - a perfect cone stack reads as a row of
// party hats, not a fir tree. Zone identity comes in through o.tint
// (trunk/leaf/leaf2 from ZONE_LOOK) and o.sc scales the whole build.
//
// Species colour identity is pulled from real trees and re-skinned under
// the fictional names: oak's bark is cool furrowed gray-brown, not warm
// brown; willow foliage is silvery sage, not plain green; acacia (Windscar's
// ironbark) is near-black deeply fissured bark under a flat, wind-pruned
// umbrella crown, the way real savanna acacias grow; poplar bark stays pale
// and the crown gets a brighter aspen-shimmer highlight; pine takes the
// warm cinnamon-orange upper bark of a real Scots pine over dark blue-green
// needles. The two dead-wood species used to be literally the same model
// under a different tint and read as duplicates - bogoak is now ancient
// black bog-preserved oak, slender and skeletal, while emberbark is a
// thicker charred trunk with painted ember-glow cracks in the bark, for the
// volcanic Ember highlands. A new `redwood` kind fills the "biggest tree in
// the place" role Kevin asked for: a massive, barely-tapering cinnamon-bark
// column, taller and thicker than anything else in the table, placeable
// from the world editor's nature catalog.
//
// Every kind also builds in one of at least two SIZE VARIANTS, chosen from
// the tree's own seed (so a given position always builds the same variant
// as the zone streams in and out) rather than a caller-supplied flag. Both
// variants are bigger than the species' old base size - never smaller - and
// carry a slightly different bark/leaf shade, so a cluster of the same
// species never reads as one tree copy-pasted next to itself.
//
// Base seam fix: the planted base flare (woodDown) and the trunk above the
// break (woodUp's upper loft) are two separate lofts that are supposed to
// read as one continuous trunk at breakY. Kevin: "you can see the seam
// where the stump and tree snap. Even when the tree is still standing
// before you cut it down." Three independent defects were stacked on top
// of each other at that one ring:
//   1. RADIUS MISMATCH. The upper loft's own taper is measured from the
//      ground, so by breakY it has already narrowed past K.r - but the
//      base flare's closing ring used to hardcode a flat K.r there with no
//      taper of its own, so the two lofts met at two different radii. The
//      same flat K.r was also used for the break-face discs (stumpCap), so
//      the same step reappeared on the stump's cut face after a fell. Fixed
//      by computing one breakR (the upper loft's own taper formula, applied
//      up front) and reusing it for the base flare's closing ring AND both
//      stumpCap discs, so all four places that have to meet at the break
//      line share one number by construction.
//   2. JITTER MISMATCH. roughen() jitters every vertex by a hash of that
//      vertex's own (rounded) position plus a seed - deterministic only
//      when the position itself matches. Even after the radii matched
//      exactly, the upper loft was built in hinge-local space (offset for
//      the fell group's own transform) while the lower loft was built in
//      world space, so the shared seed hashed to two different numbers at
//      the same physical point on the trunk and the ring still came out as
//      a stitch of mismatched facets. Fixed by building the upper loft in
//      world space too - identical coordinates to the lower loft at the
//      shared ring - and only translating into hinge space afterward, once
//      roughening and bark paint are already baked in.
//   3. COINCIDENT END CAPS. loftRect auto-caps both ends of every loft with
//      a triangle fan. Two lofts butted flush against each other each grow
//      their own cap at the shared ring, landing as two coincident,
//      oppositely-facing flat discs right at the seam - a textbook z-fight.
//      Fixed by adding an opt-in caps:{start,end} parameter to loftRect
//      (grim-kit.js) and skipping the redundant cap on each side.
// All three fixes land in this one shared build() path, so every species in
// KINDS is fixed by the same change.

import {
  rngFor, mergeParts, roughen, paintByPos, logBetween, placed, loftRect
} from './grim-kit.js';

export function makeTreeKit(T, opt) {
  opt = opt || {};
  const kit = { T, mats: {} };
  const M = kit.mats;
  M.wood = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.95, metalness: 0, flatShading: true });
  M.leaf = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, metalness: 0, flatShading: true });

  // per-kind identity: sizes, bark and leaf ramps, branching habit. Sizes
  // here are already the "scaled up" numbers Kevin asked for - roughly 20
  // to 30 percent bigger than this rig originally shipped with, more for
  // the oak/evergreen tier so they end up the biggest things in the forest
  // short of the ancient elder and the new redwood.
  const KINDS = {
    tree: {   // the starter broadleaf: one leader, branches in the upper third
      h: 6.7, r: 0.36, flare: 0.74, breakY: 0.66,
      bark: [0.40, 0.33, 0.24], barkDark: [0.20, 0.16, 0.11],
      leaf: [0.28, 0.46, 0.18], leafDeep: [0.14, 0.28, 0.11], leafSun: [0.52, 0.64, 0.22],
      limbs: 3, limbY: [0.55, 0.85], limbLen: [1.32, 2.04], limbUp: [0.5, 0.85],
      clumps: 6, clumpR: [1.02, 1.5], crownR: 1.8, crownY0: 4.08
    },
    oak: {    // the great oak: squat heavy trunk, limbs leave LOW and spread wide.
              // real oak bark reads cool gray-brown, not warm - a stronger, older
              // colour than a young broadleaf's, and the biggest hardwood here.
      h: 9.9, r: 0.69, flare: 1.37, breakY: 0.94,
      bark: [0.32, 0.28, 0.23], barkDark: [0.14, 0.12, 0.10],
      leaf: [0.18, 0.32, 0.16], leafDeep: [0.09, 0.20, 0.09], leafSun: [0.38, 0.50, 0.19],
      limbs: 5, limbY: [0.32, 0.62], limbLen: [2.47, 3.9], limbUp: [0.35, 0.7],
      clumps: 9, clumpR: [1.37, 2.08], crownR: 3.12, crownY0: 5.46
    },
    // ---- zone shapes: tints come from ZONE_LOOK via o.tint ------------------
    broad: {  // generic zone broadleaf (zoak, orchard fallback): wide spreading crown
      h: 7.7, r: 0.43, flare: 0.90, breakY: 0.70,
      bark: [0.38, 0.29, 0.19], barkDark: [0.20, 0.15, 0.10],
      leaf: [0.27, 0.44, 0.19], leafDeep: [0.14, 0.27, 0.12], leafSun: [0.47, 0.60, 0.24],
      limbs: 4, limbY: [0.42, 0.68], limbLen: [1.68, 2.64], limbUp: [0.4, 0.75],
      clumps: 7, clumpR: [1.14, 1.62], crownR: 2.28, crownY0: 4.32
    },
    acacia: { // Windscar's ironbark: real acacia bark is near-black and deeply
              // fissured, and an umbrella thorn's crown is flat and wide, not
              // round - branches leave HIGH and nearly horizontal so the whole
              // canopy sits as one wind-pruned layer over a bare trunk.
      h: 6.6, r: 0.40, flare: 0.82, breakY: 0.62,
      bark: [0.16, 0.13, 0.11], barkDark: [0.07, 0.06, 0.05],
      leaf: [0.34, 0.44, 0.20], leafDeep: [0.19, 0.27, 0.13], leafSun: [0.58, 0.64, 0.28],
      limbs: 5, limbY: [0.66, 0.86], limbLen: [2.2, 3.4], limbUp: [0.06, 0.28],
      clumps: 6, clumpR: [0.7, 1.0], crownR: 2.6, crownY0: 5.6
    },
    poplar: { // fastigiate: branches nearly VERTICAL, one continuous column.
              // pale aspen-poplar bark, brighter shimmering highlight on top.
      h: 10.1, r: 0.29, flare: 0.58, breakY: 0.60,
      bark: [0.50, 0.47, 0.40], barkDark: [0.28, 0.26, 0.22],
      leaf: [0.32, 0.48, 0.20], leafDeep: [0.16, 0.30, 0.12], leafSun: [0.62, 0.72, 0.28],
      limbs: 4, limbY: [0.28, 0.55], limbLen: [0.66, 0.96], limbUp: [1.9, 2.6],
      clumps: 7, clumpR: [0.74, 1.06], crownR: 0.48, crownY0: 3.12,
      clumpYScale: 1.6, column: true
    },
    elder: {  // the ancient one: massive trunk, heavy low limbs, huge crown.
              // deep purple-brown ancient bark, mossy near-black canopy.
      h: 11.75, r: 0.84, flare: 1.69, breakY: 1.03,
      bark: [0.24, 0.17, 0.16], barkDark: [0.11, 0.08, 0.08],
      leaf: [0.19, 0.33, 0.16], leafDeep: [0.09, 0.21, 0.09], leafSun: [0.38, 0.50, 0.20],
      limbs: 6, limbY: [0.30, 0.60], limbLen: [2.75, 4.25], limbUp: [0.35, 0.7],
      clumps: 10, clumpR: [1.5, 2.25], crownR: 3.5, crownY0: 6.25
    },
    willow: { // stout trunk, up-arching scaffolds, dome with HANGING curtains.
              // real weeping willow foliage is a distinctive silvery sage
              // green, quite unlike a normal leaf ramp - that is the one
              // structural fact that makes a willow read as a willow.
      h: 7.9, r: 0.53, flare: 1.08, breakY: 0.72,
      bark: [0.35, 0.33, 0.29], barkDark: [0.17, 0.16, 0.14],
      leaf: [0.40, 0.48, 0.34], leafDeep: [0.22, 0.30, 0.20], leafSun: [0.62, 0.68, 0.46],
      limbs: 5, limbY: [0.34, 0.58], limbLen: [1.56, 2.4], limbUp: [0.8, 1.25],
      clumps: 8, clumpR: [1.08, 1.56], crownR: 2.64, crownY0: 4.08,
      drapes: 8
    },
    pine: {   // conifer: straight leader, soft roughened needle tiers shrinking
              // to a point. Real Scots pine bark runs warm cinnamon-orange
              // higher up the trunk over near-black needles - a stack of clean
              // cones reads as spikes, so the tiers are built from clustered
              // foliage on real branch stubs instead (see canopy 'conifer').
      h: 10.1, r: 0.44, flare: 0.81, breakY: 0.68,
      bark: [0.42, 0.24, 0.14], barkDark: [0.22, 0.11, 0.06],
      leaf: [0.13, 0.27, 0.22], leafDeep: [0.07, 0.17, 0.15], leafSun: [0.30, 0.46, 0.32],
      limbs: 0, clumps: 0, crownR: 2.21, crownY0: 3.25,
      canopy: 'conifer', tiers: 6, moss: 0.5, tintMix: 0.38
    },
    redwood: { // the biggest thing in the forest: massive, barely-tapering
               // cinnamon-red trunk, branch-free low down like a real coast
               // redwood, and now a genuinely FULL conifer head up top,
               // not the small tapering point the shared conifer builder
               // gives pine. A real coast redwood's own crown is actually
               // narrow and pyramidal - Kevin's ask ("way bushier, way
               // more green greenery, big bushy full head") is a
               // deliberate departure from that toward a giant-sequoia-like
               // dense, rounded crown, since that is what reads as
               // impressive at fifty metres instead of "bare at the top".
               // crownTaper/crownDenseBase/crownDenseFall/crownClumpMul/
               // crownTipMul/crownTipExtra all default to pine's old
               // numbers when unset, so pine is untouched by this.
               // Not part of any zone's harvest table yet - placeable
               // from the world editor's nature catalog for decoration.
      h: 13.5, r: 1.05, flare: 1.85, breakY: 0.95,
      bark: [0.40, 0.20, 0.14], barkDark: [0.20, 0.09, 0.06],
      leaf: [0.15, 0.36, 0.21], leafDeep: [0.08, 0.23, 0.13], leafSun: [0.36, 0.56, 0.31],
      limbs: 3, limbY: [0.66, 0.84], limbLen: [1.8, 2.6], limbUp: [0.55, 0.9],
      clumps: 0, crownR: 2.85, crownY0: 8.2,
      canopy: 'conifer', tiers: 8, taper: 0.24, moss: 0.55, tintMix: 0.30,
      crownTaper: 0.42, crownDenseBase: 9, crownDenseFall: 1,
      crownClumpMul: 1.3, crownTipMul: 2.1, crownTipExtra: 5
    },
    palm: {   // one bare ringed stem, swept, frond crown at the very top
      h: 8.4, r: 0.31, flare: 0.48, breakY: 0.60,
      bark: [0.50, 0.42, 0.29], barkDark: [0.29, 0.24, 0.16],
      leaf: [0.32, 0.52, 0.22], leafDeep: [0.15, 0.31, 0.13], leafSun: [0.54, 0.68, 0.28],
      limbs: 0, clumps: 0, crownR: 0, crownY0: 0,
      canopy: 'fronds', fronds: 11, rings: true, moss: 0, sweep: 2.2, taper: 0.30
    },
    snag: {   // "bogoak": ancient dead wood pulled black from a peat bog -
              // slender and skeletal, near-black, not brown. DEAD: shattered
              // top, crooked bare limbs, not one leaf.
      h: 6.2, r: 0.41, flare: 0.90, breakY: 0.63,
      bark: [0.13, 0.115, 0.105], barkDark: [0.055, 0.05, 0.045],
      leaf: [0, 0, 0], leafDeep: [0, 0, 0], leafSun: [0, 0, 0],
      limbs: 3, limbY: [0.35, 0.75], limbLen: [1.15, 2.19], limbUp: [0.3, 0.95],
      clumps: 0, crownR: 0, crownY0: 0,
      canopy: 'none', crooked: true, shatterTop: true, moss: 0.30
    },
    emberbark: { // the Ember highlands' dead wood: distinct from bogoak, not a
                 // recolour of it - a thicker, heavier charred trunk with
                 // painted ember-glow cracks running through the black bark
                 // (see barkPaint's K.embers pass), and less moss since it is
                 // scorched volcanic ground, not a wet bog.
      h: 6.4, r: 0.62, flare: 1.15, breakY: 0.65,
      bark: [0.10, 0.085, 0.075], barkDark: [0.045, 0.038, 0.032],
      leaf: [0, 0, 0], leafDeep: [0, 0, 0], leafSun: [0, 0, 0],
      limbs: 4, limbY: [0.30, 0.68], limbLen: [1.2, 2.1], limbUp: [0.25, 0.85],
      clumps: 0, crownR: 0, crownY0: 0,
      canopy: 'none', crooked: true, shatterTop: true, moss: 0.15, embers: true
    }
  };
  KINDS.zoak = KINDS.broad; KINDS.orchard = KINDS.broad;
  KINDS.icewood = KINDS.pine; KINDS.elderking = KINDS.elder;
  KINDS.bogoak = KINDS.snag;   // dead wood alias kept for the legacy node name
  KINDS.dead = KINDS.snag;     // the world editor's older "Dead tree" catalog entry

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
  // scales the moss down for dead wood and dry species, K.embers blends in
  // glowing crack veins for the charred emberbark trunk.
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
    let r = base[0] * ridge * (0.72 + h * 0.55) * (1 - moss);
    let g = base[1] * ridge * (0.72 + h * 0.55) * (1 - moss * 0.2) + moss * 0.10;
    let b = base[2] * ridge * (0.72 + h * 0.55) * (1 - moss);
    if (K.embers) {
      // a second, TIGHTER hash than the bark grain picks out thin veins in
      // the charred wood; where it crosses a high threshold the crack glows
      // hot ember-orange instead of char black.
      let h2 = Math.sin(Math.round(x * 540) * 61.3 + Math.round(y * 460) * 21.7 + Math.round(z * 500) * 91.1 + seed * 3.1) * 24634.2;
      h2 -= Math.floor(h2);
      const vein = h2 > 0.93 ? (h2 - 0.93) / 0.07 : 0;
      r = r * (1 - vein) + 0.95 * vein;
      g = g * (1 - vein) + 0.42 * vein;
      b = b * (1 - vein) + 0.08 * vein;
    }
    c.setRGB(r, g, b);
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

  // A plain, flat stump cap: a shallow wood disc with painted growth rings
  // radiating from the pith, fading to a dark bark-toned rim. Used for BOTH
  // exposed break faces - the stump the game reveals when a tree is felled,
  // and the matching cut face on the butt of the falling trunk. No jagged
  // "shattered wood" shard geometry: a cut face is flat, and the rings alone
  // read as a cut tree trunk instantly.
  //
  // The visible face is built as its own disc (a flattened RingGeometry) with
  // real radial subdivisions, not a cylinder's end cap. A cylinder cap is a
  // fan from one center vertex to the outer rim - only two distinct radii
  // exist in the mesh, so a concentric ring pattern painted by radius has
  // nowhere to land and collapses into a single center-to-edge gradient. That
  // read as a blank rounded dome, not a cut trunk, on the first pass. A few
  // real radial rings, painted a bit boldly, gives the low-poly style actual
  // concentric bands instead of a smooth blend.
  const stumpCap = (K, rnd, upward, ringR) => {
    // ringR is the ACTUAL wood radius at the break line (see breakR in
    // kit.build below) - it can be narrower than K.r once the upper trunk's
    // own taper is applied. Falls back to K.r for any future caller that
    // does not pass one.
    const R = (ringR === undefined ? K.r : ringR) * 0.97;
    const h = Math.max(0.05, K.r * 0.12);
    const ringPhase = rnd() * 6.28;
    const paint = (c, x, y, z) => {
      const rr = Math.min(1.05, Math.hypot(x, z) / R);
      const band = 0.5 + 0.5 * Math.sin(rr * 10 - ringPhase);
      const pith = Math.max(0, 1 - rr * 1.6);
      const pale = [0.70, 0.55, 0.32], dark = [0.24, 0.16, 0.09];
      let r0 = dark[0] + (pale[0] - dark[0]) * band + pith * 0.13;
      let g0 = dark[1] + (pale[1] - dark[1]) * band + pith * 0.09;
      let b0 = dark[2] + (pale[2] - dark[2]) * band + pith * 0.03;
      const edge = Math.max(0, (rr - 0.82) / 0.18);
      r0 = r0 * (1 - edge) + K.bark[0] * 0.8 * edge;
      g0 = g0 * (1 - edge) + K.bark[1] * 0.8 * edge;
      b0 = b0 * (1 - edge) + K.bark[2] * 0.8 * edge;
      c.setRGB(r0, g0, b0);
    };
    // the flat top: nine concentric rings of vertices, so the sine bands
    // above draw as real steps of colour instead of one gradient. Roughen is
    // light and applied before the colour pass would otherwise blur it - too
    // much radial jitter here smears adjacent rings into each other.
    const face = new T.RingGeometry(R * 0.03, R, 16, 9);
    face.rotateX(-Math.PI / 2);
    face.translate(0, h * 0.5, 0);
    roughen(T, face, 0.018, Math.floor(rnd() * 900) + 1, 0.3);
    paintByPos(T, face, paint);
    // a short open rim wall so the disc still reads as solid wood from a low
    // angle, not a sheet floating on the trunk
    const rim = new T.CylinderGeometry(R, R * 1.015, h, 16, 1, true);
    roughen(T, rim, 0.03, Math.floor(rnd() * 900) + 2, 1);
    paintByPos(T, rim, paint);
    return [
      placed(T, face, 0, upward ? h * 0.5 : -h * 0.5, 0, 0, 0, 0, 1),
      placed(T, rim, 0, upward ? h * 0.5 : -h * 0.5, 0, 0, 0, 0, 1)
    ];
  };

  // o: { kind, seed, x, y, z, sc, tint: {trunk,leaf,leaf2}, merged }
  // merged: one mesh for wood + leaves (zone streaming - draw calls matter
  // more than a sway split the zone registration never uses).
  kit.build = function (o) {
    o = o || {};
    let K = KINDS[o.kind || 'tree'] || KINDS.broad;

    // ---- size variant: at least two sizes per species so a cluster of the
    // same kind never reads as one tree copy-pasted next to itself. Keyed
    // off the seed rather than a fresh random roll, so the SAME position
    // always builds the SAME variant as the zone streams in and out. Always
    // bigger than the species' base size, never smaller, with a slightly
    // different shade so the two variants read as two trees even standing
    // side by side.
    const vr = rngFor((o.seed || 3) * 131 + 977);
    const vRoll = vr();
    const isBig = vRoll > 0.62;
    const variantScale = isBig ? (1.18 + vr() * 0.16) : 1.0;
    const shadeT = isBig ? (0.87 + vr() * 0.09) : (1.0 + vr() * 0.10);

    K = tinted(scaled(K, (o.sc || 1) * variantScale), o.tint);
    K = Object.assign({}, K);
    ['bark', 'barkDark', 'leaf', 'leafDeep', 'leafSun'].forEach(f => {
      K[f] = K[f].map(v => Math.min(1, v * shadeT));
    });

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

    // ---- trunk: base flare to tip, split at the break line ------------------
    const lean = (rnd() - 0.5) * 0.16 * (K.sweep || 1) + (K.sweep ? (rnd() > 0.5 ? 0.08 : -0.08) * K.sweep : 0);
    const line = (t) => ({ x: lean * t * t * 2.4, y: t });   // gentle sweep
    // The upper trunk's taper (below) is measured from the GROUND, not from
    // the break, so by the time its loft reaches the break line it has
    // already narrowed past K.r. The base flare used to close its own top
    // ring at a flat K.r with no such taper applied, so the two lofts met at
    // two different radii - a visible step ringing every trunk right where
    // the base flare meets the trunk above it, at the base of the tree
    // (breakY sits low, well under a fifth of the way up). The same step
    // showed up on the stump's cut face after a fell, for the same reason.
    // One shared radius for that one ring, reused by both lofts AND both
    // stumpCap discs below, removes it for every species built from this
    // rig, since they all share this exact code path.
    const upperTaperAmt = K.taper === undefined ? 0.72 : K.taper;
    const breakR = K.r * (1 - (K.breakY / K.h) * upperTaperAmt);
    const trunkSecs = [];
    const steps = [[0, K.flare * 0.82, 2.0], [0.04, K.r * 1.30, 2.5], [0.10, K.r * 1.06, 2.6]];
    for (const [tt, rr, p] of steps) {
      const y = tt * K.h;
      if (y > K.breakY) break;
      trunkSecs.push({ at: y, hu: rr, hv: rr, cu: line(y / K.h).x, p });
    }
    // lower trunk (planted): flare up to the break. This loft is the ENTIRE
    // base - no separate buttress-root lobes glued on. A first pass tried
    // those and they read as four little planks stuck on a pole no matter
    // how they were angled; the loft's own flare is the tree's base. The
    // closing ring uses breakR (not K.r) so it meets the upper loft's first
    // ring at an identical radius - see the comment above. end:false skips
    // this loft's own top cap: the upper loft's matching bottom ring sits
    // flush against it, so a cap here would be a second, exactly coincident
    // disc and z-fight with the one below.
    const lower = loftRect(T, 'y', trunkSecs.concat([{ at: K.breakY, hu: breakR, hv: breakR, cu: line(K.breakY / K.h).x, p: 2.6 }]), 9,
      barkPaint(K, seed), { end: false });
    roughen(T, lower, 0.085, seed + 2, 1);   // same seed as the upper loft
    woodDown.push({ geo: lower });

    // upper trunk (falls): break line to tip. Built in WORLD coordinates
    // here, NOT hinge space like the rest of woodUp - that puts its first
    // ring at the exact same (x,y,z) as the base flare's closing ring right
    // above, so roughen() (same seed, hashed off vertex position) jitters
    // every matching vertex around that ring identically instead of just
    // landing on the same average radius. Built in hinge space, the two
    // rings shared a radius after the breakR fix above but still landed on
    // slightly different jitter per vertex - close, but a small stitch of
    // mismatched facets remained right at the seam. Translated into hinge
    // space, the same place IN() would have put it, only once roughen and
    // the bark paint are already baked in below.
    const upperSecs = [];
    const tipY = K.h * (0.86 + rnd() * 0.1);
    const nSec = 5;
    for (let i = 0; i <= nSec; i++) {
      const y = K.breakY + (tipY - K.breakY) * (i / nSec);
      const t = y / K.h;
      const rr = K.r * (1 - t * upperTaperAmt);
      upperSecs.push({ at: y, hu: Math.max(0.05, rr), hv: Math.max(0.05, rr), cu: line(t).x, p: 2.6 });
    }
    // start:false skips this loft's own bottom cap for the same reason the
    // base flare above skips its top one - the two rings sit flush and a
    // cap on both sides is a coincident, z-fighting pair of discs.
    const upper = loftRect(T, 'y', upperSecs, 9, barkPaint(K, seed), { start: false });
    // a snag's top is TORN, not sawn: a jagged ring of upward shards. This is
    // the dead tree's permanent, naturally-broken silhouette (what a snag
    // IS), a different thing from the fell mechanic's break faces below.
    if (K.shatterTop) {
      const topR = K.r * (1 - (K.taper === undefined ? 0.72 : K.taper) * (tipY / K.h));
      for (let i = 0; i < 5; i++) {
        const a = (i / 5) * Math.PI * 2 + rnd() * 0.4;
        const hgt = 0.22 + rnd() * 0.34;
        const shard = new T.ConeGeometry(0.06 + rnd() * 0.05, hgt, 4);
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
    roughen(T, upper, 0.085, seed + 2, 1);   // matches the lower loft at the break ring, vertex for vertex now that both build it in the same coordinate frame
    upper.translate(-hingeX, -K.breakY, 0);   // now into hinge space, where the fell group's own transform expects it
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
      // willow: curtains hang off the crown, almost to the ground. Each one
      // springs from an actual foliage clump's position (picked from
      // clumpAt, the same list just rendered above) rather than an
      // independent random point out near the crown radius - the old way,
      // a drape's own random radius/height rarely landed inside any real
      // clump's volume, so several curtains every build hung visibly in
      // empty air with nothing holding them up. A thin drooping branch
      // stub (buried into the source clump, same trick the limb-end
      // clusters use) connects clump to curtain, which also reads more
      // correctly - a willow's curtains are drooping BRANCHES, not leaves
      // floating free.
      if (K.drapes && clumpAt.length) {
        for (let i = 0; i < K.drapes; i++) {
          const src = clumpAt[Math.floor(rnd() * clumpAt.length)];
          const [scx, scy, scz, scs] = src;
          const srcR = (K.clumpR[0] + (K.clumpR[1] - K.clumpR[0]) * 0.5) * scs;
          // small lateral jitter so several drapes off the same clump do
          // not all hang dead center on top of each other
          const jx = (rnd() - 0.5) * srcR * 1.3, jz = (rnd() - 0.5) * srcR * 1.3;
          const tipX = scx + jx, tipZ = scz + jz;
          const topY = scy - srcR * 0.1;
          const dropLen = 0.9 + rnd() * 1.1;
          const stub = logBetween(T,
            new T.Vector3(...IN(scx, scy - srcR * 0.25, scz)),
            new T.Vector3(...IN(tipX, topY, tipZ)),
            Math.max(0.02, K.r * 0.10), Math.max(0.012, K.r * 0.04),
            { rough: 0.16, seed: i * 23 + seed + 5, segments: 4 });
          paintByPos(T, stub.geo, (c, x, y, z) => barkPaint(K, seed)(c, x + hingeX, y + K.breakY, z));
          woodUp.push(stub);
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
          // top of the drape overlaps up into where the stub ends, so
          // there is no seam even before the stub geometry is accounted for
          leafParts.push(placed(T, geo,
            ...IN(tipX, topY - dropLen * 0.42, tipZ),
            0, rnd() * 3, 0, 1));
        }
      }
    } else if (style === 'conifer') {
      // conifer: soft branch TIERS built from clustered, roughened foliage on
      // real branch stubs, not smooth stacked cones - a stack of perfect
      // cones reads as a stack of party hats. Each tier is narrower than the
      // one below it, so the silhouette still tapers to a point, but the
      // surface reads as needle clumps instead of sheet metal.
      // taper/density are parameterized per species so redwood can carry a
      // full, bushy head without changing pine (which keeps the old
      // defaults exactly: 0.80 taper, a 7-to-4 clump falloff, a small tip
      // cap). Redwood overrides all four to stop the top tiers from
      // shrinking to almost nothing, which read as "bare at the top".
      const nT = K.tiers || 6;
      const topY = tipY + 0.3;
      const span = topY - K.crownY0;
      const taperAmt = K.crownTaper === undefined ? 0.80 : K.crownTaper;
      const denseBase = K.crownDenseBase === undefined ? 7 : K.crownDenseBase;
      const denseFall = K.crownDenseFall === undefined ? 3 : K.crownDenseFall;
      const clumpMul = K.crownClumpMul || 1;
      for (let i = 0; i < nT; i++) {
        const u = i / (nT - 1);
        const cy = K.crownY0 + span * u;
        const cx0 = line(cy / K.h).x;
        const tierR = K.crownR * (1 - u * taperAmt) * (0.92 + rnd() * 0.14);
        const nClump = Math.max(4, Math.round(denseBase - u * denseFall));
        for (let cc = 0; cc < nClump; cc++) {
          const a = (cc / nClump) * Math.PI * 2 + rnd() * 0.4 + u * 2.3;
          const rr = tierR * (0.68 + rnd() * 0.3);
          const bx = cx0 + Math.sin(a) * rr, bz = Math.cos(a) * rr;
          const by = cy - rnd() * 0.16;
          // a real branch stub reaching from the leader out to the clump
          const stub = logBetween(T, new T.Vector3(...IN(cx0, cy, 0)), new T.Vector3(...IN(bx, by - 0.04, bz)),
            Math.max(0.02, K.r * 0.16 * (1 - u * 0.4)), Math.max(0.012, K.r * 0.05), { rough: 0.14, seed: i * 19 + cc * 7 + seed, segments: 4 });
          paintByPos(T, stub.geo, (c, x, y, z) => barkPaint(K, seed)(c, x + hingeX, y + K.breakY, z));
          woodUp.push(stub);
          const br = tierR * (0.34 + rnd() * 0.16) * clumpMul;
          const geo = roughen(T, new T.IcosahedronGeometry(br, 1), 0.42, (i * 13 + cc * 5 + 1) * 31 + seed, 0.6);
          geo.scale(1, 0.60 + rnd() * 0.12, 1);
          paintByPos(T, geo, (c, x, y, z) => leafPaint(K, cy - 0.35, br * 1.5)(c, x, y, z));
          leafParts.push(placed(T, geo, ...IN(bx, by, bz), rnd() * 3, rnd() * 3, rnd() * 3, 1));
        }
      }
      // the crown tip: one clump closes off the leader instead of a bare
      // point - crownTipMul lets redwood end on a real full head instead of
      // the small default cap.
      {
        const tipYY = topY - 0.05;
        const tipMul = K.crownTipMul || 1;
        const geo = roughen(T, new T.IcosahedronGeometry(K.crownR * 0.22 * tipMul, 1), 0.4, seed + 91, 0.6);
        paintByPos(T, geo, (c, x, y, z) => leafPaint(K, tipYY - 0.2, K.crownR * 0.3)(c, x, y, z));
        leafParts.push(placed(T, geo, ...IN(line(tipYY / K.h).x, tipYY, 0), rnd() * 3, rnd() * 3, rnd() * 3, 1));
        // redwood only: a couple of extra sub-clumps clustered right around
        // the tip cap, so the top reads as one full mass of foliage instead
        // of a single ball balanced on the leader
        if (K.crownTipExtra) {
          for (let e = 0; e < K.crownTipExtra; e++) {
            const ea = rnd() * Math.PI * 2, er = K.crownR * (0.22 + rnd() * 0.28) * tipMul;
            const ey = tipYY - 0.15 - rnd() * 0.5;
            const ebr = K.crownR * (0.16 + rnd() * 0.1) * tipMul;
            const egeo = roughen(T, new T.IcosahedronGeometry(ebr, 1), 0.42, (e + 1) * 47 + seed + 91, 0.6);
            paintByPos(T, egeo, (c, x, y, z) => leafPaint(K, ey - 0.3, ebr * 1.5)(c, x, y, z));
            leafParts.push(placed(T, egeo,
              ...IN(line(ey / K.h).x + Math.sin(ea) * er, ey, Math.cos(ea) * er),
              rnd() * 3, rnd() * 3, rnd() * 3, 1));
          }
        }
      }
    } else if (style === 'fronds') {
      // palm crown: a fan of drooping blades from the very tip, nuts beneath.
      // Frond length was hardcoded here rather than scaled off the trunk, so
      // a bumped-up palm kept the old rig's crown on a taller pole and a big
      // size variant looked balding. frScale ties the crown back to K.r,
      // against the species' own base radius.
      const frScale = K.r / 0.26;
      const nF = K.fronds || 10;
      const crownY = tipY;
      const crownX = line(tipY / K.h).x;
      // the fibrous husk where the fronds sheath the stem - also plugs the
      // dark hole the blade roots leave when seen from below
      {
        const husk = roughen(T, new T.IcosahedronGeometry(0.30 * frScale, 1), 0.2, seed + 77, 1);
        husk.scale(1, 0.8, 1);
        paintByPos(T, husk, (c) => c.setRGB(K.bark[0] * 0.9, K.bark[1] * 0.85, K.bark[2] * 0.8));
        woodUp.push(placed(T, husk, ...IN(crownX, crownY + 0.05, 0), 0, 0, 0, 1));
      }
      for (let i = 0; i < nF + 6; i++) {
        const young = i % 5 === 0;
        const a = (i / nF) * Math.PI * 2 + rnd() * 0.35;
        const len = ((young ? 1.6 : 2.3) + rnd() * 0.6) * frScale;
        // tilt is the blade's ELEVATION above horizontal (rotX(PI/2 - tilt)).
        // A near-horizontal blade points its broad face almost straight UP
        // and DOWN in world space, and from anywhere near ground level a
        // player mostly sees its underside - which gets next to no direct
        // light from either the sun or the sky hemisphere, so the whole
        // crown read as a flat black star no matter how bright its paint
        // was. Working fronds now droop at a real angle instead of staying
        // near flat, the way a real mature frond actually hangs: the broad
        // face turns to catch light from the side rather than presenting a
        // shadowed floor to the camera. Only the young center blades stand up.
        const tilt = young ? 1.05 + rnd() * 0.3 : -0.95 + rnd() * 0.45;
        const geo = new T.ConeGeometry(0.42 * frScale, len, 4);
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
          // taller palms now get looked at from further below than this
          // rig was first tuned for, which put MOST of a drooping frond's
          // visible area into that unlit case rather than a rare grazing
          // edge - the -0.15 cutoff and a 2.3x ceiling were not enough
          // headroom, and a whole crown went black. Wider catch, harder
          // push: anything at or below level gets brightened, ramping up
          // fast as the face points further down.
          if (nn && cc) for (let vi = 0; vi < nn.count; vi++) {
            v.set(nn.getX(vi), nn.getY(vi), nn.getZ(vi)).applyMatrix3(nm3);
            if (v.y < 0.08) {
              const k2 = 1 + Math.min(2.8, (0.08 - v.y) * 3.1);
              cc.setXYZ(vi, Math.min(1, cc.getX(vi) * k2), Math.min(1, cc.getY(vi) * k2), Math.min(1, cc.getZ(vi) * k2));
            }
          }
          leafParts.push({ geo: g2, matrix: m });
        }
      }
      // coconuts tucked under the crown
      for (let i = 0; i < 3; i++) {
        const a = rnd() * Math.PI * 2;
        const nut = new T.IcosahedronGeometry(0.13 * frScale, 0);
        paintByPos(T, nut, (c) => c.setRGB(0.30, 0.22, 0.12));
        woodUp.push(placed(T, nut,
          ...IN(crownX + Math.sin(a) * 0.24 * frScale, crownY - 0.16 * frScale, Math.cos(a) * 0.24 * frScale), 0, 0, 0, 1));
      }
    }
    // style 'none' (snags): not one leaf

    // ---- the break faces ----------------------------------------------------
    // trunk butt: a flat, ring-painted cut face, back toward the stump, in
    // hinge space. Both halves of the same break get the SAME rng seed, so
    // the rings drawn on the stump and on the fallen trunk's butt line up as
    // if they were always one cut.
    for (const p of stumpCap(K, rngFor(seed * 3 + 5), false, breakR)) {
      p.matrix = new T.Matrix4().makeTranslation(-hingeX + line(K.breakY / K.h).x, 0.006, 0).multiply(p.matrix);
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

    // ---- the planted base: trunk flare, ALWAYS visible ---------------------
    // It is the bottom of the living tree and, once the top breaks off, it IS
    // the stump body. Nothing about it changes at the fell.
    const baseMesh = new T.Mesh(mergeParts(T, woodDown), M.wood);
    baseMesh.castShadow = true; g.add(baseMesh);

    // ---- the stump crown: the game's toggled stump group -------------------
    // The plain, ring-painted cut face lives here, hidden while the tree
    // stands (the upper trunk loft covers the same footprint) and revealed
    // at the exact moment the trunk breaks off. resourceRespawned hides it
    // again.
    const stumpG = new T.Group();
    stumpG.visible = false;
    g.add(stumpG);
    const crownParts = [];
    for (const p of stumpCap(K, rngFor(seed * 3 + 5), true, breakR)) {
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
