#!/usr/bin/env python3
"""Rebuild the buildings of Hollowrest.

Hollowrest is the town the player lives out of - bank, shop, quest line, the
place you stand around in between jobs - and every building in it was one box
with one four-sided cone on top, plus a flat door rectangle and two flat window
squares. No eaves, no chimney, no frame, no depth. A pyramid roof on a
rectangular building is also just wrong: cottages have a RIDGE.

What a building is now:

  plinth        a stone base course that sits proud of the walls and runs BELOW
                ground level, so a hut on a slope no longer floats on one corner
  walls         as before, but inset above the plinth
  gable roof    two real slopes meeting at a ridge along the long axis, with a
                ridge beam and a 0.35m eaves overhang on every side. The
                overhang alone does more for the silhouette than everything
                else here put together
  gable ends    filled triangles, so you cannot see into the roof void
  roof texture  thatch gets laid courses, slate gets a capping row
  half-timber   plaster buildings get corner posts, a mid rail, a top plate and
                diagonal braces, which is what makes a cottage read as built
                rather than extruded
  door          recessed into a frame with two jambs and a lintel, with plank
                lines and a handle
  windows       a frame, a sill and a mullion cross, still warm-lit
  chimney       a stone stack with a cap on the buildings that would have a
                hearth (the inn, the trader's hall, two cottages)

The well and the market stalls got the same treatment: the well gets a proper
pitched roof, a windlass with a crank, a rope and a bucket; the stalls get a
striped awning with a scalloped valance, posts with feet, and goods on the
bench.

PERFORMANCE. This is roughly ten times the geometry per building, and a draw
call per mesh would have put about 180 extra calls into the one place the player
stands still. So every building merges into ONE mesh on a shared vertex-coloured
material, exactly the way the dressing engine handles clutter. Six buildings are
six draw calls, the same as before, and the whole town's structural geometry
costs about what the old boxes did. Windows stay separate because they are
emissive and cannot ride a non-emissive material.

Colliders are untouched: same centres, same radii, so nothing about where you
can walk changes.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


OLD_HUT = """    // --- a building: walls, gabled roof, door, windows, and a collider
    const hut = (x, z, w, d, h, rot, wallM, roofM) => {
      const g = new T.Group();
      const walls = new T.Mesh(new T.BoxGeometry(w, h, d), wallM);
      walls.position.y = h / 2; walls.castShadow = true; walls.receiveShadow = true; g.add(walls);
      const roof = new T.Mesh(new T.ConeGeometry(Math.max(w, d) * 0.82, h * 0.72, 4), roofM);
      roof.position.y = h + h * 0.34; roof.rotation.y = Math.PI / 4; roof.castShadow = true; g.add(roof);
      const door = new T.Mesh(new T.BoxGeometry(0.9, 1.7, 0.12), woodD);
      door.position.set(0, 0.85, d / 2 + 0.04); g.add(door);
      for (const s of [-1, 1]) {
        const win = new T.Mesh(new T.BoxGeometry(0.6, 0.6, 0.1), fm(0xe8c774, 0.4));
        win.position.set(s * (w / 4 + 0.3), h * 0.62, d / 2 + 0.03); g.add(win);
      }
      g.position.set(x, this.groundY(x, z), z); g.rotation.y = rot; S.add(g);
      this.colliders.push({ x, z, r: Math.max(w, d) * 0.62 });
      return g;
    };

    hut(TX - 9, TZ + 4, 6, 5, 3.0, 0.2, plaster, thatch);
    hut(TX + 8, TZ + 6, 5.5, 5, 2.8, -0.5, plaster, thatch);
    hut(TX - 11, TZ - 8, 5, 4.5, 2.7, 1.1, plaster, slate);
    hut(TX + 11, TZ - 6, 7, 6, 3.4, -1.3, stone, slate);      // the trader's hall
    hut(TX + 2, TZ + 14, 8, 6, 3.6, Math.PI, stone, slate);    // the inn
    hut(TX - 20, TZ + 12, 5, 4.5, 2.6, 0.7, plaster, thatch);
"""

NEW_HUT = """    // --- shared building material. Everything structural in this town merges
    // into vertex-coloured meshes on ONE material, the same trick the dressing
    // engine uses for clutter: a building is ten times the geometry it was and
    // still exactly one draw call.
    const townMat = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, flatShading: true });
    const glassMat = new T.MeshStandardMaterial({ color: 0xe8c774, emissive: 0xb08420, emissiveIntensity: 0.9, roughness: 0.35, flatShading: true });
    const nonIdx = (x) => (x.index ? x.toNonIndexed() : x);
    const C_PLASTER = new T.Color(0xc4b89a), C_STONE = new T.Color(0x8a8578), C_STONED = new T.Color(0x6a6558);
    const C_WOOD = new T.Color(0x6b4a2a), C_WOODD = new T.Color(0x46301c), C_TIMBER = new T.Color(0x3f2b18);
    const C_THATCH = new T.Color(0x9a7f45), C_THATCHD = new T.Color(0x7d6534), C_SLATE = new T.Color(0x4a4e56), C_SLATED = new T.Color(0x35383e);

    // a triangle standing in the XY plane, extruded through its own thickness:
    // the filler that closes a gable end
    const gableGeo = (span, rise, thick) => {
      const sh = new T.Shape();
      sh.moveTo(-span / 2, 0); sh.lineTo(span / 2, 0); sh.lineTo(0, rise); sh.closePath();
      const geo = new T.ExtrudeGeometry(sh, { depth: thick, bevelEnabled: false });
      geo.translate(0, 0, -thick / 2);
      return nonIdx(geo);
    };

    // --- a building: plinth, walls, half-timbering, a real ridged roof with
    // eaves, a framed door, mullioned windows, and a chimney where one belongs
    const hut = (x, z, w, d, h, rot, wallKind, roofKind, opts) => {
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
      const timbered = wallKind === 'plaster';
      const wallC = timbered ? C_PLASTER : C_STONE;
      const roofC = roofKind === 'thatch' ? C_THATCH : C_SLATE;
      const roofD = roofKind === 'thatch' ? C_THATCHD : C_SLATED;

      // plinth: proud of the walls and sunk well below zero, so a hut pitched
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

      if (timbered) {
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

      // door, set into a frame rather than pasted on the wall
      const dz = d / 2;
      put(new T.BoxGeometry(1.26, 2.16, 0.14), 0, 0.35 + 1.08, dz + 0.02, 0, 0, 0, C_WOODD);
      put(new T.BoxGeometry(0.98, 1.94, 0.1), 0, 0.35 + 0.97, dz + 0.07, 0, 0, 0, C_WOOD);
      for (const px of [-0.3, 0, 0.3]) {
        put(new T.BoxGeometry(0.05, 1.86, 0.04), px, 0.35 + 0.97, dz + 0.12, 0, 0, 0, C_WOODD);
      }
      put(new T.BoxGeometry(0.13, 0.13, 0.1), 0.36, 0.35 + 1.0, dz + 0.14, 0, 0, 0, C_STONED);
      put(new T.BoxGeometry(1.4, 0.18, 0.3), 0, 0.35 + 2.2, dz + 0.06, 0, 0, 0, C_STONED);
      put(new T.BoxGeometry(1.5, 0.12, 0.5), 0, 0.32, dz + 0.16, 0, 0, 0, C_STONED);

      // windows: frame, sill and mullions merge with the building; only the
      // glass is a separate mesh, because it has to glow
      const wins = [];
      const winAt = (px, py, pz, ry) => {
        // The frame is FOUR BARS, not a solid box. A solid box seals the glass
        // inside itself and the window reads as a dark panel with a light
        // border, which is exactly what the first cut of this did.
        const fw = 0.98, bar = 0.13, dep = 0.16, inner = fw - bar * 2;
        // local +x of a window rotated by ry, so offsets land on the right wall
        const ax = Math.cos(ry), az = -Math.sin(ry);
        const at = (t, dy) => [px + ax * t, py + dy, pz + az * t];
        let q2 = at(0, (fw - bar) / 2); put(new T.BoxGeometry(fw, bar, dep), q2[0], q2[1], q2[2], 0, ry, 0, C_WOODD);
        q2 = at(0, -(fw - bar) / 2); put(new T.BoxGeometry(fw, bar, dep), q2[0], q2[1], q2[2], 0, ry, 0, C_WOODD);
        q2 = at(-(fw - bar) / 2, 0); put(new T.BoxGeometry(bar, inner, dep), q2[0], q2[1], q2[2], 0, ry, 0, C_WOODD);
        q2 = at((fw - bar) / 2, 0); put(new T.BoxGeometry(bar, inner, dep), q2[0], q2[1], q2[2], 0, ry, 0, C_WOODD);
        // mullion cross, sitting proud of the glass
        q2 = at(0, 0);
        put(new T.BoxGeometry(0.075, inner, dep * 0.55), q2[0], q2[1], q2[2], 0, ry, 0, C_WOODD);
        put(new T.BoxGeometry(inner, 0.075, dep * 0.55), q2[0], q2[1], q2[2], 0, ry, 0, C_WOODD);
        q2 = at(0, -(fw / 2 + 0.07)); put(new T.BoxGeometry(fw + 0.2, 0.11, 0.26), q2[0], q2[1], q2[2], 0, ry, 0, C_STONED);
        wins.push([px, py, pz, ry]);
      };
      for (const s of [-1, 1]) winAt(s * (w / 4 + 0.26), 0.35 + h * 0.62, dz + 0.04, 0);
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
    };

    hut(TX - 9, TZ + 4, 6, 5, 3.0, 0.2, 'plaster', 'thatch', { chimney: 1 });
    hut(TX + 8, TZ + 6, 5.5, 5, 2.8, -0.5, 'plaster', 'thatch');
    hut(TX - 11, TZ - 8, 5, 4.5, 2.7, 1.1, 'plaster', 'slate', { chimney: -1 });
    hut(TX + 11, TZ - 6, 7, 6, 3.4, -1.3, 'stone', 'slate', { chimney: 1 });      // the trader's hall
    hut(TX + 2, TZ + 14, 8, 6, 3.6, Math.PI, 'stone', 'slate', { chimney: -1 });   // the inn
    hut(TX - 20, TZ + 12, 5, 4.5, 2.6, 0.7, 'plaster', 'thatch');
"""
sub(OLD_HUT, NEW_HUT, 'hut factory')

# ------------------------------------------------------------------ the well
OLD_WELL = """    const wellG = new T.Group();
    const ring = new T.Mesh(new T.CylinderGeometry(1.15, 1.25, 0.9, 12), stone); ring.position.y = 0.45; ring.castShadow = true; wellG.add(ring);
    const hole = new T.Mesh(new T.CylinderGeometry(0.9, 0.9, 0.12, 12), fm(0x14160f)); hole.position.y = 0.92; wellG.add(hole);
    for (const s of [-1, 1]) { const post = new T.Mesh(new T.BoxGeometry(0.16, 2.0, 0.16), wood); post.position.set(s * 1.0, 1.4, 0); post.castShadow = true; wellG.add(post); }
    const wroof = new T.Mesh(new T.ConeGeometry(1.6, 0.8, 4), thatch); wroof.position.y = 2.7; wroof.rotation.y = Math.PI / 4; wroof.castShadow = true; wellG.add(wroof);
    wellG.position.set(TX, this.groundY(TX, TZ), TZ); S.add(wellG);
"""
NEW_WELL = """    const wellG = new T.Group();
    {
      const W = [];
      const wput = (geo, px, py, pz, rx, ry, rz, col) => {
        W.push({
          geo: nonIdx(geo),
          m: new T.Matrix4().compose(new T.Vector3(px, py, pz),
            new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
            new T.Vector3(1, 1, 1)),
          color: col
        });
      };
      wput(new T.CylinderGeometry(1.3, 1.4, 0.34, 14), 0, 0.17, 0, 0, 0, 0, C_STONED);
      wput(new T.CylinderGeometry(1.14, 1.2, 0.72, 14), 0, 0.7, 0, 0, 0, 0, C_STONE);
      // coping stones round the rim, so it is masonry and not a pipe
      for (let i = 0; i < 10; i++) {
        const a = i * Math.PI * 2 / 10;
        wput(new T.BoxGeometry(0.42, 0.16, 0.3), Math.cos(a) * 1.16, 1.13, Math.sin(a) * 1.16, 0, -a, 0, C_STONED);
      }
      wput(new T.CylinderGeometry(0.94, 0.94, 0.1, 14), 0, 1.0, 0, 0, 0, 0, new T.Color(0x14160f));
      for (const s of [-1, 1]) {
        wput(new T.BoxGeometry(0.2, 2.1, 0.2), s * 1.05, 2.05, 0, 0, 0, 0, C_WOOD);
        wput(new T.BoxGeometry(0.3, 0.24, 0.3), s * 1.05, 0.98, 0, 0, 0, 0, C_WOODD);
      }
      // windlass, crank, rope and bucket
      wput(new T.CylinderGeometry(0.15, 0.15, 1.9, 8), 0, 2.5, 0, 0, 0, Math.PI / 2, C_WOODD);
      wput(new T.BoxGeometry(0.07, 0.4, 0.07), 1.2, 2.32, 0, 0, 0, 0, C_WOODD);
      wput(new T.BoxGeometry(0.07, 0.07, 0.34), 1.2, 2.14, 0.15, 0, 0, 0, C_WOODD);
      wput(new T.CylinderGeometry(0.03, 0.03, 1.1, 4), 0, 1.95, 0, 0, 0, 0, new T.Color(0xa89a78));
      wput(new T.CylinderGeometry(0.26, 0.22, 0.34, 8), 0, 1.28, 0, 0, 0, 0, C_WOOD);
      wput(new T.TorusGeometry(0.26, 0.035, 4, 10), 0, 1.42, 0, Math.PI / 2, 0, 0, C_WOODD);
      // a pitched roof over it, not a pyramid
      const wr = 0.62, wSpan = 1.5, wSlope = Math.sqrt(wSpan * wSpan + wr * wr), wPitch = Math.atan2(wr, wSpan);
      for (const s of [-1, 1]) {
        wput(new T.BoxGeometry(2.9, 0.13, wSlope), 0, 3.02 + wr / 2, s * wSpan / 2, s * wPitch, 0, 0, C_THATCH);
        wput(new T.BoxGeometry(2.8, 0.06, 0.16), 0, 3.02 + wr * 0.55, s * wSpan * 0.5, s * wPitch, 0, 0, C_THATCHD);
      }
      wput(new T.BoxGeometry(3.05, 0.16, 0.22), 0, 3.02 + wr + 0.03, 0, 0, 0, 0, C_THATCHD);
      const wm = new T.Mesh(this.mergeGeos(W), townMat);
      wm.castShadow = true; wm.receiveShadow = true; wellG.add(wm);
    }
    wellG.position.set(TX, this.groundY(TX, TZ), TZ); S.add(wellG);
"""
sub(OLD_WELL, NEW_WELL, 'the well')

# ----------------------------------------------------------------- the stalls
OLD_STALL = """      const st = new T.Group();
      const top = new T.Mesh(new T.BoxGeometry(2.6, 0.16, 1.8), i % 2 ? fm(0x8a2b26) : fm(0x3d6b35)); top.position.y = 2.0; st.add(top);
      const bench = new T.Mesh(new T.BoxGeometry(2.4, 0.14, 1.2), wood); bench.position.y = 1.0; st.add(bench);
      for (const [ox, oz] of [[-1.1, -0.7], [1.1, -0.7], [-1.1, 0.7], [1.1, 0.7]]) { const p = new T.Mesh(new T.BoxGeometry(0.1, 2.0, 0.1), woodD); p.position.set(ox, 1.0, oz); st.add(p); }
"""
NEW_STALL = """      const st = new T.Group();
      {
        const A = [];
        const aput = (geo, px, py, pz, rx, ry, rz, col) => {
          A.push({
            geo: nonIdx(geo),
            m: new T.Matrix4().compose(new T.Vector3(px, py, pz),
              new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
              new T.Vector3(1, 1, 1)),
            color: col
          });
        };
        const cA = new T.Color(i % 2 ? 0x9a3128 : 0x3d6b35);
        const cB = new T.Color(i % 2 ? 0xd8c9a8 : 0xd8c9a8);
        // a pitched awning with alternating stripes and a scalloped valance
        const aRise = 0.34, aSpan = 0.95;
        const aSlope = Math.sqrt(aSpan * aSpan + aRise * aRise), aPitch = Math.atan2(aRise, aSpan);
        for (const s of [-1, 1]) {
          for (let k = 0; k < 6; k++) {
            aput(new T.BoxGeometry(0.44, 0.08, aSlope), -1.32 + 0.44 * k + 0.22, 2.02 + aRise / 2, s * aSpan / 2,
                 s * aPitch, 0, 0, k % 2 ? cA : cB);
          }
          for (let k = 0; k < 6; k++) {
            aput(new T.BoxGeometry(0.4, 0.2, 0.06), -1.32 + 0.44 * k + 0.22, 1.94, s * (aSpan + 0.02), 0, 0, 0, k % 2 ? cA : cB);
          }
        }
        aput(new T.BoxGeometry(2.78, 0.12, 0.16), 0, 2.02 + aRise + 0.02, 0, 0, 0, 0, C_WOODD);
        aput(new T.BoxGeometry(2.5, 0.16, 1.24), 0, 1.0, 0, 0, 0, 0, C_WOOD);
        aput(new T.BoxGeometry(2.5, 0.3, 0.1), 0, 0.82, -0.62, 0, 0, 0, C_WOODD);
        for (const [ox, oz] of [[-1.16, -0.72], [1.16, -0.72], [-1.16, 0.72], [1.16, 0.72]]) {
          aput(new T.BoxGeometry(0.13, 2.0, 0.13), ox, 1.0, oz, 0, 0, 0, C_WOODD);
          aput(new T.BoxGeometry(0.26, 0.1, 0.26), ox, 0.05, oz, 0, 0, 0, C_STONED);
        }
        // something actually laid out on the bench
        const goods = [C_THATCH, new T.Color(0x8a4a2a), new T.Color(0x6f8a4e)];
        for (let k = 0; k < 5; k++) {
          const gx = -0.9 + k * 0.45;
          aput(new T.BoxGeometry(0.3, 0.22, 0.3), gx, 1.19, -0.1 + (k % 2) * 0.24, 0, k * 0.6, 0, goods[k % 3]);
        }
        aput(new T.CylinderGeometry(0.2, 0.24, 0.3, 8), 1.0, 1.23, 0.2, 0, 0, 0, C_WOODD);
        const sm = new T.Mesh(this.mergeGeos(A), townMat);
        sm.castShadow = true; sm.receiveShadow = true; st.add(sm);
      }
"""
sub(OLD_STALL, NEW_STALL, 'market stalls')


out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
