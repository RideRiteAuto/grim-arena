#!/usr/bin/env python3
"""Patch 67: the social panel (hold-O player list) becomes a real toggleable
window, and party frames stop going dead the moment any window is open.

Two things Kevin flagged:

1. O had to be held down to see the roster, and none of its buttons
   (INVITE, WHISPER, ADD FRIEND) could actually be clicked, because holding
   O never released the mouse -- you were still in pointer lock, aiming the
   camera, with no real cursor to click anything with. O now toggles the
   panel like every other window (press once to open, again -- or Escape,
   or the new close button -- to shut it), and it joins the same
   uiWindowOpen() union pauseOpen already uses, so it gets the same
   shared dimmer, the same released cursor, and the same hotkey gate for
   free. Chrome (title row, close button, footer legend) now matches every
   other panel in the game instead of being a bare unstyled div.

   The O toggle itself lives at the very top of the keydown handler, same
   spot M already uses for the map -- both release the mouse, so both have
   to work whether or not the cursor is currently locked, and whether or
   not something else happens to already be open.

2. KICK and LEAVE on the party frames looked clickable but were not,
   whenever ANY window was open (bank, pack, the new social panel, all of
   them). Root cause: the shared scrim that dims the screen behind a window
   sits at Z.scrim (99), and the party frames were drawn at Z.hint (10) --
   so the dimmer's own full-screen click-catcher was stacked IN FRONT of
   the party frames the whole time a window was up, swallowing every click
   before it reached KICK or LEAVE. Moving party frames to Z.bar (100),
   the same tier the action bar already uses (above the dimmer, below an
   actual window), puts them back on top of the scrim so clicks land where
   they look like they should land.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 67 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. O toggle lives at the top of kd(), same spot as M -----------------
sub(
    """      if (e.code === 'KeyK' && this.started && this.mode === 'ai' && !this.walletOpen && !this.bankOpen) { this.toggleSkills(); return; }
      if (this.bankOpen && e.code === 'Escape') { this.closeBank(); return; }""",
    """      if (e.code === 'KeyK' && this.started && this.mode === 'ai' && !this.walletOpen && !this.bankOpen) { this.toggleSkills(); return; }
      // The roster releases the mouse too, same as the map -- so its toggle
      // lives up here like M/K/Escape, and works whether or not the cursor
      // is locked, or another window happens to already be open.
      if (e.code === 'KeyO' && !e.repeat && this.started && this.mode === 'ai') { this.togglePlayerList(); return; }
      if (this.bankOpen && e.code === 'Escape') { this.closeBank(); return; }""",
    tag='KeyO toggle lives with M')

# ---- 2. Escape closes the roster before falling through to the pause menu -
sub(
    """      if (e.code === 'Escape') {
        if (this._skOpen) { this.toggleSkills(); return; }
        if (this._wmOpen) { this.closeWorldMap(); return; }
        if (this.shopOpen) { this.closeShop(); return; }
        if (this.sackWinId) { this.closeSackWin(); return; }
        if (this.started && this.mode === 'ai') { this.toggleMenuOverlay(); return; }
      }""",
    """      if (e.code === 'Escape') {
        if (this._skOpen) { this.toggleSkills(); return; }
        if (this._wmOpen) { this.closeWorldMap(); return; }
        if (this.shopOpen) { this.closeShop(); return; }
        if (this.sackWinId) { this.closeSackWin(); return; }
        if (this.plListOpen) { this.togglePlayerList(false); return; }
        if (this.started && this.mode === 'ai') { this.toggleMenuOverlay(); return; }
      }""",
    tag='Escape closes roster')

# ---- 3. drop the old hold-to-show keydown/keyup wiring --------------------
sub(
    """      if (k === 'dodge') this.tryDodge(); if (k === 'jump') this.tryJump(); if (k === 'wheel') this.openSpellWheel(); if (k === 'plist') this.togglePlayerList(true);""",
    """      if (k === 'dodge') this.tryDodge(); if (k === 'jump') this.tryJump(); if (k === 'wheel') this.openSpellWheel();""",
    tag='drop keydown hold-open')
sub(
    """    const ku = e => { const k = norm(e); if (!k) return; this.keys[k] = false; if (k === 'wheel') this.closeSpellWheel(); if (k === 'plist') this.togglePlayerList(false); };""",
    """    const ku = e => { const k = norm(e); if (!k) return; this.keys[k] = false; if (k === 'wheel') this.closeSpellWheel(); };""",
    tag='drop keyup hold-close')

# ---- 4. plListOpen joins the shared window union --------------------------
sub(
    """  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen || this.furnOpen || this.anvOpen || this.pauseOpen); }""",
    """  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen || this.furnOpen || this.anvOpen || this.pauseOpen || this.plListOpen); }""",
    tag='plListOpen joins uiWindowOpen')

# ---- 5. clicking the shared scrim also closes the roster ------------------
sub(
    """  closeTopWindow() {
    if (this.pauseOpen) return this.closePauseMenu();
    if (this.anvOpen) return this.closeAnvil();
    if (this.furnOpen) return this.closeFurnace();
    if (this.shopOpen) return this.closeShop();
    if (this._wmOpen) return this.closeWorldMap();
    if (this._skOpen) return this.toggleSkills();
    if (this.bankOpen) return this.closeBank();
    if (this.sackWinId) return this.closeSackWin();
    if (this.walletOpen) return this.toggleWallet();
  }""",
    """  closeTopWindow() {
    if (this.pauseOpen) return this.closePauseMenu();
    if (this.anvOpen) return this.closeAnvil();
    if (this.furnOpen) return this.closeFurnace();
    if (this.shopOpen) return this.closeShop();
    if (this._wmOpen) return this.closeWorldMap();
    if (this._skOpen) return this.toggleSkills();
    if (this.bankOpen) return this.closeBank();
    if (this.sackWinId) return this.closeSackWin();
    if (this.walletOpen) return this.toggleWallet();
    if (this.plListOpen) return this.togglePlayerList(false);
  }""",
    tag='closeTopWindow roster branch')

# ---- 6. party frames move above the scrim, not just under the hints -------
sub(
    """  buildPartyFramesDom() {
    if (this.pfEl) return;
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;width:230px;display:none;flex-direction:column;gap:4px;z-index:' + this.Z.hint + ';';
    document.body.appendChild(d);
    this.pfEl = d;
  }""",
    """  // Z.hint (10) used to sit UNDER the shared scrim (99) -- which meant KICK
  // and LEAVE went dead the moment any window was open, since the dimmer's
  // own click-catcher was stacked in front of them. Z.bar (100) is the same
  // tier the action bar already uses: above the dimmer, still under an
  // actual window, so party frames stay lit and clickable no matter what
  // else you have open.
  buildPartyFramesDom() {
    if (this.pfEl) return;
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;width:230px;display:none;flex-direction:column;gap:4px;z-index:' + this.Z.bar + ';';
    document.body.appendChild(d);
    this.pfEl = d;
  }""",
    tag='party frames above scrim')

# ---- 7. the roster itself: real toggle, real chrome, real close button ----
sub(
    """togglePlayerList(show) { if (!this.plEl) { const d = document.createElement('div'); d.style.cssText = 'position:fixed;top:calc(50% - 40px);left:50%;transform:translate(-50%,-50%);min-width:300px;padding:18px 22px;background:rgba(12,13,9,0.97);border:1px solid #3a3f2c;border-top:2px solid #c8a24a;font-family:IBM Plex Mono,monospace;color:#d8d4c6;z-index:' + this.Z.window + ';display:none;pointer-events:none;box-shadow:0 18px 70px rgba(0,0,0,0.78);'; document.body.appendChild(d); this.plEl = d; } this.plEl.style.display = show ? 'block' : 'none'; this.plListOpen = !!show; if (show) this.renderPlayerList(); } renderPlayerList() { const el = this.plEl; if (!el) return; while (el.firstChild) el.removeChild(el.firstChild); const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; }; el.appendChild(mk('div', 'font-size:11px;letter-spacing:0.2em;color:#7d8a63;margin-bottom:12px;', 'PLAYERS IN GRIM WORLD'));
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
  }""",
    """togglePlayerList(show) {
    if (!this.plEl) this.buildPlayerListDom();
    const want = show === undefined ? !this.plListOpen : !!show;
    if (want === this.plListOpen) return;
    this.plListOpen = want;
    this.plEl.style.display = want ? 'flex' : 'none';
    if (want) { this.renderPlayerList(); try { document.exitPointerLock(); } catch (e) {} }
    else { this.uiClosedHandback(); if (this.started && this.mode === 'ai') this.requestLock(); }
  }
  // Same imperative-DOM chrome as every other window -- title and close on a
  // sticky header, a legend footer, no own dimmer since the shared uiScrim()
  // draws one automatically the moment plListOpen joins uiWindowOpen(). Built
  // once; renderPlayerList only ever touches the body below the header, so
  // the roster can redraw every 250ms without rebuilding its own chrome.
  buildPlayerListDom() {
    if (this.plEl) return;
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    const wrap = mk('div', this.panelCss('340px'));
    const head = mk('div', this.panelHeadCss());
    head.appendChild(mk('div', this.panelTitleCss(), 'PLAYERS IN GRIM WORLD'));
    head.appendChild(this.panelClose(() => this.togglePlayerList(false)));
    wrap.appendChild(head);
    const body = mk('div', 'display:flex;flex-direction:column;');
    wrap.appendChild(body);
    wrap.appendChild(mk('div', this.panelLegendCss(), 'O, ESC, OR × TO CLOSE'));
    document.body.appendChild(wrap);
    this.plEl = wrap;
    this._plBody = body;
  }
  renderPlayerList() {
    const el = this._plBody;
    if (!el) return;
    while (el.firstChild) el.removeChild(el.firstChild);
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
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
  }""",
    tag='roster toggle + chrome')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('67_social_toggle_clickthrough: %d edits applied (1-7)' % n)
