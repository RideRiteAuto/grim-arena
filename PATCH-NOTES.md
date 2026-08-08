# Grim World — patch notes

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


## 2026-08-08 (v17.15) - UNDER-THE-HOOD PERFORMANCE CLEANUP

WORKS NOW - trimmed a batch of small per-frame memory allocations across camera movement, NPC animation, quest tracking, arrows and projectiles, and terrain loading. Less garbage-collection stutter to expect in busy scenes. Nothing should look or play differently, this is all internal.


## 2026-08-08 (v17.14) - GROUND TEXTURE STATIC FIXED, BIGGER BRUSH, SLOPE/SNOW LINE NOW TUNABLE

FIXED - the dithered ground blend from the last patch could show a grid-like static pattern over large or bumpy areas, worst from a low angle. The dither now fades into the old smooth blend automatically at distance and grazing angles, where a screen pixel can no longer resolve the fine grain, so it never shows static again but keeps the crisp up-close blending where it matters.

FIXED - an older road drawn before the most recent one could never be selected or deleted from the Select tool, only the most recent road could. Any road can now be clicked and deleted from wherever it sits in the list.

ADDED - four new paint brush controls: hardness (softens the brush's own edge instead of a hard circle), flow (builds coverage up gradually like an airbrush instead of committing at full strength on contact), organic edge (breaks up the brush footprint so patches read as hand-placed instead of a stamped circle), and a paint-only-over lock so one texture can be retextured into another without spilling onto the rest of the ground.

ADDED - the slope where a hillside starts showing rock, and the altitude where the snow/cap line starts, are both tunable per world from a new Ground texture rules panel, instead of being fixed in code. Old worlds render exactly as before until touched.


## 2026-08-08 (v17.13) - THE HAND-PLACED WORLD LOADS MORE RELIABLY

FIXED - if the one fetch for your saved map edits lost a race against a slow or flaky connection, the game gave up silently and showed the bare generated world with no sign anything went wrong. It now tries a second time before giving up, and if it still fails, says so in the console instead of failing silent.


## 2026-08-08 (v17.12) - TREES AND ORE VEINS ARE SOLID NOW

ADDED - trees and ore veins block movement now instead of being walk-through scenery, both the ones the world grows on its own and the ones placed by hand in the editor. Herbs, berries and mushrooms stay walk-through on purpose, they are too small to read as an obstacle.


## 2026-08-08 (v18.3) - FROST BOLT REWORK, AND YOU CAN NOW SEE OTHER PLAYERS' SPELLS AND SHOTS

ADDED - the frost bolt has the same treatment fire got last patch: a real model instead of a plain glowing ball, a forward-leading cluster of icy shards with a frost-mist trail, same quality bar as the fireball.
ADDED - hitting someone with frost now has a 25% chance to freeze them in place for 1.5 seconds (was: always froze for 2 seconds) and plants a block of ice at their feet for as long as the freeze lasts. Every frost hit also slows the target's movement 15% for a few seconds, whether or not it freezes.
FIXED - only the person casting a spell or firing a shot could ever see it fly. In open-world play (including PvP) everyone else's fireballs, frost bolts, snares, toxin darts and arrows were completely invisible to you until they hit - so you could take a fireball to the face with no warning it was coming. Every player's own cast or shot is now broadcast to everyone else nearby, rendered with the same real model you'd see if you cast it yourself.
Cast and hit sounds for frost are unchanged - they already got a full pass earlier and didn't need touching.


## 2026-08-07 (v18.2) - TREES: NO MORE SEAM AT THE BASE

FIXED - every tree in the game had a visible seam ringing the trunk right where it meets the ground, even standing before it's ever chopped - the two trunk pieces that split apart when a tree falls didn't quite line up. Fixed three separate causes at once: the two pieces were different thicknesses at the seam, their surface roughness didn't line up vertex to vertex, and they were each drawing a flat cap right on top of the other's. Applies to every species - oak, willow, pine, redwood, palm, the works.


## 2026-08-07 (v18.1) - ADJUSTABLE DRAW DISTANCE

ADDED - a DRAW button next to GRAPHICS on the pause menu, cycling NEAR/NORMAL/FAR. Controls how far the camera sees: fog, the horizon, and how much terrain and scenery load in around you. NORMAL is a small step in from before (nothing was visible past where fog already hid it), FAR pushes it back out for a bigger view if your machine can take it.
FIXED - the fog and the sky behind it used to be two different colors, so distant terrain sat as a lighter band on the horizon instead of fading away. They match now.
