#!/usr/bin/env python3
"""Patch 86.150: fix a sign error in paint()'s blend-weight remap that was
still producing hard, blocky edges on SOME sides of a paint stroke after
86.100.

BACKGROUND: 86.100 fixed paintAt()'s coverage formula so it genuinely fades
with distance instead of being pinned at 1.0. Kevin re-tested and reported
it was STILL blocky, with an annotated screenshot showing specific edges of
a single circular stroke still hard while other edges of the SAME circle
looked fine. That directional inconsistency was the tell: whatever was
still wrong depended on something that varies by direction around the
stroke, not on paintAt() itself (which is direction-agnostic).

Investigation ruled out ditherMix()'s contrast-based dithering gate (forcing
it fully smooth, unconditionally, produced a pixel-for-pixel identical
render to the buggy one -- confirmed the shader wasn't the culprit at all).
Live probing of the real per-vertex data (monkey-patching groundSurface()
during an actual chunk rebuild, and querying the real GRIM_EDIT.paintAt()
directly) found the actual break in paint() itself, a few lines below where
86.100 already fixed paintAt():

    const surf = hit[0], cov = hit[1];
    const around = (out[4] > 0.5) ? out[1] : out[0];
    if (surf === around) { out[0] = around; out[1] = around; return; }
    out[0] = around; out[1] = surf;
    out[4] = Math.max(out[4] * (1 - cov), cov);

out[4] is the blend weight, read downstream as mix(out[0], out[1], out[4])
(0 = pure out[0], 1 = pure out[1]). Call the natural, pre-paint value of
out[4] t0.

  - When t0 <= 0.5, "around" is assigned from the natural out[0]. Reusing t0
    (small) as the residual term in max(t0*(1-cov), cov) is roughly sound:
    it represents "how much of not-around was already showing here", which
    is a reasonable thing to ease back toward as cov fades.
  - When t0 > 0.5, "around" is assigned from the natural out[1] INSTEAD. But
    the code still reused the same t0 (now large, e.g. 0.97) as the residual
    term. Since out[1] has just been reassigned to `surf`, t0 no longer
    means "residual toward not-around" in this branch -- it means the
    opposite. The correct residual here is (1 - t0), not t0.

Real numbers captured live from the running game (single hardness=1/flow=1/
organic=false meadow dot, brush radius 8, painted at world (0, 300), sampled
along +X): real paintAt() coverage faded cleanly and monotonically (0.9911,
0.9039, 0.7763, ..., 0.1853, 0.0365, then null past the blend radius), but
the actual per-vertex blend weight the shader received JUMPED back up to
0.7869 (79% meadow) at x=10 where coverage was only 0.1853 (should read
~19% meadow), because the natural terrain's own t0 at that vertex happened
to be about 0.966 (> 0.5). Two metres further out, coverage crossed the 0.02
cutoff and paint() stopped applying at all, so the surface fell from ~79%
meadow straight to 0% in a single 2m step -- a much harder, more sudden
transition than the smooth cov curve it was supposed to be tracking. This
only happens on whichever side of a stroke crosses terrain where the
natural blend happens to favour its own second texture (t0 > 0.5), which is
essentially random per-vertex and unrelated to where the paint was applied,
exactly matching the "hard on some sides, fine on others" symptom in
Kevin's screenshot.

FIX: complement t0 in the branch where "around" came from out[1], so the
residual term always means the same thing (how much of not-around/surf was
already showing) regardless of which side "around" was pulled from:

    const t0 = out[4];
    const around = (t0 > 0.5) ? out[1] : out[0];
    if (surf === around) { out[0] = around; out[1] = around; return; }
    const resid = (t0 > 0.5) ? (1 - t0) : t0;
    out[0] = around; out[1] = surf;
    out[4] = Math.max(resid * (1 - cov), cov);

VERIFIED:
  - harness/ground-paint-coverage.js (86.100's regression harness, untouched
    by this patch) still passes in full, including the painted-to-painted
    border numbers, which this patch does not touch.
  - Re-ran the same live per-vertex probe after this fix: the x=10 sample
    above now reads 0.1853, matching cov exactly (was 0.7869). Checked a
    second, independent direction (+Z from the same paint centre) and found
    every sample already tracked cov exactly with no spike, confirming the
    fix generalises rather than being tuned to one direction.
  - Real before/after screenshots at the same test spot/settings used
    throughout this investigation (world (0, 300), camera straight down at
    y=45, hardness=1/flow=1/organic=false): before, a sharp binary
    green/brown "staircase" with zero visible gradient; after, a wide,
    genuinely dithered/mottled transition band several metres across, all
    the way around the stroke.

WHERE THIS LIVES: paint() ships inside editor-core.js, inside the EDITOR
marker region of the bundle (read by every client, since ground paint has
to render for players, not just the editor), so this patch edits the
tracked file directly, never /tmp/game-src.html -- see patch 83.200's and
86.100's docstrings for why that distinction matters.

NOTE ON PATCH ORDER: this fix was authored and verified directly against
editor-core.js in-place, then this script was written afterward purely as
the durable historical record (matching the project's numbered-patch
convention) -- the old/new pair below is accurate to what changed, but
running this script against the current tracked file will correctly fail
its anchor assert, since the file already contains the fix. That failure is
intentional, same as any other applied/ patch.
"""
import io

n = 0
def sub(path, old, new, count=1, tag=''):
    global n
    t = io.open(path, encoding='utf-8').read()
    f = t.count(old)
    assert f == count, 'patch 86.150 [%s / %s]: anchor found %d times, wanted %d' % (path, tag, f, count)
    t = t.replace(old, new)
    io.open(path, 'w', encoding='utf-8').write(t)
    n += 1

sub('editor-core.js',
    """    const surf = hit[0], cov = hit[1];
    const around = (out[4] > 0.5) ? out[1] : out[0];
    if (surf === around) { out[0] = around; out[1] = around; return; }
    out[0] = around; out[1] = surf;
    out[4] = Math.max(out[4] * (1 - cov), cov);
    // Authored ground beats the snow cap and the shore blend: if Kevin paints
    // a courtyard at altitude he means a courtyard, not a courtyard under
    // snow.
    if (cov > 0.6) { out[5] = out[5] * (1 - cov); out[6] = out[6] * (1 - cov); }""",
    """    const surf = hit[0], cov = hit[1];
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
    if (cov > 0.6) { out[5] = out[5] * (1 - cov); out[6] = out[6] * (1 - cov); }""",
    tag='paint: complement the residual when "around" comes from out[1]')

print('86.150_ground_paint_blend_remap_sign: %d edits applied' % n)
