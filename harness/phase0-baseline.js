// Phase 0 verification harness (terrain worker offload plan).
//
// Byte-diffs the pure-function extraction: dumps chunkProps (clutter+nodes),
// buildChunk's per-vertex colors/tiles/mixes for a battery of chunks, and
// raw terrainColor/groundSurface/bridgePad samples near bridges, to a JSON
// fixture. Run once before the refactor (mode=before) and once after
// (mode=after), then diff the two files. Not committed to the repo; this is
// scratch tooling for one verification pass.
const { chromium } = require('playwright');
const fs = require('fs');
const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const MODE = process.argv[2] || 'before';
const OUT = `/tmp/phase0-${MODE}.json`;

const CHUNKS = [];
for (let cx = 3; cx <= 7; cx++) for (let cz = 3; cz <= 7; cz++) CHUNKS.push([cx, cz]);
for (const c of [[-12, 9], [40, -6], [-20, -20], [25, 18], [0, 0], [-3, 4], [-1, -1], [50, 50]]) CHUNKS.push(c);

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1024, height: 640 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    const hits = Array.from(document.querySelectorAll('button, a, div, span'))
      .filter(el => (el.textContent || '').toUpperCase().includes('PLAY AS GUEST'));
    if (hits.length) hits[hits.length - 1].click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); });
  await page.waitForTimeout(8000);

  const data = await page.evaluate((cs) => {
    const g = window.__grim;
    const f = (n) => Number(n).toFixed(6);
    const out = { chunkProps: {}, vertData: {}, bridgeSamples: [], terrainColorSamples: [], groundSurfaceSamples: [] };

    for (const [cx, cz] of cs) {
      const p = g.chunkProps(cx, cz);
      out.chunkProps[cx + ',' + cz] = {
        clutter: p.clutter.map(c => [c.type, c.zone, f(c.x), f(c.y), f(c.z), f(c.rot), f(c.sc)].join('|')),
        nodes: p.nodes.map(n => [n.kind, n.zone, n.nid, f(n.x), f(n.y), f(n.z), f(n.rot), f(n.sc)].join('|'))
      };
    }

    // buildChunk vertex data: read straight off the live scene chunk meshes,
    // which cover both terrainColor and groundSurface (colors/aTile/aMix
    // attributes) for whatever the player actually has streamed in.
    if (g._chunks) {
      let n = 0;
      for (const [key, rec] of g._chunks) {
        if (n++ > 40) break;
        const geo = rec.mesh.geometry;
        const col = geo.getAttribute('color'), til = geo.getAttribute('aTile'), mix = geo.getAttribute('aMix');
        const pos = geo.getAttribute('position');
        const sample = [];
        for (let i = 0; i < pos.count; i += 17) {
          sample.push([
            f(pos.getX(i)), f(pos.getY(i)), f(pos.getZ(i)),
            f(col.getX(i)), f(col.getY(i)), f(col.getZ(i)),
            f(til.getX(i)), f(til.getY(i)), f(til.getZ(i)), f(til.getW(i)),
            f(mix.getX(i)), f(mix.getY(i)), f(mix.getZ(i))
          ].join(','));
        }
        out.vertData[key] = sample.join(';');
      }
    }

    // Direct pure-function samples, including near a bridge if one exists.
    const c = { r: 0, g: 0, b: 0 }, su = [0, 0, 0, 0, 0, 0, 0];
    for (let i = 0; i < 400; i++) {
      const wx = (i * 37 - 5000) % 6000, wz = (i * 53 - 4000) % 4000;
      const zi = g.WORLD().zone(wx, wz);
      const h = g.WORLD().height(wx, wz);
      g.terrainColor(zi, h, wx, wz, c);
      out.terrainColorSamples.push([f(wx), f(wz), f(c.r), f(c.g), f(c.b)].join(','));
      g.groundSurface(zi, h, wx, wz, su);
      out.groundSurfaceSamples.push([f(wx), f(wz), ...su.map(f)].join(','));
    }
    const B = g.WORLD().bridges || [];
    for (const b of B) {
      for (let s = -40; s <= 40; s += 4) {
        const wx = b.x + Math.sin(b.heading) * s, wz = b.z + Math.cos(b.heading) * s;
        out.bridgeSamples.push([f(wx), f(wz), f(g.bridgePad(wx, wz))].join(','));
      }
    }
    return out;
  }, CHUNKS);

  fs.writeFileSync(OUT, JSON.stringify(data));
  console.log(JSON.stringify({ mode: MODE, out: OUT, errors, chunkCount: CHUNKS.length, vertChunks: Object.keys(data.vertData).length }, null, 2));
  await browser.close();
})();
