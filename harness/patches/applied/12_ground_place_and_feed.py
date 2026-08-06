#!/usr/bin/env python3
"""Distant NPCs stay on the ground, and stop fighting the position feed.

Ground height was written ONLY inside animate(), and animate() is skipped on 2
of 3 frames past 50m and 5 of 6 past 85m. Every skipped frame left
g.position.y at 0, absolute sea level, against terrain that runs -27m to +87m.
Measured on the live bundle with an NPC parked at 82m: 20 of 30 frames drew it
at sea level. That is the flicker Kevin reported. It hid for months because the
starting field is flattened to exactly h = 0.

groundPlace() now owns placement and runs every frame in every band, carrying
the boat, swim, wraith-drift and death-sink cases across. farBand() gives the
50m / 85m / 90m thresholds a 15 percent return margin, because a bare compare
on a distance that moves every frame makes anything pacing a line blink or
change gait twice a second. The animation step is capped at 50ms so the damped
lerps stop saturating and distant turns stop snapping.

The pack-separation shove was missing the srvNpc() half of its gate, so it ran
at 60Hz on top of positions the server had already separated at 10Hz.

The matching relay change (an empty snapshot is still a heartbeat) is a plain
edit to relay-worker.js and is readable in the diff, so it is not scripted here.

Full write-up in PATCH-NOTES.md.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


sub(
    "  animate(e, dt) {",

    "  // Ground placement is deliberately NOT part of animate(). animate() is\n  // skipped on most frames at distance, and while it owned the only write\n  // of g.position.y every skipped frame drew the body at y = 0, absolute\n  // sea level. Against terrain that ranges from -27m to +87m that is a\n  // 23m vertical strobe at 10-20Hz, which is what the distant flickering\n  // actually was. This runs every frame, in every band. Keep it that way.\n  groundPlace(e) {\n    let gy = (this.worldOn && this.mode === 'ai') ? this.groundY(e.pos.x, e.pos.z) : 0;\n    const dep = Math.max(0, -gy);\n    const inBoat = (e === this.me && this.boating) || !!e._boatOn;\n    e.swimF = !inBoat && dep > 1.05 && e.state !== 'dead';\n    if (inBoat) gy = -0.43 + Math.sin(this.worldT * 1.7) * 0.05;\n    else if (e.swimF) gy = e.ridingF ? (-0.06 - 0.92) : (-0.06 - 0.52);\n    if (e.state === 'dead') { e.g.position.set(e.pos.x, gy - Math.min(e.st / 0.7, 1) * 0.3, e.pos.z); return; }\n    let y = e.pos.y + gy;\n    if (e.wraith) y += 0.6 + Math.sin(this.worldT * 1.6 + e.phase) * 0.13;\n    e.g.position.set(e.pos.x, y, e.pos.z);\n  }\n  // Distance bands with hysteresis. A bare compare on a distance that\n  // wobbles frame to frame makes an NPC pacing near a threshold blink in\n  // and out, or change gait, twice a second. Measured across the 90m line:\n  // 89.4 visible, 90.3 hidden, 90.6 hidden, 89.9 visible. A band now has to\n  // be left by a wider margin than it was entered by. Returns 0 to hide,\n  // otherwise the animation stride.\n  farBand(e, d2) {\n    const OUT = [2500, 7225, 8100];            // 50m, 85m, 90m\n    let b = (e._band == null) ? 3 : e._band;\n    while (b > 0 && d2 > OUT[3 - b]) b--;      // fall outward at the line\n    while (b < 3 && d2 < OUT[2 - b] * 0.85) b++;  // climb back only well inside it\n    e._band = b;\n    return b === 3 ? 1 : b === 2 ? 3 : b === 1 ? 6 : 0;\n  }\n  animate(e, dt) {",
    "groundPlace + farBand")

sub(
    "    e.g.position.copy(e.pos);\n    if (e !== this.me && this.me && this.worldOn && this.mode === 'ai') {\n      const dx = e.pos.x - this.me.pos.x, dz = e.pos.z - this.me.pos.z;\n      const d2 = dx * dx + dz * dz;\n      if (d2 > 8100) {\n        if (e.g.visible && e.hp > 0) { e.g.visible = false; e._farHide = 1; e.g.traverse(o => { o.matrixAutoUpdate = false; }); }\n        return;\n      }\n      if (e._farHide) { e._farHide = 0; e.g.traverse(o => { o.matrixAutoUpdate = true; }); if (e.hp > 0 && !e.deadHandled) e.g.visible = true; }\n      if (d2 > 2500) {\n        const step = d2 > 7225 ? 6 : 3;                    // >85m: 1-in-6 · >50m: 1-in-3\n        e._animSkip = ((e._animSkip || 0) + 1) % step;\n        if (e._animSkip) return;\n        this.animate(e, dt * step);\n        return;\n      }\n    }\n    this.animate(e, dt);",

    "    this.groundPlace(e);\n    if (e !== this.me && this.me && this.worldOn && this.mode === 'ai') {\n      const dx = e.pos.x - this.me.pos.x, dz = e.pos.z - this.me.pos.z;\n      const step = this.farBand(e, dx * dx + dz * dz);\n      if (!step) {\n        if (e.g.visible && e.hp > 0) { e.g.visible = false; e._farHide = 1; e.g.traverse(o => { o.matrixAutoUpdate = false; }); }\n        return;\n      }\n      if (e._farHide) { e._farHide = 0; e.g.traverse(o => { o.matrixAutoUpdate = true; }); if (e.hp > 0 && !e.deadHandled) e.g.visible = true; }\n      if (step > 1) {\n        e._animSkip = ((e._animSkip || 0) + 1) % step;\n        if (e._animSkip) return;\n        this.animate(e, Math.min(dt * step, 0.05));       // capped: the damped lerps saturate past this\n        return;\n      }\n    }\n    this.animate(e, dt);",
    "stepFighter placement band")

sub(
    "n.g.position.copy(n.pos); const ddx = n.pos.x - me.pos.x, ddz = n.pos.z - me.pos.z, dd2 = ddx * ddx + ddz * ddz; if (dd2 > 8100) { if (n.g.visible && n.hp > 0) { n.g.visible = false; n._farHide = 1; n.g.traverse(o => { o.matrixAutoUpdate = false; }); } continue; } if (n._farHide) { n._farHide = 0; n.g.traverse(o => { o.matrixAutoUpdate = true; }); if (n.hp > 0 && !n.deadHandled) n.g.visible = true; } if (dd2 > 2500) { const stp = dd2 > 7225 ? 6 : 3; n._animSkip = ((n._animSkip || 0) + 1) % stp; if (n._animSkip) continue; this.animate(n, adt * stp); continue; } this.animate(n, adt);",

    "this.groundPlace(n); const ddx = n.pos.x - me.pos.x, ddz = n.pos.z - me.pos.z; const stp = this.farBand(n, ddx * ddx + ddz * ddz); if (!stp) { if (n.g.visible && n.hp > 0) { n.g.visible = false; n._farHide = 1; n.g.traverse(o => { o.matrixAutoUpdate = false; }); } continue; } if (n._farHide) { n._farHide = 0; n.g.traverse(o => { o.matrixAutoUpdate = true; }); if (n.hp > 0 && !n.deadHandled) n.g.visible = true; } if (stp > 1) { n._animSkip = ((n._animSkip || 0) + 1) % stp; if (n._animSkip) continue; this.animate(n, Math.min(adt * stp, 0.05)); continue; } this.animate(n, adt);",
    "mirror placement band")

sub(
    "    // Engaged NPCs shove each other apart so a pack surrounds you instead of\n    // collapsing into one shared point. Only over foes actually in the fight,\n    // so this stays a handful of checks rather than the whole roster.\n    if (!this.connectedAsClient()) {",

    "    // Engaged NPCs shove each other apart so a pack surrounds you instead of\n    // collapsing into one shared point. Only over foes actually in the fight,\n    // so this stays a handful of checks rather than the whole roster.\n    //\n    // The srvNpc() half of this gate was missing. connectedAsClient() is\n    // false for the sim owner, and a solo player is always the sim owner, so\n    // this ran at 60Hz on top of positions the server had already separated\n    // with the identical formula at 10Hz. The client shoved six times harder\n    // than the server, the interpolator pulled back, and the monsters you\n    // were actually fighting vibrated. n.aggro is set from a server\n    // broadcast and never cleared in server mode, so it never stopped.\n    // Compare the auth line below, which had the gate right all along.\n    if (!this.srvNpc() && !this.connectedAsClient()) {",
    "pack shove gate")

for old, new, label in edits:
    assert src.count(old) == 1, 'anchor %s went stale' % label
    src = src.replace(old, new)

io.open(SRC, 'w', encoding='utf-8').write(src)
print('patched %d anchors -> %s' % (len(edits), SRC))
