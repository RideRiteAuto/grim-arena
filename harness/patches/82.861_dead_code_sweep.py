#!/usr/bin/env python3
"""Patch 82.861: delete four confirmed-dead helper methods.

Each was verified via a full-file grep with zero call sites anywhere else in
the bundle (including no bracket-notation this['name'] calls):

- saveWallet(): a trivial one-line alias of invSave(), which is called
  directly everywhere else.
- invFindStack(id): listed under the file's own "pure helpers" section,
  unused.
- armourName(): traced via patch history (38_ui_pass_one.py) to a shop-panel
  footer line ("WEARING: " + this.armourName()) that a later UI redesign
  removed. The helper was left behind; neither "WEARING:" nor "ARMOUR:"
  appears anywhere in the current bundle.
- recolorForGoblin(e): a goblin gear-recolor helper with no spawn/equip code
  anywhere that calls it.

Left alone on purpose (confirmed intentional, not dead-from-neglect):
frameToWorld/worldToFrame (labeled Phase-1c vehicle-frame scaffolding) and
the RULES()/EDIT()/WORLD()/etc. debug console handles (labeled devtools
accessors). Neither is touched by this patch.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD1 = """  saveWallet() { this.invSave(); }
"""
NEW1 = ""
count1 = s.count(OLD1)
assert count1 == 1, 'anchor1 matched %d times, expected 1' % count1
s = s.replace(OLD1, NEW1)

OLD2 = """  invFindStack(id) { for (let i = 0; i < 28; i++) { const c = this.inv[i]; if (c && c.item === id) return i; } return -1; }
"""
NEW2 = ""
count2 = s.count(OLD2)
assert count2 == 1, 'anchor2 matched %d times, expected 1' % count2
s = s.replace(OLD2, NEW2)

OLD3 = """  armourName() {
    const b = this.worn && this.worn.BODY;
    return b ? b.item : 'NONE';
  }
"""
NEW3 = ""
count3 = s.count(OLD3)
assert count3 == 1, 'anchor3 matched %d times, expected 1' % count3
s = s.replace(OLD3, NEW3)

OLD4 = """ recolorForGoblin(e) { const swap = (root, fromHex, toHex) => { root.traverse(o => { if (o.isMesh && o.material && o.material.color && o.material.color.getHex() === fromHex) { o.material = o.material.clone(); o.material.color.setHex(toHex); } }); }; swap(e.parts.sword, 0xccd4dc, 0x9a6a34); swap(e.parts.sword, 0xf2f6fa, 0xc9a15a); swap(e.parts.shield, 0x6f8a3d, 0x6b4a2a);
  }"""
NEW4 = ""
count4 = s.count(OLD4)
assert count4 == 1, 'anchor4 matched %d times, expected 1' % count4
s = s.replace(OLD4, NEW4)

io.open(PATH, 'w', encoding='utf-8').write(s)
