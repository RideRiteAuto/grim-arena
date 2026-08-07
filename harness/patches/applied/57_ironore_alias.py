# Patch 57: zone iron veins use the iron nugget identity.
# The zone resource kind is 'ironore' but the ORES identity table keys it as
# 'iron', so IRONSPIRE veins fell through to the generic stone lump - the one
# thing the per-ore identity work was for. Alias ironore (and rock, for
# safety) to iron at the lookup. Same line fixed in model-lab/orenode.js.
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()

old = "const O = ORES[o.kind || 'iron'] || ORES.stone;"
new = "const O = ORES[{ ironore: 'iron', rock: 'iron' }[o.kind] || o.kind || 'iron'] || ORES.stone;"
n = s.count(old)
assert n == 1, 'ORES lookup anchor found %d times' % n
s = s.replace(old, new)
print('  ok: ironore/rock alias to the iron identity')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 57 applied')
