# Grim World — patch notes

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


## 2026-08-08 (v17.11) - CLEANER GROUND TEXTURE BLENDS, WIDER BLEND RANGE

REDONE - where two ground textures meet (or ground blends into rock on a slope), the game used to average the two textures' colours together, which washes them into a hazy, flat-looking band right at the seam, on top of the blend being limited by how fine the terrain mesh itself is. Reworked so each patch of ground is drawn with one texture or the other at full detail, scattered by a fine, stable grain so the transition reads as an organic mix rather than a blend bounded by mesh geometry. No extra cost to draw and no change to the terrain mesh itself.
CHANGED - the paint tool's "Ground blend / edge softness" setting can now go up to 6m (was 4m). A wide soft blend used to just mean a wider band of that same washed-out colour, so there was no reason to want one; that is no longer true, so the range grew to match.

FIXED - every coastline used to force a sandy strip onto the ground near any water, regardless of zone or what was actually painted there, left over from before the zone and paint system existed. It was baked at the terrain mesh's own grid resolution rather than the paint tool's, which made it noticeably more jagged than a real paint blend, and it kept fighting attempts to paint over it since it was never actual ground paint to begin with. Removed both places it was forced in. Sun Coast and the Isles are unaffected, they already carry their own real coastal sand as part of the zone itself; everywhere else, the water's edge now shows the zone's real ground, or whatever gets painted there.


## 2026-08-07 (v17.9) - MONSTERS DON'T TELEPORT ON YOU ANYMORE

FIXED - monsters used to visibly jump to a different spot as you ran up on them, worse the faster you were moving even with FPS fine. The game was drawing monsters farther away than it was willing to tell you their real position, so they'd freeze in place out past a certain range and then snap to the truth the instant you got close. Draw range for monsters is a little shorter now to match, and reacquiring one after a gap eases in instead of popping.


## 2026-08-07 (v17.9) - FIREBALL: NO MORE FREEZE, NEW LOOK

FIXED - casting spells used to freeze and stutter the whole game for a beat, worse the more torches and lit props were in view. Every frost, fire and snare bolt built its own light and threw it away when the bolt died, and changing how many lights are in the scene forces every lit shader in view to recompile. Casts now share a fixed pool of five lights that never leave the scene, so nothing recompiles no matter how fast you cast.
ADDED - the fireball spell now looks like actual fire instead of a glowing lump: a raked cluster of flame tongues built from the same shader the campfires use, with a trail of embers riding along behind it. Frost and snare are unchanged, and the cast sound is unchanged.
