#!/usr/bin/env python3
"""Patch 62: chat transport + UI shell (LOCAL / GLOBAL).

Kevin: a WoW/OSRS-style multi-tab chat box, bottom-left, local chat for the
area around you and global chat for everyone. Per the reviewed plan
(claude/CHAT-PARTY-FRIENDS-PLAN.md): non-modal (does not join uiWindowOpen,
never pauses or dims the world), Local is proximity-filtered client-side at
45m, and local messages ride the patch-61 speech-bubble system so they float
over the sender's head - the same mechanism NPC catchphrases now use.

Transport needed ZERO worker changes: relay-worker.js already allowlists a
'chat' message type that nothing sent (see RELAYED in relay-worker.js). This
patch is the sender and the handler for it. netAll()/netTo() (used by PvP
already) are the existing broadcast/directed helpers - no new network
primitive invented here either.

Party (patch 63) and whispers/friends (patch 64) extend this same shell:
CHAT_TABS() is written as a table specifically so those patches can append a
tab without rewriting the tab bar.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 62 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. chat methods, appended right after patch 61's bubble/chatter block
sub(
"""R) this.sfx('tick');
      }
    }
  }

  // ------------------------------------------------------------- pickups""",
"""R) this.sfx('tick');
      }
    }
  }

  // --------------------------------------------------------------- chat
  // Table-driven so patches 63 (party) and 64 (whispers) can each append one
  // tab without touching the bar-building code.
  LOCAL_CHAT_R = 45;
  CHAT_TABS() { return [{ key: 'local', label: 'LOCAL' }, { key: 'global', label: 'GLOBAL' }]; }

  buildChatDom() {
    if (this.chatEl) return;
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    const wrap = mk('div', 'position:fixed;left:14px;bottom:14px;width:380px;max-width:44vw;display:flex;flex-direction:column;' +
      'background:rgba(12,13,9,0.9);border:1px solid #3a3f2c;border-top:2px solid #c8a24a;font-family:IBM Plex Mono,monospace;' +
      'z-index:' + this.Z.bar + ';box-shadow:0 10px 34px rgba(0,0,0,0.55);');
    const tabs = mk('div', 'display:flex;gap:4px;padding:6px 6px 0;');
    wrap.appendChild(tabs);
    const log = mk('div', 'height:150px;overflow-y:auto;padding:6px 10px;font-size:12px;line-height:1.5;color:#d8d4c6;');
    wrap.appendChild(log);
    const inputRow = mk('div', 'padding:6px;border-top:1px solid #2f3426;');
    const input = document.createElement('input');
    input.placeholder = 'PRESS ENTER TO CHAT';
    input.maxLength = 180;
    input.autocomplete = 'off';
    input.style.cssText = 'width:100%;box-sizing:border-box;background:#15170f;border:1px solid #3a3f2c;color:#d8d4c6;' +
      'padding:7px 9px;font-family:inherit;font-size:12px;letter-spacing:0.02em;outline:none;';
    input.addEventListener('focus', () => { input.style.borderColor = '#c8a24a'; });
    input.addEventListener('blur', () => { input.style.borderColor = '#3a3f2c'; });
    // Enter sends and re-focuses (fire off several lines fast); Escape's blur
    // is already handled up in bindInput's global text-box guard.
    input.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); this.sendChat(); } });
    inputRow.appendChild(input);
    wrap.appendChild(inputRow);
    document.body.appendChild(wrap);
    this.chatEl = wrap; this.chatTabsEl = tabs; this.chatLogEl = log; this.chatInputEl = input;
    this.chatTab = 'local';
    this.chatLines = {};
    this.CHAT_TABS().forEach(t => { this.chatLines[t.key] = []; });
    this.renderChatTabs();
    this.renderChatLog();
  }
  renderChatTabs() {
    if (!this.chatTabsEl) return;
    while (this.chatTabsEl.firstChild) this.chatTabsEl.removeChild(this.chatTabsEl.firstChild);
    this.CHAT_TABS().forEach(t => {
      const on = t.key === this.chatTab;
      const b = document.createElement('button');
      b.textContent = t.label + (!on && this._chatUnread && this._chatUnread[t.key] ? ' *' : '');
      b.style.cssText = 'flex:1;background:' + (on ? '#c8a24a' : '#1c1e15') + ';color:' + (on ? '#17180f' : '#7d8a63') +
        ';border:1px solid #3a3f2c;padding:5px 0;font-size:10.5px;letter-spacing:0.1em;font-weight:700;font-family:inherit;cursor:pointer;';
      b.onclick = () => { this.chatTab = t.key; if (this._chatUnread) this._chatUnread[t.key] = false; this.renderChatTabs(); this.renderChatLog(); };
      this.chatTabsEl.appendChild(b);
    });
  }
  renderChatLog() {
    if (!this.chatLogEl) return;
    while (this.chatLogEl.firstChild) this.chatLogEl.removeChild(this.chatLogEl.firstChild);
    const lines = this.chatLines[this.chatTab] || [];
    for (const l of lines) this.chatLogEl.appendChild(this.chatRowEl(l));
    this.chatLogEl.scrollTop = this.chatLogEl.scrollHeight;
  }
  chatRowEl(l) {
    const row = document.createElement('div');
    row.style.cssText = 'margin:2px 0;word-break:break-word;';
    const tag = document.createElement('span');
    tag.style.cssText = 'color:#7d8a63;';
    tag.textContent = '[' + l.ch.toUpperCase() + '] ';
    const name = document.createElement('span');
    name.style.cssText = 'color:#e8c774;font-weight:700;';
    name.textContent = l.name + ': ';
    const body = document.createElement('span');
    body.textContent = l.text;
    row.appendChild(tag); row.appendChild(name); row.appendChild(body);
    return row;
  }
  // Buffers 100 lines per channel (no server-side history - a new joiner
  // gets nothing older than what they were online for, same as every other
  // relay-held state). Renders immediately if the tab is active, else marks
  // an unread dot on the tab button.
  chatLine(ch, name, text) {
    if (!this.chatLines) return;
    const arr = this.chatLines[ch] || (this.chatLines[ch] = []);
    arr.push({ ch: ch, name: name, text: text });
    if (arr.length > 100) arr.shift();
    if (ch === this.chatTab) { if (this.chatLogEl) { this.chatLogEl.appendChild(this.chatRowEl(arr[arr.length - 1])); this.chatLogEl.scrollTop = this.chatLogEl.scrollHeight; } }
    else { (this._chatUnread = this._chatUnread || {})[ch] = true; this.renderChatTabs(); }
  }
  focusChat() {
    this.buildChatDom();
    if (this.chatInputEl) this.chatInputEl.focus();
  }
  sendChat() {
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
  }
  // Never trusts the relay itself for anything but delivery: length, channel
  // and (for Local) distance are all re-checked here exactly like every
  // other inbound packet in this game validates rather than assumes.
  onChatMsg(m) {
    if (!m || typeof m.msg !== 'string') return;
    const text = String(m.msg).slice(0, 180).trim();
    if (!text) return;
    const name = String(m.n || 'PLAYER').toUpperCase().slice(0, 12);
    const ch = (m.ch === 'global') ? 'global' : 'local';
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
    }
  }

  // ------------------------------------------------------------- pickups""",
    tag='chat methods block')

# ---- 2. build the chat HUD as soon as you're in the shared world ---------
sub("    this.joinSharedWorld();\n    this.fit();",
    "    this.joinSharedWorld();\n    this.buildChatDom();\n    this.fit();",
    tag='play() builds chat')

# ---- 3. route the relay's default-cased 'chat' messages -------------------
sub("onWorldData(from, m) { if (!m || !m.t) return;",
    "onWorldData(from, m) { if (!m || !m.t) return; if (m.t === 'chat') { this.onChatMsg(m); return; }",
    tag='onWorldData chat route')

# ---- 4. hide chat behind the pause overlay, restore it on close ----------
sub("""    o.style.display = on ? 'flex' : 'none';
    if (on) {
      if (this.promptRef && this.promptRef.current) this.promptRef.current.style.display = 'none';
      this.hideBanner();
      this.hideBubbles();
    }""",
    """    o.style.display = on ? 'flex' : 'none';
    if (on) {
      if (this.promptRef && this.promptRef.current) this.promptRef.current.style.display = 'none';
      this.hideBanner();
      this.hideBubbles();
      if (this.chatEl) this.chatEl.style.display = 'none';
    } else if (this.chatEl && this.started) this.chatEl.style.display = 'flex';""",
    tag='showOverlay chat hide/restore')

# ---- 5. Enter opens/focuses chat (a no-op key everywhere except the old
#         pre-duel warmup ready-check, which still wins first) -------------
sub(
"""      const tgt = e.target;
      if (tgt && (tgt.tagName === 'INPUT' || tgt.tagName === 'TEXTAREA' || tgt.isContentEditable)) {
        if (e.code === 'Escape') { tgt.blur(); this.closeTopWindow(); }
        return;
      }""",
"""      const tgt = e.target;
      if (tgt && (tgt.tagName === 'INPUT' || tgt.tagName === 'TEXTAREA' || tgt.isContentEditable)) {
        if (e.code === 'Escape') { tgt.blur(); this.closeTopWindow(); }
        return;
      }
      if ((e.code === 'Enter' || e.code === 'NumpadEnter') && !this.warmup && this.started && this.mode === 'ai') {
        e.preventDefault(); this.focusChat(); return;
      }""",
    tag='enter opens chat')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('62_chat: %d edits applied' % n)
