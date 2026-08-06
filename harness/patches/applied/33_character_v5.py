#!/usr/bin/env python3
"""Patch 33: the player character, v5, and the straight-arm idle.

Kevin's review of v4, verbatim themes: joints were round balls glued together
with visible seams; eyebrows and chin were ovals stuck on the face; hair was
blocky; feet were bad and clipped the ground; the lower shoulder could be
seen THROUGH into the model; the sword blade was obviously stacked blocks;
and the shield arm crossed the body when both arms should hang straight down,
with the shield carried flat at the side, long axis front to back, point aft.

v5 answers with construction, not new proportions:
  - bulges (deltoid, knee, chin, brow) are sections of their limb's own loft
  - joints are domes CENTERED on the pivots, tucked under the garment above,
    so no gap can open at any swing angle
  - the boot flows shin-to-toe as ONE swept surface with a heel and toe box,
    underside flat on the sole plane, sole bottom at world 0.015
  - the scimitar blade is one continuous swept body along the same curve the
    stacked boxes followed, so swing arcs and the bladeTip trail are unmoved
  - and the real find: loftY wound its caps inward and rendered every
    top-down-authored loft INSIDE-OUT. That was the see-through shoulder, in
    v4 and in v3 before it. v5's loftY normalises section order and winds
    caps out. The fix lives in the module; this patch just ships it.

Game-side pose changes, all in animate():
  1. idle arm defaults hang straight (was a 0.1 rad inward tilt)
  2. the sword-and-board idle no longer pulls the left arm across the body
  3. the shield rest pose becomes the flat side carry; blocking still blends
     to the same square-on guard as before

Anchored edits: the module body swap (banner to tail), then three pose lines.
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
# 1. swap the v4 module block for v5, between patch 32's banner and its tail
# ---------------------------------------------------------------------------
BANNER = '    // ---- v4 rig ------------------------------------------------------------'
TAIL = '    const model = makeFighterModel(T, pal);'
assert s.count(BANNER) == 1, 'v4 banner matched %d times' % s.count(BANNER)
assert s.count(TAIL) == 1, 'module tail matched %d times' % s.count(TAIL)
i = s.find(BANNER)
j = s.find(TAIL)
assert i < j < i + 80000, 'banner and tail out of order'

NEW = BANNER.replace('v4 rig', 'v5 rig') + '''
    // Built from model-lab/character.js by harness/patches/33_character_v5.py.
    // Do not hand-edit: change the lab module, review it on the turntable
    // (model-lab/character.html + harness/char-review.js), and rebuild.

''' + body + '\n\n'
s = s[:i] + NEW + s[j:]

# ---------------------------------------------------------------------------
# 2. idle arm defaults: hang straight down at the sides
# ---------------------------------------------------------------------------
OLD_DEF = 'let armRx = -sw * 0.55, armLx = sw * 0.55, armRz = 0.1, armLz = -0.1, handRy = 0, handRz = 0;'
assert s.count(OLD_DEF) == 1, 'arm defaults matched %d times' % s.count(OLD_DEF)
s = s.replace(OLD_DEF,
  'let armRx = -sw * 0.55, armLx = sw * 0.55, armRz = 0.04, armLz = -0.06, handRy = 0, handRz = 0;')

# ---------------------------------------------------------------------------
# 3. sword-and-board idle: no more cross-body pull on the shield arm
# ---------------------------------------------------------------------------
OLD_W0 = 'else if (e.weapon === 0) { armLx += -0.16; armLz = -0.2; }'
assert s.count(OLD_W0) == 1, 'weapon-0 idle matched %d times' % s.count(OLD_W0)
s = s.replace(OLD_W0,
  'else if (e.weapon === 0) { armLz = -0.06; }   // hangs straight; shield rides the side')

# ---------------------------------------------------------------------------
# 4. shield: rest is the flat side carry, block is the same guard as ever
# ---------------------------------------------------------------------------
OLD_SH = '''      // At rest the shield counter-rotates against the arm so it hangs
      // world-vertical at the side instead of following the arm's inward
      // tilt. Guarding still presents the face square-on, unchanged.
      P.shield.rotation.x = -P.armL.rotation.x * Math.max(b2, 0.85);
      P.shield.rotation.y = Math.PI - 1.62 * b2;
      P.shield.rotation.z = (-P.armL.rotation.z + 0.04) * (1 - b2) - 0.1 * b2;
      P.shield.position.set(0.09 - 0.16 * b2, -0.52 - 0.07 * b2, 0.06 + 0.3 * b2);'''
assert s.count(OLD_SH) == 1, 'shield pose block matched %d times' % s.count(OLD_SH)
s = s.replace(OLD_SH, '''      // Rest: carried FLAT along the side like a slung heater - long axis
      // front to back, point aft, face out (local +Y rolled to world +Z).
      // Blocking blends to the same square-on guard as before.
      P.shield.rotation.x = (-Math.PI / 2) * (1 - b2) + (-P.armL.rotation.x) * b2;
      P.shield.rotation.y = Math.PI - 1.62 * b2;
      P.shield.rotation.z = (-P.armL.rotation.z) * (1 - b2) - 0.1 * b2;
      P.shield.position.set(0.07 - 0.14 * b2, -0.55 - 0.04 * b2, -0.05 + 0.35 * b2);''')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 33: character v5 installed (%d bytes of module inlined)' % len(body))
