#!/usr/bin/env python3
"""Patch 72: two editor-only fixes Kevin flagged after a night of testing.

1. Tab, in the editor, was popping up the game's own PAUSED menu (title
   "PAUSED", a RESUME button, settings, logout) in the middle of the screen,
   on top of the tool panel.

   Root cause: setFly(false) in editor-ui.js calls document.exitPointerLock()
   to free the cursor for clicking tools, which fires a real 'pointerlockchange'
   event on document. The editor's own listener for that event just resets its
   own S.fly bookkeeping -- but the GAME's player-controls binding (bind()'s
   plc closure, game-src.html ~20096) is ALSO still listening for the exact
   same event, because nothing ever unbinds it for an editor session. It sees
   the lock drop, and since none of the game's own guards ("a bank/pack window
   is open", "not started yet") apply during an editor session, it calls
   this.openPauseMenu() -- the PAUSED overlay. Every Tab press replays this.

   Fix: openPauseMenu() is guarded on this.editorOn, the same flag every other
   editor-vs-player branch in this file already uses (see EDIT_UI().tick()
   above). editorOn is never true for a real player, so their pause-on-unlock
   behaviour -- opening the menu when they Escape or otherwise lose the lock
   -- is untouched byte for byte. This is the ONLY thing this patch changes
   about openPauseMenu's triggering; the menu itself, and every other way to
   reach it, are not touched.

2. Loading straight into ?edit=1 showed the game's title screen (login box,
   "Grim World" wordmark, LOADING...) for a beat before flipping into the
   editor. componentDidMount() always calls buildLoginUi() first and only
   hides the title overlay much later, inside GRIM_EDIT_UI.enter(), which
   cannot run until three.js has loaded, the world has booted and the edit
   layer has been fetched -- so the title screen is genuinely what paints
   first for everyone, editor session or not.

   Fix: componentDidMount() checks the same URL flag the editor itself uses
   to decide whether to enter (GRIM_EDIT_UI.wanted(), a synchronous check of
   location.search/hash with no network or boot dependency) and hides the
   title overlay in that same first tick, before buildLoginUi() populates it.
   Hiding happens before the browser's next paint, so there is nothing to
   flash. A normal player never has ?edit=1, wanted() is false, and boot is
   byte-for-byte what it was.

Both fixes are additive guards on GRIM_EDIT_UI/editorOn, which are only ever
true inside an editor session. Neither one moves, renames or removes anything
in the normal game path.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 72 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. Tab's pointer-lock-exit stops waking the game's own pause menu ----
sub(
    """    const plc = () => {
      this.locked = document.pointerLockElement === el;
      if (this.locked) { this.lockFails = 0; this.showOverlay(false); return; }
      if (this.uiWindowOpen()) return;   // pack/sack/bank/shop own the cursor: world stays visible behind them
      if (this.started && !this.freeAim) this.openPauseMenu();
    };""",
    """    const plc = () => {
      this.locked = document.pointerLockElement === el;
      if (this.locked) { this.lockFails = 0; this.showOverlay(false); return; }
      // The editor's own Tab key frees and re-locks the cursor constantly to
      // switch between flying and clicking tools. That is an editor gesture,
      // not a player asking to pause, so an editor session is the one case
      // this skips. editorOn is never true for a real player.
      if (this.editorOn) return;
      if (this.uiWindowOpen()) return;   // pack/sack/bank/shop own the cursor: world stays visible behind them
      if (this.started && !this.freeAim) this.openPauseMenu();
    };""",
    tag='plc skips the pause menu in an editor session')

# ---- 2. An editor session hides the title screen before it ever paints ----
sub(
    """  componentDidMount() {
    this.alive = true;
    window.__grim = this;   // test/debug handle
    // the menu must look RIGHT from the first paint - not after the 3D
    // engine downloads. Login box, hidden name field, relocated colours
    // and the retired PLAY NOW all happen before three.js arrives.
    try { this.buildLoginUi(); } catch (e) {}""",
    """  componentDidMount() {
    this.alive = true;
    window.__grim = this;   // test/debug handle
    // An editor session (?edit=1) never wants the title screen at all, and
    // normally it would still get one for a beat: GRIM_EDIT_UI.enter() can
    // only hide it once boot finishes, minutes of setup away in wall time
    // terms, seconds in real ones, but still a visible flash. wanted() is a
    // synchronous check of the URL with no boot dependency, so hide it here,
    // in the same tick as mount and before buildLoginUi() populates it,
    // rather than showing it and hiding it again later. A normal player
    // never has ?edit=1: wanted() is false and this never runs for them.
    try {
      if (GRIM_EDIT_UI.wanted() && this.overlayRef.current) this.overlayRef.current.style.display = 'none';
    } catch (e) {}
    // the menu must look RIGHT from the first paint - not after the 3D
    // engine downloads. Login box, hidden name field, relocated colours
    // and the retired PLAY NOW all happen before three.js arrives.
    try { this.buildLoginUi(); } catch (e) {}""",
    tag='hide the title overlay before mount if ?edit=1')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('72_editor_boot_and_tab_menu: %d edits applied (1-2)' % n)
