#!/usr/bin/env python3
"""Patch 58: the world keeps running while the furnace or anvil works.

Kevin: "the game crashes anytime i hit smelt". Reproduced in his own
browser: no exception anywhere - the world SIM freezes. active() only runs
the simulation when the pointer is locked, free-aiming, or a window is
open. Clicking SMELT closes the furnace window, the pointer is not locked
(it was freed for the UI), so active() goes false and stepWorld stops:
frozen world, no bars, no XP, looks exactly like a crash. The pre-UI
smelt never hit this because F never released the lock.

Two fixes, both in the spirit of the v14 pause-bug rule ("the world does
not stop because of UI state"):

1. active() also accepts a running work queue (smelting or smithQ) - the
   furnace and anvil keep working whatever the pointer is doing.
2. SMELT and SMITH re-request the pointer lock as they close the window.
   The click IS a user gesture, so the browser grants it: the player is
   instantly back in control, watching the bars come out.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'anchor matched %d times (wanted %d): %s | %s' % (f, count, tag, old[:110].replace('\n', ' / '))
    s = s.replace(old, new)
    n += 1


sub("  active() { return this.started && !this.contextLost && (this.locked || this.freeAim || this.uiWindowOpen() || this.smelting || this.smithQ); }"
    if False else
    "  active() { return this.started && !this.contextLost && (this.locked || this.freeAim || this.uiWindowOpen()); }",
    "  active() { return this.started && !this.contextLost && (this.locked || this.freeAim || this.uiWindowOpen() || this.smelting || this.smithQ); }",
    tag='active() runs work queues')

sub("""    this.smeltT = 0;
    this.closeFurnace();""",
    """    this.smeltT = 0;
    this.closeFurnace();
    this.requestLock();   // the SMELT click is a user gesture, so this is granted""",
    tag='smelt relocks')

sub("""    this.smithT = 0; this.forgeClang = 0;
    this.closeAnvil();""",
    """    this.smithT = 0; this.forgeClang = 0;
    this.closeAnvil();
    this.requestLock();   // the SMITH click is a user gesture, so this is granted""",
    tag='smith relocks')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('58_station_unfreeze: %d edits applied' % n)
