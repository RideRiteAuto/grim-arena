#!/usr/bin/env python3
"""Interaction picks the NEAREST thing, and the reach is a hand's length.

Two problems, reported as "the ranges blend into each other and one shows over
the other".

First, both the prompt and the F key ran a fixed priority chain:

    tryBank() || trySack() || tryTalk() || tryTalkNorth() || tryTrade()
      || trySmelt() || tryForge() || trySheep()

Whoever came first in that list won, regardless of which one you were actually
standing on. Stand between Margaret and Fenwick and you always get Margaret,
even with your nose against Fenwick. Stand between the furnace and the anvil and
you always get the furnace.

Second, the reaches were long and uneven: 4.2m for two of the NPCs, 4.0 for the
bank, 3.6, 3.2, 3.0, 2.2 for the rest. In a town where the smith's furnace, his
anvil and the man himself stand within a few metres of each other, four metre
bubbles overlap three deep.

Now there is ONE list of what is reachable, both the prompt and the key read it,
and it is sorted by distance so the thing you are standing on is the thing you
get. Reaches are a consistent 2.6m for people and stations, which is close
enough that two of them have to be almost inside each other to overlap, and far
enough that you do not have to hunt for the spot.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# ------------------------------------------------------- 1. the shared list
sub(
    "  tryBank() {",

    "  // Everything you can reach right now, nearest first. One list, read by\n"
    "  // both the on-screen prompt and the F key, so the prompt can never name\n"
    "  // one thing while the key does another.\n"
    "  //\n"
    "  // REACH is deliberately short. A person and a workbench standing a couple\n"
    "  // of metres apart used to have overlapping four metre bubbles, and the\n"
    "  // winner was whoever came first in a hardcoded chain rather than whoever\n"
    "  // you were standing on.\n"
    "  REACH() { return { npc: 2.6, station: 2.6, bank: 2.8, sack: 2.6, sheep: 2.0 }; }\n"
    "\n"
    "  interactCandidates() {\n"
    "    const me = this.me;\n"
    "    const out = [];\n"
    "    if (!me || me.hp <= 0 || this.mode !== 'ai' || !this.worldOn) return out;\n"
    "    const R = this.REACH();\n"
    "    const add = (pos, r, label, run) => {\n"
    "      if (!pos) return;\n"
    "      const d = Math.hypot(me.pos.x - (pos.x !== undefined ? pos.x : pos[0]),\n"
    "                           me.pos.z - (pos.z !== undefined ? pos.z : pos[1]));\n"
    "      if (d <= r) out.push({ d: d, label: label, run: run });\n"
    "    };\n"
    "    add(this.bankPos, R.bank, 'F - OPEN YOUR BANK', () => this.tryBank());\n"
    "    const sid = this.nearestSack(R.sack);\n"
    "    if (sid && this.sacks[sid]) add(this.sacks[sid], R.sack, 'F - OPEN LOOT SACK', () => this.trySack());\n"
    "    if (this.margaret) add(this.margaret.pos, R.npc, 'F - TALK TO MARGARET VANCE', () => this.tryTalkNorth());\n"
    "    if (this.fenwick) add(this.fenwick.pos, R.npc, 'F - TRADE WITH FENWICK', () => this.tryTrade());\n"
    "    if (this.paul) add(this.paul.pos, R.npc, 'F - TALK TO BALL PELLINGER', () => this.tryTalk());\n"
    "    if (this.furnace) add(this.furnace.pos, R.station,\n"
    "      this.smelting ? 'F - STOP SMELTING' : 'F - SMELT IRON ORE', () => this.trySmelt());\n"
    "    if (this.anvil) add(this.anvil.pos, R.station, 'F - FORGE (10 IRON BARS)', () => this.tryForge());\n"
    "    for (const s of (this.sheep || [])) add(s.g.position, R.sheep, 'F - SHEAR SHEEP', () => this.trySheep());\n"
    "    out.sort((a, b) => a.d - b.d);\n"
    "    return out;\n"
    "  }\n"
    "  // What F would act on this instant. Panels that are already open win,\n"
    "  // because closing the thing in front of you is always what you meant.\n"
    "  bestInteract() {\n"
    "    if (this.shopOpen) return { label: 'F - CLOSE THE TRADER', run: () => { this.closeShop(); return true; } };\n"
    "    if (this.bankOpen) return { label: 'F - CLOSE THE BANK', run: () => this.tryBank() };\n"
    "    if (this.sackWinId) return { label: 'F - CLOSE THE SACK', run: () => this.trySack() };\n"
    "    return this.interactCandidates()[0] || null;\n"
    "  }\n"
    "\n"
    "  tryBank() {",
    'interact list')

# ------------------------------------------------------------ 2. the F key
sub(
    "      if (k === '3') { if (this.shopOpen) { this.closeShop(); return; } if (this.tryBank() || this.trySack() || this.tryTalk() || this.tryTalkNorth() || this.tryTrade() || this.trySmelt() || this.tryForge() || this.trySheep()) return; this.switchWeapon(2); }",
    "      if (k === '3') {\n"
    "        // One list, nearest first. The old fixed chain meant the prompt and\n"
    "        // the key could disagree, and that whoever was first in the chain won\n"
    "        // no matter which one you were standing on.\n"
    "        const pick = this.bestInteract();\n"
    "        if (pick && pick.run()) return;\n"
    "        this.switchWeapon(2);\n"
    "      }",
    'F key')

# ---------------------------------------------------------- 3. the prompt
sub(
    "    if (this.promptRef.current) {\n"
    "      let ptxt = '';\n"
    "      if (world && this.started && me.hp > 0) {\n"
    "        if (this.shopOpen) ptxt = 'F — CLOSE THE TRADER';\n"
    "        else if (this.bankOpen) ptxt = 'F — CLOSE THE BANK';\n"
    "        else if (this.bankPos && me.pos.distanceTo(this.bankPos) < 4.0) ptxt = 'F — OPEN YOUR BANK';\n"
    "        else if (this.sackWinId) ptxt = 'F — CLOSE THE SACK';\n"
    "        else if (this.nearestSack()) ptxt = 'F — OPEN LOOT SACK';\n"
    "        else if (this.margaret && me.pos.distanceTo(this.margaret.pos) < 4.2) ptxt = 'F — TALK TO MARGARET VANCE';\n"
    "        else if (this.fenwick && me.pos.distanceTo(this.fenwick.pos) < 4.2) ptxt = 'F — TRADE WITH FENWICK';\n"
    "        else if (this.paul && me.pos.distanceTo(this.paul.pos) < 3.6) ptxt = 'F — TALK TO BALL PELLINGER';\n"
    "        else if (this.furnace && me.pos.distanceTo(this.furnace.pos) < 3.2) ptxt = this.smelting ? 'F — STOP SMELTING' : 'F — SMELT IRON ORE';\n"
    "        else if (this.anvil && me.pos.distanceTo(this.anvil.pos) < 3.0) ptxt = 'F — FORGE (10 IRON BARS)';\n"
    "        else if ((this.sheep || []).some(s => me.pos.distanceTo(s.g.position) < 2.2)) ptxt = 'F — SHEAR SHEEP';\n"
    "      }",

    "    if (this.promptRef.current) {\n"
    "      let ptxt = '';\n"
    "      if (world && this.started && me.hp > 0) {\n"
    "        const pick = this.bestInteract();\n"
    "        ptxt = pick ? pick.label : '';\n"
    "      }",
    'prompt')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
