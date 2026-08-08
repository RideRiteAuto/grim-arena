#!/usr/bin/env python3
"""Patch 84.910: unpack the relay's new batched combat/theatre event message.

Tier 2 item #2 (claude/TIER2-NETWORKING-EDITOR-PLAN.md): relay-worker.js's
advance() used to send every combat/boss/projectile event from a single sim
step as its own ws.send() (this patch's sibling edit, made directly since
relay-worker.js is a real top-level file, not part of this embedded
bundle). During any multi-monster fight, event count directly multiplied
send calls -- the same shape of problem nsnap already solved for NPC
position snapshots by batching into one array per tick.

The server now sends one { t:'evb', at, e:[...] } message per tick instead,
where every entry in `e` is exactly the same event object it would have
sent standalone before (an 'atk', 'boss', 'proj', or regen 'nhp'). This is
a real protocol change: an old client reading a server already batching
would see nothing (evb falls to `default` and is silently dropped by
onWorldData, since evb isn't a relay-truth type it recognizes), so both
sides ship in the same commit.

The unpack itself deliberately does not duplicate any per-type handling:
onRelay(m) is a plain dispatch on m.t with no per-call state beyond m
itself, so recursing onRelay(e) for each unpacked event runs the exact
same onAttackEvent/onBossEvent/onProjEvent/onNpcHp code path an unbatched
message would have, just arriving inside one JSON payload instead of many.

Verify: relay-worker.js's own change was exercised via harness/relay-bot.js
against a local wrangler dev relay (manifest + nreg + a boss npc queued
into combat range), confirming a single 'evb' message arrives carrying
multiple atk/boss events per tick instead of one message each. This
client-side unpack was verified by feeding a synthetic evb payload
(several atk/boss/proj/nhp entries) through onRelay() in a headless
harness client and confirming each fired its normal handler exactly once,
same as calling onRelay() on each event individually would have.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """      case 's': if (m._p !== this.netId) this.updateRemote(m._p, m); return;
      default: this.onWorldData(m._p || 'HOST', m); return;"""

NEW = """      case 's': if (m._p !== this.netId) this.updateRemote(m._p, m); return;
      // Tier 2 item #2 (patch 84.910, matching edit in relay-worker.js's
      // advance()): a tick's worth of combat/boss/projectile events arrives
      // batched in one message instead of one ws.send() per event. Each
      // entry is exactly the standalone shape onRelay already knows how to
      // handle (atk/boss/proj/nhp), so recursing here reuses every existing
      // handler unchanged rather than duplicating any of their logic.
      case 'evb': (m.e || []).forEach(e => this.onRelay(e)); return;
      default: this.onWorldData(m._p || 'HOST', m); return;"""

count = s.count(OLD)
assert count == 1, 'patch 84.910: anchor found %d times, wanted 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
print('84.910_batched_combat_events: edited /tmp/game-src.html')
