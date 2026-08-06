// Render the campfire's procedural sound offline and write it out as a WAV,
// plus a waveform PNG.
//
// Sound is the one part of a prop that cannot be reviewed by looking at a
// screenshot, and "it sounded fine when I played it once" is not a test. An
// OfflineAudioContext renders the exact graph the game will build, at full
// speed, deterministically enough to eyeball: you can see whether the crackles
// are evenly spaced (a rhythm, which is wrong), whether the bed is clipping,
// and whether the level sits where it should.
//
//   node harness/serve.js & node harness/campfire-audio.js 12
const { chromium } = require('playwright');
const fs = require('fs');

const SECONDS = Number(process.argv[2] || 12);
const BASE = process.env.URL || 'http://127.0.0.1:8123/model-lab/';
const OUT = process.env.OUT || '/tmp/campfire-audio';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox', '--autoplay-policy=no-user-gesture-required']
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(String(e && e.message)));
  await page.goto(BASE + 'campfire.html', { waitUntil: 'load', timeout: 60000 });
  for (let i = 0; i < 40; i++) {
    if (await page.evaluate(() => !!window.__ready).catch(() => false)) break;
    await page.waitForTimeout(300);
  }

  const res = await page.evaluate(async (secs) => {
    const RATE = 44100;
    const oc = new OfflineAudioContext(1, Math.floor(RATE * secs), RATE);
    const h = window.__kit.sound(oc, oc.destination, { prerender: secs, gain: 0.55 });
    h.setVolume(1);
    const rendered = await oc.startRendering();
    const ch = rendered.getChannelData(0);
    // peak, rms and a coarse envelope for the plot
    let peak = 0, sum = 0;
    const BINS = 1200;
    const env = new Array(BINS).fill(0);
    const per = Math.floor(ch.length / BINS);
    for (let i = 0; i < ch.length; i++) {
      const a = Math.abs(ch[i]);
      if (a > peak) peak = a;
      sum += ch[i] * ch[i];
      const b = Math.min(BINS - 1, Math.floor(i / per));
      if (a > env[b]) env[b] = a;
    }
    // count transients: an envelope bin more than 3x the running floor
    const sorted = env.slice().sort((a, b) => a - b);
    const med = sorted[Math.floor(BINS * 0.5)];
    let hits = 0, wasOver = false;
    for (let b = 0; b < BINS; b++) {
      const over = env[b] > med * 1.9;
      if (over && !wasOver) hits++;      // count events, not bins
      wasOver = over;
    }
    // downsample to 16-bit PCM for the wav
    const pcm = new Int16Array(ch.length);
    for (let i = 0; i < ch.length; i++) {
      pcm[i] = Math.max(-32768, Math.min(32767, Math.round(ch[i] * 32767)));
    }
    return {
      rate: RATE, peak, rms: Math.sqrt(sum / ch.length), hits, med, env,
      pcm: Array.from(new Uint8Array(pcm.buffer))
    };
  }, SECONDS);

  // WAV header
  const data = Buffer.from(res.pcm);
  const hdr = Buffer.alloc(44);
  hdr.write('RIFF', 0); hdr.writeUInt32LE(36 + data.length, 4); hdr.write('WAVE', 8);
  hdr.write('fmt ', 12); hdr.writeUInt32LE(16, 16); hdr.writeUInt16LE(1, 20);
  hdr.writeUInt16LE(1, 22); hdr.writeUInt32LE(res.rate, 24);
  hdr.writeUInt32LE(res.rate * 2, 28); hdr.writeUInt16LE(2, 32); hdr.writeUInt16LE(16, 34);
  hdr.write('data', 36); hdr.writeUInt32LE(data.length, 40);
  const wav = OUT + '/campfire.wav';
  fs.writeFileSync(wav, Buffer.concat([hdr, data]));

  // waveform SVG, cheap and readable
  const W = 1200, H = 220;
  const pts = res.env.map((v, i) => (i) + ',' + (H / 2 - v * (H / 2 - 6))).join(' ');
  const pts2 = res.env.map((v, i) => (i) + ',' + (H / 2 + v * (H / 2 - 6))).join(' ');
  fs.writeFileSync(OUT + '/waveform.svg',
    '<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '">' +
    '<rect width="' + W + '" height="' + H + '" fill="#141414"/>' +
    '<line x1="0" y1="' + H / 2 + '" x2="' + W + '" y2="' + H / 2 + '" stroke="#333"/>' +
    '<polyline fill="none" stroke="#F3DC00" stroke-width="1" points="' + pts + '"/>' +
    '<polyline fill="none" stroke="#F3DC00" stroke-width="1" points="' + pts2 + '"/>' +
    '<text x="8" y="16" fill="#8f8f8f" font-family="monospace" font-size="12">campfire, ' +
    SECONDS + 's, peak ' + res.peak.toFixed(3) + ', rms ' + res.rms.toFixed(4) +
    ', transients ' + res.hits + '</text></svg>');

  const fail = [];
  if (res.peak >= 0.999) fail.push('clipping: peak ' + res.peak.toFixed(3));
  if (res.peak < 0.10) fail.push('too quiet: peak ' + res.peak.toFixed(3));
  if (res.rms < 0.004) fail.push('bed missing: rms ' + res.rms.toFixed(5));
  // a fire this size should crack a few times a second, not once every ten
  const perSec = res.hits / SECONDS;
  if (perSec < 0.6) fail.push('too few crackles: ' + perSec.toFixed(2) + '/s');
  if (perSec > 14) fail.push('too many crackles: ' + perSec.toFixed(2) + '/s');
  if (errs.length) fail.push(errs.length + ' page error(s)');

  console.log(JSON.stringify({
    seconds: SECONDS, peak: +res.peak.toFixed(4), rms: +res.rms.toFixed(5),
    transients: res.hits, perSecond: +perSec.toFixed(2), wav, errs, fail
  }, null, 2));
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})();
