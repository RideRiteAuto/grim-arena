"""
Kevin, Aug 12: "come up with new stuff for the crafting table, full flesh
it out."

Six new recipes (3 -> 9 total), all wood/hand-craft themed like ROWBOAT and
CRUDE AXE/PICK -- no ore, no bars, nothing that duplicates the anvil's
SMELTS()/SMITHS() ladder. Design note for whoever picks this up next:

The real find here is that GATHER.NODES defines a huge pile of FORAGING,
higher-tier WOODCUTTING and MINING materials (BERRIES, MUSHROOMS, REEDS,
HOLLY, FENROOT, PEARL, DYE FLOWERS, CORAL, SPICE, FIRE LILY, BLACK LOTUS,
PALM/WILLOW/BOG OAK/ELDER/ACACIA/ICEWOOD/EMBERBARK/ANCIENT ELDER LOGS,
GLASS SAND, SALTPETER, SALT, plus the three BONUS drops BIRD NEST/GEM
SHARD/WILD SEED) that are gathered, auto-defined with a real icon, and
then used by NOTHING anywhere in the game. They fall back to the generic
value:6 -> sells to Fenwick for ~3g regardless of how high-level the node
is, so a level 70 SPICE forager and a level 1 BERRIES forager get paid
the same pittance. That is the dead end this patch fixes, not a re-skin
of existing content.

Six new recipes, spread across all three gathering skills, craft `lvl`
set to match the HIGHEST-gather-level material each recipe needs (same
rule ROWBOAT/CRUDE AXE/CRUDE PICK already follow with LOGS):

  TRAIL RATIONS       FORAGING 15  BERRIES x4 + MUSHROOMS x2   -> food, +12 HP
  HEARTHFEN POULTICE  FORAGING 45  HOLLY x3 + FENROOT x2       -> medicine, +35 HP
  SUNSCORCH TONIC     FORAGING 70  SPICE x3 + DYE FLOWERS x2 + PEARL x1 -> medicine, +60 HP
  ELDERWOOD CARVINGS  WOODCUTTING 50  ELDER LOGS x8 + ACACIA LOGS x4 -> trade good
  SALT GLASS TALISMAN MINING 55   GLASS SAND x6 + SALTPETER x2 -> trade good
  GATHERERS TRINKET   WOODCUTTING 1   BIRD NEST + GEM SHARD + WILD SEED (1 each)
                       -> trade good; the real gate is the 5% bonus-drop
                          roll on each of the three gathering skills, not
                          the level, so the skill/lvl fields are nominal

The three food/medicine items reuse the exact VENISON itemUse() pattern
(EAT/APPLY/DRINK -> takeItem -> heal -> splat -> sfx), nothing new. The
three trade goods get no itemUse() at all, same as WOLF PELT/DEER HIDE/
RAT TAIL today -- sellable only, priced with a real craft markup over
their raw materials' combined sell value (Fenwick's fallback formula is
value*0.55, and none of these six ids are in sellPrices()/shopStock(), so
that fallback is what prices them) so crafting them is actually worth
more than dumping the raw mats on Fenwick, not a trap.

Deliberately NOT done, flagged rather than shipped half-baked:
- A second ROWBOAT tier (faster boat from higher-tier wood). The boat's
  row speed is a flat constant read off `this.boating` in the movement
  code (~line 35806) and replicated to other players via the boat-state
  sync block (~line 38620-38751); giving it a second speed would mean
  threading a per-boat stat through movement AND multiplayer sync, a real
  gameplay-mechanic change, not a crafting-table content add. Worth its
  own pass if Kevin wants it.
- Nothing touches GATHER.RECIPES (the dead tool-tier-upgrade table at
  lines ~1461-1467) -- that is a different, already-flagged balance item,
  unrelated to the crafting table.
- No new equippable weapon shapes, no new 3D held models. Every item here
  is inventory-only (default slot: null), so it only needed a 2D icon,
  same reasoning as ROWBOAT/CRUDE AXE/CRUDE PICK before it.
"""

PATH = '/tmp/game-src.html'
with open(PATH, 'r', encoding='utf-8') as f:
    text = f.read()


def sub(old, new, tag, count=1):
    global text
    n = text.count(old)
    assert n == count, f'{tag}: found {n}, wanted {count}'
    text = text.replace(old, new, count)


# ---- 1. six new item defs, dropped in next to the other hand-authored
# consumables (VENISON, WOLF PELT, TOME OF STORMS), right before worn gear.
sub(
    '''    def('TOME OF STORMS',{ value: 750, icon: '<div style="width:16px;height:20px;background:#3a2f52;border:2px solid #c8a2ff;border-radius:2px 5px 5px 2px;"></div>' });

    // worn gear (never stacks). Stats: att/str/def/mag/rng.''',
    '''    def('TOME OF STORMS',{ value: 750, icon: '<div style="width:16px;height:20px;background:#3a2f52;border:2px solid #c8a2ff;border-radius:2px 5px 5px 2px;"></div>' });

    // Crafting-table content (Kevin, Aug 12): gives previously dead-end
    // FORAGING/WOODCUTTING/MINING materials (raw value:6, never used by
    // any recipe before this) a real sink. See CRAFT_RECIPES() below.
    def('TRAIL RATIONS', { value: 18, icon: svg('<path d="M5 12 L25 12 L23 24 L7 24 Z" fill="#c9a86a" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M11 12 L11 8.6 Q15 5.6 19 8.6 L19 12" fill="none" stroke="#8a6b3a" stroke-width="1.6"/>' +
      '<circle cx="11.6" cy="18" r="2.6" fill="#a8443a" stroke="' + O + '" stroke-width="1.2"/><circle cx="16.4" cy="19.4" r="2.3" fill="#c25a48" stroke="' + O + '" stroke-width="1.2"/>' +
      '<path d="M18.6 15.4 Q21.6 12 24.4 15.4 Q21.6 17 18.6 15.4 Z" fill="#e0d8c4" stroke="' + O + '" stroke-width="1.2"/>') });
    def('HEARTHFEN POULTICE', { value: 82, icon: svg('<ellipse cx="15" cy="17" rx="9.4" ry="7.6" fill="#5c7a45" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M6.6 14.4 Q15 17.4 23.4 14.4 M6.6 19.6 Q15 22.6 23.4 19.6" fill="none" stroke="#8a6b3a" stroke-width="1.4"/>' +
      '<path d="M15 9.6 L17 4.6 L19.6 3 L18.6 7.4 L22 6 L20 10 Z" fill="#1f5c2a" stroke="' + O + '" stroke-width="1.3"/>' +
      '<circle cx="19" cy="6.6" r="1.6" fill="#c8384a" stroke="' + O + '" stroke-width="1"/>') });
    def('SUNSCORCH TONIC', { value: 200, icon: svg('<path d="M11 13 Q9 18 10 23.4 Q10 26.4 15 26.4 Q20 26.4 20 23.4 Q21 18 19 13 Z" fill="#e8a23c" fill-opacity="0.88" stroke="' + O + '" stroke-width="1.8"/>' +
      '<rect x="12.6" y="6.6" width="4.8" height="7" fill="#e8a23c" fill-opacity="0.88" stroke="' + O + '" stroke-width="1.6"/>' +
      '<rect x="12" y="3.6" width="6" height="3.6" rx="1" fill="#8a6b3a" stroke="' + O + '" stroke-width="1.4"/>' +
      '<path d="M12.4 16 Q11.4 20 12 24" stroke="#fbe4b0" stroke-width="1.2" fill="none" opacity="0.7"/><circle cx="21.6" cy="21" r="2" fill="#d98736" stroke="' + O + '" stroke-width="1"/>') });
    def('ELDERWOOD CARVINGS', { value: 160, icon: svg('<circle cx="15" cy="15" r="10.6" fill="#5d4726" stroke="' + O + '" stroke-width="1.9"/>' +
      '<path d="M15 6.6 Q21.4 9 21.4 15 Q21.4 21 15 21 Q10 21 10 16.4" fill="none" stroke="#8a6b3a" stroke-width="1.6" stroke-linecap="round"/>' +
      '<circle cx="15" cy="15" r="2.4" fill="#8a6b3a" stroke="' + O + '" stroke-width="1.2"/>') });
    def('SALT GLASS TALISMAN', { value: 130, icon: svg('<path d="M10 4.6 Q15 2 20 4.6" fill="none" stroke="#8a6b3a" stroke-width="1.4"/>' +
      '<path d="M15 5.6 L21 12 L15 25.4 L9 12 Z" fill="#bfe6e0" fill-opacity="0.82" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M9 12 L21 12 M15 5.6 L15 25.4" stroke="#ffffff" stroke-width="1" opacity="0.55"/>') });
    def('GATHERERS TRINKET', { value: 270, icon: svg('<ellipse cx="10.4" cy="20" rx="5.4" ry="3.4" fill="none" stroke="#8a6b3a" stroke-width="2.2"/>' +
      '<path d="M18 8.6 L22.4 13 L18 21.4 L14.6 13 Z" fill="#7fc8ff" stroke="' + O + '" stroke-width="1.4"/>' +
      '<ellipse cx="21.6" cy="23.4" rx="2.6" ry="1.8" fill="#c9a94e" stroke="' + O + '" stroke-width="1.2" transform="rotate(30 21.6 23.4)"/>') });

    // worn gear (never stacks). Stats: att/str/def/mag/rng.''',
    'ITEMS: add 6 crafting-table items',
)

# ---- 2. itemUse() cases for the three consumables, same shape as VENISON.
sub(
    '''    if (id === 'VENISON') return { label: 'EAT', fn: () => {
      const e = this.me; if (!e || e.hp <= 0) return;
      if (e.hp >= e.max) { this.banner('YOU ARE FULL', 'NOT A SCRATCH ON YOU', false, 1800); return; }
      if (this.takeItem('VENISON', 1)) {
        e.hp = Math.min(e.max, e.hp + 18);
        this.splat(e.pos.clone().add(new this.T.Vector3(0, 2.3, 0)), '+18', 'heal');
        this.sfx('pickup');
      }
    } };
    return null;
  }''',
    '''    if (id === 'VENISON') return { label: 'EAT', fn: () => {
      const e = this.me; if (!e || e.hp <= 0) return;
      if (e.hp >= e.max) { this.banner('YOU ARE FULL', 'NOT A SCRATCH ON YOU', false, 1800); return; }
      if (this.takeItem('VENISON', 1)) {
        e.hp = Math.min(e.max, e.hp + 18);
        this.splat(e.pos.clone().add(new this.T.Vector3(0, 2.3, 0)), '+18', 'heal');
        this.sfx('pickup');
      }
    } };
    // Kevin, Aug 12: crafting-table food/medicine tier, same EAT/heal
    // shape as VENISON above -- TRAIL RATIONS is the cheap early option,
    // HEARTHFEN POULTICE and SUNSCORCH TONIC are stronger and gated to
    // the FORAGING level their materials already require to gather.
    if (id === 'TRAIL RATIONS') return { label: 'EAT', fn: () => {
      const e = this.me; if (!e || e.hp <= 0) return;
      if (e.hp >= e.max) { this.banner('YOU ARE FULL', 'NOT A SCRATCH ON YOU', false, 1800); return; }
      if (this.takeItem('TRAIL RATIONS', 1)) {
        e.hp = Math.min(e.max, e.hp + 12);
        this.splat(e.pos.clone().add(new this.T.Vector3(0, 2.3, 0)), '+12', 'heal');
        this.sfx('pickup');
      }
    } };
    if (id === 'HEARTHFEN POULTICE') return { label: 'APPLY', fn: () => {
      const e = this.me; if (!e || e.hp <= 0) return;
      if (e.hp >= e.max) { this.banner('YOU ARE FULL', 'NOT A SCRATCH ON YOU', false, 1800); return; }
      if (this.takeItem('HEARTHFEN POULTICE', 1)) {
        e.hp = Math.min(e.max, e.hp + 35);
        this.splat(e.pos.clone().add(new this.T.Vector3(0, 2.3, 0)), '+35', 'heal');
        this.sfx('pickup');
      }
    } };
    if (id === 'SUNSCORCH TONIC') return { label: 'DRINK', fn: () => {
      const e = this.me; if (!e || e.hp <= 0) return;
      if (e.hp >= e.max) { this.banner('YOU ARE FULL', 'NOT A SCRATCH ON YOU', false, 1800); return; }
      if (this.takeItem('SUNSCORCH TONIC', 1)) {
        e.hp = Math.min(e.max, e.hp + 60);
        this.splat(e.pos.clone().add(new this.T.Vector3(0, 2.3, 0)), '+60', 'heal');
        this.sfx('pickup');
      }
    } };
    return null;
  }''',
    'itemUse: add TRAIL RATIONS/HEARTHFEN POULTICE/SUNSCORCH TONIC',
)

# ---- 3. six new CRAFT_RECIPES() rows.
sub(
    '''  CRAFT_RECIPES() {
    return [
      { id: 'ROWBOAT', need: [['LOGS', 12]], xp: 30, skill: 'WOODCUTTING', lvl: 1 },
      // Kevin, Aug 12: a free way to replace a lost starting tool with
      // nothing but logs -- both items already exist (GATHER.TOOLS, same
      // ones Fenwick sells per 88.170), so this is purely a new source for
      // them, not a new item.
      { id: 'CRUDE AXE', need: [['LOGS', 8]], xp: 15, skill: 'WOODCUTTING', lvl: 1 },
      { id: 'CRUDE PICK', need: [['LOGS', 8]], xp: 15, skill: 'WOODCUTTING', lvl: 1 }
    ];
  }''',
    '''  CRAFT_RECIPES() {
    return [
      { id: 'ROWBOAT', need: [['LOGS', 12]], xp: 30, skill: 'WOODCUTTING', lvl: 1 },
      // Kevin, Aug 12: a free way to replace a lost starting tool with
      // nothing but logs -- both items already exist (GATHER.TOOLS, same
      // ones Fenwick sells per 88.170), so this is purely a new source for
      // them, not a new item.
      { id: 'CRUDE AXE', need: [['LOGS', 8]], xp: 15, skill: 'WOODCUTTING', lvl: 1 },
      { id: 'CRUDE PICK', need: [['LOGS', 8]], xp: 15, skill: 'WOODCUTTING', lvl: 1 },
      // Kevin, Aug 12: full flesh-out pass. `lvl` on every row below
      // matches the highest GATHER.NODES level its own materials already
      // require to gather, same rule the three rows above follow with
      // LOGS -- the recipe is not a separate gate, the materials are.
      { id: 'TRAIL RATIONS', need: [['BERRIES', 4], ['MUSHROOMS', 2]], xp: 20, skill: 'FORAGING', lvl: 15 },
      { id: 'HEARTHFEN POULTICE', need: [['HOLLY', 3], ['FENROOT', 2]], xp: 90, skill: 'FORAGING', lvl: 45 },
      { id: 'SUNSCORCH TONIC', need: [['SPICE', 3], ['DYE FLOWERS', 2], ['PEARL', 1]], xp: 220, skill: 'FORAGING', lvl: 70 },
      { id: 'ELDERWOOD CARVINGS', need: [['ELDER LOGS', 8], ['ACACIA LOGS', 4]], xp: 260, skill: 'WOODCUTTING', lvl: 50 },
      { id: 'SALT GLASS TALISMAN', need: [['GLASS SAND', 6], ['SALTPETER', 2]], xp: 230, skill: 'MINING', lvl: 55 },
      // The real gate here is luck, not level: BIRD NEST/GEM SHARD/WILD
      // SEED are the 5 percent bonus drop off WOODCUTTING/MINING/FORAGING
      // respectively (GG.BONUS_CHANCE), obtainable from level 1 on. lvl 1
      // is nominal so the row is never greyed out by anything but having
      // the three drops in hand.
      { id: 'GATHERERS TRINKET', need: [['BIRD NEST', 1], ['GEM SHARD', 1], ['WILD SEED', 1]], xp: 150, skill: 'WOODCUTTING', lvl: 1 }
    ];
  }''',
    'CRAFT_RECIPES: add 6 new recipes',
)

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(text)

print('applied 89.734 (3 edits)')
