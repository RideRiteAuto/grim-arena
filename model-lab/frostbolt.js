// GRIM WORLD: the frost bolt, and the ice block it leaves at your feet.
//
// The frost bolt used to be the same flat-shaded icosahedron the fireball
// started as: one solid pale-blue lump with a point light taped to it. Fire
// already got rebuilt out of the campfire's flame shader (see fireball.js);
// this gives frost the same treatment, but ice is not fire with the palette
// swapped. Two structural facts a recolour would miss:
//
//   1. Fire is a soft, trailing plume - the tongues rake BACKWARD along
//      -velocity because flame has no mass of its own, it is combustion
//      dragging in the bolt's wake. Ice is a rigid, hurled solid. A thrown
//      shard leads with its point: this cluster rakes FORWARD along
//      +velocity instead, tips first, like a thrown dagger, not a comet.
//   2. Fire visibly writhes - flameMat's lick/sway terms exist because real
//      flame never holds still. A crystal does not lick or sway; it is
//      rigid. Reusing flameMat here (see the material note below) but with
//      lick and sway both driven near zero keeps the geometry still and
//      lets only a faint surface shimmer read as "catching the light",
//      which is the crystalline equivalent of fire's motion.
//
// One module, two consumers, same as every other asset here: the lab page
// imports it directly and the bundle patch inlines the same source, so the
// thing reviewed on the turntable is the thing that ships.
//
// MATERIAL REUSE, ON PURPOSE. flameMat (grim-kit.js) is not fire-specific in
// its machinery - it is a layered, edge-lit, faintly-noised additive
// material driven by four per-vertex attributes (aSeed/aNorm/aBase/aAxis)
// that any tongueGeo-shaped cluster can use. Tuned cold (a white-to-blue
// ramp instead of white-to-red), with erosion low instead of tearing and
// lick/sway low instead of writhing, the exact same shader reads as frosted
// crystal rather than flame. Writing a second bespoke shader for a look this
// close to what flameMat already does well would be maintaining two things
// that drift; tuning the one that exists is the actual fix. The noise that
// makes fire look torn instead reads, at low erosion, as a faint frosted
// crackle across the shard's surface - a genuinely different, fitting
// texture, not a compromise.
//
// The ice block (makeIceBlockKit) is a separate, ground-level effect: a
// jagged low-poly chunk that grows up out of the earth at a frozen target's
// feet, with its own frost-mist burst and a ground glow draped under it.
// It is built from the same shared vocabulary (roughen for the jagged
// facets, driftField/driftMat for the mist, glowMat/drapedDisc for the
// ground pool) rather than anything bespoke, for the same reason as above.
//
// Everything animated is done on the GPU off a single uTime uniform, exactly
// like the campfire and the fireball, so any number of frost bolts and ice
// blocks in the world at once costs one uniform write per material per
// frame, not per instance.

/* eslint-disable no-unused-vars */

import {
  rngFor, mergeParts, tongueParts, flameMat, driftMat, driftField,
  placed, roughen, glowMat, drapedDisc
} from './grim-kit.js';

// Materials are created once and shared by every frost bolt in the world -
// the player's own casts and every spellcasting NPC's - so animating them
// costs three uniform writes a frame no matter how many are in flight.
export function makeFrostboltKit(T, opt) {
  opt = opt || {};
  const kit = { T, mats: {}, _t: 0 };

  // Outer shards: the silhouette. erode stays low (0.20) so the surface
  // reads as a faint frosted crackle rather than fire's torn edge; lick and
  // sway both sit near zero so the cluster holds rigid instead of writhing;
  // rate is slow (0.55) because the little motion left - the fresnel glint
  // as a facet catches the light - should drift, not flicker.
  kit.mats.outer = flameMat(T, {
    c0: 0xf2ffff, c1: 0x9fd8ff, c2: 0x2f6fb3,
    alpha: 0.62, erode: 0.20, sway: 0.14, lick: 0.10, rate: 0.55
  });
  // Core: near-white where the bolt is thickest, essentially solid (erode
  // 0.09) so the middle always reads as a dense frozen mass while the outer
  // shards carry the faint crackle texture - the same "solid middle, torn
  // edge" split the fireball's core/outer pair uses, just with ice's much
  // lower erosion throughout.
  kit.mats.core = flameMat(T, {
    c0: 0xffffff, c1: 0xe8f9ff, c2: 0xbfe6ff,
    alpha: 0.82, erode: 0.09, sway: 0.06, lick: 0.05, rate: 0.45
  });
  // Frost mist: unlike embers, which are hot gas rising and cooling, this is
  // fine ice dust shed off a fast-moving cold object - it barely rises
  // (0.10 against the ember's 0.34), sits smaller, and fades white toward a
  // pale cold blue instead of warming-then-dying to a coal colour. flick is
  // low: embers glow and gutter, ice dust just drifts and dims.
  kit.mats.mist = driftMat(T, {
    rise: 0.10, size: 0.044, grow: 0.62, wander: 0.09, spread: 0.13, ease: 0.38,
    lean: -0.10, col: 0xf5ffff, col2: 0x6fb0e0, alpha: 0.85, rate: 1.7,
    hold: 0.20, flick: 0.12, additive: true
  });

  // One call a frame for the WHOLE WORLD's frost bolts, same shape as
  // fireballKit().tick. Lazily created, so a match where nobody ever casts
  // frost never pays for it.
  kit.tick = function (seconds) {
    kit.mats.outer.userData.U.uTime.value = seconds;
    kit.mats.core.userData.U.uTime.value = seconds;
    kit.mats.mist.userData.U.uTime.value = seconds;
  };

  // Build one bolt. Returns { g, radius }. Every instance shares the three
  // materials above; only the geometry is per-instance, and even that is a
  // single merged mesh per layer, so one bolt is three draw calls (outer,
  // core, mist) however many shards it is built from - identical budget to
  // the fireball.
  kit.build = function (o) {
    o = o || {};
    const rnd = rngFor(o.seed === undefined ? Math.floor(Math.random() * 1e6) : o.seed);
    const g = new T.Group();

    // Five shards around a tight radius, uneven headings and uneven reach -
    // the same "evenly spaced reads as a starburst" trap the fireball and
    // the failure catalogue both call out. p MUST be well below flameMat's
    // own flame value (0.55), not above it: p drags the widest point toward
    // the BASE, and a flame tongue already does this a little to get a
    // rounded teardrop. The first pass here used p 0.72 - HIGHER than
    // flame's own 0.55 - which drags the belly back toward the MIDDLE
    // instead, and on the turntable it rendered as a round lumpy blob with
    // no visible point at all, not a shard. p 0.36 pushes the full width to
    // within the first few percent of the shard's length and holds a long,
    // near-linear taper the rest of the way to a sharp tip - the actual
    // difference between "flame licking" and "ice spiking". Six radial
    // segments (down from nine) reads as faceted crystal rather than a
    // smooth round tube. tx/tz stay small - ice shards are straight, they do
    // not flare like licking flame does.
    const outerList = [];
    const n = 5;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + rnd() * 0.8;
      const rim = rnd();
      const r = 0.012 + rim * 0.016;
      outerList.push({
        R: 0.020 + (1 - rim) * 0.012 + rnd() * 0.008,
        H: 0.18 + rim * 0.13 + rnd() * 0.08,
        x: Math.sin(a) * r, z: Math.cos(a) * r, y: 0,
        tx: -Math.cos(a) * (0.02 + rim * 0.03),
        tz: Math.sin(a) * (0.02 + rim * 0.03),
        seed: rnd() * 6.283, p: 0.36, q: 1.10
      });
    }
    const outer = new T.Mesh(mergeParts(T, tongueParts(T, outerList, 6, 9)), kit.mats.outer);
    outer.renderOrder = 3;
    g.add(outer);

    // One longer, straighter spike down the centre - the leading point of
    // the whole cluster, and the thing "orientAlong" actually points
    // forward. Even lower p (0.28) than the outer shards so this one reads
    // as the sharpest, straightest point in the cluster, the way a thrown
    // dagger's own point is finer than the guard around it.
    const core = new T.Mesh(mergeParts(T, tongueParts(T, [{
      R: 0.028, H: 0.27, x: 0, z: 0, y: -0.01, seed: rnd() * 6.283, p: 0.28, q: 1.15
    }], 6, 9)), kit.mats.core);
    core.renderOrder = 4;
    g.add(core);

    // Mist. Tight spread, riding the group's own transform so it trails
    // with the bolt for free.
    const mist = new T.Mesh(driftField(T, 10, 0.050, 0.01, rnd), kit.mats.mist);
    mist.renderOrder = 5;
    mist.visible = opt.mist !== false;
    g.add(mist);

    return { g, radius: 0.14, mistMesh: mist };
  };

  // Point the whole cluster so its shards lead FORWARD along +dir, tips
  // first - the opposite of the fireball's orientAlong, and the whole point
  // of building ice as a separate kit rather than a fireball recolour. Call
  // once, at cast time; the bolt flies a straight line.
  kit.orientAlong = function (g, dir) {
    if (dir.lengthSq() < 1e-8) return;
    const fwd = dir.clone().normalize();
    g.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), fwd);
  };

  return kit;
}

// The ice block that grows at a frozen target's feet. A separate kit, not a
// mode of the bolt above: it is ground-level, one-shot, and driven by the
// game's existing fx-lifecycle system (fx kind 'iceblock' in stepFx) rather
// than flying under its own velocity.
export function makeIceBlockKit(T, opt) {
  opt = opt || {};
  const kit = { T, mats: {} };

  // The block's own faint inner glow, same shader family as the bolt for a
  // consistent "this is the same magic" read, tuned even stiller (erode
  // 0.14, lick/sway effectively off) since a block sitting on the ground has
  // no reason to shimmer as much as a shard cutting through the air.
  kit.mats.glow = flameMat(T, {
    c0: 0xf5ffff, c1: 0xaee0ff, c2: 0x3f7fc0,
    alpha: 0.55, erode: 0.14, sway: 0.05, lick: 0.04, rate: 0.35
  });
  // The solid-reading shell: a real three.js material (not the additive
  // shader above) so the block also catches the scene's own light and casts
  // a believable silhouette instead of being pure glow. Low roughness for a
  // wet-ice specular highlight; transparent+thin so the additive glow
  // material nested just inside it still reads through.
  // A flat emissive floor is mixed in on top of whatever the scene's own
  // lighting contributes - the first pass left this out and the block
  // picked up the ground's own colour under ambient bounce (it rendered
  // grey-green over grass instead of blue), because a 0.55-opacity dialback
  // material with no emissive of its own is mostly showing what is behind
  // and around it, not its own colour.
  kit.mats.shell = new T.MeshPhysicalMaterial({
    color: 0x8ecdff, roughness: 0.12, metalness: 0, transparent: true,
    opacity: 0.58, side: T.DoubleSide, depthWrite: false,
    emissive: 0x1c4a72, emissiveIntensity: 0.4
  });
  // A burst of frost dust at the moment the block appears - reuses the
  // bolt's exact mist recipe (same driftMat shape) so the two effects read
  // as one continuous piece of magic rather than two unrelated systems.
  kit.mats.mist = driftMat(T, {
    rise: 0.16, size: 0.05, grow: 0.7, wander: 0.11, spread: 0.20, ease: 0.42,
    lean: 0, col: 0xffffff, col2: 0x7fb8e8, alpha: 0.8, rate: 1.4,
    hold: 0.16, flick: 0.1, additive: true
  });
  // Ground pool: glowMat's own default palette is fire-coloured, so this
  // passes an icy stop list instead - same radial-gradient recipe as the
  // campfire's ground glow, different four colours.
  kit.mats.pool = glowMat(T, [
    [0.00, 'rgba(230,250,255,0.85)'],
    [0.25, 'rgba(170,220,255,0.55)'],
    [0.55, 'rgba(120,190,255,0.22)'],
    [1.00, 'rgba(100,170,255,0.00)']
  ]);

  kit.tick = function (seconds) {
    kit.mats.glow.userData.U.uTime.value = seconds;
    kit.mats.mist.userData.U.uTime.value = seconds;
  };

  // Build one block. Returns { g, radius, mist }. heightAt is the same
  // groundY-style callback the rest of the world drapes ground props with;
  // pass null on flat ground (the lab, the arena) and the pool sits flat.
  kit.build = function (o) {
    o = o || {};
    const rnd = rngFor(o.seed === undefined ? Math.floor(Math.random() * 1e6) : o.seed);
    const g = new T.Group();

    // Three overlapping, independently roughened low-poly chunks read as one
    // jagged mass far better than one roughened icosahedron alone does - a
    // single blob roughened this hard just looks like a crumpled ball, the
    // same "one shape rotated" trap the tongue clusters avoid by being
    // several uneven pieces instead of one.
    const parts = [];
    // Squat on purpose: this clamps around a target's feet and lower legs,
    // not a spire over their head. The first pass centred its biggest chunk
    // at y 0.30 with radius up to 0.34 (before roughen's own expansion),
    // which on the turntable read as a stalagmite taller than it was wide.
    // Lower centres and a smaller top radius keep the whole cluster under
    // about half a metre.
    const chunks = [
      { r: 0.27, x: 0, z: 0, y: 0.20 },
      { r: 0.18, x: 0.15, z: 0.09, y: 0.13 },
      { r: 0.15, x: -0.13, z: 0.08, y: 0.11 }
    ];
    for (const c of chunks) {
      const geo = new T.IcosahedronGeometry(c.r, 1);
      roughen(T, geo, 0.55, rnd() * 999, 1);
      parts.push(placed(T, geo, c.x, c.y, c.z, rnd() * 3.14, rnd() * 3.14, rnd() * 3.14, 1));
    }
    const shell = new T.Mesh(mergeParts(T, parts), kit.mats.shell);
    shell.renderOrder = 4;
    g.add(shell);

    // A smaller, tighter copy of the same chunks, nested just inside the
    // shell, carrying the glow shader - the block's own light source, same
    // "shrunk duplicate as an inner core" trick the fireball uses.
    const innerParts = chunks.map(c => {
      const geo = new T.IcosahedronGeometry(c.r * 0.72, 1);
      roughen(T, geo, 0.55, rnd() * 999 + 50, 1);
      return placed(T, geo, c.x, c.y, c.z, rnd() * 3.14, rnd() * 3.14, rnd() * 3.14, 1);
    });
    const glow = new T.Mesh(mergeParts(T, innerParts), kit.mats.glow);
    glow.renderOrder = 3;
    g.add(glow);

    const mist = new T.Mesh(driftField(T, 14, 0.32, 0.08, rnd), kit.mats.mist);
    mist.renderOrder = 5;
    g.add(mist);

    const heightAt = o.heightAt || null;
    const pool = new T.Mesh(drapedDisc(T, 0.85, 24, 0, 0, heightAt, 0.02), kit.mats.pool);
    pool.rotation.x = 0; // drapedDisc already lies flat on the XZ plane
    pool.renderOrder = 2;
    g.add(pool);

    return { g, radius: 0.5, mist, pool };
  };

  return kit;
}
