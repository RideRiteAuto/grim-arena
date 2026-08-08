# Grim World — patch notes

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


## 2026-08-07 (v17.8) - HOTFIX: ACTION BAR PATCH BROKE THE GAME

FIXED - the previous patch (R/F hotkey fix, 6->8 action bar slots) shipped with a broken invLoad(): a deleted variable declaration and a duplicated if-line left the game unable to parse at all, so nothing loaded for anyone. Restored the missing declaration, kept the new bank-array line and the 8-slot bar, dropped the duplicate line. No gameplay change beyond un-breaking the game.


## 2026-08-07 (v17.7) - ACTION BAR: 8 SLOTS, STARTS EMPTY, AND R/F STOP HIJACKING YOUR WEAPON

FIXED - pressing R was silently equipping whatever was bound to action-bar slot 2, and F (when nothing was nearby to interact with) was silently equipping slot 3. Neither key was ever meant to touch your weapon - R's only real job is SORT inside the pack, and F's is the universal interact key (loot, bank, shop, furnace, talk). Both now do only what they are supposed to.
ADDED - the action bar grew from 6 slots to 8 (keys 1-8), and stays centered under the crosshair either way.
CHANGED - a brand new character's action bar now starts completely empty. Your starting gear is unchanged - the scimitar is still equipped and the staff, bow, pick and axe are still in your pack - you just bind them to the bar yourself instead of it being done for you. Returning characters keep every slot they already had bound; the two new slots just start empty like everything else did.


## 2026-08-07 (v17.7) - TRADE BUTTON (COMING SOON)

ADDED - a TRADE button next to WHISPER on every other player's row in the Who's Online list (press O), including your online friends. It is not a real trade window yet, tapping it just tells you trading is coming soon and to whisper them for now, but the target-a-player groundwork is in place so a real offer-and-accept trade system can drop in later without changing how you pick who to trade with.


## 2026-08-07 (v17.6) - WHO'S ONLINE

ADDED - the players list (press O) now shows where everyone is and how tough they are: a Zone · Level line under every name, yours included. Two new filters at the top narrow it down by zone or by a minimum combat level, so a big server reads as a short list of exactly who you're looking for. Friends and your own row are never filtered out.
