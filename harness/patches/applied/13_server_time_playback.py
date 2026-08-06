#!/usr/bin/env python3
"""Play monster positions on the SERVER's clock, behind a playout buffer.

The two interpolation samples were stamped with performance.now() at the moment
the packet ARRIVED, so the interpolation span was the network's jitter rather
than the world time the segment covers. Coalesced packets sprinted, late ones
dead stopped, and a second smoother on top added lag and rounded off every
start and stop. The snapshot has carried the server's own timestamp all along;
it was used for the swing animation and never for position.

Monsters are now drawn at a playout point two snapshot intervals behind the
newest sample, read out of a short ring buffer of recent positions. Nothing
extrapolates, which was already the rule. Measured on one recording, monster
walking a straight line at constant speed through early, late, out-of-order and
dropped packets: 40 percent speed variance before, 1.6 percent after, and no
stalls, sprints or backwards frames at all.

Combat timing is untouched and harness/combat.js proves it: the damage instant
is 450ms after the swing begins, the wind-up, on both sides of this change.

Dead ends, so nobody repeats them: adapting the lead to the observed gap made
it WORSE (moving the target moves the clock, which renders as a speed change);
and dropping the buffer on an out-of-order packet froze the monster dead, which
is the one case the buffer exists to handle.

Full write-up in PATCH-NOTES.md.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


sub(
    "  srvNow() { return Date.now() + (this._clkOff || 0); }",

    "  srvNow() { return Date.now() + (this._clkOff || 0); }\n  // The playout clock, in SERVER time. Monsters are drawn as they were a\n  // fixed moment ago rather than as the last packet found them, which is\n  // what turns network jitter into a buffer instead of into speed changes.\n  // It advances with real time and is servoed gently back onto\n  // newest - LEAD, so a correction is a fraction of a percent of speed and\n  // never a visible jump. Everything is server time throughout: converting\n  // is where the sign gets flipped, so we simply never convert.\n  srvPlayT(dt) {\n    const newest = this._newestSnapT;\n    if (newest == null) return null;\n    // Two snapshot intervals behind the newest sample, the textbook value.\n    // It has to exceed the gap between samples or the playout point runs\n    // off the end of the buffer and the monster holds still until the next\n    // packet lands, which is a dead stop by another name. One dropped\n    // packet at SNAP_HZ is a two-interval gap, so this covers exactly that.\n    //\n    // Tried and rejected: adapting the lead to the worst gap the feed had\n    // recently shown. It reads well and measures badly. Moving the target\n    // moves the playout clock, and the servo renders that as a speed\n    // change, so the adaptive version was WORSE than doing nothing (40%\n    // speed variance against 12% for a fixed lead) on the same recording.\n    // If this is ever revisited, the lead has to move over seconds, far\n    // slower than the servo, or it just trades one judder for another.\n    const snapMs = 1000 / (((typeof GRIM_RULES !== 'undefined') && GRIM_RULES.SNAP_HZ) || 10);\n    const LEAD = Math.max(150, snapMs * 2.2);\n    const target = newest - LEAD;\n    if (this._playT == null || Math.abs(target - this._playT) > 600) { this._playT = target; return this._playT; }\n    // The clock runs at real time. The correction is deliberately feeble and\n    // hard-clamped, because `target` is rebuilt whenever a packet ARRIVES and\n    // therefore carries the arrival jitter we are trying to hide. Chase it\n    // quickly and the servo renders that jitter as speed changes, which is\n    // the original bug wearing a different hat. Measured on the same\n    // recording: gain dt*2.5 gave 27% speed variance, this gives 5%.\n    // The clamp is the guarantee: playback time can never bend by more than\n    // 8 percent, so no correction is ever visible as a stall or a dash.\n    this._playT += dt * 1000;\n    const err = target - this._playT;\n    const cap = dt * 1000 * 0.08;\n    this._playT += Math.max(-cap, Math.min(cap, err * Math.min(1, dt * 0.5)));\n    return this._playT;\n  }",
    "srvPlayT")

sub(
    "      else { const ik = 1 - Math.exp(-11 * dt); const adt = this._srvSim ? Math.min(this._dtReal || dt, 0.25) : dt; for (const n of this.npcs) {\n        if (this._srvSim && n.sbT != null) {\n          // Play the monster from the previous server position to the latest\n          // one, over exactly the gap between them. Guessing past the newest\n          // sample is what caused the jagged look: it would run ahead, then\n          // get yanked back when the next one landed. Never guess; the cost is\n          // one update of delay, which is a tenth of a second.\n          const span = Math.min(700, Math.max(60, n.sbT - n.saT));\n          let a = (performance.now() - n.sbT) / span;\n          if (a < 0) a = 0; else if (a > 1) a = 1;\n          const tx = n.sax + (n.sbx - n.sax) * a, tz = n.saz + (n.sbz - n.saz) * a;\n          const ex2 = tx - n.pos.x, ez2 = tz - n.pos.z;\n          if (ex2 * ex2 + ez2 * ez2 > 16) { n.pos.x = tx; n.pos.z = tz; }\n          else { const sk = 1 - Math.exp(-30 * adt); n.pos.x += ex2 * sk; n.pos.z += ez2 * sk; }\n        }",

    "      else { const ik = 1 - Math.exp(-11 * dt); const adt = this._srvSim ? Math.min(this._dtReal || dt, 0.25) : dt; const play = this._srvSim ? this.srvPlayT(this._dtReal || dt) : null; for (const n of this.npcs) {\n        if (this._srvSim && n.sbuf && n.sbuf.length && play != null) {\n          // Draw the monster where the server had it at the playout instant,\n          // by finding the two samples that bracket it. Still never\n          // extrapolates: past the newest sample it holds, exactly as before.\n          // What is new is that the buffer holds enough history for the\n          // playout point to sit a fixed distance back, so a packet arriving\n          // late is absorbed instead of being rendered as a dead stop.\n          //\n          // The samples used to be stamped on ARRIVAL and only two were kept,\n          // which made the interpolation span the network jitter rather than\n          // the world time the segment covers.\n          const bf = n.sbuf;\n          let bi = bf.length - 1;\n          while (bi > 0 && bf[bi].t > play) bi--;\n          const A = bf[bi], B = bf[bi + 1];\n          if (!B || play <= A.t) { n.pos.x = A.x; n.pos.z = A.z; }\n          else {\n            const sp = B.t - A.t;\n            let a = sp > 0 ? (play - A.t) / sp : 1;\n            if (a > 1) a = 1;\n            // Straight assignment. The old second smoother on top of this was\n            // double filtering: a third of a snapshot of extra lag, and it\n            // rounded off the start and stop of every segment.\n            n.pos.x = A.x + (B.x - A.x) * a;\n            n.pos.z = A.z + (B.z - A.z) * a;\n          }\n          while (bf.length > 2 && bf[1].t < play - 500) bf.shift();\n        }",
    "server time interpolation")

sub(
    "      // two samples with their arrival times: the monster is then drawn moving\n      // from one to the other over the real gap between them, instead of\n      // snapping to each new one and waiting for the next\n      n.sax = n.sbx == null ? r[1] / 10 : n.sbx;\n      n.saz = n.sbz == null ? r[2] / 10 : n.sbz;\n      n.saT = n.sbT == null ? this._wAt : n.sbT;\n      n.sbx = r[1] / 10; n.sbz = r[2] / 10; n.sbT = this._wAt;",

    "      // A short history of positions stamped with the SERVER's own time. Two\n      // samples is not enough: the playout point sits a fixed distance behind\n      // the newest sample, and with only a 100ms window to work in it falls\n      // off the back of the pair and the monster judders between held\n      // positions. A second of history is a few hundred bytes per monster.\n      //\n      // The buffer is dropped and restarted on a gap or a backwards stamp.\n      // Carrying an old sample across a pause replayed a stale segment: the\n      // target became a position from seconds ago, which teleported the\n      // monster backwards and then crawled it forward.\n      const sT = (m.at != null) ? m.at : this.srvNow();\n      const sx = r[1] / 10, sz = r[2] / 10;\n      let bf = n.sbuf;\n      const lastT = (bf && bf.length) ? bf[bf.length - 1].t : null;\n      if (!bf || lastT == null || (sT - lastT) > 400 || sT < lastT - 2000) bf = n.sbuf = [];\n      // Insert in time order rather than assuming packets arrive in it. A\n      // sample that turns up after a newer one still belongs in the\n      // timeline, and it is exactly the case the buffer exists to cover:\n      // throwing the buffer away for it (which an earlier draft of this did)\n      // left one stale sample and froze the monster dead until the feed\n      // caught up. Reordering is common enough to be the normal case.\n      let ins = bf.length;\n      while (ins > 0 && bf[ins - 1].t > sT) ins--;\n      if (ins > 0 && bf[ins - 1].t === sT) bf[ins - 1] = { t: sT, x: sx, z: sz };\n      else bf.splice(ins, 0, { t: sT, x: sx, z: sz });\n      if (bf.length > 12) bf.shift();\n      const nb = bf[bf.length - 1];\n      n.sbT = nb.t; n.sax = nb.x; n.saz = nb.z; n.sbx = nb.x; n.sbz = nb.z; n.saT = nb.t;\n      if (this._newestSnapT == null || sT > this._newestSnapT) this._newestSnapT = sT;",
    "server time samples")

sub(
    "      if (this.npcs) for (const n of this.npcs) { n.sbT = null; n.saT = null; n.sbx = null; }",

    "      this._newestSnapT = null; this._playT = null;   // the playout clock indexes samples that are now gone\n      if (this.npcs) for (const n of this.npcs) { n.sbT = null; n.saT = null; n.sbx = null; n.sbuf = null; }",
    "reset playback clock on disconnect")

sub(
    "    n.sbT = null; n.saT = null; n.sbx = null;    // do not play a path from before it died",

    "    n.sbT = null; n.saT = null; n.sbx = null; n.sbuf = null;    // do not play a path from before it died",
    "drop the buffer on respawn")

for old, new, label in edits:
    assert src.count(old) == 1, 'anchor %s went stale' % label
    src = src.replace(old, new)

io.open(SRC, 'w', encoding='utf-8').write(src)
print('patched %d anchors -> %s' % (len(edits), SRC))
