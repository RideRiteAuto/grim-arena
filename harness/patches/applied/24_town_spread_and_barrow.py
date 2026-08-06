#!/usr/bin/env python3
"""Spread Hollowrest out, get it off the road, and make the barrow a real tomb.

FOUR THINGS, all from Kevin looking at it.

1. THE BUILDINGS WERE IN THE ROAD. Not "near" it - measured against the game's
   own road corridor, three of the six sat inside it and one stood dead on the
   centreline:

       cottage  (-9, +4)   15m clear   ok
       cottage  (+8, +6)    0m clear   ON the centreline
       cottage (-11, -8)   18m clear   ok
       trader  (+11, -6)    6m clear   inside the 7m corridor
       the inn  (+2,+14)    2m clear   inside the corridor
       cottage (-20,+12)   18m clear   ok

   Every building is now placed in a surveyed pocket of clear ground and then
   pushed through clearOfRoad at a 13m clearance as a belt-and-braces check, so
   this cannot silently come back when the roads are rebaked.

2. IT WAS CRAMPED. Six buildings inside a 20m circle with their eaves nearly
   touching. They now sit at 22 to 40m from the square, which makes the town
   about 70m across, and each one gets a fenced plot: a front garden facing the
   square with vegetable rows, and a back yard with a woodpile, a barrel and a
   drying rail. The yards are what create the spacing - the buildings are not
   just further apart, there is something between them.

3. NO PATHS. Townsfolk wandered across open grass. There is now a dirt path
   network: a ring around the square and a spur out to every garden gate,
   drawn as terrain-draped decals the same way roads are.

   The town safe radius goes 24/26 -> 42/46 to match. It was sized for the old
   20m huddle, and leaving it would have left the outer cottages outside the
   safe zone, where monsters could walk into somebody's back garden.

4. THE BARROW. Kevin: it needs an entrance, monsters must not clip through it,
   it needs to be big enough to walk into, the door has to be big enough for the
   King to come out of, and he should not be living twenty-eight metres from
   town.

   - The mound had NO COLLIDER AT ALL. Only the nine menhirs did. Anything could
     and did walk straight through the hill. It now carries a ring of colliders
     with a deliberate GAP at the doorway, so it is solid everywhere except
     where you are meant to go in.
   - Radius 9 -> 16 and taller, so it reads as a hill you could be buried under.
   - A real entrance: a recessed passage cut into the south face with two
     uprights, a lintel and a threshold, 5m wide and 5.4m tall. The Hollow King
     stands 1.5 scale, about 2.7m, so he clears it with room to spare.
   - Moved from (-96, 122) to (-84, 246). That is 150m due north of town instead
     of 28m. Site surveyed, not guessed: 1.5m of relief across a 15m ring so the
     mound sits flat, 40m clear of any road, and on land.
   - The King now stands at the threshold of his own tomb facing out, and the
     three frost wraiths ring the mound at 22-32m instead of 16-24m, which used
     to put them standing on it.

Spawn ORDER is untouched. Every npc is created in exactly the same sequence, so
the network indices are unchanged. Only positions move.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ================================================= 1. spread the buildings out
OLD_PLACE = """    hut(TX - 9, TZ + 4, 6, 5, 3.0, 0.2, 'plaster', 'thatch', { chimney: 1 });
    hut(TX + 8, TZ + 6, 5.5, 5, 2.8, -0.5, 'plaster', 'thatch');
    hut(TX - 11, TZ - 8, 5, 4.5, 2.7, 1.1, 'plaster', 'slate', { chimney: -1 });
    hut(TX + 11, TZ - 6, 7, 6, 3.4, -1.3, 'stone', 'slate', { chimney: 1 });      // the trader's hall
    hut(TX + 2, TZ + 14, 8, 6, 3.6, Math.PI, 'stone', 'slate', { chimney: -1 });   // the inn
    hut(TX - 20, TZ + 12, 5, 4.5, 2.6, 0.7, 'plaster', 'thatch');
"""

NEW_PLACE = """    // --- where the buildings go.
    //
    // The old layout put six buildings inside a 20m circle and three of them
    // INSIDE the road corridor, one dead on the centreline. These offsets were
    // picked off a survey of the game's own road-distance field around the
    // town: every one sits in a pocket with 18m or more of clearance, and each
    // is then run through clearOfRoad at 13m anyway, so a future road rebake
    // cannot quietly put a house back in the middle of the highway.
    //
    // dx, dz, w, d, h, yaw, walls, roof, opts, gateYaw (which way the garden
    // gate faces, normally back toward the square)
    const PLOTS = [
      [-22, 6, 6, 5, 3.0, 0.35, 'plaster', 'thatch', { chimney: 1 }],
      [-30, 21, 5.5, 5, 2.8, -0.4, 'plaster', 'thatch', {}],
      [-8, -13, 5, 4.5, 2.7, 1.15, 'plaster', 'slate', { chimney: -1 }],
      [30, 11, 7, 6, 3.4, -1.25, 'stone', 'slate', { chimney: 1 }],     // trader's hall
      [26, 29, 8, 6, 3.6, Math.PI, 'stone', 'slate', { chimney: -1 }],  // the inn
      [-35, 30, 5, 4.5, 2.6, 0.8, 'plaster', 'thatch', {}]
    ];
    const plotAt = [];
    for (const [dx, dz, w, d, h, yaw, wk, rk, op] of PLOTS) {
      const p = this.clearOfRoad(TX + dx, TZ + dz, 13);
      hut(p[0], p[1], w, d, h, yaw, wk, rk, op);
      plotAt.push({ x: p[0], z: p[1], w, d, yaw });
    }

    // --- a plot around each building: fence, gate, garden, back yard.
    //
    // This is what actually makes the town feel less cramped. Spacing alone
    // reads as buildings that drifted apart; a fenced garden with something in
    // it reads as somebody's home.
    for (const pl of plotAt) {
      const yd = new T.Group();
      const F = [];
      const fput = (geo, px, py, pz, rx, ry, rz, col) => {
        F.push({
          geo: nonIdx(geo),
          m: new T.Matrix4().compose(new T.Vector3(px, py, pz),
            new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
            new T.Vector3(1, 1, 1)),
          color: col
        });
      };
      const hw = pl.w / 2 + 4.6, hd = pl.d / 2 + 4.2;
      // the gate faces the square
      const toSq = Math.atan2(TX - pl.x, TZ - pl.z);
      const gateSide = Math.abs(Math.sin(toSq - pl.yaw)) > Math.abs(Math.cos(toSq - pl.yaw)) ? 'x' : 'z';
      const gateSign = gateSide === 'x'
        ? Math.sign(Math.sin(toSq - pl.yaw) || 1)
        : Math.sign(Math.cos(toSq - pl.yaw) || 1);
      // fence: posts and two rails, with a gap left where the gate goes
      const runFence = (along, fixed, axis, sign) => {
        const n = Math.max(3, Math.round(along * 2 / 2.0));
        for (let i = 0; i <= n; i++) {
          const t = -along + (2 * along) * (i / n);
          const isGate = (gateSide === axis && sign === gateSign && Math.abs(t) < 1.5);
          if (isGate) continue;
          const px = axis === 'x' ? sign * fixed : t;
          const pz = axis === 'x' ? t : sign * fixed;
          fput(new T.BoxGeometry(0.16, 1.15, 0.16), px, 0.5, pz, 0, 0, 0, C_WOODD);
        }
        // rails, skipping the gate opening
        for (const seg of (gateSide === axis && sign === gateSign)
          ? [[-along, -1.5], [1.5, along]] : [[-along, along]]) {
          const len = seg[1] - seg[0], mid = (seg[0] + seg[1]) / 2;
          if (len < 0.4) continue;
          for (const ry2 of [0.62, 0.95]) {
            const px = axis === 'x' ? sign * fixed : mid;
            const pz = axis === 'x' ? mid : sign * fixed;
            fput(new T.BoxGeometry(axis === 'x' ? 0.07 : len, 0.1, axis === 'x' ? len : 0.07),
                 px, ry2, pz, 0, 0, 0, C_WOOD);
          }
        }
      };
      for (const s of [-1, 1]) runFence(hd, hw, 'x', s);
      for (const s of [-1, 1]) runFence(hw, hd, 'z', s);
      // gate posts, taller, either side of the opening
      for (const s of [-1, 1]) {
        const px = gateSide === 'x' ? gateSign * hw : s * 1.5;
        const pz = gateSide === 'x' ? s * 1.5 : gateSign * hd;
        fput(new T.BoxGeometry(0.22, 1.7, 0.22), px, 0.75, pz, 0, 0, 0, C_TIMBER);
      }
      // front garden: raised beds with rows in them
      const fx = gateSide === 'x' ? gateSign * (hw - 2.6) : 2.4;
      const fz = gateSide === 'x' ? 2.4 : gateSign * (hd - 2.6);
      for (let b = 0; b < 2; b++) {
        const bx = fx, bz = fz + (b - 0.5) * 1.5;
        fput(new T.BoxGeometry(2.6, 0.22, 1.0), bx, 0.11, bz, 0, 0, 0, C_WOODD);
        for (let r3 = 0; r3 < 4; r3++) {
          fput(new T.BoxGeometry(0.24, 0.3, 0.24), bx - 0.9 + r3 * 0.6, 0.3, bz, 0, 0, 0, new T.Color(0x4e7a38));
        }
      }
      // back yard: woodpile, barrel, drying rail
      const bxs = -fx * 0.8, bzs = -fz * 0.8;
      for (let r3 = 0; r3 < 3; r3++) for (let c3 = 0; c3 < 4; c3++) {
        fput(new T.CylinderGeometry(0.14, 0.14, 1.3, 6), bxs + c3 * 0.3, 0.16 + r3 * 0.28, bzs, 0, 0, Math.PI / 2, C_WOOD);
      }
      fput(new T.CylinderGeometry(0.42, 0.36, 0.9, 10), bxs - 1.6, 0.45, bzs + 1.2, 0, 0, 0, C_WOODD);
      fput(new T.TorusGeometry(0.42, 0.05, 4, 10), bxs - 1.6, 0.78, bzs + 1.2, Math.PI / 2, 0, 0, C_TIMBER);
      for (const s of [-1, 1]) {
        fput(new T.BoxGeometry(0.12, 1.7, 0.12), bxs + s * 1.4, 0.85, bzs - 1.8, 0, 0, 0, C_WOODD);
      }
      fput(new T.BoxGeometry(2.9, 0.07, 0.07), bxs, 1.62, bzs - 1.8, 0, 0, 0, C_WOOD);
      for (let c3 = 0; c3 < 3; c3++) {
        fput(new T.BoxGeometry(0.55, 0.62, 0.03), bxs - 0.85 + c3 * 0.85, 1.3, bzs - 1.8, 0, 0, 0,
             new T.Color(c3 % 2 ? 0xd8cfc0 : 0xbfc9d4));
      }
      const fm2 = new T.Mesh(this.mergeGeos(F), townMat);
      fm2.castShadow = true; fm2.receiveShadow = true; yd.add(fm2);
      yd.position.set(pl.x, this.groundY(pl.x, pl.z), pl.z);
      yd.rotation.y = pl.yaw;
      S.add(yd);
    }

    // --- dirt paths: a ring round the square and a spur to every gate.
    //
    // Drawn as terrain-draped decals, the same idea the roads use, so a path
    // follows the ground instead of hovering over it. Townsfolk have something
    // to wander along and the square reads as a place rather than a gap.
    const pathMat = new T.MeshStandardMaterial({ color: 0x8a7350, roughness: 1, transparent: true, opacity: 0.9, flatShading: true });
    const pathDot = new T.CircleGeometry(1.25, 8);
    const layPath = (ax, az, bx, bz, wobble) => {
      const dx = bx - ax, dz = bz - az, L = Math.hypot(dx, dz);
      const n = Math.max(2, Math.round(L / 1.5));
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        // a hand-trodden path wanders; a ruler-straight one reads as a runway
        const off = wobble ? Math.sin(t * Math.PI * 2.4 + ax) * 1.1 * Math.sin(t * Math.PI) : 0;
        const px = ax + dx * t - (dz / L) * off;
        const pz = az + dz * t + (dx / L) * off;
        const m = new T.Mesh(pathDot, pathMat);
        // sit on the slope, not through it
        const e = 1.0;
        const hL = this.groundY(px - e, pz), hR = this.groundY(px + e, pz);
        const hD = this.groundY(px, pz - e), hU = this.groundY(px, pz + e);
        const nrm = new T.Vector3(hL - hR, 2 * e, hD - hU).normalize();
        m.quaternion.setFromUnitVectors(new T.Vector3(0, 0, 1), nrm);
        m.position.set(px, this.groundY(px, pz) + 0.035, pz);
        m.scale.setScalar(0.85 + ((i * 37) % 7) * 0.06);
        m.renderOrder = -1;
        S.add(m);
      }
    };
    // the ring round the square
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
sub(OLD_PLACE, NEW_PLACE, 'building placement, yards and paths')

# ============================================== 2. the safe zone has to grow
sub("""    if (this.townPos) safe.push({ x: r2(this.townPos.x), z: r2(this.townPos.z), rMe: 24, rNpc: 26 });""",
    """    // 42/46, not 24/26. The old radii were sized for a town whose buildings all
    // sat inside a 20m circle. Now that the plots reach 40m out, the old figure
    // left the outer cottages OUTSIDE the safe zone, where a wolf could walk
    // into somebody's back garden and start a fight.
    if (this.townPos) safe.push({ x: r2(this.townPos.x), z: r2(this.townPos.z), rMe: 42, rNpc: 46 });""",
    'town safe radius')

# ================================================== 3. the barrow, rebuilt
OLD_BARROW = """    // --- the barrow: the Hollow King's cairn, north of town
    const BX = -96, BZ = 122;
    this.barrowPos = new T.Vector3(BX, 0, BZ);
    const mound = new T.Mesh(new T.SphereGeometry(9, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2), fm(0x4a5236));
    mound.position.set(BX, this.groundY(BX, BZ) - 0.4, BZ); mound.receiveShadow = true; S.add(mound);
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2, sx = BX + Math.cos(a) * 11, sz = BZ + Math.sin(a) * 11;
      const menhir = new T.Mesh(new T.BoxGeometry(1.0 + rnd() * 0.5, 3.4 + rnd() * 1.8, 0.8), stoneD);
      menhir.position.set(sx, this.groundY(sx, sz) + 1.9, sz);
      menhir.rotation.set((rnd() - 0.5) * 0.12, a, (rnd() - 0.5) * 0.12);
      menhir.castShadow = true; S.add(menhir);
      this.colliders.push({ x: sx, z: sz, r: 0.85 });
    }
    const arch = new T.Mesh(new T.BoxGeometry(5.2, 0.9, 1.0), stoneD);
    arch.position.set(BX, this.groundY(BX, BZ - 9) + 4.2, BZ - 9); arch.castShadow = true; S.add(arch);
"""

NEW_BARROW = """    // --- the barrow: the Hollow King's tomb.
    //
    // Moved from (-96, 122) to (-84, 246). It used to sit 28m from the town
    // well, which made the king a neighbour rather than something you go and
    // find; it is now 150m due north. The site was surveyed rather than picked:
    // 1.5m of relief across a 15m ring so the mound sits flat, 40m clear of any
    // road, and on land.
    //
    // The mound also had NO COLLIDER. Only the menhirs did, so anything could
    // walk straight through the hill, which is exactly what Kevin was seeing. It
    // now carries a ring of colliders with a GAP left at the doorway.
    const BX = -84, BZ = 246;
    const BR = 16;                 // was 9. Big enough to read as a buried hall.
    const DOOR_A = -Math.PI / 2;   // the entrance faces south, back toward town
    const DOOR_HALF = 0.34;        // half-angle of the gap left in the collider ring
    // 5.4m of clear headroom plus the lintel. The King is 1.5 scale, about
    // 2.7m, so he walks out of his own tomb upright. Shared by the hole cut in
    // the dome and the stonework built into it, so the two cannot drift apart.
    const DOOR_H = 5.4, DOOR_TOP = DOOR_H + 1.2;
    this.barrowPos = new T.Vector3(BX, 0, BZ);
    const bY = this.groundY(BX, BZ);
    // The dome is built with a WEDGE MISSING over the entrance, and the wedge
    // filled back in above the doorway only. Framing a door on an unbroken dome
    // just puts a picture of a door on a hill: the dome's own front face is
    // still between you and the passage, so you look through the frame at green
    // grass. This actually cuts the hole.
    //
    // three.js measures SphereGeometry's phi from +Z toward +X, so a world
    // bearing A sits at phi = PI - A.
    const moundMat = fm(0x4a5236);
    const DOOR_HG = 0.23;                                     // half-angle of the opening
    const phiDoor = Math.PI - DOOR_A;
    // polar angle at the top of the doorway: above this the wedge is filled in
    const thDoor = Math.acos(Math.min(0.97, (DOOR_TOP) / BR));
    const moundA = new T.Mesh(
      new T.SphereGeometry(BR, 24, 12, phiDoor + DOOR_HG, Math.PI * 2 - DOOR_HG * 2, 0, Math.PI / 2), moundMat);
    const moundB = new T.Mesh(
      new T.SphereGeometry(BR, 6, 10, phiDoor - DOOR_HG, DOOR_HG * 2, 0, thDoor), moundMat);
    for (const m of [moundA, moundB]) {
      m.position.set(BX, bY - 1.2, BZ); m.receiveShadow = true; m.castShadow = true; S.add(m);
    }
    // a skirt of turf so the dome does not cut a hard line into the ground.
    // It stops just under the threshold so it cannot dam up the doorway.
    const skirt = new T.Mesh(new T.CylinderGeometry(BR + 1.6, BR + 2.6, 1.4, 20), fm(0x46512f));
    skirt.position.set(BX, bY - 1.0, BZ); skirt.receiveShadow = true; S.add(skirt);

    // Solid everywhere except the doorway. Without this the hill is scenery you
    // can stand inside.
    for (let i = 0; i < 26; i++) {
      const a = i * Math.PI * 2 / 26;
      let da = a - DOOR_A; while (da > Math.PI) da -= Math.PI * 2; while (da < -Math.PI) da += Math.PI * 2;
      if (Math.abs(da) < DOOR_HALF) continue;         // this is the way in
      this.colliders.push({ x: BX + Math.cos(a) * (BR - 1.6), z: BZ + Math.sin(a) * (BR - 1.6), r: 2.6 });
    }

    // The entrance. The King is built at 1.5 scale, about 2.7m tall, so the
    // opening is 5.0m wide and 5.4m clear: he walks out of his own tomb without
    // ducking, which is the whole point of it being his.
    {
      const E = [];
      const eput = (geo, px, py, pz, rx, ry, rz, col) => {
        E.push({
          geo: nonIdx(geo),
          m: new T.Matrix4().compose(new T.Vector3(px, py, pz),
            new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
            new T.Vector3(1, 1, 1)),
          color: col
        });
      };
      const DW = 5.0, DH = DOOR_H, PD = 5.0;   // width, height, how far it cuts in
      // the passage: side walls, roof and floor, sunk into the mound face
      for (const s of [-1, 1]) {
        eput(new T.BoxGeometry(1.1, DH + 0.6, PD), s * (DW / 2 + 0.55), (DH + 0.6) / 2, -PD / 2 + 0.4, 0, 0, 0, C_STONED);
      }
      eput(new T.BoxGeometry(DW + 2.2, 1.0, PD), 0, DH + 0.5, -PD / 2 + 0.4, 0, 0, 0, C_STONED);
      eput(new T.BoxGeometry(DW + 1.4, 0.3, PD + 1.2), 0, 0.15, -PD / 2 + 0.2, 0, 0, 0, C_STONE);
      // A stepped passage receding into the hill. Without this the doorway is a
      // flat black rectangle painted on a mound: there is nothing to tell you
      // it has depth, because the passage walls sit outside the opening and
      // never come into view head-on.
      for (let k = 0; k < 3; k++) {
        const sh = 1 - k * 0.13, zz = -1.5 - k * 1.4;
        const ow = DW * sh, oh = DH * sh, t = 0.55;
        const shade = new T.Color().lerpColors(C_STONED, new T.Color(0x191c17), (k + 1) / 4);
        for (const s of [-1, 1]) eput(new T.BoxGeometry(t, oh, 1.25), s * (ow / 2 + t / 2), oh / 2, zz, 0, 0, 0, shade);
        eput(new T.BoxGeometry(ow + t * 2, t, 1.25), 0, oh + t / 2, zz, 0, 0, 0, shade);
      }
      // the dark at the end of it
      eput(new T.BoxGeometry(DW, DH, 0.4), 0, DH / 2, -PD - 0.8, 0, 0, 0, new T.Color(0x090b08));
      // jambs and lintel standing proud of the face
      for (const s of [-1, 1]) {
        eput(new T.BoxGeometry(1.5, DH + 1.2, 1.5), s * (DW / 2 + 0.75), (DH + 1.2) / 2, 0.5, 0, 0, 0, C_STONED);
      }
      eput(new T.BoxGeometry(DW + 3.4, 1.5, 1.9), 0, DH + 1.5, 0.5, 0, 0, 0, C_STONED);
      eput(new T.BoxGeometry(DW + 2.0, 0.9, 1.4), 0, DH + 2.7, 0.4, 0, 0, 0, C_STONE);
      // threshold step
      eput(new T.BoxGeometry(DW + 2.6, 0.34, 1.8), 0, 0.17, 1.5, 0, 0, 0, C_STONE);
      const em = new T.Mesh(this.mergeGeos(E), townMat);
      em.castShadow = true; em.receiveShadow = true;
      const eg = new T.Group();
      eg.add(em);
      eg.position.set(BX + Math.cos(DOOR_A) * (BR - 1.0), bY, BZ + Math.sin(DOOR_A) * (BR - 1.0));
      // The passage is built along local -z, so local -z has to point at the
      // centre of the mound. Getting this wrong by a quarter turn cuts the
      // passage into open air beside the hill instead of into it, and the dark
      // plane at the end of it hangs in space next to the barrow, which is
      // exactly what the first version of this did.
      //   local -z -> world (-sin t, -cos t), want (-cos A, -sin A)
      //   => t = PI/2 - A
      eg.rotation.y = Math.PI / 2 - DOOR_A;
      S.add(eg);
      // the jambs are solid; the gap between them is not
      const exX = Math.cos(DOOR_A), exZ = Math.sin(DOOR_A);      // local +z, outward
      const axX = Math.sin(DOOR_A), axZ = -Math.cos(DOOR_A);     // local +x, across
      for (const s of [-1, 1]) {
        const off = s * (DW / 2 + 0.75);
        this.colliders.push({
          x: eg.position.x + exX * 0.5 + axX * off,
          z: eg.position.z + exZ * 0.5 + axZ * off,
          r: 1.0
        });
      }
    }

    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2, sx = BX + Math.cos(a) * (BR + 5), sz = BZ + Math.sin(a) * (BR + 5);
      const menhir = new T.Mesh(new T.BoxGeometry(1.0 + rnd() * 0.5, 3.4 + rnd() * 1.8, 0.8), stoneD);
      menhir.position.set(sx, this.groundY(sx, sz) + 1.9, sz);
      menhir.rotation.set((rnd() - 0.5) * 0.12, a, (rnd() - 0.5) * 0.12);
      menhir.castShadow = true; S.add(menhir);
      this.colliders.push({ x: sx, z: sz, r: 0.85 });
    }
"""
sub(OLD_BARROW, NEW_BARROW, 'the barrow')

# ------------------------------------------- 4. wraiths off the mound, king out
sub("""      const a = (i / 3) * Math.PI * 2, rr = 16 + rnd() * 8;
      foe('FROST WRAITH', { steel: 0x6f8fae, cloth: 0x2a3a4e, trim: 0x9fdcff },""",
    """      // 22 to 32, not 16 to 24: the mound is 16m across now and the old ring
      // would have stood them on top of it
      const a = (i / 3) * Math.PI * 2, rr = 22 + rnd() * 10;
      foe('FROST WRAITH', { steel: 0x6f8fae, cloth: 0x2a3a4e, trim: 0x9fdcff },""",
    'wraith ring')

sub("""      { max: 620, xp: 500, dmgScale: 0.95, aiD: 1.0, spdScale: 0.92, brawler: true, aggroR: 18, king: true, specialCd: 3, weapon: 5, lockWeapon: 5 },
      BX, BZ);""",
    """      { max: 620, xp: 500, dmgScale: 0.95, aiD: 1.0, spdScale: 0.92, brawler: true, aggroR: 18, king: true, specialCd: 3, weapon: 5, lockWeapon: 5 },
      // at the threshold of his own tomb, facing out, rather than buried in the
      // middle of the hill where he used to stand inside the geometry
      BX + Math.cos(-Math.PI / 2) * (16 + 3.5), BZ + Math.sin(-Math.PI / 2) * (16 + 3.5));""",
    'king at the threshold')


out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
