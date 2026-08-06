#!/usr/bin/env python3
"""Patch 50: opt-in PvP. Edits /tmp/game-src.html.

(Numbered 50 deliberately: the UI track now works in the 50-69 range so the
two tracks stop colliding on patch numbers - four collisions on Aug 6 alone.)

Players can fight each other, kill each other, and lose NOTHING for dying:
death is the existing FELLED flow - rise at the camp with your pack intact -
with the killer's name on the banner and five seconds of respawn protection.

Consent is mutual and lives on the main menu as a PVP: ON/OFF toggle. Your
toggle arms your own blade and your own hide at once: with it off nobody can
touch you and your swings pass through other players. Both sides must be ON
for a hit to land. The flag rides the state packet every player already
broadcasts, so everyone can see who is dangerous: a red sword mark on their
nameplate and in the player list.

How a hit travels (the victim is always the authority - their toggle, their
armour, their block, their parry, their death, on their machine):

  attacker's swing/arrow  ->  finds the remote in its target list (both
  toggles on)             ->  applyDamage sees the _peerId and relays instead
  of applying             ->  host applies it if it is the victim, else
  forwards it to the victim's connection  ->  victim's pvpTakeHit runs the
  blow through the real applyDamage pipeline, shield facing and all.

This rides the machinery that already existed for host NPCs striking remote
players (remoteTargets + the phit channel): NPC blows keep their old channel
untouched, player blows get a new 'pvp' message that carries the attacker's
name and position, so the death banner can name the killer and blocking
face-on means something.
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


# ---------------------------------------------------------- menu toggle button
sub(
    '<input ref="{{ musicVolRef }}" type="range" min="0" max="100" value="75" style="margin-left:8px; width:104px; accent-color:#8fbf6a; vertical-align:middle; cursor:pointer;">',
    '<input ref="{{ musicVolRef }}" type="range" min="0" max="100" value="75" style="margin-left:8px; width:104px; accent-color:#8fbf6a; vertical-align:middle; cursor:pointer;">\n'
    '        <button ref="{{ pvpRef }}" sc-camel-on-click="{{ onPvp }}" title="Fight other players who also turn this on. Dying costs nothing - you rise at the camp with your pack intact." style="margin-left:8px; padding:9px 16px; background:transparent; border:1px solid #3a3f2c; color:#8f9a76; font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.14em; cursor:pointer;">PVP: OFF</button>',
    tag='menu button')

sub('  assistRef = React.createRef(); musicRef = React.createRef(); musicVolRef = React.createRef();',
    '  assistRef = React.createRef(); musicRef = React.createRef(); musicVolRef = React.createRef(); pvpRef = React.createRef();',
    tag='ref decl')

sub('      assistRef: this.assistRef, musicRef: this.musicRef, musicVolRef: this.musicVolRef,',
    '      assistRef: this.assistRef, musicRef: this.musicRef, musicVolRef: this.musicVolRef, pvpRef: this.pvpRef,',
    tag='ref map')

sub('      onAssist: () => this.toggleAssist(),',
    '      onAssist: () => this.toggleAssist(),\n      onPvp: () => this.togglePvp(),',
    tag='handler map')

# The menu is the one place guaranteed to build before play; syncing here also
# loads the persisted flag so a returning player is armed before they spawn.
sub("""  buildLoginUi() {
    const ov = this.overlayRef && this.overlayRef.current;
    if (!ov) return;""",
    """  buildLoginUi() {
    const ov = this.overlayRef && this.overlayRef.current;
    if (!ov) return;
    this.syncPvpBtn();""",
    tag='buildLoginUi sync')


# ------------------------------------------------------------------ PvP core
sub('  remoteTargets() {',
    """  // ------------------------------------------------------------------ PvP
  // Opt-in on BOTH sides. Your toggle arms your own blade and your own hide
  // at once: off means nobody can touch you and your swings pass through
  // other players. Dying to a player costs nothing but the walk back.
  syncPvpBtn() {
    if (this.pvpOn === undefined) { let v = null; try { v = localStorage.getItem('grim-pvp'); } catch (e) {} this.pvpOn = v === '1'; }
    const b = this.pvpRef && this.pvpRef.current;
    if (b) {
      b.textContent = 'PVP: ' + (this.pvpOn ? 'ON' : 'OFF');
      b.style.border = '1px solid ' + (this.pvpOn ? '#e0574f' : '#3a3f2c');
      b.style.color = this.pvpOn ? '#e0574f' : '#8f9a76';
    }
  }
  togglePvp() {
    this.syncPvpBtn();                            // ensures pvpOn is loaded first
    this.pvpOn = !this.pvpOn;
    try { localStorage.setItem('grim-pvp', this.pvpOn ? '1' : '0'); } catch (e) {}
    this.syncPvpBtn();
    this.sfx('switch');
    this.banner(this.pvpOn ? 'PVP ON' : 'PVP OFF',
      this.pvpOn
        ? 'YOU CAN FIGHT ANYONE ELSE WITH PVP ON - LOOK FOR THE RED SWORD BY THEIR NAME. DYING COSTS NOTHING: YOU RISE AT THE CAMP WITH YOUR PACK INTACT.'
        : 'NOBODY CAN TOUCH YOU, AND YOUR BLADE PASSES THROUGH OTHER PLAYERS.', false, 4600);
  }
  // The remote players my swings and shots may strike: both of us opted in,
  // they are alive, and I am not inside my own respawn protection.
  pvpTargets() {
    if (!this.pvpOn || !this.sharedWorldOn || !this.remotes) return [];
    if (Date.now() < (this._pvpSafeUntil || 0)) return [];
    const out = [];
    for (const id in this.remotes) { const r = this.remotes[id]; if (r.ent && r.ent._pv && r.ent.hp > 0) out.push(r.ent); }
    return out;
  }
  // One handler for every seat. Host: apply hits addressed to it, forward the
  // rest down the right connection. Client: every pvp message that reaches it
  // is addressed to it. The VICTIM is the authority - their toggle, their
  // armour, their block, their death, on their machine.
  onPvpMsg(from, m) {
    if (this.isWorldHost) {
      if (!m.to || m.to === 'HOST') { this.pvpTakeHit(m); return; }
      const c = this.hostConns && this.hostConns[m.to];
      if (c && c.open) { try { c.send({ t: 'pvp', d: m.d, k: m.k, o: m.o, n: m.n, p: m.p }); } catch (e) {} }
      return;
    }
    this.pvpTakeHit(m);
  }
  pvpTakeHit(m) {
    const me = this.me;
    if (!this.pvpOn || !me || me.hp <= 0 || !this.started || this.meDead) return;
    if (Date.now() < (this._pvpSafeUntil || 0)) return;
    const T = this.T;
    // The attacker's real position, so facing them with the shield up means
    // something. Fall back to dead ahead if the packet lost it.
    const ax = (m.p && m.p.length === 2) ? m.p[0] : me.pos.x + Math.sin(me.yaw) * 2.2;
    const az = (m.p && m.p.length === 2) ? m.p[1] : me.pos.z + Math.cos(me.yaw) * 2.2;
    const src = { pos: new T.Vector3(ax, 0, az), yaw: 0, stagger: 0, state: 'idle', st: 0, act: null, lungeT: 0, snareCd: 0 };
    this._pvpKiller = m.n || 'ANOTHER PLAYER';
    this.applyDamage(src, me, m.d, m.k || 'hit', me.pos.clone().add(new T.Vector3(0, 1.5, 0)), m.o || {});
    if (me.hp > 0) this._pvpKiller = null;       // only the killing blow keeps the credit
  }
  remoteTargets() {""",
    tag='pvp methods')


# ------------------------------------------------- flag rides the state packet
sub('w: me.weapon, an: (me.act && me.act.name) || 0,',
    'w: me.weapon, an: (me.act && me.act.name) || 0, pv: this.pvpOn ? 1 : 0,',
    tag='state pv flag')

sub('e.hp = s.h; e.max = s.m; r.age = 0;',
    'e.hp = s.h; e.max = s.m; e._pv = s.pv === 1; r.age = 0;',
    tag='remote pv flag')


# --------------------------------------------- remotes join the target lists
sub('? this.npcs.filter(n => n.hp > 0).concat((this.coop && this.netFoe.g.visible && this.netFoe.hp > 0) ? [this.netFoe] : [])',
    '? this.npcs.filter(n => n.hp > 0).concat((this.coop && this.netFoe.g.visible && this.netFoe.hp > 0) ? [this.netFoe] : []).concat(this.pvpTargets())',
    tag='melee targets')

sub('? ((this.coop && this.netFoe.g.visible && this.netFoe.hp > 0) ? this.npcs.concat([this.netFoe]) : this.npcs)',
    '? ((this.coop && this.netFoe.g.visible && this.netFoe.hp > 0) ? this.npcs.concat([this.netFoe]) : this.npcs).concat(this.pvpTargets())',
    tag='projectile targets')


# ------------------------------------------ applyDamage relays player targets
sub("""    // A hit landing on ANOTHER player is resolved on that player's own machine —
    // they own their HP, armour and death. Relay it and stop here.
    if (this.sharedWorldOn && this.isWorldHost && t && t._peerId) {
      this.netTo(t._peerId, { t: 'phit', d: Math.round(dmg), k: kind, o: opt || {} });
      return;
    }""",
    """    // A hit landing on ANOTHER player is resolved on that player's own machine —
    // they own their HP, armour and death. Relay it and stop here. NPC blows
    // the host relays keep the old phit channel and no consent check; a
    // PLAYER's blow becomes a pvp message that only fires when both toggles
    // are on, and carries the attacker's name and position for the victim.
    if (this.sharedWorldOn && t && t._peerId) {
      const mine = from === this.me;
      if (mine && !(this.pvpOn && t._pv)) return;
      if (mine && Date.now() < (this._pvpSafeUntil || 0)) return;
      const wire = mine
        ? { t: 'pvp', to: t._peerId, d: Math.round(dmg), k: kind, o: opt || {}, n: this.myName || 'A PLAYER', p: [+this.me.pos.x.toFixed(1), +this.me.pos.z.toFixed(1)] }
        : { t: 'phit', d: Math.round(dmg), k: kind, o: opt || {} };
      if (this.isWorldHost) this.netTo(t._peerId, wire);
      else if (mine && this.hostConn && this.hostConn.open) { try { this.hostConn.send(wire); } catch (e) {} }
      else return;
      if (mine) {
        this.splat(this.bodyAnchor(t) || t.pos.clone().add(new this.T.Vector3(0, 1.5, 0)), Math.round(dmg), kind === 'crit' ? 'crit' : 'hit');
        this.sfx('hit');
      }
      return;
    }""",
    tag='applyDamage relay')


# --------------------------------------------------------- route the message
sub("if (m.t === 'phit' && !this.isWorldHost) {",
    "if (m.t === 'pvp') { this.onPvpMsg(from, m); return; } if (m.t === 'phit' && !this.isWorldHost) {",
    tag='onWorldData route')


# ------------------------------------- death: name the killer, protect respawn
sub("""      this.meDead = true; this.meRespawn = 3.4;
      this.banner('FELLED', 'RISE AGAIN AT THE CAMP', false, 3000);""",
    """      this.meDead = true; this.meRespawn = 3.4;
      if (this._pvpKiller) {
        this.banner('SLAIN BY ' + this._pvpKiller, 'YOUR PACK IS SAFE - RISE AGAIN AT THE CAMP', false, 3400);
        this._pvpKiller = null;
      } else this.banner('FELLED', 'RISE AGAIN AT THE CAMP', false, 3000);""",
    tag='death banner')

sub("        me.elev = null; me._vy = 0; me._air = false; if (me.vel) me.vel.set(0, 0, 0);   // 1d: respawn clears fall state like the teleport does",
    """        me.elev = null; me._vy = 0; me._air = false; if (me.vel) me.vel.set(0, 0, 0);   // 1d: respawn clears fall state like the teleport does
        this._pvpSafeUntil = Date.now() + 5000;   // five seconds where no player can touch you, and you cannot touch them""",
    tag='respawn protection')


# ----------------------------------------------- show who is dangerous
sub('r.tag.textContent = r.name;',
    "const pvpT = !!(this.pvpOn && r.ent && r.ent._pv); r.tag.textContent = (pvpT ? '⚔ ' : '') + r.name; r.tag.style.color = pvpT ? '#e0574f' : '#e8c774';",
    tag='nametag mark')

sub("el.appendChild(row(r.name || 'PLAYER', (r.s && r.s.h !== undefined ? r.s.h + ' HP' : 'ONLINE'), false));",
    "el.appendChild(row((r.s && r.s.pv ? '⚔ ' : '') + (r.name || 'PLAYER'), (r.s && r.s.h !== undefined ? r.s.h + ' HP' : 'ONLINE'), false));",
    tag='player list mark')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('50_pvp: %d edits applied' % n)
