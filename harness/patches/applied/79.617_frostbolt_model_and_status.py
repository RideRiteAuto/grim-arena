#!/usr/bin/env python3
"""Patch 79.617: the frost bolt reskin, and the "hit with frost" rework.

Kevin's ask, in full: give frost bolt the fireball's treatment - a real
high-quality projectile, glow and particles, cast/hit sound. Then, on the
gameplay side: a frozen ice block appears at a target's feet when they are
hit with frost; 25 percent of the time it actually roots them (down from
today's 100 percent), for 1.5 seconds (down from today's 2), and then the
block disappears with the freeze. Separately: EVERY frost hit slows the
target by 15 percent, whether or not that hit also freezes.

Five pieces, all touching model-lab/frostbolt.js and the same handful of
combat functions, shipped together:

1. THE MODEL. model-lab/frostbolt.js builds two kits: makeFrostboltKit (the
   flying bolt - a forward-leading cluster of tapered ice shards, reusing
   grim-kit's flameMat tuned cold and near-rigid rather than a new shader,
   plus a frost-mist trail off driftMat/driftField) and makeIceBlockKit (the
   ground effect - three overlapping roughened low-poly chunks, a nested
   glow core, a frost-mist burst and a draped ground pool). Both are inlined
   into one lazily-built frostKits() method, the same "read the lab module,
   wrap it into a class method" recipe as fireballKit() from 72.319, sharing
   one copy of the grim-kit primitives both kits need rather than two.
   fireFrost's frost branch swaps the flat icosahedron for frostKits().bolt,
   mirroring exactly how the fire branch already uses fireballKit().

2. THE FREEZE ROLL. applyDamage's `opt.freeze` block went from an
   unconditional t.frozen = 2 to a 25 percent roll landing t.frozen = 1.5.
   freezeCd (6s, anti-chain-freeze) is untouched - it already existed and
   still does its job regardless of how often the roll succeeds.

3. THE ICE BLOCK. Only spawns on a SUCCESSFUL freeze roll (this is one
   event, not two: the block IS the freeze landing, not a separate visual
   for every hit) via a new fx kind 'iceblock' driven by stepFx, given a
   life equal to the freeze duration so the block and the root end in the
   same frame. iceblock's cleanup can't reuse retireFx: retireFx assumes a
   single Mesh with .geometry/.material, and the ice block is a Group of
   four child meshes (shell, glow, mist, ground pool) - calling retireFx on
   it would throw on the missing .geometry. stepFx's iceblock case disposes
   each child directly instead.

4. THE SLOW. New per-entity timer e.slowT (decays in stepFighter next to
   e.frozen, e.freezeCd and friends), set on every unblocked frost hit that
   deals damage via a new opt.chill flag threaded alongside the existing
   opt.freeze at both applyDamage call sites that already set
   `freeze: kind === 'frost'` - stepProjectiles' own-thrown-bolt hit
   resolution, and the 'hit' network path for a bolt somebody else threw
   at you. Both of the game's two speed functions (the player's own
   movement and NPC/monster AI movement) multiply speed by 0.85 while
   e.slowT > 0, the same shape as the existing e.blocking / e.state
   multipliers already sitting right next to them - not a new system.

5. SOUND: NOT TOUCHED. sp-frost-cast and sp-frost-hit already went through
   the same real-WoW-reference-matched rebuild the fireball's own sounds
   did (patches 62.519 and 63.104 - the current sp-frost-hit was built
   specifically so its tail communicates "you are now frozen", per Kevin's
   note on v2). Regenerating already-approved work is against the project's
   own standing rule; this patch reuses both samples exactly as they are.

Anchors are asserted to occur exactly once each. Re-grep fresh against a
freshly extracted bundle before reusing this number - two tracks have
collided on one before.
"""
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
KIT = os.path.join(HERE, '..', '..', 'model-lab', 'grim-kit.js')
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'frostbolt.js')

s = io.open(SRC, encoding='utf-8').read()
kit_src = io.open(KIT, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# inline grim-kit.js + frostbolt.js, same recipe as 72.319's fireball patch.
# Both kits in frostbolt.js need more of grim-kit than fireball.js did
# (roughen, glowMat, drapedDisc for the ice block), so this pulls a larger
# set - still only the names actually used, so no dead code rides along.
# ---------------------------------------------------------------------------
NEEDED_FN = ['rngFor', 'mergeParts', 'roughen', 'placed', 'tongueGeo', 'flameMat',
             'driftMat', 'driftField', 'tongueParts', 'glowMat', 'drapedDisc']
NEEDED_CONST = ['GLSL_NOISE']


def extract_export_fn(src, name):
    marker = 'export function %s(' % name
    i = src.index(marker)
    assert i >= 0, 'grim-kit.js missing export function %s' % name
    depth = 0
    j = src.index('{', i)
    k = j
    while True:
        if src[k] == '{':
            depth += 1
        elif src[k] == '}':
            depth -= 1
            if depth == 0:
                break
        k += 1
    return src[i:k + 1].replace('export function', 'function', 1) + '\n'


def extract_export_const(src, name):
    marker = 'export const %s' % name
    i = src.index(marker)
    assert i >= 0, 'grim-kit.js missing export const %s' % name
    depth = 0
    k = i
    started = False
    while True:
        ch = src[k]
        if ch in '([{':
            depth += 1; started = True
        elif ch in ')]}':
            depth -= 1
        elif ch == ';' and depth == 0 and started:
            break
        k += 1
    return src[i:k + 1].replace('export const', 'const', 1) + '\n'


kit_body = (''.join(extract_export_const(kit_src, n) for n in NEEDED_CONST)
            + ''.join(extract_export_fn(kit_src, n) for n in NEEDED_FN))

assert mod.count("export function makeFrostboltKit(T, opt) {") == 1, 'frostbolt.js bolt entry point moved'
assert mod.count("export function makeIceBlockKit(T, opt) {") == 1, 'frostbolt.js block entry point moved'
fz_body = mod.replace('export function makeFrostboltKit(T, opt) {', 'function makeFrostboltKit(T, opt) {')
fz_body = fz_body.replace('export function makeIceBlockKit(T, opt) {', 'function makeIceBlockKit(T, opt) {')
fz_body = fz_body.replace(
    "import {\n  rngFor, mergeParts, tongueParts, flameMat, driftMat, driftField,\n  placed, roughen, glowMat, drapedDisc\n} from './grim-kit.js';\n",
    '')
fz_body = fz_body.replace('/* eslint-disable no-unused-vars */\n', '')
# Strip the leading file-header comment block (a run of '//' and blank lines)
# line by line rather than with a DOTALL regex - an earlier version of this
# used `.*?` under re.S, which matches newlines too, so the "//" inside
# `(//.*\n)*` was free to swallow real code across many lines looking for the
# next blank line and ate almost the whole file. Plain line-stripping has no
# such trap.
fz_lines = fz_body.split('\n')
k = 0
while k < len(fz_lines) and (fz_lines[k].strip() == '' or fz_lines[k].startswith('//')):
    k += 1
fz_body = '\n'.join(fz_lines[k:])

BODY = kit_body + '\n' + fz_body
BODY = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in BODY.split('\n'))

# ---------------------------------------------------------------------------
# 1. frostKits(): lazily built, cached, alongside fireballKit(). Placed right
#    after fireballKit() so both spell kits sit together.
# ---------------------------------------------------------------------------
FBKIT_END = """    this._fbKit = makeFireballKit(T);
    return this._fbKit;
  }

"""
assert s.count(FBKIT_END) == 1, 'fireballKit() end anchor matched %d times' % s.count(FBKIT_END)

FROSTKITS_METHOD = '''  // ---- frost kits (bolt + ice block) ---------------------------------------
  // Built from model-lab/frostbolt.js (and grim-kit.js) by
  // harness/patches/79.617_frostbolt_model_and_status.py. Do not hand-edit
  // this block: change the lab module, look at it with
  // node harness/prop.js frostbolt, and rebuild.
  //
  // Both kits are cached together the first time EITHER is asked for -
  // whichever happens first, in practice always the bolt on the first frost
  // cast anyone makes - so a match with no frost cast never pays for either.
  frostKits() {
    if (this._frostKits) return this._frostKits;
    const T = this.T;
{BODY}
    this._frostKits = { bolt: makeFrostboltKit(T), block: makeIceBlockKit(T) };
    return this._frostKits;
  }

'''.replace('{BODY}', BODY)

s = s.replace(FBKIT_END, FBKIT_END + FROSTKITS_METHOD)

# ---------------------------------------------------------------------------
# 2. fireFrost: the frost branch gets the same treatment fire already has.
# ---------------------------------------------------------------------------
OLD_FROST = """    let m;
    if (fire && this.gfx !== 'low') {
      const kit = this.fireballKit();
      const built = kit.build({});
      kit.orientAlong(built.g, dir);
      m = built.g;
    } else {
      m = new T.Mesh(new T.IcosahedronGeometry(0.2, 1), new T.MeshBasicMaterial({ color: fire ? 0xffb36b : 0xa8e2ff }));
    }"""
assert s.count(OLD_FROST) == 1, 'fireFrost mesh-branch anchor matched %d times' % s.count(OLD_FROST)

NEW_FROST = """    let m;
    if (fire && this.gfx !== 'low') {
      const kit = this.fireballKit();
      const built = kit.build({});
      kit.orientAlong(built.g, dir);
      m = built.g;
    } else if (!fire && this.gfx !== 'low') {
      const kit = this.frostKits().bolt;
      const built = kit.build({});
      kit.orientAlong(built.g, dir);
      m = built.g;
    } else {
      m = new T.Mesh(new T.IcosahedronGeometry(0.2, 1), new T.MeshBasicMaterial({ color: fire ? 0xffb36b : 0xa8e2ff }));
    }"""
s = s.replace(OLD_FROST, NEW_FROST)

# ---------------------------------------------------------------------------
# 3. stepProjectiles: tick the frost bolt + ice block shader clocks too.
# ---------------------------------------------------------------------------
STEP_ANCHOR = """  stepProjectiles(dt) {
    const T = this.T;
    // One uniform write per fireball material for every fire bolt in
    // flight at once, not per bolt - same shape as tickCampfires().
    if (this._fbKit) this._fbKit.tick(this.worldT || 0);
"""
assert s.count(STEP_ANCHOR) == 1, 'stepProjectiles anchor matched %d times' % s.count(STEP_ANCHOR)
s = s.replace(STEP_ANCHOR, STEP_ANCHOR +
    "    // Same shape, for frost - both kits share one cache, so this is a\n"
    "    // single object read even though it drives two materials' worth of\n"
    "    // uniforms (the bolt's own two, plus the ice block's, ticked from\n"
    "    // stepFx while any block is alive - see the 'iceblock' fx case).\n"
    "    if (this._frostKits) { this._frostKits.bolt.tick(this.worldT || 0); }\n")

# ---------------------------------------------------------------------------
# 4. applyDamage: the freeze roll, the slow, and the ice block spawn.
# ---------------------------------------------------------------------------
OLD_APPLY = """    if (opt.freeze && !blocked && t.freezeCd <= 0) { t.frozen = 2; t.freezeCd = 6; }
    if (opt.burn && !blocked && dmg > 0) { t.burnS = 3; t.burnTk = 0; }"""
assert s.count(OLD_APPLY) == 1, 'applyDamage freeze/burn anchor matched %d times' % s.count(OLD_APPLY)

NEW_APPLY = """    // 25 percent of unblocked frost hits actually root the target (was
    // unconditional), for 1.5s (was 2s). freezeCd is untouched: it already
    // stopped one target being chain-frozen hit after hit, and still does.
    if (opt.freeze && !blocked && t.freezeCd <= 0 && Math.random() < 0.25) {
      t.frozen = 1.5; t.freezeCd = 6;
      this.spawnIceBlock(t);
    }
    // Every unblocked frost hit that lands damage slows the target 15
    // percent for a few seconds, whether or not that same hit also rolled
    // the freeze above - see e.slowT in stepFighter and both speed
    // functions (wishDir's player branch and driveAI's monster branch).
    if (opt.chill && !blocked && dmg > 0) { t.slowT = Math.max(t.slowT || 0, 3.0); }
    if (opt.burn && !blocked && dmg > 0) { t.burnS = 3; t.burnTk = 0; }"""
s = s.replace(OLD_APPLY, NEW_APPLY)

# spawnIceBlock: a small helper, dropped right before applyDamage so the
# method it calls is defined nearby. gfx==='low' skips it entirely, same
# reasoning as fireFrost skipping the fireball/frostbolt kits on low: three
# transparent draw calls plus a mist field is exactly what low graphics
# exists to shed, and the existing frostShell wireframe (already toggled by
# e.frozen > 0 regardless of graphics setting) still marks the target as
# frozen either way.
APPLYDAMAGE_ANCHOR = "  applyDamage(from, t, dmg, kind, worldPos, opt) {"
assert s.count(APPLYDAMAGE_ANCHOR) == 1, 'applyDamage entry anchor matched %d times' % s.count(APPLYDAMAGE_ANCHOR)
SPAWN_ICEBLOCK = """  spawnIceBlock(t) {
    if (this.gfx === 'low') return;
    const T = this.T;
    const world = (this.worldOn && this.mode === 'ai');
    const heightAt = world ? ((x, z) => this.groundY(x, z)) : null;
    const gy = world ? this.groundY(t.pos.x, t.pos.z) : 0;
    const kit = this.frostKits().block;
    const built = kit.build({ heightAt });
    built.g.position.set(t.pos.x, gy, t.pos.z);
    this.scene.add(built.g);
    // life matches the freeze duration set just above (1.5s) so the block
    // and the root end together - see the fx kind 'iceblock' case in stepFx
    // for the grow-hold-shrink curve and its own disposal (NOT retireFx:
    // this is a Group of four child meshes, not one Mesh with a single
    // geometry/material pair).
    this.fx.push({ kind: 'iceblock', mesh: built.g, life: 1.5, max: 1.5 });
  }

"""
s = s.replace(APPLYDAMAGE_ANCHOR, SPAWN_ICEBLOCK + APPLYDAMAGE_ANCHOR)

# ---------------------------------------------------------------------------
# 5. thread opt.chill alongside the two existing opt.freeze: kind === 'frost'
#    sites, so the slow applies wherever the freeze already can.
# ---------------------------------------------------------------------------
OLD_SITE_A = "{ magic: p.kind !== 'arrow', freeze: p.kind === 'frost', burn: p.kind === 'fire', snare: p.kind === 'snare', poison: p.kind === 'toxin', style: p.style });"
assert s.count(OLD_SITE_A) == 1, 'stepProjectiles hit-opt anchor matched %d times' % s.count(OLD_SITE_A)
NEW_SITE_A = "{ magic: p.kind !== 'arrow', freeze: p.kind === 'frost', chill: p.kind === 'frost', burn: p.kind === 'fire', snare: p.kind === 'snare', poison: p.kind === 'toxin', style: p.style });"
s = s.replace(OLD_SITE_A, NEW_SITE_A)

OLD_SITE_B = "{ magic: m.k === 'frost' || m.k === 'fire', freeze: m.k === 'frost', burn: m.k === 'fire' });"
assert s.count(OLD_SITE_B) == 1, 'onWorldData hit-opt anchor matched %d times' % s.count(OLD_SITE_B)
NEW_SITE_B = "{ magic: m.k === 'frost' || m.k === 'fire', freeze: m.k === 'frost', chill: m.k === 'frost', burn: m.k === 'fire' });"
s = s.replace(OLD_SITE_B, NEW_SITE_B)

# ---------------------------------------------------------------------------
# 6. stepFighter: decay e.slowT next to e.frozen, e.freezeCd and friends.
# ---------------------------------------------------------------------------
OLD_DECAY = """    e.frozen = Math.max(0, e.frozen - dt);
    e.iframe = Math.max(0, e.iframe - dt);"""
assert s.count(OLD_DECAY) == 1, 'stepFighter decay anchor matched %d times' % s.count(OLD_DECAY)
NEW_DECAY = """    e.frozen = Math.max(0, e.frozen - dt);
    e.slowT = Math.max(0, (e.slowT || 0) - dt);
    e.iframe = Math.max(0, e.iframe - dt);"""
s = s.replace(OLD_DECAY, NEW_DECAY)

# ---------------------------------------------------------------------------
# 7. both speed functions: 15 percent slow while e.slowT > 0. Same shape as
#    the e.blocking / e.state multipliers already sitting next to each.
# ---------------------------------------------------------------------------
OLD_SPEED_PLAYER = """    if (e.state === 'draw') sp *= 0.5;
    if (e.frozen > 0 || e.stagger > 0) sp = 0;
    if (e.state === 'dodge') { wish = e.dodgeDir; sp = 17 * Math.max(0, 1 - e.st / 0.5); }"""
assert s.count(OLD_SPEED_PLAYER) == 1, 'player speed anchor matched %d times' % s.count(OLD_SPEED_PLAYER)
NEW_SPEED_PLAYER = """    if (e.state === 'draw') sp *= 0.5;
    if (e.slowT > 0) sp *= 0.85;
    if (e.frozen > 0 || e.stagger > 0) sp = 0;
    if (e.state === 'dodge') { wish = e.dodgeDir; sp = 17 * Math.max(0, 1 - e.st / 0.5); }"""
s = s.replace(OLD_SPEED_PLAYER, NEW_SPEED_PLAYER)

OLD_SPEED_AI = """    if (e.state === 'attack' || e.state === 'cast') sp *= 0.22;
    if (e.frozen > 0 || e.stagger > 0) sp = 0;
    if (e.state === 'dodge') { move = e.dodgeDir; sp = 12; }"""
assert s.count(OLD_SPEED_AI) == 1, 'AI speed anchor matched %d times' % s.count(OLD_SPEED_AI)
NEW_SPEED_AI = """    if (e.state === 'attack' || e.state === 'cast') sp *= 0.22;
    if (e.slowT > 0) sp *= 0.85;
    if (e.frozen > 0 || e.stagger > 0) sp = 0;
    if (e.state === 'dodge') { move = e.dodgeDir; sp = 12; }"""
s = s.replace(OLD_SPEED_AI, NEW_SPEED_AI)

# ---------------------------------------------------------------------------
# 8. stepFx: the 'iceblock' kind. Grow in fast, hold, shrink+fade over the
#    last 0.25s, dispose all four child meshes directly (NOT retireFx - see
#    the note above spawnIceBlock for why).
# ---------------------------------------------------------------------------
STEPFX_ANCHOR = """  stepFx(dt) {
    for (let i = this.fx.length - 1; i >= 0; i--) {
      const f = this.fx[i];
      if (f.kind === 'firefly') {"""
assert s.count(STEPFX_ANCHOR) == 1, 'stepFx entry anchor matched %d times' % s.count(STEPFX_ANCHOR)
NEW_STEPFX = """  stepFx(dt) {
    for (let i = this.fx.length - 1; i >= 0; i--) {
      const f = this.fx[i];
      if (f.kind === 'iceblock') {
        f.life -= dt;
        const grownIn = Math.min(1, (f.max - f.life) / 0.15);
        const fadeOut = f.life < 0.25 ? Math.max(0, f.life / 0.25) : 1;
        const s2 = grownIn * fadeOut;
        f.mesh.scale.setScalar(Math.max(0.001, s2));
        f.mesh.traverse(o => { if (o.isMesh && o.material && 'opacity' in o.material) o.material.opacity = (o.userData.baseOpacity == null ? (o.userData.baseOpacity = o.material.opacity) : o.userData.baseOpacity) * fadeOut; });
        if (f.life <= 0) {
          f.mesh.traverse(o => { if (o.isMesh) { o.geometry.dispose(); o.material.dispose(); } });
          this.scene.remove(f.mesh);
          this.fx.splice(i, 1);
        }
        continue;
      }
      if (f.kind === 'firefly') {"""
s = s.replace(STEPFX_ANCHOR, NEW_STEPFX)

# ---------------------------------------------------------------------------
# 9. also tick the ice block's own shader clock while any are alive - cheap
#    (a no-op object read) even in the common case of zero blocks in flight.
# ---------------------------------------------------------------------------
FROSTKIT_TICK = "if (this._frostKits) { this._frostKits.bolt.tick(this.worldT || 0); }\n"
assert s.count(FROSTKIT_TICK) == 1, 'frost tick anchor matched %d times' % s.count(FROSTKIT_TICK)
s = s.replace(FROSTKIT_TICK,
    "if (this._frostKits) { this._frostKits.bolt.tick(this.worldT || 0); if (this.fx.some(f => f.kind === 'iceblock')) this._frostKits.block.tick(this.worldT || 0); }\n")

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 79.617 applied: frostbolt model + ice block + 25%%/1.5s freeze + 15%% slow (%d bytes of module inlined)' % len(BODY))
