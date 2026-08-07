#!/usr/bin/env python3
"""Patch 55: the trees and the ore nodes, rebuilt from the ground up.

Kevin's brief: redo the starter-tier tree models from scratch in the
anvil/furnace art style; make the fell read as ONE trunk splitting off its
stump (matching splinter faces, hinged at the break); keep the stump system;
give the whole sequence real sound - chop, crack, groan, whoosh, ground hit -
tuned once and reused by every tree. Then the iron vein as the template ore
node: nuggets sunk in visible crater sockets, honest full and EMPTIED states
(bare sockets plus rubble), per-ore nugget identity on the shared base, and
the mining sounds to match.

Models come from model-lab/tree.js and model-lab/orenode.js, reviewed on the
turntable; sounds were generated with ElevenLabs via harness/sfx.py (see the
MANIFEST for the prompts), takes picked by envelope, end-trimmed and
re-encoded (113 KB of base64 total). The fall animation is TIMED TO THE
RECORDING: the tree-fell take cracks at 0.05s and lands its crash at 3.0s,
so the fx holds a shivering lean through the crack, accelerates over from
0.9s, and thuds exactly when the audio does.

Integration map:
  1. natureKits(): grim-kit + both modules inlined once, shared by both.
  2. makeTreeBroadleaf/makeOreRock/makeZoneOre become thin delegates, same
     return contracts ({g, fell, canopies, stump} / {g, studs}) plus the new
     `rubble` group.
  3. makeZoneOre's world call site now passes the node KIND, so copper, coal,
     gold, salt, saltpeter, glass sand, obsidian and ember crystal each get
     their own nuggets. The editor's call keeps the old signature and falls
     back to the generic stone look.
  4. resourceDepleted/Respawned handle rubble, play the new mining chip +
     collapse layers, and launch the retimed 5.4s fall.
  5. sfx(): chop and mine rotations widen to four variants (the new takes
     join the audio track's a/b/c), and treefell / treeimpact / orechip /
     oredeplete map to the new samples with the old sounds as fallbacks.
  6. Six new samples enter the bundle's SFX_SAMPLES table.
"""
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
KIT = os.path.join(HERE, '..', '..', 'model-lab', 'grim-kit.js')
TREE = os.path.join(HERE, '..', '..', 'model-lab', 'tree.js')
ORE = os.path.join(HERE, '..', '..', 'model-lab', 'orenode.js')
ENTRIES = '/tmp/sfx-entries.js'

s = io.open(SRC, encoding='utf-8').read()

def sub(old, new, why):
    global s
    assert s.count(old) == 1, 'anchor x%d: %s' % (s.count(old), why)
    s = s.replace(old, new)
    print('  ok:', why)

def strip_module(path, banner):
    m = io.open(path, encoding='utf-8').read()
    m = re.sub(r'import \{[\s\S]*?\} from \'\./grim-kit\.js\';\n', '', m)
    m = m.replace('export function ', 'function ').replace('export const ', 'const ')
    m = re.sub(r'\A// GRIM WORLD: ' + banner + r'[\s\S]*?\n\n(?=import|function|const|//|export)', '', m, count=1)
    return m

kitSrc = io.open(KIT, encoding='utf-8').read()
kitSrc = kitSrc.replace('export function ', 'function ').replace('export const ', 'const ')
kitSrc = re.sub(r'\A(//.*\n)+', '', kitSrc)
treeSrc = strip_module(TREE, 'the trees')
oreSrc = strip_module(ORE, 'the ore nodes')

full = kitSrc + '\n' + treeSrc + '\n' + oreSrc
full = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in full.split('\n'))

METHOD = '''  // ---- trees and ore nodes -------------------------------------------------
  // Built from model-lab/tree.js + orenode.js + grim-kit.js by patch 55. Do
  // not hand-edit this block: change the lab modules, review with the
  // turntable pages, and rebuild. The lab and the game run the same source.
  natureKits() {
    if (this._natKits) return this._natKits;
    const T = this.T;
{BODY}
    this._natKits = { tree: makeTreeKit(T), ore: makeOreNodeKit(T) };
    return this._natKits;
  }

'''.replace('{BODY}', full)

sub('  campfireKit() {\n    if (this._cfKit) return this._cfKit;',
    METHOD + '  campfireKit() {\n    if (this._cfKit) return this._cfKit;',
    'natureKits injected')

# ---------------------------------------------------------------------------
# builders become delegates
# ---------------------------------------------------------------------------
start = '  makeTreeBroadleaf(rand, big) {'
end = 'return { g, fell, canopies, stump: stumpG };\n  }'
assert s.count(start) == 1 and s.count(end) == 1, 'broadleaf span moved'
i0 = s.index(start); i1 = s.index(end) + len(end)
s = s[:i0] + '''  makeTreeBroadleaf(rand, big) {
    const kit = this.natureKits().tree;
    const built = kit.build({ kind: big ? 'oak' : 'tree', seed: 1 + Math.floor(rand() * 99991) });
    return { g: built.g, fell: built.fell, canopies: built.canopies, stump: built.stump };
  }''' + s[i1:]
print('  ok: makeTreeBroadleaf delegates')

start = '  makeOreRock(rand) {'
end = "return { g, studs };\n  }"
assert s.count(start) == 1, 'ore rock start moved'
assert s.count(end) == 1, 'ore rock end moved'
i0 = s.index(start); i1 = s.index(end) + len(end)
s = s[:i0] + '''  makeOreRock(rand) {
    const kit = this.natureKits().ore;
    const built = kit.build({ kind: 'iron', seed: 1 + Math.floor(rand() * 99991), sc: 1.15 });
    return { g: built.g, studs: built.studs, rubble: built.rubble };
  }''' + s[i1:]
print('  ok: makeOreRock delegates')

start = '  makeZoneOre(look, sc, seed, tint) {'
end = 'return { g: g, studs: [studs] };\n  }'
assert s.count(start) == 1 and s.count(end) == 1, 'zone ore span moved'
i0 = s.index(start); i1 = s.index(end) + len(end)
s = s[:i0] + '''  makeZoneOre(look, sc, seed, tint, kind) {
    const kit = this.natureKits().ore;
    const st = new this.T.Color(look && look.stone !== undefined ? look.stone : 0x6e6a5e);
    const built = kit.build({ kind: kind || 'stone', seed: (seed % 99991) + 1, sc: sc, stone: [st.r, st.g, st.b] });
    return { g: built.g, studs: built.studs, rubble: built.rubble };
  }''' + s[i1:]
print('  ok: makeZoneOre delegates')

sub("built = this.makeZoneOre(look, p.sc, seed, this.NODE_TINT(p.kind));",
    "built = this.makeZoneOre(look, p.sc, seed, this.NODE_TINT(p.kind), p.kind);",
    'zone call site passes the kind')

# registrations carry the rubble group
sub("        studs: built.studs || null, hp: nd.hp, max: nd.hp, dead: false, respawn: 0, streamed: true",
    "        studs: built.studs || null, rubble: built.rubble || null, hp: nd.hp, max: nd.hp, dead: false, respawn: 0, streamed: true",
    'streamed nodes carry rubble')
sub("this.resources.push({ kind: 'rock', g, studs: rockT.studs, hp: 4, max: 4, dead: false, respawn: 0 });",
    "this.resources.push({ kind: 'rock', g, studs: rockT.studs, rubble: rockT.rubble, hp: 4, max: 4, dead: false, respawn: 0 });",
    'starter vein carries rubble')

# a node found empty on stream-in must come back with its rubble out too
sub("""    if (skill === 'MINING') {
      if (R.studs) R.studs.forEach(s2 => { s2.visible = false; });
      if (p) this.spark(p, 0xd88a4a, 16);
      this.sfx('break');
    } else if (skill === 'FORAGING') {""",
"""    if (skill === 'MINING') {
      if (R.studs) R.studs.forEach(s2 => { s2.visible = false; });
      if (R.rubble) R.rubble.visible = true;
      if (p) this.spark(p, 0xd88a4a, 16);
      // the chunk coming free, then the spent vein crumbling under it
      this.sfx('orechip');
      this.sfx('oredeplete', 0.22);
    } else if (skill === 'FORAGING') {""",
    'mining deplete: rubble + chip/collapse layers')

sub("""    } else {
      if (R.stump) R.stump.visible = true;
      const fm = R.fell || R.g;
      fm.matrixAutoUpdate = true;                     // the fall animates this node
      this.fx.push({ kind: 'fall', mesh: fm, life: 2.4, max: 2.4 });
      this.sfx('timber');
    }""",
"""    } else {
      if (R.stump) R.stump.visible = true;
      const fm = R.fell || R.g;
      fm.matrixAutoUpdate = true;                     // the fall animates this node
      // Timed to the tree-fell recording: crack at 0, crash at 3.0s. The fx
      // holds a shivering lean through the crack and lands ON the crash.
      this.fx.push({ kind: 'fall', mesh: fm, life: 5.4, max: 5.4, big: R.kind !== 'tree' });
      this.sfx('treefell');
    }""",
    'tree deplete: retimed fall + the recording')

sub("""    if (R.stump) R.stump.visible = false;
    if (R.fell) { R.fell.visible = true; R.fell.rotation.z = 0; R.fell.position.y = 0; }
    if (R.studs) R.studs.forEach(s2 => { s2.visible = true; });""",
"""    if (R.stump) R.stump.visible = false;
    if (R.fell) { R.fell.visible = true; R.fell.rotation.z = 0; R.fell.position.y = 0; }
    if (R.studs) R.studs.forEach(s2 => { s2.visible = true; });
    if (R.rubble) R.rubble.visible = false;""",
    'respawn clears the rubble')

# ---------------------------------------------------------------------------
# the fall, retimed to the take
# ---------------------------------------------------------------------------
sub("""      if (f.kind === 'fall') {
        // Hinged at the stump: accelerates over, THUDS onto the ground,
        // rests a beat still joined at the base, then sinks away.
        const t = f.max - f.life;
        if (t < 1.1) {
          const u = t / 1.1;
          f.mesh.rotation.z = u * u * 1.45;
        } else {
          f.mesh.rotation.z = 1.45;
          if (!f.thud) { f.thud = true; this.sfx('break'); this.shake = Math.min(1, this.shake + 0.14); }
          if (t > 1.9) f.mesh.position.y = -((t - 1.9) / 0.5) * 2.6;
        }
        if (f.life <= 0) { f.mesh.visible = false; f.mesh.rotation.z = 0; f.mesh.position.y = 0; this.fx.splice(i, 1); }
        continue;
      }""",
"""      if (f.kind === 'fall') {
        // Timed to the tree-fell recording: the crack lands at t=0, so the
        // tree SHIVERS and leans while the wood tears (0 to 0.9s), then
        // accelerates over and hits the ground at exactly 3.0s - the moment
        // the recording's crash lands - bounces once, rests, and sinks.
        const t = f.max - f.life;
        const A = 1.58;
        if (t < 0.9) {
          const u = t / 0.9;
          f.mesh.rotation.z = u * u * 0.10 + Math.sin(t * 46) * 0.008 * (1 - u * 0.6);
        } else if (t < 3.0) {
          const u = (t - 0.9) / 2.1;
          f.mesh.rotation.z = 0.10 + u * u * (A - 0.10);
        } else {
          if (!f.thud) {
            f.thud = true;
            this.shake = Math.min(1, this.shake + (f.big ? 0.2 : 0.12));
            if (f.big) this.sfx('treeimpact');
          }
          // one bounce off the ground, then still
          const b = t - 3.0;
          f.mesh.rotation.z = A - (b < 0.45 ? Math.sin(b / 0.45 * Math.PI) * 0.05 : 0);
          if (t > 4.6) f.mesh.position.y = -((t - 4.6) / 0.8) * 2.8;
        }
        if (f.life <= 0) { f.mesh.visible = false; f.mesh.rotation.z = 0; f.mesh.position.y = 0; this.fx.splice(i, 1); }
        continue;
      }""",
    'the fall lands on the crash')

# ---------------------------------------------------------------------------
# sfx: four-variant gathering rotation + the new one-shots
# ---------------------------------------------------------------------------
sub("    const GVAR = { chop: 3, mine: 3 };",
    "    const GVAR = { chop: 4, mine: 4 };", 'four gathering variants')
sub("      const pick = name + '-' + 'abc'[this._gAlt % GVAR[name]];",
    "      const pick = name + '-' + 'abcd'[this._gAlt % GVAR[name]];", 'rotation includes d')
sub("""    if ((name === 'forage' || name === 'timber') && this._samples
        && this._samples.ready() && this._samples.has(name)) {""",
"""    // The felled-tree and mining one-shots, with the older sounds as
    // fallbacks while the samples decode.
    const NAT = {
      treefell: ['tree-fell', 0.9, 40, 'timber'],
      treeimpact: ['tree-impact', 0.8, 50, 'break'],
      orechip: ['mine-chip', 0.7, 60, 'break'],
      oredeplete: ['mine-deplete', 0.55, 45, null]
    };
    if (NAT[name]) {
      const nv = NAT[name];
      if (this._samples && this._samples.ready() && this._samples.has(nv[0])) {
        this._samples.play(nv[0], { gain: nv[1], detune: (Math.random() * 2 - 1) * nv[2],
                                    when: t ? this.ac.currentTime + t : undefined });
        return;
      }
      if (!nv[3]) return;
      name = nv[3];
    }
    if ((name === 'forage' || name === 'timber') && this._samples
        && this._samples.ready() && this._samples.has(name)) {""",
    'new one-shots with fallbacks')

# the new takes join the sample table as chop-d and mine-d plus the one-shots
entries = io.open(ENTRIES, encoding='utf-8').read()
entries = entries.replace("  'tree-chop':", "  'chop-d':").replace("  'mine-strike':", "  'mine-d':")
sub("    const SFX_SAMPLES = {\n      'anvil-strike':",
    "    const SFX_SAMPLES = {\n" + '\n'.join('  ' + ln for ln in entries.split('\n')) + "\n      'anvil-strike':",
    'six samples join the table')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 55 applied')
