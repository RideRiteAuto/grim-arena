// Structural in-game test for patch 80.142 (pvp/open-world projectile
// visibility). A genuine two-tab live-relay test was attempted first and
// abandoned: this sandbox's headless Chromium cannot complete a wss://
// upgrade to the production Cloudflare Worker at all (plain Node and curl
// both reach it fine over HTTPS - this looks like a headless-browser-vs-
// sandbox-network quirk, not anything about this patch), so `hostConn`
// never opens and a real send/receive round trip can't be observed here.
//
// This test gets equivalent coverage without a live connection, by driving
// both ends of the wire directly against a single booted client:
//   SEND side  - stub this.hostConn, cast, and check coopProj() produces
//                exactly the right 'pproj' message, only when it should
//                (relay mode, own cast, not coop).
//   RECEIVE side - call onRelay() with a synthetic 'pproj' message exactly
//                shaped like what the server would forward, and check it
//                spawns the real high-quality cosmetic projectile via the
//                existing fake-caster path in onWorldData - the same path
//                already proven for coop 'proj'.
// Together these cover every line patch 80.142 touches; only the actual
// network hop (relay-worker.js forwarding 'pproj', now in RELAYED) is
// unverified by this harness and was instead verified by direct code
// reading against the real relay-worker.js.
//
// Boot sequence copied from harness/rf-hotkey-test.js.
const { chromium } = require('playwright');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);

  const started = await page.evaluate(() => !!(window.__grim && window.__grim.started)).catch(() => false);
  const results = [];
  const check = (label, cond) => results.push({ label, ok: !!cond });
  check('game started', started);

  if (started) {
    // ---------------------------------------------------------------------
    // SEND side: stub hostConn, force relay mode, cast, inspect what was
    // actually sent.
    // ---------------------------------------------------------------------
    const sendInfo = await page.evaluate(() => {
      const g = window.__grim;
      const sent = [];
      const realHostConn = g.hostConn, realRelayMode = g._relayMode, realCoop = g.coop;
      g.hostConn = { open: true, send: (m) => sent.push(m) };
      g._relayMode = true;
      g.coop = false;
      g.element = 'frost';
      g.me.pos.set(0, 0, 0);
      g.me.yaw = 0;
      let threw = null;
      try { g.fireFrost(g.me); } catch (e) { threw = e.message; }
      const out = { threw, sentCount: sent.length, msg: sent[0] || null };
      g.hostConn = realHostConn; g._relayMode = realRelayMode; g.coop = realCoop;
      return out;
    });
    check('fireFrost -> coopProj does not throw with a stubbed hostConn', !sendInfo.threw);
    check('exactly one pproj message sent for the local player\'s own cast', sendInfo.sentCount === 1);
    check('message type is "pproj" (not the server-only "proj")', sendInfo.msg && sendInfo.msg.t === 'pproj');
    check('message carries the frost kind', sendInfo.msg && sendInfo.msg.k === 'frost');
    check('message carries a 3-component position', sendInfo.msg && Array.isArray(sendInfo.msg.p) && sendInfo.msg.p.length === 3);
    check('message carries a 3-component velocity', sendInfo.msg && Array.isArray(sendInfo.msg.v) && sendInfo.msg.v.length === 3);

    // coop mode must still use the OLD netSendRaw path, unaffected - confirm
    // coopProj does NOT touch a stubbed hostConn while this.coop is true.
    const coopInfo = await page.evaluate(() => {
      const g = window.__grim;
      const sent = [];
      const realHostConn = g.hostConn, realRelayMode = g._relayMode, realCoop = g.coop, realNetFoe = g.netFoe;
      g.hostConn = { open: true, send: (m) => sent.push(m) };
      g._relayMode = true;
      g.coop = true;
      g.netFoe = { pos: new g.T.Vector3(5, 0, 5), g: { visible: false } };
      g.isHost = true;
      let threw = null;
      try { g.fireFrost(g.me); } catch (e) { threw = e.message; }
      const out = { threw, sentToStubbedHostConn: sent.length };
      g.hostConn = realHostConn; g._relayMode = realRelayMode; g.coop = realCoop; g.netFoe = realNetFoe;
      return out;
    });
    check('coop mode unaffected: does not throw', !coopInfo.threw);
    check('coop mode unaffected: still does NOT send over hostConn (uses netSendRaw, untouched)', coopInfo.sentToStubbedHostConn === 0);

    // ---------------------------------------------------------------------
    // RECEIVE side: feed onRelay() a synthetic 'pproj' exactly as the relay
    // would forward one from another player, and confirm it spawns the
    // real, high-quality, cosmetic projectile via the existing fake-caster
    // path (same one already proven for coop's 'proj').
    // ---------------------------------------------------------------------
    const recvInfo = await page.evaluate(() => {
      const g = window.__grim;
      const before = g.projectiles.length;
      let threw = null;
      try {
        g.onRelay({ t: 'pproj', k: 'frost', p: [3, 1.5, 3], v: [5, 0, 5], _p: 'REMOTE_TEST_PLAYER' });
      } catch (e) { threw = e.message; }
      const after = g.projectiles.length;
      const p = g.projectiles[g.projectiles.length - 1];
      return {
        threw, before, after,
        kind: p ? p.kind : null,
        isGroup: p && p.mesh ? !!p.mesh.isGroup : false,
        ownerCosmetic: p && p.owner ? !!p.owner.cosmetic : false,
        dmgZero: p ? p.dmg === 0 : null,
        posMatches: p && p.mesh ? (Math.abs(p.mesh.position.x - 3) < 0.01 && Math.abs(p.mesh.position.z - 3) < 0.01) : false
      };
    });
    check('onRelay(\'pproj\') does not throw', !recvInfo.threw);
    check('a new projectile was spawned from the synthetic remote message', recvInfo.after === recvInfo.before + 1);
    check('it is a frost bolt', recvInfo.kind === 'frost');
    check('it is the real kit-built mesh (a Group), not a placeholder icosahedron', recvInfo.isGroup);
    check('its owner is marked cosmetic (receiver will not resolve damage from it locally)', recvInfo.ownerCosmetic);
    check('its damage is zeroed (real damage only ever arrives via hit/nhit)', recvInfo.dmgZero);
    check('it was placed at the network message\'s exact position, not the fake caster\'s', recvInfo.posMatches);

    // Self-echo guard: a 'pproj' claiming to be from myself must be ignored
    // (defensive - the relay's broadcast() already excludes the sender).
    const echoInfo = await page.evaluate(() => {
      const g = window.__grim;
      const realNetId = g.netId;
      g.netId = 'MY_TEST_ID';
      const before = g.projectiles.length;
      g.onRelay({ t: 'pproj', k: 'frost', p: [9, 1.5, 9], v: [1, 0, 1], _p: 'MY_TEST_ID' });
      const after = g.projectiles.length;
      g.netId = realNetId;
      return { before, after };
    });
    check('a pproj claiming to be from myself is ignored (no duplicate spawn)', echoInfo.after === echoInfo.before);

    // Different kinds go through the same path correctly - spot check fire
    // and arrow so the fix is confirmed generic, not frost-only.
    const otherKinds = await page.evaluate(() => {
      const g = window.__grim;
      const out = {};
      for (const k of ['fire', 'arrow', 'snare', 'toxin']) {
        const before = g.projectiles.length;
        let threw = null;
        try { g.onRelay({ t: 'pproj', k, p: [1, 1.5, 1], v: [4, 0, 4], _p: 'REMOTE_TEST_PLAYER_2' }); } catch (e) { threw = e.message; }
        const p = g.projectiles[g.projectiles.length - 1];
        out[k] = { threw, spawned: g.projectiles.length === before + 1, kind: p ? p.kind : null };
      }
      return out;
    });
    for (const k of ['fire', 'arrow', 'snare', 'toxin']) {
      check(`pproj also works for kind "${k}"`, otherKinds[k] && !otherKinds[k].threw && otherKinds[k].spawned && otherKinds[k].kind === k);
    }
  }

  check('no page/console errors', errors.length === 0);

  console.log(JSON.stringify({ results, errors: errors.slice(0, 20) }, null, 2));
  const failed = results.filter(r => !r.ok);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('TEST CRASHED:', e); process.exit(1); });
