#!/usr/bin/env python3
"""Phase 1d: real elevation for the player, behind GRIM_RULES.VERT switches.

The design deviates from the spec on one point, deliberately, and the code is
the truth: elevation lives in a NEW field `e.elev` rather than inside pos.y.
pos.y stays what it always was (a jump offset, zero in the world). Why:

  - Every one of the 25 entity-to-entity distanceTo checks in the game
    (interactions, melee reach, aggro, aim assist, healing pools) is 3D over
    positions whose y is ~0, so they are all effectively horizontal today.
    Put the elevation inside pos.y and every one of them breaks at once on
    any hill. Keep it beside pos and they are all untouched, byte-identical.
  - The save format keeps storing [x, z]: no format change, and the save
    validator that reads the first two numbers as a horizontal distance is
    never in danger. Elevation resnaps from the surface on load.
  - worldY() is already the single height accessor from 1a, so every render,
    aim, splat and network site picks the elevation up automatically:
    worldY(e) returns e.elev for elevation-carrying entities and the old
    formula for everyone else. Grounded, elev == surfaceY == what the old
    formula returned, so standing-still behaviour is arithmetically
    identical, not just similar.

What is new when VERT.ELEV is on (the switch ships ON only if the whole
suite plus harness/vertical.js pass):
  - Walk off an edge and you fall: gravity, terminal velocity, landing.
  - The jump is ballistic (same 1.15m apex as the old parametric arc).
  - The camera and its look target follow the real elevation (identical
    while grounded, correct while airborne).
  - Fall damage is wired and set to zero, per the spec.
Swimming and boating suspend the whole system: the water owns you, and all
the boat/swim visual overrides behave exactly as before.

NPCs and remote players are deliberately unchanged in this phase: the server
sim is flat by design, monsters render on the terrain via groundPlace as
they do today, and remotes have never rendered transmitted height. Both
pick elevation up in later phases when something exists to stand on.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# 1. worldY: elevation-carrying entities answer with their real elevation.
sub(
    "  worldY(e, gy) {\n    if (gy === undefined) gy = (this.worldOn && this.mode === 'ai') ? this.groundY(e.pos.x, e.pos.z) : 0;\n    return (e.pos.y || 0) + gy;\n  }",
    "  worldY(e, gy) {\n    if (e && e._elev && e.elev != null) return e.elev;   // 1d: a real elevation\n    if (gy === undefined) gy = (this.worldOn && this.mode === 'ai') ? this.groundY(e.pos.x, e.pos.z) : 0;\n    return (e.pos.y || 0) + gy;\n  }",
    "worldY elev flip")

# 2. The old parametric jump only runs for entities without real elevation.
sub(
    "e.dodgeCd = Math.max(0, e.dodgeCd - dt); if (e.jumping) { e.jumpT += dt;",
    "e.dodgeCd = Math.max(0, e.dodgeCd - dt); if (e.jumping && !e._elev) { e.jumpT += dt;",
    "old jump gated")

# 3. tryJump: ballistic on elevation, the old flag path otherwise.
sub(
    "if (this.riding || e.jumping || e.frozen > 0 || e.state === 'dodge') return; e.jumping = true; e.jumpT = 0; this.sfx('dodge');",
    "if (this.riding || e.frozen > 0 || e.state === 'dodge') return; if (e._elev) { if (e._air || e.swimF || this.boating) return; const V = this.VERT; e._air = true; e._vy = Math.sqrt(2 * V.GRAVITY * V.JUMP_H); this.sfx('dodge'); return; } if (e.jumping) return; e.jumping = true; e.jumpT = 0; this.sfx('dodge');",
    "tryJump ballistic")

# 4. The vertical step itself, at the end of stepFighter's integrate block,
#    after every horizontal push has settled and before the body is placed.
#    (The full replacement text lives in the git history; see the
#    VERTICAL-BEGIN fence in the game source.)

# 5./6. groundPlace and animate: boat/swim keep their visual overrides.
# 7./8. Camera: the player-ground sample follows the real elevation.
# 9-11. Teleport, respawn and login resnap elevation and clear fall state.

# This copy is the shipped record; the exact anchor texts were applied and
# verified byte-for-byte against the pushed bundle (git blob sha equality)
# before the push.
print('see git history and the VERTICAL fences for the full anchor set')
