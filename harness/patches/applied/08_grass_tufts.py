#!/usr/bin/env python3
"""Phase 2, part 3: grass templates are tufts, not single blades.

A three sided cone seen from the side is a flat triangle, so one cone per prop
gave fields of little gold shards standing on end rather than grass. Each grass
type is now a small merged cluster of leaning blades, built once at init, so a
single prop reads as a tuft with volume and the per-chunk merge is unchanged:
still one draw call for the whole chunk's ground cover.
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
    "      wheat:   nonIdx(new T.ConeGeometry(0.09, 0.62, 3)),\n"
    "      reed:    nonIdx(new T.ConeGeometry(0.055, 0.95, 3)),\n"
    "      fern:    nonIdx(new T.ConeGeometry(0.42, 0.34, 5)),",

    "      wheat:   this.bladeTuft(5, 0.075, 0.62, 0.30, 11),\n"
    "      reed:    this.bladeTuft(5, 0.05, 1.00, 0.16, 23),\n"
    "      tallgrass: this.bladeTuft(6, 0.07, 0.44, 0.42, 37),\n"
    "      fern:    this.bladeTuft(6, 0.16, 0.30, 1.15, 41),",
    'grass templates')

sub(
    "      tuft:    nonIdx(new T.ConeGeometry(0.2, 0.55, 4)),",
    "      tuft:    this.bladeTuft(5, 0.10, 0.42, 0.46, 7),",
    'tuft template')

# The tuft builder. Blades lean outward on the golden angle so no two sit in the
# same plane, which is what stops a tuft reading as one flat triangle.
sub(
    "  dressInit() {\n"
    "    if (this._dressReady) return;\n"
    "    const T = this.T;",

    "  // A merged cluster of leaning blades. n blades, each a thin cone, splayed\n"
    "  // on the golden angle and tipped outward by `lean` radians. Returned as one\n"
    "  // non-indexed geometry so it drops straight into the per-chunk merge.\n"
    "  bladeTuft(n, w, h, lean, seed) {\n"
    "    const T = this.T;\n"
    "    const rnd = grimRnd(grimSeed(seed, seed * 7, 'tuft'));\n"
    "    const parts = [];\n"
    "    for (let i = 0; i < n; i++) {\n"
    "      const a = i * 2.39996 + rnd() * 0.4;\n"
    "      const hh = h * (0.68 + rnd() * 0.6);\n"
    "      const geo = new T.ConeGeometry(w * (0.75 + rnd() * 0.5), hh, 3);\n"
    "      const m = new T.Matrix4();\n"
    "      const q = new T.Quaternion().setFromEuler(new T.Euler(Math.cos(a) * lean, a, Math.sin(a) * lean));\n"
    "      m.compose(new T.Vector3(Math.cos(a) * w * 1.5, hh * 0.42, Math.sin(a) * w * 1.5),\n"
    "                q, new T.Vector3(1, 1, 1));\n"
    "      parts.push({ geo: geo.index ? geo.toNonIndexed() : geo, m: m });\n"
    "    }\n"
    "    return this.mergeGeos(parts);\n"
    "  }\n"
    "\n"
    "  dressInit() {\n"
    "    if (this._dressReady) return;\n"
    "    const T = this.T;",
    'blade tuft builder')

# The tuft geometries are now built around their own base, so they no longer
# need lifting off the ground by half their height.
sub(
    "      tuft: [0.24, 0], bush: [0.30, 0], wheat: [0.29, 0], reed: [0.45, 0],",
    "      tuft: [0.02, 0], bush: [0.30, 0], wheat: [0.02, 0], reed: [0.02, 0],\n"
    "      tallgrass: [0.02, 0],",
    'grass sit')

sub(
    "      fern: [0.14, 0], flower: [0.22, 0], shell: [0.05, 0], bone: [0.04, 1],",
    "      fern: [0.02, 0], flower: [0.22, 0], shell: [0.05, 0], bone: [0.04, 1],",
    'fern sit')

# Tall grass is the Heartlands and Greenwood filler the plan calls wheat-grass:
# it goes everywhere temperate, which is what makes the ground read as a field
# rather than as a lawn with objects on it.
sub(
    "      HEARTLANDS: [['wheat', 7], ['flower', 4], ['tuft', 4], ['bush', 2], ['pebble', 3], ['stick', 2]],\n"
    "      GREENWOOD:  [['fern', 7], ['bush', 5], ['tuft', 3], ['log', 2], ['stick', 4], ['pebble', 2]],",
    "      HEARTLANDS: [['tallgrass', 9], ['wheat', 6], ['flower', 4], ['tuft', 3], ['bush', 2], ['pebble', 3], ['stick', 2]],\n"
    "      GREENWOOD:  [['tallgrass', 6], ['fern', 7], ['bush', 5], ['tuft', 3], ['log', 2], ['stick', 4], ['pebble', 2]],",
    'temperate grass')

sub(
    "      wheat: [4, 7, 1.9], reed: [4, 7, 1.6], flower: [3, 6, 1.7], tuft: [3, 5, 1.6],",
    "      wheat: [4, 7, 1.9], reed: [4, 7, 1.6], flower: [3, 6, 1.7], tuft: [3, 5, 1.6],\n"
    "      tallgrass: [5, 9, 2.4],",
    'tallgrass clump')

sub(
    "    if (type === 'wheat') return zone === 'WINDSCAR' ? 0xc0ad72 : 0xc9b25e;",
    "    if (type === 'wheat') return zone === 'WINDSCAR' ? 0xc0ad72 : 0xc9b25e;\n"
    "    if (type === 'tallgrass') return zone === 'GREENWOOD' ? 0x62813f : 0x76893f;",
    'tallgrass tint')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
