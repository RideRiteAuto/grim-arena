#!/usr/bin/env python3
"""Patch 68.520: replace the turn-in-place shuffle with a real pivot-step rig.

Kevin's report: turning in place (mouse-look while standing still) makes the
legs jitter, and it's obvious to every new player within seconds. He does not
want an audio workaround; he wants the animation itself replaced.

DIAGNOSIS FIRST (per standing instruction - read the real live code before
writing anything, so nothing gets rebuilt that already exists): audited
animate()'s turn-in-place block and footTick_'s shuffle branch directly in
/tmp/game-src.html. This is not a rebuild of a missing system - it is a
targeted replacement of an identified, specific defect in an existing one.

The old "shuffle" (added in patch 68.001, right alongside the footstep
system) drove the whole thing straight off the RAW per-frame delta of the
view yaw:

    e._shufA  = clamp(e._shufA + (|dY| > 0.004 ? 0.3 : -0.08))   -- NOT dt-scaled
    e._shufPh += |dY| * 3.2 + dt * 1.5 * e._shufA
    sp = sin(e._shufPh * 6)                                       -- drives both legs

Two compounding bugs:

  1. `_shufA`'s ramp (+0.3 / -0.08) is a flat per-CALL increment, not scaled
     by dt. At 60fps it hits full amplitude in ~4 frames; at 30fps in ~4
     frames of TWICE the wall-clock speed. The shuffle amplitude is
     frame-rate dependent, so the same turn looks and sounds different by
     the player's frame rate, and snaps on/off rather than easing.
  2. `_shufPh` (the phase driving the leg sine wave) advances every frame by
     a term proportional to `|dY|`, the raw per-frame mouse-look delta.
     Mouse input is not perfectly smooth frame to frame - small stalls,
     coalesced OS input batches, acceleration curves - and every bit of
     that noise went straight into the leg animation's speed with no
     smoothing once triggered. That IS the jitter: the legs are quite
     literally redrawing themselves off mouse noise, every frame, for as
     long as the view keeps moving. footTick_'s shuffle branch rode the
     same noisy `_shufPh` via a phase-crossing check, so the stutter was
     audible too.

This is a design problem, not a tuning problem - no amount of retuning the
0.004 threshold or the 3.2/1.5 constants fixes a system whose speed IS the
raw input noise. Replacing it, as instructed, with a real state machine.

THE FIX: a discrete pivot-step.

Real people (and WoW's turn-in-place, the reference this project already
leans on for footsteps) don't wobble continuously while turning - they take
a foot off the ground, pivot it, and plant it again every so often,
alternating feet. So: yaw rotation accumulates quietly in the background as
the player turns (`e._pivAccum`, in actual radians - summing real per-frame
yaw deltas is exactly frame-rate independent, unlike the old amplitude
ramp). Once it crosses ~31 degrees (PIVOT_STEP_RAD), ONE step fires: a
single foot lifts, swings, and plants over a fixed PIVOT_STEP_DUR on ITS OWN
internal timer - once started, further mouse noise that frame cannot speed
it up, slow it down, or restart it. Feet alternate every step. If the view
stops turning mid-accumulation, the partial accumulation bleeds off
(dt-scaled, after a short idle grace) instead of lingering to ambush a later
small turn.

footTick_'s shuffle branch used to re-derive "did we cross a phase boundary"
from the same noisy `_shufPh` it shares no ownership of. Now animate() just
sets a one-frame `e._pivPlant = true` on the exact frame a step completes
(the plant), and footTick_ reads-and-clears that flag: one footstep sound,
exactly on the plant, every time, no heuristics, no shared noisy phase.

`e._shufA`/`e._shufPh` are retired entirely - grepped the whole tree first;
harness/sfxroute.js's section I was the only other reader, updated alongside
this patch. `e.bob`'s small shuffle-linked bob term now reads the new step's
own lift curve (`e._pivLift`) instead.
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
# 1. animate(): swap the whole shuffle block for the pivot-step state
#    machine. Anchored on the walk-cycle fallthrough through the e.bob line
#    so the footTick_ call site and bob's shuffle term move together.
# ---------------------------------------------------------------------------
OLD_PIVOT = """    } else { P.legR.rotation.x = sw; P.legL.rotation.x = -sw; }
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
    if (P.kneeR) e._pvY = e.vyaw || 0;
    // Footsteps (patch 68). Reads this frame's e.phase and e._shufA/e._shufPh,
    // just computed above, so a footstep lands on the frame the rig actually
    // plants that foot rather than on a separately tracked clock.
    this.footTick_(e, dt, inBoat);
    e.bob = (Math.abs(Math.sin(e.phase)) * (0.030 + 0.030 * Math.min(1, e.moveAmt || 0)) * Math.min(1, (e.moveAmt || 0) * 3) + ((e._shufA || 0) > 0.02 ? Math.abs(Math.sin((e._shufPh || 0) * 6)) * 0.012 * e._shufA : 0)) * (1 - Math.max(e._rowT || 0, e._swimT || 0));"""

NEW_PIVOT = """    } else { P.legR.rotation.x = sw; P.legL.rotation.x = -sw; }
    if (P.backR) { P.backR.rotation.x = -sw; P.backL.rotation.x = sw; }
    // Turn-in-place pivot-step (patch 68.520, replaces the 68.001 shuffle -
    // see the patch docstring for why the old continuous, mouse-delta-driven
    // wobble was jittery by construction, not just under-tuned). A discrete
    // state machine: yaw rotation quietly accumulates in real radians while
    // stationary, and every PIVOT_STEP_RAD of turn fires ONE foot-plant step
    // that runs to completion on its own timer, alternating feet, regardless
    // of further mouse noise that frame. footTick_ (below) plays the
    // footstep sound once per step, exactly on the plant.
    const PIVOT_STEP_RAD = 0.55, PIVOT_STEP_DUR = 0.24;
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
    if (P.kneeR) e._pvY = e.vyaw || 0;
    // Footsteps (patch 68, plant hookup reworked in 68.520). Reads this
    // frame's e.phase and e._pivPlant, just computed above, so a footstep
    // lands on the frame the rig actually plants that foot rather than on a
    // separately tracked clock.
    this.footTick_(e, dt, inBoat);
    e.bob = (Math.abs(Math.sin(e.phase)) * (0.030 + 0.030 * Math.min(1, e.moveAmt || 0)) * Math.min(1, (e.moveAmt || 0) * 3) + (e._pivLift || 0) * 0.012) * (1 - Math.max(e._rowT || 0, e._swimT || 0));"""

sub(OLD_PIVOT, NEW_PIVOT, 'animate() shuffle block -> pivot-step (68.520)')

# ---------------------------------------------------------------------------
# 2. footTick_: read-and-clear e._pivPlant instead of the old _shufA/_shufPh
#    phase-crossing heuristic.
# ---------------------------------------------------------------------------
OLD_FOOTTICK = """  footTick_(e, dt, inBoat) {
    // Simulated clock for the NPC footstep voice cap (patch 68.417, see
    // footVoiceAllow_ below) - accumulated from real per-frame dt rather
    // than this.ac's audio-context time, so it advances correctly whether
    // or not audio has started, and advances realistically under the test
    // harness's synchronous drivePhase loop too.
    this._footNow = (this._footNow || 0) + (dt || 0);
    if (inBoat || e.swimF || e.ridingF || e.wraith || e.state === 'dead'
        || !e.parts || !e.parts.kneeR) {
      e._footPh = e.phase; e._footShPh = (e._shufPh || 0) * 6;
      return;
    }
    const RUN_ON = 1.15, RUN_OFF = 1.0;
    const running = (e._footRun = (e.moveAmt || 0) >= (e._footRun ? RUN_OFF : RUN_ON));
    const spd = Math.min(1, e.moveAmt || 0);
    if (spd >= 0.1) {
      if (e._footPh === undefined) e._footPh = e.phase;
      const a = Math.floor(e._footPh / Math.PI), b = Math.floor(e.phase / Math.PI);
      if (b !== a) this.footPlay_(e, this.footMat_(e), running, false);
      e._footPh = e.phase;
      e._footShPh = (e._shufPh || 0) * 6;
    } else {
      e._footPh = e.phase;
      const shPh = (e._shufPh || 0) * 6;
      if ((e._shufA || 0) > 0.02) {
        if (e._footShPh === undefined) e._footShPh = shPh;
        const a = Math.floor(e._footShPh / Math.PI), b = Math.floor(shPh / Math.PI);
        if (b !== a) this.footPlay_(e, this.footMat_(e), false, true);
      }
      e._footShPh = shPh;
    }
  }"""

NEW_FOOTTICK = """  footTick_(e, dt, inBoat) {
    // Simulated clock for the NPC footstep voice cap (patch 68.417, see
    // footVoiceAllow_ below) - accumulated from real per-frame dt rather
    // than this.ac's audio-context time, so it advances correctly whether
    // or not audio has started, and advances realistically under the test
    // harness's synchronous drivePhase loop too.
    this._footNow = (this._footNow || 0) + (dt || 0);
    // e._pivPlant (patch 68.520) is a one-frame flag animate() sets on the
    // exact frame a turn-in-place pivot-step plants its foot. Read and clear
    // it up front so every path below (including the gated-off early
    // return) consumes it exactly once, regardless of which branch runs.
    const planted = e._pivPlant; e._pivPlant = false;
    if (inBoat || e.swimF || e.ridingF || e.wraith || e.state === 'dead'
        || !e.parts || !e.parts.kneeR) {
      e._footPh = e.phase;
      return;
    }
    const RUN_ON = 1.15, RUN_OFF = 1.0;
    const running = (e._footRun = (e.moveAmt || 0) >= (e._footRun ? RUN_OFF : RUN_ON));
    const spd = Math.min(1, e.moveAmt || 0);
    if (spd >= 0.1) {
      if (e._footPh === undefined) e._footPh = e.phase;
      const a = Math.floor(e._footPh / Math.PI), b = Math.floor(e.phase / Math.PI);
      if (b !== a) this.footPlay_(e, this.footMat_(e), running, false);
      e._footPh = e.phase;
    } else {
      e._footPh = e.phase;
      if (planted) this.footPlay_(e, this.footMat_(e), false, true);
    }
  }"""

sub(OLD_FOOTTICK, NEW_FOOTTICK, 'footTick_ -> reads e._pivPlant (68.520)')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 68.520 applied: turn-in-place pivot-step rework')
