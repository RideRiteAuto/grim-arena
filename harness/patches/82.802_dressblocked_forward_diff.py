#!/usr/bin/env python3
"""Patch 82.802: cut dressBlocked()'s noise sampling from 5 height() calls to
3 per call.

dressBlocked's own comment says the dressing pass calls it about a thousand
times per chunk, and each call was sampling GRIM_WORLD.height() 5 times: once
for the water-depth check (h, already computed) plus 4 more for a centered-
difference slope estimate that never reused h. Switched the slope check to a
forward difference that reuses the already-computed h as one leg of the
gradient, cutting it to 2 new samples instead of 4 - a real reduction on a
function whose own docstring flags it as the hot path in chunk generation.
height() itself is not cheap (macro-elevation bilinear sample plus fbm()
plus zoneAt() plus a scan over CALM anchors), so this multiplies out to
roughly 2,000 fewer noise evaluations per chunk build.

This is an approximation change, not a pure refactor: a forward difference
is a coarser slope estimate than a centered one. Acceptable here because the
result only ever feeds a boolean "too steep for a prop" gate (threshold 1.2
on the squared gradient, i.e. roughly a 47-degree slope) - the kind of check
where being off by a small amount at the margin means a handful of props
near very steep terrain occasionally land on the other side of the gate, not
a correctness or gameplay-visible change.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    // steep ground: props standing on a cliff face read as floating
    const e = 1.5;
    const gx = (GRIM_WORLD.height(x + e, z) - GRIM_WORLD.height(x - e, z)) / (2 * e);
    const gz = (GRIM_WORLD.height(x, z + e) - GRIM_WORLD.height(x, z - e)) / (2 * e);
    return (gx * gx + gz * gz) > 1.2;
"""

NEW = """    // steep ground: props standing on a cliff face read as floating.
    // Forward difference reusing h (already sampled above) instead of a
    // centered difference: 2 new height() samples instead of 4, and this
    // runs about a thousand times per chunk per its own comment above.
    const e = 1.5;
    const gx = (GRIM_WORLD.height(x + e, z) - h) / e;
    const gz = (GRIM_WORLD.height(x, z + e) - h) / e;
    return (gx * gx + gz * gz) > 1.2;
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
