#!/usr/bin/env python3
"""Patch 31: the anvil is too small in the world. Kevin's call, +35%.

The lab model was built to real-world size (a 150 lb London pattern is about
51 cm long) and real size reads small in Grim World, where props sit against
chunky terrain and a stylised player. Game scale beats catalogue scale.

One anchored edit: the build call gets scale 1.35. Everything downstream
already flows from it - root.scale.setScalar(S), the collider radius
(0.30 * S), the face height, and the spark position all take S from the same
option, which is exactly why build() was written to take a scale in the first
place.
"""
import io

SRC = '/tmp/game-src.html'

s = io.open(SRC, encoding='utf-8').read()

OLD = "    const avRec = this.addAnvil(36.2, 23.2, { seed: 11 });"
assert s.count(OLD) == 1, 'anvil call anchor matched %d times' % s.count(OLD)
s = s.replace(OLD,
    "    const avRec = this.addAnvil(36.2, 23.2, { seed: 11, scale: 1.35 });")

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 31: anvil scaled to 1.35')
