#!/usr/bin/env python3
"""Phase 1, part 1: gathering skills core.

Swaps the level curve onto the shared-rules formula (with a one-time save
migration off the old one), adds FORAGING as the eighth skill, defines the
tool ladder and every gather material as real items, and rewrites gatherCheck
so a refusal always names the exact requirement that failed.

Every replacement asserts a unique anchor first and the file is written ONCE
at the very end, so a stale anchor aborts without leaving a half-patched file.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ---------------------------------------------------------------- 1. the curve
sub(
    "  lvl(xp) { return Math.min(99, Math.max(1, Math.floor(Math.pow((xp || 0) / 60, 0.6)) + 1)); }\n"
    "  xpFor(l) { return Math.round(60 * Math.pow(Math.max(0, l - 1), 1 / 0.6)); }",

    "  // One curve for every skill, defined in shared-rules so the client and any\n"
    "  // future server check can never disagree. The old inline curve is kept in\n"
    "  // shared-rules as grimLegacyLevel purely so saves can be migrated off it.\n"
    "  lvl(xp) { return grimLevelFromXp(xp); }\n"
    "  xpFor(l) { return grimXpForLevel(l); }\n"
    "  // Skill XP was stored against the old curve. Convert once, keep the old\n"
    "  // values under a backup key for one release so this is reversible, and\n"
    "  // stamp the save so it never runs twice. Level and progress through it are\n"
    "  // both preserved: nobody drops a level.\n"
    "  migrateSkillCurve(store) {\n"
    "    if (!store || store.skillCurve === 2) return false;\n"
    "    const skills = store.skills || store;\n"
    "    const backup = {};\n"
    "    for (const k in skills) {\n"
    "      const v = Math.floor(Number(skills[k]));\n"
    "      if (!Number.isFinite(v) || v <= 0) continue;\n"
    "      backup[k] = v;\n"
    "      skills[k] = grimMigrateXp(v);\n"
    "    }\n"
    "    store.skillCurve = 2;\n"
    "    store.skillXpV1 = backup;\n"
    "    return true;\n"
    "  }",
    'lvl/xpFor')

# ------------------------------------------------- 2. FORAGING in the skill set
sub(
    "    for (const sk of ['MELEE', 'MAGIC', 'RANGED', 'HITPOINTS', 'WOODCUTTING', 'MINING', 'SMITHING']) this.skills[sk] = this.skills[sk] || 0;\n"
    "    this.invLoad();",

    "    { const wrap = { skills: this.skills, skillCurve: Number(this.skills.__curve) || 0 };\n"
    "      if (this.migrateSkillCurve(wrap)) {\n"
    "        this.skills.__curve = 2;\n"
    "        try { localStorage.setItem('grim-skills', JSON.stringify(this.skills)); } catch (e) {}\n"
    "      } }\n"
    "    for (const sk of this.SKILL_KEYS()) this.skills[sk] = this.skills[sk] || 0;\n"
    "    this.invLoad();",
    'boot skill list')

sub(
    "      this.skills = {};\n"
    "      for (const sk of ['MELEE', 'MAGIC', 'RANGED', 'HITPOINTS', 'WOODCUTTING', 'MINING', 'SMITHING']) {\n"
    "        const v = raw.skills && Math.floor(Number(raw.skills[sk]));\n"
    "        this.skills[sk] = (Number.isFinite(v) && v >= 0) ? v : 0;\n"
    "      }",

    "      this.skills = {};\n"
    "      for (const sk of this.SKILL_KEYS()) {\n"
    "        const v = raw.skills && Math.floor(Number(raw.skills[sk]));\n"
    "        this.skills[sk] = (Number.isFinite(v) && v >= 0) ? v : 0;\n"
    "      }\n"
    "      // Saves written before the zone update carry the old curve.\n"
    "      { const wrap = { skills: this.skills, skillCurve: Number(raw.skillCurve) || 0 };\n"
    "        if (this.migrateSkillCurve(wrap)) { this._curveMigrated = true; this.scheduleSave && this.scheduleSave(); } }",
    'profile skill load')

sub(
    "    this.skills = { MELEE: 0, MAGIC: 0, RANGED: 0, HITPOINTS: 0, WOODCUTTING: 0, MINING: 0, SMITHING: 0 };",
    "    this.skills = {};\n"
    "    for (const sk of this.SKILL_KEYS()) this.skills[sk] = 0;\n"
    "    this._curveMigrated = true;",
    'freshCharacter skills')

# New characters get the crude pair. Veterans keep the iron tools they already
# own, which the ladder reads as tier 3: an upgrade, not a rename.
sub(
    "    for (const t of ['OAK STAFF', 'HUNTING BOW', 'IRON PICKAXE', 'IRON AXE']) this.inv[i++] = { item: t, qty: 1 };",
    "    for (const t of ['OAK STAFF', 'HUNTING BOW', 'CRUDE PICK', 'CRUDE AXE']) this.inv[i++] = { item: t, qty: 1 };",
    'freshCharacter tools')

sub(
    "      for (const t of ['OAK STAFF', 'HUNTING BOW', 'IRON PICKAXE', 'IRON AXE']) w[t] = (w[t] || 0) + 1;",
    "      for (const t of ['OAK STAFF', 'HUNTING BOW', 'CRUDE PICK', 'CRUDE AXE']) w[t] = (w[t] || 0) + 1;",
    'starter grant tools')

# Only the freshCharacter bar moves to the crude pair. The two pre-load
# defaults stay on iron so a veteran whose save carries no bar layout still
# opens with the tools they actually own.
sub(
    "      SHIELD: { item: 'IRON KITE SHIELD', qty: 1 }, LEGS: { item: 'IRON PLATELEGS', qty: 1 }\n"
    "    };\n"
    "    this.bar = ['IRON SCIMITAR', 'OAK STAFF', 'HUNTING BOW', 'IRON PICKAXE', 'IRON AXE', 'GRIM CLEAVER'];",
    "      SHIELD: { item: 'IRON KITE SHIELD', qty: 1 }, LEGS: { item: 'IRON PLATELEGS', qty: 1 }\n"
    "    };\n"
    "    this.bar = ['IRON SCIMITAR', 'OAK STAFF', 'HUNTING BOW', 'CRUDE PICK', 'CRUDE AXE', 'GRIM CLEAVER'];",
    'freshCharacter bar')

# ------------------------------------------------- 3. tool + material item defs
sub(
    "    def('GRIM CLEAVER',    { stack: false, slot: 'WEAPON', hands: 2, wieldAs: 5, style: 'melee', value: 900,",

    "    // ---- the gathering ladder -------------------------------------------\n"
    "    // Tools and materials are generated from the shared-rules tables rather\n"
    "    // than hand-written, so a tier can never exist in the gate check and be\n"
    "    // missing from the item list. IRON AXE and IRON PICKAXE are already\n"
    "    // defined above as tier 3 and are skipped here.\n"
    "    {\n"
    "      const GG = GRIM_RULES.GATHER;\n"
    "      const TINT = { 1: '#8a7a62', 2: '#c07a3e', 3: '#aab3bf', 4: '#d6dae2', 5: '#4a3f52', 6: '#f0d878' };\n"
    "      const haft = '<line x1=\"12\" y1=\"6\" x2=\"18\" y2=\"27\" stroke=\"' + WD + '\" stroke-width=\"3\"/>';\n"
    "      const haft2 = '<line x1=\"15\" y1=\"9\" x2=\"15\" y2=\"27\" stroke=\"' + WD + '\" stroke-width=\"3\"/>';\n"
    "      for (const t of GG.TOOLS) {\n"
    "        const c = TINT[t.tier] || '#aab3bf';\n"
    "        const val = 40 * t.tier * t.tier;\n"
    "        const st = { att: t.tier, str: t.tier, def: 0, mag: 0, rng: 0 };\n"
    "        if (t.axe && !R[t.axe]) def(t.axe, { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 4, style: 'melee', value: val, tool: 'axe', toolTier: t.tier, stats: st,\n"
    "          icon: svg(haft + '<path d=\"M11 4 Q22 3 24 12 Q16 13 10 9 Z\" fill=\"' + c + '\" stroke=\"' + O + '\" stroke-width=\"1.8\"/>') });\n"
    "        if (t.pick && !R[t.pick]) def(t.pick, { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 3, style: 'melee', value: val, tool: 'pick', toolTier: t.tier, stats: st,\n"
    "          icon: svg(haft2 + '<path d=\"M4 10 Q15 2 26 10 Q15 7 4 10 Z\" fill=\"' + c + '\" stroke=\"' + O + '\" stroke-width=\"1.8\"/>') });\n"
    "        if (t.sickle && !R[t.sickle]) def(t.sickle, { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 4, style: 'melee', value: val, tool: 'sickle', toolTier: t.tier, stats: st,\n"
    "          icon: svg('<path d=\"M8 26 L14 14\" stroke=\"' + WD + '\" stroke-width=\"3\" stroke-linecap=\"round\"/><path d=\"M13 15 Q24 6 25 17 Q18 12 13 15 Z\" fill=\"' + c + '\" stroke=\"' + O + '\" stroke-width=\"1.6\"/>') });\n"
    "      }\n"
    "      // Every yield in the node table becomes a stackable material, plus the\n"
    "      // three bonus drops. Nothing a node can hand you is undefined.\n"
    "      const MC = { WOODCUTTING: '#8a6b3a', MINING: '#c8842a', FORAGING: '#4fb3a0' };\n"
    "      const mats = {};\n"
    "      for (const k in GG.NODES) { const nd = GG.NODES[k]; mats[nd.yield[0]] = MC[nd.skill] || '#9a9484'; }\n"
    "      for (const sk in GG.BONUS) mats[GG.BONUS[sk]] = MC[sk] || '#9a9484';\n"
    "      for (const id in mats) {\n"
    "        if (R[id]) continue;\n"
    "        def(id, { stack: true, value: 6,\n"
    "          icon: svg('<circle cx=\"15\" cy=\"16\" r=\"9\" fill=\"' + mats[id] + '\" stroke=\"' + O + '\" stroke-width=\"2\"/>') });\n"
    "      }\n"
    "    }\n"
    "    def('GRIM CLEAVER',    { stack: false, slot: 'WEAPON', hands: 2, wieldAs: 5, style: 'melee', value: 900,",
    'tool + material defs')

# ------------------------------------------------------- 4. skill list helpers
sub(
    "  SKILL_INFO() {\n"
    "    return [",

    "  // The one list of skills. Everything that iterates skills reads this, so\n"
    "  // adding a ninth never means hunting for array literals again.\n"
    "  SKILL_KEYS() { return ['MELEE', 'MAGIC', 'RANGED', 'HITPOINTS', 'WOODCUTTING', 'MINING', 'FORAGING', 'SMITHING']; }\n"
    "\n"
    "  // Which tool a skill swings, and the best tier of it the player is\n"
    "  // carrying. Foraging tier 1 is bare hands, so it can never be below 1.\n"
    "  toolTierFor(skill) {\n"
    "    const kind = GRIM_RULES.GATHER.TOOL_FOR[skill];\n"
    "    if (!kind) return 0;\n"
    "    let best = (kind === 'sickle') ? 1 : 0;\n"
    "    const seen = (id) => {\n"
    "      if (!id) return;\n"
    "      for (const t of GRIM_RULES.GATHER.TOOLS) if (t[kind] === id && t.tier > best) best = t.tier;\n"
    "    };\n"
    "    for (const c of (this.inv || [])) if (c) seen(c.item);\n"
    "    const w = this.worn && this.worn.WEAPON; if (w) seen(w.item);\n"
    "    return best;\n"
    "  }\n"
    "  toolName(skill, tier) {\n"
    "    const kind = GRIM_RULES.GATHER.TOOL_FOR[skill];\n"
    "    const t = GRIM_RULES.GATHER.TOOLS[Math.max(0, Math.min(5, tier - 1))];\n"
    "    return (t && t[kind]) || (t ? t.name : 'CRUDE');\n"
    "  }\n"
    "\n"
    "  SKILL_INFO() {\n"
    "    return [",
    'SKILL_KEYS + tool helpers')

sub(
    "      ['WOODCUTTING', '#b08a5c', 'Felling trees for logs.', 'Great oaks need level 5. Palm, willow, ironbark, icewood, emberbark and ancient elder tiers arrive with the zone update.'],\n"
    "      ['MINING', '#c8842a', 'Breaking ore from veins.', 'Iron is open to all. Copper, salt, coal, saltpeter, glass-sand, gold, obsidian and ember crystal tiers arrive with the zone update.'],\n"
    "      ['SMITHING', '#9a9484', 'Smelting and forging.', 'Train it at the Hollowrest furnace and anvil - smelt bars, forge gear. Tool tiers (copper to masterwork) arrive with the zone update.']",

    "      ['WOODCUTTING', '#b08a5c', 'Felling trees for logs.', 'Poplar at 1, oak at 10, palm 20, willow and bog oak 30, elder 40, acacia ironbark 50, icewood 60, emberbark 75, ancient elder 90. A tree needs the skill AND an axe of its tier.'],\n"
    "      ['MINING', '#c8842a', 'Breaking ore from veins.', 'Loose stone at 1, copper 10, salt 20, iron 30, coal 40, saltpeter 50, glass sand 55, gold 65, obsidian 80, ember crystal 90. Coal is Ironspire only, gold and obsidian are Ember only.'],\n"
    "      ['FORAGING', '#4fb3a0', 'Gathering herbs, plants and shore finds.', 'Berries at 1, mushrooms 15, reeds 25, holly 35, fenroot 45, pearls 50, dye flowers 55, coral 65, spice 70, fire lilies 75, black lotus 90. Bare hands work at tier 1, sickles from there.'],\n"
    "      ['SMITHING', '#9a9484', 'Smelting and forging.', 'Train it at the Hollowrest furnace and anvil - smelt bars, forge gear. The gathering tool ladder from copper to masterwork is forged here.']",
    'SKILL_INFO')

# ----------------------------------------------------------- 5. the gate check
OLD_GATHER_START = "    const wantKind = e.weapon === 3 ? 'rock' : 'tree';"
OLD_GATHER_END = "    return this.meleeCheck(e, { dmg: [3, 5], range: 2.4, arc: 1.8 });   // tools are poor weapons\n  }"
i0 = src.find(OLD_GATHER_START)
i1 = src.find(OLD_GATHER_END)
assert i0 > 0 and i1 > i0, 'gatherCheck body not found'
assert src.count(OLD_GATHER_START) == 1, 'gatherCheck start not unique'
assert src.count(OLD_GATHER_END) == 1, 'gatherCheck end not unique'
OLD_GATHER = src[i0:i1 + len(OLD_GATHER_END)]

NEW_GATHER = """    // What is in your hand decides which skill you are trying to use. Bare
    // hands and a sickle both forage; pick mines; axe chops.
    const held = (this.worn && this.worn.WEAPON && this.worn.WEAPON.item) || '';
    const heldDef = held ? this.itemDef(held) : null;
    const heldTool = (heldDef && heldDef.tool) || (e.weapon === 3 ? 'pick' : e.weapon === 4 ? 'axe' : null);
    const GG = GRIM_RULES.GATHER;
    const nodeDef = (R2) => GG.NODES[R2 && R2.kind] || null;

    if (bestDead) {
      const dd = nodeDef(bestDead);
      const mining = dd && dd.skill === 'MINING';
      this.banner(mining ? 'THE VEIN IS EMPTY' : 'ONLY A STUMP REMAINS',
        mining ? 'IT WILL REFILL SOON' : 'IT IS REGROWING', false, 1600);
      if (!best) return true;
    }
    if (!best) return this.meleeCheck(e, { dmg: [3, 5], range: 2.4, arc: 1.8 });   // tools are poor weapons

    const nd = nodeDef(best);
    if (!nd) return this.meleeCheck(e, { dmg: [3, 5], range: 2.4, arc: 1.8 });
    const wantTool = GG.TOOL_FOR[nd.skill];
    const pretty = this.nodeLabel(best.kind);

    // Wrong tool entirely. Foraging is the exception: hands count, so only a
    // pick or an axe in the way can block it.
    if (wantTool !== heldTool && !(wantTool === 'sickle' && !heldTool)) {
      this.banner('NEEDS ' + (wantTool === 'axe' ? 'AN AXE' : wantTool === 'pick' ? 'A PICK' : 'A FREE HAND OR A SICKLE'),
        pretty.toUpperCase() + ' IS ' + nd.skill, false, 2000);
      return true;
    }

    // Both gates are checked, and the message always names the one that failed
    // and what closes it. A bare refusal teaches the player nothing.
    const have = this.lvl(this.skills[nd.skill] || 0);
    if (have < nd.lvl) {
      this.banner('REQUIRES ' + nd.skill + ' ' + nd.lvl,
        pretty.toUpperCase() + ' NEEDS LEVEL ' + nd.lvl + ', YOU ARE ' + have, false, 2200);
      return true;
    }
    const tier = this.toolTierFor(nd.skill);
    if (tier < nd.tool) {
      this.banner('NEEDS A ' + this.toolName(nd.skill, nd.tool),
        pretty.toUpperCase() + ' NEEDS TIER ' + nd.tool + ', YOURS IS TIER ' + tier, false, 2200);
      return true;
    }

    const p = best.g.position.clone().add(new T.Vector3(0, 1.2, 0));
    this.spark(p, nd.skill === 'MINING' ? 0xc8c8c0 : nd.skill === 'FORAGING' ? 0x4fb3a0 : 0x8a6b3a, 8);
    this.sfx(nd.skill === 'MINING' ? 'mine' : 'chop'); this.shake = Math.min(1, this.shake + 0.12);
    if (this.connectedAsClient()) {
      try { this.hostConn.send({ t: 'rhit', i: this.resources.indexOf(best), nid: best.nid || null }); } catch (er) {}
      best.hp--;
      if (best.hp <= 0) this.resourceDepleted(best, p);
      return true;
    }
    // Skill and tool both make you faster. Progress is accumulated as a
    // fraction so a better axe means fewer swings, not a different node.
    const speed = Math.pow(GG.TOOL_SPEED, tier - 1) * (1 + Math.max(0, have - nd.lvl) * 0.004);
    const qty = nd.yield[1] + ((nd.yield[2] > nd.yield[1]) ? (this.gatherRoll(best) % (nd.yield[2] - nd.yield[1] + 1)) : 0);
    if (best.hp <= 1 && this.canAccept(nd.yield[0], qty) < qty) { this.packFullNote(); return true; }
    best.prog = (best.prog || 0) + speed;
    const step = Math.max(1, Math.floor(best.prog));
    best.prog -= step;
    best.hp -= step; this._rDirty = true;
    if (best.hp <= 0) {
      this.resourceDepleted(best, p);
      this.addItem(nd.yield[0], qty);
      this.awardXp(nd.skill, nd.xp);
      if (this.gatherRoll(best, 7) / 100 < GG.BONUS_CHANCE) {
        const bonus = GG.BONUS[nd.skill];
        if (bonus && this.canAccept(bonus, 1) >= 1) { this.addItem(bonus, 1); this.banner('RARE FIND', bonus, false, 1800); }
      }
    }
    return true;
  }

  // Readable name for a node kind, derived from the kind id so a new node
  // never shows up in a message as a raw key.
  nodeLabel(kind) {
    const NAMES = {
      tree: 'Tree', oak: 'Great oak', rock: 'Iron vein', poplar: 'Poplar', zoak: 'Oak',
      palm: 'Palm', willow: 'Willow', bogoak: 'Bog oak', elder: 'Elder', acacia: 'Acacia ironbark',
      icewood: 'Icewood', emberbark: 'Emberbark blackwood', elderking: 'Ancient elder',
      stone: 'Loose stone', copper: 'Copper', salt: 'Salt flat', ironore: 'Iron', coal: 'Coal seam',
      saltpeter: 'Saltpeter crust', glasssand: 'Glass sand', gold: 'Gold vein', obsidian: 'Obsidian flow',
      embercryst: 'Ember crystal', berry: 'Berry bush', mushroom: 'Mushroom ring', reeds: 'Reeds',
      holly: 'Holly', fenroot: 'Fenroot', pearl: 'Pearl bed', dyeflower: 'Dye flowers',
      coral: 'Coral', spice: 'Spice bush', firelily: 'Fire lily', lotus: 'Black lotus'
    };
    return NAMES[kind] || String(kind || 'node');
  }
  // Small deterministic roll tied to the node itself, so two players emptying
  // the same node get the same yield and the same rare find.
  gatherRoll(R2, salt) {
    const id = R2 && (R2.nid || String(this.resources.indexOf(R2)));
    let h = grimSeed(0, 0, id + ':' + (salt || 0) + ':' + Math.round((R2 && R2.rolls) || 0));
    return h % 100;
  }"""

sub(OLD_GATHER, NEW_GATHER, 'gatherCheck')

# The old code only looked for the kind the held tool wanted, so `best` was
# already filtered. It is now unfiltered, which is what makes a wrong-tool
# message possible at all.
sub(
    "      if (R.dead) { if (d < bdD) { bestDead = R; bdD = d; } continue; }\n"
    "      if (d < bd) { best = R; bd = d; }",
    "      if (R.dead) { if (d < bdD) { bestDead = R; bdD = d; } continue; }\n"
    "      if (d < bd) { best = R; bd = d; }   // any kind: the gate check below explains the refusal",
    'gatherCheck scan note')

# ------------------------------------------------------- 6. relayed loot yield
sub(
    "    if (m.t === 'rdead' && !this.isWorldHost) { if (m.k === 'oak') { this.grantItem('OAK LOGS', 3); this.awardXp('WOODCUTTING', 60); this.sfx('timber'); } else if (m.k === 'rock') { this.grantItem('IRON ORE', 2); this.awardXp('MINING', 20); this.sfx('break'); } else { this.grantItem('LOGS', 2); this.awardXp('WOODCUTTING', 15); this.sfx('timber'); } return; }",
    "    if (m.t === 'rdead' && !this.isWorldHost) { const nd = GRIM_RULES.GATHER.NODES[m.k] || GRIM_RULES.GATHER.NODES.tree; this.grantItem(nd.yield[0], nd.yield[1]); this.awardXp(nd.skill, nd.xp); this.sfx(nd.skill === 'MINING' ? 'break' : 'timber'); return; }",
    'relayed rdead yield')

# ------------------------------------------------------------ 7. respawn table
sub(
    "  resourceRespawnTime(kind) { return kind === 'oak' ? 90 : kind === 'rock' ? 60 : 45; }",
    "  resourceRespawnTime(kind) {\n"
    "    const nd = GRIM_RULES.GATHER.NODES[kind];\n"
    "    return nd ? nd.respawn : 45;\n"
    "  }",
    'respawn table')

# ---------------------------------------------------------------------- write
out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)

assert out != src, 'nothing changed'
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
