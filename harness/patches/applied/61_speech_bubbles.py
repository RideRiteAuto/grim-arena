#!/usr/bin/env python3
"""Patch 61: one shared speech-bubble system, generalized catchphrases.

Kevin: "there's some characters in the game that have catchphrases... it
doesn't appear right above their head for most of them... there should be a
max distance on how far away that will actually be visible to you, and the
text should get smaller as you get further away... same thing with the
catchphrases at those random NPCs say."

Root cause: showShout()/stepShouts() was ONE global DOM element, positioned
every frame at this.foe's position, visible only while f.shouts was true on
whichever entity happened to be your CURRENT LOCKED TARGET. Mr. Sailers (the
only NPC with shouts:true) is a wandering world boss, not a duel opponent -
his catchphrase has nothing to do with what you have locked on. Whenever he
wasn't your foe, his line either didn't show or was positioned over whatever
you did have targeted. The Warden's scripted phase-change bark (onBossEvent,
m.shout) had the exact same bug for the same reason.

Fix: bubbles are keyed per-entity (sayBubble/npcSay), not by a single shared
element tied to this.foe. Every NPC with .shouts talks on its own timer,
independently, positioned over its own head. This is also the exact
primitive patch 62 (chat) needs for "my chat floats over my own head" and
"a nearby player's local chat floats over theirs" - one mechanism, not three
copies of the same projection math.

Distance rules, the other half of the ask: BUBBLE_NEAR_R (full size) to
BUBBLE_MAX_R (invisible) with a linear size/opacity falloff in between -
matches how nametag/chat-bubble LOD works in the games this is modeled on.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0
# Every (old, new) pair actually applied, in order - lets the browser pusher
# replay this exact same transformation against the live bundle instead of
# needing a second hand-written copy that could drift from this file.
LOG = []


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 61 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    LOG.append((old, new))
    n += 1


OLD_BLOCK = """  // ------------------------------------------------------------- shouts
  // Mr. Sailers bellows random gibberish that floats over his head mid-fight.
  showShout(text, gold, dur) {
    const layer = this.splatRef.current; if (!layer) return;
    if (!this.shoutEl) {
      this.shoutEl = document.createElement('div');
      this.shoutEl.style.cssText = 'position:absolute;transform:translate(-50%,-100%) rotate(-2deg);background:#f2efe6;color:#1a1a12;' +
        'border:2px solid #0e0f0d;padding:7px 12px;font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:15px;letter-spacing:0.04em;' +
        'box-shadow:3px 4px 0 rgba(0,0,0,0.45);white-space:nowrap;display:none;';
      layer.appendChild(this.shoutEl);
    }
    this.shoutText = text;
    this.shoutUntil = performance.now() + (dur || 2400);
    this.shoutEl.textContent = text;
    this.shoutEl.style.background = gold ? '#e8c774' : '#f2efe6';
    this.shoutEl.style.fontSize = gold ? '18px' : '15px';
    this.shoutEl.style.transform = 'translate(-50%,-100%) rotate(' + (Math.random() * 6 - 3) + 'deg)';
  }

  stepShouts(dt) {
    const layer = this.splatRef.current; if (!layer) return;
    const f = this.foe;
    if (this.mode === 'ai' && f.shouts && !this.roundOver && !this.matchOver && f.hp > 0) {
      this.shoutT = (this.shoutT ?? 2.5) - dt;
      if (this.shoutT <= 0) {
        this.shoutT = 3.5 + Math.random() * 4.5;
        const LINES = ['GET OFF YOUR SEAT!', 'DID YOU CLOSE OUT YOUR PM?', 'ANY LINE LIMITERS?'];
        this.showShout(LINES[Math.floor(Math.random() * LINES.length)]);
        this.sfx('tick');
      }
    }
    if (this.shoutEl) {
      const on = performance.now() < (this.shoutUntil || 0) && f.shouts && f.hp > 0;
      this.shoutEl.style.display = on ? 'block' : 'none';
      if (on) {
        const v = f.pos.clone().add(new this.T.Vector3(0, 3.15, 0)).project(this.cam);
        if (v.z > 1) { this.shoutEl.style.display = 'none'; return; }
        const rect = layer.getBoundingClientRect();
        this.shoutEl.style.left = ((v.x * 0.5 + 0.5) * rect.width) + 'px';
        this.shoutEl.style.top = ((-v.y * 0.5 + 0.5) * rect.height) + 'px';
      }
    }
  }

"""

NEW_BLOCK = """  // ------------------------------------------------------------- speech bubbles
  // One shared mechanism for every floating line above a head: your own
  // chat, a nearby player's chat, an NPC catchphrase. Same visual, same
  // distance rules, keyed per-entity so more than one can talk at once -
  // the old version was a single shared DOM node tied to this.foe.
  BUBBLE_NEAR_R = 10;    // full size inside this range
  BUBBLE_MAX_R = 55;     // invisible past this range - "not the whole map"
  BUBBLE_MIN_SCALE = 0.55;

  bubbleSlot(key) {
    if (!this._bubbles) this._bubbles = {};
    let b = this._bubbles[key];
    if (b) return b;
    const layer = this.splatRef && this.splatRef.current;
    if (!layer) return null;
    const d = document.createElement('div');
    d.style.cssText = 'position:absolute;transform:translate(-50%,-100%);background:#f2efe6;color:#1a1a12;' +
      'border:2px solid #0e0f0d;padding:6px 11px;font-family:"IBM Plex Mono",monospace;font-weight:600;' +
      'font-size:14px;letter-spacing:0.03em;box-shadow:3px 4px 0 rgba(0,0,0,0.45);white-space:normal;' +
      'max-width:240px;text-align:center;line-height:1.3;display:none;pointer-events:none;z-index:' + this.Z.tag + ';' +
      'transition:opacity 120ms;';
    layer.appendChild(d);
    return (this._bubbles[key] = { el: d, until: 0, pos: null, headY: 2.55, rot: 0 });
  }
  // text floats above pos for dur ms. gold = the louder boss-event treatment
  // (existing colour cue, reused rather than inventing a second one).
  sayBubble(key, pos, text, opts) {
    const b = this.bubbleSlot(key); if (!b) return;
    opts = opts || {};
    b.pos = pos; b.headY = opts.headY || 2.55;
    b.until = performance.now() + (opts.dur || 4200);
    b.rot = Math.random() * 6 - 3;
    b.el.textContent = text;
    b.el.style.background = opts.gold ? '#e8c774' : '#f2efe6';
  }
  // Any entity (world NPC or otherwise) gets a stable bubble key of its own
  // the first time it talks - O(1), and it never depends on array position.
  npcSay(n2, text, opts) {
    if (!n2) return;
    if (!n2._bk) n2._bk = 'e' + (this._bkSeq = (this._bkSeq || 0) + 1);
    this.sayBubble(n2._bk, n2.pos, text, opts);
  }
  hideBubbles() {
    if (!this._bubbles) return;
    for (const k in this._bubbles) { this._bubbles[k].until = 0; this._bubbles[k].el.style.display = 'none'; }
  }
  stepBubbles(dt) {
    if (!this._bubbles || !this.me) return;
    const gy0 = (this.worldOn && this.mode === 'ai');
    for (const key in this._bubbles) {
      const b = this._bubbles[key];
      if (performance.now() >= b.until || !b.pos) { if (b.el.style.display !== 'none') b.el.style.display = 'none'; continue; }
      const dist = this.me.pos.distanceTo(new this.T.Vector3(b.pos.x, 0, b.pos.z));
      if (dist >= this.BUBBLE_MAX_R) { b.el.style.display = 'none'; continue; }
      const gy = gy0 ? this.groundY(b.pos.x, b.pos.z) : 0;
      const v = this._sv1.set(b.pos.x, gy + b.headY, b.pos.z).project(this.cam);
      if (v.z > 1 || v.x < -1.35 || v.x > 1.35) { b.el.style.display = 'none'; continue; }
      const t = Math.max(0, (dist - this.BUBBLE_NEAR_R) / (this.BUBBLE_MAX_R - this.BUBBLE_NEAR_R));
      const scale = Math.max(this.BUBBLE_MIN_SCALE, 1 - t * (1 - this.BUBBLE_MIN_SCALE));
      b.el.style.display = 'block';
      b.el.style.left = ((v.x * 0.5 + 0.5) * 100) + '%';
      b.el.style.top = ((-v.y * 0.5 + 0.5) * 100) + '%';
      b.el.style.opacity = String(Math.max(0.3, 1 - t * 0.45));
      b.el.style.transform = 'translate(-50%,-100%) rotate(' + b.rot.toFixed(1) + 'deg) scale(' + scale.toFixed(2) + ')';
    }
  }
  // Random idle catchphrases for every world NPC flagged .shouts, each on its
  // own independent timer - was gated on f.shouts where f = this.foe, so a
  // wandering boss only ever talked while YOU happened to have it targeted.
  stepNpcChatter(dt) {
    if (this.mode !== 'ai' || !this.npcs) return;
    const LINES = ['GET OFF YOUR SEAT!', 'DID YOU CLOSE OUT YOUR PM?', 'ANY LINE LIMITERS?'];
    for (const n2 of this.npcs) {
      if (!n2.shouts || n2.hp <= 0) continue;
      n2._chatT = (n2._chatT ?? (2 + Math.random() * 3)) - dt;
      if (n2._chatT <= 0) {
        n2._chatT = 3.5 + Math.random() * 4.5;
        this.npcSay(n2, LINES[Math.floor(Math.random() * LINES.length)]);
        if (this.me && this.me.pos.distanceTo(n2.pos) < this.BUBBLE_MAX_R) this.sfx('tick');
      }
    }
  }

"""

sub(OLD_BLOCK, NEW_BLOCK, tag='shout system rewrite')

# ---- tick() call site: replace the single stepShouts call ----------------
sub("    this.stepShouts(dt);\n",
    "    this.stepBubbles(dt);\n    this.stepNpcChatter(dt);\n",
    tag='tick call site')

# ---- pause overlay: hide every live bubble, not one shared element -------
sub("      if (this.shoutEl) this.shoutEl.style.display = 'none';",
    "      this.hideBubbles();",
    tag='showOverlay hide')

# ---- Sailers' scripted taunt move (driveAI) -------------------------------
sub('this.showShout("WHERE\'S THE RIVET?!", true, 2800);',
    "this.npcSay(e, \"WHERE'S THE RIVET?!\", { gold: true, dur: 2800 });",
    tag='sailers taunt')

# ---- Warden phase-change bark (onBossEvent, two call sites) --------------
sub("if (m.shout) this.showShout(m.shout, true, 2600);",
    "if (m.shout) this.npcSay(n, m.shout, { gold: true, dur: 2600 });",
    tag='boss event shout 2600')
sub("if (m.shout) this.showShout(m.shout, true, 2400);",
    "if (m.shout) this.npcSay(n, m.shout, { gold: true, dur: 2400 });",
    tag='boss event shout 2400')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('61_speech_bubbles: %d edits applied' % n)
