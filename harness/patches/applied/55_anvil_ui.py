#!/usr/bin/env python3
"""Patch 55: the anvil becomes a real smithy. Edits /tmp/game-src.html.

Before: the anvil made exactly one thing, ever - the Grim Cleaver, 10 iron
bars, once per character.

Now: F opens THE ANVIL with three material tabs - BRONZE, IRON, STEEL - each
listing the full set for that metal: Full Helm (3 bars), Platebody (8),
Platelegs (6), Kite Shield (5), Scimitar (4), Claymore (7, the two-hander
every tier has now, using the greatsword moveset), Pickaxe (3), Axe (3),
Sickle (2), and Skinning Knife (1 - craftable now, skinning comes later).
Every row shows the thumbnails, your bar count, level and XP, and the same
[-] [typed number] [+] [MAX] picker the furnace uses. SMITH closes the
window and the anvil rings: hammer blows and sparks off the face, one item
every ~2.6 seconds, XP floating up, items straight into your pack.

Tab gates (SMITHING): bronze 1, iron 15, steel 40. XP per item = bars used
x the metal's rate (bronze 12, iron 20, steel 34), so a platebody pays.

Sixteen new items ship with hand-made thumbnails in the house style - the
iron shapes recoloured per metal (warm bronze, bright steel) plus new
claymore and skinning knife silhouettes. Bronze/steel tools already existed
in the auto-generated tool ladder. New-tier armour renders on the knight as
tinted iron for now; distinct 3D armour is an art-track follow-up.

Every craft consumes bars and grants the item inside one atomic inventory
commit (the Grim Cleaver's own machinery, generalised) - a full pack or a
mid-queue interruption can never dupe or eat materials. The Grim Cleaver
itself is retired from crafting but every existing one still works; the
iron claymore is its successor with identical stats.
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


# ------------------------------------------------ 16 new gear defs + icons
sub("    def('GRIM CLEAVER',    { stack: false, slot: 'WEAPON', hands: 2, wieldAs: 5, style: 'melee', value: 900,",
    """    {
      const BZ = '#b0714a', BZ2 = '#8a5533', BZB = '#d29a6a';
      const ST = '#c3cdd9', ST2 = '#93a1b0', STB = '#e4ebf2';
      const helmI = (a, b) => svg('<path d="M7 16 Q7 6 15 6 Q23 6 23 16 L23 24 L19 24 L19 19 L11 19 L11 24 L7 24 Z" fill="' + a + '" stroke="' + O + '" stroke-width="2"/><rect x="11" y="13" width="8" height="2.6" fill="' + O + '"/>');
      const bodyI = (a, b) => svg('<path d="M9 5 L21 5 L24 10 L22 25 L8 25 L6 10 Z" fill="' + a + '" stroke="' + O + '" stroke-width="2"/><path d="M6 10 L2 14 L5 17 L8 12 Z M24 10 L28 14 L25 17 L22 12 Z" fill="' + b + '" stroke="' + O + '" stroke-width="1.6"/><line x1="15" y1="8" x2="15" y2="23" stroke="' + b + '" stroke-width="2"/>');
      const legsI = (a, b) => svg('<path d="M9 4 L21 4 L21 10 L17 10 L17 26 L12.5 26 L12.5 10 L9 10 Z M17 10 L21 10 L21 26 L17 26 Z" fill="' + a + '" stroke="' + O + '" stroke-width="2"/>');
      const shieldI = (a, b) => svg('<path d="M15 3 L26 8 L24 19 L15 27 L6 19 L4 8 Z" fill="' + a + '" stroke="' + O + '" stroke-width="2"/><path d="M15 7 L15 22 M8.5 13 L21.5 13" stroke="' + b + '" stroke-width="2.4"/>');
      const scimI = (bl) => svg('<path d="M6 24 Q4 12 14 5 Q24 0 26 6 Q19 6 13 13 Q9 18 9 24 Z" fill="' + bl + '" stroke="' + O + '" stroke-width="2"/><rect x="5" y="22" width="7" height="4" rx="1.4" transform="rotate(-45 8 24)" fill="#7a5a34" stroke="' + O + '" stroke-width="1.4"/>');
      const clayI = (bl, ac) => svg('<path d="M14 2 L16 2 L17.6 19 L12.4 19 Z" fill="' + bl + '" stroke="' + O + '" stroke-width="1.8"/><rect x="9.4" y="18.4" width="11.2" height="2.6" rx="0.8" fill="' + ac + '" stroke="' + O + '" stroke-width="1.3"/><rect x="13.6" y="21" width="2.8" height="5.6" rx="1" fill="' + WD + '" stroke="' + O + '" stroke-width="1.2"/><circle cx="15" cy="27" r="1.7" fill="' + ac + '" stroke="' + O + '" stroke-width="1.1"/>');
      const skinI = (bl) => svg('<path d="M9 21 Q8 10 17 5 Q21 8 15 14 Q11 17 12 21 Z" fill="' + bl + '" stroke="' + O + '" stroke-width="1.8"/><rect x="9.6" y="20" width="4.6" height="7" rx="1.4" transform="rotate(14 12 23)" fill="' + WD + '" stroke="' + O + '" stroke-width="1.3"/>');
      def('BRONZE FULL HELM',   { stack: false, slot: 'HEAD',   value: 55,  stats: { att: 0, str: 0, def: 7,  mag: 0, rng: 0 }, icon: helmI(BZ, BZ2) });
      def('BRONZE PLATEBODY',   { stack: false, slot: 'BODY',   value: 155, stats: { att: 0, str: 0, def: 18, mag: 0, rng: 0 }, icon: bodyI(BZ, BZ2) });
      def('BRONZE PLATELEGS',   { stack: false, slot: 'LEGS',   value: 110, stats: { att: 0, str: 0, def: 12, mag: 0, rng: 0 }, icon: legsI(BZ, BZ2) });
      def('BRONZE KITE SHIELD', { stack: false, slot: 'SHIELD', value: 100, stats: { att: 0, str: 0, def: 12, mag: 0, rng: 0 }, icon: shieldI(BZ, BZ2) });
      def('BRONZE SCIMITAR',    { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 0, style: 'melee', value: 70,  stats: { att: 6,  str: 5,  def: 0, mag: 0, rng: 0 }, icon: scimI(BZB) });
      def('BRONZE CLAYMORE',    { stack: false, slot: 'WEAPON', hands: 2, wieldAs: 5, style: 'melee', value: 300, stats: { att: 10, str: 13, def: 0, mag: 0, rng: 0 }, icon: clayI(BZB, BZ2) });
      def('BRONZE SKINNING KNIFE', { stack: false, value: 25,  stats: { att: 0, str: 0, def: 0, mag: 0, rng: 0 }, icon: skinI(BZB) });
      def('IRON CLAYMORE',      { stack: false, slot: 'WEAPON', hands: 2, wieldAs: 5, style: 'melee', value: 500, stats: { att: 16, str: 22, def: 0, mag: 0, rng: 0 }, icon: clayI('#ccd4dc', FE2) });
      def('IRON SKINNING KNIFE',{ stack: false, value: 40,  stats: { att: 0, str: 0, def: 0, mag: 0, rng: 0 }, icon: skinI('#ccd4dc') });
      def('STEEL FULL HELM',    { stack: false, slot: 'HEAD',   value: 135, stats: { att: 0, str: 0, def: 18, mag: 0, rng: 0 }, icon: helmI(ST, ST2) });
      def('STEEL PLATEBODY',    { stack: false, slot: 'BODY',   value: 390, stats: { att: 0, str: 0, def: 45, mag: 0, rng: 0 }, icon: bodyI(ST, ST2) });
      def('STEEL PLATELEGS',    { stack: false, slot: 'LEGS',   value: 270, stats: { att: 0, str: 0, def: 30, mag: 0, rng: 0 }, icon: legsI(ST, ST2) });
      def('STEEL KITE SHIELD',  { stack: false, slot: 'SHIELD', value: 255, stats: { att: 0, str: 0, def: 30, mag: 0, rng: 0 }, icon: shieldI(ST, ST2) });
      def('STEEL SCIMITAR',     { stack: false, slot: 'WEAPON', hands: 1, wieldAs: 0, style: 'melee', value: 180, stats: { att: 15, str: 14, def: 0, mag: 0, rng: 0 }, icon: scimI(STB) });
      def('STEEL CLAYMORE',     { stack: false, slot: 'WEAPON', hands: 2, wieldAs: 5, style: 'melee', value: 750, stats: { att: 24, str: 33, def: 0, mag: 0, rng: 0 }, icon: clayI(STB, ST2) });
      def('STEEL SKINNING KNIFE',{ stack: false, value: 60, stats: { att: 0, str: 0, def: 0, mag: 0, rng: 0 }, icon: skinI(STB) });
    }
    def('GRIM CLEAVER',    { stack: false, slot: 'WEAPON', hands: 2, wieldAs: 5, style: 'melee', value: 900,""",
    tag='new gear defs')

# --------------------------------------- anvil recipes, window, and queue
sub("""  tryForge() {
    if (!this.anvil || !this.started || this.mode !== 'ai' || !this.worldOn) return false;
    if (this.me.pos.distanceTo(this.anvil.pos) > 3.0) return false;
    if (this.forging) return true;
    if (this.hasItem('GRIM CLEAVER')) { this.banner('THE ANVIL', 'THE GRIM CLEAVER IS ALREADY YOURS — ONE IS ENOUGH', false, 3000); return true; }
    const bars = this.invCount('IRON BAR');
    if (bars < 10) { this.banner('THE ANVIL', 'NEEDS 10 IRON BARS — YOU HAVE ' + bars, false, 3000); return true; }
    if (!this.invSimulate(() => { this.invTakeRaw('IRON BAR', 10); return this.invPlace('GRIM CLEAVER', 1) === 1; })) {
      this.banner('THE ANVIL', 'NO ROOM FOR THE CLEAVER — FREE A PACK SLOT', false, 3000); return true;
    }
    this.forging = 1.6; this.forgeClang = 0;
    this.banner('FORGING…', 'THE ANVIL RINGS', false, 1800);
    return true;
  }""",
    """  // The three metals the anvil works, and everything each one makes.
  SMITHS() {
    return [
      { tab: 'BRONZE', bar: 'BRONZE BAR', lvl: 1,  xpb: 12 },
      { tab: 'IRON',   bar: 'IRON BAR',   lvl: 15, xpb: 20 },
      { tab: 'STEEL',  bar: 'STEEL BAR',  lvl: 40, xpb: 34 }
    ];
  }
  SMITH_KINDS() {
    return [
      ['FULL HELM', 3], ['PLATEBODY', 8], ['PLATELEGS', 6], ['KITE SHIELD', 5],
      ['SCIMITAR', 4], ['CLAYMORE', 7],
      ['PICKAXE', 3], ['AXE', 3], ['SICKLE', 2], ['SKINNING KNIFE', 1]
    ];
  }
  tryForge() {
    if (!this.anvil || !this.started || this.mode !== 'ai' || !this.worldOn) return false;
    if (this.me.pos.distanceTo(this.anvil.pos) > 3.0) return false;
    if (this.anvOpen) { this.closeAnvil(); return true; }
    if (this.smithQ) { this.smithQ = null; this.banner('SMITHING STOPPED', '', false, 1400); return true; }
    this.openAnvil();
    return true;
  }
  openAnvil() {
    this.buildAnvilWin();
    this.anvOpen = true;
    this._anvEl.style.display = 'block';
    this.renderAnvil();
    try { document.exitPointerLock(); } catch (e) {}
  }
  closeAnvil() {
    if (this._anvEl) this._anvEl.style.display = 'none';
    this.anvOpen = false;
    this.uiClosedHandback();
  }
  buildAnvilWin() {
    if (this._anvEl) return;
    const el = document.createElement('div');
    el.style.cssText = this.panelCss('min(640px, 94vw)');
    const head = document.createElement('div');
    head.style.cssText = this.panelHeadCss();
    const title = document.createElement('div');
    title.style.cssText = this.panelTitleCss();
    title.textContent = 'THE ANVIL';
    head.appendChild(title);
    head.appendChild(this.panelClose(() => this.closeAnvil()));
    el.appendChild(head);
    const tabs = document.createElement('div');
    tabs.style.cssText = 'display:flex; gap:6px; padding:8px 0 10px;';
    this._anvTabs = tabs;
    el.appendChild(tabs);
    const rows = document.createElement('div');
    this._anvRows = rows;
    el.appendChild(rows);
    el.appendChild(this.panelLegend([['TABS', 'pick the metal'], ['CLICK + / -', 'set the count'], ['TYPE A NUMBER', 'set it faster'], ['MAX', 'all your bars'], ['SMITH', 'start'], ['ESC', 'close']],
      'The anvil works while you stand by it. Bars are only spent as each piece is finished. Skinning knives can be made now - skinning itself comes soon.'));
    document.body.appendChild(el);
    this._anvEl = el;
  }
  renderAnvil() {
    if (!this._anvRows) return;
    const sm = this.lvl(this.skills.SMITHING || 0);
    const tiers = this.SMITHS();
    if (this._anvTab === undefined) this._anvTab = 0;
    // tabs
    const tabs = this._anvTabs;
    tabs.textContent = '';
    tiers.forEach((t, i) => {
      const b = document.createElement('button');
      const on = i === this._anvTab;
      const locked = sm < t.lvl;
      b.style.cssText = 'flex:1; padding:8px 0; font-family:inherit; font-size:11px; letter-spacing:0.12em; cursor:pointer;'
        + (on ? 'background:#c8a24a; color:#17180f; border:1px solid #c8a24a; font-weight:700;'
              : 'background:#1c1e15; color:' + (locked ? '#5f6b4a' : '#d8d4c6') + '; border:1px solid #3a3f2c;');
      b.textContent = t.tab + (locked ? ' (LVL ' + t.lvl + ')' : '');
      b.onclick = () => { this._anvTab = i; this.renderAnvil(); };
      tabs.appendChild(b);
    });
    // rows
    const t = tiers[this._anvTab];
    const rows = this._anvRows;
    rows.textContent = '';
    const locked = sm < t.lvl;
    const bars = this.invCount(t.bar);
    const barLine = document.createElement('div');
    barLine.style.cssText = 'font-size:10.5px; color:#7d8a63; letter-spacing:0.06em; padding:0 2px 8px;';
    barLine.textContent = locked
      ? 'NEEDS SMITHING ' + t.lvl + ' - YOU ARE ' + sm
      : 'YOU HAVE ' + bars + ' ' + t.bar + (bars === 1 ? '' : 'S') + ' - SMELT MORE AT THE FURNACE';
    rows.appendChild(barLine);
    for (const [kind, cost] of this.SMITH_KINDS()) {
      const id = t.tab + ' ' + kind;
      if (!this.itemDef(id)) continue;
      const max = Math.floor(bars / cost);
      const usable = !locked && max > 0;
      const xp = cost * t.xpb;
      const row = document.createElement('div');
      row.style.cssText = 'display:flex; align-items:center; gap:10px; padding:7px 10px; margin-bottom:5px;'
        + 'background:rgba(21,23,15,0.55); border:1px solid #2f3426;' + (usable ? '' : ' opacity:0.45;');
      const ic = document.createElement('div');
      ic.style.cssText = 'width:30px; height:30px; flex:none;';
      ic.innerHTML = this.itemIcon(id);
      row.appendChild(ic);
      const mid = document.createElement('div');
      mid.style.cssText = 'flex:1; min-width:0;';
      const nm = document.createElement('div');
      nm.style.cssText = 'font-size:12px; color:#e8c774; letter-spacing:0.08em;';
      nm.textContent = id + (kind === 'SKINNING KNIFE' ? '  (SKINNING COMES SOON)' : '');
      mid.appendChild(nm);
      const info = document.createElement('div');
      info.style.cssText = 'font-size:10px; color:#7d8a63; margin-top:2px;';
      info.textContent = cost + ' ' + t.bar + (cost === 1 ? '' : 'S') + ' · ' + xp + ' XP · you can make ' + max + ' · you own ' + this.invCount(id);
      mid.appendChild(info);
      row.appendChild(mid);
      if (usable) {
        const ctl = document.createElement('div');
        ctl.style.cssText = 'display:flex; align-items:center; gap:5px; flex:none;';
        const btnCss = 'width:26px; height:26px; background:#1c1e15; border:1px solid #3a3f2c; color:#d8d4c6; font-size:14px; cursor:pointer; font-family:inherit;';
        const inp = document.createElement('input');
        inp.type = 'text'; inp.inputMode = 'numeric'; inp.value = '1';
        inp.style.cssText = 'width:40px; height:24px; background:#12140d; border:1px solid #3a3f2c; color:#f2efe6; text-align:center; font-family:inherit; font-size:12px;';
        const maxNow = () => Math.floor(this.invCount(t.bar) / cost);
        const clamp = () => { let v = parseInt(inp.value, 10); if (!Number.isFinite(v)) v = 1; v = Math.max(1, Math.min(maxNow(), v)); inp.value = String(v); return v; };
        const step = (d2) => { let v = parseInt(inp.value, 10) || 0; inp.value = String(v + d2); clamp(); };
        const minus = document.createElement('button'); minus.style.cssText = btnCss; minus.textContent = '-'; minus.onclick = () => step(-1);
        const plus = document.createElement('button'); plus.style.cssText = btnCss; plus.textContent = '+'; plus.onclick = () => step(1);
        const mx = document.createElement('button'); mx.style.cssText = btnCss + 'width:auto; padding:0 7px; font-size:10px;'; mx.textContent = 'MAX';
        mx.onclick = () => { inp.value = String(maxNow()); clamp(); };
        inp.addEventListener('change', clamp);
        const go = document.createElement('button');
        go.style.cssText = 'height:26px; padding:0 12px; background:#c8a24a; border:none; color:#17180f; font-weight:700; font-size:11px; letter-spacing:0.1em; cursor:pointer; font-family:inherit;';
        go.textContent = 'SMITH';
        go.onclick = () => this.startSmith(id, t, cost, xp, clamp());
        ctl.appendChild(minus); ctl.appendChild(inp); ctl.appendChild(plus); ctl.appendChild(mx); ctl.appendChild(go);
        row.appendChild(ctl);
      }
      rows.appendChild(row);
    }
  }
  startSmith(id, t, cost, xp, count) {
    const max = Math.floor(this.invCount(t.bar) / cost);
    count = Math.max(1, Math.min(max, Math.floor(count) || 0));
    if (count < 1 || this.lvl(this.skills.SMITHING || 0) < t.lvl) return;
    if (this.canAccept(id, 1) < 1) { this.packFullNote(); return; }
    this.smithQ = { id: id, bar: t.bar, cost: cost, xp: xp, left: count };
    this.smithT = 0; this.forgeClang = 0;
    this.closeAnvil();
    this.banner('SMITHING ' + count + ' ' + id + (count === 1 ? '' : 'S'), 'STAY BY THE ANVIL · F TO STOP', false, 2400);
  }""",
    tag='anvil window + queue start')

# ------------------------------------------- the queue replaces the cleaver
sub("""    if (this.forging) {
      this.forging -= dt; this.forgeClang -= dt;
      if (this.forgeClang <= 0) {
        this.forgeClang = 0.4;
        this._forgeBlow = (this._forgeBlow || 0) + 1;
        // the first blow of a heat lands hardest
        this.anvilStrike(this._forgeBlow % 4 === 1);
        // Sparks off the FACE rather than a guessed 0.8 m above the base, so
        // they come off the metal instead of out of the middle of the stump.
        this.spark((this.anvil.face || this.anvil.pos.clone().add(new T.Vector3(0, 0.8, 0)))
          .clone().add(new T.Vector3(0, 0.03, 0)), 0xfff2c8, 8);
      }
      if (this.forging <= 0) {
        this.forging = 0;
        if (this.craftAtAnvil()) {
          this.awardXp('SMITHING', 120);
          this.banner('THE GRIM CLEAVER', 'AN IRON TWO-HANDER — PRESS 6 TO WIELD IT', false, 5200); this.sfx('win');
          this.saveQuest();
        }
      }
    }""",
    """    if (this.smithQ) {
      if (this.me.hp <= 0 || this.me.pos.distanceTo(this.anvil.pos) > 3.6) this.smithQ = null;
      else {
        this.forgeClang -= dt;
        if (this.forgeClang <= 0) {
          this.forgeClang = 0.65;
          this._forgeBlow = (this._forgeBlow || 0) + 1;
          // the first blow of a heat lands hardest
          this.anvilStrike(this._forgeBlow % 4 === 1);
          // Sparks off the FACE rather than a guessed 0.8 m above the base, so
          // they come off the metal instead of out of the middle of the stump.
          this.spark((this.anvil.face || this.anvil.pos.clone().add(new T.Vector3(0, 0.8, 0)))
            .clone().add(new T.Vector3(0, 0.03, 0)), 0xfff2c8, 8);
        }
        this.smithT = (this.smithT || 0) + dt;
        if (this.smithT >= 2.6) {
          this.smithT = 0;
          const q = this.smithQ;
          if (this.invCount(q.bar) < q.cost) { this.smithQ = null; this.banner('OUT OF BARS', 'SMELT MORE AT THE FURNACE', false, 2600); }
          else {
            // bars out, item in, one atomic commit - interruptions and full
            // packs can never dupe or eat materials
            const made = this.invCommit(() => {
              this.invTakeRaw(q.bar, q.cost);
              if (this.invPlace(q.id, 1) !== 1) throw new Error('no room');
              return true;
            });
            if (!made) { this.smithQ = null; this.packFullNote(); }
            else {
              this.lootToast(q.id, 1);
              this.awardXp('SMITHING', q.xp);
              q.left--;
              if (q.left < 1) { this.smithQ = null; this.banner('SMITHING DONE', 'YOUR WORK IS IN YOUR PACK', false, 2200); }
            }
          }
        }
      }
    }""",
    tag='smith queue loop')

# --------------------------------------------- window system registration
sub("""  closeTopWindow() {
    if (this.furnOpen) return this.closeFurnace();""",
    """  closeTopWindow() {
    if (this.anvOpen) return this.closeAnvil();
    if (this.furnOpen) return this.closeFurnace();""",
    tag='closeTopWindow anvil')

sub("    if (this.anvil) add(this.anvil.pos, R.station, 'PRESS F - FORGE (10 IRON BARS)', () => this.tryForge());",
    "    if (this.anvil) add(this.anvil.pos, R.station, this.anvOpen ? 'F - CLOSE THE ANVIL' : this.smithQ ? 'PRESS F - STOP SMITHING' : 'PRESS F - SMITH', () => this.tryForge());",
    tag='anvil prompt')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('55_anvil_ui: %d edits applied' % n)
