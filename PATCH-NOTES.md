# Grim World — patch notes

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


## August 5, 2026 (art) — the Plague Rat is solid again, and so is everything else

You could see straight through the Plague Rat into the inside of its own body.
Its head looked fine, which is what made it read as one broken monster rather
than what it actually was: a bug in the geometry builder that every lofted model
in the game runs through.

Bodies are built by stacking cross sections along the length of the model and
skinning between them. The triangle order that skinning used only produced
outward-facing surfaces when the sections happened to be listed back to front.
List them nose first and the whole model comes out inside out, and since the
renderer throws away back faces, it discards the surface nearest you and draws
the inside of the far wall instead. That is the see-through look.

Sixteen models were listed one way and nine the other, so nine were inverted:
the Plague Rat's body and legs, its tail, your own cape, the wolf and deer legs,
and the donkey's legs and tail. The rat was the obvious one because it is the
biggest thing in the game and it is scaled up almost twice.

The builder now reads which way the sections run and winds the surface to match,
so it no longer matters which way a model is written. Every one of the 25 lofted
meshes in the game now faces outward, and the 16 that were already correct are
untouched, triangle for triangle. Lighting on the nine fixed models is better
too, since their surfaces were previously being lit from the inside.


## August 4, 2026 (zones-1c) - Gathering XP splats read in their skill's colour

Small one. When you gather, the floating XP text now comes up in the skill's own colour instead of the same gold as everything else: green for woodcutting, orange for mining, teal for foraging. Combat XP is unchanged.

The point is that you can tell what moved without reading it, which matters once you are swinging at three kinds of node in the same clearing.


## August 4, 2026 (zones-1b) - Five new creature rigs in the model lab

Groundwork for the monsters, not the monsters themselves. Nothing in the game changes with this one.

Five rig types the bestiary needs did not exist yet, so each one is now built and animated on its own turntable page before any creature is wired to it. Open model-lab/index.html to see them turn.

- SERPENT. Ten links, each parented to the one in front, driven by a single wave equation. Coils, travels, rears up and strikes. This is the bog serpent, and CONSTRICT hangs off it.
- WISP. No skeleton at all, so it is a core, a halo, six orbiting motes and a light. It winds down small and dark before it bursts, which is the only telegraph a shapeless thing can give you. Ice sprites, will-o-wisps and dust devils.
- FLYER. Three joints per wing, so the wing folds on the upstroke instead of flapping like a plank, and so the same rig can genuinely perch. Cave bats and vultures.
- CRAB. Eight legs on a sideways gait that travels along the body, and two jointed claws. The PINCER GRAB is in: claws snap shut and then HOLD while the body hauls backward, because the hold is the move, not the snap.
- INSECT. Six legs on the alternating tripod gait, three feet planted at all times, with mandibles and an optional tail. BURROW AMBUSH is a real state: it sinks, waits, and erupts.

Each rig was checked at four points in every state, from four camera angles, with no console errors. Two problems were found and fixed that way: the crab's shell was rendering black because a vertex colour material was on a shape with no vertex colours, and the serpent was rendering as a straight pipe because its wave packed half a cycle between neighbouring links, so they cancelled each other out.


## August 4, 2026 (zones-1) - Gathering skills and the zone dressing engine

The world stops being bald. Ground outside the towns and roads now grows its own trees, bushes, stones and sticks, and the harvestable nodes in it are the ones that zone is supposed to have.

WHAT LANDED

- One level curve for every skill, defined in shared rules so the game and the server can never disagree about it. 2,838,130 XP to 99. Levels 1 to 40 come fast, the 50s are earned, 99 is a long haul.
- Your existing skill XP was written against the old curve, so it is converted once on load. Your level does not change and neither does your progress through it. The old numbers are kept in your save under a backup key for one release, so this is reversible if anything looks wrong.
- FORAGING is in. Eight skills now, so total level runs to 792.
- Harvesting checks TWO things: your skill level and your tool tier. When you cannot take something, the message says which one stopped you and what fixes it, for example REQUIRES WOODCUTTING 5 or NEEDS A STEEL AXE. No more silent refusals.
- Tool ladder from crude to masterwork. New characters start with crude tools. If you already own the iron axe and pickaxe, the game now reads those as tier 3, so nobody was downgraded.
- Every tool and every gathered material is generated from the same table the gate check reads, so nothing can be required and missing.
- Better tools and higher skill gather faster.
- The dressing engine places props per 64m chunk from a seeded hash of the chunk and the world generation number. Same ground, same props, on every machine, forever. Nothing is placed in water, on a road, inside a town safe zone, or on a cliff face.
- Ground clutter is merged into one mesh per chunk, no shadows, frozen matrix. A dressed chunk costs one draw call no matter how much is on it.
- Harvestable nodes are real objects and run through the same depletion and refill code the old resources always used. Trees fall and leave a stump, ore veins empty out, picked plants leave their stalks. Walk away from a node you emptied and it is still empty when you come back.

MEASURED, NOT ASSUMED

Standing in the Heartlands at (-340, 200), worst frame over a full turn on the spot:

- dressing off: 5,249 meshes, 1,269 draw calls
- dressing on: 5,429 meshes, 1,286 draw calls

So the whole dressing pass costs about 180 meshes and 17 draw calls. Greenwood at (-600, 420) read 5,417 meshes and 1,308 draw calls with 71 harvestable nodes and 25 dressed chunks loaded. Both are inside the 7,000 mesh and 1,400 draw call budget.

Determinism was checked by booting the game twice from scratch and comparing the generated prop lists for 31 chunks: identical, down to position, rotation, scale, node kind and node id. 139 generated props were checked against the placement rules: none in water, none on a road, none in a town.

Walking a twelve stop loop away and back left the mesh count where it started, so chunks are releasing their props properly.

WHAT IS NOT IN YET

Zone art is next, one zone at a time, starting with the Heartlands. Right now every zone uses the same shapes in its own colours. The new creature rigs, the tool forge recipes and the monsters are still to come.

KNOWN, AND HONEST ABOUT IT

- The arena and camp trees and iron rocks kept their old levels and yields on purpose. Retuning them to the new tables would have locked existing players out of the iron their smithing quest needs.
- In a shared world the host still counts one swing as one swing, so a better tool does not yet make you faster when someone else is hosting. Single player and hosting are correct. This is on the list for the balance pass.
