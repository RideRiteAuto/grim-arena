# Grim World — patch notes

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


## Monsters move on the server's clock now, not on whenever the packet showed up

The last of the choppiness. The game drew each monster by interpolating between
the last two positions it had received, and it timed that using the moment
those packets ARRIVED. The packets carry the server's own timestamp and always
have; it was being used for the swing animation but never for the position.

So the network's jitter was being rendered as movement. Two packets arriving
together made a monster cover a tenth of a second of ground in six hundredths
and then hold still. A packet arriving late made it stop dead until the next
one landed. On top of that a second smoother chased the first one, which added
lag and rounded off the start and stop of every step, so the stalls read as
sagging rather than being hidden.

Monsters are now drawn where the server actually had them a fixed moment ago,
two snapshot intervals back, with a short buffer of recent positions to read
from. Jitter goes into the buffer instead of into the legs. Nothing guesses
ahead of the newest position the server has sent, which was already the rule
and still is.

Measured, on a recording of a monster walking a dead straight line at a
constant speed while the network misbehaves around it (arrivals early, late,
out of order, one packet dropped entirely):

    before      speed varied by 40 percent, 14 sprints, 2 dead stops
    after       speed varied by 1.6 percent, no sprints, no dead stops

Nothing moves backwards any more either, which it used to do when the feed
hiccuped and the game replayed a stale position before crawling forward again.

COMBAT TIMING IS UNTOUCHED, AND THIS WAS CHECKED RATHER THAN ASSUMED. Drawing a
body a moment later is only safe if the blow still lands when the animation
says it does. There is a new test, harness/combat.js, that announces a real
swing and records the exact instant the damage resolves. Before this change:
450ms after the swing began, which is the wind-up. After: 450ms. Identical. The
swing rides its own clock and always did, and the blow is still judged against
the body you can actually see, so what you dodge is still what is on screen.

For the one case where it could cost anything, a monster still walking while it
swings, the drawn body sits about a third of a metre further behind than it
used to. That case does not happen in practice: the server plants an attacker
the moment it commits, and with it planted the drawn body and the server's body
are in exactly the same place, measured at zero difference.

Two things tried and rejected on the way, written down so nobody spends the
evening rediscovering them:

ADAPTING THE DELAY to the worst gap the connection had recently shown. Reads
well, measures badly. Moving the target moves the playback clock, and that gets
rendered as a speed change, so it came out worse than doing nothing at all: 40
percent speed variance against 12 for a fixed delay.

THROWING THE BUFFER AWAY when a packet arrived out of order. That is exactly
the case the buffer exists for, and discarding it left one stale position and
froze the monster until the feed caught up. Late packets are inserted into the
timeline where they belong instead.

Still not done, and now the largest remaining source of roughness: positions go
over the wire rounded to a tenth of a metre. At walking pace that rounding is
about a fifth of the distance covered between updates, so it is worth roughly
20 percent apparent speed variation on its own. Fixing it is a wire format
change and wants its own patch.


## The distant NPCs stop flashing, and stop fighting the server

Kevin said NPCs in the far distance were jittery, flashing and flickering, and
that everything felt choppy and slow after the recent updates. Three separate
causes, all found and measured rather than guessed at.

THEY WERE BEING DRAWN AT SEA LEVEL. This is the big one. Only one piece of code
in the whole game put a body on the terrain, and it lived inside the animation
function. The animation function is deliberately skipped on two frames out of
three past 50 metres, and five out of six past 85 metres, to save work. On
every skipped frame the body was drawn at height zero, absolute sea level.

The ground in this world runs from 27 metres below sea level to 87 above. So a
distant NPC was being thrown roughly 23 metres up or down, ten to twenty times
a second, usually straight into the dirt. That is the flashing. Measured on an
NPC standing still 82 metres away: twenty of thirty frames drew it at sea level
and ten drew it correctly.

The reason nobody caught it in months: the starting field is flattened to
exactly height zero, where the bug is invisible.

Placement is its own step now and runs every frame at every distance. Animation
can still be thinned as much as we like without a body ever leaving the ground.
There is a test, harness/ground.js, that reads the rendered height frame by
frame and fails if a single frame lands at sea level.

THINGS BLINKED AT THE CULL LINE. NPCs vanish past 90 metres, and that was a
bare comparison against a distance that changes every frame. Anything pacing
near the line blinked in and out once per pass. Measured: 89.4 visible, 90.3
hidden, 90.6 hidden, 89.9 visible, over and over. The same went for the 50 and
85 metre animation thresholds, so a monster walking toward you changed gait
speed on and off. Every band now has to be left by a wider margin than it was
entered by, so a wobble cannot cross it twice.

THE GAME WAS FIGHTING THE SERVER OVER MONSTER POSITIONS. Monsters in a pack
shove each other apart so they surround you instead of stacking on one point.
The server already does this, ten times a second. The client was also doing it,
sixty times a second, on top of the positions the server had just sent, because
one half of the check that was supposed to switch it off was missing. The
client shoved six times harder than the server, the smoothing pulled back, and
the monsters you were actually fighting vibrated. One line.

WALKING AWAY FROM MONSTERS BROKE THE FEED. The server only tells you about
monsters within 60 metres, and if there were none it sent nothing at all. The
game waits two seconds for word and then assumes the connection is dead and
starts simulating all 88 NPCs on your own machine, colliders and all. The world
is 4800 metres across, so being more than 60 metres from every monster is the
ordinary case, and that fallback was switching on and off as Kevin walked
around. The server now sends an empty heartbeat, about 30 bytes, so the game
knows the silence is real.

Still on the list and not done yet: monster positions are played back using the
time each packet ARRIVED rather than the timestamp the server put on it, with
no jitter buffer, which is its own source of chop. That one needs two machines
to test properly.


## Your levels stop falling every time you log in

Kevin logged out at 11 woodcutting and came back at 7. This is why, and it was
not a rollback, a lost save, or a bad connection. It was the game converting
his XP to the new skill curve every single time he logged in.

The zone update changed the XP curve, so old saves needed converting once. The
converter did its job and then stamped the save so it would never run twice.
The problem is where the stamp went: onto a temporary object the code threw
away on the very next line. Nothing about the stamp ever reached the save file.

So every login the game read the save, found no stamp, and decided this must be
an old save that still needed converting. It read XP that was already on the
new curve as if it were on the old one, which always lands lower, and wrote the
result back four seconds later as the truth. Once. Then again. Then again.

The ratchet, measured: woodcutting 11 becomes 7, then 5, then 4, then 3. Every
skill at once, melee and hitpoints included. And because a deploy forces
everyone back to the login screen, every patch that shipped took another bite.

Guests were never affected. The guest save writes its stamp somewhere that
survives, which is why this only ever showed up on real accounts.

Saves now carry a version number, and the converter is retired outright. Every
save in the database has already been through it many times over, precisely
because the old code ran it on every login, so letting it run one more time on
the way past would have taken one more level off everybody. There is nothing
left for it to convert. Saves also carry a backup of their XP from here on, so
if a conversion is ever needed again it can be undone.

The only account this does not help is one that has not logged in since before
the zone update. That character will read a little high rather than a little
low, which is the right side to be wrong on.

Two more holes in the same path, closed while I was in there:

A SAVE THE SERVER REFUSED WAS COUNTED AS A SAVE. The database answers every
save with yes or no, and says no if the password hash does not match or the
save is too big. Both of those come back looking like a successful request, and
only the request was being checked, never the answer. A refused save cleared
the unsaved flag and was never retried. The answer is read now, and a refusal
is logged and retried.

NOTHING WAS WATCHING FOR XP GOING BACKWARDS. Nothing in this game lowers a
skill, so a save about to write less XP than the last one is always a bug. That
is now checked on the way out and shouted into the console. This one check
would have caught the whole thing in a single login instead of over weeks.

There is a new test, harness/savecurve.js, that logs a character in and out ten
times and asserts nothing moved. It was written against the broken build first
and reproduced Kevin's exact numbers, 11 to 7 on the first login, so it is a
real guard and not a formality.

Kevin's lost XP is not recoverable. The backup that would have made it
recoverable was part of what was being thrown away.
