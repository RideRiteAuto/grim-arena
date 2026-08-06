#!/usr/bin/env python3
"""UI pass one. Edits /tmp/game-src.html in place.

Six jobs, in the order they matter:

  1. The world no longer freezes behind a panel. active() went false the moment
     a panel released the pointer lock, so tick() took the frozen branch and
     stepWorld never ran: NPCs stopped, quests stopped, the whole world held
     its breath while you sorted your pack. active() now stays true while a
     window is open and the KEYBOARD is gated instead.
  2. FPS joins the coord readout, and the readout moves to a fixed layer above
     the dimmer so a screenshot always carries both.
  3. The duel-era round frame (FREE ROAM + the win pips) stops drawing in the
     open world, which also stops it colliding with the compass ribbon.
  4. One z-index ladder. The action bar no longer covers the pack, the bank or
     the skills page, and the panels no longer reach down into the bar.
  5. One dimmer behind every window, the treatment the world map already had.
  6. One panel chrome: same border, same fill, same font, same header and
     footer. Every window now says what its controls do.

Every anchor is an exact string and asserted to match exactly once, so this
replays onto whatever the other track last pushed or fails loudly.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n_edits = 0


def sub(old, new, count=1, tag=''):
    global s, n_edits
    found = s.count(old)
    assert found == count, 'anchor matched %d times (wanted %d): %s | %s' % (
        found, count, tag, old[:110].replace('\n', ' / '))
    s = s.replace(old, new)
    n_edits += 1


# ===================================================================== 1. SIM
# active() is what tick() asks before it runs the world. It used to require the
# pointer lock, which every panel releases on purpose, so opening the pack was
# indistinguishable from pausing. uiWindowOpen() joins the test.
sub(
    "  active() { return this.started && !this.contextLost && (this.locked || this.freeAim); }",
    "  active() { return this.started && !this.contextLost && (this.locked || this.freeAim || this.uiWindowOpen()); }",
    tag='active')

# Now that the world keeps running, the keyboard is what has to be held back:
# otherwise WASD walks you around while you drag items. One gate, and F still
# closes whatever window is in front of you.
sub(
    """      const k = norm(e); if (!k) return;
      if (!this.active()) return;
      e.preventDefault();""",
    """      const k = norm(e); if (!k) return;
      // A panel owns the keyboard. The WORLD keeps simulating behind it - the
      // sim is gated on active(), which no longer goes false just because the
      // cursor was released - so this gate is the only thing stopping WASD
      // from walking you around while you sort the pack. F still closes the
      // window in front of you, which is what F already promised in the prompt.
      if (this.uiWindowOpen()) {
        if (k === '3') { e.preventDefault(); const pick = this.bestInteract(); if (pick) pick.run(); }
        return;
      }
      if (!this.active()) return;
      e.preventDefault();""",
    tag='kd gate')

# Escape closed the pack, the bank, the map and the sack but not the trader,
# where it opened the pause menu on top of the shop instead.
sub(
    "        if (this.sackWinId) { this.closeSackWin(); return; }",
    "        if (this.shopOpen) { this.closeShop(); return; }\n"
    "        if (this.sackWinId) { this.closeSackWin(); return; }",
    tag='esc shop')

# Drop anything held on the frame a window opens, and raise the dimmer.
sub(
    """    if (this.hitstop > 0) { this.hitstop -= dt; dt *= 0.09; }
    const me = this.me, foe = this.foe;
""",
    """    if (this.hitstop > 0) { this.hitstop -= dt; dt *= 0.09; }
    const me = this.me, foe = this.foe;
    // Edge-triggered, not per-frame: on the frame a window opens, let go of
    // whatever was held down so a key pressed before the panel appeared does
    // not stick once it closes. Also raises and drops the shared dimmer.
    const uiOn = this.uiWindowOpen();
    if (uiOn !== this._uiHold) {
      this._uiHold = uiOn;
      if (uiOn) { this.keys = {}; this.mouse.l = false; this.mouse.r = false; if (me) me.blocking = false; }
      this.uiScrim(uiOn);
    }
""",
    tag='tick ui hold')


# ================================================================== 2. FPS HUD
# The coord stamp is a keeper - it is what makes a screenshot a repro case - so
# it gains a frame-rate reading and moves onto a fixed layer above the dimmer,
# where a panel can never hide it mid-screenshot.
sub(
    """      const cd = document.createElement('div');
      cd.style.cssText = 'position:absolute;left:14px;bottom:46px;padding:5px 10px;' +
        'background:rgba(10,11,8,0.62);border:1px solid #3a3f2c;color:#7d8a63;' +
        'font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:0.10em;' +
        'z-index:5;pointer-events:none;white-space:pre;';
      mount.appendChild(cd); this._coordHud = cd;""",
    """      const cd = document.createElement('div');
      cd.style.cssText = 'position:fixed;left:12px;bottom:12px;padding:6px 11px;' +
        'background:rgba(10,11,8,0.8);border:1px solid #3a3f2c;color:#7d8a63;' +
        'font-family:IBM Plex Mono,monospace;font-size:10px;letter-spacing:0.10em;' +
        'z-index:' + this.Z.debug + ';pointer-events:none;white-space:pre;';
      document.body.appendChild(cd); this._coordHud = cd;""",
    tag='coord hud el')

sub(
    """        this._coordHud.textContent =
          'X ' + f(m.x, 1) + '   Z ' + f(m.z, 1) + '   Y ' + f(gy + m.y, 1) +
          '   YAW ' + f(this.yaw, 3) + '   PITCH ' + f(this.pitch, 2) +
          (zn ? ('   ' + zn) : '');""",
    """        // Frame rate rides in the same box, so one glance off a screenshot
        // gives both the camera numbers and whether the shot was taken on a
        // good frame. Colour uses the SAME thresholds stepPerf uses to decide
        // whether to drop the graphics, so amber means "close to the edge" and
        // red means "the game is about to protect itself".
        const ftms = (this._ftAvg || 0) * 1000;
        const fps = ftms > 0 ? Math.round(1000 / ftms) : 0;
        const fcol = ftms <= 0 ? '#7d8a63' : ftms < 17 ? '#8fe36a' : ftms < 27 ? '#f3dc00' : '#e0574f';
        this._coordHud.innerHTML =
          '<span style="color:' + fcol + ';font-weight:700">' + fps + ' FPS  ' + ftms.toFixed(1) + ' ms</span>   ' +
          'X ' + f(m.x, 1) + '   Z ' + f(m.z, 1) + '   Y ' + f(gy + m.y, 1) +
          '   YAW ' + f(this.yaw, 3) + '   PITCH ' + f(this.pitch, 2) +
          (zn ? ('   ' + zn) : '');""",
    tag='coord hud text')

# F3 readout moves up so it stacks with the coord box instead of sitting on it,
# and onto the same always-visible layer.
sub(
    """      d.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:40;background:rgba(26,26,26,.86);' +
        'border:1px solid #383838;border-radius:8px;padding:8px 11px;font:11px/1.5 ui-monospace,Menlo,Consolas,monospace;' +
        'color:#ededed;white-space:pre;pointer-events:none;letter-spacing:.02em';""",
    """      d.style.cssText = 'position:fixed;left:12px;bottom:46px;z-index:' + this.Z.debug + ';background:rgba(10,11,8,0.8);' +
        'border:1px solid #3a3f2c;padding:8px 11px;font:11px/1.5 IBM Plex Mono,ui-monospace,Menlo,monospace;' +
        'color:#d8d4c6;white-space:pre;pointer-events:none;letter-spacing:.02em';""",
    tag='perf hud el')


# ============================================================ 3. DUEL FURNITURE
# ROUND / FREE ROAM and the four win pips are duel furniture. There is no round
# to win in the open world, and the block sat directly under the compass ribbon.
# The elements stay in the DOM: stepMap's HUD blackout reaches the header row
# through roundRef.parentElement.parentElement, and duel mode still needs them.
sub(
    "  paintWins() {",
    """  // The round counter and the win pips only mean something in a duel. In the
  // open world they read FREE ROAM over four empty diamonds and fought the
  // compass ribbon for the same 200 pixels. Collapse the centre column down to
  // the connection line, and leave duel mode exactly as it was.
  syncDuelHud() {
    const duel = this.mode === 'net';
    const r = this.roundRef && this.roundRef.current;
    if (r) { r.style.display = duel ? 'block' : 'none'; if (!duel && r.textContent) r.textContent = ''; }
    const p1 = this.myWin1Ref && this.myWin1Ref.current;
    const pipRow = p1 && p1.parentElement && p1.parentElement.parentElement;
    if (pipRow) pipRow.style.display = duel ? 'flex' : 'none';
    const nt = this.netRef && this.netRef.current;
    if (nt) nt.style.marginTop = duel ? '10px' : '0';
  }
  paintWins() {""",
    tag='syncDuelHud')

sub(
    "      this.roundRef.current.textContent = this.mode === 'net' ? 'ROUND ' + this.round : 'FREE ROAM';",
    "      this.roundRef.current.textContent = this.mode === 'net' ? 'ROUND ' + this.round : '';\n"
    "      this.syncDuelHud();",
    tag='resetRound text')

sub(
    "    if (this.roundRef.current) this.roundRef.current.textContent = 'FREE ROAM';",
    "    this.syncDuelHud();",
    tag='resetWorldSpawn text')

# Entering the world is the one moment guaranteed to happen, so pin it there too.
sub(
    "      if (this._homeHint) this._homeHint.style.display = hudHide ? 'none' : 'block';",
    "      if (this._homeHint) this._homeHint.style.display = hudHide ? 'none' : 'block';\n"
    "      this.syncDuelHud();",
    tag='stepMap syncDuelHud')


# =============================================== 4/5. Z LADDER, DIMMER, CHROME
# One ladder and one panel chrome, both declared once so the next panel added
# inherits them instead of picking new numbers. Inserted ahead of uiWindowOpen,
# which is the method every one of them is keyed off.
sub(
    "  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen); }",
    """  // ------------------------------------------------------------ UI system
  // ONE ladder. Before this there were sixteen hand-picked z-index values with
  // no scale behind them, which is how the action bar (75) ended up drawing
  // over the pack (70), the sack (71), the bank and the skills page (72).
  // Anything added later picks a rung here rather than a new number.
  Z = {
    tag: 4,        // world-anchored nametags
    hint: 10,      // interact prompt, ride HUD, home hint, boat hint
    compass: 12,
    scrim: 99,     // the dimmer behind every window
    bar: 100,      // action bar: over the dimmer, under the windows
    window: 101,   // pack, bank, skills, shop, sack, map, spell wheel
    debug: 200,    // coord + FPS stamp and the F3 readout, always readable
    toast: 210,    // loot pickups
    pop: 900,      // tooltips, context menus, split picker, in-panel notes
    drag: 950,     // the thing under the cursor is always on top
    banner: 1000
  };

  // ONE panel chrome. Same fill, same border, same gold top rule, same font.
  // Pass a width; everything else is fixed so two windows can never disagree.
  // The height cap and the upward nudge keep every window clear of the action
  // bar at the bottom of the screen, which is what made the bar look like it
  // was covering things: it was, because the panels reached into it.
  panelCss(width) {
    return 'position:fixed;left:50%;top:calc(50% - 40px);transform:translate(-50%,-50%);display:none;' +
      'flex-direction:column;gap:10px;width:' + width + ';max-width:96vw;' +
      'max-height:calc(100vh - 190px);overflow-y:auto;padding:15px 18px 14px;' +
      'background:rgba(12,13,9,0.97);border:1px solid #3a3f2c;border-top:2px solid #c8a24a;' +
      'font-family:IBM Plex Mono,monospace;color:#d8d4c6;z-index:' + this.Z.window + ';' +
      'box-shadow:0 18px 70px rgba(0,0,0,0.78);';
  }
  // Header rule and footer legend, so the reading order is identical in every
  // window: title on the left, tools on the right, close last, controls along
  // the bottom. The legend is not decoration - it is why the panels are usable
  // without a manual, so every window gets one.
  panelHeadCss() { return 'display:flex;align-items:center;gap:10px;border-bottom:1px solid #2f3426;padding-bottom:9px;flex-wrap:wrap;'; }
  panelTitleCss() { return 'font-family:Cinzel,serif;font-size:15px;letter-spacing:0.2em;color:#e8c774;flex:1;min-width:150px;'; }
  panelLegendCss() { return 'border-top:1px solid #2f3426;padding-top:8px;margin-top:2px;font-size:9.5px;line-height:1.75;color:#7d8a63;letter-spacing:0.05em;'; }
  panelBtnCss(gold) {
    return 'padding:7px 13px;background:' + (gold ? '#c8a24a' : 'transparent') + ';border:1px solid #c8a24a;' +
      'color:' + (gold ? '#17180f' : '#e8c774') + ';font-family:IBM Plex Mono,monospace;font-size:10px;' +
      'letter-spacing:0.12em;cursor:pointer;font-weight:700;transition:background 120ms,color 120ms;';
  }
  // Every window gets the same close button, and it is always the last thing
  // in the header, so the eye learns one place to look.
  panelClose(fn) {
    const b = document.createElement('button');
    b.style.cssText = 'width:30px;height:30px;flex:none;background:#1c1e14;border:1px solid #3a3f2c;color:#d8d4c6;' +
      'font-size:15px;line-height:1;cursor:pointer;font-family:IBM Plex Mono,monospace;';
    b.textContent = '×'; b.title = 'CLOSE';
    b.onmouseenter = () => { b.style.borderColor = '#c8a24a'; b.style.color = '#e8c774'; };
    b.onmouseleave = () => { b.style.borderColor = '#3a3f2c'; b.style.color = '#d8d4c6'; };
    b.onclick = fn;
    return b;
  }

  // One dimmer for every window - the treatment the world map already had and
  // nothing else did. Before this, opening the bank left the compass, quest
  // tracker, minimap and the whole lit world competing with the panel.
  uiScrim(on) {
    if (!this._scrimEl) {
      const d = document.createElement('div');
      d.style.cssText = 'position:fixed;inset:0;display:none;opacity:0;z-index:' + this.Z.scrim + ';' +
        'background:radial-gradient(ellipse at 50% 45%, rgba(8,9,6,0.62), rgba(5,6,4,0.88));' +
        'backdrop-filter:blur(2.5px);-webkit-backdrop-filter:blur(2.5px);transition:opacity 150ms ease;';
      d.addEventListener('pointerdown', () => this.closeTopWindow());
      document.body.appendChild(d);
      this._scrimEl = d;
    }
    const d = this._scrimEl;
    if (on) { d.style.display = 'block'; requestAnimationFrame(() => { if (this.uiWindowOpen()) d.style.opacity = '1'; }); }
    else { d.style.opacity = '0'; d.style.display = 'none'; }
  }
  // Clicking the dimmer closes what is in front of you, same as Escape.
  closeTopWindow() {
    if (this.shopOpen) return this.closeShop();
    if (this._wmOpen) return this.closeWorldMap();
    if (this._skOpen) return this.toggleSkills();
    if (this.bankOpen) return this.closeBank();
    if (this.sackWinId) return this.closeSackWin();
    if (this.walletOpen) return this.toggleWallet();
  }
  // banner() paints into the root HUD div, which sits under the dimmer, so any
  // message raised BY a panel (pack full, wrong slot, key unbound) was being
  // hidden by the panel that caused it. Route those to a note that rides above.
  uiNote(main, sub2, ms) {
    if (!this._noteEl) {
      const d = document.createElement('div');
      d.style.cssText = 'position:fixed;left:50%;top:76px;transform:translateX(-50%);z-index:' + this.Z.pop + ';' +
        'display:none;max-width:min(560px,92vw);padding:10px 18px;text-align:center;pointer-events:none;' +
        'background:rgba(12,13,9,0.97);border:1px solid #c8a24a;border-left:3px solid #c8a24a;' +
        'font-family:IBM Plex Mono,monospace;box-shadow:0 10px 40px rgba(0,0,0,0.7);';
      document.body.appendChild(d);
      this._noteEl = d;
    }
    this._noteEl.innerHTML =
      '<div style="font-size:12px;letter-spacing:0.14em;color:#e8c774;font-weight:700;">' + String(main || '') + '</div>' +
      (sub2 ? '<div style="font-size:10.5px;letter-spacing:0.06em;color:#b3afa0;margin-top:5px;line-height:1.6;">' + sub2 + '</div>' : '');
    this._noteEl.style.display = 'block';
    clearTimeout(this._noteT);
    this._noteT = setTimeout(() => { if (this._noteEl) this._noteEl.style.display = 'none'; }, ms || 2200);
  }
  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen); }""",
    tag='ui system')

# banner() itself makes the choice, so every call site is covered at once.
sub(
    "  banner(main, sub, keep, ms) {",
    """  banner(main, sub, keep, ms) {
    // A window is open, so the banner would be behind the dimmer. Almost every
    // banner raised at that moment came FROM the window (pack full, wrong
    // slot, key unbound), which made it exactly the message you must not lose.
    if (this.uiWindowOpen()) { this.uiNote(main, sub, ms || 2200); return; }""",
    tag='banner route')


# ------------------------------------------------------------ z-index rewiring
sub("      if (cont) { cont.style.position = 'fixed'; cont.style.zIndex = '75'; document.body.appendChild(cont); }",
    "      if (cont) { cont.style.position = 'fixed'; cont.style.zIndex = String(this.Z.bar); document.body.appendChild(cont); }",
    tag='bar z')

# drag ghosts and pop-ups must beat everything, including each other's panels
sub("        ghost.style.cssText = 'position:fixed;z-index:99;width:40px;height:40px;pointer-events:none;opacity:0.85;filter:drop-shadow(0 3px 6px #000);';",
    "        ghost.style.cssText = 'position:fixed;z-index:' + this.Z.drag + ';width:40px;height:40px;pointer-events:none;opacity:0.85;filter:drop-shadow(0 3px 6px #000);';",
    tag='bar ghost z')
sub("        g.style.cssText = 'position:fixed;width:44px;height:44px;pointer-events:none;z-index:99;display:flex;align-items:center;justify-content:center;background:rgba(21,23,15,0.9);border:1.5px solid #c8a24a;';",
    "        g.style.cssText = 'position:fixed;width:44px;height:44px;pointer-events:none;z-index:' + this.Z.drag + ';display:flex;align-items:center;justify-content:center;background:rgba(21,23,15,0.94);border:1.5px solid #c8a24a;';",
    tag='inv ghost z')
sub("    tip.style.cssText = 'position:fixed;display:none;z-index:98;background:rgba(10,11,8,0.97);border:1px solid #c8a24a;padding:8px 11px;font-family:\"IBM Plex Mono\",monospace;font-size:10.5px;color:#d8d4c6;pointer-events:none;max-width:230px;line-height:1.6;';",
    "    tip.style.cssText = 'position:fixed;display:none;z-index:' + this.Z.pop + ';background:rgba(12,13,9,0.98);border:1px solid #c8a24a;padding:8px 11px;font-family:IBM Plex Mono,monospace;font-size:10.5px;color:#d8d4c6;pointer-events:none;max-width:250px;line-height:1.6;box-shadow:0 8px 30px rgba(0,0,0,0.7);';",
    tag='inv tip z')
sub("    const M = mk('div', 'position:fixed;z-index:99;background:rgba(10,11,8,0.98);border:1px solid #c8a24a;min-width:130px;font-family:\"IBM Plex Mono\",monospace;font-size:11px;');",
    "    const M = mk('div', 'position:fixed;z-index:' + this.Z.pop + ';background:rgba(12,13,9,0.98);border:1px solid #c8a24a;min-width:150px;font-family:IBM Plex Mono,monospace;font-size:11px;box-shadow:0 8px 30px rgba(0,0,0,0.7);');",
    tag='ctx menu z')
sub("    const U = mk('div', 'position:fixed;left:50%;bottom:64px;transform:translateX(-50%);z-index:80;background:rgba(10,11,8,0.95);border:1px solid #c8a24a;padding:9px 16px;font-family:\"IBM Plex Mono\",monospace;font-size:11px;color:#d8d4c6;display:flex;gap:14px;align-items:center;');",
    "    const U = mk('div', 'position:fixed;left:50%;bottom:96px;transform:translateX(-50%);z-index:' + this.Z.pop + ';background:rgba(12,13,9,0.97);border:1px solid #c8a24a;padding:9px 16px;font-family:IBM Plex Mono,monospace;font-size:11px;color:#d8d4c6;display:flex;gap:14px;align-items:center;box-shadow:0 8px 30px rgba(0,0,0,0.7);');",
    tag='undo z')
sub("      layer.style.cssText = 'position:fixed;right:18px;bottom:150px;width:280px;pointer-events:none;z-index:55;display:flex;flex-direction:column-reverse;align-items:flex-end;';",
    "      layer.style.cssText = 'position:fixed;right:18px;bottom:150px;width:280px;pointer-events:none;z-index:' + this.Z.toast + ';display:flex;flex-direction:column-reverse;align-items:flex-end;';",
    tag='loot toast z')
sub("    box.style.cssText = 'position:fixed;top:8px;left:50%;transform:translateX(-50%);width:440px;height:30px;background:rgba(10,11,8,0.72);border:1px solid #3a3f2c;overflow:hidden;z-index:6;pointer-events:none;font-family:\"IBM Plex Mono\",monospace;display:none;';",
    "    box.style.cssText = 'position:fixed;top:8px;left:50%;transform:translateX(-50%);width:440px;height:30px;background:rgba(10,11,8,0.72);border:1px solid #3a3f2c;overflow:hidden;z-index:' + this.Z.compass + ';pointer-events:none;font-family:IBM Plex Mono,monospace;display:none;';",
    tag='compass z')


# ============================================================ 6. PANEL REBUILDS
# ---- pack & gear ----------------------------------------------------------
sub(
    """    const P = mk('div', 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);display:none;flex-direction:column;gap:10px;' +
      'width:730px;max-width:96vw;max-height:92vh;overflow-y:auto;padding:16px 18px;background:rgba(10,11,8,0.78);border:2px solid #3a3f2c;' +
      'font-family:"IBM Plex Mono",monospace;color:#d8d4c6;z-index:70;box-shadow:0 14px 60px rgba(0,0,0,0.7);');""",
    "    const P = mk('div', this.panelCss('740px'));",
    tag='inv root')

sub(
    """    const head = mk('div', 'display:flex;align-items:center;gap:14px;border-bottom:1px solid #3a3f2c;padding-bottom:9px;');
    head.appendChild(mk('div', 'font-size:14px;letter-spacing:0.22em;color:#e8c774;flex:1;', 'PACK & GEAR'));
    this.invGoldEl = mk('div', 'font-size:12px;color:#c8a24a;');
    head.appendChild(this.invGoldEl);
    const sortB = mk('button', 'padding:6px 14px;background:transparent;border:1px solid #c8a24a;color:#e8c774;font-family:monospace;font-size:11px;letter-spacing:0.12em;cursor:pointer;', 'SORT (R)');
    sortB.onclick = () => this.sortInventory();
    head.appendChild(sortB);
    const closeB = mk('button', 'width:30px;height:30px;background:#1c1e14;border:1px solid #3a3f2c;color:#d8d4c6;font-size:15px;cursor:pointer;', '×');
    closeB.onclick = () => this.toggleWallet();
    head.appendChild(closeB);
    P.appendChild(head);""",
    """    const head = mk('div', this.panelHeadCss());
    head.appendChild(mk('div', this.panelTitleCss(), 'PACK & GEAR'));
    this.invGoldEl = mk('div', 'font-size:12px;color:#c8a24a;letter-spacing:0.08em;');
    head.appendChild(this.invGoldEl);
    const sortB = mk('button', this.panelBtnCss(false), 'SORT (R)');
    sortB.title = 'Stack and tidy the whole pack. Nothing is ever lost, only rearranged.';
    sortB.onclick = () => this.sortInventory();
    head.appendChild(sortB);
    head.appendChild(this.panelClose(() => this.toggleWallet()));
    P.appendChild(head);
    P.appendChild(mk('div', 'font-size:10px;color:#7d8a63;letter-spacing:0.06em;line-height:1.6;margin-top:-2px;',
      'Everything you carry. Drag a piece onto the doll to wear it, or onto the bar at the bottom of the screen to put it on a number key. Hover anything for its stats.'));""",
    tag='inv head')

sub("    this.invStatsEl = mk('div', 'margin-top:10px;background:rgba(21,23,15,0.42);border:1px solid #26281f;padding:10px 12px;');",
    "    this.invStatsEl = mk('div', 'margin-top:10px;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:10px 12px;');",
    tag='inv stats box')

sub("    const dg = mk('div', 'display:grid;grid-template-columns:repeat(3,52px);grid-template-rows:repeat(4,52px);gap:6px;justify-content:center;background:rgba(21,23,15,0.42);border:1px solid #26281f;padding:12px 8px;');",
    "    const dg = mk('div', 'display:grid;grid-template-columns:repeat(3,52px);grid-template-rows:repeat(4,52px);gap:6px;justify-content:center;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:12px 8px;');",
    tag='inv doll grid')

sub(
    """    const leg = mk('div', 'border-top:1px solid #26281f;padding-top:8px;font-size:9.5px;line-height:1.7;color:#7d8a63;letter-spacing:0.05em;');
    leg.innerHTML =
      '<span style="color:#b3c29a">DRAG</span> move &nbsp;·&nbsp; <span style="color:#b3c29a">DRAG ONTO DOLL</span> equip &nbsp;·&nbsp; <span style="color:#b3c29a">DRAG TO BOTTOM BAR</span> bind key &nbsp;·&nbsp; <span style="color:#b3c29a">DRAG OFF PANEL</span> drop<br>' +
      '<span style="color:#b3c29a">SHIFT+CLICK</span> equip / unequip &nbsp;·&nbsp; <span style="color:#b3c29a">CTRL+CLICK</span> drop one &nbsp;·&nbsp; <span style="color:#b3c29a">RIGHT-CLICK</span> menu &nbsp;·&nbsp; <span style="color:#b3c29a">SHIFT+DRAG</span> split stack<br>' +
      '<span style="color:#b3c29a">R</span> sort &nbsp;·&nbsp; <span style="color:#b3c29a">TAB</span> close &nbsp;·&nbsp; hover any item for its stats';
    P.appendChild(leg);""",
    """    P.appendChild(this.panelLegend([
      ['DRAG', 'move an item'], ['DRAG ONTO DOLL', 'wear it'], ['DRAG TO BOTTOM BAR', 'bind it to a number key'], ['DRAG OFF THE PANEL', 'drop it on the ground'],
      ['SHIFT+CLICK', 'equip or unequip'], ['CTRL+CLICK', 'drop one'], ['RIGHT-CLICK', 'full menu'], ['SHIFT+DRAG', 'split a stack'],
      ['R', 'sort'], ['TAB or ESC', 'close']
    ]));""",
    tag='inv legend')

# ---- bank -----------------------------------------------------------------
sub(
    """    const P = mk('div', 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);display:none;flex-direction:column;gap:10px;width:712px;max-width:97vw;max-height:92vh;overflow-y:auto;padding:16px 18px;background:rgba(10,11,8,0.9);border:2px solid #c8a24a;font-family:"IBM Plex Mono",monospace;color:#d8d4c6;z-index:72;box-shadow:0 14px 60px rgba(0,0,0,0.7);');""",
    "    const P = mk('div', this.panelCss('740px'));",
    tag='bank root')

sub(
    """    const head = mk('div', 'display:flex;align-items:center;gap:10px;border-bottom:1px solid #c8a24a;padding-bottom:9px;');
    head.appendChild(mk('div', 'font-size:14px;letter-spacing:0.22em;color:#e8c774;', 'BANK OF HOLLOWREST'));
    this.bankSearch = document.createElement('input');
    this.bankSearch.placeholder = 'SEARCH…';
    this.bankSearch.style.cssText = 'flex:1;background:#15170f;border:1px solid #3a3f2c;color:#d8d4c6;padding:7px 10px;font-family:monospace;font-size:11px;letter-spacing:0.08em;';
    this.bankSearch.addEventListener('input', () => this.renderBank());
    head.appendChild(this.bankSearch);
    const btn = (label, fn, gold) => { const b = mk('button', 'padding:7px 12px;background:' + (gold ? '#c8a24a' : 'transparent') + ';border:1px solid #c8a24a;color:' + (gold ? '#17180f' : '#e8c774') + ';font-family:monospace;font-size:10px;letter-spacing:0.1em;cursor:pointer;font-weight:700;', label); b.onclick = fn; return b; };
    head.appendChild(btn('SORT', () => { this.bankSort(); this.renderBank(); }));
    head.appendChild(btn('DEPOSIT PACK', () => { this.bankDepositAll(); this.renderBank(); }, true));
    head.appendChild(btn('DEPOSIT WORN', () => { this.bankDepositWorn(); this.renderBank(); }));
    const x = mk('button', 'width:30px;height:30px;background:#1c1e14;border:1px solid #3a3f2c;color:#d8d4c6;font-size:15px;cursor:pointer;', '×');
    x.onclick = () => this.closeBank();
    head.appendChild(x);
    P.appendChild(head);
    this.bankGridEl = mk('div', 'display:grid;grid-template-columns:repeat(9,52px);gap:6px;justify-content:center;min-height:120px;');
    P.appendChild(this.bankGridEl);
    P.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#7d8a63;margin-top:4px;', 'YOUR PACK — CLICK TO DEPOSIT ALL · SHIFT+CLICK ONE'));
    this.bankPackEl = mk('div', 'display:grid;grid-template-columns:repeat(14,46px);gap:5px;justify-content:center;');
    P.appendChild(this.bankPackEl);
    const leg = mk('div', 'border-top:1px solid #26281f;padding-top:8px;font-size:9.5px;line-height:1.7;color:#7d8a63;letter-spacing:0.05em;');
    leg.innerHTML = '<span style="color:#b3c29a">CLICK BANK ITEM</span> withdraw 1 &nbsp;·&nbsp; <span style="color:#b3c29a">SHIFT+CLICK</span> withdraw 5 &nbsp;·&nbsp; <span style="color:#b3c29a">RIGHT-CLICK</span> withdraw ALL &nbsp;·&nbsp; <span style="color:#b3c29a">F / ESC</span> close &nbsp;·&nbsp; everything stacks in the vault';
    P.appendChild(leg);""",
    """    const head = mk('div', this.panelHeadCss());
    head.appendChild(mk('div', this.panelTitleCss(), 'BANK OF HOLLOWREST'));
    this.bankGoldEl = mk('div', 'font-size:12px;color:#c8a24a;letter-spacing:0.08em;');
    head.appendChild(this.bankGoldEl);
    this.bankSearch = document.createElement('input');
    this.bankSearch.placeholder = 'SEARCH THE VAULT…';
    this.bankSearch.title = 'Type any part of an item name to filter the vault.';
    this.bankSearch.style.cssText = 'flex:1;min-width:130px;background:#15170f;border:1px solid #3a3f2c;color:#d8d4c6;padding:7px 10px;font-family:IBM Plex Mono,monospace;font-size:11px;letter-spacing:0.08em;outline:none;';
    this.bankSearch.addEventListener('focus', () => { this.bankSearch.style.borderColor = '#c8a24a'; });
    this.bankSearch.addEventListener('blur', () => { this.bankSearch.style.borderColor = '#3a3f2c'; });
    this.bankSearch.addEventListener('input', () => this.renderBank());
    head.appendChild(this.bankSearch);
    const btn = (label, fn, gold, tip) => { const b = mk('button', this.panelBtnCss(gold), label); b.title = tip || ''; b.onclick = fn; return b; };
    head.appendChild(btn('SORT', () => { this.bankSort(); this.renderBank(); }, false, 'Group the vault by kind, most valuable first.'));
    head.appendChild(btn('DEPOSIT PACK', () => { this.bankDepositAll(); this.renderBank(); }, true, 'Store everything in your pack. Worn gear is not touched.'));
    head.appendChild(btn('DEPOSIT WORN', () => { this.bankDepositWorn(); this.renderBank(); }, false, 'Strip what you are wearing into the vault.'));
    head.appendChild(this.panelClose(() => this.closeBank()));
    P.appendChild(head);
    P.appendChild(mk('div', 'font-size:10px;color:#7d8a63;letter-spacing:0.06em;line-height:1.6;margin-top:-2px;',
      'Your vault is bottomless and everything in it stacks. Nothing stored here is ever dropped when you fall.'));
    P.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin-top:6px;', 'THE VAULT'));
    this.bankGridEl = mk('div', 'display:grid;grid-template-columns:repeat(9,52px);gap:6px;justify-content:center;min-height:112px;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:10px;');
    P.appendChild(this.bankGridEl);
    P.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin-top:6px;', 'YOUR PACK'));
    // Seven across, four down - the SAME shape the pack panel uses. Showing the
    // same 28 slots as 14x2 here meant the muscle memory did not carry over.
    this.bankPackEl = mk('div', 'display:grid;grid-template-columns:repeat(7,52px);gap:6px;justify-content:center;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:10px;');
    P.appendChild(this.bankPackEl);
    P.appendChild(this.panelLegend([
      ['CLICK A VAULT ITEM', 'withdraw one'], ['SHIFT+CLICK', 'withdraw five'], ['RIGHT-CLICK', 'withdraw the whole stack'],
      ['CLICK A PACK ITEM', 'deposit the whole stack'], ['SHIFT+CLICK', 'deposit one'], ['F or ESC', 'close']
    ]));""",
    tag='bank build')

sub(
    """  renderBank() {
    if (!this.bankWinEl || !this.bankOpen) return;
    const q = (this.bankSearch && this.bankSearch.value || '').trim().toUpperCase();""",
    """  renderBank() {
    if (!this.bankWinEl || !this.bankOpen) return;
    if (this.bankGoldEl) this.bankGoldEl.textContent = this.invCount('GOLD CROWNS').toLocaleString('en-US') + ' GOLD ON YOU';
    const q = (this.bankSearch && this.bankSearch.value || '').trim().toUpperCase();""",
    tag='bank gold')

sub(
    """      d.style.cssText = 'width:52px;height:52px;background:#15170f;border:1.5px solid #3a3f2c;display:flex;align-items:center;justify-content:center;position:relative;cursor:pointer;';
      d.innerHTML = this.slotHTML(c.item, c.qty);
      d.title = c.item + ' ×' + c.qty;""",
    """      d.style.cssText = 'width:52px;height:52px;background:#15170f;border:1.5px solid #3a3f2c;display:flex;align-items:center;justify-content:center;position:relative;cursor:pointer;transition:border-color 110ms;';
      d.innerHTML = this.slotHTML(c.item, c.qty);
      d.title = c.item + ' ×' + c.qty.toLocaleString('en-US') + '  —  click withdraw 1, shift+click 5, right-click all';
      d.onmouseenter = () => { d.style.borderColor = '#c8a24a'; };
      d.onmouseleave = () => { d.style.borderColor = '#3a3f2c'; };""",
    tag='bank vault slot')

sub(
    """      const d = document.createElement('div');
      d.style.cssText = 'width:46px;height:46px;background:#15170f;border:1.5px solid #2c2f24;display:flex;align-items:center;justify-content:center;position:relative;cursor:' + (c ? 'pointer' : 'default') + ';';
      if (c) {
        d.innerHTML = this.slotHTML(c.item, c.qty);
        const idx = i;""",
    """      const d = document.createElement('div');
      d.style.cssText = 'width:52px;height:52px;background:#15170f;border:1.5px solid #2c2f24;display:flex;align-items:center;justify-content:center;position:relative;transition:border-color 110ms;cursor:' + (c ? 'pointer' : 'default') + ';';
      if (c) {
        d.innerHTML = this.slotHTML(c.item, c.qty);
        d.title = c.item + ' ×' + c.qty.toLocaleString('en-US') + '  —  click deposits the stack, shift+click deposits one';
        d.onmouseenter = () => { d.style.borderColor = '#c8a24a'; };
        d.onmouseleave = () => { d.style.borderColor = '#2c2f24'; };
        const idx = i;""",
    tag='bank pack slot')

# ---- skills ---------------------------------------------------------------
sub(
    """    const P = mk2('position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);display:none;flex-direction:column;gap:10px;width:520px;max-width:95vw;max-height:90vh;overflow-y:auto;padding:16px 18px;background:rgba(10,11,8,0.94);border:2px solid #c8a24a;font-family:"IBM Plex Mono",monospace;color:#d8d4c6;z-index:72;box-shadow:0 14px 60px rgba(0,0,0,0.7);');
    const head = mk2('display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #c8a24a;padding-bottom:9px;');
    head.appendChild(mk2('font-size:14px;letter-spacing:0.22em;color:#e8c774;', 'SKILLS'));
    this._skTotalEl = mk2('font-size:10px;letter-spacing:0.14em;color:#7d8a63;');
    head.appendChild(this._skTotalEl);
    const x = document.createElement('button');
    x.style.cssText = 'width:30px;height:30px;background:#1c1e14;border:1px solid #3a3f2c;color:#d8d4c6;font-size:15px;cursor:pointer;';
    x.textContent = '×'; x.onclick = () => this.toggleSkills();
    head.appendChild(x);
    P.appendChild(head);
    this._skRowsEl = mk2('display:flex;flex-direction:column;gap:9px;');
    P.appendChild(this._skRowsEl);
    P.appendChild(mk2('border-top:1px solid #26281f;padding-top:7px;font-size:9.5px;color:#7d8a63;letter-spacing:0.08em;', 'K / ESC - CLOSE · HOVER A SKILL FOR DETAILS'));
    document.body.appendChild(P);
    this._skEl = P;
    // one rich tooltip for the whole page
    const tip = mk2('position:fixed;display:none;z-index:99;background:rgba(10,11,8,0.97);border:1px solid #c8a24a;padding:9px 12px;font-size:10.5px;color:#d8d4c6;pointer-events:none;max-width:260px;line-height:1.6;letter-spacing:0.03em;font-family:"IBM Plex Mono",monospace;');""",
    """    const P = mk2(this.panelCss('560px'));
    const head = mk2(this.panelHeadCss());
    head.appendChild(mk2(this.panelTitleCss(), 'SKILLS'));
    this._skTotalEl = mk2('font-size:10px;letter-spacing:0.14em;color:#7d8a63;');
    head.appendChild(this._skTotalEl);
    head.appendChild(this.panelClose(() => this.toggleSkills()));
    P.appendChild(head);
    P.appendChild(mk2('font-size:10px;color:#7d8a63;letter-spacing:0.06em;line-height:1.6;margin-top:-2px;',
      'Every skill trains by doing the thing. Levels raise what you hit for, what you can chop, mine and gather, and how much punishment you take.'));
    this._skRowsEl = mk2('display:flex;flex-direction:column;gap:9px;');
    P.appendChild(this._skRowsEl);
    P.appendChild(this.panelLegend([['HOVER A SKILL', 'what it does and how to train it'], ['K or ESC', 'close']]));
    document.body.appendChild(P);
    this._skEl = P;
    // one rich tooltip for the whole page
    const tip = mk2('position:fixed;display:none;z-index:' + this.Z.pop + ';background:rgba(12,13,9,0.98);border:1px solid #c8a24a;padding:9px 12px;font-size:10.5px;color:#d8d4c6;pointer-events:none;max-width:270px;line-height:1.6;letter-spacing:0.03em;font-family:IBM Plex Mono,monospace;box-shadow:0 8px 30px rgba(0,0,0,0.7);');""",
    tag='skills build')

sub(
    "      row.style.cssText = 'background:rgba(21,23,15,0.5);border:1px solid #26281f;padding:8px 12px;cursor:default;';",
    "      row.style.cssText = 'background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:8px 12px;cursor:help;transition:border-color 110ms;';",
    tag='skills row')
sub(
    "      row.addEventListener('mouseenter', () => {\n        this._skTip.innerHTML =",
    "      row.addEventListener('mouseenter', () => {\n        row.style.borderColor = '#c8a24a';\n        this._skTip.innerHTML =",
    tag='skills row hover in')
sub(
    "      row.addEventListener('mouseleave', () => { this._skTip.style.display = 'none'; });",
    "      row.addEventListener('mouseleave', () => { row.style.borderColor = '#2f3426'; this._skTip.style.display = 'none'; });",
    tag='skills row hover out')

# ---- loot sack ------------------------------------------------------------
sub(
    """      d.style.cssText = 'position:fixed;top:50%;right:26px;transform:translateY(-50%);width:300px;max-height:70vh;overflow-y:auto;z-index:71;' +
        'background:rgba(10,11,8,0.82);border:2px solid #3a3f2c;padding:14px 16px;font-family:"IBM Plex Mono",monospace;color:#d8d4c6;box-shadow:0 14px 60px rgba(0,0,0,0.7);';""",
    """      d.style.cssText = 'position:fixed;top:calc(50% - 40px);right:26px;transform:translateY(-50%);width:310px;max-height:calc(100vh - 210px);overflow-y:auto;z-index:' + this.Z.window + ';' +
        'background:rgba(12,13,9,0.97);border:1px solid #3a3f2c;border-top:2px solid #c8a24a;padding:14px 16px;font-family:IBM Plex Mono,monospace;color:#d8d4c6;box-shadow:0 18px 70px rgba(0,0,0,0.78);';""",
    tag='sack root')

sub(
    """    const head = mk('div', 'display:flex;align-items:center;border-bottom:1px solid #3a3f2c;padding-bottom:8px;margin-bottom:10px;');
    head.appendChild(mk('div', 'flex:1;font-size:12px;letter-spacing:0.18em;color:#e8c774;', 'LOOT SACK'));
    const x = mk('button', 'width:26px;height:26px;background:#1c1e14;border:1px solid #3a3f2c;color:#d8d4c6;cursor:pointer;', '×');
    x.onclick = () => this.closeSackWin();
    head.appendChild(x);
    el.appendChild(head);""",
    """    const head = mk('div', this.panelHeadCss());
    head.style.marginBottom = '10px';
    head.appendChild(mk('div', this.panelTitleCss(), 'LOOT SACK'));
    head.appendChild(this.panelClose(() => this.closeSackWin()));
    el.appendChild(head);""",
    tag='sack head')

sub(
    "    el.appendChild(mk('div', 'font-size:9px;color:#5f6b4a;margin-top:8px;letter-spacing:0.05em;line-height:1.6;', 'F CLOSE · WHAT YOU LEAVE STAYS FOR OTHER PLAYERS UNTIL THE SACK FADES'));",
    "    el.appendChild(this.panelLegend([['T', 'take everything that fits'], ['F or ESC', 'close']],\n"
    "      'Anything you leave behind stays here for other players until the sack fades.'));",
    tag='sack legend')

# ---- trader ---------------------------------------------------------------
sub(
    """      d.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:min(680px,92vw);max-height:82vh;overflow:auto;padding:22px 26px;background:rgba(10,11,8,0.96);border:2px solid #3a3f2c;font-family:monospace;color:#d8d4c6;z-index:80;box-shadow:0 14px 60px rgba(0,0,0,0.7);';
      document.body.appendChild(d); this.shopEl = d;
    }
    this.shopEl.style.display = 'block';""",
    """      d.style.cssText = this.panelCss('min(700px,94vw)');
      document.body.appendChild(d); this.shopEl = d;
    }
    this.shopEl.style.display = 'flex';""",
    tag='shop root')

sub(
    """    const head = mk('div', 'display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid #3a3f2c;padding-bottom:10px;margin-bottom:14px;');
    head.appendChild(mk('div', 'font-size:15px;letter-spacing:0.18em;color:#e8c774;', 'FENWICK THE TRADER'));
    head.appendChild(mk('div', 'font-size:13px;color:#c8a24a;', gold + ' GOLD CROWNS'));
    el.appendChild(head);
    el.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#7d8a63;margin-bottom:8px;', 'WARES'));""",
    """    const head = mk('div', this.panelHeadCss());
    head.appendChild(mk('div', this.panelTitleCss(), 'FENWICK THE TRADER'));
    head.appendChild(mk('div', 'font-size:12px;color:#c8a24a;letter-spacing:0.08em;', gold.toLocaleString('en-US') + ' GOLD CROWNS'));
    head.appendChild(this.panelClose(() => this.closeShop()));
    el.appendChild(head);
    el.appendChild(mk('div', 'font-size:10px;color:#7d8a63;letter-spacing:0.06em;line-height:1.6;margin-top:-2px;',
      'Fenwick sells armour and spell tomes, and buys anything you have hauled back out of the world. Prices are fixed - he does not haggle.'));
    el.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin:10px 0 4px;', 'HE SELLS'));""",
    tag='shop head')

# Wares rows gain the icon every other panel already shows.
sub(
    """      const row = mk('div', 'display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #26281f;');
      const info = mk('div', 'flex:1;');
      info.appendChild(mk('div', 'font-size:13px;color:' + (owned ? '#5f6b4a' : '#f2efe6') + ';', s.k + (owned ? ' (OWNED)' : '')));""",
    """      const row = mk('div', 'display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #2f3426;');
      row.appendChild(this.shopIcon(s.k, owned));
      const info = mk('div', 'flex:1;');
      info.appendChild(mk('div', 'font-size:13px;color:' + (owned ? '#5f6b4a' : '#f2efe6') + ';', s.k + (owned ? '  (OWNED)' : '')));""",
    tag='shop wares row')

sub(
    """    el.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#7d8a63;margin:16px 0 8px;', 'FENWICK BUYS'));
    const prices = this.sellPrices();
    let any = false;
    for (const k in prices) {
      const have = this.invCount(k); if (have <= 0) continue;
      any = true;
      const row = mk('div', 'display:flex;align-items:center;gap:12px;padding:7px 0;border-bottom:1px solid #26281f;');
      row.appendChild(mk('div', 'flex:1;font-size:13px;', k + '  ×' + have));""",
    """    el.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin:14px 0 4px;', 'HE BUYS — WHAT YOU ARE CARRYING'));
    const prices = this.sellPrices();
    let any = false;
    for (const k in prices) {
      const have = this.invCount(k); if (have <= 0) continue;
      any = true;
      const row = mk('div', 'display:flex;align-items:center;gap:12px;padding:7px 0;border-bottom:1px solid #2f3426;');
      row.appendChild(this.shopIcon(k, false));
      row.appendChild(mk('div', 'flex:1;font-size:13px;', k + '  ×' + have.toLocaleString('en-US')));""",
    tag='shop buys row')

sub(
    """    if (!any) el.appendChild(mk('div', 'font-size:11px;color:#5f6b4a;', 'NOTHING HE WANTS. BRING PELTS, HIDES, ORE OR PAYCHECKS.'));
    const foot = mk('div', 'margin-top:18px;display:flex;justify-content:space-between;align-items:center;');
    foot.appendChild(mk('div', 'font-size:10.5px;color:#5f6b4a;', 'ARMOUR: ' + this.armourName()));
    const close = mk('button', 'padding:9px 20px;background:#c8a24a;border:none;color:#17180f;font-family:monospace;font-weight:700;font-size:12px;letter-spacing:0.12em;cursor:pointer;', 'CLOSE (F)');
    close.onclick = () => this.closeShop();
    foot.appendChild(close);
    el.appendChild(foot);""",
    """    if (!any) el.appendChild(mk('div', 'font-size:11px;color:#5f6b4a;padding:6px 0;', 'NOTHING HE WANTS RIGHT NOW. BRING PELTS, HIDES, ORE OR PAYCHECKS.'));
    const foot = mk('div', 'margin-top:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;');
    foot.appendChild(mk('div', 'font-size:10.5px;color:#7d8a63;letter-spacing:0.06em;', 'WEARING: ' + this.armourName()));
    const close = mk('button', this.panelBtnCss(true), 'CLOSE (F)');
    close.style.padding = '9px 20px'; close.style.fontSize = '12px';
    close.onclick = () => this.closeShop();
    foot.appendChild(close);
    el.appendChild(foot);
    el.appendChild(this.panelLegend([['BUY', 'costs gold, goes straight into your pack'], ['SELL 1 or ALL', 'turns what you carry into gold'], ['F or ESC', 'close']]));""",
    tag='shop foot')

# ---- spell wheel ----------------------------------------------------------
sub(
    "const ring = document.createElement('div'); ring.style.cssText = 'position:absolute;top:50%;left:50%;width:280px;height:280px;margin:-140px 0 0 -140px;border-radius:50%;background:rgba(10,11,8,0.85);border:2px solid #3a3f2c;box-shadow:0 10px 40px rgba(0,0,0,0.5);'; wrap.appendChild(ring);",
    "const ring = document.createElement('div'); ring.style.cssText = 'position:absolute;top:50%;left:50%;width:280px;height:280px;margin:-140px 0 0 -140px;border-radius:50%;background:radial-gradient(circle, rgba(12,13,9,0.92) 55%, rgba(12,13,9,0.7) 100%);border:1px solid #3a3f2c;box-shadow:0 10px 44px rgba(0,0,0,0.6);'; wrap.appendChild(ring);"
    " const hint = document.createElement('div'); hint.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;font-family:IBM Plex Mono,monospace;pointer-events:none;width:150px;';"
    " const hn = document.createElement('div'); hn.style.cssText = 'font-size:12px;font-weight:700;letter-spacing:0.1em;color:#e8c774;'; const hs = document.createElement('div'); hs.style.cssText = 'font-size:8.5px;letter-spacing:0.14em;color:#7d8a63;margin-top:4px;line-height:1.5;'; hs.textContent = 'MOVE THE MOUSE · RELEASE Q TO SELECT';"
    " hint.appendChild(hn); hint.appendChild(hs); ring.appendChild(hint); this.wheelHintEl = hn;",
    tag='spell wheel ring')

sub(
    "const wrap = document.createElement('div'); wrap.style.cssText = 'position:fixed;inset:0;display:none;pointer-events:none;z-index:60;';",
    "const wrap = document.createElement('div'); wrap.style.cssText = 'position:fixed;inset:0;display:none;pointer-events:none;z-index:' + this.Z.window + ';';",
    tag='spell wheel wrap')

sub(
    "for (const k in this.wheelSlices) { const on = k === this.wheelHover; this.wheelSlices[k].style.transform = on ? 'scale(1.12)' : 'scale(1)'; this.wheelSlices[k].style.borderColor = on ? '#e8c774' : '#3a3f2c'; this.wheelSlices[k].style.background = on ? 'rgba(42,40,20,0.95)' : 'rgba(21,23,15,0.9)'; } }",
    "for (const k in this.wheelSlices) { const on = k === this.wheelHover; this.wheelSlices[k].style.transform = on ? 'scale(1.12)' : 'scale(1)'; this.wheelSlices[k].style.borderColor = on ? '#e8c774' : '#3a3f2c'; this.wheelSlices[k].style.background = on ? 'rgba(42,40,20,0.95)' : 'rgba(21,23,15,0.9)'; }"
    " if (this.wheelHintEl) { const cur = this.spellList().filter(sp => sp.key === this.wheelHover)[0]; this.wheelHintEl.textContent = cur ? cur.label : ''; this.wheelHintEl.style.color = cur ? cur.color : '#e8c774'; } }",
    tag='spell wheel hint')

# ---- player list ----------------------------------------------------------
sub(
    "d.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);min-width:280px;padding:20px 24px;background:rgba(10,11,8,0.93);border:2px solid #3a3f2c;font-family:monospace;color:#d8d4c6;z-index:70;display:none;pointer-events:none;box-shadow:0 10px 40px rgba(0,0,0,0.6);';",
    "d.style.cssText = 'position:fixed;top:calc(50% - 40px);left:50%;transform:translate(-50%,-50%);min-width:300px;padding:18px 22px;background:rgba(12,13,9,0.97);border:1px solid #3a3f2c;border-top:2px solid #c8a24a;font-family:IBM Plex Mono,monospace;color:#d8d4c6;z-index:' + this.Z.window + ';display:none;pointer-events:none;box-shadow:0 18px 70px rgba(0,0,0,0.78);';",
    tag='plist root')

# ---- world map ------------------------------------------------------------
sub(
    "    ov.style.cssText = 'position:fixed;inset:0;z-index:78;display:none;align-items:center;justify-content:center;background:rgba(6,7,4,0.9);font-family:\"IBM Plex Mono\",monospace;';",
    "    ov.style.cssText = 'position:fixed;inset:0;z-index:' + this.Z.window + ';display:none;align-items:center;justify-content:center;background:rgba(6,7,4,0.72);font-family:IBM Plex Mono,monospace;';",
    tag='map root')
sub(
    "    fr.style.cssText = 'position:relative;width:min(96vw,152vh);border:2px solid #3a3f2c;background:#11130c;box-shadow:0 20px 80px rgba(0,0,0,0.8);';",
    "    fr.style.cssText = 'position:relative;width:min(94vw,148vh);border:1px solid #3a3f2c;border-top:2px solid #c8a24a;background:#11130c;box-shadow:0 18px 70px rgba(0,0,0,0.78);';",
    tag='map frame')
sub(
    "    tb.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:9px 16px;border-bottom:1px solid #26281f;';",
    "    tb.style.cssText = 'display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 16px;border-bottom:1px solid #2f3426;';",
    tag='map toolbar')
sub(
    "    tb.innerHTML = '<span style=\"color:#e8c774;font-size:14px;letter-spacing:0.35em;font-weight:700\">A S T E R R A &mdash; WORLD MAP</span>' +\n"
    "      '<span style=\"color:#7d8a63;font-size:10px;letter-spacing:0.2em\">DRAG &mdash; PAN &nbsp;&middot;&nbsp; SCROLL &mdash; ZOOM &nbsp;&middot;&nbsp; M / ESC &mdash; CLOSE</span>';",
    "    tb.innerHTML = '<span style=\"font-family:Cinzel,serif;color:#e8c774;font-size:15px;letter-spacing:0.3em;font-weight:700\">ASTERRA &mdash; WORLD MAP</span>' +\n"
    "      '<span style=\"color:#7d8a63;font-size:9.5px;letter-spacing:0.1em\"><span style=\"color:#b3c29a\">DRAG</span> pan &nbsp;&middot;&nbsp; <span style=\"color:#b3c29a\">SCROLL</span> zoom &nbsp;&middot;&nbsp; <span style=\"color:#b3c29a\">M or ESC</span> close</span>';",
    tag='map toolbar text')

# ---- shared helpers used by the panels above ------------------------------
# panelLegend and shopIcon live next to the rest of the UI system.
sub(
    "  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen); }",
    """  // Every window ends with the same control strip, built from pairs so the
  // wording stays parallel and nothing gets forgotten when a control is added.
  panelLegend(pairs, note) {
    const d = document.createElement('div');
    d.style.cssText = this.panelLegendCss();
    d.innerHTML = pairs.map(p => '<span style="color:#b3c29a;font-weight:700">' + p[0] + '</span> ' + p[1]).join(' &nbsp;·&nbsp; ') +
      (note ? '<div style="margin-top:4px;color:#5f6b4a;">' + note + '</div>' : '');
    return d;
  }
  // The trader was the one window with no icons at all, which made it read as
  // a spreadsheet next to the pack and the bank.
  shopIcon(id, dim) {
    const d = document.createElement('div');
    d.style.cssText = 'width:38px;height:38px;flex:none;display:flex;align-items:center;justify-content:center;' +
      'background:#15170f;border:1.5px solid #2c2f24;opacity:' + (dim ? '0.4' : '1') + ';';
    const inner = document.createElement('div');
    inner.style.cssText = 'width:26px;height:26px;display:flex;align-items:center;justify-content:center;';
    inner.innerHTML = this.itemIcon(id);
    d.appendChild(inner);
    return d;
  }
  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen); }""",
    tag='panel helpers')


# ============================================ 7. FONT: one typeface everywhere
# Twenty places asked for the generic `monospace`, so those panels rendered in
# whatever the browser picked rather than IBM Plex Mono. Unquoted on purpose:
# this string appears both inside JS strings and inside HTML style attributes,
# and an unquoted family name with spaces is valid CSS in both.
before = s.count('font-family:monospace')
s = s.replace('font-family:monospace', 'font-family:IBM Plex Mono,monospace')
assert s.count('font-family:monospace') == 0
assert before > 0, 'no generic monospace left to fix'
n_edits += 1
print('  generic monospace fixed in %d places' % before)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('38_ui_pass_one: %d edits applied' % n_edits)
