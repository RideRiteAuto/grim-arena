#!/usr/bin/env python3
"""Patch 64: whispers + friends list (client-only, no relay changes).

Whispers reuse the pre-existing generic directed-send path in relay-worker.js
(the "if (m.to) { ... }" block used since before this session for loot
grants) -- a chat message with m.to set is delivered to exactly that socket,
with m._p stamped as the real sender before the send. That path has been
live in production since before patch 63, so unlike party this needs no
deploy step to work.

Friends persist through the exact same generic save-blob mechanism pvpStats
already uses (see charSave/applySaveBlob): a plain array on the save object,
restored with validation (cap 50, uppercase-normalized, deduped) on load.
Both guests and account holders get this for free through the existing
localStorage-always/cloud-if-linked split in flushSaveAsync, so there is no
separate guest-only code path to build.

Online/offline detection for friends uses rosterNames (the full server-wide
id->name roster fed by the 'roster'/'join'/'left' relay messages), not
this.remotes (which only contains players close enough to have exchanged
position packets) -- a friend across the map is still "online."

Nametag right-click was already deferred to a future patch in 63_party_client.py
(pointer-events:none on r.tag, risk of interfering with click-to-attack); this
patch keeps that scope decision and extends the same player-list button row
pattern with WHISPER / ADD FRIEND / UNFRIEND, plus a standalone FRIENDS
section in the same hold-O panel so a friend who isn't nearby is still
reachable.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 64 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. WHISPERS tab -------------------------------------------------------
sub(
"""  CHAT_TABS() { return [{ key: 'local', label: 'LOCAL' }, { key: 'global', label: 'GLOBAL' }, { key: 'party', label: 'PARTY' }]; }""",
"""  CHAT_TABS() { return [{ key: 'local', label: 'LOCAL' }, { key: 'global', label: 'GLOBAL' }, { key: 'party', label: 'PARTY' }, { key: 'whisper', label: 'WHISPERS' }]; }""",
    tag='CHAT_TABS whisper entry')

# ---- 2. sendChat(): /w, /r, /friend, /unfriend commands + whisper-tab guard
sub(
"""    const inviteM = /^\\/invite\\s+(.+)$/i.exec(text);
    if (inviteM) { this.inviteByName(inviteM[1].trim()); return; }
    const ch = this.chatTab;
    if (ch === 'party' && !this.party) { this.uiNote('NOT IN A PARTY', 'Invite someone, or type /invite NAME, to start one.'); return; }""",
"""    const inviteM = /^\\/invite\\s+(.+)$/i.exec(text);
    if (inviteM) { this.inviteByName(inviteM[1].trim()); return; }
    const whisperM = /^\\/(?:w|whisper|tell|msg)\\s+(\\S+)\\s+([\\s\\S]+)$/i.exec(text);
    if (whisperM) { this.sendWhisper(whisperM[1], whisperM[2]); return; }
    const replyM = /^\\/r\\s+([\\s\\S]+)$/i.exec(text);
    if (replyM) { this.sendWhisperTo(this._lastWhisperFrom, replyM[1]); return; }
    const friendM = /^\\/friend\\s+(.+)$/i.exec(text);
    if (friendM) { this.addFriend(friendM[1].trim()); return; }
    const unfriendM = /^\\/unfriend\\s+(.+)$/i.exec(text);
    if (unfriendM) { this.removeFriend(unfriendM[1].trim()); return; }
    const ch = this.chatTab;
    if (ch === 'party' && !this.party) { this.uiNote('NOT IN A PARTY', 'Invite someone, or type /invite NAME, to start one.'); return; }
    if (ch === 'whisper') { this.uiNote('USE /w NAME MESSAGE', 'Type /w followed by a player name to send a whisper. /r replies to the last one you got.'); return; }""",
    tag='sendChat commands + whisper guard')

# ---- 3. onChatMsg(): route ch:'whisper', track last sender for /r ---------
sub(
"""    const ch = (m.ch === 'global') ? 'global' : (m.ch === 'party') ? 'party' : 'local';
    let pos = null;
    if (Array.isArray(m.p) && m.p.length >= 2) pos = { x: m.p[0], y: 0, z: m.p[1] };
    if (ch === 'local') {
      if (!pos || !this.me) return;
      if (this.me.pos.distanceTo(new this.T.Vector3(pos.x, 0, pos.z)) > this.LOCAL_CHAT_R) return;
    }
    this.buildChatDom();
    this.chatLine(ch, name, text);""",
"""    const ch = (m.ch === 'global') ? 'global' : (m.ch === 'party') ? 'party' : (m.ch === 'whisper') ? 'whisper' : 'local';
    let pos = null;
    if (Array.isArray(m.p) && m.p.length >= 2) pos = { x: m.p[0], y: 0, z: m.p[1] };
    if (ch === 'local') {
      if (!pos || !this.me) return;
      if (this.me.pos.distanceTo(new this.T.Vector3(pos.x, 0, pos.z)) > this.LOCAL_CHAT_R) return;
    }
    this.buildChatDom();
    if (ch === 'whisper') {
      this._lastWhisperFrom = m._p || this._lastWhisperFrom || null;
      this.chatLine('whisper', 'FROM ' + name, text);
      this.uiNote('WHISPER FROM ' + this.escHtml(name), this.escHtml(text), 3200);
      return;
    }
    this.chatLine(ch, name, text);""",
    tag='onChatMsg whisper routing')

# ---- 4. friend-online toast on 'join' --------------------------------------
sub(
"""      case 'join':
        if (!this.rosterNames) this.rosterNames = {};
        this.rosterNames[m.i] = m.n;
        // the old transport pushed existing loot sacks on connect; the relay
        // has no connect hook, so the owner does it when a player announces.
        if (this.isWorldHost && this.sacks) {
          for (const sid in this.sacks) this.netTo(m.i, { t: 'sknew', s: this.sackWire(this.sacks[sid]) });
        }
        return;""",
"""      case 'join':
        if (!this.rosterNames) this.rosterNames = {};
        this.rosterNames[m.i] = m.n;
        if (this.isFriend(m.n)) this.uiNote('FRIEND ONLINE', this.escHtml(m.n) + ' just logged in.', 3200);
        // the old transport pushed existing loot sacks on connect; the relay
        // has no connect hook, so the owner does it when a player announces.
        if (this.isWorldHost && this.sacks) {
          for (const sid in this.sacks) this.netTo(m.i, { t: 'sknew', s: this.sackWire(this.sacks[sid]) });
        }
        return;""",
    tag='join friend toast')

# ---- 5. charSave(): persist friends, same shape as pvpStats ---------------
sub(
"""      unlocks: this.unlocks || {}, at: at, mount: mount,
      pvp: this.pvpStats || { k: 0, d: 0 }
    };
  }""",
"""      unlocks: this.unlocks || {}, at: at, mount: mount,
      pvp: this.pvpStats || { k: 0, d: 0 },
      friends: this.friends || []
    };
  }""",
    tag='charSave friends field')

# ---- 6. applySaveBlob(): restore friends, cap 50 / dedup / normalized -----
sub(
"""      const pvR = raw.pvp || {};
      this.pvpStats = { k: Math.max(0, Math.floor(Number(pvR.k)) || 0), d: Math.max(0, Math.floor(Number(pvR.d)) || 0) };
    } else {
      this.pvpStats = { k: 0, d: 0 };
    }""",
"""      const pvR = raw.pvp || {};
      this.pvpStats = { k: Math.max(0, Math.floor(Number(pvR.k)) || 0), d: Math.max(0, Math.floor(Number(pvR.d)) || 0) };
      const frR = Array.isArray(raw.friends) ? raw.friends : [];
      const frSeen = {};
      this.friends = [];
      for (const f of frR) {
        const fn = String(f || '').trim().toUpperCase().slice(0, 12);
        if (fn && !frSeen[fn] && this.friends.length < 50) { frSeen[fn] = 1; this.friends.push(fn); }
      }
    } else {
      this.pvpStats = { k: 0, d: 0 };
      this.friends = [];
    }""",
    tag='applySaveBlob friends restore')

# ---- 7. whisper send/reply + friend add/remove/lookup methods -------------
# Dropped in right after the existing party methods block, before the pickups
# comment -- same insertion point 63_party_client.py used, kept as one block
# so all social-system methods (party + whisper + friends) sit together.
sub(
"""  onPartyRoster(m) {""",
"""  // ------------------------------------------------------------- whispers
  // Directed chat needs a socket id, not just a name, and a friend or a
  // /w target may not be a nearby entity in this.remotes -- rosterNames is
  // the full server-wide roster (fed by 'roster'/'join'/'left'), so name
  // lookups for whisper and friends both go through it, not this.remotes.
  findIdByName(name) {
    const nl = String(name || '').trim().toUpperCase();
    if (!nl) return null;
    if (this.rosterNames) {
      for (const id in this.rosterNames) { if ((this.rosterNames[id] || '').toUpperCase() === nl) return id; }
    }
    return null;
  }

  sendWhisperTo(id, msg) {
    if (!id) { this.uiNote('NO ONE TO REPLY TO', ''); return; }
    const text = String(msg || '').trim().slice(0, 180);
    if (!text) return;
    if (id === this.netId) { this.uiNote('CANNOT WHISPER YOURSELF', ''); return; }
    const now = performance.now();
    if (now - (this._chatSentAt || 0) < 380) return;   // same throttle sendChat uses
    this._chatSentAt = now;
    const myName = ((this.myName || this.myIdentity().name || 'YOU') + '').toUpperCase().slice(0, 12);
    this.netTo(id, { t: 'chat', ch: 'whisper', msg: text, n: myName });
    this.buildChatDom();
    const toName = (this.rosterNames && this.rosterNames[id]) || 'PLAYER';
    this.chatLine('whisper', 'TO ' + toName, text);
  }

  sendWhisper(name, msg) {
    const id = this.findIdByName(name);
    if (!id) { this.uiNote('PLAYER NOT FOUND', this.escHtml(name) + ' is not online.'); return; }
    this.sendWhisperTo(id, msg);
  }

  openWhisperTo(id, name) {
    this.chatTab = 'whisper';
    this.buildChatDom();
    if (this._chatUnread) this._chatUnread.whisper = false;
    this.renderChatTabs();
    this.renderChatLog();
    this.focusChat();
    if (this.chatInputEl) this.chatInputEl.value = '/w ' + (name || '') + ' ';
  }

  // -------------------------------------------------------------- friends
  // OSRS-style one-directional list: adding or removing is entirely your
  // own call, no request/accept round trip and nothing the other player
  // sees. Persists through the same generic save blob pvpStats already
  // uses (see charSave/applySaveBlob), so it works for guests and account
  // holders alike with no separate storage path.
  isFriend(name) {
    if (!this.friends || !name) return false;
    return this.friends.indexOf(String(name).toUpperCase().slice(0, 12)) !== -1;
  }

  addFriend(name) {
    const nl = String(name || '').trim().toUpperCase().slice(0, 12);
    if (!nl) return;
    if (nl === ((this.myName || '') + '').toUpperCase()) { this.uiNote('CANNOT FRIEND YOURSELF', ''); return; }
    if (!this.friends) this.friends = [];
    if (this.friends.indexOf(nl) === -1) {
      if (this.friends.length >= 50) { this.uiNote('FRIENDS LIST FULL', 'Remove someone before adding more (50 max).'); return; }
      this.friends.push(nl);
      this.flushSaveAsync();
    }
    this.uiNote('FRIEND ADDED', nl, 1800);
    if (this.plListOpen) this.renderPlayerList();
  }

  removeFriend(name) {
    const nl = String(name || '').trim().toUpperCase().slice(0, 12);
    if (!this.friends) return;
    const i = this.friends.indexOf(nl);
    if (i === -1) { this.uiNote('NOT ON YOUR FRIENDS LIST', nl); return; }
    this.friends.splice(i, 1);
    this.flushSaveAsync();
    this.uiNote('FRIEND REMOVED', nl, 1800);
    if (this.plListOpen) this.renderPlayerList();
  }

  onPartyRoster(m) {""",
    tag='whisper + friends methods')

# ---- 8. renderPlayerList(): WHISPER/ADD FRIEND/UNFRIEND buttons + a FRIENDS
# section (friends aren't necessarily nearby, so this reads rosterNames, not
# this.remotes). Extracted from the live file by start/end marker rather than
# hand-transcribed, since the function is a single very long line -- this
# guarantees `old` is byte-exact and lets the assert below catch drift
# instead of silently mismatching on a stray character.
START = "renderPlayerList() { const el = this.plEl;"
END = " updateQuickHealCd() {"
i0 = s.index(START)
i1 = s.index(END, i0)
old_rpl = s[i0:i1]
assert old_rpl.count("const row = (name, right, gold, id, rawName) => {"), \
    'patch 64 [renderPlayerList extract]: row() signature not found, function shape changed'
assert old_rpl.rstrip().endswith('}'), 'patch 64 [renderPlayerList extract]: unexpected trailing text'

new_rpl = """renderPlayerList() { const el = this.plEl; if (!el) return; while (el.firstChild) el.removeChild(el.firstChild); const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; }; el.appendChild(mk('div', 'font-size:11px;letter-spacing:0.2em;color:#7d8a63;margin-bottom:12px;', 'PLAYERS IN GRIM WORLD'));
    // row() takes an explicit button-descriptor array now (instead of
    // deriving one INVITE button from id) so nearby-player rows and the
    // FRIENDS section below, which has no this.remotes entry to key off of,
    // can share the exact same row renderer.
    const row = (name, right, gold, buttons) => {
      const d = mk('div', 'display:flex;align-items:center;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid #26281f;font-size:13px;' + (gold ? 'color:#e8c774;' : ''));
      d.appendChild(mk('span', 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;', name));
      const rightWrap = mk('div', 'display:flex;align-items:center;gap:8px;flex:none;');
      rightWrap.appendChild(mk('span', 'color:#7d8a63;font-size:11px;white-space:nowrap;', right));
      (buttons || []).forEach(bt => {
        const btn = document.createElement('button');
        btn.textContent = bt.label;
        btn.style.cssText = 'pointer-events:auto;cursor:pointer;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:5px;font-size:9px;padding:3px 6px;font-family:inherit;';
        btn.onclick = bt.onclick;
        rightWrap.appendChild(btn);
      });
      d.appendChild(rightWrap);
      return d;
    };
    el.appendChild(row((this.myName || 'YOU') + ' (you)', this.isWorldHost ? 'HOST' : 'ONLINE', true));
    let n = 0;
    for (const id in (this.remotes || {})) {
      const r = this.remotes[id];
      n++;
      const rawName = r.name || 'PLAYER';
      const btns = [];
      if (!(this.party && this.party.members.some(pm => pm.i === id))) btns.push({ label: 'INVITE', onclick: () => this.sendPartyInvite(id, rawName) });
      btns.push({ label: 'WHISPER', onclick: () => this.openWhisperTo(id, rawName) });
      if (this.isFriend(rawName)) btns.push({ label: 'UNFRIEND', onclick: () => this.removeFriend(rawName) });
      else btns.push({ label: 'ADD FRIEND', onclick: () => this.addFriend(rawName) });
      el.appendChild(row((r.s && r.s.pv ? '⚔ ' : '') + rawName, (r.s && r.s.h !== undefined ? r.s.h + ' HP' : 'ONLINE'), false, btns));
    }
    if (!n) el.appendChild(mk('div', 'font-size:11px;color:#5f6b4a;margin-top:10px;letter-spacing:0.08em;', 'NO ONE ELSE ONLINE RIGHT NOW'));
    if (this.friends && this.friends.length) {
      el.appendChild(mk('div', 'font-size:11px;letter-spacing:0.2em;color:#7d8a63;margin-top:14px;margin-bottom:8px;border-top:1px solid #26281f;padding-top:10px;', 'FRIENDS'));
      this.friends.slice().sort().forEach(fn => {
        let onlineId = null;
        for (const rid in (this.rosterNames || {})) { if ((this.rosterNames[rid] || '').toUpperCase() === fn) { onlineId = rid; break; } }
        const isMe = fn === ((this.myName || '') + '').toUpperCase();
        const online = isMe || !!onlineId;
        const btns = [];
        if (onlineId) btns.push({ label: 'WHISPER', onclick: () => this.openWhisperTo(onlineId, fn) });
        btns.push({ label: 'REMOVE', onclick: () => this.removeFriend(fn) });
        el.appendChild(row(fn, online ? 'ONLINE' : 'OFFLINE', online, btns));
      });
    }
    el.appendChild(mk('div', 'font-size:10px;color:#5f6b4a;margin-top:12px;letter-spacing:0.1em;', this.worldStatusText || ''));
  }"""

f = s.count(old_rpl)
assert f == 1, 'patch 64 [renderPlayerList replace]: extracted text found %d times, wanted 1' % f
s = s.replace(old_rpl, new_rpl)
LOG.append((old_rpl, new_rpl))
n += 1

io.open(SRC, 'w', encoding='utf-8').write(s)
print('64_whispers_friends: %d edits applied (1-8)' % n)
