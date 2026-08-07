#!/usr/bin/env python3
"""Patch 72.416: R and F no longer hijack the action bar.

Kevin's report: pressing R equips whatever is in action-bar slot 2 (his
staff), and pressing F equips slot 3 (his bow) -- alternating R/F just
bounces between the two. He never bound either key to the bar and doesn't
want that.

Root cause, confirmed in bindInput()'s CODES table (present since the
initial commit, so this predates every current track):

    KeyQ: 'wheel', KeyR: '2', KeyF: '3', KeyO: 'plist',

Every physical key is normalised through this table before the dispatcher
looks at it, so KeyR and KeyF were quietly ALIASED to the exact same
internal values as the Digit2 / Digit3 hotkeys. Two different bugs fall
out of that one line:

- R: the ONLY documented job for R is "SORT (R)" inside the Pack & Gear
  panel (walletOpen), which is already handled by its own dedicated
  `if (this.walletOpen) { if (e.code === 'KeyR') { ...sortInventory... } }`
  check earlier in the handler. The CODES alias below that meant R ALSO
  fell through to the normal dispatcher as if you had pressed 2, equipping
  bar slot 1 (displayed "2") any time the pack wasn't open. Nothing in the
  game ever intended R to be a weapon-swap key -- the front-menu control
  legend lists "1-5 blade . staff . bow . pick . axe" and nothing else, and
  UI-REGISTRY.md documents no other R binding.
- F: F's real, load-bearing job is the interact key -- "PRESS F" on every
  prompt in the game (talk to Ball, loot a sack, bank at Odwin's booth,
  open Fenwick's shop, work the furnace). That already runs through the
  k === '3' branch on purpose, so F and Digit3 share code. The bug is the
  fallback tacked onto the END of that branch: when there is nothing to
  interact with, it falls through to `this.switchWeapon(2)`, which makes
  sense for the ACTUAL Digit3 key (the documented "3 = bow" hotkey) but
  is a pure side effect for F, which was never supposed to double as a
  weapon key at all.

Fix: stop aliasing KeyR/KeyF onto the digit values in CODES. Give F its
own 'interact' token instead, wired into both places the old '3' alias
fired (the uiWindowOpen() close-panel path and the normal-play path), but
WITHOUT the switchWeapon(2) fallback that only belongs to the real Digit3
key. R gets no alias at all, so outside the pack panel it now does
nothing, exactly like every other unbound key -- the sortInventory branch
that already gates on this.walletOpen is untouched and still works.

Net effect: R only sorts, and only while the pack is open (unchanged). F
still opens/closes/talks/loots/banks/smiths exactly as before (unchanged),
but no longer equips the bow as a side effect when nothing is nearby to
interact with. Digit key 3 keeps its existing dual behaviour (interact if
possible, else equip bow) exactly as documented.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 72.416 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. stop aliasing KeyR/KeyF onto the Digit2/Digit3 bar values ---------
sub(
    """      KeyQ: 'wheel', KeyR: '2', KeyF: '3', KeyO: 'plist',""",
    """      KeyQ: 'wheel', KeyF: 'interact', KeyO: 'plist',""",
    tag='CODES table: drop KeyR alias, retarget KeyF to its own token')

# ---- 2. panel-open path: F still closes/interacts with whatever is under
#         the window (loot sack take-all prompt, "F - CLOSE ..." etc) ------
sub(
    """      if (this.uiWindowOpen()) {
        if (k === '3') { e.preventDefault(); const pick = this.bestInteract(); if (pick) pick.run(); }
        return;
      }""",
    """      if (this.uiWindowOpen()) {
        if (k === '3' || k === 'interact') { e.preventDefault(); const pick = this.bestInteract(); if (pick) pick.run(); }
        return;
      }""",
    tag='uiWindowOpen path: F still interacts, no digit coupling needed')

# ---- 3. normal-play path: F interacts only; the switchWeapon(2) fallback
#         stays exclusive to the real Digit3 key -----------------------------
sub(
    """      if (k === '3') {
        // One list, nearest first. The old fixed chain meant the prompt and
        // the key could disagree, and that whoever was first in the chain won
        // no matter which one you were standing on.
        const pick = this.bestInteract();
        if (pick && pick.run()) return;
        this.switchWeapon(2);
      }""",
    """      if (k === '3' || k === 'interact') {
        // One list, nearest first. The old fixed chain meant the prompt and
        // the key could disagree, and that whoever was first in the chain won
        // no matter which one you were standing on.
        const pick = this.bestInteract();
        if (pick && pick.run()) return;
        // Only the real Digit3 key doubles as a weapon-bar hotkey (matches
        // the documented "3 = bow" control). F is interact-only -- it used
        // to fall through to here too and silently re-equip bar slot 3 any
        // time nothing was in reach, which is the bug Kevin reported.
        if (k === '3') this.switchWeapon(2);
      }""",
    tag='normal-play path: switchWeapon(2) fallback exclusive to Digit3')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('72.416_r_f_hotkey_hijack: %d edits applied (1-3)' % n)
