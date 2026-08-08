# Grim World — patch notes

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


## 2026-08-07 (v17.5) - COMBAT LEVEL

ADDED - a combat level now shows next to your name at the top of the screen and in party frames, right alongside each member's zone. It is your hitpoints level plus your best of melee, ranged, or magic, halved and capped at 99, so it reflects real fighting strength rather than time spent gathering. It updates the instant a relevant skill levels up.


## 2026-08-07 (v17.4) - PARTY FRAMES SHOW WHERE YOUR PARTY IS

ADDED - party frames now show which zone each member is standing in, right under their name. Your own zone updates live as you move; a party member's zone comes from the same state broadcast that already drives their health bar, so it stays current with no extra chat needed to find each other.


## 2026-08-07 (v17.3) - ITEM TOOLTIPS STOP GETTING STUCK ON SCREEN

FIXED - hovering an item in your pack or the bank, then hitting Tab or Escape to close the window, used to leave the little item info box floating on screen with no window under it. The pack and the bank now both hide their tooltip the instant the window closes, so nothing gets left behind. The bank's item hover also got upgraded from plain text to the same stats box the pack and Fenwick's shop already show.


## 2026-08-07 (v17.2) - THE SOCIAL PANEL WORKS LIKE A REAL WINDOW NOW

FIXED - O had to be held down to see who is online, and none of its buttons (INVITE, WHISPER, ADD FRIEND) could actually be clicked, since holding O never released your mouse from the camera. O now toggles the panel open and closed like every other window, hitting O again (or ESC, or the new close button) shuts it, and your cursor is freed the moment it opens so the buttons genuinely work. Chrome (title bar, close button, footer legend) now matches every other window instead of a bare unstyled box.
FIXED - KICK and LEAVE on your party frames looked clickable but were not, any time another window was open (bank, pack, the social panel, all of them) - the screen dimmer behind that window was silently sitting in front of the party frames and eating every click. Party frames now render above the dimmer, so KICK and LEAVE stay reachable no matter what else you have open.


## 2026-08-07 (v17.1) - NO MORE GUEST, A REAL PAUSE MENU

REMOVED - the PLAY AS GUEST button. Accounts are mandatory now, so LOGIN & PLAY is the only door in, and the front-door copy and login-box status line that mentioned guest play are gone too.
FIXED - hitting ESC used to dump you straight back onto the title screen, the same login/patch-notes overlay with the message swapped to PAUSED. ESC now opens a proper in-game pause menu: RESUME, SETTINGS (aim assist, music, volume, graphics quality, PVP, all the same controls, just relocated), and LOG OUT, which is now the only button that actually takes you back to the real title screen. Click outside the panel or hit ESC again to resume.


## 2026-08-07 (v17.0) - HUD LAYOUT CLEANUP

FIXED - the FPS/coords debug stamp sat directly under the new chat box; moved to the bottom-right, clear of both chat and the PRESS H / boat-interact hints. FIXED - party frames were pinned over your own health bar and the quest helper box; they now sit directly under your health bar where they belong, the quest helper is pushed further down to stay clear even with a full 5-person party, and the quest box grew a matching gap. NEW - party frames show mana now, not just HP, for every member whose client has synced it.
