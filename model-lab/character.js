// GRIM WORLD: the player character, v5.
//
// v4 built a person instead of a suit of armor, and its proportions are kept
// here unchanged. What v5 fixes is CONSTRUCTION. Kevin's review of v4, in
// full, because every decision below answers a line of it: the joints were
// round balls and every limb looked like separate pieces glued together with
// visible seams; the eyebrows and chin were ovals stuck onto the face; the
// hair was blocky; the feet were bad and clipped into the ground; the lower
// shoulder could be seen through into the model; the sword blade was
// obviously stacked blocks; and the shield arm crossed the body when it
// should hang straight down with the shield carried flat at the side.
//
// The three construction rules that answer all of that:
//
// 1. NO GLUED BLOBS. A bulge that belongs to a limb - deltoid, knee, chin,
//    brow - is shaped in that limb's own section list, so it is part of one
//    continuous surface. v4's separate spheres are gone.
//
// 2. JOINTS ARE DOMES CENTERED ON THE PIVOT. The top of each limb loft
//    converges to a rounded cap whose center IS the rotation pivot, tucked
//    under the garment above it (tunic shoulder, pelvis). A sphere about the
//    pivot looks identical at any rotation, so no gap can open mid-swing -
//    which is exactly when v4's shoulder showed daylight. Where two surfaces
//    must meet, the boundary sits on a real clothing line (sleeve hem, boot
//    cuff, belt, collar) because clothing edges are the one place a seam is
//    information instead of a defect.
//
// 3. ANYTHING THAT TURNS A CORNER IS ONE SWEEP. sweep() lofts superellipse
//    sections along a curved spine with parallel-ish frames. The boot flows
//    from the shin around the ankle into a real foot as a single surface,
//    and the scimitar blade is one continuous curved body with a distal
//    taper - not six boxes fanned around an arc.
//
// Numbers (unchanged from the v4 research pass):
//   total height 2.20, head 0.30 (7.3 heads) | chin 1.93, shoulder line 1.76
//   waist 1.32, crotch 1.10, knee 0.63, ankle 0.10 | bideltoid 0.72, hips 0.52
//   trap slope 20-30 deg, wrist ~58% of forearm peak, ankle ~55% of calf,
//   5-8 deg elbow and 3-5 deg knee bend baked in - straight limbs read as pipes
//
// The rig contract is the game's and is frozen: parts upper, torso, head,
// armR, armL, legR, legL, hand, handL, sword, staff, bow, backBow, shield,
// ward, orb, frostShell, crest, capePiv, bladeTip, pick, axe, great,
// greatTip (+ optional chest, hair, helm guarded game-side). animate() writes
// rotations only, except P.shield.position which it owns outright. mats.cloth
// is the recolourable identity for multiplayer.
import { rngFor, mergeParts } from './grim-kit.js';

// An open loft along Y through elliptical superellipse sections, smooth
// shaded. Silhouette lives in the section list; a part is one surface.
// secs: { y, w, d, x?, z?, p? }  half-width, half-depth, centre offset, power.
//
// WINDING, learned the hard way: v4's version assumed ascending sections and
// still wound both end caps INWARD. Every loft authored top-down (sleeves,
// thighs, palms) came out inside-out - the renderer was showing the interior
// of the far wall through the culled near wall, which is where "I can see
// through the lower shoulder into the model" came from. Sections are
// normalised to ascending, and caps wound bottom -Y / top +Y. Measured with
// a triangle-normal test, not assumed.
function loftY(T, secs, n, mat) {
  if (secs.length > 1 && secs[0].y > secs[secs.length - 1].y) secs = secs.slice().reverse();
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
  const cap = (s, up) => {
    const base = s * N, ctr = pos.length / 3;
    pos.push(secs[s].x || 0, secs[s].y, secs[s].z || 0);
    for (let i = 0; i < N; i++) {
      const j = (i + 1) % N;
      // up: outward normal +Y is (ctr, j, i); down: -Y is (ctr, i, j)
      if (up) idx.push(ctr, base + j, base + i); else idx.push(ctr, base + i, base + j);
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

// A loft along a CURVED spine. Each section: { at:[x,y,z], w, d, p?, roll? }.
// The section ring starts in the XZ plane (like loftY's) and is rotated so
// its +Y points along the spine tangent at that station, so `w` stays the
// half-width across the spine and `d` the half-thickness. Tangents come from
// neighbouring stations; setFromUnitVectors from a fixed +Y reference keeps
// frames consistent for the gentle curves this model needs (a boot ankle, a
// scimitar's arc) - nothing here approaches the -Y antipode where that
// shortcut would flip.
function sweep(T, secs, n, mat) {
  const pos = [], idx = [];
  const N = n;
  const P = secs.map(c => new T.Vector3(c.at[0], c.at[1], c.at[2]));
  const up = new T.Vector3(0, 1, 0);
  for (let s = 0; s < secs.length; s++) {
    const c = secs[s], p = c.p || 2.2, e = 2 / p;
    const tan = new T.Vector3();
    if (s === 0) tan.subVectors(P[1], P[0]);
    else if (s === secs.length - 1) tan.subVectors(P[s], P[s - 1]);
    else tan.subVectors(P[s + 1], P[s - 1]);
    tan.normalize();
    const q = new T.Quaternion().setFromUnitVectors(up, tan);
    if (c.roll) q.multiply(new T.Quaternion().setFromAxisAngle(up, c.roll));
    const v = new T.Vector3();
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2;
      const ca = Math.cos(a), sa = Math.sin(a);
      v.set(
        c.w * Math.sign(ca) * Math.pow(Math.abs(ca), e),
        0,
        c.d * Math.sign(sa) * Math.pow(Math.abs(sa), e));
      v.applyQuaternion(q).add(P[s]);
      pos.push(v.x, v.y, v.z);
    }
  }
  for (let s = 0; s < secs.length - 1; s++) {
    for (let i = 0; i < N; i++) {
      const j = (i + 1) % N, a = s * N + i, b = s * N + j, c2 = (s + 1) * N + i, d = (s + 1) * N + j;
      idx.push(a, c2, b, b, c2, d);
    }
  }
  const cap = (s, first) => {
    const base = s * N, ctr = pos.length / 3;
    pos.push(P[s].x, P[s].y, P[s].z);
    for (let i = 0; i < N; i++) {
      const j = (i + 1) % N;
      // rings advance along +tangent, so the first cap faces -tangent
      // (ctr, i, j) and the last faces +tangent (ctr, j, i) - same fix as
      // loftY's caps, same triangle-normal test
      if (first) idx.push(ctr, base + i, base + j); else idx.push(ctr, base + j, base + i);
    }
  };
  cap(0, true); cap(secs.length - 1, false);
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
  // Skin and cloth smooth shaded; steel keeps flat shading - hard facets read
  // as beaten metal and match the world.
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
  const upper = new T.Group(); upper.position.y = 0.98; body.add(upper);

  // Pelvis and seat, in trousers. Runs a little higher than v4 so the leg
  // domes (below) are born covered.
  const pelvis = loftY(T, [
    { y: 0.945, w: 0.126, d: 0.098, p: 2.6 },
    { y: 1.02, w: 0.190, d: 0.130, p: 2.5 },   // flares over the thigh domes
    { y: 1.10, w: 0.196, d: 0.134, p: 2.4 },
    { y: 1.16, w: 0.184, d: 0.128, p: 2.3 },
    { y: 1.23, w: 0.166, d: 0.118, p: 2.2 }
  ], 14, pants);
  body.add(pelvis);
  // belt: an elliptical loft that follows the body, not a round hoop
  // floating off the front and back
  const belt = loftY(T, [
    { y: 1.215, w: 0.172, d: 0.124, p: 2.35 },
    { y: 1.275, w: 0.170, d: 0.122, p: 2.35 }
  ], 14, leather);
  body.add(belt);
  const buckle = box(0.055, 0.048, 0.02, trim); buckle.position.set(0, 1.245, 0.132); body.add(buckle);

  // The padded tunic: hips to shoulders in ONE loft. The deltoid shelf now
  // reaches further out (0.26) and stays soft, because it must meet the
  // sleeve domes and read as one shoulder - v4 stopped at 0.24 and left the
  // arm pivots stranded outside the silhouette.
  const chest = new T.Group(); upper.add(chest);   // breathing pivot
  const torso = loftY(T, [
    { y: 0.245, w: 0.163, d: 0.115, p: 2.3 },  // tunic hem, tucked at the belt
    { y: 0.34, w: 0.152, d: 0.108, p: 2.3 },   // waist pinch (0.60 H)
    { y: 0.46, w: 0.168, d: 0.118, p: 2.3 },   // lower ribcage
    { y: 0.60, w: 0.190, d: 0.130, p: 2.4 },   // chest at the nipple line
    { y: 0.685, w: 0.240, d: 0.134, p: 2.7 },  // deltoid shelf rising
    { y: 0.735, w: 0.260, d: 0.130, p: 2.8 },  // shelf peak: reaches the sleeve domes
    { y: 0.775, w: 0.218, d: 0.122, p: 2.6 },  // shelf folding over the domes
    { y: 0.805, w: 0.130, d: 0.104, p: 2.3 },  // trap slope
    { y: 0.83, w: 0.092, d: 0.088, p: 2.2 }    // neck root
  ], 16, cloth);
  chest.add(torso);

  const neck = loftY(T, [
    { y: 0.80, w: 0.062, d: 0.062, p: 2.1 },
    { y: 0.92, w: 0.052, d: 0.055, p: 2.1 }
  ], 12, skin);
  upper.add(neck);

  // ---- head ---------------------------------------------------------------
  // Pivot at the neck base, world 1.86. The chin, jawline and brow ridge are
  // SECTIONS OF THE SKULL LOFT now - the glued chin ball and brow ball are
  // gone. The underside of the jaw slopes from the chin point back over the
  // throat, so there is skin (not void) when seen from below.
  const head = new T.Group(); head.position.y = 0.88; upper.add(head);
  head.add(loftY(T, [
    { y: 0.008, w: 0.026, d: 0.030, z: 0.052, p: 2.0 },  // chin point, forward
    { y: 0.022, w: 0.048, d: 0.052, z: 0.030, p: 2.1 },  // jaw underside sloping back
    { y: 0.045, w: 0.066, d: 0.078, z: 0.012, p: 2.1 },  // jawline
    { y: 0.085, w: 0.088, d: 0.100, p: 2.2 },            // cheekbones
    { y: 0.130, w: 0.098, d: 0.108, z: 0.004, p: 2.2 },  // under the brow
    { y: 0.155, w: 0.104, d: 0.116, z: 0.010, p: 2.3 },  // BROW RIDGE, pushed forward
    { y: 0.185, w: 0.106, d: 0.114, z: 0.004, p: 2.3 },  // forehead settling back
    { y: 0.235, w: 0.108, d: 0.118, p: 2.4 },            // cranium
    { y: 0.300, w: 0.088, d: 0.098, p: 2.2 },            // crown curve
    { y: 0.340, w: 0.030, d: 0.036, p: 2.0 }             // crown
  ], 14, skin));
  // nose: a narrow bridge wedge swept OUT of the face, not a ball on it.
  // Root buried between the eyes, tip small; same skin, smooth shaded.
  const nose = sweep(T, [
    { at: [0, 0.132, 0.086], w: 0.016, d: 0.010, p: 2.2 },
    { at: [0, 0.116, 0.104], w: 0.014, d: 0.011, p: 2.2 },
    { at: [0, 0.102, 0.113], w: 0.017, d: 0.012, p: 2.3 }
  ], 8, skin);
  head.add(nose);
  const eyeM = new T.MeshStandardMaterial({ color: 0x1c1713, roughness: 0.35, metalness: 0 });
  for (const sd of [-1, 1]) {
    const eye = sph(0.013, eyeM, 1.3, 1, 0.55, 8);
    eye.position.set(sd * 0.040, 0.128, 0.093); head.add(eye);
    // eyebrow: a thin strip of hair lying flat against the brow ridge just
    // over each eye, tilted with the forehead slope and angled a touch - a
    // brow line, not an oval stuck on
    const brow = box(0.036, 0.0065, 0.008, hairM);
    brow.position.set(sd * 0.041, 0.141, 0.112);
    brow.rotation.set(-0.30, 0, sd * 0.10);
    head.add(brow);
    const ear = sph(0.020, skin, 0.6, 1.15, 0.85, 8);
    ear.position.set(sd * 0.100, 0.115, -0.012); head.add(ear);
  }
  const mouth = box(0.032, 0.004, 0.006, new T.MeshStandardMaterial({ color: 0xa5745c, roughness: 0.9 }));
  mouth.position.set(0, 0.050, 0.094); head.add(mouth);
  // hair: one shaped upright shell, 18 segments so the hairline reads as a
  // line instead of a staircase, everywhere proud of the skull so the scalp
  // can never poke through (pitching the loft back to fake a nape did
  // exactly that - the crown showed through and read as mange). The low back
  // taper comes from a separate nape wedge hugging the back of the skull.
  const hair = loftY(T, [
    { y: 0.150, w: 0.108, d: 0.117, z: -0.012, p: 2.45 },  // hairline, brows clear below
    { y: 0.185, w: 0.114, d: 0.125, z: -0.006, p: 2.5 },
    { y: 0.230, w: 0.116, d: 0.126, z: -0.002, p: 2.45 },  // volume over the cranium
    { y: 0.285, w: 0.103, d: 0.112, z: 0.002, p: 2.35 },
    { y: 0.335, w: 0.068, d: 0.078, z: 0.004, p: 2.2 },
    { y: 0.358, w: 0.024, d: 0.030, z: 0.005, p: 2.1 }     // rounded crown, no spike
  ], 18, hairM);
  head.add(hair);
  const nape = loftY(T, [
    { y: 0.055, w: 0.062, d: 0.030, z: -0.078, p: 2.4 },   // tapers in above the collar
    { y: 0.110, w: 0.084, d: 0.040, z: -0.070, p: 2.5 },
    { y: 0.160, w: 0.100, d: 0.052, z: -0.058, p: 2.5 }    // disappears under the main mass
  ], 12, hairM);
  head.add(nape);

  // ---- arms ---------------------------------------------------------------
  // One sleeve surface per arm whose top is a DOME CENTERED ON THE PIVOT, so
  // any swing angle shows the same rounded shoulder and no seam can open.
  // The deltoid bulge is in the same loft. The dome tucks against the
  // widened tunic shelf; the crease where they meet is a real garment line.
  // Below the sleeve hem (cuff roll), one skin loft to the wrist with the
  // elbow drift and forearm peak baked in, its top capped INSIDE the sleeve.
  // The dome stays LOW: its top sits barely above the pivot and leans in
  // toward the trap, so the shoulder line runs neck -> trap -> deltoid in one
  // slope instead of humping up into a puffed sleeve. The widened tunic shelf
  // folds over the dome's inner quarter and hides the meeting line.
  //
  // v6: the arm has a real ELBOW. The upper arm ends in a dome centered on
  // the elbow pivot and the forearm begins as one, so the joint is a pair of
  // nested spheres about the same point - it can bend to a right angle
  // without opening, same trick as the shoulder. The forearm is authored
  // STRAIGHT down its own local axis (the old baked forward drift is now a
  // small default rotation on the joint), so the geometry stays honest at
  // any bend.
  const armGeo = (mirror) => {
    const arm = new T.Group();
    const sleeve = loftY(T, [
      { y: 0.034, w: 0.030, d: 0.036, x: mirror * -0.014, p: 2.3 },  // cap top, leaning into the trap
      { y: 0.022, w: 0.056, d: 0.060, x: mirror * -0.008, p: 2.4 },
      { y: 0.000, w: 0.074, d: 0.078, p: 2.4 },              // dome equator at the pivot
      { y: -0.055, w: 0.082, d: 0.084, p: 2.4 },             // deltoid bulge, part of the SAME surface
      { y: -0.120, w: 0.067, d: 0.068, p: 2.3 },
      { y: -0.195, w: 0.056, d: 0.056, p: 2.3 },
      { y: -0.225, w: 0.053, d: 0.053, p: 2.3 }              // hem
    ], 14, cloth);
    arm.add(sleeve);
    const cuffRoll = new T.Mesh(new T.TorusGeometry(0.052, 0.010, 6, 12), cloth);
    cuffRoll.rotation.x = Math.PI / 2; cuffRoll.position.y = -0.225; cuffRoll.castShadow = true;
    arm.add(cuffRoll);
    // upper arm skin: out of the sleeve, ending in a dome ON the elbow pivot
    const upperSkin = loftY(T, [
      { y: -0.170, w: 0.049, d: 0.049, p: 2.2 },              // capped inside the sleeve
      { y: -0.245, w: 0.047, d: 0.049, p: 2.2 },
      { y: -0.276, w: 0.043, d: 0.046, p: 2.2, z: 0.004 },
      { y: -0.298, w: 0.036, d: 0.039, p: 2.2, z: 0.008 },    // elbow dome
      { y: -0.318, w: 0.024, d: 0.027, p: 2.1, z: 0.010 }
    ], 12, skin);
    arm.add(upperSkin);
    // ELBOW: the forearm hangs from here. Anatomical pivot, world y 0.46.
    const elbow = new T.Group(); elbow.position.set(0, -0.295, 0.012); arm.add(elbow);
    const foreSkin = loftY(T, [
      { y: 0.022, w: 0.026, d: 0.029, p: 2.1 },               // dome nested in the upper arm's
      { y: -0.008, w: 0.040, d: 0.044, p: 2.2 },
      { y: -0.065, w: 0.049, d: 0.051, p: 2.2 },              // forearm peak: widest BELOW the elbow
      { y: -0.185, w: 0.036, d: 0.037, p: 2.2 },
      { y: -0.290, w: 0.028, d: 0.030, p: 2.1 }               // wrist, reaching INTO the palm
    ], 12, skin);
    elbow.add(foreSkin);
    arm.elbow = elbow;
    return arm;
  };
  const armR = armGeo(-1); armR.position.set(-0.295, 0.755, 0); upper.add(armR);
  const armL = armGeo(1);  armL.position.set(0.295, 0.755, 0); upper.add(armL);
  const elbowR = armR.elbow, elbowL = armL.elbow;
  // the old baked elbow drift, now a joint default the animation adds to
  elbowR.rotation.x = -0.10; elbowL.rotation.x = -0.10;

  // Hands: palm loft, curled finger mass, thumb. Parented to the FOREARM
  // now, so a bent elbow carries the hand (and everything gripped in it).
  // The right fist stays the weapon grip origin; at the default joint pose
  // it sits where it always did, so every weapon still sits right.
  const handAt = (elbow, side, curl) => {
    const hand = new T.Group(); hand.position.set(0, -0.305, 0.018); elbow.add(hand);
    const palm = loftY(T, [
      { y: 0.032, w: 0.029, d: 0.034, p: 2.3 },   // overlaps up into the wrist: no gap ring
      { y: -0.045, w: 0.036, d: 0.040, p: 2.6 },
      { y: -0.075, w: 0.033, d: 0.036, p: 2.4 }
    ], 10, skin);
    hand.add(palm);
    const fing = loftY(T, [
      { y: -0.070, w: 0.032, d: 0.030, p: 2.8 },
      { y: -0.105, w: 0.030, d: 0.026, p: 2.8, z: 0.012 * curl },
      { y: -0.130, w: 0.026, d: 0.020, p: 2.6, z: 0.030 * curl }
    ], 10, skin);
    hand.add(fing);
    const thumb = sph(0.013, skin, 1, 1.55, 1, 8);
    thumb.position.set(0.026 * side, -0.052, 0.030);
    thumb.rotation.set(0.35, 0, 0.30 * -side);
    hand.add(thumb);
    return hand;
  };
  const hand = handAt(elbowR, -1, 1.0);     // weapon fist
  const handL = handAt(elbowL, 1, 0.45);    // relaxed

  // ---- legs ---------------------------------------------------------------
  // Trouser loft: hip dome centered on the pivot (born inside the pelvis, so
  // the hip can never open), thigh taper, KNEE SHAPED IN THE LOFT, tucked
  // below the knee. Then the boot as ONE SWEEP: cuff over the trouser, calf,
  // around the ankle corner and forward into a real foot with a heel and a
  // rising toe box. Sole is a separate slab - a real boot's sole is - and
  // the sole plane sits at world 0.015 so the foot STANDS ON the ground
  // instead of reaching under it, which is what kept eating v4's feet.
  // v6: the leg has a real KNEE. Thigh ends in a trouser dome centered on
  // the knee pivot; the shin group (boot and sole included) starts as one
  // nested inside it. Flexion never opens the joint, and the knee reads as
  // a knee because the shin actually swings back in the stride.
  const legGeo = () => {
    const leg = new T.Group();
    const thigh = loftY(T, [
      { y: 0.085, w: 0.030, d: 0.034, p: 2.3 },              // dome top, inside the pelvis
      { y: 0.055, w: 0.078, d: 0.086, p: 2.4 },
      { y: 0.000, w: 0.098, d: 0.108, p: 2.4 },              // dome equator at the pivot
      { y: -0.14, w: 0.086, d: 0.093, p: 2.3, z: 0.006 },
      { y: -0.30, w: 0.072, d: 0.078, p: 2.3, z: 0.010 },
      { y: -0.375, w: 0.064, d: 0.070, p: 2.3, z: 0.012 },   // approaching the knee
      { y: -0.412, w: 0.056, d: 0.062, p: 2.3, z: 0.014 },   // KNEE dome on the pivot
      { y: -0.442, w: 0.042, d: 0.048, p: 2.2, z: 0.012 }
    ], 12, pants);
    leg.add(thigh);
    const knee = new T.Group(); knee.position.set(0, -0.415, 0.012); leg.add(knee);
    // trouser continues INSIDE the boot from the knee dome down
    const shinTrouser = loftY(T, [
      { y: 0.024, w: 0.040, d: 0.046, p: 2.2 },              // nested in the thigh's knee dome
      { y: -0.005, w: 0.054, d: 0.059, p: 2.3 },
      { y: -0.055, w: 0.055, d: 0.060, p: 2.3 }              // tucked into the boot cuff
    ], 12, pants);
    knee.add(shinTrouser);
    leg.knee = knee;
    // Boot: shin to toe as one surface. w is half-width throughout; d is
    // half-depth on the shin and becomes half-HEIGHT as the spine turns
    // forward at the ankle. Heel comes from the spine kinking back before the
    // turn, and every foot section's UNDERSIDE sits on the same plane
    // (y = -0.985, world 0.035) so the whole foot stands flat on the sole -
    // v5's first pass had the midfoot digging through it and the toe floating.
    // Boot sections are in KNEE space now (leg space shifted by the pivot),
    // so the whole boot swings with the shin.
    const boot = sweep(T, [
      // The cuff FLARES: its lip is clearly wider than the trouser leg above
      // it (0.077 against 0.058), so the leg reads as going INTO the boot
      // instead of the boot being painted on. Leg armor will cover this line
      // later; the flare stays subtle for that reason.
      { at: [0, -0.010, -0.006], w: 0.077, d: 0.082, p: 2.35 },  // flared lip
      { at: [0, -0.040, -0.008], w: 0.070, d: 0.075, p: 2.3 },   // cuff settling in
      { at: [0, -0.145, -0.014], w: 0.063, d: 0.069, p: 2.3 },   // calf peak, upper third
      { at: [0, -0.305, -0.018], w: 0.046, d: 0.051, p: 2.2 },
      { at: [0, -0.430, -0.022], w: 0.040, d: 0.045, p: 2.2 },   // ankle
      { at: [0, -0.485, -0.030], w: 0.041, d: 0.047, p: 2.3 },   // front-of-ankle bridge
      { at: [0, -0.508, -0.042], w: 0.044, d: 0.062, p: 2.4 },   // heel, kicked back behind the shin
      { at: [0, -0.534, 0.008], w: 0.045, d: 0.036, p: 2.5 },    // instep
      { at: [0, -0.540, 0.073], w: 0.048, d: 0.030, p: 2.6 },    // midfoot
      { at: [0, -0.544, 0.133], w: 0.046, d: 0.026, p: 2.6 },    // toe box
      { at: [0, -0.554, 0.173], w: 0.036, d: 0.015, p: 2.4 }     // toe
    ], 12, leather);
    knee.add(boot);
    // Sole: ONE extruded outline that follows the foot - rounded heel,
    // waist, wider at the ball, rounded toe - with a few millimetres of
    // welt standing proud of the leather, the way a stitched medieval
    // turnshoe sole actually reads. Kevin's note on the box version: "the
    // sole right now is just a rectangular block". Plan view is drawn in
    // XY (x width, y forward), extruded downward after the rotate.
    {
      const so = new T.Shape();
      so.moveTo(0, -0.078);                                  // heel, centre back
      so.quadraticCurveTo(0.044, -0.076, 0.046, -0.040);     // round heel corner
      so.quadraticCurveTo(0.047, 0.010, 0.052, 0.075);       // waist into the ball
      so.quadraticCurveTo(0.055, 0.120, 0.049, 0.160);       // ball to toe box
      so.quadraticCurveTo(0.043, 0.196, 0, 0.200);           // rounded toe
      so.quadraticCurveTo(-0.043, 0.196, -0.049, 0.160);
      so.quadraticCurveTo(-0.055, 0.120, -0.052, 0.075);
      so.quadraticCurveTo(-0.047, 0.010, -0.046, -0.040);
      so.quadraticCurveTo(-0.044, -0.076, 0, -0.078);
      const sg = new T.ExtrudeGeometry(so, { depth: 0.018, bevelEnabled: false });
      sg.rotateX(Math.PI / 2);   // plan-y becomes forward z, thickness extrudes down
      const sole = new T.Mesh(sg, dark);
      sole.castShadow = true;
      sole.position.set(0, -0.570, -0.012);   // knee space
      knee.add(sole);
    }
    return leg;
  };
  const legR = legGeo(); legR.position.set(-0.122, 1.02, 0); body.add(legR);
  const legL = legGeo(); legL.position.set(0.122, 1.02, 0); body.add(legL);
  const kneeR = legR.knee, kneeL = legL.knee;
  // the old baked knee bend, now a joint default the stride adds to
  kneeR.rotation.x = 0.06; kneeL.rotation.x = 0.06;

  // ---- gear: every armor piece, fitted OVER the body ----------------------
  const gear = { list: [] };
  const gearAdd = (parent, mesh) => { parent.add(mesh); gear.list.push(mesh); return mesh; };

  // breastplate: follows the tunic loft 0.02 proud, chest to trap
  const plate = gearAdd(chest, loftY(T, [
    { y: 0.30, w: 0.185, d: 0.138, p: 2.5 },
    { y: 0.46, w: 0.190, d: 0.140, p: 2.5 },
    { y: 0.60, w: 0.210, d: 0.150, p: 2.6 },
    { y: 0.69, w: 0.248, d: 0.150, p: 2.7 },
    { y: 0.745, w: 0.238, d: 0.140, p: 2.7 },
    { y: 0.795, w: 0.150, d: 0.112, p: 2.4 },
    { y: 0.825, w: 0.104, d: 0.100, p: 2.2 }
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

  // pauldrons: curved plate CAPS that hug the new sleeve dome, not balls.
  // Each is a shallow loft shell seated on the dome's curvature, tilted with
  // the trap slope; a second smaller lame overlaps below on the outside.
  for (const [arm, sd] of [[armR, -1], [armL, 1]]) {
    const p1 = gearAdd(arm, loftY(T, [
      { y: 0.096, w: 0.030, d: 0.036, p: 2.2 },
      { y: 0.070, w: 0.072, d: 0.080, p: 2.5 },
      { y: 0.022, w: 0.096, d: 0.098, p: 2.6 },
      { y: -0.030, w: 0.098, d: 0.096, p: 2.6 },
      { y: -0.062, w: 0.090, d: 0.090, p: 2.4 }
    ], 12, steel));
    p1.rotation.z = sd * -0.10;
    const p2 = gearAdd(arm, loftY(T, [
      { y: -0.040, w: 0.088, d: 0.090, p: 2.5 },
      { y: -0.085, w: 0.082, d: 0.084, p: 2.4 },
      { y: -0.112, w: 0.070, d: 0.072, p: 2.3 }
    ], 12, steel));
    p2.rotation.z = sd * -0.06;
    const pRim = gearAdd(arm, cyl(0.072, 0.078, 0.022, trim, -0.118, 12));
    // bracer wrapping the forearm peak down to the wrist - on the FOREARM,
    // so it bends with the elbow
    const bracer = gearAdd(arm.elbow, loftY(T, [
      { y: -0.035, w: 0.058, d: 0.060, p: 2.4 },
      { y: -0.155, w: 0.046, d: 0.047, p: 2.4 },
      { y: -0.250, w: 0.038, d: 0.040, p: 2.3 }
    ], 12, steel));
    const cuff = gearAdd(arm.elbow, cyl(0.043, 0.047, 0.030, trim, -0.257, 10)); cuff.position.z = 0.018;
  }

  // greaves + sabaton caps hugging the boot - on the SHIN, in knee space
  for (const leg of [legR, legL]) {
    gearAdd(leg.knee, loftY(T, [
      { y: -0.035, w: 0.072, d: 0.076, p: 2.4 },
      { y: -0.185, w: 0.066, d: 0.072, p: 2.4 },
      { y: -0.345, w: 0.048, d: 0.053, p: 2.3 }
    ], 12, steel));
    const sab = gearAdd(leg.knee, sweep(T, [
      // first ring hugs the boot tight so the open end's cap is a sliver -
      // a loose ring left a bright steel disc gleaming at the ankle in low sun
      { at: [0, -0.480, -0.024], w: 0.0435, d: 0.0475, p: 2.4 },
      { at: [0, -0.530, 0.018], w: 0.052, d: 0.034, p: 2.6 },
      { at: [0, -0.537, 0.088], w: 0.054, d: 0.028, p: 2.6 },
      { at: [0, -0.545, 0.138], w: 0.046, d: 0.020, p: 2.5 }
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
  // plume: stiff comb then a horsehair tail. P.crest stays parented to head.
  const crest = new T.Group(); crest.position.set(0, 0.34, -0.01); head.add(crest);
  gear.list.push(crest);
  for (let i = 0; i < 4; i++) {
    const fin = new T.Mesh(new T.BoxGeometry(0.022, 0.105 - i * 0.016, 0.085), cloth);
    fin.position.set(0, 0.048 - i * 0.014, 0.030 - i * 0.062); fin.castShadow = true; crest.add(fin);
  }
  for (let i = 0; i < 6; i++) {
    const t = i / 5;
    // segments overlap (0.125 spacing against 0.15 length) so the tail is a
    // tail, not a dotted line - the old spacing showed daylight between them
    const seg = new T.Mesh(new T.CylinderGeometry(0.042 - t * 0.024, 0.036 - t * 0.020, 0.15, 5), cloth);
    seg.position.set(0, 0.005 - t * t * 0.155, -0.145 - t * 0.125);
    seg.rotation.x = 1.05 + t * 0.72; seg.castShadow = true; crest.add(seg);
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
    elbowR, elbowL, kneeR, kneeL,
    hand, handL, crest, capePiv, gear,
    mats: { steel, cloth, trim, skin, pants, leather, dark },
    box, cyl, sph
  };
}


// ---- weapons ---------------------------------------------------------------
// Grip rotations and rest offsets are tuned against animate()'s swing arcs
// and are unchanged from v3/v4. What changed in v5 is the scimitar BLADE:
// one continuous swept body along the same curve the old stacked boxes
// followed (len 0.2 per station, +0.13 rad each), so every swing arc and the
// bladeTip trail anchor land exactly where they always did.
export function buildWeaponSet(T, rig) {
  const { armR, armL, elbowR, elbowL, upper, hand, handL, box, cyl, sph, g } = rig;
  const steel = rig.mats.steel, cloth = rig.mats.cloth, trim = rig.mats.trim, dark = rig.mats.dark, leather = rig.mats.leather;

  const bladeMat = new T.MeshStandardMaterial({ color: 0xccd4dc, roughness: 0.34, metalness: 0.78 });
  const edgeMat  = new T.MeshStandardMaterial({ color: 0xf2f6fa, roughness: 0.22, metalness: 0.85 });
  const sword = new T.Group();
  // The spine: same march as the v4 boxes. Half-width tapers 0.085 -> point;
  // cross-section is a flattened lens (low p) so the blade has a spine and
  // two faces instead of four box walls.
  const spine = [];
  {
    let bx = 0, by = 0.10, ba = 0;
    for (let i = 0; i <= 6; i++) {
      spine.push([bx, by, ba]);
      bx += -Math.sin(ba) * 0.2; by += Math.cos(ba) * 0.2; ba += 0.13;
    }
  }
  const bladeSecs = spine.map((s, i) => {
    const t = i / 6;
    return { at: [s[0], s[1], 0], w: 0.085 - t * 0.030, d: 0.0165 - t * 0.004, p: 1.55 };
  });
  // the point: carry the curve on and converge
  const last = spine[6];
  bladeSecs.push({ at: [last[0] - Math.sin(last[2]) * 0.14, last[1] + Math.cos(last[2]) * 0.14, 0], w: 0.030, d: 0.009, p: 1.6 });
  bladeSecs.push({ at: [last[0] - Math.sin(last[2]) * 0.24, last[1] + Math.cos(last[2]) * 0.24, 0], w: 0.004, d: 0.003, p: 1.8 });
  sword.add(sweep(T, bladeSecs, 12, bladeMat));
  // edge highlight: a thin continuous sweep along the OUTER (convex, +x)
  // edge of the curve, replacing v4's per-segment edge boxes
  const edgeSecs = spine.map((s, i) => {
    const t = i / 6;
    const w = 0.085 - t * 0.030;
    const off = w - 0.010;
    return { at: [s[0] + Math.cos(s[2]) * off, s[1] + Math.sin(s[2]) * off, 0], w: 0.011, d: 0.011, p: 1.8 };
  });
  edgeSecs.push({ at: [last[0] - Math.sin(last[2]) * 0.13 + Math.cos(last[2]) * 0.018, last[1] + Math.cos(last[2]) * 0.13 + Math.sin(last[2]) * 0.018, 0], w: 0.005, d: 0.006, p: 1.8 });
  sword.add(sweep(T, edgeSecs, 8, edgeMat));
  // bladeTip: same anchor formula as v4 so trails don't move
  const bladeTip = new T.Object3D();
  { let bx = 0, by = 0.2, ba = 0; for (let i = 0; i < 6; i++) { bx += -Math.sin(ba) * 0.2; by += Math.cos(ba) * 0.2; ba += 0.13; } bladeTip.position.set(bx, by + 0.16, 0); }
  sword.add(bladeTip);
  // Crossguard: one swept bar that dips at the centre and curves UP into
  // rounded knob ends - the classic upswept scimitar guard - plus a collar
  // hugging the blade root. Kevin's note on the box-and-cubes version: the
  // quillons "still look really blocky and don't match the high quality
  // blade". Same sweep machinery as the blade, so they match by construction.
  const guardBar = sweep(T, [
    { at: [-0.215, 0.122, 0], w: 0.013, d: 0.013, p: 2.2 },   // knob end
    { at: [-0.195, 0.104, 0], w: 0.024, d: 0.020, p: 2.2 },
    { at: [-0.105, 0.072, 0], w: 0.027, d: 0.023, p: 2.3 },
    { at: [0, 0.062, 0], w: 0.031, d: 0.027, p: 2.4 },        // dip at the centre
    { at: [0.105, 0.072, 0], w: 0.027, d: 0.023, p: 2.3 },
    { at: [0.195, 0.104, 0], w: 0.024, d: 0.020, p: 2.2 },
    { at: [0.215, 0.122, 0], w: 0.013, d: 0.013, p: 2.2 }     // knob end
  ], 10, trim);
  sword.add(guardBar);
  const ferrule = loftY(T, [
    { y: 0.078, w: 0.094, d: 0.026, p: 2.0 },                 // seats over the blade root
    { y: 0.130, w: 0.068, d: 0.019, p: 2.0 }
  ], 10, trim);
  sword.add(ferrule);
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

  // ---- the bow, from scratch ----------------------------------------------
  // A strung recurve, built the way one is actually shaped. Local frame:
  // +Y up the riser, +Z toward the TARGET, string side -Z. The numbers:
  // 1.17 tall tip to tip; limbs sweep BACK toward the archer as they leave
  // the riser and the tips hook FORWARD - that reversed hook is what makes
  // it a recurve; the string runs dead straight between the nock grooves at
  // z = -0.148, which puts a real brace height between grip and string. The
  // old bow was a torus with a stick through it, held sideways through the
  // body; nothing of it survives.
  const bowWood = new T.MeshStandardMaterial({ color: 0x4a3420, roughness: 0.62, metalness: 0 });
  const bowHorn = new T.MeshStandardMaterial({ color: 0x8a6a3c, roughness: 0.5, metalness: 0.05 });
  const bowStringM = new T.MeshStandardMaterial({ color: 0xd8d2c0, roughness: 0.8 });
  const bow = new T.Group();
  // riser: pocketed ends, thin waist, leather-wrapped grip, arrow rest
  bow.add(loftY(T, [
    { y: -0.185, w: 0.021, d: 0.032, z: -0.002, p: 2.2 },   // lower limb pocket
    { y: -0.095, w: 0.017, d: 0.027, z: 0.004, p: 2.2 },
    { y: -0.030, w: 0.0155, d: 0.024, z: 0.006, p: 2.2 },   // grip waist
    { y: 0.045, w: 0.016, d: 0.025, z: 0.005, p: 2.2 },
    { y: 0.115, w: 0.018, d: 0.028, z: 0.002, p: 2.2 },
    { y: 0.185, w: 0.021, d: 0.032, z: -0.002, p: 2.2 }     // upper limb pocket
  ], 10, bowWood));
  const gripWrap = loftY(T, [
    { y: -0.062, w: 0.0185, d: 0.027, z: 0.006, p: 2.3 },
    { y: -0.015, w: 0.020, d: 0.029, z: 0.006, p: 2.3 },
    { y: 0.030, w: 0.0185, d: 0.027, z: 0.006, p: 2.3 }
  ], 10, leather);
  bow.add(gripWrap);
  const rest = box(0.012, 0.008, 0.016, bowHorn); rest.position.set(0.02, 0.052, 0.004); bow.add(rest);
  // limbs: one sweep each, flat lens section tapering to the tip, with a
  // horn lamination sweep on the belly for the two-tone read
  const limbAt = (sgn) => {
    const spine = [
      [0, 0.170 * sgn, 0.004], [0, 0.30 * sgn, -0.042], [0, 0.42 * sgn, -0.102],
      [0, 0.50 * sgn, -0.148], [0, 0.552 * sgn, -0.152], [0, 0.585 * sgn, -0.126]
    ];
    const secs = spine.map((at, i) => {
      const t = i / 5;
      return { at, w: 0.023 - t * 0.013, d: 0.010 - t * 0.0045, p: 2.6 };
    });
    bow.add(sweep(T, secs, 8, bowWood));
    const belly = spine.slice(0, 5).map((at, i) => {
      const t = i / 4;
      return { at: [at[0], at[1], at[2] - 0.006], w: 0.017 - t * 0.009, d: 0.004, p: 2.4 };
    });
    bow.add(sweep(T, belly, 8, bowHorn));
    const nock = cyl(0.006, 0.008, 0.02, trim, 0, 6);
    nock.position.set(0, 0.572 * sgn, -0.140); nock.rotation.x = sgn * -0.9;
    bow.add(nock);
  };
  limbAt(1); limbAt(-1);
  // string: two segments meeting at the nocking point, re-aimed by setDraw
  // so drawing pulls a clean V toward the archer. Unit cylinders scaled to
  // length, endpoint to endpoint - never composed angles.
  const NOCK_T = new T.Vector3(0, 0.572, -0.148);
  const NOCK_B = new T.Vector3(0, -0.572, -0.148);
  const strTop = new T.Mesh(new T.CylinderGeometry(0.004, 0.004, 1, 4, 1), bowStringM);
  const strBot = strTop.clone();
  bow.add(strTop); bow.add(strBot);
  // nocked arrow, shown by the game only while drawing
  const arrow = new T.Group();
  const arrowShaft = new T.Mesh(new T.CylinderGeometry(0.0055, 0.0055, 0.60, 5), bowWood);
  arrowShaft.rotation.x = Math.PI / 2; arrowShaft.position.z = 0.30; arrow.add(arrowShaft);
  const headA = new T.Mesh(new T.ConeGeometry(0.013, 0.05, 5), steel);
  headA.rotation.x = Math.PI / 2; headA.position.z = 0.615; arrow.add(headA);
  for (const fr of [0, 2.1, 4.2]) {
    const f = box(0.002, 0.022, 0.055, cloth); f.position.set(0, 0.012, 0.05);
    const fg = new T.Group(); fg.rotation.z = fr; fg.add(f); fg.position.z = 0.02; arrow.add(fg);
  }
  arrow.visible = false; bow.add(arrow);
  const aim = (mesh, a, b) => {
    const dir = new T.Vector3().subVectors(b, a);
    const len = dir.length();
    mesh.scale.set(1, len, 1);
    mesh.position.copy(a).addScaledVector(dir, 0.5);
    mesh.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), dir.normalize());
  };
  const bowSet = {
    arrow,
    // t: 0 at brace, 1 at full draw. The nocking point rides just below
    // centre, like a real nock, and the arrow tail follows it.
    setDraw(t) {
      const np = new T.Vector3(0, -0.015, -0.148 - Math.max(0, Math.min(1, t)) * 0.46);
      aim(strTop, NOCK_T, np);
      aim(strBot, np, NOCK_B);
      arrow.position.set(np.x, np.y + 0.006, np.z);
    }
  };
  bowSet.setDraw(0);
  // Held in the LEFT hand at IDENTITY: the game counter-rotates handL
  // against the arm chain (it already does this for the bow), so the fist's
  // world frame stays upright and the bow reads vertical in every pose -
  // exactly how a wrist works. Authoring any fixed tilt here instead is what
  // had the old bow lying through the body.
  bow.position.set(0, -0.055, 0.02);
  bow.rotation.set(0, 0, 0);
  bow.scale.setScalar(1.15);   // hero scale: 1.35 tip to tip
  bow.visible = false; handL.add(bow);
  // Slung copy for when the bow isn't drawn - diagonal across the back.
  const backBow = bow.clone();
  backBow.position.set(0.06, 0.34, -0.30);
  backBow.rotation.set(0.35, 0, 0.6);
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
  // cross, corner studs. Geometry unchanged; the CARRY changed. At rest it
  // now rides flat along the character's side like a slung heater: long axis
  // front-to-back, point aft, face out. animate() owns the live orientation;
  // the base transform here matches the game's rest pose so the lab and the
  // game show the same carry.
  const shield = new T.Group();
  // The plate is ONE extruded heater outline: straight top, sides easing in
  // through quadratic curves to a single point at the base. The old build
  // butted a 45-degree diamond against a square and the join read exactly
  // like that - "a diamond placed next to the square". One outline, no join.
  const heater = (mat, scale, thick) => {
    const w = 0.34 * scale, t = 0.46 * scale, tip = -0.64 * scale;
    const sh = new T.Shape();
    sh.moveTo(-w, t);
    sh.lineTo(w, t);
    sh.quadraticCurveTo(w * 1.03, t * 0.12, w * 0.85, -t * 0.38);
    sh.quadraticCurveTo(w * 0.52, tip * 0.80, 0, tip);
    sh.quadraticCurveTo(-w * 0.52, tip * 0.80, -w * 0.85, -t * 0.38);
    sh.quadraticCurveTo(-w * 1.03, t * 0.12, -w, t);
    const g2 = new T.ExtrudeGeometry(sh, { depth: thick, bevelEnabled: false });
    g2.rotateY(Math.PI / 2);   // face plane in y-z, thickness along +x
    const m = new T.Mesh(g2, mat); m.castShadow = true;
    return m;
  };
  const back = heater(dark, 1.0, 0.05); back.position.x = -0.025; shield.add(back);
  const sface = heater(steel, 0.93, 0.032); sface.position.x = -0.032; shield.add(sface);
  const topRim = box(0.065, 0.09, 0.7, trim, 0.44); shield.add(topRim);
  const crossV = box(0.05, 0.7, 0.11, cloth); crossV.position.x = -0.055; shield.add(crossV);
  const crossH = box(0.05, 0.11, 0.48, cloth); crossH.position.set(-0.055, 0.14, 0); shield.add(crossH);
  const boss = new T.Mesh(new T.SphereGeometry(0.12, 8, 6), trim); boss.position.set(-0.09, 0.14, 0); boss.castShadow = true; shield.add(boss);
  for (const [yy, zz] of [[0.38, 0.24], [0.38, -0.24], [-0.12, 0.24], [-0.12, -0.24]]) {
    const stud = box(0.06, 0.06, 0.06, trim); stud.position.set(-0.06, yy, zz); shield.add(stud);
  }
  // v6 carry: the shield is strapped to the FOREARM. With the carry pose
  // (shoulder out a touch, elbow near a right angle) the forearm runs along
  // the shield's back and the fist sits at the grip, which is how a heater
  // is actually held. In elbow space: long axis along the forearm (top rim
  // toward the hand, so the point trails aft of the elbow), face outboard.
  // Every angle here is reviewed on the lab's shieldside camera, not derived
  // on paper - deriving it on paper shipped the point facing forward once.
  shield.position.set(0.102, -0.351, -0.157); shield.rotation.set(-1.220, 0.207, 3.131); shield.scale.setScalar(0.86); elbowL.add(shield);

  const ward = new T.Mesh(new T.SphereGeometry(1.15, 16, 12), new T.MeshBasicMaterial({ color: 0x6fb8ff, transparent: true, opacity: 0.16, side: T.DoubleSide }));
  ward.position.y = 1.1; ward.visible = false; g.add(ward);

  const frostShell = new T.Mesh(new T.IcosahedronGeometry(1.05, 1), new T.MeshBasicMaterial({ color: 0x9fdcff, transparent: true, opacity: 0.3, wireframe: true }));
  frostShell.position.y = 1.05; frostShell.visible = false; g.add(frostShell);

  return { sword, staff, bow, backBow, bowSet, shield, ward, frostShell, orb, pick,
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
      elbowR: rig.elbowR, elbowL: rig.elbowL, kneeR: rig.kneeR, kneeL: rig.kneeL,
      hand: rig.hand, handL: rig.handL,
      crest: rig.crest, capePiv: rig.capePiv,
      sword: wep.sword, staff: wep.staff, bow: wep.bow, backBow: wep.backBow,
      bowSet: wep.bowSet,
      shield: wep.shield, ward: wep.ward, frostShell: wep.frostShell,
      orb: wep.orb, pick: wep.pick, axe: wep.axe, great: wep.great,
      greatTip: wep.greatTip, bladeTip: wep.bladeTip
    }
  };
}
