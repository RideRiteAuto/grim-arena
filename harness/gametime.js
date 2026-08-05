// Wait on GAME time, not wall time.
//
// This harness renders in software at roughly a tenth to a fifth of real speed,
// so a three second move needs twenty or thirty seconds of wall clock to finish.
// Every early test in this repo guessed at that multiplier, and one of them
// guessed wrong and sent me hunting a bug in a charge that was working fine: it
// simply had not finished winding up yet.
//
// So tests wait on the game's own clock. `worldT` advances with the simulation,
// so sleeping "three seconds of game time" means the same thing whether the page
// is running at 60fps or 6.
module.exports = {
  // Seconds of SIMULATION, however long that takes on the wall clock.
  async sleepGame(page, seconds, timeoutMs = 240000) {
    const t0 = await page.evaluate(() => (window.__grim && window.__grim.worldT) || 0);
    const start = Date.now();
    for (;;) {
      const now = await page.evaluate(() => (window.__grim && window.__grim.worldT) || 0);
      if (now - t0 >= seconds) return { gameSeconds: now - t0, wallMs: Date.now() - start };
      if (Date.now() - start > timeoutMs) {
        throw new Error('waited ' + Math.round((Date.now() - start) / 1000) + 's of wall clock for ' +
          seconds + 's of game time and only got ' + (now - t0).toFixed(1) +
          '. The page is probably not running.');
      }
      await page.waitForTimeout(150);
    }
  },
  // How much slower than real time this machine is rendering, for the record.
  async speedRatio(page, sampleMs = 4000) {
    const a = await page.evaluate(() => (window.__grim && window.__grim.worldT) || 0);
    await page.waitForTimeout(sampleMs);
    const b = await page.evaluate(() => (window.__grim && window.__grim.worldT) || 0);
    return +((b - a) / (sampleMs / 1000)).toFixed(3);
  }
};
