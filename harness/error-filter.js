// Verifies patch 83.150's error-banner filter, pulled LIVE out of index.html
// (not retyped here, so this fails loudly if the shipped handler ever drifts
// from what this test checks) and run in a minimal sandboxed `window` via
// Node's vm module -- no browser needed for this one, it's pure JS logic.
//
// Three synthetic events, matching the three real cases the handler has to
// tell apart:
//  1. A resource-load failure (no message/error, has a target) -- always
//     just a console.warn, never the banner. Pre-existing behaviour.
//  2. The one diagnosed bundler-internal error (stack mentions evalDcLogic)
//     -- patch 83.150's new case: logged quietly, banner NOT shown.
//  3. A real error from our own code (or literally anything else, including
//     unknown future errors) -- banner still shows exactly as before. This
//     is the one that matters most: the fix must not get greedy and start
//     hiding real bugs.
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const startMarker = "window.addEventListener('error', function(e) {";
const i = src.indexOf(startMarker);
if (i < 0) throw new Error('error handler not found in index.html -- did patch 83.150 land?');
const j = src.indexOf('}, true);', i);
if (j < 0) throw new Error('could not find the end of the error handler');
const handlerSrc = src.slice(i + "window.addEventListener('error', ".length, j + 1);

const fails = [];
function ok(cond, label, detail) {
  console.log((cond ? '  ok     ' : '  FAIL   ') + label + (detail ? '  (' + detail + ')' : ''));
  if (!cond) fails.push(label);
}

function run(event) {
  const logs = { warn: [], debug: [] };
  const created = [];
  const fakeDiv = () => ({ id: '', style: {}, textContent: '', _tag: 'div' });
  const sandbox = {
    console: { warn: (...a) => logs.warn.push(a.join(' ')), debug: (...a) => logs.debug.push(a.join(' ')) },
    document: {
      body: {},
      documentElement: {},
      getElementById: () => null,
      createElement: () => fakeDiv(),
    },
  };
  sandbox.document.body.appendChild = (el) => { created.push(el); return el; };
  // In a real page `window` IS the global object, which is how the handler's
  // own `e.target !== window` check works. Mirror that: point it at itself.
  sandbox.window = sandbox;
  const ctx = vm.createContext(sandbox);
  const fn = vm.runInContext('(' + handlerSrc + ')', ctx);
  fn(event);
  return { logs, bannerShown: created.length > 0 };
}

// ---- 1. resource load failure: unchanged, still just a warn ---------------
{
  const r = run({ target: { tagName: 'IMG', src: 'missing.png' } });
  ok(r.logs.warn.length === 1 && r.logs.debug.length === 0 && !r.bannerShown,
    'a resource-load failure still just warns, no banner');
}

// ---- 2. the diagnosed bundler-internal noise: quiet, no banner ------------
{
  const r = run({
    message: "Cannot read properties of undefined (reading 'toLowerCase')",
    error: { stack: "TypeError: Cannot read properties of undefined (reading 'toLowerCase')\n    at eval (eval at evalDcLogic (blob:x:844:16), <anonymous>:3563:20)" }
  });
  ok(!r.bannerShown, 'the evalDcLogic bundler-internal error does not show the banner');
  ok(r.logs.debug.length === 1, 'it is still logged (quietly, to console.debug) rather than swallowed silently');
}

// ---- 3. a real error, from our own code or anywhere else: still shown -----
{
  const r = run({
    message: 'paint is not a function',
    error: { stack: 'TypeError: paint is not a function\n    at groundSurface (blob:x:11053:5)' }
  });
  ok(r.bannerShown, 'a genuine game-code error still shows the banner, unchanged from before');
}
{
  // Unknown future error with NO stack at all (e.g. a browser that reports
  // message/lineno but not e.error) must not be swallowed just because it
  // has no stack to check -- indexOf on '' is -1, so the filter is a no-op.
  const r = run({ message: 'something else entirely broke', filename: 'x', lineno: 1 });
  ok(r.bannerShown, 'an error with no stack at all still shows the banner (fails open, not closed)');
}

console.log('');
if (fails.length) { console.log(fails.length + ' FAILED:'); fails.forEach(f => console.log('  ' + f)); process.exit(1); }
console.log('all error-filter checks passed');
