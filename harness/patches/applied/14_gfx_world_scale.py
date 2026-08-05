#!/usr/bin/env python3
"""GRAPHICS: LOW thins the world too, not just the shadows.

The roster and the ground cover were both being held down by a mesh budget that
does not measure anything the renderer charges for. Content should not be thin
for everyone because some machines are slower than others, so the graphics
setting becomes the lever: it already drops shadows and extra lights, and now it
also drops ground cover density and the dressed radius.

That is the honest place to give ground. It costs a struggling machine scenery,
not monsters, not reach, not anything a player has to fight with.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# Density and dressed radius both read the graphics setting.
sub(
    "    const G = GRIM_RULES.GATHER;\n"
    "    const rnd = grimRnd(grimSeed(cx, cz, 'dress'));\n"
    "    const clutter = [], nodes = [];\n"
    "    const cN = G.CLUTTER_PER_CHUNK[0] + Math.floor(rnd() * (G.CLUTTER_PER_CHUNK[1] - G.CLUTTER_PER_CHUNK[0] + 1));",

    "    const G = GRIM_RULES.GATHER;\n"
    "    const rnd = grimRnd(grimSeed(cx, cz, 'dress'));\n"
    "    const clutter = [], nodes = [];\n"
    "    // The seeded stream is drawn from identically at every graphics setting,\n"
    "    // and the count is trimmed afterwards. Rolling a different NUMBER of\n"
    "    // values would give two players on different settings different worlds.\n"
    "    const gs = (GRIM_RULES.GFX_SCALE || {})[this.gfx === 'high' ? 'high' : 'low'] || { clutter: 1 };\n"
    "    const cFull = G.CLUTTER_PER_CHUNK[0] + Math.floor(rnd() * (G.CLUTTER_PER_CHUNK[1] - G.CLUTTER_PER_CHUNK[0] + 1));\n"
    "    const cN = Math.max(6, Math.round(cFull * (gs.clutter || 1)));",
    'density scale')

sub(
    "    const DETAIL = 3, COARSE = 7, DRESS = 2;",
    "    const DETAIL = 3, COARSE = 7;\n"
    "    const _gs = (GRIM_RULES.GFX_SCALE || {})[this.gfx === 'high' ? 'high' : 'low'] || {};\n"
    "    const DRESS = _gs.dressRing != null ? _gs.dressRing : 2;",
    'dress ring scale')

# Changing the setting has to redress what is already loaded, or the world stays
# at whatever density it happened to be built at.
sub(
    "  togglePerfHud() {",
    "  // Re-dress everything loaded. Called when the graphics setting changes,\n"
    "  // since density and dressed radius both key off it.\n"
    "  redressWorld() {\n"
    "    if (!this._chunks) return;\n"
    "    for (const [, rec] of this._chunks) if (rec.dressed) this.dressDrop(rec);\n"
    "    this._terrAcc = 99;\n"
    "  }\n"
    "\n"
    "  togglePerfHud() {",
    'redress helper')

# Changing the setting has to take effect immediately.
sub(
    "  applyGfx() {\n"
    "    const low = this.gfx === 'low';",
    "  applyGfx() {\n"
    "    const low = this.gfx === 'low';\n"
    "    // ground cover density and the dressed radius both key off the setting,\n"
    "    // so what is already built has to be rebuilt at the new one\n"
    "    if (this._gfxWas !== undefined && this._gfxWas !== this.gfx) this.redressWorld();\n"
    "    this._gfxWas = this.gfx;",
    'applyGfx redress')

# The node loop must NOT share the clutter loop's random stream. Clutter is
# drawn until the count is reached, so scaling the count changes how many values
# are consumed, which would shift every node position after it. Clutter is
# decorative and may differ between graphics settings; nodes are harvestables
# that sync by id and must be identical on every machine, forever.
sub(
    "    for (let i = 0; i < nN; i++) {\n"
    "      const x = x0 + 4 + rnd() * (CH - 8), z = z0 + 4 + rnd() * (CH - 8);\n"
    "      const rot = rnd() * Math.PI * 2, roll = rnd(), sc = 0.9 + rnd() * 0.35;",

    "    // Its own stream, on its own salt. Nodes cannot be allowed to move\n"
    "    // because someone turned the grass down.\n"
    "    const rndN = grimRnd(grimSeed(cx, cz, 'nodes'));\n"
    "    for (let i = 0; i < nN; i++) {\n"
    "      const x = x0 + 4 + rndN() * (CH - 8), z = z0 + 4 + rndN() * (CH - 8);\n"
    "      const rot = rndN() * Math.PI * 2, roll = rndN(), sc = 0.9 + rndN() * 0.35;",
    'node stream')

# nN is drawn before any clutter is placed, so it is already stable, but it is
# moved onto the node stream too so the whole node list depends on nothing but
# the chunk.
sub(
    "    const nN = G.NODES_PER_CHUNK[0] + Math.floor(rnd() * (G.NODES_PER_CHUNK[1] - G.NODES_PER_CHUNK[0] + 1));",
    "    const nN = G.NODES_PER_CHUNK[0] + Math.floor(grimRnd(grimSeed(cx, cz, 'nodecount'))() * (G.NODES_PER_CHUNK[1] - G.NODES_PER_CHUNK[0] + 1));",
    'node count stream')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
