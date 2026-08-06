#!/usr/bin/env python3
"""Patch 46: Kevin's corrections to the patch 37 weapon carries.

His review of 37, point by point:
1. The shield arm hugged the hip and tilted slightly INWARD. Now it tilts
   slightly outward (armL.z +0.20, left side is +X) so there is a visible
   gap between the hand and the hip.
2. The shield point aimed at "7 o'clock" in the side view. He wants "3
   o'clock": the shield HORIZONTAL at the side, long axis front to back,
   point aft, face vertical. Solved in the lab from a world basis
   (local Y -> world +Z, bright face outboard) in elbow space and baked.
3. The bow idle read wrong. Reference: the bow crosses the FRONT of the
   body, string side toward the character. Fist euler solved from the bow's
   desired world basis (top tip up-right across the chest, string -Z ->
   world -Z), not hand-tuned.
4. Running, the string must face UP, not down: fist solved so local -Z ->
   world +Y at mid-swing, the bow rides fore-aft at the side.
5. The draw's right arm was wonky and never touched the string. Two-bone IK
   in the lab puts the fist ON the nocking point at two keys (first grab,
   full anchor); the game lerps between them with the charge while setDraw
   moves the string the same distance, so the hand tracks the pull.

Every number here is read out of harness/pose38-{shield,bow,draw}.js runs
against model-lab/character.html, never typed from memory.
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

# 1+2a. Shield idle overlay: arm tilted OUTWARD, soft elbow, no forearm yaw.
sub("if (P.elbowL) { armLx = -0.05; armLz = -0.10; elbLx = -0.35; elbLy = 0.05; }",
    "if (P.elbowL) { armLx = -0.05; armLz = 0.20; elbLx = -0.30; elbLy = 0; }",
    'shield idle arm: outward tilt, gap off the hip')

# 2b. Shield rest orientation: horizontal, point aft (solved: -1.220, 0.207,
# 3.131 in elbow space), blending to the same lab-solved guard as before.
sub("P.shield.rotation.x = -0.06 + (-0.218 + 0.06) * b2;",
    "P.shield.rotation.x = -1.220 + (-0.218 + 1.220) * b2;",
    'shield rest rot.x')
sub("P.shield.rotation.y = Math.PI + (1.294 - Math.PI) * b2;",
    "P.shield.rotation.y = 0.207 + (1.294 - 0.207) * b2;",
    'shield rest rot.y')
sub("P.shield.rotation.z = 0.10 + (2.083 - 0.10) * b2;",
    "P.shield.rotation.z = 3.131 + (2.083 - 3.131) * b2;",
    'shield rest rot.z')
sub("P.shield.position.set(0.075 + (0.065 - 0.075) * b2, -0.34 + (-0.427 + 0.34) * b2, 0.05 + (-0.113 - 0.05) * b2);",
    "P.shield.position.set(0.102 + (0.065 - 0.102) * b2, -0.351 + (-0.427 + 0.351) * b2, -0.157 + (-0.113 + 0.157) * b2);",
    'shield rest position: centred on the leg')

# 2c. The module's base transform matches the new rest, so the first frame
# before animate() runs shows the same carry.
sub("shield.position.set(0.075, -0.17, 0.14); shield.rotation.set(Math.PI, Math.PI, 0);",
    "shield.position.set(0.102, -0.351, -0.157); shield.rotation.set(-1.220, 0.207, 3.131);",
    'shield base transform = rest carry')

# 3a. Bow idle arm: fist in front of the hip, near the midline.
sub("e.weapon === 2 && P.elbowL && e.state !== 'draw' && spd < 0.35) { armLx = -0.50; armLz = 0.20; elbLx = -0.32; }",
    "e.weapon === 2 && P.elbowL && e.state !== 'draw' && spd < 0.35) { armLx = -0.50; armLz = 0.06; elbLx = -0.30; }",
    'bow idle arm: hand to the front midline')

# 3b+4. The carry fist: two solved eulers, idle (bow across the front,
# string toward the body) and run (string UP, bow fore-aft at the side),
# blended by movement so the wrist rolls naturally as he sets off.
sub("""        P.handL.rotation.set(0.35, 1.55, -0.55);
        if (P.bowSet) { P.bowSet.setDraw(0); P.bowSet.arrow.visible = false; }""",
    """        const mvB = Math.min(1, Math.max(0, ((e.moveAmt || 0) - 0.25) / 0.35));
        P.handL.rotation.set(0.799 + 0.921 * mvB, -0.029 + 0.112 * mvB, 1.227 - 1.210 * mvB);
        if (P.bowSet) { P.bowSet.setDraw(0); P.bowSet.arrow.visible = false; }""",
    'carry fist: idle crosses the front, run rolls string-up')

# 5a. Draw: lerp the right arm between the two IK keys with the charge. The
# keys were solved with the fist ON the string at setDraw(0.15) and (0.9).
sub("""        armRx = 0.873; armRy = 0.747; armRz = 1.397;
        elbRx = 2.396; elbRy = 0.889; elbRz = 1.384;""",
    """        const dp = Math.min(1, c * 1.15);
        armRx = -0.095 + 0.815 * dp; armRy = -0.524 + 0.683 * dp; armRz = 1.444 - 0.081 * dp;
        elbRx = -0.015 - 0.380 * dp; elbRy = 0.125 + 0.268 * dp; elbRz = -0.031 + 0.210 * dp;""",
    'draw arm: IK keys lerped with the charge')

# 5b. The string travels the SAME range the keys were solved against, so
# the fist and the nock stay together through the whole pull.
sub("P.bowSet.setDraw(Math.min(1, c * 1.1)); P.bowSet.arrow.visible = true;",
    "P.bowSet.setDraw(0.15 + Math.min(1, c * 1.15) * 0.75); P.bowSet.arrow.visible = true;",
    'string travel matches the IK keys')

# 5c. Torso yaw the IK was solved at (0.45, not 0.55).
sub("upperYaw = 0.55;", "upperYaw = 0.45;", 'draw torso yaw matches the solve')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 46 applied, %+d bytes' % (len(s) - n0))
