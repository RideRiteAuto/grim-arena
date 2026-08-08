#!/usr/bin/env python3
"""Patch 83.200: widen the default ground-paint blend so it actually spans
more than one terrain-mesh vertex, and auto-upgrade worlds already saved
under the old default.

Kevin's follow-up report: even after 83.100's contrast-aware dither, a
single meadow brush stroke on a plain background still blends smoothly
around roughly half its circumference and looks stairstepped on the other
half. Traced this to geometry, not the shader: the ground mesh near the
player renders at 2m between vertices (buildChunk() uses a 64m chunk split
into 32 segments inside the "detail" ring stepTerrain() keeps around
whoever is editing, i.e. always, while editing), and GRIM_EDIT's "Ground
blend" edge-softness setting defaults to exactly 2m (EDIT.BLEND_DEFAULT).
The blend value only exists as data on mesh vertices (aMix), smoothly
interpolated across each triangle by the GPU; it is not sampled per-pixel
from world position. Where a circle's edge happens to run along a row or
column of vertices, several of them fall inside that 2m band and the ratio
interpolates into a real gradient. Where the edge cuts across the grid at
other angles (which a circle does for most of its circumference), most
vertices are either fully outside the band or fully inside it, with none
catching an intermediate value in between, so the interpolated result jumps
straight from one texture to the other with nothing in between. This is why
it looked exactly half-smooth, half-blocky rather than uniformly bad in
every direction: it is an undersampling problem tied to how the boundary's
local angle happens to line up with the grid, not a per-texture or
brightness one (83.100 still helps: it softens whatever hard jumps remain
in the worst directions; it just cannot fix jumps that are actually
happening in the underlying geometry).

FIX: raise EDIT.BLEND_DEFAULT from 2m to 5m, comfortably wider than the 2m
vertex spacing in every direction rather than exactly equal to it in the
best case and narrower in the worst. BLEND_MAX (the "Ground blend" slider's
ceiling) already sits at 6m from an earlier pass and needs no change here;
raising it further would leave the default sitting right at the ceiling,
an unusual place for a default to live and a change nobody asked for.

This is a single global value (the UI's own description: "One setting for
the whole world"), read live by paintAt()/paint() from GRIM_EDIT.raw.blend
on every chunk build rather than being baked into each painted stroke at
paint time. That is good news for Kevin's second question (does every
already-authored patch of ground need to be repainted by hand): no, raising
this one number retroactively re-blends every already-painted area in the
world the next time its chunks rebuild, with no per-texture work required.

The one thing that number alone will not fix: this world has been loaded
and saved at least once already under the old code, and editor-core.js's
migration function unconditionally stamps a concrete `blend` value onto
the saved edit layer on every load (`out.blend = ...`), so the live save
almost certainly already carries an explicit `blend: 2`, not a blank field
that would fall through to the new default. Bumping BLEND_DEFAULT alone
would therefore do nothing for Kevin's existing world; only a brand-new
layer would ever see it. Treat a saved blend that is still exactly the OLD
default (2) as "nobody ever touched the slider" and carry it forward to
the new default, the same way this same function already migrates a
resized paint grid (see oldPcell above it) rather than leaving old saves
stuck on stale values. A blend the user genuinely dialled in, including
the rare case where that happens to already equal 2, is left alone; this
is a one-time, one-directional upgrade, never applied twice since the
value != 2 after the first migration.

WHERE THIS LIVES: EDIT.BLEND_DEFAULT is defined in shared-rules.js (shared
with relay-worker.js), and the migration function is in editor-core.js.
Both are injected into the bundle from these tracked files by repack.py's
pack() step, so they are edited directly here rather than through
game-src.html, which pack() would otherwise overwrite with the unpatched
originals on the next build.

Verify: harness/simtest.mjs and harness/dressing.js (no ground-blend
specific coverage exists; both exercise world load/migrate and must still
pass with no behaviour change for any world that already customized blend).
"""
import io

n = 0


def sub(path, old, new, count=1, tag=''):
    global n
    t = io.open(path, encoding='utf-8').read()
    f = t.count(old)
    assert f == count, 'patch 83.200 [%s / %s]: anchor found %d times, wanted %d' % (path, tag, f, count)
    t = t.replace(old, new)
    io.open(path, 'w', encoding='utf-8').write(t)
    n += 1


# ---- 1. raise the default in shared-rules.js, the one place that drives it -
sub(
    'shared-rules.js',
    "    BLEND_DEFAULT: 2, // default paint/road edge softness, in metres",
    "    // Patch 83.200: was 2m, exactly equal to the near-field terrain mesh's\n"
    "    // 2m vertex spacing (64m chunks / 32 segments), so the blend band was\n"
    "    // only ever wide enough to interpolate smoothly along a boundary that\n"
    "    // happened to run with the grid, and jumped hard everywhere else. 5m\n"
    "    // gives 2.5x that spacing, comfortably wide in every direction rather\n"
    "    // than exactly one vertex wide in the best case.\n"
    "    BLEND_DEFAULT: 5, // default paint/road edge softness, in metres",
    tag='raise EDIT.BLEND_DEFAULT from 2 to 5')

# ---- 2. auto-upgrade a world already saved under the old default -----------
sub(
    'editor-core.js',
    "    out.blend = Math.max(0.5, Math.min(BLEND_MAX, num(raw.blend, BLEND_DEFAULT)));",
    "    // Patch 83.200: this function stamps an explicit numeric blend onto\n"
    "    // every saved layer unconditionally (see below), so a world that has\n"
    "    // been loaded and saved even once under the old code already has\n"
    "    // blend: 2 baked in, not a blank field that would fall through to the\n"
    "    // new BLEND_DEFAULT above. Treat that specific old value as \"nobody\n"
    "    // ever touched the slider\" and carry it forward, the same way\n"
    "    // oldPcell above migrates a resized paint grid rather than leaving old\n"
    "    // saves stuck. Anything else the user actually dialled in, including\n"
    "    // the rare case where that happens to already be 2, is left alone.\n"
    "    const rawBlend = num(raw.blend, BLEND_DEFAULT);\n"
    "    out.blend = Math.max(0.5, Math.min(BLEND_MAX, rawBlend === 2 ? BLEND_DEFAULT : rawBlend));",
    tag='auto-upgrade a stamped old default of 2 to the new default')

print('83.200_ground_blend_width: %d edits applied' % n)
