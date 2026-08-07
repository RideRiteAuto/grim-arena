# Patch 59: every zone tree gets the new rig.
#
# Patch 56 rebuilt the two starter trees (hinged splinter-break fell, root
# flares, real limbs); the ten streamed zone kinds still built the old
# lofted-pole-with-balls props. model-lab/tree.js now carries all the zone
# shapes - poplar (vertical column), broad (zoak/acacia), palm (frond crown),
# willow (hanging curtains), snag (dead, shattered top - bogoak/emberbark),
# pine (cone tiers - icewood), elder (elder/elderking) - each tinted by
# ZONE_LOOK and scaled by the spawner's sc, all sharing the fell/stump/sound
# contract the starter trees shipped with.
#
# Three changes:
#   1. The natureKits() block is REGENERATED from the current lab modules
#      (grim-kit + tree + orenode), replacing the patch-56 copy wholesale.
#   2. makeZoneTree delegates into the kit (merged single-mesh mode: a
#      streamed tree is one draw call for the falling part, zone budget is
#      1,400 calls scene-wide).
#   3. resourceDepleted goes SILENT on stream-in restores: a chunk loading
#      with an already-dead node used to queue the full 5.4s fall with the
#      crack-and-crash recording (trees) or the chip sounds (ore) every time
#      you walked back into range. Restores now snap to the end state.
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
KIT = os.path.join(HERE, '..', '..', 'model-lab', 'grim-kit.js')
TREE = os.path.join(HERE, '..', '..', 'model-lab', 'tree.js')
ORE = os.path.join(HERE, '..', '..', 'model-lab', 'orenode.js')

s = io.open(SRC, encoding='utf-8').read()

def sub(old, new, why):
    global s
    assert s.count(old) == 1, 'anchor x%d: %s' % (s.count(old), why)
    s = s.replace(old, new)
    print('  ok:', why)

def span(start, end, new, why):
    global s
    assert s.count(start) == 1, 'start anchor x%d: %s' % (s.count(start), why)
    i = s.find(start)
    j = s.find(end, i)
    assert j > i, 'end anchor after start: ' + why
    j += len(end)
    s = s[:i] + new + s[j:]
    print('  ok:', why)

def strip_module(path, banner):
    m = io.open(path, encoding='utf-8').read()
    m = re.sub(r'import \{[\s\S]*?\} from \'\./grim-kit\.js\';\n', '', m)
    m = m.replace('export function ', 'function ').replace('export const ', 'const ')
    m = re.sub(r'\A// GRIM WORLD: ' + banner + r'[\s\S]*?\n\n(?=import|function|const|//|export)', '', m, count=1)
    return m

# ---- 1. regenerate natureKits() from the current lab modules ---------------
kitSrc = io.open(KIT, encoding='utf-8').read()
kitSrc = kitSrc.replace('export function ', 'function ').replace('export const ', 'const ')
kitSrc = re.sub(r'\A(//.*\n)+', '', kitSrc)
treeSrc = strip_module(TREE, 'the trees')
oreSrc = strip_module(ORE, 'the ore nodes')

full = kitSrc + '\n' + treeSrc + '\n' + oreSrc
full = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in full.split('\n'))

METHOD = '''  // ---- trees and ore nodes -------------------------------------------------
  // Built from model-lab/tree.js + orenode.js + grim-kit.js by patch 59. Do
  // not hand-edit this block: change the lab modules, review with the
  // turntable pages, and rebuild. The lab and the game run the same source.
  natureKits() {
    if (this._natKits) return this._natKits;
    const T = this.T;
''' + full + '''
    this._natKits = { tree: makeTreeKit(T), ore: makeOreNodeKit(T) };
    return this._natKits;
  }'''

span('  // ---- trees and ore nodes -----',
     "    this._natKits = { tree: makeTreeKit(T), ore: makeOreNodeKit(T) };\n    return this._natKits;\n  }",
     METHOD,
     'natureKits regenerated from the current lab modules')

# ---- 2. makeZoneTree delegates into the kit --------------------------------
NEW_ZONE_TREE = '''makeZoneTree(look, sc, seed, shape) {
    // Every zone species now comes off the same rig as the starter trees:
    // hinged splinter-break fell, planted root flare, per-shape silhouette
    // from the KINDS table, zone identity from the look's tints. merged:
    // the falling half is ONE mesh - streamed chunks live on a draw budget.
    const built = this.natureKits().tree.build({
      kind: shape || 'broad', seed: seed, sc: (sc || 1),
      tint: { trunk: look.trunk, leaf: look.leaf, leaf2: look.leaf2 },
      merged: true
    });
    return { g: built.g, fell: built.fell, stump: built.stump, canopies: built.canopies };
  }'''

END_ZT = 'return { g: g, fell: fell, stump: stumpG };\n  }'
i = s.find('makeZoneTree(look, sc, seed, shape) {')
assert s.count('makeZoneTree(look, sc, seed, shape) {') == 1, 'makeZoneTree start'
j = s.find(END_ZT, i)
assert j > i, 'makeZoneTree end anchor'
j += len(END_ZT)
s = s[:i] + NEW_ZONE_TREE + s[j:]
print('  ok: makeZoneTree delegates to the tree kit')

# ---- 3. stream-in restores go silent ---------------------------------------
sub("""      if (p) this.spark(p, 0xd88a4a, 16);
      // the chunk coming free, then the spent vein crumbling under it
      this.sfx('orechip');
      this.sfx('oredeplete', 0.22);""",
    """      if (p) this.spark(p, 0xd88a4a, 16);
      // the chunk coming free, then the spent vein crumbling under it.
      // No p means a stream-in restore of an already-empty vein: silent.
      if (p) {
        this.sfx('orechip');
        this.sfx('oredeplete', 0.22);
      }""",
    'mining stream-in restore is silent')

sub("""      if (p) this.spark(p, 0x4fb3a0, 12);
      this.sfx('pickup');""",
    """      if (p) this.spark(p, 0x4fb3a0, 12);
      if (p) this.sfx('pickup');""",
    'foraging stream-in restore is silent')

sub("""      if (R.stump) R.stump.visible = true;
      const fm = R.fell || R.g;
      fm.matrixAutoUpdate = true;                     // the fall animates this node""",
    """      if (R.stump) R.stump.visible = true;
      const fm = R.fell || R.g;
      // No p means a chunk streamed in with this tree already down: snap to
      // the fallen end state instead of replaying the 5.4s fall and the
      // crack-and-crash recording at whoever walked back into range.
      if (!p) { fm.visible = false; return; }
      fm.matrixAutoUpdate = true;                     // the fall animates this node""",
    'tree stream-in restore snaps to the end state, silent')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 59 applied')
