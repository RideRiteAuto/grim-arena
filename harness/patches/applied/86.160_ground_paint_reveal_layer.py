#!/usr/bin/env python3
"""Patch 86.160: replace paint()'s "discard one natural texture" design with
a genuine independent reveal layer, fixing a residual hard-edge bug that
86.150 did not (and structurally could not) fix.

BACKGROUND: 86.100 fixed paintAt()'s coverage falloff. 86.150 fixed a sign
error in paint()'s blend-weight remap. Kevin re-tested both and reported
the SAME symptom persisting: "it better but i still clearly see the jagged
edges in your after image." My own before/after comparison at that point
was, on honest re-inspection, nearly pixel-identical -- I should have
caught that before claiming the fix, not after Kevin did.

Re-investigation with real per-vertex probes (monkey-patching groundSurface
during a real chunk rebuild, matched against GRIM_EDIT.paintAt()'s own
coverage numbers) ruled out a confound first: found a location with a
provably uniform natural texture pair (out[0]=7 "mountain gravel", out[1]=2
"heath", constant over a 60m x 70m scanned area, nowhere near a zone
boundary) and confirmed the SAME direction-dependent hard/soft asymmetry
still happened there, so it was not the natural-zone-boundary confound it
first looked like.

The actual root cause was architectural, not a further sign/math bug.
Every version of paint() since 83.200 (including 86.100 and 86.150) worked
by REWRITING the natural A/B blend in place:

    const around = (t0 > 0.5) ? out[1] : out[0];   // keep whichever natural
                                                     // texture is locally
                                                     // dominant
    out[0] = around; out[1] = surf;                 // discard the OTHER one
    out[4] = <coverage-derived weight>;

This can only ever show ONE of the two natural textures underneath a paint
stroke -- the other is always discarded -- and WHICH one survives flips
discretely wherever the natural blend's own weight (t0) crosses 0.5. That
crossing is a property of the natural terrain, unrelated to where a paint
stroke was drawn. Where the two happen to coincide, the discard choice
itself flips partway around a stroke, which reads as a hard seam even
though 86.150's coverage math is, by then, numerically identical on both
sides of that seam. Confirmed live: painting the same brush onto the
uniform 7/2 pair above showed a clean, wide dithered fade on the side where
the natural blend favoured out[0], and a sharp stair-stepped edge on the
side where it favoured out[1] instead -- with paintAt()'s own coverage
curve verified identical in both directions.

FIX: stop discarding a natural texture at all. Leave out[0]/out[1]/out[4]
(the natural A/B pair and its blend weight) completely untouched, and
instead have paint ride the existing altitude-cap slot -- out[3] (tile.w)
and out[6] (mix.z) -- which every vertex already carries and which the
shader already renders as an independent reveal layer on top of the
natural blend (`if (vMix.z > 0.001) gcol = ditherMix(gcol, groundSurf(vTile.w,
...), vMix.z, ...)`), the same mechanism the rock-on-steep-slopes layer
uses. Paint simply fades in at strength `cov` with nothing underneath to
discard, so there is no discrete choice left to flip:

    out[3] = hit[0];
    out[6] = hit[1];

This needed no new vertex attribute and no shader change -- the reveal slot
already existed and authored ground already had priority over it (the
86.150-era comment this replaces: "Authored ground beats the snow cap and
the shore blend"). It requires GRIM_EDIT to keep its own capLo/capHi-driven
altitude cap out of the way where paint is active, which it already does
naturally: paint() returns the untouched grimGroundSurface() cap value
whenever there is no paint hit at a vertex, and overwrites it outright
whenever there is one, so paint always wins outright over the snow cap
exactly where it applies, with no separate blend-weight arithmetic needed.

VERIFIED:
  - harness/ground-paint-coverage.js (86.100's regression harness, untouched
    by this patch) still passes in full, including the painted-to-painted
    border numbers.
  - Live per-vertex probe (hooking GRIM_EDIT.paint directly -- see note
    below on why groundSurface itself is no longer the right hook point)
    at the same uniform 7/2 test location, all 4 cardinal directions: out[0]
    and out[1] are bit-identical before and after paint() runs at every
    sampled vertex in all 4 directions (7 and 2, never touched), while
    out[6] tracks paintAt()'s coverage number exactly and monotonically in
    every direction (0.81, 0.98, 1, 1, 1 approaching the centre; 0.14, 0.44,
    0.92, 1 on the +Z side; matching, mirrored curves on -X/-Z) -- no spike,
    no discrete flip, on any side.
  - Rendered GRIM_GDBG=3 (raw vTile/vMix channel, no ditherMix) at the same
    location with no paint applied at all: perfectly smooth gradient, no
    staircase, confirming the underlying natural blend-weight data was
    never the problem.

A REMAINING, SEPARATE FINDING -- NOT FIXED BY THIS PATCH: after this fix,
Kevin's mountain-gravel ("IRONSPIRE" zone base texture, index 7) side of a
painted circle can still look more textured/mottled at the low-opacity
fringe of the fade than the heath side does. Rendered GRIM_GDBG=2 (raw
unblended detail texture, no blending at all) for index 7 alone and found
mountain-gravel's own procedural detail texture is visibly tiled/checkered
by design at this sampling scale; heath's equivalent render is far more
uniform. This looks like a property of that one texture's own design, not
a paint or blend-math bug, and reported to Kevin as a separate, optional
art follow-up rather than folded into this fix.

WHY groundSurface() IS NO LONGER THE RIGHT PROBE HOOK POINT (context for
future investigation, not part of the fix itself): commit 579be43 (Phase 0
of the terrain-worker-offload plan, landed on origin/master between this
fix being authored and being pushed) extracted groundSurface's body to a
module-level grimGroundSurface() function, called directly from the real
per-vertex mesh-build loop -- G.groundSurface(...) is now a thin
still-monkey-patchable wrapper around it, kept for other call sites (the
road-surface builder, the paint tool's own probe), but no longer the path
real chunk builds take. grimGroundSurface()'s own last line still calls
GRIM_EDIT.paint(wx, wz, out) exactly as before, so this fix's logic is
unaffected either way -- only the live-probe technique needed updating, to
hook GRIM_EDIT.paint directly instead (G.EDIT() returns the live GRIM_EDIT
object by reference).

WHERE THIS LIVES: paint() ships inside editor-core.js, inside the EDITOR
marker region of the bundle (read by every client, since ground paint has
to render for players, not just the editor), so this patch edits the
tracked file directly, never /tmp/game-src.html -- see patch 83.200's,
86.100's and 86.150's docstrings for why that distinction matters.

NOTE ON PATCH ORDER: this fix was authored and verified directly against
editor-core.js in-place (rebased onto 579be43 after that commit landed
upstream mid-investigation -- editor-core.js itself was untouched by that
commit, confirmed via `git diff --stat`, so the fix applied and repacked
cleanly with no conflict), then this script was written afterward purely
as the durable historical record, matching the project's numbered-patch
convention. Running this script against the current tracked file will
correctly fail its anchor assert, since the file already contains the fix.
That failure is intentional, same as any other applied/ patch.
"""
import io

n = 0
def sub(path, old, new, count=1, tag=''):
    global n
    t = io.open(path, encoding='utf-8').read()
    f = t.count(old)
    assert f == count, 'patch 86.160 [%s / %s]: anchor found %d times, wanted %d' % (path, tag, f, count)
    t = t.replace(old, new)
    io.open(path, 'w', encoding='utf-8').write(t)
    n += 1

sub('editor-core.js',
    """  // Rewrite a groundSurface() result in place. Roads sit on top of paint, so
  // a road drawn across a painted field still reads as a road.
  //
  // This rides the EXISTING A-to-B blend rather than adding a channel, which
  // is the same trick the bridge abutment pads use: keep whichever surface is
  // locally dominant as A, put the authored surface in B, and hand the
  // coverage to the blend. The feather is then the ground's own feather, so
  // the join is seamless by construction and costs nothing extra to draw.
  function paint(wx, wz, out) {
    if (!api.on) return;
    if (paintBounds && (wx < paintBounds.x0 || wx > paintBounds.x1 ||
                        wz < paintBounds.z0 || wz > paintBounds.z1)) return;
    let hit = paintAt(wx, wz);
    const rd = roadAt(wx, wz);
    if (rd && (!hit || rd[1] >= hit[1])) hit = rd;
    if (!hit) return;
    const surf = hit[0], cov = hit[1];
    const t0 = out[4];
    const around = (t0 > 0.5) ? out[1] : out[0];
    if (surf === around) { out[0] = around; out[1] = around; return; }
    // "resid" is how much of the natural, unpainted blend was already NOT
    // "around" -- i.e. how much would show through a thin coat of paint. When
    // "around" comes from out[0] that's just t0. When it comes from out[1]
    // instead (the natural blend already favoured its own second texture),
    // the residual is the complement: reusing t0 unmodified there used to
    // read as "the natural blend was 97% toward around" and then treat that
    // 97% as leftover paint weight, which forced coverage to spike back up
    // right at the edge of a stroke's reach before snapping to nothing the
    // moment paintAt() ran out of blend radius. That spike-then-cliff was
    // the still-blocky edges reported after 86.100: 86.100 made paintAt()'s
    // OWN coverage curve genuinely smooth, but this remap was distorting it
    // downstream on whichever side of a stroke happened to cross terrain
    // where the natural blend leaned toward out[1].
    const resid = (t0 > 0.5) ? (1 - t0) : t0;
    out[0] = around; out[1] = surf;
    out[4] = Math.max(resid * (1 - cov), cov);
    // Authored ground beats the snow cap and the shore blend: if Kevin paints
    // a courtyard at altitude he means a courtyard, not a courtyard under
    // snow.
    if (cov > 0.6) { out[5] = out[5] * (1 - cov); out[6] = out[6] * (1 - cov); }
  }""",
    """  // Rewrite a groundSurface() result in place. Roads sit on top of paint, so
  // a road drawn across a painted field still reads as a road.
  //
  // Patch 86.160: paint is now a genuine third layer, revealed over the
  // natural A-to-B blend rather than rewritten into it. out[0]/out[1]/out[4]
  // (the natural pair and its weight) are left completely untouched here --
  // paint instead rides the altitude-cap slot (out[3]/out[6], tile.w/mix.z
  // in the shader), which every vertex already carries and which authored
  // ground already had priority over ("Authored ground beats the snow cap").
  // That slot renders as a plain reveal on top of whatever came before it,
  // the same way the rock-on-steep-slopes layer works, so paint simply fades
  // in at strength `cov` with nothing to discard underneath.
  //
  // The old approach (83.200 through 86.150) rode the EXISTING A-to-B blend
  // instead: keep whichever natural surface was locally dominant as A, put
  // the authored surface in B, and hand coverage to the blend weight. That
  // worked, but it could only ever show ONE of the two natural textures
  // under a stroke -- the other was discarded -- and WHICH one survived
  // flipped discretely wherever the natural blend's own weight crossed 50%.
  // Where that crossing happened to fall near a paint stroke, the discard
  // choice itself flipped mid-fade, which read as a hard seam through an
  // otherwise smooth stroke: fixed math (86.150), on real per-vertex
  // textures, still discarding one of them. Confirmed live: painting the
  // same brush onto a single uniform natural pair still showed a sharp,
  // stair-stepped edge on the side where the natural blend favoured its
  // second texture, and a clean fade on the side where it favoured its
  // first, with 86.150's coverage curve numerically identical on both
  // sides. Revealing paint as an independent layer removes the discard
  // entirely, so there is nothing left to flip.
  function paint(wx, wz, out) {
    if (!api.on) return;
    if (paintBounds && (wx < paintBounds.x0 || wx > paintBounds.x1 ||
                        wz < paintBounds.z0 || wz > paintBounds.z1)) return;
    let hit = paintAt(wx, wz);
    const rd = roadAt(wx, wz);
    if (rd && (!hit || rd[1] >= hit[1])) hit = rd;
    if (!hit) return;
    out[3] = hit[0];
    out[6] = hit[1];
  }""",
    tag='paint: reveal over out[3]/out[6] instead of discarding a natural texture into out[0]/out[1]/out[4]')

print('86.160_ground_paint_reveal_layer: %d edits applied' % n)
