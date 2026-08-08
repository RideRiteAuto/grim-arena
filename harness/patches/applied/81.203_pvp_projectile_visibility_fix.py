#!/usr/bin/env python3
"""Patch 81.203: fixes a wrong anchor in 80.142 (pvp projectile visibility).

Boot-testing 80.142 caught a real bug before it shipped: the fake-caster
block it extended (the one that turns a network 'proj' message into a real
fireFrost/fireSnare/fireToxin/fireArrow call, so a remote cast renders with
the actual high-quality kit) does not live in onWorldData() as I'd assumed
from an earlier read. It lives in handleNet() - the OLD duel/coop dispatcher,
wired only to the direct WebRTC channel (ctlConn/stateConn) and the legacy
`?room=` websocket. Two consequences, both confirmed with a live boot test
against the built bundle:

1. handleNet() opens with `if (this.mode !== 'net' && !this.coop) return;` -
   a guard that makes the ENTIRE function a no-op outside old-duel/coop mode.
   Relay-mode open-world play (this.mode === 'ai', this.coop false) never
   gets past that line, so my 80.142 edit to handleNet's fake-caster
   condition never ran for the case it was meant for.
2. handleNet(m) only takes `m` - there is no `from` in scope. The condition
   80.142 wrote, `m.t === 'pproj' && from !== this.netId`, references an
   undefined identifier. It happened not to throw only because guard #1
   already returned first every time this was tested - a real
   ReferenceError was one dead-code path away from shipping.

The actual receiver for anything onRelay() forwards in relay mode is
onWorldData(from, m) - it DOES have `from`, and it's what onRelay()'s
'pproj' case (and its default case, for every other message type not
explicitly switched on) already calls. This patch:

1. Reverts the handleNet() condition to exactly what it was before 80.142
   (plain `m.t === 'proj' && this.coop`) - handleNet was correct already;
   80.142 should never have touched it.
2. Adds the fake-caster block - functionally identical to the one in
   handleNet, just using `from` (onWorldData's real sender parameter)
   instead of a bare, undefined identifier - to the END of onWorldData(),
   right before its closing brace, guarded on `m.t === 'pproj' && from !==
   this.netId` (the self-echo guard stays; the relay's own broadcast()
   already excludes the sender, so this is defense in depth, not load
   bearing).

Verified against a fresh boot: onRelay('pproj') -> onWorldData() now spawns
the real kit-built cosmetic projectile for frost, fire, snare, toxin and
arrow, a self-authored echo is ignored, and handleNet() no longer carries
the broken reference. See harness/pvp-visibility-test.js.

Re-grep anchors fresh before reusing this number.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# 1. Revert handleNet()'s condition - it should never have been touched.
# ---------------------------------------------------------------------------
BROKEN_HANDLENET = "    if ((m.t === 'proj' && this.coop) || (m.t === 'pproj' && from !== this.netId)) {\n      const fake = { pos: new this.T.Vector3(m.p[0], 0, m.p[2]), yaw: Math.atan2(m.v[0], m.v[2]), cosmetic: true };\n      if (m.k === 'frost' || m.k === 'fire') { fake.elem = m.k === 'fire' ? 'fire' : 'water'; this.fireFrost(fake); }\n      else if (m.k === 'snare') this.fireSnare(fake);\n      else if (m.k === 'toxin') this.fireToxin(fake);\n      else this.fireArrow(fake, 0, 1, 0);\n      const pr = this.projectiles[this.projectiles.length - 1];\n      if (pr) { pr.mesh.position.set(m.p[0], m.p[1], m.p[2]); pr.vel.set(m.v[0], m.v[1], m.v[2]); pr.dmg = 0; pr.owner = fake; }\n    }\n  }\n\n  startCoop(oppName, oppColor) {"
assert s.count(BROKEN_HANDLENET) == 1, 'handleNet fake-caster anchor matched %d times' % s.count(BROKEN_HANDLENET)
FIXED_HANDLENET = BROKEN_HANDLENET.replace(
    "if ((m.t === 'proj' && this.coop) || (m.t === 'pproj' && from !== this.netId)) {",
    "if (m.t === 'proj' && this.coop) {"
)
s = s.replace(BROKEN_HANDLENET, FIXED_HANDLENET)

# ---------------------------------------------------------------------------
# 2. Add the real handler to onWorldData(), which actually has `from`.
# ---------------------------------------------------------------------------
OWD_TAIL = "    if (m.t === 'rdead' && !this.isWorldHost) { const nd = GRIM_RULES.GATHER.NODES[m.k] || GRIM_RULES.GATHER.NODES.tree; this.grantItem(nd.yield[0], nd.yield[1]); this.awardXp(nd.skill, nd.xp); this.sfx(nd.skill === 'MINING' ? 'break' : 'timber'); return; } }"
assert s.count(OWD_TAIL) == 1, 'onWorldData tail anchor matched %d times' % s.count(OWD_TAIL)
OWD_NEW_TAIL = """    if (m.t === 'rdead' && !this.isWorldHost) { const nd = GRIM_RULES.GATHER.NODES[m.k] || GRIM_RULES.GATHER.NODES.tree; this.grantItem(nd.yield[0], nd.yield[1]); this.awardXp(nd.skill, nd.xp); this.sfx(nd.skill === 'MINING' ? 'break' : 'timber'); return; }
    // Patch 80.142/81.203: someone else's spell cast or shot, mirrored to
    // everyone in the open world/PvP over the relay (coopProj() sends this
    // only for a===this.me). Same fake-caster trick handleNet() already
    // used for the coop duel path, just with a real sender id to guard the
    // self-echo (the relay's own broadcast() already excludes the sender -
    // this is a second, cheap line of defense, not load bearing).
    if (m.t === 'pproj' && from !== this.netId) {
      const fake = { pos: new this.T.Vector3(m.p[0], 0, m.p[2]), yaw: Math.atan2(m.v[0], m.v[2]), cosmetic: true };
      if (m.k === 'frost' || m.k === 'fire') { fake.elem = m.k === 'fire' ? 'fire' : 'water'; this.fireFrost(fake); }
      else if (m.k === 'snare') this.fireSnare(fake);
      else if (m.k === 'toxin') this.fireToxin(fake);
      else this.fireArrow(fake, 0, 1, 0);
      const pr = this.projectiles[this.projectiles.length - 1];
      if (pr) { pr.mesh.position.set(m.p[0], m.p[1], m.p[2]); pr.vel.set(m.v[0], m.v[1], m.v[2]); pr.dmg = 0; pr.owner = fake; }
    }
  }"""
s = s.replace(OWD_TAIL, OWD_NEW_TAIL)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 81.203 applied: pproj now handled in onWorldData (from), handleNet reverted')
