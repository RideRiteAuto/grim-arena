#!/usr/bin/env python3
"""Patch 73.140: real walk/run/sprint gaits (locomotion overhaul phase 1/4).

Kevin's report, twice over: "walk/run/sprint animations for humanoids...
look identical just sped up." He asked for research into how real game
animators solve this (calling it a solved problem -- Unreal/Unity blend
spaces, GDC talks) before touching anything, then to implement the full
plan. This is phase 1 of harness/patches/../../claude/LOCOMOTION-ANIMATION-
PLAN.md (a Claude Project doc, not in this repo): the humanoid gait blend,
first in the plan's stated build order because it's the change Kevin will
actually see in the first five seconds of walking around, and it's a
coefficient-authoring problem against existing code, not a new system.

DIAGNOSIS, confirmed by re-reading animate() live in /tmp/game-src.html
before writing anything: the whole walk/run/sprint stride was ONE sine wave
with amplitude scaled by a single number:

    const spd = Math.min(1, e.moveAmt || 0);              // <- clamps at 1
    const hip = Math.sin(e.phase) * (0.42 + 0.28 * spd) * gA;
    const kMax = (0.85 + 0.80 * spd) * gA;
    ... Math.pow(..., 1.4)                                  // <- fixed shape

e.moveAmt is a continuous 0-1.5 value (0 idle, 1.0 the game's one normal
move speed, 1.5 sprint -- GRIM_RULES.SPRINT is exactly 1.5x SPEED, and it
also passes through partial values from combat-move penalties, water depth,
and casting slowdown, so "walk" band gets hit constantly outside of sprint
too). Two bugs stacked:

  1. `spd` clamps at 1, so RUN (moveAmt 1.0) and SPRINT (moveAmt 1.5) fed
     the IDENTICAL number into hip/knee amplitude. Holding shift did
     literally nothing to the leg animation. Same story for e.bob a few
     lines down, which used the same min(1, moveAmt) clamp.
  2. Below the clamp, walk vs. run was only ever an amplitude turn-down on
     the SAME curve (same knee exponent 1.4, same lean-to-speed ratio, same
     arm-swing ratio) -- a quiet run, not a walk. That is exactly "looks
     identical just sped up."

THE FIX: three keyed gait shapes -- WALK, RUN, SPRINT -- blended by
e.moveAmt the way an engine blend space would key a walk/run/sprint 1D
blend space off speed, not one formula stretched by a multiplier. GAIT_RUN
is defined to reproduce the OLD formula's numbers exactly when evaluated at
moveAmt 1 (see the const block above the class for the arithmetic), so
ordinary running -- the overwhelming majority of on-foot movement -- is
pixel-identical to before this patch. GAIT_WALK and GAIT_SPRINT are new,
distinct shapes, not smaller/bigger copies of GAIT_RUN: walk is upright and
round (near-zero lean, low knee-curve exponent for a gentle tuck, short arm
swing), sprint is a hard forward drive (large lean, high knee-curve
exponent for a snappy tuck, big arm pump) -- and two of the eight blended
values are deliberately NON-monotonic across walk -> run -> sprint:

  - yawC (torso counter-rotation) RISES from walk to run, then FALLS for
    sprint. A real sprinter stabilises the torso and drives the arms
    sagitally instead of twisting -- less wasted rotation, not more, at top
    speed. A linear extrapolation from run would have kept climbing; this
    doesn't, on purpose.
  - bob (vertical bob) also rises walk->run then falls for sprint, for the
    same reason real efficient running minimises vertical oscillation
    relative to a jog as pace increases, rather than bouncing harder.

Blend is a two-segment lerp across three keyframes at moveAmt 0.55 / 1.0 /
1.5 (below 0.55 pins to the WALK shape -- amplitude still fades to zero at
a standstill via the existing gFade gate, only the SHAPE stays walk-like all
the way down instead of degrading toward run's shape). This is the same
structure as the turn-in-place pivot-step's own accumulate-then-fire state
machine and the footstep system's RUN_ON/RUN_OFF hysteresis: numeric
constants doing a state-machine's job, not a new abstraction layered on top.

Everything changed here is DEFAULT locomotion pose only -- hip/knee
rotation, upperYaw, upperPitch, armRx/armLx, elbRx/elbLx, e.bob. Every
combat state (attack swings, dodge, block, bash, cast, mount specials,
draw) sets these same variables again further down in animate() and
overwrites whatever this block computed, exactly as before this patch --
confirmed by re-reading that whole cascade before writing this patch.
Combat hit timing (e.st vs a.wind/a.act) is untouched. e.phase's own
increment formula (the cadence, which footTick_ and multiplayer footstep
sync both read) is untouched -- only the AMPLITUDE and SHAPE riding on top
of that phase changed, never its rate.
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
# 1. Gait tables, module scope, right before the game class so they're built
#    once (not per-entity, not per-frame) and in scope for animate() below.
# ---------------------------------------------------------------------------
OLD_ANCHOR = """/* EDITOR-END */

class Component extends DCLogic {"""

NEW_ANCHOR = """/* EDITOR-END */

// Locomotion gait blend (patch 73.140): three keyed silhouettes for the
// biped walk cycle -- WALK, RUN, SPRINT -- read by animate() below. RUN
// reproduces the pre-patch formula's numbers exactly at e.moveAmt === 1 (the
// game's one non-sprint move speed), so ordinary movement doesn't shift.
// WALK and SPRINT are deliberately NOT that same curve scaled smaller/larger
// -- that was Kevin's whole complaint, that all three speeds were one curve
// with a different multiplier. Each has its own shape:
//   hip/knee    peak stride and knee-drive amplitude (radians)
//   curve       the knee's flexion exponent -- low is a round, gentle tuck
//               (walk), high is a sharp, snappy drive (sprint)
//   lean/yawC   forward torso pitch vs. counter-rotation yaw. yawC is
//               NOT monotonic: it peaks at run and drops for sprint, because
//               a real sprinter stabilises the torso and drives the arms
//               sagittally instead of twisting, trading rotation for drive
//   armSw/elbFold  arm swing and elbow fold amplitude (radians)
//   bob         vertical bob amplitude -- also non-monotonic; an efficient
//               sprinter minimises wasted vertical motion versus a jog
const GAIT_WALK = { hip: 0.40, knee: 0.68, curve: 1.00, lean: 0.018, yawC: 0.075, armSw: 0.16, elbFold: 0.16, bob: 0.040 };
const GAIT_RUN = { hip: 0.70, knee: 1.65, curve: 1.40, lean: 0.110, yawC: 0.160, armSw: 0.341, elbFold: 0.31, bob: 0.060 };
const GAIT_SPRINT = { hip: 0.92, knee: 2.05, curve: 1.75, lean: 0.300, yawC: 0.110, armSw: 0.62, elbFold: 0.62, bob: 0.050 };

class Component extends DCLogic {"""

sub(OLD_ANCHOR, NEW_ANCHOR, 'gait tables before class (73.140)')

# ---------------------------------------------------------------------------
# 2. Hip/knee stride: drop the spd = min(1, moveAmt) clamp, blend by gait.
# ---------------------------------------------------------------------------
OLD_HIPKNEE = """    e.phase += dt * (5 + e.moveAmt * 5) * (e.moveAmt > 0.05 ? 1 : 0.18);
    const sw = Math.sin(e.phase) * 0.62 * e.moveAmt;
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
    } else { P.legR.rotation.x = sw; P.legL.rotation.x = -sw; }"""

NEW_HIPKNEE = """    e.phase += dt * (5 + e.moveAmt * 5) * (e.moveAmt > 0.05 ? 1 : 0.18);
    const sw = Math.sin(e.phase) * 0.62 * e.moveAmt;
    const spd = Math.min(1, e.moveAmt || 0);
    // Gait blend (patch 73.140): walk/run/sprint as three keyed shapes, not
    // one curve scaled by a clamped speed number. gFade is the same
    // standstill-to-moving fade the old code used (min(1, spd*3)); gt is
    // where e.moveAmt sits between the WALK/RUN/SPRINT keyframes (0.55 /
    // 1.0 / 1.5). Below 0.55 pins to the WALK shape rather than
    // extrapolating past it, so a slow shuffle still reads as a small walk.
    const gFade = Math.min(1, spd * 3);
    const gma = Math.min(1.5, e.moveAmt || 0);
    let gA0, gA1, gt;
    if (gma <= 0.55) { gA0 = GAIT_WALK; gA1 = GAIT_RUN; gt = 0; }
    else if (gma <= 1.0) { gA0 = GAIT_WALK; gA1 = GAIT_RUN; gt = (gma - 0.55) / 0.45; }
    else { gA0 = GAIT_RUN; gA1 = GAIT_SPRINT; gt = (gma - 1.0) / 0.5; }
    const gHip = (gA0.hip + (gA1.hip - gA0.hip) * gt) * gFade;
    const gKnee = (gA0.knee + (gA1.knee - gA0.knee) * gt) * gFade;
    const gCurve = gA0.curve + (gA1.curve - gA0.curve) * gt;
    const gLean = (gA0.lean + (gA1.lean - gA0.lean) * gt) * gFade;
    const gYawC = (gA0.yawC + (gA1.yawC - gA0.yawC) * gt) * gFade;
    const gArmSw = (gA0.armSw + (gA1.armSw - gA0.armSw) * gt) * gFade;
    const gElbFold = (gA0.elbFold + (gA1.elbFold - gA0.elbFold) * gt) * gFade;
    const gBob = gA0.bob + (gA1.bob - gA0.bob) * gt;
    if (P.kneeR) {
      // A stride, not scissors: the swing leg's knee flexes hard while the
      // stance leg stays near straight. Phase offset -0.65 puts peak flexion
      // mid-swing, where a real leg tucks to clear the ground.
      const hip = Math.sin(e.phase) * gHip;
      P.legR.rotation.x = hip; P.legL.rotation.x = -hip;
      P.kneeR.rotation.x = 0.06 + gKnee * Math.pow(Math.max(0, Math.sin(e.phase - 0.65)), gCurve);
      P.kneeL.rotation.x = 0.06 + gKnee * Math.pow(Math.max(0, Math.sin(e.phase - 0.65 + Math.PI)), gCurve);
    } else { P.legR.rotation.x = sw; P.legL.rotation.x = -sw; }"""

sub(OLD_HIPKNEE, NEW_HIPKNEE, 'hip/knee gait blend (73.140)')

# ---------------------------------------------------------------------------
# 3. Vertical bob: same clamp bug, same fix.
# ---------------------------------------------------------------------------
OLD_BOB = """    e.bob = (Math.abs(Math.sin(e.phase)) * (0.030 + 0.030 * Math.min(1, e.moveAmt || 0)) * Math.min(1, (e.moveAmt || 0) * 3) + (e._pivLift || 0) * 0.012) * (1 - Math.max(e._rowT || 0, e._swimT || 0));"""

NEW_BOB = """    e.bob = (Math.abs(Math.sin(e.phase)) * gBob * Math.min(1, (e.moveAmt || 0) * 3) + (e._pivLift || 0) * 0.012) * (1 - Math.max(e._rowT || 0, e._swimT || 0));"""

sub(OLD_BOB, NEW_BOB, 'vertical bob gait blend (73.140)')

# ---------------------------------------------------------------------------
# 4. Torso counter-rotation, lean, arm swing and elbow fold: replace the
#    flat *moveAmt scale with the same gait blend.
# ---------------------------------------------------------------------------
OLD_UPPER = """    // Shoulders lead: the upper body counter-rotates against the stride, and
    // during a swing it drives the whole arc.
    let upperYaw = -Math.sin(e.phase) * 0.16 * e.moveAmt;
    let upperPitch = e.moveAmt * 0.11;
    let armRx = -sw * 0.55, armLx = sw * 0.55, armRy = 0, armRz = 0.04, armLz = -0.06, handRy = 0, handRz = 0;
    // elbows follow the swing: bend as the arm comes forward, like a person
    let elbRx = -0.14 - Math.max(0, sw) * 0.50, elbRy = 0, elbRz = 0;
    let elbLx = -0.14 - Math.max(0, -sw) * 0.50, elbLy = 0, elbLz = 0;"""

NEW_UPPER = """    // Shoulders lead: the upper body counter-rotates against the stride, and
    // during a swing it drives the whole arc. Amplitudes come from the same
    // walk/run/sprint gait blend as the legs (patch 73.140) instead of a
    // flat *moveAmt scale, so a sprint drives the torso forward hard while
    // twisting it LESS than a run does -- see the GAIT_* comment above the
    // class for why that's deliberate, not a typo.
    let upperYaw = -Math.sin(e.phase) * gYawC;
    let upperPitch = gLean;
    let armRx = -Math.sin(e.phase) * gArmSw, armLx = Math.sin(e.phase) * gArmSw, armRy = 0, armRz = 0.04, armLz = -0.06, handRy = 0, handRz = 0;
    // elbows follow the swing: bend as the arm comes forward, like a person
    let elbRx = -0.14 - Math.max(0, Math.sin(e.phase)) * gElbFold, elbRy = 0, elbRz = 0;
    let elbLx = -0.14 - Math.max(0, -Math.sin(e.phase)) * gElbFold, elbLy = 0, elbLz = 0;"""

sub(OLD_UPPER, NEW_UPPER, 'torso/arm gait blend (73.140)')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 73.140 applied: walk/run/sprint gait blend')
