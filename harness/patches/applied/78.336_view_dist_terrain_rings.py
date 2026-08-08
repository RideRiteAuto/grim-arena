#!/usr/bin/env python3
"""Patch 78.336: scale the terrain detail/coarse rings and the prop-dressing
ring by VIEW_DIST (part 3 of the Phase 2 overhaul; see 78.104's docstring).

At the default 'normal' tier (mult 1.0) this reproduces today's live numbers
exactly: DETAIL 3, COARSE 7, DRESS = whatever GFX_SCALE.dressRing already
resolves to. Only 'near' and 'far' change anything. COARSE is capped at 10
regardless of tier - stepTerrain's own chunk budget is small per tick, and an
unbounded ring count on a fast machine with FAR selected would just grow the
backlog instead of drawing further, since chunks build a few at a time.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    const DETAIL = 3, COARSE = 7;
    const _gs = (GRIM_RULES.GFX_SCALE || {})[this.gfx === 'high' ? 'high' : 'low'] || {};
    const DRESS = _gs.dressRing != null ? _gs.dressRing : 2;
"""

NEW = """    const _vdT = (GRIM_RULES.VIEW_DIST || {})[this.viewDist] || { mult: 1 };
    const DETAIL = Math.max(2, Math.round(3 * _vdT.mult));
    const COARSE = Math.min(10, Math.max(DETAIL + 2, Math.round(7 * _vdT.mult)));
    const _gs = (GRIM_RULES.GFX_SCALE || {})[this.gfx === 'high' ? 'high' : 'low'] || {};
    const DRESS = Math.max(1, Math.round((_gs.dressRing != null ? _gs.dressRing : 2) * _vdT.mult));
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
