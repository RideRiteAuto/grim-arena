#!/usr/bin/env python3
"""Phase 2, part 1: zone art. Per-zone clutter sets and per-species tree shapes.

Phase 1 gave every zone the same four props in different colours, which is
enough to prove the engine and not enough to make a place feel like itself.
This gives each zone its own clutter mix and every tree species its own
silhouette, so a poplar is not an oak wearing a different green.

The Heartlands is what this phase is aimed at, so it gets the set the plan asks
for: broad oaks, poplars, orchard apples, wheat grass, wildflowers, hay bales
near the capital, sticks and field stones.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ---------------------------------------------- 1. per-zone clutter tables
# `mix` was four weights against a fixed type list, so every zone had to have
# exactly tufts, bushes, pebbles and sticks in some ratio. A clutter LIST per
# zone lets Windscar have sun bleached bones and no bushes, and lets the
# Heartlands have wheat and wildflowers that exist nowhere else.
sub(
    "      ISLES:      { tuft: 0x8fa25e, bush: 0x4f7a44, stone: 0xa89e86, stick: 0x8a7a5a, trunk: 0x7a5f3c, leaf: 0x5f9a4e, leaf2: 0x4e8a42, mix: [5, 3, 4, 3] }\n"
    "    });\n"
    "  }",

    "      ISLES:      { tuft: 0x8fa25e, bush: 0x4f7a44, stone: 0xa89e86, stick: 0x8a7a5a, trunk: 0x7a5f3c, leaf: 0x5f9a4e, leaf2: 0x4e8a42, mix: [5, 3, 4, 3] }\n"
    "    });\n"
    "  }\n"
    "\n"
    "  // What actually litters the ground in each zone, and how often. Weights are\n"
    "  // relative within the zone. Every type named here must exist in _clutterGeo.\n"
    "  ZONE_CLUTTER() {\n"
    "    return this._zoneClutter || (this._zoneClutter = {\n"
    "      HEARTLANDS: [['wheat', 7], ['flower', 4], ['tuft', 4], ['bush', 2], ['pebble', 3], ['stick', 2]],\n"
    "      GREENWOOD:  [['fern', 7], ['bush', 5], ['tuft', 3], ['log', 2], ['stick', 4], ['pebble', 2]],\n"
    "      FROSTWILD:  [['drift', 6], ['tuft', 3], ['bush', 2], ['pebble', 5], ['stick', 3]],\n"
    "      IRONSPIRE:  [['pebble', 9], ['boulder', 4], ['tuft', 2], ['bush', 1]],\n"
    "      SUNCOAST:   [['tuft', 5], ['shell', 4], ['pebble', 4], ['stick', 3], ['bush', 2]],\n"
    "      WINDSCAR:   [['wheat', 8], ['tuft', 4], ['bone', 2], ['pebble', 2], ['bush', 1]],\n"
    "      EMBER:      [['ash', 6], ['shard', 4], ['pebble', 4], ['stick', 3], ['bush', 1]],\n"
    "      MISTFEN:    [['reed', 7], ['fern', 4], ['tuft', 3], ['log', 2], ['pebble', 1]],\n"
    "      SUNSCORCH:  [['pebble', 6], ['bone', 3], ['tuft', 3], ['bush', 2], ['shard', 2]],\n"
    "      EASTRIDGE:  [['pebble', 8], ['boulder', 3], ['tuft', 3], ['bush', 1]],\n"
    "      ISLES:      [['tuft', 5], ['shell', 4], ['pebble', 3], ['stick', 3], ['bush', 2]]\n"
    "    });\n"
    "  }\n"
    "\n"
    "  // Colour for a clutter type. Types that exist in more than one zone read\n"
    "  // from that zone's palette so wheat is gold in the Heartlands and bleached\n"
    "  // in Windscar; types that only make sense one way carry their own colour.\n"
    "  CLUTTER_TINT(zone, type) {\n"
    "    const look = this.ZONE_LOOK()[zone] || this.ZONE_LOOK().HEARTLANDS;\n"
    "    const OWN = {\n"
    "      flower: 0xd8d05a, shell: 0xe6dcc6, bone: 0xd9d2bd, ash: 0x59524c,\n"
    "      shard: 0x2b2436, drift: 0xe4ecf2, reed: 0x7f9a4a, hay: 0xc9a94e\n"
    "    };\n"
    "    if (OWN[type] !== undefined) return OWN[type];\n"
    "    if (type === 'wheat') return zone === 'WINDSCAR' ? 0xc0ad72 : 0xc9b25e;\n"
    "    if (type === 'fern' || type === 'bush') return look.bush;\n"
    "    if (type === 'pebble' || type === 'boulder') return look.stone;\n"
    "    if (type === 'stick' || type === 'log') return look.stick;\n"
    "    return look.tuft;\n"
    "  }",
    'zone clutter tables')

# ------------------------------------------------- 2. the clutter geometry
sub(
    "    this._clutterGeo = {\n"
    "      pebble: nonIdx(new T.DodecahedronGeometry(0.22, 0)),\n"
    "      stick:  nonIdx(new T.BoxGeometry(0.06, 0.06, 0.8)),\n"
    "      tuft:   nonIdx(new T.ConeGeometry(0.2, 0.55, 4)),\n"
    "      bush:   nonIdx(new T.IcosahedronGeometry(0.55, 0))\n"
    "    };",

    "    // One template per clutter type, prepared non-indexed once and then\n"
    "    // instanced into the per-chunk merge. Everything here is deliberately\n"
    "    // tiny: a chunk carries up to 22 of these and they all end up in a\n"
    "    // single mesh, so triangle count matters more than detail.\n"
    "    this._clutterGeo = {\n"
    "      pebble:  nonIdx(new T.DodecahedronGeometry(0.22, 0)),\n"
    "      boulder: nonIdx(new T.DodecahedronGeometry(0.55, 0)),\n"
    "      stick:   nonIdx(new T.BoxGeometry(0.06, 0.06, 0.8)),\n"
    "      log:     nonIdx(new T.CylinderGeometry(0.16, 0.19, 1.5, 6)),\n"
    "      tuft:    nonIdx(new T.ConeGeometry(0.2, 0.55, 4)),\n"
    "      bush:    nonIdx(new T.IcosahedronGeometry(0.55, 0)),\n"
    "      wheat:   nonIdx(new T.ConeGeometry(0.13, 1.05, 3)),\n"
    "      reed:    nonIdx(new T.ConeGeometry(0.07, 1.35, 3)),\n"
    "      fern:    nonIdx(new T.ConeGeometry(0.42, 0.34, 5)),\n"
    "      flower:  nonIdx(new T.IcosahedronGeometry(0.11, 0)),\n"
    "      shell:   nonIdx(new T.ConeGeometry(0.14, 0.1, 6)),\n"
    "      bone:    nonIdx(new T.BoxGeometry(0.07, 0.07, 0.62)),\n"
    "      ash:     nonIdx(new T.ConeGeometry(0.46, 0.16, 6)),\n"
    "      shard:   nonIdx(new T.TetrahedronGeometry(0.24, 0)),\n"
    "      drift:   nonIdx(new T.SphereGeometry(0.52, 7, 4)),\n"
    "      hay:     nonIdx(new T.CylinderGeometry(0.42, 0.42, 0.62, 8))\n"
    "    };\n"
    "    // How each type sits on the ground: y offset as a fraction of scale, and\n"
    "    // whether it lies down rather than standing up.\n"
    "    this._clutterSit = {\n"
    "      pebble: [0.10, 0], boulder: [0.24, 0], stick: [0.04, 1], log: [0.17, 1],\n"
    "      tuft: [0.24, 0], bush: [0.30, 0], wheat: [0.48, 0], reed: [0.62, 0],\n"
    "      fern: [0.14, 0], flower: [0.22, 0], shell: [0.05, 0], bone: [0.04, 1],\n"
    "      ash: [0.05, 0], shard: [0.11, 0], drift: [0.14, 0], hay: [0.31, 1]\n"
    "    };",
    'clutter geometry')

# ------------------------------------------- 3. pick clutter from the table
sub(
    "    const TYPES = ['tuft', 'bush', 'pebble', 'stick'];\n",
    "",
    'drop fixed types')

sub(
    "      const look = this.ZONE_LOOK()[zone] || this.ZONE_LOOK().HEARTLANDS;\n"
    "      const mix = look.mix, mt = mix[0] + mix[1] + mix[2] + mix[3];\n"
    "      let acc = pick * mt, ti = 0;\n"
    "      for (; ti < 3; ti++) { if (acc < mix[ti]) break; acc -= mix[ti]; }\n"
    "      clutter.push({ type: TYPES[ti], zone: zone, x: x, z: z, y: GRIM_WORLD.height(x, z), rot: rot, sc: sc });",

    "      const set = this.ZONE_CLUTTER()[zone] || this.ZONE_CLUTTER().HEARTLANDS;\n"
    "      let mt = 0;\n"
    "      for (const e of set) mt += e[1];\n"
    "      let acc = pick * mt, type = set[0][0];\n"
    "      for (const e of set) { if (acc < e[1]) { type = e[0]; break; } acc -= e[1]; }\n"
    "      // Hay bales are farmland dressing, so they only appear on the ring of\n"
    "      // Heartlands ground that is near the capital without being inside its\n"
    "      // exclusion: close enough to read as farmland, far enough to be legal.\n"
    "      if (zone === 'HEARTLANDS' && type === 'wheat') {\n"
    "        const d = Math.hypot(x, z);\n"
    "        if (d < 220 && pick > 0.93) type = 'hay';\n"
    "      }\n"
    "      clutter.push({ type: type, zone: zone, x: x, z: z, y: GRIM_WORLD.height(x, z), rot: rot, sc: sc });",
    'clutter pick')

# ------------------------------------------------ 4. place it with its sit
sub(
    "      for (const p of props.clutter) {\n"
    "        const look = LOOKS[p.zone] || LOOKS.HEARTLANDS;\n"
    "        const m = new T.Matrix4().compose(\n"
    "          new T.Vector3(p.x, p.y + (p.type === 'pebble' ? 0.08 : p.type === 'stick' ? 0.04 : 0.2) * p.sc, p.z),\n"
    "          new T.Quaternion().setFromEuler(new T.Euler(p.type === 'stick' ? Math.PI / 2 : 0, p.rot, 0)),\n"
    "          new T.Vector3(p.sc, p.sc, p.sc));\n"
    "        parts.push({ geo: this._clutterGeo[p.type], m: m, color: new T.Color(look[p.type] || look.tuft) });\n"
    "      }",

    "      for (const p of props.clutter) {\n"
    "        const geo = this._clutterGeo[p.type];\n"
    "        if (!geo) continue;\n"
    "        const sit = this._clutterSit[p.type] || [0.2, 0];\n"
    "        const m = new T.Matrix4().compose(\n"
    "          new T.Vector3(p.x, p.y + sit[0] * p.sc, p.z),\n"
    "          new T.Quaternion().setFromEuler(new T.Euler(sit[1] ? Math.PI / 2 : 0, p.rot, sit[1] ? 0 : (p.rot * 0.3) % 0.25)),\n"
    "          new T.Vector3(p.sc, p.sc, p.sc));\n"
    "        parts.push({ geo: geo, m: m, color: new T.Color(this.CLUTTER_TINT(p.zone, p.type)) });\n"
    "      }",
    'clutter placement')

# --------------------------------------------------- 5. tree silhouettes
# One builder, driven by a shape name off the node definition. A poplar is
# narrow and tall with the canopy stacked up the trunk; an oak is short and
# wide; an orchard apple is small, round and carries fruit.
sub(
    "  makeZoneTree(look, sc, seed) {\n"
    "    const T = this.T;\n"
    "    const rnd = grimRnd(seed);\n"
    "    const S = 1.25 * sc;\n"
    "    const lean = (rnd() - 0.5) * 0.14;",

    "  // Per species silhouette. shape comes off the node definition, so adding a\n"
    "  // species is a table entry and a case here, not a new function.\n"
    "  TREE_SHAPE(shape) {\n"
    "    const S = {\n"
    "      broad:   { h: 1.00, trunk: 1.00, blobs: 3, rad: 1.35, spread: 0.90, rise: 3.10, step: 0.85, squash: 0.85 },\n"
    "      poplar:  { h: 1.45, trunk: 0.68, blobs: 4, rad: 0.78, spread: 0.26, rise: 2.30, step: 1.05, squash: 1.25 },\n"
    "      orchard: { h: 0.72, trunk: 0.95, blobs: 3, rad: 1.05, spread: 0.72, rise: 2.05, step: 0.62, squash: 0.92, fruit: 0xb8342c },\n"
    "      elder:   { h: 1.30, trunk: 1.45, blobs: 4, rad: 1.85, spread: 1.20, rise: 3.60, step: 1.00, squash: 0.80 },\n"
    "      pine:    { h: 1.20, trunk: 0.80, blobs: 4, rad: 1.10, spread: 0.10, rise: 2.40, step: 1.15, squash: 1.55, cone: true },\n"
    "      palm:    { h: 1.15, trunk: 0.55, blobs: 5, rad: 0.62, spread: 1.10, rise: 4.10, step: 0.06, squash: 0.35 },\n"
    "      willow:  { h: 1.05, trunk: 0.92, blobs: 4, rad: 1.30, spread: 1.05, rise: 2.70, step: 0.42, squash: 1.30 },\n"
    "      snag:    { h: 0.95, trunk: 0.85, blobs: 1, rad: 0.45, spread: 0.20, rise: 2.90, step: 0.5, squash: 0.7 }\n"
    "    };\n"
    "    return S[shape] || S.broad;\n"
    "  }\n"
    "\n"
    "  makeZoneTree(look, sc, seed, shape) {\n"
    "    const T = this.T;\n"
    "    const rnd = grimRnd(seed);\n"
    "    const F = this.TREE_SHAPE(shape);\n"
    "    const S = 1.25 * sc * F.h;\n"
    "    const lean = (rnd() - 0.5) * 0.14 * (F.trunk > 1 ? 0.6 : 1);",
    'tree shape table')

sub(
    "    const trunkMesh = this.loftMesh([\n"
    "      { z: 0, w: 0.42 * S, h: 0.42 * S, y: 0 },\n"
    "      { z: 0.5 * S, w: 0.26 * S, h: 0.26 * S, y: lean * 0.6 },\n"
    "      { z: 2.0 * S, w: 0.2 * S, h: 0.2 * S, y: lean * 1.6 },\n"
    "      { z: 3.0 * S, w: 0.14 * S, h: 0.14 * S, y: lean * 2.4 }\n"
    "    ], 7, look.trunk, look.stick, this._nodeMat);",

    "    const W = F.trunk;\n"
    "    const trunkMesh = this.loftMesh([\n"
    "      { z: 0, w: 0.42 * S * W, h: 0.42 * S * W, y: 0 },\n"
    "      { z: 0.5 * S, w: 0.26 * S * W, h: 0.26 * S * W, y: lean * 0.6 },\n"
    "      { z: 2.0 * S, w: 0.2 * S * W, h: 0.2 * S * W, y: lean * 1.6 },\n"
    "      { z: (F.rise + 0.2) * S, w: 0.13 * S * W, h: 0.13 * S * W, y: lean * 2.4 }\n"
    "    ], 7, look.trunk, look.stick, this._nodeMat);",
    'tree trunk')

sub(
    "    for (let i = 0; i < 3; i++) {\n"
    "      const geo = this.jitterGeo(new T.IcosahedronGeometry(1.35 * S * (1 - i * 0.16) + rnd() * 0.3, 0), 0.22, rnd() * 97, 0.85);\n"
    "      const a = rnd() * Math.PI * 2;\n"
    "      const m = new T.Matrix4().makeTranslation(\n"
    "        Math.sin(a) * (i ? 0.9 : 0) * S + lean * 2.2, (3.1 + i * 0.85) * S, Math.cos(a) * (i ? 0.9 : 0) * S);\n"
    "      parts.push({ geo: geo.index ? geo.toNonIndexed() : geo, m: m, color: i % 2 ? cL2 : cL });\n"
    "    }",

    "    for (let i = 0; i < F.blobs; i++) {\n"
    "      const r = F.rad * S * (1 - i * (F.cone ? 0.22 : 0.16)) + rnd() * 0.3;\n"
    "      const geo = this.jitterGeo(new T.IcosahedronGeometry(r, 0), 0.22, rnd() * 97, F.squash);\n"
    "      const a = rnd() * Math.PI * 2;\n"
    "      const off = F.spread * (i ? 1 : 0.15) * S;\n"
    "      const m = new T.Matrix4().makeTranslation(\n"
    "        Math.sin(a) * off + lean * 2.2, (F.rise + i * F.step) * S, Math.cos(a) * off);\n"
    "      parts.push({ geo: geo.index ? geo.toNonIndexed() : geo, m: m, color: i % 2 ? cL2 : cL });\n"
    "    }\n"
    "    // Orchard trees carry fruit. It is four tiny spheres and it is the whole\n"
    "    // difference between an apple tree and a small oak at fifty metres.\n"
    "    if (F.fruit) {\n"
    "      const cF = new T.Color(F.fruit);\n"
    "      for (let i = 0; i < 5; i++) {\n"
    "        const a = rnd() * Math.PI * 2, r = (0.45 + rnd() * 0.5) * S;\n"
    "        const geo = new T.IcosahedronGeometry(0.10 * S, 0);\n"
    "        const m = new T.Matrix4().makeTranslation(Math.sin(a) * r, (F.rise + rnd() * 0.7) * S, Math.cos(a) * r);\n"
    "        parts.push({ geo: geo.index ? geo.toNonIndexed() : geo, m: m, color: cF });\n"
    "      }\n"
    "    }",
    'tree canopy')

sub(
    "    const stumpMesh = this.loftMesh([\n"
    "      { z: 0, w: 0.42 * S, h: 0.42 * S, y: 0 },\n"
    "      { z: 0.3 * S, w: 0.32 * S, h: 0.32 * S, y: lean * 0.36 }\n"
    "    ], 7, look.trunk, 0xb08a5c, this._nodeMat);",
    "    const stumpMesh = this.loftMesh([\n"
    "      { z: 0, w: 0.42 * S * W, h: 0.42 * S * W, y: 0 },\n"
    "      { z: 0.3 * S, w: 0.32 * S * W, h: 0.32 * S * W, y: lean * 0.36 }\n"
    "    ], 7, look.trunk, 0xb08a5c, this._nodeMat);",
    'tree stump')

sub(
    "      if (nd.skill === 'WOODCUTTING') built = this.makeZoneTree(look, p.sc, seed);",
    "      if (nd.skill === 'WOODCUTTING') built = this.makeZoneTree(look, p.sc, seed, nd.shape);",
    'pass shape')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
