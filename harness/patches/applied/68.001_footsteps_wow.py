#!/usr/bin/env python3
"""Patch 68.001: footstep sounds, WoW-referenced, material and gait aware.

Kevin's ask: footsteps that change tone between walking and running, blend
seamlessly, change with the ground material (wood, dirt, sand, metal), cover
the turn-in-place foot shuffle, and apply to the player and to NPCs, using
World of Warcraft as the reference and looking at how professional sound
engineers actually solve this. "Really think this part through."

RESEARCH, briefly (full writeup lands in SOUND-TRACK-HANDOFF.md):
- Industry technique for surface-aware footsteps is a downward trace to a
  physical material, an animation-driven trigger (not a distance tracker),
  random-no-immediate-repeat sample selection, and gait handled as a Blend
  Space so a walk/run mix never mis-triggers mid-transition.
- WoW's own terrain footstep audio (Wowhead's Footsteps category, sample
  names MON_Footstep_Bipedal_Foot_<size>_<material>) turned out to be ONE
  POOL of one-shot variants PER MATERIAL, with no separate walk/run
  recordings at all. WoW differentiates gait by animation cadence and
  impact force, not by swapping samples. That is the shape this patch
  copies: one texture per material (three variants, model-lab/sfx-samples.js,
  prepared and verified earlier this session), gait as a playback-time
  gain/pitch change.

WHY THIS CAN HOOK STRAIGHT INTO animate() RATHER THAN ADD A NEW TRACKER:
The rig already has everything a professional system builds from scratch.
e.phase is a shared clock that already drives the leg-swing sine and already
speeds up with e.moveAmt (0 idle, 1 walk, up to 1.5 sprint) - exactly WoW's
own cadence-not-samples idea, for free. e._shufA / e._shufPh already exist
too: the turn-in-place shoulder-swing "shuffle" rig Kevin asked for earlier.
So this patch adds three small methods and one call site, all reading state
the rig already computes, rather than a parallel distance-travelled system:

  footMat_(e)   what the ground is under e, right now.
  footTick_(e, dt, inBoat)   called once a frame from inside animate(), right
                after the shuffle block computes this frame's e._shufA and
                e._shufPh (so it reads this frame's numbers, not last frame's).
                Fires at most one footstep per call: a distant NPC's animate()
                runs less often and catches up with a bigger dt (see the LOD
                skip around stepEntity), which can walk e.phase across more
                than one pi in a single call. This treats that as "you missed
                some strides while off-screen," not "play four footsteps at
                once."
  footPlay_(e, mat, running, shuffle)   picks a rotating a/b/c variant
                (chop/mine's own no-immediate-repeat convention, patch 41),
                applies gain+detune for the gait, and reuses sfxAtten_ so a
                distant NPC's footsteps fade exactly like their swing or hit
                sounds already do.

GAIT: hysteresis on e.moveAmt (RUN_ON 1.15, RUN_OFF 1.0) so it cannot flicker
at the walk/sprint boundary. moveAmt settles at exactly 1.0 walking and 1.5
sprinting (this.C.SPRINT is exactly 1.5x this.C.SPEED), so the band sits
cleanly between the two states a real player produces.

STRIDE PARTITION: normal-stride footsteps fire when Math.min(1, moveAmt) is
at least 0.1; shuffle footsteps fire below that, and only while e._shufA (the
existing turn-in-place amplitude) is above the same 0.02 threshold the visual
rig already uses to turn the shuffle on. The two are mutually exclusive by
construction, so a player rotating in place while barely drifting forward
never gets both a stride footstep and a shuffle footstep on the same frame.

MATERIAL: zoneAt() is the only per-position signal the world exposes today.
IRONSPIRE (the mountain/forge zone) reads as metal; SUNCOAST, SUNSCORCH and
ISLES (beach and desert) read as sand; everything else defaults to dirt,
which is stretched to also cover grass, forest floor and swamp mud since none
of those has a recorded material yet. A collider can also carry a 'mat' tag
for a future wood dock, bridge or floor, checked first - but nothing in the
world tags a collider that way yet, so it is scaffolding, exactly like the
'mat' field patch 58.641 built into shotSurface_ for arrows and never wired
up either. This does NOT reuse shotSurface_ itself: that function's height
gate is written for a projectile's true world Y, and a walking character's
e.pos.y is not that (animate() only ever sets it while swimming or boating),
so calling shotSurface_ with a footstep's position would compare against the
wrong number. footMat_ below does its own dx/dz-only scan over the same
collider records instead.

GATING: no footsteps while swimming (e.swimF), boating (inBoat, both the
local player's own boat and a passenger's e._boatOn), riding a mount
(e.ridingF), or for a wraith (e.wraith - floats, and already hides its own
legs in dressVillain, patch unknown/pre-existing). e.state === 'dead' is
checked too even though animate() already returns before reaching this call
for a dead entity, so the guard can never actually trip today - left in
because footTick_ is a small, independently reachable method and a future
edit to animate()'s early-return should not have to remember this dependency.

WHAT THIS DOES NOT DO: quadrupeds (the donkey mount) and anything without a
knee joint (P.kneeR) are silently skipped - there is no quadruped footstep
material or gait design in this patch, and four legs on packed dirt is a
different sound than two boots on it. Road surface (roadAt) is not read
separately; roads fall under the dirt default already. Attack-envelope
shaping per gait (a run "landing harder" as a shorter, punchier transient) is
not implemented - the sample player exposes gain, detune, loop and start
time, not per-play envelope shaping, so gait reads as louder and a shade
lower in pitch, which is the same lever WoW itself leans on (impact force),
just without a bespoke DSP stage per play.

Two blocks:
1. The 12 footstep samples, generated FROM model-lab/sfx-samples.js (already
   edited and verified this session: 3 variants x 4 materials, shaped against
   real WoW reference measurements - see the comment on that block for the
   full derivation).
2. footMat_ / footTick_ / footPlay_, and the one call site inside animate().
"""
import io, os

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()


def one(anchor, label):
    n = s.count(anchor)
    assert n == 1, '%s matched %d times' % (label, n)


def sub(anchor, new, label):
    global s
    one(anchor, label)
    s = s.replace(anchor, new)


# ---------------------------------------------------------------------------
# 1. the samples (see model-lab/sfx-samples.js for the full derivation
#    comment; this just carries that block into the bundle, same mechanism
#    every prior sample-adding patch back to 30_sfx_samples.py has used)
# ---------------------------------------------------------------------------
m0 = mod.find('  // FOOTSTEPS (patch 68.x)')
assert m0 > 0, 'footsteps block missing from model-lab/sfx-samples.js'
m1 = mod.find('\n};', m0)
assert m1 > m0
block = '\n'.join(('  ' + ln) if ln.strip() else '' for ln in mod[m0:m1].split('\n'))

# Anchor on the declaration and walk to its close rather than on a sample
# key - a later track re-emitting this object has shifted key indentation
# before (58.641's note), and an anchor on a key would silently find nothing.
d0 = s.find('    const SFX_SAMPLES = {')
assert d0 > 0, 'SFX_SAMPLES declaration not found'
b1 = s.find('\n    };', d0)
assert b1 > d0, 'SFX_SAMPLES close not found'
s = s[:b1] + '\n' + block + s[b1:]

# ---------------------------------------------------------------------------
# 2. the trigger. One call site inside animate(), right after this frame's
#    shuffle amplitude/phase are computed, plus three new methods placed
#    right after animate() closes.
# ---------------------------------------------------------------------------
sub(
    """    if (P.kneeR) e._pvY = e.vyaw || 0;
    e.bob = (Math.abs(Math.sin(e.phase)) * (0.030 + 0.030 * Math.min(1, e.moveAmt || 0)) * Math.min(1, (e.moveAmt || 0) * 3) + ((e._shufA || 0) > 0.02 ? Math.abs(Math.sin((e._shufPh || 0) * 6)) * 0.012 * e._shufA : 0)) * (1 - Math.max(e._rowT || 0, e._swimT || 0));""",
    """    if (P.kneeR) e._pvY = e.vyaw || 0;
    // Footsteps (patch 68). Reads this frame's e.phase and e._shufA/e._shufPh,
    // just computed above, so a footstep lands on the frame the rig actually
    // plants that foot rather than on a separately tracked clock.
    this.footTick_(e, dt, inBoat);
    e.bob = (Math.abs(Math.sin(e.phase)) * (0.030 + 0.030 * Math.min(1, e.moveAmt || 0)) * Math.min(1, (e.moveAmt || 0) * 3) + ((e._shufA || 0) > 0.02 ? Math.abs(Math.sin((e._shufPh || 0) * 6)) * 0.012 * e._shufA : 0)) * (1 - Math.max(e._rowT || 0, e._swimT || 0));""",
    'footTick_ call site')

sub(
    """    // quadrupeds: the rig pass owns every joint, after everything above
    if (e.qr) this.poseQuadRig(e, dt);
  }

  // ------------------------------------------------------------- speech bubbles""",
    """    // quadrupeds: the rig pass owns every joint, after everything above
    if (e.qr) this.poseQuadRig(e, dt);
  }

  // ----------------------------------------------------------------- footsteps
  // Ground material under e, right now. Zone default first (see the patch
  // docstring for the material-to-zone mapping), collider 'mat' tag override
  // second - scaffolding for a future wood dock/bridge/floor, inert until a
  // builder actually tags a collider that way, same state shotSurface_'s own
  // 'mat' field has been in since patch 58.641.
  footMat_(e) {
    if (this.colliders && this.colliders.length) {
      for (let i = 0; i < this.colliders.length; i++) {
        const c = this.colliders[i];
        if (!c.mat) continue;
        const dx = e.pos.x - c.x, dz = e.pos.z - c.z;
        const on = c.r ? (dx * dx + dz * dz < c.r * c.r)
                        : (Math.abs(dx) < c.hw && Math.abs(dz) < c.hd);
        if (on) return c.mat;
      }
    }
    let z = null;
    try { z = this.zoneAt(e.pos.x, e.pos.z); } catch (err) {}
    if (z === 'IRONSPIRE') return 'metal';
    if (z === 'SUNCOAST' || z === 'SUNSCORCH' || z === 'ISLES') return 'sand';
    return 'dirt';
  }

  // Fires at most one footstep per call - see the patch docstring on why a
  // skipped-frame catch-up dt must not burst out every missed stride.
  footTick_(e, dt, inBoat) {
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
  }

  // Rotating a/b/c variant, same no-immediate-repeat convention chop/mine use
  // (patch 41's GVAR block) - a whole run across a courtyard never sounds
  // like one clip retriggering. Gait is louder and a shade lower in pitch for
  // a run rather than a different recording, per the WoW research in the
  // patch docstring; a shuffle is a half-lift, quieter than either. Distance
  // falloff comes from sfxAtten_/this._att, the same path every other sound
  // in the world uses, so a nearby NPC's footsteps are audible and a distant
  // one's are not.
  footPlay_(e, mat, running, shuffle) {
    if (!this.started || !this.ac || !this._samples || !this._samples.ready()) return;
    const att = this.sfxAtten_(e);
    if (att <= 0.02) return;          // too far to be part of the world mix
    this._footAlt = (this._footAlt || 0) + 1;
    const pick = 'foot-' + mat + '-' + 'abc'[this._footAlt % 3];
    if (!this._samples.has(pick)) return;
    const gain = shuffle ? 0.30 : (running ? 0.58 : 0.46);
    const detune = (running ? -70 : 0) + (Math.random() * 2 - 1) * 90;
    this._att = att;
    try { this._samples.play(pick, { gain: gain, detune: detune }); } finally { this._att = 1; }
  }

  // ------------------------------------------------------------- speech bubbles""",
    'footstep methods')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 68.001 applied: footsteps (samples + trigger)')
