#!/usr/bin/env python3
"""Patch 78.512: pause-menu DRAW button (part 4 of the Phase 2 overhaul; see
78.104's docstring for the full rationale).

Adds viewDistInit()/applyViewDist()/toggleViewDist()/updateViewDistHud(),
modeled directly on the existing gfxInit()/applyGfx()/toggleGfx()/
updateGfxHud() cluster right above them, and drops a 'DRAW: NEAR/NORMAL/FAR'
button into the same settings row as the GRAPHICS button. Cycles the three
VIEW_DIST tiers and reuses redressWorld() (the same rebuild path GRAPHICS
already uses when dressRing changes) so a toggle takes effect immediately
instead of waiting for the player to cross a chunk boundary.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    const low = this.gfx === 'low';
    this._gfxBtn.textContent = 'GRAPHICS: ' + (low ? 'LOW' : 'HIGH');
    this._gfxBtn.style.borderColor = low ? '#c8a24a' : '#8fbf6a';
    this._gfxBtn.style.color = low ? '#c8a24a' : '#8fbf6a';
  }
  freezeStaticWorld() {"""

NEW = """    const low = this.gfx === 'low';
    this._gfxBtn.textContent = 'GRAPHICS: ' + (low ? 'LOW' : 'HIGH');
    this._gfxBtn.style.borderColor = low ? '#c8a24a' : '#8fbf6a';
    this._gfxBtn.style.color = low ? '#c8a24a' : '#8fbf6a';
  }

  // ------------------------------------------------------------ draw distance
  // Independent of GRAPHICS: that setting is the frame-rate safety net
  // (shadows, extra lights, clutter), this is a player preference for how
  // far the world itself renders. See GRIM_RULES.VIEW_DIST. this.viewDist
  // is already read from localStorage before the scene is built (patch
  // 78.219), so init here only wires up the button.
  viewDistInit() {
    if (this.viewDist === undefined) {
      let v = null; try { v = localStorage.getItem('grim-viewdist'); } catch (e) {}
      this.viewDist = (v === 'near' || v === 'far') ? v : 'normal';
    }
    this.updateViewDistHud();
  }
  applyViewDist() {
    const cfg = GRIM_RULES.VIEW_DIST[this.viewDist] || GRIM_RULES.VIEW_DIST.normal;
    if (this.cam) { this.cam.far = Math.round(750 * cfg.mult); this.cam.updateProjectionMatrix(); }
    if (this.scene && this.scene.fog) {
      this.scene.fog.near = 70 * cfg.mult;
      this.scene.fog.far = Math.round(420 * cfg.mult);
    }
    this.redressWorld();   // terrain/prop rings key off viewDist too - rebuild what's already placed
  }
  toggleViewDist() {
    const order = ['near', 'normal', 'far'];
    this.viewDist = order[(order.indexOf(this.viewDist) + 1) % order.length];
    try { localStorage.setItem('grim-viewdist', this.viewDist); } catch (e) {}
    this.applyViewDist(); this.updateViewDistHud(); this.sfx('switch');
  }
  updateViewDistHud() {
    const row = this.musicRef && this.musicRef.current && this.musicRef.current.parentElement;
    if (!row) return;
    if (!this._vdBtn || !this._vdBtn.isConnected) {
      const b = document.createElement('button');
      b.style.cssText = 'margin-left:8px;padding:9px 16px;background:transparent;border:1px solid #8fbf6a;color:#8fbf6a;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:0.14em;cursor:pointer;';
      b.onclick = () => this.toggleViewDist();
      row.appendChild(b);
      this._vdBtn = b;
    }
    const cfg = GRIM_RULES.VIEW_DIST[this.viewDist] || GRIM_RULES.VIEW_DIST.normal;
    this._vdBtn.textContent = 'DRAW: ' + cfg.label;
  }
  freezeStaticWorld() {"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)

OLD2 = """    this.gfxInit();
"""
NEW2 = """    this.gfxInit();
    this.viewDistInit();
"""
count2 = s.count(OLD2)
assert count2 == 1, 'gfxInit call-site anchor matched %d times, expected 1' % count2
s = s.replace(OLD2, NEW2)

io.open(PATH, 'w', encoding='utf-8').write(s)
