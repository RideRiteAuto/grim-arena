# Patch 66: the tree rework Kevin asked for after seeing the patch 59 zone
# tree lineup.
#
# model-lab/tree.js changed in six ways:
#   1. Buttress roots removed entirely - "that looks stupid... don't even
#      try to fix them, just remove them." The trunk's own base flare loft
#      (always there, underneath the roots) is what is left.
#   2. The splinter-shard stump/break-face treatment is gone, replaced by a
#      plain flat cut face with painted growth rings (stumpCap()). No more
#      "spiky bits to make it look broken."
#   3. Pine's canopy is rebuilt from soft roughened needle clumps on real
#      branch stubs (canopy 'conifer') instead of smooth stacked cones -
#      "it's all spiky... we need a way better design."
#   4. bogoak and emberbark, previously the SAME geometry under a tint, are
#      now two distinct KINDS entries - bogoak slender ancient bog-black
#      wood, emberbark a thicker charred trunk with painted ember-glow
#      cracks. acacia also splits out of the generic broad shape into its
#      own near-black ironbark, flat-topped umbrella silhouette. A new
#      `redwood` kind - massive, barely-tapering, cinnamon bark - is the
#      "bigger than all the rest of them" tree Kevin asked for, added to
#      the world editor's nature catalog (this patch's second change).
#   5. A real-species colour pass across every kind (oak's cool gray-brown,
#      willow's silvery sage foliage, poplar's aspen shimmer, and so on),
#      so species stop reading as the same green tree recoloured.
#   6. Every kind is both scaled up (roughly 20-30 percent, more for the
#      oak/evergreen tier) AND builds one of two size variants keyed off its
#      own seed, with a slightly different shade, so a cluster of the same
#      species never reads as one tree copy-pasted next to itself.
#
# The natureKits() block is REGENERATED wholesale from the current lab
# modules (grim-kit + tree + orenode), same as every previous tree patch.
# makeZoneTree and the silent stream-in restores are unchanged (patch 59)
# and are not touched here.
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
  // Built from model-lab/tree.js + orenode.js + grim-kit.js by patch 66. Do
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
     'natureKits regenerated from the reworked lab modules')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 66 applied')
