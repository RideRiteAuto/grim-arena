#!/usr/bin/env python3
"""Patch 87.600 (Phase 3 of TERRAIN-WORKER-OFFLOAD-PLAN.md): retune the
steady-state on-foot chunk-stream budget back from 1+1 (the 85.100 stopgap)
toward its pre-stopgap values of 3+2.

85.100 cut this from 3+2 to 1+1 because the budget throttled REAL
synchronous main-thread work (buildChunk()/dressChunk() building actual
geometry and props inline) -- more per tick meant a longer main-thread
stall, which is what caused the camera-turn stutter Kevin reported.

With TERRAIN_WORKER now true (flipped on Kevin's go-ahead once Phase 1's
byte-diff and Phase 2's own live-path verification both confirmed parity),
the ring-scan loop's worker branch (Phase 2) no longer does that work
synchronously: each budget unit is now just a Map lookup + a postMessage
call, both ~free. The stall this budget was throttling doesn't exist on
that path, so there's no longer a reason to keep it artificially low there
-- see TERRAIN-WORKER-OFFLOAD-PLAN.md Sec8's own note that this was always
meant to be revisited once the offload shipped.

Only the steady-state (non-boot, non-boating/turbo) values move. Boot
backfill (260/40) and boating/turbo (10) budgets are untouched -- those
were never part of 85.100's stopgap and aren't part of this patch's scope.

Real-world effect intentionally observed on the fallback path too: with the
flag flipped back to false (the rollback story), stepTerrain falls through
to the untouched synchronous `else` branch, which WOULD now do 3+2 worth of
real synchronous work per tick again -- i.e. flipping the flag off after
this patch ships reverts terrain-worker behavior but does NOT by itself
restore 85.100's stutter mitigation. Documented here rather than left as a
silent trap: if the worker flag is ever flipped back to false for real (not
just a local test), these two numbers should be dropped back to 1+1 in the
same patch, not assumed still safe.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

ANCHOR1 = "    let budget = boot || ((this.boating || this.rideTurbo) ? 10 : 1);"
assert s.count(ANCHOR1) == 1, 'patch 87.600: anchor1 found %d times, wanted 1' % s.count(ANCHOR1)
NEW1 = "    let budget = boot || ((this.boating || this.rideTurbo) ? 10 : 3);"
s = s.replace(ANCHOR1, NEW1, 1)

ANCHOR2 = "      let dbud = boot ? 40 : 1;"
assert s.count(ANCHOR2) == 1, 'patch 87.600: anchor2 found %d times, wanted 1' % s.count(ANCHOR2)
NEW2 = "      let dbud = boot ? 40 : 2;"
s = s.replace(ANCHOR2, NEW2, 1)

io.open(PATH, 'w', encoding='utf-8').write(s)
print('87.600_terrain_throttle_retune: edited %s (2 anchors)' % PATH)
