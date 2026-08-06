# Phase 1 baseline, captured before any edit

Repo: grim-arena, master at `060cf62`, Aug 6 2026.
Environment: cloud sandbox, node v22.22.2, three 0.160.1 + playwright installed
in the PARENT dir, chromium from /opt/pw-browsers.

Every check below was run against unmodified `060cf62`. Any of these going red
after a patch means the patch changed behaviour.

| Test | Result | Notes |
|---|---|---|
| `harness/simtest.mjs` | all green, 10/10 | pure node, seconds |
| `harness/boot.js` | green | started true, chunks 225, errorCount 2 (the two known 404s, present on unmodified master) |
| `harness/skills.js` | green | errors [] |
| `harness/sigs.js` | green | errors [] |
| `harness/leash.js` | green | errors [] |
| `harness/rigs.js` | green | 16 shots, errors [] |
| `harness/bridges.js` | green | all bridge and torch checks passed |
| `harness/plants.js` | green | 9 distinct shapes; only errors are the offline relay websocket |
| `harness/dressing.js` | green | `determinism.identical: true`; only error is the offline relay websocket. Takes 7+ minutes. |

## Two corrections to the written docs

1. `BUNDLE-MERGE-HAZARD.md` says `harness/dressing.js` cannot boot in this
   sandbox because of outbound TLS. It runs fine here and reports
   `determinism.identical: true`. It is just slow (7 to 9 minutes), which is
   probably what it looked like before.

2. `BUILD-HANDOFF.md` says master is at `db58d4c`. It was at `e9876a2` when this
   session started and moved to `060cf62` during setup (the combat track's
   campfire work plus a save-migration fix).

## The build path was broken on master, and is fixed locally

`harness/patches/28_campfire.py` was pushed into the bundle but left in
`harness/patches/` instead of being moved to `harness/patches/applied/`. So
`bash harness/build.sh` aborts for anyone who pulls:

    AssertionError: camp forge anchor matched 0 times

That is the assert doing its job, not a bug. Moved to `applied/` here.
`build.sh` then round-trips byte-identically against master, which is the proof
the build path is sound. **The other track should make the same move on their
side**, or the next person to pull hits the same wall.

Patch numbering collided twice with the combat track tonight; the vertical patches landed as 31 and 32.

## Delivery constraint

This sandbox can `git fetch` but cannot `git push`: the git proxy denies
`RideRiteAuto/grim-arena` with a 403 on both tokens. This matches what
`BUNDLE-MERGE-HAZARD.md` already records. Work can be built and fully verified
here; landing it needs the route from that document, run from Kevin's machine.
