// Shared model lab kit.
//
// wolf.html carried its own copy of the scene, the loft helper and the fur
// texture. Five more rigs meant five more copies drifting apart, so the parts
// that are the same everywhere live here and each rig page is only its own
// anatomy and its own pose function.
//
// These are deliberately the SAME helpers the game ships (loftMesh, furTex,
// jitterGeo), so a rig proven here behaves the same once it is wired in.
import * as T from 'three';

export { T };

// ---------------------------------------------------------------- scene
export function makeScene(opts) {
  opts = opts || {};
  const W = opts.w || 900, H = opts.h || 620;
  const renderer = new T.WebGLRenderer({ antialias: true });
  renderer.setSize(W, H); renderer.shadowMap.enabled = true;
  document.body.appendChild(renderer.domElement);
  const scene = new T.Scene();
  const sky = opts.sky !== undefined ? opts.sky : 0x232a1c;
  scene.background = new T.Color(sky);
  scene.fog = new T.Fog(sky, 18, 40);
  const cam = new T.PerspectiveCamera(38, W / H, 0.1, 100);
  scene.add(new T.HemisphereLight(0xcdd9e8, 0x3a3628, 0.85));
  const sun = new T.DirectionalLight(0xffeecc, 1.5); sun.position.set(6, 10, 4);
  sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -8; sun.shadow.camera.right = 8;
  sun.shadow.camera.top = 8; sun.shadow.camera.bottom = -8;
  scene.add(sun);
  const ground = new T.Mesh(new T.CircleGeometry(20, 40),
    new T.MeshStandardMaterial({ color: opts.ground || 0x4a5236, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
  return { renderer, scene, cam };
}

// ---------------------------------------------------------------- textures
// Directional streaks, no repeating look. Cached by argument pair.
const TEX = {};
export function furTexture(base, dark) {
  const key = base + '|' + dark;
  if (TEX[key]) return TEX[key];
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d');
  x.fillStyle = base; x.fillRect(0, 0, 128, 128);
  let s = 7;
  const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 420; i++) {
    x.strokeStyle = 'rgba(' + dark + ',' + (0.05 + rnd() * 0.12).toFixed(2) + ')';
    x.lineWidth = 0.8 + rnd() * 1.2;
    const px = rnd() * 128, py = rnd() * 128, len = 4 + rnd() * 9, a = -0.35 + rnd() * 0.7;
    x.beginPath(); x.moveTo(px, py); x.lineTo(px + Math.cos(a) * len, py + Math.sin(a) * len); x.stroke();
  }
  const t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping;
  TEX[key] = t; return t;
}

// Scales and chitin: hard little plates rather than soft streaks.
export function plateTexture(base, dark) {
  const key = 'p' + base + '|' + dark;
  if (TEX[key]) return TEX[key];
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d');
  x.fillStyle = base; x.fillRect(0, 0, 128, 128);
  let s = 13;
  const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let row = 0; row < 16; row++) {
    for (let col = 0; col < 16; col++) {
      const px = col * 8 + (row % 2 ? 4 : 0), py = row * 8;
      x.fillStyle = 'rgba(' + dark + ',' + (0.06 + rnd() * 0.16).toFixed(2) + ')';
      x.beginPath(); x.ellipse(px + 4, py + 4, 3.6, 3.0, 0, 0, 7); x.fill();
    }
  }
  const t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping;
  TEX[key] = t; return t;
}

// ---------------------------------------------------------------- loft
// Sections: { z, w, h, y }. Returns a watertight flat-shaded tube with vertex
// colours darkening the back and lightening the belly. Section order is
// normalised so faces always wind outward no matter which end you author first.
export function loft(secs, n, colTop, colBelly, mat) {
  const pos = [], col = [], uv = [];
  const cT = new T.Color(colTop), cB = new T.Color(colBelly), cc = new T.Color();
  if (secs.length > 1 && secs[secs.length - 1].z < secs[0].z) secs = secs.slice().reverse();
  const ring = s => {
    const pts = [];
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2;
      pts.push([Math.sin(a) * s.w, s.y + Math.cos(a) * s.h, s.z]);
    }
    return pts;
  };
  const rings = secs.map(ring);
  const vf = k => 0.5 + 0.5 * Math.cos((k / n) * Math.PI * 2);
  const push = (p, vfrac, u, v) => {
    pos.push(p[0], p[1], p[2]);
    cc.copy(cB).lerp(cT, vfrac); col.push(cc.r, cc.g, cc.b);
    uv.push(u, v);
  };
  for (let r = 0; r < rings.length - 1; r++) {
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      const a = rings[r][i], b = rings[r][j], c = rings[r + 1][i], d = rings[r + 1][j];
      push(a, vf(i), r / secs.length, i / n); push(c, vf(i), (r + 1) / secs.length, i / n); push(b, vf(j), r / secs.length, j / n);
      push(b, vf(j), r / secs.length, j / n); push(c, vf(i), (r + 1) / secs.length, i / n); push(d, vf(j), (r + 1) / secs.length, j / n);
    }
  }
  for (const [ri, dir] of [[0, -1], [rings.length - 1, 1]]) {
    const s = secs[ri], ctr = [0, s.y, s.z];
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n, a = rings[ri][i], b = rings[ri][j];
      if (dir < 0) { push(ctr, 0.5, 0, 0.5); push(a, vf(i), 0, i / n); push(b, vf(j), 0, j / n); }
      else { push(ctr, 0.5, 1, 0.5); push(b, vf(j), 1, j / n); push(a, vf(i), 1, i / n); }
    }
  }
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new T.Float32BufferAttribute(col, 3));
  g.setAttribute('uv', new T.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  const m = new T.Mesh(g, mat); m.castShadow = true; return m;
}

// Displaces vertices hashed by ROUNDED position, so duplicated corners of a
// non-indexed geometry move identically and seams never crack open.
export function jitterGeo(geo, amt, seed, ys) {
  const p = geo.getAttribute('position');
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    let h = Math.sin(Math.round(x * 1000) * 12.9898 + Math.round(y * 1000) * 78.233 + Math.round(z * 1000) * 37.719 + seed) * 43758.5453;
    h -= Math.floor(h);
    const m = 1 + (h - 0.5) * amt;
    p.setXYZ(i, x * m, y * m * (ys || 1), z * m);
  }
  geo.computeVertexNormals();
  return geo;
}

// ---------------------------------------------------------------- turntable
// Every rig page ends with this. It gives the same three things each time: a
// live turntable cycling the states, a label so you can see which state you are
// looking at, and a __shot hook so a screenshot test can freeze any state, any
// time, from any view.
export function runLab(ctx, rig, pose, opts) {
  opts = opts || {};
  const { renderer, scene, cam } = ctx;
  const states = opts.states || ['idle', 'move', 'attack'];
  const views = opts.views || {
    three4: { pos: [2.6, 1.5, 3.1], look: [0, 0.55, 0] },
    side:   { pos: [3.6, 0.9, 0.15], look: [0, 0.55, 0] },
    front:  { pos: [0.4, 1.0, 3.6], look: [0, 0.6, 0] },
    low:    { pos: [2.2, 0.55, 2.4], look: [0, 0.6, 0] }
  };
  scene.add(rig.g);

  const label = document.createElement('div');
  label.style.cssText = 'position:fixed;left:12px;top:12px;font:600 14px system-ui,sans-serif;color:#F3DC00;letter-spacing:.08em';
  document.body.appendChild(label);

  window.__shot = (state, t, view, yaw) => {
    pose(rig, state, t);
    rig.g.rotation.y = yaw || 0;
    const v = views[view] || views.three4;
    cam.position.set(...v.pos); cam.lookAt(...v.look);
    renderer.render(scene, cam);
    return true;
  };
  window.__states = states;
  window.__ready = true;

  const t0 = performance.now();
  (function loop() {
    const t = (performance.now() - t0) / 1000;
    const st = states[Math.floor(t / 5) % states.length];
    label.textContent = (opts.name || 'RIG') + '  ' + st.toUpperCase();
    pose(rig, st, t);
    rig.g.rotation.y = t * 0.35;
    const v = views.three4;
    cam.position.set(...v.pos); cam.lookAt(...v.look);
    renderer.render(scene, cam);
    requestAnimationFrame(loop);
  })();
}
