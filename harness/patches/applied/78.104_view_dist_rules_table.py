#!/usr/bin/env python3
"""Patch 78.104: add GRIM_RULES.VIEW_DIST, the adjustable-draw-distance table.

Part 1 of the Phase 2 overhaul from claude/MOB-SYNC-JITTER-PLAN.md and
claude/PERF-AUDIT-AUG6.md (items 6/7 in that doc's ship order): a player-
facing draw distance setting, independent of GRAPHICS (HIGH/LOW). GRAPHICS is
the frame-rate safety net (shadows, extra lights, clutter density). VIEW_DIST
is a preference for how far the world itself renders - camera far plane, fog,
and the terrain/prop chunk-ring radii, scaled together so raising it does not
defog scenery the camera still clips or fog the scenery it draws further out.

Deliberately does NOT touch farBand() (fixed at 65m, patch 74.317): the relay
only tracks a monster's real position within 60m (GRIM_RULES.INTEREST_R), so
showing one further out than the client can hear from reopens the exact
"teleport" bug that patch fixed. Widening monster visibility needs INTEREST_R
to grow on the relay too, which costs Cloudflare relay time per player - a
separate sizing conversation, not bundled into this slider.

normal.mult = 1.0 reproduces today's live numbers exactly (DETAIL 3, COARSE
7, dressRing unchanged) so nobody's view changes until they touch the new
button.

IMPORTANT: GRIM_RULES is authored in shared-rules.js, not in the bundle.
repack.py's sync_rules() overwrites everything between the SHARED-RULES
markers in /tmp/game-src.html from that file on every pack, so a patch
against the embedded copy gets silently discarded the moment build.sh packs
- learned the hard way when this patch's first version passed node --check
and the round-trip verify (both blind to it) and only failed at runtime
("Cannot read properties of undefined, reading 'normal'") because
GRIM_RULES.VIEW_DIST did not survive the sync. This version edits the real
source file so the sync carries it forward.
"""
import io

PATH = 'shared-rules.js'
s = io.open(PATH, encoding='utf-8').read()

OLD = """  GFX_SCALE: {
    high: { clutter: 1.0, dressRing: 2 },
    low:  { clutter: 0.45, dressRing: 1 }
  },
"""

NEW = """  GFX_SCALE: {
    high: { clutter: 1.0, dressRing: 2 },
    low:  { clutter: 0.45, dressRing: 1 }
  },

  // Adjustable draw distance (patch 78.104+, see that patch's docstring for
  // the full rationale). Scales camera far, fog near/far, and the terrain
  // detail/coarse/prop-dressing chunk rings together. normal = live today.
  VIEW_DIST: {
    near:   { mult: 0.72, label: 'NEAR' },
    normal: { mult: 1.0,  label: 'NORMAL' },
    far:    { mult: 1.35, label: 'FAR' }
  },
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
