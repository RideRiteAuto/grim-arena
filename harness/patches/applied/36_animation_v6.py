#!/usr/bin/env python3
"""Patch 36: rig v6 (elbows and knees), the locomotion rebuild, the shield
carry, and the new bow.

Kevin's Aug 6 direction, in order:
  - the shield arm must BEND: out at the side, elbow near a right angle,
    fist at the grip behind the shield
  - idle/walk/run need to look professional: knees flexing in the stride,
    transitions, and feet that move when turning in place instead of the
    body spinning on planted feet
  - weapon-specific idles for sword+board, staff and bow
  - a from-scratch high-quality bow held correctly in the LEFT hand with an
    animated, drawable string

What ships:
  1. The v6 module: every limb split at a real joint. Both segments end in
     domes CENTERED on the joint pivot (nested spheres - the shoulder trick),
     so a right-angle bend cannot open a seam. New optional parts elbowR/L,
     kneeR/L; hand rides the forearm, shield rides the LEFT forearm, boots
     and greaves ride the shins. Old-rig bosses never see any of it - every
     game-side write is guarded on P.kneeR / P.elbowR.
  2. Gait: hip swing with knee flexion peaking mid-swing (stance leg near
     straight - that asymmetry is what reads as a stride), speed-scaled
     amplitudes, arm counter-swing with elbow follow-through.
  3. Turn-in-place: stationary yaw change drives alternating foot lifts
     instead of a statue-spin.
  4. Weapon idles: shield carry (the pose reviewed on the lab turntable),
     staff, bow. Blocking presents the same square-on guard, with the pose
     SOLVED from world-space targets in the lab and baked here as numbers.
  5. The bow: strung recurve, 1.35 tip to tip, riser + swept limbs + straight
     string between nocks with real brace height. Draw state anchors the
     string hand at the cheek (vector-solved eulers) and pulls the string
     into a V via P.bowSet.setDraw(charge); a nocked arrow shows while
     drawing. The fist counter-rotates the arm chain so the bow stays
     upright in every pose, with a slight archer's cant.

Anchors verified 1x each against the live bundle before writing.
"""
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'character.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

assert 'export function makeFighterModel(T, pal)' in mod, 'module entry point moved'
body = re.sub(r'^import \{[^}]*\} from \'\./grim-kit\.js\';\n', '', mod, flags=re.M)
assert 'grim-kit' not in body, 'import line did not come out'
body = re.sub(r'^export ', '', body, flags=re.M)
body = re.sub(r'\A// GRIM WORLD: the player character, v5\.\n(//.*\n)*', '', body)
body = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n'))

# ---------------------------------------------------------------------------
# 1. module swap, banner to tail
# ---------------------------------------------------------------------------
BANNER = '    // ---- v5 rig ------------------------------------------------------------'
TAIL = '    const model = makeFighterModel(T, pal);'
assert s.count(BANNER) == 1, 'v5 banner matched %d times' % s.count(BANNER)
assert s.count(TAIL) == 1, 'module tail matched %d times' % s.count(TAIL)
i = s.find(BANNER); j = s.find(TAIL)
assert i < j < i + 95000, 'banner and tail out of order'
NEW = BANNER.replace('v5 rig', 'v6 rig') + '''
    // Built from model-lab/character.js by harness/patches/36_animation_v6.py.
    // Do not hand-edit: change the lab module, review it on the turntable
    // (model-lab/character.html + harness/char-review.js), and rebuild.

''' + body + '\n\n'
s = s[:i] + NEW + s[j:]

# the parts map the game builds from `model.parts` must carry the new pieces.
# makeFighter's tail spreads model.parts directly? No - it destructures. Add
# the new parts to the destructure and the parts object.
OLD_DESTR = 'const upper = model.parts.upper, torso = model.parts.torso, head = model.parts.head,'
assert s.count(OLD_DESTR) == 1, 'parts destructure anchor matched %d times' % s.count(OLD_DESTR)
s = s.replace(OLD_DESTR, OLD_DESTR + '''
      elbowR = model.parts.elbowR, elbowL = model.parts.elbowL,
      kneeR = model.parts.kneeR, kneeL = model.parts.kneeL, bowSet = model.parts.bowSet,''')
OLD_PARTS = 'parts: { upper, torso, head, armR, armL, legR, legL, hand, handL, sword, staff, bow, backBow, shield, ward, orb, frostShell, crest, capePiv, bladeTip,'
assert s.count(OLD_PARTS) == 1, 'parts map anchor matched %d times' % s.count(OLD_PARTS)
s = s.replace(OLD_PARTS,
  'parts: { upper, torso, head, armR, armL, legR, legL, elbowR, elbowL, kneeR, kneeL, bowSet, hand, handL, sword, staff, bow, backBow, shield, ward, orb, frostShell, crest, capePiv, bladeTip,')

# ---------------------------------------------------------------------------
# 2. gait: knees in the stride
# ---------------------------------------------------------------------------
OLD_GAIT = """const sw = Math.sin(e.phase) * 0.62 * e.moveAmt;
    P.legR.rotation.x = sw; P.legL.rotation.x = -sw;
    if (P.backR) { P.backR.rotation.x = -sw; P.backL.rotation.x = sw; }"""
assert s.count(OLD_GAIT) == 1, 'gait anchor matched %d times' % s.count(OLD_GAIT)
s = s.replace(OLD_GAIT, """const sw = Math.sin(e.phase) * 0.62 * e.moveAmt;
    const spd = Math.min(1, e.moveAmt || 0);
    if (P.kneeR) {
      // A stride, not scissors: the swing leg's knee flexes hard while the
      // stance leg stays near straight. Phase offset -0.65 puts peak flexion
      // mid-swing, where a real leg tucks to clear the ground.
      const gA = Math.min(1, spd * 3);
      const hip = Math.sin(e.phase) * (0.42 + 0.28 * spd) * gA;
      P.legR.rotation.x = hip; P.legL.rotation.x = -hip;
      const kMax = (0.85 + 0.80 * spd) * gA;
      P.kneeR.rotation.x = 0.06 + kMax * Math.pow(Math.max(0, Math.sin(e.phase - 0.65)), 1.4);
      P.kneeL.rotation.x = 0.06 + kMax * Math.pow(Math.max(0, Math.sin(e.phase - 0.65 + Math.PI)), 1.4);
    } else { P.legR.rotation.x = sw; P.legL.rotation.x = -sw; }
    if (P.backR) { P.backR.rotation.x = -sw; P.backL.rotation.x = sw; }
    // Turn-in-place: stationary but rotating, the feet SHUFFLE - small
    // alternating lifts driven by how fast the view is swinging - instead of
    // the statue-spin Kevin called out.
    if (P.kneeR && spd < 0.1) {
      const vy = e.vyaw || 0;
      const dY = vy - (e._pvY === undefined ? vy : e._pvY);
      e._shufA = Math.max(0, Math.min(1, (e._shufA || 0) + (Math.abs(dY) > 0.004 ? 0.3 : -0.08)));
      if (e._shufA > 0.02) {
        e._shufPh = (e._shufPh || 0) + Math.abs(dY) * 3.2 + dt * 1.5 * e._shufA;
        const sp = Math.sin(e._shufPh * 6), a = e._shufA;
        P.legR.rotation.x += sp * 0.15 * a;
        P.legL.rotation.x += -sp * 0.15 * a;
        P.kneeR.rotation.x += Math.max(0, sp) * 0.32 * a;
        P.kneeL.rotation.x += Math.max(0, -sp) * 0.32 * a;
      }
    }
    if (P.kneeR) e._pvY = e.vyaw || 0;""")

OLD_BOB = 'e.bob = Math.abs(Math.sin(e.phase)) * 0.055 * e.moveAmt * (1 - Math.max(e._rowT || 0, e._swimT || 0));'
assert s.count(OLD_BOB) == 1, 'bob anchor matched %d times' % s.count(OLD_BOB)
s = s.replace(OLD_BOB,
  'e.bob = (Math.abs(Math.sin(e.phase)) * (0.030 + 0.030 * Math.min(1, e.moveAmt || 0)) * Math.min(1, (e.moveAmt || 0) * 3) + ((e._shufA || 0) > 0.02 ? Math.abs(Math.sin((e._shufPh || 0) * 6)) * 0.012 * e._shufA : 0)) * (1 - Math.max(e._rowT || 0, e._swimT || 0));')

# ---------------------------------------------------------------------------
# 3. arm pose targets: y axis freed, elbows added
# ---------------------------------------------------------------------------
OLD_LETS = 'let armRx = -sw * 0.55, armLx = sw * 0.55, armRz = 0.04, armLz = -0.06, handRy = 0, handRz = 0;'
assert s.count(OLD_LETS) == 1, 'arm lets anchor matched %d times' % s.count(OLD_LETS)
s = s.replace(OLD_LETS, """let armRx = -sw * 0.55, armLx = sw * 0.55, armRy = 0, armRz = 0.04, armLz = -0.06, handRy = 0, handRz = 0;
    // elbows follow the swing: bend as the arm comes forward, like a person
    let elbRx = -0.14 - Math.max(0, sw) * 0.50, elbRy = 0, elbRz = 0;
    let elbLx = -0.14 - Math.max(0, -sw) * 0.50, elbLy = 0, elbLz = 0;""")

OLD_APS = """ap(P.armR, armRx, handRy * 0, armRz);
    ap(P.armL, armLx, 0, armLz);
    ap(P.hand, 0, handRy, handRz);"""
assert s.count(OLD_APS) == 1, 'ap anchor matched %d times' % s.count(OLD_APS)
s = s.replace(OLD_APS, """ap(P.armR, armRx, armRy, armRz);
    ap(P.armL, armLx, 0, armLz);
    ap(P.hand, 0, handRy, handRz);
    if (P.elbowR) { ap(P.elbowR, elbRx, elbRy, elbRz); ap(P.elbowL, elbLx, elbLy, elbLz); }""")

# ---------------------------------------------------------------------------
# 4. weapon idles and the block
# ---------------------------------------------------------------------------
OLD_BLOCK = 'if (e.blocking && e.weapon === 0) { armLx = -1.18; armLz = -0.42; upperYaw += 0.18; upperPitch = 0.1; }'
assert s.count(OLD_BLOCK) == 1, 'block pose anchor matched %d times' % s.count(OLD_BLOCK)
s = s.replace(OLD_BLOCK,
  'if (e.blocking && e.weapon === 0) { if (P.elbowL) { armLx = -0.72; armLz = -0.14; elbLx = -1.15; elbLy = 0.15; } else { armLx = -1.18; armLz = -0.42; } upperYaw += 0.18; upperPitch = 0.1; }')

OLD_W0 = 'else if (e.weapon === 0) { armLz = -0.06; }   // hangs straight; shield rides the side'
assert s.count(OLD_W0) == 1, 'weapon-0 idle anchor matched %d times' % s.count(OLD_W0)
s = s.replace(OLD_W0, """else if (e.weapon === 0) {
      // the carry: shoulder out a touch, elbow near a right angle, fist at
      // the grip - the pose from the lab turntable
      if (P.elbowL) { armLx = -0.10; armLz = -0.16; elbLx = -1.22; elbLy = 0.10; }
      else { armLz = -0.06; }
    }
    else if (e.weapon === 1 && P.elbowR && e.state !== 'attack' && e.state !== 'cast') { armRx = -0.06; armRz = 0.08; elbRx = -0.42; }
    else if (e.weapon === 2 && P.elbowL && e.state !== 'draw') { armLx = -0.04; armLz = -0.10; elbLx = -0.38; }""")

OLD_DRAW = 'armLx = -1.5; armLz = 0; armRx = -1.35 + c * 0.3; armRz = -0.5 - c * 0.25;'
assert s.count(OLD_DRAW) == 1, 'draw pose anchor matched %d times' % s.count(OLD_DRAW)
s = s.replace(OLD_DRAW, """if (P.elbowL) {
        // vector-solved in the lab: bow arm extended, string elbow high and
        // back, fist anchored at the cheek
        armLx = -1.50; armLz = -0.04; elbLx = -0.08;
        armRx = 0.873; armRy = 0.747; armRz = 1.397;
        elbRx = 2.396; elbRy = 0.889; elbRz = 1.384;
      } else { armLx = -1.5; armLz = 0; armRx = -1.35 + c * 0.3; armRz = -0.5 - c * 0.25; }
      if (P.bowSet) { P.bowSet.setDraw(Math.min(1, c * 1.1)); P.bowSet.arrow.visible = true; }""")

OLD_HANDL = 'if (e.weapon === 2) P.handL.rotation.x = -P.armL.rotation.x;'
assert s.count(OLD_HANDL) == 1, 'handL anchor matched %d times' % s.count(OLD_HANDL)
s = s.replace(OLD_HANDL, """if (e.weapon === 2 && P.elbowL) {
      // the fist counter-rotates the whole arm chain so the bow stays
      // upright, with a slight archer's cant
      P.handL.rotation.x = -(P.armL.rotation.x + P.elbowL.rotation.x);
      P.handL.rotation.z = -0.10;
      if (P.bowSet && e.state !== 'draw' && !(e.state === 'attack' && e.act && e.act.name === 'shot')) { P.bowSet.setDraw(0); P.bowSet.arrow.visible = false; }
    } else if (e.weapon === 2) P.handL.rotation.x = -P.armL.rotation.x;
    else if (P.elbowL && P.handL.rotation.x !== 0) { P.handL.rotation.x = 0; P.handL.rotation.z = 0; }""")

# ---------------------------------------------------------------------------
# 5. shield: rest carry and guard, both in FOREARM space now
# ---------------------------------------------------------------------------
OLD_SH = """P.shield.rotation.x = (Math.PI / 2) * (1 - b2) + (-P.armL.rotation.x) * b2;
      P.shield.rotation.y = Math.PI - 1.62 * b2;
      P.shield.rotation.z = (-P.armL.rotation.z) * (1 - b2) - 0.1 * b2;
      P.shield.position.set(0.07 - 0.14 * b2, -0.55 - 0.04 * b2, -0.05 + 0.35 * b2);"""
assert s.count(OLD_SH) == 1, 'shield write anchor matched %d times' % s.count(OLD_SH)
s = s.replace(OLD_SH, """if (P.elbowL) {
        // carry (PI, PI, 0) at the forearm; guard solved in the lab from
        // world targets: face square front, fist behind the plate
        P.shield.rotation.x = Math.PI + (-0.218 - Math.PI) * b2;
        P.shield.rotation.y = Math.PI + (1.294 - Math.PI) * b2;
        P.shield.rotation.z = 2.083 * b2;
        P.shield.position.set(0.075 + (0.065 - 0.075) * b2, -0.19 + (-0.427 + 0.19) * b2, 0.12 + (-0.113 - 0.12) * b2);
      } else {
        P.shield.rotation.x = (Math.PI / 2) * (1 - b2) + (-P.armL.rotation.x) * b2;
        P.shield.rotation.y = Math.PI - 1.62 * b2;
        P.shield.rotation.z = (-P.armL.rotation.z) * (1 - b2) - 0.1 * b2;
        P.shield.position.set(0.07 - 0.14 * b2, -0.55 - 0.04 * b2, -0.05 + 0.35 * b2);
      }""")

# ---------------------------------------------------------------------------
# 6. seated poses get knees
# ---------------------------------------------------------------------------
OLD_RIDE = 'P.legR.rotation.x = -0.8; P.legL.rotation.x = -0.8;'
assert s.count(OLD_RIDE) == 1, 'riding anchor matched %d times' % s.count(OLD_RIDE)
s = s.replace(OLD_RIDE, 'P.legR.rotation.x = -0.8; P.legL.rotation.x = -0.8;\n      if (P.kneeR) { P.kneeR.rotation.x = 1.25; P.kneeL.rotation.x = 1.25; }')

OLD_ROW = 'P.legR.rotation.x = P.legR.rotation.x * (1 - rt) + (-1.32) * rt;'
assert s.count(OLD_ROW) == 1, 'rowing anchor matched %d times' % s.count(OLD_ROW)
s = s.replace(OLD_ROW, 'P.legR.rotation.x = P.legR.rotation.x * (1 - rt) + (-1.32) * rt;\n      if (P.kneeR) { P.kneeR.rotation.x = P.kneeR.rotation.x * (1 - rt) + 1.45 * rt; P.kneeL.rotation.x = P.kneeL.rotation.x * (1 - rt) + 1.45 * rt; }')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 36: animation v6 installed (%d bytes of module inlined)' % len(body))
