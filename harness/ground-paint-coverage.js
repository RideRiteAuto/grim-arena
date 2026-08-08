// Verifies patch 86.100's ground-paint coverage falloff, pulled LIVE out of
// editor-core.js (not retyped here) and run against synthetic paint data in
// plain Node -- coverage math is pure geometry once paintIdx/PCELL/BLEND are
// known, no browser needed.
//
// Background: patch 83.200 widened EDIT.BLEND_DEFAULT (2m -> 5m) to fix
// meadow-into-mountain-gravel blending, and it did fix that case. But Kevin
// then painted a single dot onto BLANK ground and reported it still looked
// hard-edged, no softer than before, which is the exact symptom of a top-hat
// (all-or-nothing) coverage function rather than a genuinely narrow one.
// This harness proves which shape the shipped formula actually has, before
// and after 86.100, by sampling real coverage values across a real edge.
const fs = require('fs');
const path = require('path');

const coreSrc = fs.readFileSync(path.join(__dirname, '..', 'editor-core.js'), 'utf8');

const fails = [];
function ok(cond, label, detail) {
  console.log((cond ? '  ok     ' : '  FAIL   ') + label + (detail ? '  (' + detail + ')' : ''));
  if (!cond) fails.push(label);
}

// ---- pull the shipped paintAt() function body straight out of editor-core.js
const startMarker = '  function paintAt(x, z) {';
const i = coreSrc.indexOf(startMarker);
if (i < 0) throw new Error('paintAt not found in editor-core.js');
// Find the matching closing brace by counting braces from the opening one.
let depth = 0, j = i, started = false;
for (; j < coreSrc.length; j++) {
  if (coreSrc[j] === '{') { depth++; started = true; }
  else if (coreSrc[j] === '}') { depth--; if (started && depth === 0) { j++; break; } }
}
const fnSrc = coreSrc.slice(i, j);

// ---- build a sandboxed paintAt with synthetic paintIdx/PCELL/BLEND_DEFAULT
const PCELL = 1;
const BLEND_DEFAULT = 5;
const PHALF = 8192, PMUL = 100000;
function pCellKey(cx, cz) { return (cx + PHALF) * PMUL + (cz + PHALF); }

function makePaintAt(paintIdx) {
  const L = null; // no per-layer override; falls back to BLEND_DEFAULT
  // eslint-disable-next-line no-new-func
  const factory = new Function('paintIdx', 'PCELL', 'BLEND_DEFAULT', 'L', 'pCellKey',
    fnSrc + '\nreturn paintAt;');
  return factory(paintIdx, PCELL, BLEND_DEFAULT, L, pCellKey);
}

function buildDot(R, surf) {
  const idx = new Map();
  const rc = Math.ceil(R / PCELL) + 1;
  for (let dz = -rc; dz <= rc; dz++) {
    for (let dx = -rc; dx <= rc; dx++) {
      const wx = (dx + 0.5) * PCELL, wz = (dz + 0.5) * PCELL;
      if (Math.sqrt(wx * wx + wz * wz) <= R) idx.set(pCellKey(dx, dz), surf);
    }
  }
  return idx;
}

function buildHalfPlanes() {
  const idx = new Map();
  const rc = 20;
  for (let dz = -rc; dz <= rc; dz++) {
    for (let dx = -rc; dx <= rc; dx++) {
      idx.set(pCellKey(dx, dz), dx < 0 ? 1 : 2);
    }
  }
  return idx;
}

// ---- 1. a lone dot on blank ground must taper, not cliff -----------------
{
  const dot = buildDot(8, 1);
  const paintAt = makePaintAt(dot);
  const c0 = paintAt(0, 0);
  const c4 = paintAt(4, 0);   // still well inside the disc
  const c8 = paintAt(8, 0);   // right at the painted edge
  const c11 = paintAt(11, 0); // past the edge, inside the old hard-coded reach
  const c14 = paintAt(14, 0); // well past everything

  ok(c0 && c0[1] > 0.99, 'centre of a lone dot is still full coverage', 'got ' + (c0 && c0[1]));
  ok(c8 && c8[1] > 0.15 && c8[1] < 0.85, 'the painted edge itself sits mid-fade, not still pinned to 1', 'got ' + (c8 && c8[1]));
  ok(!c11 || c11[1] < 0.20, 'just past the edge coverage has genuinely dropped low, not still ~1', 'got ' + (c11 ? c11[1] : 'null'));
  ok(!c14, 'well outside the dot, coverage cuts off to null entirely', 'got ' + (c14 ? c14[1] : 'null'));
  ok(c4[1] > c8[1] && c8[1] > (c11 ? c11[1] : 0), 'coverage is strictly decreasing with distance (a real gradient, not a plateau)',
    'c4=' + c4[1].toFixed(3) + ' c8=' + c8[1].toFixed(3) + ' c11=' + (c11 ? c11[1].toFixed(3) : '0'));
}

// ---- 2. two adjacent painted regions: unchanged from before this patch ---
// (the meadow/mountain-gravel case that already worked -- must not regress)
{
  const hp = buildHalfPlanes();
  const paintAt = makePaintAt(hp);
  const expected = { '-4': 0.996, '-2': 0.933, '-1': 0.785, '0': 0.500, '1': 0.785, '2': 0.933, '4': 0.996 };
  let allMatch = true;
  const detail = [];
  Object.keys(expected).forEach(function (xs) {
    const x = parseInt(xs, 10);
    const c = paintAt(x, 0);
    const got = c ? c[1] : null;
    const want = expected[xs];
    const close = got !== null && Math.abs(got - want) < 0.002;
    if (!close) allMatch = false;
    detail.push(xs + ':' + (got !== null ? got.toFixed(3) : 'null'));
  });
  ok(allMatch, 'painted-to-painted border coverage is numerically identical to the pre-patch formula', detail.join(' '));
}

console.log('');
if (fails.length) { console.log(fails.length + ' FAILED:'); fails.forEach(function (f) { console.log('  ' + f); }); process.exit(1); }
console.log('all ground-paint-coverage checks passed');
