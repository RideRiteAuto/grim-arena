#!/usr/bin/env python3
"""Patch 52: PvP finished. Edits /tmp/game-src.html.

Kevin's live test showed the truth: hitsplats but no damage. Patch 50 was
written against the old peer-to-peer shape, but the LIVE game runs on the
Cloudflare relay (one websocket per player, worker forwards by allowlist),
and the worker's RELAYED set did not contain 'pvp' - every hit died at the
relay. The worker fix is a separate edit to relay-worker.js (it deploys from
the same push via Workers Builds); this patch finishes the client side:

- onPvpMsg is relay-aware: any directed message that reaches you IS yours.
  (The old code made the sim owner try hostConns[] that never exist in relay
  mode, dropping every hit on the owner.)
- Victim clamps incoming damage to 80 before armour - a tampered client can
  lie, but it cannot one-shot anybody.
- Kill confirmation, the way big MMOs attribute kills: the VICTIM announces
  its own death to the killer ('pvpk', directed, relay-stamped sender id),
  and the killer only honours it if they really damaged that player in the
  last 30 seconds. Kill credit cannot be gifted by a spoofed message.
- Dog tags: killing a player mints 'DOG TAG: <NAME>' into your pack (grant
  path - spills to overflow, never lost to a full pack). Dynamic item ids
  registered into the ITEMS cache on demand and re-registered at save load
  BEFORE the validator runs, so tags bank, stack, tooltip and persist like
  any other item. Names are sanitised to [A-Z0-9 _-] so a hostile name can
  never smuggle HTML into a tooltip. value:0 keeps Fenwick out of it.
  Anti kill-trading: one tag per victim per 10 minutes.
- PvP kills and deaths counted, saved in the character blob (guest and
  cloud), shown on the K stats page footer.
- Burn and frost already ride the wire in opt (freeze respects the existing
  6s freeze cooldown = diminishing returns; burn never lands the killing
  blow) - they were only dead because the relay dropped the message.
- No combat XP from player hits (the relay branch returns before awardXp):
  deliberate, XP farming by kill trading is the classic new-MMO mistake.
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


# ------------------------------------------------- 1. relay-aware routing
sub("""  onPvpMsg(from, m) {
    if (this.isWorldHost) {
      if (!m.to || m.to === 'HOST') { this.pvpTakeHit(m); return; }
      const c = this.hostConns && this.hostConns[m.to];
      if (c && c.open) { try { c.send({ t: 'pvp', d: m.d, k: m.k, o: m.o, n: m.n, p: m.p }); } catch (e) {} }
      return;
    }
    this.pvpTakeHit(m);
  }""",
    """  onPvpMsg(from, m) {
    // Relay mode: the worker only ever delivers messages addressed to this
    // socket, so whatever arrives is ours - including on the sim owner, who
    // has no hostConns to forward through.
    if (this._relayMode) { this.pvpTakeHit(m, from); return; }
    if (this.isWorldHost) {
      if (!m.to || m.to === 'HOST') { this.pvpTakeHit(m, from); return; }
      const c = this.hostConns && this.hostConns[m.to];
      if (c && c.open) { try { c.send({ t: 'pvp', d: m.d, k: m.k, o: m.o, n: m.n, p: m.p, _p: from }); } catch (e) {} }
      return;
    }
    this.pvpTakeHit(m, from);
  }""",
    tag='onPvpMsg relay-aware')

# ------------------------------------- 2. victim clamps damage, keeps killer id
sub("""  pvpTakeHit(m) {
    const me = this.me;
    if (!this.pvpOn || !me || me.hp <= 0 || !this.started || this.meDead) return;
    if (Date.now() < (this._pvpSafeUntil || 0)) return;""",
    """  pvpTakeHit(m, from) {
    const me = this.me;
    if (!this.pvpOn || !me || me.hp <= 0 || !this.started || this.meDead) return;
    if (Date.now() < (this._pvpSafeUntil || 0)) return;
    // Never trust the wire: cap the claimed damage at the biggest hit the
    // game can legitimately produce, before armour has its say.
    m = Object.assign({}, m, { d: Math.max(0, Math.min(80, Math.round(Number(m.d) || 0))) });
    this._pvpKillerId = from || null;""",
    tag='pvpTakeHit clamp + killer id')

sub("    this._pvpKiller = m.n || 'ANOTHER PLAYER';",
    "    this._pvpKiller = String(m.n || 'ANOTHER PLAYER').toUpperCase().replace(/[^A-Z0-9 _-]/g, '').slice(0, 14) || 'ANOTHER PLAYER';",
    tag='killer name sanitised')

sub("    if (me.hp > 0) this._pvpKiller = null;       // only the killing blow keeps the credit",
    "    if (me.hp > 0) { this._pvpKiller = null; this._pvpKillerId = null; }   // only the killing blow keeps the credit",
    tag='survive clears credit')

# ---------------------------------------- 3. attacker remembers who they hit
sub("""      else return;
      if (mine) {
        this.splat(this.bodyAnchor(t) || t.pos.clone().add(new this.T.Vector3(0, 1.5, 0)), Math.round(dmg), kind === 'crit' ? 'crit' : 'hit');""",
    """      else return;
      if (mine) {
        (this._pvpHitAt = this._pvpHitAt || {})[t._peerId] = Date.now();   // kill attribution window
        this.splat(this.bodyAnchor(t) || t.pos.clone().add(new this.T.Vector3(0, 1.5, 0)), Math.round(dmg), kind === 'crit' ? 'crit' : 'hit');""",
    tag='hit attribution stamp')

# ----------------------------------------------- 4. route pvpk in onWorldData
sub("if (m.t === 'pvp') { this.onPvpMsg(from, m); return; }",
    "if (m.t === 'pvp') { this.onPvpMsg(m._p || from, m); return; } if (m.t === 'pvpk') { this.onPvpKill(m._p || from, m); return; }",
    tag='onWorldData pvpk route')

# ------------------------------------- 5. kill confirmation + dog tag minting
sub("""  pvpTargets() {
    if (!this.pvpOn || !this.sharedWorldOn || !this.remotes) return [];""",
    """  // The victim announced its own death. Honour the claim only if we really
  // hurt that player inside the last 30 seconds - kill credit works like MMO
  // tagging, and a spoofed message earns nothing. One dog tag per victim per
  // 10 minutes, so kill trading cannot mint a stack of them.
  onPvpKill(from, m) {
    if (!this._relayMode && this.isWorldHost && m.to && m.to !== 'HOST') {
      const c = this.hostConns && this.hostConns[m.to];
      if (c && c.open) { try { c.send({ t: 'pvpk', n: m.n, _p: from }); } catch (e) {} }
      return;
    }
    const hitAt = (this._pvpHitAt || {})[from] || 0;
    if (!hitAt || Date.now() - hitAt > 30000) return;
    delete this._pvpHitAt[from];
    this.pvpStats = this.pvpStats || { k: 0, d: 0 };
    this.pvpStats.k++;
    this.scheduleSave();
    const nm = String(m.n || 'A PLAYER').toUpperCase().replace(/[^A-Z0-9 _-]/g, '').slice(0, 14) || 'A PLAYER';
    const cd = this._tagCd = this._tagCd || {};
    const now = Date.now();
    if (now >= (cd[from] || 0)) {
      cd[from] = now + 600000;
      this.dogTagReg('DOG TAG: ' + nm);
      this.grantItem('DOG TAG: ' + nm, 1);
      this.banner('YOU SLEW ' + nm, 'THEIR DOG TAG IS IN YOUR PACK - PROOF OF THE KILL', false, 4200);
    } else {
      this.banner('YOU SLEW ' + nm, 'NO TAG THIS TIME - YOU TOOK THEIRS MINUTES AGO', false, 3400);
    }
    this.sfx('win');
  }
  // Dog tags are minted per victim ('DOG TAG: NAME'), registered into the
  // item table on demand so every existing system - icons, tooltips, the
  // bank, save validation - treats them like any other item. value 0 keeps
  // them out of Fenwick's ledger: proof of a kill is not for sale.
  dogTagReg(id) {
    const IT = this.ITEMS();
    if (IT[id]) return IT[id];
    const nm = String(id).slice(9).toUpperCase().replace(/[^A-Z0-9 _-]/g, '').slice(0, 14);
    if (!nm) return null;
    const safeId = 'DOG TAG: ' + nm;
    if (!IT[safeId]) {
      const ini = nm.replace(/[^A-Z0-9]/g, '').slice(0, 2) || 'GW';
      IT[safeId] = {
        name: safeId, stack: true, slot: null, hands: 0, wieldAs: -1, style: '',
        stats: { att: 0, str: 0, def: 0, mag: 0, rng: 0 }, value: 0, dogTag: true,
        icon: '<svg viewBox="0 0 30 30" style="width:100%;height:100%;display:block;">' +
          '<path d="M11 7 Q15 3.5 19 7" fill="none" stroke="#6f7884" stroke-width="1.6"/>' +
          '<rect x="8.5" y="7.5" width="13" height="18" rx="5" fill="#9aa3ad" stroke="#0e0f0d" stroke-width="1.8"/>' +
          '<circle cx="15" cy="11" r="1.4" fill="#0e0f0d"/>' +
          '<text x="15" y="19.5" text-anchor="middle" font-size="7" font-weight="800" fill="#434b56" font-family="monospace">' + ini + '</text>' +
          '<path d="M11.5 22.5 h7" stroke="#7d8694" stroke-width="1.2"/></svg>'
      };
    }
    return IT[safeId];
  }
  pvpTargets() {
    if (!this.pvpOn || !this.sharedWorldOn || !this.remotes) return [];""",
    tag='onPvpKill + dogTagReg')

# ------------------------------------------ 6. death: count it, tell the killer
sub("""      if (this._pvpKiller) {
        this.banner('SLAIN BY ' + this._pvpKiller, 'YOUR PACK IS SAFE - RISE AGAIN AT THE CAMP', false, 3400);
        this._pvpKiller = null;
      } else this.banner('FELLED', 'RISE AGAIN AT THE CAMP', false, 3000);""",
    """      if (this._pvpKiller) {
        this.banner('SLAIN BY ' + this._pvpKiller, 'YOUR PACK IS SAFE - RISE AGAIN AT THE CAMP', false, 3400);
        this.pvpStats = this.pvpStats || { k: 0, d: 0 };
        this.pvpStats.d++;
        this.scheduleSave();
        const kid = this._pvpKillerId;
        if (kid) {
          const ack = { t: 'pvpk', to: kid, n: this.myName || 'A PLAYER' };
          if (!this._relayMode && this.isWorldHost) this.netTo(kid, ack);
          else if (this.hostConn && this.hostConn.open) { try { this.hostConn.send(ack); } catch (e) {} }
        }
        this._pvpKiller = null; this._pvpKillerId = null;
      } else this.banner('FELLED', 'RISE AGAIN AT THE CAMP', false, 3000);""",
    tag='death counts + pvpk send')

# --------------------------------------------------- 7. stats ride the save
sub("      unlocks: this.unlocks || {}, at: at, mount: mount",
    "      unlocks: this.unlocks || {}, at: at, mount: mount,\n      pvp: this.pvpStats || { k: 0, d: 0 }",
    tag='charSave pvp')

sub("""  applySaveBlob(raw) {
    // same validation discipline as invLoad: unknown or corrupt entries can
    // never crash the game or fabricate items.
    const IT = this.ITEMS();""",
    """  applySaveBlob(raw) {
    // same validation discipline as invLoad: unknown or corrupt entries can
    // never crash the game or fabricate items.
    const IT = this.ITEMS();
    // Dog tag ids are dynamic - register every one found in the save BEFORE
    // the validator runs, or it would silently delete them. A tampered name
    // fails the sanitiser inside dogTagReg and stays unregistered, so the
    // validator throws it away: exactly right.
    const regTag = (c) => { if (c && typeof c.item === 'string' && c.item.indexOf('DOG TAG: ') === 0) this.dogTagReg(c.item); };
    if (raw) {
      (Array.isArray(raw.inv) ? raw.inv : []).forEach(regTag);
      (Array.isArray(raw.overflow) ? raw.overflow : []).forEach(regTag);
      (Array.isArray(raw.bank) ? raw.bank : []).forEach(regTag);
      const pvR = raw.pvp || {};
      this.pvpStats = { k: Math.max(0, Math.floor(Number(pvR.k)) || 0), d: Math.max(0, Math.floor(Number(pvR.d)) || 0) };
    } else {
      this.pvpStats = { k: 0, d: 0 };
    }""",
    tag='applySaveBlob pvp + tag reg')

# -------------------------------------------- 8. K page shows the pvp record
sub("    this._skTotalEl.textContent = 'TOTAL LEVEL ' + total + ' / ' + (99 * this.SKILL_INFO().length);",
    """    const pvS = this.pvpStats || { k: 0, d: 0 };
    this._skTotalEl.textContent = 'TOTAL LEVEL ' + total + ' / ' + (99 * this.SKILL_INFO().length) +
      '  ·  PVP: ' + pvS.k + ' KILL' + (pvS.k === 1 ? '' : 'S') + ', ' + pvS.d + ' DEATH' + (pvS.d === 1 ? '' : 'S');""",
    tag='skills footer pvp record')


# ------------------------------- 9. Fenwick will not buy proof of a kill
# fenBase floors every known item at 1g, so value:0 alone does not opt out.
sub("  fenBuys(id) { return id !== 'GOLD CROWNS' && this.fenBase(id) > 0; }",
    "  fenBuys(id) { const d = this.itemDef(id); if (d && d.dogTag) return false; return id !== 'GOLD CROWNS' && this.fenBase(id) > 0; }",
    tag='fenBuys refuses dog tags')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('52_pvp_finish: %d edits applied' % n)
