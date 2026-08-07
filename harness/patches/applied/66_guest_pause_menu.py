#!/usr/bin/env python3
"""Patch 66: remove Guest, replace Escape's "back to the title screen" with a
real in-game pause menu.

Two things Kevin flagged:

1. Guest play served no purpose once accounts became mandatory back in the
   "ACCOUNTS" patch notes entry -- LOGIN & PLAY is the only door in now.
   Removed the button, its onclick, the front-door copy that mentioned it,
   and the login-box status line that explained it.

2. Escape called toggleMenuOverlay(), which showed the SAME overlayRef the
   title screen/login box/patch notes live in, just with the message swapped
   to "PAUSED" -- which is why hitting Escape felt like getting dumped back
   at the front door. This adds a separate, minimal pause panel (RESUME /
   SETTINGS / LOGOUT) built the same imperative-DOM way as every other
   window in the game (buildChatDom, buildPartyFramesDom, togglePlayerList),
   and folds it into the existing "pauseOpen" concept via uiWindowOpen() --
   which for free gets it the shared dimmer (uiScrim), the shared
   edge-triggered keys/mouse reset, the shared "no other hotkey fires while
   a window is open" gate, and the shared "don't fight to re-lock the
   pointer while a window is open" retry guard, all already wired to that
   one flag by the existing per-frame loop and requestLock().

   SETTINGS does not duplicate the aim-assist/music/PVP controls -- it
   reparents the REAL nodes (assistRef, musicRef, musicVolRef, pvpRef, and
   whatever updateGfxHud() has appended beside music) out of the title
   screen and into the pause panel the first time it opens. Same refs, same
   onclick handlers, same future updateGfxHud() calls (it looks up its own
   parent via musicRef.current.parentElement, so once music has moved,
   graphics keeps landing next to it automatically). DIFFICULTY stays
   behind on the title screen; it was never one of the three controls Kevin
   asked for and net-mode-only in practice.

   LOGOUT calls the existing doLogout() unchanged -- that is still the only
   path back to the real title screen. plc()'s "pointer lock dropped
   unexpectedly, nothing else open" fallback now opens this same pause menu
   instead of the old overlayRef message, so an accidental unlock (alt-tab,
   the browser's own Escape-unlocks-pointer behaviour) gets the same light
   panel Escape does, not the heavy one.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 66 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. front-door copy: drop the guest mention --------------------------
sub(
    """EVERYONE WHO OPENS THIS LINK LANDS IN THE SAME SHARED WORLD - LOG IN (OR PLAY AS GUEST) AND GO. HOLD <span style="color:#c8a24a;">O</span> IN GAME TO SEE WHO IS ONLINE.""",
    """EVERYONE WHO OPENS THIS LINK LANDS IN THE SAME SHARED WORLD - LOG IN AND GO. HOLD <span style="color:#c8a24a;">O</span> IN GAME TO SEE WHO IS ONLINE.""",
    tag='front door copy')

# ---- 2. remove the PLAY AS GUEST button entirely --------------------------
sub(
    """    const guest = mk('button', 'display:block;margin:7px auto 0;background:transparent;border:none;color:#7d8a63;font-family:IBM Plex Mono,monospace;font-size:9.5px;letter-spacing:0.12em;cursor:pointer;text-decoration:underline;', 'PLAY AS GUEST — SAVED IN THIS BROWSER ONLY');
    guest.onclick = () => { if (!this.started) this.play(); };
    box.appendChild(guest);
""",
    "",
    tag='guest button removed')

# ---- 3. login-box status line: drop the guest explanation -----------------
sub(
    """this._loginStatus = mk('div', 'font-size:9.5px;letter-spacing:0.08em;color:#7d8a63;margin-top:7px;line-height:1.5;', 'NEW NAME + PASSWORD CREATES A CHARACTER. NO LOGIN = GUEST, SAVED IN THIS BROWSER ONLY.');""",
    """this._loginStatus = mk('div', 'font-size:9.5px;letter-spacing:0.08em;color:#7d8a63;margin-top:7px;line-height:1.5;', 'NEW NAME + PASSWORD CREATES A CHARACTER. YOUR PROGRESS SAVES AUTOMATICALLY.');""",
    tag='login status copy')

# ---- 4. toggleMenuOverlay(): target the new pause panel, not overlayRef ---
sub(
    """  toggleMenuOverlay() {
    const o = this.overlayRef.current; if (!o) return;
    const open = o.style.display !== 'none' && o.style.display !== '';
    if (open) { this.showOverlay(false); if (this.started && this.mode === 'ai') this.requestLock(); }
    else { this.showOverlay(true, 'PAUSED — PLAY NOW TO RETURN'); try { document.exitPointerLock(); } catch (e) {} }
  }""",
    """  // Escape used to dump the player straight onto the title screen -- same
  // overlayRef as login/patch notes, just with the message swapped. This is
  // a separate, minimal panel instead: resume, a settings flyout that
  // reparents the real assist/music/pvp controls rather than duplicating
  // them, and logout as the only door back to the actual title screen.
  toggleMenuOverlay() {
    if (this.pauseOpen) this.closePauseMenu(); else this.openPauseMenu();
  }
  openPauseMenu() {
    if (this.pauseOpen) return;
    this.buildPauseDom();
    this.pauseOpen = true;
    this.pauseEl.style.display = 'flex';
    this.syncPvpBtn();
    try { document.exitPointerLock(); } catch (e) {}
  }
  closePauseMenu() {
    if (!this.pauseOpen) return;
    this.pauseOpen = false;
    if (this.pauseEl) this.pauseEl.style.display = 'none';
    if (this._pauseSettingsEl) this._pauseSettingsEl.style.display = 'none';
    if (this._pauseSettingsBtn) this._pauseSettingsBtn.textContent = 'SETTINGS';
    this.uiClosedHandback();
    if (this.started && this.mode === 'ai') this.requestLock();
  }
  buildPauseDom() {
    if (this.pauseEl) return;
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    // No own dimmer -- the shared uiScrim() already draws one for every
    // window the moment pauseOpen makes uiWindowOpen() true.
    const wrap = mk('div', 'position:fixed;inset:0;display:none;align-items:center;justify-content:center;z-index:' + this.Z.window + ';');
    wrap.addEventListener('pointerdown', e => { if (e.target === wrap) this.closePauseMenu(); });
    const panel = mk('div', 'width:360px;max-width:92vw;display:flex;flex-direction:column;gap:12px;padding:20px 22px 16px;' +
      'background:rgba(12,13,9,0.97);border:1px solid #3a3f2c;border-top:2px solid #c8a24a;' +
      'font-family:IBM Plex Mono,monospace;color:#d8d4c6;box-shadow:0 18px 70px rgba(0,0,0,0.78);');
    panel.addEventListener('pointerdown', e => e.stopPropagation());
    const head = mk('div', this.panelHeadCss());
    head.appendChild(mk('div', this.panelTitleCss(), 'PAUSED'));
    head.appendChild(this.panelClose(() => this.closePauseMenu()));
    panel.appendChild(head);

    const resume = mk('button', 'display:block;width:100%;padding:14px 0;background:#c8a24a;border:none;color:#17180f;font-family:"Cinzel",serif;font-weight:700;font-size:16px;letter-spacing:0.14em;cursor:pointer;box-shadow:0 0 0 2px rgba(232,199,116,0.3), 0 6px 24px rgba(200,162,74,0.35);', 'RESUME');
    resume.onclick = () => this.closePauseMenu();
    panel.appendChild(resume);

    const settingsBtn = mk('button', 'display:block;width:100%;padding:11px 0;background:transparent;border:1px solid #8f9a76;color:#c9cdb8;font-family:IBM Plex Mono,monospace;font-size:11px;letter-spacing:0.14em;cursor:pointer;', 'SETTINGS');
    const settingsBody = mk('div', 'display:none;flex-direction:column;gap:9px;padding:12px 2px 2px;border-top:1px solid #2f3426;');
    settingsBtn.onclick = () => {
      const on = settingsBody.style.display === 'none';
      settingsBody.style.display = on ? 'flex' : 'none';
      settingsBtn.textContent = on ? 'SETTINGS ▲' : 'SETTINGS';
    };
    this._pauseSettingsBtn = settingsBtn;
    this._pauseSettingsEl = settingsBody;
    panel.appendChild(settingsBtn);
    panel.appendChild(settingsBody);
    this.movePauseSettingsControlsIn(settingsBody, mk);

    const logout = mk('button', 'display:block;width:100%;margin-top:2px;padding:11px 0;background:transparent;border:1px solid #6b4a3f;color:#c07a68;font-family:IBM Plex Mono,monospace;font-size:11px;letter-spacing:0.16em;cursor:pointer;', 'LOG OUT');
    logout.onclick = () => { logout.textContent = 'SAVING…'; this.doLogout(); };
    panel.appendChild(logout);

    panel.appendChild(mk('div', this.panelLegendCss(), 'ESC, CLICK OUTSIDE, OR × — RESUME'));
    wrap.appendChild(panel);
    document.body.appendChild(wrap);
    this.pauseEl = wrap;
  }
  // The title-screen settings row (aim assist, music + volume, PVP, and
  // whatever updateGfxHud() appends beside music) already works end to
  // end -- reparenting the real nodes into the pause panel keeps every
  // handler, and every future updateGfxHud() call, wired exactly as it
  // already was instead of rebuilding the same four controls a second time.
  // The volume slider's own listener is a plain addEventListener bound in
  // updateMusicHud(), so it survives the move for free. AIM ASSIST, MUSIC
  // and PVP are React-bound (sc-camel-on-click) to the title screen's own
  // render root, and React's delegated click listener does not follow a
  // node once it is moved outside that root's subtree (confirmed: the
  // button still looks clickable but the handler silently stops firing) --
  // so those three get a plain native listener onto the same real method
  // the React prop already called, once, right here.
  movePauseSettingsControlsIn(host, mk) {
    const row1 = mk('div', 'display:flex;flex-wrap:wrap;gap:8px;align-items:center;');
    const row2 = mk('div', 'display:flex;flex-wrap:wrap;gap:8px;align-items:center;');
    host.appendChild(row1); host.appendChild(row2);
    const put = (ref, row) => { if (ref && ref.current) row.appendChild(ref.current); };
    put(this.assistRef, row1);
    put(this.musicRef, row1);
    put(this.musicVolRef, row1);
    if (this._gfxBtn) row1.appendChild(this._gfxBtn);
    put(this.pvpRef, row2);
    if (this.assistRef && this.assistRef.current) this.assistRef.current.addEventListener('click', () => this.toggleAssist());
    if (this.musicRef && this.musicRef.current) this.musicRef.current.addEventListener('click', () => this.toggleMusic());
    if (this.pvpRef && this.pvpRef.current) this.pvpRef.current.addEventListener('click', () => this.togglePvp());
  }""",
    tag='pause menu methods')

# ---- 5. closeTopWindow(): clicking the shared scrim also resumes ----------
sub(
    """  closeTopWindow() {
    if (this.anvOpen) return this.closeAnvil();""",
    """  closeTopWindow() {
    if (this.pauseOpen) return this.closePauseMenu();
    if (this.anvOpen) return this.closeAnvil();""",
    tag='closeTopWindow pause branch')

# ---- 6. uiWindowOpen(): pause now shares the dimmer/gate/relock plumbing --
sub(
    """  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen || this.furnOpen || this.anvOpen); }""",
    """  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen || this.furnOpen || this.anvOpen || this.pauseOpen); }""",
    tag='uiWindowOpen includes pauseOpen')

# ---- 7. plc() fallback: accidental unlock opens the pause panel, not the
#         old title-screen message -----------------------------------------
sub(
    """      if (this.started && !this.freeAim) this.showOverlay(true, 'PAUSED — CLICK ANYWHERE TO RESUME');""",
    """      if (this.started && !this.freeAim) this.openPauseMenu();""",
    tag='plc fallback opens pause menu')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('66_guest_pause_menu: %d edits applied (1-7)' % n)
