// Grim World shared asset primitives.
//
// Extracted from the shipped campfire (model-lab/campfire.js). Every function
// here earned its shape by being wrong first; the comments say how. Import
// these rather than pasting them, so the next fix lands everywhere at once.
//
// Everything takes `T` (the three namespace) as an argument and touches nothing
// else. No `this`, no game object, no globals. That is what lets a lab page and
// the game run the same file.
//
// Drop this next to your asset module in model-lab/ and:
//   import { rngFor, mergeParts, roughen, paintByPos, logBetween } from './grim-kit.js';

// ---------------------------------------------------------------------------
// determinism
// ---------------------------------------------------------------------------
// A streaming world loads and unloads props constantly. Two instances with the
// same seed must be the same object, exactly, or geometry flickers as the
// player walks away and back.
export function rngFor(seed) {
  let s = (Math.abs(Math.floor(seed || 1)) % 2147483646) + 1;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

// ---------------------------------------------------------------------------
// merging
// ---------------------------------------------------------------------------
// Merge [{ geo, matrix }] into one non-indexed BufferGeometry, keeping every
// attribute the sources carry.
//
// Item size is READ off the source attribute and never guessed. An earlier
// version carried a lookup table of known attribute names and defaulted
// anything unknown to 1, so a custom vec2 got rebuilt as a float: the particle
// quads collapsed to zero size and the sparks and smoke rendered nothing at
// all, with no error, no warning, and a shader that compiled clean. If a merge
// helper has to know the names of your attributes, it will meet one it does not.
export function mergeParts(T, parts) {
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

// ---------------------------------------------------------------------------
// surface
// ---------------------------------------------------------------------------
// Displace vertices by a hash of the ROUNDED position, so duplicated corners of
// a non-indexed geometry move identically and seams never crack open. Hashing
// raw floats splits a stone along every one of its faces.
export function roughen(T, geo, amt, seed, ys) {
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

// Paint vertex colours from a function of the vertex's own position. This is
// how soot, char, wear, moss, rust and dirt are all done: one material, no
// textures, and the shading follows the geometry exactly instead of a UV layout
// nobody authored.
//
//   paintByPos(T, geo, (c, x, y, z) => { ...; c.setRGB(r, g, b); });
export function paintByPos(T, geo, fn) {
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
// placement
// ---------------------------------------------------------------------------
// Build a tapered cylinder running from p0 to p1 and return { geo, matrix }
// ready for mergeParts.
//
// Author anything oriented in 3D by its ENDPOINTS. A heading plus a tilt
// composed into a Euler applies its axes in a fixed order, and a teepee of
// sticks written that way came out as a flat fan of pick-up sticks. "The foot
// is here, the tip is there" has no third number to get wrong.
//
// paint(c, x, y, z, t) is optional and receives t = 0 at p0, 1 at p1, so char,
// wear and grain can be painted in world terms while the geometry is local.
export function logBetween(T, p0, p1, rA, rB, opt) {
  opt = opt || {};
  const dir = new T.Vector3().subVectors(p1, p0);
  const len = dir.length();
  const g = new T.CylinderGeometry(rA, rB, len, opt.segments || 9, opt.rings || 2, false);
  if (opt.rough !== 0) roughen(T, g, opt.rough === undefined ? 0.085 : opt.rough, opt.seed || 1, 1);
  if (opt.paint) {
    paintByPos(T, g, (c, x, y, z) => opt.paint(c, x, y, z, (y + len / 2) / len));
  }
  const q = new T.Quaternion().setFromUnitVectors(new T.Vector3(0, 1, 0), dir.clone().normalize());
  const mid = new T.Vector3().addVectors(p0, p1).multiplyScalar(0.5);
  const m = new T.Matrix4().compose(mid, q, new T.Vector3(1, 1, 1));
  return { geo: g, matrix: m, length: len };
}

// Compose a { geo, matrix } from position, Euler and uniform scale. Fine for
// blobs like stones and rubble whose orientation is arbitrary; use logBetween
// for anything whose direction actually means something.
export function placed(T, geo, x, y, z, rx, ry, rz, s) {
  const m = new T.Matrix4().compose(
    new T.Vector3(x, y, z),
    new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
    new T.Vector3(s || 1, s || 1, s || 1));
  return { geo, matrix: m };
}

// ---------------------------------------------------------------------------
// shapes
// ---------------------------------------------------------------------------
// A lathed teardrop, for flames, droplets, buds, gems, anything organic that
// tapers.
//
// A cone has a straight side and a point at the bottom, so its base reads as a
// second tip and the whole thing looks like a party hat. r = R sin(PI t^p)^q
// with p below 1 drags the widest point down toward the base and leaves a
// horizontal tangent at the axis, which is what makes the bottom read as a
// rounded cap. p 0.55 / q 0.9 is a flame tongue; lower p is squatter.
export function tongueGeo(T, R, H, p, q, radial, steps) {
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const r = R * Math.pow(Math.sin(Math.PI * Math.pow(t, p)), q);
    pts.push(new T.Vector2(Math.max(0.0005, r), t * H));
  }
  return new T.LatheGeometry(pts, radial);
}

// A ring on the superellipse |u/hu|^p + |v/hv|^p = 1, sampled at n even angles.
//
// p = 2 is an ellipse, p = 12 is very nearly a rectangle with eased corners,
// and everything between is a rounded rectangle. This is the shape most
// man-made objects actually are, and the reason it is parametrised by ANGLE
// rather than by walking the perimeter is correspondence: two rings with
// different p and different half-extents still have their i-th points in the
// same place around, so they can be lofted together without shearing.
//
// That is what lets one loft run from a round horn into a square-edged anvil
// face, or a round handle into a rectangular blade, in a single surface.
export function superRing(hu, hv, p, n) {
  const pts = [];
  const e = 2 / Math.max(0.5, p);
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const ca = Math.cos(a), sa = Math.sin(a);
    pts.push([
      hu * Math.sign(ca) * Math.pow(Math.abs(ca), e),
      hv * Math.sign(sa) * Math.pow(Math.abs(sa), e)
    ]);
  }
  return pts;
}

// Loft a rounded-rectangular profile along one axis.
//
// sections: [{ at, hu, hv, cu, cv, p }] where `at` is the position along the
// run axis, hu/hv are the half-extents in the other two axes, cu/cv offset the
// section's centre, and p is the superellipse exponent for that section.
// axis: 'x', 'y' or 'z'. For 'x' the cross-section is (z, y); for 'y' it is
// (x, z); for 'z' it is (x, y).
//
// Repeat an `at` value with different extents to get a HARD STEP rather than a
// ramp: the two rings sit at the same position and the quad between them is a
// vertical wall. That is how an anvil's cutting step, a chest lid lip or a
// blade's ricasso are made in one surface instead of two overlapping boxes.
//
// paint(c, x, y, z, t) is optional, with t running 0..1 along the axis.
//
// caps is optional: { start, end }, each defaulting to true (unchanged
// behaviour for every existing caller). Pass start:false / end:false to skip
// that end's triangle fan - for a loft that butts flush against another
// solid at that end, its own cap is a redundant, exactly-coincident flat disc
// sitting right on top of whatever covers that end already. Two coincident
// discs facing opposite directions is a textbook z-fight: a thin, randomly
// bright or dark sliver right at the seam, even once both sides share an
// identical radius and identical jitter. Skipping the redundant cap removes
// the second surface instead of trying to out-jitter it.
export function loftRect(T, axis, sections, n, paint, caps) {
  const doStart = !caps || caps.start !== false;
  const doEnd = !caps || caps.end !== false;
  const pos = [], col = [];
  const c = new T.Color();
  const put3 = (a, b, at) => (axis === 'x' ? [at, b, a] : axis === 'y' ? [a, at, b] : [a, b, at]);
  const rings = sections.map(s => superRing(s.hu, s.hv, s.p === undefined ? 8 : s.p, n)
    .map(q => put3(q[0] + (s.cu || 0), q[1] + (s.cv || 0), s.at)));
  const lo = sections[0].at, hi = sections[sections.length - 1].at;
  const span = (hi - lo) || 1;
  const push = (v, t) => {
    pos.push(v[0], v[1], v[2]);
    if (paint) { paint(c, v[0], v[1], v[2], t); col.push(c.r, c.g, c.b); }
  };
  for (let r = 0; r < rings.length - 1; r++) {
    const t0 = (sections[r].at - lo) / span, t1 = (sections[r + 1].at - lo) / span;
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      const a = rings[r][i], b = rings[r][j], cc = rings[r + 1][i], d = rings[r + 1][j];
      push(a, t0); push(cc, t1); push(b, t0);
      push(b, t0); push(cc, t1); push(d, t1);
    }
  }
  // End caps, wound so both face outward along the run axis.
  for (const [ri, dir, on] of [[0, -1, doStart], [rings.length - 1, 1, doEnd]]) {
    if (!on) continue;
    const s = sections[ri];
    const ctr = put3(s.cu || 0, s.cv || 0, s.at);
    const t = (s.at - lo) / span;
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n, a = rings[ri][i], b = rings[ri][j];
      if (dir < 0) { push(ctr, t); push(a, t); push(b, t); }
      else { push(ctr, t); push(b, t); push(a, t); }
    }
  }
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
  if (paint) g.setAttribute('color', new T.Float32BufferAttribute(col, 3));
  g.computeVertexNormals();
  return g;
}

// ---------------------------------------------------------------------------
// shader building blocks
// ---------------------------------------------------------------------------
// Two octaves of value noise, no texture needed. Prepend to a fragment shader.
export const GLSL_NOISE = [
  'float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
  'float vnoise(vec2 p){',
  '  vec2 i = floor(p), f = fract(p);',
  '  f = f * f * (3.0 - 2.0 * f);',
  '  return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), f.x),',
  '             mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), f.x), f.y);',
  '}'
].join('\n');

// A flame / plasma / magic-wisp material.
//
// Layers of this are what make fire read as fire. Build three: an outer set of
// torn tongues for the silhouette, a squat body for the mass, and a small
// bright core down in the fuel. Colours run the real temperature ladder,
// white-blue where it meets the fuel through to deep red where it thins away.
//
// Geometry fed to it must carry four attributes, one value per vertex:
//   aSeed  float  per-tongue phase, so tongues merged into one draw call
//                 never dance together
//   aNorm  float  0 at that tongue's base, 1 at its tip
//   aBase  float  that tongue's base height in object space
//   aAxis  vec2   that tongue's own axis in x,z, so tapering pinches toward it
//                 rather than toward the object origin
//
// The per-INSTANCE phase is free: modelMatrix[3] is the object's world
// translation, so every instance in the world dances differently with no
// instancing and no per-object uniforms.
//
// cfg: { c0, c1, c2, alpha, erode, sway, lick, rate }
export function flameMat(T, cfg) {
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
      'float wseed = aSeed + modelMatrix[3].x * 0.37 + modelMatrix[3].z * 0.71;',
      'vSeed = wseed;',
      'vFuv = uv;',
      'float ft = clamp(aNorm, 0.0, 1.0);',
      'vT = ft;',
      // Scaled about the tongue's OWN base. About the object origin instead,
      // the flame hops clear of the fuel and back down every cycle.
      'float lick = 1.0 + uLick * (0.30 * sin(uTime * uRate * 7.3 + wseed)',
      '                          + 0.14 * sin(uTime * uRate * 16.0 + wseed * 2.1));',
      'transformed.y = (transformed.y - aBase) * lick + aBase;',
      // Taper toward the tongue's own axis, THEN lean. The other way round
      // quietly cancels most of the motion where it matters most.
      'float pinch = 1.0 - ft * 0.42;',
      'transformed.x = aAxis.x + (transformed.x - aAxis.x) * pinch;',
      'transformed.z = aAxis.y + (transformed.z - aAxis.y) * pinch;',
      'float sx = sin(uTime * uRate * 5.4 + wseed + ft * 4.0) * 0.055',
      '         + sin(uTime * uRate * 10.3 + wseed * 1.7 + ft * 7.0) * 0.030;',
      'float sz = cos(uTime * uRate * 4.7 + wseed * 0.6 + ft * 3.5) * 0.050',
      '         + cos(uTime * uRate * 12.1 + wseed + ft * 6.0) * 0.025;',
      'transformed.x += sx * ft * uSway;',
      'transformed.z += sz * ft * uSway;',
      // How square-on this surface is to the camera. Flat alpha reads as a
      // cut-out sheet of orange paper; fading the rim and holding the middle is
      // the cheapest honest approximation of looking THROUGH hot gas.
      'vec3 vnrm = normalize(normalMatrix * normal);',
      'vec3 vpos = (modelViewMatrix * vec4(transformed, 1.0)).xyz;',
      'vFace = abs(dot(vnrm, normalize(-vpos)));'
    ].join('\n'));
    sh.fragmentShader =
      'uniform float uTime;\nuniform vec3 uC0;\nuniform vec3 uC1;\nuniform vec3 uC2;\n' +
      'uniform float uAlpha;\nuniform float uErode;\nuniform float uRate;\n' +
      'varying float vT;\nvarying float vSeed;\nvarying vec2 vFuv;\nvarying float vFace;\n' +
      GLSL_NOISE + '\n' + sh.fragmentShader;
    sh.fragmentShader = sh.fragmentShader.replace('#include <dithering_fragment>', [
      '#include <dithering_fragment>',
      'vec3 fire = mix(uC0, uC1, smoothstep(0.03, 0.40, vT));',
      'fire = mix(fire, uC2, smoothstep(0.40, 0.94, vT));',
      'float flick = 0.82 + 0.18 * sin(uTime * uRate * 21.0 + vSeed * 3.1)',
      '                  + 0.10 * sin(uTime * uRate * 9.0 + vSeed);',
      // Three octaves. At four repeats around a tongue the noise cell is bigger
      // than the tongue, nothing tears, and the layer is a smooth glass shell.
      'float n = vnoise(vec2(vFuv.x * 7.0 + vSeed, vFuv.y * 4.5 - uTime * uRate * 1.7)) * 0.58',
      '        + vnoise(vec2(vFuv.x * 14.0 - vSeed, vFuv.y * 9.0 - uTime * uRate * 2.9)) * 0.29',
      '        + vnoise(vec2(vFuv.x * 26.0 + vSeed * 2.0, vFuv.y * 17.0 - uTime * uRate * 4.3)) * 0.13;',
      // Narrow threshold tears; a wide one dissolves. The threshold climbs with
      // height so the base stays a solid hot core and only the top breaks up.
      'float lo = 0.08 + vT * 0.66 * uErode;',
      'float erode = smoothstep(lo, lo + 0.19, n + (1.0 - vT) * 0.54);',
      'float a = erode * (1.0 - smoothstep(0.60, 1.0, vT)) * flick * uAlpha;',
      'a *= smoothstep(0.0, 0.14, vT);',
      'a *= mix(0.14, 1.22, pow(vFace, 0.80));',
      // Additive stacks, so a bright core over a bright core clips to white and
      // the flame loses its colour exactly where it should be hottest.
      'gl_FragColor = vec4(fire * (1.02 - vT * 0.30) * flick, a);'
    ].join('\n'));
  };
  return m;
}

// Sparks, embers, smoke, dust, pollen, bubbles.
//
// Camera-facing quads whose entire life happens in the vertex shader: position,
// size and fade all come out of fract(time * rate + seed). Zero CPU, one draw
// call, and nothing to drift out of sync because there is no integration.
//
// Geometry must carry, per vertex:
//   aSeed    float  this particle's phase, 0..1
//   aCorner  vec2   this vertex's offset within its quad, +/-0.5
// and every vertex of a quad sits at the particle's ORIGIN in object space —
// the shader rebuilds the quad in view space.
//
// cfg: { rise, size, grow, wander, spread, ease, lean, col, col2, alpha, rate,
//        hold, flick, additive }
export function driftMat(T, cfg) {
  const m = new T.MeshBasicMaterial({
    transparent: true, depthWrite: false,
    blending: cfg.additive ? T.AdditiveBlending : T.NormalBlending,
    color: 0xffffff, side: T.DoubleSide
  });
  const U = {
    uTime: { value: 0 }, uRise: { value: cfg.rise }, uSize: { value: cfg.size },
    uGrow: { value: cfg.grow }, uWander: { value: cfg.wander },
    uSpread: { value: cfg.spread }, uEase: { value: cfg.ease }, uLean: { value: cfg.lean },
    uCol: { value: new T.Color(cfg.col) },
    uCol2: { value: new T.Color(cfg.col2 === undefined ? cfg.col : cfg.col2) },
    uAlpha: { value: cfg.alpha }, uRate: { value: cfg.rate },
    uHold: { value: cfg.hold }, uFlick: { value: cfg.flick || 0 }
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
    // The first version rose on a straight line at a constant rate and the
    // sparks came out as a dead vertical column of evenly spaced dots. Hot gas
    // leaves fast and slows as it cools, and the plume widens as it entrains
    // air, so the height is eased and the lateral offset grows with the EASED
    // height: narrow at the source, open by the time it is overhead.
    sh.vertexShader = sh.vertexShader.replace('#include <project_vertex>', [
      'float life = fract(uTime * uRate + aSeed);',
      'vLife = life; vS = aSeed; vC = aCorner;',
      'float e = pow(life, uEase);',
      'float ang = aSeed * 43.0;',
      'vec2 rad = vec2(sin(ang), cos(ang)) * uSpread * e;',
      'vec2 wob = vec2(sin(aSeed * 31.0 + life * 6.2 + uTime * 0.7),',
      '                cos(aSeed * 17.0 + life * 5.4 + uTime * 0.6)) * uWander * e;',
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
      'float d = length(vC) * 2.0;',
      'float soft = 1.0 - smoothstep(0.42, 1.0, d);',
      'float fade = smoothstep(0.0, 0.05, vLife) * (1.0 - smoothstep(uHold, 1.0, vLife));',
      'fade *= 1.0 - uFlick * 0.55 * (0.5 + 0.5 * sin(vLife * 52.0 + vS * 31.0));',
      'vec3 c = mix(uCol, uCol2, vLife);',
      'gl_FragColor = vec4(c, soft * fade * uAlpha);'
    ].join('\n'));
  };
  return m;
}

// Build the geometry driftMat expects: n particles scattered within `spread`
// of the origin at height y, every quad collapsed to its particle's origin.
export function driftField(T, n, spread, y, rnd) {
  const parts = [];
  for (let i = 0; i < n; i++) {
    const a = rnd() * Math.PI * 2, r = rnd() * spread;
    const g = new T.PlaneGeometry(1, 1);
    const c = g.attributes.position.count;
    const seed = i / n + rnd() * (0.6 / n);      // spread the phases, then jitter
    const aSeed = new Float32Array(c).fill(seed);
    const aCorner = new Float32Array(c * 2);
    for (let v = 0; v < c; v++) {
      aCorner[v * 2] = g.attributes.position.getX(v);
      aCorner[v * 2 + 1] = g.attributes.position.getY(v);
    }
    g.setAttribute('aSeed', new T.BufferAttribute(aSeed, 1));
    g.setAttribute('aCorner', new T.BufferAttribute(aCorner, 2));
    const p = g.attributes.position;
    for (let v = 0; v < c; v++) p.setXYZ(v, Math.sin(a) * r, y, Math.cos(a) * r);
    parts.push({ geo: g });
  }
  return mergeParts(T, parts);
}

// Bake the four attributes flameMat needs onto a list of tongues.
// Each tongue: { R, H, x, z, y, seed, p, q, tx, tz }
export function tongueParts(T, list, radial, steps) {
  return list.map((t) => {
    const g = tongueGeo(T, t.R, t.H, t.p || 0.55, t.q || 0.9, radial, steps);
    const pos = g.attributes.position, n = pos.count;
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
    return placed(T, g, t.x, t.y, t.z, t.tx || 0, 0, t.tz || 0);
  });
}

// ---------------------------------------------------------------------------
// ground glow
// ---------------------------------------------------------------------------
// A flat disc of uniform opacity reads as a painted circle with a hard rim. A
// radial gradient baked once into a small canvas gives a hot centre falling
// away to nothing, which is the point: you should not be able to see where the
// light stops.
//
// Cheaper than a point light, reads correctly in daylight, one draw call, and
// it never gets culled by the five-nearest-lights rule.
export function glowMat(T, stops) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g2 = c.getContext('2d');
  const rg = g2.createRadialGradient(64, 64, 0, 64, 64, 64);
  (stops || [
    [0.00, 'rgba(255,184,104,0.98)'],
    [0.20, 'rgba(255,148,58,0.62)'],
    [0.46, 'rgba(255,116,34,0.28)'],
    [0.74, 'rgba(255,102,28,0.08)'],
    [1.00, 'rgba(255,96,26,0.00)']
  ]).forEach(s => rg.addColorStop(s[0], s[1]));
  g2.fillStyle = rg; g2.fillRect(0, 0, 128, 128);
  const tex = new T.CanvasTexture(c);
  if (T.SRGBColorSpace) tex.colorSpace = T.SRGBColorSpace;
  return new T.MeshBasicMaterial({
    map: tex, transparent: true, opacity: 0.55,
    blending: T.AdditiveBlending, depthWrite: false
  });
}

// A glow disc DRAPED over the terrain rather than laid flat, so the pool
// follows a slope instead of being sliced off along a dead straight line
// wherever the ground rises through it.
//
// heightAt is optional; without it the disc is flat at `lift`.
export function drapedDisc(T, radius, segments, cx, cz, heightAt, lift) {
  const g = new T.CircleGeometry(radius, segments || 30);
  g.rotateX(-Math.PI / 2);
  const p = g.attributes.position;
  const up = lift === undefined ? 0.055 : lift;
  const base = heightAt ? heightAt(cx, cz) : 0;
  for (let v = 0; v < p.count; v++) {
    p.setY(v, heightAt ? (heightAt(cx + p.getX(v), cz + p.getZ(v)) + up - base) : up);
  }
  p.needsUpdate = true;
  return g;
}
