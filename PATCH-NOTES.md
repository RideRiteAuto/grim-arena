# Grim World — patch notes

## August 5, 2026 (sigs-server) - Signature moves work on the server too

Boar, rat and goblin now throw their signature moves whether the fight is running on your machine or on ours.

Doing it properly meant moving the numbers rather than copying the code. The server never deals damage: it announces a swing by name, and every player's game judges its own dodge against the shape stored under that name. A move that only existed as special client code could never be thrown by a server-run monster at all. So the tusk hit and the tail whip are now real entries in the shared move table, exactly like a sword swing, and both the game and the server read the same numbers. There is one set, not two that drift.

The shriek needed no wire at all, since it does no damage. It just wakes goblins.

Two things had to be carried across that were not: a server-run monster had no idea what species it was or what its signature was, because the world list the game sends to the server dropped those fields. It now sends species, signature and kin tags, which is also what lets a shriek tell which of its neighbours are goblins.

The world generation number goes up as a result, so the server takes the new world list. Ground cover and node positions are seeded from that number, so trees, stones and ore veins will be in different places than they were yesterday. Nothing is lost, the world is just re-dressed.

TESTING, HONESTLY

The test harness here renders at about an eighth of real speed, which is now measured rather than guessed: five seconds of game time took forty four seconds of wall clock. That is what made me report a working boar charge as broken earlier this week, so tests now wait on the game's own clock instead of counting seconds on a stopwatch.

The server brain has its own test suite now, ten checks, and it runs the real code rather than reading it.


## August 5, 2026 (roam) - Monsters stay in their own fields

A bug that has been in the game since the world got big, found while writing a test for something else.

Wandering monsters pick a spot near home and walk to it. Before walking, the game checked that the spot was not too far away, and it measured that from the CENTRE OF THE WORLD rather than from the monster's home. Anything more than 162 metres out from the capital had its wander spot dragged back toward the capital. That was fine when the whole game was one arena about that size. In a world 4,800 metres across it meant almost every monster in it, everywhere, was slowly pulled inward instead of holding its own ground.

So: monsters stay where they live now. A wolf in the Greenwood wanders the Greenwood.

The same line was in the server simulation and got the same fix, so it holds whether the fight is running on your machine or ours.

ALSO

A monster walking home after giving up now keeps walking home even if nobody is watching it. The check for that sat below the code that picks a target, so the moment no player was nearby it fell through to ordinary wandering and ambled back at a third of the pace, sometimes never arriving.

HOW IT WAS FOUND, AND WHAT IS NOW IN PLACE

Yesterday's leash fix shipped a crash into the server simulation: it read the rules from a place they did not exist, threw on the first tick, and stopped every monster in the world from moving, attacking or respawning until it was hotfixed. The check that was supposed to catch that only read the file, it never ran it.

There is now a test that actually runs the server brain: it builds the same world the relay builds, ticks ten different kinds of monster through sixty seconds of simulation, and fails if anything throws. It also checks the things that are easy to break silently. It found both bugs above within a minute of existing.


## August 5, 2026 (zones-2d) - The Heartlands creatures fight like themselves

Boar, giant rats and young goblins each have their own move now. Not a reskinned swing, an actual different problem.

TUSK CHARGE, the boar. From five to twelve metres it plants, scuffs the ground in the line it is about to run, and then goes. It commits: once it starts it does not steer, so the answer is to be somewhere else by the time it arrives. Hits hard and knocks you off your feet. Nine second cooldown or so.

TAIL WHIP, the giant rat. Up close only. Winds up, then sweeps all the way round, so there is no clever side to stand on. Modest damage and a shove that puts you at arm's length again. About six seconds.

GOBLIN SHRIEK, the young goblin. Does no damage at all. It screams, and every goblin within twenty five metres that was not already interested comes running. Killing the one that shrieks is not the problem. Whatever answers it is.

Each has a real wind-up you can see and read before it lands, and each declines politely if you are at the wrong distance, so a boar with its nose against you fights normally instead of trying to charge from two metres.

ALSO FIXED, AND IT AFFECTED EXISTING FIGHTS

Charges used a single point check to decide whether they connected: is the target within two metres, right now. Anything moving quickly steps clean over that between two frames, so a fast charge could run straight through you and register nothing. Charges now test against the whole path covered since the last frame. Mr. Sailers benefits from this too.

WHAT IS NOT DONE

Server-run monsters do not fire signature moves yet. These live in the client's fight logic and the server simulation has no equivalent, so you will see them in single player and when you are the host. That is stated plainly rather than half-built.


## August 5, 2026 (hotfix) — the world had stopped moving

The monster simulation was throwing on its very first tick and had been down on
the live server: nothing walked, nothing attacked, nothing respawned, anywhere.

The new leashing code called two helpers, `roamRadius` and `walkHome`, that read
the rules through a variable called `R`. But `R` is a local inside `stepNpc`, not
something the file has at the top level, so both threw ReferenceError the moment
they were called, out of the middle of the simulation loop, taking every monster
in the world with them.

Both now take the rules as an argument, which is what every other helper in that
file already did. The whole file was swept for the same mistake: no function
reads a bare `R` any more.

Caught it because the relay's health endpoint reports `simErr`, which is exactly
what that field is for. Worth checking after any push that touches the sim.


## August 5, 2026 (zones-2c) - The roster goes back to full, and GRAPHICS: LOW thins the world

Content that was cut to fit a budget is back, and the budget is replaced by something that actually helps a slow machine.

The Heartlands roster was trimmed from the design plan's thirty-odd head down to twenty five, purely to stay under a 7,000 mesh ceiling. That ceiling turned out not to measure anything the renderer charges for. It is now back at full: six boar, ten giant rats, nine young goblins, seven hares.

Instead of everyone getting a thinner world so that slower machines cope, GRAPHICS: LOW now thins the world for the machines that need it. It already turned shadows and extra lights off. It now also:

- halves the ground cover, 159 props a chunk down to 72 in the same field
- dresses a smaller radius around you, nine chunks instead of eighteen

That is the honest place to give ground. It costs you scenery, not monsters, not reach, not anything you have to fight.

ONE THING WORTH KNOWING

Harvestable nodes do NOT move between graphics settings. That sounds obvious and it very nearly was not: ground cover and nodes were drawn from the same seeded sequence, so generating less grass would have shifted every tree and ore vein after it, and two players on different settings would have been chopping at trees the other one could not see. Nodes now run on their own sequence. Checked across four chunks at both settings: identical, every time.

Press F3 to watch what any of this costs on your own machine.


## August 5, 2026 (ops) — the game tells you when it has been updated

Shipping used to mean messaging whoever was online and asking them to log out,
because a browser that is already running keeps the old copy of the game until
it reloads, and the server will not swap the world over while people are still
on the old one.

Now the game handles it. Every client checks once a minute whether the build it
is playing is still the build that is deployed. When a new one lands you get:

  GAME UPDATE READY
  SAVING AND LOGGING YOU OUT IN 30s. YOUR PROGRESS IS SAFE.
  [ SAVE AND LOG OUT NOW ]

Then it saves and drops you at the front door, where your name is already filled
in and the password box is empty on purpose: press LOGIN & PLAY and you are back
in. One click, not a retype.

**It waits if you are fighting.** Getting yanked out at five percent of a boss
would be the single most annoying thing a patch could do, so if you have landed
or taken a hit in the last eight seconds the countdown holds and says so. It
holds for up to two minutes, then goes anyway, because one person parked in
combat must not be able to keep everyone else on an old build.

Two things worth saying plainly. Your progress was never actually at risk from a
push: saves already run every four seconds, every forty five seconds, and again
when the page closes. The old warning would have been a lie. And this now flushes
the save and WAITS for the server to confirm it before logging you out, which is
something even the LOG OUT button did not do.

There is no admin command and nothing to log into. Each client reads a static
version file, so there is no endpoint to secure and no message another player
could forge to kick everyone out. It also fires for any push at all, not only
one that remembered to announce itself.

For whoever is shipping: `python3 ship.py "what changed"` stamps the build,
packs both bundles, syntax checks the game, the relay and the sim, commits,
rebases, pushes, and then waits until GitHub Pages is really serving the new
build before telling you how many players are about to see the notice. It
refuses to run if PATCH-NOTES.md has no new entry.


## August 5, 2026 (reach) - You get the thing you are standing on

Interacting with the furnace when you meant the anvil, or Margaret when you meant Fenwick, is fixed.

There were two things wrong. The prompt and the F key both ran a fixed list, in order: bank, then sack, then Ball Pellinger, then Margaret, then Fenwick, then the furnace, then the anvil, then sheep. Whoever came first in that list won, no matter which one you were actually standing on. And the reaches were long and uneven, four point two metres for two of the townsfolk down to two for a sheep, so in a town where the furnace, the anvil and the smith stand a few metres apart you had three overlapping bubbles and no say in which one answered.

Now there is one list of what is in reach, both the prompt and the key read it, and it is sorted by distance. The nearest thing wins. The prompt can no longer name one thing while F does another, because they are the same lookup.

Reach is a consistent 2.6 metres for people and workstations, 2.8 for the bank chest, 2 for a sheep. Close enough that two things have to be nearly inside each other to overlap, far enough that you are not hunting for the exact spot. For scale, your furnace and anvil sit three metres apart, so standing at either one now offers only that one.

Also cleaned up while in there: the prompt used em dashes, which is against the brand rule. It reads F - SMELT IRON ORE now.


## August 5, 2026 (leash) - Monsters stop shaking at the edge of their ground

The one where a monster you dragged to the edge of its patch would stand there vibrating and clicking at you. Fixed, and the reason was daft.

Leashing was a distance check with nothing behind it. Hold a monster at its limit and stand next to it, and the code did this every single frame: too far from home, drop aggro, turn around; next frame, player is close, grab aggro, play the aggro sound, turn back; next frame, too far from home, drop aggro. Sixty times a second. That is the shake, and the aggro sound firing on every other frame is the noise.

Now, when a monster gives up it actually GIVES UP:

- It walks back to where it lives, and it cannot be pulled into a fight on the way. No amount of standing in front of it will restart the chase until it gets home.
- It walks back noticeably faster than it wanders, so it reads as leaving rather than milling about.
- It heals on arrival. You cannot wear something down by dragging it to the edge of its ground over and over.
- The aggro sound only plays on a real transition into a fight, never twice within a second and a bit.
- Nothing starts a fight from outside its own ground any more either, so a monster standing at the edge of its patch will not lunge at someone one step beyond it.

ROAMING DISTANCES

Every creature in the world used the same wander radius, roughly 5 to 16 metres, whether it was a townsperson or a boar. They now each have their own patch, and each will follow you 18 metres past it and no further:

  townsfolk        6m patch, chases to 24m
  workers          8m
  camp humanoids  14m patch, chases to 32m
  giant rats      14m, goblins 16m
  hares           22m
  roaming beasts  24m, wild boar 26m, chases to 44m
  bosses          18m, they hold their lair

The idea is the one RuneScape and WoW both use: a camp guards a spot, a beast owns a field, and a boss does not follow you home.

The same fix is in the server simulation, so monsters behave identically whether the fight is running on your machine or the server. If those two ever disagree about who is chasing you, monsters teleport.


## August 5, 2026 (perf) - A performance readout on F3, and three times the ground cover

Press F3 in game for a live readout: frame time, frames per second, draw calls, triangles, mesh count, and how much headroom you have before the game drops the graphics on itself.

WHY THIS EXISTS

The zone update has been working to a budget of under 1,400 draw calls and under 7,000 meshes. That budget is a guess written down before the ground cover was merged into single meshes, and nobody could check it, so it was measured properly instead.

Standing in the same field, with ground cover set four different ways:

  cover per chunk   meshes   draws   triangles   ms to build a chunk
  55 to 85           6,780   1,282        176k        7.0
  150 to 220         6,807   1,289        213k        6.1
  400 to 600         6,815   1,279        296k       21.3
  900 to 1300        6,827   1,281        539k       32.0

Sixteen times the grass, flowers and stones moves draw calls by ONE and mesh count by forty seven. It is all one merged mesh per chunk, so the count does not matter to the renderer. What actually grows is triangles, which are cheap, and the time to build a chunk, which is the small hitch when you walk into ground you have not seen yet. That is the real ceiling, and it is flat up to about 220 per chunk and triples past it.

So the ground cover is now 150 to 220 per chunk, roughly triple what shipped yesterday, for no measurable cost.

WHAT THE GAME ALREADY DOES

None of this changes the safety net. The game watches its own frame time and turns shadows and extra lights off by itself if it sits above 27ms for four seconds, and does it harder above 55ms. That is a real measurement with a real consequence, which is more than a draw call count can say. The readout shows you the same number the game is watching.

WHAT THIS DOES NOT TELL YOU

Frame rate cannot be measured from the test harness, which renders in software and runs at about a fifth of real speed. Any number it produced would be made up. That is exactly why the readout is in the game: the only machine whose frame rate matters is yours.


## August 5, 2026 (zones-2b) - The Heartlands has animals in it

Boar, giant rats, young goblins and hares now live in the Heartlands, out in the fields rather than only around the camp.

WHAT LANDED

- WILD BOAR. Heavy through the shoulders, bristled ridge down the spine, tusks. 45 health.
- GIANT RAT. Low, long and lean, with a naked segmented tail. 26 health.
- YOUNG GOBLIN. 30 health.
- HARE. Small, big eared, harmless, and it runs. Killable, but it drops nothing worth the walk.

Twenty five head in total, spawned at fixed points across Heartlands ground. The points come out of the same seeded generator that places the trees and stones, so the same boar stands in the same field on your screen and on everyone else's. That is not cosmetic: monster state travels between players by position in a list, so a roster that changed per machine would desync every fight in the zone.

Nothing spawns in water, on a road, or inside a town. That was checked against every spawn point, and the roster was checked for being identical across two cold boots.

MEASURED

Standing in a dressed Heartlands field with the whole roster loaded: 6,757 meshes and 1,292 draw calls, worst frame over a full turn on the spot. Greenwood reads 6,749 and 1,303. Both inside the 7,000 mesh and 1,400 draw call budget.

The roster is 25 head rather than the 30 the design plan asks for, and that is a budget decision, not a taste one. A quad costs about 50 scene meshes and the zone already sits near 5,300 before anything spawns, so 30 head put it over 7,000. Twenty five fits with room. If the budget moves, the number is one line in the rules.

WHAT IS NOT IN YET

The signature moves. TUSK CHARGE, TAIL WHIP and GOBLIN SHRIEK are written down and the animals are wired to know which one is theirs, but none of them fire yet, so right now a boar fights like a boar-shaped wolf. That is the next push, and it is deliberately its own push because signature moves reach into the fight and the fight is being worked on elsewhere at the same time.


## August 5, 2026 (content) — THE ARGENT WARDEN

There is something standing in the northern Heartlands now, about 215 metres
north of spawn. The capital built it to hold the northern road and then lost the
means to put it back to sleep. Three times a man's height, pale Ironspire stone
bound in argent bands, with the drained light of the lake burning in a cavity in
its chest.

**It takes two people. That is not a suggestion and it is not a message on a
door.** While either of its two Argent Anchors still stands the Warden pulls the
field back into itself and heals 70 health a second, and an anchor re-forges 26
seconds after you break it. One player can comfortably break an anchor. What one
player cannot do is break the SECOND one before the first is back up, so the
drain never stops and the health bar never really moves. Two players split the
field, both anchors go down inside the same window, the drain stops, and the
Warden is mortal.

Simulated against the real server code, with a knight landing 30 to 45 damage a
second:

  one player,  ordinary gear    walls at 87% and gets pushed back to full
  one player,  good gear        walls at 73%
  one player,  exceptional gear kills it, in six and a half brutal minutes
  two players, ordinary gear    kills it in about two and a half minutes
  two players, good gear        kills it in about a minute

So it is not a locked door. If you are geared enough to grind it alone you have
earned it. You will not enjoy it.

### Two phases

**PLATED** is a siege engine: slow, enormous reach, and three ways to hit you.
The maul is its jab, the hammer is the one that ends you, and the sunder is an
eight metre ground shock you have to be outside of, not blocking.

**UNBOUND** starts at 55%. The argent bands snap off the model, it shouts, and
it gets faster and hits harder. It also starts vaulting the field to land on
whoever thought distance was safety.

### Three mechanics

- **The Argent Siphon**, above. The fight.
- **Sunder**, an eight metre omnidirectional shock. Your shield does not help.
- **The Argent Lance**, a five bolt spread it throws from up to thirty metres,
  so standing at range plinking is not a plan either.

### The drop

**WARDEN'S BULWARK**: 34 defence and 6 strength, against the Iron Kite Shield's
20 and nothing. It is the only shield upgrade in the game and the Iron Kite has
been the only shield at all, so this fills a real hole.

Anchors drop nothing and give no experience, on purpose. They come back every 26
seconds; anything they gave would be an infinite tap.

### Under the hood

The world generation number went to 6, which is what makes the relay throw away
its stored world and take the new one even with people online. Spawn order is a
protocol invariant so the Warden and its anchors are appended at the end of the
list: every creature already in the world keeps the index it had.


## August 4, 2026 (zones-2a) - Zone art: every tree its own shape, every zone its own ground

Phase 2 begins with the look. The engine already placed props correctly, it just placed the same four props everywhere in different colours. Now a zone looks like itself.

WHAT CHANGED

- Every tree species has its own silhouette instead of one shape recoloured. A poplar is tall and narrow with its canopy stacked up the trunk, an oak is short and wide, an elder is huge, a pine is a spire, a palm is a bare trunk with a crown on top, a bog oak and an emberbark are bare snags. Orchard apples carry fruit, which at fifty metres is the entire difference between an apple tree and a small oak.
- Every zone has its own ground cover. The Heartlands get tall grass, wheat, wildflowers and field stones, with hay bales on the farmland ring near the capital. Greenwood gets ferns and fallen logs. Frostwild gets snow drifts. Ironspire gets scree and boulders. Windscar gets dry grass and sun bleached bones. Ember gets ash drifts and obsidian shards. Mistfen gets reeds. Sunscorch gets bone and glass glitter. The coast and isles get shells and driftwood.
- Clutter grows in CLUMPS now. Grass grows in patches, stones collect in drifts, ferns cluster. Scattering props evenly put one every twelve metres, which reads as litter, not as ground.
- Grass is a tuft of leaning blades rather than a single blade. A three sided cone seen side on is a flat triangle, so the first pass gave fields of little gold shards standing on end.
- Ground cover density is up roughly four times, from the plan's 14 to 22 props per chunk to 55 to 85.

ABOUT THAT DENSITY

The plan's 14 to 22 was written before the clutter was merged. Merged, a chunk's entire ground cover is ONE draw call no matter how much is on it, so the low number bought nothing and left the starter fields looking bald. It was raised and then measured, not assumed.

Heartlands, worst frame over a full turn on the spot: 5,427 meshes and 1,288 draw calls with dressing on, against 5,252 and 1,274 with it off. Greenwood: 5,419 meshes, 1,303 draw calls. Four times the ground cover cost about 14 draw calls. Both well inside the 7,000 mesh and 1,400 draw call budget.

Determinism still holds: two fresh boots generate identical prop lists. 652 generated props were checked against the placement rules with none in water, on a road, or in a town. One bug was caught that way and fixed: the first member of each clump was skipping the water check because the site had already passed it, but a clump member sits offset from its site.

STILL TO COME IN PHASE 2

The Heartlands creatures: boar, giant rat and the young goblin's shriek.
