# Grim World — patch notes

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
