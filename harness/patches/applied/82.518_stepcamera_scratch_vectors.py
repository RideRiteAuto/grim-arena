#!/usr/bin/env python3
"""Patch 82.518: stop stepCamera() allocating 5-6 Vector3 objects every frame.

stepCamera runs once per frame unconditionally. Every intermediate vector it
builds (dir, right, want, the shake offset, look) is fully overwritten on
each call and never read after the function returns (want/look feed into
camPos.lerp()/cam.lookAt(), both of which copy values rather than keep a
reference), so each can be a scratch vector cached lazily on the instance
instead of a fresh allocation. Dedicated fields (not the existing _sv1/_sv2
scratch pair, which are used transiently all over the file) to avoid any risk
of aliasing with another call mid-frame.

No behavior change: identical math, identical order of operations. The one
shape change is `.add(new T.Vector3(0, dy, 0))` becoming `want.y += dy`,
which is the same result without allocating a throwaway vector just to add
a y-only offset.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    const dir = new T.Vector3(Math.sin(this.yaw), 0, Math.cos(this.yaw));
    const right = new T.Vector3(-dir.z, 0, dir.x);
    const want = e.pos.clone()
      .addScaledVector(dir, -dist * Math.cos(this.pitch))
      .addScaledVector(right, this.shoulderX)
      .add(new T.Vector3(0, height - Math.sin(this.pitch) * dist, 0));
    // Camera bound must match the playable space — clamping it to the arena
    // while the PLAYER can roam the world left the camera pinned at the wall.
    const r = Math.hypot(want.x, want.z);
    const lim = (this.worldOn && this.mode === 'ai') ? 1e9 : this.C.ARENA_R + 4.5;
    if (r > lim) { want.x *= lim / r; want.z *= lim / r; }
    want.y = Math.max(0.9, want.y) + ((this.worldOn && this.mode === 'ai')
      ? Math.max(this.groundY(want.x, want.z), this.groundY((want.x + e.pos.x) / 2, (want.z + e.pos.z) / 2), (e._elev ? this.worldY(e) : this.groundY(e.pos.x, e.pos.z)), (this.boating && e === this.me) ? 0.3 : (e.swimF && e === this.me) ? 0.25 : -0.05)
      : 0);
    this.camPos.lerp(want, 1 - Math.exp(-13 * dt));
    this.shake = Math.max(0, this.shake - dt * 3.6);
    // Continuous trauma noise rather than per-frame randomness — random each
    // frame reads as flicker; sinusoidal decay reads as impact.
    this.shakeT = (this.shakeT || 0) + dt;
    const s = this.shake * this.shake * 0.34, w = this.shakeT * 46;
    this.cam.position.copy(this.camPos).add(new T.Vector3(
      Math.sin(w * 1.0) * s, Math.sin(w * 1.37 + 1.7) * s * 0.8, Math.sin(w * 0.83 + 3.1) * s));
    let gyL = (this.worldOn && this.mode === 'ai') ? (e._elev ? this.worldY(e) : this.groundY(e.pos.x, e.pos.z)) : 0;
    // Afloat, the body rides the SURFACE - but gyL is the seabed, which over
    // deep water dragged the look target meters underwater and pitched the
    // camera over the top of the player. Clamp to the waterline when afloat.
    if ((this.boating || e.swimF) && gyL < -0.4) gyL = -0.4;
    const look = e.pos.clone().add(new T.Vector3(0, gyL + 1.5 + Math.sin(this.pitch) * 2.4, 0)).addScaledVector(right, this.shoulderX * 0.62);
"""

NEW = """    const dir = (this._camDir || (this._camDir = new T.Vector3())).set(Math.sin(this.yaw), 0, Math.cos(this.yaw));
    const right = (this._camRight || (this._camRight = new T.Vector3())).set(-dir.z, 0, dir.x);
    const want = (this._camWant || (this._camWant = new T.Vector3())).copy(e.pos)
      .addScaledVector(dir, -dist * Math.cos(this.pitch))
      .addScaledVector(right, this.shoulderX);
    want.y += height - Math.sin(this.pitch) * dist;
    // Camera bound must match the playable space — clamping it to the arena
    // while the PLAYER can roam the world left the camera pinned at the wall.
    const r = Math.hypot(want.x, want.z);
    const lim = (this.worldOn && this.mode === 'ai') ? 1e9 : this.C.ARENA_R + 4.5;
    if (r > lim) { want.x *= lim / r; want.z *= lim / r; }
    want.y = Math.max(0.9, want.y) + ((this.worldOn && this.mode === 'ai')
      ? Math.max(this.groundY(want.x, want.z), this.groundY((want.x + e.pos.x) / 2, (want.z + e.pos.z) / 2), (e._elev ? this.worldY(e) : this.groundY(e.pos.x, e.pos.z)), (this.boating && e === this.me) ? 0.3 : (e.swimF && e === this.me) ? 0.25 : -0.05)
      : 0);
    this.camPos.lerp(want, 1 - Math.exp(-13 * dt));
    this.shake = Math.max(0, this.shake - dt * 3.6);
    // Continuous trauma noise rather than per-frame randomness — random each
    // frame reads as flicker; sinusoidal decay reads as impact.
    this.shakeT = (this.shakeT || 0) + dt;
    const s = this.shake * this.shake * 0.34, w = this.shakeT * 46;
    const shakeOff = (this._camShakeOff || (this._camShakeOff = new T.Vector3())).set(
      Math.sin(w * 1.0) * s, Math.sin(w * 1.37 + 1.7) * s * 0.8, Math.sin(w * 0.83 + 3.1) * s);
    this.cam.position.copy(this.camPos).add(shakeOff);
    let gyL = (this.worldOn && this.mode === 'ai') ? (e._elev ? this.worldY(e) : this.groundY(e.pos.x, e.pos.z)) : 0;
    // Afloat, the body rides the SURFACE - but gyL is the seabed, which over
    // deep water dragged the look target meters underwater and pitched the
    // camera over the top of the player. Clamp to the waterline when afloat.
    if ((this.boating || e.swimF) && gyL < -0.4) gyL = -0.4;
    const look = (this._camLook || (this._camLook = new T.Vector3())).copy(e.pos);
    look.y += gyL + 1.5 + Math.sin(this.pitch) * 2.4;
    look.addScaledVector(right, this.shoulderX * 0.62);
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
