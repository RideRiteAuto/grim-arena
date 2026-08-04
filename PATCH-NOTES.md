# Grim World — patch notes

## August 5, 2026 (map follow-up) — M toggles the map both ways

Opening the map releases your mouse cursor, and the key handler used to
ignore most keys while the cursor was unlocked - so M could open the map
but not close it. The M toggle now sits above that gate (like Escape
does): press M to open, press M again to close, no clicking back into the
game first.

## August 5, 2026 (the map update) — Asterra in your pocket

### World map on M
Press M (or Esc to close) for the full map of Asterra — the exact "World
Map v2" chart the terrain was baked from, so it is pixel-accurate to the
world by construction: 4 meters per map pixel, world origin at The
Capital, top of the map is TRUE NORTH. Region names, rivers, roads, towns
and ports are all there, with a legend bottom-left (points of interest
get added to it later) and a gold arrow showing exactly where you are and
which way you face, live. Ships inside the game file as crisp vector art.

### Compass ribbon
A compass now runs across the top of the screen whenever the map is
closed: cardinal letters and degree ticks scroll smoothly under a gold
caret as you look around, N highlighted. The FREE ROAM banner moved down
a touch to make room.

### Minimap, rebuilt
The top-right minimap is now a live circular cutout of the real Asterra
map instead of an abstract dot disc. Your arrow is pinned dead-center and
never moves; the world rotates around it as you turn, so up on the disc
is always the way you are looking. Monster and NPC dots ride on top, and
a gold N on the rim always shows where true north went. The minimap uses
a label-free copy of the chart so text never clutters the disc.

### Keys
M added to the menu binding list.

## August 5, 2026 (swim camera) — swimming POV raised

The camera was skimming the water surface while swimming, leaving the
whole screen full of sea. It now rides higher and further back (the same
treatment the rowboat camera got), with its floor above the waterline, so
swimming reads like the normal on-land chase view.

## August 5, 2026 (donkey) — the donkey swims now

Your donkey no longer sinks to the lakebed when it follows you into water.
In the shallows its hooves stay on the bottom like before; once the water
is deep it floats up to the surface, nose up, gently bobbing, legs
paddling, and swims after you wherever you go. Other players' trailing
donkeys float the same way on your screen.

## August 5, 2026 (rowing follow-up) — hands on the grips, both hands busy

### Hands meet the handles
The arms were rowing a half-cycle out of step with the oars — reaching
forward while the handles swung back. The stroke phases are now aligned:
arms reach forward exactly when the handles swing forward, pull back as
they come back, and the arms angle inward to the grips instead of splaying
out to the gunwales. The oarlocks moved slightly ahead of the bench so the
handles sit in front of the rower where his hands are.

### The blade works the water properly
The blade was lifting during the pull and dragging during the return —
backwards. It now stays buried through the pull and lifts clear on the
way forward, like actual rowing.

### Rowing takes both hands
Weapons AND the shield now stow automatically the moment you board, and
come back when you step off. Attacks, guard, and every spell (including
quick heal) are disabled while boating or swimming — no casting frost
bolts from the rowing bench.

## August 5, 2026 (hotfix) — un-piling the great monster huddle

The "keep creatures out of the water" pass had a bad wet test: it treated
anything below 0.35m elevation as underwater. The town plateau sits at
exactly 0m, so every monster, boss, tree and ore rock around town was
flagged "wet", found no slope to climb on the flat ground, and took the
emergency "walk to the capital" fallback — all of them, into one pile at
the center of the old arena ring.

Wet now means what it should: below sea level. Everything on land is left
exactly where its builder put it, so monsters, bosses, trees and rocks are
back in their original spots automatically. Things that really were in the
water still walk themselves ashore. World gen bumped so the relay accepts
the corrected world without waiting for an empty room.

## August 5, 2026 (later) — one-piece oars, rowing that actually rows

### Oars a carpenter would sell you
The oar blades were floating disconnected next to the shafts. Each oar is
now ONE continuous piece: a grip by the rower's hands, a round shaft
running through the oarlock, and a throat and blade welded onto the tip of
that same shaft, all on one axis. The whole stick slopes down from your
hands into the water like a real oar. On the stroke the blade lifts clear
of the water on the way forward and drops back in to pull.

### Hands and handles on the same beat
Your arms and the oars now row on the SAME clock (and other players see
the same thing), so the hands and the oar handles move together instead of
drifting apart on two separate timers.

### No more bouncing while rowing
The run-cycle bob is fully switched off in a boat and while swimming. You
rise and fall only with the hull now — your seat is glued to the bench,
including the gentle bob other players see on your boat.

### Swimmers lean the right way
Swimming forward now pitches you FORWARD into the water instead of
leaning backward, and turns bank around your direction of travel, so the
crawl finally reads like swimming.

## August 5, 2026 (follow-up) — a rowboat a shipwright would recognize

The blocky box-boat is gone. The hull is now built the way real boats are:
six cross-sections lofted from a flat transom stern to a raised, pointed
bow and skinned into one watertight shell — curved, flared sides, a sheer
line that sweeps up toward the stem, gunwale rails that follow the curve,
floorboards, a rowing bench, and a small foredeck sealing the bow. No more
seeing the water through the front of the boat, no more panels that don't
meet. Same seat, same oars, same controls.


## August 5, 2026 — you SIT in the boat, and swimmers stopped barrel-rolling

### Rowing, seated, like a person
You now sit down IN the hull — hips on the bench, legs locked forward,
no more hovering above the boat. Your body is bolted to the hull: it
cannot spin on deck anymore. Only your head turns to follow the camera,
clamped to a natural range.

### The boat drives like a boat
W rows forward along the hull's heading and S back-paddles; A and D steer
the hull; the mouse is pure free-look. You can hold W dead straight while
looking all around — driving and looking are fully separate now. Shift is
still the full-speed row. The camera also rides higher and a touch farther
back while aboard, so you see the boat and the water instead of a wall of
knight.

### The swimming barrel-roll is dead
Turning while swimming rolled your whole body over like a spit-roast —
a rotation-order bug: the body was laid prone first and then turned around
its own tilted axis. Rotation now yaws flat around the world's up axis
first, then tilts. Turns pivot cleanly with a gentle bank, no more
backflips.

### Wading before swimming
At rest or moving slowly in deep water you tread more upright; the body
lays down into the full prone stroke as you pick up speed, and stands back
up as you slow. The transition is blended, not snapped.


## August 5, 2026 (small hours) — B for boat, and everyone out of the pool

### B — launch / stow the rowboat
One key for the boat now: press B at the waterline to launch and board,
press B again (aboard or beside the hull) to stow it back in your pack.
A prompt appears whenever the boat is out — "B — STOW BOAT · X — HOP OUT"
while aboard — and B is listed in the menu's key bindings.

### Monsters stay on dry land
Wolves, deer, and everything else were wandering into the lake and rivers
and spawning in the drink. Every creature's spawn point now walks itself
uphill to dry land when the world builds (all clients and the server agree
on the moved spots), monsters can no longer step into water while roaming,
and any beast that somehow ends up wet wades straight out. When swimming
combat becomes a thing, they'll learn to chase you in — deliberately.

### No more trees in the lake
A handful of trees and mining rocks were still standing in open water —
they were placed on the dead-flat lake bed where the "walk uphill to shore"
rule had no slope to follow. Flat-bottomed water now routes them toward
town instead, and every last tree, rock, and oak stands on dry ground.


## August 4, 2026 (later that night) — the keys work, the seams are gone

### Z and H actually do something now
Honest bug: the donkey turbo (Z) and the town teleport (H) shipped wired to
a key filter that silently ate both keys — they never reached the game at
all. Fixed. And while fixing it, turbo got simpler: when it's ON, you move
at five times speed while mounted, walking or sprinting, no Shift required.

### You can SEE your bindings
While mounted, the prompt now reads "X — DISMOUNT · Z — TURBO ON/OFF" and
updates live. The menu's key list gained X (mount / hop out of boat),
Z (donkey turbo), and H (teleport to town).

### Region borders blend now
Where two regions met — Heartlands grass against Ironspire rock, steppe
against ash — the ground changed color in hard stair-steps along the data
grid. Region colors now blend across a soft dithered band about fifteen
meters wide, so each biome fades into the next the way the coastline
already fades into the beach.


## August 4, 2026 (night) — swimming feels like swimming, and H takes you home

### The swimmer got coaching
Your body now faces the direction you are actually swimming — strokes carry
you straight instead of crab-gliding wherever the camera points. Turning
banks you into the turn and the heading follows smoothly, like a real
swimmer coming about. The stroke itself is calmer and cleaner (no more
windmilling), your weapon is stowed while you are in the water, and if you
stop, you float facing the way you were going while the camera orbits free.

### Swim camera fixed
The camera now rides level with you at the surface instead of hovering
too high off the water. Boat and land framing are untouched.

### H — teleport to town
The world is enormous and testing shouldn't be a hike. Press H anywhere to
warp back to the spawn camp — there's a hint in the bottom-right corner so
nobody has to remember it. If your rowboat is deployed it is stowed safely
into your pack first. This is a testing convenience and will likely become
a proper spell or item later.


## August 4, 2026 (late) — boats for everyone's eyes, and dry ruins

### Your friends can see your boat now
The rowboat is synced: everyone in the world sees the hull, sees it pointed
the right way, and sees the oars pulling at your actual rowing pace.

### You sit and row like you mean it
Proper rowing pose: seated low in an open hull (the boat got rebuilt — open
cockpit, bench, real pivoting oars), legs forward, arms pulling the stroke,
weapon stowed while your hands are on the oars. The hull trims forward as
you pick up speed. No more standing statue on a floating box.

### Getting OUT of the boat works now
X hops you out and actually steps you ASHORE: the game walks uphill out of
the water and puts you a stride past the waterline, so the boat can't
scoop you straight back in. Out at sea with no shore in reach, X drops you
in the water beside the hull as before — touch the hull to climb back in
(and that grab now only happens when you're properly IN the water, never
while you're walking the beach).

### Boat camera behaves like land camera
Afloat, the camera now treats the water surface as the ground, exactly as
if you were standing on a flat field at sea level. No more sagging half
underwater or hugging the hull.

### The castle ruins are back on dry land
The old ruins site ended up under Lake Argent when the real world arrived.
The whole site — walls, towers, rubble, and its goblins — now stands on the
plateau EAST of town. Scattered trees and rocks that were left standing in
the lake and rivers have all stepped out onto dry ground too (mining rocks
and choppable trees stay in sync for multiplayer — everyone sees them in
the same new spots).

Everyone should hard-refresh (Ctrl+Shift+R) after this one.


## August 4, 2026 (evening) — you can SWIM, and everyone owns a rowboat

### Swimming is in
Walk into any water deeper than your waist and you swim: slower than running,
no attacking or blocking while you're in the drink, with a proper stroke
animation. Your donkey swims too — stay mounted and it paddles you across
with its head up. Rivers are now crossable anywhere, not just at the fords.

### The rowboat is an item, and it is yours
Everyone gets a ROWBOAT in their pack on login (already had one? It won't
duplicate — pack, worn and bank are all checked). Drag it onto your action
bar. Stand at the waterline facing open water and use it: the boat drops in
and you're aboard. WASD rows at your sprint pace; HOLD SHIFT to row flat out
at five times walking speed. X hops out without packing it up — swim back
and touch the hull to climb back in. Use the item again (aboard or beside
the boat) to stow it back in your pack. Log out with it deployed and you'll
find a fresh one in your pack next login, guaranteed.

For now the deployed boat is only drawn on YOUR screen — friends see you
gliding across the water without it. Properly shared boats come with the
trade update.

### Donkey turbo (testing helper)
The world got three hundred times bigger and your legs did not. While
mounted, press Z to toggle TURBO: sprinting on the donkey moves at five
times sprint speed so you can actually explore Asterra. Sprinting while
mounted no longer drains your stamina either — the donkey does the work.

### The coastline got fixed
Shores were jagged stair-steps that dropped into the sea like cliffs. The
whole coast is rebuilt around a smooth shoreline profile: gentle wadeable
beaches, a soft slope into the deep, no more triangle-toothed coasts.

### The ground got a face
Terrain now has an actual surface texture — mottled turf on grass, grit on
sand — instead of flat untextured color, and the too-bright washed-out look
at altitude is gone. Beach sand now only hugs the actual waterline (a few
meters) instead of painting whole regions; the capital plateau is properly
green. Deserts are still sand everywhere, as deserts should be.

### World version mismatch — fixed
If you saw "WORLD VERSION MISMATCH - RELOAD" at the top of your screen: the
multiplayer server was still holding the old world's fingerprint. New world
builds now replace the server's copy automatically. Everyone should
hard-refresh (Ctrl+Shift+R) once after this update.


## August 4, 2026 (later) — ASTERRA: the whole new world is under your feet

### The world map is real now
The old 336m circle of scrubland is gone. The full world of Asterra from the
world map is generated under the game: two continents (Valewold in the west,
Ashmar in the east), the Sundered Sea between them, the Shattered Isles,
Driftwatch Isle, the Ironspire and Ember mountain ranges, Lake Argent, the
Great River and the Cinder Run, snowfields in the Frostwild, marsh in the
Mistfen, desert in the Sunscorch Barrens. It is about 6.6km east to west —
roughly 300 times the area of the old world — and every hill and coastline
matches the map because the terrain is baked straight from the map file.

The land streams in around you in chunks as you walk, detailed up close and
coarser in the distance, and it is generated from a seed, so every player
stands on exactly the same ground (verified: browser and server-side height
checks agree to the millimeter).

### Where you are now
The town, the bank, the arena, and everyone you know now stand at THE CAPITAL
site on the southeast shore of Lake Argent, in the Heartlands. Your character,
inventory, bank, skills, and quests are untouched. If your saved position was
somewhere in the old world you will find yourself in or near town.

### What stops you (for now)
Deep water. You can wade in up to about waist depth; past that the coastline
and rivers hold you back, and you slide along the shore instead of sticking to
it. Swimming ships next, then boats. Bridges are also coming with the water
work — until then the Great River still has a shallow crossing at the Argent
Bridge site.

### Honest list of what is NOT in yet
Trees, rocks, and monsters outside the capital area (the wider world is empty
land so far — that is the next phase along with the other towns), swimming,
boats, the world map screen, and the housing districts. If you sail your eyes
along the horizon and see bare hills, that is intentional, not broken.

### If anything looks wrong after the update
Hard-refresh the page (Ctrl+Shift+R) so the new bundle loads. Old cached pages
and the new world disagree about the ground.


## August 4, 2026 (night) — you come back where you left, and F loots

### The world remembers where you logged out
Your position and your donkey are part of your character save now. Log out
halfway across the map and you come back standing there, with your donkey under
you if you were riding it, or waiting exactly where you left it if you were
not.

Dying still sends you back to the camp — that has not changed, and it should
not. A fresh character still starts at the camp too, and a save with an
impossible position in it is ignored rather than trusted, so nothing can strand
you outside the world.

Your position is written on a slow beat rather than every step, and logging out
or closing the tab flushes it immediately.

### You can see each other's donkeys
Mounts were only ever drawn for their owner. Everyone else saw you jogging
along at riding speed with nothing underneath you, and a dismounted donkey was
invisible entirely. Now you can see other players riding, and see their donkey
trailing after them on foot when they are not.

### F loots the whole sack
One key. It used to open the bag and leave you reaching for T as well, which is
two presses for the thing you want every single time.

The bag now only appears if something would not fit in your pack, so you can
see what is left on the ground. A clean sweep never opens a window at all.
Escape still closes it, and T still works if that is the habit.

## August 4, 2026 (later still) — the Hollow King, and spells on hillsides

### Spells were being destroyed the instant they were cast on high ground
This is the big one, and it affected every caster and archer in the world, not
just Mr. Sailers.

The simulation is deliberately flat: it works in X and Z and leaves height to
your machine to draw. So when it fires a bolt it can only say "chest height",
meaning 1.7 metres above sea level. Stand on the hill north-west of the mere,
where the ground is 5.4 metres up, and that bolt spawns four metres
underground. The game's own rule is that a projectile below the ground is gone,
so it was deleted on its first frame. On the occasions one survived, it flew
along at sea level, far below anyone standing on the hill, and the hit check
requires the bolt to be within 1.6 metres of your chest vertically. It never
was.

Bolts now ride the landscape at the height they were cast. Measured on a 5.4
metre rise: the bolt holds 2.66 metres above the ground for its entire flight
and lands on a player standing up there. Before, it did not survive one frame.

### Mr. Sailers casts from his staff, not from his donkey
The simulation has no models, so it reported spells leaving a generic point a
metre in front of the caster at chest height. On a man sitting on a donkey,
that point is the middle of the animal. Spells now leave the actual end of his
staff, which on the same hilltop is 2.66 metres up rather than 1.7. Bows fire
from the bow and the Plague Rat spits from its snout, on the same rule.

### The Hollow King
He has always swung two-handed cleaves while visibly holding a sword and
shield. He carries the greatsword now, which is what his moves were describing
all along.

His fighting matches the rest of the roster: a fast cleave and a committed
overhead, the same quick-and-heavy pairing every other fight uses, instead of a
single heavy swing on a one to two second cooldown behind a 1.3 second
animation. He was landing roughly one real swing every three seconds and
filling the gaps with ordinary sword swings that were not his. Now every blow
he throws is his own: 15 attacks became 18 over the same stretch, all of them
greatsword work, and he never stands still.

The ground slam is still the thing you have to read and dodge, and he throws it
more often the angrier he gets.

## August 4, 2026 (later) — the two bosses, and where numbers appear

### Mr. Sailers casts again, and starts casting straight away
He was casting, but his opening move was a taunt that stood him still for two
seconds with no animation and no shout, and every real spell sat on a six to
eleven second cooldown behind it. A fight began with him doing nothing.

He now has three spells and almost always has one in the air: a fast bolt as
his backbone, a three-bolt volley, and a snare. The charge stays. The taunt is
shorter, rarer, and now actually shouts at you. Measured over the same 22
seconds: he spent 59% of the fight motionless and now spends 21%, and he throws
three different spells instead of one.

### The Plague Rat is a rat again
It had no pinned weapon, so the simulation periodically decided it should be
using a staff, backed it off to twenty feet and had it lob frost bolts at you.
It now keeps its paws and fights with the dire wolf's claw and bite, in your
face where it belongs. Swings went from 12 to 23 over the same stretch, and it
no longer drifts away mid-fight.

Its toxin spit was doing two things wrong. It only unlocked below half health,
and it was throwing a stray frost bolt alongside the toxin because a scripted
spell was firing its own projectiles *and* a generic fallback set. The spit is
now available from the start of the fight, works at any range (it fights with
its face in yours, and a spit gated at three metres simply never happened), and
throws toxin and nothing else.

### Bosses stopped freezing mid-move
While a boss was swinging or casting, the script took the turn and left it
frozen on whatever speed it happened to be carrying. It now hands the turn back
to the ordinary movement step, which already slows a monster to a crawl mid-
swing, keeps it facing you, and holds it at its weapon's range. That is most of
what read as broken pathing on both bosses.

### Charges, leaps and taunts were invisible
The game was ignoring boss announcements entirely. A charge, a pounce, a leap
or a phase change arrived as nothing but a boss standing still. They now play
their animation, make their noise, and shout their line.

### Damage numbers sit on the thing being hit
They were anchored to the point of impact, which is wherever the blade happened
to be or wherever a bolt struck, then given a random jitter, then allowed to
walk up to nine steps upward to avoid overlapping. Between the three of them a
number could end up most of a screen away from what it belonged to.

Every damage number now sits at the centre of the body it belongs to, on you
and on enemies alike. Measured: dead centre, zero pixels off. Two numbers
landing at the same instant still stack upward so both stay readable, but only
two steps, and the random jitter is gone.

### XP floats above your head and reads like a sentence
It now says **+15 Woodcutting XP** rather than "+15 WOODCUTTING", appears above
your head rather than in the hitsplat pile, and drifts slowly upward as it
fades instead of popping. Several skills at once stack neatly.

## August 4, 2026 — everything fights like a goblin now

The goblins were the only thing in the world whose combat felt right. This is
the rest of the roster brought up to them.

### Wolves, Jim and Pete could not hit you at all
Not "hit you weakly" — could not land a blow, ever. A tool swing or a paw swipe
used to have its damage and reach written inline in the game code, and when the
fight moved onto the server that inline shape was left behind. The server read
the shared rulebook, found a swing with no reach and no damage, and dutifully
sent it out. So a dire wolf would wind up, swing, connect visually and do
nothing. No damage, no hit splat, no reaction. Same for Jim the Lumberjack and
Pete the Prospector.

Both now carry a real shape in the rulebook where the server can see it.

### Dire wolves have a paw slash and a bite
Rather than a sword and shield they never had, wolves get the goblin's exact
setup rebuilt around a beast: a quick one-handed paw slash, an occasional
committed bite, and no shield, so a wolf never stops to block. Both are
dodgeable on reach and arc like every other swing in the game.

### Nobody reacts slower than a goblin
Reaction speed was authored per NPC, and most of the roster came in under the
goblin. Austin Little was at 0.42 against the goblin's 0.62, Alexis Ayala at
0.3. In practice Austin was swinging barely half as often as the rabble, which
reads as him not fighting back. Anything that can fight now runs at the goblin's
baseline or its own value, whichever is higher, so the Bandit Captain still
reacts like a captain. Skittish wildlife is left alone, since raising it would
only make deer sprint away faster.

Damage is untouched. Alexis still hits like Alexis.

### The Bandit Captain
His flourish is gone. It was a psych-up the game played while closing distance,
and once the server owned the fight it turned into 1.2 seconds of standing
still at range. His melee now swings on a goblin's cadence rather than once or
twice a second. The leap and the shield bash stay, because those are what make
him read as a captain.

Mr. Sailers, the Hollow King and the Plague Rat are untouched, as agreed.

### Measured, sixteen seconds each, one on one

| | swings/min before | after | landed a blow before |
|---|---|---|---|
| Goblin (the reference) | 33.8 | 33.8 | yes |
| Austin Little | 18.8 | 33.8 | yes |
| Alexis Ayala | 22.5 | 37.5 | yes |
| Steven Carrasco | 30.0 | 33.8 | yes |
| Bandit | 33.8 | 33.8 | yes |
| Bandit Captain | 41.3 | 52.5 | yes |
| Jim the Lumberjack | 26.3 | 52.5 | **never** |
| Pete the Prospector | 26.3 | 52.5 | **never** |
| Dire Wolf | 41.3 | 41.3 | **never** |

Jim and Pete swing quickly and hit for about 3. They are still townsfolk who
will not start anything with you.

## August 4, 2026 (very late) — bandits fight like goblins, hit splats are back

### Every monster now fights the way the goblins do
Goblins were the only ones authored with their weapon pinned to melee. Everyone
else was left open, so the simulation would periodically decide a bandit should
be using a bow, back it off to bow range, and orbit you out there. That is the
"weird pathing" — it was never a pathing bug, it was the monster changing its
mind about what fight it wanted.

Every ordinary monster now keeps the weapon it spawned with. Bosses and casters
are untouched, since switching is part of what they do.

Measured, same spawn 18m away, before and after:

| | closest it gets | what it throws |
|---|---|---|
| before | 9.1m | ranged shots only |
| after | 1.8m | real melee swings, 3.0–3.4m reach |

### Monsters are no longer twitchier than they should be
The reaction-speed setting sent to the server fell back to 1.0 for any monster
that did not name its own, instead of falling back to your difficulty. On squire
that is 0.62, so every unnamed monster has been reacting about 60% faster than
intended since the server took over. They now match the difficulty you picked.

### Hit splats show up again
The damage number that appears when something hits YOU was being placed at sea
level rather than at your feet. On flat ground you could not tell. On any rise
it spawned below the map and the number flew up from off the bottom of the
screen, so it read as simply missing. Measured on a 5.4m rise: it was landing at
718 pixels down a 720 pixel window, and now lands on you.

## August 4, 2026 (late night) — animations play again, townsfolk fight back

### You can see swings and deaths again
Animations are driven by how far through a move a monster is, and the game
stopped running that clock when the server took over — it only jumped forward
whenever an update arrived. Ten times a second is enough to move something
around convincingly, and nowhere near enough to show a sword swing or a body
falling, so both effectively vanished.

The animation clock now runs on your machine at full frame rate, and the
server's updates only correct it when something genuinely changes. Swings,
casts and deaths all play properly again.

That is also why a goblin looked like it was just circling you: it was
attacking the whole time, you simply could not see it wind up or swing.

### Townsfolk defend themselves
Only the timid and the genuinely passive are supposed to refuse a fight. I had
lumped townspeople in with them, which made Alexis Ayala and the rest permanent
punching bags — you could hit them all day and they would keep wandering. Hit
one now and it fights back, the way it always did. Deer and other skittish
wildlife still just run.

## August 4, 2026 (night) — corpses, fighting back, and safe ground

Three more from live play.

### Dead monsters actually die
A killed monster kept being reported as standing idle, so its body stayed put
and walked on the spot forever. The server now says plainly when something is
dead, the body drops, and it disappears a moment later. Anything already dead
when you join is simply not there, rather than appearing as a corpse jogging in
place.

### Safe ground worked too well
Two bugs, opposite directions.

The town has always protected both the player standing in it and any monster
that wandered in, while the starting camp only protects the PLAYER. I had made
the camp protect monsters too, which meant every monster living anywhere near
the camp could never fight back — anywhere in the world, forever. Fixed.

Then the code that handed those zones to the simulation was quietly throwing
away the separate player and monster radii, which broke safe ground entirely in
the other direction. Also fixed.

Worth knowing, because it is deliberate and always has been: **nothing will
fight you while you are standing in the starting camp or in town.** If you are
whacking something and it refuses to hit back, step out of the safe circle.

### Smoother, and the last of the stutter
Monsters no longer guess ahead of the server between updates, and a monster
peacefully wandering is now updated as often as one in a fight.

## August 4, 2026 (later) — monsters move properly and fight back

Fixes for the first live run of the server simulation. Three real faults, all
found from the same report: monsters crawling, lurching, and ignoring you.

### The world now runs on its own clock
The simulation only advanced when a player's message arrived, which tied every
monster's movement to how often your browser happened to send. One player on a
slow frame rate made monsters crawl in lurching steps for everyone. The server
now keeps its own clock while anyone is connected.

Measured with a client deliberately sending only twice a second: monsters still
update ten times a second, still walk at full speed, and still move in small
smooth steps. Before this fix that client saw them at a crawl.

### Hitting something now makes it fight back
Only walking close enough could start a fight. Anything you shot from range, or
anything with a small notice radius, simply stood there and took it. Landing a
hit now makes it personal, the way it always did before the move to the server.

### Archers and mages actually throw something
A monster with a staff or a bow played its whole wind-up and then nothing left
its hands, so it looked like it was ignoring you. Ranged attacks now fire what
they are supposed to fire.

### Smoother monsters
Movement between server updates was guessing ahead and then getting yanked back
when the real position arrived, which is what made everything look jagged. It
now plays cleanly from one known position to the next and never guesses. Updates
also went out at a rate based on whether a monster was in a fight, which meant a
monster peacefully wandering around was only reported once a second. The rate now
follows whether it is MOVING.

## August 4, 2026 — monsters now run on the server, end to end

The rest of it. Monster movement, decisions, attacks, projectiles and boss
fights have all moved into Cloudflare. No player's browser simulates anything
any more, and the idea of one player being "in charge" of the world is gone.

### Monsters are simulated by the server (phase 2)
Their brain now runs in the same place for everyone: chasing whoever hit them
or the nearest player, aggro ranges, giving up when dragged too far from home,
breaking off inside town and camp, wandering, keeping their distance by weapon,
circling once in reach, guarding and dodging. Wildlife still bolts. Packs still
shove each other apart so they surround you instead of stacking up.

Every player draws the same feed, so two screens can no longer disagree about
where a monster is or what it is doing. Running monsters locally still exists,
but only as a fallback if your connection drops.

Each player is only sent the monsters near them. That is what keeps a much
bigger world costing the same per player as this one.

### Attacks land at the same moment for everyone (phase 3)
This is the dodge fix.

The server announces each attack once, in full: the exact instant it begins on
the shared clock, where the monster is standing, which way it faces, how far the
swing reaches and how wide it is. Every player plays the identical telegraph at
the identical moment.

Then your own machine decides whether YOU were inside it when it landed, judged
against where you actually were. Your dodge is judged against what you saw, not
against somebody else's stale copy of you. That was the real reason dodging felt
wrong, and it is gone.

Rolling still gives you invincibility frames, and a swing that reaches all the
way round (the Hollow King's ground slam) now correctly hits behind him too —
that was a rounding error that let you stand in the one spot it could not touch.

### Projectiles cost nothing to watch (phase 4)
The server says where a bolt started, how fast it is going and when it left.
Every machine draws the identical arc from that, and nothing further crosses the
network. A boss throwing a volley costs the same as throwing one. Each player
checks only themselves for a hit.

### Bosses are scripts now (phase 5)
The Hollow King, Mr. Sailers, Austin Little and the Plague Rat are described as
data instead of code: phases that change as their health falls, a move list per
phase, and each move declaring its own cooldown and the range it wants. They
shout when they change phase, they get faster and hit harder in later phases,
and the King's slam, leaps, Sailers' charge, taunt and volley, and the Rat's
pounce and spit all run from that table.

The point of doing it this way: a bigger, meaner boss later is a longer table,
not new engine code.

### Verified
Six server suites, all passing: manifest and clock, monster movement and
interest filtering, boss scripts and projectiles, health/death/loot, ownership
handover, and message routing. Movement checks confirm monsters close on you and
stop at their own reach rather than walking into you, that wildlife flees, that
distant monsters are filtered out of your feed, and that two players are sent
the same positions. Boss checks confirm phase changes fire with their shout,
volleys spread rather than stacking, and every projectile carries a full flight
path. Dodge geometry is checked seven ways, including standing behind a
full-circle slam and rolling through a hit.

## August 4, 2026 — server simulation, phase 1 (foundations)

Groundwork for moving monsters fully onto the server. Nothing about how the
game plays changes yet; this is the scaffolding the next phases stand on.

### One rulebook instead of two
Attack timings, reach, arcs, damage, movement speed and the loot tables now
live in a single file that gets built into both the game and the server. Until
now the server had its own hand-copied loot table, which is exactly the kind of
thing that quietly drifts and then two players see different drops. That can no
longer happen: there is one copy, and the build refuses to run if it cannot
find where to put it.

### The world is now something the server knows
The game now hands the server a full description of the world when you join:
every collision shape, the safe ground around town and camp, and all 53 monster
spawns with their stats. It carries a fingerprint, and the server keeps the
first one it is given.

If somebody joins running an older build, the server says so and its copy wins,
and that player is told to reload rather than quietly playing in a world that
does not line up with everyone else's. A genuinely new build replaces the world
only when nobody else is in it.

### A shared clock
Every message from the server now carries the server's time, and each player
works out their own offset from it. This is what will let a boss's wind-up
start at the same real moment on every screen no matter whose connection is
worse.

Getting this right needed one real fix: a browser throttles tabs that are not
in focus, and a throttled tab can sit on a reply for seconds, which would have
poisoned that player's clock. Samples that took too long are now thrown away
and the estimate uses the fastest round trip rather than the average. Measured
on a deliberately starved machine, the estimate went from being eight and a
half seconds wrong to half a millisecond.

### Verified
Thirteen new server checks covering manifest upload, fingerprint agreement,
refusing a mismatched world while players are connected, keeping monster health
across a rejoin, accepting a new build into an empty world, and loot rolling
from the shared table for both ordinary monsters and bosses. The existing
combat, ownership and loot suites all still pass, plus the game-side check that
every shared number arrives identical to what it replaced.

## August 3, 2026 (late night) — monsters stay in sync for boss fights

Follow-up to the server move. Every player was animating monsters on their own
machine, which meant two screens could disagree about where a monster was
standing and what it was doing. Measured across a live fight, positions
differed by an average of 1.9 metres, sometimes as much as 7, and one screen
showed a monster leaping while the other showed it standing still. Fine for a
wandering goblin, useless for fighting a boss together.

Monster positions and animations now come from one shared feed, so every
player sees the same fight. Running the monsters locally is demoted to a
fallback that only kicks in if that feed actually stops, which is what keeps a
sleeping or crashed tab from turning monsters back into statues.

Measured again after the change, same test:

| | before | after |
|---|---|---|
| average difference between screens | 1.89 m | 0.60 m |
| worst case | 7.02 m | 1.99 m |
| animation disagreements | yes | none |

That remaining half-metre is normal network smoothing, and the test machine
was running two copies of the game on software rendering. On real hardware it
will be tighter.

### Two real bugs found while measuring
- **A dropped connection made you harmless.** If your connection died, the game
  still believed the server owned monster health, so it stopped applying damage
  locally while having nobody to report hits to. You could swing forever and
  nothing would take damage. Losing the connection now falls back to running
  monsters locally until it returns.
- **Reconnecting left you fighting ghosts.** After a reconnect the game never
  asked the server for current monster health again, so you could be fighting
  something the server considered long dead. It now re-syncs on every reconnect.
- A monster more than four metres out of place now snaps into position instead
  of sliding there, so a brief network hiccup cannot leave a boss visibly in the
  wrong spot mid-fight.

## August 3, 2026 (night) — monsters now live on the server

This is the change you asked for. Monster health, death, respawn, kill credit
and every loot sack have moved off players' computers and into the Cloudflare
server. No player's browser decides any of it any more.

### What this fixes for good
- **Monsters freezing.** Every player now animates monsters on their own
  machine. If someone's tab sleeps, crashes or lags, it is invisible to you.
  There is no longer a single player everyone depends on.
- **Hits not registering.** Damage is reported to the server, the server
  subtracts it and tells everyone the new health. Two players can no longer
  disagree about how hurt something is.
- **Monsters not dying or dropping loot.** The server declares the death, rolls
  the loot itself, and creates the sack. It survives a player leaving mid-fight.
- **Respawns.** Timed by the server, so they happen whether anyone is watching
  or not, and they still happen if every player closes the game and comes back.
- **Loot.** Sacks live on the server. The killer's one-minute claim, quantities,
  and the sack expiring are all decided there. Nobody can grant themselves loot.

The server keeps this in permanent storage, so even if Cloudflare recycles it
mid-fight nothing is lost. Respawn timers run on a scheduled wake-up rather
than a countdown, so they fire correctly even while the server is idle.

### Also fixed
- A player whose tab loaded in the background could silently fail to hand over
  to the server and drift out of sync with everyone else. Registration no
  longer depends on browser timers, which are throttled to a crawl in
  background tabs.

### Verified
Two real browsers against a live server: damage agrees on both screens, deaths
and loot sacks appear for both, the killer can loot and a bystander is refused
during the claim window, and with one player's tab deliberately frozen the
monsters keep moving and keep taking damage for the other player. Twenty-two
separate server checks cover health, death, loot rules, forged messages and
respawn.

### Still to come
Monster movement is still drawn by each player locally rather than dictated by
the server, so positions can differ very slightly between screens. Nothing that
matters depends on it any more.

## August 3, 2026 (late) — combat sync fixed

### Fixed: hitting monsters did nothing
Attacks landed on your screen but the monster never lost health, never fought
back, never died and never dropped loot. One line caused it.

Only one player runs the monsters. Everyone else sends "I hit monster number 7"
to that player. The relay server stamps who sent each message, and it was
writing the sender's id into the same field the game uses for the monster
number. The owning player received "I hit monster number pj4x8b", found no such
monster, and dropped the hit on the floor. Same field, same result, for chopping
trees and mining rocks.

### Fixed: everything the owner sends back to one player
The old peer-to-peer code addressed replies through per-player connections.
Those no longer exist under the relay, so the owner was writing into an empty
list and every one of these was silently thrown away:

- monster damage aimed at another player (remote players took no damage at all)
- loot grants and refusals (nobody but the owner could pick anything up)
- monster death notices (no kill credit, no quest progress)
- tree and rock depletion replies
- existing loot sacks sent to a player who just joined

All of them now route properly. Two message types, refused-loot and
sack-expired, were not even on the relay's allowed list and were being dropped
outright; both are through now.

## August 3, 2026 (evening) — frozen worlds fixed, one action bar

### Fixed: monsters freezing (not fighting back, not dying, no loot)
Cause found. Whichever player joined first runs the monsters, and when that
player's browser tab goes into the background, Chrome freezes it. Monsters kept
their health but stopped animating, stopped fighting, and deaths never
processed, so no loot dropped. Everyone else in the world was watching a
frozen simulation.

Three layers of fix, so this cannot come back:

- A player whose tab goes hidden now hands the simulation to a visible player
  immediately.
- If ownership lands on a tab that is already hidden, it hands it back the
  moment it notices. The server only ever hands simulation to a VISIBLE
  player, so two hidden tabs can never pass it back and forth.
- If the owning tab freezes so hard it cannot even say goodbye, the server
  evicts it after 8 silent seconds and promotes the most recently active
  visible player.

### One action bar
The duplicate action bar inside the inventory is gone. The bar at the bottom
of the screen is the only bar, and it does everything:

- Drag weapons, tools, and potions from your pack straight onto it
- Drag between slots to rearrange, drop onto a full slot to swap
- Drag an icon off the bar to unbind it (the item stays in your pack)
- Click a slot to use it, exactly like pressing its number key
- Right-click a slot to unbind
- Icons appear and disappear instantly, and bindings save with your character
- Empty slots stay empty

Also fixed along the way: equipping by number key crashed if any bar slot was
empty. That bug was hiding in the old bar code.

## August 3, 2026 — multiplayer rebuilt, log out added

**Status: live.** The relay is deployed at `grim-arena.kevin-230.workers.dev` and the
game at rideriteauto.github.io/grim-arena is connected to it. Verified on the
live site with two players: both connect, the server names one owner, and player
position, health and name all cross correctly between them.

### Log out
There is now a **LOG OUT** button on the pause menu (press Escape while in the
world, it sits under RESUME). It saves your character, hands the world back to
the other players, and returns you to the login screen. You no longer have to
reload the page to switch characters.

### Multiplayer rebuilt on a relay server
Players used to connect directly to each other, with one player elected as
host. That design was the source of every multiplayer outage. It is gone.

Every player now holds a single connection to a small always-on server (a
Cloudflare Worker, in `relay-worker.js` in this repo). The server tracks who is
present and names exactly one simulation owner.

What this removes, permanently:

- **Blocked home networks.** Some networks refuse direct player-to-player
  connections, and there was no fallback. Players could see the world existed
  but never connect, with no error shown. A relay does not need direct
  connections at all.
- **Two players in separate worlds.** With no central authority, two players
  could each decide they were the host and never discover each other. The
  server is now the only thing that decides, so this cannot happen.
- **Dependency on the host's PC.** If the host alt-tabbed, crashed, or closed
  the tab, the world froze or died for everyone. Ownership now moves to the
  next player instantly and automatically, announced by the server.

### Bugs fixed along the way
- A single failed connection attempt used to move a player to a different world
  channel permanently, with no way back. This is the defect that most closely
  matched the reported symptom.
- One failed request to the save server used to disable the good connection path
  for the entire session and silently drop the player onto the broken one. It
  now recovers on its own after a short cooldown.
- The host announced itself every 20 seconds while the server declared hosts
  dead after 20 seconds. Any delay killed a live host. Now 7 seconds against 20.
- A player who joined as a guest still accepted incoming connections it was
  coded never to answer, so anyone dialing them got a healthy-looking connection
  that delivered nothing, forever.
- Chrome freezes background tabs, which used to stop the entire shared world
  whenever the host switched away. The network layer now runs on a worker clock
  that survives backgrounding.
- Failed connections used to hang for 15 seconds before giving up. Now 7, and
  the status line names the failure instead of spinning.

### Verified
On the deployed relay, and before that in two real browsers against a local copy: both players connect, see each other by
name and colour, positions track correctly, and when the host disconnects the
second player is promoted within a second with no errors on either side. The
relay's own test suite covers presence, ownership handover, message routing,
forged-message rejection, rate limiting and reconnection.

### Not done yet
Monster simulation still runs on the owning player's machine. Moving it into the
relay is the next step and is what will fix the frame rate drops during boss
fights with heavy projectile counts.
