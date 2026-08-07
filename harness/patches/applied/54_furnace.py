#!/usr/bin/env python3
"""Patch 54: the furnace, reworked from the ground up.

The old furnace was two cylinders, a box, a glowing sticker and a light. The
new one comes from model-lab/furnace.js, reviewed on the turntable at every
angle and light: a bulging clay shaft on field stones with iron strapping, a
projecting firebrick forebox with a genuinely open chamber (coals, flames,
sparks, backlit arch), a breathing double-lung bellows feeding a tuyere, a
slag gutter to a pit of cooled black glass, a mold bench with bars still
cooling, an ore trough of copper, iron and gold, an ember-glowing charge hole
with a spark column, and a deep bellows-surged roar with a molten pour
one-shot when a bar comes off.

This script does not re-author the model: it READS model-lab/furnace.js and
model-lab/grim-kit.js and inlines them, the same single-source rule the
campfire and anvil follow.

Function changes ride along, because Kevin asked the furnace to "process all
the different types of ores": smelting now takes COPPER ORE (lvl 1, 10 xp),
IRON ORE (lvl 1, 16 xp, unchanged) and GOLD ORE (SMITHING 40, 56 xp), picking
the first smeltable ore in the pack each cycle, with COPPER BAR and GOLD BAR
defined as items and priced at the trader. The Irons in the Fire quest still
counts IRON bars only, and reads exactly as before.
"""
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
KIT = os.path.join(HERE, '..', '..', 'model-lab', 'grim-kit.js')
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'furnace.js')

s = io.open(SRC, encoding='utf-8').read()
kitSrc = io.open(KIT, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

def sub(old, new, why):
    global s
    assert s.count(old) == 1, 'anchor x%d: %s' % (s.count(old), why)
    s = s.replace(old, new)
    print('  ok:', why)

# ---------------------------------------------------------------------------
# turn the two ES modules into one method body
# ---------------------------------------------------------------------------
# grim-kit: strip the export keywords; every helper becomes a local function.
kitBody = kitSrc.replace('export function ', 'function ').replace('export const ', 'const ')
kitBody = re.sub(r'\A(//.*\n)+', '', kitBody)
# furnace: strip the import (the helpers are in scope) and the export.
assert mod.count('export function makeFurnaceKit(T, opt) {') == 1, 'module entry point moved'
body = re.sub(r'import \{[\s\S]*?\} from \'\./grim-kit\.js\';\n', '', mod)
body = body.replace('export function makeFurnaceKit(T, opt) {', 'function makeFurnaceKit(T, opt) {')
body = re.sub(r'\A// GRIM WORLD: the smelting furnace\.\n(//.*\n)*\n', '', body)
full = kitBody + '\n' + body
full = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in full.split('\n'))

METHOD = '''  // ---- the furnace ---------------------------------------------------------
  // Built from model-lab/furnace.js + grim-kit.js by patch 54. Do not
  // hand-edit this block: change the lab module, review it with
  // harness/prop.js furnace, and rebuild. The lab and the game run the same
  // source.
  furnaceKit() {
    if (this._fnKit) return this._fnKit;
    const T = this.T;
{BODY}
    this._fnKit = makeFurnaceKit(T);
    return this._fnKit;
  }

'''.replace('{BODY}', full)

sub('  campfireKit() {\n    if (this._cfKit) return this._cfKit;',
    METHOD + '  campfireKit() {\n    if (this._cfKit) return this._cfKit;',
    'furnaceKit method injected')

# ---------------------------------------------------------------------------
# buildCampForge: the new furnace replaces the two-cylinder prop
# ---------------------------------------------------------------------------
sub("""    const stone = new T.MeshStandardMaterial({ color: 0x6e6a5e, roughness: 0.95, flatShading: true });
    const dark = new T.MeshStandardMaterial({ color: 0x2a2622, roughness: 0.9, flatShading: true });
    const fur = new T.Group();
    const base = new T.Mesh(new T.CylinderGeometry(0.95, 1.1, 1.1, 8), stone); base.position.y = 0.55; base.castShadow = true; fur.add(base);
    const stack = new T.Mesh(new T.CylinderGeometry(0.5, 0.8, 1.5, 8), stone); stack.position.y = 1.8; stack.castShadow = true; fur.add(stack);
    const mouth = new T.Mesh(new T.BoxGeometry(0.6, 0.5, 0.4), dark); mouth.position.set(0, 0.45, 0.85); fur.add(mouth);
    const glow = new T.Mesh(new T.PlaneGeometry(0.44, 0.34), new T.MeshBasicMaterial({ color: 0xff8a2e })); glow.position.set(0, 0.45, 1.06); fur.add(glow);
    const fLight = new T.PointLight(0xff9636, 6, 9, 2); fLight.position.set(0, 1, 1.2); fur.add(fLight);
    fur.position.set(33.5, 0, 24.5); S.add(fur);
    this.furnace = { pos: new T.Vector3(33.5, 0, 24.5), light: fLight };
    this.colliders.push({ x: 33.5, z: 24.5, r: 1.35 });""",
"""    const fKit = this.furnaceKit();
    const fgy = (typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.ready) ? GRIM_WORLD.height(33.5, 24.5) : 0;
    const fRec = fKit.build({ seed: 7, x: 33.5, y: fgy, z: 24.5,
      heightAt: (hx, hz) => ((typeof GRIM_WORLD !== 'undefined' && GRIM_WORLD.ready) ? GRIM_WORLD.height(hx, hz) : fgy) });
    S.add(fRec.g);
    if (fRec.light) (this.decorLights = this.decorLights || []).push(fRec.light);
    this.furnace = { pos: new T.Vector3(33.5, 0, 24.5), light: fRec.light, kit: fKit, rec: fRec, snd: null };
    this.colliders.push({ x: 33.5, z: 24.5, r: fRec.radius });
    // the station's furniture pushes back too: bellows, mold bench, ore trough
    this.colliders.push({ x: 31.72, z: 25.16, r: 0.8 });
    this.colliders.push({ x: 32.45, z: 25.52, r: 0.5 });
    this.colliders.push({ x: 34.72, z: 25.18, r: 0.6 });""",
    'buildCampForge uses the kit')

# ---------------------------------------------------------------------------
# frame loop: tick the kit, run the roar by proximity
# ---------------------------------------------------------------------------
sub("    if (this.furnace) this.furnace.light.intensity = 5.4 + Math.sin(this.worldT * 9.7) * 1.2;",
"""    if (this.furnace) {
      this.furnace.light.intensity = 5.4 + Math.sin(this.worldT * 9.7) * 1.2;
      if (this.furnace.kit) this.furnace.kit.tick(this.worldT);
      // the roar reaches further than a campfire and surges with the bellows
      if (this.ac && this.started && this.me) {
        const fd = Math.hypot(this.furnace.pos.x - this.me.pos.x, this.furnace.pos.z - this.me.pos.z);
        if (fd < 24 && !this.furnace.snd && this.furnace.kit) this.furnace.snd = this.furnace.kit.sound(this.ac, this.master, { gain: 0.6 });
        else if (fd > 28 && this.furnace.snd) { this.furnace.snd.stop(); this.furnace.snd = null; }
        if (this.furnace.snd) this.furnace.snd.setDistance(fd, 28);
      }
    }""",
    'kit tick + proximity roar')

# ---------------------------------------------------------------------------
# smelting: every ore in the game, one key
# ---------------------------------------------------------------------------
sub("""    if (this.invCount('IRON ORE') < 1) { this.banner('THE FURNACE', 'NO IRON ORE — MINE THE STUDDED ROCKS (PICKAXE, SLOT 4)', false, 3200); return true; }
    if (this.canAccept('IRON BAR', 1) < 1) { this.packFullNote(); return true; }""",
"""    const pick = this.smeltPick();
    if (!pick) {
      const anyOre = this.SMELTS().some(r => this.invCount(r[0]) > 0);
      this.banner('THE FURNACE', anyOre
        ? 'YOUR SMITHING IS TOO LOW FOR THAT ORE'
        : 'NOTHING TO SMELT — BRING COPPER, IRON OR GOLD ORE', false, 3200);
      return true;
    }
    if (this.canAccept(pick[1], 1) < 1) { this.packFullNote(); return true; }""",
    'trySmelt picks any smeltable ore')

# the cycle: re-pick every bar so a mixed pack flows straight through
sub("""        this.smeltT += dt;
        if (this.smeltT >= 1.1) {
          this.smeltT = 0;
          if (this.canAccept('IRON BAR', 1) < 1) { this.smelting = false; this.packFullNote(); }
          else if (!this.takeItem('IRON ORE', 1)) { this.smelting = false; this.banner('OUT OF ORE', 'MINE MORE — THE STUDDED ROCKS', false, 2600); }
          else {
            this.addItem('IRON BAR', 1); this.awardXp('SMITHING', 16);
            this.spark(this.furnace.pos.clone().add(new T.Vector3(0, 1.2, 0.9)), 0xffa040, 10);
            this.sfx('break');
            if (this.invCount('IRON ORE') < 1) this.smelting = false;
          }
        }""",
"""        this.smeltT += dt;
        if (this.smeltT >= 1.1) {
          this.smeltT = 0;
          const r = this.smeltPick();
          if (!r) { this.smelting = false; this.banner('OUT OF ORE', 'MINE MORE — COPPER, IRON OR GOLD', false, 2600); }
          else if (this.canAccept(r[1], 1) < 1) { this.smelting = false; this.packFullNote(); }
          else if (!this.takeItem(r[0], 1)) { this.smelting = false; }
          else {
            this.addItem(r[1], 1); this.awardXp('SMITHING', r[3]);
            this.spark(this.furnace.pos.clone().add(new T.Vector3(0, 0.75, 1.35)), 0xffa040, 10);
            if (this.furnace.kit && this.ac) this.furnace.kit.pour(this.ac, this.master, { gain: 0.5 });
            else this.sfx('break');
            if (!this.smeltPick()) this.smelting = false;
          }
        }""",
    'smelt cycle runs the ore ladder')

# the ladder itself, next to trySmelt
sub('  trySmelt() {',
'''  // ore -> bar, level gate, xp. Priority order: cheap ore first, so a mixed
  // pack burns copper before it touches gold.
  SMELTS() {
    return [
      ['COPPER ORE', 'COPPER BAR', 1, 10],
      ['IRON ORE', 'IRON BAR', 1, 16],
      ['GOLD ORE', 'GOLD BAR', 40, 56]
    ];
  }
  smeltPick() {
    const sm = this.lvl(this.skills.SMITHING || 0);
    for (const r of this.SMELTS()) {
      if (this.invCount(r[0]) > 0 && sm >= r[2] && this.canAccept(r[1], 1) > 0) return r;
    }
    // a full pack for one bar kind should not silently skip to the next ore
    for (const r of this.SMELTS()) {
      if (this.invCount(r[0]) > 0 && sm >= r[2]) return r;
    }
    return null;
  }
  trySmelt() {''',
    'the smelt ladder')

# prompt copy
sub("this.smelting ? 'PRESS F - STOP SMELTING' : 'PRESS F - SMELT IRON ORE', () => this.trySmelt());",
    "this.smelting ? 'PRESS F - STOP SMELTING' : 'PRESS F - SMELT ORE', () => this.trySmelt());",
    'prompt covers every ore')

# ---------------------------------------------------------------------------
# the new bars: items and prices
# ---------------------------------------------------------------------------
IRON_DEF = """def('IRON BAR',      { value: 14, icon: svg('<path d="M4 20.4 L8.6 12 L25.4 12 L26 20.4 Z" fill="#aab3bf" stroke="' + O + '" stroke-width="1.8"/>' +"""
assert s.count(IRON_DEF) == 1, 'iron bar def moved'
i = s.find(IRON_DEF)
j = s.find('def(', i + 10)
ironFull = s[i:j]
copper = ironFull.replace("'IRON BAR',      { value: 14,", "'COPPER BAR',    { value: 9,") \
                 .replace('#aab3bf', '#c07a4a').replace('#d8dee6', '#e0a476').replace('#ffffff', '#f2d0ae')
gold = ironFull.replace("'IRON BAR',      { value: 14,", "'GOLD BAR',      { value: 80,") \
               .replace('#aab3bf', '#d9a93c').replace('#d8dee6', '#f0d270').replace('#ffffff', '#fdf0be')
s = s[:j] + copper + gold + s[j:]
print('  ok: COPPER BAR and GOLD BAR defined')

sub("'IRON ORE': 10, 'IRON BAR': 26,", "'IRON ORE': 10, 'IRON BAR': 26, 'COPPER ORE': 6, 'COPPER BAR': 16, 'GOLD ORE': 45, 'GOLD BAR': 130,",
    'trader prices the new bars and ores')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 54 applied, %+d bytes' % (len(s) - len(io.open(SRC, encoding='utf-8').read()) + len(s) - 0))
