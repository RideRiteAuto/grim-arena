#!/usr/bin/env python3
"""Patch 63 (relay half): server-owned party membership.

Run ONCE directly against the real relay-worker.js in the working tree (NOT
under harness/patches/ -- that directory is replayed against /tmp/game-src.html
on every build, and this script touches a different file entirely and is not
idempotent, same convention already used for the shared-rules sync).

Per claude/CHAT-PARTY-FRIENDS-PLAN.md section 3.3: party membership is relay-
owned (not client-synced) for the same reason combat is server-authoritative --
two members disagreeing about the roster after a dropped packet has no other
source of truth to resolve it. Membership lives on each socket's own
attachment (meta.party / meta.partyLeader), the same durable-across-hibernation
mechanism owner/leader flags already use, rather than a second structure that
could point at a socket that no longer exists. A party's member list is always
just "every current live socket with this partyId."

ptyi (invite) and ptyd (decline) are pure notifications -- no membership
change, so they're plain directed relays. ptya (accept), ptyl (leave) and
ptyk (kick) mutate membership and are handled here. ptyu (full roster) is
server-authored only, exactly like ndead/skupd -- it is deliberately left out
of RELAYED so a client can never forge one.

Session-only, matches the plan: nothing here touches this.state.storage, only
the transient per-socket attachment and this.sockets(), so a party simply does
not survive the Durable Object being evicted -- same as `this.sim`.
"""
import io

SRC = '/root/grim-arena/relay-worker.js'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 63 relay [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. document the new types where the other message-type sets live -----
sub(
"""// Messages the relay forwards. Anything else is dropped.
const RELAYED = new Set(['s', 'w', 'nhit', 'ndead', 'rhit', 'rdead', 'phit', 'pvp', 'pvpk', 'lreq', 'lok', 'lno', 'skupd', 'sknew', 'skgone', 'chat']);""",
"""// Messages the relay forwards. Anything else is dropped.
// ptyi/ptya/ptyd/ptyl/ptyk are listed for documentation even though they are
// intercepted and handled before this set is ever consulted (same as
// manifest/nreg/nhit/lreq/lall below) -- ptyu is deliberately NOT here: it is
// server-authored only (like ndead/skupd), so a client sending one is simply
// dropped by the generic RELAYED gate, no special-case exclusion needed.
const RELAYED = new Set(['s', 'w', 'nhit', 'ndead', 'rhit', 'rdead', 'phit', 'pvp', 'pvpk', 'lreq', 'lok', 'lno', 'skupd', 'sknew', 'skgone', 'chat', 'ptyi', 'ptya', 'ptyd', 'ptyl', 'ptyk']);
const PARTY_CAP = 5;""",
    tag='RELAYED set + party cap')

# ---- 2. intercept party message types before the generic relay path -------
sub(
"""    // ---- server-authoritative combat ------------------------------------
    if (m.t === 'manifest' || m.t === 'nreg' || m.t === 'nhit' || m.t === 'lreq' || m.t === 'lall') {
      await this.combat(ws, meta, m, socks);
      return;
    }""",
"""    // ---- server-authoritative combat ------------------------------------
    if (m.t === 'manifest' || m.t === 'nreg' || m.t === 'nhit' || m.t === 'lreq' || m.t === 'lall') {
      await this.combat(ws, meta, m, socks);
      return;
    }
    // ---- party membership (relay-owned, see the note above RELAYED) -----
    if (m.t === 'ptyi' || m.t === 'ptya' || m.t === 'ptyd' || m.t === 'ptyl' || m.t === 'ptyk') {
      this.party(ws, meta, m, socks);
      return;
    }""",
    tag='party dispatch intercept')

# ---- 3. party chat fans out to members only, not everyone -----------------
sub(
"""    m._p = meta.id;                                 // sender, stamped here and never trusted from the client
    delete m.to_;                                   // reserved

    if (m.to) {                                     // directed reply, used for loot grants""",
"""    m._p = meta.id;                                 // sender, stamped here and never trusted from the client
    delete m.to_;                                   // reserved

    // Party chat is scoped server-side to the sender's current party rather
    // than trusting each client to loop over member ids itself -- one send
    // in, correctly scoped delivery out, and it can't drift from ptyu.
    if (m.t === 'chat' && m.ch === 'party') {
      if (meta.party) {
        for (const s of this.partyMembers(socks, meta.party)) { if (s !== ws) this.send(s, m); }
      }
      return;
    }

    if (m.to) {                                     // directed reply, used for loot grants""",
    tag='party chat fan-out')

# ---- 4. a disconnecting member leaves their party the same way /leave does
sub(
"""  gone(ws) {
    const meta = this.meta(ws);
    const socks = this.sockets().filter(s => s !== ws);
    if (meta) this.broadcast(socks, { t: 'left', i: meta.id });""",
"""  gone(ws) {
    const meta = this.meta(ws);
    const socks = this.sockets().filter(s => s !== ws);
    if (meta) this.broadcast(socks, { t: 'left', i: meta.id });
    if (meta && meta.party) this.partyLeaveInternal(meta, socks);""",
    tag='disconnect leaves party')

# ---- 5. the party methods themselves, dropped in beside owner handover ----
sub(
"""  // ------------------------------------------------------------------ owner

  // The sticky flag wins; with no flag in the room the oldest connection is""",
"""  // ------------------------------------------------------------------ party
  //
  // Every party op reads/writes the mutating socket's own attachment plus
  // whichever other sockets are affected, then always finishes by pushing a
  // fresh ptyu to every remaining member so nobody's client can go stale.
  // Nothing here is trusted from the client except which target id a client
  // is asking about -- membership itself is decided from live attachments.

  party(ws, meta, m, socks) {
    if (m.t === 'ptyi') {                             // pure notification, no membership change
      if (!m.to || m.to === meta.id) return;
      const target = socks.find(s => { const x = this.meta(s); return x && x.id === m.to; });
      if (target) this.send(target, { t: 'ptyi', from: meta.id, name: meta.name, color: meta.color });
      return;
    }
    if (m.t === 'ptyd') {                             // decline: notify the inviter only
      if (!m.to) return;
      const target = socks.find(s => { const x = this.meta(s); return x && x.id === m.to; });
      if (target) this.send(target, { t: 'ptyd', from: meta.id, name: meta.name });
      return;
    }
    if (m.t === 'ptya') { this.partyAccept(ws, meta, m, socks); return; }
    if (m.t === 'ptyl') { this.partyLeave(ws, meta, socks); return; }
    if (m.t === 'ptyk') { this.partyKick(ws, meta, m, socks); return; }
  }

  partyMembers(socks, partyId) {
    return socks.filter(s => { const x = this.meta(s); return x && x.party === partyId; });
  }

  partyRosterPush(socks, partyId) {
    const members = this.partyMembers(socks, partyId);
    const roster = members.map(s => { const x = this.meta(s); return { i: x.id, n: x.name, c: x.color, leader: !!x.partyLeader }; });
    for (const s of members) this.send(s, { t: 'ptyu', party: partyId, members: roster });
  }

  partyAccept(ws, meta, m, socks) {
    if (!m.to) return;
    const inviter = socks.find(s => { const x = this.meta(s); return x && x.id === m.to; });
    if (!inviter) return;
    let invMeta = this.meta(inviter);
    if (!invMeta) return;

    // the inviter's first accepted invite is what starts a party
    let partyId = invMeta.party;
    if (!partyId) {
      partyId = 'pty_' + invMeta.id;
      invMeta.party = partyId; invMeta.partyLeader = true;
      this.setMeta(inviter, invMeta);
    }

    if (meta.party === partyId) return;               // already in it (duplicate accept)

    const already = this.partyMembers(socks, partyId);
    if (already.length >= PARTY_CAP) {
      this.send(ws, { t: 'ptyu', party: null, members: [], full: true });
      return;
    }

    // joining a new party means leaving whatever party you were already in
    if (meta.party) this.partyLeaveInternal(meta, socks);

    meta.party = partyId; meta.partyLeader = false;
    this.setMeta(ws, meta);
    this.partyRosterPush(socks, partyId);
  }

  partyLeave(ws, meta, socks) {
    if (!meta.party) return;
    this.partyLeaveInternal(meta, socks);
    this.setMeta(ws, meta);
    this.send(ws, { t: 'ptyu', party: null, members: [] });
  }

  // Shared by an explicit /leave, a kick target, and a plain disconnect.
  // Mutates the departing member's own `meta` object (caller persists or
  // discards it) and repromotes / dissolves the remainder.
  partyLeaveInternal(meta, socks) {
    const partyId = meta.party;
    const leavingId = meta.id;
    const wasLeader = !!meta.partyLeader;
    delete meta.party; delete meta.partyLeader;

    const remaining = this.partyMembers(socks, partyId).filter(s => { const x = this.meta(s); return x && x.id !== leavingId; });
    if (!remaining.length) return;                     // party dissolves with nobody left

    if (remaining.length === 1) {                       // no reason to keep a lone member "in a party"
      const only = this.meta(remaining[0]);
      delete only.party; delete only.partyLeader;
      this.setMeta(remaining[0], only);
      this.send(remaining[0], { t: 'ptyu', party: null, members: [] });
      return;
    }

    if (wasLeader) {                                    // hand leadership to the longest-standing member,
      let best = null;                                  // the same seniority rule pickNewOwner already uses
      for (const s of remaining) {
        const x = this.meta(s);
        if (!best || x.joined < best.x.joined) best = { s, x };
      }
      if (best) { best.x.partyLeader = true; this.setMeta(best.s, best.x); }
    }
    this.partyRosterPush(socks, partyId);
  }

  partyKick(ws, meta, m, socks) {
    if (!meta.party || !meta.partyLeader || !m.to || m.to === meta.id) return;
    const target = socks.find(s => { const x = this.meta(s); return x && x.id === m.to && x.party === meta.party; });
    if (!target) return;
    const tMeta = this.meta(target);
    delete tMeta.party; delete tMeta.partyLeader;
    this.setMeta(target, tMeta);
    this.send(target, { t: 'ptyu', party: null, members: [], kicked: true });
    this.partyRosterPush(socks, meta.party);
  }

  // ------------------------------------------------------------------ owner

  // The sticky flag wins; with no flag in the room the oldest connection is""",
    tag='party methods')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('63_party_relay: %d edits applied' % n)
