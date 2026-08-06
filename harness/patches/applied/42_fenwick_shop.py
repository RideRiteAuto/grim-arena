#!/usr/bin/env python3
"""Patch 42: Fenwick becomes a real shop. Edits /tmp/game-src.html.

The old trader screen was a spreadsheet: four fixed rows he sells, a list of
the handful of things he deigns to buy, one SELL 1 button each. This replaces
it with a store in the RuneScape general-store mould:

  - Two inventory grids side by side: HIS STOCK on the left, YOUR PACK on the
    right (the same 7x4 the pack panel and the bank use, same slot visuals).
  - Click his stock to buy one, right-click for BUY 1 / 5 / 10 with totals.
    Click your item to sell one, right-click for SELL 1 / 5 / 10 / ALL with
    totals. Hover anything for its price before you commit.
  - He buys nearly ANYTHING with a value now, not just pelts and ore. Gold is
    the one thing he will not buy.
  - What players sell him goes ON THE SHELF, with a quantity, for anyone to
    buy. Stock is SHARED across every player and survives reload: it lives in
    Supabase behind the same security-definer RPC pattern as accounts and the
    world-host directory (grim_shop_state / grim_shop_sell / grim_shop_buy,
    atomic, so two buyers cannot both win the last unit). No backend reachable
    means a per-browser fallback with the same rules, so nothing breaks.
  - The more he holds of an item, the less he pays for the next one:
    pay(stock) = max(35% of base, base * 0.97^stock). Base prices for the old
    sell list are UNCHANGED at zero stock, so the quest economy is untouched.
    He also works stock off at 1 unit per 10 minutes (lazily, server-side),
    so a glut clears and prices recover on their own.
  - Resale of player goods is fixed at ~135% of base pay: always a spread, and
    a mis-sold item can be bought straight back, which is the natural undo.
  - Big purchases get a confirm screen: any buy totalling 500g or more, and
    any multi-buy of an expensive unit. No more accidental three hollow plates.

The four base wares (jerkin, cuirass, plate, tome) stay unlimited - infinity
badge - so other players can never buy them out.
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


# ============================================================ open/close + core
sub(
    """  openShop() {
    this.shopOpen = true;
    this.sfx('switch');
    if (document.exitPointerLock) { try { document.exitPointerLock(); } catch (e) {} }
    if (!this.shopEl) {
      const d = document.createElement('div');
      d.style.cssText = this.panelCss('min(700px,94vw)');
      document.body.appendChild(d); this.shopEl = d;
    }
    this.shopEl.style.display = 'flex';
    this.renderShop();
  }
  closeShop() {
    this.shopOpen = false;
    if (this.shopEl) this.shopEl.style.display = 'none';
    this.requestLock();
  }""",
    """  openShop() {
    this.shopOpen = true;
    this.sfx('switch');
    if (document.exitPointerLock) { try { document.exitPointerLock(); } catch (e) {} }
    if (!this.shopEl) {
      const d = document.createElement('div');
      d.style.cssText = this.panelCss('min(880px,96vw)');
      d.addEventListener('contextmenu', e => e.preventDefault());
      document.body.appendChild(d); this.shopEl = d;
    }
    this.shopEl.style.display = 'flex';
    this.renderShop();
    // Stock is shared with every other player, so read it fresh on open and
    // keep it fresh while the window is up. Each sync re-renders on arrival.
    this.shopSync();
    clearInterval(this._fenIv);
    this._fenIv = setInterval(() => { if (this.shopOpen) this.shopSync(); }, 12000);
  }
  closeShop() {
    this.shopOpen = false;
    clearInterval(this._fenIv); this._fenIv = null;
    this.closeShopMenus();
    if (this.shopEl) this.shopEl.style.display = 'none';
    this.requestLock();
  }

  // ------------------------------------------------ Fenwick's economy
  // One base number per item and three rules on top of it. The base for the
  // old sell list is EXACTLY the old price, so day-one earnings are untouched;
  // everything else derives from the item's def.value; the four base wares
  // derive from their shop price so selling armour back is not a robbery.
  fenWare(id) { for (const w of this.shopStock()) if (w.k === id) return w; return null; }
  fenBase(id) {
    const o = this.sellPrices()[id]; if (o) return o;
    const w = this.fenWare(id); if (w) return Math.max(1, Math.round(w.p * 0.35));
    const d = this.itemDef(id);
    return d ? Math.max(1, Math.round((d.value || 1) * 0.55)) : 0;
  }
  // What he pays for the NEXT unit, given how many he already holds. The
  // RuneScape rule: 3 percent off per unit in stock, floored at 35 percent,
  // so flooding him with pelts stops paying and the price recovers as his
  // 10-minute restock drain works the pile off.
  fenPays(id, atStock) {
    const b = this.fenBase(id); if (!b) return 0;
    const st = (atStock === undefined) ? ((this.fenStock && this.fenStock[id]) || 0) : atStock;
    return Math.max(Math.floor(b * 0.35), Math.round(b * Math.pow(0.97, st)));
  }
  // What a player-sold item resells for: fixed at ~135 percent of base so the
  // spread never inverts, and a mis-sold item can be bought straight back.
  fenSellsFor(id) {
    const w = this.fenWare(id); if (w) return w.p;
    const b = this.fenBase(id);
    return Math.max(this.fenPays(id, 0) + 1, Math.round(b * 1.35));
  }
  // Total for selling n: each unit is priced against the stock it lands on,
  // exactly like feeding them through one at a time.
  fenQuote(id, nUnits) {
    const start = (this.fenStock && this.fenStock[id]) || 0;
    let t = 0;
    for (let i = 0; i < nUnits; i++) t += this.fenPays(id, start + i);
    return t;
  }
  fenBuys(id) { return id !== 'GOLD CROWNS' && this.fenBase(id) > 0; }

  // ------------------------------------------------ shared stock plumbing
  // Cloud first (same Supabase the accounts and the world-host directory
  // use), per-browser fallback with identical rules when it is unreachable.
  // The fallback applies the same 1-per-10-minutes drain on load, stamped
  // per item, so a glut clears offline exactly like it does online.
  async shopSync() {
    const r = await this.dirRpc('grim_shop_state', {});
    if (r && r.data && !r.missing) { this.fenCloud = true; this.fenStock = r.data || {}; }
    else { this.fenCloud = false; this.fenStock = this.fenLocalLoad(); }
    if (this.shopOpen) this.renderShop();
  }
  fenLocalLoad() {
    let raw = {}; try { raw = JSON.parse(localStorage.getItem('grim-fen-stock') || '{}'); } catch (e) { raw = {}; }
    const now = Date.now(), out = {}, keep = {};
    for (const k in raw) {
      const e = raw[k]; if (!e || !(e.q > 0)) continue;
      const steps = Math.floor((now - (e.t || now)) / 600000);
      const q = Math.max(0, e.q - Math.max(0, steps));
      if (q > 0) { out[k] = q; keep[k] = { q: q, t: (e.t || now) + Math.max(0, steps) * 600000 }; }
    }
    try { localStorage.setItem('grim-fen-stock', JSON.stringify(keep)); } catch (e) {}
    return out;
  }
  fenLocalSet(id, q) {
    let raw = {}; try { raw = JSON.parse(localStorage.getItem('grim-fen-stock') || '{}'); } catch (e) { raw = {}; }
    if (q > 0) raw[id] = { q: q, t: Date.now() }; else delete raw[id];
    try { localStorage.setItem('grim-fen-stock', JSON.stringify(raw)); } catch (e) {}
  }

  // ------------------------------------------------ transactions
  // Sell: price the batch against known stock, commit the stock change, THEN
  // move items and gold. On the cloud path the RPC answer is authoritative
  // for the new stock; a dead backend degrades to the local ledger mid-flight
  // rather than eating the sale.
  async fenSell(id, nWant) {
    if (!this.fenBuys(id)) { this.uiNote('FENWICK DOES NOT BUY THAT', '', 1800); return; }
    const n = Math.min(nWant, this.invCount(id));
    if (n < 1) return;
    const pay = this.fenQuote(id, n);
    if (!this.takeItem(id, n)) return;
    this.addItem('GOLD CROWNS', pay);
    this.fenStock = this.fenStock || {};
    this.fenStock[id] = (this.fenStock[id] || 0) + n;
    if (this.fenCloud) {
      const r = await this.dirRpc('grim_shop_sell', { i: id, n: n });
      if (r && r.data && r.data.ok) this.fenStock[id] = r.data.qty;
      else { this.fenCloud = false; this.fenLocalSet(id, this.fenStock[id]); }
    } else this.fenLocalSet(id, this.fenStock[id]);
    this.sfx('pickup');
    this.uiNote('SOLD ' + n + ' × ' + id, '+' + pay.toLocaleString('en-US') + 'G' + (n > 1 ? ' · PRICED PER UNIT AS HIS STOCK GREW' : ''), 2200);
    this.renderShop();
  }
  // Buy: gold, pack space and stock all clamp BEFORE money moves. Expensive
  // totals go through the confirm screen. On the cloud path the stock
  // decrement is atomic server-side, so losing a race costs a message, never
  // gold: the RPC answers first and only a yes moves anything.
  fenBuy(id, nWant) {
    const ware = this.fenWare(id);
    const unit = this.fenSellsFor(id);
    const gold = this.invCount('GOLD CROWNS');
    let n = nWant;
    if (ware) {
      const owned = this.hasItem(id) || (id === 'TOME OF STORMS' && this.knowsStorm());
      if (owned) { this.uiNote('YOU ALREADY HAVE ONE', id === 'TOME OF STORMS' ? 'THE STORM IS ALREADY YOURS' : 'ONE IS ALL ANYONE NEEDS', 2000); return; }
      n = 1;                                   // armour and tomes: one each
    } else {
      n = Math.min(n, (this.fenStock && this.fenStock[id]) || 0);
      if (n < 1) { this.uiNote('OUT OF STOCK', 'ANOTHER PLAYER MAY HAVE BOUGHT IT', 2000); this.shopSync(); return; }
    }
    n = Math.min(n, this.canAccept(id, n));
    if (n < 1) { this.packFullNote(); return; }
    while (n > 0 && unit * n > gold) n--;
    if (n < 1) { this.uiNote('NOT ENOUGH GOLD', unit.toLocaleString('en-US') + 'G EACH · YOU HAVE ' + gold.toLocaleString('en-US') + 'G', 2200); return; }
    const cost = unit * n;
    const go = () => this.fenBuyCommit(id, n, unit, !!ware);
    // The confirm gate: a misclick may not cost a fortune. 500g total, or
    // more than one of anything expensive, has to be meant.
    if (cost >= 500 || (n > 1 && unit >= 250)) {
      this.shopConfirm('BUY ' + n + ' × ' + id + '?',
        cost.toLocaleString('en-US') + 'G TOTAL · YOU HAVE ' + gold.toLocaleString('en-US') + 'G', go);
    } else go();
  }
  async fenBuyCommit(id, n, unit, isWare) {
    if (!isWare) {
      if (this.fenCloud) {
        const r = await this.dirRpc('grim_shop_buy', { i: id, n: n });
        if (!(r && r.data)) this.fenCloud = false;
        else if (!r.data.ok) {
          this.fenStock[id] = r.data.qty || 0;
          this.uiNote('TOO SLOW', 'ANOTHER PLAYER GOT THERE FIRST · ' + (r.data.qty || 0) + ' LEFT', 2400);
          this.renderShop(); return;
        } else this.fenStock[id] = r.data.qty;
      }
      if (!this.fenCloud) {
        const have = (this.fenStock && this.fenStock[id]) || 0;
        if (have < n) { this.uiNote('OUT OF STOCK', '', 1800); this.renderShop(); return; }
        this.fenStock[id] = have - n;
        this.fenLocalSet(id, this.fenStock[id]);
      }
      if (this.fenStock[id] <= 0) delete this.fenStock[id];
    }
    if (!this.takeItem('GOLD CROWNS', unit * n)) { this.renderShop(); return; }
    this.addItem(id, n);
    this.sfx('win');
    this.uiNote('BOUGHT ' + n + ' × ' + id, '-' + (unit * n).toLocaleString('en-US') + 'G', 2000);
    this.renderShop();
  }

  // ------------------------------------------------ menus, confirm, tooltip
  openShopMenu(x, y, side, id) {
    this.closeShopMenus();
    const M = document.createElement('div');
    M.style.cssText = 'position:fixed;z-index:' + this.Z.pop + ';background:rgba(12,13,9,0.98);border:1px solid #c8a24a;min-width:190px;font-family:IBM Plex Mono,monospace;font-size:11px;box-shadow:0 8px 30px rgba(0,0,0,0.7);';
    const add = (label, right, fn) => {
      const r = document.createElement('div');
      r.style.cssText = 'display:flex;justify-content:space-between;gap:14px;padding:8px 14px;cursor:pointer;letter-spacing:0.06em;color:#d8d4c6;border-bottom:1px solid #26281f;';
      r.innerHTML = '<span>' + label + '</span><span style="color:#c8a24a">' + right + '</span>';
      r.onmouseenter = () => r.style.background = '#26281f';
      r.onmouseleave = () => r.style.background = 'transparent';
      r.onclick = () => { this.closeShopMenus(); fn(); };
      M.appendChild(r);
    };
    if (side === 'pack') {
      const have = this.invCount(id);
      for (const q of [1, 5, 10]) if (have >= q) add('SELL ' + q, this.fenQuote(id, q).toLocaleString('en-US') + 'G', () => this.fenSell(id, q));
      if (have > 1) add('SELL ALL (' + have + ')', this.fenQuote(id, have).toLocaleString('en-US') + 'G', () => this.fenSell(id, have));
      if (!M.childNodes.length) add('SELL 1', this.fenQuote(id, 1) + 'G', () => this.fenSell(id, 1));
    } else {
      const ware = this.fenWare(id);
      const unit = this.fenSellsFor(id);
      const stock = ware ? Infinity : ((this.fenStock && this.fenStock[id]) || 0);
      for (const q of (ware ? [1] : [1, 5, 10])) {
        if (q > stock) continue;
        add('BUY ' + q, (unit * q).toLocaleString('en-US') + 'G', () => this.fenBuy(id, q));
      }
    }
    M.style.left = Math.min(innerWidth - 220, x) + 'px';
    M.style.top = Math.min(innerHeight - 200, y) + 'px';
    document.body.appendChild(M);
    this.shopMenuEl = M;
    setTimeout(() => addEventListener('pointerdown', this._shopMenuCloser = (ev) => { if (!M.contains(ev.target)) this.closeShopMenus(); }), 0);
  }
  closeShopMenus() {
    if (this.shopMenuEl) { try { document.body.removeChild(this.shopMenuEl); } catch (e) {} this.shopMenuEl = null; }
    if (this._shopMenuCloser) { removeEventListener('pointerdown', this._shopMenuCloser); this._shopMenuCloser = null; }
    if (this.shopConfirmEl) { this.shopConfirmEl.style.display = 'none'; }
    if (this.shopTipEl) this.shopTipEl.style.display = 'none';
  }
  shopConfirm(main, sub2, onYes) {
    if (!this.shopConfirmEl) {
      const d = document.createElement('div');
      d.style.cssText = 'position:fixed;inset:0;z-index:' + this.Z.pop + ';display:none;align-items:center;justify-content:center;background:rgba(5,6,4,0.6);';
      const box = document.createElement('div');
      box.style.cssText = 'width:340px;max-width:90vw;padding:18px 20px;background:rgba(12,13,9,0.98);border:1px solid #c8a24a;border-top:2px solid #c8a24a;font-family:IBM Plex Mono,monospace;text-align:center;box-shadow:0 18px 70px rgba(0,0,0,0.8);';
      d.appendChild(box); document.body.appendChild(d);
      this.shopConfirmEl = d; this._fenCfBox = box;
    }
    const box = this._fenCfBox;
    box.innerHTML = '<div style="font-size:13px;letter-spacing:0.12em;color:#e8c774;font-weight:700;">' + main + '</div>' +
      '<div style="font-size:11px;color:#b3afa0;margin-top:7px;letter-spacing:0.06em;line-height:1.6;">' + sub2 + '</div>';
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:10px;margin-top:14px;';
    const mkB = (label, gold, fn) => {
      const b = document.createElement('button');
      b.style.cssText = this.panelBtnCss(gold) + 'flex:1;padding:11px 0;font-size:11px;';
      b.textContent = label; b.onclick = fn; return b;
    };
    row.appendChild(mkB('CONFIRM', true, () => { this.shopConfirmEl.style.display = 'none'; onYes(); }));
    row.appendChild(mkB('CANCEL', false, () => { this.shopConfirmEl.style.display = 'none'; }));
    box.appendChild(row);
    this.shopConfirmEl.style.display = 'flex';
  }
  shopTip(html, x, y) {
    if (!this.shopTipEl) {
      const t = document.createElement('div');
      t.style.cssText = 'position:fixed;display:none;z-index:' + this.Z.pop + ';background:rgba(12,13,9,0.98);border:1px solid #c8a24a;padding:8px 11px;font-family:IBM Plex Mono,monospace;font-size:10.5px;color:#d8d4c6;pointer-events:none;max-width:250px;line-height:1.6;box-shadow:0 8px 30px rgba(0,0,0,0.7);';
      document.body.appendChild(t); this.shopTipEl = t;
    }
    const t = this.shopTipEl;
    if (!html) { t.style.display = 'none'; return; }
    t.innerHTML = html;
    t.style.display = 'block';
    t.style.left = Math.min(innerWidth - 260, x + 16) + 'px';
    t.style.top = Math.min(innerHeight - 120, y + 14) + 'px';
  }
  // One 46px cell, the same slot look the pack and the bank use. badge is a
  // count, '∞' for base wares, or nothing.
  fenCell(id, badge, dim, onClick, onMenu, tipHtml) {
    const d = document.createElement('div');
    d.style.cssText = 'width:46px;height:46px;background:#15170f;border:1.5px solid #2c2f24;display:flex;align-items:center;justify-content:center;position:relative;transition:border-color 110ms;opacity:' + (dim ? '0.42' : '1') + ';cursor:' + (onClick ? 'pointer' : 'default') + ';';
    d.innerHTML = '<div style="width:32px;height:32px;display:flex;align-items:center;justify-content:center;pointer-events:none;">' + this.itemIcon(id) + '</div>' +
      (badge ? '<div style="position:absolute;right:3px;bottom:2px;font-size:9px;font-weight:700;color:#e8c774;text-shadow:0 1px 2px #000;pointer-events:none;">' + badge + '</div>' : '');
    d.onmouseenter = () => { d.style.borderColor = '#c8a24a'; };
    d.onmouseleave = () => { d.style.borderColor = '#2c2f24'; this.shopTip(null); };
    d.addEventListener('pointermove', (e) => this.shopTip(tipHtml(), e.clientX, e.clientY));
    if (onClick) d.addEventListener('pointerup', (e) => { if (e.button === 0) onClick(); });
    if (onMenu) d.addEventListener('contextmenu', (e) => { e.preventDefault(); this.shopTip(null); onMenu(e.clientX, e.clientY); });
    return d;
  }""",
    tag='shop core')


# ============================================================ renderShop
sub(
    """  renderShop() {
    const el = this.shopEl; if (!el || !this.shopOpen) return;
    while (el.firstChild) el.removeChild(el.firstChild);
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    const gold = this.invCount('GOLD CROWNS');
    const head = mk('div', this.panelHeadCss());
    head.appendChild(mk('div', this.panelTitleCss(), 'FENWICK THE TRADER'));
    head.appendChild(mk('div', 'font-size:12px;color:#c8a24a;letter-spacing:0.08em;', gold.toLocaleString('en-US') + ' GOLD CROWNS'));
    head.appendChild(this.panelClose(() => this.closeShop()));
    el.appendChild(head);
    el.appendChild(mk('div', 'font-size:10px;color:#7d8a63;letter-spacing:0.06em;line-height:1.6;margin-top:-2px;',
      'Fenwick sells armour and spell tomes, and buys anything you have hauled back out of the world. Prices are fixed - he does not haggle.'));
    el.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin:10px 0 4px;', 'HE SELLS'));
    for (const s of this.shopStock()) {
      const owned = this.hasItem(s.k) || (s.k === 'TOME OF STORMS' && this.knowsStorm());
      const row = mk('div', 'display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #2f3426;');
      row.appendChild(this.shopIcon(s.k, owned));
      const info = mk('div', 'flex:1;');
      info.appendChild(mk('div', 'font-size:13px;color:' + (owned ? '#5f6b4a' : '#f2efe6') + ';', s.k + (owned ? '  (OWNED)' : '')));
      info.appendChild(mk('div', 'font-size:10.5px;color:#7d8a63;margin-top:3px;', s.d));
      row.appendChild(info);
      row.appendChild(mk('div', 'font-size:12px;color:#c8a24a;min-width:70px;text-align:right;', s.p + 'g'));
      const b = mk('button', 'padding:7px 14px;background:transparent;border:1px solid ' + (owned || gold < s.p ? '#3a3f2c' : '#c8a24a') + ';color:' + (owned || gold < s.p ? '#5f6b4a' : '#e8c774') + ';font-family:IBM Plex Mono,monospace;font-size:11px;letter-spacing:0.1em;cursor:' + (owned || gold < s.p ? 'default' : 'pointer') + ';', owned ? '—' : 'BUY');
      if (!owned && gold >= s.p) b.onclick = () => {
        if (this.canAccept(s.k, 1) < 1) { this.packFullNote(); return; }
        if (this.takeItem('GOLD CROWNS', s.p)) { this.addItem(s.k, 1); this.sfx('win'); this.banner('PURCHASED', s.k, false, 2000); this.renderShop(); }
      };
      row.appendChild(b);
      el.appendChild(row);
    }
    el.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin:14px 0 4px;', 'HE BUYS — WHAT YOU ARE CARRYING'));
    const prices = this.sellPrices();
    let any = false;
    for (const k in prices) {
      const have = this.invCount(k); if (have <= 0) continue;
      any = true;
      const row = mk('div', 'display:flex;align-items:center;gap:12px;padding:7px 0;border-bottom:1px solid #2f3426;');
      row.appendChild(this.shopIcon(k, false));
      row.appendChild(mk('div', 'flex:1;font-size:13px;', k + '  ×' + have.toLocaleString('en-US')));
      row.appendChild(mk('div', 'font-size:12px;color:#c8a24a;min-width:70px;text-align:right;', prices[k] + 'g ea'));
      const b1 = mk('button', 'padding:6px 12px;background:transparent;border:1px solid #7d8a63;color:#b3c29a;font-family:IBM Plex Mono,monospace;font-size:11px;cursor:pointer;', 'SELL 1');
      b1.onclick = () => { if (this.takeItem(k, 1)) { this.addItem('GOLD CROWNS', prices[k]); this.sfx('pickup'); this.renderShop(); } };
      const bA = mk('button', 'padding:6px 12px;background:transparent;border:1px solid #7d8a63;color:#b3c29a;font-family:IBM Plex Mono,monospace;font-size:11px;cursor:pointer;', 'ALL');
      bA.onclick = () => { const n = this.invCount(k); if (n > 0 && this.takeItem(k, n)) { this.addItem('GOLD CROWNS', prices[k] * n); this.sfx('pickup'); this.renderShop(); } };
      row.appendChild(b1); row.appendChild(bA);
      el.appendChild(row);
    }
    if (!any) el.appendChild(mk('div', 'font-size:11px;color:#5f6b4a;padding:6px 0;', 'NOTHING HE WANTS RIGHT NOW. BRING PELTS, HIDES, ORE OR PAYCHECKS.'));
    const foot = mk('div', 'margin-top:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;');
    foot.appendChild(mk('div', 'font-size:10.5px;color:#7d8a63;letter-spacing:0.06em;', 'WEARING: ' + this.armourName()));
    const close = mk('button', this.panelBtnCss(true), 'CLOSE (F)');
    close.style.padding = '9px 20px'; close.style.fontSize = '12px';
    close.onclick = () => this.closeShop();
    foot.appendChild(close);
    el.appendChild(foot);
    el.appendChild(this.panelLegend([['BUY', 'costs gold, goes straight into your pack'], ['SELL 1 or ALL', 'turns what you carry into gold'], ['F or ESC', 'close']]));
  }""",
    """  renderShop() {
    const el = this.shopEl; if (!el || !this.shopOpen) return;
    while (el.firstChild) el.removeChild(el.firstChild);
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    const gold = this.invCount('GOLD CROWNS');
    const head = mk('div', this.panelHeadCss());
    head.appendChild(mk('div', this.panelTitleCss(), 'FENWICK THE TRADER'));
    head.appendChild(mk('div', 'font-size:12px;color:#c8a24a;letter-spacing:0.08em;', gold.toLocaleString('en-US') + ' GOLD CROWNS'));
    head.appendChild(this.panelClose(() => this.closeShop()));
    el.appendChild(head);
    el.appendChild(mk('div', 'font-size:10px;color:#7d8a63;letter-spacing:0.06em;line-height:1.6;margin-top:-2px;',
      'Fenwick buys nearly anything and puts it up for sale. The more he holds of something, the less he pays for the next one, and he works his surplus off over time. Whatever players sell him, anyone can buy.'));

    const cols = mk('div', 'display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;margin-top:8px;');

    // ---- his stock: base wares (unlimited) first, then player-sold goods
    const left = mk('div', 'flex:1 1 430px;min-width:0;');
    const lh = mk('div', 'display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px;');
    lh.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;', "FENWICK'S STOCK"));
    lh.appendChild(mk('div', 'font-size:9px;color:#5f6b4a;letter-spacing:0.08em;', this.fenCloud ? 'SHARED · ALL PLAYERS' : 'THIS BROWSER ONLY'));
    left.appendChild(lh);
    const lg = mk('div', 'display:grid;grid-template-columns:repeat(auto-fill,46px);gap:6px;justify-content:start;min-height:160px;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:10px;');
    for (const w of this.shopStock()) {
      const owned = this.hasItem(w.k) || (w.k === 'TOME OF STORMS' && this.knowsStorm());
      lg.appendChild(this.fenCell(w.k, '∞', owned,
        () => this.fenBuy(w.k, 1),
        (x, y) => this.openShopMenu(x, y, 'stock', w.k),
        () => '<div style="color:#e8c774;letter-spacing:0.08em;">' + w.k + '</div>' +
              '<div style="color:#7d8a63;margin-top:2px;">' + w.d + '</div>' +
              '<div style="margin-top:4px;"><span style="color:#c8a24a;font-weight:700;">' + w.p.toLocaleString('en-US') + 'G</span><span style="color:#7d8a63;"> · UNLIMITED STOCK</span></div>' +
              (owned ? '<div style="color:#5f6b4a;margin-top:3px;">YOU ALREADY HAVE ' + (w.k === 'TOME OF STORMS' ? 'THE STORM' : 'ONE') + '</div>'
                     : '<div style="color:#5a6349;margin-top:3px;">CLICK TO BUY</div>')));
    }
    const soldIds = Object.keys(this.fenStock || {}).filter(k => (this.fenStock[k] > 0) && !this.fenWare(k)).sort();
    for (const k of soldIds) {
      const q = this.fenStock[k], unit = this.fenSellsFor(k);
      lg.appendChild(this.fenCell(k, (q > 9999 ? Math.floor(q / 1000) + 'K' : q), false,
        () => this.fenBuy(k, 1),
        (x, y) => this.openShopMenu(x, y, 'stock', k),
        () => '<div style="color:#e8c774;letter-spacing:0.08em;">' + k + '</div>' +
              '<div style="margin-top:3px;"><span style="color:#c8a24a;font-weight:700;">' + unit.toLocaleString('en-US') + 'G EACH</span><span style="color:#7d8a63;"> · ' + q.toLocaleString('en-US') + ' IN STOCK</span></div>' +
              '<div style="color:#5a6349;margin-top:3px;">CLICK BUYS 1 · RIGHT-CLICK FOR MORE</div>'));
    }
    if (!soldIds.length) lg.appendChild(mk('div', 'grid-column:1/-1;align-self:center;text-align:center;color:#5f6b4a;font-size:10px;letter-spacing:0.08em;padding:26px 8px;line-height:1.7;', 'THE SHELVES PAST THE ARMOUR ARE BARE. WHATEVER PLAYERS SELL HIM SHOWS UP HERE.'));
    left.appendChild(lg);
    cols.appendChild(left);

    // ---- your pack: the same 28 slots, priced
    const right = mk('div', 'flex:0 0 auto;');
    right.appendChild(mk('div', 'font-size:10px;letter-spacing:0.2em;color:#e8c774;margin-bottom:5px;', 'YOUR PACK — CLICK SELLS 1'));
    const rg = mk('div', 'display:grid;grid-template-columns:repeat(7,46px);gap:6px;justify-content:center;background:rgba(21,23,15,0.55);border:1px solid #2f3426;padding:10px;');
    for (let i = 0; i < 28; i++) {
      const c = this.inv[i];
      if (!c) {
        const d = mk('div', 'width:46px;height:46px;background:#15170f;border:1.5px solid #2c2f24;');
        rg.appendChild(d); continue;
      }
      const id = c.item, buys = this.fenBuys(id);
      const st = (this.fenStock && this.fenStock[id]) || 0;
      rg.appendChild(this.fenCell(id, c.qty > 1 ? (c.qty > 9999 ? Math.floor(c.qty / 1000) + 'K' : c.qty) : '', !buys,
        buys ? (() => this.fenSell(id, 1)) : null,
        buys ? ((x, y) => this.openShopMenu(x, y, 'pack', id)) : null,
        () => '<div style="color:#e8c774;letter-spacing:0.08em;">' + id + (c.qty > 1 ? ' ×' + c.qty.toLocaleString('en-US') : '') + '</div>' +
              (buys
                ? '<div style="margin-top:3px;">FENWICK PAYS <span style="color:#8fbf6a;font-weight:700;">' + this.fenPays(id) + 'G</span> EACH</div>' +
                  (st >= 8 ? '<div style="color:#c07a68;margin-top:2px;">HE IS FLUSH WITH THESE · PAYING LESS</div>' : '') +
                  '<div style="color:#5a6349;margin-top:3px;">CLICK SELLS 1 · RIGHT-CLICK FOR MORE</div>'
                : '<div style="color:#5f6b4a;margin-top:3px;">HE DOES NOT BUY ' + (id === 'GOLD CROWNS' ? 'GOLD' : 'THAT') + '</div>')));
    }
    right.appendChild(rg);
    cols.appendChild(right);
    el.appendChild(cols);

    el.appendChild(this.panelLegend([
      ['CLICK HIS STOCK', 'buy one'], ['CLICK YOUR ITEM', 'sell one'], ['RIGHT-CLICK', 'buy or sell in bulk'],
      ['HOVER', 'the price, before you commit'], ['F or ESC', 'close']
    ], 'Sold something by mistake? It is on his shelf now. Buy it straight back.'));
  }""",
    tag='renderShop grid')


# ============================================================ pack tooltip
# The everyday pack tooltip quoted def.value, which was never what he actually
# pays. Quote the live price, including the glut discount.
sub(
    """        html += '<div style="color:#7d8a63;">WORTH ~' + def.value + 'G AT FENWICK</div>';""",
    """        html += (this.fenBuys(it.item)
          ? '<div style="color:#7d8a63;">FENWICK PAYS ' + this.fenPays(it.item) + 'G EACH</div>'
          : '<div style="color:#7d8a63;">FENWICK DOES NOT BUY THIS</div>');""",
    tag='pack tooltip')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('42_fenwick_shop: %d edits applied' % n)
