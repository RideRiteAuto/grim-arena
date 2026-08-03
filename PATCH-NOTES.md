# Grim World — patch notes

## August 3, 2026 — multiplayer rebuilt, log out added

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
Two real browsers against a live relay: both players connect, see each other by
name and colour, positions track correctly, and when the host disconnects the
second player is promoted within a second with no errors on either side. The
relay's own test suite covers presence, ownership handover, message routing,
forged-message rejection, rate limiting and reconnection.

### Not done yet
Monster simulation still runs on the owning player's machine. Moving it into the
relay is the next step and is what will fix the frame rate drops during boss
fights with heavy projectile counts.
