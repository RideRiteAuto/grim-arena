#!/usr/bin/env python3
"""Patch 86.100: fix ground-paint coverage so it actually fades with distance.

ROOT CAUSE (found investigating Kevin's "half the circle blends smooth, half
is blocky" report -- patch 83.200 widened EDIT.BLEND_DEFAULT, which helped
paint-onto-paint borders, but Kevin then re-tested with a single dot painted
onto BLANK ground and it still looked hard-edged with no improvement at all
from the wider slider):

  paintAt() in editor-core.js computes coverage as:

      cov = (weight of nearby painted cells matching the nearest surface)
          / (weight of nearby painted cells, period)

  This is a ratio over PAINTED cells only -- unpainted neighbours are
  skipped entirely (`if (s === undefined) continue;`) and never enter
  either side of the ratio. So anywhere the paint is a single surface with
  no other paint nearby (a lone dot, or any stroke's interior), every
  painted cell within the sample radius matches the nearest surface by
  definition, and the ratio is EXACTLY 1 at every distance from 0 out to
  blend + PCELL, where it hits a wall and returns null. Raising
  BLEND_DEFAULT (83.200) only pushed that wall further out; it never
  created an actual gradient, because the top of the fraction and the
  bottom of the fraction were always equal.

  This is also why meadow-into-mountain-gravel already looked seamless
  before 83.200: with paint on BOTH sides of the border, "nearby painted
  cells" is a real mix of the two surfaces, so the ratio genuinely does
  slide from 0 to 1 across the border. It was never about the surface
  type, exactly matching what Kevin suspected out loud.

FIX: coverage has to be a ratio over the WHOLE sampled neighbourhood, not
just the painted part of it. Unpainted cells now enter the denominator
(as non-matching weight) even though they can never enter the numerator,
so a lone dot's coverage genuinely tapers across `blend` metres as the
sample point crosses from "surrounded by paint" to "surrounded by nothing".
Verified in isolation (see harness/ground-paint-coverage.js) that:
  - a single painted dot on blank ground now fades from ~1.0 near its
    centre down through the whole 0..1 range and past the 0.02 cutoff,
    across roughly one BLEND width outside the painted edge, instead of
    being pinned at 1.0 right up to a hard cliff
  - two adjacent painted regions (the already-working case) are numerically
    UNCHANGED, because every sampled cell there is painted either way, so
    the new denominator equals the old one exactly

This does not touch the separate, smaller flat-shading banding artifact in
the terrain mesh (each triangle's aTile/aMix come from one provoking vertex,
so a real gradient still renders as a staircase at the mesh's vertex
spacing, ~2m near the player). That is a real, secondary residue worth a
follow-up pass, but it no longer produces a one-sided hard edge, since the
underlying data is now a genuine multi-step gradient instead of a two-value
cliff.

WHERE THIS LIVES: editor-core.js ships inside the EDITOR marker region of
the bundle and is read by every client (ground paint has to render for
players, not just the editor), so this patch edits the tracked file
directly, never /tmp/game-src.html -- see patch 83.200's docstring for why
that distinction matters.
"""
import io

n = 0
def sub(path, old, new, count=1, tag=''):
    global n
    t = io.open(path, encoding='utf-8').read()
    f = t.count(old)
    assert f == count, 'patch 86.100 [%s / %s]: anchor found %d times, wanted %d' % (path, tag, f, count)
    t = t.replace(old, new)
    io.open(path, 'w', encoding='utf-8').write(t)
    n += 1

sub('editor-core.js',
    """  function paintAt(x, z) {
    if (!paintIdx || !paintIdx.size) return null;
    const jAmp = PCELL * 0.6;
    const jx = Math.sin(x * 0.83 + z * 1.31) * jAmp;
    const jz = Math.cos(x * 1.17 - z * 0.71) * jAmp;
    const sx = x + jx, sz = z + jz;
    const blend = Math.max(PCELL * 0.5, (L && L.blend) || BLEND_DEFAULT);
    const rc = Math.max(1, Math.ceil(blend / PCELL) + 1);
    const c0 = Math.floor(sx / PCELL), z0 = Math.floor(sz / PCELL);
    let nearSurf, nearD = Infinity;
    const hits = [];                       // flattened [d, surf, d, surf, ...]
    for (let dz = -rc; dz <= rc; dz++) {
      for (let dx = -rc; dx <= rc; dx++) {
        const cx = c0 + dx, cz = z0 + dz;
        const s = paintIdx.get(pCellKey(cx, cz));
        if (s === undefined) continue;
        const wx = (cx + 0.5) * PCELL, wz = (cz + 0.5) * PCELL;
        const ddx = wx - sx, ddz = wz - sz;
        const d = Math.sqrt(ddx * ddx + ddz * ddz);
        if (d > blend + PCELL) continue;
        hits.push(d, s);
        if (d < nearD) { nearD = d; nearSurf = s; }
      }
    }
    if (nearSurf === undefined) return null;
    let wSum = 0, wMatch = 0;
    for (let i = 0; i < hits.length; i += 2) {
      const d = hits[i], s = hits[i + 1];
      const t = Math.min(1, d / blend);
      const w = 1 - t * t * (3 - 2 * t);   // smoothstep falloff, 1 at d=0
      wSum += w;
      if (s === nearSurf) wMatch += w;
    }
    const cov = wSum > 0 ? wMatch / wSum : 1;
    if (cov <= 0.02) return null;
    return [nearSurf, cov];
  }""",
    """  function paintAt(x, z) {
    if (!paintIdx || !paintIdx.size) return null;
    const jAmp = PCELL * 0.6;
    const jx = Math.sin(x * 0.83 + z * 1.31) * jAmp;
    const jz = Math.cos(x * 1.17 - z * 0.71) * jAmp;
    const sx = x + jx, sz = z + jz;
    const blend = Math.max(PCELL * 0.5, (L && L.blend) || BLEND_DEFAULT);
    const rc = Math.max(1, Math.ceil(blend / PCELL) + 1);
    const c0 = Math.floor(sx / PCELL), z0 = Math.floor(sz / PCELL);
    let nearSurf, nearD = Infinity;
    // Pass 1: nearest painted cell decides what "the authored surface" is
    // here, same as before -- only painted cells are candidates.
    for (let dz = -rc; dz <= rc; dz++) {
      for (let dx = -rc; dx <= rc; dx++) {
        const cx = c0 + dx, cz = z0 + dz;
        const s = paintIdx.get(pCellKey(cx, cz));
        if (s === undefined) continue;
        const wx = (cx + 0.5) * PCELL, wz = (cz + 0.5) * PCELL;
        const ddx = wx - sx, ddz = wz - sz;
        const d = Math.sqrt(ddx * ddx + ddz * ddz);
        if (d > blend + PCELL) continue;
        if (d < nearD) { nearD = d; nearSurf = s; }
      }
    }
    if (nearSurf === undefined) return null;
    // Pass 2: patch 86.100 -- weigh EVERY sampled cell, painted or not, so an
    // unpainted neighbour dilutes coverage instead of being skipped. Without
    // this, a lone patch surrounded by nothing has no non-matching weight to
    // divide against, so the ratio is stuck at 1 out to a hard cliff instead
    // of actually fading. Two adjacent painted surfaces are unaffected: every
    // sampled cell there is painted either way, so this sums the same terms
    // the old loop did.
    let wSum = 0, wMatch = 0;
    for (let dz = -rc; dz <= rc; dz++) {
      for (let dx = -rc; dx <= rc; dx++) {
        const cx = c0 + dx, cz = z0 + dz;
        const wx = (cx + 0.5) * PCELL, wz = (cz + 0.5) * PCELL;
        const ddx = wx - sx, ddz = wz - sz;
        const d = Math.sqrt(ddx * ddx + ddz * ddz);
        if (d > blend + PCELL) continue;
        const s = paintIdx.get(pCellKey(cx, cz));
        const t = Math.min(1, d / blend);
        const w = 1 - t * t * (3 - 2 * t);   // smoothstep falloff, 1 at d=0
        wSum += w;
        if (s === nearSurf) wMatch += w;
      }
    }
    const cov = wSum > 0 ? wMatch / wSum : 1;
    if (cov <= 0.02) return null;
    return [nearSurf, cov];
  }""",
    tag='paintAt: weigh unpainted neighbours so coverage actually fades')

print('86.100_ground_paint_coverage_falloff: %d edits applied' % n)
