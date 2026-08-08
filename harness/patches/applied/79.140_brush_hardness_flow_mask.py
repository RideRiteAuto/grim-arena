#!/usr/bin/env python3
"""Patch 79.140: richer ground-paint brush controls (Phase 2 of the ground
texture plan, claude/GROUND-TEXTURE-BRUSH-PLAN.md).

Adds four brush controls Kevin asked for, all additive and all defaulted so
an untouched brush behaves byte-for-byte like before:

- Hardness: fades the CHANCE a cell near the brush's edge gets painted this
  stroke, so the brush has a genuine soft edge in the authored data itself
  rather than relying only on the render-time neighbour blend. Default 1
  (fully hard, i.e. the existing behaviour) so nothing changes unless dialled
  down.
- Flow: probability a cell is committed on any single pass, so a slow drag
  can build coverage up gradually like an airbrush instead of always
  committing at full strength on first contact. Default 1 (existing
  behaviour, no accumulation needed).
- Organic edge: jitters the brush footprint itself with the same trig-noise
  trick already used for zone and bridge-pad borders, so a painted patch
  reads as hand-placed rather than a stamped circle. Default off.
- Paint-only-over-X mask: restricts painting to cells that already carry a
  specific authored surface (or specifically unpainted ground), so one
  texture can be retextured into another without spilling onto the rest of
  the field. Default off (paints anywhere the brush touches, as before).

Only editor-ui.js changes (direct file edits, not the extracted bundle):
the brush lives entirely in the editor tools, which ship to nobody but
Kevin behind ?edit=1.
"""
import io

UI = 'editor-ui.js'
u = io.open(UI, encoding='utf-8').read()
n = 0


def usub(old, new, count=1, tag=''):
    global u, n
    f = u.count(old)
    assert f == count, 'patch 79.140 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    u = u.replace(old, new)
    n += 1


# ---- 1. new state fields, all defaulted to the pre-patch behaviour --------
usub(
    """      surf: 15, brush: 8, strength: 1,""",
    """      surf: 15, brush: 8, strength: 1,
      hardness: 1, flow: 1, organic: false, maskSurf: null,""",
    tag='add hardness/flow/organic/maskSurf to fresh() state')

# ---- 2. paintAt(): hardness falloff, flow, organic jitter, mask lock -------
usub(
    """  function paintAt(pt, erase) {
    const L = GRIM_EDIT.raw;
    if (!L) return;
    const rad = Math.max(0, S.brush);
    const rc = Math.max(1, Math.ceil(rad / PCELL) + 1);
    const c0 = pcellOf(pt.x), z0 = pcellOf(pt.z);
    let touched = 0;
    for (let dz = -rc; dz <= rc; dz++) {
      for (let dx = -rc; dx <= rc; dx++) {
        const cx = c0 + dx, cz = z0 + dz;
        // The cell under the cursor always counts, so even the smallest
        // brush setting still paints something; every other cell has to
        // pass the real-distance test.
        if (dx || dz) {
          const wx = (cx + 0.5) * PCELL, wz = (cz + 0.5) * PCELL;
          const ddx = wx - pt.x, ddz = wz - pt.z;
          if (ddx * ddx + ddz * ddz > rad * rad) continue;
        }
        const key = pChunkOfCell(cx, cz);
        let list = L.paint[key];
        if (!list) { if (erase) continue; list = L.paint[key] = []; }
        let at = -1;
        for (let i = 0; i < list.length; i++) if (list[i][0] === cx && list[i][1] === cz) { at = i; break; }
        if (erase) { if (at >= 0) { list.splice(at, 1); touched++; } }
        else if (at >= 0) { if (list[at][2] !== S.surf) { list[at][2] = S.surf; touched++; } }
        else { list.push([cx, cz, S.surf]); touched++; }
        if (!list.length) delete L.paint[key];
      }
    }
    if (touched) { GRIM_EDIT.reindex(); S.dirty = true; }
    return touched;
  }""",
    """  function paintAt(pt, erase) {
    const L = GRIM_EDIT.raw;
    if (!L) return;
    const rad = Math.max(0, S.brush);
    // Hardness: fraction of the radius that is always painted; beyond it the
    // chance of a cell landing fades to 0 at the outer edge, giving the
    // brush a real soft edge in the authored data (not just render-time
    // blending). 1 = old fully-hard behaviour, unchanged by default.
    const hardFrac = (S.hardness == null) ? 1 : Math.max(0, Math.min(1, S.hardness));
    const hardR = rad * hardFrac;
    const rc = Math.max(1, Math.ceil(rad / PCELL) + 1);
    const c0 = pcellOf(pt.x), z0 = pcellOf(pt.z);
    // Flow: chance a cell commits on this pass at all, so a slow drag can
    // build coverage up like an airbrush. 1 = old always-commits behaviour.
    const flow = (S.flow == null) ? 1 : Math.max(0.05, Math.min(1, S.flow));
    // Paint-only-over-X: null paints anywhere (old behaviour), -1 restricts
    // to currently unpainted ground, >=0 restricts to that authored surface.
    const mask = (S.maskSurf == null) ? null : S.maskSurf;
    let touched = 0;
    for (let dz = -rc; dz <= rc; dz++) {
      for (let dx = -rc; dx <= rc; dx++) {
        const cx = c0 + dx, cz = z0 + dz;
        const isCentre = !dx && !dz;
        let wx = (cx + 0.5) * PCELL, wz = (cz + 0.5) * PCELL;
        // Organic edge: jitter the footprint itself with the same trig-noise
        // trick zone and bridge-pad borders use, so painted patches read as
        // hand-placed rather than a stamped circle. Never jitters the centre
        // cell, so the smallest brush still always paints something.
        if (S.organic && !isCentre) {
          wx += Math.sin(wx * 0.31 + wz * 0.53) * (rad * 0.12);
          wz += Math.cos(wx * 0.47 - wz * 0.29) * (rad * 0.12);
        }
        // The cell under the cursor always counts, so even the smallest
        // brush setting still paints something; every other cell has to
        // pass the real-distance test, and then the hardness falloff.
        if (!isCentre) {
          const ddx = wx - pt.x, ddz = wz - pt.z;
          const dd = Math.sqrt(ddx * ddx + ddz * ddz);
          if (dd > rad) continue;
          if (dd > hardR) {
            const t = (dd - hardR) / Math.max(0.001, rad - hardR);
            const chance = 1 - t * t * (3 - 2 * t);
            if (Math.random() > chance) continue;
          }
        }
        if (flow < 1 && Math.random() > flow) continue;
        const key = pChunkOfCell(cx, cz);
        let list = L.paint[key];
        let at = -1;
        if (list) for (let i = 0; i < list.length; i++) if (list[i][0] === cx && list[i][1] === cz) { at = i; break; }
        if (mask !== null) {
          const cur = at >= 0 ? list[at][2] : -1;
          if (cur !== mask) continue;
        }
        if (!list) { if (erase) continue; list = L.paint[key] = []; }
        if (erase) { if (at >= 0) { list.splice(at, 1); touched++; } }
        else if (at >= 0) { if (list[at][2] !== S.surf) { list[at][2] = S.surf; touched++; } }
        else { list.push([cx, cz, S.surf]); touched++; }
        if (!list.length) delete L.paint[key];
      }
    }
    if (touched) { GRIM_EDIT.reindex(); S.dirty = true; }
    return touched;
  }""",
    tag='paintAt: hardness falloff, flow, organic jitter, mask lock')

# ---- 3. the panel: expose the four controls --------------------------------
usub(
    """      if (S.tool === 'paint') {
        row(b, 'Brush');
        slider(b, 'radius, metres', 0.5, 24, 0.5, S.brush, v => S.brush = v);
        const er = el('div', 'color:#8f8f8f;font-size:10px;margin-top:6px',
          'Alt click erases back to the generated ground. Alt right click picks the surface under the cursor. ' +
          'Ground paint is authored on a 1m grid, so this brush can now paint a single small patch.');
        b.appendChild(er);
      } else {""",
    """      if (S.tool === 'paint') {
        row(b, 'Brush');
        slider(b, 'radius, metres', 0.5, 24, 0.5, S.brush, v => S.brush = v);
        slider(b, 'hardness', 0, 1, 0.05, S.hardness == null ? 1 : S.hardness, v => S.hardness = v);
        slider(b, 'flow', 0.05, 1, 0.05, S.flow == null ? 1 : S.flow, v => S.flow = v);
        const org = el('button', S.organic ? BTN_ON : BTN, S.organic ? 'Organic edge ON' : 'Organic edge OFF');
        org.onclick = () => { S.organic = !S.organic; paintPanel(); };
        b.appendChild(org);
        const er = el('div', 'color:#8f8f8f;font-size:10px;margin-top:6px',
          'Alt click erases back to the generated ground. Alt right click picks the surface under the cursor. ' +
          'Ground paint is authored on a 1m grid, so this brush can now paint a single small patch. ' +
          'Hardness below 1 fades the brush toward its own edge; flow below 1 needs several passes to fully commit; ' +
          'organic edge breaks up the brush footprint so patches read as hand-placed.');
        b.appendChild(er);
        row(b, 'Paint only over');
        const maskCol = el('div', 'display:grid;grid-template-columns:1fr;gap:3px');
        const noneBt = el('button', (S.maskSurf == null ? BTN_ON : BTN) + 'font-size:10px;text-align:left;margin:0', 'any ground, no lock');
        noneBt.onclick = () => { S.maskSurf = null; paintPanel(); };
        maskCol.appendChild(noneBt);
        const unpaintedBt = el('button', (S.maskSurf === -1 ? BTN_ON : BTN) + 'font-size:10px;text-align:left;margin:0', 'unpainted ground only');
        unpaintedBt.onclick = () => { S.maskSurf = -1; paintPanel(); };
        maskCol.appendChild(unpaintedBt);
        const lockLbl = (S.maskSurf != null && S.maskSurf >= 0)
          ? ('locked to ' + S.maskSurf + ' ' + (SURF_NAMES[S.maskSurf] || ''))
          : 'lock to the surface selected above';
        const lockBt = el('button', BTN + 'font-size:10px;text-align:left;margin:0', lockLbl);
        lockBt.onclick = () => { S.maskSurf = S.surf; paintPanel(); };
        maskCol.appendChild(lockBt);
        b.appendChild(maskCol);
        b.appendChild(el('div', 'color:#8f8f8f;font-size:10px;margin-top:4px',
          'Restricts this brush to cells that already match the locked surface, so one authored patch can be ' +
          'retextured into another without spilling onto the rest of the ground. Pick the target surface above, ' +
          'then use the surface picker to choose what it becomes, then lock again if you switch targets.'));
      } else {""",
    tag='paintPanel: expose hardness/flow/organic/mask controls')

io.open(UI, 'w', encoding='utf-8').write(u)

print('79.140_brush_hardness_flow_mask: %d edits applied' % n)
