#!/usr/bin/env python3
"""Patch 65: HUD layout cleanup (debug overlay, party frames, quest HUD).

Three things Kevin flagged after patches 62-64 landed:

1. The FPS/coords debug stamp was fixed at left:12px;bottom:12px -- exactly
   where the new chat box (patch 62) also lives. Moved to the bottom-right,
   stacked above the existing PRESS H / boat-interact hint boxes (which are
   also right:14px, at bottom:14px and bottom:76px) with enough clearance
   that none of the three ever overlap.

2. Party frames (patch 63) were a hardcoded position:fixed;left:14px;top:14px
   block -- sitting exactly on top of both the player's own health bar and
   the quest helper box, which live in the same top-left corner via normal
   document flow. Rather than hardcode a second pixel guess that could drift
   out of sync with the health block's real size, positionPartyFrames() reads
   the live bounding box of the stamina/mana row (a sibling of the mana fill
   ref that's always present) and anchors the frames block directly under it
   every render -- same left edge, fixed gap below. This is also where "each
   member's name at the top of their frame" already lived (partyFrameRow's
   top row) -- nothing needed there.

3. Mana was missing from party frames entirely -- HP only. Fixed two ways:
   myWorldState() now includes mn/mc (current/max mana) in the periodic self
   state broadcast, so it rides the exact same already-relayed 's'/'w' path
   position and HP already use (zero relay changes, same reasoning already
   established for whispers in patch 64). partyFrameRow() gained a second,
   thinner bar under HP for it. A remote on an older build simply never sends
   mn, so the bar is skipped entirely for that row rather than drawn stuck at
   0, which would misread as "out of mana."

4. The quest helper box's margin-top grew from 14px to 296px so it clears a
   full 5-member (PARTY_CAP) party-frame stack even in the worst case (every
   member showing both HP and mana bars) -- measured directly against a live
   5-member render rather than estimated, with a 10px gap to spare.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 65 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


# ---- 1. debug/coords stamp: bottom-left (under chat) -> bottom-right ------
sub(
"""      const cd = document.createElement('div');
      cd.style.cssText = 'position:fixed;left:12px;bottom:12px;padding:6px 11px;' +
        'background:rgba(10,11,8,0.8);border:1px solid #3a3f2c;color:#7d8a63;' +
        'font-family:IBM Plex Mono,monospace;font-size:10px;letter-spacing:0.10em;' +
        'z-index:' + this.Z.debug + ';pointer-events:none;white-space:pre;';
      document.body.appendChild(cd); this._coordHud = cd;""",
"""      const cd = document.createElement('div');
      // Bottom-right, stacked above the PRESS H / boat-interact hints below
      // it (right:14px;bottom:14px and bottom:76px) with enough clearance
      // that a full 3-line readout never touches either one.
      cd.style.cssText = 'position:fixed;right:14px;bottom:130px;padding:6px 11px;' +
        'background:rgba(10,11,8,0.8);border:1px solid #3a3f2c;color:#7d8a63;' +
        'font-family:IBM Plex Mono,monospace;font-size:10px;letter-spacing:0.10em;' +
        'z-index:' + this.Z.debug + ';pointer-events:none;white-space:pre;text-align:right;';
      document.body.appendChild(cd); this._coordHud = cd;""",
    tag='debug HUD reposition')

# ---- 2. myWorldState(): broadcast current/max mana alongside hp/max -------
sub(
"""an: (me.act && me.act.name) || 0, pv: this.pvpOn ? 1 : 0, h: Math.round(me.hp), m: Math.round(me.max), b: this.worn && this.worn.BODY ? this.worn.BODY.item : 'NONE',""",
"""an: (me.act && me.act.name) || 0, pv: this.pvpOn ? 1 : 0, h: Math.round(me.hp), m: Math.round(me.max), mn: Math.round(me.mana || 0), mc: Math.round(me.manaCap || 100), b: this.worn && this.worn.BODY ? this.worn.BODY.item : 'NONE',""",
    tag='myWorldState mana fields')

# ---- 3. party frames: anchor under the live health block, widen slightly -
sub(
"""  buildPartyFramesDom() {
    if (this.pfEl) return;
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;left:14px;top:14px;width:190px;display:none;flex-direction:column;gap:4px;z-index:' + this.Z.hint + ';';
    document.body.appendChild(d);
    this.pfEl = d;
  }""",
"""  buildPartyFramesDom() {
    if (this.pfEl) return;
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;width:230px;display:none;flex-direction:column;gap:4px;z-index:' + this.Z.hint + ';';
    document.body.appendChild(d);
    this.pfEl = d;
  }
  // Anchored to the live stamina/mana row (a sibling of manaFillRef, always
  // present once the HUD is built) instead of a second hardcoded pixel
  // guess -- stays correct under your own health bar even if that block's
  // own size ever changes, and matches its left edge exactly.
  positionPartyFrames() {
    if (!this.pfEl) return;
    const bar = this.manaFillRef && this.manaFillRef.current;
    const row = bar && bar.parentElement && bar.parentElement.parentElement;
    if (!row) return;
    const r = row.getBoundingClientRect();
    if (!r.width && !r.height) return;   // HUD not laid out yet (e.g. hidden)
    this.pfEl.style.left = Math.round(r.left) + 'px';
    this.pfEl.style.top = Math.round(r.bottom + 10) + 'px';
  }""",
    tag='party frames positioning')

# ---- 4. partyFrameRow(): add a mana bar under HP, skipped when unknown ----
sub(
"""  partyFrameRow(name, hp, max, opts) {
    opts = opts || {};
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    const row = mk('div', 'background:rgba(12,13,9,0.88);border:1px solid #3a3f2c;border-radius:8px;padding:5px 8px;pointer-events:auto;' + (opts.dead ? 'opacity:0.5;' : ''));
    const top = mk('div', 'display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:3px;');
    const nm = mk('span', 'font-size:11px;font-weight:700;color:#e8c774;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;', (opts.leader ? '★ ' : '') + (opts.pv ? '⚔ ' : '') + name);
    top.appendChild(nm);
    if (opts.self && this.party) {
      const lv = document.createElement('button');
      lv.textContent = 'LEAVE';
      lv.style.cssText = 'pointer-events:auto;cursor:pointer;flex:none;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:5px;font-size:9px;padding:2px 5px;font-family:inherit;';
      lv.onclick = () => this.leaveParty();
      top.appendChild(lv);
    } else if (!opts.self && opts.id && this.amPartyLeader()) {
      const kk = document.createElement('button');
      kk.textContent = 'KICK';
      kk.style.cssText = 'pointer-events:auto;cursor:pointer;flex:none;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:5px;font-size:9px;padding:2px 5px;font-family:inherit;';
      kk.onclick = () => this.kickPartyMember(opts.id);
      top.appendChild(kk);
    }
    const track = mk('div', 'height:8px;background:#1c1e15;border:1px solid #2a2c20;border-radius:4px;overflow:hidden;');
    const pct = max > 0 ? Math.max(0, Math.min(1, hp / max)) : 0;
    const fill = mk('div', 'height:100%;width:' + Math.round(pct * 100) + '%;background:' + (pct > 0.5 ? '#5fae3d' : pct > 0.25 ? '#c8a24a' : '#a3342c') + ';transition:width 200ms;');
    track.appendChild(fill);
    row.appendChild(top); row.appendChild(track);
    return row;
  }""",
"""  partyFrameRow(name, hp, max, mana, manaMax, opts) {
    opts = opts || {};
    const mk = (tag, css, txt) => { const d = document.createElement(tag); d.style.cssText = css; if (txt !== undefined) d.textContent = txt; return d; };
    const row = mk('div', 'background:rgba(12,13,9,0.88);border:1px solid #3a3f2c;border-radius:8px;padding:5px 8px;pointer-events:auto;' + (opts.dead ? 'opacity:0.5;' : ''));
    const top = mk('div', 'display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:3px;');
    const nm = mk('span', 'font-size:11px;font-weight:700;color:#e8c774;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;', (opts.leader ? '★ ' : '') + (opts.pv ? '⚔ ' : '') + name);
    top.appendChild(nm);
    if (opts.self && this.party) {
      const lv = document.createElement('button');
      lv.textContent = 'LEAVE';
      lv.style.cssText = 'pointer-events:auto;cursor:pointer;flex:none;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:5px;font-size:9px;padding:2px 5px;font-family:inherit;';
      lv.onclick = () => this.leaveParty();
      top.appendChild(lv);
    } else if (!opts.self && opts.id && this.amPartyLeader()) {
      const kk = document.createElement('button');
      kk.textContent = 'KICK';
      kk.style.cssText = 'pointer-events:auto;cursor:pointer;flex:none;background:#1c1e15;color:#7d8a63;border:1px solid #3a3f2c;border-radius:5px;font-size:9px;padding:2px 5px;font-family:inherit;';
      kk.onclick = () => this.kickPartyMember(opts.id);
      top.appendChild(kk);
    }
    const track = mk('div', 'height:8px;background:#1c1e15;border:1px solid #2a2c20;border-radius:4px;overflow:hidden;');
    const pct = max > 0 ? Math.max(0, Math.min(1, hp / max)) : 0;
    const fill = mk('div', 'height:100%;width:' + Math.round(pct * 100) + '%;background:' + (pct > 0.5 ? '#5fae3d' : pct > 0.25 ? '#c8a24a' : '#a3342c') + ';transition:width 200ms;');
    track.appendChild(fill);
    row.appendChild(top); row.appendChild(track);
    // A remote on an older build never sends mn/mc at all -- draw nothing
    // rather than a bar stuck at 0, which would misread as "out of mana."
    if (mana !== null && mana !== undefined) {
      const mtrack = mk('div', 'height:6px;background:#1c1e15;border:1px solid #2a2c20;border-radius:3px;overflow:hidden;margin-top:3px;');
      const mpct = manaMax > 0 ? Math.max(0, Math.min(1, mana / manaMax)) : 0;
      const mfill = mk('div', 'height:100%;width:' + Math.round(mpct * 100) + '%;background:#4a8fd8;transition:width 200ms;');
      mtrack.appendChild(mfill);
      row.appendChild(mtrack);
    }
    return row;
  }""",
    tag='partyFrameRow mana bar')

# ---- 5. renderPartyFrames(): position each render, pass mana through ------
sub(
"""  renderPartyFrames() {
    this.buildPartyFramesDom();
    const el = this.pfEl;
    while (el.firstChild) el.removeChild(el.firstChild);
    if (!this.party || !this.party.members || !this.party.members.length) { el.style.display = 'none'; return; }
    el.style.display = 'flex';
    const meMember = this.party.members.find(pm => pm.i === this.netId);
    if (meMember && this.me) {
      el.appendChild(this.partyFrameRow(this.myName || meMember.n || 'YOU', this.me.hp, this.me.max, { leader: !!meMember.leader, pv: !!this.pvpOn, dead: this.me.hp <= 0, self: true }));
    }
    this.party.members.forEach(pm => {
      if (pm.i === this.netId) return;
      const r = this.remotes[pm.i];
      const hp = r && r.ent ? r.ent.hp : 0;
      const max = r && r.ent ? r.ent.max : 100;
      el.appendChild(this.partyFrameRow(pm.n || 'PLAYER', hp, max, { leader: !!pm.leader, pv: !!(r && r.ent && r.ent._pv), dead: !!(r && r.ent && r.ent.hp <= 0), self: false, id: pm.i }));
    });
  }""",
"""  renderPartyFrames() {
    this.buildPartyFramesDom();
    this.positionPartyFrames();
    const el = this.pfEl;
    while (el.firstChild) el.removeChild(el.firstChild);
    if (!this.party || !this.party.members || !this.party.members.length) { el.style.display = 'none'; return; }
    el.style.display = 'flex';
    const meMember = this.party.members.find(pm => pm.i === this.netId);
    if (meMember && this.me) {
      el.appendChild(this.partyFrameRow(this.myName || meMember.n || 'YOU', this.me.hp, this.me.max, this.me.mana, this.me.manaCap || 100, { leader: !!meMember.leader, pv: !!this.pvpOn, dead: this.me.hp <= 0, self: true }));
    }
    this.party.members.forEach(pm => {
      if (pm.i === this.netId) return;
      const r = this.remotes[pm.i];
      const hp = r && r.ent ? r.ent.hp : 0;
      const max = r && r.ent ? r.ent.max : 100;
      const mana = (r && r.s && r.s.mn !== undefined) ? r.s.mn : null;
      const manaMax = (r && r.s && r.s.mc) || 100;
      el.appendChild(this.partyFrameRow(pm.n || 'PLAYER', hp, max, mana, manaMax, { leader: !!pm.leader, pv: !!(r && r.ent && r.ent._pv), dead: !!(r && r.ent && r.ent.hp <= 0), self: false, id: pm.i }));
    });
  }""",
    tag='renderPartyFrames position+mana wiring')

# ---- 6. quest helper box: push down to clear a full 5-member party stack --
sub(
"""      <div ref="{{ questRef }}" style="display:none; margin-top:14px; width:250px; padding:10px 13px; background:rgba(10,11,8,0.62); border:2px solid #2c2f24; border-left:3px solid #c8a24a;">""",
"""      <div ref="{{ questRef }}" style="display:none; margin-top:296px; width:250px; padding:10px 13px; background:rgba(10,11,8,0.62); border:2px solid #2c2f24; border-left:3px solid #c8a24a;">""",
    tag='quest box pushed down')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('65_hud_layout: %d edits applied (1-6)' % n)
