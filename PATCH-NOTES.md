# Grim World — patch notes

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


## August 5, 2026 (model rewrite 6) — bigger, better trees and ore

Every tree and ore node is rebuilt, and all trees are 25 percent bigger.
Field trees now have tapered lofted trunks with a slight natural lean,
root flares at the base, and organically jittered two-tone canopies that
still sway in the wind. The big oaks get thick flared trunks and broad
layered crowns. Pines get taller lofted trunks, four staggered needle
tiers and a crown spike. Ore rocks are now weathered boulder clusters
with vertex-sculpted faces and six copper-glinting ore studs. Chopping,
mining, respawns and multiplayer sync all unchanged - these builders are
also the base set for the zone dressing work coming next.


## August 5, 2026 (model rewrite 5) — The Plague Rat, properly repulsive

The barrow boss got the loft treatment: a low-slung chest rising into a
high arched rump, mangy two-tone hide with fur texture, a real rat head
with a long tapering snout, chisel teeth, glowing toxic eyes and nose,
thin dish ears, actual whiskers, clawed feet, and a naked segmented tail
that tapers away in a falling curve. The toxic boils still glow along its
spine. Same fight, same toxin pools, same loot.


## August 5, 2026 (model rewrite 4) — sheep worth shearing

The pasture sheep are rebuilt: a slim lofted under-body beneath a lumpy,
vertex-sculpted wool shell (the shell is what shrinks when you shear
them), a proper dark face with side ears, a little wool cap between the
ears, a stub wool tail, and jointed legs with hooves that actually trot
while they wander and stop when they graze. Shearing, wool regrowth and
the F prompt all work exactly as before.


## August 5, 2026 (model rewrite 3) — red deer rebuilt

The red deer now use the new build style: slender lofted body with a pale
belly, a properly upright neck with an alert, small head, big swiveling
ears, long thin legs with real knees and dark hooves, a stub tail, and
three-tined antlers on the stags. They graze with their head high, flick
their ears, and stretch flat-out when they bolt. Same skittish behavior,
same loot.
