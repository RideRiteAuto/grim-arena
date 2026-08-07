// Prove the sounds go where Kevin said they should go.
//
// Every complaint in his review was a ROUTING bug, not a bad sample: an axe
// rang like a sword because 'chop' fell through to 'swing', a fireball landed
// with the sword crit because 'fire' resolved to 'crit', an arrow across the
// map was at full volume because nothing attenuated. None of that is provable
// by listening to a file, and none of it is caught by a boot test. So this
// intercepts sfxVoice_ (the real one, past the distance gate), drives the real
// call sites, and asserts on the NAME that came out and the gain it came out
// at.
//
//   node harness/serve.js & node harness/sfxroute.js
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
  // Wait for THREE to be attached, not just for the game object. The two do
  // not land together and the gap moved when the editor track shipped, which
  // failed this whole file on `G.T` being undefined.
  await page.waitForFunction(() => !!(window.__grim && window.__grim.T),
    { timeout: 90000 });

  const res = await page.evaluate(async () => {
    const G = window.__grim;
    const fail = [];
    const note = {};

    G.audioInit();
    if (!G._samples) return { fail: ['no sample player'] };
    await G._samples.load;
    if (G.raf) { cancelAnimationFrame(G.raf); G.raf = null; }
    G.started = true;

    // Record what the voice was ASKED for, and what attenuation was in force
    // when it was asked. Both matter: the right sample at the wrong level is
    // still the arrow complaint.
    let log = [];
    const realVoice = G.sfxVoice_.bind(G);
    G.sfxVoice_ = function (n, t) { log.push({ n: n, att: this._att }); };
    const drive = fn => { log = []; try { fn(); } catch (e) { log.push({ n: 'THREW:' + e.message }); } return log.slice(); };
    const names = l => l.map(x => x.n);

    const T = G.T;
    G.me = G.me || {};
    G.me.pos = new T.Vector3(0, 0, 0);
    const near = { pos: new T.Vector3(3, 0, 0), hp: 100, max: 100 };
    const far = { pos: new T.Vector3(120, 0, 0), hp: 100, max: 100 };

    // ---- A. distance ------------------------------------------------------
    // The curve, at the boundaries that matter rather than at arbitrary points.
    note.att = {
      self: +G.sfxAtten_(G.me).toFixed(3),
      noEntity: +G.sfxAtten_(null).toFixed(3),
      m3: +G.sfxAtten_(near).toFixed(3),
      m20: +G.sfxAtten_({ pos: new T.Vector3(20, 0, 0) }).toFixed(3),
      m40: +G.sfxAtten_({ pos: new T.Vector3(40, 0, 0) }).toFixed(3),
      m120: +G.sfxAtten_(far).toFixed(3)
    };
    if (note.att.noEntity !== 1) fail.push('A: a sound with no source was attenuated');
    if (note.att.self !== 1) fail.push('A: the player\'s own sound was attenuated');
    if (note.att.m3 !== 1) fail.push('A: a sound 3m away was attenuated');
    if (!(note.att.m20 < 0.6 && note.att.m20 > 0.1)) fail.push('A: 20m attenuation out of range: ' + note.att.m20);
    if (!(note.att.m40 < note.att.m20)) fail.push('A: attenuation is not monotonic');
    if (note.att.m120 !== 0) fail.push('A: a sound 120m away was still audible');

    // and the gate itself: the far sound must never reach the voice at all
    if (drive(() => G.sfx('hit', far)).length) fail.push('A: a sound across the map still played');
    if (!drive(() => G.sfx('hit', near)).length) fail.push('A: a sound 3m away did not play');

    // the attenuation must not leak into the next call
    G.sfx('hit', { pos: new T.Vector3(25, 0, 0) });
    const dry = drive(() => G.sfx('hit', null));
    if (dry.length && dry[0].att !== 1) fail.push('A: attenuation leaked, next dry sound played at ' + dry[0].att);

    // ---- B. the metallic swoosh on a gathering swing ----------------------
    // "when you're moving an axe or a pickaxe through the air, it doesn't
    //  really make any sound"
    G.me.stam = 999; G.me.mana = 999; G.me.combo = 0; G.me.yaw = 0;
    const chop = drive(() => G.startMove(G.me, 'chop'));
    note.chopSwing = names(chop);
    if (chop.length) fail.push('B: swinging a tool still makes a sound: ' + names(chop).join(','));

    // ---- C. sword swings reach the RECORDED samples, not the synth --------
    const light = drive(() => G.startMove(G.me, 'light'));
    const heavy = drive(() => G.startMove(G.me, 'heavy'));
    note.swordSwing = { light: names(light), heavy: names(heavy) };
    if (names(light)[0] !== 'swing') fail.push('C: a light attack asked for ' + names(light).join(',') + ', not swing');
    if (names(heavy)[0] !== 'heavy') fail.push('C: a heavy attack asked for ' + names(heavy).join(',') + ', not heavy');
    if (!G._samples.has('combat-swing')) fail.push('C: swing has no sample to reach');

    // ---- D. no spell may ask for a sword sound ----------------------------
    // "some of the sounds for magic actually still sound like sword swings
    //  and sword hits"
    const SWORD = /^(swing|heavy|slash|crit|hit|parry|block)$/;
    const spellMoves = ['frost', 'storm', 'heal', 'snare'];
    note.spellCasts = {};
    for (const mv of spellMoves) {
      const got = names(drive(() => G.startMove(G.me, mv)));
      note.spellCasts[mv] = got;
      for (const n of got) if (SWORD.test(n)) fail.push('D: casting ' + mv + ' asked for the sword sound ' + n);
    }
    // heal specifically must reach its own sample
    if (note.spellCasts.heal[0] !== 'sp-heal-cast') fail.push('D: heal cast asked for ' + note.spellCasts.heal.join(','));

    // the projectile leaving the hand
    G.element = 'fire';
    const fc = names(drive(() => G.fireFrost(G.me)));
    G.element = 'water';
    const wc = names(drive(() => G.fireFrost(G.me)));
    note.projCast = { fire: fc, frost: wc };
    if (fc[0] !== 'sp-fire-cast') fail.push('D: casting fire asked for ' + fc.join(','));
    if (wc[0] !== 'sp-frost-cast') fail.push('D: casting frost asked for ' + wc.join(','));

    // and healing must stop playing the item pickup chime
    G.me.hp = 10; G.me.max = 200; G.me.mana = 999; G.quickHealCd = 0;
    G.roundOver = false; G.boating = false; G.me.swimF = 0;
    const qh = names(drive(() => G.tryCastQuickHeal()));
    note.quickHeal = qh;
    if (qh.indexOf('pickup') >= 0) fail.push('D: healing still plays the item pickup chime');
    if (qh[0] !== 'sp-heal-apply') fail.push('D: quick heal asked for ' + qh.join(','));

    // ---- E. impacts ------------------------------------------------------
    // Every kind that reaches the funnel, checked against what it must NOT be.
    G.warmup = 0; G.roundOver = false;
    // The impact name is asserted by MEMBERSHIP, not by position. Driving
    // applyDamage directly against a stubbed world can also trip the round
    // bookkeeping and emit a 'win' alongside the impact, which is the harness
    // showing through and not a routing bug. What matters is that the right
    // impact is in there and no sword sound is.
    const hitAs = (kind, opt) => {
      G.roundOver = false; G.warmup = 0;
      const t = { pos: new T.Vector3(3, 0, 0), hp: 500, max: 500, iframe: 0,
                  frozen: 0, freezeCd: 0, stagger: 0, block: 0 };
      return names(drive(() => G.applyDamage(G.me, t, 10, kind,
        new T.Vector3(3, 0, 0), opt || {})));
    };
    const landed = (got, want, what) => {
      if (got.indexOf(want) < 0) fail.push('E: ' + what + ' landed as ' + got.join(',') + ', wanted ' + want);
    };
    note.impacts = {
      fire: hitAs('fire', { magic: true }),
      frost: hitAs('frost', { magic: true }),
      arrow: hitAs('arrow', { style: 'RANGED' }),
      arrowCrit: hitAs('crit', { style: 'RANGED' }),
      sword: hitAs('hit', {}),
      swordCrit: hitAs('crit', {})
    };
    landed(note.impacts.fire, 'sp-fire-hit', 'a fireball');
    landed(note.impacts.frost, 'sp-frost-hit', 'frost');
    landed(note.impacts.arrow, 'arrow-hit', 'an arrow');
    landed(note.impacts.arrowCrit, 'arrow-hit', 'a critical arrow');
    landed(note.impacts.sword, 'hit', 'a sword hit');
    landed(note.impacts.swordCrit, 'crit', 'a sword crit');
    // and the whole point: nothing magic or ranged may carry a melee sound
    for (const k of ['fire', 'frost', 'arrow', 'arrowCrit']) {
      for (const n of note.impacts[k]) {
        if (SWORD.test(n)) fail.push('E: ' + k + ' landed with the sword sound ' + n);
      }
    }

    // ---- F. the hit marker -----------------------------------------------
    // "maybe I'll just hear some sort of a hit marker just to register that
    //  you hit" — but only for blows YOU landed, never for a fight across the
    //  map that has nothing to do with you.
    let marks = 0;
    const realMark = G.hitMark_.bind(G);
    G.hitMark_ = function () { marks++; };
    const farT = () => ({ pos: new T.Vector3(120, 0, 0), hp: 500, max: 500, iframe: 0,
                          frozen: 0, freezeCd: 0, stagger: 0, block: 0 });
    marks = 0;
    G.applyDamage(G.me, farT(), 10, 'arrow', new T.Vector3(120, 0, 0), { style: 'RANGED' });
    note.markMine = marks;
    if (marks !== 1) fail.push('F: your own distant hit did not register (' + marks + ' marks)');
    marks = 0;
    G.applyDamage({ pos: new T.Vector3(118, 0, 0) }, farT(), 10, 'hit', new T.Vector3(120, 0, 0), {});
    note.markTheirs = marks;
    if (marks !== 0) fail.push('F: a fight across the map marked as if you were in it');
    marks = 0;
    G.applyDamage(G.me, { pos: new T.Vector3(3, 0, 0), hp: 500, max: 500, iframe: 0,
                          frozen: 0, freezeCd: 0, stagger: 0, block: 0 },
                  10, 'hit', new T.Vector3(3, 0, 0), {});
    note.markNear = marks;
    if (marks !== 0) fail.push('F: a hit you could hear also fired the marker');
    G.hitMark_ = realMark;

    // ---- G. the samples the routing now depends on actually exist ---------
    const need = ['arrow-flesh', 'arrow-plate', 'sp-fire-cast', 'sp-fire-hit',
                  'sp-frost-cast', 'sp-frost-hit', 'sp-heal-cast', 'sp-heal-apply'];
    const missing = need.filter(n => !G._samples.has(n));
    if (missing.length) fail.push('G: routed to samples that did not decode: ' + missing.join(','));

    // ---- H. arrows land QUIETLY -------------------------------------------
    // Kevin's other arrow note was level, not character: too loud even up
    // close. Read the gain the voice actually applied rather than trusting the
    // constant in the source.
    G.sfxVoice_ = realVoice;
    const gainOf = (n, t) => {
      const b = G._samples.play(n, { gain: 0 });
      if (b) try { b.src.stop(); } catch (e) {}
      let seen = null;
      const realPlay = G._samples.play;
      G._samples.play = function (nm, o) { seen = { nm: nm, g: (o || {}).gain }; return null; };
      try { G.sfx(n, t); } finally { G._samples.play = realPlay; }
      return seen;
    };
    const ga = gainOf('arrow-hit', near);
    const gh = gainOf('hit', near);
    note.gains = { arrow: ga, sword: gh };
    if (!ga || !/^arrow-/.test(ga.nm)) fail.push('H: arrow-hit did not reach an arrow sample: ' + JSON.stringify(ga));
    if (ga && gh && !(ga.g < gh.g)) fail.push('H: an arrow lands at ' + ga.g + ', no quieter than the sword at ' + gh.g);

    return { fail: fail, note: note };
  });

  res.pageErrors = errs;
  if (errs.length) res.fail.push('page errors: ' + errs.slice(0, 3).join(' | '));
  console.log(JSON.stringify(res, null, 1));
  await browser.close();
  process.exit(res.fail.length ? 1 : 0);
})();
