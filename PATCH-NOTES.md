# Grim World — patch notes

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
