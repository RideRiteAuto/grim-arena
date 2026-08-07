#!/usr/bin/env python3
"""Patch 62.519: Frostbolt v2. Swaps two samples, no logic.

Kevin, after approving chain lightning v4 ("that was actually way better...
totally usable"): "let's go ahead and have you redo our frost bolt sound
effect... same route, getting the WoW sound effect, and then kind of reverse
engineering it to make our own, like you just did for the chain lightning."

Same method as 61.847: pulled real game audio rather than guessing. 9 Mage
Frostbolt files from Wowhead (4 cast/release, 4 precast windup, 1 impact),
measured with the same script:

               dur     cent      rise          <200Hz  crest   pkpos  tail
WoW cast(x4)  1.75-2.16 3644-4932 mostly FALLING  9-12%  6.4-8.1 .19-.23 .64-1.03s
WoW precast   1.90-2.10 3680-4604 FALLING steeply 7.4-8% 7.4-9.3 .14-.18 ~1.0s
WoW impact    1.63     7008     -681            8.3%   10.9    .01    .88s

Old sp-frost-cast/-hit (55.283) measured cent 7162-8768 (both far brighter
than any WoW reference), under 1.2% of energy below 200Hz against WoW's
8-12% (almost no cold weight at all), RISING brightness on both takes
(getting brighter over time) where every WoW reference gets darker, and a
tail of 0.03-0.04s (a hard stop, same defect storm v3 had before 61.847).

Worth noting explicitly: this fix runs in the OPPOSITE direction from chain
lightning's on nearly every axis. Storm needed rising brightness; frost needs
falling. Storm's instant-transient hit was the gunshot bug; frost's own
impact reference is ALSO an instant transient (WoW pkpos .01) and that is
correct here, an ice shard shattering is a genuinely sharp event with
different frequency content (bright/glassy, not a low boom) than a "close
lightning strike" reads as. Each spell gets measured against its own
reference rather than reusing the previous one's shape.

Building the tail surfaced a real measurement-methodology trap: the tail
metric walks forward from the smoothed peak and stops at the FIRST dip below
5 percent of peak, it does not resume counting content further out. A
synthesised ice-crackle tail appended AFTER the raw ElevenLabs texture's own
natural decay (which already fell silent by ~0.3s) left a silent gap the
metric could not see past, and tail kept measuring 0.26s regardless of how
much crackle was appended on the far side of that gap. Fix: overlay the
crackle starting WHILE the natural decay is still above threshold (0.15s in)
instead of after the clip ends, so there is no silent gap - landed tail at
0.90s against WoW's 0.88s.

Final numbers (full derivation in the model-lab/sfx-samples.js comment):
  sp-frost-cast  cent 3532 rise -1450 crest 5.7 pkpos .15 tonal 0% tail 1.10s
  sp-frost-hit   cent 7033 rise -491  crest 8.0 pkpos .02 tonal 0% tail 0.90s

Nothing but the two base64 payloads changes.
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
    return '\n'.join(('  ' + ln) if ln.strip() else '' for ln in body.split('\n'))


for key in ('sp-frost-cast', 'sp-frost-hit'):
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
print('patch 62.519 applied')
