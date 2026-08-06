#!/usr/bin/env python3
"""Phase 1c: frames of reference, structure only. Zero behaviour change.

A cargo pack set on a boat deck has to stay on the deck while the boat
sails. That needs a concept the game does not have: a position expressed
relative to a moving thing. This patch adds the STRUCTURE for that and
nothing else. The world is the only frame that exists, everything defaults
to it, and every value in the game is byte-identical to before.

What ships here, per the spec's 1c:
  - A frame registry on the game (this._frames) and two conversion helpers,
    frameToWorld / worldToFrame, which are the identity for the world frame.
    Vehicles register real frames in phase 9; the helpers make that phase
    additive instead of a rewrite.
  - The player state message gains `fr: 0`, the sender's frame id. Old
    clients ignore unknown fields, new clients store it (r.fr) exactly the
    way the transmitted height r.ty is already stored: read by nothing yet,
    read by phase 9.
  - The surfaces query accepts an optional frame argument, ignored while
    the world is the only frame.

Not here, deliberately: saves gaining height and a frame is a 1e item
(their validator must be fixed in the same change), and item/sack messages
gain their fields when set-down-on-deck exists to use them (phase 9/12).
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# 1. The frame registry and converters, appended inside the VERTICAL fence
#    right after ceilingY so the whole vertical API reads as one block.
sub(
    "  ceilingY(x, z) {\n    return Infinity;\n  }\n  /* VERTICAL-END */",

    "  ceilingY(x, z) {\n    return Infinity;\n  }\n"
    "  // Phase 1c: frames of reference, structure only. A frame is a moving\n"
    "  // origin a position can be expressed inside: a boat deck, a cart bed,\n"
    "  // one day a lift. Frame 0 is the world and is the only frame that\n"
    "  // exists today, so both converters are the identity and every caller\n"
    "  // behaves exactly as before. Phase 9 registers real vehicle frames\n"
    "  // here ({ id: { x, y, z, yaw } }), and these two functions become the\n"
    "  // one place attach/detach maths lives.\n"
    "  frameToWorld(fr, out) {\n"
    "    if (!fr) return out;                       // world frame: identity\n"
    "    const F = this._frames && this._frames[fr];\n"
    "    if (!F) return out;                        // unknown frame: treat as world\n"
    "    const c = Math.cos(F.yaw || 0), s = Math.sin(F.yaw || 0);\n"
    "    const lx = out.x, lz = out.z;\n"
    "    out.x = F.x + lx * c + lz * s;\n"
    "    out.z = F.z - lx * s + lz * c;\n"
    "    out.y = (out.y || 0) + (F.y || 0);\n"
    "    return out;\n"
    "  }\n"
    "  worldToFrame(fr, out) {\n"
    "    if (!fr) return out;\n"
    "    const F = this._frames && this._frames[fr];\n"
    "    if (!F) return out;\n"
    "    const c = Math.cos(F.yaw || 0), s = Math.sin(F.yaw || 0);\n"
    "    const dx = out.x - F.x, dz = out.z - F.z;\n"
    "    out.x = dx * c - dz * s;\n"
    "    out.z = dx * s + dz * c;\n"
    "    out.y = (out.y || 0) - (F.y || 0);\n"
    "    return out;\n"
    "  }\n"
    "  /* VERTICAL-END */",
    "frame registry and converters")

# 2. The player state message carries the sender's frame id. 0 = world.
#    Old clients ignore unknown fields; this is the wire growing the field
#    early so phase 9 does not need a lockstep deploy.
sub(
    "return { n: this.myName, c: this.myColorIdx, p: [+me.pos.x.toFixed(2), +this.worldY(me, gy).toFixed(2), +me.pos.z.toFixed(2)],",
    "return { n: this.myName, c: this.myColorIdx, fr: (me.frame | 0), p: [+me.pos.x.toFixed(2), +this.worldY(me, gy).toFixed(2), +me.pos.z.toFixed(2)],",
    "myWorldState frame id")

# 3. Remotes store the sender's frame exactly the way they already store the
#    transmitted height: read by nothing until phase 9.
sub(
    "r.s = s; r.name = s.n || 'PLAYER'; r.tx = s.p[0]; r.ty = s.p[1]; r.tz = s.p[2];",
    "r.s = s; r.name = s.n || 'PLAYER'; r.fr = s.fr | 0; r.tx = s.p[0]; r.ty = s.p[1]; r.tz = s.p[2];",
    "updateRemote frame store")

# 4. The surfaces query accepts a frame. While the world is the only frame
#    the argument is ignored, which is the whole point of shipping the
#    signature before the behaviour.
sub(
    "  surfaceY(x, z) {\n    let P = this._surfaces;",
    "  surfaceY(x, z, fr) {\n    // fr: optional frame id. World-frame only today, so it is accepted\n    // and ignored; phase 9 consults the frame's own deck provider first.\n    let P = this._surfaces;",
    "surfaceY frame arg")

for old, new, label in edits:
    assert src.count(old) == 1, 'anchor %s went stale' % label
    src = src.replace(old, new)

io.open(SRC, 'w', encoding='utf-8').write(src)
print('patched %d anchors -> %s' % (len(edits), SRC))
