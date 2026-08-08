// SUPERSEDED for routine use by relay-hybrid-test.js + relay-bot.js: two
// full 3D Playwright clients in one browser proved unstable in this sandbox
// (crashes with "Target page, context or browser has been closed" when both
// are driven concurrently, likely dual concurrent WebGL/swiftshader context
// contention under --no-sandbox -- unconfirmed root cause, not memory or
// relay-server health, both were ruled out). One real client + a scripted
// ws-protocol bot gives the same mutual-visibility coverage without that
// instability, and was the actual method used to validate Tier 2's relay
// items. Left here, not deleted, in case a future sandbox/launch-arg change
// makes two real clients reliable again -- worth revisiting since it is a
// strictly more realistic test than a client + a bot.
//
// Original intent: confirm two real game clients, both pointed at the local
// wrangler dev relay, actually see each other through the Durable Object
// (not just each independently opening a socket).
const { chromium } = require('playwright');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const RELAY = process.env.RELAY || 'ws://127.0.0.1:8787/world/main';

async function bootClient(browser, label) {
  const page = await browser.newPage({ viewport: { width: 1000, height: 700 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.addInitScript((relayUrl) => { try { localStorage.setItem('grim-relay', relayUrl); } catch (e) {} }, RELAY);
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(5000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(7000);
  return { page, label, errors };
}

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });

  const a = await bootClient(browser, 'A');
  await a.page.waitForTimeout(1500); // let A fully register before B joins
  const b = await bootClient(browser, 'B');
  await b.page.waitForTimeout(4000); // let relay propagate B's join to A

  const aState = await a.page.evaluate(() => {
    const g = window.__grim;
    return {
      netId: g.netId,
      remoteCount: g.remotes ? Object.keys(g.remotes).length : -1,
      remoteIds: g.remotes ? Object.keys(g.remotes) : []
    };
  }).catch(e => ({ evalError: String(e) }));

  const bState = await b.page.evaluate(() => {
    const g = window.__grim;
    return {
      netId: g.netId,
      remoteCount: g.remotes ? Object.keys(g.remotes).length : -1,
      remoteIds: g.remotes ? Object.keys(g.remotes) : []
    };
  }).catch(e => ({ evalError: String(e) }));

  console.log(JSON.stringify({
    aNetId: aState.netId, bNetId: bState.netId,
    aSeesB: aState.remoteIds && aState.remoteIds.includes(bState.netId),
    bSeesA: bState.remoteIds && bState.remoteIds.includes(aState.netId),
    aState, bState,
    aErrors: a.errors.slice(0, 5), bErrors: b.errors.slice(0, 5)
  }, null, 2));

  await browser.close();
})();
