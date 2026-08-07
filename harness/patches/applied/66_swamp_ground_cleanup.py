#!/usr/bin/env python3
"""Removes the two flat hand-placed meshes buildSwamp() laid over the mere:
a dark CircleGeometry 'bog' disc and a glassy CircleGeometry 'lake' plane.
Both predate the ground-atlas texture system (the zone already paints a real
'bog' surface there through groundSurface()/MISTFEN, see the [13,13] entry
around line ~5259 in the source), so these two overlay meshes were always
just old scenery sitting on top of the real terrain, not terrain themselves.
That is exactly why the world editor's paint tool could never touch them:
they are not part of the ground surface, they are two separate opaque
circles floating a few centimetres above it.

Kevin asked for the fake pond and the dark round ground patch near the area
he calls "the playground" to go so he can repaint that ground properly in
the editor. This is that zone (buildSwamp, cx=93 cz=-87, the mere/MISTFEN
quest area for THE MERE ROAD / FELL THE PLAGUE RAT). Everything else in
buildSwamp is left alone: the reeds, the oak trees, and the sheep (shearable,
tied to the swamp-wool quest step) all stay exactly as they were. Only the
two overlay meshes are removed. The real terrain underneath (already a bog
surface per the zone table) is what shows through now, ready to be painted.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()

def sub(old, new, what):
    global s
    n = s.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (what, n)
    s = s.replace(old, new, 1)

sub(
    "  buildSwamp() {\n"
    "    const T = this.T, S = this.scene;\n"
    "    const cx = 93, cz = -87;\n"
    "    const bog = new T.Mesh(new T.CircleGeometry(24, 22), new T.MeshStandardMaterial({ color: 0x3d4a33, roughness: 1 }));\n"
    "    bog.rotation.x = -Math.PI / 2; bog.position.set(cx, 0.02, cz); bog.receiveShadow = true; S.add(bog);\n"
    "    const lake = new T.Mesh(new T.CircleGeometry(13, 26), new T.MeshStandardMaterial({ color: 0x2e4238, roughness: 0.25, metalness: 0.35 }));\n"
    "    lake.rotation.x = -Math.PI / 2; lake.position.set(cx + 2, 0.045, cz - 2); S.add(lake);\n"
    "    const reedM = new T.MeshStandardMaterial({ color: 0x5c6b38, roughness: 1, flatShading: true });",
    "  buildSwamp() {\n"
    "    const T = this.T, S = this.scene;\n"
    "    const cx = 93, cz = -87;\n"
    "    // The old flat 'bog' disc and 'lake' plane that used to sit here were\n"
    "    // removed (patch 66): pre-atlas overlay meshes, not real terrain, so the\n"
    "    // editor's paint tool could never touch them. The zone already paints a\n"
    "    // real bog surface here on its own; this area is now plain paintable\n"
    "    // ground like everywhere else.\n"
    "    const reedM = new T.MeshStandardMaterial({ color: 0x5c6b38, roughness: 1, flatShading: true });",
    'buildSwamp bog+lake removal'
)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('ok: buildSwamp bog+lake meshes removed')
