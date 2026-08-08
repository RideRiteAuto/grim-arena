#!/usr/bin/env python3
"""Patch 82.671: give the NPC shadow-cast distance check a hysteresis band.

Every other distance threshold in the file got an enter/exit band in the
v18.1 draw-distance overhaul (78.104-78.512) except this one: an NPC sitting
right at the old bare 40m line could flip castShadow (and pay a full
mesh-hierarchy traverse()) twice a second, every 0.5s tick, for as long as it
stood near the boundary. Already throttled to 0.5s so this was never severe,
but it is the one distance gate the farBand() hysteresis comment two screens
away explicitly describes the failure mode of and it did not get the same
treatment. Enter (shadow on) under 38m, exit (shadow off) past 44m.

No behavior change outside the ~38-44m band: same 0.5s cadence, same
per-NPC traverse only on an actual state change.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """      for (const n of this.npcs) {
        const sdx = n.pos.x - me.pos.x, sdz = n.pos.z - me.pos.z;
        const want = (sdx * sdx + sdz * sdz) < 1600 && n.hp > 0;
        if (n._shadowOn !== want) {
"""

NEW = """      for (const n of this.npcs) {
        const sdx = n.pos.x - me.pos.x, sdz = n.pos.z - me.pos.z;
        const sd2 = sdx * sdx + sdz * sdz;
        const want = n.hp > 0 && (n._shadowOn ? sd2 < 1936 : sd2 < 1444);   // hysteresis: off past 44m, on under 38m
        if (n._shadowOn !== want) {
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
