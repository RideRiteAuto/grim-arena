#!/usr/bin/env python3
"""Patch 58.641: chain lightning stops being a sword, and arrows hit the world.

The two things left on placeholders after 55.283, plus one collision between
the two audio tracks that had to be resolved before either could be right.

1. CHAIN LIGHTNING was the last spell still wearing the sword's clothes.
   fireStorm resolved every link through applyDamage with kind 'crit', so a
   bolt of lightning played the SWORD crit, and then finished with an explicit
   this.sfx('crit') on top of it. The cast fell through to the generic synth
   hum. Two real sounds now: a spark gap accelerating on the wind up, and a
   close strike on each link.

   The damage kind stays 'crit' on purpose. It drives the splat styling and the
   crit damage numbers, and changing it to make a SOUND different would be the
   sound track reaching into combat feel for no reason. The routing keys off a
   new opt.storm flag instead, which is additive and cannot affect anything
   else.

   Links are staggered in the AUDIO only. All three fire in the same frame,
   matching the visuals, but three identical cracks at the same instant read as
   one loud crack rather than as a chain. 55 ms apart, which is enough to hear
   as separate arrivals and short enough to still be one event.

2. ARROWS NOW HIT THE WORLD. Kevin asked for the sound of an arrow sticking
   into a wooden wall and the shaft vibrating, and the honest answer last round
   was that there was nowhere to hang it: arrows only ever resolved against
   entities. This adds the hook.

   THIS IS A GAMEPLAY CHANGE and it is flagged as one. Until now an arrow flew
   through keep walls, houses and tree trunks. Now it stops, sticks and stays
   stuck for a few seconds. ARROWS_HIT_WORLD below is the one-line revert.

   The test is against this.colliders, which the player already collides with,
   so an arrow stops at exactly the things you cannot walk through. Those
   records are infinite height in XZ, which would otherwise mean an arrow lobbed
   over a roof struck the building; hence the height gate. Only 'arrow' is
   affected. Magic still passes through, which is a balance question rather than
   a sound one and not mine to change.

   A stuck arrow deals no further damage: it skips the target sweep entirely.

3. THE sfx() SIGNATURE COLLISION, which had to be fixed first. Patch 55.283
   made the second argument the entity a sound belongs to, so distance could be
   measured from it. The other audio track then shipped this.sfx('oredeplete',
   0.22), using the same argument as a DELAY IN SECONDS. Both shipped. Nothing
   crashed only because sfxAtten_ guards on t.pos, so a number fell through to
   no attenuation by luck.

   Luck is not a design. The signature becomes sfx(name, t, delay): t is what
   the sound belongs to, delay is when. Their four call sites are updated to the
   explicit form, and while they are being touched they get a source position,
   which they never had. A tree felled on the far side of the map was playing at
   full volume in your ear, which is the exact complaint Kevin already made
   about arrows.

Eleven anchored edits.
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


def sub(anchor, new, label):
    global s
    one(anchor, label)
    s = s.replace(anchor, new)


# ---------------------------------------------------------------------------
# 1. the samples
# ---------------------------------------------------------------------------
m0 = mod.find('  // -- chain lightning, and an arrow meeting something solid (patch 58.641)')
assert m0 > 0, 'storm/arrow block missing from model-lab/sfx-samples.js'
m1 = mod.find('\n};', m0)
assert m1 > 0
block = '\n'.join(('  ' + ln) if ln.strip() else '' for ln in mod[m0:m1].split('\n'))

# Anchor on the declaration and walk to its close rather than on a sample key.
# The gathering track re-emits this object, and when it did the key indentation
# changed from six spaces to four; an anchor on a key silently found nothing
# and the block went in at the wrong place.
d0 = s.find('    const SFX_SAMPLES = {')
assert d0 > 0, 'SFX_SAMPLES declaration not found'
b1 = s.find('\n    };', d0)
assert b1 > d0, 'SFX_SAMPLES close not found'
s = s[:b1] + '\n' + block + s[b1:]

# ---------------------------------------------------------------------------
# 2. sfx(name, t, delay). Resolves the collision between the two audio tracks.
# ---------------------------------------------------------------------------
sub("""  sfx(name, t) {
    const att = this.sfxAtten_(t);
    if (att <= 0.02) return;          // too far to be part of the world mix
    this._att = att;
    try { this.sfxVoice_(name, t); } finally { this._att = 1; }
  }

  sfxVoice_(name, t) {""",
    """  /* Two tracks arrived at this signature from opposite directions. 55.283 made
     the second argument the ENTITY a sound belongs to, so distance could be
     measured from it. The gathering work then shipped sfx('oredeplete', 0.22),
     using the same argument as a DELAY IN SECONDS. Both are live. Nothing
     broke only because sfxAtten_ guards on t.pos, so a bare number fell
     through to no attenuation by accident.
     Third argument, and the attenuation source is only ever read from an
     object, so a number can never be mistaken for a place. */
  sfx(name, t, delay) {
    const src = (t && typeof t === 'object') ? t : null;
    const att = this.sfxAtten_(src);
    if (att <= 0.02) return;          // too far to be part of the world mix
    this._att = att;
    try { this.sfxVoice_(name, t, delay); } finally { this._att = 1; }
  }

  sfxVoice_(name, t, delay) {""", 'sfx wrapper')

# ---------------------------------------------------------------------------
# 3. the gathering one-shots read the explicit delay, not the second argument
# ---------------------------------------------------------------------------
sub("""        this._samples.play(nv[0], { gain: nv[1], detune: (Math.random() * 2 - 1) * nv[2],
                                    when: t ? this.ac.currentTime + t : undefined });""",
    """        this._samples.play(nv[0], { gain: nv[1], detune: (Math.random() * 2 - 1) * nv[2],
                                    when: delay ? this.ac.currentTime + delay : undefined });""",
    'NAT delay')

# ---------------------------------------------------------------------------
# 4. and their call sites say where the sound is, so distance applies. A tree
#    felled across the map was playing at full volume in your ear.
# ---------------------------------------------------------------------------
# The gathering track guards both of these on p, and returns early when it is
# missing, so p is always a real position by the time the sound plays.
sub("""        this.sfx('orechip');
        this.sfx('oredeplete', 0.22);""",
    """        this.sfx('orechip', { pos: p });
        this.sfx('oredeplete', { pos: p }, 0.22);""", 'ore call sites')

sub("""      this.fx.push({ kind: 'fall', mesh: fm, life: 5.4, max: 5.4, big: R.kind !== 'tree' });
      this.sfx('treefell');""",
    """      this.fx.push({ kind: 'fall', mesh: fm, life: 5.4, max: 5.4, big: R.kind !== 'tree' });
      this.sfx('treefell', { pos: p });""", 'treefell call site')

sub("            if (f.big) this.sfx('treeimpact');",
    "            if (f.big) this.sfx('treeimpact', f.mesh ? { pos: f.mesh.position } : null);",
    'treeimpact call site')

# ---------------------------------------------------------------------------
# 5. the storm samples, and the chain stagger
# ---------------------------------------------------------------------------
sub("""    const SPELL = {
      'sp-fire-cast': 0.80, 'sp-fire-hit': 0.85,
      'sp-frost-cast': 0.75, 'sp-frost-hit': 0.80,
      'sp-heal-cast': 0.60, 'sp-heal-apply': 0.70
    };
    if (SPELL[name] !== undefined) {
      if (SP && SP.ready() && SP.has(name)) {
        SP.play(name, { gain: SPELL[name], detune: (Math.random() * 2 - 1) * 50 });
        return;""",
    """    const SPELL = {
      'sp-fire-cast': 0.80, 'sp-fire-hit': 0.85,
      'sp-frost-cast': 0.75, 'sp-frost-hit': 0.80,
      'sp-heal-cast': 0.60, 'sp-heal-apply': 0.70,
      'sp-storm-cast': 0.70, 'sp-storm-hit': 0.85
    };
    if (SPELL[name] !== undefined) {
      if (SP && SP.ready() && SP.has(name)) {
        /* Chain lightning resolves all three links in one frame, matching the
           visuals. Three identical cracks at the same instant read as one loud
           crack rather than as a chain, so each link after the first is nudged
           back 55 ms: far enough apart to hear as separate arrivals, close
           enough to still be one event. */
        let when;
        if (name === 'sp-storm-hit') {
          const now = this.ac.currentTime;
          const run = (this._stormAt && now - this._stormAt < 0.30) ? (this._stormN || 0) + 1 : 0;
          this._stormAt = now; this._stormN = run;
          when = now + run * 0.055;
        }
        SP.play(name, { gain: SPELL[name], detune: (Math.random() * 2 - 1) * 50, when: when });
        return;""", 'SPELL map')

# ---------------------------------------------------------------------------
# 6. arrow surfaces: the wall and the ground get their own sounds
# ---------------------------------------------------------------------------
sub("""    if (name === 'arrow-hit') {
      const an = 'arrow-' + (this.hitMat_(t) === 'plate' ? 'plate' : 'flesh');""",
    """    /* An arrow that hit the world rather than a creature. mat comes from the
       collider when one declares it, so any track adding a stone or metal
       collider only has to set mat and the right sound follows; wood is the
       fallback because everything solid in the world today is a trunk, a
       plank or a crate. */
    const SURF = { 'arrow-wood': 0.55, 'arrow-dirt': 0.34 };
    if (SURF[name] !== undefined) {
      if (SP && SP.ready() && SP.has(name)) {
        SP.play(name, { gain: SURF[name], detune: (Math.random() * 2 - 1) * 110 });
        return;
      }
      name = 'chop';
    }
    if (name === 'arrow-hit') {
      const an = 'arrow-' + (this.hitMat_(t) === 'plate' ? 'plate' : 'flesh');""", 'arrow surface routing')

# ---------------------------------------------------------------------------
# 7. the storm cast, on the wind up
# ---------------------------------------------------------------------------
sub("      snare: 'cast', storm: 'cast',",
    "      snare: 'cast', storm: 'sp-storm-cast',", 'MSFX storm')

# ---------------------------------------------------------------------------
# 8. fireStorm: flag the link, and drop the sword crit that sat on top of it
# ---------------------------------------------------------------------------
sub("      this.applyDamage(a, n, i === 0 ? 34 : 21, 'crit', p, { magic: true, style: 'MAGIC' });",
    """      /* kind stays 'crit': it drives the splat styling and the crit damage
         number, and changing combat feel to fix a SOUND would be the wrong
         trade. opt.storm is additive and only the audio reads it. */
      this.applyDamage(a, n, i === 0 ? 34 : 21, 'crit', p,
        { magic: true, style: 'MAGIC', storm: true });""", 'fireStorm applyDamage')

sub("""    this.shake = Math.min(1, this.shake + 0.35);
    this.sfx('crit');
  }""",
    """    this.shake = Math.min(1, this.shake + 0.35);
    /* The sword crit used to play here, on top of the sword crit each link was
       already triggering through the impact funnel. Both are gone: the links
       carry the sound now, each at its own target, so a chain that reaches
       something far away is quieter at the far end. */
  }""", 'fireStorm trailing sfx')

# ---------------------------------------------------------------------------
# 9. the impact funnel learns about storm
# ---------------------------------------------------------------------------
sub("""    this.sfx(broke ? 'break' : perfect ? 'parry' : blocked ? 'block'
      : kind === 'frost' ? 'sp-frost-hit'
      : kind === 'fire' ? 'sp-fire-hit'
      : (kind === 'arrow' || opt.style === 'RANGED') ? 'arrow-hit'
      : kind === 'crit' ? 'crit' : 'hit', t);""",
    """    this.sfx(broke ? 'break' : perfect ? 'parry' : blocked ? 'block'
      : opt.storm ? 'sp-storm-hit'
      : kind === 'frost' ? 'sp-frost-hit'
      : kind === 'fire' ? 'sp-fire-hit'
      : (kind === 'arrow' || opt.style === 'RANGED') ? 'arrow-hit'
      : kind === 'crit' ? 'crit' : 'hit', t);""", 'impact funnel storm')

# ---------------------------------------------------------------------------
# 10. the arrow/world test itself
# ---------------------------------------------------------------------------
sub("""  stepProjectiles(dt) {
    const T = this.T;""",
    """  /* What a shot ran into, or null. Reuses this.colliders, so an arrow stops
     at exactly the things you cannot walk through, and nothing has to be
     tagged twice.
     THE HEIGHT GATE IS NOT OPTIONAL. Collider records are (x, z, radius) or
     (x, z, halfWidth, halfDepth) with no height at all: they are infinite
     columns. Without a gate, an arrow lobbed over a roof would bury itself in
     thin air above the building. Four metres covers a wall, a trunk, a crate
     and a boulder, and anything higher than that is flying over. */
  shotSurface_(pos) {
    if (!this.colliders || !this.colliders.length) return null;
    const gy = (this.worldOn && this.mode === 'ai') ? this.groundY(pos.x, pos.z) : 0;
    if (pos.y - gy > 4.0) return null;
    for (let i = 0; i < this.colliders.length; i++) {
      const c = this.colliders[i];
      const dx = pos.x - c.x, dz = pos.z - c.z;
      if (c.r) { if (dx * dx + dz * dz < c.r * c.r) return c; }
      else if (Math.abs(dx) < c.hw && Math.abs(dz) < c.hd) return c;
    }
    return null;
  }

  stepProjectiles(dt) {
    const T = this.T;
    /* GAMEPLAY CHANGE, and the one line that reverts it. Until this landed an
       arrow flew straight through keep walls, houses and tree trunks. Kevin
       asked for the sound of one sticking into a wooden wall, and there was
       nowhere to hang that sound because nothing ever told a shot it had hit
       the world. Arrows only: magic still passes through, which is a balance
       question rather than a sound one. */
    const ARROWS_HIT_WORLD = true;""", 'stepProjectiles head')

sub("""      const p = this.projectiles[i];
      p.mesh.position.addScaledVector(p.vel, dt);""",
    """      const p = this.projectiles[i];
      /* A stuck arrow is scenery: it does not move, and it cannot hurt anyone,
         so it skips the target sweep entirely rather than sitting inside a
         wall dealing damage to whatever wanders past. */
      if (p.stuck) {
        p.life -= dt;
        if (p.life <= 0) { this.scene.remove(p.mesh); this.projectiles.splice(i, 1); }
        continue;
      }
      p.mesh.position.addScaledVector(p.vel, dt);
      if (ARROWS_HIT_WORLD && p.kind === 'arrow') {
        const surf = this.shotSurface_(p.mesh.position);
        if (surf) {
          /* Back it up along its own flight so the shaft stands proud of the
             surface instead of vanishing inside it. */
          p.mesh.position.addScaledVector(p.vel, -dt * 0.55);
          p.stuck = true; p.life = 5.0; p.vel.set(0, 0, 0);
          this.sfx(surf.mat === 'stone' ? 'arrow-hit' : 'arrow-wood',
                   { pos: p.mesh.position.clone() });
          this.spark(p.mesh.position.clone(), 0xd8c9a0, 4);
          continue;
        }
      }""", 'arrow world test')

# ---------------------------------------------------------------------------
# 11. and the ground, which already ended an arrow's flight in silence
# ---------------------------------------------------------------------------
sub("""        this.spark(p.mesh.position.clone(), p.kind === 'frost' ? 0x9fdcff : p.kind === 'fire' ? 0xffa050 : p.kind === 'snare' ? 0x8fefaf : p.kind === 'toxin' ? 0x6fdf3f : 0xd8c9a0, hit ? 12 : 5);""",
    """        /* An arrow reaching the dirt already ended its flight here, silently.
           It is the most common way a shot ends and it made no sound at all. */
        if (!hit && p.kind === 'arrow' && p.life > 0) {
          this.sfx('arrow-dirt', { pos: p.mesh.position.clone() });
        }
        this.spark(p.mesh.position.clone(), p.kind === 'frost' ? 0x9fdcff : p.kind === 'fire' ? 0xffa050 : p.kind === 'snare' ? 0x8fefaf : p.kind === 'toxin' ? 0x6fdf3f : 0xd8c9a0, hit ? 12 : 5);""",
    'arrow ground sound')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 58.641 applied')
