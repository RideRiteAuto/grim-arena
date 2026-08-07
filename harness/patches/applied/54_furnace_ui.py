#!/usr/bin/env python3
"""Patch 54: the furnace gets a real smelting UI. Edits /tmp/game-src.html.

Before: F at the furnace silently smelted whatever ore it found, in a fixed
order, until it ran dry. No choice, no target, no idea what was happening.

Now: F opens THE FURNACE window - one row per recipe with the ore and bar
thumbnails, how many you hold, the SMITHING level and XP, and a quantity
picker ([-] [typed number] [+] [MAX]) with a SMELT button per row. Pick a
recipe and a count, hit SMELT, the window closes and the furnace works the
queue exactly as before: one bar every 1.1s, the pour sound, sparks, XP
floating up. Ore is consumed one bar at a time so stopping early keeps the
rest. Walking away, dying, running out of ore or a full pack stops it.

Ships with the bronze rename (tier 2 is BRONZE now, done in shared-rules.js
in the same push, no obtainable items were named COPPER) and two new bars:

  1 COPPER ORE            -> BRONZE BAR  lvl 1   10xp
  1 COPPER BAR (recast)   -> BRONZE BAR  lvl 1    2xp   (legacy bars melt over)
  1 IRON ORE              -> IRON BAR    lvl 1   16xp
  1 IRON ORE + 2 COAL     -> STEEL BAR   lvl 40  30xp
  1 GOLD ORE              -> GOLD BAR    lvl 40  56xp

The window uses the standard panel system (panelCss, scrim, ESC, keyboard
gate) and is registered in uiWindowOpen/closeTopWindow like every window
since the v14 pass. Recipe rows are DOM-built; the only innerHTML is our own
item icons.
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


# ------------------------------------------------------------ two new bars
sub("""    def('GOLD BAR',      { value: 80, icon: svg('<path d="M4 20.4 L8.6 12 L25.4 12 L26 20.4 Z" fill="#d9a93c" stroke="' + O + '" stroke-width="1.8"/>' +""",
    """    def('BRONZE BAR',    { value: 10, icon: svg('<path d="M4 20.4 L8.6 12 L25.4 12 L26 20.4 Z" fill="#a56a38" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M8.6 12 L25.4 12 L23.6 9.6 L10.6 9.6 Z" fill="#cf9058" stroke="' + O + '" stroke-width="1.5"/>' +
      '<path d="M11 14.4 L23 14.4" stroke="#e8bc8e" stroke-width="1.2" opacity="0.55"/>') });
    def('STEEL BAR',     { value: 34, icon: svg('<path d="M4 20.4 L8.6 12 L25.4 12 L26 20.4 Z" fill="#c3cdd9" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M8.6 12 L25.4 12 L23.6 9.6 L10.6 9.6 Z" fill="#e2e9f1" stroke="' + O + '" stroke-width="1.5"/>' +
      '<path d="M11 14.4 L23 14.4" stroke="#ffffff" stroke-width="1.2" opacity="0.7"/>') });
    def('GOLD BAR',      { value: 80, icon: svg('<path d="M4 20.4 L8.6 12 L25.4 12 L26 20.4 Z" fill="#d9a93c" stroke="' + O + '" stroke-width="1.8"/>' +""",
    tag='bronze + steel bar defs')

# ------------------------------- recipes, window, and the queued trySmelt
sub("""  SMELTS() {
    return [
      ['COPPER ORE', 'COPPER BAR', 1, 10],
      ['IRON ORE', 'IRON BAR', 1, 16],
      ['GOLD ORE', 'GOLD BAR', 40, 56]
    ];
  }
  smeltPick() {
    const sm = this.lvl(this.skills.SMITHING || 0);
    for (const r of this.SMELTS()) {
      if (this.invCount(r[0]) > 0 && sm >= r[2] && this.canAccept(r[1], 1) > 0) return r;
    }
    // a full pack for one bar kind should not silently skip to the next ore
    for (const r of this.SMELTS()) {
      if (this.invCount(r[0]) > 0 && sm >= r[2]) return r;
    }
    return null;
  }
  trySmelt() {
    if (!this.furnace || !this.started || this.mode !== 'ai' || !this.worldOn) return false;
    if (this.me.pos.distanceTo(this.furnace.pos) > 3.2) return false;
    if (this.smelting) { this.smelting = false; this.banner('SMELTING STOPPED', '', false, 1400); return true; }
    const pick = this.smeltPick();
    if (!pick) {
      const anyOre = this.SMELTS().some(r => this.invCount(r[0]) > 0);
      this.banner('THE FURNACE', anyOre
        ? 'YOUR SMITHING IS TOO LOW FOR THAT ORE'
        : 'NOTHING TO SMELT — BRING COPPER, IRON OR GOLD ORE', false, 3200);
      return true;
    }
    if (this.canAccept(pick[1], 1) < 1) { this.packFullNote(); return true; }
    this.smelting = true; this.smeltT = 0;
    this.banner('SMELTING', 'STAY BY THE FURNACE · F TO STOP', false, 2200);
    return true;
  }""",
    """  // [ore, bar, smithing lvl, xp, extra inputs?]. The recast row melts the
  // legacy copper bars (pre-bronze rename) into the new currency for 2xp.
  SMELTS() {
    return [
      ['COPPER ORE', 'BRONZE BAR', 1, 10],
      ['COPPER BAR', 'BRONZE BAR', 1, 2],
      ['IRON ORE', 'IRON BAR', 1, 16],
      ['IRON ORE', 'STEEL BAR', 40, 30, [['COAL', 2]]],
      ['GOLD ORE', 'GOLD BAR', 40, 56]
    ];
  }
  // How many of a recipe the pack can feed right now. Level is checked
  // separately so the row can say WHY it is grey.
  smeltMax(r) {
    let m = this.invCount(r[0]);
    for (const [id, q] of (r[4] || [])) m = Math.min(m, Math.floor(this.invCount(id) / q));
    return m;
  }
  smeltCan(r) { return this.lvl(this.skills.SMITHING || 0) >= r[2] && this.smeltMax(r) > 0; }
  trySmelt() {
    if (!this.furnace || !this.started || this.mode !== 'ai' || !this.worldOn) return false;
    if (this.me.pos.distanceTo(this.furnace.pos) > 3.2) return false;
    if (this.furnOpen) { this.closeFurnace(); return true; }
    if (this.smelting) { this.smelting = false; this.banner('SMELTING STOPPED', '', false, 1400); return true; }
    this.openFurnace();
    return true;
  }
  openFurnace() {
    this.buildFurnaceWin();
    this.furnOpen = true;
    this._furnEl.style.display = 'block';
    this.renderFurnace();
    try { document.exitPointerLock(); } catch (e) {}
  }
  closeFurnace() {
    if (this._furnEl) this._furnEl.style.display = 'none';
    this.furnOpen = false;
    this.uiClosedHandback();
  }
  buildFurnaceWin() {
    if (this._furnEl) return;
    const el = document.createElement('div');
    el.style.cssText = this.panelCss('min(560px, 94vw)');
    const head = document.createElement('div');
    head.style.cssText = this.panelHeadCss();
    const title = document.createElement('div');
    title.style.cssText = this.panelTitleCss();
    title.textContent = 'THE FURNACE';
    head.appendChild(title);
    head.appendChild(this.panelClose(() => this.closeFurnace()));
    el.appendChild(head);
    const note = document.createElement('div');
    note.style.cssText = 'font-size:10.5px; color:#7d8a63; letter-spacing:0.06em; padding:8px 2px 10px; line-height:1.5;';
    note.textContent = 'Pick an ore and how many bars to smelt. The furnace works while you stand by it - one bar at a time, straight into your pack.';
    el.appendChild(note);
    const rows = document.createElement('div');
    this._furnRows = rows;
    el.appendChild(rows);
    el.appendChild(this.panelLegend([['CLICK + / -', 'set the count'], ['TYPE A NUMBER', 'set it faster'], ['MAX', 'all your ore'], ['SMELT', 'start'], ['ESC', 'close']],
      'Smelting stops if you walk away. Ore is only spent as each bar comes out.'));
    document.body.appendChild(el);
    this._furnEl = el;
  }
  renderFurnace() {
    if (!this._furnRows) return;
    const rows = this._furnRows;
    rows.textContent = '';
    const sm = this.lvl(this.skills.SMITHING || 0);
    for (const r of this.SMELTS()) {
      const max = this.smeltMax(r);
      const okLvl = sm >= r[2];
      const usable = okLvl && max > 0;
      const row = document.createElement('div');
      row.style.cssText = 'display:flex; align-items:center; gap:10px; padding:9px 10px; margin-bottom:6px;'
        + 'background:rgba(21,23,15,0.55); border:1px solid #2f3426;' + (usable ? '' : ' opacity:0.45;');
      const icons = document.createElement('div');
      icons.style.cssText = 'display:flex; align-items:center; gap:4px; flex:none;';
      const mkIcon = (id) => { const d = document.createElement('div'); d.style.cssText = 'width:30px; height:30px;'; d.innerHTML = this.itemIcon(id); return d; };
      icons.appendChild(mkIcon(r[0]));
      for (const [xid] of (r[4] || [])) icons.appendChild(mkIcon(xid));
      const arrow = document.createElement('div');
      arrow.style.cssText = 'color:#5f6b4a; font-size:14px; flex:none;';
      arrow.textContent = '>';
      icons.appendChild(arrow);
      icons.appendChild(mkIcon(r[1]));
      row.appendChild(icons);
      const mid = document.createElement('div');
      mid.style.cssText = 'flex:1; min-width:0;';
      const nm = document.createElement('div');
      nm.style.cssText = 'font-size:12.5px; color:#e8c774; letter-spacing:0.08em;';
      nm.textContent = r[1];
      mid.appendChild(nm);
      const info = document.createElement('div');
      info.style.cssText = 'font-size:10px; color:#7d8a63; margin-top:2px; line-height:1.5;';
      let needTxt = '1 ' + r[0];
      for (const [xid, q] of (r[4] || [])) needTxt += ' + ' + q + ' ' + xid;
      info.textContent = needTxt + ' · you can make ' + max + ' · ' + r[3] + ' XP each'
        + (okLvl ? '' : ' · NEEDS SMITHING ' + r[2] + ' (you are ' + sm + ')');
      mid.appendChild(info);
      row.appendChild(mid);
      if (usable) {
        const ctl = document.createElement('div');
        ctl.style.cssText = 'display:flex; align-items:center; gap:5px; flex:none;';
        const btnCss = 'width:26px; height:26px; background:#1c1e15; border:1px solid #3a3f2c; color:#d8d4c6; font-size:14px; cursor:pointer; font-family:inherit;';
        const inp = document.createElement('input');
        inp.type = 'text'; inp.inputMode = 'numeric'; inp.value = String(max);
        inp.style.cssText = 'width:44px; height:24px; background:#12140d; border:1px solid #3a3f2c; color:#f2efe6; text-align:center; font-family:inherit; font-size:12px;';
        const clamp = () => { let v = parseInt(inp.value, 10); if (!Number.isFinite(v)) v = 1; v = Math.max(1, Math.min(this.smeltMax(r), v)); inp.value = String(v); return v; };
        const step = (d2) => { let v = parseInt(inp.value, 10) || 0; inp.value = String(v + d2); clamp(); };
        const minus = document.createElement('button'); minus.style.cssText = btnCss; minus.textContent = '-'; minus.onclick = () => step(-1);
        const plus = document.createElement('button'); plus.style.cssText = btnCss; plus.textContent = '+'; plus.onclick = () => step(1);
        const mx = document.createElement('button'); mx.style.cssText = btnCss + 'width:auto; padding:0 7px; font-size:10px;'; mx.textContent = 'MAX';
        mx.onclick = () => { inp.value = String(this.smeltMax(r)); clamp(); };
        inp.addEventListener('change', clamp);
        const go = document.createElement('button');
        go.style.cssText = 'height:26px; padding:0 13px; background:#c8a24a; border:none; color:#17180f; font-weight:700; font-size:11px; letter-spacing:0.1em; cursor:pointer; font-family:inherit;';
        go.textContent = 'SMELT';
        go.onclick = () => this.startSmelt(r, clamp());
        ctl.appendChild(minus); ctl.appendChild(inp); ctl.appendChild(plus); ctl.appendChild(mx); ctl.appendChild(go);
        row.appendChild(ctl);
      }
      rows.appendChild(row);
    }
  }
  startSmelt(r, count) {
    count = Math.max(1, Math.min(this.smeltMax(r), Math.floor(count) || 0));
    if (!this.smeltCan(r) || count < 1) return;
    if (this.canAccept(r[1], 1) < 1) { this.packFullNote(); return; }
    this.smelting = { r: r, left: count };
    this.smeltT = 0;
    this.closeFurnace();
    this.banner('SMELTING ' + count + ' ' + r[1] + (count === 1 ? '' : 'S'), 'STAY BY THE FURNACE · F TO STOP', false, 2400);
  }""",
    tag='furnace window + queued smelt')

# ------------------------------------------------- the loop works the queue
sub("""    if (this.smelting) {
      if (this.me.hp <= 0 || this.me.pos.distanceTo(this.furnace.pos) > 3.6) this.smelting = false;
      else {
        this.smeltT += dt;
        if (this.smeltT >= 1.1) {
          this.smeltT = 0;
          const r = this.smeltPick();
          if (!r) { this.smelting = false; this.banner('OUT OF ORE', 'MINE MORE — COPPER, IRON OR GOLD', false, 2600); }
          else if (this.canAccept(r[1], 1) < 1) { this.smelting = false; this.packFullNote(); }
          else if (!this.takeItem(r[0], 1)) { this.smelting = false; }
          else {
            this.addItem(r[1], 1); this.awardXp('SMITHING', r[3]);
            this.spark(this.furnace.pos.clone().add(new T.Vector3(0, 0.75, 1.35)), 0xffa040, 10);
            if (this.furnace.kit && this.ac) this.furnace.kit.pour(this.ac, this.master, { gain: 0.5 });
            else this.sfx('break');
            if (!this.smeltPick()) this.smelting = false;
          }
        }
      }
    }""",
    """    if (this.smelting) {
      if (this.me.hp <= 0 || this.me.pos.distanceTo(this.furnace.pos) > 3.6) this.smelting = false;
      else {
        this.smeltT += dt;
        if (this.smeltT >= 1.1) {
          this.smeltT = 0;
          const q = this.smelting, r = q.r;
          // inputs are checked BEFORE anything is taken, so a multi-input
          // recipe (steel: ore + coal) can never half-consume
          if (this.smeltMax(r) < 1) { this.smelting = false; this.banner('OUT OF ORE', 'MINE MORE AND COME BACK', false, 2600); }
          else if (this.canAccept(r[1], 1) < 1) { this.smelting = false; this.packFullNote(); }
          else if (!this.takeItem(r[0], 1)) { this.smelting = false; }
          else {
            for (const [xid, xq] of (r[4] || [])) this.takeItem(xid, xq);
            this.addItem(r[1], 1); this.awardXp('SMITHING', r[3]);
            this.spark(this.furnace.pos.clone().add(new T.Vector3(0, 0.75, 1.35)), 0xffa040, 10);
            if (this.furnace.kit && this.ac) this.furnace.kit.pour(this.ac, this.master, { gain: 0.5 });
            else this.sfx('break');
            q.left--;
            if (q.left < 1 || this.smeltMax(r) < 1) this.smelting = false;
          }
        }
      }
    }""",
    tag='smelt loop queue')

# --------------------------------------------- window system registration
sub("  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen); }",
    "  uiWindowOpen() { return !!(this.walletOpen || this.sackWinId || this.bankOpen || this.shopOpen || this._wmOpen || this._skOpen || this.furnOpen || this.anvOpen); }",
    tag='uiWindowOpen furnace')

sub("""  closeTopWindow() {
    if (this.shopOpen) return this.closeShop();""",
    """  closeTopWindow() {
    if (this.furnOpen) return this.closeFurnace();
    if (this.shopOpen) return this.closeShop();""",
    tag='closeTopWindow furnace')

# -------------------------------------------------------- interact prompt
sub("""    if (this.furnace) add(this.furnace.pos, R.station,
      this.smelting ? 'PRESS F - STOP SMELTING' : 'PRESS F - SMELT ORE', () => this.trySmelt());""",
    """    if (this.furnace) add(this.furnace.pos, R.station,
      this.furnOpen ? 'F - CLOSE THE FURNACE' : this.smelting ? 'PRESS F - STOP SMELTING' : 'PRESS F - SMELT ORE', () => this.trySmelt());""",
    tag='furnace prompt')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('54_furnace_ui: %d edits applied' % n)
