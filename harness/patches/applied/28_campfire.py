#!/usr/bin/env python3
"""Patch 28: the campfire.

Numbering note: this was written as 27 and renumbered. Both tracks named a patch
26 on August 6; the bridge-ends-and-torches change was renamed to 27 and pushed
as ce61db7 while this was in flight. Check harness/patches/applied/ on a FRESH
pull before naming the next one: uploading under a number already in use
destroys the record of what that change did.

The model, the shader, the particles and the sound all come from
model-lab/campfire.js, which is the file the turntable page imports and the file
harness/prop.js screenshots. This script does not re-author any of it: it READS
that module and wraps it as a method. The alternative, keeping a second copy
inline in the bundle, means the thing that ships and the thing that was reviewed
start out identical and drift apart on the first tweak.

Three insertion points, each anchored on a string asserted to occur exactly
once:

  1. campfireKit / addCampfire / tickCampfires / campfireAudioStep, added just
     before tickTorches, which is the same class and the same concern.
  2. this.tickCampfires(t) in the frame loop, right after this.tickTorches(t).
  3. one campfire in the starting camp at the end of buildCampForge, so there
     is something to walk to. Everything else is placed through addCampfire.
"""
import io, os, re

SRC = '/tmp/game-src.html'
MODULE = os.path.join(os.path.dirname(__file__), '..', '..', 'model-lab', 'campfire.js')

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# turn the ES module into a method body
# ---------------------------------------------------------------------------
# Only two things have to change: the export keyword, which is meaningless
# inside a class, and the leading banner, which is re-stated below in the
# method's own comment. Everything else, including every function declaration,
# is legal exactly as written inside a method body.
assert mod.count('export function makeCampfireKit(T, opt) {') == 1, 'module entry point moved'
body = mod.replace('export function makeCampfireKit(T, opt) {',
                   'function makeCampfireKit(T, opt) {')
body = body.replace('/* eslint-disable no-unused-vars */\n', '')
# strip the module's top banner: the method carries its own
body = re.sub(r'\A// GRIM WORLD: the campfire\.\n(//.*\n)*\n', '', body)
body = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n'))

METHODS = '''  // ---- campfires -----------------------------------------------------------
  // Built from model-lab/campfire.js by harness/patches/27_campfire.py. Do not
  // hand-edit this block: change the lab module, re-run harness/prop.js to look
  // at it, and rebuild. The lab page and the game run the same source, so a
  // campfire that was reviewed on the turntable is the campfire that ships.
  //
  // Materials are shared by every fire in the world, so lighting all of them
  // for a frame is six uniform writes and one opacity assignment no matter how
  // many are burning. The geometry is five meshes: fuel and stones merged into
  // one, embers, three flame layers, then sparks, smoke and the ground glow.
  campfireKit() {
    if (this._cfKit) return this._cfKit;
    const T = this.T;
{BODY}
    this._cfKit = makeCampfireKit(T);
    return this._cfKit;
  }

  // Place one. Returns the record so a caller can move it, put it out, or hang
  // an interaction on it later.
  //   x, z    world position, dropped onto the terrain
  //   opt     seed, scale, light, lightPower, glowR, quiet
  addCampfire(x, z, opt) {
    opt = opt || {};
    const kit = this.campfireKit();
    const gy = (typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.ready)
      ? GRIM_WORLD.height(x, z) : this.groundY(x, z);
    const fire = kit.build(Object.assign({
      x: x, y: gy, z: z,
      // The glow disc is DRAPED over the terrain rather than laid flat, so the
      // pool of light follows a slope instead of being sliced off along a
      // straight line wherever the ground rises through it.
      heightAt: (hx, hz) => ((typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.ready)
        ? GRIM_WORLD.height(hx, hz) : gy)
    }, opt));
    this.scene.add(fire.g);
    // You cannot walk into a fire. The radius is the stone ring plus a little,
    // not the flame, so you can stand close enough to feel like you are at it.
    this.colliders.push({ x: x, z: z, r: fire.radius });
    if (fire.light) (this.decorLights = this.decorLights || []).push(fire.light);
    const rec = { x: x, z: z, y: gy, g: fire.g, light: fire.light, radius: fire.radius,
                  // How close you can get before it starts hurting. The collider
                  // already stops your CENTRE at fire.radius, so this only has
                  // to reach a little past it: pressed against the stones
                  // burns, a stride back does not.
                  heat: (opt.heat === undefined ? fire.radius + 0.55 : opt.heat),
                  quiet: !!opt.quiet, snd: null, kit: kit };
    (this.campfires = this.campfires || []).push(rec);
    return rec;
  }

  // One call a frame for the whole world.
  tickCampfires(tms) {
    if (!this.campfires || !this.campfires.length) return;
    const kit = this._cfKit;
    if (!kit) return;
    kit.tick(tms * 0.001);
    // Sparks and smoke are the first thing to go in performance mode: they are
    // transparent, so they cost fill rate, which is exactly what is scarce on
    // the machines that end up in LOW.
    const low = this.gfx === 'low';
    if (low !== this._cfLow) {
      this._cfLow = low;
      for (const f of this.campfires) {
        f.g.traverse(o => {
          if (o.isMesh && (o.material === kit.mats.spark || o.material === kit.mats.smoke)) o.visible = !low;
        });
      }
    }
    this.stepCampfireSound();
    this.stepCampfireBurn();
  }

  // Standing in a fire burns you.
  //
  // This rides the burn the game already has, the one fire magic applies, so it
  // looks and sounds like every other burn: the fire-coloured splat, the embers
  // off the body, the screen flash, and the same rule that a burn tick can take
  // you to 1 HP but never kills you. An environment hazard that can kill you
  // outright while you are reading a signpost is a bug report, not a mechanic.
  //
  // Topped up every frame you are inside the heat radius rather than applied
  // once, so it keeps ticking while you stand there and dies out about a second
  // after you step back.
  stepCampfireBurn() {
    if (!this.campfires || !this.campfires.length) return;
    const me = this.me;
    if (!me || me.hp <= 0 || !this.started || this.mode !== 'ai' || this.warmup) return;
    for (const f of this.campfires) {
      if (f.out) continue;
      const dx = f.x - me.pos.x, dz = f.z - me.pos.z;
      if (dx * dx + dz * dz > f.heat * f.heat) continue;
      me.burnS = Math.max(me.burnS || 0, 1.1);
      if (!this._cfBurnWarned) {
        this._cfBurnWarned = true;
        this.banner('THE FIRE', 'IT BURNS - STAND BACK', false, 2400);
      }
      return;
    }
  }

  // The sound follows the player rather than riding a spatialiser per fire: the
  // game already knows where everyone is every frame, one gain write is cheaper
  // than a panner, and it stays correct when the listener is not the camera.
  // A fire out of earshot is torn down entirely, so walking across the map does
  // not accumulate a graph of silent oscillators.
  stepCampfireSound() {
    if (!this.ac || !this.me || !this.started) return;
    if (this.ac.state === 'suspended') return;
    const NEAR = 22, GONE = 30;
    const P = this.me.pos;
    for (const f of this.campfires) {
      if (f.quiet) continue;
      const d = Math.hypot(f.x - P.x, f.z - P.z);
      if (d < NEAR && !f.snd) {
        f.snd = f.kit.sound(this.ac, this.master, { gain: 0.5 });
      } else if (d > GONE && f.snd) {
        f.snd.stop(); f.snd = null;
      }
      if (f.snd) f.snd.setDistance(d, GONE);
    }
  }

'''.replace('{BODY}', body)

# ---------------------------------------------------------------------------
# 1. the methods, just before tickTorches
# ---------------------------------------------------------------------------
ANCHOR = """  // One uniform for every flame in the world, plus a gentle breath on the pool
  // of light. Deliberately restrained on the ground: there is no night cycle
  // yet, and in daylight a torch throws a faint wash, not a spotlight.
  tickTorches(tms) {"""
assert s.count(ANCHOR) == 1, 'tickTorches anchor matched %d times' % s.count(ANCHOR)
s = s.replace(ANCHOR, METHODS + ANCHOR)

# ---------------------------------------------------------------------------
# 2. the frame loop
# ---------------------------------------------------------------------------
LOOP = """      this.tick(dt);
      this.tickTorches(t);"""
assert s.count(LOOP) == 1, 'frame loop anchor matched %d times' % s.count(LOOP)
s = s.replace(LOOP, LOOP + """
      this.tickCampfires(t);""")

# ---------------------------------------------------------------------------
# 3. one campfire in the starting camp
# ---------------------------------------------------------------------------
# Placed through clearOfRoad so it cannot land in the road corridor, and offset
# from the forge and the anvil, which both carry their own colliders.
CAMP = """    av.position.set(36.2, 0, 23.2); S.add(av);
    this.anvil = { pos: new T.Vector3(36.2, 0, 23.2) };
    this.colliders.push({ x: 36.2, z: 23.2, r: 0.9 });
  }"""
assert s.count(CAMP) == 1, 'camp forge anchor matched %d times' % s.count(CAMP)
s = s.replace(CAMP, """    av.position.set(36.2, 0, 23.2); S.add(av);
    this.anvil = { pos: new T.Vector3(36.2, 0, 23.2) };
    this.colliders.push({ x: 36.2, z: 23.2, r: 0.9 });

    // A campfire in the camp, so there is one to walk to without hunting for
    // it.
    //
    // The first attempt put it at 30.6, 28.4 and it came out half inside a
    // boulder. clearOfRoad only keeps a prop off the ROAD, and dressBlocked
    // only keeps zone clutter off a prop; neither can see geometry another
    // builder already placed. 45, 24 was surveyed with harness/campsite.js
    // against the loaded scene: 6.9 m to the nearest mesh of any kind, 7.9 m
    // to the nearest collider, dead flat, and about eight metres from where a
    // new player spawns, so it is the first thing they walk past.
    this.addCampfire(45, 24, { seed: 7 });
  }""")

# ---------------------------------------------------------------------------
# 4. keep the zone dressing off it
# ---------------------------------------------------------------------------
# A campfire's collider stops the PLAYER walking into it, but clutter is placed
# by the pure generator, which knows nothing about colliders. Without this a
# boulder grows straight up through the flames, which is exactly what the first
# in-game shot caught. dressBlocked is called about a thousand times per chunk,
# so this has to stay a handful of squared distances, which it is: there are
# never many campfires.
DRESS = """    // steep ground: props standing on a cliff face read as floating
    const e = 1.5;"""
assert s.count(DRESS) == 1, 'dressBlocked anchor matched %d times' % s.count(DRESS)
s = s.replace(DRESS, """    // Campfires. The collider stops the player walking in; this stops a boulder
    // growing up through the flames, which the collider cannot do because
    // clutter is placed by the pure generator and never sees a collider.
    for (const f of (this.campfires || [])) {
      const r = f.radius + 1.2;
      if ((x - f.x) * (x - f.x) + (z - f.z) * (z - f.z) < r * r) return true;
    }
""" + DRESS)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 28: campfire installed (%d bytes of module inlined)' % len(body))
