#!/usr/bin/env python3
"""Patch 87.020: shrink the ground shader's macro texture period so its
blotches stop reading as big flat "little squares".

Kevin's report, after 86.160 (which fixed the paint tool's coverage math)
still showed hard-edged blocky patches in NATURAL, unpainted terrain far from
any paint stroke. His own theory was that the paint brush itself is built
"like Microsoft Paint, little squares added together" and needs a rewrite.

Investigation this session (real before/after renders at a fixed grazing
camera, PX=0 PZ=300, throwaway Playwright harnesses in /tmp, not committed):

1. Per-vertex probes on GRIM_EDIT.paint() showed out[0]/out[1]/out[4] (the
   natural blend channels) are bit-identical before and after paint() runs.
   GRIM_GDBG=3 (raw vTile/vMix as RGB) rendered the natural blend channel as
   a perfectly smooth solid colour even off any paint stroke. The blockiness
   reproduces in terrain nowhere near a paint stroke. All three rule out the
   paint tool/brush entirely: this is a ground-rendering issue, not a paint
   one.
2. Two shader theories were tested and DISPROVEN by real render comparison
   (pixel-identical before/after at the same crop): h21()'s sin()-based hash
   losing precision at large world coordinates, and the rock/slope reveal
   ditherMix() call.
3. Isolating groundSurf()'s two texture() samples independently (temporary
   debug render modes, not shipped) found the cause: the "detail" sample
   (w/3.5) renders as fine grain, but the "macro" sample (w/26.0) ALONE
   reproduces the exact same blocky pattern as the full shaded render.

ROOT CAUSE: groundSurf()'s macro texture() call divides world position by
26.0, meaning one full repeat of the 256x256 ground atlas layer (the comment
above calls out 3.5m/26m as "deliberately not harmonics") spans 26 real
metres. Each layer's blotch() pass paints a modest number of relatively
large, flat-coloured shapes onto that 256x256 canvas (see buildGroundArray
above, e.g. layer 7 MOUNTAIN GRAVEL's `blotch(...,28,30,120,...)`). Stretched
across a 26m span, those same blotches project to multi-metre flat-coloured
patches in the game world, which is exactly what reads as "big flat squares".
This is unrelated to mipmapping/precision/dithering: it is simply how large
the macro layer's own features are once you fix how many real metres its
one texture repeat covers.

FIX: divide by 9.5 instead of 26.0, i.e. shrink the macro layer's real-world
footprint by roughly 2.7x, so the same blotch shapes project to much smaller,
less visually dominant patches. Chosen, not just any smaller number, to stay
comfortably non-harmonic with the 3.5m detail period (per the existing
in-code design intent) while still being clearly larger-scale than detail,
preserving the "distinct macro variation that only repeats hundreds of
metres out" the original comment describes. Verified by direct real-render
comparison at the same crop used throughout this investigation: 26.0 shows
prominent multi-metre flat blocks, 9.5 shows visibly smaller, far less
dominant patches. (A same-crop test at a still-smaller period, 13.0, showed
the effect scales continuously with the divisor, i.e. this is a real,
explainable lever and not a threshold fluke; 9.5 was chosen over an even
smaller value to avoid collapsing macro's scale too close to detail's.)

Two other changes were tried and explicitly do NOT ship here because they
were disproven or added no measurable benefit: the h21() sine-free hash
rewrite (zero effect on the actual artifact) and a texture() LOD bias on the
macro sample (negligible effect, mean pixel delta well under 1/255 at the
same crop). Neither is included in this patch; the fix is the single divisor
change below.

This is not expected to fully eliminate every trace of "textured" ground at
extreme close range (already flagged as a separate, optional, art-only
follow-up when 86.160 shipped) -- it fixes the specific "little squares"
complaint by shrinking the macro layer's real-world feature size, which is
the thing that was actually causing it.

WHERE THIS LIVES: groundSurf() is built inline inside makeGroundMat()'s
onBeforeCompile fragment-shader string, outside every SHARED-RULES/WORLD-GEN
/EDITOR/WORKER marker region repack.py syncs from tracked source files, so it
is patched directly against the extracted game-src.html, following the same
pattern as 83.100/83.200/79.083 before it.

Verify: harness/build.sh (syntax gate both sides of pack); no automated
render harness exists for this shader path, so this was verified with a
manual before/after screenshot comparison during the session that authored
this patch, not by a script checked into the repo.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 87.020 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


sub(
    "'  vec3 macro  = texture(uGround, vec3(w / 26.0, idx)).rgb;',",
    "  // Patch 87.020: was / 26.0. At that period each surface's blotch()\n"
    "          // shapes (see buildGroundArray, e.g. layer 7 MOUNTAIN GRAVEL's\n"
    "          // blotch(...,28,30,120,...)) project to multi-metre flat-coloured\n"
    "          // patches in world space, which is what read as \"little squares\".\n"
    "          // Shrinking to / 9.5 cuts that real-world footprint by ~2.7x while\n"
    "          // staying comfortably non-harmonic with the 3.5m detail period, per\n"
    "          // this function's original design-intent comment above.\n"
    "          '  vec3 macro  = texture(uGround, vec3(w / 9.5, idx)).rgb;',",
    tag='shrink macro texture period from 26.0 to 9.5')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('87.020_ground_macro_scale: %d edits applied' % n)
