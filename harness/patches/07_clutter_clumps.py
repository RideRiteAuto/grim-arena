#!/usr/bin/env python3
"""Phase 2, part 2: clutter grows in clumps, not one prop at a time.

Scattering fourteen to twenty two props uniformly across a 64m chunk puts one
prop every twelve metres, and a single stalk of wheat standing alone in a field
reads as a traffic cone rather than as a field. Nature clumps: grass grows in
patches, stones collect in drifts, ferns cluster in shade.

Same prop budget, same determinism, same one merged mesh per chunk. The only
change is that the props arrive in small groups around a handful of sites,
which is what makes ground read as ground.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# Wheat and reeds were authored at full height and then placed at whatever scale
# the site rolled, so a single stalk stood over a metre tall. They are grass:
# they belong at ankle height and in numbers.
sub(
    "      wheat:   nonIdx(new T.ConeGeometry(0.13, 1.05, 3)),\n"
    "      reed:    nonIdx(new T.ConeGeometry(0.07, 1.35, 3)),",
    "      wheat:   nonIdx(new T.ConeGeometry(0.09, 0.62, 3)),\n"
    "      reed:    nonIdx(new T.ConeGeometry(0.055, 0.95, 3)),",
    'grass size')

sub(
    "      tuft: [0.24, 0], bush: [0.30, 0], wheat: [0.48, 0], reed: [0.62, 0],",
    "      tuft: [0.24, 0], bush: [0.30, 0], wheat: [0.29, 0], reed: [0.45, 0],",
    'grass sit')

# How many props a clump of each type wants, and how tight it sits. A boulder is
# a boulder; wheat is never one stalk.
sub(
    "  // Colour for a clutter type. Types that exist in more than one zone read",
    "  // How a clutter type clumps: [min count, max count, radius in metres].\n"
    "  // The prop budget per chunk does not change, so a type that clumps hard\n"
    "  // simply occupies fewer sites.\n"
    "  CLUTTER_CLUMP(type) {\n"
    "    const C = {\n"
    "      wheat: [4, 7, 1.9], reed: [4, 7, 1.6], flower: [3, 6, 1.7], tuft: [3, 5, 1.6],\n"
    "      fern: [2, 4, 1.6], pebble: [2, 5, 1.5], shell: [2, 4, 1.3], ash: [2, 4, 2.1],\n"
    "      shard: [2, 4, 1.5], drift: [2, 3, 2.0], bone: [1, 3, 1.4], stick: [1, 3, 1.5],\n"
    "      bush: [1, 2, 1.8], boulder: [1, 2, 2.2], log: [1, 1, 0], hay: [1, 3, 2.4]\n"
    "    };\n"
    "    return C[type] || [1, 2, 1.4];\n"
    "  }\n"
    "\n"
    "  // Colour for a clutter type. Types that exist in more than one zone read",
    'clump table')

# The generator: pick a site, roll a type, then grow a clump on it. Every value
# still comes off the chunk's own seeded stream, so this is as deterministic as
# the one-prop-per-site version it replaces.
sub(
    "    for (let i = 0; i < cN; i++) {\n"
    "      const x = x0 + rnd() * CH, z = z0 + rnd() * CH;\n"
    "      const rot = rnd() * Math.PI * 2, sc = 0.7 + rnd() * 0.8, pick = rnd();\n"
    "      if (this.dressBlocked(x, z)) continue;\n"
    "      const bake = GRIM_WORLD.zone(x, z);\n"
    "      const zone = grimZoneName(bake);\n"
    "      if (zone === 'SEA') continue;\n",

    "    let guard = 0;\n"
    "    while (clutter.length < cN && guard++ < 200) {\n"
    "      const x = x0 + rnd() * CH, z = z0 + rnd() * CH;\n"
    "      const rot = rnd() * Math.PI * 2, sc = 0.7 + rnd() * 0.8, pick = rnd();\n"
    "      const spread = rnd(), count = rnd();\n"
    "      if (this.dressBlocked(x, z)) continue;\n"
    "      const bake = GRIM_WORLD.zone(x, z);\n"
    "      const zone = grimZoneName(bake);\n"
    "      if (zone === 'SEA') continue;\n",
    'clutter loop head')

sub(
    "      clutter.push({ type: type, zone: zone, x: x, z: z, y: GRIM_WORLD.height(x, z), rot: rot, sc: sc });\n"
    "    }",

    "      // grow the clump outward from the site, dropping any member that\n"
    "      // lands somewhere a prop is not allowed to be\n"
    "      const cl = this.CLUTTER_CLUMP(type);\n"
    "      const n = cl[0] + Math.floor(count * (cl[1] - cl[0] + 1));\n"
    "      for (let j = 0; j < n && clutter.length < cN; j++) {\n"
    "        const a = (j * 2.39996 + spread * 6.283);        // golden angle, so a\n"
    "        const r = cl[2] * Math.sqrt((j + 0.35) / n);     // clump fills evenly\n"
    "        const px = x + Math.cos(a) * r, pz = z + Math.sin(a) * r;\n"
    "        // every member is checked, including the first: it sits offset from\n"
    "        // the site, so the site passing does not mean the member does\n"
    "        if (this.dressBlocked(px, pz)) continue;\n"
    "        clutter.push({\n"
    "          type: type, zone: zone, x: px, z: pz, y: GRIM_WORLD.height(px, pz),\n"
    "          rot: rot + j * 1.7, sc: sc * (0.78 + ((j * 37) % 11) / 24)\n"
    "        });\n"
    "      }\n"
    "    }",
    'clutter clump emit')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
