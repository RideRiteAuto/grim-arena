#!/usr/bin/env python3
"""Patch 82.047: stop farBand() allocating a 3-element array on every call.

farBand runs for every NPC, every frame, from two different call sites
(stepFighter's per-frame pose step and the server-sim NPC loop) - the
highest-frequency allocation site found in the code-sweep audit. OUT never
changes, so cache it once on the instance instead of building a fresh array
literal each call. Same "lazy-init on the game instance" pattern already
used elsewhere in this file (e.g. _sv1/_sv2 scratch vectors), so this needs
no new anchor beyond the method itself.

No behavior change: same three thresholds, same hysteresis logic below it.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """  farBand(e, d2) {
    const OUT = [2500, 3600, 4225];            // 50m, 60m, 65m
    let b = (e._band == null) ? 3 : e._band;
"""

NEW = """  farBand(e, d2) {
    const OUT = this._farBandOut || (this._farBandOut = [2500, 3600, 4225]);            // 50m, 60m, 65m, cached once instead of realloc'd every call
    let b = (e._band == null) ? 3 : e._band;
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
