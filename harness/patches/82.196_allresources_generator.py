#!/usr/bin/env python3
"""Patch 82.196: stop allResources() allocating a full array via .concat()
every frame.

stepWorld calls this every frame once zoneNodes is populated (normal in-world
play), and it only ever gets iterated with for...of at both call sites (grepped
and confirmed - never .length'd, .filter'd, or indexed). A generator method
yields the exact same elements in the exact same order (resources, then
zoneNodes) with zero array allocation, and for...of works on it identically
to how it worked on the old concatenated array. No behavior change.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """  allResources() {
    if (!this.zoneNodes || !this.zoneNodes.length) return this.resources;
    return this.resources.concat(this.zoneNodes);
  }
"""

NEW = """  *allResources() {
    if (this.resources) for (const r of this.resources) yield r;
    if (this.zoneNodes) for (const r of this.zoneNodes) yield r;
  }
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
