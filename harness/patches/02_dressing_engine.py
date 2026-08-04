#!/usr/bin/env python3
"""Phase 1, part 2: the deterministic per-chunk dressing engine.

chunkProps(cx, cz) is a pure function: same chunk, same WORLD_GEN, same list of
props on every machine forever. The scene layer turns that list into one merged
clutter mesh per chunk plus a handful of real harvestable nodes, and disposes
all of it when the chunk unloads, exactly as the terrain does.

Every replacement asserts a unique anchor and the file is written ONCE at the
end, so a stale anchor aborts without leaving a half-patched file.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ------------------------------------------------------- 1. road registration
# Both roads are local arrays inside their builders. The dressing engine needs
# them as world data, so each one registers its centreline as it is built.
sub(
    "    const road = [[34, 32], [20, 46], [2, 58], [-22, 70], [-46, 80], [-66, 88], [TX, TZ], [-92, 110], [-96, 122]];",
    "    const road = [[34, 32], [20, 46], [2, 58], [-22, 70], [-46, 80], [-66, 88], [TX, TZ], [-92, 110], [-96, 122]];\n"
    "    this.registerRoad(road);",
    'north road register')

sub(
    "    const road = [[37, 27], [44, 11], [50, -7], [56, -28], [61, -48], [67, -69], [92, -79]];",
    "    const road = [[37, 27], [44, 11], [50, -7], [56, -28], [61, -48], [67, -69], [92, -79]];\n"
    "    this.registerRoad(road);",
    'main road register')

# ---------------------------------------------------- 2. the engine itself
ENGINE = r"""
  // ---- zone dressing -----------------------------------------------------
  // The world is dressed per chunk from a seeded hash of (chunkX, chunkZ,
  // WORLD_GEN). There is no Math.random anywhere below on purpose: harvest
  // state syncs by node id, and a node id only means the same thing on two
  // machines if both machines generated the same list from the same inputs.
  //
  // Clutter is decorative, merged into ONE mesh per chunk, shadow-free and
  // matrix-frozen. Harvestable nodes are real objects because they animate and
  // change state, so they stay separate and are deliberately rarer and closer.

  registerRoad(pts) {
    this.roadSegs = this.roadSegs || [];
    for (let i = 0; i < pts.length - 1; i++) {
      this.roadSegs.push([pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]]);
    }
  }

  // Visual identity per zone. Content (what grows, what can be mined) lives in
  // shared-rules; this is only how it looks.
  ZONE_LOOK() {
    return this._zoneLook || (this._zoneLook = {
      HEARTLANDS: { tuft: 0x7f8f4a, bush: 0x4e7a38, stone: 0x8a8a80, stick: 0x6e5636, trunk: 0x6e4f2e, leaf: 0x4e7a38, leaf2: 0x3f6a30, mix: [4, 3, 5, 3] },
      GREENWOOD:  { tuft: 0x5c7a38, bush: 0x2f5a2a, stone: 0x77786c, stick: 0x5a4830, trunk: 0x4a3a24, leaf: 0x2f5a2a, leaf2: 0x3d6b30, mix: [5, 5, 3, 5] },
      FROSTWILD:  { tuft: 0xa8b6ae, bush: 0x5d7a68, stone: 0xa9b0b4, stick: 0x6b6256, trunk: 0x4a3524, leaf: 0x9fc2c8, leaf2: 0x7fa8b2, mix: [4, 2, 6, 4] },
      IRONSPIRE:  { tuft: 0x6f7360, bush: 0x4c5544, stone: 0x8b8b84, stick: 0x5a5346, trunk: 0x4a3524, leaf: 0x24452c, leaf2: 0x2e5636, mix: [2, 1, 9, 2] },
      SUNCOAST:   { tuft: 0xbcae74, bush: 0x6f8a4e, stone: 0xb4a888, stick: 0x9a8560, trunk: 0x8a6a40, leaf: 0x6f9a4a, leaf2: 0x5c8a3e, mix: [5, 2, 5, 2] },
      WINDSCAR:   { tuft: 0xb09a52, bush: 0x7c7a42, stone: 0x9a9078, stick: 0x8a7a4e, trunk: 0x6a5734, leaf: 0x7c8a46, leaf2: 0x68763c, mix: [8, 3, 3, 2] },
      EMBER:      { tuft: 0x6a5a4e, bush: 0x4a3a34, stone: 0x54504c, stick: 0x39322c, trunk: 0x2e2622, leaf: 0x53342a, leaf2: 0x6a3a26, mix: [3, 4, 7, 2] },
      MISTFEN:    { tuft: 0x5f7a4e, bush: 0x3c5a3e, stone: 0x6d7268, stick: 0x4c4436, trunk: 0x4a4030, leaf: 0x466a44, leaf2: 0x3a5c3a, mix: [6, 4, 2, 5] },
      SUNSCORCH:  { tuft: 0xc6b184, bush: 0x8a8a52, stone: 0xc0b494, stick: 0xa89a72, trunk: 0x8a7450, leaf: 0x8a9a52, leaf2: 0x76873f, mix: [5, 3, 6, 1] },
      EASTRIDGE:  { tuft: 0x76786a, bush: 0x53604c, stone: 0x92928a, stick: 0x5f584a, trunk: 0x4a3524, leaf: 0x2c4c32, leaf2: 0x37593c, mix: [3, 2, 8, 2] },
      ISLES:      { tuft: 0x8fa25e, bush: 0x4f7a44, stone: 0xa89e86, stick: 0x8a7a5a, trunk: 0x7a5f3c, leaf: 0x5f9a4e, leaf2: 0x4e8a42, mix: [5, 3, 4, 3] }
    });
  }

  // ---- geometry merging ---------------------------------------------------
  // three's BufferGeometryUtils lives in the examples bundle, which this game
  // does not load, so merging is done here. Inputs must be non-indexed; every
  // template below is prepared that way once.
  mergeGeos(parts) {
    const T = this.T;
    let n = 0;
    for (const p of parts) n += p.geo.getAttribute('position').count;
    const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3), col = new Float32Array(n * 3);
    const v = new T.Vector3(), nm = new T.Matrix3();
    let o = 0;
    for (const p of parts) {
      const pa = p.geo.getAttribute('position'), na = p.geo.getAttribute('normal'), ca = p.geo.getAttribute('color');
      nm.getNormalMatrix(p.m);
      const c = p.color || null;
      for (let i = 0; i < pa.count; i++) {
        v.fromBufferAttribute(pa, i).applyMatrix4(p.m);
        pos[o * 3] = v.x; pos[o * 3 + 1] = v.y; pos[o * 3 + 2] = v.z;
        if (na) { v.fromBufferAttribute(na, i).applyMatrix3(nm).normalize(); nor[o * 3] = v.x; nor[o * 3 + 1] = v.y; nor[o * 3 + 2] = v.z; }
        if (c) { col[o * 3] = c.r; col[o * 3 + 1] = c.g; col[o * 3 + 2] = c.b; }
        else if (ca) { col[o * 3] = ca.getX(i); col[o * 3 + 1] = ca.getY(i); col[o * 3 + 2] = ca.getZ(i); }
        else { col[o * 3] = 1; col[o * 3 + 1] = 1; col[o * 3 + 2] = 1; }
        o++;
      }
    }
    const g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(pos, 3));
    g.setAttribute('normal', new T.BufferAttribute(nor, 3));
    g.setAttribute('color', new T.BufferAttribute(col, 3));
    if (!parts.length || !parts[0].geo.getAttribute('normal')) g.computeVertexNormals();
    return g;
  }

  dressInit() {
    if (this._dressReady) return;
    const T = this.T;
    // One material for every scrap of clutter in the world, so a dressed chunk
    // costs exactly one draw call no matter how much is on it.
    this._clutterMat = new T.MeshStandardMaterial({ vertexColors: true, roughness: 1, flatShading: true });
    this._nodeMat = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.95, flatShading: true });
    const nonIdx = (g) => (g.index ? g.toNonIndexed() : g);
    this._clutterGeo = {
      pebble: nonIdx(new T.DodecahedronGeometry(0.22, 0)),
      stick:  nonIdx(new T.BoxGeometry(0.06, 0.06, 0.8)),
      tuft:   nonIdx(new T.ConeGeometry(0.2, 0.55, 4)),
      bush:   nonIdx(new T.IcosahedronGeometry(0.55, 0))
    };
    this._dressReady = true;
  }

  // ---- placement rules ----------------------------------------------------
  // Water, roads and town ground are all hard rejections rather than nudges: a
  // nudged prop would move if the rule ever changed, and a moved prop is a
  // desynced prop.
  dressBlocked(x, z) {
    if (!GRIM_WORLD.ready) return true;
    const h = GRIM_WORLD.height(x, z);
    if (h < 0.35) return true;                       // the water wall
    if (!GRIM_WORLD.walkable(x, z)) return true;
    const TC = GRIM_RULES.GATHER.TOWN_CLEAR;
    for (const s of GRIM_RULES.SAFE) {
      const r = s.r + TC;
      if ((x - s.x) * (x - s.x) + (z - s.z) * (z - s.z) < r * r) return true;
    }
    for (const a of (GRIM_WORLD.anchors || [])) {
      if (a.kind !== 'town' && a.kind !== 'capital' && a.kind !== 'port') continue;
      if ((x - a.x) * (x - a.x) + (z - a.z) * (z - a.z) < TC * TC) return true;
    }
    const RC = GRIM_RULES.GATHER.ROAD_CLEAR, RC2 = RC * RC;
    for (const s of (this.roadSegs || [])) {
      const dx = s[2] - s[0], dz = s[3] - s[1];
      const len2 = dx * dx + dz * dz;
      let t = len2 ? ((x - s[0]) * dx + (z - s[1]) * dz) / len2 : 0;
      t = t < 0 ? 0 : t > 1 ? 1 : t;
      const px = s[0] + dx * t - x, pz = s[1] + dz * t - z;
      if (px * px + pz * pz < RC2) return true;
    }
    // steep ground: props standing on a cliff face read as floating
    const e = 1.5;
    const gx = (GRIM_WORLD.height(x + e, z) - GRIM_WORLD.height(x - e, z)) / (2 * e);
    const gz = (GRIM_WORLD.height(x, z + e) - GRIM_WORLD.height(x, z - e)) / (2 * e);
    return (gx * gx + gz * gz) > 1.2;
  }

  // Which harvestable node kinds can roll in this zone, with weights. Common
  // low tiers are common; the level-90 rares are rare and only in deep ground.
  zoneNodeTable(zone, deep) {
    const key = zone + (deep ? ':deep' : '');
    this._zoneTbl = this._zoneTbl || {};
    if (this._zoneTbl[key]) return this._zoneTbl[key];
    const out = [];
    const N = GRIM_RULES.GATHER.NODES;
    for (const k in N) {
      const nd = N[k];
      if (nd.legacy || !nd.zones || nd.zones.indexOf(zone) < 0) continue;
      if (nd.deep && !deep) continue;
      if (nd.water) continue;                        // pearls and coral are a dive, not ground dressing
      out.push({ kind: k, w: nd.rare ? 0.4 : (24 / (12 + nd.lvl)) });
    }
    let tot = 0; for (const o of out) tot += o.w;
    this._zoneTbl[key] = { list: out, total: tot };
    return this._zoneTbl[key];
  }

  // ---- THE PURE GENERATOR -------------------------------------------------
  // Given a chunk, return exactly what stands on it. No scene, no player, no
  // clock, no randomness that is not seeded off the chunk itself. This is the
  // function the determinism test asserts on.
  chunkProps(cx, cz) {
    const CH = 64, x0 = cx * CH, z0 = cz * CH;
    const G = GRIM_RULES.GATHER;
    const rnd = grimRnd(grimSeed(cx, cz, 'dress'));
    const clutter = [], nodes = [];
    const cN = G.CLUTTER_PER_CHUNK[0] + Math.floor(rnd() * (G.CLUTTER_PER_CHUNK[1] - G.CLUTTER_PER_CHUNK[0] + 1));
    const nN = G.NODES_PER_CHUNK[0] + Math.floor(rnd() * (G.NODES_PER_CHUNK[1] - G.NODES_PER_CHUNK[0] + 1));
    const TYPES = ['tuft', 'bush', 'pebble', 'stick'];

    for (let i = 0; i < cN; i++) {
      const x = x0 + rnd() * CH, z = z0 + rnd() * CH;
      const rot = rnd() * Math.PI * 2, sc = 0.7 + rnd() * 0.8, pick = rnd();
      if (this.dressBlocked(x, z)) continue;
      const bake = GRIM_WORLD.zone(x, z);
      const zone = grimZoneName(bake);
      if (zone === 'SEA') continue;
      const look = this.ZONE_LOOK()[zone] || this.ZONE_LOOK().HEARTLANDS;
      const mix = look.mix, mt = mix[0] + mix[1] + mix[2] + mix[3];
      let acc = pick * mt, ti = 0;
      for (; ti < 3; ti++) { if (acc < mix[ti]) break; acc -= mix[ti]; }
      clutter.push({ type: TYPES[ti], zone: zone, x: x, z: z, y: GRIM_WORLD.height(x, z), rot: rot, sc: sc });
    }

    for (let i = 0; i < nN; i++) {
      const x = x0 + 4 + rnd() * (CH - 8), z = z0 + 4 + rnd() * (CH - 8);
      const rot = rnd() * Math.PI * 2, roll = rnd(), sc = 0.9 + rnd() * 0.35;
      if (this.dressBlocked(x, z)) continue;
      const bake = GRIM_WORLD.zone(x, z);
      const zone = grimZoneName(bake);
      if (zone === 'SEA') continue;
      const tbl = this.zoneNodeTable(zone, grimZoneIsDeep(bake));
      if (!tbl.total) continue;
      let acc = roll * tbl.total, kind = tbl.list[0].kind;
      for (const o of tbl.list) { if (acc < o.w) { kind = o.kind; break; } acc -= o.w; }
      // keep nodes off each other so two trees never grow through each other
      let clash = false;
      for (const p of nodes) { const dx = p.x - x, dz = p.z - z; if (dx * dx + dz * dz < 64) { clash = true; break; } }
      if (clash) continue;
      nodes.push({ kind: kind, zone: zone, x: x, z: z, y: GRIM_WORLD.height(x, z), rot: rot, sc: sc,
                   nid: grimNodeId(cx, cz, i) });
    }
    return { clutter: clutter, nodes: nodes };
  }

  // ---- node models --------------------------------------------------------
  // Built with the shipped model kit (loftMesh, jitterGeo) and then merged, so
  // a standing tree is one draw call instead of five. The stump stays its own
  // mesh because it is revealed at the exact moment the tree breaks off it.
  makeZoneTree(look, sc, seed) {
    const T = this.T;
    const rnd = grimRnd(seed);
    const S = 1.25 * sc;
    const lean = (rnd() - 0.5) * 0.14;
    const trunkMesh = this.loftMesh([
      { z: 0, w: 0.42 * S, h: 0.42 * S, y: 0 },
      { z: 0.5 * S, w: 0.26 * S, h: 0.26 * S, y: lean * 0.6 },
      { z: 2.0 * S, w: 0.2 * S, h: 0.2 * S, y: lean * 1.6 },
      { z: 3.0 * S, w: 0.14 * S, h: 0.14 * S, y: lean * 2.4 }
    ], 7, look.trunk, look.stick, this._nodeMat);
    const parts = [];
    const mRot = new T.Matrix4().makeRotationX(-Math.PI / 2);
    parts.push({ geo: trunkMesh.geometry, m: mRot });
    const cL = new T.Color(look.leaf), cL2 = new T.Color(look.leaf2);
    for (let i = 0; i < 3; i++) {
      const geo = this.jitterGeo(new T.IcosahedronGeometry(1.35 * S * (1 - i * 0.16) + rnd() * 0.3, 0), 0.22, rnd() * 97, 0.85);
      const a = rnd() * Math.PI * 2;
      const m = new T.Matrix4().makeTranslation(
        Math.sin(a) * (i ? 0.9 : 0) * S + lean * 2.2, (3.1 + i * 0.85) * S, Math.cos(a) * (i ? 0.9 : 0) * S);
      parts.push({ geo: geo.index ? geo.toNonIndexed() : geo, m: m, color: i % 2 ? cL2 : cL });
    }
    const g = new T.Group();
    const fell = new T.Group(); g.add(fell);
    const body = new T.Mesh(this.mergeGeos(parts), this._nodeMat);
    body.castShadow = true; fell.add(body);
    const stumpMesh = this.loftMesh([
      { z: 0, w: 0.42 * S, h: 0.42 * S, y: 0 },
      { z: 0.3 * S, w: 0.32 * S, h: 0.32 * S, y: lean * 0.36 }
    ], 7, look.trunk, 0xb08a5c, this._nodeMat);
    const stumpG = new T.Group(); stumpG.visible = false; g.add(stumpG);
    stumpMesh.rotation.x = -Math.PI / 2; stumpG.add(stumpMesh);
    return { g: g, fell: fell, stump: stumpG };
  }

  makeZoneOre(look, sc, seed, tint) {
    const T = this.T;
    const rnd = grimRnd(seed);
    const g = new T.Group();
    const rockParts = [];
    const cR = new T.Color(look.stone);
    for (let i = 0; i < 3; i++) {
      const geo = this.jitterGeo(new T.DodecahedronGeometry((0.75 - i * 0.16) * sc, 0), 0.3, rnd() * 61, 0.8);
      const m = new T.Matrix4().makeTranslation((rnd() - 0.5) * 0.7 * sc, 0.32 * sc + i * 0.16 * sc, (rnd() - 0.5) * 0.7 * sc);
      rockParts.push({ geo: geo.index ? geo.toNonIndexed() : geo, m: m, color: cR });
    }
    const boulder = new T.Mesh(this.mergeGeos(rockParts), this._nodeMat);
    boulder.castShadow = true; g.add(boulder);
    // the ore itself: one merged mesh that vanishes when the vein is emptied
    const oreParts = [];
    const cO = new T.Color(tint);
    for (let i = 0; i < 4; i++) {
      const geo = new T.DodecahedronGeometry(0.13 * sc, 0);
      const a = rnd() * Math.PI * 2, r = 0.45 * sc;
      const m = new T.Matrix4().makeTranslation(Math.sin(a) * r, 0.42 * sc + rnd() * 0.5 * sc, Math.cos(a) * r);
      oreParts.push({ geo: geo.index ? geo.toNonIndexed() : geo, m: m, color: cO });
    }
    const studs = new T.Mesh(this.mergeGeos(oreParts), this._nodeMat);
    g.add(studs);
    return { g: g, studs: [studs] };
  }

  makeZonePlant(look, sc, seed, tint) {
    const T = this.T;
    const rnd = grimRnd(seed);
    const g = new T.Group();
    const fell = new T.Group(); g.add(fell);
    const parts = [];
    const c = new T.Color(tint);
    for (let i = 0; i < 4; i++) {
      const geo = this.jitterGeo(new T.IcosahedronGeometry(0.34 * sc, 0), 0.3, rnd() * 53, 0.9);
      const a = rnd() * Math.PI * 2, r = rnd() * 0.4 * sc;
      const m = new T.Matrix4().makeTranslation(Math.sin(a) * r, 0.3 * sc + rnd() * 0.3 * sc, Math.cos(a) * r);
      parts.push({ geo: geo.index ? geo.toNonIndexed() : geo, m: m, color: i ? c : new T.Color(look.bush) });
    }
    const body = new T.Mesh(this.mergeGeos(parts), this._nodeMat);
    fell.add(body);
    // picked state: the stalks stay, the harvest does not
    const stubG = new T.Group(); stubG.visible = false; g.add(stubG);
    const stub = new T.Mesh(this.mergeGeos([{ geo: this._clutterGeo.tuft, m: new T.Matrix4().makeScale(sc, sc * 0.6, sc), color: new T.Color(look.tuft) }]), this._nodeMat);
    stub.position.y = 0.16 * sc; stubG.add(stub);
    return { g: g, fell: fell, stump: stubG };
  }

  // ---- scene layer --------------------------------------------------------
  dressChunk(rec) {
    if (!GRIM_WORLD.ready) return;
    this.dressInit();
    const T = this.T;
    const props = this.chunkProps(rec.cx, rec.cz);
    // clutter: one merged mesh, no shadows, frozen matrix
    if (props.clutter.length) {
      const parts = [];
      const LOOKS = this.ZONE_LOOK();
      for (const p of props.clutter) {
        const look = LOOKS[p.zone] || LOOKS.HEARTLANDS;
        const m = new T.Matrix4().compose(
          new T.Vector3(p.x, p.y + (p.type === 'pebble' ? 0.08 : p.type === 'stick' ? 0.04 : 0.2) * p.sc, p.z),
          new T.Quaternion().setFromEuler(new T.Euler(p.type === 'stick' ? Math.PI / 2 : 0, p.rot, 0)),
          new T.Vector3(p.sc, p.sc, p.sc));
        parts.push({ geo: this._clutterGeo[p.type], m: m, color: new T.Color(look[p.type] || look.tuft) });
      }
      const mesh = new T.Mesh(this.mergeGeos(parts), this._clutterMat);
      mesh.castShadow = false; mesh.receiveShadow = false;
      mesh.matrixAutoUpdate = false; mesh.updateMatrix();
      this.scene.add(mesh);
      rec.clutter = mesh;
    }
    // nodes: real objects, registered through the shared resource system
    this.zoneNodes = this.zoneNodes || [];
    rec.nodes = [];
    const LOOKS = this.ZONE_LOOK();
    for (const p of props.nodes) {
      const nd = GRIM_RULES.GATHER.NODES[p.kind];
      if (!nd) continue;
      const look = LOOKS[p.zone] || LOOKS.HEARTLANDS;
      const seed = grimSeed(Math.round(p.x * 4), Math.round(p.z * 4), p.kind);
      let built;
      if (nd.skill === 'WOODCUTTING') built = this.makeZoneTree(look, p.sc, seed);
      else if (nd.skill === 'MINING') built = this.makeZoneOre(look, p.sc, seed, this.NODE_TINT(p.kind));
      else built = this.makeZonePlant(look, p.sc, seed, this.NODE_TINT(p.kind));
      built.g.position.set(p.x, p.y, p.z);
      built.g.rotation.y = p.rot;
      this.scene.add(built.g);
      const R = {
        kind: p.kind, nid: p.nid, g: built.g, fell: built.fell || null, stump: built.stump || null,
        studs: built.studs || null, hp: nd.hp, max: nd.hp, dead: false, respawn: 0, streamed: true
      };
      // a node emptied a moment ago must come back empty when you walk away
      // and back, not full: the chunk unloads, the state does not
      const kept = this._nodeState && this._nodeState[p.nid];
      if (kept && kept.dead) { R.hp = 0; R.dead = true; R.respawn = kept.respawn; }
      this.zoneNodes.push(R);
      rec.nodes.push(R);
      if (R.dead) this.resourceDepleted(R, null);
      if (this._frozeStatic) { built.g.updateMatrix(); built.g.matrixAutoUpdate = false; }
    }
  }

  NODE_TINT(kind) {
    const TINT = {
      copper: 0xc06a34, ironore: 0x9a6a4a, coal: 0x2a2a2c, gold: 0xd8b23c, obsidian: 0x2b2436,
      embercryst: 0xff7a3c, salt: 0xe6e2d8, saltpeter: 0xd8d2b4, glasssand: 0xd6cf9e, stone: 0x8b8b84,
      berry: 0xb03a4a, mushroom: 0xc08a5a, reeds: 0x8a9a4a, holly: 0xc03a3a, fenroot: 0x6a5a8a,
      dyeflower: 0xc04a9a, spice: 0xc07a2a, firelily: 0xff6a2a, lotus: 0x2a1a3a
    };
    return TINT[kind] || 0x8a8a80;
  }

  dressDrop(rec) {
    if (rec.clutter) {
      this.scene.remove(rec.clutter);
      rec.clutter.geometry.dispose();
      rec.clutter = null;
    }
    if (rec.nodes) {
      this._nodeState = this._nodeState || {};
      for (const R of rec.nodes) {
        // remember what was harvested so the world does not refill behind you
        if (R.dead) this._nodeState[R.nid] = { dead: true, respawn: R.respawn };
        else delete this._nodeState[R.nid];
        this.scene.remove(R.g);
        R.g.traverse(o => { if (o.isMesh && o.geometry) o.geometry.dispose(); });
        const i = this.zoneNodes.indexOf(R);
        if (i >= 0) this.zoneNodes.splice(i, 1);
      }
      rec.nodes = null;
    }
  }
"""

sub(
    "  // ---- rowboat -----------------------------------------------------------",
    ENGINE + "\n  // ---- rowboat -----------------------------------------------------------",
    'engine insert')

# ---------------------------------------------------------- 3. streaming hooks
sub(
    "          this._chunks.set(key, { mesh: nmch, seg: wantSeg, cx: cx, cz: cz });\n"
    "          budget--;",
    "          const rec = { mesh: nmch, seg: wantSeg, cx: cx, cz: cz };\n"
    "          this._chunks.set(key, rec);\n"
    "          // Only the detail rings are dressed. Clutter beyond that is\n"
    "          // invisible at distance and would cost draw calls for nothing.\n"
    "          if (ring <= DRESS && this.worldOn) this.dressChunk(rec);\n"
    "          budget--;",
    'dress on load')

sub(
    "          if (have) { this.scene.remove(have.mesh); have.mesh.geometry.dispose(); this._chunks.delete(key); }",
    "          if (have) { this.dressDrop(have); this.scene.remove(have.mesh); have.mesh.geometry.dispose(); this._chunks.delete(key); }",
    'dress drop on reseg')

sub(
    "        this.scene.remove(ch.mesh); ch.mesh.geometry.dispose(); this._chunks.delete(key);",
    "        this.dressDrop(ch); this.scene.remove(ch.mesh); ch.mesh.geometry.dispose(); this._chunks.delete(key);",
    'dress drop on unload')

sub(
    "    const DETAIL = 3, COARSE = 7;",
    "    const DETAIL = 3, COARSE = 7, DRESS = 2;",
    'dress ring')

# ------------------------------------------- 4. streamed nodes join the systems
sub(
    "    if (!this.connectedAsClient()) for (const R of this.resources) {\n"
    "      if (R.dead) { R.respawn -= dt; if (R.respawn <= 0) { this.resourceRespawned(R); this._rDirty = true; } }\n"
    "    }",
    "    if (!this.connectedAsClient()) for (const R of this.allResources()) {\n"
    "      if (R.dead) { R.respawn -= dt; if (R.respawn <= 0) { this.resourceRespawned(R); this._rDirty = true; } }\n"
    "    }",
    'respawn tick')

sub(
    "    let best = null, bd = 3.0, bestDead = null, bdD = 3.0;\n"
    "    for (const R of this.resources) {",
    "    let best = null, bd = 3.0, bestDead = null, bdD = 3.0;\n"
    "    for (const R of this.allResources()) {",
    'gather scan')

sub(
    "  // Tier-based refill clocks: bigger and richer takes longer to come back.",
    "  // The world's harvestables in one list: the fixed set built at world load\n"
    "  // plus whatever the dressing engine has streamed in around the player.\n"
    "  // Everything that walks resources walks this, so a streamed node is never\n"
    "  // a second class of node with its own half-implemented rules.\n"
    "  allResources() {\n"
    "    if (!this.zoneNodes || !this.zoneNodes.length) return this.resources;\n"
    "    return this.resources.concat(this.zoneNodes);\n"
    "  }\n"
    "\n"
    "  // Tier-based refill clocks: bigger and richer takes longer to come back.",
    'allResources')

# ----------------------------------- 5. depletion understands all three skills
sub(
    "  resourceDepleted(R, p) {\n"
    "    R.dead = true; R.respawn = this.resourceRespawnTime(R.kind);\n"
    "    this._rDirty = true;\n"
    "    if (R.kind === 'rock') {\n"
    "      if (R.studs) R.studs.forEach(s2 => { s2.visible = false; });\n"
    "      if (p) this.spark(p, 0xd88a4a, 16);\n"
    "      this.sfx('break');\n"
    "    } else {",

    "  resourceDepleted(R, p) {\n"
    "    R.dead = true; R.respawn = this.resourceRespawnTime(R.kind);\n"
    "    this._rDirty = true;\n"
    "    const nd = GRIM_RULES.GATHER.NODES[R.kind];\n"
    "    const skill = nd ? nd.skill : (R.kind === 'rock' ? 'MINING' : 'WOODCUTTING');\n"
    "    if (skill === 'MINING') {\n"
    "      if (R.studs) R.studs.forEach(s2 => { s2.visible = false; });\n"
    "      if (p) this.spark(p, 0xd88a4a, 16);\n"
    "      this.sfx('break');\n"
    "    } else if (skill === 'FORAGING') {\n"
    "      // A picked plant does not topple. The harvest disappears and the\n"
    "      // stalks stay, so the spot still reads as somewhere worth returning to.\n"
    "      if (R.fell) R.fell.visible = false;\n"
    "      if (R.stump) R.stump.visible = true;\n"
    "      if (p) this.spark(p, 0x4fb3a0, 12);\n"
    "      this.sfx('pickup');\n"
    "    } else {",
    'resourceDepleted skills')

# ---------------------------------------------------------------------- write
out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)

assert out != src, 'nothing changed'
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
