# Grim World

Third-person action duelling in the browser. Solo boss ladder or peer-to-peer 1v1.

## Solo

Open the game, type a name, pick a colour, hit **SOLO — FIGHT THE BOSSES**.
Boss 1 is **Austin Little** (a pushover). Fell him and **Mr. Sailers** rides out —
a very large man on a very small donkey who casts snares and shouts gibberish.

## Play against your coworker (the easy way — no server)

Duels are **peer-to-peer over WebRTC**: after a free public broker introduces the
two browsers, game traffic flows directly PC-to-PC — the lowest-latency path.

1. Send your coworker the game link (or the standalone HTML file — same thing).
2. You click **HOST DUEL** → you get a 4-letter code. Send it to him.
3. He types the code and clicks **JOIN DUEL**. That's it — best of 3, 100 HP each.

Both PCs just need internet. No accounts, no port forwarding, nothing to run.

If the broker is ever unreachable (rare), the old relay still works:

```bash
cd server && npm install && node index.js
cloudflared tunnel --url http://localhost:8080
```

Open the printed URL with `#room=ring` on the end on both PCs.

## Controls

| | |
|---|---|
| `W A S D` / arrows | move |
| Mouse | look and aim |
| `E` / `Tab` | lock-on to target (great on trackpads) |
| `Space` | dodge roll (i-frames) |
| `Shift` | sprint |
| `1` `2` `3` (or `Q R F`) | blade / staff / bow |
| LMB | swing — fires on press; hold to chain light, light, heavy |
| RMB | shield block (blade) · ward (staff) · rapid shot (bow) |
| `Esc` | release the cursor |

**Perfect parry:** raise the shield within 200ms of impact — zero damage, attacker staggers.
**Guard break:** blocking drains stamina per hit absorbed; empty means 1.4s wide open.
**Frostbolt** roots 2s (6s cooldown). Sailers' **snares** root 1s.

## Tuning

Everything lives in `cfg()` in `Grim World.dc.html`. Tweaks panel exposes
player health, difficulty, turn speed, volume.
