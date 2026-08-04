#!/usr/bin/env python3
"""Phase 1, part 4: dress chunks as a pass, not as a creation hook.

The boot backfill builds the whole ring set inside initTerrain, before the
world's roads and landmarks exist. Dressing on chunk creation therefore never
fired for those chunks (they already had the right detail level, so the create
loop skipped them forever) and, if it had fired, it would have placed props
across roads that had not been registered yet.

So dressing is its own pass over the detail rings, and it is armed only once
the player is actually in the world, which is after every road is registered.
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
    "          const rec = { mesh: nmch, seg: wantSeg, cx: cx, cz: cz };\n"
    "          this._chunks.set(key, rec);\n"
    "          // Only the detail rings are dressed. Clutter beyond that is\n"
    "          // invisible at distance and would cost draw calls for nothing.\n"
    "          if (ring <= DRESS && this.worldOn) this.dressChunk(rec);\n"
    "          budget--;",

    "          this._chunks.set(key, { mesh: nmch, seg: wantSeg, cx: cx, cz: cz });\n"
    "          budget--;",
    'drop creation hook')

sub(
    "    for (const [key, ch] of this._chunks) {\n"
    "      if (Math.max(Math.abs(ch.cx - pcx), Math.abs(ch.cz - pcz)) > COARSE + 1) {\n"
    "        this.dressDrop(ch); this.scene.remove(ch.mesh); ch.mesh.geometry.dispose(); this._chunks.delete(key);\n"
    "      }\n"
    "    }",

    "    for (const [key, ch] of this._chunks) {\n"
    "      const r = Math.max(Math.abs(ch.cx - pcx), Math.abs(ch.cz - pcz));\n"
    "      if (r > COARSE + 1) {\n"
    "        this.dressDrop(ch); this.scene.remove(ch.mesh); ch.mesh.geometry.dispose(); this._chunks.delete(key);\n"
    "      } else if (r > DRESS && ch.dressed) {\n"
    "        // walked away: the props go, the harvest state they carried does not\n"
    "        this.dressDrop(ch);\n"
    "      }\n"
    "    }\n"
    "    // Dressing pass. Separate from chunk creation because the boot backfill\n"
    "    // builds every nearby chunk before the world has roads or landmarks, and\n"
    "    // a chunk that already has the right detail level is never rebuilt. Armed\n"
    "    // only once the player is in the world, which is after every road is\n"
    "    // registered, so nothing can be placed across a road that does not exist\n"
    "    // yet.\n"
    "    // _dressOff is a tooling switch: the perf harness needs the same ground\n"
    "    // with dressing suppressed to measure the delta honestly.\n"
    "    if (this.worldOn && this.started && GRIM_WORLD.ready && !this._dressOff) {\n"
    "      let dbud = boot ? 40 : 2;\n"
    "      for (let ring = 0; ring <= DRESS && dbud > 0; ring++) {\n"
    "        for (let dx = -ring; dx <= ring && dbud > 0; dx++) {\n"
    "          for (let dz = -ring; dz <= ring && dbud > 0; dz++) {\n"
    "            if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;\n"
    "            const rec = this._chunks.get((pcx + dx) + ',' + (pcz + dz));\n"
    "            if (!rec || rec.dressed) continue;\n"
    "            this.dressChunk(rec);\n"
    "            rec.dressed = true;\n"
    "            dbud--;\n"
    "          }\n"
    "        }\n"
    "      }\n"
    "    }",
    'dress pass')

sub(
    "  dressDrop(rec) {\n"
    "    if (rec.clutter) {",
    "  dressDrop(rec) {\n"
    "    rec.dressed = false;\n"
    "    if (rec.clutter) {",
    'dressDrop clears flag')

# Entering the world re-arms the pass, so the first tick after play() dresses
# the ring the player is standing in rather than trickling it in two per frame.
sub(
    "    this.started = true;\n"
    "    this.musicInit();",
    "    this.started = true;\n"
    "    this._terrAcc = 99;\n"
    "    if (this.worldOn) this.stepTerrain(0, 40);   // dress the ground under the player before the first frame\n"
    "    this.musicInit();",
    'arm dressing on play')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
