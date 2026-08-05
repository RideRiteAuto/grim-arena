#!/usr/bin/env python3
"""One source of truth for roam radius.

buildZoneCreatures set `homeR` from the spawn table AND the bestiary carried a
`roamR`, and roamRadius reads homeR first, so the spawn table silently won: a
boar roamed 30 metres while the table that is supposed to describe boars said
26. Two numbers for one fact is how they drift.
"""
import io
SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
OLD = "          sig: B.sig || null, sigCd: 2 + (i % 5), zoneSpecies: entry.of, homeR: entry.homeR || 26"
NEW = "          sig: B.sig || null, sigCd: 2 + (i % 5), zoneSpecies: entry.of"
assert src.count(OLD) == 1, 'anchor not unique'
out = src.replace(OLD, NEW, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('roam radius single-sourced, %d -> %d bytes' % (len(src), len(out)))
