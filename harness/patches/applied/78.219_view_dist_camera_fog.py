#!/usr/bin/env python3
"""Patch 78.219: wire the scene's camera far plane, fog, and background to
the new VIEW_DIST setting (part 2 of the Phase 2 overhaul; see 78.104's
docstring for the full rationale).

Also applies the near/far/fog retune from claude/PERF-AUDIT-AUG6.md item 6,
independent of which VIEW_DIST tier is active:

- near 0.1 -> 0.35: the sea plane and pushed-down terrain vertices leave only
  a 3cm gap, and depth resolution at 24-bit exceeds that gap past ~224m, so
  every shoreline shimmers. 0.35 pushes the onset past the fog wall; the
  third-person camera never gets within 0.35m of anything, so this costs
  nothing.
- far 950 -> 750 (before the VIEW_DIST multiplier): nothing exists past
  ~510m, the r=640 sky dome just needs headroom.
- fog 60/430 -> 70/420 (before the multiplier), and scene.background set to
  the exact fog color instead of a slightly different one (0x231e29 vs
  0x2b2331) - fully-fogged terrain used to sit as a lighter band on the
  horizon instead of dissolving into the sky.

this.viewDist is read from localStorage here, before the scene is built, so
the very first frame already renders at the saved distance instead of
snapping right after boot. See applyViewDist()/toggleViewDist() (patch
78.512) for how it changes at runtime.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    const scene = new T.Scene();
    scene.background = new T.Color(0x231e29);
    scene.fog = new T.Fog(0x2b2331, 60, 430);
    this.scene = scene;

    const cam = new T.PerspectiveCamera(62, 16 / 9, 0.1, 950);
    this.cam = cam;
"""

NEW = """    // Draw distance is adjustable (pause-menu DRAW button). Read the saved
    // preference before the scene exists so boot doesn't visibly snap once
    // gfxInit()/viewDistInit() run later. See GRIM_RULES.VIEW_DIST.
    if (this.viewDist === undefined) {
      let vv = null; try { vv = localStorage.getItem('grim-viewdist'); } catch (e) {}
      this.viewDist = (vv === 'near' || vv === 'far') ? vv : 'normal';
    }
    const _vdBoot = (GRIM_RULES.VIEW_DIST[this.viewDist] || GRIM_RULES.VIEW_DIST.normal).mult;

    const scene = new T.Scene();
    const FOG_COLOR = 0x2b2331;
    scene.background = new T.Color(FOG_COLOR);   // matched to fog so fully-fogged terrain dissolves instead of banding
    scene.fog = new T.Fog(FOG_COLOR, 70 * _vdBoot, Math.round(420 * _vdBoot));
    this.scene = scene;

    const cam = new T.PerspectiveCamera(62, 16 / 9, 0.35, Math.round(750 * _vdBoot));
    this.cam = cam;
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
