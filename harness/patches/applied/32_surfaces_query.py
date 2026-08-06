#!/usr/bin/env python3
"""Phase 1b: the surfaces query, with bridges moved inside it. Zero behaviour change.

"What is under me here?" stops being a terrain question with a bridge special
case wedged into it, and becomes a provider question. Two providers exist
today, in priority order: bridge decks (their exact shipped maths, unchanged,
via bridgeDeckY) and terrain. First answer wins, which is precisely the
relationship groundY has encoded since the bridges shipped, so every value
this returns is byte-identical to before.

Why bother, if nothing changes: later phases need floors that are not the
terrain. Platforms and stairs from the world editor, watchtower decks, and
vehicle decks all become providers pushed onto this one list, instead of each
becoming another special case inside groundY. Phase 1d upgrades the query to
answer "highest walkable surface at or just above my height" (so a player can
finally be UNDER a bridge rather than teleported on top of it), and adds the
underside query for head clearance. The stub for that second question ships
here so the API pair is complete.

Deliberately unchanged:
  - bridgeGeom and bridgeDeckY: not one character. The bridge tests
    (harness/bridges.js) walk the real deck in 5cm steps and are the check.
  - clampToRails: its comment explains it cannot use height while pos.y is
    not an elevation. That inverts to a height test in 1d, not before.
  - waterDepthAt: already deck-aware, stays as is until 1e makes swim state
    consult surfaces generally.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()

OLD = """  groundY(x, z) {
    // Asterra terrain: map-baked macro + seeded detail (worldgen.js). Pure and
    // identical on every machine, exactly like the old analytic heightfield.
    if (!GRIM_WORLD.ready) return 0;
    const d = this.bridgeDeckY(x, z);
    return d !== null ? d : GRIM_WORLD.height(x, z);
  }"""

NEW = """  groundY(x, z) {
    // Asterra terrain: map-baked macro + seeded detail (worldgen.js). Pure and
    // identical on every machine, exactly like the old analytic heightfield.
    // Phase 1b: delegates to the surfaces query below. Same values, one
    // extensible answer instead of a terrain function with a bridge special
    // case inside it.
    if (!GRIM_WORLD.ready) return 0;
    return this.surfaceY(x, z);
  }

  /* VERTICAL-BEGIN */
  // Phase 1b: the surfaces query. Providers answer with a walkable top
  // height or null, first answer wins. Priority order is the relationship
  // groundY has always encoded: a bridge deck overrides the terrain under
  // it, and terrain always answers. Later phases PUSH providers here
  // instead of adding special cases: editor platforms and stairs, elevated
  // structure decks, and vehicle decks once frames exist (1c/9). Phase 1d
  // upgrades this to answer at-or-just-above a reference height, so being
  // under a bridge becomes possible; today deck width means on top, by
  // design (see clampToRails).
  surfaceY(x, z) {
    let P = this._surfaces;
    if (!P) {
      P = this._surfaces = [
        (sx, sz) => this.bridgeDeckY(sx, sz),
        (sx, sz) => GRIM_WORLD.height(sx, sz),
      ];
    }
    for (let i = 0; i < P.length; i++) {
      const y = P[i](x, z);
      if (y !== null && y !== undefined) return y;
    }
    return 0;
  }
  // The other half of the pair: the lowest underside above your head, for
  // head clearance under decks and floors. No provider supplies undersides
  // yet, so this answers "open sky" everywhere and nothing consumes it
  // until 1d. It ships now so the API is complete when gravity arrives.
  ceilingY(x, z) {
    return Infinity;
  }
  /* VERTICAL-END */"""

n = src.count(OLD)
assert n == 1, 'groundY anchor matched %d times, expected 1' % n
src = src.replace(OLD, NEW)

io.open(SRC, 'w', encoding='utf-8').write(src)
print('patched 1 anchor -> %s' % SRC)
