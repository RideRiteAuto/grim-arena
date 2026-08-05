#!/usr/bin/env python3
"""Phase 2, part 4: the Heartlands bestiary.

Wild boar, giant rat, young goblin and hares, spawned at deterministic points
across Heartlands ground from the same seeded generator the dressing uses.

Two deliberate choices worth stating.

First, the new quads are a NEW builder rather than parameters bolted onto
makeWolfBeast. The wolf is a shipped reference implementation and the deer
already leans on it; threading proportion multipliers through it to make a boar
would put every existing wolf one typo away from a regression. makeQuadVariant
copies its structure and honours the same `qr` contract, which is exactly what
the handoff asks for.

Second, zone creatures are spawned ONCE at world load into this.npcs, not
streamed per chunk. Monster state syncs by array index, so a roster that grows
and shrinks as you walk would desync every client against every other. A fixed
roster with the existing distance culling is what the plan's "zone total capped
with distance-based activation" describes anyway.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


QUAD = r"""
  // ---- quad variants -----------------------------------------------------
  // Same skeleton and the same `qr` contract as the wolf, with the proportions
  // in a table. A boar is a wedge with its weight over the shoulders; a giant
  // rat is low, long and thin; a hare is small with big ears and long back
  // legs. Anything that reads as a different animal is in the profile, not in
  // new code.
  QUAD_PROFILE(name) {
    const P = {
      boar: {
        len: 1.0, girth: 1.45, tall: 0.62, legLen: 0.72, neckLen: 0.55, neckPitch: -0.15,
        headScale: 1.15, snout: 1.5, earScale: 0.55, tailLen: 0.35, tailTuft: 0.7,
        fur: 0x5a4a38, belly: 0x8a7658, eye: 0xd8a03c, tusks: true, bristles: true, headBase: 0.15
      },
      rat: {
        len: 1.15, girth: 0.80, tall: 0.44, legLen: 0.52, neckLen: 0.42, neckPitch: -0.35,
        headScale: 0.92, snout: 1.7, earScale: 1.7, tailLen: 1.5, tailTuft: 0,
        fur: 0x6b6058, belly: 0xa39684, eye: 0xc4452e, naked_tail: true, headBase: 0.35
      },
      hare: {
        len: 0.62, girth: 0.70, tall: 0.44, legLen: 0.46, neckLen: 0.3, neckPitch: -0.5,
        headScale: 0.8, snout: 0.9, earScale: 3.0, tailLen: 0.12, tailTuft: 1.2,
        fur: 0x9a8b74, belly: 0xd8cfba, eye: 0x2a1a12, headBase: 0.4
      }
    };
    return P[name] || P.boar;
  }

  makeQuadVariant(cfg) {
    const T = this.T;
    const P = this.QUAD_PROFILE(cfg.profile);
    const sc = cfg.scale || 1;
    const fur = this.furTex('#ddd8cb', '60,56,48');
    const matBody = new T.MeshStandardMaterial({ vertexColors: true, map: fur, roughness: 0.95, flatShading: true });
    const matFur = new T.MeshStandardMaterial({ color: P.fur, map: fur, roughness: 0.95, flatShading: true });
    const matDark = new T.MeshStandardMaterial({ color: 0x2f2a24, roughness: 0.95, flatShading: true });
    const matPale = new T.MeshStandardMaterial({ color: 0xd8d0bc, roughness: 0.8, flatShading: true });
    const TOP = P.fur, BELLY = P.belly;
    const L = P.len, G = P.girth;

    const root = new T.Group();
    const body = new T.Group(); body.position.y = (0.68 * P.tall / 0.62) * sc; root.add(body);
    // torso: tail end to chest. A boar's deepest point is the shoulder, a rat's
    // is the middle, which is most of what tells them apart in silhouette.
    const hump = cfg.profile === 'boar' ? 1.22 : 0.98;
    body.add(this.loftMesh([
      { z: -0.58 * L, w: 0.125 * G, h: 0.165 * G, y: 0.05 },
      { z: -0.28 * L, w: 0.15 * G, h: 0.20 * G, y: 0.05 },
      { z: 0.08 * L, w: 0.165 * G, h: 0.25 * G, y: 0.02 },
      { z: 0.34 * L, w: 0.17 * G * hump, h: 0.285 * G * hump, y: 0.0 },
      { z: 0.5 * L, w: 0.15 * G * hump, h: 0.26 * G * hump, y: 0.05 },
      { z: 0.58 * L, w: 0.12 * G, h: 0.2 * G, y: 0.07 }
    ], 10, TOP, BELLY, matBody));

    const neckG = new T.Group();
    neckG.position.set(0, 0.14 * G, 0.56 * L); neckG.rotation.x = P.neckPitch - 0.45; body.add(neckG);
    const nl = P.neckLen;
    neckG.add(this.loftMesh([
      { z: 0, w: 0.13 * G, h: 0.175 * G, y: 0 },
      { z: 0.16 * nl, w: 0.115 * G, h: 0.15 * G, y: 0.05 },
      { z: 0.3 * nl, w: 0.10 * G, h: 0.125 * G, y: 0.10 }
    ], 8, TOP, BELLY, matBody));

    const head = new T.Group();
    head.position.set(0, 0.10, 0.30 * nl); head.rotation.x = P.headBase; neckG.add(head);
    const H = P.headScale, SN = P.snout;
    head.add(this.loftMesh([
      { z: -0.07 * H, w: 0.12 * H, h: 0.12 * H, y: 0 },
      { z: 0.08 * H, w: 0.11 * H, h: 0.105 * H, y: 0.005 },
      { z: 0.17 * H * SN, w: 0.062 * H, h: 0.058 * H, y: -0.025 },
      { z: 0.34 * H * SN, w: 0.045 * H, h: 0.04 * H, y: -0.05 }
    ], 8, TOP, BELLY, matBody));
    const nose = new T.Mesh(new T.BoxGeometry(0.06 * H, 0.045 * H, 0.045 * H), matDark);
    nose.position.set(0, -0.04, 0.35 * H * SN); head.add(nose);

    const jaw = new T.Group(); jaw.position.set(0, -0.06 * H, 0.11 * H); head.add(jaw);
    jaw.add(this.loftMesh([
      { z: -0.02, w: 0.052 * H, h: 0.03 * H, y: 0 },
      { z: 0.2 * SN, w: 0.032 * H, h: 0.02 * H, y: -0.002 }
    ], 6, TOP, BELLY, matBody));
    const teeth = new T.Mesh(new T.BoxGeometry(0.048 * H, 0.009, 0.08), matPale);
    teeth.position.set(0, 0.012, 0.1 * SN); jaw.add(teeth);

    // A boar without tusks is a pig. They are the read on the charge.
    if (P.tusks) {
      for (const sd of [-1, 1]) {
        const tk = new T.Mesh(new T.ConeGeometry(0.022 * H, 0.17 * H, 4), matPale);
        tk.position.set(sd * 0.055 * H, -0.03, 0.30 * H * SN);
        tk.rotation.set(-0.9, 0, sd * 0.35);
        head.add(tk);
      }
    }
    const ears = [];
    for (const sd of [-1, 1]) {
      const e = new T.Group(); e.position.set(sd * 0.07 * H, 0.115 * H, -0.045);
      const cone = new T.Mesh(new T.ConeGeometry(0.045 * H * P.earScale, 0.13 * H * P.earScale, 4), matFur);
      cone.rotation.y = Math.PI / 4; cone.position.y = 0.05 * P.earScale; cone.castShadow = true;
      e.add(cone); e.rotation.z = sd * -0.18; head.add(e); ears.push(e);
    }
    for (const sd of [-1, 1]) {
      const eye = new T.Mesh(new T.SphereGeometry(0.021 * H, 8, 6),
        new T.MeshStandardMaterial({ color: P.eye, emissive: 0x3a2408, roughness: 0.3 }));
      eye.position.set(sd * 0.068 * H, 0.028 * H, 0.13 * H); head.add(eye);
    }
    // bristled ridge along a boar's spine
    if (P.bristles) {
      for (let i = 0; i < 6; i++) {
        const br = new T.Mesh(new T.ConeGeometry(0.02 * G, 0.13 * G, 3), matDark);
        br.position.set(0, 0.26 * G, (0.42 - i * 0.16) * L); br.rotation.x = -0.35;
        body.add(br);
      }
    }

    // tail: the rat's is long, naked and segmented; everyone else gets fur
    const tailRoot = new T.Group(); tailRoot.position.set(0, 0.1 * G, -0.56 * L); body.add(tailRoot);
    let tp = tailRoot; const tailSegs = [tailRoot];
    const tsegs = P.naked_tail ? 4 : 2;
    for (let i = 0; i < tsegs; i++) {
      const w0 = (0.055 - i * 0.010) * (P.naked_tail ? 0.55 : 1) * G;
      const w1 = (0.045 - i * 0.011) * (P.naked_tail ? 0.5 : 1) * G;
      const seg = this.loftMesh([
        { z: 0, w: w0, h: w0, y: 0 },
        { z: -0.2 * P.tailLen, w: w1, h: w1, y: 0 }
      ], 6, P.naked_tail ? 0xa08878 : TOP, P.naked_tail ? 0xc8b0a0 : BELLY, matBody);
      tp.add(seg);
      const nxt = new T.Group(); nxt.position.z = -0.175 * P.tailLen; tp.add(nxt); tp = nxt; tailSegs.push(nxt);
    }
    if (P.tailTuft > 0) {
      const tuft = new T.Mesh(new T.ConeGeometry(0.05 * G * P.tailTuft, 0.16 * G * P.tailTuft, 6), matDark);
      tuft.rotation.x = Math.PI / 2 + 0.15; tuft.position.z = -0.07; tuft.castShadow = true; tp.add(tuft);
    }

    const legs = [];
    const mkLeg = (x, z, front) => {
      const hip = new T.Group(); hip.position.set(x, -0.02, z); body.add(hip);
      const up = this.loftMesh([
        { z: 0, w: 0.07 * G, h: 0.09 * G, y: 0 },
        { z: -0.32 * P.legLen / 0.62, w: 0.042 * G, h: 0.05 * G, y: 0 }
      ], 6, TOP, BELLY, matBody);
      up.rotation.x = -Math.PI / 2; hip.add(up);
      const knee = new T.Group(); knee.position.y = -0.32 * P.legLen / 0.62; hip.add(knee);
      const lo = this.loftMesh([
        { z: 0, w: 0.04 * G, h: 0.048 * G, y: 0 },
        { z: -0.3 * P.legLen / 0.62, w: 0.028 * G, h: 0.033 * G, y: 0 }
      ], 6, TOP, BELLY, matBody);
      lo.rotation.x = -Math.PI / 2; knee.add(lo);
      const paw = new T.Mesh(new T.BoxGeometry(0.075 * G, 0.045, 0.11), matDark);
      paw.position.set(0, -0.315 * P.legLen / 0.62, 0.02); paw.castShadow = true; knee.add(paw);
      legs.push({ hip, knee, front });
    };
    mkLeg(-0.13 * G, 0.42 * L, true); mkLeg(0.13 * G, 0.42 * L, true);
    mkLeg(-0.115 * G, -0.42 * L, false); mkLeg(0.115 * G, -0.42 * L, false);

    root.scale.setScalar(sc);
    root.traverse(o => { if (o.isMesh) o.castShadow = true; });

    const empty = () => new T.Group();
    const hand = empty(), handL = empty();
    const ward = new T.Mesh(new T.SphereGeometry(0.9 * sc, 10, 8),
      new T.MeshBasicMaterial({ color: 0x6fdf8f, transparent: true, opacity: 0.12, side: T.DoubleSide }));
    ward.position.y = 0.9 * sc; ward.visible = false; root.add(ward);
    const frostShell = new T.Mesh(new T.IcosahedronGeometry(0.95 * sc, 1),
      new T.MeshBasicMaterial({ color: 0x9fdcff, transparent: true, opacity: 0.3, wireframe: true }));
    frostShell.position.y = 0.85 * sc; frostShell.visible = false; root.add(frostShell);
    const orb = new T.Mesh(new T.IcosahedronGeometry(0.05, 0),
      new T.MeshStandardMaterial({ color: 0x9ad8ff })); orb.visible = false; root.add(orb);

    return {
      g: root, body: body, isMe: false, beast: true,
      mats: { steel: matFur, cloth: matFur, trim: matFur },
      parts: { upper: body, torso: null, head: head, armR: empty(), armL: empty(),
               legR: empty(), legL: empty(), hand, handL, sword: empty(), staff: empty(),
               bow: empty(), shield: empty(), ward, orb, frostShell, crest: empty(),
               capePiv: empty(), bladeTip: empty() },
      qr: { legs, neckG, head, jaw, ears, tailSegs, body, baseY: body.position.y },
      headBase: P.headBase,
      pos: new T.Vector3(), vel: new T.Vector3(), want: new T.Vector3(),
      yaw: 0, vyaw: 0, phase: 0, moveAmt: 0, bob: 0,
      guardBreak: 0, guardFlash: 0,
      state: 'idle', st: 0, act: null, hitDone: false, burst: 0, burstT: 0,
      blocking: false, blockAge: 99, _wasBlocking: false, guardT: 0, frozen: 0, iframe: 0, stagger: 0,
      charge: 0, drawing: false, combo: 0, comboT: 0, chain: 0, chainT: 0, freezeCd: 0, dodgeCd: 0,
      lungeT: 0, lungeMax: 1, lungePow: 0, lungeDir: new T.Vector3(),
      target: new T.Vector3(), tyaw: 0, aiT: 0, aiStrafe: 1, aiSwitch: 999
    };
  }

  // ---- deterministic zone roster ------------------------------------------
  // Spawn points come off the same seeded hash the dressing uses, walked over a
  // grid of chunks around the zone, so every client puts the same boar in the
  // same field. Filtered through dressBlocked, which already enforces the water
  // wall, the road corridors and the town exclusion.
  zoneSpawnPoints(zone, n, salt) {
    const out = [];
    const CH = 64;
    let ring = 1;
    while (out.length < n && ring < 26) {
      for (let dx = -ring; dx <= ring && out.length < n; dx++) {
        for (let dz = -ring; dz <= ring && out.length < n; dz++) {
          if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;
          const rnd = grimRnd(grimSeed(dx, dz, 'spawn:' + zone + ':' + salt));
          if (rnd() > 0.42) continue;                 // most chunks hold nothing
          const x = dx * CH + rnd() * CH, z = dz * CH + rnd() * CH;
          if (this.zoneAt(x, z) !== zone) continue;
          if (this.dressBlocked(x, z)) continue;
          out.push([x, z]);
        }
      }
      ring++;
    }
    return out;
  }

  buildZoneCreatures(beast, foe) {
    const SP = GRIM_RULES.ZONE_SPAWNS.HEARTLANDS;
    if (!SP) return;
    const cap = GRIM_RULES.ZONE_MONSTER_CAP.HEARTLANDS || 30;
    let spawned = 0;
    for (const entry of SP) {
      const B = GRIM_RULES.BESTIARY[entry.of];
      if (!B) continue;
      const isMonster = !B.passive;
      const want = entry.count;
      const pts = this.zoneSpawnPoints('HEARTLANDS', want, entry.of);
      for (let i = 0; i < pts.length; i++) {
        if (isMonster && spawned >= cap) break;
        const [x, z] = pts[i];
        const extra = {
          max: B.hp, xp: B.xp, dmgScale: B.dmgScale, spdScale: B.spdScale,
          aiD: B.aiD, aggroR: B.aggroR, lockWeapon: 9,
          sig: B.sig || null, sigCd: 2 + (i % 5), zoneSpecies: entry.of, homeR: entry.homeR || 26
        };
        if (B.passive) { extra.passive = true; extra.skittish = !!B.skittish; extra.dmgScale = 0; }
        else { extra.brawler = true; }
        Object.assign(extra, B.tags || {});
        let e;
        if (B.rig === 'goblin') {
          e = foe(B.name, { steel: 0x6f7a4a, cloth: 0x4a5a34, trim: 0x8a7a3a }, extra, x, z);
          e.goblin = true;
        } else {
          e = beast(B.name, { profile: B.profile, quadVariant: true, scale: B.profile === 'hare' ? 0.75 : 1.15 }, extra, x, z);
        }
        if (isMonster) spawned++;
      }
    }
    this._zoneRoster = spawned;
  }
"""

sub("  makeBeast(cfg) {\n"
    "    if (cfg.wolfModel) return this.makeWolfBeast(cfg);\n"
    "    if (cfg.deerModel) return this.makeDeerBeast(cfg);",
    QUAD +
    "\n  makeBeast(cfg) {\n"
    "    if (cfg.quadVariant) return this.makeQuadVariant(cfg);\n"
    "    if (cfg.wolfModel) return this.makeWolfBeast(cfg);\n"
    "    if (cfg.deerModel) return this.makeDeerBeast(cfg);",
    'quad variant builder')

# Spawn the roster where the rest of the zone's inhabitants are made, so it uses
# the same beast() and foe() helpers and lands in this.npcs in a stable order.
sub(
    "    for (let i = 0; i < 5; i++) {\n"
    "      const a = rnd() * Math.PI * 2, rr = 20 + rnd() * 16;\n"
    "      foe('BANDIT', { steel: 0x6a6258, cloth: 0x4a2a2a, trim: 0x8a6a2a },",

    "    // The Heartlands roster. Deterministic points, so the same boar stands in\n"
    "    // the same field on every machine, which is what keeps monster state in\n"
    "    // sync when it travels by array index.\n"
    "    this.buildZoneCreatures(beast, foe);\n"
    "\n"
    "    for (let i = 0; i < 5; i++) {\n"
    "      const a = rnd() * Math.PI * 2, rr = 20 + rnd() * 16;\n"
    "      foe('BANDIT', { steel: 0x6a6258, cloth: 0x4a2a2a, trim: 0x8a6a2a },",
    'roster spawn call')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
