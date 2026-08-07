# Grim World — patch notes

## 2026-08-07 (v16.9) - WHISPERS AND A FRIENDS LIST

NEW - a WHISPERS chat tab. Type /w NAME your message (or /whisper, /tell, /msg) to send a private line to anyone online anywhere in the world, not just nearby, and /r replies to whoever last whispered you without retyping their name. NEW - a friends list. Type /friend NAME or /unfriend NAME, or use the ADD FRIEND and UNFRIEND buttons in the hold-O player list. Friends show in their own section of that list with ONLINE or OFFLINE status and a one-click WHISPER button, and you get a toast when a friend logs in. The list holds up to 50 and carries over between sessions, guests included. This one needed no server changes, so it is live the moment this patch ships, unlike the party system which is still waiting on a relay deploy.


## 2026-08-07 (v16.8) - PARTY SYSTEM

NEW - a party system. Invite from the hold-O player list (or type /invite NAME), the other player gets an accept/decline popup. Once formed, a PARTY tab appears in chat (party-only, no distance limit) and small HP frames show top-left for you and every party member, with a star on the leader and a sword if someone has PVP on. LEAVE is on your own frame, KICK (leader only) is on everyone else's. If the leader disconnects or leaves, the next-longest-standing member takes over automatically, and a party that drops to one person dissolves rather than sitting there empty. Cap is 5. Party membership lives on the relay server itself, the same way monster health does, so two players can never end up disagreeing about who is actually in the party.


## 2026-08-07 (v16.7) - IN-GAME CHAT: LOCAL AND GLOBAL

NEW - a chat box in the bottom left, press Enter to open it. LOCAL is only seen by players within about 45m of you and your message floats above your head just like an NPC catchphrase, using the same fading distance system. GLOBAL reaches everyone in the world. Tabs show a little marker when a channel gets a new message you have not read yet. Chat never pauses or dims the game, so you can keep fighting and walking while it is open.


## 2026-08-07 (v16.6) - CATCHPHRASES NOW SHOW ABOVE THE RIGHT HEAD

FIXED - a talking NPC's line only ever showed up while that NPC happened to be your current target, and it was positioned there too, so Mr. Sailers' catchphrases were invisible or in the wrong place most of the time. Every NPC that talks now gets its own floating line above its own head, independent of who you have targeted. NEW - a max distance on how far away chat and catchphrases are visible, and the text shrinks the further away it is, so you are never reading dialogue from across the map.


## 2026-08-07 (v16.5) - HOTFIX: TYPE A NUMBER INTO THE CRAFTING WINDOWS

FIXED - typing a quantity into the furnace or anvil window fired the game's hotkeys instead: pressing 3 closed the window under your cursor, and other keys could swap weapons or open the map mid-type. Any text box you click into now owns the keyboard until you leave it. BONUS - pressing Enter in a quantity box starts the smelt or smith right away, and Escape steps out of the box and closes the window.


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
