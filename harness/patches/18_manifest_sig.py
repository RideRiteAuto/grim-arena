#!/usr/bin/env python3
"""The world manifest carries species, signature and kin tags to the server.

The manifest is what the client tells the relay about every monster in the
world, and the server simulation builds its roster from it. It copied the
combat flags but not `sig`, `zoneSpecies` or the kin tags, so a server-run boar
had no idea it was a boar: no signature move, and nothing for a goblin's shriek
to call to.
"""
import io
SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
OLD = ("      if (n.king) s.king = 1;\n"
       "      return s;")
NEW = ("      if (n.king) s.king = 1;\n"
       "      // Species, signature and kin tags. Without these a server-run monster\n"
       "      // is an anonymous stat block: it cannot throw its own signature move,\n"
       "      // and a shriek has no way to tell which of its neighbours are goblins.\n"
       "      if (n.sig) s.sig = n.sig;\n"
       "      if (n.zoneSpecies) s.zoneSpecies = n.zoneSpecies;\n"
       "      if (n.homeR != null) s.homeR = n.homeR;\n"
       "      for (const tag of ['goblin', 'wolf', 'rat', 'boar', 'bandit']) if (n[tag]) s[tag] = 1;\n"
       "      return s;")
assert src.count(OLD) == 1, 'anchor not unique'
out = src.replace(OLD, NEW, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('manifest carries species and signature, %d -> %d bytes' % (len(src), len(out)))
