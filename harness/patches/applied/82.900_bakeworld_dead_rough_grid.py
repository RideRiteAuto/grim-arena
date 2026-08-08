#!/usr/bin/env python3
"""Patch 82.900: remove a dead, hand-mirrored 'rough' grid from bake_world.py.

bake_world.py computed a per-cell `rough` array (mirroring each zone's
'rough' config value into a grid) but never read it again anywhere in the
file after computing it - it is not written to any output layer, not
returned, not used downstream. The actual runtime source of truth for
per-zone roughness is worldgen.js's ROUGH table, read directly by the
client at generation time. This left two copies of the same numbers that
could silently drift apart, with the baker's copy doing nothing.

Confirmed dead via full-file grep for `rough` in bake_world.py: only the
three lines removed here reference it (the np.zeros allocation, the loop
write, and no third site). No output layer, JSON blob, or return value
touches it.

Note: this file lives outside the embedded game-src.html bundle, so unlike
the other 82.x patches in this batch it edits bake_world.py directly at the
repo root rather than /tmp/game-src.html. Re-running bake_world.py is a
separate manual/ops step (it regenerates world data offline); this patch
only removes dead code from it and changes no output.
"""
import io

PATH = 'bake_world.py'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    # --- elevation, in meters ------------------------------------------------
    base = np.zeros((GH, GW))
    rough = np.zeros((GH, GW))
    for i, (_n, _c, p) in enumerate(ZONES):
        sel = zone == i
        base[sel] = p['base']
        rough[sel] = p['rough']
"""

NEW = """    # --- elevation, in meters ------------------------------------------------
    # Per-zone 'rough' in ZONES below is the source of truth for noise
    # amplitude at runtime - it's read directly by worldgen.js's ROUGH table,
    # not from anything this baker emits. A `rough` grid used to be computed
    # here as a hand-mirrored duplicate and was never actually read again
    # (code-sweep audit, 2026-08-08) - removed rather than left as a second,
    # driftable copy of numbers that already live in worldgen.js.
    base = np.zeros((GH, GW))
    for i, (_n, _c, p) in enumerate(ZONES):
        sel = zone == i
        base[sel] = p['base']
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
