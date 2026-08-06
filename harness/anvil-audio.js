// Render the anvil's hammer strike offline to a WAV, and measure it.
//
// The forge fires four blows in 1.6 seconds (forgeClang resets to 0.4), so this
// renders exactly that sequence rather than one isolated hit: the thing most
// likely to be wrong is that four blows in a row sound identical, which is the
// giveaway of a sample being retriggered. Then a single strike on its own so
// the ring-out can be heard to the end.
//
//   node harness/serve.js & node harness/anvil-audio.js
const { chromium } = require('playwright');
const fs = require('fs');

const BASE = process.env.URL || 'http://127.0.0.1:8123/model-lab/';
const OUT = process.env.OUT || '/tmp/anvil-audio';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox', '--autoplay-policy=no-user-gesture-required']
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(String(e && e.message)));
  await page.goto(BASE + 'anvil.html', { waitUntil: 'load', timeout: 60000 });
  for (let i = 0; i < 40; i++) {
    if (await page.evaluate(() => !!window.__ready).catch(() => false)) break;
    await page.waitForTimeout(300);
  }

  const render = async (secs, times, label) => {
    const res = await page.evaluate(async ([s, ts]) => {
      const RATE = 44100;
      const oc = new OfflineAudioContext(1, Math.floor(RATE * s), RATE);
      const bus = oc.createGain(); bus.gain.value = 1; bus.connect(oc.destination);
      ts.forEach((t, i) => window.__kit.strikeAt(oc, bus, t, { gain: 0.5, heavy: i === 0 }));
      const r = await oc.startRendering();
      const ch = r.getChannelData(0);
      let peak = 0, sum = 0;
      const BINS = 1200, env = new Array(BINS).fill(0);
      const per = Math.floor(ch.length / BINS);
      for (let i = 0; i < ch.length; i++) {
        const a = Math.abs(ch[i]);
        if (a > peak) peak = a;
        sum += ch[i] * ch[i];
        const b = Math.min(BINS - 1, Math.floor(i / per));
        if (a > env[b]) env[b] = a;
      }
      // how long the ring takes to fall 40 dB from the peak, measured from the
      // LAST strike. A short tail is a clank; an anvil sustains.
      const lastAt = Math.floor((ts[ts.length - 1] / s) * BINS);
      let tail = 0;
      for (let b = lastAt; b < BINS; b++) {
        if (env[b] > peak * 0.01) tail = (b - lastAt) / BINS * s;
      }
      const pcm = new Int16Array(ch.length);
      for (let i = 0; i < ch.length; i++) {
        pcm[i] = Math.max(-32768, Math.min(32767, Math.round(ch[i] * 32767)));
      }
      return { rate: RATE, peak, rms: Math.sqrt(sum / ch.length), tail, env,
               pcm: Array.from(new Uint8Array(pcm.buffer)) };
    }, [secs, times]);

    const data = Buffer.from(res.pcm);
    const hdr = Buffer.alloc(44);
    hdr.write('RIFF', 0); hdr.writeUInt32LE(36 + data.length, 4); hdr.write('WAVE', 8);
    hdr.write('fmt ', 12); hdr.writeUInt32LE(16, 16); hdr.writeUInt16LE(1, 20);
    hdr.writeUInt16LE(1, 22); hdr.writeUInt32LE(res.rate, 24);
    hdr.writeUInt32LE(res.rate * 2, 28); hdr.writeUInt16LE(2, 32); hdr.writeUInt16LE(16, 34);
    hdr.write('data', 36); hdr.writeUInt32LE(data.length, 40);
    fs.writeFileSync(OUT + '/' + label + '.wav', Buffer.concat([hdr, data]));
    return { label, peak: +res.peak.toFixed(4), rms: +res.rms.toFixed(5), tail: +res.tail.toFixed(2) };
  };

  // the forge sequence, then one strike left to ring out
  const forge = await render(4.2, [0.10, 0.50, 0.90, 1.30], 'forge-sequence');
  const single = await render(3.2, [0.08], 'single-strike');

  const fail = [];
  if (forge.peak >= 0.999) fail.push('clipping on the sequence');
  if (single.tail < 0.8) fail.push('ring too short: ' + single.tail + 's, an anvil is not a clank');
  if (single.tail > 3.2) fail.push('ring too long: ' + single.tail + 's, that is a church bell');
  if (errs.length) fail.push(errs.length + ' page error(s): ' + errs.slice(0, 2).join(' | '));

  console.log(JSON.stringify({ forge, single, out: OUT, errs, fail }, null, 2));
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})();
