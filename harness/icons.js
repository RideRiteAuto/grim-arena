// Item icon test.
//
// The generated items - 16 tools and 34 materials - used to share two tool
// silhouettes and one material disc between them, so most of the pack was the
// same picture in different paint. This is the guard against that coming back:
// it hashes every icon's markup and fails if any two items produce identical
// art. It also renders every icon into a labelled contact sheet so the result
// can be looked at rather than assumed.
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const OUT = process.env.OUT || '/tmp/icons';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1180, height: 1000 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(5000);
  for (let i = 0; i < 40; i++) {
    const ok = await page.evaluate(() => !!(window.__grim && window.__grim.ITEMS)).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(1000);
  }

  const report = await page.evaluate(() => {
    const g = window.__grim;
    const R = g.ITEMS();
    // GRIM_RULES is module-scoped inside the bundle and g.C is cfg(), not the
    // rules table, so classify from the registry itself: tiered tools carry a
    // `tool` kind and a `toolTier`, materials are stackables with no slot.
    const toolIds = {}, matIds = {};
    for (const id in R) {
      if (R[id].tool && R[id].toolTier) toolIds[id] = R[id].toolTier + ':' + R[id].tool;
      else if (R[id].stack && !R[id].slot) matIds[id] = 'material';
    }

    const out = { items: {}, counts: { all: 0, tools: 0, mats: 0 } };
    for (const id in R) {
      const icon = R[id].icon;
      out.counts.all++;
      if (toolIds[id]) out.counts.tools++;
      if (matIds[id]) out.counts.mats++;
      out.items[id] = {
        len: icon ? String(icon).length : 0,
        // full markup, so identical art is detectable exactly rather than by eye
        art: String(icon || ''),
        group: toolIds[id] ? 'tool' : (matIds[id] ? 'material' : 'hand'),
        tag: toolIds[id] || matIds[id] || ''
      };
    }
    return out;
  });

  // ---- contact sheet -------------------------------------------------------
  const shot = async (group, file, title) => {
    await page.evaluate(([group, title]) => {
      const g = window.__grim, R = g.ITEMS();
      const toolIds = {}, matIds = {};
      for (const id in R) {
        if (R[id].tool && R[id].toolTier) toolIds[id] = 1;
        else if (R[id].stack && !R[id].slot) matIds[id] = 1;
      }
      const want = (id) => group === 'tool' ? !!toolIds[id]
        : group === 'material' ? !!matIds[id]
        : !(toolIds[id] || matIds[id]);
      let el = document.getElementById('__iconsheet');
      if (el) el.remove();
      el = document.createElement('div');
      el.id = '__iconsheet';
      el.style.cssText = 'position:fixed;inset:0;z-index:99999;background:#1a1a1a;color:#ededed;' +
        'font-family:Arial,Helvetica,sans-serif;padding:14px 16px;overflow:hidden;';
      const ids = Object.keys(R).filter(want).sort();
      el.innerHTML = '<div style="color:#F3DC00;font-size:17px;font-weight:800;margin-bottom:10px">' + title +
        ' <span style="color:#8f8f8f;font-size:12px;font-weight:600">' + ids.length + ' items</span></div>' +
        '<div style="display:grid;grid-template-columns:repeat(8,1fr);gap:9px">' +
        ids.map(id =>
          '<div style="background:#232323;border:1px solid #383838;border-radius:9px;padding:7px 5px;text-align:center">' +
          '<div style="width:46px;height:46px;margin:0 auto 5px;display:flex;align-items:center;justify-content:center">' +
          R[id].icon + '</div>' +
          '<div style="font-size:9px;line-height:1.2;color:#cfcabd">' + id + '</div></div>').join('') +
        '</div>';
      document.body.appendChild(el);
    }, [group, title]);
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${OUT}/${file}` });
  };
  await shot('tool', 'tools.png', 'GRIM WORLD  tiered tools');
  await shot('material', 'materials.png', 'GRIM WORLD  materials');
  await shot('hand', 'hand.png', 'GRIM WORLD  equipment and hand-drawn items');

  // ---- assertions ----------------------------------------------------------
  const fails = [];
  const byArt = {};
  for (const id in report.items) {
    const it = report.items[id];
    if (!it.len) { fails.push(id + ': no icon'); continue; }
    if (it.len < 40) fails.push(id + ': icon markup suspiciously short (' + it.len + ')');
    if (byArt[it.art]) fails.push('IDENTICAL ART: ' + id + ' and ' + byArt[it.art]);
    else byArt[it.art] = id;
  }
  const tools = Object.keys(report.items).filter(k => report.items[k].group === 'tool');
  const mats = Object.keys(report.items).filter(k => report.items[k].group === 'material');
  if (tools.length < 14) fails.push('expected 14+ tiered tools, found ' + tools.length);
  if (mats.length < 30) fails.push('expected 30+ stackable materials, found ' + mats.length);

  console.log(JSON.stringify({
    counts: report.counts,
    tools: tools.length, materials: mats.length,
    distinctArt: Object.keys(byArt).length,
    totalItems: Object.keys(report.items).length,
    fails, errors: errors.slice(0, 6)
  }, null, 2));
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
