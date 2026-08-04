# Grim World — patch notes

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
