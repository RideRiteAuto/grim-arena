// GRIM WORLD: the campfire.
//
// One module, two consumers. The lab page imports it directly and the bundle
// patch inlines the same source as class methods, so what gets reviewed on the
// turntable is literally what ships. Nothing in here touches the game object:
// terrain sampling comes in as an optional callback and the only three.js
// surface used is the plain namespace, passed in.
//
// What a campfire has to get right, in the order a player notices it:
//
//   1. The FLAME must be a cluster of tongues, not a candle. A single cone or
//      a single teardrop reads as a torch no matter how good the shader is,
//      because a wood fire burns at five or six points across the fuel bed at
//      once and each one leans on its own timing.
//   2. The colour has to run the real temperature ladder. White-blue where it
//      meets the wood (above 2000F), yellow, orange through the body, deep red
//      where it thins out and becomes smoke. Getting this backwards, or
//      flattening it to one orange, is what makes game fire look like plastic.
//   3. It must SIT in something. Real fire leaves a ring of soot-blackened
//      stones, a dished bed of pale ash with black char at the middle, and logs
//      that are charred at the ends nearest the heat and still pale further
//      out. Fire without its aftermath floats.
//   4. Embers under the logs, sparks off the top, a thread of smoke, and a pool
//      of light on the ground that has no edge you can see.
//
// Everything animated is done on the GPU off a single uTime uniform, so a
// campfire costs no per-frame CPU at all and the flame, the embers, the sparks
// and the smoke are one draw call each.

/* eslint-disable no-unused-vars */

// ---------------------------------------------------------------------------
// small helpers, deliberately dependency free
// ---------------------------------------------------------------------------

// Deterministic per-fire RNG. Two campfires with the same seed are the same
// campfire, which is what a streaming world needs.
function rngFor(seed) {
  let s = (Math.abs(Math.floor(seed || 1)) % 2147483646) + 1;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

// Merge a list of {geo, matrix} into one non-indexed BufferGeometry, keeping
// every attribute the sources carry. Written here rather than pulled from
// BufferGeometryUtils so the module has no import beyond three itself.
// Item size is READ off the source attribute and never guessed. An earlier
// version carried a lookup table of known attribute names and defaulted
// anything unknown to 1, so a custom vec2 got rebuilt as a float: the particle
// quads collapsed to zero size and the sparks and the smoke rendered nothing at
// all, with no error, no warning and a shader that compiled clean. If a merge
// helper has to know the names of your attributes, it will eventually meet one
// it does not know.
function mergeParts(T, parts) {
  const attrs = {};
  const size = {};
  const names = new Set();
  parts.forEach(p => Object.keys(p.geo.attributes).forEach(n => {
    names.add(n);
    if (size[n] === undefined) size[n] = p.geo.attributes[n].itemSize;
  }));
  for (const n of names) attrs[n] = [];
  const nm = new T.Matrix3();
  for (const p of parts) {
    let g = p.geo;
    if (g.index) g = g.toNonIndexed();
    const pos = g.attributes.position;
    if (p.matrix) nm.getNormalMatrix(p.matrix);
    const v = new T.Vector3();
    for (const n of names) {
      const a = g.attributes[n];
      for (let i = 0; i < pos.count; i++) {
        if (!a) { for (let k = 0; k < size[n]; k++) attrs[n].push(0); continue; }
        if ((n === 'position' || n === 'normal') && p.matrix) {
          v.fromBufferAttribute(a, i);
          if (n === 'position') v.applyMatrix4(p.matrix); else v.applyMatrix3(nm).normalize();
          attrs[n].push(v.x, v.y, v.z);
        } else {
          for (let k = 0; k < a.itemSize; k++) attrs[n].push(a.array[i * a.itemSize + k]);
        }
      }
    }
  }
  const out = new T.BufferGeometry();
  for (const n of names) out.setAttribute(n, new T.Float32BufferAttribute(attrs[n], size[n]));
  return out;
}

// Displace vertices by a hash of the ROUNDED position, so duplicated corners of
// a non-indexed geometry move together and seams never crack open. Same rule
// the game's own jitterGeo follows, and the reason it is worth repeating: a
// stone jittered per-vertex instead of per-position splits along every face.
function roughen(T, geo, amt, seed, ys) {
  const p = geo.getAttribute('position');
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    let h = Math.sin(Math.round(x * 1000) * 12.9898 + Math.round(y * 1000) * 78.233
      + Math.round(z * 1000) * 37.719 + seed) * 43758.5453;
    h -= Math.floor(h);
    const m = 1 + (h - 0.5) * amt;
    p.setXYZ(i, x * m, y * m * (ys === undefined ? 1 : ys), z * m);
  }
  geo.computeVertexNormals();
  return geo;
}

// Paint vertex colours from a function of the vertex position. This is how the
// soot on the ring stones, the char on the log ends and the ash gradient are
// all done: one material, no textures, and the darkening follows the geometry
// instead of a UV layout nobody authored.
function paintByPos(T, geo, fn) {
  const p = geo.getAttribute('position');
  const col = new Float32Array(p.count * 3);
  const c = new T.Color();
  for (let i = 0; i < p.count; i++) {
    fn(c, p.getX(i), p.getY(i), p.getZ(i));
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
  }
  geo.setAttribute('color', new T.BufferAttribute(col, 3));
  return geo;
}

// ---------------------------------------------------------------------------
// the flame profile
// ---------------------------------------------------------------------------
// A cone has a straight side and a point at the bottom, so its base reads as a
// second tip and the whole thing looks like a party hat. A flame tongue is
// fattest low down and tapers away slowly above that. r = R sin(PI t^p)^q with
// p below 1 drags the widest point down toward the base and leaves a horizontal
// tangent at the axis, which is what makes the bottom read as a rounded cap.
function tongueGeo(T, R, H, p, q, radial, steps) {
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const r = R * Math.pow(Math.sin(Math.PI * Math.pow(t, p)), q);
    pts.push(new T.Vector2(Math.max(0.0005, r), t * H));
  }
  return new T.LatheGeometry(pts, radial);
}

// ---------------------------------------------------------------------------
// the kit
// ---------------------------------------------------------------------------
// Materials are created once and shared by every campfire in the world, so the
// per-frame animation cost is four uniform writes for the whole map no matter
// how many fires are burning.
export function makeCampfireKit(T, opt) {
  opt = opt || {};
  const kit = { T, mats: {}, lights: [], _t: 0 };

  // ---- flame material ------------------------------------------------------
  // One shader, three instances of it. The layers differ only by colour ramp,
  // alpha and how hard the noise eats them, which keeps the hot core solid
  // while the outer tongues tear into wisps.
  //
  // The per-tongue seed is baked into a vertex attribute and the per-FIRE seed
  // is read out of modelMatrix[3], the object's world translation. So five
  // tongues in one fire never move together, and two fires a hundred metres
  // apart never move together either, with no instancing and no uniforms per
  // object.
  const NOISE = [
    'float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
    'float vnoise(vec2 p){',
    '  vec2 i = floor(p), f = fract(p);',
    '  f = f * f * (3.0 - 2.0 * f);',
    '  return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), f.x),',
    '             mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), f.x), f.y);',
    '}'
  ].join('\n');

  function flameMat(cfg) {
    const m = new T.MeshBasicMaterial({
      transparent: true, depthWrite: false, blending: T.AdditiveBlending,
      color: 0xffffff, side: T.DoubleSide
    });
    const U = {
      uTime: { value: 0 },
      uC0: { value: new T.Color(cfg.c0) },
      uC1: { value: new T.Color(cfg.c1) },
      uC2: { value: new T.Color(cfg.c2) },
      uAlpha: { value: cfg.alpha },
      uErode: { value: cfg.erode },
      uSway: { value: cfg.sway },
      uLick: { value: cfg.lick },
      uRate: { value: cfg.rate }
    };
    m.userData.U = U;
    m.onBeforeCompile = (sh) => {
      Object.keys(U).forEach(k => { sh.uniforms[k] = U[k]; });
      sh.vertexShader =
        'attribute float aSeed;\nattribute float aNorm;\nattribute float aBase;\nattribute vec2 aAxis;\n' +
        'uniform float uTime;\nuniform float uSway;\nuniform float uLick;\nuniform float uRate;\n' +
        'varying float vT;\nvarying float vSeed;\nvarying vec2 vFuv;\nvarying float vFace;\n' + sh.vertexShader;
      sh.vertexShader = sh.vertexShader.replace('#include <begin_vertex>', [
        '#include <begin_vertex>',
        // world seed: the fire's own position, so no two fires share a phase
        'float wseed = aSeed + modelMatrix[3].x * 0.37 + modelMatrix[3].z * 0.71;',
        'vSeed = wseed;',
        'vFuv = uv;',
        'float ft = clamp(aNorm, 0.0, 1.0);',
        'vT = ft;',
        // The whole tongue surges and drops. Scaled about the tongue's OWN base
        // and not about the object origin, otherwise the flame hops clear of
        // the fuel and back down again every cycle.
        'float lick = 1.0 + uLick * (0.30 * sin(uTime * uRate * 7.3 + wseed)',
        '                          + 0.14 * sin(uTime * uRate * 16.0 + wseed * 2.1));',
        'transformed.y = (transformed.y - aBase) * lick + aBase;',
        // Taper toward the tongue's own axis, then lean. Leaning after the
        // taper keeps the lick at the tip at full strength; doing it the other
        // way round quietly cancels most of the motion where it matters most.
        'float pinch = 1.0 - ft * 0.42;',
        'transformed.x = aAxis.x + (transformed.x - aAxis.x) * pinch;',
        'transformed.z = aAxis.y + (transformed.z - aAxis.y) * pinch;',
        'float sx = sin(uTime * uRate * 5.4 + wseed + ft * 4.0) * 0.055',
        '         + sin(uTime * uRate * 10.3 + wseed * 1.7 + ft * 7.0) * 0.030;',
        'float sz = cos(uTime * uRate * 4.7 + wseed * 0.6 + ft * 3.5) * 0.050',
        '         + cos(uTime * uRate * 12.1 + wseed + ft * 6.0) * 0.025;',
        'transformed.x += sx * ft * uSway;',
        'transformed.z += sz * ft * uSway;',
        // How square-on this bit of surface is to the camera. A lathed tongue
        // drawn at flat alpha reads as a cut-out sheet of orange paper, because
        // its silhouette ends on a hard polygon edge and the middle is no
        // brighter than the rim. Fading the rim and keeping the middle solid is
        // the cheapest honest approximation of looking THROUGH a volume of hot
        // gas, and it is what turns the tongues from paper into fire.
        'vec3 vnrm = normalize(normalMatrix * normal);',
        'vec3 vpos = (modelViewMatrix * vec4(transformed, 1.0)).xyz;',
        'vFace = abs(dot(vnrm, normalize(-vpos)));'
      ].join('\n'));
      sh.fragmentShader =
        'uniform float uTime;\nuniform vec3 uC0;\nuniform vec3 uC1;\nuniform vec3 uC2;\n' +
        'uniform float uAlpha;\nuniform float uErode;\nuniform float uRate;\n' +
        'varying float vT;\nvarying float vSeed;\nvarying vec2 vFuv;\nvarying float vFace;\n' + NOISE + '\n' + sh.fragmentShader;
      sh.fragmentShader = sh.fragmentShader.replace('#include <dithering_fragment>', [
        '#include <dithering_fragment>',
        // the real temperature ladder, bottom to top
        'vec3 fire = mix(uC0, uC1, smoothstep(0.03, 0.40, vT));',
        'fire = mix(fire, uC2, smoothstep(0.40, 0.94, vT));',
        'float flick = 0.82 + 0.18 * sin(uTime * uRate * 21.0 + vSeed * 3.1)',
        '                  + 0.10 * sin(uTime * uRate * 9.0 + vSeed);',
        // Noise scrolling UP the tongue. This is the piece that separates a
        // shader flame from a lit cone: eroding the alpha with moving noise
        // breaks the body into tongues that pinch off and vanish, instead of a
        // smooth silhouette that can only ever wobble.
        'float n = vnoise(vec2(vFuv.x * 7.0 + vSeed, vFuv.y * 4.5 - uTime * uRate * 1.7)) * 0.58',
        '        + vnoise(vec2(vFuv.x * 14.0 - vSeed, vFuv.y * 9.0 - uTime * uRate * 2.9)) * 0.29',
        '        + vnoise(vec2(vFuv.x * 26.0 + vSeed * 2.0, vFuv.y * 17.0 - uTime * uRate * 4.3)) * 0.13;',
        // the threshold climbs with height, so the base stays a solid hot core
        // and only the upper body tears
        'float lo = 0.08 + vT * 0.66 * uErode;',
        'float erode = smoothstep(lo, lo + 0.19, n + (1.0 - vT) * 0.54);',
        'float a = erode * (1.0 - smoothstep(0.60, 1.0, vT)) * flick * uAlpha;',
        'a *= smoothstep(0.0, 0.14, vT);',   // no hard rim where it meets the fuel
        // volume, not paper: solid where you look straight through the tongue,
        // gone where the surface turns edge on and would otherwise draw a line
        'a *= mix(0.14, 1.22, pow(vFace, 0.80));',
        // Additive stacks, so a bright core over a bright core clips to white
        // and the flame loses its colour exactly where it should be hottest.
        'gl_FragColor = vec4(fire * (1.02 - vT * 0.30) * flick, a);'
      ].join('\n'));
    };
    return m;
  }

  // Outer tongues: the silhouette. Big, torn, orange falling to deep red.
  kit.mats.flameOuter = flameMat({
    c0: 0xffb843, c1: 0xf87016, c2: 0xb82a08,
    alpha: 0.66, erode: 1.30, sway: 1.85, lick: 1.0, rate: 1.0
  });
  // Body: the mass of the fire.
  kit.mats.flameMid = flameMat({
    c0: 0xffe07a, c1: 0xff9a24, c2: 0xea4d0e,
    alpha: 0.60, erode: 1.08, sway: 1.15, lick: 0.85, rate: 0.86
  });
  // Core: white-blue where it touches the wood, and it barely tears at all.
  kit.mats.flameCore = flameMat({
    c0: 0xdbeaff, c1: 0xfff0b0, c2: 0xffab33,
    alpha: 0.95, erode: 0.42, sway: 0.55, lick: 0.6, rate: 0.72
  });

  // ---- ember material ------------------------------------------------------
  // Coals sit in the ash and glow, they do not light the scene. Unlit basic
  // material pulsed per lump off its own baked seed: a bed of coals where every
  // lump breathes on the same beat reads as a string of fairy lights.
  kit.mats.ember = (() => {
    const m = new T.MeshBasicMaterial({ vertexColors: true, toneMapped: false });
    const U = { uTime: { value: 0 } };
    m.userData.U = U;
    m.onBeforeCompile = (sh) => {
      sh.uniforms.uTime = U.uTime;
      sh.vertexShader = 'attribute float aSeed;\nvarying float vS;\n' + sh.vertexShader;
      sh.vertexShader = sh.vertexShader.replace('#include <begin_vertex>',
        '#include <begin_vertex>\nvS = aSeed;');
      sh.fragmentShader = 'uniform float uTime;\nvarying float vS;\n' + sh.fragmentShader;
      sh.fragmentShader = sh.fragmentShader.replace('#include <dithering_fragment>', [
        '#include <dithering_fragment>',
        // A coal breathes: it brightens when air reaches it and dulls again.
        // Two rates, well apart, so the pattern never repeats visibly.
        'float b = 0.55 + 0.45 * sin(uTime * 1.9 + vS * 6.283)',
        '                + 0.22 * sin(uTime * 0.63 + vS * 11.0);',
        'b = clamp(b * 0.5 + 0.42, 0.10, 1.35);',
        'vec3 cool = vec3(0.42, 0.055, 0.015);',   // deep red, the coolest coal
        'vec3 hot  = vec3(1.00, 0.62, 0.18);',     // orange where the air gets in
        'vec3 col = mix(cool, hot, smoothstep(0.34, 1.05, b)) * gl_FragColor.rgb;',
        'gl_FragColor = vec4(col * (0.42 + b * 0.62), 1.0);'
      ].join('\n'));
    };
    return m;
  })();

  // ---- sparks and smoke ----------------------------------------------------
  // Both are camera-facing quads whose entire life happens in the vertex
  // shader: position, size and fade all come out of fract(time * rate + seed).
  // Zero CPU, one draw call each, and they cannot drift out of sync with the
  // frame rate because there is no integration to drift.
  function driftMat(cfg) {
    const m = new T.MeshBasicMaterial({
      transparent: true, depthWrite: false,
      blending: cfg.additive ? T.AdditiveBlending : T.NormalBlending,
      color: 0xffffff, side: T.DoubleSide
    });
    const U = {
      uTime: { value: 0 },
      uRise: { value: cfg.rise },
      uSize: { value: cfg.size },
      uGrow: { value: cfg.grow },
      uWander: { value: cfg.wander },
      uSpread: { value: cfg.spread },
      uEase: { value: cfg.ease },
      uLean: { value: cfg.lean },
      uCol: { value: new T.Color(cfg.col) },
      uCol2: { value: new T.Color(cfg.col2 === undefined ? cfg.col : cfg.col2) },
      uAlpha: { value: cfg.alpha },
      uRate: { value: cfg.rate },
      uHold: { value: cfg.hold },
      uFlick: { value: cfg.flick || 0 }
    };
    m.userData.U = U;
    m.onBeforeCompile = (sh) => {
      Object.keys(U).forEach(k => { sh.uniforms[k] = U[k]; });
      sh.vertexShader =
        'attribute float aSeed;\nattribute vec2 aCorner;\n' +
        'uniform float uTime;\nuniform float uRise;\nuniform float uSize;\nuniform float uGrow;\n' +
        'uniform float uWander;\nuniform float uSpread;\nuniform float uEase;\nuniform float uLean;\n' +
        'uniform float uRate;\n' +
        'varying float vLife;\nvarying float vS;\nvarying vec2 vC;\n' + sh.vertexShader;
      // The quad is built in VIEW space off the particle's view-space centre,
      // which is what makes it face the camera without a per-frame lookAt and
      // without the mesh needing to know where the camera is.
      //
      // The first version rose on a straight line at a constant rate, and the
      // sparks came out as a dead vertical column of evenly spaced dots. Hot
      // gas does not do that. It leaves fast and slows down as it cools, and
      // the column widens as it rises because the plume entrains air. So the
      // height is eased, and the lateral offset grows with the EASED height:
      // narrow where it leaves the flame, open by the time it is overhead.
      sh.vertexShader = sh.vertexShader.replace('#include <project_vertex>', [
        'float life = fract(uTime * uRate + aSeed);',
        'vLife = life; vS = aSeed; vC = aCorner;',
        'float e = pow(life, uEase);',
        'float ang = aSeed * 43.0;',
        'vec2 rad = vec2(sin(ang), cos(ang)) * uSpread * e;',
        'vec2 wob = vec2(sin(aSeed * 31.0 + life * 6.2 + uTime * 0.7),',
        '                cos(aSeed * 17.0 + life * 5.4 + uTime * 0.6)) * uWander * e;',
        // a touch of drift, so the plume leans instead of standing to attention
        'vec3 cen = transformed + vec3(rad.x + wob.x + uLean * e * e, uRise * e, rad.y + wob.y);',
        'vec4 mvPosition = modelViewMatrix * vec4(cen, 1.0);',
        'mvPosition.xy += aCorner * (uSize * (1.0 + uGrow * e));',
        'gl_Position = projectionMatrix * mvPosition;'
      ].join('\n'));
      sh.fragmentShader =
        'uniform vec3 uCol;\nuniform vec3 uCol2;\nuniform float uAlpha;\nuniform float uHold;\n' +
        'uniform float uFlick;\n' +
        'varying float vLife;\nvarying float vS;\nvarying vec2 vC;\n' + sh.fragmentShader;
      sh.fragmentShader = sh.fragmentShader.replace('#include <dithering_fragment>', [
        '#include <dithering_fragment>',
        // round, soft edged, no visible quad
        'float d = length(vC) * 2.0;',
        'float soft = 1.0 - smoothstep(0.42, 1.0, d);',
        // fast in, slow out: it appears at once and dies away
        'float fade = smoothstep(0.0, 0.05, vLife) * (1.0 - smoothstep(uHold, 1.0, vLife));',
        // an ember tumbling end over end winks as it goes
        'fade *= 1.0 - uFlick * 0.55 * (0.5 + 0.5 * sin(vLife * 52.0 + vS * 31.0));',
        'vec3 c = mix(uCol, uCol2, vLife);',
        'gl_FragColor = vec4(c, soft * fade * uAlpha);'
      ].join('\n'));
    };
    return m;
  }

  // Embers: small, bright, out fast, and they wink as they tumble. Real sparks
  // off a wood fire travel a metre or so and go dark, they do not sail away.
  kit.mats.spark = driftMat({
    rise: 1.45, size: 0.017, grow: -0.50, wander: 0.13, spread: 0.30,
    ease: 0.62, lean: 0.16, rate: 0.44, hold: 0.26, flick: 1.0,
    col: 0xffa63c, col2: 0xb62704, alpha: 1.0, additive: true
  });
  // Smoke has to be almost not there. Any single puff you can pick out of the
  // column reads as a cannonball, so these are wide, faint and heavily
  // overlapped, and they are gone before they reach the treeline.
  kit.mats.smoke = driftMat({
    rise: 2.40, size: 0.34, grow: 2.2, wander: 0.26, spread: 0.34,
    ease: 0.80, lean: 0.62, rate: 0.095, hold: 0.06, flick: 0,
    col: 0x746c60, col2: 0x46423c, alpha: 0.036, additive: false
  });

  // ---- the ground glow -----------------------------------------------------
  // A flat disc of uniform opacity reads as a painted circle with a hard rim.
  // A radial gradient baked once into a small canvas gives a hot centre falling
  // away to nothing, which is the whole point: you should not be able to see
  // where the light stops.
  kit.mats.glow = (() => {
    const c = (opt.canvas || document).createElement('canvas');
    c.width = c.height = 128;
    const g2 = c.getContext('2d');
    const rg = g2.createRadialGradient(64, 64, 0, 64, 64, 64);
    rg.addColorStop(0.00, 'rgba(255,184,104,0.98)');
    rg.addColorStop(0.20, 'rgba(255,148,58,0.62)');
    rg.addColorStop(0.46, 'rgba(255,116,34,0.28)');
    rg.addColorStop(0.74, 'rgba(255,102,28,0.08)');
    rg.addColorStop(1.00, 'rgba(255,96,26,0.00)');
    g2.fillStyle = rg; g2.fillRect(0, 0, 128, 128);
    const tex = new T.CanvasTexture(c);
    if (T.SRGBColorSpace) tex.colorSpace = T.SRGBColorSpace;
    return new T.MeshBasicMaterial({
      map: tex, transparent: true, opacity: 0.55,
      blending: T.AdditiveBlending, depthWrite: false
    });
  })();

  // Stone, ash and timber all read through one flat-shaded vertex-coloured
  // material, which is the game's own contract for dressed props: one merged
  // mesh, one material, one draw call.
  kit.mats.solid = new T.MeshStandardMaterial({
    vertexColors: true, roughness: 0.95, metalness: 0.0, flatShading: true
  });

  // -------------------------------------------------------------------------
  // build
  // -------------------------------------------------------------------------
  // opt: { seed, scale, heightAt(x,z), glowR, light }
  kit.build = function (o) {
    o = o || {};
    const S = o.scale || 1;
    const rnd = rngFor(o.seed === undefined ? 7 : o.seed);
    const root = new T.Group();
    const solidParts = [];
    const M = new T.Matrix4(), Q = new T.Quaternion(), E = new T.Euler(), V = new T.Vector3();
    const place = (geo, x, y, z, rx, ry, rz, s) => {
      E.set(rx || 0, ry || 0, rz || 0);
      M.compose(V.set(x, y, z), Q.setFromEuler(E), new T.Vector3(s || 1, s || 1, s || 1));
      solidParts.push({ geo, matrix: M.clone() });
    };

    // ---- the fire ring ----------------------------------------------------
    // Fieldstones bedded into the ground, angle and radius jittered so it never
    // reads as a drawn circle, and squashed in Y because a stone that has been
    // kicked into place lies flat, it does not stand up.
    //
    // Size is the thing that goes wrong here. Ring stones are hand sized: you
    // carried them from the riverbank one at a time. Built any bigger they turn
    // into a boulder pile, they hide the fuel, and the fire stops being the
    // thing you look at, which is exactly what the first build did.
    //
    // The soot is the detail that sells it: every stone in a real ring is
    // blackened on the face that looks at the fire and clean on the outside,
    // and that is done here by painting vertex colours from the vertex's own
    // distance to the fire centre. No texture, no UV layout, follows the
    // geometry exactly.
    const RING = 0.66;
    const NSTONE = 17;
    for (let i = 0; i < NSTONE; i++) {
      const a = (i / NSTONE) * Math.PI * 2 + (rnd() - 0.5) * 0.30;
      const rr = RING + (rnd() - 0.5) * 0.065;
      const size = 0.072 + rnd() * 0.058;
      const geo = roughen(T, new T.DodecahedronGeometry(size, 0), 0.44, rnd() * 97, 0.58);
      const sx = Math.sin(a) * rr, sz = Math.cos(a) * rr;
      const tone = 0.84 + rnd() * 0.30;
      paintByPos(T, geo, (c, x, y, z) => {
        // distance of this vertex from the fire centre once the stone is placed
        const wx = sx + x, wz = sz + z;
        const d = Math.sqrt(wx * wx + wz * wz);
        // soot from the inner face outward, and heavier low down where the
        // flame actually licks
        const soot = Math.max(0, Math.min(1, (RING + 0.12 - d) / 0.30))
          * (1 - Math.max(0, Math.min(1, (y + size * 0.2) / (size * 1.5))) * 0.42);
        const base = 0.225 * tone;
        c.setRGB(base * (1 - soot * 0.84), base * 0.98 * (1 - soot * 0.87), base * 0.94 * (1 - soot * 0.9));
        // a hint of warmth bounced back off the coals onto the inner faces
        c.r += soot * 0.05;
      });
      // bedded, not balanced: a third of each stone is under the dirt
      place(geo, sx, size * 0.30, sz, (rnd() - 0.5) * 0.45, rnd() * 3, (rnd() - 0.5) * 0.45);
    }

    // ---- the ash bed ------------------------------------------------------
    // Built on a RingGeometry rather than by hand. The first version wound its
    // own triangle fan and got the winding right for some rings and backwards
    // for others, so half the bed came out with its normals in the ground and
    // read as a pale crescent lying next to the fire. Three's own primitive
    // cannot be wound backwards, so displace one of those instead.
    //
    // The colour ramp then went wrong in a subtler way. Char in the middle
    // running out to PALE ash at the rim is what a fire bed actually looks like
    // from above, but it makes the outermost ring the brightest thing on the
    // ground, and a bright ring is a drawn circle no matter how much you warp
    // its radius. From a seated camera it read as a thin white hoop looped
    // round behind the stones. So the ash peaks at about two thirds out and
    // falls back to plain scorched earth at the rim, where it has something to
    // blend into instead of an edge to draw.
    {
      const AR = 0.44, SEG = 36, RINGS = 5;
      const ring = new T.RingGeometry(0.0001, AR, SEG, RINGS);
      ring.rotateX(-Math.PI / 2);
      const p = ring.attributes.position;
      const col = new Float32Array(p.count * 3);
      const cc = new T.Color();
      const CHAR = [0.036, 0.031, 0.028];   // burnt through
      const ASH = [0.235, 0.222, 0.205];    // spent wood ash
      const SOIL = [0.048, 0.040, 0.034];   // scorched to nearly nothing at the rim
      for (let i = 0; i < p.count; i++) {
        const x = p.getX(i), z = p.getZ(i);
        const d = Math.min(1, Math.sqrt(x * x + z * z) / AR);
        // A fire eats down into its own bed, so the middle is dished. The rim
        // is warped hard by cheap trig noise so the edge is never a circle.
        const th = Math.atan2(x, z);
        const warp = 1 + Math.sin(th * 3.1 + 1.7) * 0.11 + Math.sin(th * 7.3) * 0.07
          + Math.sin(th * 13.1 + 0.6) * 0.035;
        const w = d > 0.60 ? 1 + (warp - 1) * ((d - 0.60) / 0.40) : 1;
        p.setX(i, x * w); p.setZ(i, z * w);
        p.setY(i, -0.038 * (1 - d * d));
        const n = 0.5 + 0.5 * Math.sin(x * 21.3 + z * 17.7) * Math.sin(x * 9.1 - z * 13.3);
        // char to ash across the inner half, ash back to soil across the outer
        const u = Math.max(0, Math.min(1, d * 1.9 - 0.16 + (n - 0.5) * 0.34));
        const v = Math.max(0, Math.min(1, (d - 0.58) / 0.42));
        const ka = u * u * (3 - 2 * u), kv = v * v * (3 - 2 * v);
        for (let ch = 0; ch < 3; ch++) {
          const mid = CHAR[ch] + (ASH[ch] - CHAR[ch]) * ka;
          col[i * 3 + ch] = mid + (SOIL[ch] - mid) * kv;
        }
      }
      p.needsUpdate = true;
      ring.setAttribute('color', new T.BufferAttribute(col, 3));
      ring.computeVertexNormals();
      place(ring, 0, 0.006, 0);
    }

    // ---- the fuel ---------------------------------------------------------
    // A real campfire mid-burn is a hybrid lay: wrist-thick splits resting low
    // in a rough log cabin, and a teepee of kindling leaning into the middle of
    // them. Neither lay alone looks like a fire people sit at. Firewood should
    // be no thicker than an adult's wrist, so 0.05 to 0.065 radius, and SPLIT
    // rather than round, which is why these are seven sided with one flat pale
    // face rather than smooth dowels.
    //
    // Every piece is placed by its two ENDPOINTS and oriented with a quaternion
    // onto that direction. The first build composed a Euler instead, and
    // because the tilt and the heading are applied in a fixed order the teepee
    // came out as a flat fan of pick-up sticks rather than a cone. Endpoints
    // cannot express that mistake: you say where the foot is and where the tip
    // is, and there is no third number to get wrong.
    const UP = new T.Vector3(0, 1, 0);
    const ONE = new T.Vector3(1, 1, 1);
    const logBetween = (p0, p1, rA, rB, seedN, splitFace) => {
      const dir = new T.Vector3().subVectors(p1, p0);
      const len = dir.length();
      const g = new T.CylinderGeometry(rA, rB, len, 9, 2, false);
      roughen(T, g, 0.085, seedN, 1);
      // char and grain, painted in the log's OWN space: local y runs from the
      // foot at -len/2 to the tip at +len/2, so the world position of any
      // vertex is just that fraction along the line the log sits on.
      paintByPos(T, g, (c, x, y, z) => {
        const t = (y + len / 2) / len;
        const wx = p0.x + (p1.x - p0.x) * t, wz = p0.z + (p1.z - p0.z) * t;
        const wy = p0.y + (p1.y - p0.y) * t;
        const d = Math.sqrt(wx * wx + wz * wz);
        // burnt where it is close to the middle of the bed AND low down: the
        // tip of a teepee stick is above the flame and blackens, the foot out
        // on the ash is barely touched
        const char = Math.max(0, Math.min(1, (0.56 - d) / 0.46))
          * (1 - Math.max(0, Math.min(1, (wy - 0.42) / 0.5)) * 0.35);
        const grain = 0.5 + 0.5 * Math.sin(y * 63 + x * 17 + z * 29);
        // one pale split face, because firewood is halved not whole
        const split = splitFace && x > rA * 0.35 ? 1 : 0;
        const b = (0.135 + split * 0.105) + grain * 0.040;
        const k = 1 - char * 0.82;
        c.setRGB(b * k, b * 0.845 * k, b * 0.685 * k);
        // a coal-red bloom on the wood right where it is burning through
        c.r += char * char * 0.20; c.g += char * char * 0.045;
      });
      const q = new T.Quaternion().setFromUnitVectors(UP, dir.clone().normalize());
      const mid = new T.Vector3().addVectors(p0, p1).multiplyScalar(0.5);
      M.compose(mid, q, ONE);
      solidParts.push({ geo: g, matrix: M.clone() });
    };
    const P = (x, y, z) => new T.Vector3(x, y, z);

    // Four base splits laid as a loose cabin: each one passes BESIDE the middle
    // rather than through it, so they frame the coal bed instead of capping it.
    // A cabin lay built on four evenly spaced headings comes out as a drawn
    // square, which is the giveaway that nobody stacked it. Real ones are two
    // roughly parallel splits with the next pair thrown across them at whatever
    // angle they landed, so the headings here are deliberately uneven and the
    // ends run past each other by different amounts.
    const baseLay = [
      { a: 0.20, off: 0.17, len: 0.72, y: 0.064, s: 0.09 },
      { a: 0.62, off: -0.19, len: 0.63, y: 0.068, s: -0.08 },
      { a: 1.55, off: 0.08, len: 0.68, y: 0.070, s: 0.14 },
      { a: 2.02, off: 0.15, len: 0.60, y: 0.126, s: -0.11 },
      { a: 2.58, off: -0.13, len: 0.66, y: 0.132, s: 0.06 },
      { a: 1.18, off: -0.05, len: 0.52, y: 0.178, s: -0.15 }
    ];
    for (let i = 0; i < baseLay.length; i++) {
      const L = baseLay[i];
      const a = L.a + (rnd() - 0.5) * 0.22;
      const dx = Math.sin(a), dz = Math.cos(a);
      const px = -dz * L.off + dx * L.s, pz = dx * L.off + dz * L.s;
      const h = L.len / 2;
      const sag = (rnd() - 0.5) * 0.04;
      logBetween(
        P(px - dx * h, L.y - sag, pz - dz * h),
        P(px + dx * h, L.y + sag, pz + dz * h),
        0.052 + rnd() * 0.014, 0.046 + rnd() * 0.012, 130 + i * 37, true);
    }

    // The teepee: six sticks with their feet out on the ash and their tips
    // crossing in a tight cluster above the middle. The tips do not all meet at
    // one point, they cross at slightly different heights, which is what makes
    // it read as stacked kindling rather than a wigwam.
    // Seven sticks on uneven headings. Evenly spaced feet plus tips meeting at
    // one point draws a six pointed star when you look down at it, so the feet
    // are clustered unevenly and the tips are scattered across a 0.13 m patch
    // at four different heights. Two of them are short and lean far in: those
    // are the ones already half burnt through.
    const FEET = [0.15, 1.05, 1.62, 2.70, 3.55, 4.30, 5.55];
    for (let i = 0; i < FEET.length; i++) {
      const a = FEET[i] + (rnd() - 0.5) * 0.35;
      const short = i % 3 === 2;
      const foot = (short ? 0.20 : 0.29) + rnd() * 0.09;
      const topR = 0.02 + rnd() * 0.115;
      const topH = (short ? 0.29 : 0.38) + rnd() * 0.15;
      const ta = a + (rnd() - 0.5) * 1.6;
      logBetween(
        P(Math.sin(a) * foot, 0.026 + rnd() * 0.028, Math.cos(a) * foot),
        P(Math.sin(ta) * topR, topH, Math.cos(ta) * topR),
        0.029 + rnd() * 0.012, 0.017 + rnd() * 0.009, 400 + i * 53, rnd() > 0.5);
    }

    // Charcoal: broken lumps of spent wood sitting in the ash between the logs.
    // Cheap, and it is the difference between a fire that was just lit and a
    // fire that has been burning a while.
    for (let i = 0; i < 7; i++) {
      const a = rnd() * Math.PI * 2, r = 0.10 + rnd() * 0.34;
      const s = 0.030 + rnd() * 0.038;
      const g = roughen(T, new T.DodecahedronGeometry(s, 0), 0.55, rnd() * 61, 0.55);
      paintByPos(T, g, (c, x, y) => {
        const k = 0.055 + Math.max(0, y) * 0.28;
        c.setRGB(k * 1.1, k * 0.95, k * 0.92);
      });
      place(g, Math.sin(a) * r, s * 0.42, Math.cos(a) * r,
        (rnd() - 0.5) * 1.2, rnd() * 3, (rnd() - 0.5) * 1.2);
    }

    const solid = new T.Mesh(mergeParts(T, solidParts), kit.mats.solid);
    solid.castShadow = true; solid.receiveShadow = true;
    solid.scale.setScalar(1);
    root.add(solid);

    // ---- embers -----------------------------------------------------------
    // Nestled low, between and under the fuel, never floating above it.
    {
      const parts = [];
      const N = 14;
      for (let i = 0; i < N; i++) {
        const a = rnd() * Math.PI * 2, r = rnd() * 0.24;
        const s = 0.024 + rnd() * 0.036;
        const g = roughen(T, new T.IcosahedronGeometry(s, 0), 0.5, rnd() * 71, 0.7);
        const seed = rnd();
        const sd = new Float32Array(g.attributes.position.count).fill(seed);
        g.setAttribute('aSeed', new T.BufferAttribute(sd, 1));
        paintByPos(T, g, (c) => c.setRGB(1, 1, 1));
        M.compose(V.set(Math.sin(a) * r, 0.020 + rnd() * 0.042, Math.cos(a) * r),
          Q.setFromEuler(E.set(rnd() * 3, rnd() * 3, rnd() * 3)), new T.Vector3(1, 1, 1));
        parts.push({ geo: g, matrix: M.clone() });
      }
      const em = new T.Mesh(mergeParts(T, parts), kit.mats.ember);
      em.renderOrder = 1;
      root.add(em);
    }

    // ---- the flame --------------------------------------------------------
    // Five outer tongues around a body and a hot core. Each tongue carries its
    // own seed, its own base height and its own axis as vertex attributes, so
    // one draw call holds five independently dancing flames.
    const flameGroup = new T.Group();
    flameGroup.position.y = 0.10;
    root.add(flameGroup);

    const tongueParts = (list, radial, steps) => list.map((t, i) => {
      const g = tongueGeo(T, t.R, t.H, t.p || 0.55, t.q || 0.9, radial, steps);
      const pos = g.attributes.position;
      const n = pos.count;
      const aSeed = new Float32Array(n), aNorm = new Float32Array(n), aBase = new Float32Array(n);
      const aAxis = new Float32Array(n * 2);
      for (let v = 0; v < n; v++) {
        aSeed[v] = t.seed;
        aNorm[v] = Math.max(0, Math.min(1, pos.getY(v) / t.H));
        aBase[v] = t.y;
        aAxis[v * 2] = t.x; aAxis[v * 2 + 1] = t.z;
      }
      g.setAttribute('aSeed', new T.BufferAttribute(aSeed, 1));
      g.setAttribute('aNorm', new T.BufferAttribute(aNorm, 1));
      g.setAttribute('aBase', new T.BufferAttribute(aBase, 1));
      g.setAttribute('aAxis', new T.BufferAttribute(aAxis, 2));
      M.compose(V.set(t.x, t.y, t.z), Q.setFromEuler(E.set(t.tx || 0, 0, t.tz || 0)), new T.Vector3(1, 1, 1));
      return { geo: g, matrix: M.clone() };
    });

    // Seven tongues, spread across the whole fuel bed rather than bunched on
    // the axis. The first build kept them inside 0.15 m of the middle and the
    // result was one tall spike: a candle, not a campfire. A wood fire burns
    // wherever air can reach the fuel, so the tongues have to reach the edges
    // of the bed, and the SHORT wide ones at the rim are what give the cluster
    // its broad base.
    const outer = [];
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2 + 0.4 + rnd() * 0.46;
      const rimness = rnd();                       // 0 near the middle, 1 at the rim
      const r = 0.05 + rimness * 0.22;
      outer.push({
        // out at the rim they are wide and short, in the middle tall and narrow
        R: 0.082 + (1 - rimness) * 0.048 + rnd() * 0.036,
        H: 0.26 + (1 - rimness) * 0.34 + rnd() * 0.13,
        x: Math.sin(a) * r, z: Math.cos(a) * r, y: 0,
        // rim tongues lean outward, which is what stops the cluster reading as
        // one fat cone with a lumpy edge
        tx: -Math.cos(a) * (0.12 + rimness * 0.20),
        tz: Math.sin(a) * (0.12 + rimness * 0.20),
        seed: rnd() * 6.283
      });
    }
    const mkFlame = (list, mat, radial, steps, order) => {
      const m = new T.Mesh(mergeParts(T, tongueParts(list, radial, steps)), mat);
      m.renderOrder = order;
      flameGroup.add(m);
      return m;
    };
    mkFlame(outer, kit.mats.flameOuter, 16, 20, 3);
    // the body: wide and squat, it is the MASS of the fire and not its height
    mkFlame([{ R: 0.255, H: 0.42, x: 0, z: 0, y: 0, seed: rnd() * 6.283, p: 0.42, q: 0.80 }],
      kit.mats.flameMid, 18, 20, 4);
    // the core sits down in the fuel where the wood is actually white hot
    mkFlame([{ R: 0.155, H: 0.22, x: 0, z: 0, y: -0.02, seed: rnd() * 6.283, p: 0.38, q: 0.72 }],
      kit.mats.flameCore, 18, 16, 5);

    // ---- sparks and smoke -------------------------------------------------
    const quadField = (n, spread, y, mat, order) => {
      const parts = [];
      for (let i = 0; i < n; i++) {
        const a = rnd() * Math.PI * 2, r = rnd() * spread;
        const g = new T.PlaneGeometry(1, 1);
        const c = g.attributes.position.count;
        const seed = i / n + rnd() * (0.6 / n);
        const aSeed = new Float32Array(c).fill(seed);
        const aCorner = new Float32Array(c * 2);
        for (let v = 0; v < c; v++) {
          aCorner[v * 2] = g.attributes.position.getX(v);
          aCorner[v * 2 + 1] = g.attributes.position.getY(v);
        }
        g.setAttribute('aSeed', new T.BufferAttribute(aSeed, 1));
        g.setAttribute('aCorner', new T.BufferAttribute(aCorner, 2));
        // the plane's own vertices are collapsed to the particle origin: the
        // shader rebuilds the quad in view space, so the geometry only has to
        // carry where the particle STARTS
        const p = g.attributes.position;
        for (let v = 0; v < c; v++) p.setXYZ(v, Math.sin(a) * r, y, Math.cos(a) * r);
        parts.push({ geo: g });
      }
      const m = new T.Mesh(mergeParts(T, parts), mat);
      m.frustumCulled = false;
      m.renderOrder = order;
      root.add(m);
      return m;
    };
    // Enough of them, with jittered phases, that the column never reads as a
    // string of beads climbing a wire.
    quadField(34, 0.26, 0.20, kit.mats.spark, 6);
    quadField(22, 0.20, 0.58, kit.mats.smoke, 2);

    // ---- ground glow ------------------------------------------------------
    // Draped over the terrain rather than laid flat, so the pool of light
    // follows the slope instead of being sliced off along a straight line
    // wherever the ground rises through it.
    // The first build ran this out to 2.9 m at full additive strength and the
    // fire lit the whole clearing like a stage light: everything within four
    // metres went the same orange and the fire stopped being the brightest
    // thing in its own picture. A campfire throws a pool you can step out of.
    {
      const GR = (o.glowR || 2.6) * S, SEG = 30;
      const g = new T.CircleGeometry(GR, SEG);
      g.rotateX(-Math.PI / 2);
      if (o.heightAt) {
        const p = g.attributes.position;
        const base = o.heightAt(o.x || 0, o.z || 0);
        for (let v = 0; v < p.count; v++) {
          p.setY(v, o.heightAt((o.x || 0) + p.getX(v), (o.z || 0) + p.getZ(v)) + 0.055 - base);
        }
        p.needsUpdate = true;
      } else {
        const p = g.attributes.position;
        for (let v = 0; v < p.count; v++) p.setY(v, 0.055);
        p.needsUpdate = true;
      }
      const mesh = new T.Mesh(g, kit.mats.glow);
      mesh.renderOrder = 2;
      root.add(mesh);
    }

    // ---- light -------------------------------------------------------------
    // Registered on the kit so the frame tick can flicker every fire in the
    // world in one pass. A campfire whose light holds perfectly steady while
    // its flame dances is the single most obvious tell that the fire is a
    // decal, because the shadows it throws stop agreeing with it.
    let light = null;
    if (o.light !== false) {
      const power = o.lightPower === undefined ? 6.5 : o.lightPower;
      light = new T.PointLight(0xff9a45, power, 15, 2);
      light.position.set(0, 0.62, 0);
      light.userData.basePower = power;
      root.add(light);
      kit.lights.push(light);
    }

    root.scale.setScalar(S);
    if (o.x !== undefined) root.position.set(o.x, o.y || 0, o.z || 0);
    root.userData.campfire = { light, flameGroup };
    return { g: root, light, flameGroup, radius: (RING + 0.22) * S };
  };

  // -------------------------------------------------------------------------
  // tick
  // -------------------------------------------------------------------------
  // Four uniform writes and one opacity assignment for every campfire in the
  // world. Call it once a frame with seconds.
  kit.tick = function (seconds) {
    kit._t = seconds;
    const m = kit.mats;
    m.flameOuter.userData.U.uTime.value = seconds;
    m.flameMid.userData.U.uTime.value = seconds;
    m.flameCore.userData.U.uTime.value = seconds;
    m.ember.userData.U.uTime.value = seconds;
    m.spark.userData.U.uTime.value = seconds;
    m.smoke.userData.U.uTime.value = seconds;
    // The pool of light breathes on three rates that do not divide into each
    // other, so it never settles into a visible pulse.
    const f = 0.72 + 0.16 * Math.sin(seconds * 6.3) + 0.09 * Math.sin(seconds * 13.7 + 1.3)
      + 0.05 * Math.sin(seconds * 27.1 + 2.1);
    const k = Math.max(0, Math.min(1, f));
    m.glow.opacity = 0.24 + k * 0.34;
    for (let i = 0; i < kit.lights.length; i++) {
      const L = kit.lights[i];
      L.intensity = L.userData.basePower * (0.74 + k * 0.42);
    }
    return f;
  };

  // -------------------------------------------------------------------------
  // sound
  // -------------------------------------------------------------------------
  // A campfire is three sounds stacked, and getting the balance wrong is what
  // makes synthesised fire read as radio static:
  //
  //   the ROAR   a low bed of brown noise under about 700 Hz, the sound of the
  //              column of hot air itself, breathing slowly
  //   the HISS   a mid band around 1 to 2 kHz, sap and steam leaving the wood
  //   the CRACK  short bright transients above 1.5 kHz with a 4 ms attack and a
  //              30 to 70 ms tail, which is wood fibre splitting
  //
  // The crackles have to be scheduled at IRREGULAR intervals. Anything even
  // becomes a rhythm within about ten seconds and the ear locks onto it, so the
  // gap is drawn from an exponential distribution, which is what a stream of
  // independent events actually sounds like.
  //
  // Nothing here is a sample. It is a few filters on a noise buffer, so the
  // whole thing costs nothing to download and the crackles are never the same
  // twice.
  kit.sound = function (ac, dest, o) {
    o = o || {};
    if (!ac) return null;
    const out = ac.createGain();
    out.gain.value = 0;
    out.connect(dest || ac.destination);

    // Brown noise: white noise integrated, which rolls off at 6 dB per octave
    // and is what gives fire its weight. White noise alone is a hiss, and a
    // hiss is rain.
    const LEN = Math.floor(ac.sampleRate * 4);
    const buf = ac.createBuffer(1, LEN, ac.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < LEN; i++) {
      const w = Math.random() * 2 - 1;
      last = (last + 0.024 * w) / 1.024;
      d[i] = last * 3.2;
    }
    // seamless loop: cross-fade the last quarter second back over the first
    const X = Math.floor(ac.sampleRate * 0.25);
    for (let i = 0; i < X; i++) {
      const t = i / X;
      d[i] = d[i] * t + d[LEN - X + i] * (1 - t);
    }

    const src = ac.createBufferSource();
    src.buffer = buf; src.loop = true;

    const roar = ac.createBiquadFilter();
    roar.type = 'lowpass'; roar.frequency.value = 620; roar.Q.value = 0.7;
    const roarG = ac.createGain(); roarG.gain.value = 0.30;

    const hiss = ac.createBiquadFilter();
    hiss.type = 'bandpass'; hiss.frequency.value = 1500; hiss.Q.value = 0.8;
    const hissG = ac.createGain(); hissG.gain.value = 0.095;

    src.connect(roar); roar.connect(roarG); roarG.connect(out);
    src.connect(hiss); hiss.connect(hissG); hissG.connect(out);

    // the bed swells and settles, the way a fire does when it catches air
    const lfo = ac.createOscillator(); lfo.type = 'sine'; lfo.frequency.value = 0.11;
    const lfoG = ac.createGain(); lfoG.gain.value = 0.22;
    lfo.connect(lfoG); lfoG.connect(roarG.gain);

    src.start(); lfo.start();

    let stopped = false;
    let timer = null;
    // Two kinds of event. Most are small ticks; about one in seven is a real
    // pop with a low thump under it, which is the one you actually notice.
    // Taking the start time as an ARGUMENT rather than reading the clock is
    // what lets the whole thing be rendered offline and inspected, instead of
    // being a sound that can only be judged by playing it and hoping.
    const crackleAt = (t0, big) => {
      const cs = ac.createBufferSource();
      cs.buffer = buf;
      cs.playbackRate.value = 0.85 + Math.random() * 0.5;
      const off = Math.random() * 3.0;
      const bp = ac.createBiquadFilter();
      bp.type = 'bandpass';
      bp.frequency.value = big ? (900 + Math.random() * 900) : (1800 + Math.random() * 3200);
      bp.Q.value = big ? 1.4 : 2.6 + Math.random() * 2.5;
      const g = ac.createGain();
      const peak = (big ? 0.78 : 0.30) * (0.45 + Math.random() * 1.0);
      const tail = big ? (0.07 + Math.random() * 0.10) : (0.018 + Math.random() * 0.045);
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak), t0 + 0.004);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + tail);
      cs.connect(bp); bp.connect(g); g.connect(out);
      cs.start(t0, off, tail + 0.05);
      cs.stop(t0 + tail + 0.06);
      if (big) {
        // the thump of a knot letting go
        const osc = ac.createOscillator(); osc.type = 'sine';
        osc.frequency.setValueAtTime(150 + Math.random() * 90, t0);
        osc.frequency.exponentialRampToValueAtTime(55, t0 + 0.09);
        const og = ac.createGain();
        og.gain.setValueAtTime(0.0001, t0);
        og.gain.exponentialRampToValueAtTime(0.30, t0 + 0.006);
        og.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.11);
        osc.connect(og); og.connect(out);
        osc.start(t0); osc.stop(t0 + 0.16);
      }
    };
    // Exponential gaps: independent events, never a rhythm. Anything evenly
    // spaced turns into a tick-tock inside about ten seconds and the ear locks
    // onto it and never lets go.
    const nextGap = () => Math.max(0.030, -Math.log(1 - Math.random()) * 0.105);
    if (o.prerender) {
      for (let t = 0.05; t < o.prerender; t += nextGap()) crackleAt(t, Math.random() < 0.14);
    } else {
      const pump = () => {
        if (stopped) return;
        crackleAt(ac.currentTime + 0.001, Math.random() < 0.14);
        timer = setTimeout(pump, nextGap() * 1000);
      };
      timer = setTimeout(pump, 120);
    }

    const handle = {
      out: out,
      // Distance falloff done by hand rather than with a PannerNode: the game
      // already knows where the player is every frame, one gain write is
      // cheaper than a spatialiser per fire, and it stays correct when the
      // listener is not the camera.
      setVolume(v) { out.gain.value = Math.max(0, Math.min(1, v)) * (o.gain === undefined ? 0.55 : o.gain); },
      setDistance(dist, range) {
        const r = range || 17;
        const k2 = Math.max(0, 1 - dist / r);
        handle.setVolume(k2 * k2);
      },
      stop() {
        stopped = true;
        if (timer) clearTimeout(timer);
        try { src.stop(); lfo.stop(); } catch (e) {}
        out.disconnect();
      }
    };
    handle.setVolume(o.volume === undefined ? 1 : o.volume);
    return handle;
  };

  return kit;
}
