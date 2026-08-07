#!/usr/bin/env python3
"""Patch 73.260: turn-in-place refinements (locomotion overhaul phase 4).

Continuation of the pivot-step system shipped in 68.520. Kevin live-tested
that patch and asked for it to go further using the same GDC-talk / engine
research he asked for on the walk/run/sprint work: "we might be able to do
a little better using the methods you're talking about... flesh out your
plan a little more." Five concrete refinements, all against the pivot-step
state machine already in animate(), none of them a new system:

  A. Turn-rate blended step size and duration. Every step used to run on
     the same fixed 0.24s regardless of how fast the view was actually
     turning - a slow deliberate look-around and a fast flick-turn produced
     an identical foot animation. Now a low-pass-filtered turn rate
     (e._pivRateS, same Math.min(1, dt*k) smoothing style already used
     throughout this rig) sets the step's duration (0.30s slow -> 0.15s
     fast) and a small swing/lift amplitude boost, at the moment the step
     fires.

  B. Closes the "eaten angle" gap. The VISUAL yaw (e.vyaw) damps toward the
     logical yaw at a fast, fixed rate (~22/s, converges in 2-3 frames) set
     at the top of animate(), completely independent of the leg step's own
     fixed-duration swing below it. That meant the body finished turning
     almost immediately while the foot was still mid-swing "catching up" to
     a rotation that had already happened - the gap. While a step is
     actively swinging, the yaw damping rate now matches the step's own
     duration instead of the fast default, so the torso's visible rotation
     is paced by the same curve driving the foot. Only active during a
     pivot step; aiming, movement and swimming yaw damping are untouched.

  C. Graded torso counter-rotation. The pivot-step used to move only the
     legs - zero counter-twist through the torso, unlike walking (which has
     had upperYaw for a long time). Reuses the exact distribution shape
     already proven by the idle-sway system a few lines down (body gets the
     bigger share, upper torso the smaller opposing share) rather than
     inventing a new one: e._pivTwist feeds additively into the same
     upperYaw variable the phase-1 gait blend (73.140) already computes and
     the rig already damps every frame, so it composes for free with
     combat states overwriting upperYaw and with the existing smoothing.

  D. Direction-based, not alternating, foot choice. e._pivFoot used to be a
     flat toggle every step regardless of which way the view was turning.
     Now it's set by a low-pass-filtered turn DIRECTION (e._pivDirS) at the
     moment a step fires: turning the same way twice in a row steps with
     the same foot, a direction reversal switches feet - matching how an
     actual pivot turn works, instead of a metronome.

  E. Hip-sway weight shift through the step, explicitly sequenced to land
     in this same patch since it reuses phase 1's stride-hip machinery and
     idle-sway's z-rotation channel rather than adding a new transform.
     P.legR/legL.rotation.z is already claimed by the mount-pose code (it
     force-resets to 0 whenever not riding, a few lines after this block),
     so the weight lean rides on e.body/P.upper's existing idle-sway
     z-rotation instead - additive, so normal idle sway is unaffected when
     no step is active.

Confirmed by re-reading the whole function before writing this patch: none
of A-E touch e.phase's increment (footstep cadence/audio timing untouched),
none touch combat state timing, and the only new per-frame state is the two
low-pass filters (e._pivRateS, e._pivDirS), which — like every other _piv*
field — live on the entity and are trivially safe to leave stale on
entities that never turn in place.

Regression found by the project's own harness/pivotstep.js (test D, "standing
still produced a phantom footstep") when this patch was run against it: the
turn accumulator (e._pivAccum) was fed by e.vyaw's frame-to-frame delta, the
same design 68.520 shipped with. That was fine at a fixed 22/s damping rate
(converges in 2-3 frames), but item B above intentionally SLOWS that rate
while a step is active, so after the player stops turning, e.vyaw can still
be several frames into catching up to e.yaw. The accumulator read that
catch-up motion as fresh turning, and on a long enough pre-idle turn it
crossed the 0.55 rad threshold during idle and fired a step nobody asked
for. Fixed by driving the accumulator from e.yaw's own wrapped frame delta
(the actual input) instead of e.vyaw's (the damped visual output) - verified
clean against the unmodified pivotstep.js suite (all of A-D pass, including
the frame-rate and noise-decoupling checks, which do not regress since input
yaw sums to the exact same total turn as before regardless of frame rate).
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
# 1. (B) Slow the visual-yaw damping rate while a pivot step is in flight,
#    so the torso paces the foot instead of finishing the turn on its own.
# ---------------------------------------------------------------------------
OLD_VYAW = """    e.vyaw += dy * (1 - Math.exp(-(e.swimF ? 7 : 22) * dt));"""

NEW_VYAW = """    // Turn-in-place pivot-step (B, patch 73.260): while a step is actively
    // swinging, pace the VISUAL yaw's own damping to roughly the step's
    // timescale instead of the fast default rate. The default converges in
    // 2-3 frames, far faster than the leg's fixed-duration swing, so the
    // torso used to finish rotating before the foot had visibly caught up -
    // the "eaten angle" gap. Slowing this rate only while a step is in
    // flight closes that gap without touching aiming, movement or swim yaw.
    const pivDampR = (P.kneeR && e._pivActive) ? Math.max(3.0, 1 / Math.max(0.08, e._pivDur || 0.24)) : (e.swimF ? 7 : 22);
    e.vyaw += dy * (1 - Math.exp(-pivDampR * dt));"""

sub(OLD_VYAW, NEW_VYAW, 'yaw damping rate during pivot step (73.260)')

# ---------------------------------------------------------------------------
# 2. (A, D) Turn-rate blended step size/duration, direction-based foot
#    choice. Full pivot-step block replacement.
# ---------------------------------------------------------------------------
OLD_PIVOT = """    const PIVOT_STEP_RAD = 0.55, PIVOT_STEP_DUR = 0.24;
    e._pivLift = 0;
    if (P.kneeR) {
      if (spd < 0.1) {
        const vy = e.vyaw || 0;
        const dY = vy - (e._pvY === undefined ? vy : e._pvY);
        if (!e._pivActive) {
          if (Math.abs(dY) > 0.0009) {
            e._pivAccum = (e._pivAccum || 0) + Math.abs(dY);
            e._pivIdleT = 0;
          } else if ((e._pivIdleT = (e._pivIdleT || 0) + dt) > 0.3) {
            e._pivAccum = Math.max(0, (e._pivAccum || 0) - dt * 1.4);
          }
          if ((e._pivAccum || 0) >= PIVOT_STEP_RAD) {
            e._pivAccum -= PIVOT_STEP_RAD;
            e._pivActive = true; e._pivT = 0;
            e._pivFoot = e._pivFoot === 0 ? 1 : 0;
          }
        }
        if (e._pivActive) {
          e._pivT += dt / PIVOT_STEP_DUR;
          if (e._pivT >= 1) { e._pivT = 1; e._pivActive = false; e._pivPlant = true; }
          const lift = Math.sin(Math.PI * e._pivT);
          const swing = 1 - (1 - e._pivT) * (1 - e._pivT);
          const stepLeg = e._pivFoot === 0 ? P.legR : P.legL;
          const stepKnee = e._pivFoot === 0 ? P.kneeR : P.kneeL;
          const anchorLeg = e._pivFoot === 0 ? P.legL : P.legR;
          stepLeg.rotation.x += 0.14 * swing;
          stepKnee.rotation.x += lift * 0.34;
          anchorLeg.rotation.x += -0.05 * swing;
          e._pivLift = lift;
        }
      } else {
        e._pivAccum = 0; e._pivActive = false; e._pivIdleT = 0;
      }
    }
    if (P.kneeR) e._pvY = e.vyaw || 0;"""

NEW_PIVOT = """    const PIVOT_STEP_RAD = 0.55;
    const PIVOT_DUR_MIN = 0.15, PIVOT_DUR_MAX = 0.30;
    e._pivLift = 0; e._pivTwist = 0; e._pivWeight = 0;
    if (P.kneeR) {
      if (spd < 0.1) {
        // Driven by the INPUT yaw's own frame delta (e.yaw), not the damped
        // VISUAL yaw (e.vyaw). vyaw is intentionally slowed while a step is
        // active (item B above) so the torso can still be several frames
        // into "catching up" to e.yaw after the player has already stopped
        // turning; accumulating that residual catch-up motion as if it were
        // fresh turning fired a phantom step during idle (caught by the
        // project's own pivotstep.js test D). e.yaw itself has no such lag,
        // so this reads exactly what the player's mouse actually did.
        const iy = e.yaw || 0;
        let dY = iy - (e._pvY === undefined ? iy : e._pvY);
        while (dY > Math.PI) dY -= Math.PI * 2;
        while (dY < -Math.PI) dY += Math.PI * 2;
        // Turn rate and direction, low-pass filtered so one noisy frame
        // can't flip the foot choice or spike the step speed.
        e._pivRateS = (e._pivRateS || 0) + (Math.abs(dY) / Math.max(dt, 1e-4) - (e._pivRateS || 0)) * Math.min(1, dt * 8);
        e._pivDirS = (e._pivDirS || 0) + ((dY > 0 ? 1 : dY < 0 ? -1 : 0) - (e._pivDirS || 0)) * Math.min(1, dt * 10);
        if (!e._pivActive) {
          if (Math.abs(dY) > 0.0009) {
            e._pivAccum = (e._pivAccum || 0) + Math.abs(dY);
            e._pivIdleT = 0;
          } else if ((e._pivIdleT = (e._pivIdleT || 0) + dt) > 0.3) {
            e._pivAccum = Math.max(0, (e._pivAccum || 0) - dt * 1.4);
          }
          if ((e._pivAccum || 0) >= PIVOT_STEP_RAD) {
            e._pivAccum -= PIVOT_STEP_RAD;
            e._pivActive = true; e._pivT = 0;
            // (A) turn-rate blended step size/duration: a fast flick-turn
            // gets a quicker, punchier step; a slow deliberate turn gets a
            // longer, more measured one.
            const rk = Math.max(0, Math.min(1, (e._pivRateS - 1.2) / 4.5));
            e._pivDur = PIVOT_DUR_MAX - (PIVOT_DUR_MAX - PIVOT_DUR_MIN) * rk;
            e._pivAmpK = 1 + rk * 0.4;
            // (D) direction-based foot choice: which foot pivots follows
            // which way the view is turning, not a metronome alternation.
            e._pivFoot = e._pivDirS >= 0 ? 0 : 1;
          }
        }
        if (e._pivActive) {
          e._pivT += dt / (e._pivDur || 0.24);
          if (e._pivT >= 1) { e._pivT = 1; e._pivActive = false; e._pivPlant = true; }
          const ampK = e._pivAmpK || 1;
          const lift = Math.sin(Math.PI * e._pivT) * ampK;
          const swing = (1 - (1 - e._pivT) * (1 - e._pivT)) * ampK;
          const stepLeg = e._pivFoot === 0 ? P.legR : P.legL;
          const stepKnee = e._pivFoot === 0 ? P.kneeR : P.kneeL;
          const anchorLeg = e._pivFoot === 0 ? P.legL : P.legR;
          stepLeg.rotation.x += 0.14 * swing;
          stepKnee.rotation.x += lift * 0.34;
          anchorLeg.rotation.x += -0.05 * swing;
          e._pivLift = lift;
          // (C) graded torso counter-rotation: feeds additively into the
          // shared upperYaw variable below (same distribution idea as the
          // idle-sway body/upper split) rather than writing P.upper
          // directly, since that transform is already damped toward
          // upperYaw every frame and a direct write here would just be
          // overwritten the same tick.
          e._pivTwist = 0.10 * swing * (e._pivFoot === 0 ? 1 : -1);
          // (E) weight shift onto the planted foot. legR/legL.rotation.z is
          // already claimed by the mount-pose reset below, so this rides
          // the idle-sway z-rotation channel instead (additive there).
          e._pivWeight = 0.028 * lift * (e._pivFoot === 0 ? -1 : 1);
        }
      } else {
        e._pivAccum = 0; e._pivActive = false; e._pivIdleT = 0;
      }
    }
    if (P.kneeR) e._pvY = e.yaw || 0;"""

sub(OLD_PIVOT, NEW_PIVOT, 'pivot-step turn-rate/direction/twist/weight (73.260)')

# ---------------------------------------------------------------------------
# 3. (E) Weight shift rides the existing idle-sway z-rotation channel.
# ---------------------------------------------------------------------------
OLD_SWAY = """      e.body.rotation.z = 0.016 * Math.sin(tN * 0.861) * idW;
      P.upper.rotation.z = -0.013 * Math.sin(tN * 0.861 + 0.5) * idW;"""

NEW_SWAY = """      e.body.rotation.z = 0.016 * Math.sin(tN * 0.861) * idW + (e._pivWeight || 0);
      P.upper.rotation.z = -0.013 * Math.sin(tN * 0.861 + 0.5) * idW + (e._pivWeight || 0) * 0.55;"""

sub(OLD_SWAY, NEW_SWAY, 'idle-sway carries pivot weight shift (73.260)')

# ---------------------------------------------------------------------------
# 4. (C) Torso counter-rotation feeds into the shared upperYaw variable.
# ---------------------------------------------------------------------------
OLD_UPPERYAW = """    let upperYaw = -Math.sin(e.phase) * gYawC + (e._pivTwist || 0);
    let upperPitch = gLean;"""

# Already inserted by patch 73.140 as a plain `-Math.sin(e.phase) * gYawC`;
# guard for either apply order by matching the 73.140 baseline directly.
OLD_UPPERYAW_BASE = """    let upperYaw = -Math.sin(e.phase) * gYawC;
    let upperPitch = gLean;"""

if s.count(OLD_UPPERYAW) == 1:
    sub(OLD_UPPERYAW, OLD_UPPERYAW, 'upperYaw already carries pivot twist (73.260)')
else:
    sub(OLD_UPPERYAW_BASE, OLD_UPPERYAW, 'torso counter-rotation into upperYaw (73.260)')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 73.260 applied: turn-in-place refinements A-E')
