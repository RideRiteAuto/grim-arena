#!/usr/bin/env python3
"""Phase 1, part 3: the public zone lookup.

Section 6b asks for a single function that answers "which zone is this world
position in". The bake already answers it as a numeric terrain id; this exposes
the DESIGN zone on the game object, which is what every content system and
every test actually wants. It also exposes the world generator on the instance
so the harness can read the same ground truth the game reads instead of
approximating it.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()

OLD = "  registerRoad(pts) {"
NEW = """  // The one zone lookup. Everything downstream keys off this, so it is a
  // direct grid read with no allocation: cheap enough to call per prop.
  zoneAt(x, z) { return grimZoneName(GRIM_WORLD.zone(x, z)); }
  // True on the volcanic core band, which is the only ground that rolls the
  // deep Ember nodes.
  zoneDeepAt(x, z) { return grimZoneIsDeep(GRIM_WORLD.zone(x, z)); }
  zoneName(x, z) { const Z = GRIM_RULES.ZONES[this.zoneAt(x, z)]; return Z ? Z.name : 'Unknown'; }
  // Debug handle for the world generator, so tooling reads the same ground
  // truth the game does rather than a second copy that can drift.
  WORLD() { return GRIM_WORLD; }
  RULES() { return GRIM_RULES; }

  registerRoad(pts) {"""

assert src.count(OLD) == 1, 'registerRoad anchor not unique'
out = src.replace(OLD, NEW, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('zone api added, %d -> %d bytes' % (len(src), len(out)))
