# Grim World — patch notes

## 2026-08-07 (v16.4) - HOTFIX: THE WORLD NO LONGER FREEZES AFTER SMELT OR SMITH

FIXED - hitting SMELT or SMITH froze the whole game solid until you clicked. The world simulation paused the moment the crafting window closed because your mouse was not locked back into the game, so the furnace never produced a single bar and everything looked crashed. Now the world always keeps running while the furnace or anvil is working, and the SMELT and SMITH buttons hand your mouse straight back to the game.


## 2026-08-07 (v16.3) - SMELT AND SMITH: REAL CRAFTING UIS

REDONE - the furnace. F now opens a menu listing every ore you can smelt with pictures, how many you carry, and what each bar needs. Pick one, set how many with + and - or just type the number, hit MAX for everything, then SMELT and watch the furnace work - one bar at a time with the pour, the sparks and the XP, straight into your pack. Stopping early keeps your leftover ore.
NEW - BRONZE and STEEL. Copper ore now smelts into BRONZE BARS (old copper bars melt over 1 for 1 at the furnace), and at SMITHING 40 iron ore plus 2 coal makes a STEEL BAR.
REDONE - the anvil. F opens a smithy with three metal tabs - BRONZE, IRON, STEEL - each listing the full set you can make: helm, platebody, platelegs, kite shield, scimitar, a two-handed CLAYMORE, pickaxe, axe, sickle, and a skinning knife (craftable now, skinning comes later). Same pick-a-number-and-go controls, then the anvil rings while your order is hammered out piece by piece with XP on every one.
NEW - sixteen new pieces of gear with their own thumbnails. Steel plate is the best armour in the game now, and every metal has its own claymore - the Grim Cleaver you may already own is the iron claymore's famous older brother and is no longer craftable.
FAIR PLAY - bars are only spent as each piece is finished, everything happens in one no-dupe inventory step, and walking away from the furnace or anvil stops the work with your materials safe.


## 2026-08-06 (v19) - Chopping and mining sound like chopping and mining

CHANGED - the axe now bites into wood with a real woody crack instead of a synthesised blip, and mining is a proper bright pickaxe ring off stone, the sound you expect from a game. Both got three different samples rather than one, and each swing is pitch-shifted, so felling a whole tree never repeats the same noise twice.
FIXED - foraging used to play the axe sound, so picking a herb sounded like chopping down a tree. It has its own sound now: stems snapping, leaves rustling, soil shaking off the roots.
CHANGED - a falling tree is a real recording of a trunk splitting and crashing through branches instead of a sawtooth sweep.


## 2026-08-07 (v16.2) - THE MENU PATCH NOTES ARE ALIVE

FIXED - the PATCH NOTES box on the main menu was frozen at V13 while the real notes kept being written to a file nobody displayed. The menu now loads the live notes file every time it opens, so everything above this line, and every future update, shows up there automatically.
NEW - the notes box scrolls, headlines get their version tag, and the NEW/FIXED/CHANGED labels keep their gold highlight. If the game is opened offline the old built-in notes still show as a fallback.


## 2026-08-06 (v16.1) - PVP ACTUALLY WORKS, DOG TAGS, K/D RECORD

FIXED - pvp hits now really land. The live game talks through the relay server, and the relay was silently dropping every pvp message - you saw the hitsplat, they never took the damage. The relay now carries player combat, delivered only to the player it is addressed to.
FIXED - the player currently hosting the simulation could not be hurt even with pvp on. Now every seat takes hits the same way.
NEW - dog tags. Kill a player and their dog tag (with their name on it) appears in your pack. Bank it, keep it, hand it in for future quests: it is proof of the kill. One tag per victim per 10 minutes, so trading kills back and forth cannot mint a pile of them. Fenwick will not buy them - proof is not for sale.
NEW - your PVP record. Kills and deaths are counted, saved with your character, and shown at the bottom of the skills page (K).
WORKS NOW - spells in pvp: fireball sets players burning (burn ticks never land the killing blow), frost freezes them solid for 2 seconds with a 6 second immunity after, so nobody can be chain-frozen forever.
FAIR PLAY - the victim's machine is always the judge: your armour, shield and parries decide what a hit does to you. Incoming damage claims are capped at the biggest hit the game can legitimately produce, kill credit is only honoured if the killer really damaged you in the last 30 seconds, and player kills award no combat XP - so kill trading earns nothing.


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
