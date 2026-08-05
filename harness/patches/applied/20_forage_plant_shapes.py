#!/usr/bin/env python3
"""Give the nine forage plants their own silhouettes.

Every foraging node in the game - berry, mushroom, reeds, holly, fenroot,
dyeflower, spice, firelily, black lotus - was the SAME model: four jittered
icosahedra in a lump, separated only by a hex tint. A level 90 black lotus in
the fen and a level 1 berry bush outside the capital were the same four blobs.
You could not tell what you were standing next to without clicking it, and no
amount of new zones fixes that.

Each kind now gets a shape that reads at a glance:

  berry      low leafy mound with berries sitting on it
  mushroom   a cluster of capped stalks, tall and short
  reeds      tall vertical blades with cattail heads
  holly      dense spiked shrub with bright berries
  fenroot    a knuckled root arching out of the ground
  dyeflower  slim stalks under wide flat flower heads
  spice      low woody shrub hung with pods
  firelily   flared trumpet flowers on stems
  lotus      flat floating pads around a layered bloom

Rules the build already lives by and this keeps:

- ONE merged mesh per plant on the shared _nodeMat, exactly as before, so the
  draw call cost does not move. Only the triangles inside that one mesh change.
- Colour still comes from the zone palette plus the node tint: foliage reads
  look.bush, stalks read look.tuft, and the part you harvest reads the kind's
  own NODE_TINT. The same plant in two zones still looks like it belongs to
  each of them.
- Deterministic. Every number comes from the seeded rnd() the caller passes,
  so harness/dressing.js's cold-boot determinism assertion still holds.
- Vertex budget: the old lump was about 240 vertices. The heaviest new plant is
  about 520 and most sit near 400. Nodes are 2 to 4 per chunk and are their own
  meshes, so this lands well inside the chunk build time ceiling that actually
  governs (flat to about 220 CLUTTER per chunk; nodes are a rounding error).

Picked state: the stub was a grass tuft for everything, which read very oddly
for a lotus floating on the fen. Lotus now leaves its pads, mushrooms leave
their stems, and everything else keeps the tuft.

makeZonePlant gains a `kind` argument; the one call site passes it. Unknown
kinds fall through to the old four-blob lump, so a node added to the rules
table before it has art still renders something.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ------------------------------------------------------------- 1. call site
sub(
    "      else built = this.makeZonePlant(look, p.sc, seed, this.NODE_TINT(p.kind));\n",
    "      else built = this.makeZonePlant(look, p.sc, seed, this.NODE_TINT(p.kind), p.kind);\n",
    'plant call site')

# --------------------------------------------------------- 2. the builder
OLD = """  makeZonePlant(look, sc, seed, tint) {
    const T = this.T;
    const rnd = grimRnd(seed);
    const g = new T.Group();
    const fell = new T.Group(); g.add(fell);
    const parts = [];
    const c = new T.Color(tint);
    for (let i = 0; i < 4; i++) {
      const geo = this.jitterGeo(new T.IcosahedronGeometry(0.34 * sc, 0), 0.3, rnd() * 53, 0.9);
      const a = rnd() * Math.PI * 2, r = rnd() * 0.4 * sc;
      const m = new T.Matrix4().makeTranslation(Math.sin(a) * r, 0.3 * sc + rnd() * 0.3 * sc, Math.cos(a) * r);
      parts.push({ geo: geo.index ? geo.toNonIndexed() : geo, m: m, color: i ? c : new T.Color(look.bush) });
    }
    const body = new T.Mesh(this.mergeGeos(parts), this._nodeMat);
    fell.add(body);
    // picked state: the stalks stay, the harvest does not
    const stubG = new T.Group(); stubG.visible = false; g.add(stubG);
    const stub = new T.Mesh(this.mergeGeos([{ geo: this._clutterGeo.tuft, m: new T.Matrix4().makeScale(sc, sc * 0.6, sc), color: new T.Color(look.tuft) }]), this._nodeMat);
    stub.position.y = 0.16 * sc; stubG.add(stub);
    return { g: g, fell: fell, stump: stubG };
  }
"""

NEW = """  // Nine foraging kinds, nine silhouettes. Still ONE merged mesh per plant on
  // the shared _nodeMat, so the draw call cost is exactly what it was; only the
  // triangles inside that mesh changed. Foliage takes the zone's bush colour and
  // stalks its tuft colour, so the same plant still reads as belonging to the
  // zone it grew in, while the part you actually harvest carries the kind's own
  // tint. Everything is seeded off the caller's rnd, so cold-boot determinism
  // holds. An unknown kind falls through to the old lump rather than vanishing.
  makeZonePlant(look, sc, seed, tint, kind) {
    const T = this.T;
    const rnd = grimRnd(seed);
    const TAU = Math.PI * 2, S = sc;
    const g = new T.Group();
    const fell = new T.Group(); g.add(fell);
    const parts = [];
    const C = new T.Color(tint);                 // the harvest: berries, caps, blooms
    const LEAF = new T.Color(look.bush);         // zone foliage
    const STEM = new T.Color(look.tuft);         // zone stalk
    const BARK = new T.Color(look.stick);        // zone wood, for roots and seed heads
    const PALE = new T.Color(0xe0d8c4);
    const nonIdx = (x) => (x.index ? x.toNonIndexed() : x);
    // one primitive into the merge. s is a number or [x, y, z].
    const put = (geo, x, y, z, rx, ry, rz, s, col) => {
      const v = (s === undefined) ? [1, 1, 1] : (s.length ? s : [s, s, s]);
      parts.push({
        geo: nonIdx(geo),
        m: new T.Matrix4().compose(
          new T.Vector3(x, y, z),
          new T.Quaternion().setFromEuler(new T.Euler(rx || 0, ry || 0, rz || 0)),
          new T.Vector3(v[0], v[1], v[2])),
        color: col
      });
    };
    // a small round thing, cheaper than an icosahedron and round enough
    const bead = (r) => new T.OctahedronGeometry(r, 0);
    const blob = (r, j) => this.jitterGeo(new T.IcosahedronGeometry(r, 0), j === undefined ? 0.3 : j, rnd() * 53, 0.9);
    const ring = (i, n, jit) => i * TAU / n + (jit ? (rnd() - 0.5) * jit : 0);

    let stubKind = 'tuft';

    if (kind === 'berry') {
      for (let i = 0; i < 3; i++) {
        const a = ring(i, 3, 1.2), r = 0.20 * S;
        put(blob(0.28 * S), Math.cos(a) * r, (0.24 + i * 0.07) * S, Math.sin(a) * r, 0, 0, 0, 1, LEAF);
      }
      for (let i = 0; i < 7; i++) {
        const a = ring(i, 7, 0.8), r = (0.24 + rnd() * 0.14) * S;
        put(bead(0.068 * S), Math.cos(a) * r, (0.26 + rnd() * 0.30) * S, Math.sin(a) * r,
            rnd() * 3, rnd() * 3, rnd() * 3, 1, C);
      }

    } else if (kind === 'mushroom') {
      stubKind = 'stems';
      const cap = (x, z, h, r) => {
        put(new T.CylinderGeometry(0.030 * S, 0.048 * S, h, 5), x, h * 0.5, z, 0, 0, 0, 1, PALE);
        put(new T.ConeGeometry(r, r * 0.78, 7), x, h + r * 0.30, z, 0, rnd() * TAU, 0, 1, C);
      };
      cap(0, 0, 0.34 * S, 0.19 * S);
      cap(0.20 * S, 0.11 * S, 0.24 * S, 0.145 * S);
      cap(-0.15 * S, 0.17 * S, 0.29 * S, 0.16 * S);
      for (let i = 0; i < 2; i++) {
        const a = ring(i, 2, 1.6), r = 0.30 * S;
        put(bead(0.055 * S), Math.cos(a) * r, 0.055 * S, Math.sin(a) * r, 0, 0, 0, 1, C);
      }

    } else if (kind === 'reeds') {
      put(this.bladeTuft(6, 0.045 * S, 1.15 * S, 0.12, 3), 0, 0.02 * S, 0, 0, rnd() * TAU, 0, 1, STEM);
      for (let i = 0; i < 3; i++) {
        const a = ring(i, 3, 1.0), r = (0.06 + rnd() * 0.10) * S;
        const h = (0.86 + rnd() * 0.30) * S, lean = (rnd() - 0.5) * 0.16;
        const x = Math.cos(a) * r, z = Math.sin(a) * r;
        put(new T.CylinderGeometry(0.012 * S, 0.018 * S, h, 4), x, h * 0.5, z, lean, 0, lean * 0.6, 1, STEM);
        // the head takes the zone's wood colour, NOT the node tint: reeds tint
        // olive, which is the stalk colour, so tinted heads vanished entirely
        put(new T.CylinderGeometry(0.036 * S, 0.030 * S, 0.22 * S, 5), x + lean * h * 0.5, h + 0.09 * S, z, lean, 0, lean * 0.6, 1, BARK);
      }

    } else if (kind === 'holly') {
      put(blob(0.26 * S), 0, 0.26 * S, 0, 0, 0, 0, 1, LEAF);
      put(blob(0.20 * S), 0.10 * S, 0.42 * S, -0.06 * S, 0, 0, 0, 1, LEAF);
      for (let i = 0; i < 9; i++) {
        const a = i * 2.39996 + rnd() * 0.3;
        const t = 0.22 + (i / 9) * 0.34;
        put(new T.ConeGeometry(0.085 * S, 0.26 * S, 3),
            Math.cos(a) * 0.24 * S, t * S, Math.sin(a) * 0.24 * S,
            Math.cos(a) * 1.05, a, Math.sin(a) * 1.05, 1, LEAF);
      }
      for (let i = 0; i < 6; i++) {
        const a = ring(i, 6, 0.7), r = (0.16 + rnd() * 0.12) * S;
        put(bead(0.055 * S), Math.cos(a) * r, (0.24 + rnd() * 0.26) * S, Math.sin(a) * r,
            rnd() * 3, rnd() * 3, rnd() * 3, 1, C);
      }

    } else if (kind === 'fenroot') {
      // a knuckled root breaking the surface, low and horizontal
      const yaw = rnd() * TAU;
      const ARC = [[-0.30, 0.06, -0.9], [-0.10, 0.20, -0.35], [0.12, 0.21, 0.35], [0.32, 0.07, 0.95]];
      for (let i = 0; i < ARC.length; i++) {
        const a = ARC[i];
        put(new T.CylinderGeometry(0.075 * S, 0.090 * S, 0.30 * S, 5),
            Math.cos(yaw) * a[0] * S, a[1] * S, Math.sin(yaw) * a[0] * S,
            0, yaw, a[2], 1, BARK);
        if (i < ARC.length - 1) {
          put(bead(0.085 * S), Math.cos(yaw) * (a[0] + 0.10) * S, (a[1] + 0.03) * S,
              Math.sin(yaw) * (a[0] + 0.10) * S, 0, 0, 0, 1, C);
        }
      }
      for (let i = 0; i < 3; i++) {
        const a = ring(i, 3, 1.1);
        put(new T.ConeGeometry(0.085 * S, 0.36 * S, 3),
            Math.cos(a) * 0.16 * S, 0.28 * S, Math.sin(a) * 0.16 * S,
            Math.cos(a) * 0.5, a, Math.sin(a) * 0.5, 1, LEAF);
      }

    } else if (kind === 'dyeflower') {
      put(this.bladeTuft(4, 0.05 * S, 0.24 * S, 0.5, 5), 0, 0.02 * S, 0, 0, rnd() * TAU, 0, 1, LEAF);
      for (let i = 0; i < 4; i++) {
        const a = ring(i, 4, 0.9), r = (0.08 + rnd() * 0.12) * S;
        const h = (0.46 + rnd() * 0.28) * S, lean = (rnd() - 0.5) * 0.3;
        const x = Math.cos(a) * r, z = Math.sin(a) * r;
        put(new T.CylinderGeometry(0.014 * S, 0.020 * S, h, 4), x, h * 0.5, z, lean, 0, lean, 1, STEM);
        const hx = x + Math.sin(lean) * h * 0.5, hz = z + Math.sin(lean) * h * 0.3;
        // a wide shallow cone reads as a flat flower head from every angle
        put(new T.ConeGeometry(0.115 * S, 0.055 * S, 6), hx, h + 0.02 * S, hz, 0, rnd() * TAU, 0, 1, C);
        put(bead(0.038 * S), hx, h + 0.055 * S, hz, 0, 0, 0, 1, PALE);
      }

    } else if (kind === 'spice') {
      put(blob(0.24 * S), 0, 0.24 * S, 0, 0, 0, 0, 1, LEAF);
      put(blob(0.19 * S), -0.13 * S, 0.36 * S, 0.08 * S, 0, 0, 0, 1, LEAF);
      for (let i = 0; i < 2; i++) {
        const a = ring(i, 2, 1.4);
        put(new T.CylinderGeometry(0.020 * S, 0.032 * S, 0.30 * S, 4),
            Math.cos(a) * 0.10 * S, 0.15 * S, Math.sin(a) * 0.10 * S, 0, 0, 0, 1, STEM);
      }
      // pods hang, so they point down and out
      for (let i = 0; i < 10; i++) {
        const a = i * 2.39996 + rnd() * 0.3, r = (0.18 + rnd() * 0.12) * S;
        put(new T.ConeGeometry(0.038 * S, 0.17 * S, 3),
            Math.cos(a) * r, (0.18 + rnd() * 0.26) * S, Math.sin(a) * r,
            Math.cos(a) * 2.3, a, Math.sin(a) * 2.3, 1, C);
      }

    } else if (kind === 'firelily') {
      put(this.bladeTuft(4, 0.055 * S, 0.30 * S, 0.62, 9), 0, 0.02 * S, 0, 0, rnd() * TAU, 0, 1, LEAF);
      for (let i = 0; i < 3; i++) {
        const a = ring(i, 3, 0.9), r = (0.07 + rnd() * 0.10) * S;
        const h = (0.40 + rnd() * 0.22) * S, lean = (rnd() - 0.5) * 0.26;
        const x = Math.cos(a) * r, z = Math.sin(a) * r;
        put(new T.CylinderGeometry(0.018 * S, 0.026 * S, h, 4), x, h * 0.5, z, lean, 0, lean, 1, STEM);
        // cone flipped so it flares open at the top: a trumpet, not a spike
        put(new T.ConeGeometry(0.135 * S, 0.23 * S, 6), x, h + 0.10 * S, z, Math.PI + lean, rnd() * TAU, 0, 1, C);
      }
      for (let i = 0; i < 2; i++) {
        const a = ring(i, 2, 1.5);
        put(new T.ConeGeometry(0.05 * S, 0.16 * S, 4), Math.cos(a) * 0.19 * S, 0.30 * S, Math.sin(a) * 0.19 * S,
            Math.cos(a) * 0.4, a, Math.sin(a) * 0.4, 1, C);
      }

    } else if (kind === 'lotus') {
      stubKind = 'pads';
      for (let i = 0; i < 3; i++) {
        const a = ring(i, 3, 0.9), r = (0.26 + rnd() * 0.14) * S;
        put(new T.CylinderGeometry(0.28 * S, 0.28 * S, 0.022 * S, 6),
            Math.cos(a) * r, 0.035 * S, Math.sin(a) * r, 0, rnd() * TAU, 0, 1, LEAF);
      }
      // two rings of petals, the outer ones opening wider than the inner
      for (let k = 0; k < 2; k++) {
        const n = 5, lean = k ? 0.55 : 1.05, r = (k ? 0.06 : 0.10) * S, y = (k ? 0.22 : 0.15) * S;
        for (let i = 0; i < n; i++) {
          const a = i * TAU / n + k * 0.62;
          put(new T.ConeGeometry(0.055 * S, 0.20 * S, 3),
              Math.cos(a) * r, y, Math.sin(a) * r,
              Math.cos(a) * lean, a, Math.sin(a) * lean, 1, C);
        }
      }
      put(bead(0.055 * S), 0, 0.28 * S, 0, 0, 0, 0, 1, PALE);

    } else {
      // unknown kind: the original lump, so a rules-table entry that has no art
      // yet still renders something instead of nothing
      for (let i = 0; i < 4; i++) {
        const a = rnd() * TAU, r = rnd() * 0.4 * S;
        put(blob(0.34 * S), Math.sin(a) * r, 0.3 * S + rnd() * 0.3 * S, Math.cos(a) * r,
            0, 0, 0, 1, i ? C : LEAF);
      }
    }

    const body = new T.Mesh(this.mergeGeos(parts), this._nodeMat);
    fell.add(body);

    // picked state: what is left behind once the harvest is gone
    const stubG = new T.Group(); stubG.visible = false; g.add(stubG);
    const sp = [];
    if (stubKind === 'pads') {
      // you take the bloom, the pads stay on the water
      const r2 = grimRnd(seed);
      for (let i = 0; i < 3; i++) {
        const a = i * TAU / 3 + (r2() - 0.5) * 0.9, r = (0.26 + r2() * 0.14) * S;
        sp.push({ geo: nonIdx(new T.CylinderGeometry(0.28 * S, 0.28 * S, 0.022 * S, 6)),
                  m: new T.Matrix4().makeTranslation(Math.cos(a) * r, 0.035 * S, Math.sin(a) * r),
                  color: LEAF });
      }
    } else if (stubKind === 'stems') {
      // cut caps: the stalks are still standing
      const at = [[0, 0, 0.13], [0.20 * S, 0.11 * S, 0.09], [-0.15 * S, 0.17 * S, 0.11]];
      for (const p of at) {
        sp.push({ geo: nonIdx(new T.CylinderGeometry(0.030 * S, 0.048 * S, p[2] * S, 5)),
                  m: new T.Matrix4().makeTranslation(p[0], p[2] * S * 0.5, p[1]),
                  color: PALE });
      }
    } else {
      sp.push({ geo: this._clutterGeo.tuft,
                m: new T.Matrix4().compose(new T.Vector3(0, 0.16 * S, 0), new T.Quaternion(),
                                           new T.Vector3(S, S * 0.6, S)),
                color: STEM });
    }
    stubG.add(new T.Mesh(this.mergeGeos(sp), this._nodeMat));
    return { g: g, fell: fell, stump: stubG };
  }
"""
sub(OLD, NEW, 'makeZonePlant')


out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
