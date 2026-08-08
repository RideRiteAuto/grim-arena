#!/usr/bin/env python3
"""Patch 82.734: give the terrain detail-ring and prop-dressing ring the same
hysteresis treatment the NPC LOD bands already got.

This is a different bug from the NPC band hysteresis fixed in v18.1
(78.104-78.512): a chunk sitting right at the DETAIL ring boundary was doing
a full geometry dispose+rebuild (32-segment <-> 8-segment) every time the
player's chunk index ticked across the line, which happens on every ~64m of
travel near the boundary - normal at the game's own measured NPC engagement
median of 157m. Same story for prop dressing at the DRESS boundary. This was
already called out as the recommended fix in PERF-AUDIT-AUG6.md ("promote at
ring<=3, demote at ring>=5" / "props ... dropped at ring 5 not ring 3") but
was only ever applied to the NPC bands, not to terrain or dressing.

Two independent, minimal changes:
1. wantSeg now checks the chunk's OWN current state: once at full detail, it
   stays there until the player is a full ring further out than the entry
   threshold, instead of flipping the instant the bare compare crosses.
2. The dressing drop check widens from `r > DRESS` to `r > DRESS + 1` so a
   chunk that gets dressed at ring<=DRESS is not immediately eligible to be
   undressed at that same ring on the way back out.

No behavior change deep in either band (well inside DETAIL/DRESS: same as
before; well outside: same as before) - only the boundary ring gets a buffer
instead of flipping on every crossing.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """          const cx = pcx + dx, cz = pcz + dz, key = cx + ',' + cz;
          const wantSeg = ring <= DETAIL ? 32 : 8;
          const have = this._chunks.get(key);
          if (have && have.seg === wantSeg) continue;
"""

NEW = """          const cx = pcx + dx, cz = pcz + dz, key = cx + ',' + cz;
          const have = this._chunks.get(key);
          // Hysteresis: once a chunk is at full detail, keep it there until the
          // player is a full ring further out, so a chunk sitting right on the
          // boundary does not dispose+rebuild its geometry on every crossing.
          const wantSeg = (have && have.seg === 32) ? (ring <= DETAIL + 1 ? 32 : 8) : (ring <= DETAIL ? 32 : 8);
          if (have && have.seg === wantSeg) continue;
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)

OLD2 = """      } else if (r > DRESS && ch.dressed) {
"""

NEW2 = """      } else if (r > DRESS + 1 && ch.dressed) {   // hysteresis: promoted at ring<=DRESS, dropped only past DRESS+1
"""

count2 = s.count(OLD2)
assert count2 == 1, 'anchor2 matched %d times, expected 1' % count2
s = s.replace(OLD2, NEW2)

io.open(PATH, 'w', encoding='utf-8').write(s)
