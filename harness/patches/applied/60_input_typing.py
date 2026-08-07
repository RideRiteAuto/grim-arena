#!/usr/bin/env python3
"""Patch 60: typing in a panel text box no longer fires game hotkeys.

Kevin's report: pressing 3 while typing a quantity in the smelting UI closes
the window, and the smithing screen has the same problem. The global keydown
handler treats every digit as a weapon-swap or interact key even when the
key was aimed at a text box, and with a crafting window open the digit-3
branch runs bestInteract(), which toggles the very station UI the player is
typing into. The bank's vault search had the same exposure for letter
hotkeys (T with a sack open, R with the pack open).

Fix, same pattern the build editor already uses for its own fields: when the
event target is a text-entry element, the box owns the keyboard. The global
handler steps aside entirely, except Escape, which blurs the box and closes
the panel - the promise Escape already makes everywhere else. Keyup stays
unguarded on purpose: it only ever clears held-key state, and guarding it
could strand a movement key as stuck-down if a box grabbed focus mid-hold.

Also gives "a little faster than clicking the arrow a bunch" its natural
ending: Enter in a quantity box commits the craft, exactly as if SMELT or
SMITH had been clicked.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 60 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. a focused text box owns the keyboard ------------------------------
sub("""    const kd = e => {
      // The map releases the mouse, which drops the pointer-lock "active\"""",
    """    const kd = e => {
      // A focused text box owns the keyboard: digits land in the box, not on
      // the weapon bar, and no hotkey can yank the panel away mid-type (the
      // digit-3 interact branch was closing the furnace UI under the cursor).
      // Escape blurs the box and closes the panel, keeping Escape's usual
      // promise. Same guard the build editor uses for its own fields.
      const tgt = e.target;
      if (tgt && (tgt.tagName === 'INPUT' || tgt.tagName === 'TEXTAREA' || tgt.isContentEditable)) {
        if (e.code === 'Escape') { tgt.blur(); this.closeTopWindow(); }
        return;
      }
      // The map releases the mouse, which drops the pointer-lock "active\"""",
    tag='kd text-box guard')

# ---- 2. furnace quantity box: Enter commits the smelt ---------------------
sub("""        mx.onclick = () => { inp.value = String(this.smeltMax(r)); clamp(); };
        inp.addEventListener('change', clamp);""",
    """        mx.onclick = () => { inp.value = String(this.smeltMax(r)); clamp(); };
        inp.addEventListener('change', clamp);
        inp.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); clamp(); go.click(); } });""",
    tag='furnace enter commits')

# ---- 3. anvil quantity box: Enter commits the smith -----------------------
sub("""        mx.onclick = () => { inp.value = String(maxNow()); clamp(); };
        inp.addEventListener('change', clamp);""",
    """        mx.onclick = () => { inp.value = String(maxNow()); clamp(); };
        inp.addEventListener('change', clamp);
        inp.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); clamp(); go.click(); } });""",
    tag='anvil enter commits')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('60_input_typing: %d edits applied' % n)
