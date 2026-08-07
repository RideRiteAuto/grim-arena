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

    // Some checks are about the NAME the voice was asked for (voice stubbed),
    // and some are about what the voice then DID with it (voice real). Keep
    // both available rather than ordering the file around which is installed.
    const withRealVoice = fn => {
      const stub = G.sfxVoice_;
      G.sfxVoice_ = realVoice;
      try { return fn(); } finally { G.sfxVoice_ = stub; }
    };
    // What sample a name actually reaches, and at what gain.
    const gainOfName = (n, t) => withRealVoice(() => {
      let seen = null;
      const realPlay = G._samples.play;
      G._samples.play = function (nm, o) { seen = { nm: nm, g: (o || {}).gain, when: (o || {}).when }; return null; };
      try { G.sfx(n, t); } finally { G._samples.play = realPlay; }
      return seen;
    });

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

    // ---- B. the tool swing, twice over ------------------------------------
    // Patch 44/55.283: "when you're moving an axe or a pickaxe through the
    //  air, it doesn't really make any sound" - the metallic-ring bug was
    //  fixed by going silent on a miss.
    // Patch 67.452: Kevin's next round asked for the opposite of silence -
    //  a tool swung at nothing should whoosh exactly like a sword does, not
    //  say nothing at all. So this now asserts the CURRENT contract: a tool
    //  swing asks for 'swing', same logical name as a sword's light attack.
    G.me.stam = 999; G.me.mana = 999; G.me.combo = 0; G.me.yaw = 0;
    const chop = drive(() => G.startMove(G.me, 'chop'));
    note.chopSwing = names(chop);
    if (names(chop)[0] !== 'swing') fail.push('B: a tool swing asked for ' + names(chop).join(',') + ', not swing');

    // ---- C. sword swings reach the RECORDED samples, not the synth --------
    const light = drive(() => G.startMove(G.me, 'light'));
    const heavy = drive(() => G.startMove(G.me, 'heavy'));
    note.swordSwing = { light: names(light), heavy: names(heavy) };
    if (names(light)[0] !== 'swing') fail.push('C: a light attack asked for ' + names(light).join(',') + ', not swing');
    if (names(heavy)[0] !== 'heavy') fail.push('C: a heavy attack asked for ' + names(heavy).join(',') + ', not heavy');
    if (!G._samples.has('combat-swing')) fail.push('C: swing has no sample to reach');

    // ---- C2. patch 67.452: 'swing' and 'heavy' reach the SAME sample ------
    // Kevin: two different takes played across one 3-swing combo and only the
    // heavy finisher's take ("combat-heavy") was the whoosh he wanted. Fixed
    // by rerouting 'swing' onto 'combat-heavy' too, so every miss - light,
    // heavy, or a tool - sounds like that one good take. Assert the ACTUAL
    // resolved sample, not just the logical name, since B and C above only
    // prove what was ASKED for for and CSAMP could still point it anywhere.
    const swingSample = gainOfName('swing');
    const heavySample = gainOfName('heavy');
    note.airSwingSample = { swing: swingSample && swingSample.nm, heavy: heavySample && heavySample.nm };
    if (!swingSample || swingSample.nm !== 'combat-heavy') {
      fail.push('C2: swing resolved to ' + (swingSample && swingSample.nm) + ', not combat-heavy');
    }
    if (!heavySample || heavySample.nm !== 'combat-heavy') {
      fail.push('C2: heavy resolved to ' + (heavySample && heavySample.nm) + ', not combat-heavy');
    }

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

    // ---- G2. chain lightning -----------------------------------------------
    // It was the last spell still resolving as a sword: every link went through
    // applyDamage as a 'crit', and a second explicit sfx('crit') sat on top.
    const storm = names(drive(() => G.startMove(G.me, 'storm')));
    note.stormCast = storm;
    if (storm[0] !== 'sp-storm-cast') fail.push('G2: casting storm asked for ' + storm.join(','));
    for (const n of storm) if (SWORD.test(n)) fail.push('G2: storm cast asked for the sword sound ' + n);

    // a chain link, which keeps kind 'crit' for the splat and flags opt.storm
    const link = hitAs('crit', { magic: true, style: 'MAGIC', storm: true });
    note.stormLink = link;
    landed(link, 'sp-storm-hit', 'a chain lightning link');
    for (const n of link) if (SWORD.test(n)) fail.push('G2: a storm link landed with the sword sound ' + n);
    // and a plain melee crit must NOT have been dragged along with it
    if (note.impacts.swordCrit.indexOf('sp-storm-hit') >= 0) fail.push('G2: a sword crit now sounds like lightning');

    // the three links must not stack on one instant, or the chain reads as one
    // loud crack instead of as a chain
    {
      const whens = [];
      withRealVoice(() => {
        const realPlay = G._samples.play;
        G._samples.play = function (nm, o) { if (nm === 'sp-storm-hit') whens.push((o || {}).when); return null; };
        try { for (let k = 0; k < 3; k++) G.sfx('sp-storm-hit', near); } finally { G._samples.play = realPlay; }
      });
      note.stormStagger = whens.map(w => (w === undefined ? null : +w.toFixed(3)));
      const spread = (whens[2] || 0) - (whens[0] || 0);
      note.stormSpreadMs = Math.round(spread * 1000);
      if (!(spread > 0.05 && spread < 0.30)) {
        fail.push('G2: three chain links spread over ' + Math.round(spread * 1000) + ' ms');
      }
    }

    // ---- G3. an arrow meeting the world ------------------------------------
    // Kevin asked for the arrow sticking into a wooden wall. Before this there
    // was no hook at all: arrows only ever resolved against creatures.
    if (typeof G.shotSurface_ !== 'function') fail.push('G3: no shotSurface_');
    else {
      G.colliders = [{ x: 10, z: 0, r: 1.5 }, { x: 0, z: 10, hw: 2, hd: 0.5, mat: 'stone' }];
      const at = (x, y, z) => G.shotSurface_(new T.Vector3(x, y, z));
      note.surface = {
        insideCircle: !!at(10, 1, 0),
        insideBox: !!at(0, 1, 10),
        clearAir: !!at(30, 1, 30),
        overTheRoof: !!at(10, 9, 0),
        matReadBack: (at(0, 1, 10) || {}).mat || null
      };
      if (!note.surface.insideCircle) fail.push('G3: an arrow inside a round collider hit nothing');
      if (!note.surface.insideBox) fail.push('G3: an arrow inside a box collider hit nothing');
      if (note.surface.clearAir) fail.push('G3: an arrow in open air hit something');
      // the height gate: collider records are infinite columns in XZ, so
      // without it a shot lobbed over a building buries itself in thin air
      if (note.surface.overTheRoof) fail.push('G3: an arrow 9m up struck a ground-level collider');
      if (note.surface.matReadBack !== 'stone') fail.push('G3: collider mat did not read back');

      // and the sounds those resolve to
      const wood = gainOfName('arrow-wood', near);
      const dirt = gainOfName('arrow-dirt', near);
      note.surfaceSounds = { wood: wood, dirt: dirt };
      if (!wood || wood.nm !== 'arrow-wood') fail.push('G3: arrow-wood did not reach its sample');
      if (!dirt || dirt.nm !== 'arrow-dirt') fail.push('G3: arrow-dirt did not reach its sample');
      if (wood && dirt && !(dirt.g < wood.g)) fail.push('G3: soil is not quieter than a wooden wall');
    }

    // ---- G3b. the arrow really stops, sticks, and stops being dangerous ----
    // shotSurface_ answering correctly is not the same as an arrow behaving.
    // This is the gameplay half of the change and it needs its own assertion.
    withRealVoice(() => {
      G.colliders = [{ x: 10, z: 0, r: 1.5 }];
      G.projectiles = [];
      G.worldOn = false;                       // flat ground, so groundY is 0
      const mesh = new T.Object3D();
      mesh.position.set(0, 1, 0);
      G.scene.add(mesh);
      G.projectiles.push({ mesh: mesh, vel: new T.Vector3(40, 0, 0), owner: G.me,
                           dmg: 20, kind: 'arrow', life: 3, style: 'RANGED' });
      let steps = 0;
      while (G.projectiles.length && G.projectiles[0] && !G.projectiles[0].stuck && steps < 40) {
        G.stepProjectiles(1 / 60); steps++;
      }
      const p = G.projectiles[0];
      note.arrowStick = p ? {
        stuck: !!p.stuck,
        x: +p.mesh.position.x.toFixed(2),
        speed: +p.vel.length().toFixed(3),
        steps: steps
      } : { gone: true };
      if (!p || !p.stuck) { fail.push('G3b: the arrow flew through the wall'); return; }
      if (p.vel.length() > 0.001) fail.push('G3b: a stuck arrow is still moving');
      if (p.mesh.position.x > 10.6) fail.push('G3b: the arrow buried itself past the surface, x=' + p.mesh.position.x.toFixed(2));

      // a stuck arrow must not keep hurting whatever walks past it
      const victim = { pos: new T.Vector3(p.mesh.position.x, 0, 0), hp: 100, max: 100,
                       iframe: 0, frozen: 0, freezeCd: 0, stagger: 0 };
      G.npcs = [victim];
      for (let k = 0; k < 20; k++) G.stepProjectiles(1 / 60);
      note.stuckArrowDamage = 100 - victim.hp;
      if (victim.hp !== 100) fail.push('G3b: a stuck arrow dealt ' + (100 - victim.hp) + ' damage to a passer-by');
      G.npcs = [];
      G.projectiles = [];
    });

    // ---- G4. the two tracks' sfx() signatures cannot collide ---------------
    // 55.283 made arg 2 the source entity; the gathering track shipped
    // sfx('oredeplete', 0.22) using it as a delay. Both must survive.
    {
      const seen = withRealVoice(() => {
        let got = null;
        const realPlay = G._samples.play;
        G._samples.play = function (nm, o) { got = { nm: nm, when: (o || {}).when }; return null; };
        try { G.sfx('oredeplete', null, 0.22); } finally { G._samples.play = realPlay; }
        return got;
      });
      note.delayForm = seen;
      if (!seen) fail.push('G4: the delayed gathering form played nothing');
      else if (!(seen.when > 0)) fail.push('G4: the explicit delay was dropped');
      // a bare number in the entity slot must not be read as a place
      if (G.sfxAtten_(0.22) !== 1) fail.push('G4: a number was treated as a source position');
    }

    // ---- G. the samples the routing now depends on actually exist ---------
    const need = ['arrow-flesh', 'arrow-plate', 'sp-fire-cast', 'sp-fire-hit',
                  'sp-frost-cast', 'sp-frost-hit', 'sp-heal-cast', 'sp-heal-apply',
                  'sp-storm-cast', 'sp-storm-hit', 'arrow-wood', 'arrow-dirt',
                  'foot-wood-a', 'foot-wood-b', 'foot-wood-c',
                  'foot-dirt-a', 'foot-dirt-b', 'foot-dirt-c',
                  'foot-sand-a', 'foot-sand-b', 'foot-sand-c',
                  'foot-metal-a', 'foot-metal-b', 'foot-metal-c'];
    const missing = need.filter(n => !G._samples.has(n));
    if (missing.length) fail.push('G: routed to samples that did not decode: ' + missing.join(','));

    // ---- H. arrows land QUIETLY -------------------------------------------
    // Kevin's other arrow note was level, not character: too loud even up
    // close. Read the gain the voice actually applied rather than trusting the
    // constant in the source.
    G.sfxVoice_ = realVoice;
    const ga = gainOfName('arrow-hit', near);
    const gh = gainOfName('hit', near);
    note.gains = { arrow: ga, sword: gh };
    if (!ga || !/^arrow-/.test(ga.nm)) fail.push('H: arrow-hit did not reach an arrow sample: ' + JSON.stringify(ga));
    if (ga && gh && !(ga.g < gh.g)) fail.push('H: an arrow lands at ' + ga.g + ', no quieter than the sword at ' + gh.g);

    // ---- I. footsteps (patch 68) -------------------------------------------
    // footTick_ reads e.phase/e.moveAmt/e._shufA/e._shufPh directly rather
    // than driving the full rig through animate(), so it can be exercised
    // here with a minimal fixture instead of a fully-built character mesh -
    // see the patch's own comment on why that split pays off for testing.
    {
      const mkFoot = over => Object.assign({
        parts: { kneeR: {} }, phase: 0, moveAmt: 0, pos: new T.Vector3(0, 0, 0),
        yaw: 0, vyaw: 0, swimF: false, ridingF: false, wraith: false, state: 'move'
      }, over || {});
      const realPlay = G._samples.play;
      const drivePhase = (e, n, inBoat) => {
        for (let i = 0; i < n; i++) { e.phase += 0.2; G.footTick_(e, 0.033, !!inBoat); }
      };

      // material resolution: zone default buckets, and a tagged collider
      // overriding the zone default.
      const origZoneAt = G.zoneAt.bind(G);
      G.zoneAt = () => 'IRONSPIRE';
      note.footMatMetal = G.footMat_(mkFoot());
      G.zoneAt = () => 'SUNCOAST';
      note.footMatSand = G.footMat_(mkFoot());
      G.zoneAt = () => 'HEARTLANDS';
      note.footMatDirt = G.footMat_(mkFoot());
      const savedColliders = G.colliders;
      G.colliders = [{ x: 0, z: 0, hw: 5, hd: 5, mat: 'wood' }];
      note.footMatOverride = G.footMat_(mkFoot());
      G.colliders = savedColliders;
      G.zoneAt = origZoneAt;
      if (note.footMatMetal !== 'metal') fail.push('I: IRONSPIRE did not resolve to metal, got ' + note.footMatMetal);
      if (note.footMatSand !== 'sand') fail.push('I: SUNCOAST did not resolve to sand, got ' + note.footMatSand);
      if (note.footMatDirt !== 'dirt') fail.push('I: a plain zone did not default to dirt, got ' + note.footMatDirt);
      if (note.footMatOverride !== 'wood') fail.push('I: a mat-tagged collider did not override the zone default, got ' + note.footMatOverride);

      // walking triggers repeated footsteps, always the right material pool
      G.zoneAt = () => 'HEARTLANDS';
      let plays = [];
      G._samples.play = (nm, o) => { plays.push({ nm: nm, g: (o || {}).gain, d: (o || {}).detune }); return null; };
      const walker = mkFoot({ moveAmt: 1.0 });
      drivePhase(walker, 80);
      note.footWalkPlays = plays.length;
      const badName = plays.find(p => !/^foot-dirt-[abc]$/.test(p.nm));
      if (plays.length < 3) fail.push('I: walking did not trigger repeated footsteps: ' + plays.length);
      if (badName) fail.push('I: a footstep asked for the wrong sample: ' + JSON.stringify(badName));
      const walkGain = plays.length ? plays[plays.length - 1].g : null;

      // running reads louder (and a shade lower) than walking, same call site
      plays = [];
      const runner = mkFoot({ moveAmt: 1.5 });
      drivePhase(runner, 80);
      note.footRunPlays = plays.length;
      const runGain = plays.length ? plays[0].g : null;
      if (!(runGain !== null && walkGain !== null && runGain > walkGain))
        fail.push('I: a run did not read louder than a walk: run=' + runGain + ' walk=' + walkGain);

      // turning in place (shuffle) plays footsteps too, even at moveAmt 0
      plays = [];
      const shuffler = mkFoot({ moveAmt: 0 });
      shuffler._shufA = 0.5;
      for (let i = 0; i < 30; i++) { shuffler._shufPh = (shuffler._shufPh || 0) + 0.15; G.footTick_(shuffler, 0.033, false); }
      note.footShufflePlays = plays.length;
      if (plays.length < 2) fail.push('I: turning in place did not trigger shuffle footsteps: ' + plays.length);

      // gated off while swimming, riding, boating, or for a wraith
      plays = [];
      for (const flag of ['swimF', 'ridingF', 'wraith']) {
        const gated = mkFoot({ moveAmt: 1.0 });
        gated[flag] = true;
        drivePhase(gated, 80);
      }
      const boater = mkFoot({ moveAmt: 1.0 });
      drivePhase(boater, 80, true);
      note.footGatedPlays = plays.length;
      if (plays.length) fail.push('I: a swimming, riding, boating or wraith entity still played footsteps: ' + plays.length);

      // distance: a footstep 120m out is below the same attenuation floor
      // every other sound in the world uses
      plays = [];
      const farWalker = mkFoot({ moveAmt: 1.0, pos: far.pos.clone() });
      drivePhase(farWalker, 80);
      note.footFarPlays = plays.length;
      if (plays.length) fail.push('I: a footstep 120m away should have been below the attenuation floor, played ' + plays.length);

      G._samples.play = realPlay;
      G.zoneAt = origZoneAt;
    }

    return { fail: fail, note: note };
  });

  res.pageErrors = errs;
  if (errs.length) res.fail.push('page errors: ' + errs.slice(0, 3).join(' | '));
  console.log(JSON.stringify(res, null, 1));
  await browser.close();
  process.exit(res.fail.length ? 1 : 0);
})();
