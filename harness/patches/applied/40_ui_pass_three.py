#!/usr/bin/env python3
"""UI pass three: the last two collisions. Edits /tmp/game-src.html.

  - The coord/FPS stamp ran 590px wide on one line and clipped the corner of
    the action bar. Three short lines instead: it now ends well left of the
    bar at any window size, and it reads faster on a screenshot.
  - The bank header carried title, gold, search and three buttons on one row,
    which wrapped BANK OF HOLLOWREST onto two lines. The search box is a vault
    filter, so it moves down to sit with the vault it filters.
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


# ------------------------------------------------- debug stamp: three lines
sub(
    """        this._coordHud.innerHTML =
          '<span style="color:' + fcol + ';font-weight:700">' + fps + ' FPS  ' + ftms.toFixed(1) + ' ms</span>   ' +
          'X ' + f(m.x, 1) + '   Z ' + f(m.z, 1) + '   Y ' + f(gy + m.y, 1) +
          '   YAW ' + f(this.yaw, 3) + '   PITCH ' + f(this.pitch, 2) +
          (zn ? ('   ' + zn) : '');""",
    """        // Three short lines, not one long one: on one line this box ran most
        // of the width of the screen and clipped the corner of the action bar.
        this._coordHud.innerHTML =
          '<span style="color:' + fcol + ';font-weight:700">' + fps + ' FPS   ' + ftms.toFixed(1) + ' ms</span>' +
          (zn ? ('<span style="color:#5f6b4a">   ' + zn + '</span>') : '') + '\\n' +
          'X ' + f(m.x, 1) + '   Z ' + f(m.z, 1) + '   Y ' + f(gy + m.y, 1) + '\\n' +
          'YAW ' + f(this.yaw, 3) + '   PITCH ' + f(this.pitch, 2);""",
    tag='coord 3 lines')

# The F3 readout stacks above it, so give the taller box room.
sub("      d.style.cssText = 'position:fixed;left:12px;bottom:46px;z-index:' + this.Z.debug + ';background:rgba(10,11,8,0.8);' +",
    "      d.style.cssText = 'position:fixed;left:12px;bottom:82px;z-index:' + this.Z.debug + ';background:rgba(10,11,8,0.8);' +",
    tag='perf hud lift')


# --------------------------------------- bank: search moves down to the vault
sub(
    """    this.bankSearch.style.cssText = 'flex:1;min-width:130px;background:#15170f;border:1px solid #3a3f2c;color:#d8d4c6;padding:7px 10px;font-family:IBM Plex Mono,monospace;font-size:11px;letter-spacing:0.08em;outline:none;';""",
    """    this.bankSearch.style.cssText = 'width:100%;box-sizing:border-box;background:#15170f;border:1px solid #3a3f2c;color:#d8d4c6;padding:7px 10px;font-family:IBM Plex Mono,monospace;font-size:11px;letter-spacing:0.08em;outline:none;margin-bottom:6px;';""",
    tag='bank search css')

# Out of the header (where it squeezed the title onto two lines) and into the
# vault column, directly above the grid it filters.
sub(
    "    head.appendChild(this.bankSearch);\n    const btn = (label, fn, gold, tip)",
    "    const btn = (label, fn, gold, tip)",
    tag='bank search out of head')

sub(
    "    left.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin-bottom:5px;', 'THE VAULT'));",
    "    left.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin-bottom:5px;', 'THE VAULT'));\n"
    "    left.appendChild(this.bankSearch);",
    tag='bank search into vault')

# Long window titles get a line of their own rather than wrapping mid-name.
sub("  panelTitleCss() { return 'font-family:Cinzel,serif;font-size:15px;letter-spacing:0.2em;color:#e8c774;flex:1;min-width:150px;'; }",
    "  panelTitleCss() { return 'font-family:Cinzel,serif;font-size:15px;letter-spacing:0.18em;color:#e8c774;flex:1 1 auto;white-space:nowrap;'; }",
    tag='panel title nowrap')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('40_ui_pass_three: %d edits applied' % n)
