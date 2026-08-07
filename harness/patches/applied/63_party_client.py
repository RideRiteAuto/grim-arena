#!/usr/bin/env python3
"""Patch 63 (client half): party UI on top of the relay-owned membership
added in relay-worker.js by 63_party_relay.py (a separate, standalone script
run directly against relay-worker.js -- that file is not part of this
extract/patch/pack pipeline, see its own docstring).

Per claude/CHAT-PARTY-FRIENDS-PLAN.md section 3: this.party is always just a
mirror of the last ptyu the relay sent -- the client never invents or
resolves membership itself, matching the server-authoritative reasoning
already used for combat.

Scope call: right-click-a-nametag "Invite to Party" (plan section 4.3) is
deferred to patch 64, where it becomes one unified Whisper / Invite / Add
Friend menu built once for all three actions rather than three separate
context-menu implementations. This patch ships the two entry points that
need no new UI infrastructure: /invite NAME (any chat tab) and an INVITE
button on the existing hold-O player list.

New PARTY chat tab reuses everything patch 62 already built (CHAT_TABS,
sendChat, chatLine, the bubble system) -- the only real gap patch 62 left is
that onChatMsg collapsed every non-global channel into 'local', which would
have wrongly local-radius-filtered party messages from members who happen to
be far away. That's fixed here alongside adding the tab.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 63 client [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. a third tab -------------------------------------------------------
sub(
"CHAT_TABS() { return [{ key: 'local', label: 'LOCAL' }, { key: 'global', label: 'GLOBAL' }]; }",
"CHAT_TABS() { return [{ key: 'local', label: 'LOCAL' }, { key: 'global', label: 'GLOBAL' }, { key: 'party', label: 'PARTY' }]; }",
    tag='CHAT_TABS adds party')

# ---- 2. sendChat: /invite command, and refuse to send to PARTY with none -
sub(
"""  sendChat() {
    if (!this.chatInputEl) return;
    const raw = this.chatInputEl.value;
    this.chatInputEl.value = '';
    const text = String(raw || '').trim().slice(0, 180);
    if (!text) { this.chatInputEl.blur(); return; }
    const now = performance.now();
    if (now - (this._chatSentAt || 0) < 380) return;   // client-side throttle; the relay backstops at 60/sec anyway
    this._chatSentAt = now;
    const ch = this.chatTab;
    const name = ((this.myName || this.myIdentity().name || 'YOU') + '').toUpperCase().slice(0, 12);
    const p = this.me ? [+this.me.pos.x.toFixed(1), +this.me.pos.z.toFixed(1)] : [0, 0];
    this.netAll({ t: 'chat', ch: ch, msg: text, n: name, p: p });
    this.chatLine(ch, name, text);
    if (ch === 'local' && this.me) this.sayBubble('chat:me', this.me.pos, text, { dur: 4200 });
  }""",
"""  sendChat() {
    if (!this.chatInputEl) return;
    const raw = this.chatInputEl.value;
    this.chatInputEl.value = '';
    const text = String(raw || '').trim().slice(0, 180);
    if (!text) { this.chatInputEl.blur(); return; }
    const inviteM = /^\\/invite\\s+(.+)$/i.exec(text);
    if (inviteM) { this.inviteByName(inviteM[1].trim()); return; }
    const ch = this.chatTab;
    if (ch === 'party' && !this.party) { this.uiNote('NOT IN A PARTY', 'Invite someone, or type /invite NAME, to start one.'); return; }
    const now = performance.now();
    if (now - (this._chatSentAt || 0) < 380) return;   // client-side throttle; the relay backstops at 60/sec anyway
    this._chatSentAt = now;
    const name = ((this.myName || this.myIdentity().name || 'YOU') + '').toUpperCase().slice(0, 12);
    const p = this.me ? [+this.me.pos.x.toFixed(1), +this.me.pos.z.toFixed(1)] : [0, 0];
    this.netAll({ t: 'chat', ch: ch, msg: text, n: name, p: p });
    this.chatLine(ch, name, text);
    if ((ch === 'local' || ch === 'party') && this.me) this.sayBubble('chat:me', this.me.pos, text, { dur: 4200 });
  }""",
    tag='sendChat invite command + party guard')

# ---- 3. onChatMsg: party is its own channel, not local's distance filter -
sub(
"""    const ch = (m.ch === 'global') ? 'global' : 'local';
    let pos = null;
    if (Array.isArray(m.p) && m.p.length >= 2) pos = { x: m.p[0], y: 0, z: m.p[1] };
    if (ch === 'local') {
      if (!pos || !this.me) return;
      if (this.me.pos.distanceTo(new this.T.Vector3(pos.x, 0, pos.z)) > this.LOCAL_CHAT_R) return;
    }
    this.buildChatDom();
    this.chatLine(ch, name, text);
    if (ch === 'local') {
      const r = m._p && this.remotes[m._p];
      this.sayBubble('chat:' + (m._p || name), r ? r.ent.pos : pos, text, { dur: 4200 });
    }""",
"""    const ch = (m.ch === 'global') ? 'global' : (m.ch === 'party') ? 'party' : 'local';
    let pos = null;
    if (Array.isArray(m.p) && m.p.length >= 2) pos = { x: m.p[0], y: 0, z: m.p[1] };
    if (ch === 'local') {
      if (!pos || !this.me) return;
      if (this.me.pos.distanceTo(new this.T.Vector3(pos.x, 0, pos.z)) > this.LOCAL_CHAT_R) return;
    }
    this.buildChatDom();
    this.chatLine(ch, name, text);
    if (ch === 'local' || ch === 'party') {
      const r = m._p && this.remotes[m._p];
      this.sayBubble('chat:' + (m._p || name), r ? r.ent.pos : pos, text, { dur: 4200 });
    }""",
    tag='onChatMsg party channel')

# ---- 4. onWorldData routes the three party message types ------------------
sub(
"onWorldData(from, m) { if (!m || !m.t) return; if (m.t === 'chat') { this.onChatMsg(m); return; }",
"onWorldData(from, m) { if (!m || !m.t) return; if (m.t === 'chat') { this.onChatMsg(m); return; } if (m.t === 'ptyi') { this.onPartyInvite(m); return; } if (m.t === 'ptyd') { this.onPartyDeclined(m); return; } if (m.t === 'ptyu') { this.onPartyRoster(m); return; }",
    tag='onWorldData party routing')

# ---- 5. tick(): keep party HP frames fresh --------------------------------
sub(
"""    this.stepBubbles(dt);
    this.stepNpcChatter(dt);
    this.stepPickups(dt);""",
"""    this.stepBubbles(dt);
    this.stepNpcChatter(dt);
    this.stepPartyFrames(dt);
    this.stepPickups(dt);""",
    tag='tick calls stepPartyFrames')

# ---- 6. hold-O player list: an INVITE button per other player -------------
sub(
"""const row = (name, right, gold) => { const d = mk('div', 'display:flex;justify-content:space-between;gap:20px;padding:5px 0;border-bottom:1px solid #26281f;font-size:13px;' + (gold ? 'color:#e8c774;' : '')); d.appendChild(mk('span', '', name)); d.appendChild(mk('span', 'color:#7d8a63;font-size:11px;', right)); return d; }; el.appendChild(row((this.myName || 'YOU') + ' (you)', this.isWorldHost ? 'HOST' : 'ONLINE', true)); let n = 0; for (const id in (this.remotes || {})) { const r = this.remotes[id]; n++; el.appendChild(row((r.s && r.s.pv ? '⚔ ' : '') + (r.name || 'PLAYER'), (r.s && r.s.h !== undefined ? r.s.h + ' HP' : 'ONLINE'), false)); }""",
"""const row = (name, right, gold, id, rawName) => { const d = mk('div', 'display:flex;align-items:center;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid #26281f;font-size:13px;' + (gold ? 'color:#e8c774;' : '')); d.appendChild(mk('span', 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;', name)); const rightWrap = mk('div', 'display:flex;align-items:center;gap:8px;flex:none;'); rightWrap.appendChild(mk('span', 'color:#7d8a63;font-size:11px;white-space:nowrap;', right)); if (id && !(this.party && this.party.members.some(pm => pm.i === id))) { const inv = document.createElement('button'); inv.textContent = 'INVITE'; inv.style.cssText = 'pointer-events:auto;cursor:pointer;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:5px;font-size:9px;padding:3px 6px;font-family:inherit;'; inv.onclick = () => this.sendPartyInvite(id, rawName || name); rightWrap.appendChild(inv); } d.appendChild(rightWrap); return d; }; el.appendChild(row((this.myName || 'YOU') + ' (you)', this.isWorldHost ? 'HOST' : 'ONLINE', true)); let n = 0; for (const id in (this.remotes || {})) { const r = this.remotes[id]; n++; el.appendChild(row((r.s && r.s.pv ? '⚔ ' : '') + (r.name || 'PLAYER'), (r.s && r.s.h !== undefined ? r.s.h + ' HP' : 'ONLINE'), false, id, r.name)); }""",
    tag='player list invite button')

# ---- 7. the party methods themselves, dropped in beside chat --------------
sub(
"""      this.sayBubble('chat:' + (m._p || name), r ? r.ent.pos : pos, text, { dur: 4200 });
    }
  }

  // ------------------------------------------------------------- pickups""",
"""      this.sayBubble('chat:' + (m._p || name), r ? r.ent.pos : pos, text, { dur: 4200 });
    }
  }

  // ------------------------------------------------------------- party
  // this.party mirrors the last ptyu the relay sent -- never resolved or
  // guessed locally, same reasoning server-authoritative combat already
  // uses. Right-click-a-nametag invite is deferred to patch 64 (see this
  // file's docstring); this ships /invite NAME and the player-list button.
  escHtml(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  amPartyLeader() {
    if (!this.party || !this.netId) return false;
    const me = this.party.members.find(pm => pm.i === this.netId);
    return !!(me && me.leader);
  }

  sendPartyInvite(id, name) {
    if (!id || id === this.netId) return;
    this.netTo(id, { t: 'ptyi' });
    this.uiNote('INVITE SENT', 'Waiting for ' + this.escHtml(name || 'that player') + ' to respond.');
  }

  inviteByName(name) {
    const nl = String(name || '').trim().toUpperCase();
    if (!nl) return;
    let id = null, found = null;
    for (const pid in (this.remotes || {})) {
      if ((this.remotes[pid].name || '').toUpperCase() === nl) { id = pid; found = this.remotes[pid].name; break; }
    }
    if (!id) { this.uiNote('PLAYER NOT FOUND', this.escHtml(name) + ' is not nearby or not connected.'); return; }
    this.sendPartyInvite(id, found);
  }

  leaveParty() { if (this.party) this.netAll({ t: 'ptyl' }); }
  kickPartyMember(id) { if (id) this.netTo(id, { t: 'ptyk' }); }

  onPartyInvite(m) { if (m && m.from) this.showPartyInvitePopup(m.from, m.name || 'PLAYER'); }
  onPartyDeclined(m) { this.uiNote('INVITE DECLINED', this.escHtml((m && m.name) || 'That player') + ' declined your party invite.'); }
  onPartyRoster(m) {
    if (!m) return;
    if (m.full) { this.uiNote('PARTY IS FULL', 'That party already has the maximum of 5 members.'); return; }
    if (m.kicked) { this.party = null; this.renderPartyFrames(); this.uiNote('REMOVED FROM PARTY', 'The party leader removed you.'); return; }
    this.party = (m.party && m.members && m.members.length) ? { id: m.party, members: m.members } : null;
    this.renderPartyFrames();
  }

  buildPartyInviteDom() {
    if (this.piEl) return this.piEl;
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    const wrap = mk('div', 'position:fixed;left:50%;top:110px;transform:translateX(-50%);z-index:' + this.Z.pop + ';display:none;' +
      'background:rgba(12,13,9,0.97);border:1px solid #3a3f2c;border-top:2px solid #c8a24a;padding:12px 16px;' +
      'font-family:IBM Plex Mono,monospace;color:#d8d4c6;text-align:center;box-shadow:0 14px 50px rgba(0,0,0,0.7);min-width:240px;');
    const name = mk('div', 'font-size:13px;margin-bottom:10px;');
    const row = mk('div', 'display:flex;gap:8px;justify-content:center;');
    const accept = document.createElement('button');
    accept.textContent = 'ACCEPT';
    accept.style.cssText = 'flex:1;background:#c8a24a;color:#17180f;border:none;border-radius:8px;padding:8px 0;font-weight:800;font-family:inherit;font-size:12px;cursor:pointer;';
    accept.onclick = () => this.respondPartyInvite(true);
    const decline = document.createElement('button');
    decline.textContent = 'DECLINE';
    decline.style.cssText = 'flex:1;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:8px;padding:8px 0;font-weight:700;font-family:inherit;font-size:12px;cursor:pointer;';
    decline.onclick = () => this.respondPartyInvite(false);
    row.appendChild(accept); row.appendChild(decline);
    wrap.appendChild(name); wrap.appendChild(row);
    document.body.appendChild(wrap);
    this.piEl = wrap; this._piNameEl = name;
    return wrap;
  }
  showPartyInvitePopup(fromId, fromName) {
    const wrap = this.buildPartyInviteDom();
    this._piFromId = fromId;
    this._piNameEl.textContent = fromName + ' invited you to a party';
    wrap.style.display = 'block';
    clearTimeout(this._piTimer);
    this._piTimer = setTimeout(() => { wrap.style.display = 'none'; }, 30000);
  }
  respondPartyInvite(accepted) {
    const from = this._piFromId;
    if (this.piEl) this.piEl.style.display = 'none';
    clearTimeout(this._piTimer);
    this._piFromId = null;
    if (!from) return;
    this.netTo(from, { t: accepted ? 'ptya' : 'ptyd' });
  }

  buildPartyFramesDom() {
    if (this.pfEl) return;
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;left:14px;top:14px;width:190px;display:none;flex-direction:column;gap:4px;z-index:' + this.Z.hint + ';';
    document.body.appendChild(d);
    this.pfEl = d;
  }
  partyFrameRow(name, hp, max, opts) {
    opts = opts || {};
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    const row = mk('div', 'background:rgba(12,13,9,0.88);border:1px solid #3a3f2c;border-radius:8px;padding:5px 8px;pointer-events:auto;' + (opts.dead ? 'opacity:0.5;' : ''));
    const top = mk('div', 'display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:3px;');
    const nm = mk('span', 'font-size:11px;font-weight:700;color:#e8c774;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;', (opts.leader ? '★ ' : '') + (opts.pv ? '⚔ ' : '') + name);
    top.appendChild(nm);
    if (opts.self && this.party) {
      const lv = document.createElement('button');
      lv.textContent = 'LEAVE';
      lv.style.cssText = 'pointer-events:auto;cursor:pointer;flex:none;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:5px;font-size:9px;padding:2px 5px;font-family:inherit;';
      lv.onclick = () => this.leaveParty();
      top.appendChild(lv);
    } else if (!opts.self && opts.id && this.amPartyLeader()) {
      const kk = document.createElement('button');
      kk.textContent = 'KICK';
      kk.style.cssText = 'pointer-events:auto;cursor:pointer;flex:none;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:5px;font-size:9px;padding:2px 5px;font-family:inherit;';
      kk.onclick = () => this.kickPartyMember(opts.id);
      top.appendChild(kk);
    }
    const track = mk('div', 'height:8px;background:#1c1e15;border:1px solid #2a2c20;border-radius:4px;overflow:hidden;');
    const pct = max > 0 ? Math.max(0, Math.min(1, hp / max)) : 0;
    const fill = mk('div', 'height:100%;width:' + Math.round(pct * 100) + '%;background:' + (pct > 0.5 ? '#5fae3d' : pct > 0.25 ? '#c8a24a' : '#a3342c') + ';transition:width 200ms;');
    track.appendChild(fill);
    row.appendChild(top); row.appendChild(track);
    return row;
  }
  renderPartyFrames() {
    this.buildPartyFramesDom();
    const el = this.pfEl;
    while (el.firstChild) el.removeChild(el.firstChild);
    if (!this.party || !this.party.members || !this.party.members.length) { el.style.display = 'none'; return; }
    el.style.display = 'flex';
    const meMember = this.party.members.find(pm => pm.i === this.netId);
    if (meMember && this.me) {
      el.appendChild(this.partyFrameRow(this.myName || meMember.n || 'YOU', this.me.hp, this.me.max, { leader: !!meMember.leader, pv: !!this.pvpOn, dead: this.me.hp <= 0, self: true }));
    }
    this.party.members.forEach(pm => {
      if (pm.i === this.netId) return;
      const r = this.remotes[pm.i];
      const hp = r && r.ent ? r.ent.hp : 0;
      const max = r && r.ent ? r.ent.max : 100;
      el.appendChild(this.partyFrameRow(pm.n || 'PLAYER', hp, max, { leader: !!pm.leader, pv: !!(r && r.ent && r.ent._pv), dead: !!(r && r.ent && r.ent.hp <= 0), self: false, id: pm.i }));
    });
  }
  stepPartyFrames(dt) {
    if (!this.party) { if (this.pfEl) this.pfEl.style.display = 'none'; return; }
    this._pfT = (this._pfT || 0) + dt;
    if (this._pfT > 0.2) { this._pfT = 0; this.renderPartyFrames(); }
  }

  // ------------------------------------------------------------- pickups""",
    tag='party methods block')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('63_party_client: %d edits applied' % n)
