"""Fix the visible seam at the base of every tree, where the planted base
flare meets the trunk above it (and, after a fell, where the stump's cut
face meets the trunk) - visible even on a standing, uncut tree.

Kevin: "at the base of the trees where the tree trunk meets the stump, the
models don't quite line up right, and you can see the seam where the stump
and tree snap. Even when the tree is still standing before you cut it
down. Can you do whatever it takes to hide that seam."

Applied first to model-lab/tree.js and model-lab/grim-kit.js (the source of
truth - see tree.js's own updated docstring for the full writeup), then
replayed here against the bundle's already-embedded copy with the same
substitutions, anchors re-grepped fresh against a freshly extracted bundle
before writing this patch. Three independent defects were stacked at that
one seam:

1. RADIUS MISMATCH. The upper loft's own taper is measured from the ground,
   so by breakY it has already narrowed past K.r - but the base flare's
   closing ring, and both stumpCap break-face discs, used to hardcode a flat
   K.r there with no taper of their own. Fixed by computing one breakR up
   front (the upper loft's own taper formula) and reusing it in all four
   places that have to meet at the break line.

2. JITTER MISMATCH. roughen() jitters every vertex by a hash of that
   vertex's own position plus a seed - identical only when the position
   itself matches. The upper loft was built in hinge-local space while the
   lower loft was built in world space, so even with matching radii the
   shared seed hashed to different numbers at the same physical point on
   the trunk. Fixed by building the upper loft in world space too (like the
   lower loft), translating into hinge space only after roughening and
   paint are baked in.

3. COINCIDENT END CAPS. loftRect auto-caps both ends of every loft. Two
   lofts butted flush against each other each grow their own cap at the
   shared ring - two coincident, oppositely-facing flat discs, a textbook
   z-fight. Fixed by adding an opt-in caps:{start,end} parameter to
   loftRect and skipping the redundant cap on each side of the seam.

Every tree kind (oak, willow, pine, redwood, palm, the dead-wood kinds, all
of them) is built from this one shared natureKits().tree code path, so one
set of changes fixes every species. loftRect is inlined three times in the
bundle (furnace, anvil and nature kits each carry their own copy); only the
copy inside natureKits() is touched here, via a region-restricted
substitution anchored after the `natureKits() {` marker so the identical
furnace/anvil copies are left alone.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()


def sub(old, new, label):
    global s
    n = s.count(old)
    assert n == 1, '%s: matched %d times' % (label, n)
    s = s.replace(old, new)


def sub_after(marker, old, new, label):
    """Restrict the substitution to the text AFTER marker's first (and only)
    occurrence - for anchors that are byte-identical in more than one
    duplicated inline copy elsewhere in the bundle."""
    global s
    mpos = s.find(marker)
    assert mpos >= 0 and s.find(marker, mpos + 1) < 0, '%s: marker not unique' % label
    head, tail = s[:mpos], s[mpos:]
    n = tail.count(old)
    assert n == 1, '%s: matched %d times after marker' % (label, n)
    s = head + tail.replace(old, new)


# ---------------------------------------------------------------------------
# 1. loftRect (natureKits' own inlined copy only): add the opt-in caps param.
# ---------------------------------------------------------------------------
OLD_LOFTRECT = """    function loftRect(T, axis, sections, n, paint) {
      const pos = [], col = [];
      const c = new T.Color();
      const put3 = (a, b, at) => (axis === 'x' ? [at, b, a] : axis === 'y' ? [a, at, b] : [a, b, at]);
      const rings = sections.map(s => superRing(s.hu, s.hv, s.p === undefined ? 8 : s.p, n)
        .map(q => put3(q[0] + (s.cu || 0), q[1] + (s.cv || 0), s.at)));
      const lo = sections[0].at, hi = sections[sections.length - 1].at;
      const span = (hi - lo) || 1;
      const push = (v, t) => {
        pos.push(v[0], v[1], v[2]);
        if (paint) { paint(c, v[0], v[1], v[2], t); col.push(c.r, c.g, c.b); }
      };
      for (let r = 0; r < rings.length - 1; r++) {
        const t0 = (sections[r].at - lo) / span, t1 = (sections[r + 1].at - lo) / span;
        for (let i = 0; i < n; i++) {
          const j = (i + 1) % n;
          const a = rings[r][i], b = rings[r][j], cc = rings[r + 1][i], d = rings[r + 1][j];
          push(a, t0); push(cc, t1); push(b, t0);
          push(b, t0); push(cc, t1); push(d, t1);
        }
      }
      // End caps, wound so both face outward along the run axis.
      for (const [ri, dir] of [[0, -1], [rings.length - 1, 1]]) {
        const s = sections[ri];
        const ctr = put3(s.cu || 0, s.cv || 0, s.at);
        const t = (s.at - lo) / span;
        for (let i = 0; i < n; i++) {
          const j = (i + 1) % n, a = rings[ri][i], b = rings[ri][j];
          if (dir < 0) { push(ctr, t); push(a, t); push(b, t); }
          else { push(ctr, t); push(b, t); push(a, t); }
        }
      }
      const g = new T.BufferGeometry();
      g.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
      if (paint) g.setAttribute('color', new T.Float32BufferAttribute(col, 3));
      g.computeVertexNormals();
      return g;
    }"""

NEW_LOFTRECT = """    function loftRect(T, axis, sections, n, paint, caps) {
      const doStart = !caps || caps.start !== false;
      const doEnd = !caps || caps.end !== false;
      const pos = [], col = [];
      const c = new T.Color();
      const put3 = (a, b, at) => (axis === 'x' ? [at, b, a] : axis === 'y' ? [a, at, b] : [a, b, at]);
      const rings = sections.map(s => superRing(s.hu, s.hv, s.p === undefined ? 8 : s.p, n)
        .map(q => put3(q[0] + (s.cu || 0), q[1] + (s.cv || 0), s.at)));
      const lo = sections[0].at, hi = sections[sections.length - 1].at;
      const span = (hi - lo) || 1;
      const push = (v, t) => {
        pos.push(v[0], v[1], v[2]);
        if (paint) { paint(c, v[0], v[1], v[2], t); col.push(c.r, c.g, c.b); }
      };
      for (let r = 0; r < rings.length - 1; r++) {
        const t0 = (sections[r].at - lo) / span, t1 = (sections[r + 1].at - lo) / span;
        for (let i = 0; i < n; i++) {
          const j = (i + 1) % n;
          const a = rings[r][i], b = rings[r][j], cc = rings[r + 1][i], d = rings[r + 1][j];
          push(a, t0); push(cc, t1); push(b, t0);
          push(b, t0); push(cc, t1); push(d, t1);
        }
      }
      // End caps, wound so both face outward along the run axis. caps lets a
      // loft that butts flush against another solid at one end skip that
      // end's cap - otherwise two coincident, oppositely-facing discs z-fight.
      for (const [ri, dir, on] of [[0, -1, doStart], [rings.length - 1, 1, doEnd]]) {
        if (!on) continue;
        const s = sections[ri];
        const ctr = put3(s.cu || 0, s.cv || 0, s.at);
        const t = (s.at - lo) / span;
        for (let i = 0; i < n; i++) {
          const j = (i + 1) % n, a = rings[ri][i], b = rings[ri][j];
          if (dir < 0) { push(ctr, t); push(a, t); push(b, t); }
          else { push(ctr, t); push(b, t); push(a, t); }
        }
      }
      const g = new T.BufferGeometry();
      g.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
      if (paint) g.setAttribute('color', new T.Float32BufferAttribute(col, 3));
      g.computeVertexNormals();
      return g;
    }"""

sub_after('natureKits() {', OLD_LOFTRECT, NEW_LOFTRECT, 'loftRect caps param (78.204)')

# ---------------------------------------------------------------------------
# 2. stumpCap: accept an optional ringR override, default to K.r unchanged.
# ---------------------------------------------------------------------------
OLD_STUMPCAP = """      const stumpCap = (K, rnd, upward) => {
        const R = K.r * 0.97;
        const h = Math.max(0.05, K.r * 0.12);
        const ringPhase = rnd() * 6.28;"""

NEW_STUMPCAP = """      const stumpCap = (K, rnd, upward, ringR) => {
        // ringR is the ACTUAL wood radius at the break line (see breakR in
        // kit.build below) - it can be narrower than K.r once the upper
        // trunk's own taper is applied. Falls back to K.r for any future
        // caller that does not pass one.
        const R = (ringR === undefined ? K.r : ringR) * 0.97;
        const h = Math.max(0.05, K.r * 0.12);
        const ringPhase = rnd() * 6.28;"""

sub(OLD_STUMPCAP, NEW_STUMPCAP, 'stumpCap ringR param (78.204)')

# ---------------------------------------------------------------------------
# 3. the trunk block: shared breakR, world-space upper loft, caps skipped.
# ---------------------------------------------------------------------------
OLD_TRUNK = """        // ---- trunk: base flare to tip, split at the break line ------------------
        const lean = (rnd() - 0.5) * 0.16 * (K.sweep || 1) + (K.sweep ? (rnd() > 0.5 ? 0.08 : -0.08) * K.sweep : 0);
        const line = (t) => ({ x: lean * t * t * 2.4, y: t });   // gentle sweep
        const trunkSecs = [];
        const steps = [[0, K.flare * 0.82, 2.0], [0.04, K.r * 1.30, 2.5], [0.10, K.r * 1.06, 2.6]];
        for (const [tt, rr, p] of steps) {
          const y = tt * K.h;
          if (y > K.breakY) break;
          trunkSecs.push({ at: y, hu: rr, hv: rr, cu: line(y / K.h).x, p });
        }
        // lower trunk (planted): flare up to the break. This loft is the ENTIRE
        // base - no separate buttress-root lobes glued on. A first pass tried
        // those and they read as four little planks stuck on a pole no matter
        // how they were angled; the loft's own flare is the tree's base.
        const lower = loftRect(T, 'y', trunkSecs.concat([{ at: K.breakY, hu: K.r, hv: K.r, cu: line(K.breakY / K.h).x, p: 2.6 }]), 9,
          barkPaint(K, seed));
        roughen(T, lower, 0.085, seed + 2, 1);   // same seed as the upper loft
        woodDown.push({ geo: lower });

        // upper trunk (falls): break line to tip, in hinge space
        const upperSecs = [];
        const tipY = K.h * (0.86 + rnd() * 0.1);
        const nSec = 5;
        for (let i = 0; i <= nSec; i++) {
          const y = K.breakY + (tipY - K.breakY) * (i / nSec);
          const t = y / K.h;
          const rr = K.r * (1 - t * (K.taper === undefined ? 0.72 : K.taper));
          const [lx, ly, lz] = IN(line(t).x, y, 0);
          upperSecs.push({ at: ly, hu: Math.max(0.05, rr), hv: Math.max(0.05, rr), cu: lx, p: 2.6 });
        }
        const upper = loftRect(T, 'y', upperSecs, 9, (c, x, y, z) => barkPaint(K, seed)(c, x + hingeX, y + K.breakY, z));
        // a snag's top is TORN, not sawn: a jagged ring of upward shards. This is"""

NEW_TRUNK = """        // ---- trunk: base flare to tip, split at the break line ------------------
        const lean = (rnd() - 0.5) * 0.16 * (K.sweep || 1) + (K.sweep ? (rnd() > 0.5 ? 0.08 : -0.08) * K.sweep : 0);
        const line = (t) => ({ x: lean * t * t * 2.4, y: t });   // gentle sweep
        // The upper trunk's taper (below) is measured from the GROUND, not
        // from the break, so by the time its loft reaches the break line it
        // has already narrowed past K.r. The base flare used to close its
        // own top ring at a flat K.r with no such taper applied, so the two
        // lofts met at two different radii - a visible step ringing every
        // trunk right where the base flare meets the trunk above it, at the
        // base of the tree. The same step showed up on the stump's cut face
        // after a fell, for the same reason. One shared radius for that one
        // ring, reused by both lofts AND both stumpCap discs below, removes
        // it for every species built from this rig, since they all share
        // this exact code path.
        const upperTaperAmt = K.taper === undefined ? 0.72 : K.taper;
        const breakR = K.r * (1 - (K.breakY / K.h) * upperTaperAmt);
        const trunkSecs = [];
        const steps = [[0, K.flare * 0.82, 2.0], [0.04, K.r * 1.30, 2.5], [0.10, K.r * 1.06, 2.6]];
        for (const [tt, rr, p] of steps) {
          const y = tt * K.h;
          if (y > K.breakY) break;
          trunkSecs.push({ at: y, hu: rr, hv: rr, cu: line(y / K.h).x, p });
        }
        // lower trunk (planted): flare up to the break. This loft is the ENTIRE
        // base - no separate buttress-root lobes glued on. A first pass tried
        // those and they read as four little planks stuck on a pole no matter
        // how they were angled; the loft's own flare is the tree's base. The
        // closing ring uses breakR (not K.r) so it meets the upper loft's
        // first ring at an identical radius - see the comment above. end:false
        // skips this loft's own top cap: the upper loft's matching bottom
        // ring sits flush against it, so a cap here would be a second,
        // exactly coincident disc and z-fight with the one below.
        const lower = loftRect(T, 'y', trunkSecs.concat([{ at: K.breakY, hu: breakR, hv: breakR, cu: line(K.breakY / K.h).x, p: 2.6 }]), 9,
          barkPaint(K, seed), { end: false });
        roughen(T, lower, 0.085, seed + 2, 1);   // same seed as the upper loft
        woodDown.push({ geo: lower });

        // upper trunk (falls): break line to tip. Built in WORLD coordinates
        // here, NOT hinge space like the rest of woodUp - that puts its first
        // ring at the exact same (x,y,z) as the base flare's closing ring
        // right above, so roughen() (same seed, hashed off vertex position)
        // jitters every matching vertex around that ring identically instead
        // of just landing on the same average radius. Translated into hinge
        // space, the same place IN() would have put it, only once roughen and
        // the bark paint are already baked in below.
        const upperSecs = [];
        const tipY = K.h * (0.86 + rnd() * 0.1);
        const nSec = 5;
        for (let i = 0; i <= nSec; i++) {
          const y = K.breakY + (tipY - K.breakY) * (i / nSec);
          const t = y / K.h;
          const rr = K.r * (1 - t * upperTaperAmt);
          upperSecs.push({ at: y, hu: Math.max(0.05, rr), hv: Math.max(0.05, rr), cu: line(t).x, p: 2.6 });
        }
        // start:false skips this loft's own bottom cap for the same reason
        // the base flare above skips its top one - the two rings sit flush
        // and a cap on both sides is a coincident, z-fighting pair of discs.
        const upper = loftRect(T, 'y', upperSecs, 9, barkPaint(K, seed), { start: false });
        // a snag's top is TORN, not sawn: a jagged ring of upward shards. This is"""

sub(OLD_TRUNK, NEW_TRUNK, 'breakR + world-space upper loft + caps (78.204)')

# ---------------------------------------------------------------------------
# 4. roughen(upper) + woodUp.push: now needs the post-roughen translate into
#    hinge space (previously baked in via IN()/paint offset above).
# ---------------------------------------------------------------------------
OLD_UPPER_FINISH = """        roughen(T, upper, 0.085, seed + 2, 1);   // matches the lower loft at the break ring
        woodUp.push({ geo: upper });"""

NEW_UPPER_FINISH = """        roughen(T, upper, 0.085, seed + 2, 1);   // matches the lower loft at the break ring, vertex for vertex now that both build it in the same coordinate frame
        upper.translate(-hingeX, -K.breakY, 0);   // now into hinge space, where the fell group's own transform expects it
        woodUp.push({ geo: upper });"""

sub(OLD_UPPER_FINISH, NEW_UPPER_FINISH, 'upper translate into hinge space (78.204)')

# ---------------------------------------------------------------------------
# 5. the fell's own butt cap (hidden until the chop plays) - pass breakR.
# ---------------------------------------------------------------------------
OLD_BUTT = """        for (const p of stumpCap(K, rngFor(seed * 3 + 5), false)) {
          p.matrix = new T.Matrix4().makeTranslation(-hingeX + line(K.breakY / K.h).x, 0.006, 0).multiply(p.matrix);
          woodUp.push(p);
        }"""

NEW_BUTT = """        for (const p of stumpCap(K, rngFor(seed * 3 + 5), false, breakR)) {
          p.matrix = new T.Matrix4().makeTranslation(-hingeX + line(K.breakY / K.h).x, 0.006, 0).multiply(p.matrix);
          woodUp.push(p);
        }"""

sub(OLD_BUTT, NEW_BUTT, 'fell butt cap breakR (78.204)')

# ---------------------------------------------------------------------------
# 6. the stump crown cap (revealed after a fell) - pass breakR.
# ---------------------------------------------------------------------------
OLD_CROWN = """        for (const p of stumpCap(K, rngFor(seed * 3 + 5), true)) {
          p.matrix = new T.Matrix4().makeTranslation(line(K.breakY / K.h).x, K.breakY, 0).multiply(p.matrix);
          crownParts.push(p);
        }"""

NEW_CROWN = """        for (const p of stumpCap(K, rngFor(seed * 3 + 5), true, breakR)) {
          p.matrix = new T.Matrix4().makeTranslation(line(K.breakY / K.h).x, K.breakY, 0).multiply(p.matrix);
          crownParts.push(p);
        }"""

sub(OLD_CROWN, NEW_CROWN, 'stump crown cap breakR (78.204)')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('78.204 tree base seam fix applied: shared breakR, world-space upper loft, no coincident end caps - every species built from natureKits().tree')
