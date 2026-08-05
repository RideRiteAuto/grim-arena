#!/usr/bin/env python3
"""Give the generated items real icons.

Two families of item art were placeholders, and between them they cover more of
the pack than every hand-drawn icon put together.

THE MATERIALS. Every yield in the node table becomes a stackable item, and all
34 of them rendered as the SAME 9px circle, filled with one of three colours by
skill. A pack holding oak logs, coal, gold ore, mushrooms and black lotus showed
five identical brown-ish dots. You could not tell what you were carrying.

Each now draws from what produced it, using data that was already there:

  WOODCUTTING  a cut log, end grain showing, in that species' wood colour
  MINING       an ore chunk. Ores that are embedded (copper, iron, gold) are
               grey rock with coloured flecks; ores that ARE the material
               (coal, obsidian, salt, saltpeter, glass sand, ember crystal) are
               a solid chunk of it
  FORAGING     a sprig matching the plant it came off, so the icon and the thing
               you walked up to look like each other
  BONUS        bird nest, gem shard and wild seed get their own drawings

THE TOOLS. Sixteen tools shared exactly two silhouettes recoloured by tier, so a
masterwork axe and a crude axe were the same picture in different paint. Tier is
now a SHAPE: the crude tools are chipped stone lashed to a crooked stick, copper
is a small cast head, iron a proper forged one, steel broader with a bevel,
obsidian angular and faceted, masterwork double-bitted with a gold ferrule and a
set gem. Colour still varies too, but you no longer need it to tell them apart.

No stats, values, recipes or gates change. This is only what the icons look like.

Note on the registry contract: every item MUST have an icon or the registry
throws at boot (`ITEM MISSING ICON`). That check is deliberate and stays; the
fallback here is the old plain disc, so a node added to the rules table before
it has art still gets a valid icon rather than crashing the game.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ------------------------------------------------------ 1. tool icon shapes
OLD_TOOLS = """      const TINT = { 1: '#8a7a62', 2: '#c07a3e', 3: '#aab3bf', 4: '#d6dae2', 5: '#4a3f52', 6: '#f0d878' };
      const haft = '<line x1="12" y1="6" x2="18" y2="27" stroke="' + WD + '" stroke-width="3"/>';
      const haft2 = '<line x1="15" y1="9" x2="15" y2="27" stroke="' + WD + '" stroke-width="3"/>';
      for (const t of GG.TOOLS) {
        const c = TINT[t.tier] || '#aab3bf';
        const val = 40 * t.tier * t.tier;
        const st = { att: t.tier, str: t.tier, def: 0, mag: 0, rng: 0 };
        if (t.axe && !R[t.axe]) def(t.axe, { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 4, style: 'melee', value: val, tool: 'axe', toolTier: t.tier, stats: st,
          icon: svg(haft + '<path d="M11 4 Q22 3 24 12 Q16 13 10 9 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>') });
        if (t.pick && !R[t.pick]) def(t.pick, { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 3, style: 'melee', value: val, tool: 'pick', toolTier: t.tier, stats: st,
          icon: svg(haft2 + '<path d="M4 10 Q15 2 26 10 Q15 7 4 10 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>') });
        if (t.sickle && !R[t.sickle]) def(t.sickle, { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 4, style: 'melee', value: val, tool: 'sickle', toolTier: t.tier, stats: st,
          icon: svg('<path d="M8 26 L14 14" stroke="' + WD + '" stroke-width="3" stroke-linecap="round"/><path d="M13 15 Q24 6 25 17 Q18 12 13 15 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.6"/>') });
      }
"""

NEW_TOOLS = """      // Tier is a SHAPE, not a paint job. Crude is chipped stone lashed to a
      // crooked stick; masterwork is double-bitted with a gold ferrule and a set
      // gem. Read down a column and the ladder is legible without the colour.
      const TINT = { 1: '#8a7a62', 2: '#c07a3e', 3: '#aab3bf', 4: '#d6dae2', 5: '#4a3f52', 6: '#f0d878' };
      const GOLD = '#e8c774', GEM = '#8fef5a', SHEEN = '#f2f6fa';
      // diagonal haft for axe and sickle, upright for the pick
      const haftD = (tier) => tier === 1
        ? '<path d="M19 27 L16 20 L17.6 13 L14.6 6" fill="none" stroke="' + WD + '" stroke-width="3.2" stroke-linecap="round"/>'
        : tier === 6
          ? '<line x1="19" y1="27" x2="13.4" y2="7" stroke="' + WD2 + '" stroke-width="3.4" stroke-linecap="round"/>' +
            '<path d="M17.8 23 L15.6 15" stroke="' + GOLD + '" stroke-width="1.5"/>' +
            '<circle cx="19.4" cy="27" r="2.1" fill="' + GOLD + '" stroke="' + O + '" stroke-width="1.2"/>'
          : '<line x1="19" y1="27" x2="13.4" y2="7" stroke="' + (tier === 5 ? '#3a3340' : WD) + '" stroke-width="3.2" stroke-linecap="round"/>';
      const haftU = (tier) => tier === 1
        ? '<path d="M15 27 L13.8 21 L15.4 15 L14.4 10" fill="none" stroke="' + WD + '" stroke-width="3.2" stroke-linecap="round"/>'
        : tier === 6
          ? '<line x1="15" y1="27" x2="15" y2="9" stroke="' + WD2 + '" stroke-width="3.4" stroke-linecap="round"/>' +
            '<path d="M15 24 L15 16" stroke="' + GOLD + '" stroke-width="1.5"/>' +
            '<circle cx="15" cy="27" r="2.1" fill="' + GOLD + '" stroke="' + O + '" stroke-width="1.2"/>'
          : '<line x1="15" y1="27" x2="15" y2="9" stroke="' + (tier === 5 ? '#3a3340' : WD) + '" stroke-width="3.2" stroke-linecap="round"/>';
      const AXE_HEAD = {
        1: (c) => '<path d="M12 9.5 L17.6 3 L24 8.4 L21 13.4 L13.8 13 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.7"/>' +
                  '<path d="M13.6 6.4 L16.6 12.6 M16.4 4.6 L19.4 11" stroke="#5d4726" stroke-width="1.5"/>',
        2: (c) => '<path d="M13.4 5 Q22 4 23.6 11 Q17 12.4 13 9.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.7"/>',
        3: (c) => '<path d="M12.6 4 Q23.4 3 25 11.8 Q16 13.2 12.2 9.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M22 5 Q24.6 8 24.2 11" fill="none" stroke="' + SHEEN + '" stroke-width="1.2"/>',
        4: (c) => '<path d="M11.6 3 Q24.6 2 26 12 Q15 14 11.4 9.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M21 4 Q25.2 8 24.8 11.6" fill="none" stroke="#ffffff" stroke-width="1.5" opacity="0.85"/>',
        5: (c) => '<path d="M11.6 4.4 L19 2 L26 9 L22 13.4 L13 12.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M19 2 L18 12.8 M26 9 L13 8.2" stroke="#9a8fb4" stroke-width="1" opacity="0.85"/>',
        6: (c) => '<path d="M13.4 3 Q25 2 26 11 Q16.4 12.8 13.4 9.4 Z M13.4 3 Q4 4 3.6 11 Q11 12.4 13.4 9.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.7"/>' +
                  '<path d="M13.4 3 L13.4 11.4" stroke="' + O + '" stroke-width="1.2"/>' +
                  '<circle cx="14.8" cy="7.2" r="2.2" fill="' + GEM + '" stroke="' + O + '" stroke-width="1.2"/>'
      };
      const PICK_HEAD = {
        1: (c) => '<path d="M6.4 13.4 Q15 5.6 23.6 13.4 Q15 9.4 6.4 13.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.7"/>' +
                  '<path d="M12.8 10.6 L12.8 16 M17.2 10.6 L17.2 16" stroke="#5d4726" stroke-width="1.5"/>',
        2: (c) => '<path d="M5.4 12.4 Q15 4.6 24.6 12.4 Q15 8.4 5.4 12.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.7"/>',
        3: (c) => '<path d="M4.2 11.4 Q15 2.4 25.8 11.4 Q15 7 4.2 11.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M8 9.6 Q15 4.6 22 9.6" fill="none" stroke="' + SHEEN + '" stroke-width="1.2"/>',
        4: (c) => '<path d="M3 11 Q15 1 27 11 Q15 6 3 11 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M7 9 Q15 3.4 23 9" fill="none" stroke="#ffffff" stroke-width="1.5" opacity="0.85"/>',
        5: (c) => '<path d="M3 12.4 L9.4 5.4 L15 7.4 L20.6 5.4 L27 12.4 L15 8.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M9.4 5.4 L11 11 M20.6 5.4 L19 11" stroke="#9a8fb4" stroke-width="1" opacity="0.85"/>',
        6: (c) => '<path d="M3 11 Q15 1 27 11 Q15 6 3 11 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<rect x="11.4" y="9.6" width="7.2" height="4" rx="1.2" fill="' + GOLD + '" stroke="' + O + '" stroke-width="1.2"/>' +
                  '<circle cx="15" cy="11.6" r="1.7" fill="' + GEM + '" stroke="' + O + '" stroke-width="1"/>'
      };
      const SICKLE_BLADE = {
        2: (c) => '<path d="M13.4 15 Q22 8 23.4 16.4 Q18 12.4 13.4 15 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.6"/>',
        3: (c) => '<path d="M13 15.4 Q24 6 25.4 17 Q18.4 12 13 15.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.6"/>' +
                  '<path d="M15 14.6 Q22.4 9 24.4 15.4" fill="none" stroke="' + SHEEN + '" stroke-width="1.1"/>',
        4: (c) => '<path d="M12.4 15.6 Q25.4 4.4 26.6 17.6 Q18.4 11.4 12.4 15.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.6"/>' +
                  '<path d="M14.6 14.4 Q23.6 7 25.6 15.6" fill="none" stroke="#ffffff" stroke-width="1.3" opacity="0.85"/>',
        5: (c) => '<path d="M12.6 15.6 L18 7 L24.4 8.6 L26 17.4 L18.6 12.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.6"/>' +
                  '<path d="M18 7 L19.4 13 M24.4 8.6 L18.6 12.4" stroke="#9a8fb4" stroke-width="1" opacity="0.85"/>',
        6: (c) => '<path d="M12.4 15.6 Q25.4 4.4 26.6 17.6 Q18.4 11.4 12.4 15.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.6"/>' +
                  '<path d="M13.4 15 Q24.6 6 25.8 16.4" fill="none" stroke="' + GOLD + '" stroke-width="1.6"/>' +
                  '<circle cx="14.6" cy="16.4" r="2" fill="' + GEM + '" stroke="' + O + '" stroke-width="1.2"/>'
      };
      for (const t of GG.TOOLS) {
        const c = TINT[t.tier] || '#aab3bf';
        const val = 40 * t.tier * t.tier;
        const st = { att: t.tier, str: t.tier, def: 0, mag: 0, rng: 0 };
        const ah = (AXE_HEAD[t.tier] || AXE_HEAD[3])(c);
        const ph = (PICK_HEAD[t.tier] || PICK_HEAD[3])(c);
        const sh = (SICKLE_BLADE[t.tier] || SICKLE_BLADE[3])(c);
        if (t.axe && !R[t.axe]) def(t.axe, { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 4, style: 'melee', value: val, tool: 'axe', toolTier: t.tier, stats: st,
          icon: svg(haftD(t.tier) + ah) });
        if (t.pick && !R[t.pick]) def(t.pick, { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 3, style: 'melee', value: val, tool: 'pick', toolTier: t.tier, stats: st,
          icon: svg(haftU(t.tier) + ph) });
        if (t.sickle && !R[t.sickle]) def(t.sickle, { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 4, style: 'melee', value: val, tool: 'sickle', toolTier: t.tier, stats: st,
          icon: svg('<path d="M8.4 26.4 L14 14.6" stroke="' + (t.tier === 5 ? '#3a3340' : WD) + '" stroke-width="3" stroke-linecap="round"/>' + sh) });
      }
"""
sub(OLD_TOOLS, NEW_TOOLS, 'tool icons')

# -------------------------------------------------- 2. material icon shapes
OLD_MATS = """      const MC = { WOODCUTTING: '#8a6b3a', MINING: '#c8842a', FORAGING: '#4fb3a0' };
      const mats = {};
      for (const k in GG.NODES) { const nd = GG.NODES[k]; mats[nd.yield[0]] = MC[nd.skill] || '#9a9484'; }
      for (const sk in GG.BONUS) mats[GG.BONUS[sk]] = MC[sk] || '#9a9484';
      for (const id in mats) {
        if (R[id]) continue;
        def(id, { stack: true, value: 6,
          icon: svg('<circle cx="15" cy="16" r="9" fill="' + mats[id] + '" stroke="' + O + '" stroke-width="2"/>') });
      }
"""

NEW_MATS = """      // Every yield in the node table becomes a stackable material. The icon is
      // drawn from what produced it - the node's skill picks the family and the
      // node's kind picks the colour and, for herbs, the silhouette - so a pack
      // of logs, ore and cuttings reads at a glance instead of as identical dots.
      const MC = { WOODCUTTING: '#8a6b3a', MINING: '#c8842a', FORAGING: '#4fb3a0' };
      // NODE_TINT hands back a NUMBER (0x6a5a8a), not a css string. Everything
      // below wants '#rrggbb', and an unconverted number silently produces
      // fill="6971786", which is not a colour and is not an error either.
      const hexs = (v) => (typeof v === 'number')
        ? '#' + ('000000' + (v >>> 0).toString(16)).slice(-6)
        : String(v);
      const darker = (hexIn, f) => {
        const hex = hexs(hexIn);
        const n = parseInt(hex.slice(1), 16);
        const r2 = Math.round(((n >> 16) & 255) * f), g2 = Math.round(((n >> 8) & 255) * f), b2 = Math.round((n & 255) * f);
        return '#' + ((1 << 24) | (r2 << 16) | (g2 << 8) | b2).toString(16).slice(1);
      };
      const WOOD = {
        poplar: '#b8a074', zoak: '#8a6a3e', tree: '#8a6a3e', oak: '#6e5230', palm: '#c2a06a',
        willow: '#9aa86a', bogoak: '#4a4038', elder: '#6a4a6e', acacia: '#b07a42',
        icewood: '#a8ccd8', emberbark: '#7a3a2a', elderking: '#c8a24a'
      };
      // ores that ARE the material get a solid chunk; ores embedded in rock get
      // grey stone with coloured flecks
      const SOLID_ORE = { coal: 1, obsidian: 1, salt: 1, saltpeter: 1, glasssand: 1, embercryst: 1, stone: 1 };
      const logArt = (c) => {
        const d = darker(c, 0.72);
        return '<rect x="6" y="10.4" width="20" height="11" rx="3.2" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
               '<path d="M14 11 L14 20.8 M19.4 11 L19.4 20.8" stroke="' + d + '" stroke-width="1.3" opacity="0.75"/>' +
               '<ellipse cx="8.6" cy="15.9" rx="3.4" ry="5.5" fill="' + d + '" stroke="' + O + '" stroke-width="1.6"/>' +
               '<ellipse cx="8.6" cy="15.9" rx="1.5" ry="2.7" fill="none" stroke="' + O + '" stroke-width="1"/>';
      };
      const oreArt = (c, solid) => solid
        ? '<path d="M15 3.4 L25 9.6 L23 22 L11.4 24.4 L4.6 16 L7.8 6.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.9"/>' +
          '<path d="M15 3.4 L11.4 24.4 M25 9.6 L4.6 16" stroke="' + O + '" stroke-width="0.9" opacity="0.4"/>'
        : '<path d="M15 3.4 L25 9.6 L23 22 L11.4 24.4 L4.6 16 L7.8 6.6 Z" fill="#8b8b84" stroke="' + O + '" stroke-width="1.9"/>' +
          '<path d="M11.6 8.6 L16 7.6 L17 12 L12.6 13 Z M18 14 L22 12.8 L23 17 L19 18.4 Z M8.6 16 L12.8 17 L11.8 21 L7.8 19 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.1"/>';
      const HERB = {
        berry: (c) => '<path d="M15 26.4 L15 14" stroke="#4e7a38" stroke-width="2"/>' +
                      '<path d="M15 17 Q8 15 6.6 8.6 Q13.6 9 15 17 Z" fill="#4e7a38" stroke="' + O + '" stroke-width="1.4"/>' +
                      '<circle cx="11.6" cy="19" r="4" fill="' + c + '" stroke="' + O + '" stroke-width="1.6"/>' +
                      '<circle cx="19" cy="17" r="3.4" fill="' + c + '" stroke="' + O + '" stroke-width="1.6"/>' +
                      '<circle cx="17" cy="23" r="3.2" fill="' + c + '" stroke="' + O + '" stroke-width="1.6"/>',
        mushroom: (c) => '<rect x="12.4" y="14.6" width="5.2" height="11.6" rx="1.8" fill="#e0d8c4" stroke="' + O + '" stroke-width="1.6"/>' +
                      '<path d="M3.6 15 Q6 4.6 15 4.6 Q24 4.6 26.4 15 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                      '<circle cx="11" cy="10.6" r="1.7" fill="#f4efe4" opacity="0.9"/><circle cx="19.4" cy="9.6" r="1.4" fill="#f4efe4" opacity="0.9"/>',
        reeds: () => '<path d="M8.6 27 Q10 15 12 5 M15 27 Q15 14 15 3.6 M21.4 27 Q20 16 18 7" fill="none" stroke="#8a9a4a" stroke-width="2.2" stroke-linecap="round"/>' +
                      '<rect x="13.3" y="3.6" width="3.4" height="8.4" rx="1.7" fill="#6b4a2e" stroke="' + O + '" stroke-width="1.4"/>' +
                      '<rect x="16.6" y="7" width="3" height="6.6" rx="1.5" fill="#6b4a2e" stroke="' + O + '" stroke-width="1.3"/>',
        holly: (c) => '<path d="M15 4 L19 7.6 L23.4 5.4 L22.2 11.6 L26.4 15 L21.6 18 L22.6 24.4 L17.2 21 L15 26.4 L12.8 21 L7.4 24.4 L8.4 18 L3.6 15 L7.8 11.6 L6.6 5.4 L11 7.6 Z" fill="#1f5c2a" stroke="' + O + '" stroke-width="1.5"/>' +
                      '<circle cx="15" cy="15" r="3" fill="' + c + '" stroke="' + O + '" stroke-width="1.5"/>',
        fenroot: (c) => '<path d="M3.6 20.6 Q9 20.6 11 15.4 Q13 10 18 11 Q23 12 25.4 6.6" fill="none" stroke="' + c + '" stroke-width="4.4" stroke-linecap="round"/>' +
                      '<circle cx="11" cy="15.4" r="2.6" fill="' + darker(c, 0.7) + '" stroke="' + O + '" stroke-width="1.3"/>' +
                      '<circle cx="18" cy="11" r="2.3" fill="' + darker(c, 0.7) + '" stroke="' + O + '" stroke-width="1.3"/>' +
                      '<path d="M6 22.4 L4 26.4 M9 21.4 L9 26.4" stroke="' + c + '" stroke-width="1.9" stroke-linecap="round"/>',
        dyeflower: (c) => '<path d="M15 27 L15 13.6" stroke="#6f8a4e" stroke-width="2"/>' +
                      '<path d="M15 20 Q9 19 7.6 13.6 Q13.6 14 15 20 Z" fill="#6f8a4e" stroke="' + O + '" stroke-width="1.3"/>' +
                      '<ellipse cx="15" cy="10.6" rx="10.4" ry="4.2" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                      '<circle cx="15" cy="10.6" r="2.4" fill="#f0e4b0" stroke="' + O + '" stroke-width="1.3"/>',
        spice: (c) => '<path d="M15 27 L15 16" stroke="#6f8a4e" stroke-width="2"/>' +
                      '<path d="M9 5.6 Q5.6 13 9.6 18.4 Q13.6 13 11 5.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.5"/>' +
                      '<path d="M15 3.6 Q11.6 12 15.6 18.4 Q19.6 12 17 3.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.5"/>' +
                      '<path d="M21 6.6 Q17.6 14 21.6 19.4 Q25.6 14 23 6.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.5"/>',
        firelily: (c) => '<path d="M15 27 L15 15" stroke="#6f8a4e" stroke-width="2"/>' +
                      '<path d="M4.6 6 L25.4 6 L18.4 17.4 L11.6 17.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                      '<path d="M15 6 L15 17.4 M9 6 L12.4 17.4 M21 6 L17.6 17.4" stroke="' + O + '" stroke-width="0.9" opacity="0.45"/>' +
                      '<path d="M15 7.6 L15 2.6" stroke="#f0e4b0" stroke-width="1.7"/>',
        lotus: (c) => '<ellipse cx="15" cy="23.4" rx="12" ry="3.6" fill="#4e7a38" stroke="' + O + '" stroke-width="1.5"/>' +
                      '<path d="M15 20.4 Q9 18 7 11 Q13 12 15 20.4 Z M15 20.4 Q21 18 23 11 Q17 12 15 20.4 Z M15 20.4 Q15 11 15 4.6 Q19.4 12 15 20.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.5"/>' +
                      '<circle cx="15" cy="17.4" r="2" fill="#e0d8c4" stroke="' + O + '" stroke-width="1.1"/>',
        pearl: () => '<path d="M4 16 Q6 6.6 15 6.6 Q24 6.6 26 16 Q15 21.4 4 16 Z" fill="#d8cfc0" stroke="' + O + '" stroke-width="1.7"/>' +
                      '<path d="M10 8 L12 16 M15 6.6 L15 17 M20 8 L18 16" stroke="' + O + '" stroke-width="0.9" opacity="0.45"/>' +
                      '<circle cx="15" cy="19.4" r="4.4" fill="#f4f1ea" stroke="' + O + '" stroke-width="1.6"/>' +
                      '<circle cx="13.4" cy="17.8" r="1.2" fill="#ffffff"/>',
        coral: (c) => '<path d="M15 27 L15 17 M15 20 L9 13 M15 19 L21 12 M9 13 L7 6.6 M9 13 L12 7.6 M21 12 L23 5.6 M21 12 L18 6.6" fill="none" stroke="' + c + '" stroke-width="2.6" stroke-linecap="round"/>' +
                      '<circle cx="7" cy="6" r="1.9" fill="' + c + '" stroke="' + O + '" stroke-width="1"/>' +
                      '<circle cx="12" cy="7" r="1.7" fill="' + c + '" stroke="' + O + '" stroke-width="1"/>' +
                      '<circle cx="23" cy="5" r="1.9" fill="' + c + '" stroke="' + O + '" stroke-width="1"/>' +
                      '<circle cx="18" cy="6" r="1.7" fill="' + c + '" stroke="' + O + '" stroke-width="1"/>'
      };
      const BONUS_ART = {
        WOODCUTTING: '<path d="M3.6 15 Q15 27 26.4 15 Q26.4 22.4 15 24.4 Q3.6 22.4 3.6 15 Z" fill="#8a6b3a" stroke="' + O + '" stroke-width="1.7"/>' +
                     '<path d="M5 15 Q15 21 25 15" fill="none" stroke="#5d4726" stroke-width="1.3"/>' +
                     '<ellipse cx="11" cy="13.6" rx="3.4" ry="4" fill="#dfe6ee" stroke="' + O + '" stroke-width="1.4"/>' +
                     '<ellipse cx="18.4" cy="13.6" rx="3.2" ry="3.8" fill="#dfe6ee" stroke="' + O + '" stroke-width="1.4"/>',
        MINING:      '<path d="M15 3 L24 12 L15 27 L6 12 Z" fill="#7fc8ff" stroke="' + O + '" stroke-width="1.9"/>' +
                     '<path d="M15 3 L11 12 L15 27 Z" fill="#dff1ff" opacity="0.4"/>' +
                     '<path d="M15 3 L15 27 M6 12 L24 12" stroke="#dff1ff" stroke-width="1.2" opacity="0.85"/>',
        FORAGING:    '<ellipse cx="15" cy="18.4" rx="6" ry="8" fill="#c9a94e" stroke="' + O + '" stroke-width="1.8"/>' +
                     '<path d="M15 11 Q15 4.6 20.4 2.6 Q20.4 8.4 15 11 Z" fill="#4e7a38" stroke="' + O + '" stroke-width="1.4"/>' +
                     '<path d="M12.4 15 Q15.4 19 13.4 23" fill="none" stroke="' + O + '" stroke-width="1" opacity="0.5"/>'
      };
      const matArt = (skill, kind) => {
        if (skill === 'WOODCUTTING') return logArt(WOOD[kind] || '#8a6a3e');
        if (skill === 'MINING') return oreArt(hexs(this.NODE_TINT(kind)), !!SOLID_ORE[kind]);
        if (skill === 'FORAGING' && HERB[kind]) return HERB[kind](hexs(this.NODE_TINT(kind)));
        // no art for this kind yet: the old plain disc, so the registry's
        // missing-icon throw can never fire on a new rules-table entry
        return '<circle cx="15" cy="16" r="9" fill="' + (MC[skill] || '#9a9484') + '" stroke="' + O + '" stroke-width="2"/>';
      };
      const mats = {};
      for (const k in GG.NODES) { const nd = GG.NODES[k]; mats[nd.yield[0]] = { skill: nd.skill, kind: k }; }
      for (const sk in GG.BONUS) mats[GG.BONUS[sk]] = { skill: sk, kind: null, bonus: sk };
      for (const id in mats) {
        if (R[id]) continue;
        const m = mats[id];
        def(id, { stack: true, value: 6,
          icon: svg(m.bonus ? (BONUS_ART[m.bonus] || matArt(m.skill, null)) : matArt(m.skill, m.kind)) });
      }
"""
sub(OLD_MATS, NEW_MATS, 'material icons')


out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
