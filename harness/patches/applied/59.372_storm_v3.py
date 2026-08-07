#!/usr/bin/env python3
"""Patch 59.372: chain lightning, take three. Swaps two samples, no logic.

Kevin on the 58.641 pair: the cast was "a weird reloading sound", the strike
"sounds like a gunshot", and neither "sounds like magic at all".

He is right, and the mistake was mine at the brief stage rather than at the
selection stage. I asked ElevenLabs for REAL electricity: a Tesla coil spinning
up, and a lightning strike ten metres away. A spark gap accelerating IS a
ratchet. A close lightning strike IS a sharp crack with a bang. Both takes met
every floor I set, and the crest-factor floor I chose actively rewarded the
rattle. Realism was the wrong target for the one sound in the game that is not
supposed to exist in the real world.

The measurement that says it plainly: both rejected takes were ZERO PERCENT
TONAL. Pure noise. Noise with a hard transient is a gunshot and noise in
discrete bursts is a ratchet, and no amount of re-rolling the generator was
going to fix that, because the generator only ever returns noise.

How the electric-magic libraries actually do it: tearing plastic and tape for
the texture, synthesis for the voice, layered. So the noise here is generated
from ripping cellophane with every mechanism banned in the prompt, and the
pitched voice is synthesised in model-lab and mixed in.

  cast  a charge: two detuned saws climbing 130 to 560 Hz under a smoothly
        accelerating flutter, over a continuous tear that brightens. It stops
        poised rather than resolving, because the discharge is the next sound.
        Tonality 0 -> 34 percent. Crest 20.8 -> 4.0, which is the number that
        was the ratchet.
        The flutter is a SMOOTH pulse, not a square gate. A hard on/off gate at
        an accelerating rate is a machine gun, i.e. the exact texture that was
        rejected, and the first attempt at this had one.

  hit   a zap: a square sweep falling 1900 to 140 Hz in 130 ms with a slower
        saw an octave under it, a sub for weight, and the generated tear ducked
        by 58 percent underneath for the first 130 ms so the pitch fall is
        heard as a pitch fall rather than as one more layer of fizz. That
        downward sweep is the whole difference between a zap and a bang.
        Tonality in the attack 0 -> 17 percent. Tail 0.24 -> 0.49 s: a gunshot
        is over, a spell sizzles.

Nothing but the two base64 payloads changes. Every route, gain, stagger and
test from 58.641 still applies.
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
print('patch 59.372 applied')
