#!/usr/bin/env python3
"""Patch 85.100: cut the steady-state on-foot chunk-stream budget from 3
terrain rebuilds + 2 dressing passes per throttled tick down to 1 + 1.

Kevin reported (Aug 8): while running and turning to look around, the
camera randomly stutters/jitters, like it "forgets which way I was
looking" for a beat. His own guess was that it's tied to how the world
streams in around the player, which is exactly right.

Root cause, read directly out of stepTerrain()/buildChunk() in
game-src.html: chunk streaming is real synchronous main-thread work
(buildChunk() loops every vertex of up to a 32x32-segment PlaneGeometry,
sampling GRIM_WORLD.height()/zone() and the ground-surface/terrain-color
functions per vertex; dressChunk() places props on top of that) called
from stepTerrain(), which runs inside the same tick(dt) frame as mouse-
look, driveLocal(), and the render call, every ~0.12s the player is
moving. Up to 3 fresh terrain chunks and 2 dressing passes could land in
one throttled window before this patch. This isn't a guess: the
CODE-SWEEP-AUG8.md Tier 3 audit already flagged this exact spot ("no Web
Worker anywhere for chunk/terrain generation... budget-throttled but not
offloaded") as a real, known cost center, and ZONE-DRESSING-STATUS.md's
own measurements name "chunk build time (the hitch walking into new
ground)" as the real performance ceiling.

Pointer-lock mouse-look (the "locked" branch of the mousemove handler)
applies raw movementX/Y deltas directly to this.yaw/this.pitch with no
smoothing on purpose - by design, that's the responsive, no-lag path.
But it means a synchronous hitch on the main thread (this budgeted chunk
work) blocks that frame's render AND queues up whatever mouse deltas
arrived during the stall; they all land at once the instant the thread
frees up. The eye sees the view hold still, then jump straight to the
new orientation with none of the frames in between - which reads exactly
like "it forgot which way I was looking," worse the more you're actively
turning (more accumulated delta to dump in one jump) and worse while
moving (more chunk-boundary crossings trigger the budget to spend).

This is a mitigation, not the real fix. The real fix (per CODE-SWEEP-
AUG8.md Tier 3) is offloading buildChunk/dressChunk to a Web Worker so
none of this blocks the render thread at all - that's real engineering
work, not a patch. What this patch does instead: spend the exact same
total budget, just spread over 3x as many throttled ticks (1 terrain +
1 dressing chunk per ~0.12s instead of 3 + 2), so no single frame does
more than one chunk's worth of vertex-loop work. Trade-off: chunks a
couple rings out take a little longer to reach full detail as you
approach (pop-in happens slightly later/more gradually), in exchange for
a meaningfully smaller worst-case synchronous stall per frame. Boot
backfill (`boot` truthy, called once at load and zone-teleport, never
mid-frame-loop) and boating/rideTurbo (already intentionally higher at
10 to keep up with faster travel) are both untouched - only the ordinary
on-foot steady-state numbers move.

Verify: harness/boot.js and friends currently can't reach gameplay (the
"PLAY AS GUEST" button was removed for mandatory accounts, a pre-existing
gap already flagged in MOB-SYNC-JITTER-PLAN.md on Aug 7, not something
this patch introduces or is trying to fix), so this could not be run
through a real-boot harness test. Verified instead by direct code
reading: both edited lines are pure numeric constants read once per
stepTerrain() call, feeding the exact same budget-countdown loop already
exercised on every single chunk load in the live game today (this is not
new logic, just a smaller number), so the failure mode of "the constant
is wrong" is strictly "pop-in is paced differently," never a crash,
desync, or save issue. node --check (via harness/build.sh) confirms the
file still parses after the edit.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD1 = "    let budget = boot || ((this.boating || this.rideTurbo) ? 10 : 3);"
NEW1 = "    let budget = boot || ((this.boating || this.rideTurbo) ? 10 : 1);"
c1 = s.count(OLD1)
assert c1 == 1, 'patch 85.100: terrain budget anchor found %d times, wanted 1' % c1
s = s.replace(OLD1, NEW1)

OLD2 = "      let dbud = boot ? 40 : 2;"
NEW2 = "      let dbud = boot ? 40 : 1;"
c2 = s.count(OLD2)
assert c2 == 1, 'patch 85.100: dressing budget anchor found %d times, wanted 1' % c2
s = s.replace(OLD2, NEW2)

io.open(PATH, 'w', encoding='utf-8').write(s)
print('85.100_terrain_stream_budget: edited /tmp/game-src.html (2 anchors)')
