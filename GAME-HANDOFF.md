# Grim World — full agent handoff

Read this top to bottom before touching anything. It is current as of the
night of August 3, 2026 and describes how the game is built, how it ships,
every system that exists, what is in flight, and the rules that keep the
project from breaking. The companion document SERVER-SIM-PLAN.md is the
approved blueprint for the next major piece of work.

---

## 1. What the game is

Grim World: a browser 3D co-op action RPG Kevin is building as a side project.
OSRS-inspired systems (skills, quests, bank, loot), souls-lite combat (wind-up
/ dodge / block / stamina), shared open world with friends. Played at:

- **Live game:** https://rideriteauto.github.io/grim-arena/
- **Repo:** github.com/RideRiteAuto/grim-arena (branch `master`)
- **Multiplayer server:** https://grim-arena.kevin-230.workers.dev (Cloudflare Worker)
- **Cloud saves:** Supabase project `nstrktevfxyiiodyeegf.supabase.co`

Kevin plays with at least one friend (ELDER) on a different network. His hard
requirements, in his words: no duplication glitches ever, monsters and bosses
must attack at the same moment on every screen so players can dodge together,
nothing that depends on a single player's computer, and nothing that costs
money beyond the free tiers he already has.

## 2. How the code is organized (unusual — read carefully)

The ENTIRE game is one self-contained HTML bundle. There is no build system,
no node_modules, no modules.

- `index.html` and `grim-arena-standalone.html` — identical bundles, both
  committed, both must always be updated together. GitHub Pages serves
  index.html.
- The actual game source lives EMBEDDED inside the bundle as a JSON string at
  ~line 390. You do not edit the bundle directly.
- `repack.py` — the only edit path. `python3 repack.py extract` writes the
  editable source to /tmp/game-src.html; `python3 repack.py pack` re-embeds it
  into BOTH bundles and verifies a byte-exact round trip. It escapes `</` as
  `</` — this escaping is load-bearing; an unescaped `</` terminates the
  script tag and bricks the page.
- `Grim Arena.dc.html` in the repo is a STALE legacy artifact. Never edit it,
  never rebuild from it.
- The game is a single class (React-style component on a tiny DCLogic base).
  three.js r160 loads from unpkg via importmap. World/init runs in `boot()`
  after three.js arrives, NOT in the constructor. `window.__grim` is the
  debug/test handle to the live instance.
- Edits are made with Python patch scripts against exact-string anchors
  (assert count==1 before replacing). Always re-grep the current text before
  patching; anchors go stale fast.

## 3. How it ships

One push to `master` deploys everything:

1. GitHub Pages redeploys the game (~1 minute).
2. Cloudflare **Workers Builds** is connected to the same repo and
   auto-deploys `relay-worker.js` as the Worker named `grim-arena`. The `name`
   field in `wrangler.jsonc` MUST stay `grim-arena` or builds fail.

Convention Kevin insists on: every shipped change updates `PATCH-NOTES.md`
(newest entry on top, plain language, honest about what was broken) so he can
refresh and see what is done. Ship work in small pushes as you go, not one big
drop.

## 4. Multiplayer architecture (rebuilt from scratch today)

History you need: the game began peer-to-peer (PeerJS + host election). That
design produced weeks of outages — squatted broker ids, split worlds, frozen
hidden-tab hosts, NAT-blocked players — and was replaced today. The old peer
code still exists in the file as a dead fallback path; ignore it.

Current design:

- **Transport:** every player holds ONE WebSocket to a Cloudflare Durable
  Object (`relay-worker.js`, class `World`, one instance per world name,
  `/world/main` is the world everyone uses). No peer-to-peer anything.
- **Hibernation-safe:** the DO stores nothing in memory. All per-player state
  rides the socket attachments; world state lives in `state.storage`. A DO
  restart is invisible to players. This is not optional style — in-memory
  state silently vanishes and has already caused a both-players-think-they-
  host bug once.
- **Protocol 5** (client checks `proto` in the welcome message). The relay
  validates every message: only listed types forward, monster-truth types are
  owner-only, per-player rate limit 60 msg/s, sender id stamped server-side as
  `_p` (never trusted from the client, and never clobbering the game's `i`
  NPC-index field — that collision was today's worst bug).
- **Server-authoritative combat (shipped today):** monster HEALTH, death,
  kill credit, LOOT rolls, sack ownership windows, sack expiry and respawn
  timers all live in the DO. Clients send `nhit` (I hit monster #i for d);
  the server answers with `nhp` broadcasts, `ndead`, `sknew/skupd/skgone`,
  `lok/lno` loot grants. Respawns/expiry run on storage alarms so they fire
  even with nobody online. Nobody can forge deaths or grant themselves loot.
- **Positions (current interim state):** one connected player is the "sim
  owner" (server-elected, sticky flag on the socket attachment) and broadcasts
  monster positions at 10Hz; everyone else mirrors that feed exactly. Owner
  handover is automatic: on disconnect, on the tab going hidden (client sends
  `yield`; server only ever hands ownership to a VISIBLE player), and on 8s of
  silence. Measured cross-screen drift after today's fixes: mean 0.6m, worst
  2m, no animation-state disagreements. A >4m error snaps instead of sliding.
- **Fallbacks that must not be broken:** if the socket drops, the client
  falls back to full local simulation (otherwise the player can't fight at
  all — that bug happened today); on reconnect it re-registers and re-syncs
  monster state from the server.

## 5. The next major work (approved, not started): full server simulation

Kevin's decision on record: monster MOVEMENT and ATTACK TIMING also move into
the Durable Object, so no elected player exists at all and every screen sees
the same fight. Each player's own dodge is judged on their own machine against
what they saw (co-op standard; no lag-compensation rewind).

**SERVER-SIM-PLAN.md is the buildable blueprint** — five phases, each
shipping alone with acceptance tests: (1) shared rules generation + world
manifest + clock sync, (2) server movement + interest-filtered snapshots,
(3) scheduled attack events + local dodge judgment, (4) server-spawned
projectiles, (5) data-scripted bosses. Scalability comes from monsters being
data (archetypes) and bosses being scripts (phased move tables) rather than
code. Read that file before proposing changes to it.

## 6. Accounts, saves, and the bank

- RSPS-style: username + password on the menu auto-creates a character;
  username IS the character name (shown on the HUD nameplate).
- Client hashes SHA-256(`grim:user:pass`); Supabase RPCs `grim_login(u,h)` /
  `grim_save(u,h,s)` (security-definer, RLS locked, no direct table access).
  The publishable key baked into the bundle is public-by-design. NEVER accept
  or embed a service_role key anywhere.
- Saves: debounced 4s + 45s interval + pagehide keepalive. Guest mode saves to
  localStorage only and is clearly labeled.
- LOG OUT button on the pause menu (Escape): flushes the save, hands the world
  back, reloads to a clean login.
- Bank in Northreach (booth + teller NPC): one merged stack per item kind,
  transactional deposit/withdraw inside the same commit system as the
  inventory.

## 7. Inventory and items (the dupe-proofing Kevin cares most about)

- 28-slot pack + worn equipment (HEAD/AMULET/WEAPON/BODY/SHIELD/LEGS),
  2H weapons occupy WEAPON and force the shield off (and auto-re-equip it on
  swap back).
- EVERY mutation goes through `invCommit(fn)`: snapshot → mutate →
  `invValidate()` → save, wholesale revert on any violation. `grantItem`
  spills to an overflow pouch rather than destroying anything. Crafting
  prechecks space BEFORE consuming inputs. Multi-stack splitting is allowed;
  sort re-merges. If you add any item-touching feature, it goes through
  invCommit or it does not ship.
- Every item MUST have a thumbnail icon: the registry throws at boot if one is
  missing. This is deliberate; do not remove the check.
- Loot arrives as shared ground sacks (server-owned, killer-claim 60s, then
  public, then expires).

## 8. UI systems as of tonight

- **Action bar (redesigned today):** ONE bar, bottom of screen, six slots.
  Drag items from the pack onto it, drag between slots to rearrange/swap,
  drag off or right-click to unbind, click a slot OR press 1-6 to use.
  Bindings persist in the save. The bar sits at z-index 75, lifted to
  document.body because the HUD wrapper is its own stacking context (the
  inventory panel is z 70 — do not "fix" this by lowering the bar).
- Inventory (Tab), game visible behind panels, Escape = pause menu with
  RESUME / LOG OUT, scroll wheel cycles bound weapons, right-click context
  menus, tooltips, split-stack picker, bank/shop/sack windows.
- Status line under the title shows the connection state (CONNECTING /
  HOSTING / CONNECTED / RECONNECTING...) — keep it accurate; it is the main
  remote-debugging tool.

## 9. World content (for design conversations)

53 NPCs in a DETERMINISTIC boot order (all network messages address monsters
by index — never reorder spawns). Zones: starting grassland + Northreach
(safe town), Hollowrest, a swamp/bog with the Plague Rat, wilderness with
wolves/deer/bandits/wraiths. Bosses: The Hollow King (slam + leap,
drops the strength/crit Hollow Amulet), Mr. Sailers (snare spell, charge,
volley, quest boss), Austin Little (brawler: leap/bash/flourish), The Plague
Rat. Quest line runs through Ball Pellinger (stages 0-17ish: goblins, the
foreman, wool, the forge/Grim Cleaver, the rat, wolves/hides, captain, king).
Skills: MELEE/MAGIC/RANGED/HITPOINTS/WOODCUTTING/MINING/SMITHING with XP and
levels; gathering (trees/rocks), furnace smelting, anvil forging. Safe-town
rules: nothing aggros in towns/camp; leashed monsters walk home; respawns
minimum 120s (bosses 150s).

## 10. Kevin's queued backlog (his priority order, after the server-sim work)

1. **Spellbook UX:** Q opens it but nothing tells you that. Add a visible
   button/hint, a tooltip when equipping a staff, and ALWAYS show the
   currently selected spell on screen.
2. **Skills menu on K:** every skill with icon, level, XP, XP-to-next,
   progress bar; RuneScape-style combat level.
3. **Map system:** minimap centered on and rotating with the player; full
   world map on M with landmarks/NPCs/banks/shops/bosses/resources and a
   legend.
4. **Overall polish pass:** consistency, feedback, onboarding, audio.

Boss-fight frame drops with many projectiles are a KNOWN open issue; the
server-sim plan's projectile phase is expected to help, but rendering load has
not been ruled out — measure before promising.

## 11. Testing (how work gets verified here)

- Local harness: bundle with the three.js import rewritten to a local file,
  served on localhost; Playwright headless Chromium (SwiftShader — frames are
  SLOW; never trust timing-sensitive results, freeze `raf` for UI tests).
- Local relay: `npx wrangler dev --local` + ws-level protocol suites
  (`test.mjs`, `yield.mjs`, `srvcombat.mjs` in /tmp/relay of the working
  session — recreate as needed; every relay change reruns all of them).
- Two-browser end-to-end tests against the local relay for anything
  multiplayer. The sandbox's WebRTC is unreliable; the WebSocket stack tests
  fine.
- Pattern: prove a bug with a failing test first, fix, rerun the whole suite,
  then ship. Kevin explicitly wants dupe-prevention and multiplayer tested,
  not assumed.

## 12. Sharp edges (violate these and things break)

1. Never edit the bundles by hand; always extract → patch → pack.
2. Never let an unescaped `</` into the embedded source.
3. Both bundle files update together, every time.
4. NPC spawn order is a protocol invariant.
5. The DO keeps no in-memory state.
6. `wrangler.jsonc` name stays `grim-arena`.
7. Everything item-related goes through `invCommit`.
8. No `Math.random()` in future server sim paths (seeded RNG per the plan);
   loot rolls server-side are exempt.
9. Free tier only: no paid services, no accounts Kevin has to pay for.
10. Update PATCH-NOTES.md with every push, in plain language.
