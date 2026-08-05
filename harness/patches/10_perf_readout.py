#!/usr/bin/env python3
"""A live performance readout, on F3.

The 1,400 draw call and 7,000 mesh budget in the handoff is a proxy for frame
rate, and a proxy nobody can check. The game already measures the real thing:
stepPerf tracks a smoothed frame time and drops the graphics automatically when
it goes past 27ms for four seconds. This puts that number on screen so a
judgement about whether the world is too full can be made from what the machine
actually does, rather than from a figure written down before the clutter was
merged.

Shows: frame time and FPS (the smoothed average the auto-drop already uses),
draw calls, triangles, scene meshes, and how far the frame time is from the
threshold that would drop the graphics.
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
    "  stepPerf() {\n"
    "    const now = performance.now();",

    "  // F3. Off by default and it costs nothing when it is off: the scene walk\n"
    "  // that counts meshes only runs while the panel is open, and only twice a\n"
    "  // second.\n"
    "  togglePerfHud() {\n"
    "    this._perfHud = !this._perfHud;\n"
    "    if (!this._perfEl) {\n"
    "      const d = document.createElement('div');\n"
    "      d.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:40;background:rgba(26,26,26,.86);' +\n"
    "        'border:1px solid #383838;border-radius:8px;padding:8px 11px;font:11px/1.5 ui-monospace,Menlo,Consolas,monospace;' +\n"
    "        'color:#ededed;white-space:pre;pointer-events:none;letter-spacing:.02em';\n"
    "      document.body.appendChild(d);\n"
    "      this._perfEl = d;\n"
    "    }\n"
    "    this._perfEl.style.display = this._perfHud ? 'block' : 'none';\n"
    "    if (this._perfHud) this.banner('PERFORMANCE READOUT ON', 'F3 TURNS IT OFF', false, 1600);\n"
    "  }\n"
    "\n"
    "  drawPerfHud() {\n"
    "    if (!this._perfHud || !this._perfEl) return;\n"
    "    const now = performance.now();\n"
    "    if (now - (this._perfHudAt || 0) < 500) return;\n"
    "    this._perfHudAt = now;\n"
    "    let meshes = 0;\n"
    "    if (this.scene) this.scene.traverse(o => { if (o.isMesh && o.visible) meshes++; });\n"
    "    const info = this.renderer && this.renderer.info.render;\n"
    "    const ft = (this._ftAvg || 0) * 1000;\n"
    "    const fps = ft > 0 ? (1000 / ft) : 0;\n"
    "    // 27ms is the threshold stepPerf already uses to drop the graphics, so\n"
    "    // it is the only number here with a real consequence attached.\n"
    "    const head = 27 - ft;\n"
    "    const col = ft < 17 ? '#8fe36a' : ft < 27 ? '#F3DC00' : '#e0574f';\n"
    "    this._perfEl.innerHTML =\n"
    "      '<span style=\"color:' + col + '\">' + ft.toFixed(1) + ' ms   ' + fps.toFixed(0) + ' fps</span>\\n' +\n"
    "      'headroom  ' + (head >= 0 ? '+' : '') + head.toFixed(1) + ' ms to auto drop\\n' +\n"
    "      'draws     ' + (info ? info.calls : 0) + '\\n' +\n"
    "      'tris      ' + (info ? Math.round(info.triangles / 1000) + 'k' : '0') + '\\n' +\n"
    "      'meshes    ' + meshes + '\\n' +\n"
    "      'zone      ' + (this.zoneAt ? this.zoneAt(this.me.pos.x, this.me.pos.z) : '') + '\\n' +\n"
    "      'nodes     ' + ((this.zoneNodes || []).length) + '   gfx ' + this.gfx;\n"
    "  }\n"
    "\n"
    "  stepPerf() {\n"
    "    const now = performance.now();",
    'perf hud')

sub(
    "      if (e.code === 'KeyK' && this.started && this.mode === 'ai' && !this.walletOpen && !this.bankOpen) { this.toggleSkills(); return; }",
    "      if (e.code === 'F3') { e.preventDefault(); this.togglePerfHud(); return; }\n"
    "      if (e.code === 'KeyK' && this.started && this.mode === 'ai' && !this.walletOpen && !this.bankOpen) { this.toggleSkills(); return; }",
    'f3 key')

# stepPerf already runs every frame, so the readout rides along with it rather
# than adding another hook into the frame loop. It has to go BEFORE the early
# returns further down: those fire whenever the graphics setting is not an
# untouched HIGH, which is most of the time, and the readout was silently never
# drawing because of it.
sub(
    "    this._ftAvg = (this._ftAvg === undefined) ? dt : this._ftAvg * 0.96 + dt * 0.04;",
    "    this._ftAvg = (this._ftAvg === undefined) ? dt : this._ftAvg * 0.96 + dt * 0.04;\n"
    "    this.drawPerfHud();",
    'hud tick')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
