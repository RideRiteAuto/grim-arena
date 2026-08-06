// ===========================================================================
// GRIM WORLD - WORLD EDITOR (tools and interface)
//
// EDITOR ONLY. Nothing in this file runs unless the URL carries ?edit=1 AND
// GRIM_RULES.EDIT.UI is on. A player never enters any of it.
//
// The editor is the real game engine with an editor flag, so the lighting,
// the ground atlas, the models and the streaming are all the ones players
// get: what Kevin sees here IS the game. What changes is the top of the tick,
// where the free camera replaces the player and combat never starts.
//
// Camera: a free camera, deliberately not a flying player. It never touches
// player physics, so nothing in the vertical layer has to care that the
// editor exists, and it will not need rebuilding when housing or vehicles
// land.
//
// Injected into the game bundle by repack.py between the EDITOR markers.
// ===========================================================================
const GRIM_EDIT_UI = (() => {
  const CFG = (typeof GRIM_RULES !== 'undefined' && GRIM_RULES.EDIT) || {};
  const SURF_NAMES = [
    'meadow', 'ploughed', 'heath', 'forest floor', 'moss and fern', 'snow',
    'frozen scree', 'mountain gravel', 'bare slate', 'beach sand',
    'dry coastal', 'steppe grass', 'cinder', 'bog', 'desert sand', 'packed dirt'
  ];
  const GOLD = '#F3DC00', DARK = '#1A1A1A';

  let G = null;                       // the game instance
  let S = null;                       // editor state
  let dom = null;

  // ---- state ---------------------------------------------------------------
  function fresh() {
    return {
      on: false, authed: false, key: '',
      cam: { x: -84, y: 60, z: 246, yaw: 0, pit: -0.7 },
      vel: { x: 0, y: 0, z: 0 },
      keys: {}, look: false, lastX: 0, lastY: 0,
      tool: 'paint',
      surf: 15, brush: 8, strength: 1,
      kind: 'tree_broad', tab: 'build',
      rot: 0, scale: 1, freePlace: false,
      road: null, roadW: 6,
      sel: null, ghost: null, hoverPt: null,
      undo: [], redo: [],
      dirty: false, saving: false, msg: '', msgAt: 0,
      districtPts: null,
      prefabName: '', clipboard: null,
      lastPaintCell: -1
    };
  }

  // ---- undo ----------------------------------------------------------------
  // Snapshots of the whole layer. It is a few hundred KB at most and an
  // editor session is minutes long, so a diff system would be effort spent
  // where nobody is waiting. Capped so a long session cannot grow without
  // bound.
  const UNDO_MAX = 40;
  function pushUndo() {
    S.undo.push(GRIM_EDIT.exportLayer());
    if (S.undo.length > UNDO_MAX) S.undo.shift();
    S.redo.length = 0;
    S.dirty = true;
  }
  function undo() {
    if (!S.undo.length) return say('nothing to undo');
    S.redo.push(GRIM_EDIT.exportLayer());
    GRIM_EDIT.setLayer(JSON.parse(S.undo.pop()));
    rebuildWorld(); say('undone');
  }
  function redo() {
    if (!S.redo.length) return say('nothing to redo');
    S.undo.push(GRIM_EDIT.exportLayer());
    GRIM_EDIT.setLayer(JSON.parse(S.redo.pop()));
    rebuildWorld(); say('redone');
  }

  function say(m) { S.msg = m; S.msgAt = performance.now(); paintStatus(); }

  // Every chunk in range is thrown away and rebuilt. Editing changes the
  // ground under existing geometry, so a partial refresh would leave the old
  // paint sitting next to the new.
  function rebuildWorld() {
    if (!G || !G._chunks) return;
    for (const [key, ch] of G._chunks) {
      try { G.dressDrop(ch); } catch (e) {}
      try { G.roadDrop(ch); } catch (e) {}
      if (typeof GRIM_EDIT_RENDER !== 'undefined') { try { GRIM_EDIT_RENDER.drop(G, ch); } catch (e) {} }
      try { G.scene.remove(ch.mesh); ch.mesh.geometry.dispose(); } catch (e) {}
    }
    G._chunks.clear();
    G._terrAcc = 99;
    try { G.stepTerrain(0, 260); } catch (e) {}
    try { drawOverlay(); } catch (e) {}
    paintStatus();
  }

  // ---- the ground ray ------------------------------------------------------
  // Where the cursor touches the world. Marched against the height field
  // rather than raycast against chunk meshes: the meshes near the camera are
  // detailed and the ones far away are 8m coarse, so a mesh raycast would
  // give a different answer depending on how far you were standing back. The
  // height field is the same everywhere and is what every other system uses.
  function rayGround(nx, ny) {
    if (!G || !GRIM_WORLD.ready) return null;
    const T = G.T;
    const dir = new T.Vector3(nx, ny, 0.5).unproject(G.cam).sub(G.cam.position).normalize();
    const o = G.cam.position;
    if (dir.y > -0.0001 && o.y > 200) return null;
    let t = 0, step = 1.0, last = o.y - surfAt(o.x, o.z);
    for (let i = 0; i < 900; i++) {
      t += step;
      const px = o.x + dir.x * t, py = o.y + dir.y * t, pz = o.z + dir.z * t;
      if (t > 1400) return null;
      const d = py - surfAt(px, pz);
      if (d <= 0) {
        // Bisect the last step so the answer is metre-accurate rather than
        // step-accurate, which matters for half-metre snapping.
        let a = t - step, b = t;
        for (let k = 0; k < 24; k++) {
          const m = (a + b) / 2;
          const mx = o.x + dir.x * m, my = o.y + dir.y * m, mz = o.z + dir.z * m;
          if (my - surfAt(mx, mz) > 0) a = m; else b = m;
        }
        const fx = o.x + dir.x * b, fz = o.z + dir.z * b;
        return { x: fx, z: fz, y: surfAt(fx, fz) };
      }
      last = d;
      step = Math.max(0.5, Math.min(14, d * 0.7));
    }
    return null;
  }
  function surfAt(x, z) {
    const d = GRIM_EDIT.deckY ? GRIM_EDIT.deckY(x, z) : null;
    const h = GRIM_WORLD.height(x, z);
    return (d !== null && d > h) ? d : h;
  }

  // ---- tools ---------------------------------------------------------------
  const CELL = CFG.CELL || 4;
  function cellOf(v) { return Math.floor(v / CELL); }
  function chunkOfCell(cx, cz) {
    return Math.floor(cx * CELL / 64) + ',' + Math.floor(cz * CELL / 64);
  }

  // Ground paint. Writes into the layer's per-chunk cell lists so the stored
  // shape is exactly what the runtime indexes, with no conversion step that
  // could drift.
  function paintAt(pt, erase) {
    const L = GRIM_EDIT.raw;
    if (!L) return;
    const r = Math.max(1, Math.round(S.brush / CELL));
    const c0 = cellOf(pt.x), z0 = cellOf(pt.z);
    let touched = 0;
    for (let dz = -r; dz <= r; dz++) {
      for (let dx = -r; dx <= r; dx++) {
        if (dx * dx + dz * dz > r * r) continue;
        const cx = c0 + dx, cz = z0 + dz;
        const key = chunkOfCell(cx, cz);
        let list = L.paint[key];
        if (!list) { if (erase) continue; list = L.paint[key] = []; }
        let at = -1;
        for (let i = 0; i < list.length; i++) if (list[i][0] === cx && list[i][1] === cz) { at = i; break; }
        if (erase) { if (at >= 0) { list.splice(at, 1); touched++; } }
        else if (at >= 0) { if (list[at][2] !== S.surf) { list[at][2] = S.surf; touched++; } }
        else { list.push([cx, cz, S.surf]); touched++; }
        if (!list.length) delete L.paint[key];
      }
    }
    if (touched) { GRIM_EDIT.reindex(); S.dirty = true; }
    return touched;
  }

  // Terrain sculpt. Deltas on the same 4m grid as paint, bilinear at runtime
  // so the result is a smooth surface. Three safeguards from the plan are
  // enforced here rather than left to Kevin's judgment.
  function sculptAt(pt, mode, dt) {
    const L = GRIM_EDIT.raw;
    if (!L) return;
    const r = Math.max(1, Math.round(S.brush / CELL));
    const c0 = cellOf(pt.x), z0 = cellOf(pt.z);
    const MAXH = CFG.MAXH || 12;
    // Safeguard one: warn near a crossing. Bridge decks measure their own
    // banks, so moving ground under an abutment moves the deck with it.
    if (nearBridge(pt.x, pt.z, S.brush + 24)) say('careful: a crossing is within 24m, its deck samples these banks');
    const base = flatTarget(pt, mode, r, c0, z0);
    let touched = 0;
    for (let dz = -r; dz <= r; dz++) {
      for (let dx = -r; dx <= r; dx++) {
        const d2 = dx * dx + dz * dz;
        if (d2 > r * r) continue;
        const cx = c0 + dx, cz = z0 + dz;
        const fall = 1 - Math.sqrt(d2) / r;
        const w = fall * fall * (3 - 2 * fall);
        const key = chunkOfCell(cx, cz);
        let list = L.height[key]; if (!list) list = L.height[key] = [];
        let at = -1;
        for (let i = 0; i < list.length; i++) if (list[i][0] === cx && list[i][1] === cz) { at = i; break; }
        const cur = at >= 0 ? list[at][2] : 0;
        const gen = GRIM_WORLD.height(cx * CELL + CELL / 2, cz * CELL + CELL / 2) - cur;
        let next = cur;
        if (mode === 'raise') next = cur + 2.6 * w * dt * S.strength;
        else if (mode === 'lower') next = cur - 2.6 * w * dt * S.strength;
        else if (mode === 'flat') {
          // Safeguard two: never flatten perfectly level. The routine that
          // walks things out of water marches to the world origin on dead
          // flat ground, so a hand-authored parade square would quietly
          // teleport every deer on it.
          const tilt = ((cx * 7 + cz * 13) % 5 - 2) * (CFG.FLATMIN || 0.06) * 0.5;
          next = cur + ((base + tilt - gen) - cur) * Math.min(1, w * dt * 3.4 * S.strength);
        } else if (mode === 'smooth') {
          const avg = neighbourAvg(L, cx, cz);
          next = cur + (avg - cur) * Math.min(1, w * dt * 3.0 * S.strength);
        }
        if (next > MAXH) next = MAXH; if (next < -MAXH) next = -MAXH;
        next = +next.toFixed(3);
        if (next === cur) continue;
        if (Math.abs(next) < 0.001) { if (at >= 0) list.splice(at, 1); }
        else if (at >= 0) list[at][2] = next;
        else list.push([cx, cz, next]);
        touched++;
        if (!list.length) delete L.height[key];
      }
    }
    if (touched) { GRIM_EDIT.reindex(); S.dirty = true; }
    return touched;
  }
  function flatTarget(pt, mode, r, c0, z0) {
    if (mode !== 'flat') return 0;
    return GRIM_WORLD.height(pt.x, pt.z);
  }
  function neighbourAvg(L, cx, cz) {
    let s = 0, n = 0;
    for (let dz = -1; dz <= 1; dz++) for (let dx = -1; dx <= 1; dx++) {
      if (!dx && !dz) continue;
      const key = chunkOfCell(cx + dx, cz + dz);
      const list = L.height[key];
      let v = 0;
      if (list) for (let i = 0; i < list.length; i++) {
        if (list[i][0] === cx + dx && list[i][1] === cz + dz) { v = list[i][2]; break; }
      }
      s += v; n++;
    }
    return n ? s / n : 0;
  }
  function nearBridge(x, z, d) {
    const B = (typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.bridges) || [];
    for (const b of B) {
      const bx = b.x !== undefined ? b.x : (b[0] || 0), bz = b.z !== undefined ? b.z : (b[1] || 0);
      if (Math.hypot(x - bx, z - bz) < d + (b.span || 60) / 2) return true;
    }
    return false;
  }

  // Object placement.
  function snap(v) { return S.freePlace ? v : Math.round(v / (CFG.SNAP || 0.5)) * (CFG.SNAP || 0.5); }
  function placeAt(pt) {
    const L = GRIM_EDIT.raw;
    if (!L || !GRIM_EDIT_CATALOG[S.kind]) return;
    pushUndo();
    L.objects.push({
      i: 'o' + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36),
      k: S.kind, x: snap(pt.x), z: snap(pt.z), y: 0, r: S.rot, s: S.scale, t: ''
    });
    GRIM_EDIT.reindex();
    rebuildWorld();
    say('placed ' + GRIM_EDIT_CATALOG[S.kind].label);
  }
  function pickObject(pt) {
    const L = GRIM_EDIT.raw;
    if (!L) return null;
    let best = null, bd = 4.5;
    for (const o of L.objects) {
      const d = Math.hypot(o.x - pt.x, o.z - pt.z);
      if (d < bd) { bd = d; best = o; }
    }
    return best;
  }
  function deleteSel() {
    const L = GRIM_EDIT.raw;
    if (!L || !S.sel) return say('nothing selected');
    pushUndo();
    const i = L.objects.indexOf(S.sel);
    if (i >= 0) L.objects.splice(i, 1);
    S.sel = null;
    GRIM_EDIT.reindex(); rebuildWorld(); say('deleted');
  }
  // Deleting a PROCEDURAL prop is different: it is not in the layer, it is
  // grown by the dressing pass from the world seed. It gets recorded as a
  // removal by its stable node id instead, which the dressing pass then skips
  // on every machine.
  function deleteProcedural(pt) {
    const L = GRIM_EDIT.raw;
    if (!L || !G.zoneNodes) return false;
    let best = null, bd = 3.4;
    for (const n of G.zoneNodes) {
      if (!n || !n.g || !n.nid) continue;
      const d = Math.hypot(n.g.position.x - pt.x, n.g.position.z - pt.z);
      if (d < bd) { bd = d; best = n; }
    }
    if (!best) return false;
    pushUndo();
    L.removed.push(best.nid);
    GRIM_EDIT.reindex(); rebuildWorld();
    say('removed the generated ' + best.kind);
    return true;
  }

  // Roads: click waypoints, Enter commits the spline.
  function roadClick(pt) {
    if (!S.road) S.road = [];
    S.road.push([+pt.x.toFixed(2), +pt.z.toFixed(2)]);
    say('road: ' + S.road.length + ' points, Enter to lay it, Escape to cancel');
  }
  function roadCommit() {
    const L = GRIM_EDIT.raw;
    if (!L || !S.road || S.road.length < 2) { S.road = null; return say('a road needs at least two points'); }
    pushUndo();
    L.roads.push({ w: S.roadW, s: S.surf, p: S.road });
    S.road = null;
    GRIM_EDIT.reindex(); rebuildWorld();
    say('road laid');
  }

  // Prefabs: everything inside the brush radius becomes a named stamp.
  function prefabSave(name, pt) {
    const L = GRIM_EDIT.raw;
    if (!L) return;
    const parts = [];
    for (const o of L.objects) {
      const dx = o.x - pt.x, dz = o.z - pt.z;
      if (Math.hypot(dx, dz) > S.brush) continue;
      parts.push({ k: o.k, dx: +dx.toFixed(2), dz: +dz.toFixed(2), dy: o.y || 0, r: o.r || 0, s: o.s || 1 });
    }
    if (!parts.length) return say('nothing inside the brush to save');
    pushUndo();
    L.prefabs[name] = parts;
    S.dirty = true;
    say('prefab "' + name + '" saved, ' + parts.length + ' pieces');
    paintPanel();
  }
  function prefabStamp(name, pt) {
    const L = GRIM_EDIT.raw;
    const parts = L && L.prefabs[name];
    if (!parts) return say('no prefab called ' + name);
    pushUndo();
    const c = Math.cos(S.rot), s = Math.sin(S.rot);
    for (const p of parts) {
      L.objects.push({
        i: 'o' + Date.now().toString(36) + Math.floor(Math.random() * 1e6).toString(36),
        k: p.k,
        x: snap(pt.x + p.dx * c - p.dz * s),
        z: snap(pt.z + p.dx * s + p.dz * c),
        y: p.dy || 0, r: (p.r || 0) + S.rot, s: p.s || 1, t: ''
      });
    }
    GRIM_EDIT.reindex(); rebuildWorld();
    say('stamped ' + name + ', ' + parts.length + ' pieces');
  }

  // ---- save and load -------------------------------------------------------
  async function probeKey(key) {
    try {
      const r = await fetch(CFG.URL, { method: 'HEAD', headers: { 'x-edit-key': key } });
      if (r.status === 204) return 'ok';
      if (r.status === 503) return 'no-key-configured';
      return 'bad';
    } catch (e) { return 'offline'; }
  }
  async function save() {
    if (S.saving) return;
    S.saving = true; say('saving');
    const body = GRIM_EDIT.exportLayer();
    try {
      const r = await fetch(CFG.URL, {
        method: 'PUT',
        headers: { 'x-edit-key': S.key, 'content-type': 'application/json' },
        body: body
      });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j.ok) {
        S.dirty = false;
        GRIM_EDIT.rev = j.rev;
        say('saved, revision ' + j.rev + ', ' + Math.round(body.length / 1024) + ' KB');
      } else {
        say('save refused: ' + (j.err || r.status) + ' (kept a local copy)');
        localBackup(body);
      }
    } catch (e) {
      say('save failed, network. Kept a local copy you can export.');
      localBackup(body);
    }
    S.saving = false;
    paintStatus();
  }
  // The editor must never be the reason an hour of work disappears. Every
  // save attempt, successful or not, also writes to this machine.
  function localBackup(body) {
    try { localStorage.setItem('grim-edit-backup', body); localStorage.setItem('grim-edit-backup-at', String(Date.now())); } catch (e) {}
  }
  function exportFile() {
    const body = GRIM_EDIT.exportLayer();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([body], { type: 'application/json' }));
    a.download = 'grim-world-edits.json';
    a.click();
    say('exported ' + Math.round(body.length / 1024) + ' KB');
  }
  function importFile() {
    const inp = document.createElement('input');
    inp.type = 'file'; inp.accept = 'application/json';
    inp.onchange = () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      const rd = new FileReader();
      rd.onload = () => {
        try {
          pushUndo();
          GRIM_EDIT.setLayer(JSON.parse(String(rd.result)));
          rebuildWorld(); say('imported');
        } catch (e) { say('that file is not a valid edit layer'); }
      };
      rd.readAsText(f);
    };
    inp.click();
  }

  // ---- the free camera -----------------------------------------------------
  function camTick(dt) {
    const k = S.keys, c = S.cam;
    const fast = k['shift'] ? 4.2 : (k['control'] ? 0.25 : 1);
    const acc = 90 * fast;
    const fx = Math.sin(c.yaw), fz = Math.cos(c.yaw);
    let ax = 0, az = 0, ay = 0;
    if (k['w']) { ax -= fx; az -= fz; }
    if (k['s']) { ax += fx; az += fz; }
    if (k['a']) { ax -= fz; az += fx; }
    if (k['d']) { ax += fz; az -= fx; }
    if (k['e'] || k[' ']) ay += 1;
    if (k['q']) ay -= 1;
    const len = Math.hypot(ax, az);
    if (len > 0) { ax /= len; az /= len; }
    // Pitch feeds the forward vector so looking down and pressing W descends,
    // which is what every editor camera in the world does.
    const pitchDrop = Math.sin(c.pit);
    S.vel.x += ax * acc * dt;
    S.vel.z += az * acc * dt;
    S.vel.y += (ay * acc + (len > 0 ? -pitchDrop * acc * (k['w'] ? 1 : k['s'] ? -1 : 0) : 0)) * dt;
    const damp = Math.exp(-9 * dt);
    S.vel.x *= damp; S.vel.y *= damp; S.vel.z *= damp;
    c.x += S.vel.x * dt; c.y += S.vel.y * dt; c.z += S.vel.z * dt;
    // Never let the camera sink under the world: from below, the ground is
    // invisible (front faces only) and it looks exactly like the world
    // failed to load.
    const floor = surfAt(c.x, c.z) + 1.2;
    if (c.y < floor) { c.y = floor; if (S.vel.y < 0) S.vel.y = 0; }
    if (c.y > 900) { c.y = 900; S.vel.y = Math.min(0, S.vel.y); }
  }

  function applyCam() {
    const T = G.T, c = S.cam;
    G.cam.position.set(c.x, c.y, c.z);
    G.cam.rotation.set(0, 0, 0);
    G.cam.rotateY(c.yaw);
    G.cam.rotateX(c.pit);
    // The terrain streamer follows the player, so the player is parked under
    // the camera. Nothing else about the player runs in editor mode.
    if (G.me) { G.me.pos.x = c.x; G.me.pos.z = c.z; }
  }

  // ---- the interface -------------------------------------------------------
  function el(tag, css, txt) {
    const e = document.createElement(tag);
    if (css) e.style.cssText = css;
    if (txt !== undefined) e.textContent = txt;
    return e;
  }
  const BTN = 'background:#2c2c2c;color:#ededed;border:1px solid #383838;border-radius:7px;' +
              'padding:6px 9px;font:600 12px system-ui;cursor:pointer;margin:2px 2px 0 0;';
  const BTN_ON = BTN.replace('#2c2c2c', GOLD).replace('color:#ededed', 'color:#1A1A1A') +
                 'border-color:' + GOLD + ';';

  function build() {
    const wrap = el('div', 'position:fixed;left:0;top:0;bottom:0;width:250px;z-index:9000;' +
      'background:rgba(26,26,26,.94);border-right:1px solid #383838;color:#ededed;' +
      'font:12px system-ui;overflow-y:auto;padding:10px 10px 40px;');
    const h = el('div', 'color:' + GOLD + ';font:800 14px system-ui;letter-spacing:.4px;margin-bottom:2px',
      'GRIM WORLD EDITOR');
    const sub = el('div', 'color:#8f8f8f;font-size:10px;margin-bottom:10px',
      'the live game with an editor flag');
    const tools = el('div', 'margin-bottom:8px');
    const body = el('div');
    const status = el('div', 'position:fixed;left:250px;bottom:0;right:0;z-index:9000;' +
      'background:rgba(26,26,26,.88);border-top:1px solid #383838;color:#8f8f8f;' +
      'font:11px ui-monospace,monospace;padding:5px 10px;');
    const help = el('div', 'position:fixed;right:10px;top:10px;z-index:9000;width:210px;' +
      'background:rgba(26,26,26,.88);border:1px solid #383838;border-radius:8px;' +
      'color:#8f8f8f;font:11px system-ui;padding:8px 10px;line-height:1.5');
    help.innerHTML =
      '<b style="color:' + GOLD + '">Camera</b><br>' +
      'WASD move, Q and E down and up<br>Shift fast, Ctrl slow<br>Right mouse drag to look<br>' +
      '<b style="color:' + GOLD + '">Editing</b><br>' +
      'Left click uses the tool<br>Alt click erases or picks<br>' +
      'Wheel rotates, Ctrl wheel resizes the brush<br>' +
      'Ctrl Z undo, Ctrl Y redo, Ctrl S save<br>Ctrl C copy, Ctrl V paste<br>' +
      'Alt right click picks the surface<br>Delete removes the selection<br>' +
      'Enter lays a road, Escape cancels';
    wrap.appendChild(h); wrap.appendChild(sub); wrap.appendChild(tools); wrap.appendChild(body);
    document.body.appendChild(wrap);
    document.body.appendChild(status);
    document.body.appendChild(help);
    dom = { wrap, tools, body, status, help };
    paintTools(); paintPanel(); paintStatus();
  }

  const TOOLS = [
    ['paint', 'Paint'], ['road', 'Roads'], ['place', 'Place'],
    ['select', 'Select'], ['sculpt', 'Sculpt'], ['spawn', 'Spawns'],
    ['district', 'Districts'], ['prefab', 'Prefabs'], ['world', 'World']
  ];

  // The creature list is read off the world the editor is standing in rather
  // than hardcoded, so a monster added to the game appears here on the next
  // boot with nothing to maintain. Falls back to the roster the world plan
  // names if nothing has streamed in yet.
  function creatureKinds() {
    const seen = {};
    for (const n of (G && G.npcs) || []) {
      const nm = String((n && n.name) || '').trim();
      if (nm) seen[nm] = 1;
    }
    const list = Object.keys(seen).sort();
    return list.length ? list : ['GOBLIN', 'WOLF', 'BOAR', 'DEER', 'PLAGUE RAT'];
  }
  function paintTools() {
    dom.tools.innerHTML = '';
    for (const [id, label] of TOOLS) {
      const b = el('button', S.tool === id ? BTN_ON : BTN, label);
      b.onclick = () => { S.tool = id; S.road = null; paintTools(); paintPanel(); };
      dom.tools.appendChild(b);
    }
  }

  function row(parent, label) {
    const r = el('div', 'margin:8px 0 3px;color:' + GOLD + ';font:700 10px system-ui;letter-spacing:.5px;text-transform:uppercase', label);
    parent.appendChild(r);
    return parent;
  }
  function slider(parent, label, min, max, step, val, on) {
    const w = el('div', 'margin:5px 0');
    const t = el('div', 'color:#8f8f8f;font-size:10px;margin-bottom:2px', label + ': ' + val);
    const i = el('input', 'width:100%');
    i.type = 'range'; i.min = min; i.max = max; i.step = step; i.value = val;
    i.oninput = () => { const v = +i.value; t.textContent = label + ': ' + v; on(v); };
    w.appendChild(t); w.appendChild(i); parent.appendChild(w);
    return i;
  }

  function paintPanel() {
    const b = dom.body;
    b.innerHTML = '';
    if (S.tool === 'paint' || S.tool === 'road') {
      row(b, 'Surface');
      const grid = el('div', 'display:grid;grid-template-columns:repeat(2,1fr);gap:3px');
      SURF_NAMES.forEach((n, i) => {
        const bt = el('button', (S.surf === i ? BTN_ON : BTN) + 'font-size:10px;padding:5px 4px;margin:0;text-align:left', i + ' ' + n);
        bt.onclick = () => { S.surf = i; paintPanel(); };
        grid.appendChild(bt);
      });
      b.appendChild(grid);
      if (S.tool === 'paint') {
        row(b, 'Brush');
        slider(b, 'radius, metres', 2, 16, 1, S.brush, v => S.brush = v);
        const er = el('div', 'color:#8f8f8f;font-size:10px;margin-top:6px',
          'Alt click erases back to the generated ground. Alt right click picks the surface under the cursor.');
        b.appendChild(er);
      } else {
        row(b, 'Road');
        slider(b, 'width, metres', 2, 24, 1, S.roadW, v => S.roadW = v);
        const n = el('div', 'color:#8f8f8f;font-size:10px;margin-top:6px',
          'Click to drop waypoints, Enter to lay the road, Escape to cancel. The curve is smoothed and the edges feather.');
        b.appendChild(n);
        const undoR = el('button', BTN, 'Remove last road');
        undoR.onclick = () => {
          const L = GRIM_EDIT.raw;
          if (!L || !L.roads.length) return say('no roads yet');
          pushUndo(); L.roads.pop(); GRIM_EDIT.reindex(); rebuildWorld(); say('road removed');
        };
        b.appendChild(undoR);
      }
    } else if (S.tool === 'place') {
      row(b, 'Catalog');
      const tabs = el('div', 'margin-bottom:4px');
      for (const t of ['build', 'props', 'nature']) {
        const bt = el('button', (S.tab === t ? BTN_ON : BTN) + 'font-size:10px', t);
        bt.onclick = () => { S.tab = t; paintPanel(); };
        tabs.appendChild(bt);
      }
      b.appendChild(tabs);
      const list = el('div', 'display:grid;grid-template-columns:1fr;gap:2px;max-height:250px;overflow-y:auto');
      for (const k in GRIM_EDIT_CATALOG) {
        const c = GRIM_EDIT_CATALOG[k];
        if (c.tab !== S.tab) continue;
        const bt = el('button', (S.kind === k ? BTN_ON : BTN) + 'font-size:11px;text-align:left;margin:0', c.label);
        bt.onclick = () => { S.kind = k; paintPanel(); };
        list.appendChild(bt);
      }
      b.appendChild(list);
      row(b, 'Placement');
      slider(b, 'scale', 0.3, 4, 0.1, S.scale, v => S.scale = v);
      const fp = el('button', S.freePlace ? BTN_ON : BTN, S.freePlace ? 'Free placement ON' : 'Snap to half metre');
      fp.onclick = () => { S.freePlace = !S.freePlace; paintPanel(); };
      b.appendChild(fp);
      b.appendChild(el('div', 'color:#8f8f8f;font-size:10px;margin-top:6px',
        'Wheel rotates the ghost. Alt click removes a generated tree or rock instead of placing.'));
    } else if (S.tool === 'select') {
      row(b, 'Selection');
      if (!S.sel) b.appendChild(el('div', 'color:#8f8f8f;font-size:11px', 'Click an object you placed.'));
      else {
        const c = GRIM_EDIT_CATALOG[S.sel.k];
        b.appendChild(el('div', 'color:#ededed;font-size:12px;font-weight:700', (c && c.label) || S.sel.k));
        b.appendChild(el('div', 'color:#8f8f8f;font-size:10px',
          S.sel.x.toFixed(1) + ', ' + S.sel.z.toFixed(1) + '  scale ' + (S.sel.s || 1).toFixed(2)));
        slider(b, 'rotation, degrees', 0, 359, 1, Math.round((S.sel.r || 0) * 57.2958),
          v => { S.sel.r = v / 57.2958; GRIM_EDIT.reindex(); rebuildWorld(); });
        slider(b, 'scale', 0.3, 4, 0.05, S.sel.s || 1,
          v => { S.sel.s = v; GRIM_EDIT.reindex(); rebuildWorld(); });
        slider(b, 'lift, metres', -3, 12, 0.1, S.sel.y || 0,
          v => { S.sel.y = v; GRIM_EDIT.reindex(); rebuildWorld(); });
        const dup = el('button', BTN, 'Duplicate');
        dup.onclick = () => {
          pushUndo();
          const n = Object.assign({}, S.sel);
          n.i = 'o' + Date.now().toString(36); n.x += 2; n.z += 2;
          GRIM_EDIT.raw.objects.push(n); S.sel = n;
          GRIM_EDIT.reindex(); rebuildWorld(); paintPanel();
        };
        const cp = el('button', BTN, 'Copy');
        cp.onclick = () => { S.clipboard = Object.assign({}, S.sel); say('copied'); };
        const del = el('button', BTN.replace('#ededed', '#e0574f'), 'Delete');
        del.onclick = () => { deleteSel(); paintPanel(); };
        b.appendChild(dup); b.appendChild(cp); b.appendChild(del);
      }
    } else if (S.tool === 'sculpt') {
      row(b, 'Terrain');
      for (const m of ['raise', 'lower', 'flat', 'smooth']) {
        const bt = el('button', S.sculpt === m ? BTN_ON : BTN, m);
        bt.onclick = () => { S.sculpt = m; paintPanel(); };
        b.appendChild(bt);
      }
      slider(b, 'radius, metres', 2, 40, 1, S.brush, v => S.brush = v);
      slider(b, 'strength', 0.1, 3, 0.1, S.strength, v => S.strength = v);
      b.appendChild(el('div', 'color:#8f8f8f;font-size:10px;margin-top:6px',
        'Hold the left mouse button and move. Flatten never leaves ground perfectly level on purpose, ' +
        'and chunks you sculpt are re-dressed so props sit on the new shape.'));
    } else if (S.tool === 'spawn') {
      row(b, 'Creature');
      const kinds = creatureKinds();
      if (!S.spawnKind) S.spawnKind = kinds[0];
      const list = el('div', 'max-height:220px;overflow-y:auto');
      for (const k of kinds) {
        const bt = el('button', (S.spawnKind === k ? BTN_ON : BTN) + 'display:block;width:100%;text-align:left;font-size:11px;margin:0 0 2px', k);
        bt.onclick = () => { S.spawnKind = k; paintPanel(); };
        list.appendChild(bt);
      }
      b.appendChild(list);
      row(b, 'Group');
      slider(b, 'how many', 1, 12, 1, S.spawnN || 1, v => S.spawnN = v);
      slider(b, 'roam radius, metres', 0, 80, 1, S.spawnRad == null ? 12 : S.spawnRad, v => S.spawnRad = v);
      b.appendChild(el('div', 'color:#8f8f8f;font-size:10px;margin-top:6px;line-height:1.5',
        'Click the ground to drop a spawn marker. Alt click removes the nearest one. ' +
        'Markers are stored in the layer and drawn here in the editor. Making the world ' +
        'actually spawn from them is server work and is not wired up yet, so this authors ' +
        'the map rather than changing the live world.'));
      const n = (GRIM_EDIT.raw && GRIM_EDIT.raw.spawns.length) || 0;
      b.appendChild(el('div', 'color:' + GOLD + ';font-size:11px;margin-top:6px',
        n + ' spawn marker' + (n === 1 ? '' : 's') + ' placed'));
    } else if (S.tool === 'district') {
      row(b, 'Housing districts');
      b.appendChild(el('div', 'color:#8f8f8f;font-size:10px;line-height:1.5',
        'Click to trace a boundary, Enter to close it, Escape to cancel. Districts are ' +
        'where players may plant a mailbox and claim a plot. Flatten the ground inside ' +
        'one with the sculpt tool before you publish it.'));
      const nm2 = el('input', 'width:100%;background:#232323;border:1px solid #383838;color:#ededed;border-radius:6px;padding:6px;margin-top:6px;font:12px system-ui');
      nm2.placeholder = 'district name'; nm2.value = S.districtName || '';
      nm2.oninput = () => S.districtName = nm2.value;
      b.appendChild(nm2);
      if (S.districtPts) b.appendChild(el('div', 'color:' + GOLD + ';font-size:11px;margin-top:6px',
        S.districtPts.length + ' points, Enter to close'));
      const LD = GRIM_EDIT.raw;
      for (const d of (LD ? LD.districts : [])) {
        const bt = el('button', BTN + 'display:block;width:100%;text-align:left', d.n + '  (' + d.poly.length + ' pts)');
        bt.onclick = () => {
          let x = 0, z = 0;
          for (const p of d.poly) { x += p[0]; z += p[1]; }
          S.cam.x = x / d.poly.length; S.cam.z = z / d.poly.length;
          S.cam.y = surfAt(S.cam.x, S.cam.z) + 70;
          S.vel.x = S.vel.y = S.vel.z = 0; rebuildWorld();
        };
        b.appendChild(bt);
      }
      if (LD && LD.districts.length) {
        const rm = el('button', BTN.replace('#ededed', '#e0574f'), 'Remove last district');
        rm.onclick = () => { pushUndo(); LD.districts.pop(); GRIM_EDIT.reindex(); drawOverlay(); paintPanel(); say('district removed'); };
        b.appendChild(rm);
      }
    } else if (S.tool === 'prefab') {
      row(b, 'Prefabs');
      const nm = el('input', 'width:100%;background:#232323;border:1px solid #383838;color:#ededed;border-radius:6px;padding:6px;font:12px system-ui');
      nm.placeholder = 'name'; nm.value = S.prefabName;
      nm.oninput = () => S.prefabName = nm.value;
      b.appendChild(nm);
      const sv = el('button', BTN, 'Save what is under the brush');
      sv.onclick = () => {
        if (!S.prefabName) return say('give the prefab a name first');
        if (!S.hoverPt) return say('point at the ground first');
        prefabSave(S.prefabName, S.hoverPt);
      };
      b.appendChild(sv);
      slider(b, 'capture radius, metres', 4, 60, 1, S.brush, v => S.brush = v);
      const L = GRIM_EDIT.raw;
      row(b, 'Stamp');
      const names = L ? Object.keys(L.prefabs) : [];
      if (!names.length) b.appendChild(el('div', 'color:#8f8f8f;font-size:11px', 'No prefabs saved yet.'));
      for (const n of names) {
        const bt = el('button', BTN + 'display:block;width:100%;text-align:left', n + '  (' + L.prefabs[n].length + ')');
        bt.onclick = () => { S.stamp = n; say('click the ground to stamp ' + n); };
        b.appendChild(bt);
      }
    } else if (S.tool === 'world') {
      row(b, 'Layer');
      const st = GRIM_EDIT.stats();
      const info = el('div', 'color:#8f8f8f;font-size:11px;line-height:1.6');
      info.innerHTML =
        'paint cells: ' + st.paint + '<br>sculpt cells: ' + st.height + '<br>roads: ' + st.roads +
        '<br>objects: ' + st.objects + '<br>spawns: ' + st.spawns + '<br>removed props: ' + st.removed +
        '<br>prefabs: ' + st.prefabs + '<br>size: ' + Math.round(st.bytes / 1024) + ' KB' +
        '<br>revision: ' + st.rev;
      b.appendChild(info);
      row(b, 'Bookmarks');
      const bn = el('input', 'width:100%;background:#232323;border:1px solid #383838;color:#ededed;border-radius:6px;padding:6px;font:12px system-ui');
      bn.placeholder = 'name this spot';
      b.appendChild(bn);
      const add = el('button', BTN, 'Bookmark here');
      add.onclick = () => {
        const L = GRIM_EDIT.raw; if (!L) return;
        pushUndo();
        L.bookmarks.push({ n: bn.value || ('mark ' + (L.bookmarks.length + 1)), x: S.cam.x, y: S.cam.y, z: S.cam.z, yaw: S.cam.yaw, pit: S.cam.pit });
        S.dirty = true; paintPanel();
      };
      b.appendChild(add);
      const L2 = GRIM_EDIT.raw;
      for (const m of (L2 ? L2.bookmarks : [])) {
        const bt = el('button', BTN + 'display:block;width:100%;text-align:left', m.n);
        bt.onclick = () => {
          S.cam.x = m.x; S.cam.y = m.y; S.cam.z = m.z; S.cam.yaw = m.yaw; S.cam.pit = m.pit;
          S.vel.x = S.vel.y = S.vel.z = 0; rebuildWorld();
        };
        b.appendChild(bt);
      }
      row(b, 'Jump to');
      const jx = el('input', 'width:47%;background:#232323;border:1px solid #383838;color:#ededed;border-radius:6px;padding:6px;margin-right:4px;font:12px system-ui');
      const jz = el('input', 'width:47%;background:#232323;border:1px solid #383838;color:#ededed;border-radius:6px;padding:6px;font:12px system-ui');
      jx.placeholder = 'x'; jz.placeholder = 'z';
      b.appendChild(jx); b.appendChild(jz);
      const go = el('button', BTN, 'Go');
      go.onclick = () => {
        const x = +jx.value, z = +jz.value;
        if (!isFinite(x) || !isFinite(z)) return say('two numbers please');
        S.cam.x = x; S.cam.z = z; S.cam.y = surfAt(x, z) + 45;
        S.vel.x = S.vel.y = S.vel.z = 0; rebuildWorld();
      };
      b.appendChild(go);
      row(b, 'Save');
      const sv = el('button', BTN_ON, 'Save to the world');
      sv.onclick = save;
      const ex = el('button', BTN, 'Export file');
      ex.onclick = exportFile;
      const im = el('button', BTN, 'Import file');
      im.onclick = importFile;
      b.appendChild(sv); b.appendChild(ex); b.appendChild(im);
      row(b, 'Danger');
      const rv = el('button', BTN.replace('#ededed', '#e0574f'), 'Revert everything to generated');
      rv.onclick = () => {
        if (!confirm('Throw away the entire authored layer and go back to the generated world?')) return;
        pushUndo(); GRIM_EDIT.setLayer(null); rebuildWorld(); say('reverted to the generated world');
      };
      b.appendChild(rv);
    }
  }

  function paintStatus() {
    if (!dom) return;
    const p = S.hoverPt;
    const st = GRIM_EDIT.stats();
    const bits = [
      'cam ' + S.cam.x.toFixed(0) + ', ' + S.cam.y.toFixed(0) + ', ' + S.cam.z.toFixed(0),
      p ? ('cursor ' + p.x.toFixed(1) + ', ' + p.z.toFixed(1) + '  ground ' + p.y.toFixed(1) + 'm') : 'cursor off world',
      'tool ' + S.tool,
      st.objects + ' objects, ' + st.paint + ' cells',
      S.dirty ? 'UNSAVED' : 'saved'
    ];
    dom.status.textContent = bits.join('   |   ') + (S.msg ? ('   |   ' + S.msg) : '');
    dom.status.style.color = S.dirty ? GOLD : '#8f8f8f';
  }

  // ---- input ---------------------------------------------------------------
  function bind() {
    const c = G.renderer.domElement;
    window.addEventListener('keydown', e => {
      if (!S.on) return;
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return;
      const k = e.key.toLowerCase();
      S.keys[k] = true;
      if (e.ctrlKey && k === 'z') { e.preventDefault(); undo(); }
      else if (e.ctrlKey && k === 'y') { e.preventDefault(); redo(); }
      else if (e.ctrlKey && k === 's') { e.preventDefault(); save(); }
      else if (e.ctrlKey && k === 'c') { if (S.sel) { S.clipboard = Object.assign({}, S.sel); say('copied'); } }
      else if (e.ctrlKey && k === 'v') { if (S.hoverPt) paste(S.hoverPt); else say('point at the ground first'); }
      else if (k === 'delete' || k === 'backspace') { if (S.sel) deleteSel(); }
      else if (k === 'enter') {
        if (S.tool === 'road') roadCommit();
        else if (S.tool === 'district') districtCommit();
      }
      else if (k === 'escape') {
        S.road = null; S.sel = null; S.stamp = null; S.districtPts = null;
        drawOverlay(); say('cancelled'); paintPanel();
      }
    });
    window.addEventListener('keyup', e => { S.keys[e.key.toLowerCase()] = false; });
    window.addEventListener('blur', () => { S.keys = {}; });

    c.addEventListener('contextmenu', e => { if (S.on) e.preventDefault(); });
    c.addEventListener('mousedown', e => {
      if (!S.on) return;
      if (e.button === 2) {
        // Alt right click is the eyedropper: take the surface under the
        // cursor as the current brush, which is how you match ground you
        // painted an hour ago without remembering its number.
        if (e.altKey) { eyedrop(e); return; }
        S.look = true; S.lastX = e.clientX; S.lastY = e.clientY; return;
      }
      if (e.button === 0) { S.drag = true; useTool(e, true); }
    });
    window.addEventListener('mouseup', e => {
      if (e.button === 2) S.look = false;
      if (e.button === 0) { S.drag = false; S.lastPaintCell = -1; }
    });
    window.addEventListener('mousemove', e => {
      if (!S.on) return;
      if (S.look) {
        S.cam.yaw -= (e.clientX - S.lastX) * 0.0032;
        S.cam.pit -= (e.clientY - S.lastY) * 0.0032;
        S.cam.pit = Math.max(-1.5, Math.min(1.5, S.cam.pit));
        S.lastX = e.clientX; S.lastY = e.clientY;
      }
      S.mouse = e;
      if (S.drag) useTool(e, false);
    });
    c.addEventListener('wheel', e => {
      if (!S.on) return;
      e.preventDefault();
      if (e.ctrlKey) { S.brush = Math.max(1, Math.min(60, S.brush + (e.deltaY > 0 ? -1 : 1))); paintPanel(); }
      else { S.rot = (S.rot + (e.deltaY > 0 ? -0.2618 : 0.2618)) % (Math.PI * 2); }
    }, { passive: false });

    window.addEventListener('beforeunload', e => {
      if (S.on && S.dirty) { e.preventDefault(); e.returnValue = ''; }
    });
  }

  // Reads the surface actually in effect at the cursor: an authored road
  // first, then authored paint, then whatever the generator put there. So
  // eyedropping unpainted ground gives you the ground's own surface, not
  // "nothing", which is what makes it useful for blending into a zone.
  function eyedropAt(pt) {
    const rd = GRIM_EDIT.roadAt(pt.x, pt.z);
    const pn = GRIM_EDIT.paintAt(pt.x, pt.z);
    if (rd && rd[1] > 0.5) return rd[0] | 0;
    if (pn && pn[1] > 0.5) return pn[0] | 0;
    const su = [0, 0, 0, 0, 0, 0, 0];
    const h = GRIM_WORLD.height(pt.x, pt.z);
    G.groundSurface(GRIM_WORLD.zone(pt.x, pt.z), h, pt.x, pt.z, su);
    return ((su[4] > 0.5) ? su[1] : su[0]) | 0;
  }
  function eyedrop(e) {
    const [nx, ny] = ndc(e);
    const pt = rayGround(nx, ny);
    if (!pt) return say('point at the ground');
    S.surf = eyedropAt(pt);
    paintPanel();
    say('picked ' + S.surf + ' ' + (SURF_NAMES[S.surf] || ''));
  }

  function paste(pt) {
    const L = GRIM_EDIT.raw;
    if (!L || !S.clipboard) return say('nothing copied');
    pushUndo();
    const n = Object.assign({}, S.clipboard);
    n.i = 'o' + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36);
    n.x = snap(pt.x); n.z = snap(pt.z);
    L.objects.push(n);
    GRIM_EDIT.reindex(); rebuildWorld();
    say('pasted');
  }

  function ndc(e) {
    const r = G.renderer.domElement.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1];
  }

  function useTool(e, first) {
    const [nx, ny] = ndc(e);
    const pt = rayGround(nx, ny);
    if (!pt) return;
    return applyTool(pt, first, !!e.altKey);
  }

  // The whole tool path from a ground point onwards, including the undo push.
  // Split out so the harness drives exactly what the mouse drives: a test that
  // called the individual brush functions would prove the brush maths and miss
  // that nothing had been recorded for undo.
  function applyTool(pt, first, alt) {
    if (S.tool === 'paint') {
      const cellId = cellOf(pt.x) * 100000 + cellOf(pt.z);
      if (!first && cellId === S.lastPaintCell) return;
      S.lastPaintCell = cellId;
      if (first) pushUndo();
      if (paintAt(pt, alt)) repaintChunksNear(pt, S.brush + 8);
    } else if (S.tool === 'sculpt') {
      if (first) pushUndo();
      if (sculptAt(pt, S.sculpt || 'raise', 0.05)) repaintChunksNear(pt, S.brush + 12);
    } else if (S.tool === 'road') {
      if (first) roadClick(pt);
    } else if (S.tool === 'place') {
      if (!first) return;
      if (S.stamp) { prefabStamp(S.stamp, pt); S.stamp = null; return; }
      if (alt) { if (!deleteProcedural(pt)) say('nothing generated close enough to remove'); return; }
      placeAt(pt);
    } else if (S.tool === 'select') {
      if (!first) {
        if (S.sel) { S.sel.x = snap(pt.x); S.sel.z = snap(pt.z); GRIM_EDIT.reindex(); rebuildWorld(); }
        return;
      }
      S.sel = pickObject(pt);
      if (S.sel) pushUndo();
      paintPanel();
      say(S.sel ? 'selected, drag to move' : 'nothing there');
    } else if (S.tool === 'spawn') {
      if (!first) return;
      if (alt) removeSpawn(pt); else addSpawn(pt);
    } else if (S.tool === 'district') {
      if (!first) return;
      if (!S.districtPts) S.districtPts = [];
      S.districtPts.push([+pt.x.toFixed(1), +pt.z.toFixed(1)]);
      drawOverlay(); paintPanel();
      say('district: ' + S.districtPts.length + ' points, Enter to close');
    } else if (S.tool === 'prefab') {
      if (first && S.stamp) { prefabStamp(S.stamp, pt); S.stamp = null; }
    }
  }

  function addSpawn(pt) {
    const L = GRIM_EDIT.raw;
    if (!L) return;
    pushUndo();
    L.spawns.push({
      i: 's' + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36),
      k: S.spawnKind || 'GOBLIN',
      x: +pt.x.toFixed(2), z: +pt.z.toFixed(2), y: 0,
      n: S.spawnN || 1, rad: S.spawnRad == null ? 12 : S.spawnRad
    });
    GRIM_EDIT.reindex(); drawOverlay(); paintPanel();
    say('spawn marker: ' + (S.spawnN || 1) + ' x ' + (S.spawnKind || 'GOBLIN'));
  }
  function removeSpawn(pt) {
    const L = GRIM_EDIT.raw;
    if (!L || !L.spawns.length) return say('no spawn markers here');
    let bi = -1, bd = 8;
    for (let i = 0; i < L.spawns.length; i++) {
      const d = Math.hypot(L.spawns[i].x - pt.x, L.spawns[i].z - pt.z);
      if (d < bd) { bd = d; bi = i; }
    }
    if (bi < 0) return say('nothing close enough');
    pushUndo();
    L.spawns.splice(bi, 1);
    GRIM_EDIT.reindex(); drawOverlay(); paintPanel();
    say('spawn marker removed');
  }
  function districtCommit() {
    const L = GRIM_EDIT.raw;
    if (!L || !S.districtPts || S.districtPts.length < 3) {
      S.districtPts = null; drawOverlay();
      return say('a district needs at least three points');
    }
    pushUndo();
    L.districts.push({
      n: S.districtName || ('district ' + (L.districts.length + 1)),
      poly: S.districtPts, tiers: [1, 2, 3]
    });
    S.districtPts = null;
    GRIM_EDIT.reindex(); drawOverlay(); paintPanel();
    say('district closed');
  }

  // ---- editor-only overlay -------------------------------------------------
  // Spawn markers and district outlines are authoring aids, not world content,
  // so they are drawn into a group that exists ONLY in editor mode and is
  // never built by a player's client. Lines rather than meshes: they have to
  // read from the air at a hundred metres.
  function drawOverlay() {
    if (!G || !G.T) return;
    const T = G.T;
    if (S.overlay) { G.scene.remove(S.overlay); disposeTree(S.overlay); }
    const grp = new T.Group();
    grp.name = '__editOverlay';
    const L = GRIM_EDIT.raw;
    const ring = (x, z, r, col, lift) => {
      const pts = [];
      for (let i = 0; i <= 40; i++) {
        const a = (i / 40) * Math.PI * 2;
        const px = x + Math.cos(a) * r, pz = z + Math.sin(a) * r;
        pts.push(new T.Vector3(px, surfAt(px, pz) + (lift || 0.25), pz));
      }
      const g = new T.BufferGeometry().setFromPoints(pts);
      return new T.Line(g, new T.LineBasicMaterial({ color: col }));
    };
    if (L) {
      for (const sp of L.spawns) {
        grp.add(ring(sp.x, sp.z, Math.max(1.5, sp.rad || 12), 0xe0574f));
        const post = new T.Mesh(new T.BoxGeometry(0.3, 3, 0.3),
          new T.MeshBasicMaterial({ color: 0xe0574f }));
        post.position.set(sp.x, surfAt(sp.x, sp.z) + 1.5, sp.z);
        grp.add(post);
      }
      for (const d of L.districts) grp.add(poly(T, d.poly, 0x4a9cf3, true));
    }
    if (S.districtPts && S.districtPts.length) grp.add(poly(T, S.districtPts, 0xF3DC00, false));
    S.overlay = grp;
    G.scene.add(grp);
  }
  function poly(T, pts, col, closed) {
    const v = pts.map(p => new T.Vector3(p[0], surfAt(p[0], p[1]) + 0.35, p[1]));
    if (closed && v.length) v.push(v[0].clone());
    return new T.Line(new T.BufferGeometry().setFromPoints(v),
      new T.LineBasicMaterial({ color: col }));
  }
  function disposeTree(o) {
    o.traverse(n => { if (n.geometry) { try { n.geometry.dispose(); } catch (e) {} } });
  }

  // Only the chunks the edit actually touched are rebuilt, so painting stays
  // interactive instead of regenerating the whole ring on every brush stroke.
  function repaintChunksNear(pt, r) {
    if (!G._chunks) return;
    const cx0 = Math.floor((pt.x - r) / 64), cx1 = Math.floor((pt.x + r) / 64);
    const cz0 = Math.floor((pt.z - r) / 64), cz1 = Math.floor((pt.z + r) / 64);
    for (let cx = cx0; cx <= cx1; cx++) for (let cz = cz0; cz <= cz1; cz++) {
      const key = cx + ',' + cz;
      const ch = G._chunks.get(key);
      if (!ch) continue;
      try { G.dressDrop(ch); } catch (err) {}
      try { G.roadDrop(ch); } catch (err) {}
      if (typeof GRIM_EDIT_RENDER !== 'undefined') { try { GRIM_EDIT_RENDER.drop(G, ch); } catch (err) {} }
      try { G.scene.remove(ch.mesh); ch.mesh.geometry.dispose(); } catch (err) {}
      G._chunks.delete(key);
    }
    G._terrAcc = 99;
    try { G.stepTerrain(0, 200); } catch (err) {}
    paintStatus();
  }

  // ---- ghost ---------------------------------------------------------------
  function updateGhost() {
    if (!G) return;
    const want = (S.tool === 'place' && GRIM_EDIT_CATALOG[S.kind]);
    if (!want) { if (S.ghost) { G.scene.remove(S.ghost); S.ghost = null; S.ghostKind = null; } return; }
    if (S.ghostKind !== S.kind) {
      if (S.ghost) G.scene.remove(S.ghost);
      const g = GRIM_EDIT_RENDER.build(G, { i: 'ghost', k: S.kind, x: 0, z: 0, y: 0, r: 0, s: 1 });
      if (!g) return;
      g.traverse(o => {
        if (o.material) {
          o.material = o.material.clone();
          o.material.transparent = true; o.material.opacity = 0.45;
          o.material.depthWrite = false;
        }
        o.castShadow = false; o.receiveShadow = false;
      });
      g.matrixAutoUpdate = true;
      S.ghost = g; S.ghostKind = S.kind;
      G.scene.add(g);
    }
    if (S.ghost && S.hoverPt) {
      S.ghost.visible = true;
      S.ghost.position.set(snap(S.hoverPt.x), GRIM_WORLD.height(S.hoverPt.x, S.hoverPt.z), snap(S.hoverPt.z));
      S.ghost.rotation.y = S.rot;
      S.ghost.scale.set(S.scale, S.scale, S.scale);
    } else if (S.ghost) S.ghost.visible = false;
  }

  // ---- entry ---------------------------------------------------------------
  function wanted() {
    if (!CFG.UI) return false;
    try {
      return /(^|[?&])edit=1(&|$)/.test(location.search) || /(^|#|&)edit=1(&|$)/.test(location.hash);
    } catch (e) { return false; }
  }

  async function enter(game) {
    G = game;
    S = fresh();
    S.sculpt = 'raise';
    // The editor's own login, per the plan: nothing about it ships to players
    // and it is not the game account.
    let key = '';
    try { key = localStorage.getItem('grim-edit-key') || ''; } catch (e) {}
    let ok = key ? await probeKey(key) : 'bad';
    while (ok !== 'ok') {
      if (ok === 'no-key-configured') {
        alert('The relay has no EDIT_KEY secret set, so the editor is read only.\n\n' +
              'Set it once with:  npx wrangler secret put EDIT_KEY\n\n' +
              'You can still edit and use Export file, then import the layer later.');
        break;
      }
      if (ok === 'offline') {
        if (!confirm('Cannot reach the relay. Work offline?\n\nEditing works, saving to the world does not, ' +
                     'but Export file will still give you the layer.')) return;
        break;
      }
      const entered = prompt('Editor key');
      if (entered === null) return;
      key = entered;
      ok = await probeKey(key);
      if (ok === 'ok') { try { localStorage.setItem('grim-edit-key', key); } catch (e) {} }
      else if (ok === 'bad') alert('That key was refused.');
    }
    S.key = key;
    S.authed = ok === 'ok';

    // Take the game out of play: no combat, no monsters, no networking.
    G.editorOn = true;
    S.on = true;
    try { if (G.sock) G.sock.close(); } catch (e) {}
    G.worldOn = true;
    G.started = true;
    G.mode = 'ai';
    // Park the player under the camera so the terrain streamer has something
    // to follow, then hide it: an editor should not have a body in the shot.
    if (G.me) {
      G.me.pos.set(S.cam.x, 0, S.cam.z);
      if (G.me.g) G.me.g.visible = false;
      G.me.hp = G.me.max || 100;
    }
    if (G.foe && G.foe.g) G.foe.g.visible = false;
    // Editor light: the world is a dusk scene and authored geometry cannot be
    // judged as a silhouette. Editor only, never in the bundle's game path.
    try {
      const fill = new G.T.HemisphereLight(0xdfe6ee, 0x4a4436, 0.85);
      fill.name = '__editFill';
      G.scene.add(fill);
    } catch (e) {}
    // Hide the game's own interface: HUD, bars, prompts, the login box.
    try {
      const hide = ['#grim-hud', '#grim-nameplate', '.grim-hud'];
      for (const sel of hide) document.querySelectorAll(sel).forEach(n => n.style.display = 'none');
      if (G._loginBox) G._loginBox.style.display = 'none';
      if (G._playBtn) G._playBtn.style.display = 'none';
      if (G._logoutBtn) G._logoutBtn.style.display = 'none';
    } catch (e) {}
    const ov = document.getElementById('grim-overlay');
    if (ov) ov.style.display = 'none';

    build();
    bind();
    applyCam();
    rebuildWorld();
    drawOverlay();
    say(S.authed ? 'editor ready' : 'editor ready, read only');
  }

  // The editor's own frame. Called from the top of the game tick, which is
  // the ONLY hook the editor needs in the game loop.
  function tick(dt) {
    if (!S || !S.on || !G) return;
    if (dt > 0.05) dt = 0.05;
    camTick(dt);
    applyCam();
    if (S.mouse) {
      const [nx, ny] = ndc(S.mouse);
      S.hoverPt = rayGround(nx, ny);
    }
    updateGhost();
    try { G.stepTerrain(dt, 40); } catch (e) {}
    try { G.stepFx && G.stepFx(dt); } catch (e) {}
    if (S._statAcc === undefined) S._statAcc = 0;
    S._statAcc += dt;
    if (S._statAcc > 0.2) { S._statAcc = 0; paintStatus(); }
    if (!document.hidden) G.renderer.render(G.scene, G.cam);
  }

  return {
    wanted, enter, tick, rayGround, surfAt,
    get state() { return S; },
    // Tool entry points, exported so the harness exercises the real
    // ones. Everything here is inert until enter() has run.
    applyTool, paintAt, sculptAt, placeAt, paste, eyedropAt, eyedrop,
    addSpawn, removeSpawn, districtCommit, roadClick, roadCommit,
    prefabSave, prefabStamp, pickObject, deleteSel, deleteProcedural,
    undo, redo, save, exportFile, importFile, rebuildWorld, drawOverlay
  };
})();
