"""
Kevin, Aug 12: "can you make it so when i click on a rock or tree, the
character start 'auto mining' it. that way i just click it once and my
character walks up to the rock and start mining it until its done. same
for cutting trees. and foraging."

Today, gathering is entirely manual: walk into the 3m cone in front of a
node yourself, face it, and left-click once per swing, forever, for every
single hit. This patch adds click-to-target: click a rock/tree/plant while
a pick, axe or sickle is equipped, and the character walks itself into
range, faces it, and keeps swinging until it depletes, gate-fails (wrong
tool/level/tier/full pack) or you take back control.

Design notes for whoever touches this next:

- Detection reuses gatherCheck's own forward-cone style (facing dot > 0.3)
  but at a much longer range (18m instead of gatherCheck's hardcoded 3m),
  so "click a rock across the clearing" actually finds it. findGatherTarget_
  is a new, separate helper -- gatherCheck itself is untouched, so every
  existing manual-gathering and tool-as-weapon code path behaves exactly
  as before.

- There is already a near-identical pattern in this file: workStep(e, dt),
  the cosmetic villager-worker AI (walk to a real node, face it, startMove
  'chop' on a timer). That one never touches gatherCheck because it only
  ever runs for NPC entities, and gatherCheck's hit branch is hard-gated to
  `e === this.me` (see line ~36202). This patch is the same walk+face+swing
  shape, but for the real player, which is exactly why it drops straight
  into the existing reward pipeline (loot/xp/depletion banners) with no
  new reward code of its own -- startMove(e,'chop') on the real player was
  already fully wired, it just needed to fire on its own.

- Movement: e.want/e.yaw are cheap to override for one entity. driveLocal
  computes them from keys every tick but does not integrate position
  itself (that happens later in tick()), so calling updateAutoGather(dt)
  right after driveLocal(me, dt) and overwriting e.want/e.yaw/this.yaw for
  that frame is enough -- no changes to driveLocal, wishDir or the shared
  integrator. This also means holding W/A/S/D is naturally a great cancel
  signal: check it before doing anything else.

- Camera: this.yaw is steered toward the node the same way the existing
  lockOn combat camera steers toward a foe in updateAim (same atan2 + wrap
  + lerp shape, dt*9). Mouse-look still runs every frame underneath (this
  patch does not touch updateAim), but this code runs after driveLocal and
  overwrites this.yaw last, so the camera reads as locked onto the node
  while auto-gathering, same feel as combat lock-on.

- No pathfinding exists anywhere in this codebase (every NPC "walk toward
  a point" is straight-line e.want math, same as workStep/wander above).
  This matches that bar deliberately: straight-line walk, plus a 14s
  timeout as a cheap safety net in case a node is ever placed somewhere
  a straight line can't reach, rather than inventing navmesh/pathfinding
  for a game that has never had it.

- Progress/gate-failure detection: gatherCheck's contract wasn't changed
  (one call site, do not want to risk that). Instead the driver snapshots
  the target's hp before each swing and compares it next time the player
  is act-able again. Unchanged hp means that swing was a gate failure
  (wrong tool/level/tier) or a full pack -- gatherCheck already banners
  the specific reason, so the loop just stops instead of silently
  retrying (and spamming) the same failing swing forever.

- Cancel conditions, checked once a tick in updateAutoGather: any UI
  window open (uiWindowOpen(), same helper tick() already uses), death,
  round over, any WASD held, weapon swapped away from pick/axe/sickle
  (wieldAs 3/4 -- a worn sickle reports e.weapon===4, same bucket as an
  axe, so this also naturally covers foraging), taking damage (hp drop
  since last tick), the target node dying (depleted/despawned), and the
  14s stuck timeout. All of these are silent cancels except the ones that
  already have their own banner from gatherCheck -- no new banner spam.

- onPrimaryDown's existing weapon===3/4 branch is a strict superset now:
  if findGatherTarget_ finds nothing (nothing gatherable in the cone),
  it falls through to the exact old line, `this.canAct(e) &&
  this.startMove(e,'chop')`, preserving "swing the tool as a weak melee
  weapon" for combat with a tool equipped. If it finds something already
  in gather range, autoGather starts in the 'gather' phase directly (one
  frame of latency versus the old instant swing, imperceptible at 60fps).
"""

PATH = '/tmp/game-src.html'
with open(PATH, 'r', encoding='utf-8') as f:
    text = f.read()


def sub(old, new, tag, count=1):
    global text
    n = text.count(old)
    assert n == count, f'{tag}: found {n}, wanted {count}'
    text = text.replace(old, new, count)


# ---- 1. onPrimaryDown: target-acquire before falling back to the old
# instant chop-in-place.
sub(
    """  onPrimaryDown() {
    const e = this.me;
    if (e.weapon === 3 || e.weapon === 4) { if (this.canAct(e)) this.startMove(e, 'chop'); return; }""",
    """  onPrimaryDown() {
    const e = this.me;
    if (e.weapon === 3 || e.weapon === 4) {
      const R = this.findGatherTarget_(e, 18);
      if (R) { e.autoGather = { res: R, phase: (e.pos.distanceTo(R.g.position) <= 2.6 ? 'gather' : 'walk'), t: 0, hp: e.hp }; return; }
      e.autoGather = null;
      if (this.canAct(e)) this.startMove(e, 'chop');
      return;
    }""",
    'onPrimaryDown: target-acquire on the tool branch',
)

# ---- 2. new helpers: target detection, cancel, and the per-frame walk +
# swing driver. Dropped in right after onSecondaryUp, same neighbourhood
# as the click handlers they extend.
sub(
    """  onSecondaryUp() { const e = this.me; e.blocking = false; }

  // -------- quests""",
    """  onSecondaryUp() { const e = this.me; e.blocking = false; }

  // Longer-range cousin of gatherCheck's own forward-cone scan (that one is
  // hardcoded to 3m, right for "am I in range to hit it", wrong for "what
  // did I just click on"). Same facing-cone shape, configurable range.
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
  }
  cancelAutoGather() { const e = this.me; if (e) e.autoGather = null; }
  // Click-to-auto-gather driver: one call a frame from tick(), right after
  // driveLocal so it has the last word on e.want/e.yaw/this.yaw for local
  // player movement this frame. No-op unless e.autoGather is set.
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
    // phase === 'gather'
    e.want.set(0, 0, 0);
    if (d > 3.4) { ag.phase = 'walk'; ag.t = 0; return; }   // pushed or wandered out of range
    if (!this.canAct(e)) return;
    if (ag.hpBefore !== undefined && ag.hpBefore === R.hp) { this.cancelAutoGather(); return; }  // last swing made no progress: gate failure, already bannered
    ag.hpBefore = R.hp;
    this.startMove(e, 'chop');
  }

  // -------- quests""",
    'add findGatherTarget_/cancelAutoGather/updateAutoGather',
)

# ---- 3. tick() hookup: run the driver once a frame, right after driveLocal
# owns e.want/e.yaw for the local player, before the AI/foe/combat pass.
sub(
    """    this.driveLocal(me, dt);
    if (this.worldOn && this.mode === 'ai') {""",
    """    this.driveLocal(me, dt);
    this.updateAutoGather(dt);
    if (this.worldOn && this.mode === 'ai') {""",
    'tick: hook updateAutoGather after driveLocal',
)

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(text)

print('applied 75.273 (3 edits)')
