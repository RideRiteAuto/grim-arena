// Prove the zone music cannot do the thing Kevin asked it not to do.
//
// "I don't want it to be all choppy and flip back and forth" is a behaviour,
// not a file, and no amount of listening to one track proves it. So this
// drives musicZoneStable() with explicit dt against a scripted walk and
// asserts on what the music engine decides, then checks the crossfade never
// jumps and that all twelve files are actually reachable.
//
//   node harness/serve.js & node harness/musictest.js
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
  // THREE lands on the game object AFTER the object itself, and the size of
  // that gap moved when the editor track shipped, which broke this file on
  // `G.T` being undefined. Wait for the thing actually used.
  await page.waitForFunction(() => !!(window.__grim && window.__grim.T),
    { timeout: 90000 });

  const res = await page.evaluate(async () => {
    const G = window.__grim;
    const fail = [];
    const note = {};

    G.musicInit();
    if (!G.tracks) return { fail: ['musicInit built no tracks'] };

    const ZK = ['HEARTLANDS', 'GREENWOOD', 'FROSTWILD', 'IRONSPIRE', 'SUNCOAST',
                'WINDSCAR', 'EMBER', 'MISTFEN', 'SUNSCORCH', 'EASTRIDGE', 'ISLES', 'SEA'];
    note.trackCount = Object.keys(G.tracks).length;
    for (const k of ZK) if (!G.tracks[k]) fail.push('no track for ' + k);

    // Nothing may be downloading before a zone is even a candidate.
    const eager = ZK.filter(k => G.tracks[k].preload === 'auto');
    if (eager.length) fail.push('preloading with no candidate: ' + eager.join(','));

    // Drive the selector against a scripted walk. zoneAt is stubbed so the
    // test is about the hysteresis, not about the world grid.
    let here = 'HEARTLANDS';
    // Cancel the render loop first. This test steps the music by hand, and a
    // world still rendering against a stubbed player throws every frame.
    if (G.raf) { cancelAnimationFrame(G.raf); G.raf = null; }
    G.started = true;
    G.me = G.me || {};
    G.me.pos = new G.T.Vector3(0, 0, 0);
    G.zoneAt = () => here;
    G._musicZone = 'HEARTLANDS'; G._zoneCand = null; G._zoneCandT = 0;

    const step = (secs, dt) => {
      const out = [];
      for (let t = 0; t < secs; t += dt) out.push(G.musicZoneStable(dt));
      return out;
    };

    // A. step over a border and come straight back inside the hold window
    here = 'GREENWOOD';
    const a1 = step(1.5, 0.05);
    here = 'HEARTLANDS';
    const a2 = step(1.5, 0.05);
    note.briefExcursion = G._musicZone;
    if (a1.some(z => z !== 'HEARTLANDS') || a2.some(z => z !== 'HEARTLANDS')) {
      fail.push('A: a 1.5s excursion changed the music zone');
    }

    // B. commit: stay put past the hold
    here = 'GREENWOOD';
    step(4.0, 0.05);
    note.afterCommit = G._musicZone;
    if (G._musicZone !== 'GREENWOOD') fail.push('B: staying 4s did not commit (got ' + G._musicZone + ')');

    // C. stand on a border and jitter for 10s
    let flips = 0, prev = G._musicZone;
    for (let t = 0; t < 10; t += 0.1) {
      here = (Math.floor(t / 0.2) % 2) ? 'FROSTWILD' : 'GREENWOOD';
      const z = G.musicZoneStable(0.1);
      if (z !== prev) { flips++; prev = z; }
    }
    note.borderFlips = flips;
    if (flips !== 0) fail.push('C: border jitter flipped the track ' + flips + ' time(s)');

    // D. the crossfade itself: no frame may jump, and the blend must finish
    here = 'SUNSCORCH';
    G.musicOn = true; G.musicVol = 0.75;
    for (const k in G.trackVol) G.trackVol[k] = 0;
    G.trackVol.GREENWOOD = 0.3375;              // the outgoing track at full
    G._musicZone = 'GREENWOOD'; G._zoneCand = null; G._zoneCandT = 0;
    let maxJump = 0, maxSnap = 0;
    const prevV = Object.assign({}, G.trackVol);
    for (let t = 0; t < 12; t += 1 / 60) {
      G.stepMusic(1 / 60);
      for (const k in G.trackVol) {
        const now = G.trackVol[k], was = prevV[k] || 0;
        // Two different properties are being checked here. Within the
        // AUDIBLE range the blend must be genuinely smooth. Separately, the
        // ease deliberately snaps a departing track to zero once it drops
        // under a floor, and that snap is only acceptable while it is small:
        // measured from the floor it is about -34 dBFS, which is inaudible
        // under a track that is already back at full level. Assert the snap
        // stays under the floor rather than pretending it does not happen.
        const d = Math.abs(now - was);
        if (Math.max(now, was) > 0.05 && d > maxJump) maxJump = d;
        if (now === 0 && was > 0 && was > maxSnap) maxSnap = was;
        prevV[k] = now;
      }
    }
    note.maxPerFrameVolumeJump = Math.round(maxJump * 10000) / 10000;
    note.outgoing = Math.round(G.trackVol.GREENWOOD * 1000) / 1000;
    note.incoming = Math.round(G.trackVol.SUNSCORCH * 1000) / 1000;
    note.terminalSnap = Math.round(maxSnap * 10000) / 10000;
    if (maxJump > 0.02) fail.push('D: volume jumped ' + maxJump.toFixed(3) + ' in one frame while audible');
    if (maxSnap > 0.021) fail.push('D: a track snapped to silence from ' + maxSnap.toFixed(3) + ', above the documented floor');
    if (G.trackVol.GREENWOOD !== 0) fail.push('D: outgoing track never reached silence');
    if (G.trackVol.SUNSCORCH < 0.3) fail.push('D: incoming track never reached level');

    // E. every file actually resolves
    const bad = [];
    for (const k of ZK) {
      try {
        const r = await fetch('audio/zone-' + k.toLowerCase() + '.mp3', { method: 'HEAD' });
        if (!r.ok) bad.push(k + ':' + r.status);
      } catch (e) { bad.push(k + ':' + e.message); }
    }
    if (bad.length) fail.push('E: unreachable audio ' + bad.join(','));

    return { fail: fail, note: note };
  });

  res.pageErrors = errs;
  if (errs.length) res.fail.push('page errors: ' + errs.slice(0, 2).join(' | '));
  console.log(JSON.stringify(res, null, 1));
  await browser.close();
  process.exit(res.fail.length ? 1 : 0);
})();
