#!/usr/bin/env python3
"""Patch 82.351: stop animate() allocating a closure (`ap`) every call.

animate() runs for the player and every non-culled NPC every frame. The `ap`
helper was a 4-line arrow function reallocated on every single call just to
blend one part's rotation toward a target - inlining the same three lines at
each of its 5 call sites removes the allocation with zero change to the math
or the order arm/hand/elbow rotations get blended in.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    const ap = (o, x, y, z) => {
      o.rotation.x += (x - o.rotation.x) * bl;
      o.rotation.y += (y - o.rotation.y) * bl;
      o.rotation.z += (z - o.rotation.z) * bl;
    };
    ap(P.armR, armRx, armRy, armRz);
    ap(P.armL, armLx, 0, armLz);
    ap(P.hand, 0, handRy, handRz);
    if (P.elbowR) { ap(P.elbowR, elbRx, elbRy, elbRz); ap(P.elbowL, elbLx, elbLy, elbLz); }
"""

NEW = """    P.armR.rotation.x += (armRx - P.armR.rotation.x) * bl; P.armR.rotation.y += (armRy - P.armR.rotation.y) * bl; P.armR.rotation.z += (armRz - P.armR.rotation.z) * bl;
    P.armL.rotation.x += (armLx - P.armL.rotation.x) * bl; P.armL.rotation.y += (0 - P.armL.rotation.y) * bl; P.armL.rotation.z += (armLz - P.armL.rotation.z) * bl;
    P.hand.rotation.x += (0 - P.hand.rotation.x) * bl; P.hand.rotation.y += (handRy - P.hand.rotation.y) * bl; P.hand.rotation.z += (handRz - P.hand.rotation.z) * bl;
    if (P.elbowR) {
      P.elbowR.rotation.x += (elbRx - P.elbowR.rotation.x) * bl; P.elbowR.rotation.y += (elbRy - P.elbowR.rotation.y) * bl; P.elbowR.rotation.z += (elbRz - P.elbowR.rotation.z) * bl;
      P.elbowL.rotation.x += (elbLx - P.elbowL.rotation.x) * bl; P.elbowL.rotation.y += (elbLy - P.elbowL.rotation.y) * bl; P.elbowL.rotation.z += (elbLz - P.elbowL.rotation.z) * bl;
    }
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
