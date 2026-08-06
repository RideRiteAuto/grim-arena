#!/usr/bin/env python3
"""Hollowrest, second pass: houses you can walk into, a walled market, and a keep.

All of this is Kevin looking at the last build and telling me what was wrong.

1. THE HOUSES WERE TOO SMALL AND SEALED SHUT.

   Measured: the player model stands 2.35m to the top of the helmet crest. The
   door leaf was 1.94m tall and sat on a plinth 0.35m proud of the ground, so
   the visible opening was shorter than the man standing in front of it. That is
   exactly what the screenshot shows.

   Worse, there was nothing behind it. The cottage was ONE BoxGeometry with a
   door painted on the front and a single round collider that pushed you away
   from the whole building. There was no way in and nothing to go in to.

   Now:
   - Footprints go from 5-8m wide to 8-12m, walls from 2.6-3.6m to 3.9-5.0m.
   - The doorway is a real hole: 2.6m wide, 3.2m clear, at GROUND level. The
     old 0.35m plinth ran under the whole building and made a step the player
     cannot climb, because the player's height comes from the terrain and not
     from what is under their feet. The footing now runs under the WALL LINES
     only, so the threshold is flush.
   - Walls are four slabs, not one solid box. A box only has outward faces, so
     from inside a solid-box house you would look straight through the walls at
     the sky. Slabs have a real inner surface.
   - The door is a leaf on a hinge that swings open as you walk up to it.
   - There is a floor, a hearth with a fire, a table and benches, a bed, a
     chest, a rug and a shelf.
   - Wall colliders per wall, with the doorway left open, so you can walk in
     and not through. Building yaws are quarter turns, because axis-aligned
     boxes are the only kind the collision resolver understands.
   - While you are inside, the roof lifts off and the walls drop to 22% opacity.
     The camera sits behind the player, which in a 9m room means outside the
     wall: without this you walk into a house and look at plaster.

2. HOUSES FACING EACH OTHER ACROSS A BLIND FENCE.

   Two plots ended up front to front with their fences meeting in a dead end.
   Every house now sits on a ring facing the square, so no two fronts look at
   each other, and the minimum centre-to-centre spacing is 24m, checked.
   Positions come from a fresh road-clearance survey of the ground out to 54m
   (harness/probe-town2.js), not from guessing.

3. THE MARKET AND THE WELL STOOD IN SOMEBODY'S GARDEN.

   The stalls were 4m from a cottage. The well, the three stalls, the notice
   board and the trough are now inside a walled market precinct 30 x 26m on the
   square, with a gate on each side and a path from every gate. The nearest
   house is 34m away.

4. THE BARROW.

   Kevin: it does not sit flat on the ground, I walk through it, I cannot see
   the inside walls once I am in it, and it looks like a semicircle. Redesign it
   as a castle and put the King in it.

   All three faults were real and had the same root:
   - A SphereGeometry only has outward faces. Once you were through the door the
     entire hill vanished, because you were looking at the backs of its
     triangles and the renderer culls those. There was no interior.
   - The collider ring had a 42 degree gap for the doorway. At that radius it is
     a ten metre hole, so "walking through the wall" was walking through a gap
     I left.
   - One dome placed at one height on ground with 2.4m of relief across it, so
     the rim floated on the high side.

   It is now THE HOLLOW KEEP: four curtain walls built as segments that each sit
   at their own ground height so the battlements are level and nothing floats,
   four corner towers, a gatehouse with an arch and a raised portcullis, and a
   courtyard OPEN TO THE SKY. Open-topped is deliberate: daylight reaches the
   inside, you can see in from the approach, and there is no roof to hide.

   Walls are solid box colliders with the gateway the only way through. The King
   stands before his throne in the middle of it.

Spawn ORDER is untouched. Every npc is created in the same sequence, so the
network indices are unchanged. Only positions move.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ============================================================ 1. the new house
OLD_HUT_HEAD = """    const hut = (x, z, w, d, h, rot, wallKind, roofKind, opts) => {
      opts = opts || {};
      const g = new T.Group();
      const P = [];
      const put = (geo, px, py, pz, rx, ry, rz, col) => {
        P.push({
          geo: nonIdx(geo),
          m: new T.Matrix4().compose(
            new T.Vector3(px, py, pz),
            new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
            new T.Vector3(1, 1, 1)),
          color: col
        });
      };
      const timbered = wallKind === 'plaster';"""

NEW_HUT_HEAD = """    // A house you can walk into.
    //
    // The player stands 2.35m to the crest. The old door leaf was 1.94m and sat
    // on a plinth 0.35m proud of the ground, so the opening was shorter than the
    // man in front of it, and behind it was a solid box. DWID/DHGT are the real
    // hole cut in the front wall, and the footing runs under the wall lines only
    // so the threshold is flush with the ground the player actually walks on.
    const DWID = 2.6, DHGT = 3.2, TW = 0.4;
    this._huts = [];
    const hut = (x, z, w, d, h, rot, wallKind, roofKind, opts) => {
      opts = opts || {};
      const g = new T.Group();
      const SB = [], SL = [], SR = [], SF = [], TRIM = [], RF = [], IN = [];
      const binPut = (bin) => (geo, px, py, pz, rx, ry, rz, col) => {
        bin.push({
          geo: nonIdx(geo),
          m: new T.Matrix4().compose(
            new T.Vector3(px, py, pz),
            new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
            new T.Vector3(1, 1, 1)),
          color: col
        });
      };
      // The shell is split by WALL, not merged into one mesh. While you are
      // inside, whichever walls stand between the camera and you are hidden:
      // that is the only way a third person camera can see into a 9m room. One
      // merged shell can only be faded as a whole, and fading the far wall too
      // means standing in a cottage looking at the sea through the back of it.
      const rput = binPut(RF), iput = binPut(IN), tput = binPut(TRIM);
      const sput = { back: binPut(SB), left: binPut(SL), right: binPut(SR), front: binPut(SF) };
      const xput = (sx) => sx < 0 ? sput.left : sput.right;
      const timbered = wallKind === 'plaster';"""
sub(OLD_HUT_HEAD, NEW_HUT_HEAD, 'hut head')

OLD_SHELL = """      // plinth: proud of the walls and sunk well below zero, so a hut pitched
      // on a slope buries its footing instead of hovering on one corner
      put(new T.BoxGeometry(w + 0.34, 0.9, d + 0.34), 0, -0.1, 0, 0, 0, 0, C_STONED);
      put(new T.BoxGeometry(w, h, d), 0, 0.35 + h / 2, 0, 0, 0, 0, wallC);

      const yTop = 0.35 + h;
      const rise = h * 0.52, eave = 0.35;
      const halfSpan = d / 2 + eave;
      const slopeLen = Math.sqrt(halfSpan * halfSpan + rise * rise);
      const pitch = Math.atan2(rise, halfSpan);

      // two real slopes meeting at a ridge, overhanging on every side
      for (const s of [-1, 1]) {
        put(new T.BoxGeometry(w + eave * 2, 0.16, slopeLen),
            0, yTop + rise / 2, s * halfSpan / 2, s * pitch, 0, 0, roofC);
        // laid courses on thatch, a capping row on slate
        const courses = roofKind === 'thatch' ? 3 : 2;
        for (let ci = 0; ci < courses; ci++) {
          const f = (ci + 1) / (courses + 1);
          const cz = s * halfSpan * f, cy = yTop + rise * (1 - f);
          put(new T.BoxGeometry(w + eave * 2 - 0.05, 0.07, roofKind === 'thatch' ? 0.16 : 0.1),
              0, cy + 0.11, cz, s * pitch, 0, 0, roofD);
        }
      }
      put(new T.BoxGeometry(w + eave * 2 + 0.12, 0.2, 0.26), 0, yTop + rise + 0.04, 0, 0, 0, 0, roofD);
      // close the roof void at both ends
      for (const s of [-1, 1]) {
        put(gableGeo(d, rise, 0.14), s * (w / 2 - 0.07), yTop, 0, 0, Math.PI / 2, 0, wallC);
      }
"""

NEW_SHELL = """      const hw = w / 2, hd = d / 2;
      const pw = (w - DWID) / 2;      // width of each pier beside the doorway

      // footing under the WALL LINES only. The old plinth ran under the whole
      // building and stood 0.35 proud, which put a step at the threshold the
      // player cannot climb: their height comes from the terrain, not from what
      // is under their feet, so they would have walked into the side of it.
      for (const sz of [-1, 1]) tput(new T.BoxGeometry(w + 0.5, 1.1, TW + 0.5), 0, -0.47, sz * (hd - TW / 2), 0, 0, 0, C_STONED);
      for (const sx of [-1, 1]) tput(new T.BoxGeometry(TW + 0.5, 1.1, d + 0.5), sx * (hw - TW / 2), -0.47, 0, 0, 0, 0, C_STONED);

      // Four wall SLABS with a hole in the front one, not one solid box. A box
      // only has outward faces: stand inside one and you look straight through
      // it at the sky. A slab has a real inner surface.
      sput.back(new T.BoxGeometry(w, h, TW), 0, h / 2, -(hd - TW / 2), 0, 0, 0, wallC);
      for (const sx of [-1, 1]) xput(sx)(new T.BoxGeometry(TW, h, d - TW * 2), sx * (hw - TW / 2), h / 2, 0, 0, 0, 0, wallC);
      for (const sx of [-1, 1]) sput.front(new T.BoxGeometry(pw, h, TW), sx * (DWID / 2 + pw / 2), h / 2, hd - TW / 2, 0, 0, 0, wallC);
      sput.front(new T.BoxGeometry(DWID, h - DHGT, TW), 0, DHGT + (h - DHGT) / 2, hd - TW / 2, 0, 0, 0, wallC);

      const yTop = h;
      const rise = h * 0.5, eave = 0.45;
      const halfSpan = hd + eave;
      const slopeLen = Math.sqrt(halfSpan * halfSpan + rise * rise);
      const pitch = Math.atan2(rise, halfSpan);

      // roof into its own bin, because it lifts off while you are inside
      for (const s of [-1, 1]) {
        rput(new T.BoxGeometry(w + eave * 2, 0.2, slopeLen),
             0, yTop + rise / 2, s * halfSpan / 2, s * pitch, 0, 0, roofC);
        const courses = roofKind === 'thatch' ? 3 : 2;
        for (let ci = 0; ci < courses; ci++) {
          const f = (ci + 1) / (courses + 1);
          const cz = s * halfSpan * f, cy = yTop + rise * (1 - f);
          rput(new T.BoxGeometry(w + eave * 2 - 0.06, 0.09, roofKind === 'thatch' ? 0.2 : 0.13),
               0, cy + 0.14, cz, s * pitch, 0, 0, roofD);
        }
      }
      rput(new T.BoxGeometry(w + eave * 2 + 0.15, 0.26, 0.32), 0, yTop + rise + 0.05, 0, 0, 0, 0, roofD);
      // gable ends close the roof void; they go with the roof so lifting it
      // off does not leave two triangles floating over an open room
      for (const s of [-1, 1]) {
        rput(gableGeo(d, rise, 0.2), s * (hw - 0.1), yTop, 0, 0, Math.PI / 2, 0, wallC);
      }
"""
sub(OLD_SHELL, NEW_SHELL, 'hut shell')

OLD_TIMBER = """      if (timbered) {
        // corner posts, mid rail, top plate, braces. This is the difference
        // between a cottage and an extruded rectangle.
        for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
          put(new T.BoxGeometry(0.3, h, 0.3), sx * (w / 2 - 0.06), 0.35 + h / 2, sz * (d / 2 - 0.06), 0, 0, 0, C_TIMBER);
        }
        const TD = 0.11;   // how far the timber stands proud of the plaster
        for (const sz of [-1, 1]) {
          const fz = sz * (d / 2 + TD / 2);
          put(new T.BoxGeometry(w, 0.24, TD), 0, 0.35 + h * 0.5, fz, 0, 0, 0, C_TIMBER);
          put(new T.BoxGeometry(w, 0.22, TD), 0, 0.35 + h - 0.12, fz, 0, 0, 0, C_TIMBER);
          // studs between the posts, and braces that actually run from the
          // corner post up to the top plate instead of floating mid-panel
          for (const sx of [-1, 1]) {
            put(new T.BoxGeometry(0.17, h * 0.46, TD), sx * w * 0.3, 0.35 + h * 0.26, fz, 0, 0, 0, C_TIMBER);
            put(new T.BoxGeometry(0.17, h * 0.58, TD),
                sx * (w / 2 - 0.52), 0.35 + h * 0.76, fz, 0, 0, sx * 0.58, C_TIMBER);
          }
        }
        for (const sx of [-1, 1]) {
          const fx = sx * (w / 2 + TD / 2);
          put(new T.BoxGeometry(TD, 0.24, d), fx, 0.35 + h * 0.5, 0, 0, 0, 0, C_TIMBER);
          put(new T.BoxGeometry(TD, 0.22, d), fx, 0.35 + h - 0.12, 0, 0, 0, 0, C_TIMBER);
          put(new T.BoxGeometry(TD, h * 0.46, 0.17), fx, 0.35 + h * 0.26, 0, 0, 0, 0, C_TIMBER);
        }
      } else {
        // stone buildings get quoins instead of framing. Real quoins alternate
        // which face they reach around, so they read as bonded masonry rather
        // than blocks glued to a corner.
        for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
          for (let q = 0; q < 5 && 0.5 + q * 0.56 < 0.35 + h - 0.2; q++) {
            const long = q % 2 === 0;
            put(new T.BoxGeometry(long ? 0.56 : 0.3, 0.28, long ? 0.3 : 0.56),
                sx * (w / 2 - (long ? 0.24 : 0.11)), 0.5 + q * 0.56, sz * (d / 2 - (long ? 0.11 : 0.24)),
                0, 0, 0, C_STONED);
          }
        }
      }
"""

NEW_TIMBER = """      if (timbered) {
        // corner posts, mid rail, top plate, braces. This is the difference
        // between a cottage and an extruded rectangle.
        for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
          xput(sx)(new T.BoxGeometry(0.34, h, 0.34), sx * (hw - 0.07), h / 2, sz * (hd - 0.07), 0, 0, 0, C_TIMBER);
        }
        const TD = 0.13;   // how far the timber stands proud of the plaster
        for (const sz of [-1, 1]) {
          const fz = sz * (hd + TD / 2), zp = sz < 0 ? sput.back : sput.front;
          zp(new T.BoxGeometry(w, 0.28, TD), 0, h * 0.52, fz, 0, 0, 0, C_TIMBER);
          zp(new T.BoxGeometry(w, 0.26, TD), 0, h - 0.14, fz, 0, 0, 0, C_TIMBER);
          // studs and braces, kept clear of the doorway on the front face
          for (const sx of [-1, 1]) {
            zp(new T.BoxGeometry(0.2, h * 0.44, TD), sx * (DWID / 2 + pw / 2), h * 0.26, fz, 0, 0, 0, C_TIMBER);
            zp(new T.BoxGeometry(0.2, h * 0.5, TD),
               sx * (hw - 0.62), h * 0.76, fz, 0, 0, sx * 0.58, C_TIMBER);
          }
        }
        for (const sx of [-1, 1]) {
          const fx = sx * (hw + TD / 2), xp = xput(sx);
          xp(new T.BoxGeometry(TD, 0.28, d), fx, h * 0.52, 0, 0, 0, 0, C_TIMBER);
          xp(new T.BoxGeometry(TD, 0.26, d), fx, h - 0.14, 0, 0, 0, 0, C_TIMBER);
          xp(new T.BoxGeometry(TD, h * 0.44, 0.2), fx, h * 0.26, 0, 0, 0, 0, C_TIMBER);
        }
      } else {
        // stone buildings get quoins instead of framing. Real quoins alternate
        // which face they reach around, so they read as bonded masonry rather
        // than blocks glued to a corner.
        for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
          for (let q = 0; q < 8 && 0.2 + q * 0.62 < h - 0.3; q++) {
            const long = q % 2 === 0;
            xput(sx)(new T.BoxGeometry(long ? 0.62 : 0.34, 0.32, long ? 0.34 : 0.62),
                sx * (hw - (long ? 0.27 : 0.12)), 0.2 + q * 0.62, sz * (hd - (long ? 0.12 : 0.27)),
                0, 0, 0, C_STONED);
          }
        }
      }
"""
sub(OLD_TIMBER, NEW_TIMBER, 'hut timbering')

OLD_DOOR = """      // door, set into a frame rather than pasted on the wall
      const dz = d / 2;
      put(new T.BoxGeometry(1.26, 2.16, 0.14), 0, 0.35 + 1.08, dz + 0.02, 0, 0, 0, C_WOODD);
      put(new T.BoxGeometry(0.98, 1.94, 0.1), 0, 0.35 + 0.97, dz + 0.07, 0, 0, 0, C_WOOD);
      for (const px of [-0.3, 0, 0.3]) {
        put(new T.BoxGeometry(0.05, 1.86, 0.04), px, 0.35 + 0.97, dz + 0.12, 0, 0, 0, C_WOODD);
      }
      put(new T.BoxGeometry(0.13, 0.13, 0.1), 0.36, 0.35 + 1.0, dz + 0.14, 0, 0, 0, C_STONED);
      put(new T.BoxGeometry(1.4, 0.18, 0.3), 0, 0.35 + 2.2, dz + 0.06, 0, 0, 0, C_STONED);
      put(new T.BoxGeometry(1.5, 0.12, 0.5), 0, 0.32, dz + 0.16, 0, 0, 0, C_STONED);
"""

NEW_DOOR = """      // The doorway is a hole, so what goes here is the surround: jambs, a
      // lintel and a threshold slab laid flush with the ground.
      const dz = hd;
      for (const sx of [-1, 1]) {
        sput.front(new T.BoxGeometry(0.42, DHGT + 0.5, 0.5), sx * (DWID / 2 + 0.21), (DHGT + 0.5) / 2, dz + 0.06, 0, 0, 0, C_STONED);
      }
      sput.front(new T.BoxGeometry(DWID + 1.3, 0.5, 0.62), 0, DHGT + 0.25, dz + 0.06, 0, 0, 0, C_STONED);
      sput.front(new T.BoxGeometry(DWID + 1.7, 0.34, 0.34), 0, DHGT + 0.67, dz + 0.1, 0, 0, 0, C_STONE);
      tput(new T.BoxGeometry(DWID + 1.4, 0.1, 1.5), 0, 0.05, dz + 0.7, 0, 0, 0, C_STONE);
"""
sub(OLD_DOOR, NEW_DOOR, 'hut doorway surround')

OLD_WIN = """      for (const s of [-1, 1]) winAt(s * (w / 4 + 0.26), 0.35 + h * 0.62, dz + 0.04, 0);
      winAt(-(w / 2 + 0.04), 0.35 + h * 0.62, 0, Math.PI / 2);
      if (w >= 6) winAt(w / 2 + 0.04, 0.35 + h * 0.62, 0, -Math.PI / 2);

      // chimney, on the gable end, where a hearth would put it
      if (opts.chimney) {
        const cx = (w / 2 - 0.5) * (opts.chimney > 0 ? 1 : -1);
        put(new T.BoxGeometry(0.86, h + rise + 1.0, 0.86), cx, 0.35 + (h + rise + 1.0) / 2, 0, 0, 0, 0, C_STONE);
        put(new T.BoxGeometry(1.06, 0.24, 1.06), cx, 0.35 + h + rise + 1.02, 0, 0, 0, 0, C_STONED);
        put(new T.BoxGeometry(0.3, 0.2, 0.3), cx, 0.35 + h + rise + 1.2, 0, 0, 0, 0, new T.Color(0x241f1a));
      }

      const body = new T.Mesh(this.mergeGeos(P), townMat);
      body.castShadow = true; body.receiveShadow = true; g.add(body);
      for (const [px, py, pz, ry] of wins) {
        const gl = new T.Mesh(new T.BoxGeometry(0.72, 0.72, 0.05), glassMat);
        gl.position.set(px, py, pz); gl.rotation.y = ry; g.add(gl);
      }

      g.position.set(x, this.groundY(x, z), z); g.rotation.y = rot; S.add(g);
      this.colliders.push({ x, z, r: Math.max(w, d) * 0.62 });
      return g;
    };"""

NEW_WIN = """      const wy = h * 0.6;
      for (const s of [-1, 1]) winAt(s * (DWID / 2 + pw / 2), wy, dz + 0.04, 0, 'front');
      for (const s of [-1, 1]) winAt(s * (hw + 0.04), wy, d * 0.2, s * Math.PI / 2, s < 0 ? 'left' : 'right');
      sput.back(new T.BoxGeometry(0.98, 0.98, 0.16), 0, wy, -(hd + 0.02), 0, 0, 0, C_WOODD);

      // chimney, on the gable end, where a hearth would put it
      const chimSide = opts.chimney ? (opts.chimney > 0 ? 1 : -1) : 0;
      if (chimSide) {
        const cx = (hw - 0.6) * chimSide;
        tput(new T.BoxGeometry(1.0, h + rise + 1.2, 1.0), cx, (h + rise + 1.2) / 2, 0, 0, 0, 0, C_STONE);
        tput(new T.BoxGeometry(1.24, 0.28, 1.24), cx, h + rise + 1.22, 0, 0, 0, 0, C_STONED);
        tput(new T.BoxGeometry(0.34, 0.24, 0.34), cx, h + rise + 1.44, 0, 0, 0, 0, new T.Color(0x241f1a));
      }

      // ------------------------------------------------------- the interior
      // Somewhere worth walking into. Everything sits on the ground plane the
      // player actually walks on, so nothing here can be stood on or clipped
      // into: no raised dais, no step.
      const iw = w - TW * 2, id = d - TW * 2;
      const hs = chimSide || 1;
      iput(new T.BoxGeometry(iw, 0.16, id), 0, 0.08, 0, 0, 0, 0, C_STONED);
      iput(new T.BoxGeometry(iw * 0.5, 0.04, id * 0.42), -hs * iw * 0.14, 0.18, 0, 0, 0, 0, new T.Color(0x6b3f34));
      // hearth on the chimney gable
      const fx0 = hs * (hw - 0.95);
      iput(new T.BoxGeometry(1.5, 0.34, 2.6), fx0, 0.17, 0, 0, 0, 0, C_STONE);
      for (const sz of [-1, 1]) iput(new T.BoxGeometry(1.3, 1.5, 0.34), fx0, 0.75, sz * 1.13, 0, 0, 0, C_STONED);
      iput(new T.BoxGeometry(1.5, 0.32, 2.9), fx0, 1.66, 0, 0, 0, 0, C_STONED);
      for (let lg = 0; lg < 5; lg++) {
        iput(new T.CylinderGeometry(0.1, 0.1, 1.1, 5), fx0 - hs * 0.1, 0.26 + (lg % 2) * 0.18, -0.4 + lg * 0.2, 0, 0, Math.PI / 2, C_WOODD);
      }
      // table, benches, bed, chest, shelf
      const tx = -hs * iw * 0.16;
      iput(new T.BoxGeometry(2.2, 0.16, 1.1), tx, 0.98, id * 0.14, 0, 0, 0, C_WOOD);
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
        iput(new T.BoxGeometry(0.16, 0.9, 0.16), tx + sx * 0.95, 0.45, id * 0.14 + sz * 0.42, 0, 0, 0, C_WOODD);
      }
      for (const sz of [-1, 1]) {
        iput(new T.BoxGeometry(2.0, 0.12, 0.36), tx, 0.55, id * 0.14 + sz * 0.95, 0, 0, 0, C_WOOD);
        for (const sx of [-1, 1]) iput(new T.BoxGeometry(0.14, 0.5, 0.14), tx + sx * 0.8, 0.27, id * 0.14 + sz * 0.95, 0, 0, 0, C_WOODD);
      }
      iput(new T.BoxGeometry(1.3, 0.42, 2.1), -hs * (hw - 1.0), 0.29, -id * 0.24, 0, 0, 0, C_WOODD);
      iput(new T.BoxGeometry(1.24, 0.3, 2.0), -hs * (hw - 1.0), 0.63, -id * 0.24, 0, 0, 0, C_THATCH);
      iput(new T.BoxGeometry(1.1, 0.26, 0.5), -hs * (hw - 1.0), 0.78, -id * 0.24 - 0.8, 0, 0, 0, new T.Color(0xd8cfc0));
      iput(new T.BoxGeometry(1.0, 0.7, 0.66), tx - 0.2, 0.35, -id * 0.36, 0, 0, 0, C_WOOD);
      iput(new T.BoxGeometry(1.06, 0.16, 0.72), tx - 0.2, 0.76, -id * 0.36, 0, 0, 0, C_TIMBER);
      iput(new T.BoxGeometry(0.3, 0.05, id * 0.5), -hs * (hw - TW - 0.2), 1.9, id * 0.12, 0, 0, 0, C_WOOD);
      for (let pI = 0; pI < 3; pI++) {
        iput(new T.CylinderGeometry(0.14, 0.12, 0.3, 7), -hs * (hw - TW - 0.2), 2.07, id * 0.12 - 0.7 + pI * 0.7, 0, 0, 0, C_STONED);
      }

      const mkSide = (bin) => {
        const grp = new T.Group();
        const m = new T.Mesh(this.mergeGeos(bin), townMat);
        m.castShadow = true; m.receiveShadow = true;
        grp.add(m); g.add(grp); return grp;
      };
      const sides = { back: mkSide(SB), left: mkSide(SL), right: mkSide(SR), front: mkSide(SF) };
      const trimM = new T.Mesh(this.mergeGeos(TRIM), townMat);
      trimM.castShadow = true; trimM.receiveShadow = true; g.add(trimM);
      const roof = new T.Mesh(this.mergeGeos(RF), townMat);
      roof.castShadow = true; roof.receiveShadow = true; g.add(roof);
      const room = new T.Mesh(this.mergeGeos(IN), townMat);
      room.receiveShadow = true; g.add(room);
      // glass rides with its own wall, so hiding a wall takes its windows too
      for (const [px, py, pz, ry, key] of wins) {
        const gl = new T.Mesh(new T.BoxGeometry(0.86, 0.86, 0.06), glassMat);
        gl.position.set(px, py, pz); gl.rotation.y = ry; sides[key].add(gl);
      }

      // the fire, and the only light the room needs. It is switched off until
      // you are inside, and an invisible light costs the renderer nothing.
      const fire = new T.Mesh(new T.BoxGeometry(1.0, 0.4, 1.5), new T.MeshStandardMaterial({
        color: 0xff9a3c, emissive: 0xff7a1e, emissiveIntensity: 2.1, roughness: 0.6, flatShading: true }));
      fire.position.set(fx0 - hs * 0.15, 0.42, 0); g.add(fire);
      const fireLight = new T.PointLight(0xffb066, 3.4, 16, 2);
      fireLight.position.set(fx0 - hs * 0.4, 1.5, 0); fireLight.visible = false; g.add(fireLight);

      // the door: a leaf on a hinge, not a slab of colour painted on the wall
      const doorG = new T.Group();
      doorG.position.set(DWID / 2 - 0.05, 0, hd - TW / 2);
      {
        const L = [];
        const lput = binPut(L);
        const lw = DWID - 0.14;
        lput(new T.BoxGeometry(lw, DHGT - 0.12, 0.14), -lw / 2, (DHGT - 0.12) / 2, 0, 0, 0, 0, C_WOOD);
        for (let k = 0; k < 4; k++) lput(new T.BoxGeometry(0.08, DHGT - 0.34, 0.05), -0.32 - k * 0.6, (DHGT - 0.12) / 2, 0.09, 0, 0, 0, C_WOODD);
        for (const yb of [DHGT * 0.24, DHGT * 0.74]) lput(new T.BoxGeometry(lw - 0.14, 0.16, 0.06), -lw / 2, yb, 0.1, 0, 0, 0, C_WOODD);
        lput(new T.BoxGeometry(0.16, 0.16, 0.14), -(lw - 0.26), DHGT * 0.46, 0.13, 0, 0, 0, C_STONED);
        const dm = new T.Mesh(this.mergeGeos(L), townMat);
        dm.castShadow = true; doorG.add(dm);
      }
      g.add(doorG);

      g.position.set(x, this.groundY(x, z), z); g.rotation.y = rot; S.add(g);

      // Wall colliders, with the doorway left open. Yaws are quarter turns, so
      // these stay axis aligned: an axis-aligned box is the only shape the
      // collision resolver understands, and the resolver pads by 0.42, which
      // leaves 1.76m of clear doorway out of the 2.6m opening.
      const c0 = Math.round(Math.cos(rot)), s0 = Math.round(Math.sin(rot));
      const wallCol = (lx, lz, ehx, ehz) => {
        this.colliders.push({
          x: x + lx * c0 + lz * s0,
          z: z - lx * s0 + lz * c0,
          hw: Math.abs(c0) * ehx + Math.abs(s0) * ehz,
          hd: Math.abs(s0) * ehx + Math.abs(c0) * ehz
        });
      };
      wallCol(0, -(hd - TW / 2), hw, TW / 2);
      for (const sx of [-1, 1]) wallCol(sx * (hw - TW / 2), 0, TW / 2, hd);
      for (const sx of [-1, 1]) wallCol(sx * (DWID / 2 + pw / 2), hd - TW / 2, pw / 2, TW / 2);

      this._huts.push({ x: x, z: z, c: c0, s: s0, hw: hw, hd: hd,
                        roof: roof, sides: sides, door: doorG, light: fireLight, _in: null });
      return g;
    };"""
sub("""      const winAt = (px, py, pz, ry) => {""",
    """      const winAt = (px, py, pz, ry, key) => {
        const put = sput[key];   // a window belongs to the wall it is cut into""",
    'winAt takes a wall')
sub("""        wins.push([px, py, pz, ry]);""",
    """        wins.push([px, py, pz, ry, key]);""",
    'winAt records its wall')

sub(OLD_WIN, NEW_WIN, 'hut windows, chimney, interior, assembly')


# ====================================================== 2. where the plots go
OLD_PLOTS = """    const PLOTS = [
      [-22, 6, 6, 5, 3.0, 0.35, 'plaster', 'thatch', { chimney: 1 }],
      [-30, 21, 5.5, 5, 2.8, -0.4, 'plaster', 'thatch', {}],
      [-8, -13, 5, 4.5, 2.7, 1.15, 'plaster', 'slate', { chimney: -1 }],
      [30, 11, 7, 6, 3.4, -1.25, 'stone', 'slate', { chimney: 1 }],     // trader's hall
      [26, 29, 8, 6, 3.6, Math.PI, 'stone', 'slate', { chimney: -1 }],  // the inn
      [-35, 30, 5, 4.5, 2.6, 0.8, 'plaster', 'thatch', {}]
    ];"""

NEW_PLOTS = """    // Positions come from harness/probe-town2.js, which reads the game's own
    // road-clearance field on a 24-bearing sweep out to 54m. Two houses ended
    // up front to front with their fences meeting in a dead end, so every plot
    // now sits on a ring FACING THE SQUARE: no two fronts look at each other,
    // and the closest pair of centres is 24m apart.
    //
    // Yaw is a quarter turn in every case. That is not laziness, it is what
    // lets each wall carry an axis-aligned box collider, which is the only kind
    // the collision resolver understands. Facing still varies: these four look
    // west, south, south, east, north and west.
    const HP = Math.PI / 2;
    const PLOTS = [
      [43.2, 15.7, 9, 7.5, 4.2, -HP, 'plaster', 'thatch', { chimney: 1 }],
      [24.6, 31.5, 8.5, 7, 4.0, Math.PI, 'plaster', 'thatch', {}],
      [4.0, 45.8, 8, 7, 4.0, Math.PI, 'plaster', 'slate', { chimney: -1 }],
      [-34.6, 20.0, 11, 9, 4.8, HP, 'stone', 'slate', { chimney: 1 }],     // trader's hall
      [17.0, -29.4, 12, 9, 5.0, 0, 'stone', 'slate', { chimney: -1 }],     // the inn
      [44.4, -11.9, 8, 7, 3.9, -HP, 'plaster', 'thatch', {}]
    ];"""
sub(OLD_PLOTS, NEW_PLOTS, 'plot table')

sub("""      const hw = pl.w / 2 + 4.6, hd = pl.d / 2 + 4.2;""",
    """      const hw = pl.w / 2 + 5.4, hd = pl.d / 2 + 5.0;""",
    'yard extents')

# the front beds sat straight in front of the door, which now has to be walked
# through. Push them off to one side and mirror them.
OLD_BEDS = """      const fx = gateSide === 'x' ? gateSign * (hw - 2.6) : 2.4;
      const fz = gateSide === 'x' ? 2.4 : gateSign * (hd - 2.6);
      for (let b = 0; b < 2; b++) {
        const bx = fx, bz = fz + (b - 0.5) * 1.5;
        fput(new T.BoxGeometry(2.6, 0.22, 1.0), bx, 0.11, bz, 0, 0, 0, C_WOODD);
        for (let r3 = 0; r3 < 4; r3++) {
          fput(new T.BoxGeometry(0.24, 0.3, 0.24), bx - 0.9 + r3 * 0.6, 0.3, bz, 0, 0, 0, new T.Color(0x4e7a38));
        }
      }"""

NEW_BEDS = """      // Beds off to the SIDE of the path, not across it: the door is a way in
      // now, and a vegetable bed in front of it is a wall you cannot see.
      const fx = gateSide === 'x' ? gateSign * (hw - 3.0) : 4.2;
      const fz = gateSide === 'x' ? 4.2 : gateSign * (hd - 3.0);
      for (let b = 0; b < 2; b++) {
        const bx = fx, bz = fz + (b - 0.5) * 1.6;
        fput(new T.BoxGeometry(2.8, 0.24, 1.1), bx, 0.12, bz, 0, 0, 0, C_WOODD);
        for (let r3 = 0; r3 < 4; r3++) {
          fput(new T.BoxGeometry(0.26, 0.32, 0.26), bx - 0.95 + r3 * 0.63, 0.32, bz, 0, 0, 0, new T.Color(0x4e7a38));
        }
      }"""
sub(OLD_BEDS, NEW_BEDS, 'front beds')


# ================================== 3. paths, and a walled market on the square
OLD_PATHS = """    // the ring round the square
    const RING = 7.5;
    for (let i = 0; i < 12; i++) {
      const a1 = i * Math.PI * 2 / 12, a2 = (i + 1) * Math.PI * 2 / 12;
      layPath(TX + Math.cos(a1) * RING, TZ + Math.sin(a1) * RING,
              TX + Math.cos(a2) * RING, TZ + Math.sin(a2) * RING, false);
    }
    // and a spur out to each gate
    for (const pl of plotAt) {
      const a = Math.atan2(pl.z - TZ, pl.x - TX);
      layPath(TX + Math.cos(a) * RING, TZ + Math.sin(a) * RING,
              pl.x - Math.cos(a) * (Math.max(pl.w, pl.d) / 2 + 4.4),
              pl.z - Math.sin(a) * (Math.max(pl.w, pl.d) / 2 + 4.4), true);
    }
"""

NEW_PATHS = """    // the ring round the well, inside the market precinct
    const RING = 8.5;
    for (let i = 0; i < 12; i++) {
      const a1 = i * Math.PI * 2 / 12, a2 = (i + 1) * Math.PI * 2 / 12;
      layPath(TX + Math.cos(a1) * RING, TZ + Math.sin(a1) * RING,
              TX + Math.cos(a2) * RING, TZ + Math.sin(a2) * RING, false);
    }
    // The market precinct: half extents, and a gate in the middle of each side.
    // Every path out of the square goes through one of the four gates, so the
    // wall reads as an enclosure rather than a fence with holes in it.
    const MW = 15, MD = 13, MGATE = 3.2;
    const MGATES = [[0, MD], [0, -MD], [MW, 0], [-MW, 0]];
    for (const [gx, gz] of MGATES) {
      const a = Math.atan2(gz, gx);
      layPath(TX + Math.cos(a) * RING, TZ + Math.sin(a) * RING, TX + gx, TZ + gz, false);
    }
    // and a spur from the nearest gate out to each garden gate
    for (const pl of plotAt) {
      let best = MGATES[0], bd = 1e9;
      for (const G of MGATES) {
        const dd = Math.hypot(pl.x - (TX + G[0]), pl.z - (TZ + G[1]));
        if (dd < bd) { bd = dd; best = G; }
      }
      const a = Math.atan2(pl.z - TZ, pl.x - TX);
      layPath(TX + best[0], TZ + best[1],
              pl.x - Math.cos(a) * (Math.max(pl.w, pl.d) / 2 + 5.2),
              pl.z - Math.sin(a) * (Math.max(pl.w, pl.d) / 2 + 5.2), true);
    }
"""
sub(OLD_PATHS, NEW_PATHS, 'paths')

sub("""    wellG.position.set(TX, this.groundY(TX, TZ), TZ); S.add(wellG);
    this.colliders.push({ x: TX, z: TZ, r: 1.5 });

    // --- market stalls, lamps, fences
    for (let i = 0; i < 3; i++) {
      const sx = TX - 4 + i * 4.4, sz = TZ - 3.5;""",
    """    // scaled up with everything else: the old well came up to the player's chest
    wellG.scale.setScalar(1.3);
    wellG.position.set(TX, this.groundY(TX, TZ), TZ); S.add(wellG);
    this.colliders.push({ x: TX, z: TZ, r: 2.0 });

    // --- the market precinct wall.
    //
    // Kevin: the market and the well are way too close to the houses and should
    // get their own area, fenced off and separate. The stalls used to stand
    // four metres from somebody's front door. This walls the square: a stone
    // kerb with timber palings on it, a gate on each side, and the nearest
    // house 34m away.
    {
      const MP = [];
      const mput = (geo, px, py, pz, rx, ry, rz, col) => {
        MP.push({
          geo: nonIdx(geo),
          m: new T.Matrix4().compose(new T.Vector3(px, py, pz),
            new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
            new T.Vector3(1, 1, 1)),
          color: col
        });
      };
      const runWall = (ax, az, bx, bz) => {
        const L = Math.hypot(bx - ax, bz - az), ang = Math.atan2(bx - ax, bz - az);
        const n = Math.max(1, Math.round(L / 2.2));
        for (let i = 0; i < n; i++) {
          const t = (i + 0.5) / n;
          const px = ax + (bx - ax) * t, pz = az + (bz - az) * t;
          const gy = this.groundY(TX + px, TZ + pz) - this.groundY(TX, TZ);
          mput(new T.BoxGeometry(0.7, 1.0, L / n + 0.04), px, gy - 0.1, pz, 0, ang, 0, C_STONE);
          mput(new T.BoxGeometry(0.86, 0.2, L / n + 0.04), px, gy + 0.5, pz, 0, ang, 0, C_STONED);
          for (let k = 0; k < 3; k++) {
            const f = (k + 0.5) / 3 - 0.5;
            mput(new T.BoxGeometry(0.16, 1.0, 0.16),
                 px + Math.cos(ang) * (L / n) * f, gy + 1.05, pz - Math.sin(ang) * (L / n) * f, 0, ang, 0, C_WOODD);
          }
          mput(new T.BoxGeometry(0.1, 0.12, L / n + 0.04), px, gy + 1.42, pz, 0, ang, 0, C_WOOD);
        }
      };
      for (const sz of [-1, 1]) {
        runWall(-MW, sz * MD, -MGATE, sz * MD);
        runWall(MGATE, sz * MD, MW, sz * MD);
      }
      for (const sx of [-1, 1]) {
        runWall(sx * MW, -MD, sx * MW, -MGATE);
        runWall(sx * MW, MGATE, sx * MW, MD);
      }
      // gate piers, tall enough to read as a way in
      for (const [gx, gz] of MGATES) {
        const ux = gx === 0 ? 1 : 0, uz = gx === 0 ? 0 : 1;
        for (const s of [-1, 1]) {
          mput(new T.BoxGeometry(0.6, 3.0, 0.6), gx + ux * s * MGATE, 1.2, gz + uz * s * MGATE, 0, 0, 0, C_STONE);
          mput(new T.BoxGeometry(0.8, 0.26, 0.8), gx + ux * s * MGATE, 2.82, gz + uz * s * MGATE, 0, 0, 0, C_STONED);
        }
      }
      // a notice board and a horse trough, because a market square has business in it
      mput(new T.BoxGeometry(0.24, 2.6, 0.24), -MW + 3.2, 1.1, -MD + 3.0, 0, 0, 0, C_WOODD);
      mput(new T.BoxGeometry(2.4, 1.5, 0.16), -MW + 3.2, 2.1, -MD + 3.0, 0, 0.4, 0, C_WOOD);
      mput(new T.BoxGeometry(2.5, 0.18, 0.3), -MW + 3.2, 2.92, -MD + 3.0, 0, 0.4, 0, C_WOODD);
      for (let nI = 0; nI < 3; nI++) {
        mput(new T.BoxGeometry(0.5, 0.62, 0.03), -MW + 2.5 + nI * 0.72, 2.1, -MD + 2.92, 0, 0.4, 0, new T.Color(0xd8cfc0));
      }
      mput(new T.BoxGeometry(3.0, 0.8, 1.2), MW - 3.4, 0.4, MD - 3.2, 0, 0, 0, C_WOODD);
      mput(new T.BoxGeometry(2.7, 0.12, 0.95), MW - 3.4, 0.75, MD - 3.2, 0, 0, 0, new T.Color(0x2e4a52));
      for (let cI = 0; cI < 4; cI++) {
        mput(new T.BoxGeometry(0.8, 0.8, 0.8), MW - 6.5 + (cI % 2) * 0.95, 0.4 + Math.floor(cI / 2) * 0.82, MD - 4.2, 0, cI * 0.3, 0, C_WOOD);
      }
      const mm = new T.Mesh(this.mergeGeos(MP), townMat);
      mm.castShadow = true; mm.receiveShadow = true;
      const mg = new T.Group(); mg.add(mm);
      mg.position.set(TX, this.groundY(TX, TZ), TZ); S.add(mg);
      // The wall is solid apart from the four gates. Boxes, so quarter-turn
      // aligned, which the four sides of a rectangle are by definition.
      for (const sz of [-1, 1]) for (const s of [-1, 1]) {
        const x0 = s * MGATE, x1 = s * MW;
        this.colliders.push({ x: TX + (x0 + x1) / 2, z: TZ + sz * MD, hw: Math.abs(x1 - x0) / 2, hd: 0.45 });
      }
      for (const sx of [-1, 1]) for (const s of [-1, 1]) {
        const z0 = s * MGATE, z1 = s * MD;
        this.colliders.push({ x: TX + sx * MW, z: TZ + (z0 + z1) / 2, hw: 0.45, hd: Math.abs(z1 - z0) / 2 });
      }
      this.colliders.push({ x: TX - MW + 3.2, z: TZ - MD + 3.0, r: 0.6 });
      this.colliders.push({ x: TX + MW - 3.4, z: TZ + MD - 3.2, r: 1.6 });
    }

    // --- market stalls, inside the precinct, lamps, fences
    for (let i = 0; i < 3; i++) {
      const sx = TX - 7.5 + i * 7.5, sz = TZ - MD + 4.6;""",
    'well scale and market precinct')

sub("""      st.position.set(sx, this.groundY(sx, sz), sz); S.add(st);
      this.colliders.push({ x: sx, z: sz, r: 1.3 });""",
    """      st.scale.setScalar(1.4);
      st.position.set(sx, this.groundY(sx, sz), sz); S.add(st);
      this.colliders.push({ x: sx, z: sz, r: 1.9 });""",
    'stall scale')

sub("""      const lp = this.clearOfRoad(TX + Math.cos(a) * 17, TZ + Math.sin(a) * 17);""",
    """      const lp = this.clearOfRoad(TX + Math.cos(a) * 21, TZ + Math.sin(a) * 21);""",
    'lamp ring')


# ============================================================== 4. the keep
OLD_BARROW_START = src.index("    // --- the barrow: the Hollow King's tomb.")
OLD_BARROW_END = src.index("    // --- pines: northern woodland, choppable like any other tree")
OLD_BARROW = src[OLD_BARROW_START:OLD_BARROW_END]

NEW_KEEP = """    // --- THE HOLLOW KEEP.
    //
    // This was a green dome with a doorway cut into it, and Kevin's verdict was
    // fair: it did not sit on the ground, he walked through it, he could not see
    // the inside once he was in, and it looked like a semicircle. Three real
    // faults under that, all of them mine:
    //
    //  - A SphereGeometry has outward faces only. Step through the door and the
    //    whole hill vanishes, because you are looking at the backs of its
    //    triangles and the renderer culls those. There was no interior to see.
    //  - The collider ring left a 42 degree gap for the doorway. At radius 14
    //    that is a TEN METRE hole. "Walking through the wall" was walking
    //    through a gap I put there.
    //  - One dome at one height on ground with 2.4m of relief across it, so the
    //    rim floated on the high side.
    //
    // It is a keep now. Curtain walls built as segments that each sit at their
    // OWN ground height, so the battlements run level and no course hangs in
    // the air. Corner towers, a gatehouse with an arch and a raised portcullis,
    // and a courtyard open to the sky. Open-topped is deliberate: daylight
    // reaches the inside, you can see in on the approach, and there is no roof
    // to hide when you walk under it.
    const KX = -84, KZ = 246;
    const KH = 20;                  // half footprint, wall centreline
    const KWT = 2.4;                // curtain wall thickness
    const KWH = 8.4;                // wall height above the highest ground
    const KGATE = 7.0;              // clear width of the gateway
    this.barrowPos = new T.Vector3(KX, 0, KZ);
    let kHi = -1e9;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) {
      kHi = Math.max(kHi, this.groundY(KX + a * KH, KZ + b * KH));
    }
    const kTop = kHi + KWH;
    {
      const K = [];
      const kput = (geo, px, py, pz, rx, ry, rz, col) => {
        K.push({
          geo: nonIdx(geo),
          m: new T.Matrix4().compose(new T.Vector3(px, py, pz),
            new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
            new T.Vector3(1, 1, 1)),
          color: col
        });
      };
      // A curtain wall in segments. Each one is sunk to its own local ground and
      // run up to the same crest, which is how a real wall handles a slope and
      // the reason the dome looked like it was hovering.
      const curtain = (ax, az, bx, bz) => {
        const L = Math.hypot(bx - ax, bz - az);
        const n = Math.max(1, Math.round(L / 4));
        const ang = Math.atan2(bx - ax, bz - az);
        for (let i = 0; i < n; i++) {
          const t = (i + 0.5) / n;
          const px = ax + (bx - ax) * t, pz = az + (bz - az) * t;
          const bot = this.groundY(px, pz) - 3.0, hgt = kTop - bot;
          kput(new T.BoxGeometry(KWT, hgt, L / n + 0.06), px, bot + hgt / 2, pz, 0, ang, 0, C_STONE);
          // A flat slab reads as a fence. Pilaster buttresses on the outer
          // face, a corbelled wall-walk on the inner, arrow loops through it,
          // and a string course tying the run together.
          const ox = Math.cos(ang), oz = -Math.sin(ang);
          const outS = (ox * (px - KX) + oz * (pz - KZ)) >= 0 ? 1 : -1;
          const btx = px + ox * outS * (KWT / 2 + 0.4), btz = pz + oz * outS * (KWT / 2 + 0.4);
          kput(new T.BoxGeometry(1.0, hgt - 1.6, 1.7), btx, bot + (hgt - 1.6) / 2, btz, 0, ang, 0, C_STONED);
          kput(new T.BoxGeometry(1.3, 0.5, 2.1), btx, kTop - 1.9, btz, 0, ang, 0, C_STONE);
          kput(new T.BoxGeometry(1.5, 0.45, L / n + 0.06),
               px - ox * outS * (KWT / 2 + 0.65), kTop - 2.1, pz - oz * outS * (KWT / 2 + 0.65), 0, ang, 0, C_STONED);
          for (const lf of [-0.28, 0.28]) {
            kput(new T.BoxGeometry(KWT + 0.6, 1.8, 0.4),
                 px + Math.sin(ang) * (L / n) * lf, kTop - 4.6, pz + Math.cos(ang) * (L / n) * lf, 0, ang, 0, new T.Color(0x14160f));
          }
          // string course, then merlons with real gaps between them
          kput(new T.BoxGeometry(KWT + 0.5, 0.34, L / n + 0.06), px, kTop - 1.5, pz, 0, ang, 0, C_STONED);
          const mc = Math.max(1, Math.round((L / n) / 1.7));
          for (let mI = 0; mI < mc; mI++) {
            const f = (mI + 0.5) / mc - 0.5;
            kput(new T.BoxGeometry(KWT + 0.34, 1.3, 1.0),
                 px + Math.sin(ang) * (L / n) * f, kTop + 0.65, pz + Math.cos(ang) * (L / n) * f, 0, ang, 0, C_STONED);
          }
        }
      };
      curtain(KX - KH, KZ - KH, KX + KH, KZ - KH);
      curtain(KX - KH, KZ + KH, KX - KH, KZ - KH);
      curtain(KX + KH, KZ + KH, KX + KH, KZ - KH);
      // the south wall is the front, split either side of the gateway
      curtain(KX - KH, KZ + KH, KX - KGATE / 2, KZ + KH);
      curtain(KX + KGATE / 2, KZ + KH, KX + KH, KZ + KH);

      // corner towers
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
        const tx = KX + sx * KH, tz = KZ + sz * KH;
        const bot = this.groundY(tx, tz) - 3.4, tTop = kTop + 3.6;
        kput(new T.CylinderGeometry(4.2, 4.8, tTop - bot, 12), tx, (tTop + bot) / 2, tz, 0, 0, 0, C_STONE);
        kput(new T.CylinderGeometry(5.0, 4.4, 0.8, 12), tx, tTop + 0.4, tz, 0, 0, 0, C_STONED);
        for (let mI = 0; mI < 10; mI++) {
          const a = mI * Math.PI * 2 / 10;
          kput(new T.BoxGeometry(1.2, 1.3, 1.0), tx + Math.cos(a) * 4.5, tTop + 1.45, tz + Math.sin(a) * 4.5, 0, -a, 0, C_STONED);
        }
        // arrow slits, facing out
        for (let sI = 0; sI < 3; sI++) {
          const a = Math.atan2(sz, sx) + (sI - 1) * 0.75;
          kput(new T.BoxGeometry(0.4, 1.9, 0.4), tx + Math.cos(a) * 4.3, this.groundY(tx, tz) + 5.0 + sI * 0.7, tz + Math.sin(a) * 4.3, 0, -a, 0, new T.Color(0x14160f));
        }
      }

      // the gatehouse
      const gz = KZ + KH, gy0 = this.groundY(KX, gz), gTop = kTop + 3.2;
      const AH = 8.0;                       // clear height under the arch
      for (const s of [-1, 1]) {
        const gx = KX + s * (KGATE / 2 + 2.8);
        const bot = this.groundY(gx, gz) - 3.0;
        kput(new T.BoxGeometry(5.6, gTop - bot, 6.0), gx, (gTop + bot) / 2, gz, 0, 0, 0, C_STONE);
        kput(new T.BoxGeometry(6.3, 0.6, 6.7), gx, gTop - 0.3, gz, 0, 0, 0, C_STONED);
        kput(new T.BoxGeometry(1.3, gTop - bot - 2.4, 1.3), gx, bot + (gTop - bot) / 2 - 1.2, gz + 3.2, 0, 0, 0, C_STONED);
        for (const sz2 of [-1, 1]) for (let mI = 0; mI < 3; mI++) {
          kput(new T.BoxGeometry(1.3, 1.3, 1.3), gx - 1.7 + mI * 1.7, gTop + 0.65, gz + sz2 * 2.1, 0, 0, 0, C_STONED);
        }
        kput(new T.BoxGeometry(0.45, 2.2, 0.45), gx, gy0 + 5.4, gz + 3.05, 0, 0, 0, new T.Color(0x14160f));
      }
      kput(new T.BoxGeometry(KGATE + 5.6, gTop - (gy0 + AH), 6.0), KX, (gTop + gy0 + AH) / 2, gz, 0, 0, 0, C_STONE);
      for (let vI = 0; vI <= 9; vI++) {
        const a = Math.PI * (vI / 9);
        kput(new T.BoxGeometry(1.2, 1.0, 6.3),
             KX + Math.cos(a) * (KGATE / 2 + 0.5), gy0 + AH - 1.3 + Math.sin(a) * 2.0, gz, 0, 0, Math.PI / 2 - a, C_STONED);
      }
      // portcullis, raised into the arch
      for (let pI = 0; pI <= 7; pI++) {
        kput(new T.BoxGeometry(0.18, 2.4, 0.18), KX - KGATE / 2 + 0.45 + pI * ((KGATE - 0.9) / 7), gy0 + AH - 1.1, gz + 1.6, 0, 0, 0, C_TIMBER);
      }
      kput(new T.BoxGeometry(KGATE - 0.3, 0.34, 0.34), KX, gy0 + AH - 2.25, gz + 1.6, 0, 0, 0, C_TIMBER);
      // a ramp of worn flags up to the gateway, laid flat on the ground
      for (let fI = 0; fI < 5; fI++) {
        const fz2 = gz + 1.5 + fI * 2.4;
        kput(new T.CircleGeometry(2.6, 7), KX, this.groundY(KX, fz2) + 0.07, fz2, -Math.PI / 2, 0, 0, C_STONED);
      }

      // The courtyard floor is laid as flat flagstones ON the terrain, not a
      // raised slab. The player's height comes from the ground, so a raised
      // floor is a floor you walk through.
      for (let ix = -4; ix <= 4; ix++) for (let iz = -4; iz <= 4; iz++) {
        const fx2 = KX + ix * 4.2, fz2 = KZ + iz * 4.2;
        if (Math.abs(ix) === 4 && Math.abs(iz) === 4) continue;
        kput(new T.CircleGeometry(2.5, 6), fx2, this.groundY(fx2, fz2) + 0.06, fz2,
             -Math.PI / 2, (ix * 7 + iz * 13) % 6, 0, (ix + iz) % 2 ? C_STONE : C_STONED);
      }

      // the throne, against the back wall, so the King stands in front of it on
      // the ground rather than on top of something he cannot be pushed off
      const thZ = KZ - KH + 5.2, thY = this.groundY(KX, thZ);
      kput(new T.BoxGeometry(4.0, 0.5, 3.0), KX, thY + 0.25, thZ, 0, 0, 0, C_STONED);
      kput(new T.BoxGeometry(2.6, 0.55, 2.2), KX, thY + 0.78, thZ, 0, 0, 0, C_STONE);
      kput(new T.BoxGeometry(2.6, 4.4, 0.55), KX, thY + 2.8, thZ - 0.9, 0, 0, 0, C_STONE);
      for (const s of [-1, 1]) kput(new T.BoxGeometry(0.55, 1.5, 1.9), KX + s * 1.35, thY + 1.6, thZ, 0, 0, 0, C_STONED);
      for (let cI = 0; cI < 5; cI++) {
        kput(new T.BoxGeometry(0.4, 0.8 + (cI % 2) * 0.6, 0.55), KX - 1.0 + cI * 0.5, thY + 5.3, thZ - 0.9, 0, 0, 0, C_STONED);
      }
      // banners down the inner faces of the side walls
      for (const sx of [-1, 1]) for (let bI = 0; bI < 3; bI++) {
        const bz2 = KZ - 9 + bI * 9;
        kput(new T.BoxGeometry(0.12, 5.2, 2.2), KX + sx * (KH - KWT / 2 - 0.1), kTop - 3.6, bz2, 0, 0, 0, new T.Color(bI % 2 ? 0x243b2c : 0x3a2430));
        kput(new T.BoxGeometry(0.2, 0.3, 2.6), KX + sx * (KH - KWT / 2 - 0.1), kTop - 0.9, bz2, 0, 0, 0, C_TIMBER);
      }
      // fallen pillars and rubble: a keep with a dead king in it is not tidy
      for (let pI = 0; pI < 7; pI++) {
        const a = pI * 1.7, rr = 8 + (pI % 3) * 3.4;
        const px = KX + Math.cos(a) * rr, pz = KZ + Math.sin(a) * rr;
        if (Math.abs(pz - thZ) < 3.5 && Math.abs(px - KX) < 3.5) continue;
        const gy2 = this.groundY(px, pz);
        if (pI % 2) {
          kput(new T.CylinderGeometry(0.7, 0.78, 4.6, 8), px, gy2 + 0.7, pz, Math.PI / 2, a, 0, C_STONE);
        } else {
          kput(new T.CylinderGeometry(0.85, 0.95, 2.6, 8), px, gy2 + 1.3, pz, 0, 0, 0, C_STONE);
          kput(new T.BoxGeometry(2.0, 0.4, 2.0), px, gy2 + 2.75, pz, 0, a, 0, C_STONED);
        }
        for (let rI = 0; rI < 3; rI++) {
          kput(new T.DodecahedronGeometry(0.45 + (rI % 2) * 0.25, 0), px + Math.cos(a + rI) * 2.4, gy2 + 0.3, pz + Math.sin(a + rI) * 2.4, rI, a, 0, C_STONED);
        }
      }
      const km = new T.Mesh(this.mergeGeos(K), townMat);
      km.castShadow = true; km.receiveShadow = true;
      S.add(km);

      // braziers, so the courtyard reads at night. Two carry a real light.
      for (let bI = 0; bI < 4; bI++) {
        const bx2 = KX + (bI % 2 ? 1 : -1) * 6.0, bz2 = KZ + (bI < 2 ? -1 : 1) * 7.0;
        const bg = new T.Group();
        const bowl = new T.Mesh(new T.CylinderGeometry(0.95, 0.5, 0.8, 10), stoneD);
        bowl.position.y = 2.0; bowl.castShadow = true; bg.add(bowl);
        const stem = new T.Mesh(new T.CylinderGeometry(0.28, 0.42, 2.0, 8), stoneD);
        stem.position.y = 1.0; stem.castShadow = true; bg.add(stem);
        const coals = new T.Mesh(new T.IcosahedronGeometry(0.7, 0), new T.MeshStandardMaterial({
          color: 0x9fef7a, emissive: 0x6fe04a, emissiveIntensity: 2.2, roughness: 0.4, flatShading: true }));
        coals.position.y = 2.5; coals.scale.set(1, 0.6, 1); bg.add(coals);
        if (bI % 2 === 0) {
          const pl = new T.PointLight(0x8fef5a, 3.0, 30, 2);
          pl.position.y = 2.7; bg.add(pl); (this.decorLights = this.decorLights || []).push(pl);
        }
        bg.position.set(bx2, this.groundY(bx2, bz2), bz2); S.add(bg);
        this.colliders.push({ x: bx2, z: bz2, r: 1.0 });
      }

      // Solid walls. The gateway is the only way in, and after the resolver's
      // 0.42 padding it is still 6.1m of clear opening.
      this.colliders.push({ x: KX, z: KZ - KH, hw: KH + 2.2, hd: KWT / 2 + 0.5 });
      for (const sx of [-1, 1]) this.colliders.push({ x: KX + sx * KH, z: KZ, hw: KWT / 2 + 0.5, hd: KH + 2.2 });
      for (const s of [-1, 1]) {
        const x0 = s * (KGATE / 2), x1 = s * (KH + 2.2);
        this.colliders.push({ x: KX + (x0 + x1) / 2, z: KZ + KH, hw: Math.abs(x1 - x0) / 2, hd: KWT / 2 + 0.5 });
      }
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
        this.colliders.push({ x: KX + sx * KH, z: KZ + sz * KH, r: 4.5 });
      }
      this.colliders.push({ x: KX, z: thZ, r: 2.4 });
    }

    // The standing stones stay, pushed out clear of the walls: they were here
    // before the keep was, which is the point of them.
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2, sx = KX + Math.cos(a) * (KH + 14), sz = KZ + Math.sin(a) * (KH + 14);
      const menhir = new T.Mesh(new T.BoxGeometry(1.2 + rnd() * 0.6, 4.2 + rnd() * 2.2, 0.9), stoneD);
      menhir.position.set(sx, this.groundY(sx, sz) + 2.3, sz);
      menhir.rotation.set((rnd() - 0.5) * 0.12, a, (rnd() - 0.5) * 0.12);
      menhir.castShadow = true; S.add(menhir);
      this.colliders.push({ x: sx, z: sz, r: 0.95 });
    }

"""
edits.append((OLD_BARROW, NEW_KEEP, 'barrow -> keep'))


# ================================================= 5. the King and the wraiths
sub("""      // 22 to 32, not 16 to 24: the mound is 16m across now and the old ring
      // would have stood them on top of it
      const a = (i / 3) * Math.PI * 2, rr = 22 + rnd() * 10;""",
    """      // Outside the walls. The keep is 20m to the wall line and the towers
      // reach 24m, so anything closer than that spawns inside the masonry.
      const a = (i / 3) * Math.PI * 2 + 0.6, rr = 34 + rnd() * 12;""",
    'wraith ring')

sub("""        { max: 85, xp: 90, dmgScale: 0.7, aiD: 0.8, spdScale: 0.8, lockWeapon: 1, aggroR: 14, wraith: true },
        BX + Math.cos(a) * rr, BZ + Math.sin(a) * rr);""",
    """        { max: 85, xp: 90, dmgScale: 0.7, aiD: 0.8, spdScale: 0.8, lockWeapon: 1, aggroR: 14, wraith: true },
        -84 + Math.cos(a) * rr, 246 + Math.sin(a) * rr);""",
    'wraith coords')

sub("""      // at the threshold of his own tomb, facing out, rather than buried in the
      // middle of the hill where he used to stand inside the geometry
      BX + Math.cos(-Math.PI / 2) * (16 + 3.5), BZ + Math.sin(-Math.PI / 2) * (16 + 3.5));""",
    """      // In his own hall, standing before the throne. His aggro radius is 18 and
      // the gateway is 31m from here, so he does not come at you until you are
      // inside the walls with him.
      -84, 235);""",
    'king inside the keep')


# ============================== 6. the per-frame hook that makes houses usable
sub("""    this.worldT = (this.worldT || 0) + dt;""",
    """    this.worldT = (this.worldT || 0) + dt;
    // Hollowrest interiors. The door swings as you walk up to it, and once you
    // are inside the roof lifts off and the walls drop to 22% opacity. The
    // camera rides behind the player, which in a 9m room means outside the
    // wall: without this you walk into a house and look at plaster. The fire's
    // light is switched on only while you are in there, and an invisible light
    // costs the renderer nothing.
    for (const ht of (this._huts || [])) {
      const dx = me.pos.x - ht.x, dz = me.pos.z - ht.z;
      const lx = dx * ht.c - dz * ht.s, lz = dx * ht.s + dz * ht.c;
      const atDoor = Math.abs(lx) < 2.6 && lz > -ht.hd && lz < ht.hd + 3.6;
      const want = atDoor ? -1.9 : 0;
      ht.door.rotation.y += (want - ht.door.rotation.y) * Math.min(1, dt * 7);
      const inside = Math.abs(lx) < ht.hw + 0.35 && Math.abs(lz) < ht.hd + 0.35;
      if (inside !== ht._in) {
        ht._in = inside;
        ht.roof.visible = !inside;
        ht.light.visible = inside;
        if (!inside) for (const k in ht.sides) ht.sides[k].visible = true;
      }
      if (inside) {
        // Hide only the walls the camera is OUTSIDE of. Fading the whole shell
        // takes the far wall with it, and you end up standing in a cottage
        // looking at the sea through the back of it.
        const kx = this.cam.position.x - ht.x, kz = this.cam.position.z - ht.z;
        const clx = kx * ht.c - kz * ht.s, clz = kx * ht.s + kz * ht.c;
        ht.sides.front.visible = clz <= ht.hd;
        ht.sides.back.visible = clz >= -ht.hd;
        ht.sides.right.visible = clx <= ht.hw;
        ht.sides.left.visible = clx >= -ht.hw;
      }
    }""",
    'interior hook')


out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
