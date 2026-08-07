#!/usr/bin/env python3
"""Patch 68.417: footstep NPC distance/volume mix fix.

Kevin's report, one of three footstep-quality issues raised after 68.001
shipped: "monster footsteps [are] audible at equal volume regardless of
distance when they should be quiet/distance-scaled." He also asked whether
there was already a distance-attenuation system before building anything,
worried this might duplicate something.

DIAGNOSIS FIRST (per that instruction): read the real sfxAtten_/sfx()/
footPlay_ implementations directly in /tmp/game-src.html before writing a
line of this patch. Confirmed footPlay_ already calls this.sfxAtten_(e) and
routes the result through this._att into _samples.play's own
`gain * (att ? att() : 1)` multiply - the exact same path every other sound
in the game uses. There is no missing or broken distance system. The real
defect is a MIX-BALANCE gap, not a routing gap:

  1. sfxAtten_'s shared curve (NEAR 7, FAR 46) was tuned for rare one-shot
     combat/spell events. Footsteps fire roughly twice a second per moving
     NPC, so "full volume out to 7m, audible out to 46m" means every NPC in
     a normal-size courtyard is within full or near-full volume at once,
     which reads as "loud regardless of distance" even though the number
     itself IS scaling correctly per NPC.
  2. The shipped gains (0.46 walk / 0.58 run / 0.30 shuffle) were sized for
     a sound that plays occasionally, not one that fires from every moving
     NPC in earshot roughly every half second.
  3. There is no cap on how many NPC footstep voices can sound at once -
     already flagged as a known gap in SOUND-TRACK-HANDOFF.md's own Next
     list (item 3, "a voice cap with per-sound cooldown") before Kevin ever
     reported this. Multiple NPCs walking near you all firing independently
     is what actually reads as "constant, undifferentiated noise" rather
     than "footsteps that get quieter as they walk away."

FIX, three parts, all scoped to footsteps only (the shared sfxAtten_ curve
used by combat/spells/arrows is untouched):

  footAtten_(t)   a footstep-specific attenuation curve, same inverse-
                  distance-with-faded-tail shape as sfxAtten_, but NEAR 4 /
                  FAR 20 instead of 7 / 46. Footfalls are quiet in the real
                  world and do not carry the way a spell discharge or a
                  weapon impact does - a tighter curve is a mix decision,
                  not an engine change, and reuses the identical formula so
                  there is only one attenuation SHAPE in the codebase, just
                  parameterised differently for two different sound classes.
                  The player's own footsteps are unaffected either way
                  (footAtten_ returns 1 for t === this.me exactly like
                  sfxAtten_ does).
  lower gains     0.46/0.58/0.30 -> 0.30/0.42/0.20. Roughly a third quieter,
                  sized for a sound that repeats constantly rather than one
                  that plays occasionally.
  footVoiceAllow_ a lightweight per-NPC voice cap: at most 2 NPC footstep
                  voices considered "active" in a rolling 0.22s window,
                  always keeping the closest (loudest) candidates - a new,
                  louder footstep can bump out the current window's quietest
                  entry, a quieter one is just dropped. The player's own
                  footsteps always bypass the cap.

                  The window clock is a SIMULATED clock (this._footNow,
                  accumulated from the real per-frame dt already passed into
                  footTick_ every call), not this.ac's real audio-context
                  time. This matters for two reasons, not just testability:
                  the cap is meant to model "how much simulated game time has
                  passed since the last voice," and dt IS that, exactly,
                  every frame, with no dependency on whether the AudioContext
                  is running, suspended, or hasn't been created yet (footTick_
                  itself has no such dependency, only footPlay_ does). It
                  also means harness/sfxroute.js's drivePhase helper, which
                  drives footTick_ synchronously with dt=0.033 per call,
                  advances this clock exactly like real gameplay frame-pacing
                  would, rather than staying frozen for an entire synchronous
                  test loop the way real wall-clock time would.

                  This is deliberately scoped to footsteps only, narrower
                  than the general engine-wide voice cap still on the Next
                  list (Phase 0, item 3) - that one is still owed for
                  combat/spell voices, this one only fixes the footstep case
                  Kevin reported.

Nothing about footMat_'s material resolution, footTick_'s triggering
conditions, or the sample pool changes. This is a pure mix/attenuation/cap
patch on top of 68.001, not a redesign - same convention as 67.452 (a
routing repoint, not new audio) and storm v4/frost v2 (measure the real
complaint, fix only what's actually wrong).

harness/sfxroute.js section I's walk/run/shuffle assertions needed a small
update alongside this patch (see harness/patches/68.417_sfxroute_section_i.py,
applied right after this one): they drove footTick_ in a tight synchronous
loop with no time passing, which the OLD cap-free footPlay_ tolerated fine,
but which the new per-NPC voice cap correctly throttles, exactly as it is
supposed to for a flood of same-instant triggers. The section still proves
everything it proved before; it just also proves the cap now.
"""
import io, os

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
# 1. footTick_: accumulate a simulated clock from the real per-frame dt, used
#    by the new voice cap below instead of real audio-context time.
# ---------------------------------------------------------------------------
OLD_FOOTTICK_HEAD = """  footTick_(e, dt, inBoat) {
    if (inBoat || e.swimF || e.ridingF || e.wraith || e.state === 'dead'
        || !e.parts || !e.parts.kneeR) {"""
one(OLD_FOOTTICK_HEAD, 'footTick_ head (pre-68.417)')

NEW_FOOTTICK_HEAD = """  footTick_(e, dt, inBoat) {
    // Simulated clock for the NPC footstep voice cap (patch 68.417, see
    // footVoiceAllow_ below) - accumulated from real per-frame dt rather
    // than this.ac's audio-context time, so it advances correctly whether
    // or not audio has started, and advances realistically under the test
    // harness's synchronous drivePhase loop too.
    this._footNow = (this._footNow || 0) + (dt || 0);
    if (inBoat || e.swimF || e.ridingF || e.wraith || e.state === 'dead'
        || !e.parts || !e.parts.kneeR) {"""
sub(OLD_FOOTTICK_HEAD, NEW_FOOTTICK_HEAD, 'footTick_ head -> + simulated clock (68.417)')

# ---------------------------------------------------------------------------
# 2. footPlay_: footstep-specific attenuation curve, lower gains, and the
#    new NPC voice cap.
# ---------------------------------------------------------------------------
OLD_FOOTPLAY = """  // Rotating a/b/c variant, same no-immediate-repeat convention chop/mine use
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
  }"""
one(OLD_FOOTPLAY, 'old footPlay_ (pre-68.417)')

NEW_FOOTPLAY = """  // Footstep-specific attenuation (patch 68.417). Same inverse-distance,
  // faded-tail shape as sfxAtten_, but tighter: footfalls are quiet in
  // reality and should not carry across a courtyard the way a spell
  // discharge or weapon impact does. NEAR/FAR are a mix decision, not an
  // engine change - the general sfxAtten_ curve used by combat/spells/
  // arrows is untouched. Returns 1 for the player's own footsteps exactly
  // like sfxAtten_ does.
  FOOT_NEAR = 4; FOOT_FAR = 20;
  footAtten_(t) {
    if (!t || !t.pos || !this.me || !this.me.pos || t === this.me) return 1;
    const dx = t.pos.x - this.me.pos.x, dz = t.pos.z - this.me.pos.z;
    const d = Math.sqrt(dx * dx + dz * dz);
    const NEAR = this.FOOT_NEAR, FAR = this.FOOT_FAR;
    if (d <= NEAR) return 1;
    if (d >= FAR) return 0;
    return (NEAR / d) * Math.min(1, (FAR - d) / (FAR * 0.25));
  }

  // Lightweight per-NPC footstep voice cap (patch 68.417). Real footsteps
  // fire roughly twice a second per moving NPC, so with no cap a courtyard
  // of five or six NPCs all reads as constant undifferentiated noise
  // regardless of any one NPC's own distance falloff. Keeps at most
  // FOOT_VOICE_CAP NPC footstep voices "active" within a short rolling
  // window of this._footNow (the simulated clock footTick_ accumulates from
  // real dt, see above - not this.ac's real audio-context time), always
  // favouring the closest (highest-att) candidates; a quieter/farther
  // candidate that doesn't beat the window's current worst entry is simply
  // dropped this play. The player's own footsteps always bypass the cap -
  // this only thins out what NPCs you hear at once, never your own feedback
  // about your own movement.
  FOOT_VOICE_CAP = 2; FOOT_VOICE_WINDOW = 0.22;
  footVoiceAllow_(e, att) {
    if (e === this.me) return true;
    const now = this._footNow || 0;
    const win = (this._footVoices = (this._footVoices || [])
      .filter((v) => now - v.t < this.FOOT_VOICE_WINDOW));
    if (win.length < this.FOOT_VOICE_CAP) { win.push({ t: now, att: att }); return true; }
    let worst = 0;
    for (let i = 1; i < win.length; i++) if (win[i].att < win[worst].att) worst = i;
    if (att > win[worst].att) { win[worst] = { t: now, att: att }; return true; }
    return false;
  }

  // Rotating a/b/c variant, same no-immediate-repeat convention chop/mine use
  // (patch 41's GVAR block) - a whole run across a courtyard never sounds
  // like one clip retriggering. Gait is louder and a shade lower in pitch for
  // a run rather than a different recording, per the WoW research in the
  // patch docstring; a shuffle is a half-lift, quieter than either. Distance
  // falloff comes from footAtten_/this._att (patch 68.417 - see above for why
  // this is a tighter curve than the shared sfxAtten_), gated by
  // footVoiceAllow_'s per-NPC cap, so a nearby NPC's footsteps are audible,
  // a distant one's are not, and a crowd of NPCs walking near you doesn't
  // all sound off on the same frame.
  footPlay_(e, mat, running, shuffle) {
    if (!this.started || !this.ac || !this._samples || !this._samples.ready()) return;
    const att = this.footAtten_(e);
    if (att <= 0.02) return;          // too far to be part of the world mix
    if (!this.footVoiceAllow_(e, att)) return;   // NPC voice cap, see above
    this._footAlt = (this._footAlt || 0) + 1;
    const pick = 'foot-' + mat + '-' + 'abc'[this._footAlt % 3];
    if (!this._samples.has(pick)) return;
    const gain = shuffle ? 0.20 : (running ? 0.42 : 0.30);
    const detune = (running ? -70 : 0) + (Math.random() * 2 - 1) * 90;
    this._att = att;
    try { this._samples.play(pick, { gain: gain, detune: detune }); } finally { this._att = 1; }
  }"""

sub(OLD_FOOTPLAY, NEW_FOOTPLAY, 'footPlay_ -> footAtten_/footVoiceAllow_/footPlay_ (68.417)')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 68.417 applied: footstep NPC distance/volume mix fix')
