# Grim World — patch notes

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


## August 5, 2026 (boat camera fix) — no more staring into the deep

The camera aims at a point anchored to the ground height under the
player. On land that is where you stand - but in a boat it is the SEABED,
so over deep water the aim point sat meters underwater, the camera
pitched over the top of you, and you were left staring straight down at
the waves. The deeper the water, the worse the flip. The aim point now
clamps to the waterline whenever you are afloat (boat or swimming), so
the chase view stays level over any depth.


## August 5, 2026 (model rewrite 8) — villains with identity, a donkey worth riding

### Every villain now reads at a glance
The knight-body villains got their own identity layered on the upgraded
base: BANDITS wear dark hoods and cowls; THE BANDIT CAPTAIN wears a
blood-red hood and a bone skull strapped to his off arm; FROST WRAITHS
float in full tattered robes with no legs and burning ice-blue eyes; THE
HOLLOW KING wears a five-spiked gold crown over sickly green glowing
eyes.

### The donkey, rebuilt
Lofted round-bellied body with fur texture and pale belly shading, a real
neck and long-eared donkey head with a dark nose, a mane ridge, lofted
legs with hooves, a rope tail with a tuft, and a proper saddle - red
blanket, leather seat and girth strap. Riding, the trailing companion,
swimming and turbo all unchanged.

This completes the first full pass of the model rewrite: wolf, goblin,
deer, sheep, Plague Rat, trees, ore, the humanoid base, every villain,
and the donkey.


## August 5, 2026 (model rewrite 7) — sealed seams + armored bodies

### The gaps are gone
The new trees, ore rocks and sheep wool had visible cracks where mesh
faces met: the surface sculpting moved each face's copy of a shared
corner differently, tearing the model open. Sculpting now displaces by
corner POSITION, so every copy of a corner moves identically and the
meshes are watertight by construction. Rocks, canopies and wool are
solid from every angle.

### Knight bodies, upgraded
Every humanoid (your character, other players, townsfolk, knights) gets
a body pass: a sculpted lofted cuirass with a waist taper and breastplate
ridge in place of the straight tube torso, real shoulder pauldrons with
trim rims that ride the arms, thigh tassets, boot cuffs, and a proper
helm with a brim, nasal bar, cheek guards - and a visible chin, so
there is finally a person inside the armor. Same pivots, same gear and
palette system, so every armor color and weapon works unchanged.
