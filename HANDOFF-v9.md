# Grim World (Grim World) — Project Handoff

Current version: **v9.3** · August 2, 2026
Single-file browser game: RuneScape Dragonwilds-style third-person action combat, open world, co-op multiplayer.

## Files
- `Grim World.dc.html` — THE source file. Everything (template UI + game logic) lives here (~3,900 lines).
- `grim-arena-standalone.html` — compiled self-contained build (~630 KB). This is what players open. Never edit it directly; rebuild it from the source file.
- `HANDOFF.md` — earlier architecture notes (v5 era); this file supersedes it for current state.

## How to play / distribute
- Open `grim-arena-standalone.html` in any modern browser (Chrome/Edge best). No server, no install.
- Solo: PLAY NOW button.
- Co-op: one player clicks HOST WORLD · CO-OP → gets a 4-letter code; the other opens their own copy of the same file and enters the code via JOIN. Networking is WebRTC P2P with an automatic relay fallback (~6 s) for restrictive office networks.
- Each player needs their own copy of the HTML file (send via Teams/email) — there is no persistent hosted URL.

## Architecture (all inside Grim World.dc.html)
- Rendering: three.js (pinned import in `<helmet>`; `window.THREE`, ready-flag `window.__threeReady`). Low-poly flat-shaded meshes, procedural canvas textures, fog, hemisphere+directional light with shadows.
- The logic is one `Component extends DCLogic` class. Key subsystems (grep for these method names):
  - `buildWorld` / world builders — terrain with elevation (`groundY(x,z)` is THE ground-height function; everything must sample it), arena centerpiece, main road to the bog, swamp/lake/mere, trees, iron rocks, bushes (walk-through, no collider), furnace + anvil near spawn.
  - `makeKnight` etc. — character rigs; `e.parts` holds named limbs/weapons. Weapon grip convention: weapons parented to `hand`, `rotation.set(Math.PI/2, -Math.PI/2, 0)` = blade horizontal forward.
  - `driveLocal` / `driveAI` / `wander` — player input & NPC AI. `stepCamera` — orbit camera, terrain-aware.
  - `pickTarget(combatOnly)` — camera-facing scored targeting; lock-on (`this.lockOn`, key E) only engages aggroed foes and releases on target death.
  - `startMove` / `swing` / `meleeCheck` / `animate` — combat. Move table in `swing`/`startMove`: light/heavy (scimitar), frost/fire/water (staff, C cycles element), charge/rapid (bow), chop/mine (axe/pick), glight/gheavy (Grim Cleaver 2H, slot 6, gated on owning the item).
  - Shield: hold RMB with sword = block; chip damage drains stamina; guard break at 0; parry window on raise.
  - `applyDamage` — hit splats (RS-style), XP, death/respawn, drops (TESLA PAYCHECK from bosses).
  - Inventory "CYBER WALLET" (Tab): `addItem`/`invCount`, dupe-safe, persisted in localStorage. Skills/XP: COMBAT, WOODCUTTING, MINING, SMITHING.
  - Quests (`quests` array + tracker HUD): Daily PMs (10 goblins), track & kill Mr. Sailers, mine 10 ore → smelt 10 bars (furnace) → forge GRIM CLEAVER (anvil).
  - Mounts: killing Mr. Sailers grants donkey riding (hotkey labeled on HUD; lost on death). Seat offset 0.42.
  - NPCs: Ball Pellinger (quest giver, spawn), Alexis Ayala ("buying gf"), roaming knights (Austin Little — easy, Steven Carrasco, Kevin Coelho), non-aggressive goblins, ambient woodcutter/miner workers with periodic chatter, Mr. Sailers (donkey-riding snare-caster, gibberish shouts), Plague Rat boss (bog, poison).
  - Netcode: `netStage`, host-authoritative co-op; partner health bar, minimap with partner marker.
- Difficulty select on menu (squire/veteran/champion). Sounds are WebAudio-synthesized (`tone`/`sfx`), menu is silent.
- Player prefs (color, difficulty, wallet, skills) persist in localStorage keys prefixed `grim-`.

## Known quirks / next ideas
- Public share links minted from this environment expire in ~1 hour — regenerate as needed, or just send the file.
- HUD weapon slots 1–6 map to keys; key layout tuned for US laptop keyboards.
- Backlog the user has mentioned: more zones/content, more quest chains, better co-op world-state sync for NPC deaths.

## Rebuilding
Edit `Grim World.dc.html`, then bundle it into `grim-arena-standalone.html` (self-contained inline build) and distribute that file.
