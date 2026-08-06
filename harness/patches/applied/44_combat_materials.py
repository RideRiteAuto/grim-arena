#!/usr/bin/env python3
"""Patch 44: swing that misses, per-material hits, and a crit that rings.

Kevin's review of patch 43, in his words: the swing "doesn't even sound like a
swing anymore", the hit "almost sounds like a punch" when it should be a sword
on armour, and the crit is dull, "like you dropped a trash can", when hearing
it should feel good. He also asked whether hits should differ by what the
target is wearing. They should.

Three changes:

1. SWING is regenerated as a genuine miss. Nothing is struck.

2. HITS BECOME PER MATERIAL. combat-hit-flesh / -leather / -plate, chosen at
   the call site by hitMat_(). Resolution order is deliberate:
     - an explicit t.mat wins, so an armoured NPC added later declares itself
       and needs no code change here
     - a player reads from what they are actually WEARING
     - a monster falls back to its tag: goblins are leather, everything else
       in the bestiary is bare flesh
   Nothing in the bestiary carries armour today, so flesh and leather are what
   actually play in the live game. plate is groundwork.

3. CRIT BECOMES A LAYER. The material impact plays, and combat-crit-ring is
   laid over it 15 ms later so the impact still reads first. The ring is
   almost pure high end, so it adds shine rather than mud, and a crit sounds
   like a crit whatever it lands on. This also means armoured enemies do not
   need their own crit samples, ever.

sfx() grows an optional second argument carrying the target. Every existing
one-argument call is untouched and behaves exactly as before.

The old combat-hit and combat-crit samples are gone from the table, so if the
material samples ever fail to decode the fallback is the synthesised voice,
which is the same safety net patch 41 shipped with.

Three anchored edits:
  1. the combat block inside SFX_SAMPLES, regenerated from the module
  2. hitMat_(), added next to sfx()
  3. sfx(): the material/crit intercept, and hit/crit out of the CSAMP table
"""
import io, os

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# 1. the samples, straight from the module so nothing is ever retyped
# ---------------------------------------------------------------------------
m0 = mod.find('  // -- combat one-shots (41, v2 in 43, materials')
assert m0 > 0, 'patch 44 combat block missing from model-lab/sfx-samples.js'
m1 = mod.find('\n};', m0)
assert m1 > 0
block = mod[m0:m1]
block = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in block.split('\n'))

b0 = s.find('// -- combat one-shots')
assert b0 > 0, 'existing combat block not found in bundle'
b0 = s.rfind('\n', 0, b0) + 1
b1 = s.find('\n    };', b0)
assert b1 > 0 and b1 - b0 < 120000, 'combat block close not where expected'
s = s[:b0] + block + s[b1:]

# ---------------------------------------------------------------------------
# 2. the material resolver, parked right before sfx()
# ---------------------------------------------------------------------------
A2 = "  sfx(name) {\n"
assert s.count(A2) == 1, 'sfx() definition matched %d times' % s.count(A2)
s = s.replace(A2, """  // Which impact sample fits this target. An explicit t.mat wins, so an
  // armoured NPC added later only has to declare itself. Players are read from
  // what they are wearing. Monsters fall back to their tag, and the bestiary
  // is currently all bare flesh apart from goblins.
  hitMat_(t) {
    if (!t) return 'flesh';
    if (t.mat) return t.mat;
    const worn = (t === this.me) ? this.worn : t.worn;
    if (worn) {
      let best = 'flesh';
      for (const k in worn) {
        const c = worn[k];
        if (!c) continue;
        const n = String(c.item || '').toUpperCase();
        if (/PLATE|MAIL|STEEL|IRON|OBSIDIAN|MASTERWORK/.test(n)) return 'plate';
        if (/LEATHER|HIDE|GUARD|BOOT/.test(n)) best = 'leather';
      }
      return best;
    }
    if (t._peerId) return 'leather';   // a remote player whose kit we do not hold
    if (t.goblin || (t.tags && t.tags.goblin)) return 'leather';
    return 'flesh';
  }

  sfx(name, t) {
""")

# ---------------------------------------------------------------------------
# 3. the intercept. hit and crit leave CSAMP and go through the resolver.
# ---------------------------------------------------------------------------
A3 = """    const CSAMP = {
      swing: ['combat-swing', 0.5, 60], heavy: ['combat-heavy', 0.5, 60],
      hit: ['combat-hit', 0.8, 70], crit: ['combat-crit', 1.0, 70],
      block: ['combat-block', 0.7, 50], parry: ['combat-parry', 0.5, 40]
    };"""
assert s.count(A3) == 1, 'CSAMP anchor matched %d times' % s.count(A3)
s = s.replace(A3, """    // Impacts pick their sample from what was actually hit, and a crit is the
    // impact PLUS a bright ring 15 ms behind it so the blow still lands first.
    const S0 = this._samples;
    if ((name === 'hit' || name === 'crit') && S0 && S0.ready()) {
      const mat = 'combat-hit-' + this.hitMat_(t);
      if (S0.has(mat)) {
        const crit = (name === 'crit');
        S0.play(mat, { gain: crit ? 0.9 : 0.8, detune: (Math.random() * 2 - 1) * 70 });
        if (crit && S0.has('combat-crit-ring')) {
          S0.play('combat-crit-ring', {
            gain: 0.5, detune: (Math.random() * 2 - 1) * 45,
            when: this.ac.currentTime + 0.015
          });
        }
        return;
      }
    }
    const CSAMP = {
      swing: ['combat-swing', 0.5, 60], heavy: ['combat-heavy', 0.5, 60],
      block: ['combat-block', 0.7, 50], parry: ['combat-parry', 0.5, 40]
    };""")

# ---------------------------------------------------------------------------
# 4. the damage funnel hands the target over
# ---------------------------------------------------------------------------
A4 = ("    this.sfx(broke ? 'break' : perfect ? 'parry' : blocked ? 'block' : "
      "kind === 'frost' ? 'frost' : kind === 'fire' ? 'crit' : kind === 'crit' ? 'crit' : 'hit');")
assert s.count(A4) == 1, 'damage funnel sfx call matched %d times' % s.count(A4)
s = s.replace(A4, ("    this.sfx(broke ? 'break' : perfect ? 'parry' : blocked ? 'block' : "
                   "kind === 'frost' ? 'frost' : kind === 'fire' ? 'crit' : kind === 'crit' ? 'crit' : 'hit', t);"))

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 44: material hits, layered crit, swing that misses')
