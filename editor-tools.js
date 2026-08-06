// ===========================================================================
// GRIM WORLD - EDITOR OBJECT CATALOG AND TOOLS
//
// Two things live here:
//
//   GRIM_EDIT_CATALOG - what can be placed, and how each one is built. This
//     part SHIPS TO PLAYERS, because a player has to see the objects Kevin
//     placed. Every entry is a pure builder: same inputs, same mesh.
//
//   GRIM_EDIT_TOOLS - brush, road, place, select, sculpt, prefab and the undo
//     stack. This part only ever runs behind ?edit=1.
//
// Injected into the game bundle by repack.py between the EDITOR markers.
//
// The renderer contract, which matters for frame rate: an authored object is
// built once per chunk load and parked with matrixAutoUpdate off, exactly the
// way the dressing pass treats procedural props. Anything that needs to
// animate has to opt in, and nothing here does.
// ===========================================================================

// ---- shared materials ------------------------------------------------------
// One material per look, created once and reused, so a hundred wall sections
// cost one bind. Flat colour on purpose: it matches the low-poly world and
// the ground atlas does the texture work.
const GRIM_EDIT_MATS = (() => {
  let M = null;
  return (T) => {
    if (M) return M;
    const mk = (c, r, m) => new T.MeshStandardMaterial({
      color: c, roughness: r === undefined ? 0.86 : r, metalness: m || 0, flatShading: true
    });
    M = {
      wood: mk(0x6b5236), woodDark: mk(0x4a3826), plank: mk(0x7d6242),
      stone: mk(0x777067), stoneDark: mk(0x5a554e), slate: mk(0x4b4f52),
      thatch: mk(0x9a8248, 0.95), tile: mk(0x5c4a44),
      iron: mk(0x3f4348, 0.55, 0.55), cloth: mk(0x8d7a5c),
      // Planes need both faces or you see straight through a wall from
      // inside, which is exactly the fault the burial mound has today.
      sheet: new T.MeshStandardMaterial({ color: 0x6b5236, roughness: 0.9, flatShading: true, side: T.DoubleSide })
    };
    return M;
  };
})();

const GRIM_EDIT_CATALOG = (() => {
  // box(): a positioned, rotated box in the object's local space. Local Y is
  // measured up from the ground the object sits on.
  const box = (T, g, mat, w, h, d, x, y, z, ry) => {
    const m = new T.Mesh(new T.BoxGeometry(w, h, d), mat);
    m.position.set(x, y + h / 2, z);
    if (ry) m.rotation.y = ry;
    m.castShadow = true; m.receiveShadow = true;
    g.add(m);
    return m;
  };

  const grp = (T) => { const g = new T.Group(); return g; };

  // --- building pieces ------------------------------------------------------
  // A 4 metre module. Walls are slabs rather than one solid box, per the
  // interiors plan, so a room built from them has a real inside face and the
  // doorway is a genuine gap rather than a texture.
  const WALL_H = 3.2, WALL_T = 0.32, MOD = 4;

  function wallSolid(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.plank, MOD, WALL_H, WALL_T, 0, 0, 0);
    box(T, g, M.woodDark, MOD, 0.18, WALL_T + 0.06, 0, WALL_H - 0.18, 0);
    return g;
  }
  function wallDoor(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const jamb = (MOD - 1.3) / 2;
    box(T, g, M.plank, jamb, WALL_H, WALL_T, -(MOD - jamb) / 2, 0, 0);
    box(T, g, M.plank, jamb, WALL_H, WALL_T, (MOD - jamb) / 2, 0, 0);
    box(T, g, M.plank, 1.3, WALL_H - 2.2, WALL_T, 0, 2.2, 0);      // header
    box(T, g, M.woodDark, MOD, 0.18, WALL_T + 0.06, 0, WALL_H - 0.18, 0);
    return g;
  }
  function wallWindow(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const side = (MOD - 1.5) / 2;
    box(T, g, M.plank, side, WALL_H, WALL_T, -(MOD - side) / 2, 0, 0);
    box(T, g, M.plank, side, WALL_H, WALL_T, (MOD - side) / 2, 0, 0);
    box(T, g, M.plank, 1.5, 1.1, WALL_T, 0, 0, 0);                 // sill
    box(T, g, M.plank, 1.5, WALL_H - 2.4, WALL_T, 0, 2.4, 0);      // head
    // The existing emissive trick: window glass glows at zero light cost.
    const gl = new T.Mesh(new T.PlaneGeometry(1.42, 1.24),
      new T.MeshBasicMaterial({ color: 0xffd98a, transparent: true, opacity: 0.5 }));
    gl.position.set(0, 1.72, WALL_T / 2 + 0.01);
    g.add(gl);
    return g;
  }
  function floorSlab(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.plank, MOD, 0.24, MOD, 0, 0, 0);
    return g;
  }
  function roofPitch(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const a = box(T, g, M.tile, MOD + 0.4, 0.2, 2.6, 0, 0, -1.15);
    a.rotation.x = -0.62; a.position.y = 1.0;
    const b = box(T, g, M.tile, MOD + 0.4, 0.2, 2.6, 0, 0, 1.15);
    b.rotation.x = 0.62; b.position.y = 1.0;
    box(T, g, M.woodDark, MOD + 0.5, 0.16, 0.22, 0, 1.72, 0);
    return g;
  }
  function stairs(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const N = 8, rise = WALL_H / N, run = MOD / N;
    for (let i = 0; i < N; i++) {
      box(T, g, M.plank, MOD * 0.75, rise, run, 0, i * rise, -MOD / 2 + run * (i + 0.5));
    }
    return g;
  }
  function pillar(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.stone, 0.5, WALL_H, 0.5, 0, 0, 0);
    box(T, g, M.stoneDark, 0.72, 0.2, 0.72, 0, 0, 0);
    box(T, g, M.stoneDark, 0.72, 0.2, 0.72, 0, WALL_H - 0.2, 0);
    return g;
  }
  function fence(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.woodDark, 0.16, 1.15, 0.16, -MOD / 2 + 0.1, 0, 0);
    box(T, g, M.woodDark, 0.16, 1.15, 0.16, MOD / 2 - 0.1, 0, 0);
    box(T, g, M.wood, MOD, 0.12, 0.09, 0, 0.42, 0);
    box(T, g, M.wood, MOD, 0.12, 0.09, 0, 0.82, 0);
    return g;
  }
  // A real walkable deck on legs: the watchtower case from the plan.
  function platform(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const H = 4.0, W = 4.0;
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      box(T, g, M.woodDark, 0.34, H, 0.34, sx * (W / 2 - 0.3), 0, sz * (W / 2 - 0.3));
    }
    box(T, g, M.plank, W, 0.26, W, 0, H, 0);
    for (const sz of [-1, 1]) {
      box(T, g, M.wood, W, 0.12, 0.1, 0, H + 1.0, sz * (W / 2 - 0.06));
      box(T, g, M.wood, 0.1, 0.12, W, sz * (W / 2 - 0.06), H + 1.0, 0);
    }
    return g;
  }
  function watchtower(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const H = 7.5, W = 3.4;
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      const p = box(T, g, M.woodDark, 0.4, H, 0.4, sx * (W / 2 - 0.3), 0, sz * (W / 2 - 0.3));
      p.rotation.z = -sx * 0.02; p.rotation.x = sz * 0.02;
    }
    for (const y of [2.4, 4.8]) {
      box(T, g, M.wood, W, 0.16, 0.16, 0, y, -(W / 2 - 0.3));
      box(T, g, M.wood, W, 0.16, 0.16, 0, y, (W / 2 - 0.3));
    }
    box(T, g, M.plank, W + 0.8, 0.28, W + 0.8, 0, H, 0);
    for (const sz of [-1, 1]) {
      box(T, g, M.wood, W + 0.8, 0.9, 0.14, 0, H + 0.28, sz * (W / 2 + 0.33));
      box(T, g, M.wood, 0.14, 0.9, W + 0.8, sz * (W / 2 + 0.33), H + 0.28, 0);
    }
    const r = box(T, g, M.thatch, W + 1.2, 0.22, W + 1.2, 0, H + 2.5, 0);
    r.rotation.x = 0.0;
    for (const sx of [-1, 1]) box(T, g, M.woodDark, 0.16, 2.2, 0.16, sx * (W / 2), H + 0.3, 0);
    return g;
  }

  // --- props ---------------------------------------------------------------
  function crate(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.wood, 0.9, 0.9, 0.9, 0, 0, 0);
    box(T, g, M.woodDark, 0.96, 0.09, 0.09, 0, 0.42, 0);
    box(T, g, M.woodDark, 0.09, 0.09, 0.96, 0, 0.42, 0);
    return g;
  }
  function barrel(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const b = new T.Mesh(new T.CylinderGeometry(0.42, 0.36, 1.0, 10), M.wood);
    b.position.y = 0.5; b.castShadow = true; g.add(b);
    for (const y of [0.24, 0.76]) {
      const h = new T.Mesh(new T.TorusGeometry(0.41, 0.035, 5, 12), M.iron);
      h.rotation.x = Math.PI / 2; h.position.y = y; g.add(h);
    }
    return g;
  }
  function bench(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.plank, 1.9, 0.12, 0.5, 0, 0.44, 0);
    for (const sx of [-1, 1]) box(T, g, M.woodDark, 0.14, 0.44, 0.44, sx * 0.75, 0, 0);
    return g;
  }
  function hay(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const h = new T.Mesh(new T.CylinderGeometry(0.72, 0.72, 1.2, 9), M.thatch);
    h.rotation.z = Math.PI / 2; h.position.y = 0.72; h.castShadow = true; g.add(h);
    return g;
  }
  function signpost(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.woodDark, 0.14, 2.3, 0.14, 0, 0, 0);
    box(T, g, M.plank, 1.25, 0.32, 0.08, 0.5, 1.72, 0);
    return g;
  }
  function well(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const w = new T.Mesh(new T.CylinderGeometry(1.05, 1.15, 0.9, 12), M.stone);
    w.position.y = 0.45; w.castShadow = true; w.receiveShadow = true; g.add(w);
    const hole = new T.Mesh(new T.CircleGeometry(0.85, 12), new T.MeshBasicMaterial({ color: 0x0b1418 }));
    hole.rotation.x = -Math.PI / 2; hole.position.y = 0.91; g.add(hole);
    for (const sx of [-1, 1]) box(T, g, M.woodDark, 0.14, 1.8, 0.14, sx * 0.95, 0.9, 0);
    box(T, g, M.thatch, 2.5, 0.16, 1.5, 0, 2.7, 0);
    return g;
  }
  function torch(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.woodDark, 0.12, 2.0, 0.12, 0, 0, 0);
    const f = new T.Mesh(new T.ConeGeometry(0.19, 0.5, 7),
      new T.MeshBasicMaterial({ color: 0xffb648 }));
    f.position.y = 2.2; g.add(f);
    return g;
  }
  function packBench(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.plank, 2.2, 0.16, 1.0, 0, 0.85, 0);
    for (const sx of [-1, 1]) box(T, g, M.woodDark, 0.18, 0.85, 0.85, sx * 0.9, 0, 0);
    box(T, g, M.cloth, 0.9, 0.5, 0.7, -0.5, 1.01, 0);
    box(T, g, M.wood, 0.5, 0.4, 0.5, 0.7, 1.01, 0);
    return g;
  }
  function tradePost(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.plank, 3.0, 0.2, 1.2, 0, 1.0, 0);
    for (const sx of [-1, 1]) box(T, g, M.woodDark, 0.18, 1.0, 1.0, sx * 1.3, 0, 0);
    for (const sx of [-1, 1]) box(T, g, M.woodDark, 0.14, 2.6, 0.14, sx * 1.4, 0, -0.5);
    const awn = box(T, g, M.cloth, 3.4, 0.1, 1.9, 0, 2.5, 0.1);
    awn.rotation.x = 0.18;
    return g;
  }
  function mailbox(G) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    box(T, g, M.woodDark, 0.16, 1.15, 0.16, 0, 0, 0);
    box(T, g, M.plank, 0.5, 0.42, 0.34, 0, 1.15, 0);
    box(T, g, M.iron, 0.52, 0.06, 0.36, 0, 1.57, 0);
    return g;
  }

  // --- procedural props, reusing the game's own builders --------------------
  // A tree placed in the editor must be the SAME tree the dressing pass grows,
  // or the authored world stops matching the generated one and every screenshot
  // Kevin takes is a lie. These call straight into the game.
  function zoneLook(G, x, z) {
    const L = G.ZONE_LOOK ? G.ZONE_LOOK() : null;
    if (!L) return null;
    const name = (typeof grimZoneName === 'function' && typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.ready)
      ? grimZoneName(GRIM_WORLD.zone(x, z)) : 'HEARTLANDS';
    return L[name] || L.HEARTLANDS;
  }
  function seedAt(x, z, salt) {
    return (typeof grimSeed === 'function')
      ? grimSeed(Math.round(x * 4), Math.round(z * 4), salt) : 1;
  }
  function treeOf(shape) {
    return (G, o) => {
      const look = zoneLook(G, o.x, o.z);
      if (!look || !G.makeZoneTree) return null;
      const built = G.makeZoneTree(look, 1, seedAt(o.x, o.z, 'edit' + shape), shape);
      return built && built.g;
    };
  }
  function oreOf(kind) {
    return (G, o) => {
      const look = zoneLook(G, o.x, o.z);
      if (!look || !G.makeZoneOre) return null;
      const tint = G.NODE_TINT ? G.NODE_TINT(kind) : 0x8a8f92;
      const built = G.makeZoneOre(look, 1, seedAt(o.x, o.z, 'edit' + kind), tint);
      return built && built.g;
    };
  }
  function plantOf(kind) {
    return (G, o) => {
      const look = zoneLook(G, o.x, o.z);
      if (!look || !G.makeZonePlant) return null;
      const tint = G.NODE_TINT ? G.NODE_TINT(kind) : 0x6f8a4a;
      const built = G.makeZonePlant(look, 1, seedAt(o.x, o.z, 'edit' + kind), tint, kind);
      return built && built.g;
    };
  }
  function rockOf(G, o) {
    const T = G.T, M = GRIM_EDIT_MATS(T), g = grp(T);
    const r = new T.Mesh(new T.DodecahedronGeometry(0.9, 0), M.stone);
    r.position.y = 0.55; r.rotation.set(0.4, o.r || 0, 0.2);
    r.scale.set(1, 0.72, 0.88);
    r.castShadow = true; r.receiveShadow = true; g.add(r);
    return g;
  }

  // clear: metres of procedural clutter suppressed around the object.
  // deck:  {w, d, h} a walkable top at local height h, w by d metres.
  const C = {
    // structures
    platform:   { label: 'Platform',      tab: 'build', clear: 3.6, deck: { w: 4, d: 4, h: 4.0 },  build: platform },
    watchtower: { label: 'Watchtower',    tab: 'build', clear: 4.2, deck: { w: 4.2, d: 4.2, h: 7.5 }, build: watchtower },
    wall:       { label: 'Wall',          tab: 'build', clear: 1.6, build: wallSolid },
    wall_door:  { label: 'Wall, doorway', tab: 'build', clear: 1.6, build: wallDoor },
    wall_win:   { label: 'Wall, window',  tab: 'build', clear: 1.6, build: wallWindow },
    floor:      { label: 'Floor',         tab: 'build', clear: 2.4, deck: { w: 4, d: 4, h: 0.24 }, build: floorSlab },
    roof:       { label: 'Roof',          tab: 'build', clear: 0,   build: roofPitch },
    stairs:     { label: 'Stairs',        tab: 'build', clear: 2.4, build: stairs },
    pillar:     { label: 'Pillar',        tab: 'build', clear: 0.9, build: pillar },
    fence:      { label: 'Fence',         tab: 'build', clear: 1.1, build: fence },
    // props
    crate:      { label: 'Crate',      tab: 'props', clear: 0.8, build: crate },
    barrel:     { label: 'Barrel',     tab: 'props', clear: 0.8, build: barrel },
    bench:      { label: 'Bench',      tab: 'props', clear: 1.2, build: bench },
    hay:        { label: 'Hay bale',   tab: 'props', clear: 1.1, build: hay },
    signpost:   { label: 'Signpost',   tab: 'props', clear: 0.8, build: signpost },
    well:       { label: 'Well',       tab: 'props', clear: 2.0, build: well },
    torch:      { label: 'Torch',      tab: 'props', clear: 0.7, build: torch },
    rock:       { label: 'Boulder',    tab: 'props', clear: 1.4, build: rockOf },
    // economy interactables from the trade plan, placed here so Kevin owns the
    // route map the moment phases 11 and 12 land
    packbench:  { label: 'Packing bench', tab: 'props', clear: 1.8, build: packBench },
    tradepost:  { label: 'Trade post',    tab: 'props', clear: 2.4, build: tradePost },
    mailbox:    { label: 'Mailbox',       tab: 'props', clear: 1.0, build: mailbox },
    // nature, straight through the game's own builders
    tree_broad: { label: 'Broadleaf tree', tab: 'nature', clear: 2.6, build: treeOf('broad') },
    tree_pine:  { label: 'Pine tree',      tab: 'nature', clear: 2.4, build: treeOf('pine') },
    tree_dead:  { label: 'Dead tree',      tab: 'nature', clear: 2.2, build: treeOf('dead') },
  };

  // Gather nodes and plants come from the live rules table rather than a
  // hardcoded list, so an ore or herb added to the game shows up in the editor
  // catalog on the next boot with nothing to maintain here.
  try {
    const N = (typeof GRIM_RULES !== 'undefined' && GRIM_RULES.GATHER && GRIM_RULES.GATHER.NODES) || {};
    for (const kind in N) {
      const nd = N[kind];
      const key = 'node_' + kind.toLowerCase();
      if (C[key]) continue;
      const label = kind.replace(/_/g, ' ').toLowerCase().replace(/^./, c => c.toUpperCase());
      if (nd.skill === 'MINING') C[key] = { label, tab: 'nature', clear: 2.0, node: kind, build: oreOf(kind) };
      else if (nd.skill === 'WOODCUTTING') C[key] = { label, tab: 'nature', clear: 2.6, node: kind, build: treeOf(nd.shape || 'broad') };
      else C[key] = { label, tab: 'nature', clear: 1.2, node: kind, build: plantOf(kind) };
    }
  } catch (e) { /* catalog stays at the built-ins */ }

  return C;
})();

// ---- authored object renderer ---------------------------------------------
// SHIPS TO PLAYERS. Called from the game's dressing pass, once per chunk, so
// authored objects stream exactly like procedural ones and are disposed the
// same way when the chunk goes out of range.
const GRIM_EDIT_RENDER = (() => {

  // Build one object's mesh and park it. Returns null if the catalog does not
  // know the kind, which is the case a stale layer hits after a rename: the
  // object is skipped and the world still loads.
  function build(G, o) {
    const c = GRIM_EDIT_CATALOG[o.k];
    if (!c || !c.build) return null;
    let g;
    try { g = c.build(G, o); } catch (e) { return null; }
    if (!g) return null;
    const gy = (typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.ready) ? GRIM_WORLD.height(o.x, o.z) : 0;
    g.position.set(o.x, gy + (o.y || 0), o.z);
    g.rotation.y = o.r || 0;
    const s = o.s || 1;
    if (s !== 1) g.scale.set(s, s, s);
    // Authored objects never animate, so the matrix is computed once and the
    // renderer stops touching it. Same contract the merged clutter uses.
    g.updateMatrixWorld(true);
    g.matrixAutoUpdate = false;
    g.userData.editId = o.i;
    return g;
  }

  // Attach every authored object in this chunk. rec is the chunk record the
  // terrain streamer already keeps, so the drop path below is symmetric with
  // the one for clutter and nodes.
  function dress(G, rec) {
    if (!GRIM_EDIT.on) return;
    const list = GRIM_EDIT.objectsIn(rec.cx, rec.cz);
    if (!list || !list.length) return;
    const built = [];
    for (let i = 0; i < list.length; i++) {
      const g = build(G, list[i]);
      if (!g) continue;
      G.scene.add(g);
      built.push(g);
    }
    if (built.length) rec.editObjs = built;
  }

  function drop(G, rec) {
    if (!rec || !rec.editObjs) return;
    for (const g of rec.editObjs) {
      try { G.scene.remove(g); } catch (e) {}
      g.traverse(o => {
        if (o.geometry) { try { o.geometry.dispose(); } catch (e) {} }
      });
    }
    rec.editObjs = null;
  }

  return { build, dress, drop };
})();

  // Applied when the edit layer lands AFTER the world has already been built,
  // which is the normal case: boot never waits for the network, so the first
  // chunks are made from the generated ground and carry it baked into their
  // vertex attributes. Dropping them makes the streamer rebuild them with the
  // authored ground on the next tick.
  //
  // Attached to the render module rather than the core so the core stays a
  // pure data layer that knows nothing about chunk records.
  GRIM_EDIT_RENDER.refresh = function (G) {
    if (!G || !G._chunks) return 0;
    let n = 0;
    for (const [key, ch] of G._chunks) {
      try { G.dressDrop(ch); } catch (e) {}
      try { G.roadDrop(ch); } catch (e) {}
      try { G.scene.remove(ch.mesh); ch.mesh.geometry.dispose(); } catch (e) {}
      n++;
    }
    G._chunks.clear();
    G._terrAcc = 99;
    try { G.stepTerrain(0, 260); } catch (e) {}
    return n;
  };
