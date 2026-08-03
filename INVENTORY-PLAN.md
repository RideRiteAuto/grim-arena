# Grim World, OSRS-style Inventory and Equipment: Design Outline

Written before any code changes, for review.

---

## 1. What exists today

I read the live build rather than the stale source. Current state:

| Thing | How it works now |
|---|---|
| Inventory | `this.wallet = {ITEM: count}`, a plain dict. Unbounded. No slots, no order. |
| Mutation | `addItem(item,n)` and `takeItem(item,n)` only. `takeItem` is already atomic (all or nothing). |
| Persistence | `localStorage['grim-wallet']`, sanitised on load by `sanitizeWallet()`. |
| Armour | Implicit. `recomputeArmour()` reads *ownership*: own HOLLOW PLATE means tier 3. No equipping. Cuts damage 0/10/20/32%. |
| Weapons | `me.weapon` is an index 0-5 bound to keys 1-6. Not an inventory slot. Cleaver gated on owning the item. |
| Ground drops | `this.drops[]` plus `spawnDrop(pos,item)`. Always quantity 1. Auto pickup within 1.5m. Client-local, never networked. |
| Floating text | `splat(worldPos,text,kind)` with `splatSlot()` collision avoidance already built, plus `queueXpToast`/`flushXpToasts` aggregation. |
| Trader | Fenwick, buy and sell against GOLD CROWNS. |
| Co-op | Host-authoritative NPCs. Loot awarded only on the killer's client (`onSharedKill` returns early unless `m.killer === myId`). Resources use a `rhit`/`rdead` request-response. |

**The good news:** `addItem`/`takeItem` already being the single chokepoint is exactly the "centralized validation" pattern the dupe literature recommends. We are building on a sound base, not a pile of scattered mutations.

---

## 2. Target design

### 2.1 Data model

Replace the dict with an explicit slot array, and add a worn set.

```
inv       = Array(28) of null | { item: 'IRON ORE', qty: 12 }
worn      = { HEAD, AMULET, WEAPON, BODY, SHIELD, LEGS }   // each null | { item, qty:1 }
ITEMS     = registry, one entry per item id
```

Registry entry shape:

```
'IRON SCIMITAR': {
  name: 'IRON SCIMITAR',
  stack: false,
  slot: 'WEAPON',        // null for non-equippable
  hands: 1,              // 1 or 2, WEAPON only
  style: 'melee',        // melee | magic | ranged, drives which weapon key it maps to
  stats: { att: 8, str: 9, def: 0, mag: 0, rng: 0 },
  icon: '<div .../>',    // reuse the existing inline-CSS icon style
  value: 60              // trader base price
}
```

Grid is 4 wide by 7 tall, index `0..27`, row-major. Slot index is the identity for drag operations.

### 2.1b Item thumbnails (every item, no exceptions)

Every slot in the grid, the worn panel, the action bar and the loot sack window shows a **thumbnail image** of the item, with the quantity overlaid bottom-right in OSRS style. A grid of text labels is unreadable and this is a hard requirement, not polish.

How they get made, keeping the game's zero-asset-download rule:

- **Every registry entry MUST carry an icon.** The registry loader throws at boot in dev if any item lacks one, so a new item without art cannot ship silently. Unknown items at runtime (say, from an old save) render a fallback "?" tile rather than an empty square.
- The game already draws 14 hand-styled CSS icons in the old wallet (logs, ore, bars, crowns, pelts, tomes...). Those survive and get reused.
- All **new** gear icons are drawn as small inline SVGs in the same flat-shaded, dark-outlined style: iron full helm, platebody, platelegs, scimitar, kite shield, staff, bow, pickaxe, axe, cleaver, amulets. SVG scales crisply at both the 34px grid size and the larger paper-doll size, and stays consistent with the existing look.
- Icons are keyed by item id in one `ICONS` map owned by the registry, so the grid, worn panel, bar, sack window, tooltips and pickup toasts all pull from the same source. One item, one image, everywhere.
- Tint variants (iron vs steel vs future tiers) are the same SVG with a palette swap, so a whole new metal tier costs one colour set, not ten drawings.

A fancier option exists — offscreen-rendering each item's actual 3D mesh to a data-URL at boot — but most items have no world mesh (ore, hides, food), lighting varies, and boot cost grows with the registry. Hand-drawn SVG in the established art style is more readable at 34px anyway. Recommend SVG now; a 3D-render pipeline can replace individual icons later without touching any consumer code.

### 2.2 Stacking rule

Recommendation: **everything stacks except equippable gear.** Ore, logs, gold, hides, food collapse into one slot with a quantity. Helmets, bodies, legs, weapons, shields, amulets take one slot each.

That is the OSRS feel, and it is what gives the equipment screen a reason to exist. It is a single boolean per registry entry, so flipping to "everything stacks" later is a one-line change per item.

### 2.3 Equipment slots

Exactly the six you asked for: **HEAD, AMULET, WEAPON, BODY, SHIELD, LEGS.** Adding BOOTS and GLOVES later is additive, no refactor.

Two-handed rule:
- Staff, bow and GRIM CLEAVER are 2H. Iron scimitar is 1H.
- Equipping a 2H weapon moves the shield to inventory first.
- If the inventory has no free slot for the displaced shield, **refuse the equip** with "NOT ENOUGH ROOM". This is the exact OSRS behaviour and it is a classic dupe vector when done sloppily.
- Equipping a shield while a 2H weapon is worn does the mirror.

### 2.4 Stats

Five per item: **ATTACK, STRENGTH, DEFENCE, MAGIC, RANGED.** Totals summed across worn gear and shown on the panel.

Wiring into combat:
- **DEFENCE** replaces the current flat `armourCut()` tier table. Diminishing-returns curve, hard cap around 60% so gear can never trivialise a fight.
- **STRENGTH** becomes a melee damage multiplier.
- **MAGIC / RANGED** multiply their own styles' damage.
- **ATTACK** is displayed and used for damage weighting, but I recommend **no accuracy roll**. OSRS misses constantly because it is a tick-based MMO. Your game is a real-time action game where the player aims manually. Adding random whiffs would fight the combat feel you have spent seven hours tuning.

### 2.5 Default kit

IRON FULL HELM, IRON PLATEBODY, IRON PLATELEGS, IRON SCIMITAR, IRON KITE SHIELD, no amulet.

Granted once, guarded by a `grim-starter-v1` localStorage flag so it is idempotent. Granting starter gear on every load is itself a dupe.

---

## 3. Migration (existing players)

Anyone with a `grim-wallet` today has an unbounded dict. On first load of the new build:

1. Read the old dict, sort by registry order.
2. Fill slots. Stackables take one slot each, non-stackables take one slot per unit.
3. Auto-equip the best owned armour so nobody loses the protection they had (their HOLLOW PLATE was cutting damage by ownership before, it should keep working).
4. Grant starter kit only for slots still empty, then set `grim-starter-v1`.
5. **Overflow beyond 28 goes to `grim-overflow`**, a holding list that auto-refills into the pack as slots free up, with a HUD note. Nothing is ever deleted. I do not want a migration that eats someone's Hollow Plate.

---

## 4. Ground loot

NPC deaths currently push loot straight into the wallet. New behaviour: the loot table spawns as a physical pile.

Entity: `{ id, item, qty, pos, gy, t, ownerPeer, ownerUntil }`

**Recommendation: keep ground loot client-local, killer-owned, for now.** Loot is already awarded only on the killer's machine, so a local-only pile is structurally dupe-proof: no other client can ever see or claim it. Piles despawn on the existing 150s timer.

Public shared piles (where a friend can pick up your drops after a timer) require a host-authoritative claim protocol:

```
client -> host : pickreq {id}
host           : validate pile exists AND unclaimed -> mark claimed
host -> client : pickok {id, item, qty}     (to exactly one requester)
host -> all    : pickgone {id}
client         : addItem ONLY on pickok, never on local proximity
```

That is the correct design and I have specced it, but it is a distributed consensus problem for a feature you have not asked for. I would not take that risk on day one. Easy to add later.

Pickup itself stays proximity-based (no new keybind), with two changes: it respects capacity, and a full pack shows a throttled "PACK FULL" toast instead of silently eating the item.

---

## 5. Pickup toasts

You want them near the inventory, floating up and fading, stacking rather than overlapping.

The game already solves the overlap problem for combat text in `splatSlot()`. I will add a screen-space sibling that reuses that slot-stacking logic, anchored bottom-right near the inventory button, with the same rise-and-fade animation.

Rapid pickups aggregate the way XP already does via `queueXpToast`, so chopping a tree reads as one "+3 OAK LOGS" line rather than three stacked lines.

---

## 6. Foreseen problems and how each is handled

### 6.1 The bug I would otherwise have shipped

Quest and shop logic calls `invCount('GRIM CLEAVER') > 0` and `invCount('TOME OF STORMS') > 0`. Once items can be **worn**, an equipped cleaver is no longer *in* the inventory, so `invCount` returns 0 and **the questline silently breaks.**

Fix: introduce `hasItem(id)` that checks inventory *and* worn, and audit all 15-odd call sites. Same applies to `applyCleaver()`, the spell wheel's storm gate, the Ball Pellinger quest markers and Fenwick's stock checks.

### 6.2 Duplication vectors, each with its mitigation

| Vector | Mitigation |
|---|---|
| Add-before-remove interrupted | **Transactional apply.** Clone state, mutate clone, validate invariants, commit in one assignment. Never partial. |
| Drag handler firing twice (`pointerup` and `click`) | Single `pointerdown/move/up` flow with a `dragToken` nulled on first handle. `click` ignored entirely. |
| Stale slot index after a re-render mid-drag | Drag payload carries `{slotId, item, qty, stamp}`. On commit, re-validate the slot still holds that exact item and quantity. Mismatch aborts the whole operation. |
| Two browser tabs open (very likely, since shared world encourages it) | Drop an item in tab A, tab B still holds it in memory and saves over you. Guard with a `BroadcastChannel` ownership lock and an "ANOTHER TAB IS PLAYING" notice. |
| Trader sell firing twice | Same token/atomic path as drag. Sell is remove-then-credit, never credit-then-remove. |
| Smelting loop adding IRON BAR per tick into a full pack | Capacity-aware `addItem` returns the amount actually added. Loop halts when it returns 0. |
| Starter kit granted repeatedly | `grim-starter-v1` idempotency flag. |
| 2H equip displacing a shield into a full pack | Refuse the whole operation. Never "equip anyway and vanish the shield", never "equip and clone it". |
| Co-op double pickup | Avoided entirely by keeping piles client-local (section 4). |

### 6.3 Structural safeguards

**Invariant checker** run after every mutation:
- exactly 28 slots
- each slot null or `{item, qty}` with integer qty > 0
- non-stackables always qty 1
- every item id exists in the registry
- worn slots only hold items whose `slot` matches
- never a 2H weapon and a shield at once

Violation logs loudly and reverts to the pre-mutation snapshot. Shipped behind a flag so it stays on in the wild for a while.

**Conservation fuzz test.** A headless harness that runs a few thousand randomised operations (pickup, drop, equip, unequip, reorder, sell, smelt, drag-abort mid-flight) and asserts that total item counts only ever change by the intended delta. This is the thing that actually catches dupes, rather than hoping to notice one by hand.

### 6.4 Integration details that will bite if ignored

- **Pointer lock.** The game holds pointer lock for mouse look. Drag and drop needs a cursor. Opening the panel must release lock and closing must re-acquire it, or dragging will not work at all.
- **TAB key** currently opens the "CYBER WALLET". That panel gets replaced, not duplicated.
- **Armour visuals.** `applyWeaponVisuals(e)` swaps weapon meshes. Worn armour should eventually drive the rig's materials too. Recommend stats-only in v1, visual gear as a follow-up, so we do not couple a data refactor to a modelling job.
- **Net state.** `myWorldState()` sends `w: me.weapon`. Other players should ideally see your worn gear. Recommend deferring; it is additive and costs bandwidth.

---

## 7. Build order

1. Item registry, slot model, migration, invariant checker, and the fuzz harness. No UI yet.
2. Equipment model, 2H rules, stat totals, combat wiring, and the `hasItem()` audit across quests and shop.
3. Combined panel UI: paper-doll plus 4x7 grid plus stat readout, drag to equip, unequip, reorder and drop.
4. Ground loot piles and pickup toasts.
5. Fuzz test, then headless play-through, then hand it to you.

Phase 1 lands with tests before any of it is visible, which is deliberate. The dupe bugs live in the data layer, not the UI.

---

## 8. The action bar

Today the bar is six hardcoded slots (`slot0Ref`..`slot5Ref`) with fixed meanings: blade, staff, bow, pickaxe, axe, cleaver. `me.weapon` is an index, and `applyWeaponVisuals()` shows one of six fixed meshes.

You want to drag swords, staves, bows and shields onto it. The design that makes that safe:

**The action bar stores item ids, not items.** It is a view into the inventory, never an owner.

```
bar = ['IRON SCIMITAR', 'OAK STAFF', null, 'IRON PICKAXE', 'IRON AXE', 'GRIM CLEAVER']
```

Because a bar slot is a *reference*, binding one can never create or destroy an item. This removes the single largest dupe risk in the whole feature, structurally rather than by careful coding.

Behaviour:
- Dragging an item from the inventory or the worn panel onto a bar slot binds its id. The item does not move.
- Pressing the key equips that item into whatever worn slot its registry entry names. A sword goes to WEAPON, a shield goes to SHIELD. Weapon switching and equipping become the same operation.
- If you no longer hold the bound item, the slot greys out and the key does nothing. No error, no phantom weapon.
- Bar layout persists in `grim-bar`.

To keep combat and meshes working, every wieldable registry entry carries `wieldAs: 0..5`, the existing archetype index. An IRON SCIMITAR and a future STEEL SCIMITAR both use `wieldAs: 0`, so they share the moveset and mesh while having different stats. Frame data in `cfg().MOVES` is untouched.

---

## 9. Crafting: furnace and anvil

This is where a naive capacity implementation destroys items rather than duplicating them, which is worse because players do not report it, they just quietly lose a Hollow Plate.

**Smelting** currently runs `takeItem('IRON ORE',1)` then `addItem('IRON BAR',1)` every 1.1s. With a 28-slot cap, a full pack makes the `addItem` fail **after** the ore is already gone. The ore is destroyed for nothing.

Fix: a `canAccept(item, qty)` precheck runs *before* the take. No room means smelting halts with "PACK FULL" and the ore is never consumed. Remove-then-add is the right order for dupe safety, but it must be gated by a precheck to also be loss-safe.

**Forging** runs `takeItem('IRON BAR',10)` then `addItem('GRIM CLEAVER',1)`. Subtle case: taking all 10 bars from a stack of exactly 10 frees that slot, so the cleaver fits. Taking 10 from a stack of 15 leaves the slot occupied, so the cleaver needs a *new* slot and can fail on a full pack. Same precheck, computed against the post-consumption state.

**A live dupe this feature would otherwise create.** `tryForge()` guards with `invCount('GRIM CLEAVER') > 0`. Once the cleaver can be *equipped*, it leaves the inventory, `invCount` returns 0, and **the anvil will happily forge you a second one.** Repeat forever. This does not exist today only because nothing can be equipped. It becomes exploitable the moment we ship equipment, so the `hasItem()` audit from 6.1 is not a nicety, it is load-bearing.

Same shape applies to `applyCleaver()`, which sets `me.cleaver` from ownership and should read "cleaver equipped" instead.

---

## 10. Quest rewards and drops

Quest advancement calls `addItem('TESLA PAYCHECK', 3)` and similar inline with stage changes. `awardKillLoot()` grants gold plus items. The Hollow King grants HOLLOW PLATE.

A full pack must never make a quest reward vanish, and must never block a quest from completing. Those are both worse failure modes than a dupe from the player's point of view.

Single unified answer: **`grantItem(item, qty)`**, used by every reward path.

1. Try the inventory.
2. Whatever does not fit spawns as a ground pile at the player's feet.
3. Toast either way, so the player always sees what they got and where it went.
4. Quest stage advances regardless. A full bag never soft-locks a questline.

Every current `addItem` call site in quest, loot and shop code moves to `grantItem`. Gathering and smelting keep the strict capacity-gated path, because there the correct behaviour is "stop, you are full", not "drop it on the floor".

---

## 11. Loot sacks (shared, interactive)

Replaces section 4. You chose shared piles, so the safe version has to be built properly.

### 11.1 Behaviour

An NPC dies and leaves a **loot sack** where the body fell. Walk up, press E, a panel opens showing its contents beside your inventory. Take what you want, leave the rest for a friend. Unlooted sacks fade out on a timer so the map does not fill with bags.

- **Ownership window:** for the first 60s only the killer can open it, and the sack glows gold for them. After that it turns grey and anyone can loot it. This is the standard MMO answer and it stops a teammate sniping your boss drop.
- **Despawn:** 3 minutes from the moment it becomes public, with the sack visibly sinking and fading over the last 15s so it never vanishes without warning. Taking an item resets nothing, an empty sack disappears at once.
- **Cap:** oldest sack is culled past 40 live sacks, so a long grind session cannot leak memory or bandwidth.

### 11.2 The claim protocol (this is the dupe-critical part)

Shared containers are the single most duped thing in multiplayer games, because two clients can both believe they took the last item. The fix is that **clients never decide, they only ask.**

```
sack   = { id, pos, ownerPeer, publicAt, dieAt, entries: [ {e, item, qty} ] }
id     = hostSessionId + ':' + monotonic counter     // survives host churn without collisions

client -> host : lootreq { s, e, qty, token }        // token is client-unique
host           : validate sack exists
                 validate entry exists and entry.qty >= qty
                 validate requester allowed (owner, or now public)
                 validate token unseen          <-- kills double-send
                 decrement entry, drop entry at 0
host -> one    : lootok  { token, item, qty }
host -> all    : lootupd { s, e, qty }               // display only
client         : grantItem() ONLY on lootok
```

Three rules that make duping structurally impossible rather than merely unlikely:

1. **Only `lootok` grants an item, and only to the client that owns that token.** `lootupd` is a redraw, never a grant. Getting this backwards is the classic shared-chest dupe.
2. **No client-side prediction.** The slot shows a brief pending state until the host answers. Loot windows are not twitch gameplay, a round trip is invisible.
3. **The host takes loot through the same function**, called locally instead of over the wire. One code path, so the host cannot have its own private bug.

Token dedupe uses a short-lived seen-set (10s), which covers packet retries and mashed clicks. A dropped reply loses an item rather than duping one, and losing beats duping every time.

**Host migration:** sacks live in host memory. When the host leaves, PeerJS elects a new one and its sack registry starts empty. Live sacks therefore vanish on migration. I would rather be upfront about that than invent a fragile sack-handoff. If it becomes annoying, the fix is persisting sacks to the world snapshot, which is a contained follow-up.

**Removing the old path:** the killer's client currently calls `spawnDrop()` directly. That must go, or a kill produces both a local pile and a networked sack, which is a dupe by construction.

---

## 12. Dropping, splitting and quick transfer

### 12.1 Dropping from the inventory

Dragging an item out of the panel drops it at your feet as a one-entry sack, owned by you, on the same despawn timer.

Every drop shows a **5 second undo** toast. Undo re-claims through the normal `lootreq` path, so the safety net cannot itself dupe. This matters because one mis-drag of a Hollow Plate with no bank to recover it from is a rage-quit.

### 12.2 Splitting

Shift-drag a stack, or right-click and choose Split, to open a quantity picker (slider plus 1 / 10 / Half / All buttons).

Guards, because split is a classic dupe:
- quantity must be an integer with `1 <= q < stack.qty` (splitting the whole stack is a move, not a split)
- a free slot must exist before anything is decremented
- the whole thing is one transaction, validated then committed, never a decrement followed by a separate insert

### 12.3 Quick transfer hotkeys

| Input | In inventory | In an open loot sack |
|---|---|---|
| Left click | select | take that stack |
| Shift + click | equip if equippable, else nothing | take all of that item type |
| Ctrl + click | drop one | take one |
| Right click | menu: Equip / Split / Drop | menu: Take / Take all |
| Drag | move, equip, or drop outside the panel | drag to inventory |
| Shift + drag | split | split-take |
| E | open or close the nearest sack | take everything that fits |

"Take everything that fits" is deliberate wording. A full pack takes what it can and leaves the rest in the sack rather than destroying the remainder.

### 12.4 On-screen control legend

You asked for the buttons to be labelled, and this is the right call given how much is bound. Three layers:

1. A permanent footer strip across the bottom of the panel showing the table above, styled like the existing HUD (mono, `#7d8a63` on dark).
2. Hover tooltips on every slot giving the item name, its stats, and what a click will do right now.
3. A first-open overlay, once ever, pointing at the grid, the paper doll and the action bar. Dismissed forever after, tracked in `grim-invtut-v1`.

---

### 12.5 Sort button

A SORT button on the panel header (hotkey R while the panel is open). Order: worn-slot gear first (weapons, then shields, then armour by slot), then tools, then resources, then food, then quest items, alphabetical within each group, stacks merged if any got fragmented. Runs as one transaction through the same validator as everything else, and the invariant checker asserts the exact same multiset of items exists after the sort as before it. A sort must be a pure permutation, which makes it trivially fuzz-testable.

---

## 13. Confirmed decisions

| Question | Decision |
|---|---|
| Gear stackable | **No.** Gear takes a slot each, everything else stacks. |
| Death penalty | **None.** No item loss on death for now. |
| Co-op loot | **Shared interactive sacks**, per section 11. |
| Accuracy rolls | **No random misses.** ATTACK weights damage instead. |
