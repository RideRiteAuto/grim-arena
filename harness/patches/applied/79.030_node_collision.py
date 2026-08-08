#!/usr/bin/env python3
"""Patch 79.030: physical collision for harvestable nodes (trees, ore).

Kevin's report: ore veins and trees walk straight through, procedural ones
and hand-placed ones alike. He specifically wants his editor-placed nodes
(copper veins, stone, etc, already saved in the live edit layer) to behave
like real obstacles, not scenery.

Root cause, confirmed by booting the harness against Kevin's actual saved
edit layer (566 KB, rev 55, fetched live from the relay) and inspecting the
running scene: his placed nodes DO make it into the game correctly (they are
in G.zoneNodes/rec.nodes with authored:true, hp/max set, mesh in the scene),
and gatherCheck() already walks allResources() = resources.concat(zoneNodes),
so mining/chopping/harvesting them already works with zero code changes
needed there. What's missing, for authored AND procedural nodes both, is
that neither build path ever pushes anything into G.colliders, the same
array every camp structure, wall and piece of furniture uses to physically
block the player. Confirmed live: 19 of Kevin's placed nodes checked, 0
colliders within 20m of any of them, out of 206 colliders total in the
world (all from hand-built camp/town/keep set pieces).

Fix: give WOODCUTTING and MINING nodes a small solid radius (foraging nodes
- herbs, berries, mushrooms - stay walk-through on purpose, they are too
small to read as an obstacle) and push/pop a collider alongside the node's
own lifecycle, in both places a node gets built (the procedural dressChunk
loop and the editor's buildNode/dress in GRIM_EDIT_RENDER) and in the one
shared place every node gets released (dressDrop), so a chunk streaming out
never leaves a dangling collider behind.

editor-tools.js carries GRIM_EDIT_CATALOG/GRIM_EDIT_RENDER/buildNode - it is
one of the three files synced into the EDITOR-BEGIN/END region on every
build, so (per the patch 77 lesson) it is edited directly on disk here, not
through the extracted bundle. dressChunk's procedural loop and dressDrop are
ordinary game code, safe to patch through the extracted bundle. shared-
rules.js is likewise edited on disk directly since GATHER config is in the
SHARED-RULES-BEGIN/END synced region.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0

def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 79.030 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1

# ---- 1. procedural node build loop: attach + push a collider --------------
sub(
    """      const R = {
        kind: p.kind, nid: p.nid, g: built.g, fell: built.fell || null, stump: built.stump || null,
        studs: built.studs || null, rubble: built.rubble || null, hp: nd.hp, max: nd.hp, dead: false, respawn: 0, streamed: true
      };
      // a node emptied a moment ago must come back empty when you walk away
      // and back, not full: the chunk unloads, the state does not
      const kept = this._nodeState && this._nodeState[p.nid];
      if (kept && kept.dead) { R.hp = 0; R.dead = true; R.respawn = kept.respawn; }
      this.zoneNodes.push(R);
      rec.nodes.push(R);
      if (R.dead) this.resourceDepleted(R, null);""",
    """      const solidR = (GRIM_RULES.GATHER.NODE_SOLID_R || {})[nd.skill];
      const R = {
        kind: p.kind, nid: p.nid, g: built.g, fell: built.fell || null, stump: built.stump || null,
        studs: built.studs || null, rubble: built.rubble || null, hp: nd.hp, max: nd.hp, dead: false, respawn: 0, streamed: true,
        col: solidR ? { x: p.x, z: p.z, r: solidR * (p.sc || 1) } : null
      };
      // a node emptied a moment ago must come back empty when you walk away
      // and back, not full: the chunk unloads, the state does not
      const kept = this._nodeState && this._nodeState[p.nid];
      if (kept && kept.dead) { R.hp = 0; R.dead = true; R.respawn = kept.respawn; }
      this.zoneNodes.push(R);
      rec.nodes.push(R);
      // Same collider list every solid prop uses, so a tree trunk or an ore
      // vein stops you the way a furnace or a wall already does.
      if (R.col) { this.colliders = this.colliders || []; this.colliders.push(R.col); }
      if (R.dead) this.resourceDepleted(R, null);""",
    tag='procedural node build: create + push collider')

# ---- 2. dressDrop: pop the collider when the node's chunk releases ---------
sub(
    """      for (const R of rec.nodes) {
        // remember what was harvested so the world does not refill behind you
        if (R.dead) this._nodeState[R.nid] = { dead: true, respawn: R.respawn };
        else delete this._nodeState[R.nid];
        this.scene.remove(R.g);
        R.g.traverse(o => { if (o.isMesh && o.geometry) o.geometry.dispose(); });
        const i = this.zoneNodes.indexOf(R);
        if (i >= 0) this.zoneNodes.splice(i, 1);
      }""",
    """      for (const R of rec.nodes) {
        // remember what was harvested so the world does not refill behind you
        if (R.dead) this._nodeState[R.nid] = { dead: true, respawn: R.respawn };
        else delete this._nodeState[R.nid];
        this.scene.remove(R.g);
        R.g.traverse(o => { if (o.isMesh && o.geometry) o.geometry.dispose(); });
        const i = this.zoneNodes.indexOf(R);
        if (i >= 0) this.zoneNodes.splice(i, 1);
        // Leaving the collider behind would build an invisible wall out of
        // every node a player has ever walked away from.
        if (R.col && this.colliders) {
          const ci = this.colliders.indexOf(R.col);
          if (ci >= 0) this.colliders.splice(ci, 1);
        }
      }""",
    tag='dressDrop: pop collider on release')

io.open(SRC, 'w', encoding='utf-8').write(s)

# ---- 3. shared-rules.js: the solid-radius table, the single source of truth
RULES = 'shared-rules.js'
r = io.open(RULES, encoding='utf-8').read()
old_rules = "    TOOL_FOR: { WOODCUTTING: 'axe', MINING: 'pick', FORAGING: 'sickle' },"
new_rules = """    TOOL_FOR: { WOODCUTTING: 'axe', MINING: 'pick', FORAGING: 'sickle' },

    // Physical collision radius for a harvestable node, in metres, scaled by
    // the node's own scale factor at build time. Trees and ore used to be
    // walk-through, which read wrong once Kevin started placing them by hand
    // to shape a path or wall off a cave mouth. Foraging nodes (herbs,
    // berries, mushrooms) are small and stay walk-through on purpose.
    NODE_SOLID_R: { WOODCUTTING: 0.5, MINING: 0.7 },"""
f = r.count(old_rules)
assert f == 1, 'patch 79.030 [add NODE_SOLID_R to shared-rules.js]: anchor found %d times, wanted 1' % f
r = r.replace(old_rules, new_rules)
io.open(RULES, 'w', encoding='utf-8').write(r)
n += 1

# ---- 4. editor-tools.js: the authored-object path (buildNode + dress) -----
TOOLS = 'editor-tools.js'
t = io.open(TOOLS, encoding='utf-8').read()

old_buildnode_tail = """    return {
      kind: c.node, nid: 'ed:' + o.i, g: built.g,
      fell: built.fell || null, stump: built.stump || null,
      studs: built.studs || null, rubble: built.rubble || null,
      hp: nd.hp, max: nd.hp, dead: false, respawn: 0,
      streamed: true, authored: true
    };
  }"""
new_buildnode_tail = """    const solidR = (typeof GRIM_RULES !== 'undefined' && GRIM_RULES.GATHER && GRIM_RULES.GATHER.NODE_SOLID_R)
      ? GRIM_RULES.GATHER.NODE_SOLID_R[nd.skill] : null;
    return {
      kind: c.node, nid: 'ed:' + o.i, g: built.g,
      fell: built.fell || null, stump: built.stump || null,
      studs: built.studs || null, rubble: built.rubble || null,
      hp: nd.hp, max: nd.hp, dead: false, respawn: 0,
      streamed: true, authored: true,
      col: solidR ? { x: o.x, z: o.z, r: solidR * sc } : null
    };
  }"""
f1 = t.count(old_buildnode_tail)
assert f1 == 1, 'patch 79.030 [editor-tools.js buildNode: attach collider]: anchor found %d times, wanted 1' % f1
t = t.replace(old_buildnode_tail, new_buildnode_tail)

old_dress_push = """        G.zoneNodes.push(R);
        rec.nodes = rec.nodes || [];
        rec.nodes.push(R);
        if (R.dead && G.resourceDepleted) { try { G.resourceDepleted(R, null); } catch (e) {} }
        continue;"""
new_dress_push = """        G.zoneNodes.push(R);
        rec.nodes = rec.nodes || [];
        rec.nodes.push(R);
        // Same collider list a placed furnace uses, so a hand-placed ore
        // vein or tree blocks a path exactly like a grown one does.
        if (R.col && G.colliders) G.colliders.push(R.col);
        if (R.dead && G.resourceDepleted) { try { G.resourceDepleted(R, null); } catch (e) {} }
        continue;"""
f2 = t.count(old_dress_push)
assert f2 == 1, 'patch 79.030 [editor-tools.js dress(): push collider]: anchor found %d times, wanted 1' % f2
t = t.replace(old_dress_push, new_dress_push)

io.open(TOOLS, 'w', encoding='utf-8').write(t)
n += 2

print('79.030_node_collision: %d edits applied' % n)
