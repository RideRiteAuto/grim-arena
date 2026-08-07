"""Recovery patch: restore patch 77.612 (legacy sound sweep) into the bundle
after it got clobbered by the locomotion overhaul push.

What happened: the locomotion patches (73.140/73.260/73.375/73.480) were
built and harness-tested against origin commit c55d826. Between that fetch
and the actual GitHub upload-form commit landing, a different track pushed
ade2e2e (patch 77.612, legacy sound sweep - 19 new sample keys + 18 call-site
rewrites). The locomotion push uploaded whole-file index.html/
grim-arena-standalone.html built from the STALE c55d826 base, which silently
reverted ade2e2e's bundle changes the moment it landed (d783aa1). This patch
puts 77.612's bundle-side changes back on top of the current (locomotion-
included) bundle, so both land together with nothing lost.

77.612's own script (harness/patches/applied/77.612_legacy_sound_sweep.py)
can't be replayed as-is here: it derives its 19 sample payloads from raw mp3
files under /tmp/sfx74/final, generated in a different session/sandbox that
no longer exists in this one. Those payloads don't need regenerating though -
they already landed safely in model-lab/sfx-samples.js (a non-bundle file,
untouched by the clobber, still on disk from the merge). This patch extracts
the exact same base64 block from that file (byte-identical to what 77.612
computed and inserted there) and re-inserts it into the bundle's SFX_SAMPLES
object, then replays every one of 77.612's non-audio call-site/table
substitutions verbatim from that script - those never depended on the mp3s
in the first place.
"""
import io

SRC = '/tmp/game-src.html'
MODULE = 'model-lab/sfx-samples.js'

s = io.open(SRC, encoding='utf-8').read()
assert "'creature-notice':" not in s, 'patch 77.612 already present in bundle - nothing to restore'

# ------------------------------------------------------------------
# 1. Pull the exact same base64 block 77.612 already inserted into
#    model-lab/sfx-samples.js (untouched by the clobber) and re-inject it
#    into the bundle's SFX_SAMPLES object, same anchor 77.612 itself used.
# ------------------------------------------------------------------
mod = io.open(MODULE, encoding='utf-8').read()
first_key_marker = "  'creature-notice':"
close_marker = '\n};\n'
a = mod.index(first_key_marker)
b = mod.index(close_marker, a)
new_block = mod[a:b]
assert new_block.startswith("  'creature-notice':") and new_block.rstrip().endswith(',')

sfx_start = s.index('const SFX_SAMPLES = {')
sfx_close = s.index('\n    };', sfx_start)
s = s[:sfx_close] + '\n' + new_block + s[sfx_close:]
assert "'creature-notice':" in s

# ------------------------------------------------------------------
# 2. Every non-audio substitution from 77.612's own script, verbatim.
# ------------------------------------------------------------------

def repl(old, new, label, count=1):
    global s
    n = s.count(old)
    assert n == count, '%s: expected %d occurrence(s), found %d' % (label, count, n)
    s = s.replace(old, new, count)

repl(
    "if (now - (e._aggroSfxAt || -99) > L.MIN_AGGRO_GAP) { e._aggroSfxAt = now; this.sfx('tick'); }",
    "if (now - (e._aggroSfxAt || -99) > L.MIN_AGGRO_GAP) { e._aggroSfxAt = now; this.sfx('creature-notice'); }",
    'aggro tick')

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

repl("    this.sfx('arrow');\n  }", "    this.sfx('bow-release');\n  }", 'bow release')

repl(
    "claw: 'slash', bite: 'slash',\n      rapid: 'draw', volley: 'draw',\n"
    "      frost: null,              /* fireFrost() sounds the release, not the wind up */\n"
    "      snare: 'cast', storm: 'sp-storm-cast',",
    "claw: 'creature-claw-swipe', bite: 'creature-claw-swipe',\n"
    "      rapid: 'bow-draw', volley: 'bow-draw',\n"
    "      frost: null,              /* fireFrost() sounds the release, not the wind up */\n"
    "      snare: 'spell-snare-cast', storm: 'sp-storm-cast',",
    'MSFX table (claw/bite/rapid/volley/snare)')

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

repl(
    "e.specialCd = 6 + Math.random() * 4;\n    this.sfx('dodge');\n  }\n\n  startCharge(e, target) {",
    "e.specialCd = 6 + Math.random() * 4;\n    this.sfx('boss-leap-telegraph');\n  }\n\n  startCharge(e, target) {",
    'startLeap windup')

repl(
    "if (a.name === 'slam') { this.shake = Math.min(1, this.shake + 0.7); "
    "this.spark(e.pos.clone().add(new this.T.Vector3(0, 0.3, 0)), 0x8fef5a, 20); this.sfx('break'); }",
    "if (a.name === 'slam') { this.shake = Math.min(1, this.shake + 0.7); "
    "this.spark(e.pos.clone().add(new this.T.Vector3(0, 0.3, 0)), 0x8fef5a, 20); this.sfx('heavy-impact-crash'); }",
    'slam impact')

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

repl(
    "this._updDeadline = performance.now() + 150000;   // 30s + 2min of combat grace\n"
    "    this.buildUpdateBanner();\n"
    "    this.sfx('horn');",
    "this._updDeadline = performance.now() + 150000;   // 30s + 2min of combat grace\n"
    "    this.buildUpdateBanner();\n"
    "    this.sfx('update-ready-chime');",
    'update-ready banner')

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
print('77.612 restored into bundle after locomotion-push clobber')
