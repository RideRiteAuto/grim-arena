#!/usr/bin/env python3
"""Patch 79.612: expose the slope-to-rock and altitude-cap ground rules as
tunable, saved, per-world settings (Phase 3 of the ground texture plan,
claude/GROUND-TEXTURE-BRUSH-PLAN.md, approved by Kevin).

Kevin asked whether steepness-driven auto-texturing (a cliff face reading as
rock without hand painting it) is something this engine can do. It already
does, in two places, both currently hardcoded:

  - groundSurface() bakes an altitude "cap" weight per vertex: out[6] =
    (h - 52) / 26, which fades in the zone's cap surface (snow, scree,
    whatever that zone uses) between 52m and 78m. This is CPU-side, baked
    into the aMix vertex attribute at chunk build time.
  - groundFragBody() computes a per-fragment slope weight on the GPU:
    rw = smoothstep(0.16, 0.42, slope), where slope = 1 - the surface
    normal's Y. This is what actually paints a steep hillside as rock.

Both thresholds become authored, saved settings, defaulting to exactly
these numbers when unset so an existing world renders pixel-for-pixel
unchanged:

  - capLo/capHi (metres) replace the fixed 52/78 in groundSurface(). Read
    fresh every vertex, same as paint and height edits already are, so no
    extra plumbing is needed to keep it live.
  - slopeLo/slopeHi (0..1, matching the shader's own `slope` value) replace
    the fixed 0.16/0.42 in groundFragBody(). This one lives in a shader
    uniform (uSlope) rather than per-vertex data, since it is evaluated on
    the GPU: set once at first material compile from the authored layer,
    and pushed again by the new setSlopeRule() whenever it changes, wired
    into rebuildWorld() so every existing call site that already rebuilds
    the world after an edit picks it up for free.

editor-core.js gets the new fields validated in sanitize() (this layer is
network data, per that file's own rule: never trust a raw number into a
divide-by-zero or a NaN chunk). editor-ui.js gets four new sliders and a
reset button on the World tab, next to the existing layer stats.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 79.612 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. altitude cap: read authored capLo/capHi, CPU side --------------
sub(
    """    // Above the tree line the cap surface takes over. A weight, not a swap, so
    // the snow line is a band rather than a contour drawn with a ruler.
    out[6] = Math.max(0, Math.min(1, (h - 52) / 26));""",
    """    // Above the tree line the cap surface takes over. A weight, not a swap, so
    // the snow line is a band rather than a contour drawn with a ruler.
    // Patch 79.612: authored capLo/capHi (ground texture plan, Phase 3)
    // override the fixed 52..78m band when set. Read fresh every vertex,
    // the same way paint() below already is, so this is always in step
    // with the current layer with no extra plumbing. Null on either means
    // "engine default", so an untouched world computes the exact same
    // (h - 52) / 26 as before.
    {
      const capR = (typeof GRIM_EDIT !== 'undefined') ? GRIM_EDIT.raw : null;
      const capLo = (capR && capR.capLo != null) ? capR.capLo : 52;
      const capHi = (capR && capR.capHi != null) ? capR.capHi : 78;
      out[6] = Math.max(0, Math.min(1, (h - capLo) / Math.max(1, capHi - capLo)));
    }""",
    tag='groundSurface: authored altitude cap')

# ---- 2. slope-to-rock: read from a shader uniform instead of a constant --
sub(
    """      'float rw = smoothstep(0.16, 0.42, slope);',""",
    """      'float rw = smoothstep(uSlope.x, uSlope.y, slope);',""",
    tag='groundFragBody: uSlope uniform replaces the fixed threshold')

sub(
    """          'uniform highp sampler2DArray uGround;',
          'flat varying vec4 vTile;',""",
    """          'uniform highp sampler2DArray uGround;',
          'uniform vec2 uSlope;',
          'flat varying vec4 vTile;',""",
    tag='declare uSlope in the fragment shader')

sub(
    """    m.onBeforeCompile = (sh) => {
      sh.uniforms.uGround = { value: surfaces };
      sh.vertexShader = sh.vertexShader""",
    """    m.onBeforeCompile = (sh) => {
      sh.uniforms.uGround = { value: surfaces };
      // Patch 79.612: authored slopeLo/slopeHi (ground texture plan,
      // Phase 3) move the slope-to-rock threshold here. Read once at first
      // compile, the same timing uGround above already relies on;
      // setSlopeRule() below pushes any later live change straight into
      // this uniform's value, no recompile needed.
      {
        const slopeR = (typeof GRIM_EDIT !== 'undefined') ? GRIM_EDIT.raw : null;
        sh.uniforms.uSlope = { value: new T.Vector2(
          (slopeR && slopeR.slopeLo != null) ? slopeR.slopeLo : 0.16,
          (slopeR && slopeR.slopeHi != null) ? slopeR.slopeHi : 0.42
        ) };
      }
      m.userData.uSlope = sh.uniforms.uSlope;
      sh.vertexShader = sh.vertexShader""",
    tag='seed uSlope from the authored layer at first compile')

sub(
    """    m.customProgramCacheKey = () => 'grimGround2' + (isRoad ? 'Road' : '');
    return m;
  }

  initTerrain(S) {""",
    """    m.customProgramCacheKey = () => 'grimGround2' + (isRoad ? 'Road' : '');
    return m;
  }

  // Live push for the slope-to-rock threshold (ground texture plan,
  // Phase 3). The value lives in a shader uniform, set once at first
  // compile above, so a later change (the World tab sliders) has to be
  // written into both ground materials directly rather than waiting for a
  // chunk rebuild, which touches geometry but never revisits a uniform.
  setSlopeRule(lo, hi) {
    if (this._chunkMat && this._chunkMat.userData.uSlope) this._chunkMat.userData.uSlope.value.set(lo, hi);
    if (this._roadMat && this._roadMat.userData.uSlope) this._roadMat.userData.uSlope.value.set(lo, hi);
  }

  initTerrain(S) {""",
    tag='add setSlopeRule() next to makeGroundMat/initTerrain')

io.open(SRC, 'w', encoding='utf-8').write(s)

# ---- 3. editor-core.js: validated fields on the layer, ships to everyone -
CORE = 'editor-core.js'
c = io.open(CORE, encoding='utf-8').read()


def csub(old, new, count=1, tag=''):
    global c, n
    f = c.count(old)
    assert f == count, 'patch 79.612 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    c = c.replace(old, new)
    n += 1


csub(
    """  function emptyLayer() {
    return {
      v: 1, gen: 0, pcell: PCELL, blend: BLEND_DEFAULT,
      paint: {}, roads: [], objects: [], removed: [],
      height: {}, spawns: [], prefabs: {}, districts: [], bookmarks: []
    };
  }""",
    """  function emptyLayer() {
    return {
      v: 1, gen: 0, pcell: PCELL, blend: BLEND_DEFAULT,
      paint: {}, roads: [], objects: [], removed: [],
      height: {}, spawns: [], prefabs: {}, districts: [], bookmarks: [],
      // Ground texture plan, Phase 3: null means "use the engine default"
      // (slope 0.16/0.42, cap 52/78m), so an old layer with neither field
      // renders exactly as it always has.
      slopeLo: null, slopeHi: null, capLo: null, capHi: null
    };
  }""",
    tag='emptyLayer: add slopeLo/slopeHi/capLo/capHi')

csub(
    """  function num(v, d) { const n = +v; return isFinite(n) ? n : d; }""",
    """  function num(v, d) { const n = +v; return isFinite(n) ? n : d; }
  // Like num(), but for the Phase 3 slope/cap overrides, where the field
  // being absent or invalid means "use the engine default", a real, distinct
  // third state, not some arbitrary fallback number.
  function clampedOrNull(v, lo, hi) {
    if (v === null || v === undefined) return null;
    const n = +v;
    if (!isFinite(n)) return null;
    return Math.max(lo, Math.min(hi, n));
  }""",
    tag='add clampedOrNull next to num()')

csub(
    """    out.pcell = PCELL;
    out.blend = Math.max(0.5, Math.min(BLEND_MAX, num(raw.blend, BLEND_DEFAULT)));
    if (raw.height && typeof raw.height === 'object') {""",
    """    out.pcell = PCELL;
    out.blend = Math.max(0.5, Math.min(BLEND_MAX, num(raw.blend, BLEND_DEFAULT)));

    // Slope-to-rock and altitude-cap tuning (ground texture plan, Phase 3).
    // A degenerate range (lo >= hi) collapses back to "use the engine
    // default" rather than being clamped into something technically valid
    // but silently wrong, such as a one-unit-wide band nobody asked for.
    out.slopeLo = clampedOrNull(raw.slopeLo, 0, 1);
    out.slopeHi = clampedOrNull(raw.slopeHi, 0, 1);
    if (out.slopeLo != null && out.slopeHi != null && out.slopeLo >= out.slopeHi) {
      out.slopeLo = out.slopeHi = null;
    }
    out.capLo = clampedOrNull(raw.capLo, -200, 500);
    out.capHi = clampedOrNull(raw.capHi, -200, 500);
    if (out.capLo != null && out.capHi != null && out.capHi <= out.capLo) {
      out.capLo = out.capHi = null;
    }

    if (raw.height && typeof raw.height === 'object') {""",
    tag='sanitize: validate slopeLo/slopeHi/capLo/capHi')

io.open(CORE, 'w', encoding='utf-8').write(c)

# ---- 4. editor-ui.js: the World tab controls, and the live uniform push --
UI = 'editor-ui.js'
u = io.open(UI, encoding='utf-8').read()


def usub(old, new, count=1, tag=''):
    global u, n
    f = u.count(old)
    assert f == count, 'patch 79.612 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    u = u.replace(old, new)
    n += 1


# rebuildWorld() already runs after every world edit; this is the one place
# to push a changed slope threshold into both ground materials' live uniform,
# so every existing call site (not only the new sliders) stays correct with
# no special-casing anywhere else. Cap needs no equivalent push: it is read
# fresh in groundSurface() for every vertex of every chunk rebuilt below.
usub(
    """    G._chunks.clear();
    G._terrAcc = 99;
    // Hand-placed resources are not streamed, so clearing chunks does not
    // remove them. Deleting the camp's oak has to take effect in the editor
    // immediately, not on the next reload.""",
    """    G._chunks.clear();
    G._terrAcc = 99;
    // Ground texture plan, Phase 3: the slope-to-rock threshold lives in a
    // shader uniform, not per-vertex data, so a slider change needs this
    // explicit push. Defaults here must match groundFragBody's fallback.
    try {
      if (G.setSlopeRule) {
        const L = GRIM_EDIT.raw;
        G.setSlopeRule((L && L.slopeLo != null) ? L.slopeLo : 0.16, (L && L.slopeHi != null) ? L.slopeHi : 0.42);
      }
    } catch (e) {}
    // Hand-placed resources are not streamed, so clearing chunks does not
    // remove them. Deleting the camp's oak has to take effect in the editor
    // immediately, not on the next reload.""",
    tag='rebuildWorld: push the live slope uniform')

# The World tab: four sliders and a reset, next to the existing layer stats.
usub(
    """      b.appendChild(info);
      row(b, 'Bookmarks');""",
    """      b.appendChild(info);
      row(b, 'Ground texture rules');
      const wL = GRIM_EDIT.raw;
      const curSloLo = (wL && wL.slopeLo != null) ? wL.slopeLo : 0.16;
      const curSloHi = (wL && wL.slopeHi != null) ? wL.slopeHi : 0.42;
      const curCapLo = (wL && wL.capLo != null) ? wL.capLo : 52;
      const curCapHi = (wL && wL.capHi != null) ? wL.capHi : 78;
      b.appendChild(el('div', 'color:#8f8f8f;font-size:10px;margin-bottom:2px',
        'Steep ground shows rock below the first slope number and is fully rock past the second, no ' +
        'painting needed. Ground above the first height starts showing the cap surface (snow, scree, ' +
        'whatever that zone uses) and is fully capped past the second.'));
      slider(b, 'rock starts, slope 0-1', 0, 1, 0.01, curSloLo, v => {
        const L = GRIM_EDIT.raw; if (!L) return;
        L.slopeLo = v; S.dirty = true; GRIM_EDIT.reindex(); rebuildWorld();
      });
      slider(b, 'rock full, slope 0-1', 0, 1, 0.01, curSloHi, v => {
        const L = GRIM_EDIT.raw; if (!L) return;
        L.slopeHi = v; S.dirty = true; GRIM_EDIT.reindex(); rebuildWorld();
      });
      slider(b, 'cap starts, metres', -50, 300, 1, curCapLo, v => {
        const L = GRIM_EDIT.raw; if (!L) return;
        L.capLo = v; S.dirty = true; GRIM_EDIT.reindex(); rebuildWorld();
      });
      slider(b, 'cap full, metres', -50, 300, 1, curCapHi, v => {
        const L = GRIM_EDIT.raw; if (!L) return;
        L.capHi = v; S.dirty = true; GRIM_EDIT.reindex(); rebuildWorld();
      });
      const rstBtn = el('button', BTN, 'Reset to engine defaults');
      rstBtn.onclick = () => {
        const L = GRIM_EDIT.raw; if (!L) return;
        pushUndo();
        L.slopeLo = L.slopeHi = L.capLo = L.capHi = null;
        S.dirty = true; GRIM_EDIT.reindex(); rebuildWorld(); paintPanel();
      };
      b.appendChild(rstBtn);
      row(b, 'Bookmarks');""",
    tag='World tab: slope/cap sliders and reset')

io.open(UI, 'w', encoding='utf-8').write(u)

print('79.612_slope_altitude_autotexture: %d edits applied' % n)
