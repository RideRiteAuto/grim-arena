# Ground-paint hard-edge bug: handoff (still open)

Read `claude/PROJECT-MEMORY.md` first if you haven't (Supabase/Cloudflare
details, non-negotiable rules, how to push safely without clobbering another
track's work). This doc picks up one specific bug thread; it does not replace
PROJECT-MEMORY.

Kevin voice-dictates from his phone. If a message from him reads garbled or
off-topic, flag it back to him rather than acting on it.

## Where this stands right now

Kevin reported that painting ground textures (e.g. meadow onto ordinary
ground) still leaves hard, blocky, "staircase" edges on **some** sides of a
brush stroke, even after a fix (patch 86.100) that was supposed to make
coverage fade smoothly with distance. He sent an annotated screenshot with
arrows pointing at specific edges that were still hard, while other edges of
the *same* circle looked fine.

His standing instruction (paraphrased, from the live conversation): try a
fix, verify it with a real before/after screenshot comparison in the editor
before shipping, and if it's still not right, say so and iterate again rather
than reporting success prematurely. Two fix attempts have gone out so far;
**a third has been root-caused below but NOT YET implemented, built, or
screenshotted.** Do not report this fixed to Kevin until you have real
before/after renders proving it.

## Everything already shipped (do not redo, do not regress)

1. **Patch 82303a3 / 83.200** (`shared-rules.js`, `EDIT.BLEND_DEFAULT`): widened
   the default ground-paint blend radius from 2m to 5m. Fixed the original
   "meadow into mountain gravel looks hard" complaint. Verified, shipped, live.
2. **Patch 433967b / 86.100** (`editor-core.js`, `paintAt()`): the original
   coverage formula only ever averaged over *painted* neighbour cells, so
   coverage inside any single-surface stroke was mathematically pinned at
   1.0 all the way to a hard cliff, regardless of the blend width. Rewrote it
   to weigh painted AND unpainted neighbours, so coverage now genuinely tapers
   with distance. Verified three ways (Node harness against the real
   extracted function text, live in-browser probing, before/after
   screenshots) and confirmed painted-to-painted borders are bit-identical
   before/after (no regression to the already-working case). **This fix is
   correct and should not be touched or re-litigated** — see the fresh
   probe data below, which independently reconfirms `paintAt()` now returns a
   clean, smoothly-decreasing coverage curve.

After 86.100 shipped, Kevin said it *still* wasn't fixed (with the annotated
screenshot). That sent this investigation down a second path:

3. **Ruled out: `ditherMix()`'s contrast-based dithering gate** (from an
   earlier patch, 83.100, in the raw doc outside all marker regions, function
   `ditherMix()` inside `makeGroundMat()`'s `onBeforeCompile`, around line
   11279 of `/tmp/game-src.html`). Hypothesis was that this GLSL function's
   luma-contrast gate was discarding the correct smooth coverage gradient by
   falling back to a noisy/binary `hardPick` render path whenever two
   textures have similar brightness (which covers nearly every case Kevin
   actually paints, e.g. meadow vs. mountain gravel/packed dirt/heath, all
   under the 0.12 "no effect" threshold in that gate).
   **This was tested directly and disproven just before this handoff was
   written.** A diagnostic patch forcing `aa = 1.0` and `contrast = 1.0`
   unconditionally (fully bypassing dithering, always using a plain smooth
   `mix(a,b,t)`) was built into a scratch bundle and rendered at the exact
   same test position/settings as the original complaint. **The render was
   pixel-for-pixel almost identical to the current shipped (buggy) render**
   (max channel diff of 29/255 across the whole frame, spread evenly, no
   visible change at the boundary itself — screenshots below). Confirmed the
   patched shader source actually reached the served bundle (grepped for
   `float contrast = 1.0;` in the served HTML) before concluding this. **Do
   not re-attempt a ditherMix fix; the smoking gun below is a different,
   earlier stage of the pipeline that no amount of shader-side smoothing can
   fix, because the input it's fed is not actually monotonic.**

## The real root cause, found just before this handoff (NOT YET fixed)

Location: **`editor-core.js`, function `paint(wx, wz, out)`, lines 631–648**
(this lives inside the EDITOR marker region, so fix it in the TRACKED FILE
`editor-core.js`, then `python3 repack.py pack`, same as any other editor
change — do NOT edit `/tmp/game-src.html` directly for this one).

```js
function paint(wx, wz, out) {
  if (!api.on) return;
  if (paintBounds && (wx < paintBounds.x0 || wx > paintBounds.x1 ||
                      wz < paintBounds.z0 || wz > paintBounds.z1)) return;
  let hit = paintAt(wx, wz);
  const rd = roadAt(wx, wz);
  if (rd && (!hit || rd[1] >= hit[1])) hit = rd;
  if (!hit) return;
  const surf = hit[0], cov = hit[1];
  const around = (out[4] > 0.5) ? out[1] : out[0];        // <-- t0 = out[4] here
  if (surf === around) { out[0] = around; out[1] = around; return; }
  out[0] = around; out[1] = surf;
  out[4] = Math.max(out[4] * (1 - cov), cov);              // <-- BUG: reuses t0 unmodified
  if (cov > 0.6) { out[5] = out[5] * (1 - cov); out[6] = out[6] * (1 - cov); }
}
```

`out[4]` is the blend weight, read as `mix(out[0], out[1], out[4])` downstream
(0 = pure `out[0]`, 1 = pure `out[1]`). Call the natural, pre-paint value of
`out[4]` **t0**.

- If `t0 <= 0.5`, `around` is assigned from the natural `out[0]`. The old
  `t0` (small, ≤0.5) genuinely represents "how much of *not-around* is
  naturally showing here", so reusing it as the residual term in
  `max(t0*(1-cov), cov)` is roughly sound: as `cov→0` the result eases back
  toward a small residual instead of slamming to 0, and as `cov→1` it
  correctly goes to 1 (pure `surf`).
- If `t0 > 0.5`, `around` is assigned from the natural `out[1]` **instead**.
  But the code still reuses `t0` (now large, e.g. 0.97) as the residual term.
  Since `out[1]` has just been reassigned to `surf`, `t0` no longer means
  "residual toward not-around" in this branch — it means the opposite. The
  correct residual here is `(1 - t0)`, not `t0`. Because the code forgets to
  complement it, whenever a paint stroke's edge crosses ground where the
  *natural, unpainted* terrain already leaned toward its own second texture
  (`t0 > 0.5`, which is common and effectively random per-vertex, unrelated
  to where you painted), the formula produces a spurious HIGH weight toward
  `surf` even where real coverage (`cov`) has already faded to almost
  nothing.

### Real proof, captured live from the actual running game

Test: painted a single hardness=1/flow=1/organic=false meadow (surf 0) dot,
brush radius 8, centered at world (0, 300), on flat HEARTLANDS ploughed/dirt
terrain (the same spot used for all prior before/after screenshots in this
thread). Sampled straight along +X from the center.

Real `GRIM_EDIT.paintAt(x, 300)` coverage (this is `paintAt()`'s own output —
confirms 86.100 is working correctly, smooth and monotonic):

```
x=4   cov=0.9911
x=5   cov=0.9039
x=6   cov=0.7763
x=7   cov=0.6630
x=8   cov=0.5546
x=9   cov=0.3966
x=10  cov=0.1853
x=11  cov=0.0365
x=12  cov=null      (below the 0.02 cutoff, paint() no-ops entirely beyond here)
```

Real per-vertex `out[]` AFTER `paint()` has run (captured by monkey-patching
`groundSurface` during an actual chunk rebuild, so this is the literal data
the shader receives — tile pair + blend weight):

```
x=-4  tileA=7 tileB=0 mixAB=0.9978   (~100% meadow, correct)
x=0   tileA=2 tileB=0 mixAB=1.0000   (100% meadow, correct)
x=6   tileA=2 tileB=0 mixAB=0.7763   (78% meadow, matches cov, correct)
x=8   tileA=2 tileB=0 mixAB=0.5546   (55% meadow, matches cov, correct)
x=10  tileA=2 tileB=0 mixAB=0.7869   (79% meadow  <- should be ~19%, matching cov=0.1853!)
x=12  tileA=7 tileB=2 mixAB=0.9959   (0% meadow at all — paint() gave up entirely)
```

`x=10` is the smoking gun: real coverage says the paint should be almost
gone (`cov=0.1853`, i.e. ~19% meadow), but the buggy remap shows **79%**
meadow instead, because the natural terrain's own `t0` at that vertex
happened to be `> 0.5` (roughly 0.966, back-calculated from
`0.966*(1-0.1853) ≈ 0.787`). Then two metres further out, coverage crosses
the 0.02 cutoff and paint stops applying at all, so the surface jumps from
~79% meadow straight to 0% meadow in a single 2m step. **That 79%→0% snap
over 2 metres is almost certainly the "hard, blocky" edge Kevin is still
seeing** — not a dithering artifact, not a mesh-resolution artifact. It also
explains why he saw hard edges on *some* sides of the circle and not others
via arrows on one screenshot: whether a given radial direction hits this bug
depends on whether the *natural, unpainted* terrain's own blend happens to
have `t0 > 0.5` at each specific vertex around the circle, which varies by
direction. Directions where natural `t0 <= 0.5` the whole way through render
correctly today; directions that cross into `t0 > 0.5` show this bump-then-
cliff.

### The fix (not yet applied)

In `editor-core.js`, complement `t0` in the branch where `around` comes from
`out[1]`:

```js
function paint(wx, wz, out) {
  if (!api.on) return;
  if (paintBounds && (wx < paintBounds.x0 || wx > paintBounds.x1 ||
                      wz < paintBounds.z0 || wz > paintBounds.z1)) return;
  let hit = paintAt(wx, wz);
  const rd = roadAt(wx, wz);
  if (rd && (!hit || rd[1] >= hit[1])) hit = rd;
  if (!hit) return;
  const surf = hit[0], cov = hit[1];
  const t0 = out[4];
  const around = (t0 > 0.5) ? out[1] : out[0];
  if (surf === around) { out[0] = around; out[1] = around; return; }
  const resid = (t0 > 0.5) ? (1 - t0) : t0;   // <-- the fix: complement when around came from out[1]
  out[0] = around; out[1] = surf;
  out[4] = Math.max(resid * (1 - cov), cov);
  if (cov > 0.6) { out[5] = out[5] * (1 - cov); out[6] = out[6] * (1 - cov); }
}
```

Sanity-check against the captured data: at `x=10`, `resid = 1 - 0.966 =
0.034`, giving `out[4] = max(0.034*(1-0.1853), 0.1853) = max(0.0277, 0.1853)
= 0.1853` — matches `cov` almost exactly, eliminating the bump. At `x=6/8`
(where the live data already happened to have `t0 <= 0.5` apparently, since
those matched `cov` correctly already), the fix is a no-op, since `resid =
t0` unchanged in that branch. This should also be sanity-checked at a couple
of `t0<=0.5` sample points to be sure nothing regresses there — the harness
described below (regression check #2, painted-to-painted borders) already
covers the most important such case, but re-run it after the change.

### Bonus finding, NOT in scope, flag but don't touch without asking

The exact same buggy pattern exists in the **bridge abutment pad** logic, a
few hundred lines away in the raw doc (not a tracked file), inside
`groundSurface()`:

```js
const pad = this.bridgePad(wx, wz);
if (pad > 0.002) {
  const around = (out[4] > 0.5) ? out[1] : out[0];
  const worn = this.padSurfaceFor(around);
  if (worn !== around) {
    out[0] = around; out[1] = worn;
    out[4] = Math.max(out[4] * (1 - pad), pad);   // same bug shape
  }
}
```

This affects the worn-ground texture at bridge abutments, not the paint
tool. It's plausible bridge abutments have the same "sometimes hard, sometimes
soft" edge depending on natural terrain, but nobody has complained about it
and it wasn't part of what Kevin asked about this session. Leave it alone
unless Kevin separately reports an issue there — flagging it here so it's
not "discovered" again from scratch later.

## What to do next, in order

1. Re-fetch and re-check the repo state before touching anything (multi-track
   collision safety — other Claude sessions may be pushing to `master`
   concurrently; see PROJECT-MEMORY.md and PUSHING.md):
   ```
   cd /home/claude/grim-arena && git fetch origin master && git log origin/master -1
   ```
   Compare against the expected head at the time of this handoff:
   `433967bc9d1c... ("Fix ground-paint coverage falloff...")` — if origin has
   moved past this, read what landed before proceeding, in case it touches
   `editor-core.js`.
2. Apply the fix above to `editor-core.js` (`paint()` function, lines
   631–648 as of this writing — confirm the line numbers still match first).
3. Run `python3 repack.py extract` then `pack` (pack also re-syncs
   `shared-rules.js`/world-gen/editor files; make sure `node --check` gates
   in `harness/build.sh` pass).
4. **Verify exactly the way Kevin has asked for twice now: a real before/after
   screenshot comparison in the editor, not just "I checked the math".**
   Reuse `harness/ground-paint-visual.js` (paints a single hardness=1/flow=1/
   organic=false meadow dot at a configurable `PX`/`PZ`, camera straight down)
   at the SAME test location used throughout this thread: `PX=0 PZ=300`,
   camera y=45. Compare against a fresh render of the CURRENT (pre-fix) shipped
   bundle at the same spot for a true before/after. Example:
   ```
   # serve the live/current repo (a server may already be running on 8123 from
   # a previous session -- check with `curl -s -o /dev/null -w '%{http_code}\n'
   # http://127.0.0.1:8123/` before starting a second one)
   node harness/serve.js &      # run this in its OWN isolated shell call, never
                                 # chained with && / ; -- chaining kills it
                                 # (observed repeatedly this project, exit 144)
   PX=0 PZ=300 node harness/ground-paint-visual.js http://127.0.0.1:8123/ /tmp/before.png
   # apply the fix, repack, then re-serve (or serve a second copy) and:
   PX=0 PZ=300 node harness/ground-paint-visual.js http://127.0.0.1:8123/ /tmp/after.png
   ```
   Also worth re-running the direction-dependent probe (`probe7.js`/`probe8.js`
   style: monkey-patch `groundSurface`, force a chunk rebuild, sample along a
   line) in at least one direction where the bug was confirmed (+X from the
   test point) to numerically confirm the bump is gone, not just "looks better".
   The exact probe scripts used to find this bug are NOT committed anywhere
   (pure scratch, written directly into `/tmp/probe7.js` and `/tmp/probe8.js`
   during this session) — they no longer exist in a fresh container, but the
   technique is fully described above and easy to rebuild: monkey-patch
   `G.groundSurface`, force `G._chunks.clear()` + `G.stepTerrain(0, 400)` with
   `G._terrAcc = 99` to force a rebuild, and/or call `G.EDIT().paintAt(x, z)`
   directly for the coverage-only check.
5. If the before/after still doesn't look right, **say so and keep
   iterating** — do not ship and report success prematurely. This has already
   happened twice in this thread; Kevin explicitly expects another round if
   needed and said as much.
6. Once genuinely confirmed smooth, ship as the next patch number after
   checking `harness/patches/applied/` for the current highest (as of this
   writing: `86.100`; use something like `86.150` if still free — check
   fresh, another track may have taken a number since). Write the patch
   script into `harness/patches/` (pending) with a docstring following the
   style of `86.100_ground_paint_coverage_falloff.py`, run it through
   `harness/build.sh`, then move it to `harness/patches/applied/` once shipped.
7. Push via the Git Data API procedure in `claude/PUSHING.md` (the sandbox
   cannot `git push` or reach `api.github.com` directly for this repo, but
   `git fetch` works). Reuse credentials/repo already on file in this
   project's instructions. **Verify the push landed with a sandbox `git fetch
   origin master` + `git log`/`git diff --stat` afterward — do not trust only
   a browser-side JS return value.**
8. Report back to Kevin with the real before/after images and a plain-language
   explanation (he's non-technical but has been engaged and precise about
   what he's seeing — the "some edges of the circle but not others" framing
   from his own screenshot is worth referencing back to him, since this fix
   explains exactly that symptom).

## Other useful context for whoever picks this up

- Kevin dictates by voice from his phone; expect garbled or run-on messages.
  Read for intent; flag anything that seems off-topic or contradictory rather
  than guessing.
- This repo bundles a full game document as JSON inside `index.html` /
  `grim-arena-standalone.html` (byte-identical). `repack.py extract` pulls it
  to `/tmp/game-src.html`; `repack.py pack` re-syncs `shared-rules.js`,
  world-gen files, and editor files (`editor-core.js`/`editor-tools.js`/
  `editor-ui.js`) back into marker regions of that doc, then re-embeds it into
  both bundle files. Code inside the SHARED-RULES/WORLD-GEN/EDITOR marker
  regions of `/tmp/game-src.html` MUST be edited via the corresponding tracked
  `.js` file, never in `/tmp/game-src.html` directly (pack() will silently
  clobber direct edits there). `paint()` and `paintAt()` are inside the
  EDITOR markers (in `editor-core.js`) — this fix goes there. `ditherMix()`
  and `buildGroundArray()` live OUTSIDE all marker regions (patch them via a
  `.py` script operating on `/tmp/game-src.html` directly, matching patches
  83.100/83.150 — not relevant to THIS fix, just noting for context since this
  thread spent a while investigating that area).
- There is at least one other track working concurrently on this same
  dashboard/game (a separate Claude session working on the world editor's
  "Today and this week"-style features was mentioned earlier in this
  project's history, in an unrelated RideRite context — not this repo. Within
  THIS repo/project, check `claude/*-STATUS.md` and `claude/*-HANDOFF*.md`
  docs and re-`git fetch` before building/pushing, since multiple tracks can
  land on `master` concurrently). See `claude/PROJECT-MEMORY.md` for the full
  multi-track safety protocol.
- A separate, unrelated, still-open thread from earlier in this project:
  Kevin asked about the world editor's "Spawns" (NPC placement) tool, which
  was found to be genuinely incomplete (authors data nothing in the live game
  reads). He has not yet responded on whether to proceed. Do not resume that
  work unless he explicitly brings it back up — it's unrelated to this
  ground-paint bug.
