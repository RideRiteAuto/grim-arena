// Live-boot companion to ground-blend-migration.js: confirms patch 83.200's
// new default actually reaches the running GRIM_EDIT layer, not just the
// source files on disk. A fresh boot has no saved layer yet, so this is the
// "brand new world" path; ground-blend-migration.js covers the "existing
// world stamped with the old default" path in pure Node since that needs no
// browser at all.
const { chromium } = require('playwright');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

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
  // The editor asks for a key it cannot verify in this harness, so answer
  // the prompt the same way editor.js does, or editorOn never flips true.
  page.on('dialog', d => d.accept('harness-key'));
  await page.goto(URL + '?edit=1', { waitUntil: 'load' });
  await page.waitForFunction(() => window.__grim && window.__grim.editorOn === true, null, { timeout: 90000 });
  const blend = await page.evaluate(() => window.__grim.EDIT().raw.blend);
  await browser.close();

  ok(blend === 5, 'a freshly booted edit layer carries the new BLEND_DEFAULT of 5m end to end', 'got ' + blend);

  console.log('');
  if (fails.length) { console.log(fails.length + ' FAILED:'); fails.forEach(f => console.log('  ' + f)); process.exit(1); }
  console.log('all ground-blend-live checks passed');
})().catch(e => { console.error(e); process.exit(1); });
