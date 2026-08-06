#!/usr/bin/env python3
"""Patch 41: sampled combat one-shots.

The applyDamage funnel plays parry/block/crit/hit and attack windups play
swing/heavy. Those six are the most heard sounds in the game and they were
all oscillator recipes: a sine thump for a blow landing, two triangle waves
for steel meeting steel. Patch 30 proved the fix for the anvil and campfire;
this extends it to combat.

Six sounds become samples, everything else stays synthesised:

  combat-swing   light attack whoosh, no impact
  combat-heavy   heavy attack whoosh, low air mass
  combat-hit     blunt blow on padded leather, the bread-and-butter impact
  combat-crit    the same weapon hitting much harder
  combat-block   sword on a wooden shield with a steel boss, dead thunk
  combat-parry   steel on steel, bright clang, fast decay

Generated FROM model-lab/sfx-samples.js (harness/sfx.py, ElevenLabs, three
takes per sound per Kevin's budget rule, winner picked on peak/RMS/crest and
the spectrogram). ~46 KB of base64 on the bundle.

Repetition: every play gets a random detune, the anvil's trick. The synth
recipes stay in the switch as the fallback for a browser that cannot decode
mp3 or a blow that lands before the async decode resolves.

Two anchored edits:
  1. the six new entries appended to SFX_SAMPLES inside sampleInit
  2. the sample intercept at the top of sfx()'s switch
"""
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# 1. pull the combat entries out of the module and append them to the bundle's
#    SFX_SAMPLES, exactly as patch 30 shipped the first four (module is the
#    single source; nothing is retyped)
# ---------------------------------------------------------------------------
m0 = mod.find('// -- combat one-shots (patch 41)')
assert m0 > 0, 'combat block missing from model-lab/sfx-samples.js'
m1 = mod.find('\n};', m0)
assert m1 > 0
block = mod[m0:m1]
block = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in block.split('\n'))

# fire-bed's base64 tail is the last entry in the bundle's SFX_SAMPLES today.
A1 = "+ 'qg==',"
assert s.count(A1) == 1, 'fire-bed tail anchor matched %d times' % s.count(A1)
i = s.find(A1)
j = s.find('};', i)
assert j > 0 and j - i < 40, 'SFX_SAMPLES close not where expected after fire-bed'
s = s[:j] + block + '\n    ' + s[j:]

# ---------------------------------------------------------------------------
# 2. the intercept: sampled voice first, synthesised voice as the fallback
# ---------------------------------------------------------------------------
A2 = """    if (this.ac.state === 'suspended') { try { this.ac.resume(); } catch (e) {} }
    switch (name) {"""
assert s.count(A2) == 1, 'sfx() anchor matched %d times' % s.count(A2)
s = s.replace(A2, """    if (this.ac.state === 'suspended') { try { this.ac.resume(); } catch (e) {} }
    // Sampled combat voice (patch 41). Gains sit against the anvil's 0.5 and
    // every play is detuned so repeats never sound retriggered. Falls through
    // to the synth recipe when the decode has not landed or cannot land.
    const CSAMP = {
      swing: ['combat-swing', 0.35, 60], heavy: ['combat-heavy', 0.5, 60],
      hit: ['combat-hit', 0.6, 70], crit: ['combat-crit', 0.85, 70],
      block: ['combat-block', 0.55, 50], parry: ['combat-parry', 0.5, 40]
    };
    const cs = CSAMP[name];
    if (cs && this._samples && this._samples.ready() && this._samples.has(cs[0])) {
      this._samples.play(cs[0], { gain: cs[1], detune: (Math.random() * 2 - 1) * cs[2] });
      return;
    }
    switch (name) {""")

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 41: combat samples in, sfx() intercept in')
