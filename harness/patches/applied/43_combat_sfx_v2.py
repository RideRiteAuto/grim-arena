#!/usr/bin/env python3
"""Patch 43: combat one-shots v2, louder and heavier.

Kevin's review of patch 41 in the live game: swing, hit, crit and block were
too quiet and did not feel impactful. This patch replaces those four samples
with regenerated takes (heavier prompts, three takes each per the budget
rule) mastered about 4 to 6 dB hotter: +5 dB into a limiter, peak -0.5 dBFS.
heavy and parry stay the v1 takes. The in-game gains come up as well, since
half of "too quiet" was the conservative mix against the anvil's 0.5:

  swing 0.35 -> 0.5    hit 0.6 -> 0.8    crit 0.85 -> 1.0    block 0.55 -> 0.7

Two anchored edits:
  1. the combat block inside SFX_SAMPLES is regenerated from
     model-lab/sfx-samples.js (the module is the single source)
  2. the CSAMP gain table in sfx()
"""
import io, os

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# 1. swap the whole combat block for the module's current one
# ---------------------------------------------------------------------------
m0 = mod.find('  // -- combat one-shots (patch 41, v2 in patch 43)')
assert m0 > 0, 'v2 combat block missing from model-lab/sfx-samples.js'
m1 = mod.find('\n};', m0)
assert m1 > 0
block = mod[m0:m1]
block = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in block.split('\n'))

b0 = s.find('// -- combat one-shots (patch 41)')
assert b0 > 0, 'v1 combat block not found in bundle'
b0 = s.rfind('\n', 0, b0) + 1
b1 = s.find('\n    };', b0)
assert b1 > 0 and b1 - b0 < 80000, 'combat block close not where expected'
s = s[:b0] + block + s[b1:]

# ---------------------------------------------------------------------------
# 2. the gains
# ---------------------------------------------------------------------------
A2 = """    const CSAMP = {
      swing: ['combat-swing', 0.35, 60], heavy: ['combat-heavy', 0.5, 60],
      hit: ['combat-hit', 0.6, 70], crit: ['combat-crit', 0.85, 70],
      block: ['combat-block', 0.55, 50], parry: ['combat-parry', 0.5, 40]
    };"""
assert s.count(A2) == 1, 'CSAMP anchor matched %d times' % s.count(A2)
s = s.replace(A2, """    const CSAMP = {
      swing: ['combat-swing', 0.5, 60], heavy: ['combat-heavy', 0.5, 60],
      hit: ['combat-hit', 0.8, 70], crit: ['combat-crit', 1.0, 70],
      block: ['combat-block', 0.7, 50], parry: ['combat-parry', 0.5, 40]
    };""")

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 43: v2 combat samples in, gains raised')
