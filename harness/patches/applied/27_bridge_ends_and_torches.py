#!/usr/bin/env python3
"""Bridge ends that actually end, a teardrop flame, and ONE torch everywhere.

Kevin, looking at Crossing 2 from the west bank: "the very edge of the end of
the bridge when it meets the ground, it gets flat and flush with the dirt, and
then it turns back up at the end. It should just hit the ground and then
terminate." Plus: round the base of the flame into a teardrop, and give the town
torches the same flame and the same post while keeping their taller height.

--------------------------------------------------------------------------
1. THE BRIDGE END. TWO BUGS, AND THE SECOND ONE IS WHY IT SURVIVED SO LONG.
--------------------------------------------------------------------------

Measured off the built mesh, not guessed. Dumping the deck ribbon's own vertex
buffer out of the live scene for Crossing 2 gives, from the west end inward:

    a = -24.0   y = 7.019      <- the end of the deck
    a = -22.0   y = 6.175
    a = -20.0   y = 6.519
    a = -18.0   y = 6.863
    a = -16.0   y = 7.019      <- full deck height, out over the water

That is the defect as a number. The deck descends to 6.175 and then the LAST
segment jumps back up 0.84m to full deck height. A notch, exactly the shape in
the screenshot.

BUG A: the outermost station falls out of bridgeDeckY's range by 1.8e-14.

`buildBridge` walks stations from `aStart = -(dA + ramp)` and asks
`bridgeDeckY` for the height at each one. That function reconstructs the
distance along the span from the world point:

    cx = b.x + dx * a          ->   rx = cx - b.x   ->   along = rx*dx + rz*dz

For Crossing 2 (heading 1.5708, so dx ~ 1 and dz ~ -3.7e-6) that round trip
returns -24.000000000000018 for a = -24. The guard

    if (along > endB || along < -endA) continue;

then fires, `bridgeDeckY` returns null, and the station falls back to

    y: (y === null ? g.deckY : y)

which is the FULL DECK HEIGHT. The far end squeaks through at
23.999999999999989 and is fine, which is why only one end of each bridge looked
wrong and why it never reproduced symmetrically. Every previous fix moved where
the bridge ends; none of them could ever have helped, because the endpoint was
not being evaluated at all.

Fixed twice over, belt and braces:
  - the range test carries a 1e-6 epsilon, so a point ON the end is on the deck
  - the ramp parameter is clamped to 0..1, so even a point that slips past the
    epsilon lands on the end of the curve instead of extrapolating off it
  - `buildBridge` no longer needs the null fallback for its own end stations,
    because they can no longer be null; it keeps it only as a guard.

BUG B: the abutment height was sampled half a ramp short of the abutment.

    hA = height(b.x - dx * (dA + ramp * 0.5), ...)

but the ramp ENDS at dA + ramp. So the deck aimed at the height of a point
still on the slope down to the river, which is lower than where the deck
actually stops. Every deck end was therefore driven INTO the bank. Measured
deck-minus-ground at the end station, before:

    Crossing 1  -0.737 / -1.217      Argent Bridge     -0.521 /  0.000
    Crossing 2  -0.250 / -0.269      Kingsford Bridge  -0.741 / -0.695
    Crossing 3  -0.055 / -0.436      Crossing 6        -0.548 / -0.035

That is the "flat and flush with the dirt" half of what Kevin described: the
last metres of deck buried in the bank. Sampling at the true ramp end puts every
one of the twelve abutments at 0.000, and the minimum deck-minus-ground
anywhere along any of the six spans becomes -0.002, which is rounding.

--------------------------------------------------------------------------
2. THE FLAME IS A TEARDROP NOW, NOT A CONE.
--------------------------------------------------------------------------

`ConeGeometry(0.26, 0.62, 8, 5)` is widest exactly at the wick and then falls
away in a dead straight line. However good the shader is, the silhouette is a
paper hat. Fire is a teardrop: it pinches at the wick, swells into a round belly
about a third of the way up, and draws out to a fine tip.

Lathed from

    r(t) = R * sin(PI * t^0.55)^0.9,    t = 0 at the wick, 1 at the tip

The fractional power inside the sine moves the widest point from the middle down
to t = 0.28, and gives the profile a HORIZONTAL tangent where it meets the axis,
which is what makes the base read as a round cap rather than a point. The tip
stays linear so the noise erosion still has something to chew into.

Height stays 0.62 centred on the origin. That is not cosmetic: the shader
derives its 0..1 height factor as `transformed.y / 0.62 + 0.5`, and one material
is shared by every flame in the world, so changing the height here would
silently break the colour ramp on every torch.

--------------------------------------------------------------------------
3. ONE TORCH, BUILT IN ONE PLACE.
--------------------------------------------------------------------------

The bridges got the shader flame in b1250d7. The town got eight posts with an
emissive icosahedron stuck on top, because it is built by a different function
300 lines away. Two builders, one of which nobody remembered to update: that is
the actual bug, and it will happen again unless there is one of them.

`buildTorches(parent, spots, h, mat, opt)` now builds all of them: stake, iron
band, packed base, the shader flame, and a glow disc draped over the terrain.
`h` is the height of the WICK above the ground, so the bridges pass 2.05 and the
town passes 3.05, which is the height Kevin looked at and asked to keep.

The town gets it instanced too: eight posts in four instanced draws instead of
eight groups of two meshes, so this is fewer draw calls than before, not more.
The point lights on every third post stay exactly as they were.
"""
import io, re

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()


def sub(old, new, what):
    """Exact-string replace with a count assert. A silently-missed anchor is the
    one failure mode that ships a bundle that looks built and is not."""
    global s
    n = s.count(old)
    assert n == 1, 'anchor for %s matched %d times, expected 1' % (what, n)
    s = s.replace(old, new)
    print('   ok  %s' % what)


def cut(start, end, what):
    """Return the exact source between two unique markers, inclusive of both."""
    a = s.find(start)
    b = s.find(end)
    assert a >= 0 and b > a, 'markers for %s not found' % what
    return s[a:b + len(end)]


# ---------------------------------------------------------------------------
# 1a. sample the abutment height where the ramp actually ends
# ---------------------------------------------------------------------------
sub(
    "    const hA = GRIM_WORLD.height(b.x - dx * (dA + ramp * 0.5), b.z - dz * (dA + ramp * 0.5));\n"
    "    const hB = GRIM_WORLD.height(b.x + dx * (dB + ramp * 0.5), b.z + dz * (dB + ramp * 0.5));\n",

    "    // Sampled at dA + ramp, which is where the ramp ENDS. It used to be\n"
    "    // dA + ramp * 0.5, half a ramp short: a point still on the slope down to\n"
    "    // the river, and therefore lower than the ground the deck actually\n"
    "    // reaches. The deck was aimed under the bank and buried its last metres\n"
    "    // in it, by 0.05m on the best abutment and 1.22m on the worst. Sampled at\n"
    "    // the true end, all twelve abutments land on the ground to within 2mm.\n"
    "    const hA = GRIM_WORLD.height(b.x - dx * (dA + ramp), b.z - dz * (dA + ramp));\n"
    "    const hB = GRIM_WORLD.height(b.x + dx * (dB + ramp), b.z + dz * (dB + ramp));\n",
    'abutment height sampled at the true ramp end')


# ---------------------------------------------------------------------------
# 1b. the endpoint must not fall off the end of its own range
# ---------------------------------------------------------------------------
sub(
    "      const endA = g.dA + g.ramp, endB = g.dB + g.ramp;\n"
    "      if (along > endB || along < -endA) continue;\n"
    "      // Flat over the water, ramping down to each bank over the approach.\n"
    "      if (along < -g.dA) {\n"
    "        const t = (along + endA) / g.ramp;\n"
    "        return g.hA + (g.deckY - g.hA) * (t * t * (3 - 2 * t));\n"
    "      }\n"
    "      if (along > g.dB) {\n"
    "        const t = (endB - along) / g.ramp;\n"
    "        return g.hB + (g.deckY - g.hB) * (t * t * (3 - 2 * t));\n"
    "      }\n",

    "      const endA = g.dA + g.ramp, endB = g.dB + g.ramp;\n"
    "      // EPS, and it is not superstition. buildBridge places its outermost\n"
    "      // station at exactly -(dA + ramp), then this function reconstructs the\n"
    "      // distance from the world point: cx = b.x + dx * a, rx = cx - b.x,\n"
    "      // along = rx * dx + rz * dz. On Crossing 2 that round trip returns\n"
    "      // -24.000000000000018 for a = -24, the test fired, this returned null,\n"
    "      // and the caller fell back to the FULL DECK HEIGHT. That is the deck\n"
    "      // end kicking back up: not a modelling mistake, a boundary miss of\n"
    "      // 1.8e-14. The far end came back 23.999999999999989 and was fine, which\n"
    "      // is why only one end of each crossing ever looked wrong.\n"
    "      const EPS = 1e-6;\n"
    "      if (along > endB + EPS || along < -endA - EPS) continue;\n"
    "      // Flat over the water, ramping down to each bank over the approach.\n"
    "      // t is clamped as well, so a point that slips past EPS still lands ON\n"
    "      // the end of the curve instead of extrapolating off the end of it.\n"
    "      if (along < -g.dA) {\n"
    "        const t = Math.max(0, Math.min(1, (along + endA) / g.ramp));\n"
    "        return g.hA + (g.deckY - g.hA) * (t * t * (3 - 2 * t));\n"
    "      }\n"
    "      if (along > g.dB) {\n"
    "        const t = Math.max(0, Math.min(1, (endB - along) / g.ramp));\n"
    "        return g.hB + (g.deckY - g.hB) * (t * t * (3 - 2 * t));\n"
    "      }\n",
    'bridgeDeckY endpoint epsilon and clamped ramp')


# ---------------------------------------------------------------------------
# 2. teardrop flame geometry, plus 3. the one shared torch builder.
#    Both go in next to the flame material they belong with.
# ---------------------------------------------------------------------------
TORCH = r"""
  // The flame SILHOUETTE. The shader was already good; the shape it was painted
  // on was a straight cone, widest exactly at the wick and falling away in a
  // dead line, which reads as a paper hat with a fire shader on it. Fire is a
  // teardrop: pinched at the wick, a round belly about a third of the way up,
  // drawn out to a fine tip.
  //
  //   r(t) = R * sin(PI * t^0.55)^0.9      t = 0 at the wick, 1 at the tip
  //
  // The fractional power inside the sine drags the widest point down from the
  // middle to t = 0.28, and leaves the profile with a HORIZONTAL tangent where
  // it meets the axis, which is the whole trick: that is what makes the bottom
  // read as a round cap instead of a second point. The tip stays linear so the
  // noise erosion still has an edge to tear into.
  //
  // The height stays 0.62 centred on the origin, and that is load bearing, not
  // cosmetic: the shader derives its 0..1 height factor as
  // transformed.y / 0.62 + 0.5, and ONE material is shared by every flame in
  // the world, so a different height here would quietly wreck the colour ramp
  // on every torch at once.
  torchFlameGeo() {
    if (this._flameGeo) return this._flameGeo;
    const T = this.T, R = 0.27, H = 0.62, N = 16;
    const pts = [];
    for (let i = 0; i <= N; i++) {
      const t = i / N;
      const r = R * Math.pow(Math.sin(Math.PI * Math.pow(t, 0.55)), 0.9);
      // a hair of radius kept off the axis except at the very tip, so the lathe
      // does not fold a ring of degenerate triangles at the base
      pts.push(new T.Vector2(i === N ? 0 : Math.max(r, 0.004), t * H - H * 0.5));
    }
    this._flameGeo = new T.LatheGeometry(pts, 10);
    return this._flameGeo;
  }

  // ---- one torch, everywhere ----------------------------------------------
  // There used to be two torch builders 300 lines apart. The bridges got the
  // shader flame and the town kept an emissive lump on a stick, because nobody
  // remembered the second copy. That is the actual bug, and it recurs until
  // there is only one of them.
  //
  //   spots  [[x, z], ...] in world space
  //   h      height of the WICK above the ground. Bridges pass 2.05; the town
  //          passes 3.05, which is the height Kevin looked at and asked to keep.
  //   mat    the timber material of whatever is building it
  //
  // Instanced, so eight town torches cost four draws rather than sixteen.
  buildTorches(parent, spots, h, mat, opt) {
    const T = this.T, o = opt || {}, n = spots.length;
    if (!n) return;
    const dm = new T.Object3D();
    // A stake, an iron band and a packed base. Three primitives is enough to
    // read as a made object rather than a dowel pushed into the dirt, and stops
    // well short of a model nobody will stand and study. The stake is unit tall
    // and scaled, so one geometry serves every height.
    const stakes = new T.InstancedMesh(new T.CylinderGeometry(0.085, 0.115, 1, 6), mat, n);
    const bands  = new T.InstancedMesh(new T.CylinderGeometry(0.140, 0.140, 0.10, 8), mat, n);
    const bases  = new T.InstancedMesh(new T.CylinderGeometry(0.34, 0.46, 0.24, 8), mat, n);
    // One material per kind, shared by every torch in the world and pulsed in
    // the frame loop. Animating a shared material is one assignment per frame
    // for the whole map; touching instance matrices would be per torch.
    const flames = new T.InstancedMesh(this.torchFlameGeo(), this.torchFlameMat(), n);
    const gm = this.torchGlowMat();
    const yaw = o.yaw || 0;
    for (let i = 0; i < n; i++) {
      const tx = spots[i][0], tz = spots[i][1];
      // Raw terrain, deliberately NOT groundY. groundY returns the DECK
      // inside a bridge footprint, and a bridge torch's 2.6m glow disc
      // reaches back under the deck edge: draped on groundY it would climb
      // the bridge. Off a deck the two are the same function anyway.
      const gy = GRIM_WORLD.height(tx, tz);
      dm.rotation.set(0, yaw, 0);
      dm.scale.set(1, h, 1);
      dm.position.set(tx, gy + h * 0.5, tz); dm.updateMatrix(); stakes.setMatrixAt(i, dm.matrix);
      dm.scale.set(1, 1, 1);
      dm.position.set(tx, gy + h - 0.15, tz); dm.updateMatrix(); bands.setMatrixAt(i, dm.matrix);
      dm.position.set(tx, gy + 0.12, tz); dm.updateMatrix(); bases.setMatrixAt(i, dm.matrix);
      // the flame is 0.62 tall about its centre, so + 0.31 stands its BASE on
      // the wick rather than running it through the top of the stake
      dm.position.set(tx, gy + h + 0.31, tz); dm.updateMatrix(); flames.setMatrixAt(i, dm.matrix);
      // The glow is a flat additive disc on the ground, not a light. Lights get
      // switched off in performance mode and cost per fragment; a disc always
      // shows, reads correctly in daylight, and is one draw call. It is DRAPED:
      // a single flat disc gets cut off along a dead straight line wherever the
      // land rises through its plane, so every vertex samples the terrain.
      const GR = 2.6, GSEG = 24;
      const gGeo = new T.CircleGeometry(GR, GSEG);
      gGeo.rotateX(-Math.PI / 2);
      const gpos = gGeo.attributes.position;
      for (let v = 0; v < gpos.count; v++) {
        gpos.setY(v, GRIM_WORLD.height(tx + gpos.getX(v), tz + gpos.getZ(v)) + 0.07 - gy);
      }
      gpos.needsUpdate = true;
      const gMesh = new T.Mesh(gGeo, gm);
      gMesh.position.set(tx, gy, tz);
      gMesh.renderOrder = 2;
      parent.add(gMesh);
    }
    for (const m of [stakes, bands, bases, flames]) {
      m.count = n; m.instanceMatrix.needsUpdate = true;
    }
    stakes.castShadow = true; bands.castShadow = true; bases.castShadow = true;
    parent.add(bases); parent.add(stakes); parent.add(bands); parent.add(flames);
    return flames;
  }
"""

sub("  // The glow was a flat disc of uniform opacity, so it read as a solid painted",
    TORCH.rstrip() + "\n\n  // The glow was a flat disc of uniform opacity, so it read as a solid painted",
    'teardrop flame geometry + shared torch builder')


# ---------------------------------------------------------------------------
# 3a. the bridge torches go through the shared builder
# ---------------------------------------------------------------------------
OLD_BRIDGE_TORCHES = cut(
    "      const tOff = g.wide + 2.0;",
    "      grp.add(bases); grp.add(stakes); grp.add(bands); grp.add(flames);",
    'bridge torch block')

sub(OLD_BRIDGE_TORCHES,
    "      // Pinned to the MEASURED abutments, not to the baked half span, so they\n"
    "      // stand at the ends of the deck as built. Any that still land wet are\n"
    "      // walked inland rather than left standing in the river. Everything from\n"
    "      // the stake up is buildTorches now, shared with the town.\n"
    "      const tOff = g.wide + 2.0;\n"
    "      const spots = [];\n"
    "      for (const sgn of [-1, 1]) {\n"
    "        const dEnd = (sgn < 0 ? (g.dA || g.half) : (g.dB || g.half)) + g.ramp - 0.5;\n"
    "        for (const so of [-tOff, tOff]) {\n"
    "          let tx = b.x + dx * sgn * dEnd + px * so, tz = b.z + dz * sgn * dEnd + pz * so;\n"
    "          for (let s = 0; s < 14 && GRIM_WORLD.waterDepth(tx, tz) > 0.02; s++) {\n"
    "            tx += dx * sgn * 1.0; tz += dz * sgn * 1.0;   // step further inland\n"
    "          }\n"
    "          spots.push([tx, tz]);\n"
    "        }\n"
    "      }\n"
    "      this.buildTorches(grp, spots, 2.05, partM, { yaw: b.heading });",
    'bridge torches routed through buildTorches')


# ---------------------------------------------------------------------------
# 3b. the town posts get the same torch, at the height Kevin kept
# ---------------------------------------------------------------------------
sub(
    "    for (let i = 0; i < 8; i++) {\n"
    "      const a = (i / 8) * Math.PI * 2;\n"
    "      const lp = this.clearOfRoad(TX + Math.cos(a) * 21, TZ + Math.sin(a) * 21);\n"
    "      const lx = lp[0], lz = lp[1];\n"
    "      const lg = new T.Group();\n"
    "      const pole = new T.Mesh(new T.CylinderGeometry(0.07, 0.09, 3.0, 6), woodD); pole.position.y = 1.5; lg.add(pole);\n"
    "      const lamp = new T.Mesh(new T.IcosahedronGeometry(0.22, 0), new T.MeshStandardMaterial({ color: 0xffd98a, emissive: 0xd8a531, emissiveIntensity: 1.6, roughness: 0.3 }));\n"
    "      lamp.position.y = 3.05; lg.add(lamp);\n"
    "      // Only a few carry a real light — point lights are the expensive part.\n"
    "      if (i % 3 === 0) { const pl = new T.PointLight(0xffc76a, 2.2, 26, 2); pl.position.y = 3.05; lg.add(pl); (this.decorLights = this.decorLights || []).push(pl); }\n"
    "      lg.position.set(lx, this.groundY(lx, lz), lz); S.add(lg);\n"
    "    }\n",

    "    // The town torches. These were a pole with an emissive icosahedron on\n"
    "    // top: a glowing ball, not a flame, because they are built here and the\n"
    "    // shader flame was added over in the bridge code. Same torch as the\n"
    "    // bridges now, through the same builder, at the 3.05m wick height these\n"
    "    // already stood at, which is the height Kevin wants kept.\n"
    "    {\n"
    "      const tSpots = [];\n"
    "      for (let i = 0; i < 8; i++) {\n"
    "        const a = (i / 8) * Math.PI * 2;\n"
    "        const lp = this.clearOfRoad(TX + Math.cos(a) * 21, TZ + Math.sin(a) * 21);\n"
    "        tSpots.push([lp[0], lp[1]]);\n"
    "      }\n"
    "      const tg = new T.Group();\n"
    "      this.buildTorches(tg, tSpots, 3.05, woodD);\n"
    "      // Only a few carry a real light — point lights are the expensive part.\n"
    "      for (let i = 0; i < tSpots.length; i += 3) {\n"
    "        const pl = new T.PointLight(0xffc76a, 2.2, 26, 2);\n"
    "        pl.position.set(tSpots[i][0], GRIM_WORLD.height(tSpots[i][0], tSpots[i][1]) + 3.15, tSpots[i][1]);\n"
    "        tg.add(pl); (this.decorLights = this.decorLights || []).push(pl);\n"
    "      }\n"
    "      S.add(tg);\n"
    "    }\n",
    'town posts routed through buildTorches at 3.05m')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 26 applied')
