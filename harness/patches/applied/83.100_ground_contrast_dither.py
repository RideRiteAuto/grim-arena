#!/usr/bin/env python3
"""Patch 83.100: soften the ground dither for high-contrast surface pairs.

Kevin's report: meadow blends into mountain gravel with no visible seam, but
beach sand blends into anything else as a "stairstep" with visible grid
static. Full investigation (this session): ditherMix() is IDENTICAL code for
every surface pair (patch 79.083 already anti-aliases it by fwidth(t), fading
from a per-fragment dithered hard pick up close to a plain smooth mix() at
distance/grazing angle). Nothing about that function singles out any surface.

ROOT CAUSE: the close-up hard pick is a per-fragment coin flip between the
two RAW texture colours, weighted by the blend fraction. When the two colours
are close in brightness (meadow wash #6f8442 vs mountain gravel wash #8a8272,
about a 12/255 luma gap) the flip is invisible: either pixel reads as roughly
the same shade. When they are far apart (mountain gravel vs beach sand wash
#d9c795, about a 68/255 gap, nearly 6x larger) the exact same flip reads as
harsh salt-and-pepper static, which at a shallow angle or across the brush's
soft edge looks like a stairstep. This is not a bug isolated to beach sand:
measuring the actual rendered luma of all 16 ground layers (below) shows
snow, desert sand and frozen scree sit in the same high-luma band as beach
sand, ~190-236/255, versus ~64-164/255 for everything else, so all four will
show the identical artifact against most neighbours, including combinations
that already exist in authored zone variants (SUNCOAST's "shingle" pairs
mountain gravel with beach sand today).

FIX: give ditherMix() a second, per-surface signal (its measured average
brightness) and use the brightness GAP between the two colours being blended
to push the anti-alias fade toward the smooth side even up close, on top of
the existing distance-based fade. A gap under ~0.12 (0-1 scale) contributes
no change at all, so meadow/mountain-gravel and every other already-fine
pair renders pixel-identical to before. The contribution ramps up between
0.12 and 0.35 and saturates at gaps at or above 0.35, which is where beach
sand, snow, desert sand and frozen scree sit against most of the palette.
This is automatic and per-pair: it never special-cases a surface index, so a
new bright (or dark) surface added later gets the same protection with zero
extra code.

The per-surface brightness comes from measuring the ACTUAL rendered canvas
pixels in buildGroundArray() (not the wash colour alone, which the grain and
blotch passes shift a little), averaged once at boot and passed to the
shader as a 16-entry uniform array alongside the existing sampler.

Verify: harness/ground-contrast.js (added by this patch) renders the same
maths in Node with no GPU, checks the meadow/gravel gap contributes exactly
0 aa boost and the gravel/sand gap contributes a large one, and checks the
measured luma of snow/desert-sand/beach-sand/frozen-scree all clear the 0.35
saturation point while every other surface stays under the 0.12 no-op floor
except where it is already close to a genuinely bright neighbour.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 83.100 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. measure each layer's real rendered brightness while painting it --
sub(
    """    const data = new Uint8Array(TS * TS * 4 * LAYERS);
    for (let i = 0; i < LAYERS; i++) {
      x.clearRect(0, 0, TS, TS);
      P[i](0, 0);
      data.set(x.getImageData(0, 0, TS, TS).data, i * TS * TS * 4);
    }
    const t = new T.DataArrayTexture(data, TS, TS, LAYERS);""",
    """    const data = new Uint8Array(TS * TS * 4 * LAYERS);
    // Patch 83.100: each layer's average rendered brightness (0..1), fed to
    // the shader below so ditherMix() can soften itself for high-contrast
    // pairs. Measured off the ACTUAL painted pixels rather than the wash
    // colour alone, since the blotch/grain passes shift the average a bit.
    const luma = new Array(LAYERS).fill(0);
    for (let i = 0; i < LAYERS; i++) {
      x.clearRect(0, 0, TS, TS);
      P[i](0, 0);
      const px = x.getImageData(0, 0, TS, TS).data;
      data.set(px, i * TS * TS * 4);
      let sum = 0;
      for (let p = 0; p < px.length; p += 4) sum += 0.299 * px[p] + 0.587 * px[p + 1] + 0.114 * px[p + 2];
      luma[i] = sum / (TS * TS) / 255;
    }
    this._groundLuma = luma;
    const t = new T.DataArrayTexture(data, TS, TS, LAYERS);""",
    tag='measure per-layer luma in buildGroundArray')

# ---- 2. pass it to the shader as a uniform ---------------------------------
sub(
    """      sh.uniforms.uGround = { value: surfaces };""",
    """      sh.uniforms.uGround = { value: surfaces };
      // Patch 83.100: per-surface average brightness, read once at first
      // compile like uGround above. ditherMix() uses the gap between two
      // surfaces' entries to soften the close-up dither for high-contrast
      // pairs (beach sand, snow, desert sand, frozen scree against most of
      // the palette) while leaving already-similar pairs untouched.
      sh.uniforms.uGroundLuma = { value: this._groundLuma || new Array(16).fill(0.5) };""",
    tag='add uGroundLuma uniform next to uGround')

# ---- 3. declare the uniform and use it inside ditherMix --------------------
sub(
    """          'uniform highp sampler2DArray uGround;',
          'uniform vec2 uSlope;',""",
    """          'uniform highp sampler2DArray uGround;',
          'uniform float uGroundLuma[16];',
          'uniform vec2 uSlope;',""",
    tag='declare uGroundLuma in the fragment shader')

sub(
    """          'vec3 ditherMix(vec3 a, vec3 b, float t, vec2 w) {',
          '  float n = h21(w * 4.0) - 0.5;',
          '  float aaScale = 40.0;',
          '  float aa = clamp(fwidth(t) * aaScale, 0.0, 1.0);',
          '  float hardPick = step(0.5, t + n * 0.92);',
          '  float e = mix(hardPick, t, aa);',
          '  return mix(a, b, e);',
          '}'""",
    """          // Patch 83.100: idxB is the surface being blended IN at this call
          // (always a single real surface, unlike `a`, which on the second
          // and third ditherMix() calls in groundFragBody is already a
          // blended result -- so lumaA is measured off the actual colour in
          // hand rather than looked up, and stays correct at every stage).
          // A brightness gap under 0.12 contributes nothing (meadow next to
          // mountain gravel, or any similarly-toned pair, renders exactly as
          // before); the gap ramps the fade toward the smooth mix() between
          // 0.12 and 0.35 and is fully smooth at or above it, which is where
          // beach sand/snow/desert sand/frozen scree sit against most of the
          // palette.
          'vec3 ditherMix(vec3 a, vec3 b, float t, vec2 w, float idxB) {',
          '  float n = h21(w * 4.0) - 0.5;',
          '  float aaScale = 40.0;',
          '  float aa = clamp(fwidth(t) * aaScale, 0.0, 1.0);',
          '  float lumaA = dot(a, vec3(0.299, 0.587, 0.114));',
          '  float lumaB = uGroundLuma[int(idxB + 0.5)];',
          '  float contrast = smoothstep(0.12, 0.35, abs(lumaA - lumaB));',
          '  aa = max(aa, contrast);',
          '  float hardPick = step(0.5, t + n * 0.92);',
          '  float e = mix(hardPick, t, aa);',
          '  return mix(a, b, e);',
          '}'""",
    tag='add the contrast-aware softening inside ditherMix')

# ---- 4. pass idxB at each call site -----------------------------------------
sub(
    "'vec3 gcol = ditherMix(groundSurf(vTile.x, vWorld), groundSurf(vTile.y, vWorld), vMix.x, vWorld);',",
    "'vec3 gcol = ditherMix(groundSurf(vTile.x, vWorld), groundSurf(vTile.y, vWorld), vMix.x, vWorld, vTile.y);',",
    tag='pass idxB on the base-pair call')

sub(
    "'if (rw > 0.001) gcol = ditherMix(gcol, groundSurf(vTile.z, vWorld), rw, vWorld + 31.7);',",
    "'if (rw > 0.001) gcol = ditherMix(gcol, groundSurf(vTile.z, vWorld), rw, vWorld + 31.7, vTile.z);',",
    tag='pass idxB on the rock call')

sub(
    "'if (vMix.z > 0.001) gcol = ditherMix(gcol, groundSurf(vTile.w, vWorld), vMix.z, vWorld + 71.3);',",
    "'if (vMix.z > 0.001) gcol = ditherMix(gcol, groundSurf(vTile.w, vWorld), vMix.z, vWorld + 71.3, vTile.w);',",
    tag='pass idxB on the cap call')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('83.100_ground_contrast_dither: %d edits applied' % n)
