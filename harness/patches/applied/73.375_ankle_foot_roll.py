#!/usr/bin/env python3
"""Patch 73.375: ankle joints + foot roll (locomotion overhaul phase 2).

Third in the plan's build order (after phase 1's gait blend and phase 4's
turn-in-place work, both already shipped this pass). Kevin's original ask
included "possibly re-rig legs/knees/feet/ankles" - this is that, scoped to
exactly what the plan calls for: a Group insertion, zero new triangles, a
lightweight foot roll, NOT a ground-conforming IK solve (that's phase 5,
explicitly out of scope - "all four phases" was the instruction).

DIAGNOSIS, confirmed by re-reading buildFighterRig's legGeo() live in
/tmp/game-src.html before writing anything: the boot (cuff to toe, one
sweep-lofted mesh), its sole, and the sabaton (foot armor) all parent
directly onto `knee`, the SAME Group the shin/calf geometry and the greave
(shin armor) use. There has never been an ankle joint - the whole foot has
always rotated exactly as much as the knee does, because there was nowhere
else for it to attach.

THE FIX: insert a new `ankle` Group as a child of `knee`, positioned at
(0, -0.430, 0) - the boot sweep's existing "ankle" waypoint, already
labelled as such in the original geometry's own comments, so this is
finding the joint the mesh already implies rather than picking an arbitrary
point. The boot, its sole, and the sabaton reparent onto `ankle`; every one
of their Y coordinates shifts by the same +0.430 to compensate, so at
rest (ankle.rotation.x === 0) the geometry sits in EXACTLY the same world
position as before this patch - confirmed by construction, not just by eye,
since the shift is arithmetic (old Y = new Y - 0.430 for every point moved).

The greave (shin armor, a separate loft) stays on `knee` completely
unchanged - it's shin armor, entirely above the ankle point, so it should
keep swinging with the knee and not roll with the foot.

One deliberate simplification, stated plainly rather than glossed over: the
boot is one merged mesh from cuff to toe, so reparenting the whole thing
means the boot's calf portion rolls slightly with the foot too, not just
the foot itself. That's not perfectly anatomical, but the roll angle this
patch drives is small (see ANKLE_AMP in animate() below), and splitting the
boot into two separately-authored meshes at the ankle line is a much larger
and riskier change for a cosmetic detail the plan itself calls "lightweight
foot roll" rather than a full solve.

ankleR/ankleL are threaded through the same four spots kneeR/kneeL already
flow through (rig return, makeFighterModel's parts object, the outer
makeFighter destructure, and its own parts return) - grepped kneeR across
the whole file first to find every one of them.

The roll itself is driven in animate(), locked to the exact same e.phase
and -0.65 offset the knee-tuck curve already uses, so it's automatically in
sync with the stride with no separate timing to tune, and inherits the
phase-1 gait blend's gFade standstill-to-moving fade for free.
"""
import io

SRC = '/tmp/game-src.html'

s = io.open(SRC, encoding='utf-8').read()


def one(anchor, label):
    n = s.count(anchor)
    assert n == 1, '%s matched %d times' % (label, n)


def sub(anchor, new, label):
    global s
    one(anchor, label)
    s = s.replace(anchor, new)


# ---------------------------------------------------------------------------
# 1. legGeo(): insert the ankle Group, reparent the boot onto it with every
#    Y coordinate shifted +0.430 to compensate.
# ---------------------------------------------------------------------------
OLD_BOOT = """        leg.knee = knee;
        // Boot: shin to toe as one surface. w is half-width throughout; d is
        // half-depth on the shin and becomes half-HEIGHT as the spine turns
        // forward at the ankle. Heel comes from the spine kinking back before the
        // turn, and every foot section's UNDERSIDE sits on the same plane
        // (y = -0.985, world 0.035) so the whole foot stands flat on the sole -
        // v5's first pass had the midfoot digging through it and the toe floating.
        // Boot sections are in KNEE space now (leg space shifted by the pivot),
        // so the whole boot swings with the shin.
        const boot = sweep(T, [
          // The cuff FLARES: its lip is clearly wider than the trouser leg above
          // it (0.077 against 0.058), so the leg reads as going INTO the boot
          // instead of the boot being painted on. Leg armor will cover this line
          // later; the flare stays subtle for that reason.
          { at: [0, -0.010, -0.006], w: 0.077, d: 0.082, p: 2.35 },  // flared lip
          { at: [0, -0.040, -0.008], w: 0.070, d: 0.075, p: 2.3 },   // cuff settling in
          { at: [0, -0.145, -0.014], w: 0.063, d: 0.069, p: 2.3 },   // calf peak, upper third
          { at: [0, -0.305, -0.018], w: 0.046, d: 0.051, p: 2.2 },
          { at: [0, -0.430, -0.022], w: 0.040, d: 0.045, p: 2.2 },   // ankle
          { at: [0, -0.485, -0.030], w: 0.041, d: 0.047, p: 2.3 },   // front-of-ankle bridge
          { at: [0, -0.508, -0.042], w: 0.044, d: 0.062, p: 2.4 },   // heel, kicked back behind the shin
          { at: [0, -0.534, 0.008], w: 0.045, d: 0.036, p: 2.5 },    // instep
          { at: [0, -0.540, 0.073], w: 0.048, d: 0.030, p: 2.6 },    // midfoot
          { at: [0, -0.544, 0.133], w: 0.046, d: 0.026, p: 2.6 },    // toe box
          { at: [0, -0.554, 0.173], w: 0.036, d: 0.015, p: 2.4 }     // toe
        ], 12, leather);
        knee.add(boot);"""

NEW_BOOT = """        leg.knee = knee;
        // Ankle joint (patch 73.375, phase 2): a Group inserted at the
        // boot's own "ankle" waypoint (below), so foot roll is a real
        // rotation instead of baked into the boot mesh. Zero new triangles -
        // the boot, sole and sabaton reparent onto it with their Y
        // coordinates shifted by the same +0.430, so ankle.rotation.x === 0
        // reproduces the old fixed geometry exactly; animate() drives it
        // from here on.
        const ankle = new T.Group(); ankle.position.set(0, -0.430, 0); knee.add(ankle);
        leg.ankle = ankle;
        // Boot: shin to toe as one surface. w is half-width throughout; d is
        // half-depth on the shin and becomes half-HEIGHT as the spine turns
        // forward at the ankle. Heel comes from the spine kinking back before the
        // turn, and every foot section's UNDERSIDE sits on the same plane
        // (y = -0.985, world 0.035) so the whole foot stands flat on the sole -
        // v5's first pass had the midfoot digging through it and the toe floating.
        // Boot sections are in ANKLE space now (shifted +0.430 from the old
        // knee-space coordinates, so nothing moves at rest), so the whole
        // boot swings with the shin AND rolls with the ankle.
        const boot = sweep(T, [
          // The cuff FLARES: its lip is clearly wider than the trouser leg above
          // it (0.077 against 0.058), so the leg reads as going INTO the boot
          // instead of the boot being painted on. Leg armor will cover this line
          // later; the flare stays subtle for that reason.
          { at: [0, 0.420, -0.006], w: 0.077, d: 0.082, p: 2.35 },  // flared lip
          { at: [0, 0.390, -0.008], w: 0.070, d: 0.075, p: 2.3 },   // cuff settling in
          { at: [0, 0.285, -0.014], w: 0.063, d: 0.069, p: 2.3 },   // calf peak, upper third
          { at: [0, 0.125, -0.018], w: 0.046, d: 0.051, p: 2.2 },
          { at: [0, 0.000, -0.022], w: 0.040, d: 0.045, p: 2.2 },   // ankle
          { at: [0, -0.055, -0.030], w: 0.041, d: 0.047, p: 2.3 },  // front-of-ankle bridge
          { at: [0, -0.078, -0.042], w: 0.044, d: 0.062, p: 2.4 },  // heel, kicked back behind the shin
          { at: [0, -0.104, 0.008], w: 0.045, d: 0.036, p: 2.5 },   // instep
          { at: [0, -0.110, 0.073], w: 0.048, d: 0.030, p: 2.6 },   // midfoot
          { at: [0, -0.114, 0.133], w: 0.046, d: 0.026, p: 2.6 },   // toe box
          { at: [0, -0.124, 0.173], w: 0.036, d: 0.015, p: 2.4 }    // toe
        ], 12, leather);
        ankle.add(boot);"""

sub(OLD_BOOT, NEW_BOOT, 'ankle Group + boot reparent (73.375)')

# ---------------------------------------------------------------------------
# 2. Sole: same reparent, same +0.430 shift.
# ---------------------------------------------------------------------------
OLD_SOLE = """          const sg = new T.ExtrudeGeometry(so, { depth: 0.018, bevelEnabled: false });
          sg.rotateX(Math.PI / 2);   // plan-y becomes forward z, thickness extrudes down
          const sole = new T.Mesh(sg, dark);
          sole.castShadow = true;
          sole.position.set(0, -0.570, -0.012);   // knee space
          knee.add(sole);"""

NEW_SOLE = """          const sg = new T.ExtrudeGeometry(so, { depth: 0.018, bevelEnabled: false });
          sg.rotateX(Math.PI / 2);   // plan-y becomes forward z, thickness extrudes down
          const sole = new T.Mesh(sg, dark);
          sole.castShadow = true;
          sole.position.set(0, -0.140, -0.012);   // ankle space (73.375, was knee space)
          ankle.add(sole);"""

sub(OLD_SOLE, NEW_SOLE, 'sole reparent to ankle (73.375)')

# ---------------------------------------------------------------------------
# 3. Sabaton (foot armor) reparents to the ankle too; the greave (shin
#    armor) stays on the knee, unchanged - it's above the ankle point.
# ---------------------------------------------------------------------------
OLD_GEAR = """      // greaves + sabaton caps hugging the boot - on the SHIN, in knee space
      for (const leg of [legR, legL]) {
        gearAdd(leg.knee, loftY(T, [
          { y: -0.035, w: 0.072, d: 0.076, p: 2.4 },
          { y: -0.185, w: 0.066, d: 0.072, p: 2.4 },
          { y: -0.345, w: 0.048, d: 0.053, p: 2.3 }
        ], 12, steel));
        const sab = gearAdd(leg.knee, sweep(T, [
          // first ring hugs the boot tight so the open end's cap is a sliver -
          // a loose ring left a bright steel disc gleaming at the ankle in low sun
          { at: [0, -0.480, -0.024], w: 0.0435, d: 0.0475, p: 2.4 },
          { at: [0, -0.530, 0.018], w: 0.052, d: 0.034, p: 2.6 },
          { at: [0, -0.537, 0.088], w: 0.054, d: 0.028, p: 2.6 },
          { at: [0, -0.545, 0.138], w: 0.046, d: 0.020, p: 2.5 }
        ], 12, steel));
      }"""

NEW_GEAR = """      // greave (shin armor) stays on the knee, unchanged - above the ankle
      // point. Sabaton (foot armor) reparents to the ankle, +0.430 shifted,
      // so it rolls with the foot (73.375) instead of the shin.
      for (const leg of [legR, legL]) {
        gearAdd(leg.knee, loftY(T, [
          { y: -0.035, w: 0.072, d: 0.076, p: 2.4 },
          { y: -0.185, w: 0.066, d: 0.072, p: 2.4 },
          { y: -0.345, w: 0.048, d: 0.053, p: 2.3 }
        ], 12, steel));
        const sab = gearAdd(leg.ankle, sweep(T, [
          // first ring hugs the boot tight so the open end's cap is a sliver -
          // a loose ring left a bright steel disc gleaming at the ankle in low sun
          { at: [0, -0.050, -0.024], w: 0.0435, d: 0.0475, p: 2.4 },
          { at: [0, -0.100, 0.018], w: 0.052, d: 0.034, p: 2.6 },
          { at: [0, -0.107, 0.088], w: 0.054, d: 0.028, p: 2.6 },
          { at: [0, -0.115, 0.138], w: 0.046, d: 0.020, p: 2.5 }
        ], 12, steel));
      }"""

sub(OLD_GEAR, NEW_GEAR, 'sabaton reparent to ankle, greave unchanged (73.375)')

# ---------------------------------------------------------------------------
# 4. Extract ankleR/ankleL alongside kneeR/kneeL, and thread them through
#    every place kneeR/kneeL already flow (grepped kneeR globally first).
# ---------------------------------------------------------------------------
sub(
    """      const kneeR = legR.knee, kneeL = legL.knee;""",
    """      const kneeR = legR.knee, kneeL = legL.knee;
      const ankleR = legR.ankle, ankleL = legL.ankle;""",
    'extract ankleR/ankleL (73.375)'
)

sub(
    """      return {
        g, body, upper, chest, torso, head, hair, helm, armR, armL, legR, legL,
        elbowR, elbowL, kneeR, kneeL,
        hand, handL, crest, capePiv, gear,
        mats: { steel, cloth, trim, skin, pants, leather, dark },
        box, cyl, sph
      };""",
    """      return {
        g, body, upper, chest, torso, head, hair, helm, armR, armL, legR, legL,
        elbowR, elbowL, kneeR, kneeL, ankleR, ankleL,
        hand, handL, crest, capePiv, gear,
        mats: { steel, cloth, trim, skin, pants, leather, dark },
        box, cyl, sph
      };""",
    'rig return carries ankleR/ankleL (73.375)'
)

sub(
    """          armR: rig.armR, armL: rig.armL, legR: rig.legR, legL: rig.legL,
          elbowR: rig.elbowR, elbowL: rig.elbowL, kneeR: rig.kneeR, kneeL: rig.kneeL,
          hand: rig.hand, handL: rig.handL,""",
    """          armR: rig.armR, armL: rig.armL, legR: rig.legR, legL: rig.legL,
          elbowR: rig.elbowR, elbowL: rig.elbowL, kneeR: rig.kneeR, kneeL: rig.kneeL,
          ankleR: rig.ankleR, ankleL: rig.ankleL,
          hand: rig.hand, handL: rig.handL,""",
    'makeFighterModel parts carries ankleR/ankleL (73.375)'
)

sub(
    """      elbowR = model.parts.elbowR, elbowL = model.parts.elbowL,
      kneeR = model.parts.kneeR, kneeL = model.parts.kneeL, bowSet = model.parts.bowSet,""",
    """      elbowR = model.parts.elbowR, elbowL = model.parts.elbowL,
      kneeR = model.parts.kneeR, kneeL = model.parts.kneeL, bowSet = model.parts.bowSet,
      ankleR = model.parts.ankleR, ankleL = model.parts.ankleL,""",
    'outer makeFighter destructure carries ankleR/ankleL (73.375)'
)

sub(
    """      parts: { upper, torso, head, armR, armL, legR, legL, elbowR, elbowL, kneeR, kneeL, bowSet, hand, handL, sword, staff, bow, backBow, shield, ward, orb, frostShell, crest, capePiv, bladeTip, pick, axe: waxe, great, greatTip, chest, hair, helm },""",
    """      parts: { upper, torso, head, armR, armL, legR, legL, elbowR, elbowL, kneeR, kneeL, ankleR, ankleL, bowSet, hand, handL, sword, staff, bow, backBow, shield, ward, orb, frostShell, crest, capePiv, bladeTip, pick, axe: waxe, great, greatTip, chest, hair, helm },""",
    'outer makeFighter parts return carries ankleR/ankleL (73.375)'
)

# ---------------------------------------------------------------------------
# 5. Drive the roll in animate(), locked to the exact phase/offset the knee
#    tuck already uses so it's automatically in sync with the stride.
# ---------------------------------------------------------------------------
OLD_DRIVE = """      P.kneeR.rotation.x = 0.06 + gKnee * Math.pow(Math.max(0, Math.sin(e.phase - 0.65)), gCurve);
      P.kneeL.rotation.x = 0.06 + gKnee * Math.pow(Math.max(0, Math.sin(e.phase - 0.65 + Math.PI)), gCurve);
    } else { P.legR.rotation.x = sw; P.legL.rotation.x = -sw; }"""

NEW_DRIVE = """      P.kneeR.rotation.x = 0.06 + gKnee * Math.pow(Math.max(0, Math.sin(e.phase - 0.65)), gCurve);
      P.kneeL.rotation.x = 0.06 + gKnee * Math.pow(Math.max(0, Math.sin(e.phase - 0.65 + Math.PI)), gCurve);
      // Foot roll (patch 73.375, phase 2): a lightweight ankle rock, not a
      // ground-conforming IK solve (that's phase 5, out of scope). Locked to
      // the same phase clock and -0.65 offset the knee tuck already uses, so
      // it's automatically in sync with the stride with nothing new to time.
      if (P.ankleR) {
        const ANKLE_AMP = 0.16;
        P.ankleR.rotation.x = -Math.sin(e.phase - 0.65) * ANKLE_AMP * gFade;
        P.ankleL.rotation.x = -Math.sin(e.phase - 0.65 + Math.PI) * ANKLE_AMP * gFade;
      }
    } else { P.legR.rotation.x = sw; P.legL.rotation.x = -sw; }"""

sub(OLD_DRIVE, NEW_DRIVE, 'foot-roll drive in animate() (73.375)')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 73.375 applied: ankle joints + foot roll')
