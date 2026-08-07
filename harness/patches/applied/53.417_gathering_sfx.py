#!/usr/bin/env python3
"""Patch 53.417: real sounds for chopping, mining and foraging.

Kevin asked for the axe to sound like an axe and, in his words, for mining to
"sound more like a mining sound that you traditionally hear in a game".

Three things happen here.

1. CHOPPING and MINING become samples, three variants each. These fire once a
   swing, many swings a node, so a single retriggered sample is immediately
   obvious. The three variants rotate and each play is detuned, the same
   treatment the anvil gets, so a whole tree never repeats a sound.

2. MINING is deliberately bright. The takes were chosen on measurement: the
   picked ones sit near a 6500 Hz spectral centroid with about 96 percent of
   their energy above 2 kHz, which is metal ringing off stone. The duller
   candidates read as digging rather than mining and were rejected on that
   number alone. Chopping is the mirror image, near 1200 Hz with real low end,
   because an axe into a trunk is a woody thunk with a crack on top.

3. FORAGING gets its own sound. The call site is
   `nd.skill === 'MINING' ? 'mine' : 'chop'`, so picking a herb has always
   played the AXE. Now stems and leaves and a shake of soil instead.

TIMBER, the falling tree, moves off its sawtooth-and-noise recipe onto a real
recording of a trunk giving way and crashing through branches.

The synth recipes stay in the switch as the fallback while the decode lands,
exactly as patches 41 and 44 left them.

Bundle cost is about 72 KB of base64, of which the falling tree is 38 KB; it
is encoded at 64k rather than 96k because it is broadband crash content, the
same reason the campfire bed is 64k. When the sprite loader arrives in the
sound project's Phase 0 these move out of the bundle entirely.

Two anchored edits:
  1. the gathering block appended to SFX_SAMPLES, taken from the module
  2. a variant-aware intercept in sfx(), plus foraging getting its own name
"""
import io, os

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# 1. the samples, straight from the module
# ---------------------------------------------------------------------------
m0 = mod.find('  // -- gathering (patch 53.417)')
assert m0 > 0, 'gathering block missing from model-lab/sfx-samples.js'
m1 = mod.find('\n};', m0)
assert m1 > 0
block = mod[m0:m1]
block = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in block.split('\n'))

b0 = s.find('    // -- combat one-shots')
assert b0 > 0, 'combat block not found in bundle'
b1 = s.find('\n    };', b0)
assert b1 > 0, 'SFX_SAMPLES close not found'
s = s[:b1] + '\n' + block + s[b1:]

# ---------------------------------------------------------------------------
# 2. the intercept. Rotating variants, so a tree never repeats a sound.
# ---------------------------------------------------------------------------
A2 = """    // Impacts pick their sample from what was actually hit, and a crit is the
    // impact PLUS a bright ring 15 ms behind it so the blow still lands first."""
assert s.count(A2) == 1, 'sfx intercept anchor matched %d times' % s.count(A2)
s = s.replace(A2, """    // Gathering. Rotating variants rather than one sample, because these fire
    // once a swing and many swings a node: a single retriggered clip is the
    // giveaway. Rotation plus a per-play detune means a whole tree never
    // repeats itself.
    const GVAR = { chop: 3, mine: 3 };
    if (GVAR[name] && this._samples && this._samples.ready()) {
      this._gAlt = (this._gAlt || 0) + 1;
      const pick = name + '-' + 'abc'[this._gAlt % GVAR[name]];
      if (this._samples.has(pick)) {
        this._samples.play(pick, { gain: name === 'mine' ? 0.62 : 0.7,
                                   detune: (Math.random() * 2 - 1) * 80 });
        return;
      }
    }
    if ((name === 'forage' || name === 'timber') && this._samples
        && this._samples.ready() && this._samples.has(name)) {
      this._samples.play(name, { gain: name === 'timber' ? 0.8 : 0.6,
                                 detune: (Math.random() * 2 - 1) * 60 });
      return;
    }
    // Impacts pick their sample from what was actually hit, and a crit is the
    // impact PLUS a bright ring 15 ms behind it so the blow still lands first.""")

# ---------------------------------------------------------------------------
# 3. foraging stops borrowing the axe
# ---------------------------------------------------------------------------
A3 = "this.sfx(nd.skill === 'MINING' ? 'mine' : 'chop');"
assert s.count(A3) == 1, 'gathering call site matched %d times' % s.count(A3)
s = s.replace(A3, "this.sfx(nd.skill === 'MINING' ? 'mine' : nd.skill === 'FORAGING' ? 'forage' : 'chop');")

# The synth switch has no 'forage' case, so give the fallback one rather than
# letting a browser that cannot decode our mp3 pick herbs in silence.
A4 = "      case 'switch':"
assert s.count(A4) == 1, 'synth switch anchor matched %d times' % s.count(A4)
s = s.replace(A4, """      case 'forage': this.hiss({ f: 2600, f1: 900, t: 0.18, g: 0.14, q: 1.2 }); break;
      case 'switch':""")

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 53.417: chop, mine, forage and timber are sampled')
