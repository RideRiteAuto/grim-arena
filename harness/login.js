// Shared login helper for every harness test that needs to get past the
// title screen into gameplay. Guest play was removed (patch v17.1) -
// accounts are mandatory now, so every test authenticates as a fixed test
// account instead. First run creates it ("NEW NAME + PASSWORD CREATES A
// CHARACTER"); every run after that logs into the same one.
//
// See claude/MOB-SYNC-JITTER-PLAN.md "Blocking issue" for why this exists
// and claude/HARNESS-GOTCHAS.md for other harness traps.
const USERNAME = 'harnessbot';
const PASSWORD = 'harnessbot1';

async function enterGame(page, opts) {
  opts = opts || {};
  const timeout = opts.timeout || 30000;

  // The account box lives right on the title overlay - no separate click
  // to get past a splash screen first.
  await page.waitForSelector('input[placeholder="USERNAME"]', { timeout });
  const u = await page.$('input[placeholder="USERNAME"]');
  const p = await page.$('input[placeholder="PASSWORD"]');
  await u.fill(USERNAME);
  await p.fill(PASSWORD);

  const loginBtn = await page.getByText('LOGIN & PLAY', { exact: true });
  await loginBtn.click();

  // doLoginClick() calls play() itself on success ("straight into the
  // world") - no further click needed. Wait for the world to actually be
  // up rather than any fixed delay.
  await page.waitForFunction(
    () => window.__grim && window.__grim.started && window.__grim.me,
    null,
    { timeout }
  );
}

module.exports = { enterGame, USERNAME, PASSWORD };
