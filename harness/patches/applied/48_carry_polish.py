#!/usr/bin/env python3
"""Patch 48: Kevin's second-round carry corrections.

1. Shield arm outward tilt halved (0.20 -> 0.10): still a gap off the hip,
   just not held away. The shield's WORLD orientation is unchanged - its
   elbow-space transform was re-solved at the new arm pose so the plate
   does not tilt with the arm.
2. Bow idle: the arm crosses the front (armLz -0.22) so the fist sits at
   the body's centreline, plus a slight hunch (upperPitch 0.18) - the
   Dragonwilds archer lean, he was "too stiff".
3. Draw rebuilt on real archer form (researched): torso stands near
   SIDEWAYS to the target (upperYaw 0.80, was 0.45), the drawing forearm
   finishes IN LINE with the arrow, elbow pointing straight away from the
   target - which is what stops the string arm clipping through the chest.
   Both arms, the bow fist and the two IK keys were re-solved at that yaw
   with armL.y pinned to 0, because ap() writes ap(P.armL, armLx, 0, armLz)
   and a solve that assumed a free y would bake a lie.

Numbers from harness/pose47.js runs; nothing here is typed from memory.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n0 = len(s)

def sub(old, new, why):
    global s
    assert s.count(old) == 1, 'anchor x%d: %s' % (s.count(old), why)
    s = s.replace(old, new)
    print('  ok:', why)

# 1. shield arm: halve the outward tilt
sub("if (P.elbowL) { armLx = -0.05; armLz = 0.20; elbLx = -0.30; elbLy = 0; }",
    "if (P.elbowL) { armLx = -0.05; armLz = 0.10; elbLx = -0.30; elbLy = 0; }",
    'shield arm tilt halved')

# 1b. shield rest re-solved at the new arm pose (same world orientation)
sub("P.shield.rotation.x = -1.220 + (-0.218 + 1.220) * b2;",
    "P.shield.rotation.x = -1.221 + (-0.218 + 1.221) * b2;",
    'shield rest rot.x')
sub("P.shield.rotation.y = 0.207 + (1.294 - 0.207) * b2;",
    "P.shield.rotation.y = 0.107 + (1.294 - 0.107) * b2;",
    'shield rest rot.y')
sub("P.shield.rotation.z = 3.131 + (2.083 - 3.131) * b2;",
    "P.shield.rotation.z = 3.137 + (2.083 - 3.137) * b2;",
    'shield rest rot.z')
sub("P.shield.position.set(0.102 + (0.065 - 0.102) * b2, -0.351 + (-0.427 + 0.351) * b2, -0.157 + (-0.113 + 0.157) * b2);",
    "P.shield.position.set(0.112 + (0.065 - 0.112) * b2, -0.341 + (-0.427 + 0.341) * b2, -0.154 + (-0.113 + 0.154) * b2);",
    'shield rest position')
sub("shield.position.set(0.102, -0.351, -0.157); shield.rotation.set(-1.220, 0.207, 3.131);",
    "shield.position.set(0.112, -0.341, -0.154); shield.rotation.set(-1.221, 0.107, 3.137);",
    'shield base transform')

# 2. bow idle: arm crosses the front, slight hunch
sub("e.weapon === 2 && P.elbowL && e.state !== 'draw' && spd < 0.35) { armLx = -0.50; armLz = 0.06; elbLx = -0.30; }",
    "e.weapon === 2 && P.elbowL && e.state !== 'draw' && spd < 0.35) { armLx = -0.50; armLz = -0.22; elbLx = -0.30; upperPitch = 0.18; }",
    'bow idle: crossing arm + hunch')

# 2b. carry fist re-solved at the crossing arm; run key unchanged
sub("P.handL.rotation.set(0.799 + 0.921 * mvB, -0.029 + 0.112 * mvB, 1.227 - 1.210 * mvB);",
    "P.handL.rotation.set(0.613 + 1.107 * mvB, 0.069 + 0.014 * mvB, 1.489 - 1.472 * mvB);",
    'carry fist keys')

# 3. draw: sideways torso, arm and fist re-solved at yaw 0.80
sub("upperYaw = 0.45;", "upperYaw = 0.80;", 'draw torso near-sideways')
sub("armLx = -1.50; armLz = -0.04; elbLx = -0.08;",
    "armLx = -1.612; armLz = -0.704; elbLx = -0.06;",
    'bow arm at the target from the yawed shoulder')
sub("P.handL.rotation.set(-(P.armL.rotation.x + P.elbowL.rotation.x), 0, -0.10);",
    "P.handL.rotation.set(1.619, -0.096, -0.118);",
    'draw fist baked from the solve (pitch-counter cannot see the yaw)')
sub("""        const dp = Math.min(1, c * 1.15);
        armRx = -0.095 + 0.815 * dp; armRy = -0.524 + 0.683 * dp; armRz = 1.444 - 0.081 * dp;
        elbRx = -0.015 - 0.380 * dp; elbRy = 0.125 + 0.268 * dp; elbRz = -0.031 + 0.210 * dp;""",
    """        const dp = Math.min(1, c * 1.15);
        armRx = 0.776 + 0.022 * dp; armRy = 0.095 - 0.105 * dp; armRz = 1.660 - 0.127 * dp;
        elbRx = -1.884 + 1.865 * dp; elbRy = 0.773 - 0.650 * dp; elbRz = 0.761 - 0.727 * dp;""",
    'string arm IK keys: elbow out along the arrow line')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 48 applied, %+d bytes' % (len(s) - n0))
