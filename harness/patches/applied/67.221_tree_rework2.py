# Patch 67.221: tree rework round 2, from Kevin's review of the patch 66
# lineup renders.
#
#   "Most of your new trees look pretty nice, except for the redwood... it
#   should be way bushier at the top, have way more green greenery... right
#   now it's like bare at the very top of the tree." and "there's one of them
#   that looks kinda like a willow tree... the danglers, a few of them aren't
#   actually attached to the tree."
#
# Two fixes in model-lab/tree.js, both isolated to the conifer canopy builder
# and the willow drape loop so nothing else in the tree rig moves:
#
#   1. REDWOOD CANOPY. A real coast redwood's own crown is actually narrow and
#      pyramidal (checked against reference before touching this - see
#      ART-TRACK-STATUS.md), so matching real life would NOT have satisfied
#      "bushier". Instead the shared conifer builder (also used by pine) grew
#      four new per-kind knobs - crownTaper, crownDenseBase/Fall, crownClumpMul,
#      crownTipMul, crownTipExtra - all defaulting to pine's old hardcoded
#      numbers when unset, so pine is provably unchanged. Redwood sets all of
#      them: taper drops from 0.80 to 0.42 (the top tiers stay wide instead of
#      shrinking to a point), tier density rises, clumps run 1.3x bigger, and
#      the tip cap gets 2.1x bigger plus 5 extra sub-clumps clustered around
#      it, closer to a giant-sequoia-like full head than the old thin spike.
#      Leaf ramp also nudged greener/brighter per "way more green greenery".
#
#   2. WILLOW DRAPES. The hanging curtain blobs used to be placed at an
#      independently random radius/height (0.75-1.05x crownR, a narrow band
#      near crownY0+0.6-1.1) while the main foliage clumps live at a
#      DIFFERENT random radius (0.3-0.8x crownR) and a much wider height
#      range - the two draws rarely landed in the same place, so several
#      drapes every build hung in empty air with nothing under them. Drapes
#      now pick an actual clump from clumpAt (the list the crown clumps were
#      just rendered from) and hang off IT, with a thin drooping branch stub
#      (the same buried-stub trick the limb-end clusters use) physically
#      connecting clump to curtain - every drape is now attached to real wood.
#
# The natureKits() block is regenerated wholesale from the current lab
# modules, same as every previous tree patch.
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
KIT = os.path.join(HERE, '..', '..', 'model-lab', 'grim-kit.js')
TREE = os.path.join(HERE, '..', '..', 'model-lab', 'tree.js')
ORE = os.path.join(HERE, '..', '..', 'model-lab', 'orenode.js')

s = io.open(SRC, encoding='utf-8').read()

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

# ---- regenerate natureKits() from the current lab modules ------------------
kitSrc = io.open(KIT, encoding='utf-8').read()
kitSrc = kitSrc.replace('export function ', 'function ').replace('export const ', 'const ')
kitSrc = re.sub(r'\A(//.*\n)+', '', kitSrc)
treeSrc = strip_module(TREE, 'the trees')
oreSrc = strip_module(ORE, 'the ore nodes')

full = kitSrc + '\n' + treeSrc + '\n' + oreSrc
full = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in full.split('\n'))

METHOD = '''  // ---- trees and ore nodes -------------------------------------------------
  // Built from model-lab/tree.js + orenode.js + grim-kit.js by patch 67.221.
  // Do not hand-edit this block: change the lab modules, review with the
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
     'natureKits regenerated: redwood canopy + willow drape attachment fix')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 67.221 applied')
