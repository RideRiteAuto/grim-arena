// Prove the sampled audio works inside the real game, not just in the lab.
//
// Boot alone cannot catch any of this. The AudioContext does not exist until a
// user gesture, decodeAudioData is async and swallows its own failures by
// design, and a browser that cannot read our mp3 would simply play nothing
// while every other test stayed green. So this drives the real page, forces
// audio up, waits for the decode, and asserts on the decoded buffers.
//
//   node harness/serve.js & node harness/sfx-ingame.js
const { chromium } = require('playwright');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox',
           '--autoplay-policy=no-user-gesture-required']
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(String(e && e.message)));
  await page.goto(URL, { waitUntil: 'load', timeout: 90000 });

  // wait for the game object, then force the audio path up the same way a
  // click would
  await page.waitForFunction(() => !!window.__grim, { timeout: 90000 });
  const res = await page.evaluate(async () => {
    const G = window.__grim;
    G.audioInit();
    if (!G.ac) return { fail: 'no AudioContext after audioInit' };
    if (!G._samples) return { fail: 'sampleInit did not build a player' };
    await G._samples.load;

    const want = ['anvil-strike', 'anvil-ring', 'anvil-dead', 'fire-bed',
                  'combat-swing', 'combat-heavy', 'combat-block', 'combat-parry',
                  'combat-hit-flesh', 'combat-hit-leather', 'combat-hit-plate',
                  'combat-crit-ring'];
    const got = {};
    for (const n of want) got[n] = G._samples.has(n);

    // Measure the buffers the game is actually holding. has() only says a key
    // exists; a partially failed decode leaves a buffer of the right length
    // full of silence, and that is the failure worth catching here.
    const stats = {};
    for (const n of want) {
      if (!got[n]) continue;
      const b = G._samples.play(n, { gain: 0 });
      if (!b) { stats[n] = 'play() returned null'; continue; }
      try { b.src.stop(); } catch (e) {}
      const buf = b.src.buffer;
      const d = buf.getChannelData(0);
      let peak = 0, sum = 0;
      for (let i = 0; i < d.length; i++) {
        const a = Math.abs(d[i]);
        if (a > peak) peak = a;
        sum += d[i] * d[i];
      }
      stats[n] = {
        seconds: +buf.duration.toFixed(2),
        rate: buf.sampleRate,
        peak: +peak.toFixed(3),
        rms: +Math.sqrt(sum / d.length).toFixed(4)
      };
    }

    // and the two things that actually fire in play
    let anvilOk = true, fireOk = true;
    try { G.anvilStrike(true); G.anvilStrike(false); G.anvilStrike(false); }
    catch (e) { anvilOk = String(e.message); }
    try {
      const f = (G.campfires || [])[0];
      if (f) { const v = G.campfireVoice(f.kit, 0.5); v.setDistance(5, 30); v.stop(); }
      else fireOk = 'no campfire in world';
    } catch (e) { fireOk = String(e.message); }

    return { got, stats, anvilOk, fireOk };
  });

  const fail = [];
  if (res.fail) fail.push(res.fail);
  for (const [n, ok] of Object.entries(res.got || {})) {
    if (!ok) fail.push('sample did not decode: ' + n);
  }
  for (const [n, st] of Object.entries(res.stats || {})) {
    if (typeof st === 'string') { fail.push(n + ': ' + st); continue; }
    // a decode that silently produced silence is the failure this catches
    if (st.peak < 0.05) fail.push(n + ' decoded to near silence, peak ' + st.peak);
    // Anvil rings and the fire bed must carry a tail; combat one-shots are
    // MEANT to be short (a 0.2s hit is a hit, not a truncation). Floor per
    // family: 0.15s catches a decode that produced near-nothing either way.
    const minSec = n.indexOf('combat-') === 0 ? 0.15 : 0.5;
    if (st.seconds < minSec) fail.push(n + ' is only ' + st.seconds + 's');
  }
  if (res.anvilOk !== true) fail.push('anvilStrike threw: ' + res.anvilOk);
  if (res.fireOk !== true) fail.push('campfireVoice: ' + res.fireOk);
  if (errs.length) fail.push(errs.length + ' page error(s): ' + errs.slice(0, 2).join(' | '));

  console.log(JSON.stringify({ ...res, errs, fail }, null, 2));
  await browser.close();
  process.exit(fail.length ? 1 : 0);
})();
