"""Patch 77.612: legacy sound sweep, 19 names off the raw tone()/hiss() synth
switch and onto real ElevenLabs audio.

Kevin's ask: work through claude/LEGACY-SOUND-AUDIT.md, generate the sounds,
wire them in. Explicitly OUT OF SCOPE per his instruction: the old arena/duel
round system (tick-as-countdown, horn-as-FIGHT-call, win/lose-as-round-
outcome). Read stepRound() itself to confirm rather than trust anyone's
memory: "if (this.worldOn && this.mode === 'ai') return; // the open world
has no rounds" -- that whole system (warmup, readyUp, startDelay, ARENA_R,
the wins[] pip scoreboard) is switched off the instant open-world/coop mode
loads (this.warmup = false at the mode = 'ai' transition), so it is dead in
every real play session today. Confirmed in code, not just recalled: left
completely untouched here, including the 'lose' name (duel-loss only, no
other caller) and the readyUp() 'horn' call (duel-only).

Two names, 'win' and 'switch', got a blanket sample upgrade rather than a
per-call-site rewrite: 'win' has ~20 call sites (every quest-complete banner,
skill level-ups, the donkey-acquired banner, plus the dead duel-round-win),
and 'switch' has ~20 more (every UI tab/loadout click). Editing 20 embedded
one-line call sites each for a synth-to-sample swap is all downside risk for
no behavioural difference over a central resolver upgrade -- every caller
still says sfx('win') or sfx('switch'), they just get real audio now instead
of a beep. Three 'win' call sites that clearly deserve their OWN distinct
sound (level-up, the CHAIN LIGHTNING LEARNED tome banner, the Argent Warden
phase transition) are individually overridden below to bypass the blanket
mapping.

Everything else (tick's aggro use, bray, draw, arrow, freeze, the MSFX
dispatch table entries for slash/cast/rapid/volley, the boss leap/charge
telegraph ternary, the 'slam' impact) is a precise single-call-site rewrite,
anchored on unique surrounding text and assert-checked.
"""
import io, os, re, base64

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')
SFXDIR = '/tmp/sfx74/final'

NEW_KEYS = [
    'creature-notice', 'goblin-shriek', 'npc-taunt-warcry', 'bow-draw',
    'bow-release', 'creature-windup-charge', 'player-dodge', 'player-jump',
    'spell-frost-freeze', 'creature-claw-swipe', 'spell-snare-cast',
    'boss-leap-telegraph', 'level-up', 'quest-complete', 'spell-learned',
    'boss-phase-shift', 'heavy-impact-crash', 'ui-switch-click',
    'update-ready-chime',
]

# ---------------------------------------------------------------- payloads

def b64_block(key, b64):
    CHUNK = 100
    chunks = [b64[i:i + CHUNK] for i in range(0, len(b64), CHUNK)]
    lines = ["  '%s':" % key, "      '%s'" % chunks[0]]
    lines += ["    + '%s'" % c for c in chunks[1:]]
    lines[-1] += ','
    return '\n'.join(lines)

payloads = {}
for key in NEW_KEYS:
    mp3_path = os.path.join(SFXDIR, key + '.mp3')
    raw = io.open(mp3_path, 'rb').read()
    assert raw[:3] == b'ID3' or raw[:2] == b'\xff\xfb', 'not an mp3: ' + key
    payloads[key] = base64.b64encode(raw).decode('ascii')

new_block = '\n'.join(b64_block(k, payloads[k]) for k in NEW_KEYS)

# ------------------------------------------------------- model-lab source

mod = io.open(MODULE, encoding='utf-8').read()
assert "'creature-notice':" not in mod, 'patch 77.612 already applied to model-lab'
mod_close = mod.index('\n};\n')
mod = mod[:mod_close] + '\n' + new_block + mod[mod_close:]
io.open(MODULE, 'w', encoding='utf-8').write(mod)
print('model-lab/sfx-samples.js: +%d keys' % len(NEW_KEYS))

# ------------------------------------------------------------- bundle src

s = io.open(SRC, encoding='utf-8').read()
assert "'creature-notice':" not in s, 'patch 77.612 already applied to bundle'

# 1. inject the 19 new sample keys into the bundle's SFX_SAMPLES object,
#    right before its closing brace (same one 71.601 et al. anchor on).
sfx_start = s.index('const SFX_SAMPLES = {')
sfx_close = s.index('\n    };', sfx_start)
s = s[:sfx_close] + '\n' + new_block + s[sfx_close:]

def repl(old, new, label, count=1):
    global s
    n = s.count(old)
    assert n == count, '%s: expected %d occurrence(s), found %d' % (label, count, n)
    s = s.replace(old, new, count)

# 2. creature aggro tick -> creature-notice. The OTHER 'tick' call site
#    (stepNpcChatter's proximity bubble ping) is untouched on purpose.
repl(
    "if (now - (e._aggroSfxAt || -99) > L.MIN_AGGRO_GAP) { e._aggroSfxAt = now; this.sfx('tick'); }",
    "if (now - (e._aggroSfxAt || -99) > L.MIN_AGGRO_GAP) { e._aggroSfxAt = now; this.sfx('creature-notice'); }",
    'aggro tick')

# 3. bray's three call sites split by who is making the noise.
repl(
    "this.npcSay(e, \"WHERE'S THE RIVET?!\", { gold: true, dur: 2800 });\n          this.sfx('bray');",
    "this.npcSay(e, \"WHERE'S THE RIVET?!\", { gold: true, dur: 2800 });\n          this.sfx('npc-taunt-warcry');",
    'Sailers taunt bray')
repl(
    "if (e.sig === 'GOBLIN SHRIEK') { this.sfx('bray'); }",
    "if (e.sig === 'GOBLIN SHRIEK') { this.sfx('goblin-shriek'); }",
    'goblin shriek bray (runSig telegraph)')
repl(
    "      // No damage at all. The cost of ignoring it is everything green\n"
    "      // within twenty five metres arriving.\n"
    "      this.sfx('bray');",
    "      // No damage at all. The cost of ignoring it is everything green\n"
    "      // within twenty five metres arriving.\n"
    "      this.sfx('goblin-shriek');",
    'goblin shriek bray (rally block)')

# 4. draw's four remaining jobs.
repl(
    "if (e.sig === 'GOBLIN SHRIEK') { this.sfx('goblin-shriek'); }\n    else { this.sfx('draw'); }",
    "if (e.sig === 'GOBLIN SHRIEK') { this.sfx('goblin-shriek'); }\n    else { this.sfx('creature-windup-charge'); }",
    'runSig non-goblin windup fallback')
repl(
    "e.specialCd = 9 + Math.random() * 4;\n    this.sfx('draw');\n  }\n  runCharge(e, me, dt) {",
    "e.specialCd = 9 + Math.random() * 4;\n    this.sfx('creature-windup-charge');\n  }\n  runCharge(e, me, dt) {",
    'startCharge windup')
repl(
    "this.sfx(m.state === 'leap' ? 'crit' : m.state === 'charge' ? 'draw' : 'bray');",
    "this.sfx(m.state === 'leap' ? 'boss-leap-telegraph' : m.state === 'charge' ? 'creature-windup-charge' : 'npc-taunt-warcry');",
    'boss telegraph ternary (fixes the leap-plays-crit bug)')
# Note: those are the ONLY two literal sfx('draw') call sites left in the
# game (startCharge above, runSig's fallback earlier) -- both monster
# windups, both now on creature-windup-charge. The player's own ranged
# windup never called sfx('draw') directly; it goes through MSFX's
# rapid/volley entries (see step 7 below), which is where bow-draw is
# actually wired in.

# 5. real arrow loose.
repl("    this.sfx('arrow');\n  }", "    this.sfx('bow-release');\n  }", 'bow release')

# 6. frost freeze, both call sites, blanket via central resolver below --
#    no per-site edit needed since both already mean the same thing.

# 7. MSFX dispatch table: claw/bite -> slash, snare -> cast, rapid/volley ->
#    draw. Point all three straight at real sample names.
repl(
    "claw: 'slash', bite: 'slash',\n      rapid: 'draw', volley: 'draw',\n"
    "      frost: null,              /* fireFrost() sounds the release, not the wind up */\n"
    "      snare: 'cast', storm: 'sp-storm-cast',",
    "claw: 'creature-claw-swipe', bite: 'creature-claw-swipe',\n"
    "      rapid: 'bow-draw', volley: 'bow-draw',\n"
    "      frost: null,              /* fireFrost() sounds the release, not the wind up */\n"
    "      snare: 'spell-snare-cast', storm: 'sp-storm-cast',",
    'MSFX table (claw/bite/rapid/volley/snare)')

# 8. player dodge-roll and jump (two branches inside tryJump share one call).
repl(
    "e.state = 'dodge'; e.st = 0; e.iframe = 0.35; e.dodgeCd = 0.9; e.stam -= 25; e.blocking = false;\n"
    "    this.sfx('dodge');",
    "e.state = 'dodge'; e.st = 0; e.iframe = 0.35; e.dodgeCd = 0.9; e.stam -= 25; e.blocking = false;\n"
    "    this.sfx('player-dodge');",
    'player dodge-roll')
repl(
    "e._air = true; e._vy = Math.sqrt(2 * V.GRAVITY * V.JUMP_H); this.sfx('dodge'); return; } "
    "if (e.jumping) return; e.jumping = true; e.jumpT = 0; this.sfx('dodge');",
    "e._air = true; e._vy = Math.sqrt(2 * V.GRAVITY * V.JUMP_H); this.sfx('player-jump'); return; } "
    "if (e.jumping) return; e.jumping = true; e.jumpT = 0; this.sfx('player-jump');",
    'player jump (both branches)')

# 9. monster leap windup (startLeap) was ALSO on 'dodge' -- give it the same
#    telegraph sample the ternary above now uses, so a leap sounds the same
#    however it gets triggered.
repl(
    "e.specialCd = 6 + Math.random() * 4;\n    this.sfx('dodge');\n  }\n\n  startCharge(e, target) {",
    "e.specialCd = 6 + Math.random() * 4;\n    this.sfx('boss-leap-telegraph');\n  }\n\n  startCharge(e, target) {",
    'startLeap windup')

# 10. the 'slam' special-move impact, the one 'break' call site worth fixing
#     (the smithing-pour-fail edge case is left on its old beep, not worth
#     the risk for how rarely it fires).
repl(
    "if (a.name === 'slam') { this.shake = Math.min(1, this.shake + 0.7); "
    "this.spark(e.pos.clone().add(new this.T.Vector3(0, 0.3, 0)), 0x8fef5a, 20); this.sfx('break'); }",
    "if (a.name === 'slam') { this.shake = Math.min(1, this.shake + 0.7); "
    "this.spark(e.pos.clone().add(new this.T.Vector3(0, 0.3, 0)), 0x8fef5a, 20); this.sfx('heavy-impact-crash'); }",
    'slam impact')

# 11. three 'win' call sites that get their own distinct sound rather than
#     the blanket quest-complete mapping below.
repl(
    "this.banner(skill + ' LEVEL ' + after, 'ONWARD', false, 2200); this.sfx('win');",
    "this.banner(skill + ' LEVEL ' + after, 'ONWARD', false, 2200); this.sfx('level-up');",
    'skill level-up banner')
repl(
    "this.banner('CHAIN LIGHTNING LEARNED', 'THE TOME CRUMBLES TO ASH. THE STORM IS YOURS FOREVER — HOLD Q WITH THE STAFF.', false, 5600);\n"
    "      this.sfx('win');",
    "this.banner('CHAIN LIGHTNING LEARNED', 'THE TOME CRUMBLES TO ASH. THE STORM IS YOURS FOREVER — HOLD Q WITH THE STAFF.', false, 5600);\n"
    "      this.sfx('spell-learned');",
    'tome-learned banner')
repl(
    "if (m.phase >= 1) this.spark(n.pos.clone().add(new this.T.Vector3(0, 5.4, 0)), 0xbfeaff, 22);\n"
    "        }\n"
    "        if (m.shout) this.npcSay(n, m.shout, { gold: true, dur: 2600 });\n"
    "        this.sfx('win');",
    "if (m.phase >= 1) this.spark(n.pos.clone().add(new this.T.Vector3(0, 5.4, 0)), 0xbfeaff, 22);\n"
    "        }\n"
    "        if (m.shout) this.npcSay(n, m.shout, { gold: true, dur: 2600 });\n"
    "        this.sfx('boss-phase-shift');",
    'boss phase transition')

# 12. the live (non-duel) 'horn' call: a deploy is ready while someone is
#     playing. The dead readyUp() 'horn' is left exactly as it was.
repl(
    "this._updDeadline = performance.now() + 150000;   // 30s + 2min of combat grace\n"
    "    this.buildUpdateBanner();\n"
    "    this.sfx('horn');",
    "this._updDeadline = performance.now() + 150000;   // 30s + 2min of combat grace\n"
    "    this.buildUpdateBanner();\n"
    "    this.sfx('update-ready-chime');",
    'update-ready banner')

# 13. central resolver additions in sfxVoice_, right next to the existing
#     CSAMP table -- same shape, so 'win' (~20 remaining callers: every
#     quest-complete banner, the donkey banner, and the dead duel-win path)
#     and 'switch' (~20 UI click callers) upgrade in one place instead of
#     twenty. 'freeze' (2 call sites, both mean the same thing) rides along.
old_csamp = (
    "    const CSAMP = {\n"
    "      swing: ['combat-heavy', 0.5, 60], heavy: ['combat-heavy', 0.5, 60],\n"
    "      block: ['combat-block', 0.7, 50], parry: ['combat-parry', 0.5, 40]\n"
    "    };\n"
    "    const cs = CSAMP[name];\n"
    "    if (cs && this._samples && this._samples.ready() && this._samples.has(cs[0])) {\n"
    "      this._samples.play(cs[0], { gain: cs[1], detune: (Math.random() * 2 - 1) * cs[2] });\n"
    "      return;\n"
    "    }\n"
    "    switch (name) {")
new_csamp = (
    "    const CSAMP = {\n"
    "      swing: ['combat-heavy', 0.5, 60], heavy: ['combat-heavy', 0.5, 60],\n"
    "      block: ['combat-block', 0.7, 50], parry: ['combat-parry', 0.5, 40],\n"
    "      // Patch 77.612: names with many callers that all want the same real\n"
    "      // sample get resolved here once instead of at every call site.\n"
    "      // 'win' still covers the legacy duel-round-win path (dead in the\n"
    "      // open world, see the patch docstring) -- harmless if it ever did\n"
    "      // fire, since it only upgrades the beep it already played.\n"
    "      win: ['quest-complete', 0.7, 40], switch: ['ui-switch-click', 0.35, 30],\n"
    "      freeze: ['spell-frost-freeze', 0.7, 30]\n"
    "    };\n"
    "    const cs = CSAMP[name];\n"
    "    if (cs && this._samples && this._samples.ready() && this._samples.has(cs[0])) {\n"
    "      this._samples.play(cs[0], { gain: cs[1], detune: (Math.random() * 2 - 1) * cs[2] });\n"
    "      return;\n"
    "    }\n"
    "    // Patch 77.612: names whose call-site literal IS the sample key. Every\n"
    "    // new one-off sound introduced this patch lands here once, rather\n"
    "    // than needing its own case in the synth switch below (which stays\n"
    "    // unreached for these names, so there is deliberately no fallback\n"
    "    // recipe for any of them -- they either have real audio or are\n"
    "    // silent for one frame until the decode lands, never a beep).\n"
    "    const DIRECT = {\n"
    "      'creature-notice': 0.75, 'npc-taunt-warcry': 0.7, 'goblin-shriek': 0.8,\n"
    "      'creature-windup-charge': 0.65, 'boss-leap-telegraph': 0.8,\n"
    "      'bow-draw': 0.55, 'bow-release': 0.8, 'creature-claw-swipe': 0.6,\n"
    "      'spell-snare-cast': 0.75, 'player-dodge': 0.55, 'player-jump': 0.55,\n"
    "      'heavy-impact-crash': 0.85, 'level-up': 0.7, 'spell-learned': 0.65,\n"
    "      'boss-phase-shift': 0.85, 'update-ready-chime': 0.5\n"
    "    };\n"
    "    if (DIRECT[name] !== undefined && this._samples && this._samples.ready() && this._samples.has(name)) {\n"
    "      this._samples.play(name, { gain: DIRECT[name], detune: (Math.random() * 2 - 1) * 40 });\n"
    "      return;\n"
    "    }\n"
    "    switch (name) {")
repl(old_csamp, new_csamp, 'CSAMP table extension + DIRECT sample table')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('bundle: +%d sample keys, 18 call-site/table rewrites applied' % len(NEW_KEYS))
