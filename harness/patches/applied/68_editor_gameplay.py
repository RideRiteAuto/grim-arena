#!/usr/bin/env python3
"""Placed objects become REAL, and the whole world becomes editable.

Kevin's two reports after his first real building session:

  1. He could not select or delete the things the world grew: zone trees, ore
     veins, boulders. Only objects he had placed himself could be picked.
  2. Objects he placed showed up in the live game but were scenery. A placed
     copper vein could not be mined, a placed tree could not be felled, and a
     placed furnace/anvil/bank did nothing. As he put it, that is the whole
     point of building the editor.

Both come from the same root: the editor could author GEOMETRY but never
authored GAMEPLAY, and it could only ever see its own objects.

This patch is the game-side half. The editor-side half is in editor-tools.js
(nodes and stations register as their chunk streams in) and editor-ui.js (the
picker sees the whole world). What lands here is:

  1. Stable ids on the four hand-placed resource sets (camp trees, camp rocks,
     the swamp oaks, the town pines). They had no nid at all, so there was no
     way to name one in order to delete it. Ids are derived from the rounded
     world position, which is stable because world build is deterministic, so
     every client computes the same id for the same tree.

  2. applyGoneFixed(), which drops hand-placed resources Kevin has deleted.
     Called at the end of world build AND again if the edit layer lands late
     (the normal case: boot never waits for the network).

  3. A STATION REGISTRY. This is the important one. The furnace, the anvil and
     the bank were singletons: `this.furnace`, `this.anvil`, `this.bankPos`.
     Every reachability test in the game asked "am I near THE furnace", so a
     furnace Kevin placed in a new town could never answer, no matter how
     correct its geometry was. They now register in one list that the camp
     forge and the Bank of Hollowrest join at world build (so nothing about
     existing content changes) and that placed objects join as their chunk
     streams in. interactCandidates, trySmelt, tryForge and tryBank all read
     the registry, so a placed furnace smelts exactly like the camp one.

     Campfires already used an array and already worked, which is the shape
     everything else is being moved to here.

     The active station's position is remembered when smelting or smithing
     starts (_smeltPos / _smithPos) so the tick's walk-away check and the
     spark positions follow the furnace you are ACTUALLY standing at rather
     than the camp one you may be a kilometre from.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()

def sub(old, new, what):
    global s
    n = s.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (what, n)
    s = s.replace(old, new, 1)

# --- 1. stable ids on the four hand-placed resource sets ---------------------
# Each is keyed off the mesh's final world position, which every client
# computes identically, so "this tree" means the same tree everywhere.

sub(
    "      this.resources.push({ kind: 'tree', g, fell: tree.fell, stump: tree.stump, hp: 3, max: 3, dead: false, respawn: 0 });",
    "      this.resources.push({ kind: 'tree', g, nid: this.fixedNid_('tree', g), fell: tree.fell, stump: tree.stump, hp: 3, max: 3, dead: false, respawn: 0 });",
    'camp broadleaf nid'
)
sub(
    "      this.resources.push({ kind: 'rock', g, studs: rockT.studs, rubble: rockT.rubble, hp: 4, max: 4, dead: false, respawn: 0 });",
    "      this.resources.push({ kind: 'rock', g, nid: this.fixedNid_('rock', g), studs: rockT.studs, rubble: rockT.rubble, hp: 4, max: 4, dead: false, respawn: 0 });",
    'camp rock nid'
)
sub(
    "      this.resources.push({ kind: 'oak', g, fell: oakT.fell, stump: oakT.stump, hp: 5, max: 5, dead: false, respawn: 0 });",
    "      this.resources.push({ kind: 'oak', g, nid: this.fixedNid_('oak', g), fell: oakT.fell, stump: oakT.stump, hp: 5, max: 5, dead: false, respawn: 0 });",
    'swamp oak nid'
)
sub(
    "      this.resources.push({ kind: 'tree', g, fell: pineT.fell, stump: pineT.stump, hp: 4, max: 4, dead: false, respawn: 0 });",
    "      this.resources.push({ kind: 'tree', g, nid: this.fixedNid_('pine', g), fell: pineT.fell, stump: pineT.stump, hp: 4, max: 4, dead: false, respawn: 0 });",
    'town pine nid'
)

# --- 2 and 3. the helpers, parked next to allResources ----------------------
sub(
    "  // The world's harvestables in one list: the fixed set built at world load",

    "  // A stable id for a HAND-PLACED resource (the camp trees and rocks, the\n"
    "  // swamp oaks, the town pines). These are built once at world load rather\n"
    "  // than grown by the dressing pass, so they never had a node id and there\n"
    "  // was no way to name one in order to delete it from the editor. The id is\n"
    "  // the rounded world position at half-metre resolution: world build is\n"
    "  // deterministic, so every client derives the same id for the same tree,\n"
    "  // which is the property the removal list depends on.\n"
    "  fixedNid_(kind, g) {\n"
    "    return 'fx:' + kind + ':' + Math.round(g.position.x * 2) + ':' + Math.round(g.position.z * 2);\n"
    "  }\n"
    "\n"
    "  // Hand-placed resources Kevin has deleted in the editor. The dressing pass\n"
    "  // checks GRIM_EDIT.gone() for the props it grows, but these are not grown,\n"
    "  // so they need their own sweep. Safe to run repeatedly, and safe to run\n"
    "  // before the layer has landed (gone() is false for everything then).\n"
    "  applyGoneFixed() {\n"
    "    if (!this.resources || !this.resources.length) return 0;\n"
    "    if (typeof GRIM_EDIT === 'undefined' || !GRIM_EDIT.on) return 0;\n"
    "    let n = 0;\n"
    "    for (let i = this.resources.length - 1; i >= 0; i--) {\n"
    "      const R = this.resources[i];\n"
    "      if (!R || !R.nid || !GRIM_EDIT.gone(R.nid)) continue;\n"
    "      try { this.scene.remove(R.g); } catch (e) {}\n"
    "      this.resources.splice(i, 1);\n"
    "      n++;\n"
    "    }\n"
    "    return n;\n"
    "  }\n"
    "\n"
    "  // ---- station registry --------------------------------------------------\n"
    "  // Every interactable station in the world in one list. The furnace, the\n"
    "  // anvil and the bank used to be singletons (this.furnace, this.anvil,\n"
    "  // this.bankPos), which meant every reachability test in the game asked\n"
    "  // whether you were near THE furnace. A furnace Kevin placed in a new town\n"
    "  // could not answer that question however correct its geometry was, so it\n"
    "  // was scenery. The camp forge and the Bank of Hollowrest register here at\n"
    "  // world build, so nothing about existing content changes; placed stations\n"
    "  // register as their chunk streams in and deregister when it drops.\n"
    "  stationsList() { return (this._stations = this._stations || []); }\n"
    "  registerStation(kind, pos, extra) {\n"
    "    if (!kind || !pos) return null;\n"
    "    const st = Object.assign({ kind: kind, pos: pos }, extra || {});\n"
    "    this.stationsList().push(st);\n"
    "    return st;\n"
    "  }\n"
    "  unregisterStation(st) {\n"
    "    if (!st) return;\n"
    "    const L = this.stationsList();\n"
    "    const i = L.indexOf(st);\n"
    "    if (i >= 0) L.splice(i, 1);\n"
    "  }\n"
    "  // Nearest station of a kind within reach, or null. Planar distance, the\n"
    "  // same measure the interact prompt uses, so the prompt and the key can\n"
    "  // never disagree about which furnace you are standing at.\n"
    "  nearestStation(kind, maxD) {\n"
    "    if (!this.me) return null;\n"
    "    let best = null, bd = (maxD === undefined ? 3.2 : maxD);\n"
    "    for (const st of this.stationsList()) {\n"
    "      if (!st || st.kind !== kind || !st.pos) continue;\n"
    "      const d = Math.hypot(this.me.pos.x - st.pos.x, this.me.pos.z - st.pos.z);\n"
    "      if (d <= bd) { bd = d; best = st; }\n"
    "    }\n"
    "    return best;\n"
    "  }\n"
    "\n"
    "  // The world's harvestables in one list: the fixed set built at world load",
    'station registry + fixed helpers'
)

# --- register the camp forge's stations --------------------------------------
sub(
    "    this.furnace = { pos: new T.Vector3(33.5, 0, 24.5), light: fRec.light, kit: fKit, rec: fRec, snd: null };",
    "    this.furnace = { pos: new T.Vector3(33.5, 0, 24.5), light: fRec.light, kit: fKit, rec: fRec, snd: null };\n"
    "    this.registerStation('furnace', this.furnace.pos, { camp: true, kit: fKit });",
    'register camp furnace'
)
sub(
    "    this.anvil = { pos: new T.Vector3(36.2, 0, 23.2), face: avRec.face, rec: avRec };",
    "    this.anvil = { pos: new T.Vector3(36.2, 0, 23.2), face: avRec.face, rec: avRec };\n"
    "    this.registerStation('anvil', this.anvil.pos, { camp: true, face: avRec.face });",
    'register camp anvil'
)
sub(
    "    this.bankPos = new T.Vector3(TX - 8.6, 0, TZ - 3.0);",
    "    this.bankPos = new T.Vector3(TX - 8.6, 0, TZ - 3.0);\n"
    "    this.registerStation('bank', this.bankPos, { camp: true });",
    'register Hollowrest bank'
)

# --- 4. interactCandidates reads the registry --------------------------------
sub(
    "    add(this.bankPos, R.bank, 'PRESS F - OPEN YOUR BANK', () => this.tryBank());\n",
    "",
    'drop hardcoded bank candidate'
)
sub(
    "    if (this.furnace) add(this.furnace.pos, R.station,\n"
    "      this.furnOpen ? 'F - CLOSE THE FURNACE' : this.smelting ? 'PRESS F - STOP SMELTING' : 'PRESS F - SMELT ORE', () => this.trySmelt());\n"
    "    if (this.anvil) add(this.anvil.pos, R.station, this.anvOpen ? 'F - CLOSE THE ANVIL' : this.smithQ ? 'PRESS F - STOP SMITHING' : 'PRESS F - SMITH', () => this.tryForge());\n",

    "    // Stations come from the registry, so the camp forge, the Bank of\n"
    "    // Hollowrest and everything Kevin has placed are all offered the same\n"
    "    // way. Sorting by distance below already picks the nearest, which is\n"
    "    // what makes two furnaces in one town behave sensibly.\n"
    "    for (const st of this.stationsList()) {\n"
    "      if (!st || !st.pos) continue;\n"
    "      if (st.kind === 'furnace') {\n"
    "        add(st.pos, R.station,\n"
    "          this.furnOpen ? 'F - CLOSE THE FURNACE' : this.smelting ? 'PRESS F - STOP SMELTING' : 'PRESS F - SMELT ORE',\n"
    "          () => this.trySmelt());\n"
    "      } else if (st.kind === 'anvil') {\n"
    "        add(st.pos, R.station,\n"
    "          this.anvOpen ? 'F - CLOSE THE ANVIL' : this.smithQ ? 'PRESS F - STOP SMITHING' : 'PRESS F - SMITH',\n"
    "          () => this.tryForge());\n"
    "      } else if (st.kind === 'bank') {\n"
    "        add(st.pos, R.bank, 'PRESS F - OPEN YOUR BANK', () => this.tryBank());\n"
    "      }\n"
    "    }\n",
    'registry-driven station candidates'
)

# --- 5. the try* guards ------------------------------------------------------
sub(
    "  trySmelt() {\n"
    "    if (!this.furnace || !this.started || this.mode !== 'ai' || !this.worldOn) return false;\n"
    "    if (this.me.pos.distanceTo(this.furnace.pos) > 3.2) return false;",

    "  trySmelt() {\n"
    "    if (!this.started || this.mode !== 'ai' || !this.worldOn) return false;\n"
    "    // Whichever furnace is actually in reach, camp or placed. Its position\n"
    "    // is remembered so the smelting loop's walk-away check and its sparks\n"
    "    // follow this furnace rather than the camp one.\n"
    "    const _st = this.nearestStation('furnace', 3.2);\n"
    "    if (!_st) return false;\n"
    "    this._smeltPos = _st.pos;",
    'trySmelt via registry'
)
sub(
    "  tryForge() {\n"
    "    if (!this.anvil || !this.started || this.mode !== 'ai' || !this.worldOn) return false;\n"
    "    if (this.me.pos.distanceTo(this.anvil.pos) > 3.0) return false;",

    "  tryForge() {\n"
    "    if (!this.started || this.mode !== 'ai' || !this.worldOn) return false;\n"
    "    const _st = this.nearestStation('anvil', 3.0);\n"
    "    if (!_st) return false;\n"
    "    this._smithPos = _st.pos;\n"
    "    this._smithFace = _st.face || null;",
    'tryForge via registry'
)
sub(
    "    if (!this.bankPos || !this.me || this.mode !== 'ai' || !this.worldOn) return false;\n"
    "    if (Math.hypot(this.me.pos.x - this.bankPos.x, this.me.pos.z - this.bankPos.z) > 4.0) return false;",

    "    if (!this.me || this.mode !== 'ai' || !this.worldOn) return false;\n"
    "    if (!this.nearestStation('bank', 4.0)) return false;",
    'tryBank via registry'
)

# --- 6. the tick follows the station you are standing at ---------------------
sub(
    "      if (this.me.hp <= 0 || this.me.pos.distanceTo(this.furnace.pos) > 3.6) this.smelting = false;",
    "      const _fp = this._smeltPos || (this.furnace && this.furnace.pos);\n"
    "      if (this.me.hp <= 0 || !_fp || this.me.pos.distanceTo(_fp) > 3.6) this.smelting = false;",
    'smelt walk-away uses the active furnace'
)
sub(
    "            this.spark(this.furnace.pos.clone().add(new T.Vector3(0, 0.75, 1.35)), 0xffa040, 10);",
    "            this.spark(_fp.clone().add(new T.Vector3(0, 0.75, 1.35)), 0xffa040, 10);",
    'smelt sparks at the active furnace'
)
sub(
    "      if (this.me.hp <= 0 || this.me.pos.distanceTo(this.anvil.pos) > 3.6) this.smithQ = null;",
    "      const _ap = this._smithPos || (this.anvil && this.anvil.pos);\n"
    "      if (this.me.hp <= 0 || !_ap || this.me.pos.distanceTo(_ap) > 3.6) this.smithQ = null;",
    'smith walk-away uses the active anvil'
)
sub(
    "          this.spark((this.anvil.face || this.anvil.pos.clone().add(new T.Vector3(0, 0.8, 0)))\n"
    "            .clone().add(new T.Vector3(0, 0.03, 0)), 0xfff2c8, 8);",
    "          this.spark((this._smithFace || (this.anvil && this.anvil.face) || _ap.clone().add(new T.Vector3(0, 0.8, 0)))\n"
    "            .clone().add(new T.Vector3(0, 0.03, 0)), 0xfff2c8, 8);",
    'smith sparks at the active anvil'
)

# --- the minimap shows every forge, not just the camp one --------------------
sub(
    "    if (this.furnace) dot(this.furnace.pos.x, this.furnace.pos.z, '#ff9636', 2.2);",
    "    for (const st of this.stationsList()) {\n"
    "      if (!st || !st.pos) continue;\n"
    "      if (st.kind === 'furnace') dot(st.pos.x, st.pos.z, '#ff9636', 2.2);\n"
    "      else if (st.kind === 'bank') dot(st.pos.x, st.pos.z, '#c8a24a', 2.2);\n"
    "    }",
    'minimap shows every station'
)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('ok: station registry, fixed-resource ids, gameplay hooks')
