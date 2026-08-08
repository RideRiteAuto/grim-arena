#!/usr/bin/env python3
"""Patch 79.083: anti-alias the ground dither, and fix the road-deletion gap.

Kevin's report after patch 77 (dithered ground blending): a "grid static"
pattern over large areas, worst at a grazing angle, plus rough/jagged
transitions, plus a persistent speckled line he could not paint or erase
away. Full research plan approved by Kevin: claude/GROUND-TEXTURE-BRUSH-PLAN.md
in the project docs.

ROOT CAUSE, confirmed by diffing patch 77's shader change: ditherMix() is a
raw fract(sin(...)) hash with NO anti-aliasing at all. Its period is about
0.25m (h21(w * 4.0)), so at any real viewing distance or shallow angle one
screen pixel spans many dither cycles, which is textbook aliasing into a
moire/static grid. This bundle already knows this failure mode and already
fixed it once, one layer down: buildGroundArray()'s ground textures are a
DataArrayTexture with generateMipmaps + LinearMipmapLinearFilter + 8x
anisotropy specifically because an earlier flat-atlas version of this exact
system aliased into "a world-sized sheet of uniform orange" at a grazing
angle (see that function's own comment). ditherMix reintroduces the same bug
one layer up, in the surface PICK rather than the texture SAMPLE, where none
of that mipmapping helps it.

It also explains why the static was worst over rippled/furrowed ground
(ploughed fields, low-poly terrain noise): groundFragBody()'s slope-to-rock
blend (rw, computed from the live vertex normal) flickers across every small
ridge on bumpy terrain, so the SAME unfiltered dither fires constantly across
open ground that was never near a paint boundary at all, not only at
paint-to-paint edges.

FIX: fade the dithered pick into the plain smooth mix() as a function of
fwidth(t), the screen-space rate of change of the blend weight. That rate is
small up close, where triangles are large on screen and full per-fragment
dithered detail is genuinely resolvable, and grows automatically with
distance or grazing angle, exactly where the dither can no longer be resolved
and the old smooth blend was already fine. At full fade (aa=1) the result is
byte-for-byte the pre-patch-77 mix(a, b, t), so distant ground is guaranteed
no worse than it used to be. This touches only ditherMix()'s body; h21() and
every call site (the base pair, the slope-to-rock swap, the treeline swap)
are unchanged, so all three benefit without three separate edits.

Also fixes the reported "stuck old texture I can't clear": roads live in
their own list (L.roads), never touched by the paint eraser (which only
edits L.paint), and the Road panel could only ever remove the MOST RECENT
road ("Remove last road"). Any older road was permanently stuck. This patch
gives roads real click-to-select-and-delete through the Select tool, the
same interaction already used for placed objects. That part is a direct
edit to editor-ui.js (not the extracted bundle), since the editor files are
resynced whole on every build.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 79.083 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. anti-alias ditherMix by fading into the old smooth mix() ----------
sub(
    """          'float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
          'vec3 ditherMix(vec3 a, vec3 b, float t, vec2 w) {',
          '  return h21(w * 4.0) < t ? b : a;',
          '}'
        ].join('\\n'))""",
    """          'float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
          // Patch 79.083: the raw hash above has no anti-aliasing, so at any
          // real distance or grazing angle one screen pixel spans many
          // dither cycles and it aliases into a static/moire grid -- the
          // exact failure groundSurf()'s mipmapped texture array already
          // exists to avoid, reintroduced here one layer up. fwidth(t) is
          // how fast the blend weight changes from this pixel to its screen
          // neighbour: small up close (full dithered detail, triangles are
          // big on screen), large at distance or a shallow angle (fades
          // smoothly back to the old plain mix(), which cannot alias).
          // aaScale is how fast that fade happens; retune here if a wider or
          // narrower crisp-detail range is wanted.
          'vec3 ditherMix(vec3 a, vec3 b, float t, vec2 w) {',
          '  float n = h21(w * 4.0) - 0.5;',
          '  float aaScale = 40.0;',
          '  float aa = clamp(fwidth(t) * aaScale, 0.0, 1.0);',
          '  float hardPick = step(0.5, t + n * 0.92);',
          '  float e = mix(hardPick, t, aa);',
          '  return mix(a, b, e);',
          '}'
        ].join('\\n'))""",
    tag='anti-alias ditherMix with a distance-faded smooth fallback')

io.open(SRC, 'w', encoding='utf-8').write(s)

# ---- 2. give roads real click-select-and-delete (editor-ui.js direct) -----
UI = 'editor-ui.js'
u = io.open(UI, encoding='utf-8').read()


def usub(old, new, count=1, tag=''):
    global u, n
    f = u.count(old)
    assert f == count, 'patch 79.083 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    u = u.replace(old, new)
    n += 1


# pickObject() currently only searches authored objects and world/generated
# nodes. Give it a third result type, 'road', found by nearest-point-on-
# segment distance to any authored road, using the SAME resampled curve
# GRIM_EDIT already builds internally (re-smoothed here since the runtime
# index does not expose per-road segment ownership, only a flat list).
usub(
    "  function pickObject(pt) {",
    """  // Nearest authored road to a point, or null. Re-smooths each road with
  // GRIM_EDIT.smooth (the same Catmull-Rom the runtime index uses) so the
  // hit-test follows the curve actually drawn, not the raw waypoints.
  function pickRoad(pt, maxD) {
    const L = GRIM_EDIT.raw;
    if (!L || !L.roads.length) return null;
    let best = null, bestD = Infinity;
    for (let ri = 0; ri < L.roads.length; ri++) {
      const r = L.roads[ri];
      const pts = GRIM_EDIT.smooth(r.p);
      for (let i = 0; i < pts.length - 1; i++) {
        const ax = pts[i + 1][0] - pts[i][0], az = pts[i + 1][1] - pts[i][1];
        const len2 = ax * ax + az * az;
        let t = len2 ? ((pt.x - pts[i][0]) * ax + (pt.z - pts[i][1]) * az) / len2 : 0;
        t = t < 0 ? 0 : t > 1 ? 1 : t;
        const px = pts[i][0] + ax * t - pt.x, pz = pts[i][1] + az * t - pt.z;
        const d = Math.hypot(px, pz);
        if (d < bestD) { bestD = d; best = ri; }
      }
    }
    if (best === null) return null;
    const tol = maxD || (L.roads[best].w / 2 + 6);
    if (bestD > tol) return null;
    return { type: 'road', index: best, road: L.roads[best], d: bestD };
  }

  function pickObject(pt) {""",
    tag='add pickRoad() ahead of pickObject()')

# The select tool's click path: try a road first if the Road panel is not
# the active tool context, matching the existing priority (authored objects
# win over generated ones within their own radius); a road is authored too,
# so it goes through the same pickRoad-then-pickObject chain.
usub(
    """      S.sel = pickObject(pt);
      S.selMoved = false;""",
    """      S.sel = pickRoad(pt) || pickObject(pt);
      S.selMoved = false;""",
    tag='select tool tries a road before falling back to pickObject')

# Selection panel: a road has no single position to drag, but it does have a
# real delete. This is additive alongside the existing 'world' and
# 'authored' branches in paintPanel(), keyed on the new type.
usub(
    """    } else if (S.tool === 'select') {
      row(b, 'Selection');
      if (!S.sel) {""",
    """    } else if (S.tool === 'select') {
      row(b, 'Selection');
      if (S.sel && S.sel.type === 'road') {
        const r = S.sel.road;
        b.appendChild(el('div', 'color:#ededed;font-size:12px;font-weight:700',
          'Road, ' + r.p.length + ' waypoint' + (r.p.length === 1 ? '' : 's')));
        b.appendChild(el('div', 'color:#8f8f8f;font-size:10px',
          'width ' + r.w + 'm  ·  surface ' + r.s + ' ' + (SURF_NAMES[r.s] || '')));
        b.appendChild(el('div', 'color:#8f8f8f;font-size:10px;margin-top:4px',
          'Click near any point along this road to select it, from anywhere ' +
          'in its waypoint list, not only the most recently drawn road.'));
        slider(b, 'width, metres', 2, 40, 1, r.w, v => { r.w = v; GRIM_EDIT.reindex(); rebuildWorld(); });
        const del = el('button', BTN.replace('#ededed', '#e0574f'), 'Delete this road');
        del.onclick = () => {
          pushUndo();
          GRIM_EDIT.raw.roads.splice(S.sel.index, 1);
          S.sel = null; GRIM_EDIT.reindex(); rebuildWorld(); paintPanel();
          say('road deleted');
        };
        b.appendChild(del);
      } else if (!S.sel) {""",
    tag='road branch in the selection panel')

io.open(UI, 'w', encoding='utf-8').write(u)

print('79.083_ground_dither_antialiasing: %d edits applied' % n)
