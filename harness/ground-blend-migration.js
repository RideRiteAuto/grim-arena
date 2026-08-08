// Verifies patch 83.200's ground-blend default and migration, pulled LIVE
// out of the shipped bundle (not retyped here) so this fails loudly if the
// shipped numbers or migration formula ever drift. No browser needed: the
// migration line is plain arithmetic once BLEND_DEFAULT/BLEND_MAX/num are
// known, so it is evaluated directly in Node.
//
// Checks:
//  1. EDIT.BLEND_DEFAULT shipped as 5, not the old 2 (2m happened to equal
//     the near-field terrain mesh's vertex spacing exactly, which is the
//     whole reason the old default undersampled the blend in most
//     directions -- see the patch docstring). BLEND_MAX stays 6, untouched.
//  2. A world saved under the old code (raw.blend === 2, the value every
//     load used to stamp in unconditionally, whether or not anyone ever
//     touched the "Ground blend" slider) gets carried forward to the new
//     default automatically, with no per-texture repainting.
//  3. A blend value the user genuinely dialled in anywhere else in the
//     0.5..6 range is left completely alone, including the top of that
//     range and the bottom.
//  4. A brand new layer with no stored blend at all (raw.blend undefined)
//     lands on the new default directly, same as case 2.
//  5. The migration is one-directional and idempotent: feeding the
//     migrated result back in a second time does not move it again.
const fs = require('fs');
const path = require('path');

const rulesSrc = fs.readFileSync(path.join(__dirname, '..', 'shared-rules.js'), 'utf8');
const coreSrc = fs.readFileSync(path.join(__dirname, '..', 'editor-core.js'), 'utf8');

const fails = [];
function ok(cond, label, detail) {
  console.log((cond ? '  ok     ' : '  FAIL   ') + label + (detail ? '  (' + detail + ')' : ''));
  if (!cond) fails.push(label);
}

// ---- 1. pull the shipped constants straight out of shared-rules.js --------
const mDefault = /BLEND_DEFAULT:\s*(\d+(?:\.\d+)?)/.exec(rulesSrc);
const mMax = /BLEND_MAX:\s*(\d+(?:\.\d+)?)/.exec(rulesSrc);
if (!mDefault || !mMax) throw new Error('BLEND_DEFAULT/BLEND_MAX not found in shared-rules.js -- did patch 83.200 land?');
const BLEND_DEFAULT = parseFloat(mDefault[1]);
const BLEND_MAX = parseFloat(mMax[1]);
ok(BLEND_DEFAULT === 5, 'EDIT.BLEND_DEFAULT shipped as 5', 'found ' + BLEND_DEFAULT);
ok(BLEND_MAX === 6, 'EDIT.BLEND_MAX left at 6, untouched by this patch', 'found ' + BLEND_MAX);

// ---- 2. pull the shipped migration formula straight out of editor-core.js -
const startMarker = 'const rawBlend = num(raw.blend, BLEND_DEFAULT);';
const i = coreSrc.indexOf(startMarker);
if (i < 0) throw new Error('migration formula not found in editor-core.js -- did patch 83.200 land?');
const j = coreSrc.indexOf('\n', coreSrc.indexOf('out.blend =', i));
const formulaSrc = coreSrc.slice(i, j);

function num(v, d) { const n = +v; return isFinite(n) ? n : d; }

function migrate(rawBlendValue) {
  // eslint-disable-next-line no-eval
  const raw = { blend: rawBlendValue };
  let rawBlend, out = {};
  eval(formulaSrc);
  return out.blend;
}

ok(migrate(2) === 5, 'a world saved under the old default (blend: 2) upgrades to the new default', 'got ' + migrate(2));
ok(migrate(undefined) === 5, 'a brand new layer with no stored blend lands on the new default directly', 'got ' + migrate(undefined));
ok(migrate(3) === 3, 'a genuinely custom value (3) is left alone', 'got ' + migrate(3));
ok(migrate(0.5) === 0.5, 'the bottom of the slider range is left alone', 'got ' + migrate(0.5));
ok(migrate(6) === 6, 'the top of the slider range is left alone', 'got ' + migrate(6));
ok(migrate(999) === 6, 'an out-of-range stored value still clamps to BLEND_MAX', 'got ' + migrate(999));
ok(migrate(5) === 5, 'a stored value that already equals the new default stays put', 'got ' + migrate(5));

const once = migrate(2);
const twice = migrate(once);
ok(once === 5 && twice === 5, 'the upgrade is idempotent -- migrating an already-migrated value does not move it again',
  'once=' + once + ' twice=' + twice);

console.log('');
if (fails.length) { console.log(fails.length + ' FAILED:'); fails.forEach(f => console.log('  ' + f)); process.exit(1); }
console.log('all ground-blend-migration checks passed');
