# Grim World — patch notes

## 2026-08-12 (v17.27) - Bugfix pass + crafting/NPC expansion

Fixed a real bug Kevin reported: the donkey mount drop had gotten wired to the Bandit Captain instead of Mr. Sailers on the relay-server multiplayer path (the direct peer path was already correct). Mr. Sailers now carries his own tag end to end. Also found and closed a dormant inconsistency in the old pre-account starter-kit code path (unreachable from the live login UI, but fixed so it can never quietly hand out free iron gear again if a guest mode ever returns). Crafting table now also makes CRUDE AXE and CRUDE PICK from logs alone (both already-existing items, zero new asset risk), giving it a real second use beyond the rowboat. Added Marta the Shipwright, a flavor NPC by the crafting table, same proven pattern as Jim and Pete. Verified via the local play() boot harness (real login still blocked in this sandbox by the known Cloudflare edge issue): quest chain, craft costs, craft-table UI, and the mount fix all check out.


## 2026-08-12 (v17.26) - NEW PLAYER START REWORKED: LOGS TO COPPER TO BRONZE TO YOUR OWN ROWBOAT

NEW - a brand new character's first few minutes now actually teach the game instead of handing you finished gear. You start with nothing worn (just the mining/woodcutting tools you always started with in your pack) and Ball Pellinger's first quests walk you through it: cut six logs, then mine copper and turn it into your own bronze helm and platebody at the furnace and anvil, then build your own rowboat at a new crafting table by the forge using logs you cut. Only after that does the old goblin-slaying quest chain start, unchanged from before.

FIXED - there used to be two different copper/iron-ore setups that didn't agree with each other (one let you mine iron at level 1, the other required level 30), which made early mining levels feel arbitrary. The camp's starting ore patches now consistently give copper at level 1, and the high-level iron vein at Ironspire (level 30) is the only iron source in the game.

NEW - Fenwick the trader now also stocks tier-1 and tier-2 tools in case you lose yours, plus venison for a quick heal.

Existing characters are unaffected - if you are already past the very first goblin quest none of this changes anything for you, and anyone already carrying a rowboat keeps it.


## 2026-08-08 (v17.25) - BACKGROUND-THREAD TERRAIN BUILDER IS NOW LIVE

WORKS NOW - the game now actually uses the background thread to build terrain instead of doing that work on the same thread as the camera and controls, which is the real, permanent fix for the earlier camera-turn stutter (the last two patches were prep and mitigation, not the fix itself). Extensively checked beforehand to draw an identical world either way. If anything looks or feels off, this can be switched back to the old way instantly - tell me and I'll flip it back.


## 2026-08-08 (v17.24) - UNDER-THE-HOOD: BACKGROUND-THREAD BUILDER IS WIRED UP, STILL SWITCHED OFF

WORKS NOW - the background terrain builder from the last patch is now actually connected to the game, behind a switch that's left off. With the switch off (today), nothing changes - the game builds terrain exactly like it always has. Flipping that switch on later is its own separate, deliberate step, not something this patch does.


## 2026-08-08 (v17.23) - UNDER-THE-HOOD: BACKGROUND-THREAD TERRAIN BUILDER, NOT TURNED ON YET

WORKS NOW - built the actual background thread the last under-the-hood patch was prepping for, but left it switched off. It builds terrain and decides what grows where, in parallel with the game itself and checked line-for-line against what the game already produces so it can't ever draw the world differently. Nothing is wired up to actually use it yet - that's a separate, later step behind its own on/off switch, so this patch changes nothing about how the game looks, plays, or feels today.


## 2026-08-08 (v17.22) - GROUND PAINT: FIXED A REMAINING HARD EDGE ON SOME SIDES OF A PAINTED AREA

FIXED - painting a patch of ground (meadow, dirt, etc.) could still show a hard, blocky edge on one side of the brush while the rest faded in smoothly, even after the last two passes at this. The real cause: painting worked by swapping out one of the two natural textures already blended at that spot, and which one got swapped depended on the natural terrain itself, not on the paint stroke. Wherever those two things lined up badly, the edge went hard. Paint now fades in as its own layer on top of the natural ground instead of swapping anything out, so there's nothing left to cause that mismatch. Verified with real before/after data in all directions around a test brush stroke, not just eyeballed.


## 2026-08-08 (v17.21) - UNDER-THE-HOOD: FIRST STEP TOWARD MOVING TERRAIN OFF THE MAIN THREAD

WORKS NOW - the ground/prop-placement math that decides what a chunk of terrain looks like and what grows on it was reorganized into standalone building blocks, as prep for eventually running that work on a background thread instead of the same thread as the camera and controls (the real fix for the v17.20 camera-turn stutter, not just the mitigation that patch shipped). Zero behavior change from this step alone: verified byte-for-byte identical ground colors, prop placement, and bridge blending across a full test boot before and after. Nothing to notice yet; this just clears the way for the actual threading change.


## 2026-08-08 (v17.20) - SMOOTHER CAMERA TURNING IN THE OPEN WORLD

FIXED - turning to look around while running used to randomly stutter or jump, like the view briefly forgot which way you were facing. The world streaming in new ground around you was doing enough work on the same frame as the camera update that it could visibly stall the view for a beat, worse the more you were actively turning at the time. Spread that work out over more frames instead of front-loading it, same total cost, no visible change to how fast the ground finishes detailing in as you walk. This is a mitigation aimed at the actual reported stutter, not a full rebuild of how terrain streams; if it doesn't fully clear this up let me know exactly when it still happens (standing still and turning vs. running and turning is the useful distinction) and I'll dig further.


## 2026-08-08 (v17.19) - MULTIPLAYER SERVER: FEWER STORAGE WRITES DURING COMBAT

CHANGED - landing a hit or looting a kill no longer writes the whole world to storage on the spot every single time. Changes still land on your screen instantly, the save itself is just bundled up and written a couple seconds later instead of once per hit, cutting real server storage costs during busy fights and looting without changing anything you'd notice. Shipped alone and watched closely since it touches how progress gets saved.


## 2026-08-08 (v17.18) - MULTIPLAYER SERVER: SMOOTHER MONSTER MOVEMENT, LESS TRAFFIC DURING FIGHTS

CHANGED - monster positions sent to your screen are now ten times more precise (about a centimetre instead of about ten centimetres), which should make monster movement read a little smoother and more consistent, especially at slower walking and patrol speeds.
CHANGED - during a fight with several monsters swinging, casting, or doing boss theatre at once, the server now bundles those into one message per tick instead of sending each one separately. You shouldn't notice anything different in how a fight looks or feels, this only cuts down on network chatter during busy fights.


## 2026-08-08 (v17.17) - MULTIPLAYER SERVER: LESS CROSS-TALK, FASTER COMBAT HITS

CHANGED - other players' position updates are now only sent to players near enough to actually see them, the same distance rule monsters already used. Party members still always see each other's position no matter how far apart, so the party overlay keeps working exactly like before. Less server traffic as more people play at once, nothing you should notice moment to moment.
CHANGED - landing a melee hit on a monster no longer forces an extra full simulation pass on top of the one already running about 10 times a second. Damage numbers, monster reactions, and death timing land exactly as fast as before, this only removes genuinely repeated work from a burst of hits landing close together.


## 2026-08-08 (v17.16) - EDITOR FEELS SNAPPIER, PLUS SOME SERVER CLEANUP

WORKS NOW - dragging a placed object, or dragging its rotate/scale/lift sliders, in the world editor used to redraw the ground under it on every tiny movement, which made it feel sluggish underhand. It only redraws once you pause or let go now, same debounce trick a couple of other editor controls already got a few patches back.
CHANGED - placing, deleting, duplicating, pasting, or stamping a prefab object in the editor now only redraws the small patch of ground right around it instead of your whole visible surroundings, so those actions land noticeably faster, especially out past the near chunks.
WORKS NOW - some behind-the-scenes traffic routing on the multiplayer server (loot grants, party invites, party kicks) got faster to look up internally. Nothing you'd see or notice, no player-facing change.
