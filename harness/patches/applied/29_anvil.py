#!/usr/bin/env python3
"""Patch 29: the blacksmith's anvil.

Replaces the camp anvil (a box, a box and a cone) with a real London pattern
anvil on an oak stump, and replaces the forge's placeholder strike sound.

Generated FROM model-lab/anvil.js and model-lab/grim-kit.js. Neither is retyped,
so the anvil reviewed on the turntable is byte for byte the anvil that ships.
This is the first patch to inline the kit as well as the asset: grim-kit is
concatenated ahead of the module with its `export` keywords stripped and the
module's import line removed, which is exactly the shape the patch template
describes.

Numbering: 28 is the campfire, now moved to applied/. Check
harness/patches/applied/ on a FRESH pull before naming the next one; two tracks
work on this repo and have collided on a number twice.

Four anchored edits:
  1. the kit, as class methods, next to the other prop builders
  2. the anvil block inside buildCampForge, swapped for a call to it
  3. the forge clang, swapped off sfx('block')
  4. a clutter exclusion, so nothing grows up through the station
"""
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
KIT = os.path.join(HERE, '..', '..', 'model-lab', 'grim-kit.js')
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'anvil.js')

s = io.open(SRC, encoding='utf-8').read()
kit = io.open(KIT, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# fold the shared kit and the asset module into one method body
# ---------------------------------------------------------------------------
# Only the module boundary changes. Every function inside is legal as written
# inside a method body, which is the whole reason the modules are authored
# without touching `this` or any global.
assert 'export function makeAnvilKit(T, opt) {' in mod, 'module entry point moved'
kit_body = re.sub(r'^export ', '', kit, flags=re.M)
mod_body = re.sub(r"^import \{[^}]*\} from '\./grim-kit\.js';\n", '', mod, flags=re.M | re.S)
assert 'grim-kit' not in mod_body, 'the import line did not come out'
mod_body = mod_body.replace('export function makeAnvilKit(T, opt) {',
                            'function makeAnvilKit(T, opt) {')
# strip each file's top banner: the method carries its own
kit_body = re.sub(r'\A// Grim World shared asset primitives\.\n(//.*\n)*\n', '', kit_body)
mod_body = re.sub(r"\A// GRIM WORLD: the blacksmith's anvil\.\n(//.*\n)*\n", '', mod_body)

body = kit_body.rstrip() + '\n\n' + mod_body
body = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n'))

METHODS = '''  // ---- the anvil -----------------------------------------------------------
  // Built from model-lab/anvil.js on model-lab/grim-kit.js by
  // harness/patches/29_anvil.py. Do not hand-edit this block: change the lab
  // module, run harness/prop.js anvil to look at it, and rebuild.
  //
  // Two materials shared by every anvil in the world (forged steel and oak) and
  // two merged meshes per station, so the whole thing is three draw calls
  // including the tools leaning against it.
  anvilKit() {
    if (this._anvilKit) return this._anvilKit;
    const T = this.T;
{BODY}
    this._anvilKit = makeAnvilKit(T);
    return this._anvilKit;
  }

  // Place one. Returns the record so a caller can find its face later, which is
  // where a hot billet or a finished blade would sit.
  addAnvil(x, z, opt) {
    opt = opt || {};
    // buildCampForge has a local `const T = this.T`, this method does not, and
    // a bare T here threw "T is not defined" at world build with nothing else
    // to say which of the four edits was at fault. The boot harness caught it;
    // the syntax gate could not, because it is perfectly valid JavaScript.
    const T = this.T;
    const kit = this.anvilKit();
    const gy = (typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.ready)
      ? GRIM_WORLD.height(x, z) : this.groundY(x, z);
    const built = kit.build(Object.assign({ x: x, y: gy, z: z }, opt));
    this.scene.add(built.g);
    // The collider is the STUMP, not the anvil. Anything bigger and you cannot
    // get close enough for the forge prompt to fire at 3 m.
    this.colliders.push({ x: x, z: z, r: built.radius });
    const rec = {
      x: x, z: z, y: gy, g: built.g, radius: built.radius,
      // world position of the middle of the face, for sparks and for anything
      // that later wants to sit a workpiece on it
      face: built.faceCentre.clone().add(new T.Vector3(x, gy, z)),
      kit: kit
    };
    (this.anvils = this.anvils || []).push(rec);
    return rec;
  }

  // The forge fired sfx('block') on every blow, which is the SHIELD BLOCK
  // sound: a square-wave chirp and a noise tick, left in as a placeholder.
  //
  // What replaces it is a real strike: a bright transient, a low thud for the
  // mass, and six INHARMONIC partials that ring for over a second. Inharmonic is
  // the whole point. Modes at f, 2f, 3f are a musical note and read as a chime;
  // a real anvil's sit at ratios like 1 : 1.51 : 2.13 : 2.88 and the ear hears
  // metal. Every blow is detuned a per cent or two with its own decay, because
  // the forge fires four of them in 1.6 seconds and four identical clangs is
  // the sound of a sample being retriggered.
  anvilStrike(heavy) {
    if (!this.ac || !this.started) { return; }
    if (this.ac.state === 'suspended') { try { this.ac.resume(); } catch (e) {} }
    const kit = this._anvilKit;
    if (!kit || !kit.strike) { this.sfx('block'); return; }
    kit.strike(this.ac, this.master, { gain: 0.5, heavy: !!heavy });
  }

'''.replace('{BODY}', body)

# ---------------------------------------------------------------------------
# 1. the methods, before the campfire block so the prop builders sit together
# ---------------------------------------------------------------------------
ANCHOR = """  // ---- campfires -----------------------------------------------------------"""
assert s.count(ANCHOR) == 1, 'campfire anchor matched %d times' % s.count(ANCHOR)
s = s.replace(ANCHOR, METHODS + ANCHOR)

# ---------------------------------------------------------------------------
# 2. the anvil itself
# ---------------------------------------------------------------------------
# `this.anvil = { pos }` is load-bearing: tryForge, craftAtAnvil and the
# interact prompt all read it, and the smithing quest runs through it. The
# record keeps the same shape and the same position so none of that moves.
OLD = """    const av = new T.Group();
    const blk = new T.Mesh(new T.BoxGeometry(0.5, 0.55, 0.5), dark); blk.position.y = 0.28; blk.castShadow = true; av.add(blk);
    const steelM = new T.MeshStandardMaterial({ color: 0x4a4a50, roughness: 0.5, metalness: 0.6, flatShading: true });
    const top = new T.Mesh(new T.BoxGeometry(1.0, 0.22, 0.34), steelM); top.position.y = 0.66; top.castShadow = true; av.add(top);
    const horn = new T.Mesh(new T.ConeGeometry(0.13, 0.42, 6), steelM); horn.rotation.z = -Math.PI / 2; horn.position.set(0.66, 0.66, 0); av.add(horn);
    av.position.set(36.2, 0, 23.2); S.add(av);
    this.anvil = { pos: new T.Vector3(36.2, 0, 23.2) };
    this.colliders.push({ x: 36.2, z: 23.2, r: 0.9 });"""
assert s.count(OLD) == 1, 'anvil anchor matched %d times' % s.count(OLD)
s = s.replace(OLD, """    // A real London pattern anvil on an oak stump, in the same spot the old one
    // stood so the forge prompt, the smithing quest and the minimap all keep
    // working. addAnvil registers the collider itself.
    const avRec = this.addAnvil(36.2, 23.2, { seed: 11 });
    this.anvil = { pos: new T.Vector3(36.2, 0, 23.2), face: avRec.face, rec: avRec };""")

# ---------------------------------------------------------------------------
# 3. the forge clang, and put the sparks where the hammer lands
# ---------------------------------------------------------------------------
CLANG = """      if (this.forgeClang <= 0) { this.forgeClang = 0.4; this.sfx('block'); this.spark(this.anvil.pos.clone().add(new T.Vector3(0, 0.8, 0)), 0xfff2c8, 8); }"""
assert s.count(CLANG) == 1, 'forge clang anchor matched %d times' % s.count(CLANG)
s = s.replace(CLANG, """      if (this.forgeClang <= 0) {
        this.forgeClang = 0.4;
        this._forgeBlow = (this._forgeBlow || 0) + 1;
        // the first blow of a heat lands hardest
        this.anvilStrike(this._forgeBlow % 4 === 1);
        // Sparks off the FACE rather than a guessed 0.8 m above the base, so
        // they come off the metal instead of out of the middle of the stump.
        this.spark((this.anvil.face || this.anvil.pos.clone().add(new T.Vector3(0, 0.8, 0)))
          .clone().add(new T.Vector3(0, 0.03, 0)), 0xfff2c8, 8);
      }""")

# ---------------------------------------------------------------------------
# 4. keep the zone dressing off it
# ---------------------------------------------------------------------------
DRESS = """    // Campfires. The collider stops the player walking in; this stops a boulder
    // growing up through the flames, which the collider cannot do because
    // clutter is placed by the pure generator and never sees a collider."""
assert s.count(DRESS) == 1, 'dressBlocked anchor matched %d times' % s.count(DRESS)
s = s.replace(DRESS, """    // Anvils, for the same reason as campfires below: a collider stops the
    // player, not the pure generator that places clutter.
    for (const a of (this.anvils || [])) {
      const r = a.radius + 1.0;
      if ((x - a.x) * (x - a.x) + (z - a.z) * (z - a.z) < r * r) return true;
    }
""" + DRESS)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 29: anvil installed (%d bytes of kit + module inlined)' % len(body))
