"""
Kevin, Aug 12 (same day as 93.215's mining progression-gap fix): "make
stone 20xp and make copper 45 and make iron like 75 for now."

Pure XP-value retune, nothing else touches. Four numbers change, all in
GRIM_RULES.GATHER.NODES:

  stone    xp   5 -> 20
  copper   xp  25 -> 45
  rock     xp  25 -> 45  (not explicitly named, but `rock`'s own comment
                          from earlier the same day says "xp matches
                          `copper` below so the same item pays the same
                          rate everywhere" -- rock and copper both yield
                          COPPER ORE, so leaving rock at the old 25 would
                          break that same-day invariant and pay COPPER ORE
                          two different rates depending on which of the 16
                          rocks you hit. Moving both keeps it true.)
  ironore  xp 150 -> 75  ("like 75 for now" -- Kevin flagged this as a
                          rough number to revisit, not a final call)

lvl/tool/hp/respawn/yield/zones are untouched on all four nodes. ironore's
lvl stays at 20 (that was the actual level-gate fix from 93.215, a
different axis from this xp retune and not something Kevin asked to
touch here).

GATHER.NODES lives in shared-rules.js, not game-src.html directly: see
93.215's writeup for the sync_rules()-overwrite gotcha this project has
hit twice now. All four edits below go straight into shared-rules.js with
the same exact-anchor + count-assert discipline.
"""

RULES = 'shared-rules.js'
with open(RULES, 'r', encoding='utf-8') as f:
    rules = f.read()


def rsub(old, new, tag, count=1):
    global rules
    n = rules.count(old)
    assert n == count, f'{tag}: found {n}, wanted {count}'
    rules = rules.replace(old, new, count)


# ---- 1. rock: xp 25 -> 45 (kept in lockstep with copper, per its own
# same-day comment a few lines above it).
rsub(
    "      rock:      { skill: 'MINING',      lvl: 1,  tool: 1, hp: 4,  xp: 25,  respawn: 60,  yield: ['COPPER ORE', 2, 2],  legacy: true },",
    "      rock:      { skill: 'MINING',      lvl: 1,  tool: 1, hp: 4,  xp: 45,  respawn: 60,  yield: ['COPPER ORE', 2, 2],  legacy: true },",
    'rock: xp 25 -> 45',
)

# ---- 2. stone: xp 5 -> 20.
rsub(
    "      stone:     { skill: 'MINING', lvl: 1,  tool: 1, hp: 3,  xp: 5,   respawn: 60,  yield: ['LOOSE STONE', 1, 2],",
    "      stone:     { skill: 'MINING', lvl: 1,  tool: 1, hp: 3,  xp: 20,  respawn: 60,  yield: ['LOOSE STONE', 1, 2],",
    'stone: xp 5 -> 20',
)

# ---- 3. copper: xp 25 -> 45.
rsub(
    "      copper:    { skill: 'MINING', lvl: 1,  tool: 1, hp: 3,  xp: 25,  respawn: 60,  yield: ['COPPER ORE', 1, 2],",
    "      copper:    { skill: 'MINING', lvl: 1,  tool: 1, hp: 3,  xp: 45,  respawn: 60,  yield: ['COPPER ORE', 1, 2],",
    'copper: xp 25 -> 45',
)

# ---- 4. ironore: xp 150 -> 75 (lvl stays 20, untouched).
rsub(
    "      ironore:   { skill: 'MINING', lvl: 20, tool: 2, hp: 5,  xp: 150, respawn: 60,  yield: ['IRON ORE', 1, 2],",
    "      ironore:   { skill: 'MINING', lvl: 20, tool: 2, hp: 5,  xp: 75,  respawn: 60,  yield: ['IRON ORE', 1, 2],",
    'ironore: xp 150 -> 75',
)

with open(RULES, 'w', encoding='utf-8') as f:
    f.write(rules)

print('applied 44.807 (4 shared-rules.js edits)')
