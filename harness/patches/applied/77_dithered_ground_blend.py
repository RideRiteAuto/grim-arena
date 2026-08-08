#!/usr/bin/env python3
"""Patch 77: dithered ground-texture blending, and a wider blend range.

Kevin's report after patch 76: the paint tool's blend edge (meadow next to
sand, tested deliberately) is "less blocky than before... still very much
blocky and still nowhere near as clean of a blend as I need," and asked to
look at what other game developers do about this and rewrite accordingly.

Researched: the root cause is not the paint tool's own sampling (paintAt()
already jitters its cell lookup at 1m resolution, patch from an earlier
session). It is TWO separate, compounding effects downstream of that, both
well documented as solved problems in terrain rendering:

1. GEOMETRIC blockiness. groundFragBody()'s blend weight (vMix.x) is baked
   per VERTEX at chunk-build time (2m spacing for the rings around the
   player, coarser further out - see buildChunk()/stepTerrain()), then
   linearly interpolated across each triangle by the GPU. That interpolation
   is smooth, but it is bounded by the triangle it lives in: the blend can
   only bend where the mesh itself has an edge. This reads as faceting no
   matter how fine the paint tool's own world-space sampling is, because the
   two systems operate at different resolutions and the coarser one wins.

2. COLOUR blockiness (a separate, compounding problem). groundSurf() is a
   real detailed texture lookup, not a flat colour, and mix()-ing two
   detailed textures together by a weight averages their pixels. Averaging
   two different ground textures produces a washed-out, hazy band right
   where the eye is looking hardest at the transition, which reads as "the
   blend looks worse than the tool should be able to do" even in the middle
   of an otherwise-smooth triangle. This is a well known texture-splatting
   artifact (see the classic "Advanced Terrain Texture Splatting" writeup),
   and every article on smooth terrain blending independently converges on
   the same class of fix: don't blend two textures' colours, PICK one or the
   other per fragment, weighted by the blend ratio, using noise as the coin
   flip (stochastic / dithered blending - the technique behind Tsushima
   Island's terrain at GDC, Unity/Godot terrain-blend writeups, and the
   ordered-dithering tricks used for mesh-to-mesh blending generally). A
   dithered pick keeps full texture detail everywhere AND is not bounded by
   mesh resolution, because it runs per FRAGMENT (screen pixel projected
   into world space), which is far finer than any vertex spacing this game
   can afford. It fixes both problems at once, for the cost of one hash call
   already used elsewhere in this codebase (h21, the same trick the zone
   borders and bridge pads already use) plus a compare, no new textures, no
   new draw calls, and no geometry change - safe against the NPC-draw-call
   perf budget in PERF-AUDIT-AUG6.md, since it does not touch triangle count
   at all.

   World-space noise, not screen-space: the hash reads vWorld (already a
   varying), so the grain is fixed to the ground and holds still as the
   camera moves, rather than swimming across the terrain the way a
   screen-space dither would.

This patch:
1. Adds h21() (already used verbatim elsewhere in this bundle) and a new
   ditherMix() helper to the ground shader's fragment stage.
2. Replaces all three mix() calls in groundFragBody() (the base pair, the
   slope-to-rock blend, and the treeline/4th-layer blend) with ditherMix(),
   each offset by a different constant so the three dither passes don't
   correlate with each other.
3. Raises BLEND_MAX from 4m to 6m in shared-rules.js (the single shared
   source both editor-core.js and editor-ui.js read it from). The old cap's
   own comment says it exists to bound groundSurface()'s per-vertex
   neighbourhood scan, which still applies - so this is a real but modest
   increase, not a removal of the safeguard. It was also implicitly a
   quality cap: a wide blend used to mean a wide band of washed-out mixed
   colour, so there was no reason to want one. Now that blending no longer
   averages colours, a soft wide blend is worth having, so the tool's own
   "Ground blend / edge softness" slider (editor-ui.js) can reach it.
   This edit is made directly to shared-rules.js on disk, NOT to the
   extracted bundle: that region of index.html is re-synced from the real
   file on every build (see build.sh's "shared rules synced" step), so a
   patch touching the extracted copy inside the SHARED-RULES markers would
   apply, then immediately get overwritten by the resync and silently do
   nothing to the shipped bundle. shared-rules.js is edited by this same
   script (below), same as patch 72 edited editor-core.js/editor-ui.js
   directly rather than through the extracted-bundle patch mechanism.

Not touched: paintAt()'s own vertex-level jitter (already good, complements
this rather than being replaced by it), buildChunk()/stepTerrain()'s mesh
density (the perf-risky lever, deliberately avoided), and the brush radius
tool (already has its own real-metres falloff-free circle; the existing
global blend-width slider is what governs edge softness, so a second
per-brush hardness control would just duplicate it).
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 77 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. add h21 + ditherMix to the ground shader's fragment stage ---------
sub(
    """          'vec3 groundSurf(float idx, vec2 w) {',
          '  vec3 detail = texture(uGround, vec3(w / 3.5, idx)).rgb;',
          '  vec3 macro  = texture(uGround, vec3(w / 26.0, idx)).rgb;',
          // Modulate rather than multiply: a straight product squares the
          // contrast and crushes the ground dark.
          '  return macro * (0.55 + detail * 0.9);',
          '}'
        ].join('\\n'))""",
    """          'vec3 groundSurf(float idx, vec2 w) {',
          '  vec3 detail = texture(uGround, vec3(w / 3.5, idx)).rgb;',
          '  vec3 macro  = texture(uGround, vec3(w / 26.0, idx)).rgb;',
          // Modulate rather than multiply: a straight product squares the
          // contrast and crushes the ground dark.
          '  return macro * (0.55 + detail * 0.9);',
          '}',
          // Same hash already used elsewhere in this bundle (zone borders,
          // bridge pads). Picks colour a or b outright per fragment rather
          // than averaging them, at a probability set by t: averaging two
          // detailed textures washes them into a grey haze right at the
          // transition, where the eye is looking hardest. A dithered pick
          // keeps full detail everywhere and runs per fragment, far finer
          // than any mesh vertex spacing, so the edge is not bounded by
          // triangle geometry. World-space w, not screen space, so the
          // grain holds still on the ground as the camera moves.
          'float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
          'vec3 ditherMix(vec3 a, vec3 b, float t, vec2 w) {',
          '  return h21(w * 4.0) < t ? b : a;',
          '}'
        ].join('\\n'))""",
    tag='add h21 + ditherMix to the ground fragment shader')

# ---- 2. use ditherMix for all three ground blends in groundFragBody() -----
sub(
    "'vec3 gcol = mix(groundSurf(vTile.x, vWorld), groundSurf(vTile.y, vWorld), vMix.x);',",
    "'vec3 gcol = ditherMix(groundSurf(vTile.x, vWorld), groundSurf(vTile.y, vWorld), vMix.x, vWorld);',",
    tag='dither the base pair blend')

sub(
    "'if (rw > 0.001) gcol = mix(gcol, groundSurf(vTile.z, vWorld), rw);',",
    "'if (rw > 0.001) gcol = ditherMix(gcol, groundSurf(vTile.z, vWorld), rw, vWorld + 31.7);',",
    tag='dither the slope-to-rock blend')

sub(
    "'if (vMix.z > 0.001) gcol = mix(gcol, groundSurf(vTile.w, vWorld), vMix.z);',",
    "'if (vMix.z > 0.001) gcol = ditherMix(gcol, groundSurf(vTile.w, vWorld), vMix.z, vWorld + 71.3);',",
    tag='dither the treeline/4th-layer blend')

io.open(SRC, 'w', encoding='utf-8').write(s)

# ---- 3. raise the blend-width cap now that wide blends aren't muddy -------
# Edited directly on shared-rules.js, not the extracted bundle copy: that
# region of index.html is re-synced from this real file on every build, so
# patching the extracted copy here would be silently overwritten.
RULES = 'shared-rules.js'
r = io.open(RULES, encoding='utf-8').read()
old_rules = """    BLEND_DEFAULT: 2, // default paint/road edge softness, in metres
    BLEND_MAX: 4,     // clamp on the per-layer blend value, so a huge blend
                      // cannot make groundSurface scan an unreasonable
                      // neighbourhood on every vertex"""
new_rules = """    BLEND_DEFAULT: 2, // default paint/road edge softness, in metres
    BLEND_MAX: 6,     // clamp on the per-layer blend value, so a huge blend
                      // cannot make groundSurface scan an unreasonable
                      // neighbourhood on every vertex. Raised from 4: ground
                      // blending is dithered now instead of averaging colour
                      // (see the ground shader), so a wide soft blend no
                      // longer means a wide band of washed-out colour, and
                      // is worth letting Kevin dial in from the tool."""
f = r.count(old_rules)
assert f == 1, 'patch 77 [raise BLEND_MAX in shared-rules.js]: anchor found %d times, wanted 1' % f
r = r.replace(old_rules, new_rules)
io.open(RULES, 'w', encoding='utf-8').write(r)
n += 1

print('77_dithered_ground_blend: %d edits applied' % n)
