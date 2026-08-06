#!/usr/bin/env python3
"""Patch 51: the shield meets the hand.

Kevin, on patch 48: "the shield is just barely not attached to the hand
anymore. Just move the shield in to meet the hand." The outboard offset the
carry was solved with (0.12 off the fist) left daylight between the knuckles
and the back plate. Re-solved at 0.05 the back plate rests against the fist.
Orientation untouched. Numbers from the pose solver run against the lab.
"""
import io
SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()

def sub(old, new, why):
    global s
    assert s.count(old) == 1, 'anchor x%d: %s' % (s.count(old), why)
    s = s.replace(old, new)
    print('  ok:', why)

sub("P.shield.position.set(0.112 + (0.065 - 0.112) * b2, -0.341 + (-0.427 + 0.341) * b2, -0.154 + (-0.113 + 0.154) * b2);",
    "P.shield.position.set(0.042 + (0.065 - 0.042) * b2, -0.333 + (-0.427 + 0.333) * b2, -0.152 + (-0.113 + 0.152) * b2);",
    'shield rest position: against the fist')
sub("shield.position.set(0.112, -0.341, -0.154); shield.rotation.set(-1.221, 0.107, 3.137);",
    "shield.position.set(0.042, -0.333, -0.152); shield.rotation.set(-1.221, 0.107, 3.137);",
    'base transform matches')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 51 applied')
