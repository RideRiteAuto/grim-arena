#!/usr/bin/env python3
"""Patch 82.409: stop poseQuadRig() allocating two array literals every call.

poseQuadRig runs every frame for every visible quadruped (wolves, boar, deer,
rat, hare). RUN_OFF has two fixed variants selected by gaitStyle and WALK_OFF
is always the same four numbers - none of the three ever change, so cache
each on the instance the first time it's built instead of allocating fresh
arrays every call. Same lazy-init-on-instance pattern as farBand (82.047).

No behavior change: same numbers, same rotary/transverse selection.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    const rotary = q.gaitStyle !== 'transverse';
    const RUN_OFF = rotary ? [0, 0.35, Math.PI, Math.PI + 0.35] : [0, 0.45, Math.PI + 0.25, Math.PI + 0.7];
    const WALK_OFF = [0, Math.PI, Math.PI, 0];
"""

NEW = """    const rotary = q.gaitStyle !== 'transverse';
    const RUN_OFF = rotary
      ? (this._quadRunOffR || (this._quadRunOffR = [0, 0.35, Math.PI, Math.PI + 0.35]))
      : (this._quadRunOffT || (this._quadRunOffT = [0, 0.45, Math.PI + 0.25, Math.PI + 0.7]));
    const WALK_OFF = this._quadWalkOff || (this._quadWalkOff = [0, Math.PI, Math.PI, 0]);
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
