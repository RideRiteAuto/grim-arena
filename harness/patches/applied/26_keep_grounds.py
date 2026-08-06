#!/usr/bin/env python3
"""The keep as a place someone took over: clear the junk, floor it, light it green.

Kevin, on the first cut of the keep: the inside is cluttered junk where you are
supposed to be fighting the King, it is hard to walk around, some of it looks
low quality, the ground is grass when it should read as castle grounds, the
front of the gate is plain, and the fire should be green because the King is.
Plus, separately: everything in the buildings needs collision.

WHAT WAS ACTUALLY WRONG

1. The courtyard was still GRASS with the world's procedural dressing growing
   through it. The flagstones I laid were CircleGeometry r2.5 on a 4.2m grid,
   which leaves a gap between every disc, so what you mostly saw was the
   terrain and the zone clutter on top of it: tufts, blades, boulders, bushes.
   That is the "cluttered junk" and most of it was not even mine.

   Fixed at the source. `keepGround(x, z)` marks the bailey and the approach,
   and `dressChunk` now skips both clutter AND nodes inside it. It is a pure
   function of position, so every client filters identically and node ids stay
   in step. On top of that the courtyard is a continuous flagstone floor:
   overlapping tiles on a 2.8m grid, each sampled onto its own ground height,
   merged into the keep mesh so it costs no extra draw call.

2. MY junk: seven fallen pillars and twenty-one rubble stones scattered through
   the middle of the arena, exactly where the fight happens. Gone. What is left
   is deliberate and against the walls: two toppled columns, a broken cart, a
   collapsed stack of crates, and dead ivy up the north wall.

3. The entrance had nothing in it. There is now a timber palisade along the
   inside of the south wall either side of the gate, two barricades angled
   across the approach inside it, and a rack of spears. It reads as a position
   somebody is holding rather than a hole in a wall.

4. Outside was plain grass to the gate. There is a cobbled road running 40m
   south from the gatehouse, and four abandoned fruit stands along it with
   their baskets tipped over and empty. Somebody used to trade here.

5. RUNDOWN. Merlons are knocked out of the curtain in a deterministic pattern
   and a few of the survivors sit askew, so the battlements are gap-toothed
   rather than machined.

6. GREEN FELL FIRE. The other track built a proper shader flame with noise
   erosion for the bridge torches. Rather than write a second one, its builder
   now takes a `fell` flag and picks a green palette: pale green-white at the
   core, green through the body, deep green where it tears away. The braziers
   in the keep burn it, and the two that carry a light throw green.

7. COLLISION ON EVERYTHING PLACED. House furniture (hearth, table, benches,
   bed, chest), yard props (woodpile, barrel, drying rail, vegetable beds), the
   plot fences with their gate gaps, market crates, and every new prop in and
   around the keep. All axis-aligned boxes, which is why every building and
   plot yaw is a quarter turn.

Spawn ORDER untouched.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ===================================================== 1. green fell fire
# The other track's flame is a good one. Give it a palette switch rather than
# writing a second shader that drifts away from it.
sub("""  torchFlameMat() {
    if (this._flameMat) return this._flameMat;""",
    """  torchFlameMat(fell) {
    // fell: the Hollow King's green. Same shader, same motion, same erosion,
    // different heat colours. One flame implementation, two palettes.
    if (fell ? this._fellMat : this._flameMat) return fell ? this._fellMat : this._flameMat;""",
    'flame mat signature')

sub("""        'vec3 core = vec3(1.00, 0.86, 0.46);',   // hot yellow at the wick
        'vec3 body = vec3(1.00, 0.62, 0.15);',   // orange through the middle
        'vec3 tipc = vec3(0.94, 0.24, 0.05);',   // red where it thins away""",
    """        fell ? 'vec3 core = vec3(0.62, 1.00, 0.48);'    // fell fire: green even at the core
             : 'vec3 core = vec3(1.00, 0.86, 0.46);',   // hot yellow at the wick
        fell ? 'vec3 body = vec3(0.20, 0.90, 0.26);'
             : 'vec3 body = vec3(1.00, 0.62, 0.15);',   // orange through the middle
        fell ? 'vec3 tipc = vec3(0.03, 0.40, 0.20);'
             : 'vec3 tipc = vec3(0.94, 0.24, 0.05);',   // red where it thins away""",
    'flame palette')

sub("""    this._flameMat = m;
    return m;
  }""",
    """    if (fell) this._fellMat = m; else this._flameMat = m;
    return m;
  }""",
    'flame mat cache')

sub("""    if (this._flameMat) this._flameMat.userData.uTime.value = s;""",
    """    if (this._flameMat) this._flameMat.userData.uTime.value = s;
    if (this._fellMat) this._fellMat.userData.uTime.value = s;""",
    'tick fell flame')


# ============================ 2. keep the world's dressing off the keep grounds
sub("""  dressChunk(rec) {
    if (!GRIM_WORLD.ready) return;""",
    """  // Ground the keep occupies: the bailey inside the walls, and the cobbled
  // approach outside the gate. The procedural dressing is kept off both,
  // because wild grass, boulders and bushes growing through a castle floor is
  // most of what "cluttered junk on the inside" actually was. A pure function
  // of position, so every client filters the same and node ids stay in step.
  keepGround(x, z) {
    const dx = x + 84, dz = z - 246;
    if (Math.abs(dx) < 23 && Math.abs(dz) < 23) return true;
    if (Math.abs(dx) < 7.5 && dz > 20 && dz < 62) return true;
    return false;
  }

  dressChunk(rec) {
    if (!GRIM_WORLD.ready) return;""",
    'keepGround helper')

sub("""      for (const p of props.clutter) {
        const geo = this._clutterGeo[p.type];
        if (!geo) continue;""",
    """      for (const p of props.clutter) {
        if (this.keepGround(p.x, p.z)) continue;
        const geo = this._clutterGeo[p.type];
        if (!geo) continue;""",
    'clutter filter')

sub("""    for (const p of props.nodes) {
      const nd = GRIM_RULES.GATHER.NODES[p.kind];
      if (!nd) continue;""",
    """    for (const p of props.nodes) {
      const nd = GRIM_RULES.GATHER.NODES[p.kind];
      if (!nd) continue;
      if (this.keepGround(p.x, p.z)) continue;""",
    'node filter')


# ==================================================== 3. house furniture solid
sub("""      wallCol(0, -(hd - TW / 2), hw, TW / 2);
      for (const sx of [-1, 1]) wallCol(sx * (hw - TW / 2), 0, TW / 2, hd);
      for (const sx of [-1, 1]) wallCol(sx * (DWID / 2 + pw / 2), hd - TW / 2, pw / 2, TW / 2);""",
    """      wallCol(0, -(hd - TW / 2), hw, TW / 2);
      for (const sx of [-1, 1]) wallCol(sx * (hw - TW / 2), 0, TW / 2, hd);
      for (const sx of [-1, 1]) wallCol(sx * (DWID / 2 + pw / 2), hd - TW / 2, pw / 2, TW / 2);
      // The furniture is solid too. Everything in here is axis aligned in local
      // space and the yaw is a quarter turn, so it stays axis aligned in world
      // space, which is the only kind of box the resolver understands.
      wallCol(fx0, 0, 0.75, 1.3);                              // hearth
      wallCol(tx, id * 0.14, 1.1, 0.55);                       // table
      wallCol(-hs * (hw - 1.0), -id * 0.24, 0.65, 1.05);       // bed
      wallCol(tx - 0.2, -id * 0.36, 0.5, 0.33);                // chest""",
    'house furniture colliders')


# ======================================================= 4. yard props solid
sub("""      const fm2 = new T.Mesh(this.mergeGeos(F), townMat);""",
    """      // Plot fences and yard props are solid. The fence keeps its gate gap, so
      // the way in is still the way in. Quarter-turn yaws again, so boxes.
      const yc = Math.round(Math.cos(pl.yaw)), ys = Math.round(Math.sin(pl.yaw));
      const yCol = (lx, lz, ehx, ehz) => {
        this.colliders.push({
          x: pl.x + lx * yc + lz * ys,
          z: pl.z - lx * ys + lz * yc,
          hw: Math.abs(yc) * ehx + Math.abs(ys) * ehz,
          hd: Math.abs(ys) * ehx + Math.abs(yc) * ehz
        });
      };
      for (const s of [-1, 1]) {
        // each side, split around the gate if the gate is on it
        if (gateSide === 'z' && s === gateSign) {
          for (const q of [-1, 1]) {
            const a0 = q * 1.5, a1 = q * hw;
            yCol((a0 + a1) / 2, s * hd, Math.abs(a1 - a0) / 2, 0.12);
          }
        } else yCol(0, s * hd, hw, 0.12);
        if (gateSide === 'x' && s === gateSign) {
          for (const q of [-1, 1]) {
            const a0 = q * 1.5, a1 = q * hd;
            yCol(s * hw, (a0 + a1) / 2, 0.12, Math.abs(a1 - a0) / 2);
          }
        } else yCol(s * hw, 0, 0.12, hd);
      }
      for (let b = 0; b < 2; b++) yCol(fx, fz + (b - 0.5) * 1.6, 1.4, 0.55);   // vegetable beds
      yCol(bxs + 0.45, bzs, 0.85, 0.7);                                        // woodpile
      yCol(bxs - 1.6, bzs + 1.2, 0.45, 0.45);                                  // barrel
      yCol(bxs, bzs - 1.8, 1.5, 0.12);                                         // drying rail

      const fm2 = new T.Mesh(this.mergeGeos(F), townMat);""",
    'yard colliders')


# ================================================ 5. market crates get collision
sub("""      this.colliders.push({ x: TX - MW + 3.2, z: TZ - MD + 3.0, r: 0.6 });
      this.colliders.push({ x: TX + MW - 3.4, z: TZ + MD - 3.2, r: 1.6 });""",
    """      this.colliders.push({ x: TX - MW + 3.2, z: TZ - MD + 3.0, r: 0.6 });
      this.colliders.push({ x: TX + MW - 3.4, z: TZ + MD - 3.2, r: 1.6 });
      this.colliders.push({ x: TX + MW - 6.0, z: TZ + MD - 4.2, hw: 1.0, hd: 0.5 });   // crates""",
    'market crates')


# ======================================================= 6. gap-toothed merlons
sub("""          const mc = Math.max(1, Math.round((L / n) / 1.7));
          for (let mI = 0; mI < mc; mI++) {
            const f = (mI + 0.5) / mc - 0.5;
            kput(new T.BoxGeometry(KWT + 0.34, 1.3, 1.0),
                 px + Math.sin(ang) * (L / n) * f, kTop + 0.65, pz + Math.cos(ang) * (L / n) * f, 0, ang, 0, C_STONED);
          }""",
    """          const mc = Math.max(1, Math.round((L / n) / 1.7));
          for (let mI = 0; mI < mc; mI++) {
            const f = (mI + 0.5) / mc - 0.5;
            // A castle nobody has repaired in a long time. Merlons are knocked
            // out on a fixed pattern and some of the survivors sit askew, so
            // the battlements read gap-toothed instead of machined. Fixed, not
            // random: the world has to build the same way on every client.
            const key = (Math.round(px) * 7 + Math.round(pz) * 13 + mI * 5) % 11;
            if (key === 0 || key === 6) continue;                       // knocked out
            const lean = key === 3 ? 0.13 : key === 8 ? -0.1 : 0;
            const drop = key === 3 || key === 8 ? -0.28 : 0;
            kput(new T.BoxGeometry(KWT + 0.34, 1.3 + (key === 4 ? -0.45 : 0), 1.0),
                 px + Math.sin(ang) * (L / n) * f, kTop + 0.65 + drop, pz + Math.cos(ang) * (L / n) * f,
                 lean, ang, lean * 0.6, C_STONED);
          }""",
    'ruined merlons')


# ============================== 7. the courtyard floor, the cobbles and the props
OLD_FLOOR_START = src.index("      // a ramp of worn flags up to the gateway, laid flat on the ground")
OLD_FLOOR_END = src.index("      // the throne, against the back wall, so the King stands in front of it on")
OLD_FLOOR = src[OLD_FLOOR_START:OLD_FLOOR_END]

NEW_FLOOR = """      // Packed earth under the whole of it. Flagstones laid edge to edge still
      // show a seam, and a seam over grass reads as a hole in the floor. This
      // is what the gaps are supposed to show.
      const EARTH = new T.Color(0x4a4030);
      for (let ix = -4; ix <= 4; ix++) for (let iz = -4; iz <= 4; iz++) {
        const ex = KX + ix * 5.0, ez = KZ + iz * 5.0;
        if (Math.abs(ex - KX) > KH || Math.abs(ez - KZ) > KH) continue;
        kput(new T.PlaneGeometry(5.4, 5.4), ex, this.groundY(ex, ez) + 0.02, ez, -Math.PI / 2, 0, 0, EARTH);
      }

      // ---- the approach: a cobbled road out of the gate, and what is left of
      // whoever used to trade on it.
      //
      // It was plain grass right up to the gatehouse. A castle has a road to
      // it. The cobbles run 40m south and the world's dressing is kept off
      // them by keepGround(), so nothing grows through.
      for (let ri = 0; ri < 16; ri++) {
        const rz = gz + 1.5 + ri * 2.6;
        kput(new T.PlaneGeometry(15.5, 3.0), KX, this.groundY(KX, rz) + 0.02, rz, -Math.PI / 2, 0, 0, EARTH);
        for (let ci = -2; ci <= 2; ci++) {
          const rx = KX + ci * 2.6 + ((ri % 2) ? 1.3 : 0);
          // the middle of a road stays laid; only the verge goes to pieces
          if (Math.abs(ci) === 2 && (ri % 3) === 0) continue;
          kput(new T.PlaneGeometry(2.75, 2.75), rx, this.groundY(rx, rz) + 0.05, rz,
               -Math.PI / 2, Math.abs(ci) === 2 ? ((ri * 5) % 3) * 0.07 : 0, 0,
               (ri + ci) % 3 === 0 ? C_STONE : C_STONED);
        }
      }
      // a verge of set kerb stones so the road has an edge
      for (let ri = 0; ri < 14; ri++) {
        const rz = gz + 3.0 + ri * 2.8;
        for (const s of [-1, 1]) {
          const rx = KX + s * 7.0;
          kput(new T.BoxGeometry(0.7, 0.42, 2.4), rx, this.groundY(rx, rz) + 0.16, rz, 0, 0, 0, C_STONE);
        }
      }

      // ---- the fruit stands.
      //
      // Empty, tipped over and long abandoned. A market outside the gate is
      // the fastest way to say somebody lived here before the King took it.
      const STANDS = [[-10.5, 9, 0.5], [10.5, 15, -0.4], [-10.5, 25, 0.2], [10.5, 33, 0.9]];
      for (let si = 0; si < STANDS.length; si++) {
        const [sxo, szo, syaw] = STANDS[si];
        const sx2 = KX + sxo, sz2 = gz + szo, sy2 = this.groundY(sx2, sz2);
        const lean = si === 1 ? 0.16 : si === 3 ? -0.12 : 0;    // two have given up
        // trestle: four legs, a bench, a back board, and a broken awning frame
        for (const ox of [-1.5, 1.5]) for (const oz of [-0.6, 0.6]) {
          kput(new T.BoxGeometry(0.16, 1.0, 0.16), sx2 + ox, sy2 + 0.5, sz2 + oz, lean, syaw, 0, C_WOODD);
        }
        kput(new T.BoxGeometry(3.5, 0.16, 1.5), sx2, sy2 + 1.03, sz2, lean, syaw, 0, C_WOOD);
        kput(new T.BoxGeometry(3.5, 0.5, 0.12), sx2, sy2 + 1.3, sz2 - 0.7, lean, syaw, 0, C_WOODD);
        if (si !== 1) {
          for (const ox of [-1.6, 1.6]) {
            kput(new T.BoxGeometry(0.12, 1.9, 0.12), sx2 + ox, sy2 + 1.95, sz2 - 0.5, 0, syaw, 0, C_WOODD);
          }
          // half the awning bar is gone on the ones still standing
          kput(new T.BoxGeometry(si === 3 ? 1.8 : 3.3, 0.12, 0.12), sx2 + (si === 3 ? -0.7 : 0), sy2 + 2.88, sz2 - 0.5, 0, syaw, 0, C_WOODD);
        }
        // baskets: one on the bench, two tipped on the ground, all empty
        const bask = (bx3, by3, bz3, tip) => {
          kput(new T.CylinderGeometry(0.42, 0.3, 0.5, 9, 1, true), bx3, by3 + 0.25, bz3, tip, syaw, 0, C_THATCHD);
          kput(new T.CylinderGeometry(0.44, 0.44, 0.07, 9), bx3, by3 + 0.5, bz3, tip, syaw, 0, C_THATCH);
        };
        bask(sx2 - 0.9, sy2 + 1.1, sz2, 0);
        bask(sx2 + 1.9 * (si % 2 ? -1 : 1), sy2 + 0.32, sz2 + 1.4, Math.PI / 2);
        bask(sx2 - 2.2, sy2 + 0.3, sz2 - 1.1, Math.PI / 2 + 0.4);
        this.colliders.push({ x: sx2, z: sz2, hw: 1.9, hd: 0.85 });
      }

      // ---- the courtyard floor.
      //
      // The first cut laid CircleGeometry r2.5 on a 4.2m grid, which leaves a
      // gap between every disc: what you actually saw was grass and the world's
      // clutter growing through a castle. This is a continuous floor, tiles
      // overlapping on a 2.8m grid, each one sampled onto its OWN ground height
      // so it follows the 2.4m of relief across the site instead of hovering at
      // one end. Merged into the keep mesh, so the whole floor is free.
      const FIN = KH - KWT / 2 - 0.4;
      for (let ix = -7; ix <= 7; ix++) for (let iz = -7; iz <= 7; iz++) {
        const fx2 = KX + ix * 2.8, fz2 = KZ + iz * 2.8;
        if (Math.abs(fx2 - KX) > FIN || Math.abs(fz2 - KZ) > FIN) continue;
        const wear = (ix * 7 + iz * 11) % 5;
        kput(new T.PlaneGeometry(2.95, 2.95), fx2, this.groundY(fx2, fz2) + 0.05, fz2,
             -Math.PI / 2, ((ix * 3 + iz * 5) % 4) * 0.06, 0,
             wear === 0 ? C_STONE : wear === 3 ? new T.Color(0x4a4a3e) : C_STONED);
      }
      // a worn track from the gate to the throne, so the floor has a direction
      for (let ti = 0; ti < 12; ti++) {
        const tz2 = KZ + KH - 3.5 - ti * 2.6;
        kput(new T.PlaneGeometry(4.4, 2.7), KX, this.groundY(KX, tz2) + 0.07, tz2,
             -Math.PI / 2, 0, 0, new T.Color(0x5c5647));
      }

      // ---- the entrance, held.
      //
      // Kevin: put some fencing along the inside entrance so it fills out. A
      // timber palisade down the inside of the south wall either side of the
      // gate, two barricades angled across the way in, and a spear rack.
      const pz0 = KZ + KH - 3.2;
      for (const s of [-1, 1]) {
        for (let pi = 0; pi < 5; pi++) {
          const px2 = KX + s * (5.5 + pi * 2.6);
          if (Math.abs(px2 - KX) > KH - 4) continue;
          const py2 = this.groundY(px2, pz0);
          kput(new T.BoxGeometry(0.26, 2.4, 0.26), px2, py2 + 1.1, pz0, 0, 0, 0, C_WOODD);
          kput(new T.ConeGeometry(0.19, 0.4, 4), px2, py2 + 2.5, pz0, 0, 0.6, 0, C_WOODD);
          if (pi < 4) {
            for (const ry3 of [0.85, 1.75]) {
              kput(new T.BoxGeometry(2.6, 0.14, 0.1), px2 + s * 1.3, py2 + ry3, pz0, 0, 0, 0, C_WOOD);
            }
          }
        }
        this.colliders.push({ x: KX + s * 11.5, z: pz0, hw: 6.5, hd: 0.3 });
      }
      // barricades angled across the gateway, inside it
      for (const s of [-1, 1]) {
        const bx3 = KX + s * 4.2, bz3 = KZ + KH - 7.5, by3 = this.groundY(bx3, bz3);
        for (const c3 of [-1, 1]) {
          kput(new T.BoxGeometry(0.22, 2.6, 0.22), bx3 + c3 * 0.9, by3 + 0.9, bz3, s * 0.5, 0, c3 * 0.55, C_WOODD);
        }
        kput(new T.BoxGeometry(3.0, 0.18, 0.18), bx3, by3 + 1.5, bz3, 0, s * -0.3, 0, C_WOOD);
        kput(new T.BoxGeometry(3.0, 0.18, 0.18), bx3, by3 + 0.8, bz3, 0, s * -0.3, 0, C_WOOD);
        this.colliders.push({ x: bx3, z: bz3, hw: 1.5, hd: 0.4 });
      }
      // a spear rack against the palisade
      {
        const rx2 = KX + 9.5, rz2 = pz0 - 1.4, ry2 = this.groundY(rx2, rz2);
        kput(new T.BoxGeometry(2.6, 0.18, 0.5), rx2, ry2 + 1.5, rz2, 0, 0, 0, C_WOODD);
        kput(new T.BoxGeometry(2.6, 0.18, 0.5), rx2, ry2 + 0.25, rz2, 0, 0, 0, C_WOODD);
        for (let si2 = 0; si2 < 5; si2++) {
          if (si2 === 2) continue;                              // one is missing
          const sx3 = rx2 - 1.0 + si2 * 0.5;
          kput(new T.CylinderGeometry(0.05, 0.05, 2.6, 5), sx3, ry2 + 1.3, rz2, 0.06, 0, 0.04, C_WOOD);
          kput(new T.ConeGeometry(0.09, 0.34, 4), sx3, ry2 + 2.7, rz2, 0, 0.7, 0, C_STONED);
        }
        this.colliders.push({ x: rx2, z: rz2, hw: 1.4, hd: 0.35 });
      }

"""
edits.append((OLD_FLOOR, NEW_FLOOR, 'courtyard floor, cobbles, stands, entrance'))


# ============================ 8. what is left in the bailey, and green braziers
OLD_RUBBLE_START = src.index("      // fallen pillars and rubble: a keep with a dead king in it is not tidy")
OLD_RUBBLE_END = src.index("      // Solid walls. The gateway is the only way in, and after the resolver's")
OLD_RUBBLE = src[OLD_RUBBLE_START:OLD_RUBBLE_END]

NEW_RUBBLE = """      // ---- what is left in the bailey.
      //
      // Seven fallen pillars and twenty-one rubble stones used to be scattered
      // through the middle of this, which is exactly where the fight happens.
      // Kevin could not walk round it and it did not read as anything. What is
      // here now is deliberate, against the walls, and out of the arena: two
      // toppled columns, a broken cart, a stack of crates that has given way,
      // and dead ivy up the back wall. All of it solid.
      const PROPS = [
        ['column', -KH + 6.0, -6.0, 1.1],
        ['column', KH - 6.5, 2.0, -0.5],
        ['cart', -KH + 7.5, 9.0, 0.35],
        ['crates', KH - 7.0, -9.5, -0.25]
      ];
      for (const [kind, ox, oz, yaw] of PROPS) {
        const px2 = KX + ox, pz2 = KZ + oz, py2 = this.groundY(px2, pz2);
        if (kind === 'column') {
          // a drum-built column that has come down in three pieces
          kput(new T.CylinderGeometry(0.8, 0.8, 3.4, 9), px2, py2 + 0.8, pz2, Math.PI / 2, yaw, 0, C_STONE);
          kput(new T.CylinderGeometry(0.78, 0.78, 1.6, 9), px2 + Math.sin(yaw) * 2.7, py2 + 0.78, pz2 + Math.cos(yaw) * 2.7, Math.PI / 2, yaw + 0.3, 0, C_STONE);
          kput(new T.BoxGeometry(2.0, 0.5, 2.0), px2 - Math.sin(yaw) * 2.4, py2 + 0.25, pz2 - Math.cos(yaw) * 2.4, 0, yaw + 0.5, 0, C_STONED);
          this.colliders.push({ x: px2, z: pz2, r: 2.2 });
        } else if (kind === 'cart') {
          kput(new T.BoxGeometry(3.2, 0.9, 1.8), px2, py2 + 0.75, pz2, 0, yaw, 0.12, C_WOODD);
          kput(new T.BoxGeometry(3.0, 0.14, 1.6), px2, py2 + 1.2, pz2, 0, yaw, 0.12, C_WOOD);
          for (const s of [-1, 1]) {
            kput(new T.CylinderGeometry(0.85, 0.85, 0.2, 10), px2 + Math.cos(yaw) * s * 1.1, py2 + 0.6, pz2 - Math.sin(yaw) * s * 1.1, 0, 0, Math.PI / 2 + (s > 0 ? 0.5 : 0), C_WOOD);
          }
          kput(new T.BoxGeometry(0.18, 0.18, 2.4), px2 + Math.sin(yaw) * 2.4, py2 + 0.5, pz2 + Math.cos(yaw) * 2.4, 0.4, yaw, 0, C_WOODD);
          this.colliders.push({ x: px2, z: pz2, r: 1.9 });
        } else {
          for (let ci = 0; ci < 5; ci++) {
            const lean = ci >= 3 ? 0.4 : 0;
            kput(new T.BoxGeometry(0.9, 0.9, 0.9),
                 px2 + (ci % 2) * 0.95 + (ci >= 3 ? 1.3 : 0), py2 + 0.45 + Math.min(ci, 2) * 0.92, pz2 + (ci >= 3 ? 0.8 : 0),
                 lean, yaw + ci * 0.2, lean * 0.5, C_WOOD);
          }
          this.colliders.push({ x: px2 + 0.5, z: pz2 + 0.3, hw: 1.5, hd: 1.1 });
        }
      }
      // dead ivy up the inside of the back wall
      for (let vi = 0; vi < 9; vi++) {
        const vx = KX - 14 + vi * 3.5, vz = KZ - KH + KWT / 2 + 0.15;
        const vh = 3.2 + ((vi * 7) % 5) * 0.7;
        kput(new T.BoxGeometry(1.3, vh, 0.14), vx, this.groundY(vx, vz) + vh / 2, vz, 0, 0, 0, new T.Color(0x35301f));
        kput(new T.BoxGeometry(0.7, vh * 0.6, 0.16), vx + 0.7, this.groundY(vx, vz) + vh * 0.34, vz, 0, 0, 0, new T.Color(0x2a2718));
      }
      const km = new T.Mesh(this.mergeGeos(K), townMat);
      km.castShadow = true; km.receiveShadow = true;
      S.add(km);

      // ---- fell fire.
      //
      // Kevin: the King is green, so make the fire green. These use the same
      // shader flame the bridge torches do, with the `fell` palette: pale green
      // at the core, green through the body, deep green where it tears apart.
      // Four braziers, moved out of the middle to the wall line so they light
      // the fight without standing in it. Two carry a real light.
      const fellM = this.torchFlameMat(true);
      for (let bI = 0; bI < 4; bI++) {
        const bx2 = KX + (bI % 2 ? 1 : -1) * 12.5, bz2 = KZ + (bI < 2 ? -1 : 1) * 12.5;
        const bg = new T.Group();
        const stem = new T.Mesh(new T.CylinderGeometry(0.3, 0.5, 2.1, 8), stoneD);
        stem.position.y = 1.05; stem.castShadow = true; bg.add(stem);
        for (const fs of [0, 2.1, 4.2]) {
          const foot = new T.Mesh(new T.BoxGeometry(0.34, 0.22, 1.5), stoneD);
          foot.position.set(Math.sin(fs) * 0.5, 0.11, Math.cos(fs) * 0.5);
          foot.rotation.y = fs; bg.add(foot);
        }
        const bowl = new T.Mesh(new T.CylinderGeometry(1.0, 0.52, 0.85, 10), stoneD);
        bowl.position.y = 2.4; bowl.castShadow = true; bg.add(bowl);
        const coals = new T.Mesh(new T.IcosahedronGeometry(0.72, 0), new T.MeshStandardMaterial({
          color: 0x6fe04a, emissive: 0x4fd02a, emissiveIntensity: 2.4, roughness: 0.5, flatShading: true }));
        coals.position.y = 2.72; coals.scale.set(1, 0.55, 1); bg.add(coals);
        // the flame itself, seeded off its own position so the four do not
        // dance in lockstep
        const fl = new T.Mesh(new T.ConeGeometry(0.78, 3.0, 10, 7), fellM);
        fl.position.y = 4.3; bg.add(fl);
        // a second, tighter tongue inside it, so the core reads solid rather
        // than as one thin translucent cone
        const fl2 = new T.Mesh(new T.ConeGeometry(0.42, 1.9, 8, 6), fellM);
        fl2.position.y = 3.7; bg.add(fl2);
        if (bI % 2 === 0) {
          const pl = new T.PointLight(0x7fef4a, 3.6, 34, 2);
          pl.position.y = 3.4; bg.add(pl); (this.decorLights = this.decorLights || []).push(pl);
        }
        bg.position.set(bx2, this.groundY(bx2, bz2), bz2); S.add(bg);
        this.colliders.push({ x: bx2, z: bz2, r: 1.2 });
      }

"""
edits.append((OLD_RUBBLE, NEW_RUBBLE, 'bailey props and fell braziers'))


out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
