# Grim World — patch notes

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


## August 5, 2026 (combat) — boss leaps and pounces actually hurt again

The Hollow King's leap, the Plague Rat's pounce and the Bandit Captain's leap
have been dealing exactly zero damage. They crossed the ground at you, landed
on your head, and did nothing at all. Pure theatre.

Same cause as the harmless woodcutters a few patches back. The damage for a
landing used to be written out inline in the game ("at 0.7 through the hop, hit
for 14-20 over 2.6m"), and when the fight moved to the server that line stopped
running for monsters. Nothing replaced it, so the move went out with no blow
attached.

The landing is now part of the shared rule book like every other attack, using
the original authored numbers: 14 to 20 damage, 2.6m reach, wide arc, counts as
a heavy hit so it breaks a block. It is timed as an offset from the start of the
hop rather than a wall-clock stamp, so it cannot drift, and it is judged against
where the boss ACTUALLY comes down. That last part matters: the whole point of a
lunge is that it closes the distance, so measuring the blow from the take-off
point would have made it miss almost every time.

Phase damage multipliers reach it, so the Hollow King's final phase lands
harder. Charges and taunts still carry no blow, which is correct: they are
positioning and noise, not attacks.

Verified with a server-side test asserting all three bosses emit a correctly
shaped landing blow (and that charges and taunts emit none), plus six in-browser
assertions: landing on top of you hurts, landing short does not, it damages
exactly once however many frames poll it, a boss killed in mid-air deals
nothing, a charge deals nothing, and nothing lands before touchdown.


## August 5, 2026 (combat) — melee is judged against the monster you can see

This is the other half of the fix below. That one put the swing ANIMATION on
the same clock as the damage, which was right and needed. But nobody had
checked WHERE the damage was being measured from, and that turned out to be the
bigger half.

### The blade swept one arc, the damage tested another

When a monster swings, the server announces it once with the position and
facing the monster had at that instant. Your machine then waited out the
wind-up and asked "was I inside that?". The trouble is that the monster you are
looking at is not drawn from the attack message at all. It is drawn from the
position feed, live, every frame, and it keeps walking and keeps turning while
the swing plays.

Measured against the live server, one ordinary 0.66 second swing:

  monster moves during the swing     0.82 m
  monster turns during the swing     20 degrees
  error at the moment the blow lands  ~0.5 m and ~14 degrees

On a three metre reach that is a sixth of the range and a quarter of the half
arc, and it is not a constant offset you could learn. Monsters pick a new
strafe direction on a random one to three second timer, so the invisible hit box
sat to your left, then to your right, then behind you. That is why it felt
random rather than merely late, and why no amount of retiming ever fixed it.

Arrows, bolts and fireballs never had this problem, which is exactly why they
always felt fine: a projectile freezes the same stale origin, but then it
becomes a real object that flies from there, so the thing that hits you is the
thing you were watching. Melee was the only attack in the game where the damage
came from somewhere you could not see.

Melee now works the way projectiles already did. The blow is resolved in the
render loop, on the frame the blade actually passes through you, measured from
the monster's drawn position and drawn facing. Reach, arc and damage still come
from the server, so nobody can widen their own hit box.

### Monsters no longer pirouette through their own swing

A monster re-aimed at you every tick, including while committed to an attack.
In a test where the player circles it, one goblin turned 351 degrees during a
single swing, tracking the player the whole way. That made the telegraph
unreadable and meant a swing could not be dodged by moving, which is the entire
point of having a wind-up. A monster now aims when it decides to swing and
lives with that until the swing is done. Applies to every monster in the world:
goblins, knights, bandits, wolves, the workers on their tools, and all four
bosses, since they all funnel through the same attack call.

### Also fixed while in here

- **Server clock offset was applied backwards.** `srvNow()` defines the offset
  as one you subtract to get back to local time, but all three schedulers added
  it. That doubled any drift in your PC's clock instead of cancelling it, and
  every telegraph in the game was delayed by twice that amount. If your Windows
  time sync had drifted a second, every monster swung a second late while its
  body carried on moving live underneath the animation.
- **Move timings now come off the wire.** The client was reading wind-up and
  recovery out of its own copy of the move table instead of the numbers the
  server sent with that exact swing. They agree today. They would have silently
  stopped agreeing the first time somebody retuned a move.
- **The two damage paths can no longer overlap.** If the position feed goes
  quiet your machine takes the fight back and runs monsters locally. Any swing
  the server had already announced is now cancelled at that moment, instead of
  landing on top of the local one from an unrelated clock. The handover also
  waits 2 seconds instead of 1.2 so an ordinary frame hitch does not trigger it.
- **A monster's health bar moves when you hit it.** Your damage number appeared
  instantly but the bar waited for the server to answer, so at any real ping the
  bar visibly lagged your hits. It is now predicted locally and corrected when
  the server's number arrives. It will never predict a death, so nothing falls
  over and stands back up.
- Removed a `hitrep` message the client sent on every landed blow. It was not on
  the relay's accepted list and had been silently discarded all along.

### How this was verified

Not by eye. A probe connected to the live production relay over a WebSocket,
aggroed a real monster and logged every attack event against the position feed
frame by frame; those are the numbers quoted above. The sim change is covered by
a test that orbits a player around a monster and asserts the facing never moves
during a committed swing (351 degrees before, 0.0 after). The client change is
covered by eight assertions driven against the real shipped bundle in a browser:
a monster standing still still hits, one that strafes out of reach does not, one
that ends up behind you does not, one that turns away does not, a swing damages
exactly once no matter how many frames poll it, nothing lands before the wind-up
finishes, a corpse deals nothing, and the wire's timings are the ones used.


## August 5, 2026 (combat) — the splat now lands on the swing, and corpses stop swinging

### Hits landed before the swing did, by exactly your ping
The damage and the hit splat were scheduled off the swing's true start
instant, but the swing ANIMATION was being re-seeded by every status
update arriving from the server. Those updates carry the phase the server
saw one network trip ago, so each one quietly dragged the animation
backwards while the damage stayed put. You got hit roughly one ping
before the blade looked like it arrived, and the gap jittered as your
connection did.

Measured on a stepped 60fps clock, before and after, at three
connection speeds. Gap between the splat and the swing:

  ping  60ms   before  -44ms    after  0ms
  ping 150ms   before -134ms    after  0ms
  ping 300ms   before -284ms    after  0ms

The swing animation now rides the exact same clock its damage does, and
a status update can no longer touch a swing that is already playing. When
one does set the phase (a swing you only learn about late), it adds the
time the message spent in transit, so it starts where the monster is now
rather than where it was.

### Corpses no longer get one last swing
A swing is announced slightly before it begins. Nothing checked whether
the monster was still alive when that moment arrived, so a monster killed
in that window played its whole attack on top of its own body, and could
still hurt you. Killing a monster now cancels any swing in flight: no
animation, no damage, no splat. Verified alongside a control where the
monster is left alive and still swings and hits normally.


## August 5, 2026 (frame rate) — the big performance pass

### Measured on real hardware first
Profiled the live game over the Chrome bridge: about 1,050 draw calls,
5,300 meshes, and a surprisingly small pixel load. The game was CPU and
draw-submission bound, not resolution bound. Everything below attacks
exactly that.

### Only nearby torches cast light
Every torch and lamp in the world was a live point light riding inside
EVERY draw call's shading, even from across the map (their light only
reaches 26 m). Now exactly the five nearest you are lit. This also keeps
the shader's light count stable, so no hitching while walking.

### Trees stop breathing at a distance
Every canopy in the world ran its sway animation every frame. Past 70 m
nobody can see a canopy breathe, so past 70 m it does not.

### Static scenery frozen
Trees, rocks and terrain no longer recompute their positions every frame
just to stand still. Only things that actually move keep paying: swaying
canopies nearby, and a trunk mid-fall.

### Distant monsters undrawn
Monsters past 90 m are not rendered or animated (the server stops
sending their movements at 60 m anyway, so they were frozen statues at
that range). Their minimap dots remain. They pop back well outside
notice range as you approach.

### Background tab stops burning your GPU
A hidden tab kept doing full renders. Now it keeps the world alive but
skips drawing, and no longer poisons the frame-rate average that decides
Performance Mode.

### Performance Mode safety floor
Choosing GRAPHICS: HIGH by hand used to disable the automatic downshift
forever. HIGH is still honored, but if the frame rate sits far below
playable for six straight seconds the game protects itself once, with a
banner. The button brings HIGH back any time.


## August 5, 2026 (combat sync) — monsters now run on the real clock on every machine

### The real bug behind the weird combat
Server-owned monsters were mixing three clocks on your screen. Their
positions moved on real time, their damage landed on real time, but
their ANIMATIONS ran on the game clock, which silently slows down
whenever your frame rate dips below 20. Result on a busy machine: the
damage arrives while the swing is still winding up, legs animate slower
than the body glides (the stutter), and monsters keep true speed while
you are slowed (the wrong-feeling pathing). The first seconds after
loading always looked fine because the local stand-in brain keeps damage
and animation on the SAME clock, and the switch to the server feed is
what you saw as the moment everything went weird.

### The fix
Everything about a server-simulated monster now advances on real elapsed
time: swing telegraphs, walk cycles and position settling all share the
same wall clock the damage timer already used. Swings land when they
look like they land, at any frame rate.

### The flash you see a few seconds in
That is PERFORMANCE MODE kicking in automatically when the frame rate
dips: it turns shadows and extra lights off and rebuilds the materials,
which shows as a one-time flicker. It was being blamed for the combat
weirdness because both happened at the same moment. The combat part is
fixed; the flicker is the graphics downshift doing its job.


## August 5, 2026 (server combat sync) — the fixes reach the server brain

Mystery solved on the lingering combat weirdness: for your first few
seconds in the world, monsters run on YOUR machine's AI (which had all
the recent combat fixes) - then the relay server takes over every
monster at once, and the server's copy of the AI still had the old
behavior. That is why combat felt right at login and went strange
moments later, all monsters at the same time.

The server brain now runs the exact same rules as the client: melee
starts from 85 percent of reach so visible swings connect, a first
attack is near-guaranteed within about half a second of reaching you,
and the attack dice are clamped against slow ticks. One combat feel,
from the first second to the last.


## August 5, 2026 (performance) — shadow diet + steady combat dice

### Why it slowed down
The model rewrite tripled the number of meshes in the scene, and nearly
every tiny part (teeth, tusks, ore studs, rivets, ears) was casting its
own shadow - invisible shadows the GPU still had to draw every frame.
On HIGH graphics that was a slideshow on many machines.

### The fix
A shadow diet now strips shadow-casting from any part too small for its
shadow to be visible - over HALF of all shadow casters removed with zero
visual difference - and it re-sweeps every few seconds so newly spawned
players, boats and mounts get the same treatment.

### Combat un-weirded
The slideshow was also what made monster attacks look broken: slow
frames made the attack dice fire in bursts and skip animation frames.
All attack rolls are now clamped so slow frames can never burst-fire
attacks, on top of the earlier timing fixes. If your machine still dips,
GRAPHICS: LOW on the menu turns shadows off entirely - and the coming
zone dressing engine batches its scenery from day one so density stays
cheap.


## August 5, 2026 (clean cuts) — stumps only exist once the tree is cut

The stump used to be a separate shape hiding inside the trunk, and its
edges peeked through the bark on standing trees. Stumps are now cut from
the trunk's own base profile and stay completely INVISIBLE while the
tree stands - the bark is seamless - then appear at the exact moment the
tree breaks off and falls, and vanish again when it regrows. The break
reads clean: falling trunk, pale sawn face, stump left behind.


## August 5, 2026 (combat feel) — swings that land when they look like they land

### No more whiffed openers
Monsters used to start their first swing at the very edge of their reach,
so the opening attacks you SAW often missed - swings with no damage and
no hit splat, which read as animation and damage being out of sync.
Melee attacks now start from 85 percent of max reach, so the swing you
see is a swing that connects.

### No more doorstep hesitation
Attack decisions were a per-frame coin flip that could leave a monster
standing in your face for over a second. The longer an NPC stands in
reach without swinging, the more certain the next swing now becomes - a
first attack is near-guaranteed within about half a second of arrival.

### Bites synced to damage
The four-legged attack lunge (wolves and their coming kin) peaked early,
before the damage moment. It now reaches full extension exactly on the
frame the damage lands, then recovers - the bite you see is the bite
that hits.
