#!/usr/bin/env python3
"""Patch 45: key hints say PRESS, and the mount hints stop covering the
interact prompt. Edits /tmp/game-src.html.

The collision Kevin hit: standing in front of Ball Pellinger while mounted,
the ride HUD (centred, bottom 200px) sat directly on top of the talk prompt
(centred, bottom 190px). Both are centred key hints, but they are different
KINDS of message. The interact prompt is about the world in front of you and
changes as you move, so it keeps the centre stage. The ride and boat hints are
standing state about YOUR mount - they never change while you ride - so they
dock bottom-right in the corner stack with the teleport hint, where persistent
controls already live. Two hint kinds, two homes, no more stacking order to
argue about.

While in there, every floating key hint gains the word PRESS - "PRESS X" reads
as an instruction where a bare "X" reads as a label. Applied to the interact
prompt labels, the ride HUD, the boat hint, the teleport hint and the lock-on
hint, so the phrasing is one voice everywhere.
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


# ---- ride HUD: out of the centre, into the bottom-right corner stack -------
# Same chrome as the teleport hint below it: this is standing state, it should
# sit quietly in the corner, not shout from centre screen.
sub(
    '<div ref="{{ rideHudRef }}" style="position:absolute; bottom:200px; left:50%; transform:translateX(-50%); display:none; padding:8px 20px; background:rgba(10,11,8,0.74); border:1px solid #c8a24a; color:#e8c774; font-size:11px; letter-spacing:0.2em; z-index:5;">X — DISMOUNT · Z — TURBO OFF</div>',
    '<div ref="{{ rideHudRef }}" style="position:absolute; right:14px; bottom:44px; display:none; padding:6px 12px; background:rgba(10,11,8,0.62); border:1px solid #3a3f2c; color:#e8c774; font-family:\'IBM Plex Mono\',monospace; font-size:10px; letter-spacing:0.14em; text-align:right; z-index:5; pointer-events:none;">PRESS X — DISMOUNT · PRESS Z — TURBO ON</div>',
    tag='ride hud dock')

sub(
    "    if (el) el.textContent = 'X — DISMOUNT · Z — TURBO ' + (this.rideTurbo ? 'ON' : 'OFF');",
    "    if (el) el.textContent = 'PRESS X — DISMOUNT · PRESS Z — TURBO ' + (this.rideTurbo ? 'OFF' : 'ON');",
    tag='ride hud text')

# ---- boat hint: same corner stack, one slot above the ride hint ------------
# Riding past your moored boat can show both at once, so they get separate
# rungs instead of sharing one.
sub(
    "      bh.style.cssText = 'position:absolute;left:50%;bottom:172px;transform:translateX(-50%);padding:8px 20px;background:rgba(10,11,8,0.74);border:1px solid #c8a24a;color:#e8c774;font-size:11px;letter-spacing:0.2em;z-index:5;display:none;pointer-events:none;';",
    "      bh.style.cssText = 'position:absolute;right:14px;bottom:76px;padding:6px 12px;background:rgba(10,11,8,0.62);border:1px solid #3a3f2c;color:#e8c774;font-family:\"IBM Plex Mono\",monospace;font-size:10px;letter-spacing:0.14em;text-align:right;z-index:5;display:none;pointer-events:none;';",
    tag='boat hint dock')

sub(
    "      this._boatHint.textContent = this.boating ? 'B — STOW BOAT · X — HOP OUT' : (nearB ? 'B — STOW BOAT · SWIM TO THE HULL TO BOARD' : '');",
    "      this._boatHint.textContent = this.boating ? 'PRESS B — STOW BOAT · PRESS X — HOP OUT' : (nearB ? 'PRESS B — STOW BOAT · SWIM TO THE HULL TO BOARD' : '');",
    tag='boat hint text')

# ---- the rest of the floating hints say PRESS too --------------------------
sub("      hh.textContent = 'H — TELEPORT TO TOWN'; hh.style.display = 'none';",
    "      hh.textContent = 'PRESS H — TELEPORT TO TOWN'; hh.style.display = 'none';",
    tag='home hint')

sub('>E — UNTARGET</div>', '>PRESS E — UNTARGET</div>', tag='lock hint')

# startRide only flipped the hint visible; the text was whatever it last was.
# Refresh it on mount so the turbo line always names the action Z will take.
sub("      if (this.rideHudRef && this.rideHudRef.current) this.rideHudRef.current.style.display = 'block';",
    "      if (this.rideHudRef && this.rideHudRef.current) this.rideHudRef.current.style.display = 'block';\n      this.updateRideHud();",
    tag='startRide refresh')

# The template placeholder the prompt boots with, before updateHUD writes it.
sub('>F &nbsp;·&nbsp; TALK TO BALL PELLINGER</div>',
    '>PRESS F &nbsp;·&nbsp; TALK TO BALL PELLINGER</div>', tag='prompt placeholder')

# Every interact label: bank, sack, Margaret, Fenwick, Ball, smelt x2, forge,
# sheep, plus the three close-the-window labels from bestInteract. One voice.
before = s.count("'F - ")
assert before == 12, 'expected 12 interact labels, found %d' % before
s = s.replace("'F - ", "'PRESS F - ")
n += 1

io.open(SRC, 'w', encoding='utf-8').write(s)
print('45_key_hints: %d edits applied' % n)
