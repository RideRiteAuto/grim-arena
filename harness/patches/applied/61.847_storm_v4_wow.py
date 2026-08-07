#!/usr/bin/env python3
"""Patch 61.847: chain lightning, take four. Swaps two samples, no logic.

Kevin, after v3 (patch 59.372): "These still don't sound that great." Asked
for the exact prompts, got them, asked to name a reference game, got one:
"let's go with... World of Warcraft... make it sound similar to World of
Warcraft."

I don't have ears, so instead of guessing what WoW "sounds like" I pulled the
actual game audio. Wowhead's public sound database serves the real files
Blizzard ships: the Shaman Lightning Bolt precast/charge (3 takes), the
"Revamp" cast variant (5 takes), and 5 impact takes, all fetched straight from
wow.zamimg.com. Ran all 13 through the same measurement script that diagnosed
v3's failure, so this round is matched against real numbers instead of a third
guess:

               dur    cent      rise    <200Hz  crest  pkpos  tonal%  tail
WoW precast   2.7-2.8s 6300-6650 +635/+1181 2.8%  5.8-7.6 .49-.80   0%   .35-1.2s
WoW impact    1.7-2.2s 2400-3300 -1450/-2000 16-21% 5.4-6.0 .08-.26  0%   .7-1.1s
v3 cast (rejected)  .62s  4953   -231    1.6%   4.0    .93    34%   .04s
v3 hit  (rejected)  .85s  5609  +1968   10.0%   8.6    .01     1%   .49s

Two concrete bugs, not just "still not great":

1. v3's cast measured 34% tonal against WoW's 0%. The synthesised pitch-sweep
   voice added in v3 to fix "not magic enough" was itself the mistake - it
   made the cast sound like a synthesizer, not electricity. WoW's magic reads
   from a bright, RISING-brightness noise texture with no melody in it at all.
   Fix: drop the tonal voice, shape the noise texture directly (lowpass sweep
   for the rise, a slow build envelope, a real tail instead of a hard stop).

2. v3's hit measured crest 8.6 with the smoothed envelope peaking at position
   .01 of its own length - an instant spike with no attack ramp, which is
   literally what a gunshot is. Fixing this needed two separate mechanisms,
   verified by measurement because neither alone was enough:
     a. A per-sample peak limiter, not an envelope-follower compressor. An
        envelope follower's own attack time (even 3ms, ~130 samples) means it
        cannot react before a transient that fast has already passed through
        at unity gain - the classic lookahead problem, confirmed by checking
        the compressor's output gain AT the sample index of the peak: 1.0,
        unchanged. A memoryless waveshaper reacts to the current sample
        directly and cannot lag.
     b. A 150ms quiet lead-in, faded from the cleaner of the two source
        textures. Limiting the transient's LEVEL does not move its TIME, and
        the smoothed envelope's peak was still sample zero even after crest
        came down. Prepending quiet material before the crack pushes the
        peak's sample index later without touching the crack's own shape,
        landing peak position at .085 (WoW's own range is .08-.26) while
        crest lands at 5.99-6.6 (WoW: 5.4-7.6 cast, 5.4-6.0 hit).

Also added: real low-mid body under the hit (WoW impacts carry 16-21% of
energy under 200Hz, v3 had 10%) via a soft-fronted 80Hz thump layered under
the crackle, and both samples now carry a proper decaying tail built by
low-passing and stretching their own tail rather than v3's hard stop (cast
tail .04s -> .91s, hit tail .49s -> 1.54s).

Final numbers (model-lab/sfx-samples.js has the full derivation in-comment):
  sp-storm-cast  cent 7695 rise +841  crest 6.6 pkpos .44 tonal 0% tail .91s
  sp-storm-hit   cent 3382 rise -4508 crest 5.7 pkpos .08 tonal 0% tail 1.54s

Nothing but the two base64 payloads changes. Every route, gain, stagger and
test from 58.641/59.372 still applies.
"""
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()


def module_entry(key):
    i = mod.find("\n  '%s':" % key)
    assert i > 0, 'no %s in the module' % key
    m = re.search(r"\n  '[a-z0-9-]+':|\n\};", mod[i + 10:])
    assert m
    body = mod[i + 1:i + 10 + m.start()]
    # the bundle indents sample keys four spaces, the module two
    return '\n'.join(('  ' + ln) if ln.strip() else '' for ln in body.split('\n'))


for key in ('sp-storm-cast', 'sp-storm-hit'):
    i = s.find("\n    '%s':" % key)
    assert i > 0, '%s not in the bundle' % key
    m = re.search(r"\n    '[a-z0-9-]+':|\n    \};", s[i + 12:])
    assert m, 'could not find the end of %s' % key
    j = i + 12 + m.start()
    new = module_entry(key)
    assert len(new) > 2000, '%s payload looks truncated' % key
    s = s[:i + 1] + new + s[j:]
    print('swapped %s' % key)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 61.847 applied')
