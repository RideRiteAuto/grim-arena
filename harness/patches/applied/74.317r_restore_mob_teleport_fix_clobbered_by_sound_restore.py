"""Recovery patch: restore patch 74.317 (mobs no longer teleport as you close
distance) into the bundle after it got clobbered by the 77.612r sound-sweep
recovery push.

Same failure shape as the 77.612r recovery itself, one push earlier: the
77.612r commit was built from a fetch of origin taken before 6ba02ea (patch
74.317) landed, and the whole-file upload silently reverted 74.317's bundle
changes the moment it went out. 74.317 shipped bundle-only (its own patch
script and harness/reacquire.js test evidently land in a later stage-2
commit, following this project's now-familiar two-stage pattern - see
72.319/72.416/72.883's stage-2 "Add patch records" commits), so there is no
source-of-record script to replay here. Reconstructed instead by diffing the
extracted game source of the two real commits bracketing it (da7fa3f before,
6ba02ea after) and replaying that exact diff, three hunks, against the
current (locomotion + 77.612-restored) bundle:

  1. stepNpcs' interpolation block: the straight assignment into n.pos.x/z
     now writes into local tx/tz first, then (if a short-lived n._glideUntil
     window is active) eases from the last drawn position to the truth
     instead of snapping, self-expiring after GLIDE_MS.
  2. farBand's hide radius: 90m (OUT=[2500,7225,8100]) down to 65m
     (OUT=[2500,3600,4225]), just past GRIM_RULES.INTEREST_R (60m), so the
     client stops drawing a monster once the relay stops telling it that
     monster's real position.
  3. The buffer-reseed site: on a reseed where a monster is already visible
     and the true position isn't far (<=30m) from where this client last
     drew it, arms the short glide window read by hunk 1; a reseed after a
     bigger jump is left alone (a legitimate teleport, not sync jitter).

None of this touches animate(), poseQuadRig() or anything the locomotion
patches or the sound sweep restoration changed - confirmed by re-grepping
all three anchors fresh against the current source before writing this
patch, all three still present and unmodified.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()


def sub(old, new, label):
    global s
    n = s.count(old)
    assert n == 1, '%s: matched %d times' % (label, n)
    s = s.replace(old, new)


# ---------------------------------------------------------------------------
# 1. stepNpcs interpolation: glide from last drawn position on a reseed
#    instead of snapping straight to the truth.
# ---------------------------------------------------------------------------
OLD_INTERP = """          if (!B || play <= A.t) { n.pos.x = A.x; n.pos.z = A.z; }
          else {
            const sp = B.t - A.t;
            let a = sp > 0 ? (play - A.t) / sp : 1;
            if (a > 1) a = 1;
            // Straight assignment. The old second smoother on top of this was
            // double filtering: a third of a snapshot of extra lag, and it
            // rounded off the start and stop of every segment.
            n.pos.x = A.x + (B.x - A.x) * a;
            n.pos.z = A.z + (B.z - A.z) * a;
          }"""

NEW_INTERP = """          let tx, tz;
          if (!B || play <= A.t) { tx = A.x; tz = A.z; }
          else {
            const sp = B.t - A.t;
            let a = sp > 0 ? (play - A.t) / sp : 1;
            if (a > 1) a = 1;
            // Straight assignment. The old second smoother on top of this was
            // double filtering: a third of a snapshot of extra lag, and it
            // rounded off the start and stop of every segment.
            tx = A.x + (B.x - A.x) * a;
            tz = A.z + (B.z - A.z) * a;
          }
          // A short bounded glide for the frame(s) right after a reseed (see
          // onNpcSnap): eases from the last position this client actually
          // drew to the truth instead of assigning it outright. Self-expires
          // once GLIDE_MS elapses, so it never lingers into ordinary playback.
          if (n._glideUntil && n._glideUntil > performance.now()) {
            const gt = Math.min(1, Math.max(0, 1 - (n._glideUntil - performance.now()) / n._glideDur));
            const ge = 1 - (1 - gt) * (1 - gt);
            n.pos.x = n._glideFromX + (tx - n._glideFromX) * ge;
            n.pos.z = n._glideFromZ + (tz - n._glideFromZ) * ge;
          } else {
            n.pos.x = tx; n.pos.z = tz;
          }"""

sub(OLD_INTERP, NEW_INTERP, 'stepNpcs glide-on-reseed (74.317)')

# ---------------------------------------------------------------------------
# 2. farBand hide radius: 90m -> 65m.
# ---------------------------------------------------------------------------
OLD_FARBAND = """  // and out, or change gait, twice a second. Measured across the 90m line:
  // 89.4 visible, 90.3 hidden, 90.6 hidden, 89.9 visible. A band now has to
  // be left by a wider margin than it was entered by. Returns 0 to hide,
  // otherwise the animation stride.
  farBand(e, d2) {
    const OUT = [2500, 7225, 8100];            // 50m, 85m, 90m"""

NEW_FARBAND = """  // and out, or change gait, twice a second. Measured across the old 90m
  // line: 89.4 visible, 90.3 hidden, 90.6 hidden, 89.9 visible. A band now
  // has to be left by a wider margin than it was entered by. Returns 0 to
  // hide, otherwise the animation stride.
  //
  // Hide radius sits at 65m, just past GRIM_RULES.INTEREST_R (60m): the
  // relay never tells this client where a monster is once it's farther
  // than that, so showing one out to 90m meant a 30m ring where the game
  // drew a monster with no live position behind it - frozen until you got
  // close enough to be told the truth, then a visible pop. See patch
  // 74.317 and claude/MOB-SYNC-JITTER-PLAN.md.
  farBand(e, d2) {
    const OUT = [2500, 3600, 4225];            // 50m, 60m, 65m"""

sub(OLD_FARBAND, NEW_FARBAND, 'farBand hide radius (74.317)')

# ---------------------------------------------------------------------------
# 3. Buffer reseed: arm the glide window read by hunk 1.
# ---------------------------------------------------------------------------
OLD_RESEED = """      if (!bf || lastT == null || (sT - lastT) > 400 || sT < lastT - 2000) bf = n.sbuf = [];"""

NEW_RESEED = """      const reseed = !bf || lastT == null || (sT - lastT) > 400 || sT < lastT - 2000;
      // A reseed with nothing yet drawn to interpolate from used to pop
      // straight to the truth next frame - the biggest source of the
      // 'teleports as I get closer' report. Narrowing farBand's hide radius
      // to sit close to INTEREST_R makes this rare, but a monster can still
      // legitimately drop out for a moment (a frame hitch, pacing the exact
      // edge). When it does, and the true position is not far from where
      // this client last actually drew it, ease to it over a short window
      // instead of assigning it in one frame. Past GLIDE_CAP the monster
      // wandered far enough while unseen that a jump is the honest result,
      // and a slide across the screen would look worse than the snap it
      // replaces.
      if (reseed && n.pos && n.g && n.g.visible) {
        const GLIDE_CAP = 30, GLIDE_MS = 220;
        const dgx = sx - n.pos.x, dgz = sz - n.pos.z;
        if (Math.hypot(dgx, dgz) <= GLIDE_CAP) {
          n._glideFromX = n.pos.x; n._glideFromZ = n.pos.z;
          n._glideUntil = performance.now() + GLIDE_MS; n._glideDur = GLIDE_MS;
        } else { n._glideUntil = 0; }
      }
      if (reseed) bf = n.sbuf = [];"""

sub(OLD_RESEED, NEW_RESEED, 'buffer reseed glide arm (74.317)')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('74.317 restored into bundle after 77.612r-restore clobber')
