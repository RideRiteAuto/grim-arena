#!/usr/bin/env python3
"""Patch 84.760: raise NPC position precision over the wire from 0.1m to 0.01m.

Tier 2 item #6 (claude/TIER2-NETWORKING-EDITOR-PLAN.md): the Aug 6 audit
flagged the hardcoded x10/round/divide-by-10 quantization on NPC positions
as worth roughly 20% apparent speed variance on its own. At 0.1m precision,
a monster's true per-tick displacement (walking at SPEED=5.6m/s over a
100ms-ish snapshot interval is on the order of half a metre) can have its
rounding error be a meaningful fraction of the actual step, which reads to
a player as inconsistent, slightly-wrong-feeling motion -- worse the slower
the monster is moving, which is most of the time (idle/patrol speeds are a
fraction of SPEED).

This is a real protocol change: both the relay-worker.js encoder (this
patch's sibling edit, made directly since relay-worker.js is a real
top-level file, not part of this embedded bundle) and this client decoder
must agree on the multiplier or NPC positions read as ten times too large
or too small depending on which side changed first. Both are edited in the
same commit so neither can deploy alone. 0.01m (x100) was chosen as a
straightforward 10x precision gain: WORLD_R is 4800, so the largest encoded
value is under 500,000, comfortably inside a safe JSON integer and only one
extra ASCII digit per coordinate per NPC snapshot row -- a negligible
bandwidth cost for the smoothness gain. Yaw's own x100 encoding two lines
below is untouched: it was never the thing the audit flagged, and 0.01 rad
(about 0.57 degrees) was already fine.

Verify: harness/editor.js and node harness/simtest.mjs don't exercise the
relay wire protocol at all (client-only / server-sim-only respectively), so
this got a real protocol-level round trip instead, via a local wrangler dev
relay: harness/relay-bot.js sending a manifest + 'nhit' burst and reading
back onNpcSnap-shaped 'nsnap' rows was not enough on its own (the bot
doesn't run onNpcSnap), so verification also decoded a captured 'nsnap' row
by hand against known NPC coordinates and confirmed x100/100 round-trips a
sub-decimetre position exactly where x10/10 could not.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = "      const sx = r[1] / 10, sz = r[2] / 10;"
NEW = "      const sx = r[1] / 100, sz = r[2] / 100;"

count = s.count(OLD)
assert count == 1, 'patch 84.760: anchor found %d times, wanted 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
print('84.760_npc_position_precision: edited /tmp/game-src.html')
