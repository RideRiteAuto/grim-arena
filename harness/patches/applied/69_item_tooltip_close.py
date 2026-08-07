#!/usr/bin/env python3
"""Patch 69: the item info tooltip no longer gets stuck on screen after you
close the pack or the bank, and the bank's hover text gets upgraded to the
same rich stats box the pack and Fenwick's shop already use.

Kevin's report: hover an item so its little info box pops up, then hit
Tab or Escape to close the pack/bank/shop window -- the window closes but
the info box stays floating on screen.

Root cause, confirmed per window:

- PACK: the tooltip element (this.invTipEl) is appended straight to
  document.body, a sibling of the pack panel, not a child of it. It is
  only hidden on a pointermove/pointerleave over the panel. Closing the
  panel just sets its own display to none -- nothing tells invTipEl to
  hide, so if you were hovering an item at the moment you pressed
  Tab/Escape, the box is still there with no panel under it.

- BANK: never had this box at all. Its item cells only set the native
  browser `title` attribute, which does not carry stats and is not
  reliably dismissed by a keypress that hides the element under it in
  every browser, which reads as the exact same stuck-tooltip bug Kevin is
  describing. Fixed by moving the bank onto the SAME shared tooltip
  element and renderer the shop already uses (this.shopTipEl / shopTip()),
  so it now shows the real stats box instead of plain title text, and
  picks up the same reliable hide-on-close behavior for free.

- SHOP: already correct. closeShop() calls closeShopMenus(), which hides
  shopTipEl, on every close path (Escape, F, the X button, clicking the
  dimmer). No change needed here, just double checked it stays that way.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 69 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. pack: hide the item tooltip the moment the pack closes ------------
sub(
    """    else {
      this.closeInvMenus();
      if (this.sackWinId) this.closeSackWin();
      this.uiClosedHandback();
      if (this.started && this.mode === 'ai') this.requestLock();
    }
    this.sfx('switch');
  }

  buildInvPanel() {""",
    """    else {
      this.closeInvMenus();
      // The tooltip lives outside the panel (appended straight to body so
      // it can float above everything), so closing the panel does not
      // touch it on its own. If you were mid-hover when you hit Tab/Escape
      // it would otherwise be left floating with no window under it.
      if (this.invTipEl) this.invTipEl.style.display = 'none';
      if (this.sackWinId) this.closeSackWin();
      this.uiClosedHandback();
      if (this.started && this.mode === 'ai') this.requestLock();
    }
    this.sfx('switch');
  }

  buildInvPanel() {""",
    tag='toggleWallet hides invTipEl on close')

# ---- 2. bank: hide the (now shared) item tooltip the moment it closes -----
sub(
    """  closeBank() {
    this.bankOpen = false;
    if (this.bankWinEl) this.bankWinEl.style.display = 'none';
    if (!this.walletOpen && this.started && this.mode === 'ai') { this.uiClosedHandback(); this.requestLock(); }
    this.sfx('switch');
  }""",
    """  closeBank() {
    this.bankOpen = false;
    if (this.bankWinEl) this.bankWinEl.style.display = 'none';
    // Bank items now hover with the same shared tip element Fenwick's shop
    // uses (see renderBank()) -- hide it here for the same reason the pack
    // hides invTipEl above, so a mid-hover Escape/F never leaves it floating.
    if (this.shopTipEl) this.shopTipEl.style.display = 'none';
    if (!this.walletOpen && this.started && this.mode === 'ai') { this.uiClosedHandback(); this.requestLock(); }
    this.sfx('switch');
  }""",
    tag='closeBank hides shopTipEl on close')

# ---- 3. shared stats-tooltip HTML builder, so the bank can show the same
#         name + stats box the pack already builds inline ------------------
sub(
    """  // ---- rendering ---------------------------------------------------
  slotHTML(item, qty) {
    const badge = (qty > 1) ? '<div style="position:absolute;right:3px;bottom:2px;font-size:9px;font-weight:700;color:#e8c774;text-shadow:0 1px 2px #000;pointer-events:none;">' + (qty > 9999 ? Math.floor(qty / 1000) + 'K' : qty) + '</div>' : '';
    return '<div style="width:34px;height:34px;display:flex;align-items:center;justify-content:center;pointer-events:none;">' + this.itemIcon(item) + '</div>' + badge;
  }""",
    """  // ---- rendering ---------------------------------------------------
  slotHTML(item, qty) {
    const badge = (qty > 1) ? '<div style="position:absolute;right:3px;bottom:2px;font-size:9px;font-weight:700;color:#e8c774;text-shadow:0 1px 2px #000;pointer-events:none;">' + (qty > 9999 ? Math.floor(qty / 1000) + 'K' : qty) + '</div>' : '';
    return '<div style="width:34px;height:34px;display:flex;align-items:center;justify-content:center;pointer-events:none;">' + this.itemIcon(item) + '</div>' + badge;
  }
  // Name + stats box, the same content the pack tooltip builds, plus a
  // trailing hint line the caller supplies (the bank uses this for its
  // withdraw/deposit hints instead of a plain browser title tooltip).
  itemTipHtml_(item, qty, hint) {
    const def = this.itemDef(item);
    let html = '<div style="color:#e8c774;letter-spacing:0.08em;">' + item + (qty > 1 ? ' ×' + qty.toLocaleString('en-US') : '') + '</div>';
    if (def && def.slot) {
      const st = def.stats, rows = [['ATT', st.att], ['STR', st.str], ['DEF', st.def], ['MAG', st.mag], ['RNG', st.rng], ['CRIT', (st.crit || 0) && st.crit + '%']].filter(p => p[1]);
      html += '<div style="color:#7d8a63;">' + def.slot + (def.hands === 2 ? ' · TWO-HANDED' : '') + '</div>';
      html += rows.map(p => '<span style="color:#8fbf6a;">' + p[0] + ' +' + p[1] + '</span>').join(' &nbsp;') || '';
    } else if (def) {
      html += (this.fenBuys(item)
        ? '<div style="color:#7d8a63;">FENWICK PAYS ' + this.fenPays(item) + 'G EACH</div>'
        : '<div style="color:#7d8a63;">FENWICK DOES NOT BUY THIS</div>');
    }
    if (hint) html += '<div style="color:#5a6349;margin-top:3px;">' + hint + '</div>';
    return html;
  }""",
    tag='shared itemTipHtml_ helper')

# ---- 4. bank vault grid: rich tooltip instead of a native title -----------
sub(
    """      d.innerHTML = this.slotHTML(c.item, c.qty);
      d.title = c.item + ' ×' + c.qty.toLocaleString('en-US') + '  —  click withdraw 1, shift+click 5, right-click all';
      d.onmouseenter = () => { d.style.borderColor = '#c8a24a'; };
      d.onmouseleave = () => { d.style.borderColor = '#3a3f2c'; };
      d.addEventListener('pointerup', (e) => {""",
    """      d.innerHTML = this.slotHTML(c.item, c.qty);
      const vaultTip = this.itemTipHtml_(c.item, c.qty, 'CLICK WITHDRAW 1, SHIFT+CLICK 5, RIGHT-CLICK ALL');
      d.onmouseenter = () => { d.style.borderColor = '#c8a24a'; };
      d.onmouseleave = () => { d.style.borderColor = '#3a3f2c'; this.shopTip(null); };
      d.addEventListener('pointermove', (e) => this.shopTip(vaultTip, e.clientX, e.clientY));
      d.addEventListener('pointerup', (e) => {""",
    tag='bank vault cells use shopTip')

# ---- 5. bank pack column: same treatment -----------------------------------
sub(
    """        d.innerHTML = this.slotHTML(c.item, c.qty);
        d.title = c.item + ' ×' + c.qty.toLocaleString('en-US') + '  —  click deposits the stack, shift+click deposits one';
        d.onmouseenter = () => { d.style.borderColor = '#c8a24a'; };
        d.onmouseleave = () => { d.style.borderColor = '#2c2f24'; };
        const idx = i;""",
    """        d.innerHTML = this.slotHTML(c.item, c.qty);
        const packTip = this.itemTipHtml_(c.item, c.qty, 'CLICK DEPOSITS THE STACK, SHIFT+CLICK DEPOSITS ONE');
        d.onmouseenter = () => { d.style.borderColor = '#c8a24a'; };
        d.onmouseleave = () => { d.style.borderColor = '#2c2f24'; this.shopTip(null); };
        d.addEventListener('pointermove', (e) => this.shopTip(packTip, e.clientX, e.clientY));
        const idx = i;""",
    tag='bank pack-column cells use shopTip')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('69_item_tooltip_close: %d edits applied (1-5)' % n)
