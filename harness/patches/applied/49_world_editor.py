#!/usr/bin/env python3
"""Phase 3 to 6: the world editor, wired into the game.

This patch is deliberately SMALL. All of the editor is in editor-core.js,
editor-tools.js and editor-ui.js, injected between the EDITOR markers by
repack.py exactly the way shared-rules.js and worldgen.js are. So what lands
in the bundle here is only the markers plus seven hooks, each one line or two,
each at a seam the engine already had:

  1. the EDITOR markers, right after the world generator
  2. boot: fetch the edit layer, register the terrain delta, then boot as usual
  3. boot: enter the editor if ?edit=1 asked for it
  4. tick: the editor's own frame replaces the game's, and nothing else
  5. surfaceY: authored decks become walkable, between bridges and terrain
  6. groundSurface: authored paint and roads rewrite the ground result
  7. keepGround: authored ground suppresses procedural clutter
  8. dressChunk: skip deleted procedural props, attach authored objects
  9. dressDrop: release authored objects with the chunk

With GRIM_RULES.EDIT.LAYER off, or with an empty layer, every one of these is
a single boolean test that falls through to exactly the old behaviour. That is
the property the whole patch is built around: a player who is not looking at
authored content runs the game that shipped yesterday.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()

def sub(old, new, what):
    global s
    n = s.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (what, n)
    s = s.replace(old, new, 1)

# --- 1. the markers ---------------------------------------------------------
sub(
    '/* WORLD-GEN-END */',
    '/* WORLD-GEN-END */\n\n'
    '/* EDITOR-BEGIN */\n'
    '/* injected from editor-core.js, editor-tools.js and editor-ui.js by\n'
    '   repack.py. Never edit this copy. */\n'
    '/* EDITOR-END */',
    'world-gen-end')

# --- 2 and 3. boot ----------------------------------------------------------
# The edit layer NEVER blocks boot. The first version of this awaited the
# fetch before calling boot(), which is wrong twice over: it puts a network
# round trip in front of every player's first frame, and it broke savecurve.js
# because the game had not booted by the time the harness reached it. The
# generated world is complete and playable on its own, so it is shown at once
# and the authored layer paints itself in the moment it lands.
#
# Chunks built before the layer arrives carry the generated ground baked into
# their vertex attributes, so they are dropped and rebuilt once. On a normal
# connection the fetch beats the world decode and nothing is ever rebuilt.
sub(
    "const start = () => { if (this.alive) GRIM_WORLD.init().then(() => { if (this.alive) this.boot(); }); };",
    "const start = () => {\n"
    "      if (!this.alive) return;\n"
    "      const layer = GRIM_EDIT.load();\n"
    "      GRIM_WORLD.init().then(() => {\n"
    "        if (!this.alive) return;\n"
    "        // The terrain hook is registered by GRIM_EDIT's own indexing, so\n"
    "        // there is exactly one place it can be wrong, and it stays right\n"
    "        // when the editor changes the layer at runtime.\n"
    "        this.boot();\n"
    "        layer.then(() => {\n"
    "          if (!this.alive) return;\n"
    "          try {\n"
    "            if (GRIM_EDIT.on && this._chunks && this._chunks.size) GRIM_EDIT_RENDER.refresh(this);\n"
    "          } catch (e) {}\n"
    "          try { if (GRIM_EDIT_UI.wanted()) GRIM_EDIT_UI.enter(this); } catch (e) { console.error('editor', e); }\n"
    "        });\n"
    "      });\n"
    "    };",
    'start-fn')

# GRIM_EDIT and friends are module-scoped inside the bundle, exactly like
# GRIM_RULES and GRIM_WORLD, so a harness cannot reach them. The game already
# has the accessor pattern for precisely this: WORLD() and RULES() sit side by
# side returning the two singletons. The editor's four follow it.
#
# The first version of this assigned them as FIELDS in componentDidMount,
# including `this.WORLD = GRIM_WORLD`, which silently overwrote the existing
# WORLD() METHOD and broke harness/dressing.js with "g.WORLD is not a
# function". Matching the established pattern instead of inventing a second
# one is what avoids that entirely.
sub(
    "  WORLD() { return GRIM_WORLD; }\n"
    "  RULES() { return GRIM_RULES; }",
    "  WORLD() { return GRIM_WORLD; }\n"
    "  RULES() { return GRIM_RULES; }\n"
    "  EDIT() { return GRIM_EDIT; }\n"
    "  EDIT_UI() { return GRIM_EDIT_UI; }\n"
    "  EDIT_CAT() { return GRIM_EDIT_CATALOG; }\n"
    "  EDIT_RENDER() { return GRIM_EDIT_RENDER; }",
    'singleton-accessors')

# The layer fetch is kicked off as early as the page can manage: at mount,
# rather than waiting for three.js to arrive. On a cold load that is most of a
# second of overlap for free.
sub(
    "    try { this.buildLoginUi(); } catch (e) {}",
    "    try { this.buildLoginUi(); } catch (e) {}\n"
    "    try { GRIM_EDIT.load(); } catch (e) {}",
    'early-layer-fetch')

# --- 4. the tick fork -------------------------------------------------------
sub(
    "  tick(dt) {\n    this._lastTickAt = performance.now();",
    "  tick(dt) {\n"
    "    this._lastTickAt = performance.now();\n"
    "    /* EDITOR: the free camera replaces the player's frame entirely. This\n"
    "       is the only hook the editor needs in the game loop, which is why\n"
    "       the editor cannot affect a player: editorOn is never set for one. */\n"
    "    if (this.editorOn) { GRIM_EDIT_UI.tick(dt); return; }",
    'tick')

# --- 5. authored decks are walkable ----------------------------------------
# Between bridges and terrain, so a bridge still wins over a platform built on
# top of one, and terrain still answers everywhere else.
sub(
    "        (sx, sz) => this.bridgeDeckY(sx, sz),\n"
    "        (sx, sz) => GRIM_WORLD.height(sx, sz),",
    "        (sx, sz) => this.bridgeDeckY(sx, sz),\n"
    "        (sx, sz) => GRIM_EDIT.deckY(sx, sz),\n"
    "        (sx, sz) => GRIM_WORLD.height(sx, sz),",
    'surfaces')

# --- 6. authored ground ----------------------------------------------------
sub(
    "    out[6] = Math.max(0, Math.min(1, (h - 52) / 26));\n  }",
    "    out[6] = Math.max(0, Math.min(1, (h - 52) / 26));\n"
    "\n"
    "    // Authored paint and roads have the last word: they ride the same\n"
    "    // A-to-B blend the bridge pads use, so the join is the ground's own\n"
    "    // feather and costs nothing extra to draw.\n"
    "    GRIM_EDIT.paint(wx, wz, out);\n"
    "  }",
    'groundsurf-end')

# --- 7. authored ground clears clutter -------------------------------------
sub(
    "    if (Math.abs(dx) < 7.5 && dz > 20 && dz < 62) return true;\n"
    "    return false;\n"
    "  }",
    "    if (Math.abs(dx) < 7.5 && dz > 20 && dz < 62) return true;\n"
    "    if (GRIM_EDIT.clears(x, z)) return true;\n"
    "    return false;\n"
    "  }",
    'keepground')

# --- 8. deleted procedural props -------------------------------------------
# A procedural tree is not in the layer, it is grown from the world seed, so
# deleting one is recorded as its stable node id and skipped here on every
# machine. Same test for clutter, which has no ids and is cleared by footprint.
sub(
    "    for (const p of props.nodes) {\n"
    "      const nd = GRIM_RULES.GATHER.NODES[p.kind];\n"
    "      if (!nd) continue;\n"
    "      if (this.keepGround(p.x, p.z)) continue;",
    "    for (const p of props.nodes) {\n"
    "      const nd = GRIM_RULES.GATHER.NODES[p.kind];\n"
    "      if (!nd) continue;\n"
    "      if (this.keepGround(p.x, p.z)) continue;\n"
    "      if (GRIM_EDIT.gone(p.nid)) continue;",
    'nodes-loop')

# --- 9. authored objects stream with the chunk -----------------------------
sub(
    "      if (this._frozeStatic) { built.g.updateMatrix(); built.g.matrixAutoUpdate = false; }\n"
    "    }\n"
    "  }\n"
    "\n"
    "  NODE_TINT(kind) {",
    "      if (this._frozeStatic) { built.g.updateMatrix(); built.g.matrixAutoUpdate = false; }\n"
    "    }\n"
    "    // Objects Kevin placed, streamed and disposed exactly like the\n"
    "    // procedural ones so they cost the same and leak the same, which is\n"
    "    // to say not at all.\n"
    "    try { GRIM_EDIT_RENDER.dress(this, rec); } catch (e) {}\n"
    "  }\n"
    "\n"
    "  NODE_TINT(kind) {",
    'dresschunk-end')

sub(
    "  dressDrop(rec) {\n    rec.dressed = false;",
    "  dressDrop(rec) {\n"
    "    rec.dressed = false;\n"
    "    try { GRIM_EDIT_RENDER.drop(this, rec); } catch (e) {}",
    'dressdrop')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('35_world_editor: 9 anchors applied')
