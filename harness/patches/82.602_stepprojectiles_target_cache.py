#!/usr/bin/env python3
"""Patch 82.602: stop stepProjectiles() rebuilding the world NPC+PvP target
list, and cloning a Vector3 per target, for every single in-flight projectile
on every frame.

Two separate allocations were happening at O(projectiles x targets):

1. `this.npcs.concat(this.pvpTargets())` (plus, in coop, one more concat) was
   rebuilt fresh for every projectile owned by the player, every frame. That
   list does not change mid-tick (NPCs are only marked dead, never spliced
   out of the array during this pass), so it only needs to be built once per
   stepProjectiles() call. Memoized lazily on first use inside the loop
   (not precomputed unconditionally before it) so a tick with zero in-flight
   projectiles - the common case - still does zero work for this, same as
   before. Other owners (an NPC's shot, a coop partner's netFoe shot) already
   used small fixed-size arrays ([this.foe], [this.me], etc.) which were not
   worth touching.
2. `t.pos.clone()` was allocating a Vector3 per target checked, per
   projectile, just to read x/y/z once for a hit-test. Replaced with a single
   lazily-cached scratch vector, same pattern as the other allocation fixes
   in this batch.

No behavior change: same target-selection rules per owner, same hit-test
math, same order of operations.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    const ARROWS_HIT_WORLD = true;
    for (let i = this.projectiles.length - 1; i >= 0; i--) {
"""

NEW = """    const ARROWS_HIT_WORLD = true;
    // Memoized on first use inside the loop below, not built here - a tick
    // with no in-flight projectiles should do zero work for this.
    let myWorldTargets;
    for (let i = this.projectiles.length - 1; i >= 0; i--) {
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)

OLD2 = """      const targets = (p.owner && p.owner.cosmetic) ? []
        : p.owner === this.me
        ? ((this.worldOn && this.mode === 'ai')
            ? ((this.coop && this.netFoe.g.visible && this.netFoe.hp > 0) ? this.npcs.concat([this.netFoe]) : this.npcs).concat(this.pvpTargets())
            : [this.foe])
        : (p.owner === this.netFoe ? []
           : ((this.coop && this.isHost && this.netFoe.g.visible && this.netFoe.hp > 0) ? [this.me, this.netFoe] : [this.me]));
      for (const t of targets) {
        if (t.hp <= 0) continue;
        const c2 = t.pos.clone(); c2.y = ((this.worldOn && this.mode === 'ai') ? this.groundY(t.pos.x, t.pos.z) : 0) + 1.1;
"""

NEW2 = """      const targets = (p.owner && p.owner.cosmetic) ? []
        : p.owner === this.me
        ? (myWorldTargets || (myWorldTargets = (this.worldOn && this.mode === 'ai')
            ? ((this.coop && this.netFoe.g.visible && this.netFoe.hp > 0) ? this.npcs.concat([this.netFoe]) : this.npcs).concat(this.pvpTargets())
            : [this.foe]))
        : (p.owner === this.netFoe ? []
           : ((this.coop && this.isHost && this.netFoe.g.visible && this.netFoe.hp > 0) ? [this.me, this.netFoe] : [this.me]));
      for (const t of targets) {
        if (t.hp <= 0) continue;
        const c2 = (this._projHitPos || (this._projHitPos = new T.Vector3())).copy(t.pos); c2.y = ((this.worldOn && this.mode === 'ai') ? this.groundY(t.pos.x, t.pos.z) : 0) + 1.1;
"""

count2 = s.count(OLD2)
assert count2 == 1, 'anchor2 matched %d times, expected 1' % count2
s = s.replace(OLD2, NEW2)

io.open(PATH, 'w', encoding='utf-8').write(s)
