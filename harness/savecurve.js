// Proves a login cannot eat your skill XP.
//
// The bug this guards: charSave() never wrote skillCurve, applySaveBlob() read
// it as undefined, decided the save predated the new XP curve, and re-ran
// migrateSkillCurve. The migration mutates this.skills for real but stamped
// itself onto a throwaway object, so it ran again on the next login, and the
// next. Woodcutting 11 became 7, then 5, then 4. Every skill at once.
//
// The test drives the REAL charSave / applySaveBlob pair through ten
// save-and-log-back-in cycles and asserts nothing moved at all, and that a
// v:1 row (every row in the live database is one) loads untouched.
// Verified to FAIL on the bundle before this fix (WOODCUTTING 11 -> 7 on the
// very first cycle), so it is a real regression test and not a tautology.
const { chromium } = require('playwright');

const CYCLES = 10;

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--no-sandbox']
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await page.goto('http://127.0.0.1:8123/index.html', { waitUntil: 'load' });
  await page.waitForFunction(() => window.__grim && window.__grim.charSave, null, { timeout: 60000 });

  const out = await page.evaluate(cycles => {
    const g = window.__grim;
    const KEYS = g.SKILL_KEYS();

    // Sit a character mid-way through some levels on the CURRENT curve, the
    // way a real player who has been gathering would be.
    const want = { WOODCUTTING: 11, MINING: 8, FORAGING: 5, MELEE: 20, HITPOINTS: 15 };
    g.skills = {};
    for (const k of KEYS) g.skills[k] = 0;
    for (const k in want) {
      const a = g.xpFor(want[k]), b = g.xpFor(want[k] + 1);
      g.skills[k] = Math.floor(a + (b - a) * 0.4);
    }
    const lvls = () => { const o = {}; for (const k in want) o[k] = g.lvl(g.skills[k]); return o; };

    const start = lvls();
    const startXp = Object.assign({}, g.skills);
    const trail = [start];

    // One cycle = save the character, then log back in on that save. This is
    // exactly what doLogout -> reload -> doLoginClick does, minus the network.
    for (let i = 0; i < cycles; i++) {
      const blob = JSON.parse(JSON.stringify(g.charSave()));
      g.applySaveBlob(blob);
      trail.push(lvls());
    }

    // A v:1 row must NOT convert. Every row in the live database is v:1 and
    // has already been through the migration many times, because the old code
    // ran it on every login. Converting one more time would cost a level.
    g.skills = Object.assign({}, startXp);
    const legacy = JSON.parse(JSON.stringify(g.charSave()));
    legacy.v = 1; delete legacy.skillCurve; delete legacy.skillXpV1;
    g.applySaveBlob(legacy);
    const afterLegacy1 = lvls();
    const reSaved = JSON.parse(JSON.stringify(g.charSave()));
    g.applySaveBlob(reSaved);
    const afterLegacy2 = lvls();

    return { start, trail, blobV: g.charSave().v, blobStamp: g.charSave().skillCurve,
             hasBackup: !!g.charSave().skillXpV1, afterLegacy1, afterLegacy2 };
  }, CYCLES);

  const fails = [];
  const same = (a, b) => Object.keys(a).every(k => a[k] === b[k]);

  // 1. Ten logins, nothing moves.
  out.trail.forEach((l, i) => {
    if (!same(out.start, l)) fails.push(`cycle ${i}: levels changed ${JSON.stringify(out.start)} -> ${JSON.stringify(l)}`);
  });

  // 2. The blob says what it is, so the next reader cannot get it wrong.
  if (out.blobV !== 2) fails.push(`blob version is ${out.blobV}, expected 2`);
  if (out.blobStamp !== 2) fails.push(`blob skillCurve is ${out.blobStamp}, expected 2`);

  // 3. A v:1 row loads untouched. This is the assertion that stops somebody
  //    "restoring" the migration and quietly taking a level off everyone.
  if (!same(out.start, out.afterLegacy1)) {
    fails.push(`a v:1 save was migrated: ${JSON.stringify(out.start)} -> ${JSON.stringify(out.afterLegacy1)}`);
  }
  if (!same(out.afterLegacy1, out.afterLegacy2)) {
    fails.push(`levels moved on the second load: ${JSON.stringify(out.afterLegacy1)} -> ${JSON.stringify(out.afterLegacy2)}`);
  }

  console.log(JSON.stringify({
    startLevels: out.start,
    levelsAfterEachLogin: out.trail.map(t => t.WOODCUTTING),
    blobVersion: out.blobV,
    legacySaveMigratedOnce: { after1: out.afterLegacy1, after2: out.afterLegacy2 },
    backupPersisted: out.hasBackup,
    consoleErrors: errs.filter(e => !/404/.test(e)),
    failures: fails,
    result: fails.length ? 'FAIL' : 'PASS'
  }, null, 2));

  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
