# Grim World — patch notes

## 2026-08-06 (v16) - PVP

NEW - PVP, strictly opt-in. Flip PVP: ON on the main menu and you can fight, and be fought by, anyone else who has done the same. A red sword marks pvp players on their nameplate and in the who-is-online list.
NEW - dying to a player costs NOTHING. No item drops, no gold lost: you rise at the camp with your pack intact, the killer's name on the banner, and five seconds where nobody can touch you and you cannot touch them.
NEW - your shield matters against players: blocks, perfect parries and armour all work exactly as they do against monsters, judged on your own machine.


## The world editor exists

Phases 3 to 6 of the build plan, all four in one push. A private editor at the game URL plus ?edit=1: the real engine with a free camera (WASD, Q and E, right mouse look), so what it shows is exactly what players get. Paint any of the sixteen ground surfaces with a feathered brush, lay roads as smoothed splines that suppress grass down their middle, place objects from a 58-kind catalog (walls with doorways and windows, floors, stairs, a watchtower and platform with genuinely walkable decks, props, packing benches and trade posts for the coming economy, and every tree, ore and plant grown by the game's own builders so they match the world), select, move, rotate, scale, duplicate, copy and paste, delete placed objects or generated ones, save prefabs and stamp them, sculpt terrain with raise, lower, flatten and smooth, drop monster spawn markers, trace housing district boundaries, bookmark places and jump to coordinates, undo, redo, and revert everything. Edits save to the relay as a layer every client fetches at boot, so a change goes live without a deploy. The layer never blocks boot, an empty layer is proven byte-inert by the new 51-check harness, and the whole existing suite stays green including dressing determinism. Saving from the editor needs the EDIT_KEY secret set on the worker once; until then it runs read-only with file export.


## 2026-08-06 (v18) - Every zone has its own music

NEW - twelve original themes, one for each region of the world, generated as a single cohesive set: the Heartlands, Greenwood, Frostwild, Ironspire, Sun Coast, Windscar, Ember, Mistfen, Sunscorch, Eastridge, the Shattered Isles, and the open sea. All instrumental, all built from the same small acoustic ensemble so the world sounds like one place rather than twelve stock tracks, and all matched to the same loudness so no region is suddenly louder than its neighbour.
CHANGED - the music follows the real map now. It used to pick between two tracks using two hardcoded circles left over from before the world was generated; it now asks the world which zone you are standing in, so it stays right wherever the map goes.
NEW - zone changes crossfade over about five seconds instead of cutting, and the track will not change until you have been in the new zone for a couple of seconds. Step over a border and step back and the music never reacts at all. Stand on a border and it stays put instead of flapping between two songs.
NEW - each theme loops seamlessly, and the next zone's music starts loading the moment you look like you are heading there, so the fade lands on music instead of silence.


## 2026-08-06 (v15.1) - Key hints say PRESS, mount hints move home

FIXED - riding up to an NPC no longer buries the talk prompt under the mount controls. The interact prompt keeps centre stage; PRESS X - DISMOUNT and the turbo hint dock bottom-right with the teleport hint, where standing controls live. The boat hint moves to the same corner.
CHANGED - every floating key hint now says PRESS, and the turbo hint names the action Z will take rather than the state it is in.


## 2026-08-06 (v17) - Hits know what they are hitting

CHANGED - the swing is a swing again. It is a genuine miss now: air and a blade whistle, nothing struck. The v2 attempt had an impact buried in it, which is why it stopped sounding like a swing.
NEW - hits pick their sound from what you actually hit. Bare creatures give a solid meaty thud, goblins and lightly geared players give a leathery slap, anything in metal gives a hard clang off the plate. Every monster in the game right now is bare or leather, so plate is waiting for the first armoured enemy: when one arrives it only has to say it wears plate and the sound is already there.
CHANGED - a critical hit is no longer just a louder hit. It plays the impact and then lays a bright ringing blade over the top of it, so a crit sounds like a reward instead of a heavier thud, and it reads the same whatever you land it on.


## 2026-08-06 (v16) - Combat sounds v2: louder, heavier

CHANGED - swing, hit, crit and shield block regenerated and remastered after Kevin's review: too quiet, not impactful. The new takes are heavier (deep bass thump under the hit, a real crack on the crit, a wooden boom on the block) and mastered 4 to 6 dB hotter, and their in-game volumes came up too. Heavy swing and parry keep their approved v1 sounds.


## 2026-08-06 (v15) - Fenwick is a real shop now

REDONE - Fenwick's whole screen. Two inventory grids side by side: his stock on the left, your pack on the right, the same slots the pack and bank use. Click his stock to buy one, click your item to sell one, right-click either side for bulk with the total shown before you commit, hover anything for its price.
NEW - he buys nearly ANYTHING with a value now, not just pelts and ore. Gold is the one thing he will not take.
NEW - whatever players sell him goes on the shelf with a quantity, for anyone to buy. Stock is shared across every player and survives reload. The armour and the Tome stay unlimited so they can never be bought out.
NEW - RuneScape pricing: the more he holds of something, the less he pays for the next one, floored at 35 percent. He works his surplus off at one unit per ten minutes, so prices recover. Day-one prices are unchanged when his shelf is empty.
NEW - expensive purchases get a confirm screen. No more accidental second hollow plate.
NEW - sold something by mistake? It is on his shelf now. Buy it straight back.
CHANGED - the pack tooltip quotes what Fenwick actually pays right now, glut discount included.


## 2026-08-06 (v15) - Combat finally sounds like combat

NEW - real sampled sounds for the six most heard combat events: light swing, heavy swing, hit, critical hit, shield block and parry. Until now every one of these was an oscillator beep; a blow landing was a sine thump and a parry was two triangle waves. Each sound was generated with ElevenLabs (three takes, best one picked on measurements and spectrogram), trimmed to the event and shipped in the bundle, about 46 KB for all six.
CHANGED - every combat sound plays at a slightly different pitch each time, the same trick the anvil uses, so a fast fight never sounds like one sample being retriggered. The old synthesised sounds stay in as an instant fallback while the samples decode, so the first hit of a session is never silent.
FIXED - harness/build.sh works again on a fresh pull. The shipped UI patches 38-40 were still sitting in harness/patches/ and broke the build for every track; they are now in applied/ where shipped patches belong.


## 2026-08-06 (v14) - UI pass: the world stops pausing, one panel system

FIXED - opening your pack, the bank or the skills page no longer PAUSES the world. active() went false the moment a panel released the pointer lock, so the whole simulation held its breath: NPCs stopped, quests stopped, nothing moved until you closed the panel. The world now keeps running behind every window, and the keyboard is what gets held back instead.
NEW - FRAME RATE in the corner readout, colour-coded against the same threshold the game uses to drop its own graphics. The coord stamp stays, now on three lines so it never clips the action bar.
FIXED - the action bar no longer draws on top of the pack, the bank, the sack or the skills page. One z-index ladder replaces sixteen hand-picked numbers, and panels no longer reach down into the bar.
NEW - every window dims the world behind it, the treatment only the world map had.
FIXED - the duel-era round frame is gone from the open world. No more FREE ROAM over four empty win pips fighting the compass ribbon for the same strip of screen.
CHANGED - one panel chrome everywhere: same border, fill, gold rule and typeface. Fourteen places were asking for generic monospace and rendering in the wrong font. Every window now carries a description of what it is for and a sticky legend of what each control does.
CHANGED - the trader shows item icons, the bank shows your gold and lays the vault out beside your pack, and the skills page reads in two columns.
FIXED - ESC closes the trader instead of opening the pause menu on top of it. Messages raised by a panel (pack full, wrong slot, key unbound) show above the dimmer instead of behind it.


## Phase 1d: falling exists

The player carries a real elevation now, behind the new VERT switches in the shared rules (ELEV is the master and any switch can be turned off in production without reverting the rest). Walk off an edge and you fall, with terminal velocity and a landing; the jump is ballistic to the same height as before; the camera follows you off a cliff; bridges are real walkable decks and standing on one over the river does not read as swimming. Slopes still climb exactly as before (the slope limit waits for 1g and its reachability sweep), swimming and boating behave exactly as they always did, and standing anywhere on the ground is arithmetically identical to the old game, not just similar. Fall damage is wired and set to zero. Elevation deliberately lives beside the position rather than inside pos.y, so all 25 distance checks in the game (interactions, melee reach, aggro) and the save format are untouched. Proven by the new harness/vertical.js (fifteen checks including jump apex, monotone falls, deck over water, and the switch restoring the old formula exactly) plus the whole existing suite.


## Phase 1c: frames of reference, structure only

A cargo pack on a boat deck has to stay on the deck while the boat sails, which needs positions that can be expressed relative to a moving thing. The structure for that exists now: a frame registry with world-frame identity converters, the player state message carries a frame id (0, the world), remotes store it the way they already store transmitted height, and the surfaces query accepts a frame argument it does not yet use. The world is the only frame, so nothing behaves differently. Phase 9 turns the rowboat into the first real frame and this structure makes that additive instead of a rewrite.


## Phase 1a and 1b: the vertical layer groundwork

worldY is now the single definition of an entity's true height, with fifteen call sites routed through it (placement, the network position, aim, damage anchors, remote players, every projectile muzzle), and surfaceY is the new surfaces query with bridge decks and terrain as its first two providers, bridges keeping their exact shipped maths. Both changes are verified zero behaviour change: the suite is green and every value is byte-identical to before. This is the safety groundwork for real elevation: when pos.y becomes a real height in 1d, these sites flip together in one switch instead of double counting the ground in twenty places. Camera, hitboxes, corpse slump and rail clamping are deliberately untouched, they are named 1e items. Also retired the shipped sfx patch 30 to applied so the build path works for anyone who pulls.
