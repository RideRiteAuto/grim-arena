#!/usr/bin/env python3
"""Patch 73: Who's Online, filterable by zone and combat level.

Next item on Kevin's explicit list, after zone tracking (70) and combat
level (71): "the Who's Online tab." The roster patch 67 built (O key,
"PLAYERS IN GRIM WORLD", togglePlayerList/buildPlayerListDom/
renderPlayerList) already lists every currently connected player, not just
nearby ones -- this.remotes is the whole shared-world peer set, the same
one the party frames read from. So this is an upgrade to that existing
panel rather than a new one: it did not yet show WHERE everyone is or how
tough they are, and had no way to narrow the list down.

Changes:
- Every row (you, other players, and online friends) grows a small muted
  subline under the name: "Zone · Lvl N", built from r.s.z and r.s.cl,
  the same broadcast fields patches 70 and 71 already put on every peer's
  state. A player whose zone or level has not arrived yet (just connected,
  or a stale client) simply gets a shorter or empty subline rather than a
  guess.
- A filter row (zone dropdown + minimum-level number field), built once in
  buildPlayerListDom alongside the header so a partially-typed number or an
  open dropdown survives the panel's existing 250ms redraw tick --
  renderPlayerList() only ever touches the body below it, never this row,
  exactly like the header and legend already didn't need rebuilding either.
- The filter narrows the "other players online" list only. Your own row
  and the FRIENDS section stay unfiltered: the filter's job is helping you
  find people out in the world you don't already know, not hiding friends
  you already keep track of.
- A filter can only confirm a match, never a miss it cannot see: a player
  whose zone or level has not broadcast yet is left out of a narrowed list
  rather than guessed into or out of it. The empty state distinguishes
  "no one online at all" from "no one matches this filter" so a wide net
  doesn't read as an empty server.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def slice_between(start_marker, end_marker, tag):
    i = s.index(start_marker)
    j = s.index(end_marker, i)
    assert i > 0 and j > i, 'patch 73 [%s]: markers not found in order' % tag
    return i, j


# ---- 1. buildPlayerListDom: add the filter row, built once --------------
i, j = slice_between('  buildPlayerListDom() {', '\n  renderPlayerList() {', tag='buildPlayerListDom bounds')
old_build = s[i:j]
assert "this.panelCss('340px')" in old_build, 'patch 73: buildPlayerListDom shape changed, re-check anchor'
assert 'PLAYERS IN GRIM WORLD' in old_build, 'patch 73: buildPlayerListDom shape changed, re-check anchor'

new_build = """  buildPlayerListDom() {
    if (this.plEl) return;
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    const wrap = mk('div', this.panelCss('380px'));
    const head = mk('div', this.panelHeadCss());
    head.appendChild(mk('div', this.panelTitleCss(), 'PLAYERS IN GRIM WORLD'));
    head.appendChild(this.panelClose(() => this.togglePlayerList(false)));
    wrap.appendChild(head);
    // Filter row: zone and minimum combat level, built once so a selection
    // and any partially-typed number survive the 250ms redraw tick below --
    // renderPlayerList() only ever touches the body, never this row.
    const filterRow = mk('div', 'display:flex;gap:8px;padding:2px 0 9px;border-bottom:1px solid #2f3426;');
    const zoneSel = document.createElement('select');
    zoneSel.style.cssText = 'flex:1 1 auto;min-width:0;background:#1c1e15;color:#d8d4c6;border:1px solid #3a3f2c;border-radius:5px;font-size:11px;padding:6px 6px;font-family:inherit;';
    const optAll = document.createElement('option');
    optAll.value = ''; optAll.textContent = 'ALL ZONES';
    zoneSel.appendChild(optAll);
    Object.keys(GRIM_RULES.ZONES).forEach(k => {
      const o = document.createElement('option');
      o.value = k; o.textContent = GRIM_RULES.ZONES[k].name;
      zoneSel.appendChild(o);
    });
    zoneSel.onchange = () => { this._plZoneFilter = zoneSel.value; this.renderPlayerList(); };
    const lvlInput = document.createElement('input');
    lvlInput.type = 'number'; lvlInput.min = '1'; lvlInput.max = '99'; lvlInput.placeholder = 'MIN LVL';
    lvlInput.style.cssText = 'width:80px;flex:none;background:#1c1e15;color:#d8d4c6;border:1px solid #3a3f2c;border-radius:5px;font-size:11px;padding:6px 6px;font-family:inherit;';
    lvlInput.oninput = () => { this._plMinLvl = parseInt(lvlInput.value, 10) || 0; this.renderPlayerList(); };
    filterRow.appendChild(zoneSel);
    filterRow.appendChild(lvlInput);
    wrap.appendChild(filterRow);
    this._plZoneSel = zoneSel;
    this._plLvlInput = lvlInput;
    const body = mk('div', 'display:flex;flex-direction:column;');
    wrap.appendChild(body);
    wrap.appendChild(mk('div', this.panelLegendCss(), 'O, ESC, OR × TO CLOSE'));
    document.body.appendChild(wrap);
    this.plEl = wrap;
    this._plBody = body;
  }
"""
s = s[:i] + new_build + s[j:]
n += 1

# ---- 2. renderPlayerList: zone/level sublines + filtering ----------------
i, j = slice_between('  renderPlayerList() {', '\n  } updateQuickHealCd()', tag='renderPlayerList bounds')
old_render = s[i:j]
assert 'NO ONE ELSE ONLINE RIGHT NOW' in old_render, 'patch 73: renderPlayerList shape changed, re-check anchor'
assert "row((this.myName || 'YOU')" in old_render, 'patch 73: renderPlayerList shape changed, re-check anchor'

new_render = """  renderPlayerList() {
    const el = this._plBody;
    if (!el) return;
    while (el.firstChild) el.removeChild(el.firstChild);
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    // row() takes an explicit button-descriptor array now (instead of
    // deriving one INVITE button from id) so nearby-player rows and the
    // FRIENDS section below, which has no this.remotes entry to key off of,
    // can share the exact same row renderer. sub is an optional muted line
    // under the name -- zone and combat level, the same treatment party
    // frames already use, so the two lists read as one consistent language.
    const row = (name, right, gold, buttons, sub) => {
      // sub gets the FULL row width on its own line below, rather than
      // being squeezed into whatever space the name leaves next to the
      // buttons -- a row with three buttons (INVITE/WHISPER/UNFRIEND)
      // barely has room for the name itself, let alone "Zone · Lvl N" too.
      // Same two-tier shape party frames already use: a top line, then an
      // optional meta line underneath.
      const d = mk('div', 'padding:5px 0;border-bottom:1px solid #26281f;font-size:13px;' + (gold ? 'color:#e8c774;' : ''));
      const top = mk('div', 'display:flex;align-items:center;justify-content:space-between;gap:12px;');
      top.appendChild(mk('span', 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;', name));
      const rightWrap = mk('div', 'display:flex;align-items:center;gap:8px;flex:none;');
      rightWrap.appendChild(mk('span', 'color:#7d8a63;font-size:11px;white-space:nowrap;', right));
      (buttons || []).forEach(bt => {
        const btn = document.createElement('button');
        btn.textContent = bt.label;
        btn.style.cssText = 'pointer-events:auto;cursor:pointer;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:5px;font-size:9px;padding:3px 6px;font-family:inherit;';
        btn.onclick = bt.onclick;
        rightWrap.appendChild(btn);
      });
      top.appendChild(rightWrap);
      d.appendChild(top);
      if (sub) d.appendChild(mk('div', 'font-size:9px;color:#7d8a63;letter-spacing:0.06em;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;', sub));
      return d;
    };
    // Builds the "Zone · Lvl N" subline from a zone key and a combat
    // level, either of which may be missing (older or mid-connect client).
    const meta = (zoneKey, lvl) => {
      const bits = [];
      if (zoneKey) bits.push(this.zoneLabel_(zoneKey));
      if (lvl !== null && lvl !== undefined) bits.push('Lvl ' + lvl);
      return bits.join(' · ');
    };
    const myZoneKey = (this.zoneAt && this.me && this.me.pos) ? this.zoneAt(this.me.pos.x, this.me.pos.z) : '';
    el.appendChild(row((this.myName || 'YOU') + ' (you)', this.isWorldHost ? 'HOST' : 'ONLINE', true, null, meta(myZoneKey, this.combatLevel())));
    let n = 0;
    const totalRemotes = Object.keys(this.remotes || {}).length;
    const zoneFilter = this._plZoneFilter || '';
    const minLvl = this._plMinLvl || 0;
    for (const id in (this.remotes || {})) {
      const r = this.remotes[id];
      const theirZoneKey = (r.s && r.s.z) || '';
      const theirLvl = (r.s && r.s.cl !== undefined) ? r.s.cl : null;
      // A filter can only confirm a match, never a miss it cannot see -- a
      // player whose zone or level has not arrived yet is left out of a
      // narrowed list rather than guessed into it.
      if (zoneFilter && theirZoneKey !== zoneFilter) continue;
      if (minLvl && (theirLvl === null || theirLvl < minLvl)) continue;
      n++;
      const rawName = r.name || 'PLAYER';
      const btns = [];
      if (!(this.party && this.party.members.some(pm => pm.i === id))) btns.push({ label: 'INVITE', onclick: () => this.sendPartyInvite(id, rawName) });
      btns.push({ label: 'WHISPER', onclick: () => this.openWhisperTo(id, rawName) });
      if (this.isFriend(rawName)) btns.push({ label: 'UNFRIEND', onclick: () => this.removeFriend(rawName) });
      else btns.push({ label: 'ADD FRIEND', onclick: () => this.addFriend(rawName) });
      el.appendChild(row((r.s && r.s.pv ? '⚔ ' : '') + rawName, (r.s && r.s.h !== undefined ? r.s.h + ' HP' : 'ONLINE'), false, btns, meta(theirZoneKey, theirLvl)));
    }
    if (!n) el.appendChild(mk('div', 'font-size:11px;color:#5f6b4a;margin-top:10px;letter-spacing:0.08em;', totalRemotes ? 'NO ONE MATCHES THIS FILTER' : 'NO ONE ELSE ONLINE RIGHT NOW'));
    if (this.friends && this.friends.length) {
      el.appendChild(mk('div', 'font-size:11px;letter-spacing:0.2em;color:#7d8a63;margin-top:14px;margin-bottom:8px;border-top:1px solid #26281f;padding-top:10px;', 'FRIENDS'));
      this.friends.slice().sort().forEach(fn => {
        let onlineId = null;
        for (const rid in (this.rosterNames || {})) { if ((this.rosterNames[rid] || '').toUpperCase() === fn) { onlineId = rid; break; } }
        const isMe = fn === ((this.myName || '') + '').toUpperCase();
        const online = isMe || !!onlineId;
        const btns = [];
        if (onlineId) btns.push({ label: 'WHISPER', onclick: () => this.openWhisperTo(onlineId, fn) });
        btns.push({ label: 'REMOVE', onclick: () => this.removeFriend(fn) });
        // Friends are never filtered out -- the filter narrows the world's
        // roster, not the short list of people already worth tracking.
        const fr = onlineId ? this.remotes[onlineId] : null;
        const frSub = isMe ? meta(myZoneKey, this.combatLevel()) : (fr ? meta((fr.s && fr.s.z) || '', (fr.s && fr.s.cl !== undefined) ? fr.s.cl : null) : '');
        el.appendChild(row(fn, online ? 'ONLINE' : 'OFFLINE', online, btns, frSub));
      });
    }
    el.appendChild(mk('div', 'font-size:10px;color:#5f6b4a;margin-top:12px;letter-spacing:0.1em;', this.worldStatusText || ''));
  } updateQuickHealCd()"""
s = s[:i] + new_render + s[j + len('\n  } updateQuickHealCd()'):]
n += 1

io.open(SRC, 'w', encoding='utf-8').write(s)
print('73_whos_online: %d edits applied (1-2)' % n)
