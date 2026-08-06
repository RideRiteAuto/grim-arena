#!/usr/bin/env python3
"""Patch 35: v5 polish from Kevin's review of the shipped build.

Three items, all in model-lab/character.js:
  1. The crossguard was still a box with two cube quillons - "really blocky,
     doesn't match the high quality blade". It is now one swept bar dipping
     at the centre with upswept rounded knob ends, plus a ferrule collar
     seated over the blade root. Same sweep machinery as the blade.
  2. The shield carried at the side had its POINT leading forward - the rest
     euler's x sign was guessed and guessed wrong. Flipped (+PI/2), point
     now trails aft. Same flip in animate()'s rest write here.
  3. The heater plate was a square with a 45-degree diamond butted against
     it, and the join read exactly like that. The plate is now ONE extruded
     outline (straight top, quadratic sides easing to the point). Boot cuffs
     flare wider than the trouser leg so the leg goes INTO the boot, and the
     soles shrank from a deck to an edge.

Numbering: 33 and 34 were taken by the vertical track while this track was
mid-flight. Fresh-pull check before naming, as always.

Two anchored edits: the module body swap, the shield rest euler in animate().
"""
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'character.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

assert 'export function makeFighterModel(T, pal)' in mod, 'module entry point moved'
body = re.sub(r'^import \{[^}]*\} from \'\./grim-kit\.js\';\n', '', mod, flags=re.M)
assert 'grim-kit' not in body, 'import line did not come out'
body = re.sub(r'^export ', '', body, flags=re.M)
body = re.sub(r'\A// GRIM WORLD: the player character, v5\.\n(//.*\n)*', '', body)
body = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n'))

# ---------------------------------------------------------------------------
# 1. swap the module block, banner to tail
# ---------------------------------------------------------------------------
BANNER = '    // ---- v5 rig ------------------------------------------------------------'
TAIL = '    const model = makeFighterModel(T, pal);'
assert s.count(BANNER) == 1, 'v5 banner matched %d times' % s.count(BANNER)
assert s.count(TAIL) == 1, 'module tail matched %d times' % s.count(TAIL)
i = s.find(BANNER)
j = s.find(TAIL)
assert i < j < i + 90000, 'banner and tail out of order'

NEW = BANNER + '''
    // Built from model-lab/character.js by harness/patches/35_character_v5_polish.py.
    // Do not hand-edit: change the lab module, review it on the turntable
    // (model-lab/character.html + harness/char-review.js), and rebuild.

''' + body + '\n\n'
s = s[:i] + NEW + s[j:]

# ---------------------------------------------------------------------------
# 2. shield rest euler: point aft, for real this time
# ---------------------------------------------------------------------------
OLD = 'P.shield.rotation.x = (-Math.PI / 2) * (1 - b2) + (-P.armL.rotation.x) * b2;'
assert s.count(OLD) == 1, 'shield rest euler matched %d times' % s.count(OLD)
s = s.replace(OLD,
  'P.shield.rotation.x = (Math.PI / 2) * (1 - b2) + (-P.armL.rotation.x) * b2;')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 35: v5 polish installed (%d bytes of module inlined)' % len(body))
