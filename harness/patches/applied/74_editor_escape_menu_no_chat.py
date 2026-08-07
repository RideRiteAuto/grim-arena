#!/usr/bin/env python3
"""Patch 74: two more editor-only fixes Kevin flagged right after patch 72
shipped, both scoped to editorOn the same way patch 72 was.

1. Escape in the editor still opened the game's real PAUSED menu, LOG OUT
   button included. Patch 72 only guarded the pointerlockchange fallback
   inside bind()'s plc closure (the thing Tab was tripping); it never
   touched bindInput()'s direct Escape handler
   (`if (this.started && this.mode === 'ai') { this.toggleMenuOverlay(); }`),
   which fires independently of pointer lock and is still exactly what
   Kevin wants Escape to do in the editor: bring up RESUME and SETTINGS
   (aim assist, music on/off, PVP) so he can toggle music without leaving
   the tool. Logging out mid-edit makes no sense though -- an editor
   session has no character, no inventory, nothing to save via doLogout(),
   it just closes the socket and reloads the title screen underneath the
   tool -- so the LOG OUT button is skipped when editorOn. buildPauseDom()
   only runs once per boot and caches its DOM (`if (this.pauseEl) return`),
   and editorOn is already true before the first Escape press can reach it
   (enter() sets it before the player can interact with anything), so this
   is a build-time skip, not a per-open check. A real player's pause menu,
   Escape binding and toggleMenuOverlay() are not touched at all.

2. The chat box (bottom-left panel, Enter to open) was showing up in the
   editor and getting in the way of the tool panel. enter() bypasses
   play() entirely -- it sets started/mode/worldOn itself -- so chat only
   ever appeared because pressing Enter while not focused in a text field
   still falls through bindInput()'s existing focusChat() branch (gated on
   started && mode === 'ai', both of which the editor sets), which calls
   buildChatDom(). Every other path into chat (onChatMsg, sendWhisperTo,
   openWhisperTo) also funnels through buildChatDom() first, and every one
   of them already no-ops safely without it (chatLine bails on
   `!this.chatLines`, renderChatTabs bails on `!this.chatTabsEl`) since the
   editor's enter() closes the socket, so no chat traffic reaches this
   session anyway. One guard at the top of buildChatDom() covers all of
   them. A real player's chat is untouched: editorOn is never true for one.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 74 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. no LOG OUT button on the editor's Escape-menu ----------------------
sub(
    """    const logout = mk('button', 'display:block;width:100%;margin-top:2px;padding:11px 0;background:transparent;border:1px solid #6b4a3f;color:#c07a68;font-family:IBM Plex Mono,monospace;font-size:11px;letter-spacing:0.16em;cursor:pointer;', 'LOG OUT');
    logout.onclick = () => { logout.textContent = 'SAVING…'; this.doLogout(); };
    panel.appendChild(logout);""",
    """    // An editor session has no character or save to log out of -- it just
    // closes the socket and drops the title screen in behind the tool --
    // so the only door back out of this panel, for an editor session, is
    // closing it again. editorOn is never true for a real player.
    if (!this.editorOn) {
      const logout = mk('button', 'display:block;width:100%;margin-top:2px;padding:11px 0;background:transparent;border:1px solid #6b4a3f;color:#c07a68;font-family:IBM Plex Mono,monospace;font-size:11px;letter-spacing:0.16em;cursor:pointer;', 'LOG OUT');
      logout.onclick = () => { logout.textContent = 'SAVING…'; this.doLogout(); };
      panel.appendChild(logout);
    }""",
    tag='no logout button in the editor pause menu')

# ---- 2. the chat box never builds during an editor session -----------------
sub(
    """  buildChatDom() {
    if (this.chatEl) return;""",
    """  buildChatDom() {
    // The editor has no socket (enter() closes it) and no use for chat --
    // it was only ever reachable here because Enter, when nothing else has
    // the keyboard, falls through to focusChat() same as it would in a
    // real game session. Every other way in (onChatMsg, sendWhisperTo,
    // openWhisperTo) already no-ops safely with chatEl left unset, so one
    // guard here is the whole fix. editorOn is never true for a player.
    if (this.chatEl || this.editorOn) return;""",
    tag='chat never builds in an editor session')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('74_editor_escape_menu_no_chat: %d edits applied (1-2)' % n)
