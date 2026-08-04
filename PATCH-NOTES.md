# Grim World — patch notes

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


## August 5, 2026 (fixes) — clean tree bases, solid Plague Rat, gentle cloak

### Tree roots removed
The four cone protrusions at every tree base (a root-flare experiment
that read as spikes) are gone from field trees and oaks alike. Trunks
meet the ground clean.

### The Plague Rat is watertight
The rat's body shell was built with its cross-sections listed
back-to-front, which flipped every face inward - you could see into the
model. The model builder now normalizes section order so every lofted
shell always faces outward. This heals the rat everywhere and armors
every future model against the same mistake.

### The cloak calmed down
Cape lift while moving is cut to about a quarter of what it was, with a
soft idle breath of a flap when standing and a modest speed-scaled
flutter when running - both clamped so a sprint never kites the cloak.

### Patch notes now self-prune
This file automatically keeps only the newest twelve entries so it never
grows forever.


## August 5, 2026 (skills page + pack cleanup) — press K

### The skills page
K opens (and closes) your character's skill sheet: all seven skills -
MELEE, RANGED, MAGIC, HITPOINTS, WOODCUTTING, MINING, SMITHING - each
with its level out of 99, a colored progress bar to the next level, your
exact XP and the XP remaining. A TOTAL LEVEL sits in the header, levels
are now capped at 99, and hovering any skill shows a detailed tooltip:
what it does, how to train it, and where the next tier unlocks. The page
updates live as XP lands, Esc also closes it, and K is in the menu
binding list.

### Pack panel cleaned up
The pack grid is now 7 wide instead of a tall 4-wide column, the panel
is tighter with the dead space gone, and GEAR STATS is a compact
two-column readout that skips zero stats, with a damage-reduction bar
and a pointer to the K page.


## August 5, 2026 (harvest feel) — falling trees, empty veins, deeper mana

### Trees fall again - and properly this time
Felled trees stopped falling entirely (a side effect of the server sim
taking over: the visual feed that used to carry it went quiet). Resource
visuals now run locally on every player's screen, so they can never go
missing again. And the fall is real now: the tree hinges over at its
base, accelerates, THUDS onto the ground with a screen shake, rests a
beat still joined to the stump, then sinks away - leaving a cut STUMP
standing where it grew until the tree regrows.

### Ore veins go empty instead of vanishing
Mined-out rocks no longer blink out of existence. The boulders stay, and
the colored ore nuggets disappear - one look tells you the vein is empty.
When the refill clock runs out, the nuggets return.

### Honest feedback, tiered refill clocks
Swinging at a stump says ONLY A STUMP REMAINS - THE TREE IS REGROWING;
picking at an empty vein says THE VEIN IS EMPTY - THE ORE WILL REFILL
SOON. Refill times now scale by tier: field trees and pines 45s, iron
veins 60s, the great oaks 90s.

### Deeper mana pool
Player mana is up 50 percent (100 to 150). Costs are unchanged, so every
caster gets half again as many spells before running dry. The mana bar
scales to the new pool.


## August 5, 2026 (clean menu) — the menu is just the menu

HUD pieces were leaking onto the menu screen: the action bar, the
compass, the minimap, the health bars and quest tracker, and the
floating key hints (H teleport, X dismount, B boat). A central HUD
blackout now runs every frame: the moment the menu overlay is up (or
before you log in), every HUD element hides, and everything returns the
instant you resume play. The pause screen is finally just the pause
screen.


## August 5, 2026 (player polish) — a hero worth following

The chase camera stares at your back all day, and your back was a flat
blue rectangle. The cape is now a draped, curved loft: it falls from a
shoulder mantle with a gold clasp, curves away from the armor, widens
toward a split-tail hem, and still sways as you move. The body got the
matching pass: forearm bracers with elbow cops, knee plates and shin
greaves over the boots, and a flared neck guard on the back of the helm.
Applies to you, other players, and every knight-built NPC.

Also shipped: Zone Dressing Plan v3 in the repo - the complete bestiary
(30+ monsters, each with a rig, stats, loot, and its own SIGNATURE
attack), the wildlife roster with town-pet protection, all gathering
numbers (XP curve, node stats, tool recipes), and the zone-by-zone
rollout order.
