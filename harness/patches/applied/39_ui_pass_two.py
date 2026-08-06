#!/usr/bin/env python3
"""UI pass two (patch 39): layout fallout from pass one. Edits /tmp/game-src.html.

Measured on a 1180x700 window, which is the small end of what anyone plays on:

  - skills panel  scrollHeight 716 vs 539 visible  -> two columns
  - bank panel    scrollHeight 667 vs 539 visible  -> vault and pack side by side
  - the action bar caption sat under the slots, where the bottom of the screen
    clipped it and the coord/FPS stamp collided with it

Plus two rules that stop the whole class of problem coming back: the header and
the control legend are sticky, so no matter how short the window gets, the
title, the close button and the list of what every control does stay on screen.
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


# ---------------------------------------------------- sticky header + legend
# A window can be taller than the screen. When it is, the two things you must
# never lose are the way out (the header, which carries the close button) and
# the list of what the controls do. Pin both.
sub(
    "  panelHeadCss() { return 'display:flex;align-items:center;gap:10px;border-bottom:1px solid #2f3426;padding-bottom:9px;flex-wrap:wrap;'; }",
    "  panelHeadCss() { return 'display:flex;align-items:center;gap:10px;border-bottom:1px solid #2f3426;padding:2px 0 9px;flex-wrap:wrap;' +\n"
    "    'position:sticky;top:-15px;z-index:2;background:rgba(12,13,9,0.98);'; }",
    tag='sticky head')

sub(
    "  panelLegendCss() { return 'border-top:1px solid #2f3426;padding-top:8px;margin-top:2px;font-size:9.5px;line-height:1.75;color:#7d8a63;letter-spacing:0.05em;'; }",
    "  panelLegendCss() { return 'border-top:1px solid #2f3426;padding:8px 0 2px;margin-top:auto;font-size:9.5px;line-height:1.75;' +\n"
    "    'color:#7d8a63;letter-spacing:0.05em;position:sticky;bottom:-14px;z-index:2;background:rgba(12,13,9,0.98);'; }",
    tag='sticky legend')


# --------------------------------------------------------- skills: 2 columns
# Eight skills stacked ran 716px tall against 539px of window. Two columns is
# 4 rows, and it reads better anyway: combat down the left, gathering down the
# right, in the order SKILL_INFO already lists them.
sub("    const P = mk2(this.panelCss('560px'));",
    "    const P = mk2(this.panelCss('660px'));", tag='skills width')

sub("    this._skRowsEl = mk2('display:flex;flex-direction:column;gap:9px;');",
    "    this._skRowsEl = mk2('display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:8px;align-content:start;');",
    tag='skills grid')


# ----------------------------------------- bank: vault and pack side by side
# Stacked, the bank ran 667px tall. Side by side is the shape every player
# already knows from every other bank in the genre, and it halves the height.
sub("    const P = mk('div', this.panelCss('740px'));\n    P.addEventListener('contextmenu', e => e.preventDefault());\n    const head = mk('div', this.panelHeadCss());\n    head.appendChild(mk('div', this.panelTitleCss(), 'BANK OF HOLLOWREST'));",
    "    const P = mk('div', this.panelCss('880px'));\n    P.addEventListener('contextmenu', e => e.preventDefault());\n    const head = mk('div', this.panelHeadCss());\n    head.appendChild(mk('div', this.panelTitleCss(), 'BANK OF HOLLOWREST'));",
    tag='bank width')

sub(
    """    P.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin-top:6px;', 'THE VAULT'));
    this.bankGridEl = mk('div', 'display:grid;grid-template-columns:repeat(9,52px);gap:6px;justify-content:center;min-height:112px;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:10px;');
    P.appendChild(this.bankGridEl);
    P.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin-top:6px;', 'YOUR PACK'));
    // Seven across, four down - the SAME shape the pack panel uses. Showing the
    // same 28 slots as 14x2 here meant the muscle memory did not carry over.
    this.bankPackEl = mk('div', 'display:grid;grid-template-columns:repeat(7,52px);gap:6px;justify-content:center;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:10px;');
    P.appendChild(this.bankPackEl);""",
    """    // Vault on the left, what you are carrying on the right, so a deposit is
    // a glance from one side to the other rather than a scroll.
    const cols = mk('div', 'display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;');
    const left = mk('div', 'flex:1 1 460px;min-width:0;');
    left.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin-bottom:5px;', 'THE VAULT'));
    this.bankGridEl = mk('div', 'display:grid;grid-template-columns:repeat(auto-fill,46px);gap:6px;justify-content:start;' +
      'min-height:250px;max-height:calc(100vh - 430px);overflow-y:auto;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:10px;');
    left.appendChild(this.bankGridEl);
    const right = mk('div', 'flex:0 0 auto;');
    right.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin-bottom:5px;', 'YOUR PACK — 28 SLOTS'));
    // Seven across, four down - the SAME shape the pack panel uses. Showing the
    // same 28 slots as 14x2 here meant the muscle memory did not carry over.
    this.bankPackEl = mk('div', 'display:grid;grid-template-columns:repeat(7,46px);gap:6px;justify-content:center;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:10px;');
    right.appendChild(this.bankPackEl);
    cols.appendChild(left); cols.appendChild(right);
    P.appendChild(cols);""",
    tag='bank columns')

# Slots follow the grid down from 52 to 46 so both sides line up.
sub("      d.style.cssText = 'width:52px;height:52px;background:#15170f;border:1.5px solid #3a3f2c;display:flex;align-items:center;justify-content:center;position:relative;cursor:pointer;transition:border-color 110ms;';",
    "      d.style.cssText = 'width:46px;height:46px;background:#15170f;border:1.5px solid #3a3f2c;display:flex;align-items:center;justify-content:center;position:relative;cursor:pointer;transition:border-color 110ms;';",
    tag='bank vault slot size')
sub("      d.style.cssText = 'width:52px;height:52px;background:#15170f;border:1.5px solid #2c2f24;display:flex;align-items:center;justify-content:center;position:relative;transition:border-color 110ms;cursor:' + (c ? 'pointer' : 'default') + ';';",
    "      d.style.cssText = 'width:46px;height:46px;background:#15170f;border:1.5px solid #2c2f24;display:flex;align-items:center;justify-content:center;position:relative;transition:border-color 110ms;cursor:' + (c ? 'pointer' : 'default') + ';';",
    tag='bank pack slot size')

# The empty-vault message spanned a fixed 9 columns that no longer exist.
sub("      d.style.cssText = 'grid-column:1/-1;text-align:center;color:#5f6b4a;font-size:11px;letter-spacing:0.1em;padding:30px 0;';",
    "      d.style.cssText = 'grid-column:1/-1;text-align:center;color:#5f6b4a;font-size:11px;letter-spacing:0.1em;padding:90px 0;';",
    tag='bank empty msg')


# --------------------------------------------- action bar: caption above slots
# The caption is a legend FOR the bar, and underneath it was both clipped by the
# bottom of the screen and sharing that strip with the coord/FPS stamp. Reversing
# the column puts it above the slots, where there is room and nothing else lives.
sub(
    '<div style="position:absolute; bottom:22px; left:50%; transform:translateX(-50%); display:flex; flex-direction:column; align-items:center; gap:6px; pointer-events:none; z-index:75;">',
    '<div style="position:absolute; bottom:26px; left:50%; transform:translateX(-50%); display:flex; flex-direction:column-reverse; align-items:center; gap:7px; pointer-events:none; z-index:75;">',
    tag='bar column reverse')

# It is a legend, so it should read like the ones inside the panels.
sub(
    '<div style="font-size:9px; letter-spacing:0.12em; color:#5a6349; font-family:\'IBM Plex Mono\',monospace; text-shadow:0 2px 4px #000;">SCROLL SWAPS WEAPON &nbsp;·&nbsp; RMB GUARDS &nbsp;·&nbsp; <span ref="{{ spellNameRef }}" style="color:#ffa15c;">Fire</span> &nbsp;<span style="color:#5a6349;">HOLD Q</span></div>',
    '<div style="font-size:9.5px; letter-spacing:0.1em; color:#7d8a63; font-family:IBM Plex Mono,monospace; text-shadow:0 2px 4px #000; background:rgba(10,11,8,0.62); border:1px solid #2f3426; padding:4px 12px;"><span style="color:#b3c29a; font-weight:700;">1-6</span> equip &nbsp;·&nbsp; <span style="color:#b3c29a; font-weight:700;">SCROLL</span> swap weapon &nbsp;·&nbsp; <span style="color:#b3c29a; font-weight:700;">RMB</span> guard &nbsp;·&nbsp; <span style="color:#b3c29a; font-weight:700;">HOLD Q</span> spell <span ref="{{ spellNameRef }}" style="color:#ffa15c;">Fire</span></div>',
    tag='bar caption')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('39_ui_pass_two: %d edits applied' % n)
