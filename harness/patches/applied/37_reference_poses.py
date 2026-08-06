#!/usr/bin/env python3
"""Patch 37: the weapon carries matched to Kevin's Dragonwilds references.

Kevin shot reference screenshots in RuneScape Dragonwilds and asked for the
same reads. Three corrections to patch 36's poses:

  1. SHIELD: the right-angle elbow carried the shield chest-high. The
     reference carries it UPRIGHT and LOW at the side on a nearly-hanging
     arm: soft elbow bend (-0.35), shield strap-hung down the forearm,
     point down, face out, a slight lean. (Kevin called his own 90-degree
     idea wrong after seeing it - the reference wins.)
  2. BOW idle: carried across the FRONT at hip height in the body's frontal
     plane - full curve visible, string toward the body - via a FIXED fist
     euler (0.35, 1.55, -0.55) chosen against the reference on the lab
     turntable. While moving, the same fixed fist rides the arm swing, which
     is exactly the reference's run frame. Drawing still counter-rotates the
     fist so the bow stands vertical.
  3. The bow-idle arm overlay only applies when nearly stationary; at speed
     the arm joins the gait swing.

All anchors are patch 36's own text, verified 1x against the live bundle.
"""
import io, os, re

SRC = '/tmp/game-src.html'

s = io.open(SRC, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# 1. shield idle overlay: soft elbow, low carry
# ---------------------------------------------------------------------------
OLD = """      if (P.elbowL) { armLx = -0.10; armLz = -0.16; elbLx = -1.22; elbLy = 0.10; }
      else { armLz = -0.06; }"""
assert s.count(OLD) == 1, 'shield idle anchor matched %d times' % s.count(OLD)
s = s.replace(OLD, """      if (P.elbowL) { armLx = -0.05; armLz = -0.10; elbLx = -0.35; elbLy = 0.05; }
      else { armLz = -0.06; }""")

# ---------------------------------------------------------------------------
# 2. shield rest transform: upright, low, slight lean
# ---------------------------------------------------------------------------
OLD_SH = """        P.shield.rotation.x = Math.PI + (-0.218 - Math.PI) * b2;
        P.shield.rotation.y = Math.PI + (1.294 - Math.PI) * b2;
        P.shield.rotation.z = 2.083 * b2;
        P.shield.position.set(0.075 + (0.065 - 0.075) * b2, -0.19 + (-0.427 + 0.19) * b2, 0.12 + (-0.113 - 0.12) * b2);"""
assert s.count(OLD_SH) == 1, 'shield write anchor matched %d times' % s.count(OLD_SH)
s = s.replace(OLD_SH, """        P.shield.rotation.x = -0.06 + (-0.218 + 0.06) * b2;
        P.shield.rotation.y = Math.PI + (1.294 - Math.PI) * b2;
        P.shield.rotation.z = 0.10 + (2.083 - 0.10) * b2;
        P.shield.position.set(0.075 + (0.065 - 0.075) * b2, -0.34 + (-0.427 + 0.34) * b2, 0.05 + (-0.113 - 0.05) * b2);""")

# ---------------------------------------------------------------------------
# 3. bow idle overlay: front carry, only near-stationary
# ---------------------------------------------------------------------------
OLD_BOW = "else if (e.weapon === 2 && P.elbowL && e.state !== 'draw') { armLx = -0.04; armLz = -0.10; elbLx = -0.38; }"
assert s.count(OLD_BOW) == 1, 'bow idle anchor matched %d times' % s.count(OLD_BOW)
s = s.replace(OLD_BOW,
  "else if (e.weapon === 2 && P.elbowL && e.state !== 'draw' && spd < 0.35) { armLx = -0.50; armLz = 0.20; elbLx = -0.32; }")

# ---------------------------------------------------------------------------
# 4. the fist: fixed frontal-plane euler except while drawing
# ---------------------------------------------------------------------------
OLD_HAND = """if (e.weapon === 2 && P.elbowL) {
      // the fist counter-rotates the whole arm chain so the bow stays
      // upright, with a slight archer's cant
      P.handL.rotation.x = -(P.armL.rotation.x + P.elbowL.rotation.x);
      P.handL.rotation.z = -0.10;
      if (P.bowSet && e.state !== 'draw' && !(e.state === 'attack' && e.act && e.act.name === 'shot')) { P.bowSet.setDraw(0); P.bowSet.arrow.visible = false; }
    } else if (e.weapon === 2) P.handL.rotation.x = -P.armL.rotation.x;"""
assert s.count(OLD_HAND) == 1, 'handL anchor matched %d times' % s.count(OLD_HAND)
s = s.replace(OLD_HAND, """if (e.weapon === 2 && P.elbowL) {
      const drawing = e.state === 'draw' || (e.state === 'attack' && e.act && e.act.name === 'shot');
      if (drawing) {
        // vertical bow at the extended arm, slight archer's cant
        P.handL.rotation.set(-(P.armL.rotation.x + P.elbowL.rotation.x), 0, -0.10);
      } else {
        // the reference carry: fixed fist euler lays the bow across the
        // body's frontal plane, and the same grip rides the run swing
        P.handL.rotation.set(0.35, 1.55, -0.55);
        if (P.bowSet) { P.bowSet.setDraw(0); P.bowSet.arrow.visible = false; }
      }
    } else if (e.weapon === 2) P.handL.rotation.x = -P.armL.rotation.x;""")

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 37: reference poses installed')
