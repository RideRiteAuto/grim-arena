#!/usr/bin/env python3
"""Patch 76: remove the legacy auto-generated beach sand along every coast.

Kevin's report: a jagged sandy strip sits along the water's edge, distinct
from and lower-quality than the paint tool's own blend, and painting over it
doesn't fully cover it -- because it isn't ground paint. It is a leftover
from before the zone/paint system existed: groundSurface() force-blended in
surface 9 (beach sand) on every vertex within 4.2m height of any water,
completely independent of zone, paint, or the SUNCOAST/ISLES zones that
already carry their own dune-sand base pair on purpose. terrainColor() had
a second, separate override doing the same thing to the vertex COLOUR tint
below 0.6m near water, which is what kept discolouring painted ground on
top of the texture fix.

Both were also a genuine source of the "jagged" look Kevin flagged, on top
of being unwanted: this blend is baked at MESH VERTEX resolution (a chunk's
vertex spacing is 2m for the rings around the player, coarser further out),
while the paint tool's own blend works in world space and reads far finer.
A coastline half a vertex off the shore band would step at the mesh grid,
which is a different and worse stair-step than the paint tool's.

Removing it does not make coastlines paintless: SUNCOAST and ISLES already
carry dry-coastal/sand as their zone's own base surface pair, so a natural
coast still reads as coast without this hack. Everywhere else, water's edge
now shows whatever the zone's real ground is (or whatever Kevin paints)
instead of an uninvited sand ring.

1. groundSurface(): the shore height/nearWater blend that fed out[5] is
   deleted; out[5] is zeroed explicitly (the su[] array is reused across
   calls, so leaving it unset would carry a stale value from whatever
   vertex ran before it -- a real bug, not just dead code).
2. The ground shader's fragment mix that read that weight and blended in
   groundSurf(9.0, ...) (hardcoded to beach sand) is deleted outright.
3. terrainColor()'s beach-strip vertex-colour override is deleted; the
   zone's real palette colour is what shows near water now.

Nothing here touches SUNCOAST/ISLES's own zone surfaces, the shore height
falloff in worldgen.js (terrain ROUGHNESS near water, a different system,
unaffected), or the paint tool's own blend (editor-core.js/editor-ui.js,
also untouched).
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 76 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. groundSurface(): no more auto beach-sand blend near water ---------
sub(
    """    // Shore: a real sand-to-ground blend up the first few metres of bank,
    // rather than the hard recolour at 0.6 m this replaced.
    let shore = 0;
    if (h < 4.2 && GRIM_WORLD.nearWater(wx, wz)) {
      const ts = Math.max(0, Math.min(1, 1 - h / 4.2));
      shore = ts * ts * (3 - 2 * ts);
    }
    out[5] = shore;""",
    """    // Retired: this used to force-blend beach sand into every vertex near
    // water, independent of zone or paint. SUNCOAST/ISLES already carry
    // their own coastal sand as a real zone surface, and everywhere else
    // this just fought the paint tool and its own mesh-grid resolution
    // made it the more jagged of the two. out[5] is explicitly zeroed
    // because su[] is a reused buffer, not a fresh array, every call.
    out[5] = 0;""",
    tag='groundSurface no longer auto-blends beach sand near water')

# ---- 2. the ground shader stops reading that (now always-zero) weight -----
sub(
    "      'if (vMix.y > 0.001) gcol = mix(gcol, groundSurf(9.0, vWorld), vMix.y);',\n",
    "",
    tag='shader no longer mixes in hardcoded beach sand')

# ---- 3. terrainColor(): no more tan tint override near water --------------
sub(
    """    if (h >= 0 && h < 0.6 && GRIM_WORLD.nearWater(wx, wz)) { r = 0.66; g2 = 0.60; b = 0.44; }  // beach strip
""",
    "",
    tag='terrainColor no longer tints near water')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('76_remove_legacy_shore_sand: %d edits applied (1-3)' % n)
