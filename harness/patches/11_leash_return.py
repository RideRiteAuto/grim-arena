#!/usr/bin/env python3
"""Monsters break off cleanly and walk home instead of shaking at leash range.

The bug, exactly: leashing was a distance test with no state behind it.

    if (e.aggro && (safe || leashed)) { e.aggro = false; wander(); return; }
    if (!e.aggro) {
      if (dp < e.aggroR && !safe) { e.aggro = true; this.sfx('tick'); }
    }

Hold a monster at leash range and stand next to it and those two branches take
turns every frame: drop aggro, turn home, re-acquire the player, turn back, drop
aggro. That is the shake, and because the re-acquire plays the aggro sound it is
also a click track at frame rate.

Breaking off is now a STATE with a destination, the way RuneScape and WoW both
do it, for exactly this reason. On leash a monster sets `returning`, walks to its
home point at a slightly increased pace, CANNOT be re-aggroed on the way, and
heals on arrival so it cannot be worn down by dragging it to the edge of its
ground over and over.

Chase distance is now per creature: a monster follows CHASE_EXTRA metres past
its own roam radius, capped by LEASH_R. A camp of goblins guards a spot, a boar
owns a field.

NOTE: this edits the aggro gate inside driveAI, which the zone handoff fences
off as the combat track's ground. Kevin asked for it directly. The matching
change is in sim.js so the server behaves the same; if the two ever disagree
about who is aggro'd, monsters teleport on the client.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ---------------------------------------------------- 1. the aggro / leash gate
sub(
    "      const leashed   = e.home && Math.hypot(e.pos.x - e.home.x, e.pos.z - e.home.z) > 46;\n"
    "      const safe = meInTown || npcInTown || meAtCamp;\n"
    "      if (e.aggro && (safe || leashed)) {\n"
    "        e.aggro = false; e.aggroPeer = null; e.way = null; e.wayT = 0;\n"
    "        this.wander(e, dt); return;\n"
    "      }\n"
    "      if (!e.aggro) {\n"
    "        if (dp < (e.aggroR ?? 10) && !safe) { e.aggro = true; this.sfx('tick'); this.rallyPack(e); }\n"
    "        else { this.wander(e, dt); return; }\n"
    "      } else if (dp > 32) { e.aggro = false; this.wander(e, dt); return; }",

    "      const L = GRIM_RULES.LEASH;\n"
    "      // How far this one will follow: its own ground plus a fixed overrun,\n"
    "      // never past the world ceiling.\n"
    "      const chaseR = Math.min(GRIM_RULES.LEASH_R, this.roamRadius(e) + L.CHASE_EXTRA);\n"
    "      const fromHome = e.home ? Math.hypot(e.pos.x - e.home.x, e.pos.z - e.home.z) : 0;\n"
    "      const leashed = e.home && fromHome > chaseR;\n"
    "      const safe = meInTown || npcInTown || meAtCamp;\n"
    "\n"
    "      // Already walking home. Nothing interrupts this, which is the whole\n"
    "      // point: the old code let the player re-acquire it on the very next\n"
    "      // frame, so it shook on the spot and retriggered its aggro sound.\n"
    "      if (e.returning) {\n"
    "        if (!e.home || fromHome <= L.HOME_TOL) {\n"
    "          e.returning = false;\n"
    "          e.way = null; e.wayT = 0;\n"
    "          // healed on arrival, so a monster cannot be ground down by being\n"
    "          // pulled to the edge of its ground again and again\n"
    "          if (L.HEAL_ON_RETURN && e.hp > 0 && e.max) e.hp = e.max;\n"
    "        } else {\n"
    "          this.walkHome(e, dt);\n"
    "          return;\n"
    "        }\n"
    "      }\n"
    "\n"
    "      if (e.aggro && (safe || leashed)) {\n"
    "        e.aggro = false; e.aggroPeer = null; e.way = null; e.wayT = 0;\n"
    "        // A monster that hit its leash goes home. One that broke off because\n"
    "        // you stepped into town just carries on wandering where it stands.\n"
    "        if (leashed && e.home) { e.returning = true; this.walkHome(e, dt); return; }\n"
    "        this.wander(e, dt); return;\n"
    "      }\n"
    "      if (!e.aggro) {\n"
    "        // Do not pick a new fight from outside your own ground either: a\n"
    "        // monster standing at the edge of its patch should not lunge at\n"
    "        // someone one step beyond it.\n"
    "        if (dp < (e.aggroR ?? 10) && !safe && !leashed) {\n"
    "          e.aggro = true;\n"
    "          const now = this.worldT || 0;\n"
    "          if (now - (e._aggroSfxAt || -99) > L.MIN_AGGRO_GAP) { e._aggroSfxAt = now; this.sfx('tick'); }\n"
    "          this.rallyPack(e);\n"
    "        } else { this.wander(e, dt); return; }\n"
    "      } else if (dp > GRIM_RULES.DEAGGRO_R) {\n"
    "        e.aggro = false;\n"
    "        if (e.home && fromHome > this.roamRadius(e)) { e.returning = true; this.walkHome(e, dt); return; }\n"
    "        this.wander(e, dt); return;\n"
    "      }",
    'aggro gate')

# --------------------------------------------------- 2. roam radius + walk home
sub(
    "  wander(e, dt) {\n"
    "    const T = this.T;",

    "  // How much ground this creature calls its own. Species first, then the\n"
    "  // role defaults, so everything that predates the bestiary table still gets\n"
    "  // a sensible patch instead of one blanket number.\n"
    "  roamRadius(e) {\n"
    "    if (e._roamR != null) return e._roamR;\n"
    "    const R = GRIM_RULES.ROAM_R;\n"
    "    let r = e.homeR;\n"
    "    if (r == null && e.zoneSpecies) {\n"
    "      const B = GRIM_RULES.BESTIARY[e.zoneSpecies];\n"
    "      if (B && B.roamR != null) r = B.roamR;\n"
    "    }\n"
    "    if (r == null) {\n"
    "      r = e.civilian ? R.civilian\n"
    "        : e.worker ? R.worker\n"
    "        : (e.king || e.rat || e.warden || e.captain) ? R.boss\n"
    "        : (e.passive || e.skittish) ? R.wildlife\n"
    "        : e.beast ? R.beast\n"
    "        : R.camp;\n"
    "    }\n"
    "    e._roamR = r;\n"
    "    return r;\n"
    "  }\n"
    "\n"
    "  // The walk back. Straight at the home point, a little quicker than an idle\n"
    "  // wander, no wandering off on the way.\n"
    "  walkHome(e, dt) {\n"
    "    const T = this.T;\n"
    "    if (!e.home) { this.wander(e, dt); return; }\n"
    "    const dir = new T.Vector3().subVectors(e.home, e.pos).setY(0);\n"
    "    const d = dir.length();\n"
    "    if (d < 0.6) { e.want.set(0, 0, 0); e.moveAmt *= 0.85; return; }\n"
    "    dir.normalize();\n"
    "    e.yaw = Math.atan2(dir.x, dir.z);\n"
    "    const sp = 2.3 * GRIM_RULES.LEASH.RETURN_SPEED;\n"
    "    e.want.set(dir.x * sp, 0, dir.z * sp);\n"
    "    e.moveAmt += (0.6 - e.moveAmt) * Math.min(1, dt * 6);\n"
    "  }\n"
    "\n"
    "  wander(e, dt) {\n"
    "    const T = this.T;",
    'roam radius and walk home')

# Wandering used one blanket 5 to 16 metre radius for every creature in the
# world, which is why a boar and a townsfolk covered the same ground.
sub(
    "      const a = Math.random() * Math.PI * 2;\n"
    "      const r = e.name === 'MR. SAILERS' ? 14 + Math.random() * 22 : 5 + Math.random() * 11;",
    "      const a = Math.random() * Math.PI * 2;\n"
    "      const rr0 = this.roamRadius(e);\n"
    "      const r = e.name === 'MR. SAILERS' ? 14 + Math.random() * 22 : rr0 * (0.35 + Math.random() * 0.65);",
    'wander radius')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
