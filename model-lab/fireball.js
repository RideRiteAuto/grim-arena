// GRIM WORLD: the fire bolt.
//
// The fireball spell used to be a flat-shaded icosahedron: one solid-colour
// lump with a point light taped to it. It read as a thrown ball, not as fire.
// This rebuilds it out of the same flame material the campfire uses, cut down
// to something that reads at a glance while it is only on screen a second or
// two: a short cluster of tongues raked backward along the direction of
// travel, like a comet, plus a handful of embers riding along with it.
//
// One module, two consumers, same as every other asset here: the lab page
// imports it directly and the bundle patch inlines the same source, so the
// thing reviewed on the turntable is the thing that ships.
//
// What a THROWN fire effect needs, in the order a player notices it, and how
// this differs from a fire that is sitting still:
//
//   1. It has to read as fire in flight, not just at rest. A campfire's tongues
//      stand upright because the fire is anchored to its fuel. A fire bolt has
//      no fuel under it, so the tongues are raked backward along -velocity
//      instead of standing on end - that reading is what makes a moving light
//      look like it is ON FIRE rather than lit from inside.
//   2. It is small and it is brief, so there is no room for the campfire's nine
//      tongues and three layers. Four outer tongues and one core is the whole
//      silhouette; anything busier is wasted geometry nobody has time to see.
//   3. Embers trail it. A fire without anything coming off it reads as a solid
//      lit object, not as something burning. The drift field here rides the
//      bolt's own transform, so the embers do not need their own per-frame
//      tracking: they are a child of the group that already moves.
//   4. The light is the caller's problem, on purpose. A game object that
//      throws a lot of these needs a POOLED light so the scene's live light
//      count never changes when one is cast, or every cast recompiles every
//      lit shader in view - see PERF-AUDIT-AUG6.md and the decorLights budget
//      in the bundle for why that is not hypothetical here. This module only
//      builds the geometry; it holds no PointLight at all.
//
// Everything animated is done on the GPU off a single uTime uniform, exactly
// like the campfire, so any number of fire bolts in flight at once costs one
// uniform write per material per frame, not per bolt.

/* eslint-disable no-unused-vars */

import { rngFor, mergeParts, tongueParts, flameMat, driftMat, driftField } from './grim-kit.js';

// Materials are created once and shared by every fire bolt in the world -
// the player's own casts and every spellcasting NPC's - so animating them
// costs three uniform writes a frame no matter how many are in flight.
export function makeFireballKit(T, opt) {
  opt = opt || {};
  const kit = { T, mats: {}, _t: 0 };

  // Outer tongues: the silhouette that reads from across the arena. Faster and
  // more torn than the campfire's, because a thrown fire is urgent, not
  // settled - rate 1.6 against the campfire's 1.0.
  kit.mats.outer = flameMat(T, {
    c0: 0xffcf6b, c1: 0xff7a1e, c2: 0xb31e05,
    alpha: 0.64, erode: 1.30, sway: 2.30, lick: 1.15, rate: 1.6
  });
  // Core: white-hot where the bolt is thickest, barely tears at all so the
  // middle of the effect always reads as solid even while the outer tongues
  // are eroding.
  //
  // First pass had this at R 0.070 / alpha 0.95, and on the turntable it
  // clipped to a white pearl that swallowed the outer tongues from anywhere
  // but dead-on - the exact "additive stacks to white where it should be
  // hottest" trap the failure catalogue warns about. Smaller and slightly
  // less opaque leaves it reading as the hot MIDDLE of a fire-coloured shape
  // instead of the whole shape.
  kit.mats.core = flameMat(T, {
    c0: 0xffffff, c1: 0xfff0b0, c2: 0xffab33,
    alpha: 0.80, erode: 0.34, sway: 0.55, lick: 0.65, rate: 1.3
  });
  // Embers: small, quick, warm fading to a dead coal colour rather than to
  // black - a spark that just goes out reads as a rendering bug, one that
  // visibly cools does not.
  //
  // spread/rise widened from the first pass (0.05/0.22): tucked in tight to
  // the core they never left the flame's own silhouette and the "trail" was
  // invisible. Wider, they clear the tongues and read as embers coming OFF
  // the bolt rather than texture on it.
  kit.mats.ember = driftMat(T, {
    rise: 0.34, size: 0.052, grow: 0.55, wander: 0.06, spread: 0.10, ease: 0.42,
    lean: -0.16, col: 0xffb066, col2: 0x662200, alpha: 0.95, rate: 2.2,
    hold: 0.22, flick: 0.4, additive: true
  });

  // One call a frame for the WHOLE WORLD's fire bolts, same shape as
  // campfireKit().tick / tickCampfires. Lazily created, so a match where
  // nobody ever casts fire never pays for it.
  kit.tick = function (seconds) {
    kit.mats.outer.userData.U.uTime.value = seconds;
    kit.mats.core.userData.U.uTime.value = seconds;
    kit.mats.ember.userData.U.uTime.value = seconds;
  };

  // Build one bolt. Returns { g, radius }. Every instance shares the three
  // materials above; only the geometry below is per-instance, and even that
  // is a single merged mesh per layer, so one bolt is three draw calls
  // (outer, core, embers) however many tongues it is built from.
  kit.build = function (o) {
    o = o || {};
    const rnd = rngFor(o.seed === undefined ? Math.floor(Math.random() * 1e6) : o.seed);
    const g = new T.Group();

    // Four tongues around a tight radius, uneven headings and uneven reach so
    // the cluster does not read as one shape rotated four times - the same
    // "evenly spaced reads as a starburst" trap the campfire and the failure
    // catalogue both call out.
    const outerList = [];
    const n = 4;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + rnd() * 0.9;
      const rim = rnd();
      const r = 0.018 + rim * 0.026;
      outerList.push({
        R: 0.048 + (1 - rim) * 0.020 + rnd() * 0.016,
        H: 0.13 + rim * 0.09 + rnd() * 0.05,
        x: Math.sin(a) * r, z: Math.cos(a) * r, y: 0,
        // lean is expressed in the tongue's OWN local frame, before the whole
        // group gets raked backward by orientAlong - so "lean" here just
        // means "flares a little wider than its own base", not "points
        // backward". The group orientation supplies the backward rake.
        tx: -Math.cos(a) * (0.10 + rim * 0.16),
        tz: Math.sin(a) * (0.10 + rim * 0.16),
        seed: rnd() * 6.283
      });
    }
    const outer = new T.Mesh(mergeParts(T, tongueParts(T, outerList, 9, 10)), kit.mats.outer);
    outer.renderOrder = 3;
    g.add(outer);

    const core = new T.Mesh(mergeParts(T, tongueParts(T, [{
      R: 0.056, H: 0.105, x: 0, z: 0, y: -0.01, seed: rnd() * 6.283, p: 0.40, q: 0.75
    }], 10, 10)), kit.mats.core);
    core.renderOrder = 4;
    g.add(core);

    // Embers. Small field, tight spread - this is a fireball, not its own
    // campsite - riding the group's own transform so they travel and rake
    // with it for free.
    const ember = new T.Mesh(driftField(T, 9, 0.055, 0.01, rnd), kit.mats.ember);
    ember.renderOrder = 5;
    ember.visible = opt.embers !== false;
    g.add(ember);

    return { g, radius: 0.15, emberMesh: ember };
  };

  // Point the whole cluster so its tongues trail backward along -dir, the
  // way a comet's tail points away from its own direction of travel. Call
  // once, at cast time - the bolt flies a straight line, so the orientation
  // never has to be touched again.
  kit.orientAlong = function (g, dir) {
    const back = dir.clone().negate();
    if (back.lengthSq() < 1e-8) return;
    back.normalize();
    g.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), back);
  };

  return kit;
}
