#!/usr/bin/env python3
"""Patch 67.452: every weapon and tool swing that hits nothing sounds the same,
and it is the good one.

Kevin's report: swinging the iron scimitar three times in a row (light, light,
heavy finisher, per the existing combo chain in swing()) played what sounded
like three different noises. The first two were "terrible," described as
sounding like hitting metal, even though nothing was struck. The third -
the heavy finisher - was "almost a perfect spot on shwoosh."

That third sound already existed and was already right: 'combat-heavy', the
sample the heavy finisher plays. The first two plays 'combat-swing' instead,
a different recorded take, and that take is what reads as metal-on-metal.
Two real samples, not one glitching - the combo just alternates between them
and only one of the two is good.

THE FIX, PER KEVIN'S EXPLICIT INSTRUCTION: do not generate anything new.
Reuse the 'combat-heavy' sample for every air-swing, sword or tool, all tiers.

1. CSAMP's 'swing' entry now points at the 'combat-heavy' sample instead of
   'combat-swing'. This one change fixes every caller of the 'swing' voice at
   once: light, glight and bash (all three route through MSFX to 'swing'),
   plus the remote/monster swing replay at sfxVoice_'s sibling call site
   (`this.sfx(m.heavy ? 'heavy' : 'swing')`), which never needed its own fix.
   'combat-swing' stays in sfx-samples.js, decodable and tested, just unused -
   safer to leave it on the shelf than to delete a working, tested asset for a
   routing change that might want reverting.

2. Tools (pickaxe, axe) got NOTHING before this, not even the wrong sound.
   MSFX had chop/gather mapped to null, a fix from the routing pass that gave
   arrows and swords their sounds (see the comment already on MSFX): an axe
   swung at nothing used to ring like a blade, and the fix at the time was
   silence rather than finding the right sound. Kevin's ask this round makes
   the right sound available for tools too, so chop/gather now map to
   'swing' exactly like light/glight/bash do, and pick up the same reroute.

   This does not touch what happens when a tool or sword actually CONNECTS.
   That path is untouched: gatherCheck() still plays the resource-specific
   chop-a/b/c, mine-a/b/c, or forage sample the instant a swing lands on a
   node, and meleeCheck()/the impact funnel still plays the material-specific
   combat-hit-flesh/leather/plate (or the frost/fire/storm spell hit) the
   instant a swing lands on a person. Both of those already fire from hitDone,
   separately from and after the swing sound. The swing sound is only ever
   the anticipation; per Kevin, going forward almost every held weapon should
   work this way - a swing sound first, then a separate, surface-dependent
   hit sound only if and when it actually lands. That is already how swords
   work (patch 44/55.283) and is now how tools work too. Expanding the
   surface-hit vocabulary itself (wood, steel, stone, per-creature flesh) is
   the next round, tracked in the roadmap, not part of this patch.

Two anchored edits, no sample module changes.
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
# 1. the sample CSAMP resolves 'swing' to
# ---------------------------------------------------------------------------
sub("""    const CSAMP = {
      swing: ['combat-swing', 0.5, 60], heavy: ['combat-heavy', 0.5, 60],
      block: ['combat-block', 0.7, 50], parry: ['combat-parry', 0.5, 40]
    };""",
    """    /* Kevin: three air-swings on the scimitar played two different takes and
       only the finisher's ('combat-heavy') was the shwoosh he wanted - the
       other ('combat-swing') read as hitting metal even though nothing was
       struck. Per his instruction, every miss now plays the good take. No
       new sample: 'swing' points at 'combat-heavy' too. 'combat-swing' stays
       in sfx-samples.js unused rather than deleted, in case a future weapon
       wants a distinct miss sound of its own later. */
    const CSAMP = {
      swing: ['combat-heavy', 0.5, 60], heavy: ['combat-heavy', 0.5, 60],
      block: ['combat-block', 0.7, 50], parry: ['combat-parry', 0.5, 40]
    };""", 'CSAMP swing reroute')

# ---------------------------------------------------------------------------
# 2. tools get the swing sound too, not silence
# ---------------------------------------------------------------------------
sub("""    /* What a move actually sounds like. This was one ternary that sent every
       move it did not name to the sword whoosh. Chopping a tree is a move, so
       an axe through air rang like a blade: Kevin heard it and it was the
       first thing he asked to lose. A tool through air now makes NOTHING, and
       the bite of it into the trunk carries the swing on its own.
       Sword attacks were routed to the synth 'slash' this whole time, which
       means the recorded swing and heavy samples from patch 41 have never
       once played. They do now.
       Chain lightning has no sample of its own yet, so it moves off the sword
       swing onto the synth cast. Better, not finished. */
    const MSFX = {
      chop: null, gather: null,
      light: 'swing', glight: 'swing', bash: 'swing',
      heavy: 'heavy', gheavy: 'heavy',
      claw: 'slash', bite: 'slash',
      rapid: 'draw', volley: 'draw',
      frost: null,              /* fireFrost() sounds the release, not the wind up */
      snare: 'cast', storm: 'sp-storm-cast',
      heal: 'sp-heal-cast'
    };""",
    """    /* What a move actually sounds like. This was one ternary that sent every
       move it did not name to the sword whoosh. Chopping a tree is a move, so
       an axe through air rang like a blade: Kevin heard it and it was the
       first thing he asked to lose. The fix at the time was NOTHING for a
       tool swing that hits nothing, which traded the wrong sound for silence
       rather than finding the right one.
       Patch 67.452: chop/gather now map to 'swing' like every other melee
       miss, and 'swing' itself was just rerouted (see CSAMP above) to the
       take Kevin actually wants - a pickaxe or axe swung at nothing now
       whooshes the same as a scimitar or claymore does. What happens on an
       actual CONNECT is untouched: gatherCheck() still plays the resource's
       own chop-a/b/c or mine-a/b/c the instant a swing lands on a node, and
       meleeCheck() still plays the material combat-hit-* the instant a swing
       lands on a person. This is only the miss.
       Sword attacks were routed to the synth 'slash' this whole time, which
       means the recorded swing and heavy samples from patch 41 have never
       once played. They do now.
       Chain lightning has no sample of its own yet, so it moves off the sword
       swing onto the synth cast. Better, not finished. */
    const MSFX = {
      chop: 'swing', gather: 'swing',
      light: 'swing', glight: 'swing', bash: 'swing',
      heavy: 'heavy', gheavy: 'heavy',
      claw: 'slash', bite: 'slash',
      rapid: 'draw', volley: 'draw',
      frost: null,              /* fireFrost() sounds the release, not the wind up */
      snare: 'cast', storm: 'sp-storm-cast',
      heal: 'sp-heal-cast'
    };""", 'MSFX chop/gather')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 67.452 applied')
