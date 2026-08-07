#!/usr/bin/env python3
"""Patch 70: party frames show which zone each member is standing in.

Kevin's earlier go-ahead: "make it look nice and polished like a modern rpg
mmo" -- knowing where your party is without asking in chat is a basic MMO
party-frame feature.

The zone key was already being computed for other purposes (the perf HUD's
debug readout, zone music), so this reuses the same this.zoneAt(x, z) rather
than inventing a second way to ask "what zone is this position in."

Plumbing:
- myWorldState() (the ~10x/second state broadcast every player already
  sends) gains a `z` field: your current zone KEY (e.g. 'HEARTLANDS'),
  computed the same way the perf HUD's zone line already does. This is the
  one broadcast every peer/host relay path already carries, so no new
  message type or send loop, just one more short field on the existing one.
- updateRemote() already stores the whole incoming state object as r.s with
  no per-field allow-list, so a remote's zone shows up at r.s.z for free,
  the same way r.s.h/r.s.pv already do for HP and PVP flag (see how the
  social panel roster reads those in patch 67).
- New zoneLabel_(key) turns a zone KEY into its display name via
  GRIM_RULES.ZONES, e.g. 'HEARTLANDS' -> 'Heartlands', so frames show the
  same names players see everywhere else, not raw internal keys.
- partyFrameRow() gains an opts.zone line, a small muted label under the
  name, above the health bar. renderPartyFrames() computes it fresh for
  your own row (this.zoneAt on your live position) and reads it from
  r.s.z for every other party member.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 70 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. broadcast your own zone key on the existing state message ---------
sub(
    "an: (me.act && me.act.name) || 0, pv: this.pvpOn ? 1 : 0, h: Math.round(me.hp),",
    "an: (me.act && me.act.name) || 0, pv: this.pvpOn ? 1 : 0, z: this.zoneAt ? this.zoneAt(me.pos.x, me.pos.z) : '', h: Math.round(me.hp),",
    tag='myWorldState broadcasts zone key')

# ---- 2. zone key -> display name, the same names players see everywhere --
sub(
    "  zoneName(x, z) { const Z = GRIM_RULES.ZONES[this.zoneAt(x, z)]; return Z ? Z.name : 'Unknown'; }",
    "  zoneName(x, z) { const Z = GRIM_RULES.ZONES[this.zoneAt(x, z)]; return Z ? Z.name : 'Unknown'; }\n"
    "  // Same lookup as zoneName(), but from a zone KEY already in hand (a\n"
    "  // remote's broadcast state, not a live position) rather than x/z.\n"
    "  zoneLabel_(key) { const Z = GRIM_RULES.ZONES[key]; return (Z && Z.name) || key || ''; }",
    tag='zoneLabel_ helper')

# ---- 3. partyFrameRow: a small zone line under the name --------------------
# Appended AFTER top (not before) so the name always stays the first thing
# in the row's text content, same as before this patch, and only a row that
# actually has a zone to show grows a 4th child.
sub(
    """    row.appendChild(top); row.appendChild(track);""",
    """    row.appendChild(top);
    if (opts.zone) row.appendChild(mk('div', 'font-size:9px;color:#7d8a63;letter-spacing:0.06em;margin:-2px 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;', opts.zone));
    row.appendChild(track);""",
    tag='partyFrameRow zone line')

# ---- 4. renderPartyFrames: pass zone for self and for every party member --
sub(
    """    if (meMember && this.me) {
      el.appendChild(this.partyFrameRow(this.myName || meMember.n || 'YOU', this.me.hp, this.me.max, this.me.mana, this.me.manaCap || 100, { leader: !!meMember.leader, pv: !!this.pvpOn, dead: this.me.hp <= 0, self: true }));
    }""",
    """    if (meMember && this.me) {
      const myZone = (this.zoneAt && this.me.pos) ? this.zoneLabel_(this.zoneAt(this.me.pos.x, this.me.pos.z)) : '';
      el.appendChild(this.partyFrameRow(this.myName || meMember.n || 'YOU', this.me.hp, this.me.max, this.me.mana, this.me.manaCap || 100, { leader: !!meMember.leader, pv: !!this.pvpOn, dead: this.me.hp <= 0, self: true, zone: myZone }));
    }""",
    tag='renderPartyFrames self row zone')

sub(
    """      const mana = (r && r.s && r.s.mn !== undefined) ? r.s.mn : null;
      const manaMax = (r && r.s && r.s.mc) || 100;
      el.appendChild(this.partyFrameRow(pm.n || 'PLAYER', hp, max, mana, manaMax, { leader: !!pm.leader, pv: !!(r && r.ent && r.ent._pv), dead: !!(r && r.ent && r.ent.hp <= 0), self: false, id: pm.i }));""",
    """      const mana = (r && r.s && r.s.mn !== undefined) ? r.s.mn : null;
      const manaMax = (r && r.s && r.s.mc) || 100;
      const theirZone = (r && r.s && r.s.z) ? this.zoneLabel_(r.s.z) : '';
      el.appendChild(this.partyFrameRow(pm.n || 'PLAYER', hp, max, mana, manaMax, { leader: !!pm.leader, pv: !!(r && r.ent && r.ent._pv), dead: !!(r && r.ent && r.ent.hp <= 0), self: false, id: pm.i, zone: theirZone }));""",
    tag='renderPartyFrames remote row zone')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('70_zone_tracking_party_frames: %d edits applied (1-5)' % n)
