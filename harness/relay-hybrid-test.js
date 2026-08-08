// Proves a real game client and a scripted bot see each other through the
// local wrangler relay -- the mutual-visibility check the two-full-client
// test was after, without needing a second unstable 3D browser context.
// One real Playwright client (proven stable, harness/relay-local-test.js's
// pattern) + one harness/relay-bot.js speaking the wire protocol directly.
const { chromium } = require('playwright');
const { RelayBot } = require('./relay-bot');

const URL = process.env.URL || 'http://127.0.0.1:8123/index.html';
const RELAY_WS = process.env.RELAY || 'ws://127.0.0.1:8787/world/main';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1000, height: 700 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.addInitScript((relayUrl) => { try { localStorage.setItem('grim-relay', relayUrl); } catch (e) {} }, RELAY_WS);
  await page.goto(URL, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(5000);
  await page.evaluate(() => { if (window.__grim && window.__grim.play) window.__grim.play(); }).catch(() => {});
  await page.waitForTimeout(6000);

  const clientNetId = await page.evaluate(() => (window.__grim && window.__grim.netId) || null).catch(() => null);

  // Bring the bot in after the real client is fully settled, mirroring how
  // the two-client test staggered A then B.
  const bot = new RelayBot(RELAY_WS, { name: 'BOT1' });
  await bot.connect();
  await bot.hello();
  bot.setPos(3, 0, 3, 0);
  bot.startPositionPump(100); // ~10Hz, matching the real client's netWorldSend throttle

  // Give both sides time to exchange several rounds of position broadcasts.
  await page.waitForTimeout(4000);

  const clientState = await page.evaluate((botId) => {
    const g = window.__grim;
    const remotes = g.remotes || {};
    return {
      netId: g.netId,
      remoteCount: Object.keys(remotes).length,
      remoteIds: Object.keys(remotes),
      seesBot: !!remotes[botId],
      // remotes[id] shape per updateRemote(): {ent, s, name, fr, tx, ty, tz, age}
      botRemoteSnapshot: remotes[botId] ? { tx: remotes[botId].tx, tz: remotes[botId].tz, name: remotes[botId].name } : null
    };
  }, bot.id).catch(e => ({ evalError: String(e) }));

  bot.stopPositionPump();
  const botSeesClient = bot.sendersSeenFor('s').includes(clientNetId);
  const botSCount = bot.countOfType('s');

  console.log(JSON.stringify({
    clientNetId,
    botId: bot.id,
    clientSeesBot: clientState.seesBot,
    botSeesClient,
    clientState,
    botSPacketsReceived: botSCount,
    botDistinctSenders: bot.sendersSeenFor('s'),
    clientErrors: errors.slice(0, 5)
  }, null, 2));

  bot.close();
  await browser.close();
})();
