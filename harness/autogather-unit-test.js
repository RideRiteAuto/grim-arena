// Standalone logic test for patch 75.273's new methods (findGatherTarget_,
// cancelAutoGather, updateAutoGather). NOT a full in-game boot test -- see
// the run notes for why: this sandbox's real-login network round trip is
// documented-broken (claude/PROJECT-MEMORY.md), and the network-free
// __grim.play() bypass no longer works either post-account-mandatory
// (v17.1): this.skills/this.me now only get built through paths that this
// sandbox's headless Chromium can't complete either. That is a pre-existing
// sandbox limitation, not something this patch introduced.
//
// What this DOES prove: the exact method bodies shipped in the patch,
// pasted verbatim (not re-derived), behave correctly against a minimal
// mock of `this` -- target acquisition (cone + range + dead filtering),
// the walk -> gather phase transition at the right distance, the swing
// loop actually firing once per idle tick, the hp-diff gate-failure
// detection stopping the loop instead of spinning forever, and every
// documented cancel condition (WASD, UI open, damage taken, weapon swap,
// target death, timeout).

class Vector3 {
  constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
  set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; }
  clone() { return new Vector3(this.x, this.y, this.z); }
  subVectors(a, b) { this.x = a.x - b.x; this.y = a.y - b.y; this.z = a.z - b.z; return this; }
  length() { return Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z); }
  normalize() { const l = this.length() || 1; this.x /= l; this.y /= l; this.z /= l; return this; }
  dot(o) { return this.x * o.x + this.y * o.y + this.z * o.z; }
  distanceTo(o) { return Math.hypot(this.x - o.x, this.y - o.z !== undefined ? this.z - o.z : 0, ); }
}
// distanceTo needs 2-arg hypot over x/z only, fix properly:
Vector3.prototype.distanceTo = function (o) { return Math.hypot(this.x - o.x, this.z - o.z); };

// ---- the exact method bodies from harness/patches/75.273_click_to_autogather.py ----
const methods = {
  findGatherTarget_(e, range) {
    const T = this.T;
    const f = new T.Vector3(Math.sin(e.yaw), 0, Math.cos(e.yaw));
    let best = null, bd = range;
    for (const R of this.allResources()) {
      if (R.dead) continue;
      const to = new T.Vector3().subVectors(R.g.position, e.pos); to.y = 0;
      const d = to.length();
      if (d > range) continue;
      if (f.dot(to.clone().normalize()) <= 0.3) continue;
      if (d < bd) { best = R; bd = d; }
    }
    return best;
  },
  cancelAutoGather() { const e = this.me; if (e) e.autoGather = null; },
  updateAutoGather(dt) {
    const e = this.me;
    const ag = e && e.autoGather;
    if (!ag) return;
    if (this.uiWindowOpen() || e.hp <= 0 || this.roundOver ||
        this.keys['w'] || this.keys['a'] || this.keys['s'] || this.keys['d'] ||
        (e.weapon !== 3 && e.weapon !== 4) || e.hp < ag.hp) { this.cancelAutoGather(); return; }
    ag.hp = e.hp;
    const R = ag.res;
    if (!R || R.dead) { this.cancelAutoGather(); return; }
    const T = this.T;
    const to = new T.Vector3().subVectors(R.g.position, e.pos); to.y = 0;
    const d = to.length();
    let dy = Math.atan2(to.x, to.z) - this.yaw;
    while (dy > Math.PI) dy -= Math.PI * 2;
    while (dy < -Math.PI) dy += Math.PI * 2;
    this.yaw += dy * Math.min(1, dt * 9);
    e.yaw = this.yaw;
    if (ag.phase === 'walk') {
      ag.t += dt;
      if (ag.t > 14) { this.cancelAutoGather(); return; }
      if (d > 2.6) {
        const sp = this.C.SPEED;
        e.want.set(Math.sin(e.yaw) * sp, 0, Math.cos(e.yaw) * sp);
        e.moveAmt += (Math.min(sp / this.C.SPEED, 1.5) - e.moveAmt) * Math.min(1, dt * 12);
        return;
      }
      e.want.set(0, 0, 0);
      ag.phase = 'gather'; ag.t = 0; ag.hpBefore = undefined;
      return;
    }
    e.want.set(0, 0, 0);
    if (d > 3.4) { ag.phase = 'walk'; ag.t = 0; return; }
    if (!this.canAct(e)) return;
    if (ag.hpBefore !== undefined && ag.hpBefore === R.hp) { this.cancelAutoGather(); return; }
    ag.hpBefore = R.hp;
    this.startMove(e, 'chop');
  }
};

function mkResource(kind, x, z, hp = 4) { return { kind, g: { position: new Vector3(x, 0, z) }, hp, dead: false }; }

function mkGame(overrides = {}) {
  const startMoveLog = [];
  const g = Object.assign({
    T: { Vector3 },
    keys: {},
    yaw: 0,
    C: { SPEED: 4 },
    resources: [],
    zoneNodes: [],
    uiWindowOpen: () => false,
    roundOver: false,
    canAct: (e) => e.state === 'idle',
    startMove: (e, name) => { startMoveLog.push(name); e.state = 'attack'; },
    allResources: function* () { for (const r of this.resources) yield r; for (const r of this.zoneNodes) yield r; },
    me: { pos: new Vector3(0, 0, 0), yaw: 0, hp: 100, weapon: 3, want: new Vector3(), moveAmt: 0, state: 'idle', autoGather: null }
  }, methods, overrides);
  g._startMoveLog = startMoveLog;
  return g;
}

let pass = 0, fail = 0;
function check(label, cond) {
  if (cond) { pass++; }
  else { fail++; console.log('FAIL:', label); }
}

// ---- 1. findGatherTarget_: picks nearest in-cone, in-range, live node ----
{
  const g = mkGame();
  g.resources.push(mkResource('rock', 0, 20));      // dead ahead, far (20 > range 18)
  g.resources.push(mkResource('rock', 0, 10));       // dead ahead, in range -- should win (nearer than the 12 below)
  g.resources.push(mkResource('rock', 0, 12));       // dead ahead, in range but farther
  g.resources.push(mkResource('rock', -15, 0));      // in range but behind/beside (outside cone)
  const deadOne = mkResource('rock', 0, 5); deadOne.dead = true;
  g.resources.push(deadOne);                          // in cone+range but dead -- must be skipped
  const R = g.findGatherTarget_(g.me, 18);
  check('finds nearest live in-cone in-range node', R && R.g.position.z === 10);
}
{
  const g = mkGame();
  const R = g.findGatherTarget_(g.me, 18);
  check('returns null when nothing is in range', R === null);
}

// ---- 2. onPrimaryDown-equivalent setup + walk -> gather transition ----
{
  const g = mkGame();
  const R = mkResource('rock', 0, 10);
  g.resources.push(R);
  g.me.autoGather = { res: R, phase: 'walk', t: 0, hp: g.me.hp };
  let ticks = 0;
  while (g.me.autoGather && g.me.autoGather.phase === 'walk' && ticks < 2000) {
    g.updateAutoGather(1 / 60);
    g.me.pos.x += g.me.want.x / 60; g.me.pos.z += g.me.want.z / 60;  // stand-in for the real integrator
    ticks++;
  }
  check('walk phase moves the player toward the node', g.me.pos.distanceTo(R.g.position) < 3);
  check('phase transitions to gather once close enough', g.me.autoGather && g.me.autoGather.phase === 'gather');
  check('reasonable tick count to close ~10m at SPEED 4 (not stuck, not instant)', ticks > 30 && ticks < 300);
}

// ---- 3. gather phase: swings fire once per idle tick, hp progress keeps it going ----
{
  const g = mkGame();
  const R = mkResource('rock', 0, 2, 4);
  g.resources.push(R);
  g.me.pos.set(0, 0, 0);
  g.me.autoGather = { res: R, phase: 'gather', t: 0, hp: g.me.hp, hpBefore: undefined };
  // simulate 4 depleting swings: each canAct-tick fires startMove, then the
  // "swing landed" tick (state back to idle) is where hp actually drops,
  // mirroring how gatherCheck only mutates hp on the hit frame.
  for (let swing = 0; swing < 4; swing++) {
    g.me.state = 'idle';
    g.updateAutoGather(1 / 60);              // fires startMove -> state='attack'
    R.hp -= 1;                                // stand-in for gatherCheck's real hp decrement
    g.me.state = 'idle';                      // swing resolved, back to idle
  }
  check('4 swings against hp=4 depleted the node', R.hp === 0);
  check('startMove(chop) fired once per swing (4 times)', g._startMoveLog.filter(n => n === 'chop').length === 4);
  R.dead = true;                              // resourceDepleted() would have set this
  g.updateAutoGather(1 / 60);
  check('autoGather clears once the target is dead', g.me.autoGather === null);
}

// ---- 4. gate failure: hp unchanged across a full swing cycle stops the loop, no spam ----
{
  const g = mkGame();
  const R = mkResource('rock', 0, 2, 4);
  g.resources.push(R);
  g.me.pos.set(0, 0, 0);
  g.me.autoGather = { res: R, phase: 'gather', t: 0, hp: g.me.hp, hpBefore: undefined };
  g.me.state = 'idle';
  g.updateAutoGather(1 / 60);   // 1st swing fires, hpBefore snapshot taken
  g.me.state = 'idle';          // swing "resolved" but gatherCheck gate-failed (wrong tier etc): hp untouched
  g.updateAutoGather(1 / 60);   // must detect no progress and cancel, NOT fire a 2nd swing
  check('gate failure (no hp change) cancels instead of retrying forever', g.me.autoGather === null);
  check('exactly one swing was attempted, not spammed', g._startMoveLog.filter(n => n === 'chop').length === 1);
}

// ---- 5. cancel conditions ----
function cancelTest(label, setupFn) {
  const g = mkGame();
  const R = mkResource('rock', 0, 5);
  g.resources.push(R);
  g.me.autoGather = { res: R, phase: 'walk', t: 0, hp: g.me.hp };
  setupFn(g);
  g.updateAutoGather(1 / 60);
  check(label, g.me.autoGather === null);
}
cancelTest('W held cancels', g => { g.keys.w = true; });
cancelTest('A held cancels', g => { g.keys.a = true; });
cancelTest('UI window open cancels', g => { g.uiWindowOpen = () => true; });
cancelTest('death (hp<=0) cancels', g => { g.me.hp = 0; });
cancelTest('round over cancels', g => { g.roundOver = true; });
cancelTest('weapon swapped away from pick/axe cancels', g => { g.me.weapon = 0; });
cancelTest('taking damage (hp drop since last tick) cancels', g => { g.me.hp = 90; g.me.autoGather.hp = 100; });
cancelTest('target already dead cancels', g => { g.resources[0].dead = true; });
{
  const g = mkGame();
  const R = mkResource('rock', 0, 100);   // far enough that walk phase never closes the distance
  g.resources.push(R);
  g.me.autoGather = { res: R, phase: 'walk', t: 13.99, hp: g.me.hp };
  g.updateAutoGather(0.02);   // pushes ag.t just past 14
  check('14s stuck timeout cancels', g.me.autoGather === null);
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
