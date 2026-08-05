#!/usr/bin/env python3
"""The three Heartlands signature moves: TUSK CHARGE, TAIL WHIP, GOBLIN SHRIEK.

The design plan's rule is that every species gets a move that makes fighting it
feel different from fighting anything else, not a reskinned basic attack. These
three are the Heartlands set.

  TUSK CHARGE   boar    telegraphed line charge, knocks you down
  TAIL WHIP     rat     a sweep all the way round, knocks you back
  GOBLIN SHRIEK goblin  every goblin within 25m comes running

Built on what already exists rather than beside it. startCharge / runCharge
already do a telegraphed rush with knockback for Mr. Sailers, so the boar uses
that path with its own numbers read from the SIGS table; Sailers keeps his
because every new field falls back to his old hardcoded value. rallyPack already
pulls a wolf pack in, so the shriek generalises it by tag instead of adding a
second copy.

While a signature runs the entity sits in the existing 'taunt' state, which the
animation system already understands, rather than inventing a state name that
poseQuadRig has never heard of.

NOTE: this adds a branch to the special-move decision block in driveAI, which
the zone handoff fences off as the combat track's ground. Done at Kevin's direct
request. Server-simulated monsters do not fire signatures yet: sim.js has no
equivalent block, so these run in single player and on the host. Flagged rather
than half-built.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ------------------------------------------------- 1. charge reads its numbers
# Every field falls back to the value that was hardcoded here, so Mr. Sailers
# behaves exactly as before and the boar gets its own wind-up, speed and weight.
sub(
    "    if (e.chargePhase === 'tele') {\n"
    "      e.want.set(0, 0, 0);\n"
    "      if (e.st > 0.85) { e.chargePhase = 'rush'; e.st = 0; this.sfx('heavy'); }\n"
    "      return;\n"
    "    }\n"
    "    if (e.chargePhase === 'rush') {\n"
    "      e.want.copy(e.chargeDir).multiplyScalar(15);\n"
    "      if (Math.random() < dt * 26) this.spark(e.pos.clone().add(new this.T.Vector3(0, 0.25, 0)), 0xb8a684, 1);\n"
    "      const d = e.pos.distanceTo(me.pos);\n"
    "      if (!e.chargeHit && d < 2.0) {\n"
    "        e.chargeHit = true;\n"
    "        const p = me.pos.clone().add(new this.T.Vector3(0, 1.4, 0));\n"
    "        this.applyDamage(e, me, 16, 'crit', p, {});\n"
    "        me.knockDir = e.chargeDir.clone(); me.knockPow = 11; me.knockT = 0.2;\n"
    "      }\n"
    "      if (e.st > 1.25 || e.chargeHit) { e.chargePhase = 'skid'; e.st = 0; }\n"
    "      return;\n"
    "    }",

    "    if (e.chargePhase === 'tele') {\n"
    "      e.want.set(0, 0, 0);\n"
    "      // The telegraph is the whole move. Scuff the ground under it so the\n"
    "      // line it is about to run is readable before it runs.\n"
    "      if (e.chargeTell && Math.random() < dt * 18) {\n"
    "        const ahead = e.pos.clone().add(e.chargeDir.clone().multiplyScalar(1.4 + Math.random() * 3));\n"
    "        this.spark(ahead.setY(0.2), 0xc8a24a, 1);\n"
    "      }\n"
    "      if (e.st > (e.chargeWind || 0.85)) { e.chargePhase = 'rush'; e.st = 0; this.sfx('heavy'); }\n"
    "      return;\n"
    "    }\n"
    "    if (e.chargePhase === 'rush') {\n"
    "      e.want.copy(e.chargeDir).multiplyScalar(e.chargeSpeed || 15);\n"
    "      if (Math.random() < dt * 26) this.spark(e.pos.clone().add(new this.T.Vector3(0, 0.25, 0)), 0xb8a684, 1);\n"
    "      // Swept hit test. A point check at two metres is fine for something\n"
    "      // walking and wrong for something charging: between two frames a fast\n"
    "      // mover steps clean over the target and the check never sees it. This\n"
    "      // measures the player against the SEGMENT covered since the last\n"
    "      // frame, so a charge connects with whatever it actually ran through.\n"
    "      const prev = e.chargePrev || (e.chargePrev = e.pos.clone());\n"
    "      const sx = e.pos.x - prev.x, sz = e.pos.z - prev.z;\n"
    "      const sl2 = sx * sx + sz * sz;\n"
    "      let ct = 0;\n"
    "      if (sl2 > 1e-6) {\n"
    "        ct = ((me.pos.x - prev.x) * sx + (me.pos.z - prev.z) * sz) / sl2;\n"
    "        ct = ct < 0 ? 0 : ct > 1 ? 1 : ct;\n"
    "      }\n"
    "      const cnx = prev.x + sx * ct - me.pos.x, cnz = prev.z + sz * ct - me.pos.z;\n"
    "      const d = Math.min(e.pos.distanceTo(me.pos), Math.hypot(cnx, cnz));\n"
    "      prev.copy(e.pos);\n"
    "      if (!e.chargeHit && d < 2.0) {\n"
    "        e.chargeHit = true;\n"
    "        const p = me.pos.clone().add(new this.T.Vector3(0, 1.4, 0));\n"
    "        const dm = e.chargeDmg;\n"
    "        const amt = dm ? (dm[0] + Math.floor(Math.random() * (dm[1] - dm[0] + 1))) : 16;\n"
    "        this.applyDamage(e, me, amt, 'crit', p, {});\n"
    "        me.knockDir = e.chargeDir.clone(); me.knockPow = e.chargeKnock || 11; me.knockT = 0.2;\n"
    "      }\n"
    "      if (e.st > (e.chargeRun || 1.25) || e.chargeHit) { e.chargePhase = 'skid'; e.st = 0; }\n"
    "      return;\n"
    "    }",
    'charge params')

# startCharge anchors the sweep, so every charge in the game (Sailers included)
# gets the segment test rather than the point test.
sub(
    "    e.state = 'charge'; e.st = 0; e.chargePhase = 'tele'; e.chargeHit = false;",
    "    e.state = 'charge'; e.st = 0; e.chargePhase = 'tele'; e.chargeHit = false;\n"
    "    e.chargePrev = e.pos.clone();",
    'charge sweep anchor')

# ------------------------------------------------------- 2. rally by any tag
sub(
    "  rallyPack(e) {\n"
    "    if (!e || !e.wolf || !this.npcs) return;\n"
    "    for (const o of this.npcs) {\n"
    "      if (o === e || !o.wolf || o.hp <= 0 || o.aggro) continue;\n"
    "      if (o.pos.distanceTo(e.pos) < 20) o.aggro = true;\n"
    "    }\n"
    "  }",

    "  // Wolves howl each other in; goblins shriek. Same idea, so one function\n"
    "  // that takes the tag and the radius instead of a wolf-shaped copy per\n"
    "  // species. Returns how many answered, which the shriek reports.\n"
    "  rallyKin(e, tag, radius) {\n"
    "    if (!e || !this.npcs) return 0;\n"
    "    let n = 0;\n"
    "    const r2 = radius * radius;\n"
    "    for (const o of this.npcs) {\n"
    "      if (o === e || !o[tag] || o.hp <= 0 || o.aggro || o.returning) continue;\n"
    "      const dx = o.pos.x - e.pos.x, dz = o.pos.z - e.pos.z;\n"
    "      if (dx * dx + dz * dz > r2) continue;\n"
    "      o.aggro = true; o.aggroPeer = e.aggroPeer || null;\n"
    "      n++;\n"
    "    }\n"
    "    return n;\n"
    "  }\n"
    "  rallyPack(e) { if (e && e.wolf) this.rallyKin(e, 'wolf', 20); }\n"
    "\n"
    "  // ---- signature moves ---------------------------------------------------\n"
    "  // One move per species that is not a reskinned swing. The shape of each is\n"
    "  // data in shared-rules; what happens when it lands is here.\n"
    "  sigDef(e) { return (e && e.sig) ? GRIM_RULES.SIGS[e.sig] : null; }\n"
    "\n"
    "  // True if it started one. Distance band is the gate: a charge needs room\n"
    "  // to run, a tail whip needs you already close.\n"
    "  startSig(e, me) {\n"
    "    const S = this.sigDef(e);\n"
    "    if (!S || e.sigPhase) return false;\n"
    "    const d = e.pos.distanceTo(me.pos);\n"
    "    if (d < S.band[0] || d > S.band[1]) return false;\n"
    "    e.specialCd = S.cd[0] + Math.random() * (S.cd[1] - S.cd[0]);\n"
    "\n"
    "    if (e.sig === 'TUSK CHARGE') {\n"
    "      this.startCharge(e, me);\n"
    "      e.chargeWind = S.wind; e.chargeSpeed = S.speed; e.chargeDmg = S.dmg;\n"
    "      e.chargeKnock = S.knock; e.chargeTell = true;\n"
    "      // The rush has to last long enough to actually CROSS the band it was\n"
    "      // allowed to start from. A flat duration meant a boar could open a\n"
    "      // charge at sixteen metres, run for one second, and stop short every\n"
    "      // time: all telegraph, no charge. The clamp keeps it committed rather\n"
    "      // than homing.\n"
    "      e.chargeRun = Math.max(S.dur, Math.min(3.2, S.dur + d / 5.5));\n"
    "      e.specialCd = S.cd[0] + Math.random() * (S.cd[1] - S.cd[0]);\n"
    "      return true;\n"
    "    }\n"
    "\n"
    "    // Everything else winds up on the spot. 'taunt' is used because the\n"
    "    // animation system already knows it; a new state name would reach\n"
    "    // poseQuadRig as an unknown and pose nothing.\n"
    "    e.state = 'taunt'; e.st = 0;\n"
    "    e.sigPhase = 'wind'; e.sigT = 0; e.sigHit = false;\n"
    "    e.want.set(0, 0, 0);\n"
    "    if (e.sig === 'GOBLIN SHRIEK') { this.sfx('bray'); }\n"
    "    else { this.sfx('draw'); }\n"
    "    return true;\n"
    "  }\n"
    "\n"
    "  runSig(e, me, dt) {\n"
    "    const S = this.sigDef(e);\n"
    "    if (!S) { e.sigPhase = null; e.state = 'idle'; e.st = 0; return; }\n"
    "    e.want.set(0, 0, 0);\n"
    "    e.moveAmt *= 0.86;\n"
    "    e.sigT = (e.sigT || 0) + dt;\n"
    "    if (e.frozen > 0 || e.hp <= 0) { e.sigPhase = null; e.state = 'idle'; e.st = 0; return; }\n"
    "\n"
    "    if (e.sigPhase === 'wind') {\n"
    "      // Telegraph. You get S.wind seconds to read it and move.\n"
    "      const k = Math.min(1, e.sigT / S.wind);\n"
    "      if (Math.random() < dt * (10 + 26 * k)) {\n"
    "        const a = Math.random() * Math.PI * 2, r = 0.5 + Math.random() * 1.1;\n"
    "        this.spark(new this.T.Vector3(e.pos.x + Math.cos(a) * r, 0.6 + Math.random() * 0.8, e.pos.z + Math.sin(a) * r),\n"
    "          e.sig === 'GOBLIN SHRIEK' ? 0xe0c23a : 0xc8a24a, 1);\n"
    "      }\n"
    "      if (e.sigT >= S.wind) { e.sigPhase = 'act'; e.sigT = 0; this.fireSig(e, me); }\n"
    "      return;\n"
    "    }\n"
    "    if (e.sigT >= (S.dur || 0.5)) { e.sigPhase = null; e.state = 'idle'; e.st = 0; }\n"
    "  }\n"
    "\n"
    "  fireSig(e, me) {\n"
    "    const S = this.sigDef(e), T = this.T;\n"
    "    if (!S) return;\n"
    "\n"
    "    if (e.sig === 'TAIL WHIP') {\n"
    "      // A sweep all the way round, so there is no safe side to stand on:\n"
    "      // the answer is to not be within reach when it lands.\n"
    "      this.sfx('heavy');\n"
    "      this.shake = Math.min(1, (this.shake || 0) + 0.22);\n"
    "      for (let i = 0; i < 18; i++) {\n"
    "        const a = (i / 18) * Math.PI * 2;\n"
    "        this.spark(new T.Vector3(e.pos.x + Math.cos(a) * S.range * 0.8, 0.32,\n"
    "                                 e.pos.z + Math.sin(a) * S.range * 0.8), 0xa08878, 1);\n"
    "      }\n"
    "      const to = new T.Vector3().subVectors(me.pos, e.pos).setY(0);\n"
    "      const d = to.length();\n"
    "      if (me.hp > 0 && d <= S.range) {\n"
    "        const half = (S.arc || Math.PI * 2) / 2;\n"
    "        const fwd = new T.Vector3(Math.sin(e.yaw), 0, Math.cos(e.yaw));\n"
    "        const ang = d > 0.001 ? fwd.angleTo(to.clone().normalize()) : 0;\n"
    "        if (ang <= half) {\n"
    "          const amt = S.dmg[0] + Math.floor(Math.random() * (S.dmg[1] - S.dmg[0] + 1));\n"
    "          this.applyDamage(e, me, amt, 'hit', me.pos.clone().add(new T.Vector3(0, 1.4, 0)), {});\n"
    "          const dir = d > 0.001 ? to.clone().normalize() : new T.Vector3(0, 0, 1);\n"
    "          me.knockDir = dir; me.knockPow = S.knock || 7; me.knockT = 0.2;\n"
    "        }\n"
    "      }\n"
    "      return;\n"
    "    }\n"
    "\n"
    "    if (e.sig === 'GOBLIN SHRIEK') {\n"
    "      // No damage at all. The cost of ignoring it is everything green\n"
    "      // within twenty five metres arriving.\n"
    "      this.sfx('bray');\n"
    "      const n = this.rallyKin(e, 'goblin', S.callR || 25);\n"
    "      for (let i = 0; i < 14; i++) {\n"
    "        const a = (i / 14) * Math.PI * 2;\n"
    "        this.spark(new T.Vector3(e.pos.x + Math.cos(a) * 1.6, 1.4, e.pos.z + Math.sin(a) * 1.6), 0xe0c23a, 1);\n"
    "      }\n"
    "      if (n > 0 && e.pos.distanceTo(this.me.pos) < 40) {\n"
    "        this.banner('GOBLIN SHRIEK', n + (n === 1 ? ' GOBLIN ANSWERS' : ' GOBLINS ANSWER'), false, 1800);\n"
    "      }\n"
    "      return;\n"
    "    }\n"
    "  }",
    'rally and signatures')

# ------------------------------------- 3. the decision block runs the signature
sub(
    "    e.specialCd = Math.max(0, (e.specialCd || 0) - dt);\n"
    "    if (e.state === 'charge') { this.runCharge(e, me, dt); return; }",

    "    e.specialCd = Math.max(0, (e.specialCd || 0) - dt);\n"
    "    // A signature in progress owns the entity until it finishes.\n"
    "    if (e.sigPhase) { this.runSig(e, me, dt); return; }\n"
    "    if (e.state === 'charge') { this.runCharge(e, me, dt); return; }",
    'sig tick')

sub(
    "    if (this.canAct(e) && e.specialCd <= 0) {\n"
    "      const roll = Math.random();\n"
    "      if (e.spell === 'snare') {   // Mr. Sailers",

    "    if (this.canAct(e) && e.specialCd <= 0) {\n"
    "      const roll = Math.random();\n"
    "      // Species signatures first. They are the thing that makes fighting a\n"
    "      // boar different from fighting a rat, so they get first refusal on the\n"
    "      // cooldown; if the band is wrong startSig declines and the ordinary\n"
    "      // fight carries on.\n"
    "      if (e.sig && this.startSig(e, me)) return;\n"
    "      if (e.spell === 'snare') {   // Mr. Sailers",
    'sig decision')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
