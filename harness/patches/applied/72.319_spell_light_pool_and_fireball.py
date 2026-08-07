#!/usr/bin/env python3
"""Patch 72.319: pooled spell lights, and the fireball reskin.

Two changes, shipped together because they touch the same three functions and
Kevin asked for them in the same pass.

1. THE FREEZE. Casting frost/fire/snare used to `new THREE.PointLight` and
   hand it straight to the projectile mesh, then let it go with the mesh when
   the bolt hit or expired 1-2.6s later. Every cast therefore changed how many
   live lights the scene had for a frame, and Three.js recompiles the shader
   program for every lit material in view when that count changes - the
   bundle already has a five-light budget on world torches for exactly this
   reason (decorLights, see stepMap()) but the budget never covered spell
   bolts. Traced end to end in PERF-AUDIT-AUG6.md's follow-up: with several
   thousand meshes and ~34 shader programs in view, that recompile is the
   freeze. Fix: five PointLights built ONCE in the constructor and never
   removed from the scene; fireFrost/fireSnare borrow one and give it back
   (grabSpellLight/releaseSpellLight) instead of constructing/destroying one
   per cast. Frost and snare are otherwise untouched.

2. THE FIREBALL REEKIN. Kevin wants the fire bolt to look like the campfire's
   fire, not a flat-shaded lump with a light taped to it, with an ember trail.
   model-lab/fireball.js builds that out of the campfire's own flame shader
   (grim-kit.js), cut down and raked backward along the direction of travel
   like a comet. Frost, snare, sound and damage numbers are untouched - this
   only replaces the mesh fireFrost() builds when the cast is fire.

Anchors are asserted to occur exactly once each. Check harness/patches/applied/
on a fresh pull before reusing this number - two tracks have collided on one
before.
"""
import io, os, re

SRC = '/tmp/game-src.html'
KIT = os.path.join(os.path.dirname(__file__), '..', '..', 'model-lab', 'grim-kit.js')
MODULE = os.path.join(os.path.dirname(__file__), '..', '..', 'model-lab', 'fireball.js')

s = io.open(SRC, encoding='utf-8').read()
kit_src = io.open(KIT, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# inline grim-kit.js + fireball.js into one method body, per the standard
# recipe: strip grim-kit's exports, drop fireball.js's import of it, and
# concatenate. grim-kit.js is large and shared by several assets; only pull in
# the names fireball.js actually uses, so this method does not carry dead code
# for logBetween, roughen, paintByPos, glowMat and the rest.
# ---------------------------------------------------------------------------
NEEDED_FN = ['rngFor', 'mergeParts', 'placed', 'tongueGeo', 'flameMat', 'driftMat', 'driftField', 'tongueParts']
# GLSL_NOISE is an `export const`, not an `export function` - flameMat's
# fragment shader concatenates it in directly. Missing it is a silent-until-
# runtime failure: the patch and the syntax gates both pass, and the error
# only shows up as a shader compile error the first time a fire bolt is drawn.
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

assert mod.count("export function makeFireballKit(T, opt) {") == 1, 'fireball.js entry point moved'
fb_body = mod.replace('export function makeFireballKit(T, opt) {',
                      'function makeFireballKit(T, opt) {')
fb_body = fb_body.replace(
    "import { rngFor, mergeParts, tongueParts, flameMat, driftMat, driftField } from './grim-kit.js';\n",
    '')
fb_body = fb_body.replace('/* eslint-disable no-unused-vars */\n', '')
fb_body = re.sub(r'\A// GRIM WORLD: the fire bolt\.\n(//.*\n)*\n', '', fb_body)

BODY = kit_body + '\n' + fb_body
BODY = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in BODY.split('\n'))

# ---------------------------------------------------------------------------
# 1. the light pool, built once, in the constructor
# ---------------------------------------------------------------------------
CTOR = """    this.projectiles = []; this.fx = [];
    this.resources = []; this.drops = [];"""
assert s.count(CTOR) == 1, 'constructor anchor matched %d times' % s.count(CTOR)
s = s.replace(CTOR, CTOR + """
    // A fixed pool of point lights for spell bolts, added to the scene ONCE
    // and never removed - see grabSpellLight()/releaseSpellLight() and the
    // patch note above for why. Five matches the decorLights torch budget
    // this mirrors: volley fires three snares at once, so five leaves room
    // for a full volley plus one more caster nearby before anything has to
    // share.
    this._spellLights = [];
    for (let sl = 0; sl < 5; sl++) {
      const spellLight = new T.PointLight(0xffffff, 0, 7, 2);
      scene.add(spellLight);
      this._spellLights.push(spellLight);
    }""")

# ---------------------------------------------------------------------------
# 2. grabSpellLight / releaseSpellLight / fireballKit, just before fireFrost
# ---------------------------------------------------------------------------
FROST_ANCHOR = "  fireFrost(a) {"
assert s.count(FROST_ANCHOR) == 1, 'fireFrost anchor matched %d times' % s.count(FROST_ANCHOR)

METHODS = '''  // Hands back a pooled spell light instead of ever constructing a new
  // PointLight at cast time. If every light is already spoken for (a full
  // volley plus another caster or two nearby) the longest-held one is
  // reclaimed - a bolt losing its glow a little early is a cosmetic trade,
  // never a correctness one, and the scene's live light count still never
  // moves either way.
  grabSpellLight() {
    const pool = this._spellLights;
    if (!pool || !pool.length) return null;
    let pick = pool.find(l => !l.userData.busy);
    if (!pick) pick = pool.reduce((a, b) => (a.userData.claimedAt || 0) <= (b.userData.claimedAt || 0) ? a : b);
    pick.userData.busy = true;
    pick.userData.claimedAt = performance.now();
    return pick;
  }
  // Turns a spell light back off and hands it back to the scene root so it
  // stays part of the render graph. It must NOT travel with the dead
  // projectile mesh into scene.remove() - that would drop the live light
  // count by one and cost exactly the recompile this pool exists to avoid.
  releaseSpellLight(l) {
    if (!l) return;
    l.userData.busy = false;
    l.intensity = 0;
    if (l.parent !== this.scene) this.scene.add(l);
  }

  // ---- fireball kit ---------------------------------------------------------
  // Built from model-lab/fireball.js (and the campfire's own flame shader out
  // of model-lab/grim-kit.js) by harness/patches/72.319_spell_light_pool_and_fireball.py.
  // Do not hand-edit this block: change the lab module, look at it with
  // node harness/prop.js fireball, and rebuild.
  //
  // Lazily built on the first fire cast anyone makes, same pattern as
  // campfireKit(), so a match where nobody ever casts fire never pays for it.
  fireballKit() {
    if (this._fbKit) return this._fbKit;
    const T = this.T;
{BODY}
    this._fbKit = makeFireballKit(T);
    return this._fbKit;
  }

'''.replace('{BODY}', BODY)

s = s.replace(FROST_ANCHOR, METHODS + FROST_ANCHOR)

# ---------------------------------------------------------------------------
# 3. fireFrost: pooled light, and the fire branch builds the fireball kit
# ---------------------------------------------------------------------------
OLD_FROST = """  fireFrost(a) {
    const T = this.T;
    const fire = a === this.me ? this.element === 'fire' : a.elem === 'fire';
    const gy = (this.worldOn && this.mode === 'ai') ? this.groundY(a.pos.x, a.pos.z) : 0;
    let dir = new T.Vector3(Math.sin(a.yaw), 0, Math.cos(a.yaw));
    if (a === this.me) dir = this.aimDirFrom(new T.Vector3(a.pos.x, this.worldY(a, gy) + 1.5, a.pos.z)); else dir = this.npcAimDir(a, this.worldY(a, gy) + 1.5);
    const m = new T.Mesh(new T.IcosahedronGeometry(0.2, 1), new T.MeshBasicMaterial({ color: fire ? 0xffb36b : 0xa8e2ff }));
    // an NPC casts from the end of its staff; only the player fires from a
    // fixed point in front of the camera
    if (a !== this.me && a.parts) m.position.copy(this.castOrigin(a)).addScaledVector(dir, 0.35);
    else m.position.set(a.pos.x, this.worldY(a, gy) + 1.5, a.pos.z).addScaledVector(dir, 1);
    const light = new T.PointLight(fire ? 0xff8c3a : 0x7fc8ff, 3.5, 7, 2); m.add(light);
    this.scene.add(m);
    this.projectiles.push({ mesh: m, vel: dir.multiplyScalar(19), owner: a, dmg: fire ? 30 : 26, style: 'MAGIC', kind: fire ? 'fire' : 'frost', life: 2.6 }); this.sfx(fire ? 'sp-fire-cast' : 'sp-frost-cast', a);
    this.coopProj(a);
  }"""
assert s.count(OLD_FROST) == 1, 'fireFrost body matched %d times' % s.count(OLD_FROST)

NEW_FROST = """  fireFrost(a) {
    const T = this.T;
    const fire = a === this.me ? this.element === 'fire' : a.elem === 'fire';
    const gy = (this.worldOn && this.mode === 'ai') ? this.groundY(a.pos.x, a.pos.z) : 0;
    let dir = new T.Vector3(Math.sin(a.yaw), 0, Math.cos(a.yaw));
    if (a === this.me) dir = this.aimDirFrom(new T.Vector3(a.pos.x, this.worldY(a, gy) + 1.5, a.pos.z)); else dir = this.npcAimDir(a, this.worldY(a, gy) + 1.5);
    // Fire gets the campfire-style tongue cluster with an ember trail; frost
    // keeps the plain icy orb it always had - only the fireball was asked
    // for. LOW graphics also keeps the orb: the cluster is three transparent
    // draw calls where the orb is one, and transparency is exactly what LOW
    // exists to shed.
    let m;
    if (fire && this.gfx !== 'low') {
      const kit = this.fireballKit();
      const built = kit.build({});
      kit.orientAlong(built.g, dir);
      m = built.g;
    } else {
      m = new T.Mesh(new T.IcosahedronGeometry(0.2, 1), new T.MeshBasicMaterial({ color: fire ? 0xffb36b : 0xa8e2ff }));
    }
    // an NPC casts from the end of its staff; only the player fires from a
    // fixed point in front of the camera
    if (a !== this.me && a.parts) m.position.copy(this.castOrigin(a)).addScaledVector(dir, 0.35);
    else m.position.set(a.pos.x, this.worldY(a, gy) + 1.5, a.pos.z).addScaledVector(dir, 1);
    // Pooled, not constructed - see grabSpellLight(). This is the fix: this
    // cast no longer changes how many lights the scene has.
    const light = this.grabSpellLight();
    if (light) {
      light.color.setHex(fire ? 0xff8c3a : 0x7fc8ff); light.intensity = 3.5; light.distance = 7; light.decay = 2;
      m.add(light);
    }
    this.scene.add(m);
    this.projectiles.push({ mesh: m, light: light, vel: dir.multiplyScalar(19), owner: a, dmg: fire ? 30 : 26, style: 'MAGIC', kind: fire ? 'fire' : 'frost', life: 2.6 }); this.sfx(fire ? 'sp-fire-cast' : 'sp-frost-cast', a);
    this.coopProj(a);
  }"""
s = s.replace(OLD_FROST, NEW_FROST)

# ---------------------------------------------------------------------------
# 4. fireSnare: pooled light only, look untouched
# ---------------------------------------------------------------------------
OLD_SNARE = """  fireSnare(a, yawOff) {
    const T = this.T;
    const gy = (this.worldOn && this.mode === 'ai') ? this.groundY(a.pos.x, a.pos.z) : 0;
    let dir = new T.Vector3(Math.sin(a.yaw + (yawOff || 0)), 0, Math.cos(a.yaw + (yawOff || 0)));
    if (a === this.me) {
      const origin = new T.Vector3(a.pos.x, this.worldY(a, gy) + 1.7, a.pos.z);
      dir = this.aimDirFrom(origin);
      if (yawOff) dir.applyAxisAngle(new T.Vector3(0, 1, 0), yawOff); } else { dir = this.npcAimDir(a, this.worldY(a, gy) + 1.7); if (yawOff) dir.applyAxisAngle(new T.Vector3(0, 1, 0), yawOff);
    }
    const m = new T.Mesh(new T.IcosahedronGeometry(0.24, 0), new T.MeshBasicMaterial({ color: 0x8fefaf }));
    m.position.set(a.pos.x, this.worldY(a, gy) + 1.7, a.pos.z).addScaledVector(dir, 1.1);
    const light = new T.PointLight(0x6fdf8f, 3, 6, 2); m.add(light);
    this.scene.add(m);
    this.projectiles.push({ mesh: m, vel: dir.multiplyScalar(15), owner: a, dmg: 8, kind: 'snare', life: 2.4 });
    this.coopProj(a);
  }"""
assert s.count(OLD_SNARE) == 1, 'fireSnare body matched %d times' % s.count(OLD_SNARE)

NEW_SNARE = """  fireSnare(a, yawOff) {
    const T = this.T;
    const gy = (this.worldOn && this.mode === 'ai') ? this.groundY(a.pos.x, a.pos.z) : 0;
    let dir = new T.Vector3(Math.sin(a.yaw + (yawOff || 0)), 0, Math.cos(a.yaw + (yawOff || 0)));
    if (a === this.me) {
      const origin = new T.Vector3(a.pos.x, this.worldY(a, gy) + 1.7, a.pos.z);
      dir = this.aimDirFrom(origin);
      if (yawOff) dir.applyAxisAngle(new T.Vector3(0, 1, 0), yawOff); } else { dir = this.npcAimDir(a, this.worldY(a, gy) + 1.7); if (yawOff) dir.applyAxisAngle(new T.Vector3(0, 1, 0), yawOff);
    }
    const m = new T.Mesh(new T.IcosahedronGeometry(0.24, 0), new T.MeshBasicMaterial({ color: 0x8fefaf }));
    m.position.set(a.pos.x, this.worldY(a, gy) + 1.7, a.pos.z).addScaledVector(dir, 1.1);
    // Pooled, same as fireFrost - see grabSpellLight(). Volley fires three of
    // these in one swing, which used to mean three fresh lights in a single
    // frame; now it is three of the same five reused every time.
    const light = this.grabSpellLight();
    if (light) { light.color.setHex(0x6fdf8f); light.intensity = 3; light.distance = 6; light.decay = 2; m.add(light); }
    this.scene.add(m);
    this.projectiles.push({ mesh: m, light: light, vel: dir.multiplyScalar(15), owner: a, dmg: 8, kind: 'snare', life: 2.4 });
    this.coopProj(a);
  }"""
s = s.replace(OLD_SNARE, NEW_SNARE)

# ---------------------------------------------------------------------------
# 5. stepProjectiles: tick the fireball shader clock, and release a light
#    BEFORE its mesh leaves the scene at each of the two removal sites
# ---------------------------------------------------------------------------
STEP_ANCHOR = "  stepProjectiles(dt) {\n    const T = this.T;\n"
assert s.count(STEP_ANCHOR) == 1, 'stepProjectiles anchor matched %d times' % s.count(STEP_ANCHOR)
s = s.replace(STEP_ANCHOR, STEP_ANCHOR +
    "    // One uniform write per fireball material for every fire bolt in\n"
    "    // flight at once, not per bolt - same shape as tickCampfires().\n"
    "    if (this._fbKit) this._fbKit.tick(this.worldT || 0);\n")

STUCK_OLD = "if (p.life <= 0) { this.scene.remove(p.mesh); this.projectiles.splice(i, 1); }"
assert s.count(STUCK_OLD) == 1, 'stuck-arrow removal anchor matched %d times' % s.count(STUCK_OLD)
s = s.replace(STUCK_OLD,
    "if (p.life <= 0) { if (p.light) this.releaseSpellLight(p.light); this.scene.remove(p.mesh); this.projectiles.splice(i, 1); }")

MAIN_OLD = ("        this.scene.remove(p.mesh); this.projectiles.splice(i, 1);\n"
            "      }\n    }\n  }\n\n  // Centre of the body")
assert s.count(MAIN_OLD) == 1, 'main removal anchor matched %d times' % s.count(MAIN_OLD)
s = s.replace(MAIN_OLD,
    "        if (p.light) this.releaseSpellLight(p.light);\n"
    "        this.scene.remove(p.mesh); this.projectiles.splice(i, 1);\n"
    "      }\n    }\n  }\n\n  // Centre of the body")

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 72.319: spell light pool + fireball reskin installed (%d bytes of module inlined)' % len(BODY))
