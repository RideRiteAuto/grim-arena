#!/usr/bin/env python3
"""Patch 63.104: frostbolt hit v3. Swaps one sample, no logic.

Kevin on v2 (62.519): the cast is fine, but "the hit should sound a little
bit more like it's freezing... it applies a freeze effect that holds the
player in its spot for a short amount of time." This game's frost bolt roots
the target for two seconds (see the in-game help text and `e.frozen` /
`frostShell` in the entity code). Vanilla WoW's Frostbolt does not root, so
the real WoW impact audio v2 was matched against was never asked to
communicate a status effect landing, only an ice shard breaking. The crack
itself was correct (Kevin liked it, and WoW's own impact peaks instantly
too), so this keeps that front untouched and only replaces what comes after
it.

The old crackle tail read as "debris falling," which is physically correct
for a shatter but does not say "you are now frozen." Recipe: a new
ElevenLabs "magical ice encasing, crystalline shimmer swelling then locking
into cold stillness" layer replaces it, with its own lowpass swept 7500 to
2200 Hz across its length (bright entry settling dark and cold, the same
falling-brightness language already used for the cast) plus a short quiet
synthesised low-frequency "hold" so the freeze reads as lasting rather than
vanishing the instant the shimmer decays. A reduced dose of the old crackle
stays underneath for physical ice-fragment texture. Full rationale and
numbers are in the comment block above 'sp-frost-cast' in
model-lab/sfx-samples.js.

Nothing but the one base64 payload changes. sp-frost-cast is untouched.
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


for key in ('sp-frost-hit',):
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
print('patch 63.104 applied')
