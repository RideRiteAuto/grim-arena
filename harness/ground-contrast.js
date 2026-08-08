// Verifies patch 83.100's contrast-aware ground dither, off the REAL measured
// per-layer brightness the running bundle computes (window.__grim._groundLuma),
// not a guessed value. No GPU/shader readback needed: the same maths
// ditherMix() does in GLSL is done here in plain JS against those numbers.
//
// Checks:
//  1. Every layer's luma comes back present and in 0..1.
//  2. meadow(0) vs mountain gravel(7), the pair Kevin says already blends
//     seamlessly, contributes exactly 0 extra softening (contrast() below is
//     the smoothstep(0.12, 0.35, gap) term ditherMix() adds on top of the
//     existing distance-based fade) -- proving that pair renders unchanged.
//  3. mountain gravel(7) vs beach sand(9), the pair Kevin reported as
//     stairstep/static, contrasts well above the no-op floor.
//  4. snow(5), desert sand(14) and frozen scree(6) -- flagged in the patch as
//     sharing beach sand's high-brightness band even though nobody has
//     reported them yet -- also clear the no-op floor against the low/mid
//     part of the palette, so they get the same protection automatically.
const { chromium } = require('playwright');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

const NAME = ['meadow', 'ploughed', 'heath', 'forest floor', 'moss/fern', 'snow',
  'frozen scree', 'mountain gravel', 'bare slate', 'beach sand', 'dry coastal',
  'steppe grass', 'cinder', 'bog', 'desert sand', 'packed dirt'];

// Mirrors ditherMix()'s GLSL exactly: smoothstep(0.12, 0.35, gap).
function contrast(gap) {
  const t = Math.max(0, Math.min(1, (gap - 0.12) / (0.35 - 0.12)));
  return t * t * (3 - 2 * t);
}

const fails = [];
function ok(cond, label, detail) {
  console.log((cond ? '  ok     ' : '  FAIL   ') + label + (detail ? '  (' + detail + ')' : ''));
  if (!cond) fails.push(label);
}

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage();
  await page.goto(URL, { waitUntil: 'load' });
  // Same boot route every other harness file uses: wait for the engine to
  // exist, click through the guest button, call play() directly since the
  // pointer lock never lands headless, then wait for a real started world.
  await page.waitForFunction(() => window.__grim && window.__grim.T && window.__grim._chunks,
    null, { timeout: 90000 });
  await page.evaluate(() => {
    const want = 'PLAY AS GUEST';
    for (const el of document.querySelectorAll('button, div, span, a')) {
      if ((el.textContent || '').trim().toUpperCase() === want) { el.click(); return true; }
    }
    return false;
  }).catch(() => {});
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForFunction(() => window.__grim.started && window.__grim._chunks && window.__grim._chunks.size > 50,
    null, { timeout: 90000 });
  const luma = await page.evaluate(() => window.__grim._groundLuma);
  await browser.close();

  ok(Array.isArray(luma) && luma.length === 16, 'uGroundLuma has all 16 layers', luma && luma.length);
  ok(luma.every(v => typeof v === 'number' && v >= 0 && v <= 1), 'every layer luma is a number in 0..1');

  const gap = (a, b) => Math.abs(luma[a] - luma[b]);
  const meadowGravel = gap(0, 7);
  const gravelSand = gap(7, 9);
  ok(contrast(meadowGravel) === 0, 'meadow/mountain-gravel gets zero extra softening, unchanged from before',
    'gap ' + meadowGravel.toFixed(3) + ', contrast ' + contrast(meadowGravel).toFixed(3));
  ok(contrast(gravelSand) > 0.5, 'mountain-gravel/beach-sand gets strong softening, fixing the reported stairstep',
    'gap ' + gravelSand.toFixed(3) + ', contrast ' + contrast(gravelSand).toFixed(3));

  // The other three bright outliers get the same automatic protection against
  // a representative low/mid-tone neighbour (meadow), with no code aware of
  // their specific surface indices. How MUCH softening scales with how far
  // apart the two actually measure -- snow (the most extreme) gets full
  // softening, frozen scree (the least extreme of the three) gets a real but
  // partial share -- rather than every "outlier" getting an identical fixed
  // boost, which is the point of keying this off measured contrast instead
  // of a hardcoded per-surface list.
  for (const i of [5, 14, 6]) {
    const g = gap(0, i);
    ok(g > 0.12 && contrast(g) > 0, NAME[i] + ' vs meadow clears the no-op floor and gets real softening',
      'gap ' + g.toFixed(3) + ', contrast ' + contrast(g).toFixed(3));
  }

  console.log('');
  if (fails.length) { console.log(fails.length + ' FAILED:'); fails.forEach(f => console.log('  ' + f)); process.exit(1); }
  console.log('all ground-contrast checks passed');
})().catch(e => { console.error(e); process.exit(1); });
