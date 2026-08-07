#!/usr/bin/env python3
"""Patch 71: combat level, shown by your name and in party frames.

Kevin's earlier go-ahead: "make it look nice and polished like a modern rpg
mmo." Next item on the explicit list after zone tracking (patch 70): "the
combat-level formula."

Formula (as specified): round((HITPOINTS_lvl + max(MELEE_lvl, RANGED_lvl,
MAGIC_lvl)) / 2), capped at 99. Non-combat gathering skills (WOODCUTTING,
MINING, FORAGING, SMITHING) are intentionally excluded -- this is a
DIFFERENT number from the existing Skills panel's "TOTAL LEVEL" stat, which
sums all 8 skills for a different purpose and is left untouched here.

Plumbing, following the same pattern patch 70 used for zone:
- New combatLevel() method computes it fresh from this.skills via the
  existing this.lvl(xp) accessor. No new state to keep in sync, it is
  always derived live from the skills that are already the source of truth.
- myWorldState() gains a `cl` field alongside the `z` zone key patch 70
  added, riding the same 10x/second broadcast every player already sends.
  updateRemote() already stores the whole incoming state with no
  allow-list, so a remote's combat level shows up at r.s.cl for free.
- The HUD's own-name nameplate (#grim-nameplate, set once in play()) grows
  a "(Lvl N)" suffix. A new refreshNameplate_() helper re-renders it from a
  stored base name, so it can be called again later without re-deriving
  the player's display name. awardXp() calls it whenever a combat-relevant
  skill (HITPOINTS/MELEE/RANGED/MAGIC) levels up, so the nameplate never
  shows a stale number after a level-up banner.
- Party frames: the zone line patch 70 added to partyFrameRow() becomes a
  combined "Zone · Lvl N" meta line. opts.zone and opts.lvl are independent
  (either can be present without the other) so a remote that has not sent
  cl yet still shows its zone with no crash and no stray "Lvl undefined",
  exactly mirroring how a missing zone already degraded gracefully.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 71 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. combatLevel() -- lives right next to lvl()/xpFor(), the skill ----
#         accessors it is built from.
sub(
    "  lvl(xp) { return grimLevelFromXp(xp); }\n"
    "  xpFor(l) { return grimXpForLevel(l); }",
    "  lvl(xp) { return grimLevelFromXp(xp); }\n"
    "  xpFor(l) { return grimXpForLevel(l); }\n"
    "  // Combat level: hitpoints plus your best combat skill, halved and\n"
    "  // capped at 99. Deliberately excludes the gathering skills, unlike\n"
    "  // the Skills panel's separate 'TOTAL LEVEL' stat which sums all 8.\n"
    "  combatLevel() {\n"
    "    const hp = this.lvl(this.skills.HITPOINTS);\n"
    "    const atk = Math.max(this.lvl(this.skills.MELEE), this.lvl(this.skills.RANGED), this.lvl(this.skills.MAGIC));\n"
    "    return Math.min(99, Math.round((hp + atk) / 2));\n"
    "  }",
    tag='combatLevel method')

# ---- 2. myWorldState broadcasts it alongside the zone key -----------------
sub(
    "an: (me.act && me.act.name) || 0, pv: this.pvpOn ? 1 : 0, z: this.zoneAt ? this.zoneAt(me.pos.x, me.pos.z) : '', h: Math.round(me.hp),",
    "an: (me.act && me.act.name) || 0, pv: this.pvpOn ? 1 : 0, z: this.zoneAt ? this.zoneAt(me.pos.x, me.pos.z) : '', cl: this.combatLevel(), h: Math.round(me.hp),",
    tag='myWorldState broadcasts combat level')

# ---- 3. own-name nameplate grows a level suffix, refreshable on level-up --
sub(
    "    const np = document.getElementById('grim-nameplate');\n"
    "    if (np) np.textContent = this.profile ? this.profile.u.toUpperCase() : (this.myIdentity().name || 'YOU');",
    "    const np = document.getElementById('grim-nameplate');\n"
    "    if (np) { this._npBaseName = this.profile ? this.profile.u.toUpperCase() : (this.myIdentity().name || 'YOU'); this.refreshNameplate_(); }",
    tag='play() sets base name and refreshes nameplate')

sub(
    "  lvl(xp) { return grimLevelFromXp(xp); }\n"
    "  xpFor(l) { return grimXpForLevel(l); }\n"
    "  // Combat level: hitpoints plus your best combat skill, halved and\n"
    "  // capped at 99. Deliberately excludes the gathering skills, unlike\n"
    "  // the Skills panel's separate 'TOTAL LEVEL' stat which sums all 8.\n"
    "  combatLevel() {\n"
    "    const hp = this.lvl(this.skills.HITPOINTS);\n"
    "    const atk = Math.max(this.lvl(this.skills.MELEE), this.lvl(this.skills.RANGED), this.lvl(this.skills.MAGIC));\n"
    "    return Math.min(99, Math.round((hp + atk) / 2));\n"
    "  }",
    "  lvl(xp) { return grimLevelFromXp(xp); }\n"
    "  xpFor(l) { return grimXpForLevel(l); }\n"
    "  // Combat level: hitpoints plus your best combat skill, halved and\n"
    "  // capped at 99. Deliberately excludes the gathering skills, unlike\n"
    "  // the Skills panel's separate 'TOTAL LEVEL' stat which sums all 8.\n"
    "  combatLevel() {\n"
    "    const hp = this.lvl(this.skills.HITPOINTS);\n"
    "    const atk = Math.max(this.lvl(this.skills.MELEE), this.lvl(this.skills.RANGED), this.lvl(this.skills.MAGIC));\n"
    "    return Math.min(99, Math.round((hp + atk) / 2));\n"
    "  }\n"
    "  // Re-renders the nameplate from the base name play() stashed, so a\n"
    "  // level-up can refresh just the number without re-deriving the name.\n"
    "  refreshNameplate_() {\n"
    "    const np = document.getElementById('grim-nameplate');\n"
    "    if (np && this._npBaseName) np.textContent = this._npBaseName + ' (Lvl ' + this.combatLevel() + ')';\n"
    "  }",
    tag='refreshNameplate_ helper')

# ---- 4. awardXp() refreshes the nameplate when a combat skill levels up ---
sub(
    "if (after > before) { this.banner(skill + ' LEVEL ' + after, 'ONWARD', false, 2200); this.sfx('win'); if (skill === 'HITPOINTS' && this.worldOn && this.mode === 'ai' && this.me) { const gain = (after - before) * 10; this.me.max += gain; this.me.hp += gain; } }",
    "if (after > before) { this.banner(skill + ' LEVEL ' + after, 'ONWARD', false, 2200); this.sfx('win'); if (skill === 'HITPOINTS' && this.worldOn && this.mode === 'ai' && this.me) { const gain = (after - before) * 10; this.me.max += gain; this.me.hp += gain; } if (skill === 'HITPOINTS' || skill === 'MELEE' || skill === 'RANGED' || skill === 'MAGIC') this.refreshNameplate_(); }",
    tag='awardXp refreshes nameplate on combat level-up')

# ---- 5. partyFrameRow: zone line becomes a combined zone/level meta line --
#         opts.zone and opts.lvl are independent, either can be missing.
sub(
    """    row.appendChild(top);
    if (opts.zone) row.appendChild(mk('div', 'font-size:9px;color:#7d8a63;letter-spacing:0.06em;margin:-2px 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;', opts.zone));
    row.appendChild(track);""",
    """    row.appendChild(top);
    const metaBits = [];
    if (opts.zone) metaBits.push(opts.zone);
    if (opts.lvl !== undefined && opts.lvl !== null) metaBits.push('Lvl ' + opts.lvl);
    if (metaBits.length) row.appendChild(mk('div', 'font-size:9px;color:#7d8a63;letter-spacing:0.06em;margin:-2px 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;', metaBits.join(' \\u00b7 ')));
    row.appendChild(track);""",
    tag='partyFrameRow combined zone/level meta line')

# ---- 6. renderPartyFrames: pass combat level for self and remotes --------
sub(
    """    if (meMember && this.me) {
      const myZone = (this.zoneAt && this.me.pos) ? this.zoneLabel_(this.zoneAt(this.me.pos.x, this.me.pos.z)) : '';
      el.appendChild(this.partyFrameRow(this.myName || meMember.n || 'YOU', this.me.hp, this.me.max, this.me.mana, this.me.manaCap || 100, { leader: !!meMember.leader, pv: !!this.pvpOn, dead: this.me.hp <= 0, self: true, zone: myZone }));
    }""",
    """    if (meMember && this.me) {
      const myZone = (this.zoneAt && this.me.pos) ? this.zoneLabel_(this.zoneAt(this.me.pos.x, this.me.pos.z)) : '';
      el.appendChild(this.partyFrameRow(this.myName || meMember.n || 'YOU', this.me.hp, this.me.max, this.me.mana, this.me.manaCap || 100, { leader: !!meMember.leader, pv: !!this.pvpOn, dead: this.me.hp <= 0, self: true, zone: myZone, lvl: this.combatLevel() }));
    }""",
    tag='renderPartyFrames self row combat level')

sub(
    """      const theirZone = (r && r.s && r.s.z) ? this.zoneLabel_(r.s.z) : '';
      el.appendChild(this.partyFrameRow(pm.n || 'PLAYER', hp, max, mana, manaMax, { leader: !!pm.leader, pv: !!(r && r.ent && r.ent._pv), dead: !!(r && r.ent && r.ent.hp <= 0), self: false, id: pm.i, zone: theirZone }));""",
    """      const theirZone = (r && r.s && r.s.z) ? this.zoneLabel_(r.s.z) : '';
      const theirLvl = (r && r.s && r.s.cl !== undefined) ? r.s.cl : null;
      el.appendChild(this.partyFrameRow(pm.n || 'PLAYER', hp, max, mana, manaMax, { leader: !!pm.leader, pv: !!(r && r.ent && r.ent._pv), dead: !!(r && r.ent && r.ent.hp <= 0), self: false, id: pm.i, zone: theirZone, lvl: theirLvl }));""",
    tag='renderPartyFrames remote row combat level')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('71_combat_level: %d edits applied (1-6)' % n)
