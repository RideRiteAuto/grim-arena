# Moving monsters onto the server — full assessment

## The thing that actually breaks dodging

I expected the problem to be attack timing. It isn't. The wind-up already
travels over the network: every position update carries the monster's state and
how far through that state it is, so both players genuinely do see a boss start
its slam at the same moment.

The problem is **who decides whether the swing hit you**.

When a monster reaches the damage frame of its attack, one player's browser runs
a check: everyone within 5.4 metres and inside a 6.3 radian arc of where the
monster is facing takes the damage. That check runs on the owning player's
machine, against **their copy of where you are standing**, which is up to a
tenth of a second plus network latency out of date.

So you dodge on your screen, and on their screen you had not moved yet. You take
the hit. The reverse happens too: you get clipped by something you never saw
touch you. Projectiles work the same way.

This is why it feels wrong, and it is not fixable by making the monsters move
more smoothly. It is fixable, but only by changing who decides.

## What decides what, after the rewrite

| Decision | Now | After |
|---|---|---|
| Where a monster is | one player | server |
| When it starts an attack | one player | server |
| Where the attack lands, how wide | one player | server |
| **Whether YOU got hit** | one player | **your own machine** |
| Your health | server | server |
| Monster health, death, loot | server | server |

That fourth row is the important one and it is deliberate. The server will own
the attack completely: the exact moment it starts, how long the wind-up runs,
where the monster stands, which way it faces, and how big the swing is. Every
player receives that as one scheduled event and plays the identical telegraph.

But whether *you* were standing inside it gets judged on your machine, at the
damage frame, against where you actually were. Your dodge is judged against what
you saw.

The alternative is letting the server decide that too, but the server's copy of
your position is just as stale as another player's, so it would feel exactly as
unfair as it does today. Making the server judge fairly means recording the
position of every player many times a second and rewinding the whole world to
the attacker's moment in time whenever it swings. That is how competitive
shooters do it. It roughly doubles the size of this project and adds a class of
bug that is genuinely hard to find. For a co-op game against monsters, letting
each player judge their own dodge is both simpler and better, and it is what
most co-op games actually ship.

## What has to move, and how hard each part is

I measured all of it.

**Easy — pure maths, no 3D engine needed**
- Monster movement is flat X and Z only. Height is decoration applied when
  drawing, so the server never needs the terrain.
- Collision is a plain list of circles and boxes for trees, rocks and buildings.
  I ship that list to the server once at startup. About 30 lines.
- The world edge is a circle at 168 metres. One line.
- Monsters shove each other apart so packs surround you instead of stacking.
  About 10 lines.
- The attack definitions are pure data: 13 moves with wind-up, damage frame,
  recovery, damage range, reach and arc. This becomes one shared block that
  generates into both the game and the server, so they can never drift apart.

**Medium — the monster brain, about 8,000 characters**
- Picking a target: whoever hit it, otherwise the nearest living player.
- Aggro radius, giving up beyond 32 metres, leashing home past 46 metres.
- Hollowrest and the camp being safe, so nothing picks a fight there.
- Wandering when idle, circling once in reach, keeping its distance by weapon.
- Choosing a weapon, raising and dropping its guard, dodging incoming shots.
- All of this is arithmetic on two coordinates. It ports cleanly.

**Medium — the fighting half of the character step, about 9,000 characters**
- Velocity, lunges, knockback, stagger, freeze, stamina and mana.
- The attack state machine: wind-up, damage frame, recovery, combo chaining.
- The player half of this same code stays exactly where it is and is untouched.

**Harder — projectiles**
- Frost bolts, arrows, volleys and toxin pools. The server will spawn them with
  a start point, a velocity and a timestamp, and every machine then draws the
  identical flight path without another byte crossing the network.
- This is also the one part that may help your boss-fight frame rate, because
  projectiles stop costing network traffic entirely.

**Harder — the boss specials**
- The Hollow King's telegraphed ground slam and leap, Mr. Sailers' charge,
  taunt and volley, Austin Little's leap, bash and flourish.
- Each becomes a server-driven state that plays the same animation it plays now.
  These are last on purpose: they are the most visible if I get one wrong.

## What it costs you

Nothing extra on the Cloudflare free plan. The simulation runs off the position
updates already arriving ten times a second, so it needs no timer of its own and
no additional requests. Projectiles are computed rather than streamed. Attack
events are rare. The traffic after this change is roughly what it is today.

## Order of work

1. **Shared rules.** One block of attack definitions and constants that
   generates into both the game and the server. Ship the collision list and
   monster spawn data to the server at startup. Add a server clock so every
   machine agrees what time it is.
2. **Movement.** Port the brain and the movement half of the character step.
   Monsters start being driven entirely by the server. Local movement becomes an
   emergency fallback for a dropped connection only.
3. **Scheduled attacks.** The dodge fix. The server announces each attack as a
   timed event; every machine plays the identical telegraph; your machine judges
   your own dodge and reports the result.
4. **Projectiles.** Server-spawned, locally drawn, each player judging their own
   hits.
5. **Boss specials.** Charge, leap, slam, volley, taunt, flourish.

Steps 1 and 2 are the bulk of the work and the biggest single change this
project has had. Step 3 is what actually fixes your complaint. Steps 4 and 5
are smaller but need care.

## Honest risks

- **Monsters will move slightly differently.** Not worse, but the randomness now
  comes from one place instead of each machine rolling its own, so packs will
  spread and circle a little differently than you are used to.
- **The collision list and the world edge have to match exactly.** If they do
  not, a monster stands somewhere on the server that it cannot stand on your
  screen, and it will jitter. This is the most likely source of a visible bug and
  the thing I will test hardest.
- **This is a rewrite, not a move.** The same behaviour has to be rebuilt in a
  different shape. I will keep the current behaviour working the whole way
  through, and each step ships and is testable on its own rather than going dark
  for days.
