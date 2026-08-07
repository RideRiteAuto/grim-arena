#!/usr/bin/env python3
"""Patch 55.283: spells stop sounding like swords, and the world gets distance.

Kevin's review, in his words, and what each line turned out to be:

  "the swinging action still has this weird metallic swoosh ... when you're
   moving an axe or a pickaxe through the air, it doesn't really make any
   sound"
      startMove() routed every move it did not explicitly name to 'swing',
      the sword whoosh. Chopping and mining are moves. So was casting.

  "I didn't notice any sound changes with magic ... some of the sounds for
   magic actually still sound like sword swings and sword hits"
      Because they WERE sword sounds. Fire landing resolved to 'crit', the
      sword crit. Casting heal or chain lightning fell through to 'swing'.
      Healing played 'pickup', the item chime. Nothing about the spell voice
      was ever a spell.

  "it's super loud, and it sounds as if they're right next to you even though
   I'm shooting arrows across the map"
      Nothing in the game attenuated with distance. Every sound in the world
      was mixed at the listener's ear regardless of where it happened. That is
      the real bug behind the arrow complaint, and it was making every distant
      fight, campfire hit and NPC brawl fight the mix.

Five things happen here.

1. DISTANCE. sfx() becomes a thin wrapper that measures how far the sound is
   from the player, sets a per-call attenuation, and delegates to the old body
   (renamed sfxVoice_). tone(), hiss() and the sample player all read that one
   number, so a single change attenuates the entire voice instead of each of
   forty synth recipes needing to know about it. Beyond 46 m a world sound is
   simply not played.

   The curve is inverse distance (near 7 m, so anything within arm's reach of
   the camera is unattenuated) with the last quarter of the range faded to
   nothing, so a sound thins out as you walk away instead of cutting off.

2. THE HIT MARKER. Kevin asked for feedback at range without the noise:
   "maybe I'll just hear some sort of a hit marker just to register that you
   hit". A blow YOU landed out of earshot plays a short quiet tick at a FIXED
   level, because it is feedback about you rather than an event in the world.
   A blow between two NPCs across the map stays silent, which is the point.

3. MOVE ROUTING. The catch-all ternary becomes an explicit table. A tool
   through air makes nothing at all, which is Kevin's call and is right: the
   axe bite carries the swing. Sword attacks finally reach the recorded swing
   and heavy samples they have been bypassing since patch 41, because they
   were routed to the synth 'slash' the whole time.

4. SPELLS. Six new samples, wired at the moments they belong to. The cast
   sound sits on the projectile leaving the hand (fireFrost) rather than on
   the wind up, so it lands with the visual. Impacts get their own names so a
   fireball landing can never resolve to the sword crit again. Chain lightning
   has no bespoke sample yet, so it moves off the SWORD SWING onto the synth
   cast, which is a strict improvement and is flagged rather than hidden.

5. ARROWS. Their own impact, picked by what was hit through the existing
   hitMat_ resolver, and deliberately quiet: 0.42 against the sword hit's 0.8.
   Kevin asked for a dull thud on flesh and explicitly not gore, and the flesh
   take was selected on measurement, spectral centroid 205 Hz with 95 percent
   of its energy under 400 Hz, the dullest of the batch.

NOT DONE, and deliberately not guessed at: an arrow sticking into scenery.
Kevin asked for it, but arrows only ever resolve against entities in this
build; there is no collision against walls or trees to hang a sound on. That
is a gameplay hook someone has to add first.

Nine anchored edits.
"""
import io, os

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()


def one(anchor, label):
    n = s.count(anchor)
    assert n == 1, '%s matched %d times' % (label, n)


def indent(block, pad):
    return '\n'.join((pad + ln) if ln.strip() else '' for ln in block.split('\n'))


# ---------------------------------------------------------------------------
# 1. the new samples, straight from the module
# ---------------------------------------------------------------------------
m0 = mod.find('  // -- spells and arrow impacts (patch 55.283)')
assert m0 > 0, 'spell block missing from model-lab/sfx-samples.js'
m1 = mod.find('\n};', m0)
assert m1 > 0
block = indent(mod[m0:m1], '  ')

b0 = s.find('    // -- gathering (patch 53.417)')
assert b0 > 0, 'gathering block not found in bundle'
b1 = s.find('\n    };', b0)
assert b1 > 0, 'SFX_SAMPLES close not found'
s = s[:b1] + '\n' + block + s[b1:]

# ---------------------------------------------------------------------------
# 2. the falling tree, replaced. Kevin: "it sounds a little too electronic."
#    The new take was chosen for low end weight; the thin bright candidates
#    are exactly the ones that read as synthetic.
# ---------------------------------------------------------------------------
t0 = mod.find("\n  'timber':")
t1 = mod.find("\n\n  // -- spells", t0)
assert t0 > 0 and t1 > t0, 'timber not found in module'
newtimber = indent(mod[t0 + 1:t1], '  ')

o0 = s.find("\n      'timber':")
assert o0 > 0, 'timber not found in bundle'
o1 = s.find("\n\n", o0)
assert o1 > o0
assert s.count("\n      'timber':") == 1, 'timber matched more than once'
s = s[:o0 + 1] + newtimber + s[o1:]

# ---------------------------------------------------------------------------
# 3. sfx() becomes the distance wrapper; the old body becomes sfxVoice_
# ---------------------------------------------------------------------------
A3 = """  sfx(name, t) {
    if (!this.started) return;   // the menu stays silent"""
one(A3, 'sfx head')
s = s.replace(A3, """  // Every world sound is heard from where the player is standing. Until this
  // landed nothing attenuated at all, so an arrow burying itself in something
  // across the map was mixed exactly as loud as one at your feet, which is
  // what Kevin heard. `t` is the entity the sound belongs to; with no entity
  // the sound is the player's own and plays dry.
  sfxAtten_(t) {
    if (!t || !t.pos || !this.me || !this.me.pos || t === this.me) return 1;
    const dx = t.pos.x - this.me.pos.x, dz = t.pos.z - this.me.pos.z;
    const d = Math.sqrt(dx * dx + dz * dz);
    const NEAR = 7, FAR = 46;
    if (d <= NEAR) return 1;
    if (d >= FAR) return 0;
    /* inverse distance, with the last quarter of the range faded out so a
       sound thins away as you walk off rather than cutting mid tail */
    return (NEAR / d) * Math.min(1, (FAR - d) / (FAR * 0.25));
  }

  // Feedback at range, not an event in the world: a blow YOU landed out of
  // earshot still reports itself, quietly and at a fixed level. Deliberately
  // not attenuated, and deliberately not fired for fights you are not in.
  hitMark_() {
    const now = this.ac ? this.ac.currentTime : 0;
    if (this._markAt && now - this._markAt < 0.05) return;
    this._markAt = now;
    this.tone({ type: 'sine', f: 1480, t: 0.045, g: 0.05, a: 0.004 });
  }

  sfx(name, t) {
    const att = this.sfxAtten_(t);
    if (att <= 0.02) return;          // too far to be part of the world mix
    this._att = att;
    try { this.sfxVoice_(name, t); } finally { this._att = 1; }
  }

  sfxVoice_(name, t) {
    if (!this.started) return;   // the menu stays silent""")

# ---------------------------------------------------------------------------
# 4 and 5. tone() and hiss() read the attenuation. One place each, so every
#    synth recipe in the switch inherits distance without being touched.
# ---------------------------------------------------------------------------
A4 = "    g.gain.exponentialRampToValueAtTime(o.g || 0.2, t0 + (o.a || 0.008));"
one(A4, 'tone gain ramp')
s = s.replace(A4, "    g.gain.exponentialRampToValueAtTime("
                  "Math.max(0.0002, (o.g || 0.2) * (this._att === undefined ? 1 : this._att)), "
                  "t0 + (o.a || 0.008));")

A5 = "    g.gain.exponentialRampToValueAtTime(o.g || 0.2, t0 + (o.a || 0.01));"
one(A5, 'hiss gain ramp')
s = s.replace(A5, "    g.gain.exponentialRampToValueAtTime("
                  "Math.max(0.0002, (o.g || 0.2) * (this._att === undefined ? 1 : this._att)), "
                  "t0 + (o.a || 0.01));")

# ---------------------------------------------------------------------------
# 6. the sample player takes the same attenuation, so samples and synth agree
# ---------------------------------------------------------------------------
A6 = "    function makeSamplePlayer(ac, dest, samples) {"
one(A6, 'makeSamplePlayer signature')
s = s.replace(A6, "    function makeSamplePlayer(ac, dest, samples, att) {")

A6b = "          g.gain.value = opt.gain === undefined ? 1 : opt.gain;"
one(A6b, 'sample player gain')
s = s.replace(A6b, "          g.gain.value = (opt.gain === undefined ? 1 : opt.gain)\n"
                   "                       * (att ? att() : 1);")

A6c = "      this._samples = makeSamplePlayer(this.ac, this.master, SFX_SAMPLES);"
one(A6c, 'sample player construction')
s = s.replace(A6c, "      this._samples = makeSamplePlayer(this.ac, this.master, SFX_SAMPLES,\n"
                   "        () => (this._att === undefined ? 1 : this._att));")

# ---------------------------------------------------------------------------
# 7. spell and arrow samples, ahead of the melee impact resolver
# ---------------------------------------------------------------------------
A7 = """    // Impacts pick their sample from what was actually hit, and a crit is the
    // impact PLUS a bright ring 15 ms behind it so the blow still lands first."""
one(A7, 'impact resolver anchor')
s = s.replace(A7, """    // Spells. Six samples, and the names are distinct from the melee ones on
    // purpose: 'fire' used to resolve to the sword crit and 'frost' was doing
    // double duty as both a cast and an impact. Nothing here can collide with
    // a sword sound any more. If the decode has not landed the name falls back
    // to its old synth recipe rather than going silent.
    const SP = this._samples;
    const SPELL = {
      'sp-fire-cast': 0.80, 'sp-fire-hit': 0.85,
      'sp-frost-cast': 0.75, 'sp-frost-hit': 0.80,
      'sp-heal-cast': 0.60, 'sp-heal-apply': 0.70
    };
    if (SPELL[name] !== undefined) {
      if (SP && SP.ready() && SP.has(name)) {
        SP.play(name, { gain: SPELL[name], detune: (Math.random() * 2 - 1) * 50 });
        return;
      }
      name = name.indexOf('frost') >= 0 ? 'frost'
           : name.indexOf('heal') >= 0 ? 'pickup' : 'fire';
    }
    // Arrows land on what they hit, through the same resolver the sword uses,
    // and land QUIETLY. 0.42 against the sword's 0.8 is not a mistake: Kevin
    // asked for a dull thud rather than gore, and said it was too loud even
    // close up. Distance does the rest.
    if (name === 'arrow-hit') {
      const an = 'arrow-' + (this.hitMat_(t) === 'plate' ? 'plate' : 'flesh');
      if (SP && SP.ready() && SP.has(an)) {
        SP.play(an, { gain: an === 'arrow-plate' ? 0.50 : 0.42,
                      detune: (Math.random() * 2 - 1) * 90 });
        return;
      }
      name = 'hit';
    }
    // Impacts pick their sample from what was actually hit, and a crit is the
    // impact PLUS a bright ring 15 ms behind it so the blow still lands first.""")

# ---------------------------------------------------------------------------
# 8. move routing. The catch-all ternary becomes a table.
# ---------------------------------------------------------------------------
A8 = ("    this.sfx(name === 'frost' ? 'cast' : (name === 'light' || name === 'heavy' || "
      "name === 'bash' || name === 'claw' || name === 'bite' || name === 'glight' || "
      "name === 'gheavy') ? 'slash' : name === 'rapid' ? 'draw' : 'swing');")
one(A8, 'startMove sfx ternary')
s = s.replace(A8, """    /* What a move actually sounds like. This was one ternary that sent every
       move it did not name to the sword whoosh. Chopping a tree is a move, so
       an axe through air rang like a blade: Kevin heard it and it was the
       first thing he asked to lose. A tool through air now makes NOTHING, and
       the bite of it into the trunk carries the swing on its own.
       Sword attacks were routed to the synth 'slash' this whole time, which
       means the recorded swing and heavy samples from patch 41 have never
       once played. They do now.
       Chain lightning has no sample of its own yet, so it moves off the sword
       swing onto the synth cast. Better, not finished. */
    const MSFX = {
      chop: null, gather: null,
      light: 'swing', glight: 'swing', bash: 'swing',
      heavy: 'heavy', gheavy: 'heavy',
      claw: 'slash', bite: 'slash',
      rapid: 'draw', volley: 'draw',
      frost: null,              /* fireFrost() sounds the release, not the wind up */
      snare: 'cast', storm: 'cast',
      heal: 'sp-heal-cast'
    };
    const msfx = Object.prototype.hasOwnProperty.call(MSFX, name) ? MSFX[name] : 'swing';
    if (msfx) this.sfx(msfx, e);""")

# ---------------------------------------------------------------------------
# 9. the cast itself, on the projectile leaving the hand
# ---------------------------------------------------------------------------
A9 = "this.sfx(fire ? 'fire' : 'frost');"
one(A9, 'fireFrost cast sfx')
s = s.replace(A9, "this.sfx(fire ? 'sp-fire-cast' : 'sp-frost-cast', a);")

# ---------------------------------------------------------------------------
# 10. the impact funnel. fire stops resolving to the sword crit, arrows get
#     their own voice, and a blow you landed out of earshot still marks.
# ---------------------------------------------------------------------------
A10 = ("    this.sfx(broke ? 'break' : perfect ? 'parry' : blocked ? 'block' : "
       "kind === 'frost' ? 'frost' : kind === 'fire' ? 'crit' : kind === 'crit' ? 'crit' : 'hit', t);")
one(A10, 'impact funnel')
s = s.replace(A10, """    /* 'fire' resolved to 'crit', the SWORD crit, which is most of what Kevin
       meant by magic still sounding like sword hits. Anything ranged is tested
       before the crit branch on purpose: a critical arrow was picking up the
       sword's bright ring, and a ringing sword is not what an arrow does. */
    this.sfx(broke ? 'break' : perfect ? 'parry' : blocked ? 'block'
      : kind === 'frost' ? 'sp-frost-hit'
      : kind === 'fire' ? 'sp-fire-hit'
      : (kind === 'arrow' || opt.style === 'RANGED') ? 'arrow-hit'
      : kind === 'crit' ? 'crit' : 'hit', t);
    /* Out of earshot, but it was YOUR blow, so it still registers. */
    if (from === this.me && this.sfxAtten_(t) <= 0.02) this.hitMark_();""")

# ---------------------------------------------------------------------------
# 11. healing stops playing the item pickup chime
# ---------------------------------------------------------------------------
for amt in ('65', '70'):
    A = "'+%s', 'heal'); this.sfx('pickup');" % amt
    one(A, 'heal +%s sfx' % amt)
    s = s.replace(A, "'+%s', 'heal'); this.sfx('sp-heal-apply');" % amt)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 55.283 applied')
