#!/usr/bin/env python3
"""Patch 32: the player character, v4.

Replaces the geometry inside makeFighter with the lab-built rig from
model-lab/character.js: a real base body (skin, padded tunic, trousers, boots
with a heel and a toe box, hands with fingers, a face) with every armor piece
a separate mesh in a `gear` group draped over it. Same part names, same pivot
convention, so animate(), combat, swimming, rowing, the donkey and multiplayer
all run unmodified. The weapons inside the module were TRANSPLANTED VERBATIM
from v3 - not redesigned - so every grip stays tuned to the swing arcs.

Also upgrades the idle in animate():
  - chest breathing on a 3.9 s cycle, weight sway at 7.3 s, head drift at
    11 s. Coprime periods, so the composite never visibly loops. All of it
    fades out with movement and is guarded on P.chest so bosses built on
    the old rig (Sailers, goblins) are untouched.
  - the shield now hangs WORLD-vertical at rest instead of following the
    arm's inward tilt, which is the thing Kevin called out. The blocking
    presentation is unchanged.

Three anchored edits: the makeFighter body, the idle line, the shield block.
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
body = re.sub(r'\A// GRIM WORLD: the player character, v4\.\n(//.*\n)*', '', body)
body = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n'))

# ---------------------------------------------------------------------------
# 1. makeFighter: swap the whole construction, keep the state tail verbatim
# ---------------------------------------------------------------------------
SIG = '  makeFighter(pal, isMe) {'
i = s.find(SIG)
assert i >= 0 and s.count(SIG) == 1, 'makeFighter signature not unique'
j = s.find('    return {', i)
assert 0 < j < i + 20000, 'makeFighter return not found where expected'

NEW_BODY = SIG + '''
    const T = this.T;
    // ---- v4 rig ------------------------------------------------------------
    // Built from model-lab/character.js by harness/patches/32_character.py.
    // Do not hand-edit: change the lab module, review it on the turntable
    // (model-lab/character.html), and rebuild.
''' + body + '''
    const model = makeFighterModel(T, pal);
    model.setArmor(true);
    const g = model.g, body = model.body;
    const upper = model.parts.upper, torso = model.parts.torso, head = model.parts.head,
      armR = model.parts.armR, armL = model.parts.armL, legR = model.parts.legR, legL = model.parts.legL,
      hand = model.parts.hand, handL = model.parts.handL, sword = model.parts.sword,
      staff = model.parts.staff, bow = model.parts.bow, backBow = model.parts.backBow,
      shield = model.parts.shield, ward = model.parts.ward, orb = model.parts.orb,
      frostShell = model.parts.frostShell, crest = model.parts.crest, capePiv = model.parts.capePiv,
      bladeTip = model.parts.bladeTip, pick = model.parts.pick, waxe = model.parts.axe,
      great = model.parts.great, greatTip = model.parts.greatTip,
      chest = model.parts.chest, hair = model.parts.hair, helm = model.parts.helm;
    const steel = model.mats.steel, cloth = model.mats.cloth, trim = model.mats.trim;
    this._lastSteel = steel;
    const setArmor = model.setArmor;
'''

# extend the parts map with the new optional parts, and expose setArmor
OLD_PARTS = "      parts: { upper, torso, head, armR, armL, legR, legL, hand, handL, sword, staff, bow, backBow, shield, ward, orb, frostShell, crest, capePiv, bladeTip, pick, axe: waxe, great, greatTip },"
assert s.count(OLD_PARTS) == 1, 'parts map anchor matched %d times' % s.count(OLD_PARTS)

s = s[:i] + NEW_BODY + s[j:]
s = s.replace(OLD_PARTS,
    "      parts: { upper, torso, head, armR, armL, legR, legL, hand, handL, sword, staff, bow, backBow, shield, ward, orb, frostShell, crest, capePiv, bladeTip, pick, axe: waxe, great, greatTip, chest, hair, helm },\n      setArmor,")

# ---------------------------------------------------------------------------
# 2. idle: breathing, weight sway, head drift - coprime periods, move-faded
# ---------------------------------------------------------------------------
IDLE = "    e.body.position.y = e.bob + Math.sin(performance.now() * 0.0016) * 0.012;"
assert s.count(IDLE) == 1, 'idle anchor matched %d times' % s.count(IDLE)
s = s.replace(IDLE, """    e.body.position.y = e.bob + Math.sin(performance.now() * 0.0016) * 0.012;
    // v4 idle: breath 3.9 s, sway 7.3 s, head drift 11 s. Coprime periods so
    // the composite never visibly loops; everything fades with movement and
    // P.chest guards it off the old-rig bosses.
    if (P.chest) {
      const idW = Math.max(0, 1 - (e.moveAmt || 0) * 3) * (e.state === 'idle' || e.state === 'move' ? 1 : 0);
      const tN = performance.now() * 0.001 + (e.phase || 0);
      const br = Math.sin(tN * 1.61);
      P.chest.scale.set(1 + 0.011 * br * idW, 1 + 0.007 * br * idW, 1 + 0.017 * br * idW);
      e.body.rotation.z = 0.016 * Math.sin(tN * 0.861) * idW;
      P.upper.rotation.z = -0.013 * Math.sin(tN * 0.861 + 0.5) * idW;
      if (!(e._rowT > 0.02)) P.head.rotation.y = 0.055 * Math.sin(tN * 0.571) * idW;
    }""")

# ---------------------------------------------------------------------------
# 3. the shield hangs straight at rest
# ---------------------------------------------------------------------------
SH = """      P.shield.rotation.x = -P.armL.rotation.x * b2;
      P.shield.rotation.y = Math.PI - 1.62 * b2;
      P.shield.rotation.z = 0.12 * (1 - b2) - 0.1 * b2;"""
assert s.count(SH) == 1, 'shield anchor matched %d times' % s.count(SH)
s = s.replace(SH, """      // At rest the shield counter-rotates against the arm so it hangs
      // world-vertical at the side instead of following the arm's inward
      // tilt. Guarding still presents the face square-on, unchanged.
      P.shield.rotation.x = -P.armL.rotation.x * Math.max(b2, 0.85);
      P.shield.rotation.y = Math.PI - 1.62 * b2;
      P.shield.rotation.z = (-P.armL.rotation.z + 0.04) * (1 - b2) - 0.1 * b2;""")

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 32: character v4 installed (%d bytes of module inlined)' % len(body))
