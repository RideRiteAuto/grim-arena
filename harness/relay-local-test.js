// Investigation test, not a permanent harness file: can headless Chromium in
// this sandbox complete a WebSocket round trip to a LOCAL wrangler dev relay
// (ws://127.0.0.1:8787) where it's confirmed unable to reach the production
// wss://grim-arena.kevin-230.workers.dev? If yes, Tier 2 relay-touching items
// get real client+server test coverage here for the first time. If no, we're
// stuck with code-reading + two-tab tests on Kevin's machine as before.
//
// Uses the client's own documented local-override hook (GRIM_RELAY() reads
// localStorage 'grim-relay' before falling back to the hardcoded production
// URL) -- no bundle patch needed to test this.
const { chromium } = require('playwright');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const RELAY = process.env.RELAY || 'ws://127.0.0.1:8787/world/main';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + (e && e.message)));

  // Set the relay override BEFORE any page script runs.
  await page.addInitScript((relayUrl) => {
    try { localStorage.setItem('grim-relay', relayUrl); } catch (e) {}
  }, RELAY);

  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(6000);

  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(8000);

  const started = await page.evaluate(() => !!(window.__grim && window.__grim.started)).catch(() => false);
  const relayInUse = await page.evaluate(() => { try { return localStorage.getItem('grim-relay'); } catch (e) { return null; } });

  // Give the relay connection attempt time to either succeed or fail.
  await page.waitForTimeout(6000);

  const netState = await page.evaluate(() => {
    const g = window.__grim;
    if (!g) return { noGrim: true };
    return {
      sharedWorldOn: !!g.sharedWorldOn,
      relayMode: !!g._relayMode,
      wsReadyState: g._ws ? g._ws.readyState : null, // 0 CONNECTING,1 OPEN,2 CLOSING,3 CLOSED
      hasHostConn: !!g.hostConn,
      hostConnOpen: g.hostConn ? !!g.hostConn.open : null,
      netId: g.netId || null,
      worldStatusText: g.worldStatusText || null
    };
  }).catch(e => ({ evalError: String(e) }));

  console.log(JSON.stringify({
    started,
    relayInUse,
    netState,
    consoleErrors: errors.slice(0, 15)
  }, null, 2));

  await browser.close();
})();
