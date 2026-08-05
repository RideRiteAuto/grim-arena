#!/usr/bin/env python3
"""Wander waypoints are clamped to the WORLD, not to a circle around the origin.

    const rr = Math.hypot(e.way.x, e.way.z);
    if (rr > 162) e.way.multiplyScalar(162 / rr);

That measures the waypoint's distance from world 0,0 and drags anything beyond
162 metres back toward it. Harmless when the whole game was one arena roughly
that size. In a 4,800 metre world it means every monster whose home is further
out than 162m has its wander target hauled toward the capital, so nothing stays
in its own field: they all drift inward.

The server had the identical line and the same fix. Caught by a smoke test that
walked an idle wolf for five simulated minutes and asked how far from home it
had ever got: 81 metres, on a 24 metre patch.
"""
import io
SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
OLD = "      const rr = Math.hypot(e.way.x, e.way.z); if (rr > 162) e.way.multiplyScalar(162 / rr);"
NEW = ("      // Clamp to the world edge, not to a 162m circle around the origin: the\n"
       "      // old line dragged every distant monster's wander target back toward\n"
       "      // the capital instead of keeping it on its own ground.\n"
       "      { const rr = Math.hypot(e.way.x, e.way.z), WR = GRIM_RULES.WORLD_R;\n"
       "        if (rr > WR) e.way.multiplyScalar(WR / rr); }")
assert src.count(OLD) == 1, 'anchor not unique'
out = src.replace(OLD, NEW, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('client wander clamp fixed, %d -> %d bytes' % (len(src), len(out)))
