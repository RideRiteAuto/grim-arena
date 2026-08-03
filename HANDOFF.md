# Grim World — Developer Handoff

**SOURCE OF TRUTH: `index.html` / `grim-arena-standalone.html` (identical bundles).**
`Grim Arena.dc.html` is STALE (last true at the Aug 2 spell-wheel commit) and must
NOT be edited or used to rebuild — doing so would erase everything after 3pm Aug 2
(Northreach, shared world, music, knight rework, Inventory 2.0, loot sacks).
Edit the bundles via `repack.py`:

    python3 repack.py extract   # game doc -> /tmp/game-src.html
    (edit /tmp/game-src.html)
    python3 repack.py pack      # writes BOTH bundles, verifies round-trip

The bundle embeds the game document as a JSON string; `repack.py` escapes `</`
so the payload cannot terminate the outer script tag.

## Inventory 2.0 (Aug 3)

- `ITEMS()` registry: every item has stack/slot/hands/wieldAs/stats/value/icon.
  **An item without an icon throws at boot.** Add art in the registry, nowhere else.
- State: `inv` (28 slots), `worn` (HEAD/AMULET/WEAPON/BODY/SHIELD/LEGS), `bar`
  (6 item IDS, never items), `overflow` (surplus pouch, auto-refills).
  Persisted as `grim-inv-v1`; legacy `grim-wallet` migrates once, losing nothing.
- EVERY mutation goes through `invCommit(fn)`: snapshot -> mutate -> `invValidate()`
  -> save. Violations revert wholesale. Use `invSimulate(fn)` for prechecks.
- `addItem` is capacity-aware (returns amount added). `grantItem` is for rewards:
  spills to overflow, never blocks, never destroys. `takeItem` is atomic.
  `hasItem` checks pack AND worn — use it for ownership gates (the anvil dupe).
- Crafting prechecks room BEFORE consuming inputs (`craftAtAnvil`, smelt loop).
- Combat: `armourCut()` = DEF/(DEF+110) capped 0.60; `styleDamageMult` from
  STR/MAG/RNG. Keys 1-6 call `switchWeapon` which EQUIPS the bar-bound item.
- Panel: `toggleWallet` (TAB). Drag logic in `bindInvPointer`; ops are
  `moveSlot/splitStack/equipFromSlot/unequipSlot/unequipToSlot/bindBar/
  dropFromSlot/sortInventory`. Sort is a pure permutation.

## Loot sacks (Aug 3)

- Authority = host, or yourself when not `connectedAsClient()` (broker down =>
  local sacks; this also fixed offline NPC lifecycle, see authority gates).
- Protocol: client `lreq{id,e,q,tok}` -> host validates (exists, qty, ownership
  window, token unseen) -> `lok` to that client only (grant happens ONLY here)
  + `skupd` broadcast. `sknew` on spawn + on late join. `skgone` on empty/expiry.
- Killer-owned 60s, public 180s more, sink+fade last 15s, 40-sack cap.
- Loot tables: `lootEntriesFor(tag)`; quest credit: `questCreditFor(tag)` on the
  killer's machine via `ndead` (unchanged flow).

## Testing

- `/tmp/fuzz.js` (conservation fuzz, migration), `/tmp/ui-test.js`,
  `/tmp/drag-test.js` (real pointer events), `/tmp/sack-test.js`,
  `/tmp/net-test.js` (two browsers + local PeerJS broker on :9944).
  Serve via http with three.js importmap pointed at a local copy — unpkg is
  unreachable from the sandbox, and file:// never fires three-ready.
- Instance handle: `window.__grim`. World init runs in `boot()`, so wait for
  `Array.isArray(__grim.inv)` before poking inventory.

## Older architecture notes

HANDOFF-v9.md still describes the world/quests/netcode accurately EXCEPT
anything about `Grim Arena.dc.html` being the source (it is not) and the old
wallet (replaced). Wire IDs and save keys deliberately keep legacy names
(`grim-arena/`, `grim-duel-`, `grim-gaylinor-world-v1`, `grim-*` storage):
renaming them would break co-op between copies and wipe player saves.
