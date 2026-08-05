#!/usr/bin/env python3
"""The client reads signature damage out of MOVES, like everything else.

The first pass at signatures kept their damage, reach and knockback inside SIGS
and applied them with bespoke client code. That works in single player and
cannot work at all on the server, because the server does not apply damage: it
announces a swing BY NAME and each client judges its own dodge against the shape
it finds under that name in MOVES.

So the shapes moved into MOVES (`whip`, `tusk`) and SIGS now points at them.
This makes the client read them from there too, so there is one set of numbers
and the two sides cannot drift.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# The shape a signature hits with, or null for the ones that do no damage.
sub(
    "  sigDef(e) { return (e && e.sig) ? GRIM_RULES.SIGS[e.sig] : null; }",
    "  sigDef(e) { return (e && e.sig) ? GRIM_RULES.SIGS[e.sig] : null; }\n"
    "  // The contact shape a signature hits with, straight out of the same MOVES\n"
    "  // table the server announces swings from. Null for the ones that do no\n"
    "  // damage at all, which is only the shriek.\n"
    "  sigShape(S) { return (S && S.move) ? GRIM_RULES.MOVES[S.move] : null; }",
    'sigShape')

sub(
    "      e.chargeWind = S.wind; e.chargeSpeed = S.speed; e.chargeDmg = S.dmg;\n"
    "      e.chargeKnock = S.knock; e.chargeTell = true;",
    "      const MS = this.sigShape(S) || {};\n"
    "      e.chargeWind = S.wind; e.chargeSpeed = S.speed; e.chargeDmg = MS.dmg;\n"
    "      e.chargeKnock = MS.knock; e.chargeTell = true;",
    'charge shape')

sub(
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
    "      }",

    "      const MS = this.sigShape(S) || { dmg: [7, 11], range: 3.2, arc: Math.PI * 2, knock: 7 };\n"
    "      const to = new T.Vector3().subVectors(me.pos, e.pos).setY(0);\n"
    "      const d = to.length();\n"
    "      if (me.hp > 0 && d <= MS.range) {\n"
    "        const half = (MS.arc || Math.PI * 2) / 2;\n"
    "        const fwd = new T.Vector3(Math.sin(e.yaw), 0, Math.cos(e.yaw));\n"
    "        const ang = d > 0.001 ? fwd.angleTo(to.clone().normalize()) : 0;\n"
    "        if (ang <= half) {\n"
    "          const amt = MS.dmg[0] + Math.floor(Math.random() * (MS.dmg[1] - MS.dmg[0] + 1));\n"
    "          this.applyDamage(e, me, amt, 'hit', me.pos.clone().add(new T.Vector3(0, 1.4, 0)), {});\n"
    "          const dir = d > 0.001 ? to.clone().normalize() : new T.Vector3(0, 0, 1);\n"
    "          me.knockDir = dir; me.knockPow = MS.knock || 7; me.knockT = 0.2;\n"
    "        }\n"
    "      }",
    'whip shape')

# The ring of sparks was drawn at S.range, which no longer exists on SIGS.
sub(
    "      for (let i = 0; i < 18; i++) {\n"
    "        const a = (i / 18) * Math.PI * 2;\n"
    "        this.spark(new T.Vector3(e.pos.x + Math.cos(a) * S.range * 0.8, 0.32,\n"
    "                                 e.pos.z + Math.sin(a) * S.range * 0.8), 0xa08878, 1);\n"
    "      }",
    "      const RNG = (this.sigShape(S) || {}).range || 3.2;\n"
    "      for (let i = 0; i < 18; i++) {\n"
    "        const a = (i / 18) * Math.PI * 2;\n"
    "        this.spark(new T.Vector3(e.pos.x + Math.cos(a) * RNG * 0.8, 0.32,\n"
    "                                 e.pos.z + Math.sin(a) * RNG * 0.8), 0xa08878, 1);\n"
    "      }",
    'whip ring')

# The shriek's tag comes from the table now, so a frost goblin or a kobold camp
# rallies its own kind without another branch here.
sub(
    "      const n = this.rallyKin(e, 'goblin', S.callR || 25);",
    "      const n = this.rallyKin(e, S.tag || 'goblin', S.callR || 25);",
    'shriek tag')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
