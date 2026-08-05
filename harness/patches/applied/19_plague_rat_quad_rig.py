#!/usr/bin/env python3
"""Put THE PLAGUE RAT on the quadruped rig.

The rat has the best-built boss geometry in the game (lofted body, lofted skull,
five-segment tail, four lofted limbs) and it has been animated the entire time by
`animate()`, the BIPED path. That path swings `armR`/`armL` like arms and
`legR`/`legL` like legs, so a giant rat walks like a man: front paws paddling out
in front of it, back legs striding, no gallop, no jaw, no tail, no ears.

`poseQuadRig` already does all of this properly for the wolf, the deer, the boar,
the giant rat and the hare. It just needs a `qr` contract to drive, and the rat
did not have the joints to offer one. This patch builds them:

  spine     a pivot ON the spine line. poseQuadRig lifts and pitches qr.body
            every frame, so that group cannot be the one sitting at floor level
            or the whole rat see-saws about its own feet. `upper` hangs back
            down by the same 1.0 so every child coordinate below stays in the
            frame it was authored in, and nothing else in the builder moves.
  neckG     the neck the wolf rig pitches. Baked to the same numbers the rig
            reads back (nIdle / headBase), so the idle pose is exactly the pose
            the model was built in. A rat carries its head low and forward, so
            these are much flatter than the wolf's -0.62 / 0.5.
  jaw       hinged, with the incisors riding it. poseQuadRig opens the jaw on
            the damage frame, which is the whole point: the bite you see is the
            bite that hits.
  ears      wrapped in pivots so the rig's rare ear-flick has something to
            rotate that is not the ear mesh's own centre.
  tail      rebuilt as a PARENTED chain. It was five independent meshes placed
            in world space; per-segment sway would have torn it apart at every
            seam. Rotating link n now carries every link behind it.
  legs      jointed. A single rigid shaft has nowhere to put the second half of
            a gait cycle. Total limb length is unchanged at 0.80 so the rat's
            standing height does not move a millimetre.

Nothing about combat timing changes. `poseQuadRig` reads `e.act.wind` and peaks
the lunge exactly on the damage frame, the same contract every other quadruped
already honours, so the telegraph the player reads stays honest.

Touches only makeRatBoss. No shared rules, no sim.js, no driveAI.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ---------------------------------------------------------------- 1. spine
sub(
    "roughness: 0.4, flatShading: true });\n"
    "    const g = new T.Group();\n"
    "    const body = new T.Group(); g.add(body);\n"
    "    const upper = new T.Group(); body.add(upper);\n",

    "roughness: 0.4, flatShading: true });\n"
    "    const g = new T.Group();\n"
    "    const body = new T.Group(); g.add(body);\n"
    "    // Spine pivot. poseQuadRig lifts and pitches qr.body every frame, so that\n"
    "    // group has to sit ON the spine; anchored at the floor the whole rat\n"
    "    // see-saws about its own feet. upper hangs back down by the same amount so\n"
    "    // every child coordinate below stays in the frame it was authored in.\n"
    "    const spine = new T.Group(); spine.position.y = 1.0; body.add(spine);\n"
    "    const upper = new T.Group(); upper.position.y = -1.0; spine.add(upper);\n",
    'spine pivot')

# ------------------------------------------------------- 2. body mesh handle
sub(
    "    upper.add((() => { const m = this.loftMesh([\n"
    "      { z: 1.15, w: 0.55, h: 0.6, y: 0.88 },\n"
    "      { z: 0.45, w: 0.8, h: 0.85, y: 0.98 },\n"
    "      { z: -0.5, w: 0.9, h: 1.05, y: 1.12 },\n"
    "      { z: -1.35, w: 0.68, h: 0.8, y: 1.0 },\n"
    "      { z: -1.75, w: 0.4, h: 0.45, y: 0.85 }\n"
    "    ], 10, RTOP, RBELLY, matRat); return m; })());\n",

    "    const bodyMesh = this.loftMesh([\n"
    "      { z: 1.15, w: 0.55, h: 0.6, y: 0.88 },\n"
    "      { z: 0.45, w: 0.8, h: 0.85, y: 0.98 },\n"
    "      { z: -0.5, w: 0.9, h: 1.05, y: 1.12 },\n"
    "      { z: -1.35, w: 0.68, h: 0.8, y: 1.0 },\n"
    "      { z: -1.75, w: 0.4, h: 0.45, y: 0.85 }\n"
    "    ], 10, RTOP, RBELLY, matRat);\n"
    "    upper.add(bodyMesh);\n",
    'body mesh handle')

# ------------------------------------------------------------- 3. neck + head
sub(
    "    const head = new T.Group(); head.position.set(0, 1.05, 1.35); upper.add(head);\n"
    "    head.add(this.loftMesh([\n",

    "    // Neck. poseQuadRig reproduces the built pose exactly when nIdle and\n"
    "    // headBase match what is baked here, so these two numbers and the two in\n"
    "    // the qr block below have to stay in step.\n"
    "    const neckG = new T.Group(); neckG.position.set(0, 0.87, 0.95); neckG.rotation.x = -0.15; upper.add(neckG);\n"
    "    neckG.add(this.loftMesh([\n"
    "      { z: -0.05, w: 0.42, h: 0.44, y: 0 },\n"
    "      { z: 0.2, w: 0.37, h: 0.37, y: 0.04 },\n"
    "      { z: 0.42, w: 0.33, h: 0.31, y: 0.07 }\n"
    "    ], 9, RTOP, RBELLY, matRat));\n"
    "    const head = new T.Group(); head.position.set(0, 0.12, 0.42); head.rotation.x = 0.15; neckG.add(head);\n"
    "    head.add(this.loftMesh([\n",
    'neck group')

# --------------------------------------------------------- 4. jaw, ears, teeth
sub(
    "    for (const s of [-1, 1]) {\n"
    "      const ear = new T.Mesh(new T.SphereGeometry(0.24, 8, 6), fm(0x8a7568, 0.9));\n"
    "      ear.scale.set(1, 1.1, 0.28); ear.position.set(s * 0.32, 0.42, -0.12); ear.rotation.z = s * -0.35; head.add(ear);\n"
    "      const eye = new T.Mesh(new T.IcosahedronGeometry(0.085, 0), toxic); eye.position.set(s * 0.2, 0.08, 0.42); head.add(eye);\n"
    "      const tooth = new T.Mesh(new T.BoxGeometry(0.07, 0.2, 0.045), fm(0xe8e2d2, 0.5));\n"
    "      tooth.position.set(s * 0.055, -0.24, 0.82); head.add(tooth);\n",

    "    // Hinged jaw. poseQuadRig opens it on the damage frame, so the incisors\n"
    "    // ride the jaw rather than the skull.\n"
    "    const jaw = new T.Group(); jaw.position.set(0, -0.16, 0.28); head.add(jaw);\n"
    "    jaw.add(this.loftMesh([\n"
    "      { z: -0.02, w: 0.18, h: 0.075, y: 0 },\n"
    "      { z: 0.34, w: 0.09, h: 0.05, y: -0.02 },\n"
    "      { z: 0.56, w: 0.05, h: 0.035, y: -0.04 }\n"
    "    ], 6, 0x6e6552, 0x8a7f68, matRat));\n"
    "    const ears = [];\n"
    "    for (const s of [-1, 1]) {\n"
    "      const earPiv = new T.Group(); earPiv.position.set(s * 0.32, 0.42, -0.12); head.add(earPiv); ears.push(earPiv);\n"
    "      const ear = new T.Mesh(new T.SphereGeometry(0.24, 8, 6), fm(0x8a7568, 0.9));\n"
    "      ear.scale.set(1, 1.1, 0.28); ear.position.y = 0.08; ear.rotation.z = s * -0.35; earPiv.add(ear);\n"
    "      const eye = new T.Mesh(new T.IcosahedronGeometry(0.085, 0), toxic); eye.position.set(s * 0.2, 0.08, 0.42); head.add(eye);\n"
    "      const tooth = new T.Mesh(new T.BoxGeometry(0.07, 0.2, 0.045), fm(0xe8e2d2, 0.5));\n"
    "      tooth.position.set(s * 0.055, -0.08, 0.54); jaw.add(tooth);\n",
    'jaw and ear pivots')

# --------------------------------------------------------------- 5. tail chain
sub(
    "    { let ty = 1.0, tz = -1.8, ang = 0.35;\n"
    "      for (let i = 0; i < 5; i++) {\n"
    "        const seg = this.loftMesh([\n"
    "          { z: 0, w: 0.1 - i * 0.015, h: 0.1 - i * 0.015, y: 0 },\n"
    "          { z: -0.5, w: 0.08 - i * 0.014, h: 0.08 - i * 0.014, y: 0 }\n"
    "        ], 6, 0x9a7d6e, 0xc4a08c, fm(0xb08a7a, 0.8));\n"
    "        seg.position.set(0, ty, tz); seg.rotation.x = -ang;\n"
    "        upper.add(seg);\n"
    "        tz -= 0.5 * Math.cos(ang); ty -= 0.5 * Math.sin(ang); ang -= 0.16;\n"
    "      } }\n",

    "    // Naked tail, now a PARENTED chain: rotating link n carries every link\n"
    "    // behind it. It used to be five independent meshes placed in world space,\n"
    "    // which per-segment sway would tear apart at every seam.\n"
    "    const tailMat = fm(0xb08a7a, 0.8);\n"
    "    const tailRoot = new T.Group(); tailRoot.position.set(0, 1.0, -1.8); upper.add(tailRoot);\n"
    "    let tp = tailRoot; const tailSegs = [tailRoot];\n"
    "    for (let i = 0; i < 5; i++) {\n"
    "      tp.add(this.loftMesh([\n"
    "        { z: 0, w: 0.1 - i * 0.015, h: 0.1 - i * 0.015, y: 0 },\n"
    "        { z: -0.5, w: 0.08 - i * 0.014, h: 0.08 - i * 0.014, y: 0 }\n"
    "      ], 6, 0x9a7d6e, 0xc4a08c, tailMat));\n"
    "      const nxt = new T.Group(); nxt.position.z = -0.5; tp.add(nxt); tp = nxt;\n"
    "      if (i < 4) tailSegs.push(nxt);\n"
    "    }\n",
    'tail chain')

# -------------------------------------------------------------- 6. jointed legs
sub(
    "    const limb2 = (x, z) => { const piv = new T.Group(); piv.position.set(x, 0.75, z);\n"
    "      const l = this.loftMesh([\n"
    "        { z: 0, w: 0.16, h: 0.2, y: 0 },\n"
    "        { z: -0.5, w: 0.1, h: 0.12, y: 0 },\n"
    "        { z: -0.78, w: 0.08, h: 0.09, y: 0 }\n"
    "      ], 6, RTOP, RBELLY, matRat);\n"
    "      l.rotation.x = -Math.PI / 2; piv.add(l);\n"
    "      for (let ti = -1; ti <= 1; ti++) {\n"
    "        const cl = new T.Mesh(new T.ConeGeometry(0.035, 0.16, 4), fm(0xe3dcc4, 0.7));\n"
    "        cl.rotation.x = Math.PI / 2; cl.position.set(ti * 0.07, -0.76, 0.14); piv.add(cl);\n"
    "      }\n"
    "      piv.traverse(o => { if (o.isMesh) o.castShadow = true; }); upper.add(piv); return piv; };\n"
    "    const armR = limb2(-0.75, 0.85), armL = limb2(0.75, 0.85), legR = limb2(-0.7, -0.9), legL = limb2(0.7, -0.9);\n"
    "    const hand = new T.Group(); hand.position.y = -0.75; armR.add(hand);\n"
    "    const handL = new T.Group(); handL.position.y = -0.75; armL.add(handL);\n",

    "    // Jointed limbs. A rigid shaft has nowhere to put the second half of a\n"
    "    // gait cycle, which is why the rat slid rather than walked. Upper 0.44 plus\n"
    "    // lower 0.36 keeps the total at the 0.78 it was, so standing height and the\n"
    "    // reach of every hit test are unchanged.\n"
    "    const limb2 = (x, z, front) => {\n"
    "      const hip = new T.Group(); hip.position.set(x, 0.75, z);\n"
    "      const up2 = this.loftMesh([\n"
    "        { z: 0, w: 0.16, h: 0.2, y: 0 },\n"
    "        { z: -0.44, w: 0.11, h: 0.13, y: 0 }\n"
    "      ], 6, RTOP, RBELLY, matRat);\n"
    "      up2.rotation.x = -Math.PI / 2; hip.add(up2);\n"
    "      const knee = new T.Group(); knee.position.y = -0.44; hip.add(knee);\n"
    "      const lo2 = this.loftMesh([\n"
    "        { z: 0, w: 0.1, h: 0.12, y: 0 },\n"
    "        { z: -0.34, w: 0.08, h: 0.09, y: 0 }\n"
    "      ], 6, 0x6e6552, 0x8a7f68, matRat);\n"
    "      lo2.rotation.x = -Math.PI / 2; knee.add(lo2);\n"
    "      for (let ti = -1; ti <= 1; ti++) {\n"
    "        const cl = new T.Mesh(new T.ConeGeometry(0.035, 0.16, 4), fm(0xe3dcc4, 0.7));\n"
    "        cl.rotation.x = Math.PI / 2; cl.position.set(ti * 0.07, -0.32, 0.14); knee.add(cl);\n"
    "      }\n"
    "      hip.traverse(o => { if (o.isMesh) o.castShadow = true; }); upper.add(hip);\n"
    "      return { hip, knee, front };\n"
    "    };\n"
    "    const legs = [limb2(-0.75, 0.85, true), limb2(0.75, 0.85, true), limb2(-0.7, -0.9, false), limb2(0.7, -0.9, false)];\n"
    "    const armR = legs[0].hip, armL = legs[1].hip, legR = legs[2].hip, legL = legs[3].hip;\n"
    "    const hand = new T.Group(); hand.position.y = -0.44; legs[0].knee.add(hand);\n"
    "    const handL = new T.Group(); handL.position.y = -0.44; legs[1].knee.add(handL);\n",
    'jointed legs')

# ------------------------------------------------------------ 7. parts and qr
sub(
    "      parts: { upper, torso: null, head, armR, armL, legR, legL, hand, handL, "
    "sword, staff, bow, shield, ward, orb, frostShell, crest, capePiv, bladeTip },\n",

    "      parts: { upper: spine, torso: bodyMesh, head, armR, armL, legR, legL, "
    "backR: null, backL: null, hand, handL, sword, staff, bow, shield, great: null, "
    "ward, orb, frostShell, crest, capePiv, bladeTip, mount: null },\n"
    "      beast: true,\n"
    "      // The quad rig. Without it the rat is posed by the biped path in\n"
    "      // animate(), which swings two of its four legs like arms. nIdle and\n"
    "      // headBase mirror what is baked into neckG and head above, so the idle\n"
    "      // pose is exactly the pose the model was built in; a rat carries its head\n"
    "      // low and forward, hence far flatter numbers than the wolf's.\n"
    "      qr: { legs, neckG, head, jaw, ears, tailSegs, body: spine, baseY: 1.0,\n"
    "            nIdle: -0.15, nMove: -0.08, nRun: 0.04, headBase: 0.15 },\n",
    'parts and qr')


out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
