// GRIM WORLD: the blacksmith's anvil.
//
// Replaces three primitives (a box, a box and a cone) with a real London
// pattern anvil on an oak stump.
//
// The measurements come from a real 100 lb London pattern anvil: 20 inches
// long, 8.5 inches tall, a 9 by 9 inch footprint, and a face 12 inches long by
// FOUR inches wide. That last number is the one that matters. The anvil this
// replaces had a face 1.0 m long and 0.34 m wide, so its face was three times
// too wide for its length, and that single proportion is why it read as a
// chunky block rather than an anvil. Everything else follows from getting it
// right: a narrow face demands a narrow waist, and a narrow waist is what makes
// the silhouette recognisable from across the camp.
//
// Scaled here to about a 150 lb smithy anvil, which is what a working forge
// would have, and stood on a stump so the face lands at 0.76 m. That is
// knuckle height on a 1.8 m smith, which is where a real anvil is set: high
// enough to hammer without stooping, low enough to put your shoulder into it.
//
// The five things a naive anvil model misses, in the order a player notices:
//
//   1. THE WAIST. The body pinches hard between the base and the face. That
//      hourglass is the anvil silhouette; without it you have a lump.
//   2. THE STEP. A flat ledge between horn and face, sitting a few centimetres
//      LOWER than the face, used for cutting. It breaks the top line in a way
//      that reads as a tool rather than a shape.
//   3. THE HORN IS ROUND AND THE FACE IS SQUARE, and one becomes the other.
//      Modelled as a single loft whose superellipse exponent runs from 2 at the
//      tip to 10 at the face, so the transition is a surface, not a joint.
//   4. THE HOLES. A square hardy hole and a round pritchel hole near the heel.
//      Small, but their absence is why a model reads as a prop.
//   5. WEAR. The face is polished bright where the hammer lands and dark at the
//      edges; the body is black forged scale. An anvil that is one uniform grey
//      is a new anvil, and nobody has ever seen one.
//
// Two materials, not one: steel and timber differ in metalness, and no amount
// of vertex colour fakes that. Two draw calls for the whole station.

import {
  rngFor, mergeParts, roughen, paintByPos, placed, loftRect, logBetween
} from './grim-kit.js';

export function makeAnvilKit(T, opt) {
  opt = opt || {};
  const kit = { T, mats: {}, lights: [] };

  // Forged iron: dark, fairly rough, genuinely metallic. Vertex colours carry
  // the polish on the face and the scale everywhere else.
  kit.mats.steel = new T.MeshStandardMaterial({
    vertexColors: true, roughness: 0.44, metalness: 0.62, flatShading: true
  });
  // Oak: the stump, the hammer haft, anything organic.
  kit.mats.timber = new T.MeshStandardMaterial({
    vertexColors: true, roughness: 0.93, metalness: 0.0, flatShading: true
  });

  // -------------------------------------------------------------------------
  // build
  // -------------------------------------------------------------------------
  // opt: { seed, scale, stump, tools, heightAt(x,z) }
  kit.build = function (o) {
    o = o || {};
    const S = o.scale || 1;
    const rnd = rngFor(o.seed === undefined ? 11 : o.seed);
    const root = new T.Group();
    const steelParts = [], woodParts = [];

    // The stump top, and therefore the whole anvil, sits here.
    const TOP = o.stump === false ? 0.0 : 0.50;

    // ---- colours ----------------------------------------------------------
    // Forged scale is not grey, it is a very dark blue-brown, and the polish on
    // a working face is warm rather than white. Painting both from position
    // means the wear follows the geometry: brightest along the centre line of
    // the face where every blow lands, falling away to the edges and the ends
    // that only ever get glancing work.
    const SCALE = [0.118, 0.111, 0.116];
    const POLISH = [0.63, 0.635, 0.655];
    const facePaint = (c, x, y, z) => {
      // how far up the object, and how far from the face's centre line
      const across = Math.min(1, Math.abs(z) / 0.058);
      const along = Math.max(0, Math.min(1, (x + 0.10) / 0.40));
      const top = Math.max(0, Math.min(1, (y - (TOP + 0.228)) / 0.028));
      // the hammer lands in the middle two thirds, not out at the heel
      const use = (1 - across * across * 0.85) * (0.35 + 0.65 * Math.sin(Math.PI * Math.min(1, along * 1.15)));
      const k = top * top * Math.max(0, use);
      const grain = 0.5 + 0.5 * Math.sin(x * 63 + z * 41);
      c.setRGB(
        SCALE[0] + (POLISH[0] - SCALE[0]) * k + grain * 0.012,
        SCALE[1] + (POLISH[1] - SCALE[1]) * k + grain * 0.012,
        SCALE[2] + (POLISH[2] - SCALE[2]) * k + grain * 0.014
      );
    };
    // The body never gets polished. Slight vertical streaking so a flat-shaded
    // slab is not one dead tone.
    const bodyPaint = (c, x, y, z) => {
      const streak = 0.5 + 0.5 * Math.sin(y * 47 + x * 19 + z * 23);
      const lift = Math.max(0, Math.min(1, (y - TOP) / 0.26)) * 0.035;
      c.setRGB(SCALE[0] + lift + streak * 0.020,
               SCALE[1] + lift + streak * 0.018,
               SCALE[2] + lift + streak * 0.022);
    };
    // The horn is worked on constantly, so its upper surface polishes up while
    // the underside stays black.
    const hornPaint = (c, x, y, z) => {
      const up = Math.max(0, Math.min(1, (y - (TOP + 0.205)) / 0.038));
      const k = up * up * 0.62;
      c.setRGB(SCALE[0] + (POLISH[0] - SCALE[0]) * k,
               SCALE[1] + (POLISH[1] - SCALE[1]) * k,
               SCALE[2] + (POLISH[2] - SCALE[2]) * k);
    };

    // ---- the horn, the step and the face, as ONE lofted surface -----------
    // A round horn bolted onto a square face is the single most common way an
    // anvil model goes wrong: you can see the joint. Here the superellipse
    // exponent runs 2 (a circle) at the tip through to 10 (a rounded rectangle)
    // at the face, so the round becomes the square along the length of one
    // continuous skin.
    //
    // The two sections at x = -0.175 are not a mistake. Repeating the position
    // with a different top height gives a VERTICAL WALL between them, which is
    // the cutting step. Interpolating it instead would give a ramp, and a ramp
    // reads as a mistake rather than a feature.
    const FACE_TOP = TOP + 0.255;
    const STEP_TOP = TOP + 0.212;
    // Sections read far better as top-and-bottom than as centre-and-half-height,
    // and the whole shape here is a matter of where surfaces sit.
    const sec = (at, hu, top, bot, p) =>
      ({ at, hu, hv: (top - bot) / 2, cv: (top + bot) / 2, p });

    // PROPORTION. The first build ran the face slab from TOP+0.140 up to
    // TOP+0.255, so 45 percent of the anvil's whole height was one rectangular
    // block and it read as a lump with a spike. A real anvil is roughly a fifth
    // face, three fifths waist, a fifth base. The face here is 0.057 deep out of
    // 0.255, and everything under it is free to pinch.
    const FACE_BOT = TOP + 0.198;
    const faceGeo = loftRect(T, 'x', [
      // The horn tapers in BOTH axes to a rounded point, and its top falls away
      // from the face rather than staying level. Held at a constant height it
      // came out as a duck bill.
      sec(-0.400, 0.010, TOP + 0.229, TOP + 0.209, 2.0),
      sec(-0.352, 0.024, TOP + 0.234, TOP + 0.198, 2.0),
      sec(-0.296, 0.036, TOP + 0.239, TOP + 0.188, 2.1),
      sec(-0.240, 0.045, TOP + 0.243, TOP + 0.180, 2.4),
      sec(-0.175, 0.052, TOP + 0.246, TOP + 0.174, 3.2),
      // The step: a flat ledge four centimetres below the face. Repeating
      // x = -0.175 makes the drop a vertical wall instead of a ramp.
      sec(-0.175, 0.052, STEP_TOP, TOP + 0.190, 6.0),
      sec(-0.100, 0.055, STEP_TOP + 0.001, TOP + 0.196, 7.0),
      // the face proper, and it is a PLATE, not a block
      sec(-0.100, 0.0575, FACE_TOP, FACE_BOT, 9.0),
      sec(0.060, 0.0585, FACE_TOP + 0.001, FACE_BOT, 10.0),
      sec(0.220, 0.0575, FACE_TOP, FACE_BOT + 0.002, 10.0),
      // the heel tapers a little and its far edge is eased
      sec(0.290, 0.0545, FACE_TOP - 0.001, FACE_BOT + 0.008, 8.0),
      sec(0.305, 0.0480, FACE_TOP - 0.007, FACE_BOT + 0.014, 5.0)
    ], 20, (c, x, y, z) => (x < -0.16 ? hornPaint : facePaint)(c, x, y, z));
    steelParts.push({ geo: faceGeo });

    // ---- the waist -------------------------------------------------------
    // Lofted along Y, from the underside of the face down to the base. The
    // pinch at 0.100 is the whole silhouette: it takes the body down to 0.090
    // half-width from 0.150 at the face, so the face visibly overhangs on every
    // side. Without that overhang an anvil is a lump with a horn stuck on, and
    // no amount of surface detail rescues it.
    const waistGeo = loftRect(T, 'y', [
      { at: FACE_BOT + 0.004, hu: 0.150, hv: 0.056, cu: 0.055, p: 8.0 },
      { at: TOP + 0.170, hu: 0.126, hv: 0.046, cu: 0.056, p: 6.0 },
      { at: TOP + 0.130, hu: 0.100, hv: 0.034, cu: 0.060, p: 4.4 },
      { at: TOP + 0.100, hu: 0.090, hv: 0.030, cu: 0.062, p: 4.0 },   // the waist
      { at: TOP + 0.075, hu: 0.098, hv: 0.038, cu: 0.060, p: 4.4 },
      { at: TOP + 0.048, hu: 0.122, hv: 0.062, cu: 0.056, p: 6.0 },
      { at: TOP + 0.030, hu: 0.142, hv: 0.090, cu: 0.052, p: 7.5 }
    ], 20, bodyPaint);
    steelParts.push({ geo: waistGeo });

    // ---- the base and its feet -------------------------------------------
    // A real anvil's base is a slab with four feet under it and a hollow
    // between them, which is why it rings. Four small blocks plus a slab reads
    // correctly and costs almost nothing.
    {
      const baseGeo = loftRect(T, 'y', [
        { at: TOP + 0.048, hu: 0.138, hv: 0.092, cu: 0.050, p: 7.5 },
        { at: TOP + 0.020, hu: 0.144, hv: 0.098, cu: 0.050, p: 9.0 },
        { at: TOP + 0.008, hu: 0.141, hv: 0.096, cu: 0.050, p: 9.0 }
      ], 16, bodyPaint);
      steelParts.push({ geo: baseGeo });
      for (const sx of [-1, 1]) {
        for (const sz of [-1, 1]) {
          const f = new T.BoxGeometry(0.052, 0.016, 0.046);
          paintByPos(T, f, bodyPaint);
          steelParts.push(placed(T, f, 0.050 + sx * 0.118, TOP + 0.008, sz * 0.074));
        }
      }
    }

    // ---- hardy and pritchel holes ----------------------------------------
    // Cutting real holes through the face costs a lot of triangles for
    // something a player sees from two metres. A dark inset sunk just below the
    // surface reads as a hole at every distance a player will ever be at, and
    // it is four faces instead of a boolean.
    {
      const hardy = new T.BoxGeometry(0.030, 0.030, 0.030);
      paintByPos(T, hardy, (c) => c.setRGB(0.016, 0.014, 0.015));
      steelParts.push(placed(T, hardy, 0.196, FACE_TOP - 0.014, 0, 0, 0.06, 0));
      const prit = new T.CylinderGeometry(0.011, 0.011, 0.030, 10);
      paintByPos(T, prit, (c) => c.setRGB(0.016, 0.014, 0.015));
      steelParts.push(placed(T, prit, 0.256, FACE_TOP - 0.014, 0));
    }

    // ---- the stump --------------------------------------------------------
    // An anvil on the bare ground is an anvil nobody can work at. The stump is
    // what puts the face at knuckle height, and it is also most of what makes
    // the station read as a place somebody works rather than an object sitting
    // in a field.
    if (o.stump !== false) {
      const OAK = [0.150, 0.104, 0.062];
      const BARK = [0.088, 0.066, 0.046];
      const stumpPaint = (c, x, y, z) => {
        const r = Math.hypot(x - 0.050, z);
        const rings = 0.5 + 0.5 * Math.sin(r * 96);
        const onTop = Math.max(0, Math.min(1, (y - (TOP - 0.030)) / 0.030));
        const bark = 0.5 + 0.5 * Math.sin(Math.atan2(x, z) * 26 + y * 31);
        // sawn end grain on top, rough bark down the sides
        const t = onTop;
        c.setRGB(
          BARK[0] + (OAK[0] - BARK[0]) * t + (t * rings - bark * (1 - t)) * 0.030,
          BARK[1] + (OAK[1] - BARK[1]) * t + (t * rings - bark * (1 - t)) * 0.022,
          BARK[2] + (OAK[2] - BARK[2]) * t + (t * rings - bark * (1 - t)) * 0.016
        );
        // scorched and stained where the anvil has sat for years
        const under = Math.max(0, 1 - Math.hypot(x - 0.05, z) / 0.175) * onTop;
        c.multiplyScalar(1 - under * 0.42);
      };
      const SX = 0.050;                       // the anvil's own centre in x
      const stump = new T.CylinderGeometry(0.205, 0.238, TOP + 0.10, 11, 3);
      roughen(T, stump, 0.052, 21, 1);
      paintByPos(T, stump, stumpPaint);
      // top lands exactly at TOP, so the anvil's feet sit ON it rather than in it
      woodParts.push(placed(T, stump, SX, TOP - (TOP + 0.10) / 2, 0, 0, rnd() * 3, 0));

      // An iron band round the top, because a stump that is hammered on for
      // twenty years splits without one.
      const band = new T.CylinderGeometry(0.212, 0.219, 0.030, 14, 1, true);
      paintByPos(T, band, (c) => c.setRGB(0.075, 0.070, 0.068));
      steelParts.push(placed(T, band, SX, TOP - 0.088, 0));

      // Wedges hammered under one side to level it. Nobody has ever found a
      // stump that stood flat on its own, and two small chocks say that.
      for (let i = 0; i < 3; i++) {
        const a = 2.1 + i * 1.9;
        const ch = new T.BoxGeometry(0.10, 0.036, 0.062);
        roughen(T, ch, 0.10, 60 + i, 1);
        paintByPos(T, ch, (c, x) => {
          const g2 = 0.5 + 0.5 * Math.sin(x * 71);
          c.setRGB(0.112 + g2 * 0.030, 0.080 + g2 * 0.022, 0.050 + g2 * 0.014);
        });
        woodParts.push(placed(T, ch,
          SX + Math.sin(a) * 0.215, 0.016, Math.cos(a) * 0.215, 0, -a, 0.06));
      }
    }

    // ---- the tools --------------------------------------------------------
    // A hammer on the face and tongs against the stump. Two small objects, and
    // they do more for "somebody works here" than another hour on the anvil.
    // Every one of these is placed by its two ENDPOINTS. The first version
    // composed a quaternion and dropped the cylinder at a CENTRE point, so half
    // the hammer haft extended backwards from where it was aimed and drove
    // straight down through the anvil face and out the underside. A centre plus
    // a direction is two facts about a stick; where it starts and where it ends
    // is the same two facts in the form that cannot be assembled wrongly.
    if (o.tools !== false) {
      const P = (x, y, z) => new T.Vector3(x, y, z);

      // cross peen hammer, head lying across the face, haft out over the heel
      const head = loftRect(T, 'x', [
        { at: -0.058, hu: 0.019, hv: 0.019, p: 3.0 },
        { at: -0.034, hu: 0.024, hv: 0.024, p: 6.0 },
        { at: 0.026, hu: 0.024, hv: 0.024, p: 6.0 },
        { at: 0.050, hu: 0.018, hv: 0.022, p: 4.0 },
        { at: 0.068, hu: 0.006, hv: 0.019, p: 2.5 }      // the cross peen
      ], 12, (c) => c.setRGB(0.128, 0.122, 0.126));
      steelParts.push({
        geo: head,
        matrix: new T.Matrix4().compose(
          new T.Vector3(0.090, FACE_TOP + 0.024, -0.006),
          new T.Quaternion().setFromEuler(new T.Euler(0, 0.46, 0)),
          new T.Vector3(1, 1, 1))
      });
      // eye of the head out to the butt of the haft, and it stays above the face
      woodParts.push(logBetween(T,
        P(0.096, FACE_TOP + 0.026, 0.006), P(0.198, FACE_TOP + 0.030, 0.268),
        0.0105, 0.0135, {
          seed: 5, rough: 0.03,
          paint: (c, x, y, z, t) => {
            const wear = Math.max(0, Math.min(1, (t - 0.25) / 0.6));
            c.setRGB(0.205 - wear * 0.040, 0.148 - wear * 0.034, 0.094 - wear * 0.026);
          }
        }));

      // Tongs leaning against the stump: reins on the ground, rivet at the
      // crossing, jaws hooked over the rim. Shorter and thicker than the first
      // attempt, which was two 0.46 m rods and read as somebody's dropped
      // walking sticks. A tool is recognisable by its JOINT, so the rivet gets
      // a visible boss even at this size.
      const rivet = P(-0.178, 0.330, 0.222);
      for (const side of [-1, 1]) {
        steelParts.push(logBetween(T,
          P(-0.332 + side * 0.048, 0.012, 0.318 + side * 0.034), rivet,
          0.0105, 0.0078, { seed: 30 + side, rough: 0.02, segments: 6,
            paint: (c) => c.setRGB(0.122, 0.115, 0.118) }));
        // the jaws, short and turned in above the rivet
        steelParts.push(logBetween(T, rivet,
          P(-0.118 + side * 0.019, 0.512, 0.152),
          0.0082, 0.0060, { seed: 40 + side, rough: 0.02, segments: 6,
            paint: (c) => c.setRGB(0.122, 0.115, 0.118) }));
      }
      const boss = new T.CylinderGeometry(0.014, 0.014, 0.020, 8);
      boss.rotateX(Math.PI / 2);
      paintByPos(T, boss, (c) => c.setRGB(0.140, 0.132, 0.134));
      steelParts.push(placed(T, boss, rivet.x, rivet.y, rivet.z, 0, 0.5, 0));
    }

    const steel = new T.Mesh(mergeParts(T, steelParts), kit.mats.steel);
    steel.castShadow = true; steel.receiveShadow = true;
    root.add(steel);
    if (woodParts.length) {
      const wood = new T.Mesh(mergeParts(T, woodParts), kit.mats.timber);
      wood.castShadow = true; wood.receiveShadow = true;
      root.add(wood);
    }

    root.scale.setScalar(S);
    if (o.x !== undefined) root.position.set(o.x, o.y || 0, o.z || 0);
    return {
      g: root,
      // The collider is the STUMP, not the anvil: the stump is what your legs
      // meet. Anything bigger and you cannot get close enough to work.
      radius: 0.30 * S,
      faceY: FACE_TOP * S,
      faceCentre: new T.Vector3(0.06 * S, FACE_TOP * S, 0)
    };
  };

  // Nothing on the anvil animates on its own, but the kit keeps the same shape
  // as every other asset so the game can call it unconditionally.
  kit.tick = function () {};

  // -------------------------------------------------------------------------
  // the sound of a hammer on an anvil
  // -------------------------------------------------------------------------
  // The forge currently plays sfx('block'), which is the SHIELD BLOCK sound: a
  // square-wave chirp and a noise tick. It was a placeholder and it sounds like
  // one.
  //
  // An anvil is one of the easier real objects to synthesise honestly, because
  // what makes it recognisable is well understood:
  //
  //   THE STRIKE   a very short bright transient, mostly above 4 kHz, under
  //                five milliseconds. This is the part that says "steel".
  //   THE THUD     a low component around 150 Hz gone within a tenth of a
  //                second. This is the MASS: it is why an anvil does not sound
  //                like a bell hanging in air.
  //   THE RING     a handful of INHARMONIC partials that sustain for one to
  //                three seconds. Inharmonic is the whole trick. A harmonic
  //                stack (f, 2f, 3f) is a musical note and reads as a chime; a
  //                real anvil's modes sit at ratios like 1 : 1.51 : 2.13 : 2.88
  //                and the ear hears metal rather than music.
  //
  // Two more details that matter more than they should:
  //   - Each partial is TWO oscillators a fraction of a hertz apart, so they
  //     beat against each other and the ring shimmers instead of sitting still.
  //   - Every strike is detuned a percent or two and the partials get their own
  //     decay times. Four identical clangs in a row is the sound of a sample,
  //     and the forge fires four of them in 1.6 seconds.
  //
  // takes the start time as an ARGUMENT, so the whole thing can be rendered
  // offline and measured rather than judged by playing it once and hoping.
  kit.strikeAt = function (ac, dest, t0, opt) {
    opt = opt || {};
    const g = opt.gain === undefined ? 0.5 : opt.gain;
    // a percent or two off every time, so no two blows are the same blow
    const dt = 1 + (Math.random() - 0.5) * 0.045;
    const heavy = opt.heavy === undefined ? (Math.random() < 0.3) : opt.heavy;

    // --- the ring: inharmonic partials, each a beating pair ---------------
    const MODES = [
      { f: 1180, a: 1.00, d: heavy ? 2.6 : 1.9 },
      { f: 1782, a: 0.62, d: heavy ? 2.1 : 1.5 },
      { f: 2513, a: 0.40, d: 1.25 },
      { f: 3398, a: 0.24, d: 0.85 },
      { f: 4620, a: 0.13, d: 0.55 },
      { f: 6240, a: 0.07, d: 0.34 }
    ];
    for (const m of MODES) {
      for (const beat of [0, 1]) {
        const o = ac.createOscillator();
        o.type = 'sine';
        // the second of each pair sits a fraction of a hertz off its twin
        o.frequency.setValueAtTime(m.f * dt * (beat ? 1.0016 : 1), t0);
        // a real strike drops a little as the metal settles
        o.frequency.exponentialRampToValueAtTime(m.f * dt * 0.995, t0 + 0.30);
        const gn = ac.createGain();
        // 0.26 normalises the summed modes back under unity, with room for
        // four overlapping blows during a forge.
        const peak = Math.max(0.0002, m.a * 0.26 * g * (beat ? 0.55 : 1) * (heavy ? 1.15 : 1));
        gn.gain.setValueAtTime(0.0001, t0);
        gn.gain.exponentialRampToValueAtTime(peak, t0 + 0.003);
        gn.gain.exponentialRampToValueAtTime(0.0001, t0 + m.d);
        o.connect(gn); gn.connect(dest);
        o.start(t0); o.stop(t0 + m.d + 0.05);
      }
    }

    // --- the strike: the bright transient that says steel ------------------
    {
      const LEN = Math.floor(ac.sampleRate * 0.05);
      const buf = ac.createBuffer(1, LEN, ac.sampleRate);
      const d = buf.getChannelData(0);
      for (let i = 0; i < LEN; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / LEN);
      const src = ac.createBufferSource(); src.buffer = buf;
      const hp = ac.createBiquadFilter();
      hp.type = 'highpass'; hp.frequency.value = 3800; hp.Q.value = 0.7;
      const gn = ac.createGain();
      gn.gain.setValueAtTime(0.0001, t0);
      gn.gain.exponentialRampToValueAtTime(0.30 * g, t0 + 0.0025);
      gn.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.035);
      src.connect(hp); hp.connect(gn); gn.connect(dest);
      src.start(t0); src.stop(t0 + 0.08);
    }

    // --- the thud: the mass under the blow ---------------------------------
    {
      const o = ac.createOscillator(); o.type = 'sine';
      o.frequency.setValueAtTime(168 * dt, t0);
      o.frequency.exponentialRampToValueAtTime(96, t0 + 0.07);
      const gn = ac.createGain();
      gn.gain.setValueAtTime(0.0001, t0);
      gn.gain.exponentialRampToValueAtTime(0.22 * g * (heavy ? 1.3 : 1), t0 + 0.004);
      gn.gain.exponentialRampToValueAtTime(0.0001, t0 + (heavy ? 0.13 : 0.085));
      o.connect(gn); gn.connect(dest);
      o.start(t0); o.stop(t0 + 0.2);
    }
  };

  // Convenience for the game: one blow, now.
  kit.strike = function (ac, dest, opt) {
    if (!ac) return;
    kit.strikeAt(ac, dest || ac.destination, ac.currentTime + 0.001, opt);
  };

  return kit;
}
