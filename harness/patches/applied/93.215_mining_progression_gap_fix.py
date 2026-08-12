"""
Kevin, Aug 12: "the xp you get for mining doesnt scale correctly. also by
the time i finish making full bronze and completing the first quest to
make bronze armor, im only 10 mining. then i get the quest to make iron
but im only 10 mining and the xp is very slow. stone only give 5 xp."

Traced the numbers rather than touching the curve blind (GRIM_RULES.GATHER
uses one shared XP_BASE/XP_RATE curve for MINING/WOODCUTTING/FORAGING
alike, so "mining doesn't scale" is really one specific gap, not the
formula): stone's 5xp is not a bug, it's the same tier-1 baseline as
poplar/berry (also 5xp) -- the intentional "always available everywhere,
no destination, no economy value" filler material, same shape across all
three skills. Copper/rock were already deliberately retuned to 25xp this
same session (see the comment above `rock:` a few lines up) specifically
to carry the early game -- not touching that again.

The actual gap: BRONZE BEGINNINGS (mine copper, forge 11 bronze bars into
a full helm + platebody) is the only mining content between character
creation and the very next quest, IRONS IN THE FIRE, which requires real
IRON ORE. The only node that yields IRON ORE is `ironore` below, gated at
MINING 30, Ironspire-only. Cumulative XP to reach level 30 is 9225; level
10 (where Kevin's report and a fresh grimXpTable() computation both land
after the bronze content) is 1033. That is an unexplained ~8200xp wall
sprung on the player immediately after the tutorial quests, with the
quest text itself only ever saying "MINE 10 ORE" -- no hint that the ore
in question needs 20 more levels than anything the game has asked for so
far, or that it lives in a different zone entirely.

Two surgical changes, both reversible, neither touching the curve itself
or the copper/rock numbers Kevin just tuned:

1. ironore's level gate: 30 -> 20. This lines it up with `salt` (also
   MINING 20, also Ironspire's neighbor zone Suncoast), so grinding up
   through the accessible lvl-20 tier gets you BOTH the salt economy and
   real iron access at the same checkpoint, instead of iron sitting a
   further 5700xp past salt for no stated reason. The "stone -> copper ->
   bronze -> [travel to Ironspire] -> iron" ladder from the rock/copper
   comment stays completely intact -- iron is still the far end of a real
   trip and a real grind, just not a second, much longer, silent grind
   bolted on after the first one.

2. BRONZE BEGINNINGS' flat MINING completion bonus: 60 -> 150. Matches
   the scale of the SMITHING bonus already awarded on the same line (120)
   instead of being a rounding afterthought, and puts a returning player
   meaningfully closer to the new lvl-20 iron gate right when IRONS IN
   THE FIRE is handed to them.

Net effect, worked through grimXpTable(): a player finishing the bronze
content at ~1033xp (lvl 10) plus this bonus is around 1400-1600xp; lvl 20
needs 3543. Iron access is still a real subsequent grind (roughly the
same order of magnitude as the bronze content itself), just no longer a
~3x-longer, unexplained one bolted directly onto it.

Comment at the `rock:` node above (a few lines earlier in the same
NODES table) is updated in the same edit so it doesn't go stale and
mislead the next person into thinking iron is still gated at 30.
"""

# GATHER.NODES (ironore's level gate and the rock/copper doc comment next to
# it) lives in shared-rules.js, NOT directly in the bundle: repack.py's
# pack() step (sync_rules()) re-injects shared-rules.js's actual content
# into game-src.html between the SHARED-RULES markers on every build,
# unconditionally overwriting whatever is in that stretch of game-src.html.
# Patching game-src.html's copy of GATHER.NODES only would look like it
# worked (the sub() asserts pass, the printed byte counts move) and then
# silently vanish the moment `python3 repack.py pack` runs, because pack()
# is the very last thing build.sh does before writing index.html. Found
# this the hard way: the first version of this patch edited only
# game-src.html, `bash harness/build.sh` printed a clean "applied 93.215 (3
# edits)" with no assertion failures, and the packed bundle still had
# ironore at lvl 30 -- the sub() calls were real, the file that held them
# just wasn't the one that reached the player. Edit the real source file
# instead, same exact-anchor + count-assert discipline as
# harness/patches/applied/79.030_node_collision.py's shared-rules.js edit.
RULES = 'shared-rules.js'
with open(RULES, 'r', encoding='utf-8') as f:
    rules = f.read()


def rsub(old, new, tag, count=1):
    global rules
    n = rules.count(old)
    assert n == count, f'{tag}: found {n}, wanted {count}'
    rules = rules.replace(old, new, count)


# ---- 1. keep the rock/copper doc comment accurate: it explicitly says
# "MINING 30" today, and would be actively misleading once ironore moves.
rsub(
    """      // Repointed from IRON ORE to COPPER ORE (Kevin, Aug 12): this was the
      // second of two differently-gated "iron ore" nodes (the other is
      // `ironore` below, MINING 30, Ironspire only, which stays the one true
      // iron source). Iron this early undercut the intended stone -> copper
      // -> bronze -> [travel to Ironspire] -> iron ladder, and every one of""",
    """      // Repointed from IRON ORE to COPPER ORE (Kevin, Aug 12): this was the
      // second of two differently-gated "iron ore" nodes (the other is
      // `ironore` below, MINING 20 as of the same day's progression-gap
      // fix, Ironspire only, which stays the one true iron source). Iron
      // this early undercut the intended stone -> copper -> bronze ->
      // [travel to Ironspire] -> iron ladder, and every one of""",
    'rock comment: MINING 30 -> 20 reference update',
)

# ---- 2. the actual gate: 30 -> 20, lined up with salt.
rsub(
    """      ironore:   { skill: 'MINING', lvl: 30, tool: 2, hp: 5,  xp: 150, respawn: 60,  yield: ['IRON ORE', 1, 2],
                   zones: ['IRONSPIRE'] },""",
    """      // lvl 30 -> 20 (Kevin, Aug 12: mining progression-gap fix): lines
      // iron up with salt at the same checkpoint instead of a further
      // ~5700xp past it -- see harness/patches for the full writeup.
      ironore:   { skill: 'MINING', lvl: 20, tool: 2, hp: 5,  xp: 150, respawn: 60,  yield: ['IRON ORE', 1, 2],
                   zones: ['IRONSPIRE'] },""",
    'ironore: lvl 30 -> 20',
)

with open(RULES, 'w', encoding='utf-8') as f:
    f.write(rules)

# ---- 3. bigger completion bonus, scaled to match the SMITHING award on the
# same line. This one IS a normal game-src.html edit: tryTalk()'s quest
# logic lives in the main game class body, well outside the SHARED-RULES
# markers, so a plain sub() against game-src.html is correct here and
# survives packing untouched.
PATH = '/tmp/game-src.html'
with open(PATH, 'r', encoding='utf-8') as f:
    text = f.read()


def sub(old, new, tag, count=1):
    global text
    n = text.count(old)
    assert n == count, f'{tag}: found {n}, wanted {count}'
    text = text.replace(old, new, count)


sub(
    """        q.stage = -1; this.awardXp('SMITHING', 120); this.awardXp('MINING', 60); this.grantItem('TESLA PAYCHECK', 2);""",
    """        q.stage = -1; this.awardXp('SMITHING', 120); this.awardXp('MINING', 150); this.grantItem('TESLA PAYCHECK', 2);""",
    'BRONZE BEGINNINGS: MINING completion bonus 60 -> 150',
)

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(text)

print('applied 93.215 (2 shared-rules.js edits + 1 game-src.html edit)')
