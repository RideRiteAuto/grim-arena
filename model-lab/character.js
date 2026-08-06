// GRIM WORLD: the player character, v4.
//
// A base body first, armor draped over it second. The v3 rig WAS its armor:
// the torso was a breastplate, the arms were steel tubes, and there was no
// person underneath. This build is a person - skin, padded tunic, trousers,
// real boots with a heel and a toe box, hands with fingers - and every armor
// piece is a separate mesh in a `gear` group fitted over that body, so armor
// can come off (rig.setArmor(false)) and future pieces can drape per slot.
//
// Numbers this body is built to (research pass, written down before modelling):
//   total height 2.20, head height 0.30 (7.3 heads, stylised-heroic)
//   chin 1.93  shoulder line 1.76 (0.80 H, was 0.70 - the single biggest fix)
//   nipple 1.65  waist 1.32  crotch 1.10  knee 0.63  ankle 0.10
//   bideltoid 0.72 (was 0.90+)  hip width 0.52  arm span ~= height
//   the four distance-critical curves, in order: trapezius slope (20-30 deg,
//   a horizontal shoulder shelf is the #1 blocky tell), waist pinch, calf
//   taper (ankle ~50% of calf), neck-to-head transition
//   limbs are NOT tubes: forearm widest below the elbow with the wrist at
//   ~58%, thigh tapers ~30% to the knee, and 5-8 deg of elbow bend and 3-5
//   deg of knee bend are BAKED into the shapes - dead-straight limbs read as
//   pipes whatever the shading
//
// The rig contract is the game's, not mine, and it is frozen:
//   parts: upper, torso, head, armR, armL, legR, legL, hand, handL, sword,
//          staff, bow, backBow, shield, ward, orb, frostShell, crest,
//          capePiv, bladeTip, pick, axe, great, greatTip
//   animate() writes ROTATIONS on those pivots and never positions, except
//   P.shield.position which it owns outright. mats.cloth is recoloured per
//   player for multiplayer palettes, so everything identity-coloured (tunic,
//   cape) shares that one material. New optional parts (chest, hair) are
//   guarded with `if (P.x)` game-side so bosses built on the old rig survive.
//
// Underclothes convention: undyed-linen padded tunic (takes pal.cloth), dark
// brown trousers, leather boots and belt. Low-saturation earth tones that
// read under any armor colour. Sleeves stop above the bracer line so armor
// layers cleanly.
import { rngFor, mergeParts } from './grim-kit.js';

// An open loft along Y through elliptical superellipse sections, smooth
// shaded. This is the whole body's construction method: silhouette lives in
// the section list, and a part is one surface instead of stacked primitives.
// secs: { y, w, d, x?, z?, p? }  half-width, half-depth, centre offset, power.
function loftY(T, secs, n, mat) {
  const pos = [], idx = [];
  const N = n;
  for (let s = 0; s < secs.length; s++) {
    const c = secs[s], p = c.p || 2.2, e = 2 / p;
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2;
      const ca = Math.cos(a), sa = Math.sin(a);
      pos.push(
        (c.x || 0) + c.w * Math.sign(ca) * Math.pow(Math.abs(ca), e),
        c.y,
        (c.z || 0) + c.d * Math.sign(sa) * Math.pow(Math.abs(sa), e));
    }
  }
  for (let s = 0; s < secs.length - 1; s++) {
    for (let i = 0; i < N; i++) {
      const j = (i + 1) % N, a = s * N + i, b = s * N + j, c2 = (s + 1) * N + i, d = (s + 1) * N + j;
      idx.push(a, c2, b, b, c2, d);
    }
  }
  // end caps
  const cap = (s, up) => {
    const base = s * N, ctr = pos.length / 3;
    pos.push(secs[s].x || 0, secs[s].y, secs[s].z || 0);
    for (let i = 0; i < N; i++) {
      const j = (i + 1) % N;
      if (up) idx.push(ctr, base + i, base + j); else idx.push(ctr, base + j, base + i);
    }
  };
  cap(0, false); cap(secs.length - 1, true);
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  const m = new T.Mesh(g, mat); m.castShadow = true;
  return m;
}

export function buildFighterRig(T, pal, opt) {
  opt = opt || {};

  // ---- materials ----------------------------------------------------------
  // Skin and cloth are SMOOTH shaded - that is half the upgrade. Steel keeps
  // flat shading: hard facets read as beaten metal and match the world.
  const skin  = new T.MeshStandardMaterial({ color: 0xc89b72, roughness: 0.92, metalness: 0 });
  const cloth = new T.MeshStandardMaterial({ color: pal.cloth, roughness: 0.95, metalness: 0 });          // tunic + cape: the recolourable identity
  const pants = new T.MeshStandardMaterial({ color: 0x6a563e, roughness: 0.97, metalness: 0 });
  const leather = new T.MeshStandardMaterial({ color: 0x241a10, roughness: 0.9, metalness: 0 });
  const hairM = new T.MeshStandardMaterial({ color: 0x2e2119, roughness: 0.95, metalness: 0 });
  const steel = new T.MeshStandardMaterial({ color: pal.steel, roughness: 0.31, metalness: 0.92, flatShading: true });
  const trim  = new T.MeshStandardMaterial({ color: pal.trim, roughness: 0.36, metalness: 0.75, flatShading: true });
  const dark  = new T.MeshStandardMaterial({ color: 0x2a2622, roughness: 0.95, metalness: 0, flatShading: true });

  const g = new T.Group();
  const body = new T.Group(); g.add(body);

  const box = (w, h, d, m, y) => { const x = new T.Mesh(new T.BoxGeometry(w, h, d), m); x.castShadow = true; if (y !== undefined) x.position.y = y; return x; };
  const cyl = (r1, r2, h, m, y, seg) => { const x = new T.Mesh(new T.CylinderGeometry(r1, r2, h, seg || 10), m); x.castShadow = true; if (y !== undefined) x.position.y = y; return x; };
  const sph = (r, m, sx, sy, sz, seg) => { const x = new T.Mesh(new T.SphereGeometry(r, seg || 14, 10), m); x.castShadow = true; x.scale.set(sx || 1, sy || 1, sz || 1); return x; };

  // ---- torso --------------------------------------------------------------
  // upper still sits at 0.98 (the game's waist-pivot convention). Everything
  // in `upper` is expressed relative to that.
  const upper = new T.Group(); upper.position.y = 0.98; body.add(upper);

  // Pelvis and seat, in trousers. World 1.00 to 1.22, so in body space.
  const pelvis = loftY(T, [
    { y: 0.955, w: 0.128, d: 0.100, p: 2.6 },
    { y: 1.02, w: 0.172, d: 0.128, p: 2.5 },
    { y: 1.10, w: 0.182, d: 0.132, p: 2.4 },
    { y: 1.16, w: 0.180, d: 0.128, p: 2.3 },
    { y: 1.22, w: 0.168, d: 0.120, p: 2.2 }
  ], 14, pants);
  body.add(pelvis);
  const belt = cyl(0.178, 0.184, 0.06, leather, 1.245, 14); body.add(belt);
  const buckle = box(0.055, 0.048, 0.02, trim); buckle.position.set(0, 1.245, 0.132); body.add(buckle);

  // The padded tunic: hips to shoulders in ONE loft so the waist pinch and
  // the trapezius slope are a single silhouette. Sections in upper space
  // (world y minus 0.98). Shoulder half-width peaks at 0.30 then the last
  // sections pull IN and UP: that is the trap slope.
  const chest = new T.Group(); upper.add(chest);   // breathing pivot, new optional part
  const torso = loftY(T, [
    { y: 0.245, w: 0.163, d: 0.115, p: 2.3 },  // tunic hem, tucked at the belt
    { y: 0.34, w: 0.152, d: 0.108, p: 2.3 },   // waist pinch (0.60 H)
    { y: 0.46, w: 0.168, d: 0.118, p: 2.3 },   // lower ribcage
    { y: 0.60, w: 0.190, d: 0.130, p: 2.4 },   // chest at the nipple line
    { y: 0.70, w: 0.240, d: 0.134, p: 2.8 },   // deltoid shelf, wide and flat
    { y: 0.775, w: 0.190, d: 0.120, p: 2.5 },  // trap slope, gentler
    { y: 0.83, w: 0.092, d: 0.088, p: 2.2 }    // neck root
  ], 16, cloth);
  chest.add(torso);
  // quilting: three thin stitch lines across the tunic front
  for (let qi = 0; qi < 3; qi++) {
    const q = cyl(0.003, 0.003, 0.30, leather, 0, 5);
    q.rotation.z = Math.PI / 2;
    q.position.set(0, 0.36 + qi * 0.14, 0.128 - qi * 0.004);
    chest.add(q);
  }

  const neck = loftY(T, [
    { y: 0.80, w: 0.062, d: 0.062, p: 2.1 },
    { y: 0.92, w: 0.052, d: 0.055, p: 2.1 }
  ], 12, skin);
  upper.add(neck);

  // ---- head ---------------------------------------------------------------
  // Pivot at the neck base, world 1.86. Skull is one loft: jaw taper, wide
  // cranium, rounded crown. Chin at world ~1.93, crown ~2.20.
  const head = new T.Group(); head.position.y = 0.88; upper.add(head);
  const skull = loftY(T, [
    { y: 0.035, w: 0.062, d: 0.070, p: 2.2 },   // jaw
    { y: 0.085, w: 0.088, d: 0.100, p: 2.2 },   // cheekbones
    { y: 0.150, w: 0.103, d: 0.113, p: 2.3 },   // temples
    { y: 0.230, w: 0.108, d: 0.118, p: 2.4 },   // cranium
    { y: 0.300, w: 0.088, d: 0.098, p: 2.2 },   // crown curve
    { y: 0.340, w: 0.030, d: 0.036, p: 2.0 }    // crown
  ], 14, skin);
  head.add(skull);
  // chin and jawline
  const chin = sph(0.045, skin, 1.15, 0.8, 0.9); chin.position.set(0, 0.028, 0.055); head.add(chin);
  // a real nose, small: bridge wedge + tip, smooth shaded so it blends
  const nose = sph(0.016, skin, 0.78, 1.25, 1.0); nose.position.set(0, 0.106, 0.108); head.add(nose);
  // brow ridge shades the eyes; eyes are shallow dark insets, deliberately
  // simple - Kevin does not want a designed face yet, just not a blank dome
  const brow = sph(0.055, skin, 1.55, 0.32, 0.62); brow.position.set(0, 0.152, 0.080); head.add(brow);
  const eyeM = new T.MeshStandardMaterial({ color: 0x1c1713, roughness: 0.35, metalness: 0 });
  for (const sd of [-1, 1]) {
    const eye = sph(0.014, eyeM, 1.35, 1, 0.6, 8);
    eye.position.set(sd * 0.040, 0.128, 0.096); head.add(eye);
    const ear = sph(0.020, skin, 0.6, 1.15, 0.85, 8);
    ear.position.set(sd * 0.103, 0.115, -0.012); head.add(ear);
  }
  const mouth = box(0.032, 0.004, 0.006, new T.MeshStandardMaterial({ color: 0xa5745c, roughness: 0.9 }));
  mouth.position.set(0, 0.050, 0.100); head.add(mouth);
  // short cropped hair: a cap loft slightly proud of the skull, with a
  // straight fringe line; sits under the helm without clipping
  const hair = loftY(T, [
    { y: 0.150, w: 0.111, d: 0.120, p: 2.4, z: -0.012 },
    { y: 0.240, w: 0.114, d: 0.124, p: 2.4, z: -0.008 },
    { y: 0.310, w: 0.092, d: 0.102, p: 2.2 },
    { y: 0.355, w: 0.030, d: 0.036, p: 2.0 }
  ], 14, hairM);
  head.add(hair);

  // ---- arms ---------------------------------------------------------------
  // Pivots raised and pulled in: (0.30, 0.78) in upper = world (0.30, 1.76),
  // the 0.80 H shoulder line. One loft per arm along -Y with the elbow bend
  // BAKED as a z drift: upper arm hangs, forearm angles slightly forward.
  // Deltoid is the widest point; forearm peaks below the elbow; wrist is 58%
  // of the forearm. Short tunic sleeve covers the deltoid.
  const armGeo = (mirror) => {
    const arm = new T.Group();
    const delt = sph(0.082, cloth, 1.18, 1.05, 1.10); delt.position.set(mirror * -0.034, -0.048, 0); arm.add(delt);
    const sleeve = loftY(T, [
      { y: -0.075, w: 0.068, d: 0.068, p: 2.3 },
      { y: -0.120, w: 0.060, d: 0.060, p: 2.3 },
      { y: -0.225, w: 0.053, d: 0.053, p: 2.3 }
    ], 12, cloth);
    arm.add(sleeve);
    const cuffRoll = new T.Mesh(new T.TorusGeometry(0.052, 0.011, 6, 12), cloth);
    cuffRoll.rotation.x = Math.PI / 2; cuffRoll.position.y = -0.225; cuffRoll.castShadow = true;
    arm.add(cuffRoll);
    const limbSkin = loftY(T, [
      { y: -0.215, w: 0.050, d: 0.050, p: 2.2 },              // out from under the sleeve
      { y: -0.240, w: 0.047, d: 0.049, p: 2.2 },              // above the elbow
      { y: -0.300, w: 0.044, d: 0.048, p: 2.2, z: 0.012 },    // elbow, drifting forward
      { y: -0.360, w: 0.049, d: 0.051, p: 2.2, z: 0.022 },    // forearm peak: widest BELOW the elbow
      { y: -0.480, w: 0.036, d: 0.037, p: 2.2, z: 0.028 },
      { y: -0.560, w: 0.028, d: 0.030, p: 2.1, z: 0.030 }     // wrist at ~58%
    ], 12, skin);
    arm.add(limbSkin);
    return arm;
  };
  const armR = armGeo(-1); armR.position.set(-0.295, 0.755, 0); upper.add(armR);
  const armL = armGeo(1);  armL.position.set(0.295, 0.755, 0); upper.add(armL);

  // Hands: a palm loft and a merged curled-finger mass plus a thumb. The
  // right hand curls tighter - it is the weapon fist - and the weapon grips
  // pass through its origin exactly like v3, so every weapon sits right.
  const handAt = (arm, curl) => {
    const hand = new T.Group(); hand.position.set(0, -0.60, 0.030); arm.add(hand);
    const palm = loftY(T, [
      { y: 0.015, w: 0.030, d: 0.036, p: 2.4 },
      { y: -0.045, w: 0.036, d: 0.040, p: 2.6 },
      { y: -0.075, w: 0.033, d: 0.036, p: 2.4 }
    ], 10, skin);
    hand.add(palm);
    // four fingers as one shaped mass, curled by `curl`
    const fing = loftY(T, [
      { y: -0.070, w: 0.032, d: 0.030, p: 2.8 },
      { y: -0.105, w: 0.030, d: 0.026, p: 2.8, z: 0.012 * curl },
      { y: -0.130, w: 0.026, d: 0.020, p: 2.6, z: 0.030 * curl }
    ], 10, skin);
    hand.add(fing);
    const thumb = sph(0.013, skin, 1, 1.55, 1, 8);
    thumb.position.set(0.026 * (arm === armL ? 1 : -1), -0.052, 0.030);
    thumb.rotation.set(0.35, 0, 0.30 * (arm === armL ? -1 : 1));
    hand.add(thumb);
    return hand;
  };
  const hand = handAt(armR, 1.0);       // weapon fist
  const handL = handAt(armL, 0.45);     // relaxed

  // ---- legs ---------------------------------------------------------------
  // Pivots at (0.145, 1.02): the crotch line. One loft per leg: thigh in
  // trousers tapering 30% to the knee, knee bulge, calf peak in the upper
  // third, ankle at half the calf, 4 deg of knee bend baked as z drift.
  const legGeo = () => {
    const leg = new T.Group();
    const thigh = loftY(T, [
      { y: 0.05, w: 0.110, d: 0.115, p: 2.4 },
      { y: -0.14, w: 0.088, d: 0.094, p: 2.3, z: 0.006 },
      { y: -0.30, w: 0.072, d: 0.078, p: 2.3, z: 0.010 },
      { y: -0.39, w: 0.062, d: 0.068, p: 2.3, z: 0.006 }    // knee, 30% off the hip
    ], 12, pants);
    leg.add(thigh);
    const knee = sph(0.056, pants, 1, 0.85, 1); knee.position.set(0, -0.40, 0.012); leg.add(knee);
    // boot from just under the knee: cuff, calf shell, ankle
    const bootTop = loftY(T, [
      { y: -0.44, w: 0.066, d: 0.070, p: 2.3 },
      { y: -0.56, w: 0.062, d: 0.068, p: 2.3, z: -0.004 },   // calf peak upper third
      { y: -0.74, w: 0.043, d: 0.047, p: 2.2 },
      { y: -0.86, w: 0.036, d: 0.040, p: 2.2 }               // ankle ~55% of calf
    ], 12, leather);
    leg.add(bootTop);
    // a real FOOT: heel behind the ankle, arch, toe box rising at the front.
    // Lofted along Y but shaped by per-section z offsets and depths.
    const foot = loftY(T, [
      { y: -0.86, w: 0.038, d: 0.052, p: 2.4, z: 0.010 },
      { y: -0.92, w: 0.043, d: 0.085, p: 2.6, z: 0.035 },    // instep, foot reaching forward
      { y: -0.97, w: 0.047, d: 0.118, p: 2.8, z: 0.062 },    // sole: heel to toe box
      { y: -0.995, w: 0.042, d: 0.110, p: 2.8, z: 0.062 }
    ], 12, leather);
    leg.add(foot);
    const heel = box(0.070, 0.028, 0.055, dark); heel.position.set(0, -0.985, -0.030); leg.add(heel);
    return leg;
  };
  const legR = legGeo(); legR.position.set(-0.122, 1.02, 0); body.add(legR);
  const legL = legGeo(); legL.position.set(0.122, 1.02, 0); body.add(legL);

  // ---- gear: every armor piece, fitted OVER the body ----------------------
  // One group's visibility is the whole armor state. Pieces that must move
  // with a limb are parented to that limb but registered here for toggling.
  const gear = { list: [] };
  const gearAdd = (parent, mesh) => { parent.add(mesh); gear.list.push(mesh); return mesh; };

  // breastplate: follows the tunic loft 0.025 proud, chest to trap
  const plate = gearAdd(chest, loftY(T, [
    { y: 0.30, w: 0.190, d: 0.140, p: 2.5 },
    { y: 0.46, w: 0.192, d: 0.142, p: 2.5 },
    { y: 0.60, w: 0.213, d: 0.152, p: 2.6 },
    { y: 0.70, w: 0.228, d: 0.150, p: 2.8 },
    { y: 0.76, w: 0.178, d: 0.132, p: 2.5 },
    { y: 0.80, w: 0.108, d: 0.106, p: 2.2 }
  ], 16, steel));
  const ridge = gearAdd(chest, box(0.035, 0.42, 0.03, trim)); ridge.position.set(0, 0.52, 0.148); ridge.rotation.x = 0.10;
  const collar = gearAdd(upper, cyl(0.115, 0.15, 0.075, trim, 0.815, 12));
  // fauld + tassets off the belt line
  const fauld = gearAdd(body, cyl(0.192, 0.212, 0.085, steel, 1.185, 14));
  for (const sd of [-1, 1]) {
    const tasset = gearAdd(body, box(0.115, 0.155, 0.035, steel));
    tasset.position.set(sd * 0.135, 1.09, 0.115); tasset.rotation.x = 0.22; tasset.rotation.z = sd * -0.12;
    const tassetTrim = gearAdd(body, box(0.115, 0.03, 0.037, trim));
    tassetTrim.position.set(sd * 0.135, 1.015, 0.135); tassetTrim.rotation.x = 0.22; tassetTrim.rotation.z = sd * -0.12;
  }

  // pauldrons: two overlapping plates per shoulder, on the arm so they move
  for (const [arm, sd] of [[armR, -1], [armL, 1]]) {
    const p1 = gearAdd(arm, sph(0.098, steel, 1.10, 0.74, 1.10, 12)); p1.position.set(sd * 0.012, 0.030, 0); p1.rotation.z = sd * -0.20;
    const p2 = gearAdd(arm, sph(0.082, steel, 1.02, 0.64, 1.02, 12)); p2.position.set(sd * 0.006, -0.045, 0); p2.rotation.z = sd * -0.16;
    const pRim = gearAdd(arm, cyl(0.086, 0.094, 0.026, trim, -0.095, 12));
    // bracer wrapping the forearm peak down to the wrist
    const bracer = gearAdd(arm, loftY(T, [
      { y: -0.330, w: 0.058, d: 0.060, p: 2.4, z: 0.020 },
      { y: -0.450, w: 0.046, d: 0.047, p: 2.4, z: 0.027 },
      { y: -0.545, w: 0.038, d: 0.040, p: 2.3, z: 0.030 }
    ], 12, steel));
    const cuff = gearAdd(arm, cyl(0.043, 0.047, 0.030, trim, -0.552, 10)); cuff.position.z = 0.030;
  }

  // greaves + sabaton caps on the boots
  for (const leg of [legR, legL]) {
    gearAdd(leg, loftY(T, [
      { y: -0.46, w: 0.070, d: 0.072, p: 2.4 },
      { y: -0.60, w: 0.064, d: 0.069, p: 2.4, z: 0.006 },
      { y: -0.76, w: 0.046, d: 0.050, p: 2.3 }
    ], 12, steel));
    const kneeCop = gearAdd(leg, sph(0.060, steel, 1, 0.8, 1, 10)); kneeCop.position.set(0, -0.40, 0.020);
    const sab = gearAdd(leg, loftY(T, [
      { y: -0.875, w: 0.042, d: 0.056, p: 2.5, z: 0.012 },
      { y: -0.93, w: 0.047, d: 0.090, p: 2.7, z: 0.038 },
      { y: -0.965, w: 0.049, d: 0.105, p: 2.8, z: 0.058 }
    ], 12, steel));
  }

  // helm: follows the skull 0.02 proud, with brim, nasal, cheeks, neck guard
  const helm = new T.Group(); head.add(helm); gear.list.push(helm);
  helm.add(loftY(T, [
    { y: 0.095, w: 0.108, d: 0.120, p: 2.3 },
    { y: 0.160, w: 0.123, d: 0.133, p: 2.3 },
    { y: 0.240, w: 0.128, d: 0.138, p: 2.4 },
    { y: 0.315, w: 0.104, d: 0.114, p: 2.2 },
    { y: 0.370, w: 0.034, d: 0.040, p: 2.0 }
  ], 14, steel));
  const brim = cyl(0.126, 0.132, 0.030, trim, 0.085, 14); helm.add(brim);
  const nasal = box(0.026, 0.105, 0.018, steel); nasal.position.set(0, 0.075, 0.128); helm.add(nasal);
  for (const sd of [-1, 1]) {
    const cheekG = box(0.036, 0.085, 0.062, steel);
    cheekG.position.set(sd * 0.098, 0.045, 0.052); cheekG.rotation.y = sd * 0.30; helm.add(cheekG);
  }
  const neckGuard = cyl(0.095, 0.125, 0.062, steel, 0.010, 10); neckGuard.position.z = -0.045; helm.add(neckGuard);
  // plume: stiff comb then a horsehair tail that sweeps back and droops.
  // P.crest lives here - the part must exist even with armor off, so the
  // group stays parented to head and only its meshes ride the gear toggle.
  const crest = new T.Group(); crest.position.set(0, 0.34, -0.01); head.add(crest);
  gear.list.push(crest);
  for (let i = 0; i < 4; i++) {
    const fin = new T.Mesh(new T.BoxGeometry(0.022, 0.105 - i * 0.016, 0.085), cloth);
    fin.position.set(0, 0.048 - i * 0.014, 0.030 - i * 0.062); fin.castShadow = true; crest.add(fin);
  }
  for (let i = 0; i < 6; i++) {
    const t = i / 5;
    const seg = new T.Mesh(new T.CylinderGeometry(0.040 - t * 0.026, 0.033 - t * 0.022, 0.105, 5), cloth);
    seg.position.set(0, 0.005 - t * t * 0.17, -0.155 - t * 0.155);
    seg.rotation.x = 1.05 + t * 0.75; seg.castShadow = true; crest.add(seg);
  }

  // cape: pivot always exists (animate writes it), the cloth rides the toggle
  const capePiv = new T.Group(); capePiv.position.set(0, 0.74, -0.17); upper.add(capePiv);
  const capeSecs = [
    { y: 0, w: 0.24, d: 0.016, p: 2.6 },
    { y: -0.34, w: 0.27, d: 0.015, p: 2.6, z: -0.055 },
    { y: -0.72, w: 0.30, d: 0.014, p: 2.6, z: -0.125 },
    { y: -1.10, w: 0.335, d: 0.013, p: 2.6, z: -0.185 }
  ];
  const cape = loftY(T, capeSecs, 10, cloth);
  gearAdd(capePiv, cape);
  const mantle = gearAdd(capePiv, box(0.50, 0.115, 0.16, cloth)); mantle.position.set(0, 0.015, 0.045); mantle.rotation.x = -0.25;
  const clasp = gearAdd(capePiv, new T.Mesh(new T.OctahedronGeometry(0.038, 0), trim)); clasp.position.set(0, 0.03, 0.14); clasp.castShadow = true;

  return {
    g, body, upper, chest, torso, head, hair, helm, armR, armL, legR, legL,
    hand, handL, crest, capePiv, gear,
    mats: { steel, cloth, trim, skin, pants, leather, dark },
    box, cyl, sph
  };
}


// ---- weapons ---------------------------------------------------------------
// TRANSPLANTED VERBATIM from the v3 makeFighter and generated from the live
// bundle by a script, not retyped: every grip rotation and rest offset here is
// tuned against animate()'s swing arcs, and none of it changed in v4. The only
// edits are mechanical: the v3 hand-creation lines are stripped (the rig
// builds real hands now) and the block is wrapped as a function.
export function buildWeaponSet(T, rig) {
  const { armR, armL, upper, hand, handL, box, cyl, sph, g } = rig;
  const steel = rig.mats.steel, cloth = rig.mats.cloth, trim = rig.mats.trim, dark = rig.mats.dark;


  // Curved blade built from stacked segments — a scimitar silhouette reads far
  // better in motion than a straight bar, and it's still six boxes.
  // Scimitar: curve, blade width and edge highlight all in the SAME plane, a
  // swept crossguard, wrapped grip and gem pommel.
  const bladeMat = new T.MeshStandardMaterial({ color: 0xccd4dc, roughness: 0.4, metalness: 0.7, flatShading: true });
  const edgeMat  = new T.MeshStandardMaterial({ color: 0xf2f6fa, roughness: 0.25, metalness: 0.85 });
  const sword = new T.Group();
  let bx = 0, by = 0.2, ba = 0;
  for (let i = 0; i < 6; i++) {
    const len = 0.2, w = 0.17 - i * 0.014;
    const seg = box(w, len, 0.045, bladeMat);
    seg.position.set(bx, by, 0); seg.rotation.z = ba; sword.add(seg);
    const edge = box(0.028, len, 0.05, edgeMat); edge.position.x = w / 2 - 0.01; seg.add(edge);
    bx += -Math.sin(ba) * len; by += Math.cos(ba) * len; ba += 0.13;
  }
  const tip = new T.Mesh(new T.ConeGeometry(0.075, 0.26, 4), bladeMat);
  tip.position.set(bx - Math.sin(ba) * 0.1, by + Math.cos(ba) * 0.1, 0);
  tip.rotation.z = ba; tip.scale.z = 0.4; tip.castShadow = true; sword.add(tip);
  const bladeTip = new T.Object3D(); bladeTip.position.set(bx, by + 0.16, 0); sword.add(bladeTip);
  const guard = box(0.4, 0.07, 0.1, trim, 0.09); sword.add(guard);
  for (const s of [-1, 1]) { const q = box(0.09, 0.09, 0.09, trim); q.position.set(s * 0.21, 0.13, 0); sword.add(q); }
  sword.add(box(0.062, 0.24, 0.062, dark, -0.07));
  const wrap1 = box(0.07, 0.03, 0.07, trim, -0.02); sword.add(wrap1);
  const wrap2 = box(0.07, 0.03, 0.07, trim, -0.13); sword.add(wrap2);
  const pommel = new T.Mesh(new T.OctahedronGeometry(0.062, 0), new T.MeshStandardMaterial({ color: 0xc23a2e, emissive: 0x5a150e, emissiveIntensity: 0.8, roughness: 0.3, flatShading: true }));
  pommel.position.y = -0.24; pommel.castShadow = true; sword.add(pommel);
  // Gripped at the base, blade PERPENDICULAR to the forearm (a real fist
  // grip) — not aligned with the arm bone.
  sword.rotation.set(Math.PI / 2, -Math.PI / 2, 0); hand.add(sword);   // blade horizontal forward, rolled the other 90° — curve flipped

  // The Grim Cleaver: forged iron two-hander, same grip convention as the sword.
  const great = new T.Group();
  const gsteel = new T.MeshStandardMaterial({ color: 0x8b929e, roughness: 0.42, metalness: 0.5, flatShading: true });
  const gfuller = new T.MeshStandardMaterial({ color: 0x30333a, roughness: 0.6, metalness: 0.4, flatShading: true });
  great.add(box(0.15, 1.45, 0.045, gsteel, 0.98));
  great.add(box(0.05, 1.2, 0.05, gfuller, 0.9));
  const gt2 = new T.Mesh(new T.ConeGeometry(0.085, 0.3, 4), gsteel); gt2.position.y = 1.83; gt2.rotation.y = Math.PI / 4; gt2.castShadow = true; great.add(gt2);
  great.add(box(0.55, 0.08, 0.12, trim, 0.24));
  great.add(box(0.075, 0.44, 0.075, dark, -0.04));
  const gp2 = new T.Mesh(new T.OctahedronGeometry(0.08, 0), trim); gp2.position.y = -0.3; gp2.castShadow = true; great.add(gp2);
  const greatTip = new T.Object3D(); greatTip.position.set(0, 1.9, 0); great.add(greatTip);
  great.rotation.set(Math.PI / 2, -Math.PI / 2, 0); great.visible = false; hand.add(great);

  const staff = new T.Group();
  const shaft = new T.Mesh(new T.CylinderGeometry(0.045, 0.055, 1.75, 6), dark); shaft.position.y = 0.5; shaft.castShadow = true; staff.add(shaft);
  const orb = new T.Mesh(new T.IcosahedronGeometry(0.15, 1), new T.MeshStandardMaterial({ color: 0x9ad8ff, emissive: 0x2f7fbf, emissiveIntensity: 1.6, roughness: 0.2 }));
  orb.position.y = 1.42; staff.add(orb);
  const orbLight = new T.PointLight(0x6fb8ff, 2.2, 5, 2); orbLight.position.y = 1.42; staff.add(orbLight);
  staff.rotation.x = 0.35;   // leans forward out of the fist, orb clear of the head
  staff.visible = false; hand.add(staff);

  // Bow lives in the LEFT hand (archer's off-hand), gripped at its centre,
  // limbs vertical, belly facing away from the archer.
  const bow = new T.Group();
  const bowMat = new T.MeshStandardMaterial({ color: 0x6b4a2a, roughness: 0.85, flatShading: true });
  const arc = new T.Mesh(new T.TorusGeometry(0.52, 0.035, 5, 16, Math.PI * 1.3), bowMat);
  arc.rotation.z = Math.PI / 2 - Math.PI * 1.3 / 2;   // arc centred on the Y axis, bulge +X
  arc.castShadow = true; bow.add(arc);
  const grip = box(0.06, 0.16, 0.06, dark, 0); grip.position.x = 0.52; bow.add(grip);
  const tipY = Math.sin(Math.PI * 1.3 / 2) * 0.52;
  const tipX = Math.cos(Math.PI * 1.3 / 2) * 0.52;
  const string = new T.Mesh(new T.CylinderGeometry(0.008, 0.008, tipY * 2, 3), new T.MeshBasicMaterial({ color: 0xd8d2c0 }));
  string.position.x = tipX; bow.add(string);
  bow.position.set(-0.52, 0, 0);          // grip sits in the palm
  bow.rotation.y = -Math.PI / 2;          // belly faces the character's +Z (forward)
  bow.visible = false; handL.add(bow);
  // Slung copy for when the bow isn't drawn — diagonal across the back like
  // any archer carries it. The hand copy only appears while drawing/firing.
  const backBow = bow.clone();
  backBow.position.set(0.05, 0.3, -0.36);
  backBow.rotation.set(0.15, Math.PI / 2, 0.55);
  backBow.visible = false; upper.add(backBow);

  // Gathering tools: pickaxe (slot 4) and woodcutting axe (slot 5).
  const pick = new T.Group();
  pick.add(cyl(0.035, 0.045, 0.95, dark, 0.3, 6));
  for (const s of [-1, 1]) {
    const spike = new T.Mesh(new T.ConeGeometry(0.06, 0.5, 5), steel);
    spike.position.set(0, 0.74, s * 0.24); spike.rotation.x = s * (Math.PI / 2 + 0.42);
    spike.castShadow = true; pick.add(spike);
  }
  pick.rotation.x = Math.PI / 2 - 0.3; pick.visible = false; hand.add(pick);   // handle forward, head up
  const waxe = new T.Group();
  waxe.add(cyl(0.035, 0.045, 0.9, dark, 0.28, 6));
  const axeBlade = box(0.05, 0.32, 0.24, steel); axeBlade.position.set(0, 0.6, 0.17); waxe.add(axeBlade);
  const axeEdge = box(0.052, 0.32, 0.05, edgeMat); axeEdge.position.set(0, 0.6, 0.31); waxe.add(axeEdge);
  waxe.rotation.x = Math.PI / 2 - 0.3; waxe.visible = false; hand.add(waxe);   // handle forward, blade up

  // Heater shield: dark backing rim, bright face, pointed base, gold boss and
  // cross, corner studs — reads as a real kite shield instead of a plank.
  const shield = new T.Group();
  const back = box(0.05, 0.92, 0.68, dark); shield.add(back);
  const sface = box(0.055, 0.84, 0.6, steel); sface.position.x = -0.025; shield.add(sface);
  const point = box(0.055, 0.34, 0.34, steel); point.rotation.x = Math.PI / 4; point.position.set(-0.025, -0.48, 0); shield.add(point);
  const pointBack = box(0.05, 0.38, 0.38, dark); pointBack.rotation.x = Math.PI / 4; pointBack.position.set(0, -0.48, 0); shield.add(pointBack);
  const topRim = box(0.065, 0.09, 0.7, trim, 0.46); shield.add(topRim);
  const crossV = box(0.05, 0.7, 0.11, cloth); crossV.position.x = -0.055; shield.add(crossV);
  const crossH = box(0.05, 0.11, 0.48, cloth); crossH.position.set(-0.055, 0.14, 0); shield.add(crossH);
  const boss = new T.Mesh(new T.SphereGeometry(0.12, 8, 6), trim); boss.position.set(-0.09, 0.14, 0); boss.castShadow = true; shield.add(boss);
  for (const [yy, zz] of [[0.38, 0.24], [0.38, -0.24], [-0.12, 0.24], [-0.12, -0.24]]) {
    const stud = box(0.06, 0.06, 0.06, trim); stud.position.set(-0.06, yy, zz); shield.add(stud);
  }
  // Slung face-OUT on the arm (rotation.y = PI). Blocking then swings it
  // forward across the front the short way, instead of sweeping the face out
  // through the body from the inside.
  shield.position.set(0.09, -0.50, 0.06); shield.rotation.set(0, Math.PI, 0.12); shield.scale.setScalar(0.86); armL.add(shield);

  const ward = new T.Mesh(new T.SphereGeometry(1.15, 16, 12), new T.MeshBasicMaterial({ color: 0x6fb8ff, transparent: true, opacity: 0.16, side: T.DoubleSide }));
  ward.position.y = 1.1; ward.visible = false; g.add(ward);

  const frostShell = new T.Mesh(new T.IcosahedronGeometry(1.05, 1), new T.MeshBasicMaterial({ color: 0x9fdcff, transparent: true, opacity: 0.3, wireframe: true }));
  frostShell.position.y = 1.05; frostShell.visible = false; g.add(frostShell);

  return { sword, staff, bow, backBow, shield, ward, frostShell, orb, pick,
           axe: waxe, great, greatTip, bladeTip };
}

// ---- the whole fighter -----------------------------------------------------
export function makeFighterModel(T, pal) {
  const rig = buildFighterRig(T, pal);
  const wep = buildWeaponSet(T, rig);
  const setArmor = (on) => { rig.gear.list.forEach(m => { m.visible = on; }); };
  return {
    g: rig.g, body: rig.body,
    mats: rig.mats,
    setArmor,
    parts: {
      upper: rig.upper, torso: rig.torso, head: rig.head,
      chest: rig.chest, hair: rig.hair, helm: rig.helm,
      armR: rig.armR, armL: rig.armL, legR: rig.legR, legL: rig.legL,
      hand: rig.hand, handL: rig.handL,
      crest: rig.crest, capePiv: rig.capePiv,
      sword: wep.sword, staff: wep.staff, bow: wep.bow, backBow: wep.backBow,
      shield: wep.shield, ward: wep.ward, frostShell: wep.frostShell,
      orb: wep.orb, pick: wep.pick, axe: wep.axe, great: wep.great,
      greatTip: wep.greatTip, bladeTip: wep.bladeTip
    }
  };
}
