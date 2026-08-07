#!/usr/bin/env python3
"""Patch 73.480: quadruped gait crossfade + rotary/transverse gait style
(locomotion overhaul phase 3, last in the plan's build order).

Kevin's original ask covered wolves and deer explicitly: "the same quality
treatment for quadrupeds." poseQuadRig (shared by every four-legged rig -
wolf, deer, the boar/rat/hare variant builder, and the giant rat boss) had
the same shape of bug the biped gait had: a single hard boolean,
`run = mv > 0.7`, switching BOTH the leg phase offsets AND every bounce/
lean/neck/tail formula between two fixed states with no blend, so the
walk-to-run transition popped, and every quadruped in the game shared the
exact same gallop pattern - a wolf and a deer moved identically at speed,
just with different proportions.

THE FIX, confirmed against the live function in /tmp/game-src.html before
writing anything:

  1. Crossfade. `run` (boolean) becomes `runK` (0-1, smoothstepped over mv
     0.5-0.9): every formula that used to branch on `run` now lerps by
     runK instead, including the leg phase offsets themselves - WALK_OFF
     and RUN_OFF are blended as an additive phase offset before the shared
     sin(), which is enough to make the transition continuous with zero new
     animation states, consistent with how every other rig in this file is
     procedural sine math rather than blended clips.

  2. Suspension phase. A real gallop has a moment where all four feet
     leave the ground - this rig never had one, at any speed. suspK fades
     in only once mv is past 1.0 (the game's normal move speed - so this is
     gallop-only, not "any run"), and susp is a short, sharp per-cycle pulse
     that lifts the body, reduces leg swing amplitude, and adds a knee-tuck,
     timed once per stride rather than continuously.

  3. gaitStyle. q.gaitStyle picks which pattern RUN_OFF resolves to:
     ROTARY (default, unchanged from the old fixed formula - predators;
     rear legs land together, a hair off the fronts) vs TRANSVERSE (a
     distinct offset set - grazers; a more diagonal footfall, closer to how
     a deer or horse actually gallops). Set explicitly on the wolf ('
     rotatory') and deer ('transverse') qr objects below, the two animals
     Kevin named. Everything else (boar/rat/hare, the giant rat boss)
     leaves q.gaitStyle unset and gets the exact same ROTARY formula as
     before this patch - deliberately untouched, since Kevin only asked
     about wolves and deer.

Every OTHER use of `run` in the original function (7 in total, grepped and
counted before writing this patch) is accounted for above: leg offsets,
bounce amplitude AND frequency, body pitch, neck angle, ear pin, tail
angle. None left branching on a variable this patch removes.
"""
import io

SRC = '/tmp/game-src.html'

s = io.open(SRC, encoding='utf-8').read()


def one(anchor, label):
    n = s.count(anchor)
    assert n == 1, '%s matched %d times' % (label, n)


def sub(anchor, new, label):
    global s
    one(anchor, label)
    s = s.replace(anchor, new)


# ---------------------------------------------------------------------------
# 1. poseQuadRig: full function replacement.
# ---------------------------------------------------------------------------
OLD_POSE = """  poseQuadRig(e, dt) {
    const q = e.qr;
    const t = (e._qt = (e._qt || 0) + dt);
    const mv = Math.min(1.5, e.moveAmt || 0);
    if (e.state === 'dead' || e.hp <= 0) {
      q.body.rotation.z += (1.35 - q.body.rotation.z) * Math.min(1, dt * 5);
      q.body.position.y += (q.baseY * 0.42 - q.body.position.y) * Math.min(1, dt * 5);
      return;
    }
    let snap = 0;
    if (e.state === 'attack' && e.act) {
      // rise to full extension EXACTLY at the wind moment (when the damage
      // lands), then recover - the bite you see is the bite that hits
      const wind = Math.max(0.15, (e.act.wind || 0.3));
      snap = e.st < wind ? Math.pow(Math.min(1, e.st / wind), 1.6) : Math.max(0, 1 - (e.st - wind) / 0.35);
    }
    const run = mv > 0.7;
    e._qph = (e._qph || 0) + dt * (1.6 + mv * 6.0);
    const ph = e._qph, amp = mv < 0.03 ? 0 : (0.3 + Math.min(1, mv) * 0.5);
    const off = run ? [0, 0.35, Math.PI, Math.PI + 0.35] : [0, Math.PI, Math.PI, 0];
    q.legs.forEach((l, i) => {
      const p = ph + off[i];
      l.hip.rotation.x = Math.sin(p) * amp * (l.front ? 1 : 0.9) + (l.front ? -0.85 : 0.6) * snap;
      l.knee.rotation.x = Math.max(0, Math.cos(p)) * amp * 0.85 + 0.07 + (l.front ? 0.45 * snap : 0);
      l.hip.rotation.z = 0;
    });
    q.body.rotation.z = 0;
    q.body.position.y = q.baseY + (mv > 0.03 ? Math.abs(Math.sin(ph * (run ? 1 : 2))) * (run ? 0.07 : 0.02) : Math.sin(t * 1.6) * 0.008) + 0.16 * snap;
    q.body.rotation.x = (mv > 0.03 ? (run ? Math.sin(ph) * 0.09 : 0) : Math.sin(t * 1.6) * 0.006) - 0.28 * snap;
    const nIdle = q.nIdle !== undefined ? q.nIdle : -0.62, nMove = q.nMove !== undefined ? q.nMove : -0.5, nRun = q.nRun !== undefined ? q.nRun : -0.25;
    q.neckG.rotation.x = (mv > 0.03 ? (run ? nRun : nMove) : nIdle + Math.sin(t * 0.9) * 0.03) + 0.5 * snap;
    q.head.rotation.x = (q.headBase !== undefined ? q.headBase : 0.5) - 0.25 * snap;
    q.head.rotation.y = (mv > 0.03 || snap) ? 0 : Math.sin(t * 0.5) * 0.25;
    q.jaw.rotation.x = 0.62 * snap;
    q.ears.forEach((er, i) => { er.rotation.x = (run || snap) ? -0.5 : (Math.sin(t * 3.1 + i * 2.6) > 0.965 ? -0.35 : 0); });
    q.tailSegs.forEach((s2, i) => {
      s2.rotation.x = i === 0 ? (snap ? -0.1 : (mv > 0.03 ? (run ? 0.15 : -0.35) : -0.55)) : (mv > 0.03 || snap ? 0.18 : 0.22);
      s2.rotation.y = Math.sin(t * (mv > 0.03 ? 3 : 1.7) + i * 0.7) * (mv > 0.03 ? 0.1 : 0.14);
    });
  }"""

NEW_POSE = """  poseQuadRig(e, dt) {
    const q = e.qr;
    const t = (e._qt = (e._qt || 0) + dt);
    const mv = Math.min(1.5, e.moveAmt || 0);
    if (e.state === 'dead' || e.hp <= 0) {
      q.body.rotation.z += (1.35 - q.body.rotation.z) * Math.min(1, dt * 5);
      q.body.position.y += (q.baseY * 0.42 - q.body.position.y) * Math.min(1, dt * 5);
      return;
    }
    let snap = 0;
    if (e.state === 'attack' && e.act) {
      // rise to full extension EXACTLY at the wind moment (when the damage
      // lands), then recover - the bite you see is the bite that hits
      const wind = Math.max(0.15, (e.act.wind || 0.3));
      snap = e.st < wind ? Math.pow(Math.min(1, e.st / wind), 1.6) : Math.max(0, 1 - (e.st - wind) / 0.35);
    }
    // Gait crossfade (patch 73.480): walk<->gallop used to be a hard
    // boolean (mv > 0.7) that popped every formula in this function at the
    // threshold. runK eases across a band instead (smoothstep 0.5 -> 0.9).
    // gaitStyle picks which gallop pattern the run end of that blend uses:
    // ROTARY (predators, e.g. the wolf below - rear legs land together, a
    // hair off the fronts) or TRANSVERSE (grazers, e.g. the deer below - a
    // more diagonal footfall), instead of every quadruped sharing one
    // formula. Unset (boar/rat/hare, the giant rat boss) defaults to the
    // exact ROTARY numbers this function always used - deliberately
    // unchanged, since Kevin only asked about wolves and deer.
    const rt = Math.max(0, Math.min(1, (mv - 0.5) / 0.4));
    const runK = rt * rt * (3 - 2 * rt);
    const rotary = q.gaitStyle !== 'transverse';
    const RUN_OFF = rotary ? [0, 0.35, Math.PI, Math.PI + 0.35] : [0, 0.45, Math.PI + 0.25, Math.PI + 0.7];
    const WALK_OFF = [0, Math.PI, Math.PI, 0];
    e._qph = (e._qph || 0) + dt * (1.6 + mv * 6.0);
    const ph = e._qph, amp = mv < 0.03 ? 0 : (0.3 + Math.min(1, mv) * 0.5);
    // Suspension phase: all four feet airborne at once, real to a gallop and
    // absent here before this patch. Only kicks in past mv 1.0 (the game's
    // one non-sprint move speed - true gallop territory, not "any run"),
    // scaling in through the sprint band; a short, sharp once-per-stride
    // pulse rather than a continuous effect.
    const suspK = Math.max(0, Math.min(1, (mv - 1.0) / 0.5));
    const susp = suspK > 0 ? Math.pow(Math.max(0, Math.sin(ph - 0.55)), 6) * suspK : 0;
    q.legs.forEach((l, i) => {
      const p = ph + (WALK_OFF[i] + (RUN_OFF[i] - WALK_OFF[i]) * runK);
      const legAmp = amp * (1 - susp * 0.5);
      l.hip.rotation.x = Math.sin(p) * legAmp * (l.front ? 1 : 0.9) + (l.front ? -0.85 : 0.6) * snap;
      l.knee.rotation.x = Math.max(0, Math.cos(p)) * legAmp * 0.85 + 0.07 + susp * 0.35 + (l.front ? 0.45 * snap : 0);
      l.hip.rotation.z = 0;
    });
    q.body.rotation.z = 0;
    const bounceAmp = 0.02 + (0.07 - 0.02) * runK;
    const bounceFreq = 2 - 1 * runK;
    q.body.position.y = q.baseY + (mv > 0.03 ? Math.abs(Math.sin(ph * bounceFreq)) * bounceAmp : Math.sin(t * 1.6) * 0.008) + 0.16 * snap + susp * 0.09;
    q.body.rotation.x = (mv > 0.03 ? Math.sin(ph) * 0.09 * runK : Math.sin(t * 1.6) * 0.006) - 0.28 * snap;
    const nIdle = q.nIdle !== undefined ? q.nIdle : -0.62, nMove = q.nMove !== undefined ? q.nMove : -0.5, nRun = q.nRun !== undefined ? q.nRun : -0.25;
    const nMoveBlend = nMove + (nRun - nMove) * runK;
    q.neckG.rotation.x = (mv > 0.03 ? nMoveBlend : nIdle + Math.sin(t * 0.9) * 0.03) + 0.5 * snap;
    q.head.rotation.x = (q.headBase !== undefined ? q.headBase : 0.5) - 0.25 * snap;
    q.head.rotation.y = (mv > 0.03 || snap) ? 0 : Math.sin(t * 0.5) * 0.25;
    q.jaw.rotation.x = 0.62 * snap;
    q.ears.forEach((er, i) => { er.rotation.x = (runK > 0.5 || snap) ? -0.5 : (Math.sin(t * 3.1 + i * 2.6) > 0.965 ? -0.35 : 0); });
    q.tailSegs.forEach((s2, i) => {
      const tailRun = -0.35 + (0.15 - (-0.35)) * runK;
      s2.rotation.x = i === 0 ? (snap ? -0.1 : (mv > 0.03 ? tailRun : -0.55)) : (mv > 0.03 || snap ? 0.18 : 0.22);
      s2.rotation.y = Math.sin(t * (mv > 0.03 ? 3 : 1.7) + i * 0.7) * (mv > 0.03 ? 0.1 : 0.14);
    });
  }"""

sub(OLD_POSE, NEW_POSE, 'poseQuadRig gait crossfade + suspension phase (73.480)')

# ---------------------------------------------------------------------------
# 2. Wolf: explicit ROTARY gait style (matches the unchanged default, stated
#    explicitly so it reads as a decision, not an accident of the fallback).
# ---------------------------------------------------------------------------
sub(
    """      qr: { legs, neckG, head, jaw, ears, tailSegs, body, baseY: 0.68 },""",
    """      qr: { legs, neckG, head, jaw, ears, tailSegs, body, baseY: 0.68, gaitStyle: 'rotatory' },""",
    'wolf gaitStyle rotatory (73.480)'
)

# ---------------------------------------------------------------------------
# 3. Deer: TRANSVERSE gait style - the one new pattern this patch adds.
# ---------------------------------------------------------------------------
sub(
    """      qr: { legs, neckG, head, jaw: empty(), ears, tailSegs: [], body, baseY: 0.85, nIdle: -1.02, nMove: -0.9, nRun: -0.55, headBase: 0.92 },""",
    """      qr: { legs, neckG, head, jaw: empty(), ears, tailSegs: [], body, baseY: 0.85, nIdle: -1.02, nMove: -0.9, nRun: -0.55, headBase: 0.92, gaitStyle: 'transverse' },""",
    'deer gaitStyle transverse (73.480)'
)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 73.480 applied: quadruped gait crossfade + rotary/transverse gait style')
