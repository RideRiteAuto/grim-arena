#!/usr/bin/env python3
"""Phase 1a: one accessor for an entity's true world height. Zero behaviour change.

Height is computed all over the client as `pos.y + groundY(x, z)`, where pos.y
is a jump offset that is almost always zero. Phase 1d makes pos.y a real
elevation, and at that moment every inline copy of that formula would add the
ground to a number that already contains it, silently. This patch introduces
`worldY(e)`, implemented as exactly the old formula, and routes every site
that composes AN ENTITY'S height through it. Twenty invisible future bugs
become one switch, with every call site verified green before the flip.

Routed (each replacement is arithmetically identical today):
  - groundPlace()   `e.pos.y + gy`             -> worldY(e, gy)
  - animate()       `e.pos.y + eGy`            -> worldY(e, eGy)
  - myWorldState()  network p[1]               -> worldY(me, gy)
  - aimPoint()      candidate centre y          -> worldY(n, gy) + 1.15
  - bodyAnchor()    splat anchor y              -> worldY(e, gy) + h
  - stepRemotes()   remote base placement       -> worldY(e, gy)
  - fireFrost/fireSnare/fireArrow  aim origin and muzzle y
                    `pos.clone().add(0, gy+H, 0)` composes pos.y + gy + H,
                    so it becomes worldY(a, gy) + H, written explicitly
  - fireToxin()     muzzle y                    -> worldY(a, gy) + 1.4
  - npcAimDir originY arguments at those call sites (NPC pos.y is always 0,
                    so worldY(a, gy) + H is byte-identical there too)

Deliberately NOT routed, with reasons, so nobody mistakes these for misses:
  - stepCamera want.y and gyL: a max-blend of ground samples and a look
    target that intentionally ignores the jump offset. Routing would change
    behaviour during jumps. The camera is an explicit 1e rework item.
  - npcAimDir's TARGET height (tgy + 1.4) and stepProjectiles' hitbox
    (gy + 1.1): aim and hitboxes ignoring elevation is the known 1e fix
    "target hitboxes sit at terrain height plus a constant".
  - The dead-slump branches (groundPlace, animate): the slump discards pos.y
    by design today; corpses are a named 1e item.
  - The storm chain bolt anchors (gyA + 1.6 / gy + 1.4): same class as aim,
    1e, and touching combat visuals stays out of a no-op patch.
  - spawnDrop / sackAdd / spawnPool / dressing / town builders / donkeyY /
    onProjEvent: these place things ON THE GROUND, which is a legitimate use
    of groundY itself. They graduate to the surface query in 1b/1d.
  - The debug coord HUD: uses a different guard (bare groundY without the
    worldOn gate) on purpose so screenshots match the map. Left alone.
  - judgeMyDodge and everything in section 5 of the handoff: combat track's
    ground. Untouched.

The optional `gy` parameter on worldY is a perf hint only: the per-frame
loops already hold the ground height, and worldY(e, gy) avoids a second
terrain lookup per entity per frame. Callers that pass a boat or swim
water-line override (groundPlace, animate) keep today's visual behaviour
exactly; 1d revisits those two lines when pos.y becomes real.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# 1. The accessor itself, fenced, directly above groundPlace so the two
#    definitions of "where does an entity sit" live side by side.
sub(
    "  groundPlace(e) {\n    let gy",

    "  /* VERTICAL-BEGIN */\n"
    "  // Phase 1a: the ONE definition of an entity's true world height.\n"
    "  // Returns exactly what the old inline formula did (pos.y is a jump\n"
    "  // offset, ground comes from the terrain lookup), so routing call\n"
    "  // sites through this is a no-op. Phase 1d flips this body to\n"
    "  // `return e.pos.y;` once pos.y becomes a real elevation, and every\n"
    "  // routed site follows in one switch.\n"
    "  // `gy` is an optional precomputed ground height: a perf hint for the\n"
    "  // per-frame loops that already hold it. Two callers (groundPlace,\n"
    "  // animate) pass a boat/swim water-line override through it, which\n"
    "  // preserves today's visuals exactly; 1d revisits those two lines.\n"
    "  worldY(e, gy) {\n"
    "    if (gy === undefined) gy = (this.worldOn && this.mode === 'ai') ? this.groundY(e.pos.x, e.pos.z) : 0;\n"
    "    return (e.pos.y || 0) + gy;\n"
    "  }\n"
    "  /* VERTICAL-END */\n"
    "  groundPlace(e) {\n    let gy",
    "worldY accessor")

# 2. groundPlace: the every-frame writer of entity height.
sub(
    "    let y = e.pos.y + gy;",
    "    let y = this.worldY(e, gy);",
    "groundPlace sum")

# 3. animate: the near-entity writer.
sub(
    "    e.g.position.y = e.pos.y + eGy;",
    "    e.g.position.y = this.worldY(e, eGy);",
    "animate sum")

# 4. myWorldState: the height that crosses the network.
sub(
    "+(me.pos.y + gy).toFixed(2)",
    "+this.worldY(me, gy).toFixed(2)",
    "myWorldState p[1]")

# 5. aimPoint: candidate body centre.
sub(
    "(n.pos.y + gy + 1.15) - o.y",
    "(this.worldY(n, gy) + 1.15) - o.y",
    "aimPoint centre")

# 6. bodyAnchor: every damage splat hangs off this.
sub(
    "return new T.Vector3(e.pos.x, (e.pos.y || 0) + gy + h, e.pos.z);",
    "return new T.Vector3(e.pos.x, this.worldY(e, gy) + h, e.pos.z);",
    "bodyAnchor")

# 7. stepRemotes: remote players' base placement (their pos.y is set to 0 in
#    updateRemote, so this is identical, and it is the line that starts
#    reading real height in 1e).
sub(
    "const gy = (this.worldOn && this.mode === 'ai') ? this.groundY(e.pos.x, e.pos.z) : 0; e.g.position.set(e.pos.x, gy, e.pos.z);",
    "const gy = (this.worldOn && this.mode === 'ai') ? this.groundY(e.pos.x, e.pos.z) : 0; e.g.position.set(e.pos.x, this.worldY(e, gy), e.pos.z);",
    "stepRemotes base")

# 8. fireFrost: aim origin and muzzle. pos.clone().add(0, gy+1.5, 0) already
#    composes pos.y + gy + 1.5; written out explicitly through worldY.
sub(
    "if (a === this.me) dir = this.aimDirFrom(a.pos.clone().add(new T.Vector3(0, gy + 1.5, 0))); else dir = this.npcAimDir(a, gy + 1.5);",
    "if (a === this.me) dir = this.aimDirFrom(new T.Vector3(a.pos.x, this.worldY(a, gy) + 1.5, a.pos.z)); else dir = this.npcAimDir(a, this.worldY(a, gy) + 1.5);",
    "frost origin")
sub(
    "else m.position.copy(a.pos).add(new T.Vector3(0, gy + 1.5, 0)).addScaledVector(dir, 1);",
    "else m.position.set(a.pos.x, this.worldY(a, gy) + 1.5, a.pos.z).addScaledVector(dir, 1);",
    "frost muzzle")

# 9. fireSnare: same pattern at 1.7.
sub(
    "const origin = a.pos.clone().add(new T.Vector3(0, gy + 1.7, 0));",
    "const origin = new T.Vector3(a.pos.x, this.worldY(a, gy) + 1.7, a.pos.z);",
    "snare origin")
sub(
    "dir = this.npcAimDir(a, gy + 1.7);",
    "dir = this.npcAimDir(a, this.worldY(a, gy) + 1.7);",
    "snare npc origin")
sub(
    "m.position.copy(a.pos).add(new T.Vector3(0, gy + 1.7, 0)).addScaledVector(dir, 1.1);",
    "m.position.set(a.pos.x, this.worldY(a, gy) + 1.7, a.pos.z).addScaledVector(dir, 1.1);",
    "snare muzzle")

# 10. fireArrow: same pattern at 1.55.
sub(
    "if (a === this.me) dir = this.aimDirFrom(a.pos.clone().add(new T.Vector3(0, gy + 1.55, 0))); else dir = this.npcAimDir(a, gy + 1.55);",
    "if (a === this.me) dir = this.aimDirFrom(new T.Vector3(a.pos.x, this.worldY(a, gy) + 1.55, a.pos.z)); else dir = this.npcAimDir(a, this.worldY(a, gy) + 1.55);",
    "arrow origin")
sub(
    "g.position.copy(a.pos).add(new T.Vector3(0, gy + 1.55, 0)).addScaledVector(dir, 1);",
    "g.position.set(a.pos.x, this.worldY(a, gy) + 1.55, a.pos.z).addScaledVector(dir, 1);",
    "arrow muzzle")

# 11. fireToxin: rat spit muzzle. NPC pos.y is always 0, identical today.
sub(
    "m.position.set(a.pos.x + dir.x * 1.4, gy + 1.4, a.pos.z + dir.z * 1.4);",
    "m.position.set(a.pos.x + dir.x * 1.4, this.worldY(a, gy) + 1.4, a.pos.z + dir.z * 1.4);",
    "toxin muzzle")

for old, new, label in edits:
    assert src.count(old) == 1, 'anchor %s went stale' % label
    src = src.replace(old, new)

io.open(SRC, 'w', encoding='utf-8').write(src)
print('patched %d anchors -> %s' % (len(edits), SRC))
